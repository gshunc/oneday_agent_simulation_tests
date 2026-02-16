#!/usr/bin/env python3
"""
Cross-model test orchestrator for OneDay agent evaluation.

Runs the full test suite against all three model providers (OpenAI, Anthropic, Google),
collects statistics, and generates an HTML report that opens automatically.

Usage:
    python run_all_models.py                    # Run all models
    python run_all_models.py --models gpt-5-mini claude-4.5-sonnet  # Run specific models
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

ALL_MODELS = ["gpt-5-mini", "claude-4.5-sonnet", "gemini-2.5-flash"]
PROJECT_ROOT = Path(__file__).parent


def run_model_tests(model: str, results_dir: str, variant: str | None = None) -> tuple[int, str]:
    """Run pytest for a single model and return (exit_code, stdout)."""
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
                "cases": {c["case"]: c for c in cases},
            })

    # Build the HTML
    html = _build_html(timestamp, model_summaries, all_cases, all_results)

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def _status_badge(case_data: dict | None) -> str:
    """Return an HTML badge for a test case status."""
    if case_data is None:
        return '<span class="badge skip">-</span>'
    if case_data.get("passed"):
        return '<span class="badge pass">PASS</span>'
    if case_data.get("failed"):
        return '<span class="badge fail">FAIL</span>'
    return '<span class="badge skip">SKIP</span>'


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
        <td class="stat-label">{label}</td>
        <td>{stats['avg']:.1f}s</td>
        <td>{stats['min']:.1f}s</td>
        <td>{stats['max']:.1f}s</td>
        <td>{stats['p90']:.1f}s</td>
        <td>{stats['stdev']:.1f}s</td>
    </tr>"""


MODEL_DISPLAY_NAMES = {
    "gpt-5-mini": "GPT-5 Mini",
    "claude-4.5-sonnet": "Claude 4.5 Sonnet",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
}

PROVIDER_COLORS = {
    "gpt-5-mini": "#10a37f",
    "claude-4.5-sonnet": "#d97706",
    "gemini-2.5-flash": "#4285f4",
}


