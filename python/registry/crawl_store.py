"""SQLite-backed store for brownfield IN:DO:OUT crawl data.

All reads/writes to crawl.db go through this class.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from registry.crawl_types import (
    AxRecord,
    DispatchKind,
    EntryPoint,
    EntryType,
    FnRecord,
    InField,
    InSource,
    MapNote,
    OutField,
    OutKind,
    Skeleton,
    SkeletonParam,
    TestReference,
)

_SCHEMA_SQL = """\
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS records (
    uuid            TEXT PRIMARY KEY,
    function_name   TEXT NOT NULL,
    class_name      TEXT,
    file_path       TEXT NOT NULL,
    line_number     INTEGER,
    src_hash        TEXT NOT NULL,
    is_external     BOOLEAN NOT NULL DEFAULT FALSE,
    do_description  TEXT NOT NULL DEFAULT '',
    do_steps        TEXT,
    do_branches     TEXT,
    do_loops        TEXT,
    do_errors       TEXT,
    failure_modes   TEXT,
    operational_claim TEXT DEFAULT '',
    skeleton_json   TEXT,
    source_crate    TEXT,
    boundary_contract TEXT,
    schema_version  INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type_str        TEXT NOT NULL,
    source          TEXT NOT NULL CHECK(source IN ('parameter','state','literal','internal_call','external')),
    source_uuid     TEXT REFERENCES records(uuid) ON DELETE SET NULL,
    source_file     TEXT,
    source_function TEXT,
    source_description TEXT,
    dispatch        TEXT NOT NULL DEFAULT 'direct'
                    CHECK(dispatch IN ('direct','attribute','dynamic','override','callback','protocol')),
    dispatch_candidates TEXT,
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);

CREATE TABLE IF NOT EXISTS outs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL CHECK(name IN ('ok','err','side_effect','mutation')),
    type_str        TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);

CREATE TABLE IF NOT EXISTS maps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name   TEXT NOT NULL UNIQUE,
    entry_uuid      TEXT NOT NULL REFERENCES records(uuid),
    path_uuids      TEXT NOT NULL,
    shared_uuids    TEXT,
    properties      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS test_refs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_file       TEXT NOT NULL,
    test_function   TEXT NOT NULL,
    target_uuid     TEXT REFERENCES records(uuid),
    target_function TEXT NOT NULL,
    target_file     TEXT NOT NULL,
    inputs_observed TEXT,
    outputs_asserted TEXT,
    covers_error_path BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(test_file, test_function, target_function)
);

CREATE TABLE IF NOT EXISTS entry_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT NOT NULL,
    function_name   TEXT NOT NULL,
    entry_type      TEXT NOT NULL CHECK(entry_type IN (
                        'http_route','cli_command','public_api',
                        'event_handler','main','test'
                    )),
    route           TEXT,
    method          TEXT,
    record_uuid     TEXT REFERENCES records(uuid),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(file_path, function_name)
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_path     TEXT NOT NULL,
    language        TEXT NOT NULL,
    codebase_type   TEXT,
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    records_failed  INTEGER DEFAULT 0,
    is_incremental  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE VIEW IF NOT EXISTS deps AS
SELECT DISTINCT
    i.record_uuid AS dependent_uuid,
    i.source_uuid AS dependency_uuid,
    i.dispatch,
    i.dispatch_candidates
FROM ins i
WHERE i.source_uuid IS NOT NULL;

CREATE VIEW IF NOT EXISTS stale_candidates AS
SELECT r.uuid, r.function_name, r.file_path, r.src_hash
FROM records r
WHERE r.is_external = FALSE;

CREATE VIEW IF NOT EXISTS ambiguous_dispatch AS
SELECT
    r.uuid,
    r.function_name,
    r.file_path,
    i.name AS input_name,
    i.dispatch,
    i.dispatch_candidates,
    i.source_function
FROM ins i
JOIN records r ON i.record_uuid = r.uuid
WHERE i.dispatch != 'direct';

CREATE VIEW IF NOT EXISTS test_coverage AS
SELECT
    r.uuid,
    r.function_name,
    r.file_path,
    COUNT(t.id) AS test_count,
    SUM(CASE WHEN t.covers_error_path THEN 1 ELSE 0 END) AS error_path_tests
FROM records r
LEFT JOIN test_refs t ON t.target_uuid = r.uuid
WHERE r.is_external = FALSE
GROUP BY r.uuid;

