"""GWT authoring bridge — research notes + crawl.db → GWT JSON.

Reads research notes, queries crawl.db for relevant IN:DO:OUT cards,
constructs an LLM prompt, parses the LLM output into a register-compatible
JSON payload with depends_on UUIDs.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from registry.crawl_store import CrawlStore, render_card
from registry.crawl_types import FnRecord

logger = logging.getLogger(__name__)

# ── Mention extraction ────────────────────────────────────────────

# Matches function_name() patterns
_FUNC_MENTION_RE = re.compile(r"\b(\w+)\(\)")

# Matches file paths like src/handlers/user.py or ./models/user.ts
_FILE_PATH_RE = re.compile(
    r"(?:^|\s|[\"'`])"
    r"((?:\.?/)?(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb))"
    r"(?=\s|[\"'`]|$|[,;:.)])",
)

# Matches directory paths like backend/services/ or src/handlers
# Must end with / or have no file extension at the end.
# Excludes paths that end with a known source file extension (those are files).
_DIR_PATH_RE = re.compile(
    r"(?:^|\s|[\"'`])"
    r"((?:\.?/)?(?:[\w.-]+/)+[\w.-]*)"
    r"(?=\s|[\"'`]|$|[,;:.)])",
)

_SOURCE_EXTENSIONS = frozenset(("py", "ts", "tsx", "js", "jsx", "go", "rs", "java", "rb"))


def extract_mentions(text: str) -> dict[str, list[str]]:
    """Extract function, file, and directory mentions from research notes text."""
    functions = list(dict.fromkeys(_FUNC_MENTION_RE.findall(text)))
    files = list(dict.fromkeys(_FILE_PATH_RE.findall(text)))
    # Filter dir regex matches: exclude anything that looks like a source file
    raw_dirs = _DIR_PATH_RE.findall(text)
    directories = []
    file_set = set(files)
    for d in raw_dirs:
        if d in file_set:
            continue
        ext = d.rsplit(".", 1)[-1] if "." in d.split("/")[-1] else ""
        if ext in _SOURCE_EXTENSIONS:
            continue
        if d not in directories:
            directories.append(d)
    return {"functions": functions, "files": files, "directories": directories}


# ── Card query ────────────────────────────────────────────────────

def _collect_directory_prefixes(mentions: dict[str, list[str]]) -> list[str]:
    """Derive directory prefixes from file paths and explicit directory mentions.

    For each mentioned file (e.g. ``backend/services/pipeline.js``), *all*
    ancestor directories are included as prefixes.  The top-level directory
    (e.g. ``backend``) is the most important — it ensures the entire
    project subtree is walked, not just the immediate parent.

    Explicit directory mentions (e.g. ``backend/``) are also included.

    Redundant prefixes are collapsed: if both ``backend`` and
    ``backend/services`` are present, only ``backend`` is kept.
    """
    prefixes: dict[str, None] = {}  # ordered set

    # All ancestor directories of mentioned files
    for fp in mentions.get("files", []):
        p = Path(fp).parent
        while str(p) not in (".", "", "/"):
            prefixes[str(p)] = None
            p = p.parent

    # Explicit directory mentions
    for dp in mentions.get("directories", []):
        clean = dp.rstrip("/")
        if clean:
            prefixes[clean] = None

    # Collapse: remove any prefix that is a sub-path of another prefix
    sorted_prefixes = sorted(prefixes, key=len)
    result: list[str] = []
    for prefix in sorted_prefixes:
        # Keep only if no shorter prefix already covers it
        if not any(prefix.startswith(r + "/") for r in result):
            result.append(prefix)

    return result


def query_relevant_cards(
    store: CrawlStore,
    mentions: dict[str, list[str]],
) -> list[FnRecord]:
    """Query crawl.db for records matching function/file/directory mentions.

    Returns mentioned records, all records in mentioned directories, plus
    their transitive dependencies.
    """
    matched: dict[str, FnRecord] = {}

    # Match by function name
    all_records = store.get_all_records()
    mentioned_fns = set(mentions.get("functions", []))
    if mentioned_fns:
        for rec in all_records:
            if rec.function_name in mentioned_fns:
                matched[rec.uuid] = rec

    # Match by file path (exact or suffix match for relative paths)
    mentioned_files = mentions.get("files", [])
    if mentioned_files:
        for rec in all_records:
            for file_path in mentioned_files:
                if rec.file_path == file_path or rec.file_path.endswith("/" + file_path):
                    matched[rec.uuid] = rec
                    break

    # Match by directory prefix — walk sibling files in the same directory
    for prefix in _collect_directory_prefixes(mentions):
        for rec in store.get_records_by_directory(prefix):
            matched[rec.uuid] = rec

    # Get transitive subgraphs for each matched function
    extended: dict[str, FnRecord] = dict(matched)
    for rec in list(matched.values()):
        try:
            subgraph = store.get_forward_subgraph(rec.function_name)
            for sub_rec in subgraph:
                if sub_rec.uuid not in extended:
                    extended[sub_rec.uuid] = sub_rec
        except Exception:
            pass  # If subgraph query fails, continue with direct matches

    return list(extended.values())


# ── Prompt building ───────────────────────────────────────────────

def build_gwt_prompt(research_text: str, cards: list[FnRecord]) -> str:
    """Build the LLM prompt from research notes and IN:DO:OUT cards."""
    sections = []

    sections.append("# GWT Specification Task\n")
    sections.append(
        "You are a behavioral specification author. Given the research notes and "
        "existing code behavior cards below, produce a JSON object with a `gwts` array. "
        "Each GWT entry must have: criterion_id, given, when, then, and optionally "
        "depends_on (array of UUID strings referencing the cards below).\n"
    )

    sections.append("## Research Notes\n")
    sections.append(research_text)
    sections.append("")

    if cards:
        sections.append("## Existing Code Behavior (IN:DO:OUT Cards)\n")
        for card in cards:
            sections.append(f"### {card.function_name} (UUID: {card.uuid})")
            sections.append(render_card(card))
            sections.append("")

    sections.append("## Output Format\n")
    sections.append(
        "Respond with a JSON object:\n"
        "```json\n"
        '{"gwts": [{"criterion_id": "...", "given": "...", "when": "...", '
        '"then": "...", "depends_on": ["uuid1", ...]}]}\n'
        "```\n"
    )

    return "\n".join(sections)


# ── Response parsing ──────────────────────────────────────────────

def parse_gwt_response(response: str) -> dict:
    """Parse LLM response into a register-compatible payload.

    Handles JSON wrapped in markdown code fences.
    """
    text = response.strip()

    # Try to extract JSON from markdown fences
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse GWT response as JSON: {e}") from e

    if not isinstance(payload, dict) or "gwts" not in payload:
        raise ValueError("Response must be a JSON object with a 'gwts' array")

    return payload


# ── Validation ────────────────────────────────────────────────────

def validate_depends_on(payload: dict, store: CrawlStore) -> list[str]:
    """Validate depends_on UUIDs against crawl.db.

    Removes invalid UUIDs from the payload in-place and returns warnings.
    """
    all_uuids = store.get_all_uuids()
    warnings: list[str] = []

    for gwt in payload.get("gwts", []):
        depends_on = gwt.get("depends_on", [])
        valid = []
        for uid in depends_on:
            if uid in all_uuids:
                valid.append(uid)
            else:
                warnings.append(f"UUID {uid} not found in crawl.db — removed from depends_on")
        gwt["depends_on"] = valid

    return warnings


# ── LLM call stub ─────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """Call the LLM with the given prompt. Stub for dependency injection."""
    raise NotImplementedError(
        "LLM integration not configured. Set up via monkeypatch or environment."
    )


# ── Top-level command ─────────────────────────────────────────────

def run_gwt_author(
    project_dir: Path,
    research_path: Path,
    llm_fn=None,
) -> dict:
    """Run the GWT authoring pipeline.

    Returns the register-compatible payload dict.
    """
    if llm_fn is None:
        llm_fn = _call_llm

    research_text = research_path.read_text(encoding="utf-8")

    crawl_db = project_dir / ".cw9" / "crawl.db"
    if not crawl_db.exists():
        raise FileNotFoundError(f"No crawl.db found at {crawl_db}. Run 'cw9 ingest' first.")

    with CrawlStore(crawl_db) as store:
        # Extract mentions from research notes
        mentions = extract_mentions(research_text)

        # Query relevant cards
        cards = query_relevant_cards(store, mentions)

        # Build prompt
        prompt = build_gwt_prompt(research_text, cards)

        # Call LLM
        response = llm_fn(prompt)

        # Parse response
        payload = parse_gwt_response(response)

        # Validate depends_on
        warnings = validate_depends_on(payload, store)
        for w in warnings:
            logger.warning(w)

    return payload
