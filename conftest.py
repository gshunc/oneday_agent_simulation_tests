"""
pytest configuration for OneDay agent testing with pytest-xdist support.

Uses pytest hooks to share testrun_uid across parallel workers, with separate

Doc extraction runs ONCE in the main process and scenarios are passed to workers
to avoid redundant API calls and cache race conditions.
"""

import pytest
import json
import re
import math
import os
import requests
import litellm
from litellm.types.utils import ModelResponse, Usage
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()


# Store results per variant
_test_results = defaultdict(list)
_test_metadata = {}
_completed_count = 0
_total_count = 0


def compute_usage_from_traces(trace_ids: list[str]) -> dict:
    """Fetch LangWatch traces and compute total token usage, cost, and per-agent LLM timing."""
    langwatch_api_key = os.getenv("LANGWATCH_API_KEY")
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    agent_llm_ms = 0
    judge_llm_ms = 0
    user_sim_llm_ms = 0

    for trace_id in trace_ids:
        try:
            response = requests.get(
                f"https://app.langwatch.ai/api/traces/{trace_id}",
                headers={"X-Auth-Token": langwatch_api_key},
            )
            if response.status_code != 200:
                continue
            trace = response.json()
        except Exception:
            continue

        spans_by_id = {s["span_id"]: s for s in trace.get("spans", [])}

        for span in trace.get("spans", []):
            if span.get("type") != "llm":
                continue
            metrics = span.get("metrics") or {}
            model = span.get("model", "")
            prompt_tokens = metrics.get("prompt_tokens") or 0
            completion_tokens = metrics.get("completion_tokens") or 0
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            try:
                mock_response = ModelResponse(
                    model=model,
                    usage=Usage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                )
                total_cost += litellm.completion_cost(  # type: ignore[attr-defined]
                    completion_response=mock_response,
                    model=model,
                )
            except Exception:
                pass  # Model not in litellm pricing table

            # Per-agent LLM timing via parent span name
            ts = span.get("timestamps") or {}
            started = ts.get("started_at")
            finished = ts.get("finished_at")
            if started and finished:
                duration_ms = finished - started
                parent_id = span.get("parent_id")
                parent_name = (spans_by_id.get(parent_id) or {}).get("name", "") if parent_id else ""
                if "UserSimulator" in parent_name:
                    user_sim_llm_ms += duration_ms
                elif "Judge" in parent_name:
                    judge_llm_ms += duration_ms
                else:
                    agent_llm_ms += duration_ms

    return {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "cost": total_cost,
        "agent_llm_ms": agent_llm_ms,
        "judge_llm_ms": judge_llm_ms,
        "user_sim_llm_ms": user_sim_llm_ms,
    }


def _is_xdist_worker(config):
    """Check if we're running as an xdist worker."""
    return hasattr(config, 'workerinput')


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--model",
        action="store",
        default="gpt-5-mini",
        choices=[
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            "gpt-5.2",
            "gpt-5-mini",
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
        ],
        help="Model to use for testing (default: gpt-5-mini)"
    )
    parser.addoption(
        "--turn",
        action="store_true",
        default=False,
        help="Use the Turn.io simulation API instead of calling the model directly"
    )
    parser.addoption(
        "--turn-uuid",
        action="store",
        default=None,
        metavar="UUID",
        help="Turn.io journey UUID to use (overrides TURN_JOURNEY_UUID env var; auto-enables --turn)",
    )
    parser.addoption(
        "--max-cases",
        action="store",
        type=int,
        default=None,
        metavar="N",
        help="Only run the first N test cases (by case order)",
    )


def pytest_configure(config):
    """Set up base test run ID and load scenarios once at startup."""
    # Get model name from CLI option
    model_label = config.getoption("--model")
    turn_uuid_arg = config.getoption("--turn-uuid", default=None)
    use_turn = config.getoption("--turn") or bool(turn_uuid_arg)

    # Generate a human-readable timestamp in UTC
    timestamp = datetime.now(timezone.utc).strftime('%b%d-%H%MZ')  # e.g., Dec03-1430Z
    if turn_uuid_arg:
        run_label = f"turn-{turn_uuid_arg[:8]}"
    elif use_turn:
        run_label = "turn"
    else:
        run_label = model_label
    base_uid = f"oneday-{run_label}-{timestamp}"
    config.base_testrun_uid = base_uid
    config.model_name = model_label
    config.use_turn = use_turn
    config.turn_uuid = turn_uuid_arg  # None when not provided; env var fallback stays in the test
    config.timestamp = timestamp

    # Store metadata for final report
    _test_metadata["model"] = run_label
    _test_metadata["timestamp"] = timestamp

    # Load scenarios - only in main process, workers get them via workerinput
    if not _is_xdist_worker(config):
        # Main process: run doc extraction once
        from doc_extraction.doc_to_scenarios import doc_to_scenarios
        scenarios = doc_to_scenarios()
        config._scenarios = scenarios
        print(f"✓ Loaded {len(scenarios)} scenarios from Google Doc (main process)")
    else:
        # Worker process: deserialize scenarios from workerinput
        config._scenarios = json.loads(config.workerinput['scenarios'])


