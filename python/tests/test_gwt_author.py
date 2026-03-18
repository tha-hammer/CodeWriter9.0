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

    def test_finds_directory_paths(self):
        text = "The pipeline code is in backend/services/ and the routes in backend/routes/"
        result = extract_mentions(text)
        assert "backend/services/" in result["directories"]
        assert "backend/routes/" in result["directories"]

    def test_file_path_implies_parent_directory(self):
        text = "Check backend/services/pipeline.js for the orchestrator."
        result = extract_mentions(text)
        assert "backend/services/pipeline.js" in result["files"]
        # The directory extraction happens in _collect_directory_prefixes,
        # not in extract_mentions itself


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

    def test_file_mention_walks_entire_ancestor_tree(self, tmp_path: Path):
        """When a file like backend/services/pipeline.js is mentioned,
        all records under backend/ (the top-level ancestor) should be
        returned — not just the immediate parent directory."""
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            files = [
                ("backend/services/pipeline.js", "runPipeline"),
                ("backend/services/transcription.js", "transcribe"),
                ("backend/services/diarization.js", "diarize"),
                ("backend/routes/health.js", "healthCheck"),
                ("backend/server.js", "startServer"),
                # Different top-level tree — should NOT be included
                ("frontend/app.js", "renderApp"),
            ]
            for fp, fn in files:
                uid = make_record_uuid(fp, fn)
                store.insert_record(FnRecord(
                    uuid=uid, function_name=fn, file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[],
                ))

            # Mention only one file — should expand to entire backend/ tree
            cards = query_relevant_cards(store, {
                "functions": [],
                "files": ["backend/services/pipeline.js"],
                "directories": [],
            })
            names = {c.function_name for c in cards}
            assert "runPipeline" in names
            assert "transcribe" in names
            assert "diarize" in names
            assert "healthCheck" in names   # backend/routes/ included
            assert "startServer" in names   # backend/ root included
            assert "renderApp" not in names  # frontend/ excluded

    def test_directory_mention_pulls_all_records(self, tmp_path: Path):
        """When a directory like backend/ is mentioned,
        all records under backend/ should be returned."""
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            files = [
                ("backend/services/pipeline.js", "runPipeline"),
                ("backend/services/transcription.js", "transcribe"),
                ("backend/routes/health.js", "healthCheck"),
                ("backend/server.js", "startServer"),
                ("frontend/app.js", "renderApp"),  # different tree
            ]
            for fp, fn in files:
                uid = make_record_uuid(fp, fn)
                store.insert_record(FnRecord(
                    uuid=uid, function_name=fn, file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[],
                ))

            # Mention directory explicitly
            cards = query_relevant_cards(store, {
                "functions": [],
                "files": [],
                "directories": ["backend/"],
            })
            names = {c.function_name for c in cards}
            assert "runPipeline" in names
            assert "transcribe" in names
            assert "healthCheck" in names
            assert "startServer" in names
            assert "renderApp" not in names

    def test_mixed_mentions_combine_results(self, tmp_path: Path):
        """Functions + files + directories all contribute to the card set."""
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            files = [
                ("backend/services/pipeline.js", "runPipeline"),
                ("backend/services/transcription.js", "transcribe"),
                ("backend/routes/health.js", "healthCheck"),
                ("frontend/hooks/useAuth.js", "useAuth"),
            ]
            for fp, fn in files:
                uid = make_record_uuid(fp, fn)
                store.insert_record(FnRecord(
                    uuid=uid, function_name=fn, file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[],
                ))

            cards = query_relevant_cards(store, {
                "functions": ["useAuth"],  # from frontend
                "files": ["backend/services/pipeline.js"],  # expands to services/
                "directories": ["backend/routes/"],  # routes/
            })
            names = {c.function_name for c in cards}
            assert "useAuth" in names       # function match
            assert "runPipeline" in names   # file + dir expansion
            assert "transcribe" in names    # sibling in services/
            assert "healthCheck" in names   # directory match


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
        assert "Fetches user" in prompt


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


class TestCmdGwtAuthor:
    def test_outputs_valid_json(self, tmp_path: Path, capsys, monkeypatch):
        from registry.cli import main

        # Set up project
        project = tmp_path / "project"
        project.mkdir()
        (project / ".cw9").mkdir()

        # Write a research file
        notes = tmp_path / "notes.md"
        notes.write_text("We need to modify get_user() to add admin checks.")

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
