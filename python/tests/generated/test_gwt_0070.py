"""Tests for gwt-0070: cross_cutting_cli_integrated.

Bridge verifiers: BackwardCompatible, FlagEnablesBehavioral, JsonIncludesBehavioral,
MissingRulesError, BothReportsPresent, SeamReportAlwaysPresent,
NoSpuriousBehavioralOnError, ExitCodeCleanOnSuccess.
"""

import argparse
import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from registry.cli import cmd_seams


def _setup_project(tmp_path: Path, *, with_rules: bool = True) -> Path:
    """Create minimal project structure for cmd_seams testing."""
    from registry.crawl_store import CrawlStore

    cw9_dir = tmp_path / ".cw9"
    cw9_dir.mkdir()

    # Create crawl.db with empty schema
    db_path = cw9_dir / "crawl.db"
    with CrawlStore(db_path):
        pass  # schema created by __init__

    if with_rules:
        schema_dir = cw9_dir / "schema"
        schema_dir.mkdir()
        rules_path = schema_dir / "cross_cutting_rules.json"
        rules_path.write_text(json.dumps({
            "rules": [
                {"resource_type": "database", "required_outs": ["audit_event"], "position": "wrap"}
            ]
        }))

    return tmp_path


def _make_args(target_dir: str, **kwargs) -> argparse.Namespace:
    defaults = {
        "target_dir": target_dir,
        "output_json": False,
        "verbose": False,
        "cross_cutting": False,
        "file": None,
        "function": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCrossCuttingCLI:
    """Trace-derived tests for cmd_seams --cross-cutting integration."""

    def test_backward_compatible_no_flag(self, tmp_path: Path) -> None:
        """Verifier BackwardCompatible: no --cross-cutting → no behavioral output."""
        project = _setup_project(tmp_path)
        args = _make_args(str(project), cross_cutting=False)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = cmd_seams(args)

        output = mock_stdout.getvalue().lower()
        assert "behavioral" not in output

    def test_flag_enables_behavioral(self, tmp_path: Path) -> None:
        """Verifier FlagEnablesBehavioral: --cross-cutting + valid rules → behavioral report."""
        project = _setup_project(tmp_path, with_rules=True)
        args = _make_args(str(project), cross_cutting=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = cmd_seams(args)

        output = mock_stdout.getvalue().lower()
        assert "behavioral" in output

    def test_json_includes_behavioral(self, tmp_path: Path) -> None:
        """Verifier JsonIncludesBehavioral: --json + --cross-cutting → JSON has behavioral key."""
        project = _setup_project(tmp_path, with_rules=True)
        args = _make_args(str(project), cross_cutting=True, output_json=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = cmd_seams(args)

        data = json.loads(mock_stdout.getvalue())
        assert "behavioral" in data
        assert "violations" in data["behavioral"]

    def test_missing_rules_error(self, tmp_path: Path) -> None:
        """Verifier MissingRulesError: --cross-cutting + no rules → stderr error, exit 1."""
        project = _setup_project(tmp_path, with_rules=False)
        args = _make_args(str(project), cross_cutting=True)

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr, \
             patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            exit_code = cmd_seams(args)

        assert exit_code == 1
        assert mock_stderr.getvalue()  # something written to stderr

    def test_no_spurious_behavioral_on_error(self, tmp_path: Path) -> None:
        """Verifier NoSpuriousBehavioralOnError: rules error → no behavioral in output."""
        project = _setup_project(tmp_path, with_rules=False)
        args = _make_args(str(project), cross_cutting=True)

        with patch("sys.stderr", new_callable=StringIO), \
             patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cmd_seams(args)

        output = mock_stdout.getvalue().lower()
        assert "behavioral" not in output

    def test_exit_code_clean_on_success(self, tmp_path: Path) -> None:
        """Verifier ExitCodeCleanOnSuccess: no errors, no mismatches → exit 0."""
        project = _setup_project(tmp_path, with_rules=True)
        args = _make_args(str(project), cross_cutting=True)

        with patch("sys.stdout", new_callable=StringIO):
            exit_code = cmd_seams(args)

        assert exit_code == 0

    def test_seam_report_always_present(self, tmp_path: Path) -> None:
        """Verifier SeamReportAlwaysPresent: successful run always has seam report."""
        project = _setup_project(tmp_path, with_rules=True)
        args = _make_args(str(project), cross_cutting=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cmd_seams(args)

        output = mock_stdout.getvalue().lower()
        assert "seam report" in output
