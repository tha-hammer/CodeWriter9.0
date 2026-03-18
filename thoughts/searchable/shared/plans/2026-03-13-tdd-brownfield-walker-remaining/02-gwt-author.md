---
component: 2
title: "cw9 gwt-author Command"
new_files: ["python/registry/gwt_author.py"]
test_files: ["python/tests/test_gwt_author.py"]
modified_files: ["python/registry/cli.py"]
behaviors: 6
beads: ["replication_ab_bench-1qz", "replication_ab_bench-xrc", "replication_ab_bench-j3p", "replication_ab_bench-90t", "replication_ab_bench-967", "replication_ab_bench-um5"]
depends_on: [1]
---

## Component 2: `cw9 gwt-author` Command

**New file**: `python/registry/gwt_author.py`
**Test file**: `python/tests/test_gwt_author.py`
**Modified file**: `python/registry/cli.py` (add `cmd_gwt_author` subcommand)

This command reads research notes, queries crawl.db for relevant IN:DO:OUT cards,
constructs an LLM prompt, parses the LLM output into a register-compatible JSON payload
with `depends_on` UUIDs, and prints it to stdout.

### Behavior 2.1: Extract function mentions from research notes

**Given**: A research notes file mentioning `get_user`, `validate_input`, `src/handlers/user.py`
**When**: `extract_mentions(text)` is called
**Then**: Returns `{"functions": ["get_user", "validate_input"], "files": ["src/handlers/user.py"]}`

```python
"""Tests for the GWT authoring bridge."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from registry.gwt_author import extract_mentions, build_gwt_prompt, parse_gwt_response
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


class TestExtractMentions:
    def test_finds_function_names(self):
        text = "We need to modify get_user() and validate_input() to support the new auth flow."
        result = extract_mentions(text)
        assert "get_user" in result["functions"]
        assert "validate_input" in result["functions"]

    def test_finds_file_paths(self):
        text = "The handler lives in src/handlers/user.py and the model in src/models/user.py."
        result = extract_mentions(text)
        assert "src/handlers/user.py" in result["files"]
        assert "src/models/user.py" in result["files"]

    def test_empty_text_returns_empty(self):
        result = extract_mentions("")
        assert result["functions"] == []
        assert result["files"] == []
```

### Behavior 2.2: Query crawl.db for matching records and their subgraph

**Given**: A CrawlStore with records and a set of function name mentions
**When**: `query_relevant_cards(store, mentions)` is called
**Then**: Returns the mentioned records plus their transitive dependencies

```python
class TestQueryRelevantCards:
    def test_finds_mentioned_functions(self, tmp_path: Path):
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            uid = make_record_uuid("src/user.py", "get_user")
            store.insert_record(FnRecord(
                uuid=uid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc",
                ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
                do_description="Fetches user", outs=[
                    OutField(name=OutKind.OK, type_str="User", description="found"),
                ],
            ))

            cards = query_relevant_cards(store, {"functions": ["get_user"], "files": []})
            assert len(cards) >= 1
            assert any(c.function_name == "get_user" for c in cards)

    def test_returns_empty_for_no_matches(self, tmp_path: Path):
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            cards = query_relevant_cards(store, {"functions": ["nonexistent"], "files": []})
            assert cards == []
```

### Behavior 2.3: Build LLM prompt from research notes and cards

**Given**: Research notes text and a list of FnRecords
**When**: `build_gwt_prompt(research_text, cards)` is called
**Then**: Returns a prompt string containing both the research notes and rendered IN:DO:OUT cards

```python
class TestBuildGwtPrompt:
    def test_includes_research_and_cards(self):
        uid = make_record_uuid("src/user.py", "get_user")
        cards = [FnRecord(
            uuid=uid, function_name="get_user", file_path="src/user.py",
            line_number=10, src_hash="abc",
            ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
            do_description="Fetches user",
            outs=[OutField(name=OutKind.OK, type_str="User", description="found")],
            operational_claim="Returns user by ID",
        )]
        prompt = build_gwt_prompt("Add admin role check to get_user", cards)
        assert "Add admin role check" in prompt
        assert "get_user" in prompt
        assert uid in prompt
        assert "IN:" in prompt or "Fetches user" in prompt
```