def pytest_configure_node(node):
    """Pass the base testrun_uid, model, and scenarios to each xdist worker."""
    node.workerinput["base_testrun_uid"] = node.config.base_testrun_uid
    node.workerinput["model_name"] = node.config.model_name
    node.workerinput["use_turn"] = str(node.config.use_turn)
    node.workerinput["turn_uuid"] = node.config.turn_uuid or ""
    node.workerinput["timestamp"] = node.config.timestamp
    # Serialize scenarios to JSON for worker
    node.workerinput["scenarios"] = json.dumps(node.config._scenarios)


def pytest_collection_modifyitems(items):
    """Store total test count after collection."""
    global _total_count
    _total_count = len(items)


def pytest_report_teststatus(report, config):
    """Override test status characters to show colored progress numbers."""
    global _completed_count
    if report.when == "call":
        _completed_count += 1
        label = f" {_completed_count}"
        if report.passed:
            return "passed", label, "PASSED"
        elif report.failed:
            return "failed", label, "FAILED"
        elif report.skipped:
            return "skipped", label, "SKIPPED"


def pytest_runtest_logreport(report):
    """Collect test results as they complete."""
    if report.when == "call":
        # Extract variant and case number from test name
        test_name = report.nodeid

        if "diagnosis_only" in test_name:
            variant = "diagnosis_only"
        elif "standard" in test_name:
            variant = "standard"
        else:
            return

        # Extract case number from test id (e.g., "case_1" -> 1)
        case_match = re.search(r'case_(\d+)', test_name)
        case_num = int(case_match.group(1)) if case_match else 0

        # Extract timing data and trace_ids from user_properties
        props = dict(report.user_properties) if hasattr(report, 'user_properties') else {}
        trace_ids_str = props.get("trace_ids", "")
        trace_ids = [t for t in trace_ids_str.split(",") if t] if trace_ids_str else []

        turn_agent_prompt = props.get("turn_agent_prompt_tokens")
        if turn_agent_prompt is not None:
            # Turn runs: only count OneDay agent tokens (production metric).
            # LangWatch is used solely for timing breakdown (Judge/UserSimulator overhead).
            lw = compute_usage_from_traces(trace_ids)
            usage = {
                "prompt_tokens": int(turn_agent_prompt),
                "completion_tokens": int(props.get("turn_agent_completion_tokens", 0)),
                "cost": 0.0,
                "agent_llm_ms": lw["agent_llm_ms"],
                "judge_llm_ms": lw["judge_llm_ms"],
                "user_sim_llm_ms": lw["user_sim_llm_ms"],
            }
        else:
            usage = compute_usage_from_traces(trace_ids)

        _test_results[variant].append({
            "case": case_num,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "total_time": props.get("total_time"),
            "agent_time": props.get("agent_time"),
            "prompt_tokens": usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"],
            "cost": usage["cost"],
            "agent_llm_ms": usage["agent_llm_ms"],
            "judge_llm_ms": usage["judge_llm_ms"],
            "user_sim_llm_ms": usage["user_sim_llm_ms"],
            "trace_id": trace_ids[0] if trace_ids else None,
        })


def _compute_timing_stats(values):
    """Compute avg, min, max, and p90 for a list of numeric values."""
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    avg = sum(values) / n
    stdev = math.sqrt(sum((v - avg) ** 2 for v in values) / n)
    p90_idx = int(n * 0.9)
    # For small lists, p90 is the last element
    p90 = values[min(p90_idx, n - 1)]
    return {
        "avg": avg,
        "stdev": stdev,
        "min": values[0],
        "max": values[-1],
        "p90": p90,
    }


def _format_timing_stats(stats):
    """Format timing stats dict into a readable string."""
    return f"avg={stats['avg']:.1f}s  stdev={stats['stdev']:.1f}s  min={stats['min']:.1f}s  max={stats['max']:.1f}s  p90={stats['p90']:.1f}s"


