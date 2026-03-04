#!/usr/bin/env python3
"""Generate an example HTML report with filler data for preview purposes."""

import webbrowser, os
from run_all_models import generate_html_report

filler_results = {
    "claude-opus-4-6": {
        "model": "claude-opus-4-6",
        "variants": {
            "standard": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 12.3},
                    {"case": 2, "passed": True, "failed": False, "total_time": 8.7},
                    {"case": 3, "passed": False, "failed": True, "total_time": 15.1},
                    {"case": 4, "passed": True, "failed": False, "total_time": 9.4},
                    {"case": 5, "passed": True, "failed": False, "total_time": 11.2},
                ],
                "total_time_stats": {"avg": 11.3, "min": 8.7, "max": 15.1, "p90": 14.2, "stdev": 2.4},
                "agent_time_stats": {"avg": 9.1, "min": 6.5, "max": 12.8, "p90": 11.9, "stdev": 2.1},
                "total_prompt_tokens": 45200,
                "total_completion_tokens": 12800,
                "total_cost": 0.1523,
            },
            "diagnosis_only": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 6.1},
                    {"case": 2, "passed": True, "failed": False, "total_time": 5.3},
                    {"case": 3, "passed": True, "failed": False, "total_time": 7.8},
                    {"case": 4, "passed": False, "failed": True, "total_time": 9.2},
                    {"case": 5, "passed": True, "failed": False, "total_time": 5.9},
                ],
                "total_time_stats": {"avg": 6.9, "min": 5.3, "max": 9.2, "p90": 8.5, "stdev": 1.5},
                "agent_time_stats": {"avg": 5.2, "min": 3.8, "max": 7.1, "p90": 6.6, "stdev": 1.2},
                "total_prompt_tokens": 28100,
                "total_completion_tokens": 7600,
                "total_cost": 0.0891,
            },
        },
    },
    "gpt-5-mini": {
        "model": "gpt-5-mini",
        "variants": {
            "standard": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 14.5},
                    {"case": 2, "passed": False, "failed": True, "total_time": 10.2},
                    {"case": 3, "passed": True, "failed": False, "total_time": 18.3},
                    {"case": 4, "passed": True, "failed": False, "total_time": 11.7},
                    {"case": 5, "passed": False, "failed": True, "total_time": 13.9},
                ],
                "total_time_stats": {"avg": 13.7, "min": 10.2, "max": 18.3, "p90": 17.1, "stdev": 3.0},
                "agent_time_stats": {"avg": 11.4, "min": 8.1, "max": 15.6, "p90": 14.3, "stdev": 2.7},
                "total_prompt_tokens": 52300,
                "total_completion_tokens": 15100,
                "total_cost": 0.0342,
            },
            "diagnosis_only": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 7.2},
                    {"case": 2, "passed": True, "failed": False, "total_time": 6.8},
                    {"case": 3, "passed": False, "failed": True, "total_time": 8.9},
                    {"case": 4, "passed": True, "failed": False, "total_time": 6.1},
                    {"case": 5, "passed": True, "failed": False, "total_time": 7.4},
                ],
                "total_time_stats": {"avg": 7.3, "min": 6.1, "max": 8.9, "p90": 8.5, "stdev": 1.0},
                "agent_time_stats": {"avg": 5.8, "min": 4.6, "max": 7.2, "p90": 6.9, "stdev": 0.9},
                "total_prompt_tokens": 31200,
                "total_completion_tokens": 8900,
                "total_cost": 0.0201,
            },
        },
    },
    "gemini-3-pro-preview": {
        "model": "gemini-3-pro-preview",
        "variants": {
            "standard": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 16.8},
                    {"case": 2, "passed": True, "failed": False, "total_time": 12.1},
                    {"case": 3, "passed": True, "failed": False, "total_time": 14.6},
                    {"case": 4, "passed": False, "failed": True, "total_time": 20.3},
                    {"case": 5, "passed": True, "failed": False, "total_time": 13.5},
                ],
                "total_time_stats": {"avg": 15.5, "min": 12.1, "max": 20.3, "p90": 18.9, "stdev": 3.1},
                "agent_time_stats": {"avg": 13.2, "min": 9.8, "max": 17.5, "p90": 16.1, "stdev": 2.8},
                "total_prompt_tokens": 61400,
                "total_completion_tokens": 18200,
                "total_cost": 0.0485,
            },
            "diagnosis_only": {
                "cases": [
                    {"case": 1, "passed": True, "failed": False, "total_time": 8.4},
                    {"case": 2, "passed": False, "failed": True, "total_time": 9.7},
                    {"case": 3, "passed": True, "failed": False, "total_time": 7.1},
                    {"case": 4, "passed": True, "failed": False, "total_time": 8.8},
                    {"case": 5, "passed": True, "failed": False, "total_time": 6.5},
                ],
                "total_time_stats": {"avg": 8.1, "min": 6.5, "max": 9.7, "p90": 9.3, "stdev": 1.2},
                "agent_time_stats": {"avg": 6.4, "min": 4.9, "max": 7.8, "p90": 7.5, "stdev": 1.0},
                "total_prompt_tokens": 35800,
                "total_completion_tokens": 10500,
                "total_cost": 0.0278,
            },
        },
    },
}

output = "reports/example-report.html"
os.makedirs("reports", exist_ok=True)
generate_html_report(filler_results, output)
print(f"Generated: {output}")
webbrowser.open(f"file://{os.path.abspath(output)}")
