"""
pytest configuration for OneDay agent testing with pytest-xdist support.

Uses pytest hooks to share a single testrun_uid across all parallel workers.
"""

import pytest
from datetime import datetime


def pytest_configure(config):
    """Set up shared test run ID once at startup (before workers spawn)."""
    # Generate a human-readable timestamp-based ID
    testrun_uid = f"oneday-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    config.testrun_uid = testrun_uid


def pytest_configure_node(node):
    """Pass the testrun_uid to each xdist worker."""
    node.workerinput["testrun_uid"] = node.config.testrun_uid


@pytest.fixture(scope="session")
def testrun_uid(request):
    """Access the shared test run UID (works with or without xdist)."""
    # Worker process: get from workerinput
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput["testrun_uid"]
    # Main process: get directly from config
    return request.config.testrun_uid