def pytest_sessionfinish(session, exitstatus):
    """Print formatted results summary at the end of the test run."""
    if not _test_results:
        return

    model = _test_metadata.get("model", "unknown")
    timestamp = _test_metadata.get("timestamp", "unknown")

    separator = "═" * 60

    print(f"\n\n{separator}")
    print(f"  TEST RESULTS SUMMARY")
    print(f"  Model: {model}  |  Time: {timestamp}")
    print(separator)

    for variant in ["standard"]:
        results = _test_results.get(variant, [])
        if not results:
            continue

        # Sort by case number
        results.sort(key=lambda x: x["case"])

        passed = sum(1 for r in results if r["passed"])
        failed = sum(1 for r in results if r["failed"])
        skipped = sum(1 for r in results if r["skipped"])
        total = len(results)

        print(f"\n  {variant.upper()} TESTS ({passed}/{total} passed)")
        print(f"  {'-' * 40}")

        for r in results:
            case_num = r["case"]
            if r["passed"]:
                status = "✓ PASS"
            elif r["failed"]:
                status = "✗ FAIL"
            else:
                status = "○ SKIP"

            timing_str = ""
            if r.get("total_time") is not None:
                timing_str += f"  total={r['total_time']:.1f}s"
            if r.get("agent_time") is not None:
                timing_str += f"  agent={r['agent_time']:.1f}s"
            if r.get("prompt_tokens") is not None:
                tokens = (r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0)
                timing_str += f"  tokens={tokens}"
            if r.get("cost") is not None:
                timing_str += f"  cost=${r['cost']:.4f}"

            print(f"    Case {case_num:3d}: {status}{timing_str}")

        print(f"  {'-' * 40}")
        print(f"  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")

        # Timing statistics
        total_times = [r["total_time"] for r in results if r.get("total_time") is not None]
        agent_times = [r["agent_time"] for r in results if r.get("agent_time") is not None]

        prompt_tokens = [r["prompt_tokens"] for r in results if r.get("prompt_tokens") is not None]
        completion_tokens = [r["completion_tokens"] for r in results if r.get("completion_tokens") is not None]

        if total_times:
            total_stats = _compute_timing_stats(total_times)
            print(f"\n  Total time:  {_format_timing_stats(total_stats)}")
        if agent_times:
            agent_stats = _compute_timing_stats(agent_times)
            print(f"  Agent time:  {_format_timing_stats(agent_stats)}")
        costs = [r["cost"] for r in results if r.get("cost") is not None]

        if prompt_tokens:
            total_prompt = sum(prompt_tokens)
            total_completion = sum(completion_tokens)
            print(f"\n  Agent tokens:  prompt={total_prompt}  completion={total_completion}  total={total_prompt + total_completion}")
        if costs:
            print(f"  Agent cost:   ${sum(costs):.4f}")

        agent_llm_ms = [r["agent_llm_ms"] for r in results if r.get("agent_llm_ms")]
        judge_llm_ms = [r["judge_llm_ms"] for r in results if r.get("judge_llm_ms")]
        user_sim_llm_ms = [r["user_sim_llm_ms"] for r in results if r.get("user_sim_llm_ms")]
        if agent_llm_ms or judge_llm_ms or user_sim_llm_ms:
            def fmt_s(ms_list): return f"{sum(ms_list)/1000:.1f}s (avg {sum(ms_list)/len(ms_list)/1000:.1f}s)"
            print(f"\n  LLM time breakdown (total across all cases, avg per case):")
            if agent_llm_ms:
                print(f"    Agent:    {fmt_s(agent_llm_ms)}")
            if judge_llm_ms:
                print(f"    Judge:    {fmt_s(judge_llm_ms)}")
            if user_sim_llm_ms:
                print(f"    User sim: {fmt_s(user_sim_llm_ms)}")

    print(f"\n{separator}\n")

    # Write JSON results file for orchestration tooling
    json_output_dir = os.environ.get("ONEDAY_RESULTS_DIR")
    if json_output_dir:
        os.makedirs(json_output_dir, exist_ok=True)
        json_data = {
            "model": model,
            "timestamp": timestamp,
            "variants": {},
        }
        for variant in ["standard", "diagnosis_only"]:
            results = _test_results.get(variant, [])
            if not results:
                continue
            results.sort(key=lambda x: x["case"])
            total_times = [r["total_time"] for r in results if r.get("total_time") is not None]
            agent_times = [r["agent_time"] for r in results if r.get("agent_time") is not None]
            prompt_tok = [r["prompt_tokens"] for r in results if r.get("prompt_tokens") is not None]
            completion_tok = [r["completion_tokens"] for r in results if r.get("completion_tokens") is not None]
            costs = [r["cost"] for r in results if r.get("cost") is not None]
            agent_llm_ms = [r["agent_llm_ms"] for r in results if r.get("agent_llm_ms")]
            judge_llm_ms = [r["judge_llm_ms"] for r in results if r.get("judge_llm_ms")]
            user_sim_llm_ms = [r["user_sim_llm_ms"] for r in results if r.get("user_sim_llm_ms")]
            json_data["variants"][variant] = {
                "cases": results,
                "total_time_stats": _compute_timing_stats(total_times),
                "agent_time_stats": _compute_timing_stats(agent_times),
                "total_prompt_tokens": sum(prompt_tok) if prompt_tok else 0,
                "total_completion_tokens": sum(completion_tok) if completion_tok else 0,
                "total_cost": sum(costs) if costs else 0,
                "total_agent_llm_ms": sum(agent_llm_ms) if agent_llm_ms else 0,
                "total_judge_llm_ms": sum(judge_llm_ms) if judge_llm_ms else 0,
                "total_user_sim_llm_ms": sum(user_sim_llm_ms) if user_sim_llm_ms else 0,
            }
        json_path = os.path.join(json_output_dir, f"{model}.json")
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)