def _build_html(timestamp: str, model_summaries: list, all_cases: list, all_results: dict) -> str:
    # --- Overview cards ---
    overview_cards = ""
    models_seen = []
    for model in all_results:
        if model in models_seen:
            continue
        models_seen.append(model)
        display = MODEL_DISPLAY_NAMES.get(model, model)
        color = PROVIDER_COLORS.get(model, "#666")

        # Aggregate across variants for this model
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
        overview_cards += f"""
        <div class="card" style="border-top: 4px solid {color}">
            <div class="card-title" style="color: {color}">{display}</div>
            <div class="card-stat">{pass_rate}%</div>
            <div class="card-label">pass rate ({total_passed}/{total_cases})</div>
            <div class="card-details">
                <span>Tokens: {_fmt_tokens(total_tokens)}</span>
                <span>Cost: {_fmt_cost(total_cost)}</span>
            </div>
        </div>"""

    # --- Per-variant comparison tables ---
    variant_sections = ""
    for variant in ["standard", "diagnosis_only"]:
        variant_label = "Standard" if variant == "standard" else "Diagnosis Only"
        summaries_for_variant = [s for s in model_summaries if s["variant"] == variant]
        if not summaries_for_variant:
            continue

        # Case-by-case comparison table
        case_header = "".join(
            f'<th style="color: {PROVIDER_COLORS.get(s["model"], "#666")}">{MODEL_DISPLAY_NAMES.get(s["model"], s["model"])}</th>'
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
                    time_str = f'<span class="case-time">{case_data["total_time"]:.1f}s</span>'
                cells += f"<td>{badge} {time_str}</td>"
            case_rows += f"<tr><td class='case-num'>Case {case_num}</td>{cells}</tr>\n"

        # Pass rate comparison row
        rate_cells = ""
        for s in summaries_for_variant:
            rate_cells += f'<td class="pass-rate">{s["pass_rate"]}%</td>'

        # Timing stats table
        timing_rows = ""
        for s in summaries_for_variant:
            display = MODEL_DISPLAY_NAMES.get(s["model"], s["model"])
            color = PROVIDER_COLORS.get(s["model"], "#666")
            timing_rows += f'<tr><td colspan="6" class="timing-model" style="color: {color}">{display}</td></tr>'
            timing_rows += _stat_row("Total time", s["total_time_stats"])
            timing_rows += _stat_row("Agent time", s["agent_time_stats"])

        # Cost & token comparison
        cost_rows = ""
        for s in summaries_for_variant:
            display = MODEL_DISPLAY_NAMES.get(s["model"], s["model"])
            color = PROVIDER_COLORS.get(s["model"], "#666")
            total_tok = s["total_prompt_tokens"] + s["total_completion_tokens"]
            cost_rows += f"""<tr>
                <td style="color: {color}; font-weight: 600">{display}</td>
                <td>{_fmt_tokens(s['total_prompt_tokens'])}</td>
                <td>{_fmt_tokens(s['total_completion_tokens'])}</td>
                <td>{_fmt_tokens(total_tok)}</td>
                <td class="cost-cell">{_fmt_cost(s['total_cost'])}</td>
            </tr>"""

        variant_sections += f"""
        <section class="variant-section">
            <h2>{variant_label} Tests</h2>

            <div class="table-container">
                <table>
                    <thead>
                        <tr><th>Case</th>{case_header}</tr>
                    </thead>
                    <tbody>
                        {case_rows}
                    </tbody>
                    <tfoot>
                        <tr class="summary-row"><td>Pass Rate</td>{rate_cells}</tr>
                    </tfoot>
                </table>
            </div>

            <div class="stats-grid">
                <div class="stats-block">
                    <h3>Timing Statistics</h3>
                    <table class="stats-table">
                        <thead><tr><th></th><th>Avg</th><th>Min</th><th>Max</th><th>P90</th><th>Stdev</th></tr></thead>
                        <tbody>{timing_rows}</tbody>
                    </table>
                </div>
                <div class="stats-block">
                    <h3>Tokens & Cost</h3>
                    <table class="stats-table">
                        <thead><tr><th>Model</th><th>Prompt</th><th>Completion</th><th>Total</th><th>Cost</th></tr></thead>
                        <tbody>{cost_rows}</tbody>
                    </table>
                </div>
            </div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OneDay Agent - Cross-Model Evaluation Report</title>
<style>
    :root {{
        --bg: #0f1117;
        --surface: #1a1d27;
        --surface2: #242837;
        --border: #2e3347;
        --text: #e4e6f0;
        --text-muted: #8b8fa3;
        --pass: #22c55e;
        --fail: #ef4444;
        --skip: #6b7280;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.6;
        padding: 2rem;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
        text-align: center;
        margin-bottom: 2.5rem;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid var(--border);
    }}
    header h1 {{
        font-size: 1.75rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }}
    header .subtitle {{
        color: var(--text-muted);
        font-size: 0.9rem;
    }}
    .overview {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1.25rem;
        margin-bottom: 2.5rem;
    }}
    .card {{
        background: var(--surface);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid var(--border);
    }}
    .card-title {{ font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
    .card-stat {{ font-size: 2.5rem; font-weight: 800; }}
    .card-label {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.75rem; }}
    .card-details {{ display: flex; gap: 1.25rem; color: var(--text-muted); font-size: 0.8rem; }}
    .variant-section {{
        margin-bottom: 3rem;
    }}
    .variant-section h2 {{
        font-size: 1.25rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    }}
    .table-container {{
        overflow-x: auto;
        margin-bottom: 1.5rem;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        background: var(--surface);
        border-radius: 8px;
        overflow: hidden;
    }}
    th, td {{
        padding: 0.65rem 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border);
        font-size: 0.875rem;
    }}
    th {{
        background: var(--surface2);
        font-weight: 600;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: var(--text-muted);
    }}
    .case-num {{ font-weight: 600; white-space: nowrap; }}
    .badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.03em;
    }}
    .badge.pass {{ background: rgba(34, 197, 94, 0.15); color: var(--pass); }}
    .badge.fail {{ background: rgba(239, 68, 68, 0.15); color: var(--fail); }}
    .badge.skip {{ background: rgba(107, 114, 128, 0.15); color: var(--skip); }}
    .case-time {{ color: var(--text-muted); font-size: 0.8rem; margin-left: 0.5rem; }}
    .summary-row td {{
        font-weight: 700;
        background: var(--surface2);
        border-top: 2px solid var(--border);
    }}
    .pass-rate {{ font-size: 1.1rem; }}
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 1.25rem;
    }}
    .stats-block {{
        background: var(--surface);
        border-radius: 8px;
        padding: 1.25rem;
        border: 1px solid var(--border);
    }}
    .stats-block h3 {{
        font-size: 0.9rem;
        color: var(--text-muted);
        margin-bottom: 0.75rem;
    }}
    .stats-table {{ background: transparent; }}
    .stats-table td, .stats-table th {{ padding: 0.4rem 0.75rem; font-size: 0.8rem; }}
    .timing-model {{
        font-weight: 700 !important;
        padding-top: 0.75rem !important;
        border-bottom: none !important;
    }}
    .stat-label {{ color: var(--text-muted); padding-left: 1.5rem !important; }}
    .cost-cell {{ font-weight: 600; }}
    footer {{
        text-align: center;
        color: var(--text-muted);
        font-size: 0.8rem;
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px solid var(--border);
    }}
    footer a {{ color: var(--text-muted); }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>OneDay Agent &mdash; Cross-Model Evaluation</h1>
        <div class="subtitle">Generated {timestamp}</div>
    </header>

    <div class="overview">
        {overview_cards}
    </div>

    {variant_sections}

    <footer>
        <p>View full traces on <a href="https://app.langwatch.ai" target="_blank">LangWatch</a></p>
    </footer>
</div>
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
        "--no-open",
        action="store_true",
        help="Don't auto-open the report in a browser",
    )
    args = parser.parse_args()

    results_dir = tempfile.mkdtemp(prefix="oneday_results_")

    print(f"OneDay Cross-Model Evaluation")
    print(f"Models: {', '.join(args.models)}")
    print(f"Results dir: {results_dir}")

    exit_codes = {}
    for model in args.models:
        exit_codes[model] = run_model_tests(model, results_dir, args.variant)

    # Load all results
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
