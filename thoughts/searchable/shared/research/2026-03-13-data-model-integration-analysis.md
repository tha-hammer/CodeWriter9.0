---
title: "Data Model Integration Analysis: Brownfield Code Walker ↔ CW9 Pipeline"
date: 2026-03-13
tags: [analysis, data-model, brownfield, pipeline, integration]
status: complete
---

# Data Model Integration Analysis

## Methodology

Traced every data path from `cw9 ingest` through `query_context()` → `format_prompt_context()` → `_build_prompt()` → LLM → `compile_compose_verify()` → `run_tlc()` → `bridge` → `gen-tests`. Verified which `Node` fields are actually read by production code, how edges flow through the DAG, and where the proposed crawl data model connects (or fails to connect) to the existing pipeline.

---

## Critical Finding #1: GWT→RESOURCE Edge Wiring Is Missing

### The Problem

The plan's core assumption is:

> `extract_subgraph(gwt_id)` already gives the minimal ancestor+descendant subgraph for a given GWT. Once the registry is populated from real code via `ingest`, this subgraph contains exactly the IN:DO:OUT context the LLM needs.

This is **false**. `extract_subgraph()` and `query_relevant()` traverse the DAG's transitive closure. But **no mechanism exists to create edges from GWT nodes to crawl-originated RESOURCE nodes**.

Evidence:
- `cmd_register()` (cli.py:431-505) only creates `DECOMPOSES` edges from requirements to GWTs
- `register_gwt()` (dag.py:313-352) creates `Node.behavior()` with no outgoing edges
- The register payload schema has no `depends_on` field for GWT→RESOURCE wiring
- In the existing greenfield pipeline, `query_relevant(gwt_id)` returns **empty** `transitive_deps` — GWTs have zero outgoing edges

### What This Means

After `cw9 ingest` populates dag.json with RESOURCE nodes and `cw9 register` adds GWT nodes, the two sets of nodes are **disconnected islands** in the DAG. `query_context(gwt_id)` returns:
- `behavior` = the GWT Node (Given/When/Then)
- `transitive_deps` = **empty** (no outgoing edges from GWT)
- `cards` = **empty** (no deps to look up in crawl.db)

The IN:DO:OUT cards sit in crawl.db unused. The LLM never sees them.

### How the Greenfield Pipeline Works Without These Edges

The existing pipeline bypasses the DAG for behavioral context:
- `context_text` (plan files from `--context-file` or copied from CW7 `plan_path`) provides the primary specification context
- `format_prompt_context()` renders only the GWT Given/When/Then
- `bundle.schemas` is populated but **never rendered** (no `## Schemas` section in `format_prompt_context()`)
- The LLM generates PlusCal from the GWT text + supplementary context + template — NOT from DAG-derived RESOURCE data

### Required Fix

Two things must happen:
1. **Extend the register payload** to accept `depends_on` edges from GWTs to RESOURCE nodes
2. **`gwt-author` must produce these edges** — its output includes `depends_on: [uuid1, uuid2]` which become `DEPENDS_ON` edges in dag.json

---

## Critical Finding #2: `merge_registered_nodes()` Destroys Crawl Nodes

### The Problem

`merge_registered_nodes()` (dag.py:373-401) only preserves nodes with `gwt-` or `req-` prefixes:

```python
prefix = nid.split("-")[0] if "-" in nid else ""
if prefix not in ("gwt", "req"):
    continue
```

Crawl-originated RESOURCE node UUIDs are uuid5 strings like `"a1b2c3d4-e5f6-..."`. When split on `"-"`, the prefix is `"a1b2c3d4"` — not `"gwt"` or `"req"`. These nodes are **silently dropped**.

### When This Fires

`cw9 pipeline` Phase 0 calls `cmd_extract` (cli.py:619), which:
1. Creates a **fresh** DAG from `SchemaExtractor.extract()` (line 221)
2. Calls `dag.merge_registered_nodes(old_dag)` (line 226) — preserves only gwt/req nodes
3. Saves to dag.json (line 229) — all crawl RESOURCE nodes are gone

So the sequence `cw9 ingest` → `cw9 pipeline` **destroys all ingested RESOURCE nodes** on the first run.

### Required Fix

Either:
- **Option A**: Extend `merge_registered_nodes()` to also preserve crawl-originated nodes (detect via crawl.db UUID lookup)
- **Option B**: Don't store crawl nodes in dag.json. Have `query_context()` query crawl.db directly via a separate path.
- **Option C**: Use a recognizable prefix for crawl node IDs (e.g., `"fn-"` prefix) and add `"fn"` to the merge whitelist.

