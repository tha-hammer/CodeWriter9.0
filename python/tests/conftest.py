"""Shared pytest configuration for CW9 test suite.

Auto-skips integration tests when required external tools aren't installed.
"""

import shutil

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when required tools aren't installed."""
    tool_checks = {
        "typescript": "npx",
        "rust": "cargo",
        "go": "go",
    }
    for item in items:
        if "integration" not in item.keywords:
            continue
        # Infer required tool from test path or marker args
        for lang, tool in tool_checks.items():
            if lang in str(item.fspath) and shutil.which(tool) is None:
                item.add_marker(pytest.mark.skip(
                    reason=f"{tool} not found -- install to run {lang} integration tests"
                ))
