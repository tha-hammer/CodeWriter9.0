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

    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.rs"
        src.write_text("fn foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64  # SHA-256 hex

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