### Behavior 2.4: Parse LLM response into register payload with depends_on

**Given**: An LLM response containing GWT JSON with depends_on UUIDs
**When**: `parse_gwt_response(response)` is called
**Then**: Returns a dict matching the `cw9 register` payload schema

```python
class TestParseGwtResponse:
    def test_parses_valid_response(self):
        uid = make_record_uuid("src/user.py", "get_user")
        response = json.dumps({
            "gwts": [{
                "criterion_id": "crawl-gwt-001",
                "given": "a user exists with ID 42",
                "when": "get_user(42) is called with admin role",
                "then": "the user profile includes admin fields",
                "depends_on": [uid],
            }]
        })
        payload = parse_gwt_response(response)
        assert len(payload["gwts"]) == 1
        assert payload["gwts"][0]["depends_on"] == [uid]
        assert payload["gwts"][0]["given"] == "a user exists with ID 42"

    def test_extracts_json_from_markdown_fences(self):
        response = '```json\n{"gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}]}\n```'
        payload = parse_gwt_response(response)
        assert len(payload["gwts"]) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            parse_gwt_response("not json at all")
```

### Behavior 2.5: Validate depends_on UUIDs against crawl.db

**Given**: A register payload with depends_on UUIDs, some valid, some invalid
**When**: `validate_depends_on(payload, store)` is called
**Then**: Invalid UUIDs are removed and logged as warnings

```python
class TestValidateDependsOn:
    def test_filters_invalid_uuids(self, tmp_path: Path):
        from registry.gwt_author import validate_depends_on

        uid_valid = make_record_uuid("src/user.py", "get_user")
        uid_invalid = "00000000-0000-0000-0000-000000000000"

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid_valid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc", ins=[], do_description="test", outs=[],
            ))

            payload = {"gwts": [{
                "criterion_id": "c1", "given": "g", "when": "w", "then": "t",
                "depends_on": [uid_valid, uid_invalid],
            }]}
            warnings = validate_depends_on(payload, store)

            assert payload["gwts"][0]["depends_on"] == [uid_valid]
            assert len(warnings) == 1
            assert uid_invalid in warnings[0]
```

### Behavior 2.6: CLI integration — cmd_gwt_author outputs to stdout

**Given**: A .cw9 project with a populated crawl.db and a research notes file
**When**: `main(["gwt-author", "--research", "notes.md", project_path])` is called with a mocked LLM
**Then**: Valid JSON is printed to stdout matching the register payload format

```python
class TestCmdGwtAuthor:
    def test_outputs_valid_json(self, tmp_path: Path, capsys, monkeypatch):
        from registry.cli import main

        # Set up project
        project = tmp_path / "project"
        project.mkdir()
        (project / ".cw9").mkdir()

        # Write a research file
        notes = tmp_path / "notes.md"
        notes.write_text("We need to modify get_user to add admin checks.")

        # Populate crawl.db
        uid = make_record_uuid("src/user.py", "get_user")
        with CrawlStore(project / ".cw9" / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc",
                ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
                do_description="Fetches user",
                outs=[OutField(name=OutKind.OK, type_str="User", description="found")],
                operational_claim="Returns user by ID",
            ))

        # Mock LLM to return predictable GWTs
        mock_response = json.dumps({
            "gwts": [{
                "criterion_id": "crawl-gwt-001",
                "given": "user exists",
                "when": "get_user called",
                "then": "user returned",
                "depends_on": [uid],
            }]
        })
        monkeypatch.setattr(
            "registry.gwt_author._call_llm",
            lambda prompt: mock_response,
        )

        rc = main(["gwt-author", "--research", str(notes), str(project)])
        assert rc == 0

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "gwts" in payload
```

### Success Criteria — Component 2

**Automated:**
- [x] All tests in `test_gwt_author.py` pass
- [x] All existing tests still pass
- [x] `cw9 gwt-author --help` displays usage
- [x] Pipe test: `echo '...' | cw9 register .` accepts gwt-author output format

---