---

## Important Finding #3: `add_node()` Already Upserts

### The Discovery

The plan specifies a new `upsert_node()` method. But `add_node()` (dag.py:36-40) already silently overwrites:

```python
def add_node(self, node: Node) -> None:
    self.nodes[node.id] = node  # dict assignment — overwrites existing
```

There is **no duplicate check**. `add_node()` IS `upsert_node()`.

### Impact

The plan's `upsert_node()` method is unnecessary. The existing `add_node()` works for both initial ingestion and incremental re-ingestion. Only `remove_node()` (for orphan cleanup) is genuinely new.

---

## Important Finding #4: `node.description` Is the Key Integration Point

### How It Works

For dependency nodes in `transitive_deps`, `format_prompt_context()` renders:
```
- {node.id} ({node.kind.value}): {node.name} — {node.description}
```

This is the **only** DAG-derived text that reaches the LLM for RESOURCE nodes (besides the GWT itself). For crawl-originated RESOURCE nodes:
- `node.name` = `"function_name @ file_path"` ← good, identifies the function
- `node.description` = `operational_claim` ← the one-liner behavioral summary

This means the `Transitive Dependencies` section provides a **summary view** of relevant functions. The full IN:DO:OUT cards (from `ContextBundle.cards`) provide the detail.

The plan correctly uses `operational_claim` as `description`, but should explicitly document this as the key integration point between the summary (DAG-derived) and detail (crawl.db-derived) views.

---

## Important Finding #5: `bundle.schemas` Is Never Rendered

### The Gap

`query_context()` populates `bundle.schemas` from `node.schema` on RESOURCE nodes (one_shot_loop.py:137-138). But `format_prompt_context()` has **no section** that renders `bundle.schemas`. The field is assembled and silently discarded.

This is a pre-existing gap in the greenfield pipeline. The plan's `cards` field would need explicit rendering (which the updated plan does specify) — but the plan should also note that `schemas` has the same gap and should either be rendered or removed.

---

## Important Finding #6: Dead Node Fields

Three `Node` fields are never read by any production code:
- `source_schema` — zero reads outside serialization
- `source_key` — zero reads outside serialization
- `version` — zero reads outside serialization

These exist for informational/debugging purposes but don't affect pipeline behavior.

---

## Important Finding #7: Downstream Stages Don't Read the DAG

After `query_context()` + `format_prompt_context()` + `_build_prompt()`:
- **Bridge** (`bridge.py`): Reads only `.tla` file text. No DAG access.
- **Gen-tests** (`cli.py:335-428`): Reads `node.given/when/then` from the DAG for the test preamble. No other DAG fields.
- **TLC** (`one_shot_loop.py:355-430`): Pure subprocess on `.tla/.cfg` files.

This confirms: the DAG/crawl data model only matters at the `query_context()` → `format_prompt_context()` boundary. Everything downstream operates on text artifacts.

---

## Data Flow Diagram (Corrected)

```
cw9 ingest
  └─ crawl.db: FnRecord rows with IN:DO:OUT
  └─ dag.json: RESOURCE nodes (id, kind, name=fn@file, description=claim)
               + CALLS/DEPENDS_ON edges between RESOURCE nodes
               ⚠️ NO edges to GWT nodes yet

cw9 gwt-author
  └─ reads crawl.db for relevant cards
  └─ outputs register-compatible JSON WITH depends_on edges
  └─ piped to cw9 register

cw9 register (EXTENDED)
  └─ creates BEHAVIOR nodes (gwt-NNNN)
  └─ creates REQUIREMENT nodes (req-NNNN)
  └─ creates DECOMPOSES edges (req → gwt)
  └─ NEW: creates DEPENDS_ON edges (gwt → RESOURCE)  ← THIS IS THE KEY

query_context(gwt_id)
  └─ dag.query_relevant(gwt_id)
  └─ closure[gwt_id] now includes RESOURCE nodes (via DEPENDS_ON edges)
  └─ for each RESOURCE UUID in transitive_deps:
     └─ look up in crawl.db → FnRecord
     └─ append to bundle.cards
  └─ format_prompt_context() renders:
     - ## Target Behavior (Given/When/Then)
     - ## Transitive Dependencies (id, kind, name, description)
     - ## Existing Code Behavior (full IN:DO:OUT cards from crawl.db)
     - ## Dependency Edges (from → to with edge type)
```
