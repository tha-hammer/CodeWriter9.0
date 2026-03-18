---
component: 5
title: "Rust Skeleton Scanner"
new_files: ["python/registry/scanner_rust.py"]
test_files: ["python/tests/test_scanner_rust.py"]
behaviors: 16
beads: ["replication_ab_bench-du2", "replication_ab_bench-v6v", "replication_ab_bench-4u6", "replication_ab_bench-zja", "replication_ab_bench-lkf", "replication_ab_bench-9mu", "replication_ab_bench-c0i", "replication_ab_bench-st1", "replication_ab_bench-zlc", "replication_ab_bench-2br", "replication_ab_bench-y54", "replication_ab_bench-l6e", "replication_ab_bench-nv0", "replication_ab_bench-nwr", "replication_ab_bench-n93", "replication_ab_bench-5fk"]
depends_on: []
---

## Component 5: Rust Skeleton Scanner

**New file**: `python/registry/scanner_rust.py`
**Test file**: `python/tests/test_scanner_rust.py`

Same interface as the Python/TypeScript/Go scanners. Rust-specific: `impl` blocks
for class context (brace-depth stack), `trait` blocks skipped (like Go interfaces),
visibility via `pub`/`pub(crate)` keywords, lifetime annotations and generics in
signatures, `where` clauses for multi-line signatures, `&self`/`&mut self` params.

**Design decisions:**
- `pub` = "public", no `pub` = "private", `pub(crate)`/`pub(super)` = "private" (crate-internal)
- `#[cfg(test)]` module functions are **ingested** (not skipped) — used as confirmatory first pass
- `trait` blocks are skipped entirely (abstract method signatures, no body)
- Lifetime annotations stripped from param types for cleaner Skeleton output
- `where` clauses handled: return type is between `->` and `where`/`{`

### Regex Patterns (design reference)

```python
# fn hello(name: &str) -> String {
# pub fn hello(name: &str) -> String {
# pub(crate) fn process(data: Vec<u8>) -> Result<(), Error> {
# async fn fetch(url: &str) -> Result<Response, Error> {
# pub async unsafe fn raw_ptr(p: *const u8) -> u8 {
# pub(super) const fn max_size() -> usize {
_FUNC_RE = re.compile(
    r"^(\s*)"                                    # leading whitespace
    r"(pub(?:\s*\([^)]*\))?\s+)?"               # optional pub/pub(crate)/pub(super)
    r"(?:default\s+)?"                           # optional default (trait impl)
    r"(?:const\s+)?"                             # optional const
    r"(async\s+)?"                               # optional async
    r"(?:unsafe\s+)?"                            # optional unsafe
    r"(?:extern\s+\"[^\"]*\"\s+)?"              # optional extern "C"
    r"fn\s+(\w+)"                                # fn keyword + name
    r"\s*(?:<[^{(]*?>)?"                         # optional generic params <T, U>
    r"\s*\("                                     # opening paren
)

# impl UserService {
# impl<T: Clone> Repository<T> {
# impl<'a> Decoder<'a> for MyDecoder {
_IMPL_RE = re.compile(
    r"^(\s*)impl\b"                              # impl keyword
    r"(?:\s*<[^{]*?>)?"                          # optional generic params
    r"\s+(\w+)"                                  # type name
)

# trait Repository {
# pub trait Handler<T> {
_TRAIT_RE = re.compile(
    r"^(\s*)(?:pub(?:\s*\([^)]*\))?\s+)?trait\s+(\w+)"
)
```

### Behavior 5.1: scan_file extracts simple fn declarations

