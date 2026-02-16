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
from datetime import datetime, timezone
from collections import defaultdict


# Store results per variant
_test_results = defaultdict(list)
_test_metadata = {}


def _is_xdist_worker(config):
    """Check if we're running as an xdist worker."""
    return hasattr(config, 'workerinput')


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--model",
        action="store",
        default="gpt-5-mini",
        choices=["gpt-5-mini", "claude-4.5-sonnet", "gemini-2.5-flash"],
        help="Model to use for testing (default: gpt-5-mini)"
    )


def pytest_configure(config):
    """Set up base test run ID and load scenarios once at startup."""
    # Get model name from CLI option
    model_label = config.getoption("--model")

    # Generate a human-readable timestamp in UTC
    timestamp = datetime.now(timezone.utc).strftime('%b%d-%H%MZ')  # e.g., Dec03-1430Z
    base_uid = f"oneday-{model_label}-{timestamp}"
    config.base_testrun_uid = base_uid
    config.model_name = model_label
    config.timestamp = timestamp

    # Store metadata for final report
    _test_metadata["model"] = model_label
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
    node.workerinput["timestamp"] = node.config.timestamp
    # Serialize scenarios to JSON for worker
    node.workerinput["scenarios"] = json.dumps(node.config._scenarios)


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

        # Extract timing data from user_properties
        props = dict(report.user_properties) if hasattr(report, 'user_properties') else {}

        _test_results[variant].append({
            "case": case_num,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "total_time": props.get("total_time"),
            "agent_time": props.get("agent_time"),
            "prompt_tokens": props.get("prompt_tokens"),
            "completion_tokens": props.get("completion_tokens"),
            "cost": props.get("cost"),
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

    for variant in ["standard", "diagnosis_only"]:
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
            json_data["variants"][variant] = {
                "cases": results,
                "total_time_stats": _compute_timing_stats(total_times),
                "agent_time_stats": _compute_timing_stats(agent_times),
                "total_prompt_tokens": sum(prompt_tok) if prompt_tok else 0,
                "total_completion_tokens": sum(completion_tok) if completion_tok else 0,
                "total_cost": sum(costs) if costs else 0,
            }
        json_path = os.path.join(json_output_dir, f"{model}.json")
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)


# Model name mapping: friendly name -> litellm model ID
MODEL_MAPPING = {
    "gpt-5-mini": "openai/gpt-5-mini",
    "claude-4.5-sonnet": "anthropic/claude-sonnet-4.5-20250929",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
}


@pytest.fixture(scope="session")
def model_id(request):
    """Get the litellm model ID for the selected model."""
    # Get model name from config or worker input
    if hasattr(request.config, "workerinput"):
        model_name = request.config.workerinput["model_name"]
    else:
        model_name = request.config.model_name

    return MODEL_MAPPING[model_name]


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
        metafunc.parametrize(
            'test_scenario',
            scenarios,
            ids=lambda s: f"case_{s['case_number']}"
        )
