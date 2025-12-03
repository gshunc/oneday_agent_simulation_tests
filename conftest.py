"""
pytest configuration for OneDay agent testing with pytest-xdist support.

Uses pytest hooks to share testrun_uid across parallel workers, with separate
UIDs for standard and strict test variants.
"""

import pytest
import os
import re
from datetime import datetime, timezone
from collections import defaultdict


# Store results per variant (standard/strict)
_test_results = defaultdict(list)
_test_metadata = {}


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
    """Set up base test run ID once at startup (before workers spawn)."""
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


def pytest_configure_node(node):
    """Pass the base testrun_uid and model to each xdist worker."""
    node.workerinput["base_testrun_uid"] = node.config.base_testrun_uid
    node.workerinput["model_name"] = node.config.model_name
    node.workerinput["timestamp"] = node.config.timestamp


def pytest_runtest_logreport(report):
    """Collect test results as they complete."""
    if report.when == "call":
        # Extract variant (standard/strict) and case number from test name
        test_name = report.nodeid

        if "strict" in test_name:
            variant = "strict"
        elif "standard" in test_name:
            variant = "standard"
        else:
            return

        # Extract case number from test id (e.g., "case_1" -> 1)
        case_match = re.search(r'case_(\d+)', test_name)
        case_num = int(case_match.group(1)) if case_match else 0

        _test_results[variant].append({
            "case": case_num,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
        })


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

    for variant in ["standard", "strict"]:
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

            print(f"    Case {case_num:3d}: {status}")

        print(f"  {'-' * 40}")
        print(f"  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")

    print(f"\n{separator}\n")


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
    Generate test run UID that's unique per test variant (standard vs strict).

    Standard and strict tests get different UIDs so they appear as separate
    runs in LangWatch, but all tests of the same variant share the same UID.
    """
    # Get base UID from config or worker input
    if hasattr(request.config, "workerinput"):
        base_uid = request.config.workerinput["base_testrun_uid"]
    else:
        base_uid = request.config.base_testrun_uid

    # Determine test variant from test function name
    test_name = request.node.name
    if "strict" in test_name:
        variant = "strict"
    elif "standard" in test_name:
        variant = "standard"
    else:
        variant = "unknown"

    return f"{base_uid}-{variant}"
