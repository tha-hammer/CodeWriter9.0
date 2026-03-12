# Plan Review Report: Gate Self-Describe to Self-Hosting Mode Only (CW9-7oz)

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ✅ | 0 issues |
| Interfaces | ⚠️ | 1 issue |
| Promises | ⚠️ | 1 issue |
| Data Models | ⚠️ | 1 issue |
| APIs | ✅ | 0 issues |

---

### Contract Review

#### Well-Defined:
- ✅ `is_self_hosting` property — `engine_root is not None and engine_root == target_root` correctly distinguishes self-hosting (both equal), external (both set, differ), and installed (`engine_root=None`) modes. `from_target` delegates to `self_hosting()` when roots match, so the check is sound.
- ✅ `self_host: bool` parameter on `SchemaExtractor` — clean additive change, default `False` preserves safety for any new callers
- ✅ Error contract — no new error paths introduced; gating is a simple conditional skip
- ✅ All 6 production callers confirmed at exact lines with `ctx` available. All `run_*_loop.py` files use `ProjectContext.self_hosting(PROJECT_ROOT)`, so `is_self_hosting → True` automatically.

#### Missing or Unclear:
- None

---

### Interface Review

#### Well-Defined:
- ✅ `SchemaExtractor.__init__` gains `self_host: bool = False` — backward-compatible, keyword-only addition
- ✅ `get_template_dir(kind)` already resolves `templates/{kind}` generically — `"schema_external"` works without changes to `_resources.py`
- ✅ Template mirroring strategy (both `templates/schema_external/` and `python/registry/_data/templates/schema_external/`) matches existing `schema` pattern

#### Missing or Unclear:
- ⚠️ **Naming inconsistency**: Parameter is `self_host` on `SchemaExtractor` but the concept is `is_self_hosting` on `ProjectContext`. Consider `self_host=ctx.is_self_hosting` reads naturally at call sites, so this is acceptable — but an alternative like `include_self_description=True` would make the extractor's interface self-documenting without requiring knowledge of the hosting model. **Low priority — current naming is functional.**

#### Recommendations:
- No blocking changes needed

---

### Promise Review

#### Well-Defined:
- ✅ Self-hosting behavior preserved — all `run_*_loop.py` scripts use `ProjectContext.self_hosting()`, so `is_self_hosting=True`, so `self_host=True` passed to extractor
- ✅ `test_artifacts` assignment (inside `_self_describe`) is automatically gated by containment
- ✅ Idempotency unaffected — `extract()` remains deterministic given same inputs

#### Missing or Unclear:
- ⚠️ **External project node count promise unclear**: Plan says "~0 nodes" for external extract, but also says `assert len >= 6` still holds. With empty `resources: {}` templates AND gated `_self_describe`, the node count depends entirely on what `test_external_pipeline.py`'s `external_dag` fixture provides. If the fixture creates its own custom schemas with resources, the `>= 6` assertion may hold. But the plan doesn't clarify this — it says "6 resources from the minimal external schemas remain" which contradicts Step 6's `"resources": {}` (empty). **Needs clarification: where do the 6 resources come from after the change?**

#### Recommendations:
- Clarify whether `test_external_pipeline.py` creates its own schemas (independent of templates) or relies on the template files. If the fixture uses templates, the `>= 6` assertion will fail with empty templates.

---

### Data Model Review

#### Well-Defined:
- ✅ External template structure mirrors existing schema structure — same 5 files, same top-level keys
- ✅ Empty sections (`"resources": {}`, `"processors": {}`, etc.) are valid for the schema parser
- ✅ `resource_registry.generic.json` retains `$schema`, `uuid_format`, `schemas` header — preserving the schema metadata contract

#### Missing or Unclear:
- ⚠️ **External template content not fully specified**: Plan lists top-level keys for `backend_schema.json` but doesn't show the full structure for all 4 layer schemas. Are all 4 identical in structure? The current CW9 schemas have different keys per layer (e.g., frontend has different sections than backend). Do the external templates need to match the _current_ key sets exactly (just empty), or is a generic empty structure acceptable? **Low priority if SchemaExtractor tolerates missing keys.**

#### Recommendations:
- Verify SchemaExtractor handles missing/extra keys in layer schemas gracefully
- Consider generating external templates programmatically from existing ones (strip values, keep keys) to ensure structural consistency

---

### API Review

#### Well-Defined:
- ✅ `cw9 init` behavior: external projects get clean empty templates; self-hosting gets existing templates
- ✅ `cw9 extract` behavior: external projects get no self-description nodes; self-hosting unchanged
- ✅ ID space clean: external projects start at `gwt-0001` without collisions from pre-existing CW9 IDs

#### Missing or Unclear:
- None

---

### Critical Issues (Must Address Before Implementation)

None — all issues are warnings, not blockers.

### Minor Issues (Should Address)

1. **Promise/Test Clarity**: The plan claims `assert len >= 6` still holds but doesn't explain the source of 6 nodes when templates have `"resources": {}`. Verify the `external_dag` fixture's schema source before implementing Step 5.
   - Impact: Test may fail unexpectedly if fixture relies on templates
   - Recommendation: Read the `external_dag` fixture definition and trace its schema source

2. **Template Content Completeness**: External template layer schemas should match the key structure of existing schemas (with empty values) to avoid parser issues.
   - Impact: SchemaExtractor may log warnings or skip sections if keys are missing
   - Recommendation: Mirror exact key structure from existing templates

---

### Suggested Plan Amendments

```diff
# In Step 5: Fix test_external_pipeline.py assertions

+ Add: Verify external_dag fixture schema source — confirm whether
+       it uses templates or creates schemas independently
~ Modify: assert len >= 6 → update based on actual expected node
~         count after self_describe gating (may need to be >= 0)

# In Step 6: Create minimal external-project templates

+ Add: Verify SchemaExtractor handles empty section values without
+       errors (e.g., empty processors: {}, empty services: {})
+ Add: Confirm all layer schema key sets match existing templates
```

### Approval Status

- [x] **Ready for Implementation** — No critical issues. Warnings are low-risk and can be resolved during implementation.

### Review Checklist

#### Contracts
- [x] Component boundaries are clearly defined
- [x] Input/output contracts are specified
- [x] Error contracts enumerate all failure modes
- [x] Preconditions and postconditions are documented
- [x] Invariants are identified

#### Interfaces
- [x] All public methods are defined with signatures
- [x] Naming follows codebase conventions
- [x] Interface matches existing patterns
- [x] Extension points are considered
- [x] Visibility modifiers are appropriate

#### Promises
- [x] Behavioral guarantees are documented
- [x] Async operations have timeout/cancellation handling (N/A — synchronous)
- [x] Resource cleanup is specified (N/A — no new resources)
- [ ] Idempotency requirements are addressed — **verify test node count promise**
- [x] Ordering guarantees are documented where needed

#### Data Models
- [x] All fields have types
- [x] Required vs optional is clear
- [x] Relationships are documented
- [x] Migration strategy is defined (N/A — new templates, no migration)
- [x] Serialization format is specified (JSON, matches existing)

#### APIs
- [x] All endpoints are defined
- [x] Request/response formats are specified
- [x] Error responses are documented
- [x] Authentication requirements are clear (N/A)
- [x] Versioning strategy is defined (N/A)