# Model name mapping: friendly name -> litellm model ID
MODEL_MAPPING = {
    "claude-opus-4-6": "anthropic/claude-opus-4-6",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4-6",
    "claude-haiku-4-5": "anthropic/claude-haiku-4-5",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-5-mini": "openai/gpt-5-mini",
    "gemini-3-pro-preview": "google/gemini-3-pro-preview",
    "gemini-3-flash-preview": "google/gemini-3-flash-preview",
}


@pytest.fixture(scope="session")
def model_id(request):
    """Get the litellm model ID for the selected model."""
    if hasattr(request.config, "workerinput"):
        model_name = request.config.workerinput["model_name"]
    else:
        model_name = request.config.model_name
    return MODEL_MAPPING[model_name]


@pytest.fixture(scope="session")
def use_turn(request):
    """Whether to use the Turn.io simulation API instead of calling the model directly."""
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput["use_turn"] == "True"
    return request.config.use_turn


@pytest.fixture(scope="session")
def turn_journey_uuid(request):
    """Turn.io journey UUID from --turn-uuid CLI arg, or None if not provided.

    When None, the test falls back to TURN_JOURNEY_UUID env var (existing behaviour).
    When set, the env var is ignored — the CLI arg takes exclusive precedence.
    """
    if hasattr(request.config, "workerinput"):
        val = request.config.workerinput.get("turn_uuid", "")
        return val or None
    return request.config.turn_uuid


@pytest.fixture(scope="session", autouse=True)
def configure_scenario(model_id):
    """Configure scenario with the selected model before running any tests."""
    import scenario

    scenario.configure(
        default_model=model_id,
        max_turns=10,
        verbose=True,
        headless=True,  # Don't open browser tabs
    )


@pytest.fixture(scope="function")
def testrun_uid(request):
    """
    Generate test run UID that's unique per test variant.

    Standard and diagnosis_only tests get different UIDs so they appear
    as separate runs in LangWatch, but all tests of the same variant share the same UID.
    """
    # Get base UID from config or worker input
    if hasattr(request.config, "workerinput"):
        base_uid = request.config.workerinput["base_testrun_uid"]
    else:
        base_uid = request.config.base_testrun_uid

    # Determine test variant from test function name
    test_name = request.node.name
    if "diagnosis_only" in test_name:
        variant = "diagnosis_only"
    elif "standard" in test_name:
        variant = "standard"
    else:
        variant = "unknown"

    return f"{base_uid}-{variant}"


def pytest_generate_tests(metafunc):
    """
    Dynamically parametrize tests with scenarios loaded from Google Doc.

    This runs during test collection and uses scenarios loaded in pytest_configure,
    avoiding module-level imports that would cause each xdist worker to re-fetch.
    """
    if 'test_scenario' in metafunc.fixturenames:
        scenarios = metafunc.config._scenarios
        max_cases = metafunc.config.getoption("--max-cases")
        if max_cases is not None:
            scenarios = scenarios[:max_cases]
        metafunc.parametrize(
            'test_scenario',
            scenarios,
            ids=lambda s: f"case_{s['case_number']}"
        )