CREATE INDEX IF NOT EXISTS idx_ins_record ON ins(record_uuid);
CREATE INDEX IF NOT EXISTS idx_ins_source ON ins(source_uuid);
CREATE INDEX IF NOT EXISTS idx_ins_source_fn ON ins(source_function);
CREATE INDEX IF NOT EXISTS idx_outs_record ON outs(record_uuid);
CREATE UNIQUE INDEX IF NOT EXISTS idx_records_qualified
    ON records(file_path, COALESCE(class_name, ''), function_name);
CREATE INDEX IF NOT EXISTS idx_records_file ON records(file_path);
CREATE INDEX IF NOT EXISTS idx_records_name ON records(function_name);
CREATE INDEX IF NOT EXISTS idx_test_refs_target ON test_refs(target_uuid);
CREATE INDEX IF NOT EXISTS idx_entry_points_record ON entry_points(record_uuid);
"""


class CrawlStore:
    """Python API for the crawl.db SQLite store.

    All methods operate within transactions. Records are committed
    per-function for crawl resumability.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CrawlStore not connected; call connect() first")
        return self._conn

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "CrawlStore":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── Record CRUD ───────────────────────────────────────────────

    def _insert_ins(self, record_uuid: str, ins: list[InField]) -> None:
        for i, inp in enumerate(ins):
            self.conn.execute(
                """INSERT INTO ins
                   (record_uuid, name, type_str, source, source_uuid,
                    source_file, source_function, source_description,
                    dispatch, dispatch_candidates, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_uuid, inp.name, inp.type_str, inp.source.value,
                    inp.source_uuid, inp.source_file, inp.source_function,
                    inp.source_description, inp.dispatch.value,
                    json.dumps(inp.dispatch_candidates) if inp.dispatch_candidates else None,
                    i,
                ),
            )

    def _insert_outs(self, record_uuid: str, outs: list[OutField]) -> None:
        for i, out in enumerate(outs):
            self.conn.execute(
                """INSERT INTO outs
                   (record_uuid, name, type_str, description, ordinal)
                   VALUES (?, ?, ?, ?, ?)""",
                (record_uuid, out.name.value, out.type_str, out.description, i),
            )

    def insert_record(self, record: FnRecord | AxRecord) -> None:
        skeleton_json = json.dumps(record.skeleton.to_dict()) if isinstance(record, FnRecord) and record.skeleton else None
        source_crate = record.source_crate if isinstance(record, AxRecord) else None
        boundary_contract = record.boundary_contract if isinstance(record, AxRecord) else None
        do_description = record.do_description if isinstance(record, FnRecord) else f"Assume {source_crate} behavior per documented contract"
        do_steps = json.dumps(record.do_steps) if isinstance(record, FnRecord) and record.do_steps else None
        do_branches = record.do_branches if isinstance(record, FnRecord) else None
        do_loops = record.do_loops if isinstance(record, FnRecord) else None
        do_errors = record.do_errors if isinstance(record, FnRecord) else None
        failure_modes = json.dumps(record.failure_modes) if isinstance(record, FnRecord) and record.failure_modes else None
        operational_claim = record.operational_claim if isinstance(record, FnRecord) else boundary_contract
        class_name = record.class_name if isinstance(record, FnRecord) else None
        line_number = record.line_number if isinstance(record, FnRecord) else None

        self.conn.execute(
            """INSERT INTO records
               (uuid, function_name, class_name, file_path, line_number, src_hash,
                is_external, do_description, do_steps, do_branches, do_loops,
                do_errors, failure_modes, operational_claim, skeleton_json,
                source_crate, boundary_contract, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.uuid, record.function_name, class_name,
                record.file_path, line_number, record.src_hash,
                record.is_external, do_description, do_steps,
                do_branches, do_loops, do_errors, failure_modes,
                operational_claim, skeleton_json, source_crate,
                boundary_contract, record.schema_version,
            ),
        )
        self._insert_ins(record.uuid, record.ins)
        self._insert_outs(record.uuid, record.outs)
        self.conn.commit()

    def upsert_record(self, record: FnRecord | AxRecord) -> None:
        # Null out any source_uuid references to this record before deleting,
        # in case the existing DB lacks ON DELETE SET NULL on ins.source_uuid.
        self.conn.execute(
            "UPDATE ins SET source_uuid = NULL WHERE source_uuid = ?",
            (record.uuid,),
        )
        self.conn.execute("DELETE FROM records WHERE uuid = ?", (record.uuid,))
        self.insert_record(record)

    def get_record(self, uuid: str) -> FnRecord | None:
        row = self.conn.execute(
            "SELECT * FROM records WHERE uuid = ?", (uuid,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_fn_record(row)

    def _row_to_fn_record(self, row: sqlite3.Row) -> FnRecord:
        uuid = row["uuid"]
        ins_rows = self.conn.execute(
            "SELECT * FROM ins WHERE record_uuid = ? ORDER BY ordinal", (uuid,)
        ).fetchall()
        outs_rows = self.conn.execute(
            "SELECT * FROM outs WHERE record_uuid = ? ORDER BY ordinal", (uuid,)
        ).fetchall()

        ins = [
            InField(
                name=r["name"],
                type_str=r["type_str"],
                source=InSource(r["source"]),
                source_uuid=r["source_uuid"],
                source_file=r["source_file"],
                source_function=r["source_function"],
                source_description=r["source_description"],
                dispatch=DispatchKind(r["dispatch"]),
                dispatch_candidates=json.loads(r["dispatch_candidates"]) if r["dispatch_candidates"] else None,
            )
            for r in ins_rows
        ]
        outs = [
            OutField(
                name=OutKind(r["name"]),
                type_str=r["type_str"],
                description=r["description"],
            )
            for r in outs_rows
        ]

        skeleton = None
        if row["skeleton_json"]:
            skel_data = json.loads(row["skeleton_json"])
            skeleton = Skeleton(
                function_name=skel_data["function_name"],
                file_path=skel_data["file_path"],
                line_number=skel_data["line_number"],
                class_name=skel_data.get("class_name"),
                visibility=skel_data.get("visibility", "public"),
                is_async=skel_data.get("is_async", False),
                params=[
                    SkeletonParam(name=p["name"], type=p.get("type", ""), is_self=p.get("is_self", False))
                    for p in skel_data.get("params", [])
                ],
                return_type=skel_data.get("return_type"),
                file_hash=skel_data.get("file_hash", ""),
            )

        return FnRecord(
            uuid=uuid,
            function_name=row["function_name"],
            class_name=row["class_name"],
            file_path=row["file_path"],
            line_number=row["line_number"],
            src_hash=row["src_hash"],
            is_external=bool(row["is_external"]),
            ins=ins,
            do_description=row["do_description"],
            do_steps=json.loads(row["do_steps"]) if row["do_steps"] else [],
            do_branches=row["do_branches"],
            do_loops=row["do_loops"],
            do_errors=row["do_errors"],
            outs=outs,
            failure_modes=json.loads(row["failure_modes"]) if row["failure_modes"] else [],
            operational_claim=row["operational_claim"] or "",
            skeleton=skeleton,
            schema_version=row["schema_version"],
        )

    def get_records_for_file(self, file_path: str) -> list[FnRecord]:
        rows = self.conn.execute(
            "SELECT * FROM records WHERE file_path = ? AND is_external = FALSE",
            (file_path,),
        ).fetchall()
        return [self._row_to_fn_record(r) for r in rows]

    def get_records_by_directory(self, dir_prefix: str) -> list[FnRecord]:
        """Return all records whose file_path contains *dir_prefix* as a
        directory segment.

        The prefix is normalised to be bounded by ``/`` so that
        ``get_records_by_directory("backend")`` matches
        ``/home/user/project/backend/server.js`` but not
        ``/home/user/project/backend_utils/foo.js``.

        Works with both relative and absolute stored paths.
        """
        if not dir_prefix.endswith("/"):
            dir_prefix += "/"
        # Match either: path starts with the prefix, or contains /prefix
        rows = self.conn.execute(
            "SELECT * FROM records WHERE"
            " (file_path LIKE ? OR file_path LIKE ?)"
            " AND is_external = FALSE",
            (dir_prefix + "%", "%/" + dir_prefix + "%"),
        ).fetchall()
        return [self._row_to_fn_record(r) for r in rows]

    def get_all_records(self) -> list[FnRecord]:
        rows = self.conn.execute(
            "SELECT * FROM records WHERE is_external = FALSE"
        ).fetchall()
        return [self._row_to_fn_record(r) for r in rows]

    def get_all_uuids(self) -> set[str]:
        rows = self.conn.execute("SELECT uuid FROM records").fetchall()
        return {r["uuid"] for r in rows}

    def get_pending_uuids(self) -> list[str]:
        """Return UUIDs of records that still need extraction."""
        rows = self.conn.execute(
            "SELECT uuid FROM records "
            "WHERE is_external = FALSE "
            "AND do_description IN ('SKELETON_ONLY', 'EXTRACTION_FAILED') "
            "ORDER BY file_path, line_number"
        ).fetchall()
        return [r["uuid"] for r in rows]

    # ── Staleness ─────────────────────────────────────────────────

    def get_stale_records(self, current_hashes: dict[str, str]) -> list[str]:
        """Compare current file hashes against stored src_hash.
        Returns UUIDs of directly stale records (file hash mismatch)."""
        rows = self.conn.execute(
            "SELECT uuid, file_path, src_hash FROM stale_candidates"
        ).fetchall()
        stale = []
        for r in rows:
            current = current_hashes.get(r["file_path"])
            if current is not None and current != r["src_hash"]:
                stale.append(r["uuid"])
        return stale

    def get_transitive_stale(self, direct_stale: list[str]) -> list[str]:
        """Propagate staleness transitively via recursive CTE."""
        if not direct_stale:
            return []
        placeholders = ",".join("?" for _ in direct_stale)
        rows = self.conn.execute(
            f"""WITH RECURSIVE stale(uuid) AS (
                SELECT uuid FROM records WHERE uuid IN ({placeholders})
                UNION
                SELECT i.record_uuid
                FROM ins i
                JOIN stale s ON i.source_uuid = s.uuid
            )
            SELECT DISTINCT uuid FROM stale""",
            direct_stale,
        ).fetchall()
        return [r["uuid"] for r in rows]

    # ── Subgraph extraction ───────────────────────────────────────

    def get_forward_subgraph(self, function_name: str) -> list[FnRecord]:
        rows = self.conn.execute(
            """WITH RECURSIVE forward(uuid) AS (
                SELECT uuid FROM records WHERE function_name = ?
                UNION
                SELECT i.source_uuid
                FROM ins i
                JOIN forward f ON i.record_uuid = f.uuid
                WHERE i.source_uuid IS NOT NULL
            )
            SELECT * FROM records WHERE uuid IN (SELECT uuid FROM forward)""",
            (function_name,),
        ).fetchall()
        return [self._row_to_fn_record(r) for r in rows]

    def get_reverse_subgraph(self, function_name: str) -> list[FnRecord]:
        rows = self.conn.execute(
            """WITH RECURSIVE reverse(uuid) AS (
                SELECT uuid FROM records WHERE function_name = ?
                UNION
                SELECT i.record_uuid
                FROM ins i
                JOIN reverse r ON i.source_uuid = r.uuid
            )
            SELECT * FROM records WHERE uuid IN (SELECT uuid FROM reverse)""",
            (function_name,),
        ).fetchall()
        return [self._row_to_fn_record(r) for r in rows]

    def get_full_subgraph(self, function_name: str) -> list[FnRecord]:
        forward = {r.uuid: r for r in self.get_forward_subgraph(function_name)}
        reverse = {r.uuid: r for r in self.get_reverse_subgraph(function_name)}
        forward.update(reverse)
        return list(forward.values())

    # ── Back-fill ─────────────────────────────────────────────────

    def backfill_source_uuids(self) -> int:
        """Post-crawl: resolve source_function -> source_uuid for internal_call ins."""
        result = self.conn.execute(
            """UPDATE ins SET source_uuid = (
                SELECT r.uuid FROM records r
                WHERE r.function_name = ins.source_function
                LIMIT 1
            )
            WHERE source_uuid IS NULL AND source = 'internal_call'
              AND source_function IS NOT NULL"""
        )
        self.conn.commit()
        return result.rowcount

    # ── Card rendering ────────────────────────────────────────────

    def get_card_text(self, uuid: str) -> str:
        record = self.get_record(uuid)
        if record is None:
            return f"No record found for UUID: {uuid}"
        return render_card(record)

    # ── Validation ────────────────────────────────────────────────

    def validate_completeness(self) -> list[str]:
        """Find internal_call ins with NULL source_uuid after back-fill."""
        rows = self.conn.execute(
            """SELECT i.record_uuid, i.name, i.source_function, r.function_name
               FROM ins i
               JOIN records r ON i.record_uuid = r.uuid
               WHERE i.source = 'internal_call'
                 AND i.source_uuid IS NULL"""
        ).fetchall()
        return [
            f"{r['function_name']}: input '{r['name']}' references "
            f"'{r['source_function']}' but no matching record found"
            for r in rows
        ]

    # ── Crawl run tracking ────────────────────────────────────────

    def start_crawl_run(
        self,
        target_path: str,
        language: str,
        codebase_type: str | None,
        is_incremental: bool,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO crawl_runs (target_path, language, codebase_type, is_incremental)
               VALUES (?, ?, ?, ?)""",
            (target_path, language, codebase_type, is_incremental),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def finish_crawl_run(
        self, run_id: int, created: int, updated: int, skipped: int, failed: int,
    ) -> None:
        self.conn.execute(
            """UPDATE crawl_runs
               SET completed_at = datetime('now'),
                   records_created = ?, records_updated = ?,
                   records_skipped = ?, records_failed = ?
               WHERE id = ?""",
            (created, updated, skipped, failed, run_id),
        )
        self.conn.commit()

    # ── Entry points ──────────────────────────────────────────────

    def insert_entry_point(self, ep: EntryPoint) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO entry_points
               (file_path, function_name, entry_type, route, method)
               VALUES (?, ?, ?, ?, ?)""",
            (ep.file_path, ep.function_name, ep.entry_type.value, ep.route, ep.method),
        )
        self.conn.commit()

    def get_entry_points(self) -> list[EntryPoint]:
        rows = self.conn.execute("SELECT * FROM entry_points").fetchall()
        return [
            EntryPoint(
                file_path=r["file_path"],
                function_name=r["function_name"],
                entry_type=EntryType(r["entry_type"]),
                route=r["route"],
                method=r["method"],
            )
            for r in rows
        ]

    # ── Test references ───────────────────────────────────────────

    def insert_test_ref(self, ref: TestReference) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO test_refs
               (test_file, test_function, target_uuid, target_function,
                target_file, inputs_observed, outputs_asserted, covers_error_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ref.test_file, ref.test_function, ref.target_uuid,
                ref.target_function, ref.target_file,
                json.dumps(ref.inputs_observed) if ref.inputs_observed else None,
                json.dumps(ref.outputs_asserted) if ref.outputs_asserted else None,
                ref.covers_error_path,
            ),
        )
        self.conn.commit()

    def get_test_coverage(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM test_coverage").fetchall()
        return [dict(r) for r in rows]

    # ── Map notes ─────────────────────────────────────────────────

    def insert_map(self, m: MapNote) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO maps
               (workflow_name, entry_uuid, path_uuids, shared_uuids, properties)
               VALUES (?, ?, ?, ?, ?)""",
            (
                m.workflow_name, m.entry_uuid,
                json.dumps(m.path_uuids),
                json.dumps(m.shared_uuids) if m.shared_uuids else None,
                json.dumps(m.properties) if m.properties else None,
            ),
        )
        self.conn.commit()

    def get_maps(self) -> list[MapNote]:
        rows = self.conn.execute("SELECT * FROM maps").fetchall()
        return [
            MapNote(
                workflow_name=r["workflow_name"],
                entry_uuid=r["entry_uuid"],
                path_uuids=json.loads(r["path_uuids"]),
                shared_uuids=json.loads(r["shared_uuids"]) if r["shared_uuids"] else [],
                properties=json.loads(r["properties"]) if r["properties"] else [],
            )
            for r in rows
        ]


def render_card(record: FnRecord) -> str:
    """Render a markdown IN:DO:OUT card for a single FnRecord."""
    parts: list[str] = []
    header = f"### {record.function_name}"
    if record.class_name:
        header += f" ({record.class_name})"
    header += f" @ {record.file_path}:{record.line_number}"
    parts.append(header)
    parts.append(f"\n**Claim:** {record.operational_claim}\n")

    if record.ins:
        parts.append("**IN:**")
        for inp in record.ins:
            dispatch_note = f" [{inp.dispatch.value}]" if inp.dispatch != DispatchKind.DIRECT else ""
            parts.append(f"- {inp.name}: {inp.type_str} ({inp.source.value}{dispatch_note})")

    parts.append(f"\n**DO:** {record.do_description}")
    if record.do_steps:
        for i, step in enumerate(record.do_steps, 1):
            parts.append(f"  {i}. {step}")

    if record.outs:
        parts.append("\n**OUT:**")
        for out in record.outs:
            parts.append(f"- {out.name.value}: {out.type_str} -- {out.description}")

    if record.failure_modes:
        parts.append("\n**FAILURE MODES:** " + "; ".join(record.failure_modes))

    return "\n".join(parts) + "\n"
