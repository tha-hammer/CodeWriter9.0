---
date: 2026-03-10
parent: INDEX.md
phase: 3
title: "Phase 3: Rust Implementation"
behaviors: [B12, B13, B14, B15, B16, B17]
status: draft
---

# Phase 3: Rust Implementation

## Behavior 12: Rust assertion compiler

### Test Specification
**Given**: TLA+ condition `x \in S /\ y = 3`
**When**: Compiling for Rust
**Then**: Produces `s.contains(&x) && y == 3`

**Given**: `\A x \in S : x > 0`
**When**: Compiling for Rust
**Then**: Produces `s.iter().all(|x| x > 0)`

**Given**: `Len(seq) > 0`
**When**: Compiling for Rust
**Then**: Produces `seq.len() > 0`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py`
```python
import pytest
from registry.lang import RustProfile, CompileError


class TestRustCompiler:
    def setup_method(self):
        self.profile = RustProfile()

    def test_membership(self):
        r = self.profile.compile_condition("x \\in S")
        assert ".contains(&x)" in r.target_expr or ".contains(x)" in r.target_expr

    def test_conjunction(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "&&" in r.target_expr

    def test_equality(self):
        r = self.profile.compile_condition("y = 3")
        assert "==" in r.target_expr
        assert "===" not in r.target_expr  # not JS triple-equals

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!=" in r.target_expr

    def test_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert ".iter().all(|x|" in r.target_expr or ".iter().all(|x| x > 0)" in r.target_expr

    def test_existential_quantifier(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert ".iter().any(|x|" in r.target_expr

    def test_len(self):
        r = self.profile.compile_condition("Len(seq) > 0")
        assert ".len()" in r.target_expr

    def test_cardinality(self):
        r = self.profile.compile_condition("Cardinality(S) = 3")
        assert ".len()" in r.target_expr  # Rust uses .len() for all collections

    def test_boolean_literals(self):
        r = self.profile.compile_condition("x = TRUE")
        assert "true" in r.target_expr

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.count" in r.target_expr  # Rust uses dot access for struct fields

    def test_disjunction(self):
        r = self.profile.compile_condition("x = 1 \\/ y = 2")
        assert "||" in r.target_expr

    def test_unsupported_raises(self):
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")

    # --- compile_assertions (batch) ---

    def test_compile_assertions_produces_rust_expressions(self):
        """Verifies compiler hints use Rust, not Python."""
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert ".contains(" in results["inv_membership"].target_expr
```

#### Green
**File**: `python/registry/lang_rust.py`

Implements the mapping:
| TLA+ | Rust |
|------|------|
| `\in` | `.contains(&x)` |
| `/\` | `&&` |
| `\/` | `\|\|` |
| `=` | `==` |
| `#` | `!=` |
| `\A x \in S : P` | `s.iter().all(\|x\| P)` |
| `\E x \in S : P` | `s.iter().any(\|x\| P)` |
| `Len(x)` | `x.len()` |
| `Cardinality(S)` | `s.len()` |
| `TRUE/FALSE` | `true/false` |
| `state.field` | `state.field` |

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustCompiler` passes
- [x] Full suite still passes

---

## Behavior 13: Rust API context discovery

### Test Specification
**Given**: A directory with `.rs` files containing `pub fn`, `pub struct`, `pub trait`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the public signatures

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustApiDiscovery:
    def test_finds_pub_functions(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "dag.rs").write_text(
            "pub struct RegistryDag {\n"
            "    nodes: Vec<Node>,\n"
            "}\n\n"
            "impl RegistryDag {\n"
            "    pub fn query_impact(&self, node_id: &str) -> ImpactResult {\n"
            "        todo!()\n"
            "    }\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "RegistryDag")
        assert "pub struct RegistryDag" in result
        assert "pub fn query_impact" in result

    def test_finds_traits(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "types.rs").write_text(
            "pub trait Queryable {\n"
            "    fn query(&self, id: &str) -> Option<Node>;\n"
            "}\n\n"
            "pub enum EdgeType {\n"
            "    Imports,\n"
            "    Exports,\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "Queryable")
        assert "pub trait Queryable" in result
        assert "pub enum EdgeType" in result

    def test_finds_impl_blocks(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "lib.rs").write_text(
            "impl Dag {\n"
            "    pub fn new() -> Self { todo!() }\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "Dag")
        assert "pub fn new" in result

    def test_no_source_returns_comment(self, tmp_path):
        profile = RustProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result
```

#### Green
Implement `RustProfile.discover_api_context()`:
- Glob for `*.rs` files
- Extract lines starting with `pub fn`, `pub struct`, `pub trait`, `pub enum`, `pub type`, `impl`, `use`
- Include doc comments (`///`) preceding public items

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustApiDiscovery` passes

---

## Behavior 14: Rust prompts and structural patterns

### Test Specification
**Given**: `RustProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions Rust, `#[test]`, not Python/pytest

**When**: Calling `build_structural_patterns()`
**Then**: Contains `#[test]`, `assert!`, `assert_eq!`, Rust `use` syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains `use` statements

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustPrompts:
    def setup_method(self):
        self.profile = RustProfile()

    def test_system_prompt_mentions_rust(self):
        prompt = self.profile.build_system_prompt()
        assert "Rust" in prompt
        assert "Python" not in prompt
        assert "TypeScript" not in prompt

    def test_system_prompt_mentions_test_attr(self):
        prompt = self.profile.build_system_prompt()
        assert "#[test]" in prompt or "#[cfg(test)]" in prompt

    def test_structural_patterns_has_rust_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "#[test]" in patterns
        assert "assert" in patterns  # assert!, assert_eq!
        assert "fn test_" in patterns

    def test_structural_patterns_has_use_statements(self):
        patterns = self.profile.build_structural_patterns()
        assert "use " in patterns

    def test_import_instructions_has_rust_syntax(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "use " in instructions
```

#### Green
Implement the three prompt methods with Rust-idiomatic code examples:
```python
class RustProfile:
    def build_system_prompt(self) -> str:
        return (
            "You are a Rust test generation expert. You generate complete, runnable "
            "Rust test modules from formal specifications and API documentation. "
            "You use ONLY the real crate imports provided — never create mock structs "
            "or re-implement the API. Use #[cfg(test)] modules with #[test] functions. "
            "Output ONLY Rust code, no markdown fencing or explanation."
        )

    def build_structural_patterns(self) -> str:
        return (
            "```rust\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::*;\n\n"
            "    // Pattern: fixture construction from trace Init state\n"
            "    fn make_dag(nodes: &[&str], edges: &[(&str, &str)]) -> RegistryDag {\n"
            "        let mut dag = RegistryDag::new();\n"
            "        for nid in nodes {\n"
            "            dag.add_node(Node::behavior(nid, nid, \"g\", \"w\", \"t\"));\n"
            "        }\n"
            "        for (src, dst) in edges {\n"
            "            dag.add_edge(Edge::new(src, dst, EdgeType::Imports));\n"
            "        }\n"
            "        dag\n"
            "    }\n\n"
            "    #[test]\n"
            "    fn test_invariant() {\n"
            "        let dag = make_dag(&[\"a\", \"b\"], &[(\"a\", \"b\")]);\n"
            "        let result = dag.query_impact(\"a\");\n"
            "        assert!(!result.is_empty());\n"
            "    }\n\n"
            "    #[test]\n"
            "    #[should_panic(expected = \"not found\")]\n"
            "    fn test_invalid_input() {\n"
            "        let dag = make_dag(&[], &[]);\n"
            "        dag.query_impact(\"nonexistent\");\n"
            "    }\n"
            "}\n"
            "```\n"
        )

    def build_import_instructions(self, module_name: str) -> str:
        return (
            f"- CRITICAL: Use EXACT crate/module paths from the API Context section above.\n"
            f"  Use `use {module_name}::dag::RegistryDag;` for the main type\n"
            f"  Use `use {module_name}::types::{{Node, Edge, EdgeType}};` for type imports\n"
            f"- Place tests in a `#[cfg(test)] mod tests` block with `use super::*;`\n"
        )
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustPrompts` passes

---

## Behavior 15: Rust test file verification

### Test Specification
**Given**: A valid Rust test file
**When**: Calling `verify_test_file()`
**Then**: Runs `cargo check` → `cargo test --no-run` → `cargo test`

**Given**: A `.rs` file with a compile error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustVerification:
    def test_verify_catches_compile_error(self, tmp_path):
        profile = RustProfile()
        test_file = tmp_path / "test_bad.rs"
        test_file.write_text("fn main() { let x: i32 = \"not a number\"; }")
        result = profile.verify_test_file(test_file, tmp_path)
        assert not result.passed
        assert result.stage == "compile"

    def test_verify_passes_valid_test(self, tmp_path):
        """Integration test — requires cargo in PATH."""
        profile = RustProfile()
        # Set up minimal Cargo project
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "test_proj"\nversion = "0.1.0"\nedition = "2021"\n'
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "lib.rs").write_text(
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    #[test]\n"
            "    fn it_works() {\n"
            "        assert_eq!(2 + 2, 4);\n"
            "    }\n"
            "}\n"
        )
        result = profile.verify_test_file(src / "lib.rs", tmp_path)
        assert result.passed
```

**Note**: Tests that invoke `cargo` MUST be marked `@pytest.mark.integration`.
The `conftest.py` auto-skip logic (added in B5b) handles skipping when `cargo` isn't installed.

```python
@pytest.mark.integration
class TestRustVerification:
    ...
```

#### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess
    from registry.lang import VerifyResult

    # Stage 1: Compile check
    result = subprocess.run(
        ["cargo", "check"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="compile",
                          errors=[f"cargo check failed (rc={result.returncode})"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 2: Test discovery (compile tests without running)
    result = subprocess.run(
        ["cargo", "test", "--no-run"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="collect",
                          errors=[f"cargo test --no-run failed"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 3: Run tests
    result = subprocess.run(
        ["cargo", "test"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="run",
                          errors=[f"cargo test failed"],
                          stdout=result.stdout, stderr=result.stderr)

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustVerification` passes (with mocked subprocess or integration mark)

---

## Behavior 16: Rust code extraction from LLM response

### Test Specification
**Given**: LLM response with `` ```rust\n...code...\n``` ``
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the Rust code without fences

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustExtraction:
    def test_strips_rust_fences(self):
        profile = RustProfile()
        response = '```rust\n#[test]\nfn test_it() { assert!(true); }\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith("#[test]")
        assert "```" not in code

    def test_strips_bare_fences(self):
        profile = RustProfile()
        response = '```\nfn main() {}\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code
        assert "fn main" in code

    def test_handles_no_fences(self):
        profile = RustProfile()
        response = "#[test]\nfn test_it() { assert!(true); }"
        code = profile.extract_code_from_response(response)
        assert "#[test]" in code
```

#### Green
```python
def extract_code_from_response(self, response: str) -> str:
    # Delegates to shared helper from lang.py (B2 refactor)
    return _extract_code_by_fence_tag(response, self.fence_language_tag)
    # fence_language_tag = "rust|rs" matches both ```rust and ```rs
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustExtraction` passes

---

## Behavior 17: Rust output file naming

### Test Specification
**Given**: `RustProfile` and a gwt_id
**When**: Calling `test_file_name(gwt_id)`
**Then**: Returns idiomatic Rust test file name

### TDD Cycle

#### Red: Write Failing Test
```python
class TestRustOutputPath:
    def test_rust_output_path(self):
        profile = RustProfile()
        gwt_id = "gwt-0024"
        expected = "test_gwt_0024.rs"
        assert profile.test_file_name(gwt_id) == expected

    def test_rust_file_extension(self):
        profile = RustProfile()
        assert profile.test_file_extension == ".rs"

    def test_rust_fence_tag(self):
        profile = RustProfile()
        assert profile.fence_language_tag == "rust"
```

#### Green
```python
class RustProfile:
    test_file_extension: str = ".rs"
    fence_language_tag: str = "rust|rs"  # regex alternation for fence extraction

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"test_{safe_id}.rs"

    def compile_assertions(self, verifiers, state_var="state"):
        results = {}
        for name, v in verifiers.items():
            if condition := v.get("condition", ""):
                results[name] = self.compile_condition(condition, state_var)
        return results

    def extract_code_from_response(self, response):
        return _extract_code_by_fence_tag(response, self.fence_language_tag)
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_rust.py::TestRustOutputPath` passes

---

## Phase 3 Checkpoint

At this point:
- `RustProfile` fully implements `LanguageProfile`
- `cw9 gen-tests gwt-0024 --lang rust` produces `.rs` test files
- Python and TypeScript paths are unchanged
- Three implementations validate the abstraction

**Gate**: `pytest` full suite passes. Manual: `cw9 gen-tests gwt-0024 --lang rust`
on a project with `.rs` source files.