**Given**: A Rust file with `fn hello(name: &str) -> String { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="hello", params, return_type="String"

```python
"""Tests for the Rust skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_rust import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "lib.rs"
        src.write_text('fn hello(name: &str) -> String {\n    format!("Hello {}", name)\n}\n')
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "hello"
        assert s.params[0].name == "name"
        assert s.params[0].type == "&str"
        assert s.return_type == "String"
        assert s.visibility == "private"  # no pub = private
        assert s.file_path == str(src)
        assert s.line_number == 1
```

### Behavior 5.2: scan_file detects pub visibility

**Given**: Functions with `pub fn`, `pub(crate) fn`, `pub(super) fn`, and bare `fn`
**When**: `scan_file(path)` is called
**Then**: `pub fn` = "public", all others = "private"

```python
    def test_pub_visibility(self, tmp_path: Path):
        src = tmp_path / "vis.rs"
        src.write_text(
            "pub fn exported(x: i32) -> i32 { x }\n\n"
            "fn internal(x: i32) -> i32 { x }\n\n"
            "pub(crate) fn crate_only(x: i32) -> i32 { x }\n\n"
            "pub(super) fn parent_only(x: i32) -> i32 { x }\n"
        )
        skels = scan_file(src)
        assert len(skels) == 4
        by_name = {s.function_name: s for s in skels}
        assert by_name["exported"].visibility == "public"
        assert by_name["internal"].visibility == "private"
        assert by_name["crate_only"].visibility == "private"
        assert by_name["parent_only"].visibility == "private"
```

### Behavior 5.3: scan_file detects async fn

**Given**: `pub async fn fetch(url: &str) -> Result<Response, Error>`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with is_async=True

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "net.rs"
        src.write_text(
            "pub async fn fetch(url: &str) -> Result<Response, Error> {\n"
            "    reqwest::get(url).await\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "fetch"
        assert skels[0].visibility == "public"
```

### Behavior 5.4: scan_file extracts impl block methods with class_name

**Given**: An `impl UserService { ... }` block with methods
**When**: `scan_file(path)` is called
**Then**: Methods have class_name="UserService"

```python
    def test_impl_block_methods(self, tmp_path: Path):
        src = tmp_path / "service.rs"
        src.write_text(
            "struct UserService;\n\n"
            "impl UserService {\n"
            "    pub fn new() -> Self {\n"
            "        UserService\n"
            "    }\n\n"
            "    pub fn get_user(&self, id: u64) -> Option<User> {\n"
            "        self.db.find(id)\n"
            "    }\n\n"
            "    fn validate(&self, user: &User) -> bool {\n"
            "        user.is_active()\n"
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        for s in skels:
            assert s.class_name == "UserService"
        by_name = {s.function_name: s for s in skels}
        assert by_name["new"].visibility == "public"
        assert by_name["get_user"].visibility == "public"
        assert by_name["validate"].visibility == "private"
```

### Behavior 5.5: scan_file handles &self and &mut self params

**Given**: Methods with `&self`, `&mut self`, `self`, `mut self`
**When**: `scan_file(path)` is called
**Then**: Self params have is_self=True and are included in the params list

```python
    def test_self_params(self, tmp_path: Path):
        src = tmp_path / "methods.rs"
        src.write_text(
            "struct Foo;\n\n"
            "impl Foo {\n"
            "    fn by_ref(&self) -> i32 { 0 }\n"
            "    fn by_mut_ref(&mut self, val: i32) { self.x = val; }\n"
            "    fn by_value(self) -> Foo { self }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        by_name = {s.function_name: s for s in skels}

        ref_params = by_name["by_ref"].params
        assert ref_params[0].is_self is True
        assert ref_params[0].name == "self"

        mut_params = by_name["by_mut_ref"].params
        assert mut_params[0].is_self is True
        assert mut_params[1].name == "val"
        assert mut_params[1].type == "i32"

        val_params = by_name["by_value"].params
        assert val_params[0].is_self is True
```

### Behavior 5.6: scan_file skips trait blocks

**Given**: A file with a `trait` definition and a concrete function
**When**: `scan_file(path)` is called
**Then**: Only the concrete function is returned, trait method signatures are skipped

```python
    def test_skips_trait_blocks(self, tmp_path: Path):
        src = tmp_path / "traits.rs"
        src.write_text(
            "pub trait Repository {\n"
            "    fn find(&self, id: u64) -> Option<Entity>;\n"
            "    fn save(&mut self, entity: Entity) -> Result<(), Error>;\n"
            "}\n\n"
            "fn concrete(x: i32) -> i32 {\n"
            "    x + 1\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "concrete"
```

### Behavior 5.7: scan_file handles generic functions and lifetime annotations

**Given**: Functions with generics `<T>`, lifetimes `<'a>`, and trait bounds
**When**: `scan_file(path)` is called
**Then**: Function name is captured; generic params don't pollute param list

```python
    def test_generic_function(self, tmp_path: Path):
        src = tmp_path / "generic.rs"
        src.write_text(
            "fn first<T>(items: &[T]) -> Option<&T> {\n"
            "    items.first()\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "first"
        assert skels[0].params[0].name == "items"
        assert skels[0].params[0].type == "&[T]"

    def test_lifetime_annotation(self, tmp_path: Path):
        src = tmp_path / "lifetime.rs"
        src.write_text(
            "fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {\n"
            "    if x.len() > y.len() { x } else { y }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "longest"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "x"
        assert skels[0].return_type == "&'a str"
```

### Behavior 5.8: scan_file handles where clauses

**Given**: A function with a `where` clause spanning multiple lines
**When**: `scan_file(path)` is called
**Then**: Return type is captured correctly (between `->` and `where`)

```python
    def test_where_clause(self, tmp_path: Path):
        src = tmp_path / "where_fn.rs"
        src.write_text(
            "fn display_all<T>(items: Vec<T>) -> String\n"
            "where\n"
            "    T: Display + Debug,\n"
            "{\n"
            "    items.iter().map(|i| format!(\"{}\", i)).collect()\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "display_all"
        assert skels[0].return_type == "String"
        assert skels[0].params[0].name == "items"
        assert skels[0].params[0].type == "Vec<T>"
```

### Behavior 5.9: scan_file handles multiline parameter lists

**Given**: A function with parameters split across multiple lines
**When**: `scan_file(path)` is called
**Then**: All parameters are captured

```python
    def test_multiline_params(self, tmp_path: Path):
        src = tmp_path / "multi.rs"
        src.write_text(
            "pub fn create_user(\n"
            "    name: String,\n"
            "    email: String,\n"
            "    age: u32,\n"
            ") -> Result<User, Error> {\n"
            "    Ok(User { name, email, age })\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[0].name == "name"
        assert skels[0].params[0].type == "String"
        assert skels[0].params[2].name == "age"
        assert skels[0].params[2].type == "u32"
        assert skels[0].return_type == "Result<User, Error>"
```

### Behavior 5.10: scan_file handles unsafe, const, extern fn modifiers

```python
    def test_unsafe_function(self, tmp_path: Path):
        src = tmp_path / "unsafe_fn.rs"
        src.write_text(
            "pub unsafe fn deref_raw(ptr: *const u8) -> u8 {\n"
            "    *ptr\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "deref_raw"
        assert skels[0].visibility == "public"

    def test_const_function(self, tmp_path: Path):
        src = tmp_path / "const_fn.rs"
        src.write_text(
            "pub const fn max_size() -> usize {\n"
            "    1024\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "max_size"

    def test_extern_function(self, tmp_path: Path):
        src = tmp_path / "ffi.rs"
        src.write_text(
            'pub extern "C" fn ffi_init(ctx: *mut Context) -> i32 {\n'
            "    0\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "ffi_init"
```

### Behavior 5.11: scan_file ingests functions inside #[cfg(test)] modules

**Given**: A file with a `#[cfg(test)] mod tests { ... }` block containing test functions
**When**: `scan_file(path)` is called
**Then**: Test functions are included in the output (ingested, not skipped)

```python
    def test_cfg_test_functions_ingested(self, tmp_path: Path):
        src = tmp_path / "with_tests.rs"
        src.write_text(
            "pub fn add(a: i32, b: i32) -> i32 {\n"
            "    a + b\n"
            "}\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::*;\n\n"
            "    #[test]\n"
            "    fn test_add() {\n"
            "        assert_eq!(add(2, 3), 5);\n"
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        names = {s.function_name for s in skels}
        assert "add" in names
        assert "test_add" in names
        assert len(skels) == 2
```

### Behavior 5.12: scan_file handles impl-for-trait blocks

**Given**: `impl Display for UserService { fn fmt(&self, f: &mut Formatter) -> Result { ... } }`
**When**: `scan_file(path)` is called
**Then**: Method has class_name="UserService" (the concrete type, not the trait)

```python
    def test_impl_for_trait(self, tmp_path: Path):
        src = tmp_path / "display.rs"
        src.write_text(
            "use std::fmt;\n\n"
            "struct UserService;\n\n"
            "impl fmt::Display for UserService {\n"
            "    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {\n"
            '        write!(f, "UserService")\n'
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fmt"
        assert skels[0].class_name == "UserService"
```

### Behavior 5.13: scan_file computes file hash

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.rs"
        src.write_text("fn foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64  # SHA-256 hex
```

### Behavior 5.14: scan_file returns empty list for empty/no-function files

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.rs"
        src.write_text("")
        assert scan_file(src) == []

    def test_struct_only_file(self, tmp_path: Path):
        src = tmp_path / "types.rs"
        src.write_text(
            "pub struct User {\n"
            "    pub name: String,\n"
            "    pub email: String,\n"
            "}\n"
        )
        assert scan_file(src) == []
```

### Behavior 5.15: scan_file handles nested impl blocks correctly

**Given**: Multiple impl blocks for different types in the same file
**When**: `scan_file(path)` is called
**Then**: Each method gets the correct class_name from its enclosing impl block

```python
    def test_multiple_impl_blocks(self, tmp_path: Path):
        src = tmp_path / "multi_impl.rs"
        src.write_text(
            "struct Foo;\n"
            "struct Bar;\n\n"
            "impl Foo {\n"
            "    fn do_foo(&self) -> i32 { 1 }\n"
            "}\n\n"
            "impl Bar {\n"
            "    fn do_bar(&self) -> i32 { 2 }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        by_name = {s.function_name: s for s in skels}
        assert by_name["do_foo"].class_name == "Foo"
        assert by_name["do_bar"].class_name == "Bar"
```

### Behavior 5.16: scan_directory walks .rs files, excludes target/

```python
class TestScanDirectory:
    def test_walks_rs_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn lib_fn() {}\n")
        (tmp_path / "src" / "main.rs").write_text("fn main() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "lib_fn" in names
        assert "main" in names

    def test_excludes_target(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn app() {}\n")
        target = tmp_path / "target" / "debug"
        target.mkdir(parents=True)
        (target / "build.rs").write_text("fn build_artifact() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "build_artifact" not in names

    def test_does_not_skip_test_files(self, tmp_path: Path):
        """Rust test files are ingested for confirmatory/first-pass use."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "integration_test.rs").write_text(
            "fn test_add() {\n    assert_eq!(add(1, 2), 3);\n}\n"
        )
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "add" in names
        assert "test_add" in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.rs").write_text("fn vendored() {}\n")
        (tmp_path / "app.rs").write_text("fn app() {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names
```

### Success Criteria — Component 5

**Automated:**
- [x] All tests in `test_scanner_rust.py` pass
- [x] All existing tests still pass: `python -m pytest tests/ -x`
- [x] `from registry.scanner_rust import scan_file, scan_directory` works

---
