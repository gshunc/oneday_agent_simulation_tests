#!/usr/bin/env python3
"""
Cross-model test orchestrator for OneDay agent evaluation.

Runs the full test suite against all three model providers (OpenAI, Anthropic, Google),
collects statistics, and generates an HTML report that opens automatically.

Usage:
    python run_all_models.py                    # Run all models
    python run_all_models.py --models gpt-5-mini claude-opus-4-6  # Run specific models
    python run_all_models.py --variant standard  # Only run standard tests
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

ALL_MODELS = [
    # "claude-opus-4-6",
    # "claude-sonnet-4-6",
    # "claude-haiku-4-5",
    "gpt-5.2",
    "gpt-5-mini",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
]
PROJECT_ROOT = Path(__file__).parent


def run_model_tests(model: str, results_dir: str, variant: str | None = None) -> int:
    """Run pytest for a single model and return the exit code."""
    cmd = [
        sys.executable, "-m", "pytest",
        "-n", "auto",
        "--model", model,
        "test_oneday_evaluation.py",
    ]
    if variant:
        cmd += ["-k", variant]

    env = {**os.environ, "ONEDAY_RESULTS_DIR": results_dir}

    print(f"\n{'=' * 60}")
    print(f"  Running tests: {model}")
    print(f"{'=' * 60}\n")

    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=False,
    )
    return proc.returncode


def run_turn_tests(turn_uuid: str, results_dir: str, max_cases: int | None = None, variant: str = "diagnosis_only") -> int:
    """Run pytest for a single Turn.io journey UUID and return the exit code."""
    if max_cases is not None:
        case_ids = " or ".join(f"[case_{i}]" for i in range(1, max_cases + 1))
        k_expr = f"{variant} and ({case_ids})"
    else:
        k_expr = variant

    cmd = [
        sys.executable, "-m", "pytest",
        "-n", "auto",
        "--turn-uuid", turn_uuid,
        "-k", k_expr,
        "test_oneday_evaluation.py",
    ]

    env = {**os.environ, "ONEDAY_RESULTS_DIR": results_dir}

    print(f"\n{'=' * 60}")
    print(f"  Running turn journey: {turn_uuid}")
    print(f"{'=' * 60}\n")

    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=False,
    )
    return proc.returncode


def load_results(results_dir: str) -> dict:
    """Load all JSON result files from the results directory."""
    results = {}
    results_path = Path(results_dir)
    for json_file in sorted(results_path.glob("*.json")):
        with open(json_file) as f:
            data = json.load(f)
        results[data["model"]] = data
    return results


def generate_html_report(all_results: dict, output_path: str) -> str:
    """Generate an HTML comparison report from all model results."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build per-model summary data for the template
    model_summaries = []
    # Collect all case numbers across all models/variants
    all_cases = set()
    for model, data in all_results.items():
        for variant, vdata in data.get("variants", {}).items():
            for case in vdata.get("cases", []):
                all_cases.add(case["case"])
    all_cases = sorted(all_cases)

    for model, data in all_results.items():
        for variant in ["standard", "diagnosis_only"]:
            vdata = data.get("variants", {}).get(variant)
            if not vdata:
                continue
            cases = vdata["cases"]
            passed = sum(1 for c in cases if c["passed"])
            failed = sum(1 for c in cases if c["failed"])
            total = len(cases)
            model_summaries.append({
                "model": model,
                "variant": variant,
                "passed": passed,
                "failed": failed,
                "total": total,
                "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
                "total_time_stats": vdata.get("total_time_stats"),
                "agent_time_stats": vdata.get("agent_time_stats"),
                "total_prompt_tokens": vdata.get("total_prompt_tokens", 0),
                "total_completion_tokens": vdata.get("total_completion_tokens", 0),
                "total_cost": vdata.get("total_cost", 0),
                "total_agent_llm_ms": vdata.get("total_agent_llm_ms", 0),
                "total_judge_llm_ms": vdata.get("total_judge_llm_ms", 0),
                "total_user_sim_llm_ms": vdata.get("total_user_sim_llm_ms", 0),
                "cases": {c["case"]: c for c in cases},
            })

    # Build the HTML
    html = _build_html(timestamp, model_summaries, all_cases, all_results)

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def _status_badge(case_data: dict | None) -> str:
    """Return a simple status string for a test case."""
    if case_data is None:
        return '<span class="skip">-</span>'
    if case_data.get("passed"):
        return '<span class="pass">PASS</span>'
    if case_data.get("failed"):
        return '<span class="fail">FAIL</span>'
    return '<span class="skip">SKIP</span>'


def _fmt_time(val: float | None) -> str:
    if val is None:
        return "-"
    return f"{val:.1f}s"


def _fmt_cost(val: float | None) -> str:
    if val is None or val == 0:
        return "-"
    return f"${val:.4f}"


