"""Data models for the brownfield code walker (IN:DO:OUT crawl).

Pydantic BaseModel is used only for models populated from LLM output:
InField, OutField, FnRecord, AxRecord.  All other models use @dataclass
to match existing CW9 patterns.
"""

from __future__ import annotations

import uuid as uuid_mod
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field as PydField, field_validator


# ── Fixed namespace for deterministic UUID generation ─────────────
CRAWL_NAMESPACE = uuid_mod.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def make_record_uuid(
    file_path: str, function_name: str, class_name: str | None = None,
) -> str:
    """Deterministic uuid5 from (file_path, class_name, function_name).

    Stable across re-ingests for the same function at the same path.
    """
    qualified = f"{file_path}::{class_name or ''}::{function_name}"
    return str(uuid_mod.uuid5(CRAWL_NAMESPACE, qualified))


# ── Enums ─────────────────────────────────────────────────────────

class InSource(str, Enum):
    PARAMETER = "parameter"
    STATE = "state"
    LITERAL = "literal"
    INTERNAL_CALL = "internal_call"
    EXTERNAL = "external"


class OutKind(str, Enum):
    OK = "ok"
    ERR = "err"
    SIDE_EFFECT = "side_effect"
    MUTATION = "mutation"


class DispatchKind(str, Enum):
    DIRECT = "direct"
    ATTRIBUTE = "attribute"
    DYNAMIC = "dynamic"
    OVERRIDE = "override"
    CALLBACK = "callback"
    PROTOCOL = "protocol"


class EntryType(str, Enum):
    HTTP_ROUTE = "http_route"
    CLI_COMMAND = "cli_command"
    PUBLIC_API = "public_api"
    EVENT_HANDLER = "event_handler"
    MAIN = "main"
    TEST = "test"


# ── Skeleton (pre-pass output, deterministic) ────────────────────

@dataclass
class SkeletonParam:
    name: str
    type: str = ""
    is_self: bool = False


@dataclass
class Skeleton:
    """Output of the language-specific scanner. Deterministic, no LLM."""
    function_name: str
    file_path: str
    line_number: int
    class_name: str | None = None
    visibility: str = "public"
    is_async: bool = False
    params: list[SkeletonParam] = field(default_factory=list)
    return_type: str | None = None
    file_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "function_name": self.function_name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "class_name": self.class_name,
            "visibility": self.visibility,
            "is_async": self.is_async,
            "params": [{"name": p.name, "type": p.type, "is_self": p.is_self} for p in self.params],
            "return_type": self.return_type,
            "file_hash": self.file_hash,
        }


# ── IN:DO:OUT fields (LLM boundary — Pydantic) ──────────────────

class InField(BaseModel):
    """Populated from LLM output. Pydantic validates structured extraction."""
    name: str
    type_str: str
    source: InSource
    source_uuid: str | None = None
    source_file: str | None = None
    source_function: str | None = None
    source_description: str | None = None
    dispatch: DispatchKind = DispatchKind.DIRECT
    dispatch_candidates: list[str] | None = None

    @field_validator("source_uuid")
    @classmethod
    def validate_uuid_format(cls, v: str | None) -> str | None:
        # Accept any non-empty string — the LLM cannot produce valid UUIDs
        # during extraction (it doesn't know them).  Real UUIDs are resolved
        # post-hoc by the orchestrator from the call graph.
        return v


class OutField(BaseModel):
    """Populated from LLM output. Pydantic validates structured extraction."""
    name: OutKind
    type_str: str
    description: str = ""


# ── Core records (LLM boundary — Pydantic) ───────────────────────

class FnRecord(BaseModel):
    """Internal function behavioral record. Populated from LLM extraction."""
    uuid: str
    function_name: str
    class_name: str | None = None
    file_path: str
    line_number: int | None = None
    src_hash: str
    is_external: bool = False
    ins: list[InField]
    do_description: str
    do_steps: list[str] = PydField(default_factory=list)
    do_branches: str | None = None
    do_loops: str | None = None
    do_errors: str | None = None
    outs: list[OutField]
    failure_modes: list[str] = PydField(default_factory=list)
    operational_claim: str = ""
    skeleton: Skeleton | None = None
    schema_version: int = 1

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        uuid_mod.UUID(v)
        return v


class AxRecord(BaseModel):
    """External boundary record (AX card)."""
    uuid: str
    function_name: str
    file_path: str
    src_hash: str
    is_external: bool = True
    source_crate: str
    ins: list[InField]
    outs: list[OutField]
    boundary_contract: str
    schema_version: int = 1

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        uuid_mod.UUID(v)
        return v


# ── Non-LLM models (deterministic — @dataclass) ─────────────────

@dataclass
class MapNote:
    """Workflow structure linking FN cards into end-to-end paths."""
    workflow_name: str
    entry_uuid: str
    path_uuids: list[str] = field(default_factory=list)
    shared_uuids: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)


@dataclass
class EntryPoint:
    """Entry point detected by the language-specific scanner."""
    file_path: str
    function_name: str
    entry_type: EntryType
    route: str | None = None
    method: str | None = None


@dataclass
class TestReference:
    """Cross-reference between a test and the function it tests."""
    test_file: str
    test_function: str
    target_function: str
    target_file: str
    target_uuid: str | None = None
    inputs_observed: list[str] = field(default_factory=list)
    outputs_asserted: list[str] = field(default_factory=list)
    covers_error_path: bool = False