def _fmt_tokens(val: int | None) -> str:
    if val is None or val == 0:
        return "-"
    return f"{val:,}"


def _stat_row(label: str, stats: dict | None) -> str:
    if not stats:
        return ""
    return f"""<tr>
        <td>&nbsp;&nbsp;{label}</td>
        <td>{stats['avg']:.1f}s</td>
        <td>{stats['min']:.1f}s</td>
        <td>{stats['max']:.1f}s</td>
        <td>{stats['p90']:.1f}s</td>
        <td>{stats['stdev']:.1f}s</td>
    </tr>"""


MODEL_DISPLAY_NAMES = {
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "gpt-5.2": "GPT-5.2",
    "gpt-5-mini": "GPT-5 Mini",
    "gemini-3-pro-preview": "Gemini 3 Pro",
    "gemini-3-flash-preview": "Gemini 3 Flash",
}


def _build_html(timestamp: str, model_summaries: list, all_cases: list, all_results: dict) -> str:
    # --- Summary list per model ---
    summary_section = ""
    models_seen = []
    for model in all_results:
        if model in models_seen:
            continue
        models_seen.append(model)
        display = MODEL_DISPLAY_NAMES.get(model, model)

        total_passed = 0
        total_cases = 0
        total_cost = 0.0
        total_tokens = 0
        for s in model_summaries:
            if s["model"] == model:
                total_passed += s["passed"]
                total_cases += s["total"]
                total_cost += s["total_cost"]
                total_tokens += s["total_prompt_tokens"] + s["total_completion_tokens"]

        pass_rate = round(total_passed / total_cases * 100, 1) if total_cases > 0 else 0
        summary_section += f"<li><strong>{display}</strong> &mdash; {pass_rate}% pass rate ({total_passed}/{total_cases}), {_fmt_tokens(total_tokens)} tokens, {_fmt_cost(total_cost)} cost</li>\n"

    # --- Per-variant sections ---
    variant_sections = ""
    for variant in ["standard", "diagnosis_only"]:
        variant_label = "Standard" if variant == "standard" else "Diagnosis Only"
        summaries_for_variant = [s for s in model_summaries if s["variant"] == variant]
        if not summaries_for_variant:
            continue

        # Case results table
        case_header = "".join(
            f"<th>{MODEL_DISPLAY_NAMES.get(s['model'], s['model'])}</th>"
            for s in summaries_for_variant
        )
        case_rows = ""
        for case_num in all_cases:
            cells = ""
            for s in summaries_for_variant:
                case_data = s["cases"].get(case_num)
                badge = _status_badge(case_data)
                time_str = ""
                if case_data and case_data.get("total_time") is not None:
                    time_str = f' <small>({case_data["total_time"]:.1f}s)</small>'
                cells += f"<td>{badge}{time_str}</td>"
            case_rows += f"<tr><td>Case {case_num}</td>{cells}</tr>\n"

        rate_cells = "".join(f"<td><strong>{s['pass_rate']}%</strong></td>" for s in summaries_for_variant)

        # Timing stats
        timing_rows = ""
        for s in summaries_for_variant:
            display = MODEL_DISPLAY_NAMES.get(s["model"], s["model"])
            timing_rows += f'<tr><td colspan="6"><strong>{display}</strong></td></tr>'
            timing_rows += _stat_row("Total time", s["total_time_stats"])
            timing_rows += _stat_row("Agent time", s["agent_time_stats"])

        # LLM time breakdown table
        llm_rows = ""
        for s in summaries_for_variant:
            display = MODEL_DISPLAY_NAMES.get(s["model"], s["model"])
            n = s["total"] or 1
            agent_ms = s.get("total_agent_llm_ms", 0)
            judge_ms = s.get("total_judge_llm_ms", 0)
            usersim_ms = s.get("total_user_sim_llm_ms", 0)
            def fmt_ms(ms, n):
                return f"{ms/1000:.1f}s <small>(avg {ms/n/1000:.1f}s)</small>" if ms else "-"
            llm_rows += f"""<tr>
                <td>{display}</td>
                <td>{fmt_ms(agent_ms, n)}</td>
                <td>{fmt_ms(judge_ms, n)}</td>
                <td>{fmt_ms(usersim_ms, n)}</td>
            </tr>"""

        # Cost table
        cost_rows = ""
        for s in summaries_for_variant:
            display = MODEL_DISPLAY_NAMES.get(s["model"], s["model"])
            total_tok = s["total_prompt_tokens"] + s["total_completion_tokens"]
            cost_rows += f"""<tr>
                <td>{display}</td>
                <td>{_fmt_tokens(s['total_prompt_tokens'])}</td>
                <td>{_fmt_tokens(s['total_completion_tokens'])}</td>
                <td>{_fmt_tokens(total_tok)}</td>
                <td>{_fmt_cost(s['total_cost'])}</td>
            </tr>"""

        variant_sections += f"""
        <h2>{variant_label} Tests</h2>

        <h3>Results</h3>
        <table>
            <thead><tr><th>Case</th>{case_header}</tr></thead>
            <tbody>{case_rows}</tbody>
            <tfoot><tr><td><strong>Pass Rate</strong></td>{rate_cells}</tr></tfoot>
        </table>

        <h3>Timing</h3>
        <table>
            <thead><tr><th></th><th>Avg</th><th>Min</th><th>Max</th><th>P90</th><th>Stdev</th></tr></thead>
            <tbody>{timing_rows}</tbody>
        </table>

        <h3>LLM Time Breakdown</h3>
        <p class="meta">Total LLM time across all cases (avg per case) split by agent role.</p>
        <table>
            <thead><tr><th>Model</th><th>Agent</th><th>Judge</th><th>User Sim</th></tr></thead>
            <tbody>{llm_rows}</tbody>
        </table>

        <h3>Tokens &amp; Cost</h3>
        <table>
            <thead><tr><th>Model</th><th>Prompt</th><th>Completion</th><th>Total</th><th>Cost</th></tr></thead>
            <tbody>{cost_rows}</tbody>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OneDay Agent — Cross-Model Evaluation Report</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #222; }}
    h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.15rem; margin-top: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }}
    h3 {{ font-size: 0.95rem; margin-top: 1.25rem; color: #555; }}
    table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; font-size: 0.875rem; }}
    th, td {{ text-align: left; padding: 0.35rem 0.75rem; border: 1px solid #ddd; }}
    th {{ background: #f5f5f5; font-weight: 600; }}
    tfoot td {{ background: #f9f9f9; }}
    .pass {{ color: #16a34a; font-weight: 600; }}
    .fail {{ color: #dc2626; font-weight: 600; }}
    .skip {{ color: #999; }}
    small {{ color: #888; }}
    .meta {{ color: #888; font-size: 0.85rem; }}
    ul {{ margin: 0.5rem 0 1.5rem; padding-left: 1.5rem; }}
</style>
</head>
<body>
<h1>OneDay Agent — Cross-Model Evaluation</h1>
<p class="meta">Generated {timestamp}</p>

<h2>Summary</h2>
<ul>
{summary_section}
</ul>

{variant_sections}

<hr>
<p class="meta">View full traces on <a href="https://app.langwatch.ai">LangWatch</a></p>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Run OneDay tests across all model providers")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=ALL_MODELS,
        default=ALL_MODELS,
        help="Models to test (default: all three)",
    )
    parser.add_argument(
        "--variant",
        choices=["standard", "diagnosis_only"],
        default=None,
        help="Only run a specific test variant",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output HTML file path (default: auto-generated in reports/)",
    )
    parser.add_argument(
        "--turn-uuids",
        nargs="+",
        default=None,
        metavar="UUID",
        help=(
            "Turn.io journey UUIDs to test. Runs all scenarios against each journey "
            "(separate flow — model loop is skipped when this is provided)."
        ),
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        metavar="N",
        help="Only run the first N test cases (by case number, 1-based). Turn journey runs only.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't auto-open the report in a browser",
    )
    args = parser.parse_args()

    results_dir = tempfile.mkdtemp(prefix="oneday_results_")

    exit_codes = {}
    if args.turn_uuids:
        print(f"OneDay Turn Journey Evaluation")
        print(f"Journey UUIDs: {', '.join(args.turn_uuids)}")
        print(f"Results dir: {results_dir}")
        turn_variant = args.variant or "diagnosis_only"
        for uuid in args.turn_uuids:
            exit_codes[uuid] = run_turn_tests(uuid, results_dir, args.max_cases, variant=turn_variant)
    else:
        print(f"OneDay Cross-Model Evaluation")
        print(f"Models: {', '.join(args.models)}")
        print(f"Results dir: {results_dir}")
        for model in args.models:
            exit_codes[model] = run_model_tests(model, results_dir, args.variant)

    all_results = load_results(results_dir)

    if not all_results:
        print("\nNo results collected. Check that tests ran successfully.")
        sys.exit(1)

    # Generate report
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = args.output or str(reports_dir / f"cross-model-{ts}.html")

    generate_html_report(all_results, output_path)

    print(f"\n{'=' * 60}")
    print(f"  Report generated: {output_path}")
    print(f"{'=' * 60}")

    # Print quick summary
    for model, data in all_results.items():
        display = MODEL_DISPLAY_NAMES.get(model, model)
        for variant, vdata in data.get("variants", {}).items():
            cases = vdata["cases"]
            passed = sum(1 for c in cases if c["passed"])
            total = len(cases)
            print(f"  {display} ({variant}): {passed}/{total} passed")

    if not args.no_open:
        webbrowser.open(f"file://{os.path.abspath(output_path)}")


if __name__ == "__main__":
    main()
