"""Tests for the JavaScript skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_javascript import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "greet.js"
        src.write_text("function greet(name) {\n  return `Hello ${name}`;\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "greet"
        assert s.params[0].name == "name"
        assert s.params[0].type == ""  # no type annotations in JS
        assert s.return_type is None
        assert s.file_path == str(src)
        assert s.line_number == 1

    def test_exported_function(self, tmp_path: Path):
        src = tmp_path / "user.js"
        src.write_text("export function fetchUser(id) {\n  return db.get(id);\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchUser"
        assert skels[0].visibility == "public"

    def test_export_default_function(self, tmp_path: Path):
        src = tmp_path / "default.js"
        src.write_text("export default function main() {\n  console.log('hi');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "main"
        assert skels[0].visibility == "public"

    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "data.js"
        src.write_text("async function loadData() {\n  return await fetch('/api');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "loadData"

    def test_arrow_function(self, tmp_path: Path):
        src = tmp_path / "handler.js"
        src.write_text(
            "export const handler = (req, res) => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "req"
        assert skels[0].params[1].name == "res"
        assert skels[0].visibility == "public"  # export

    def test_async_arrow_function(self, tmp_path: Path):
        src = tmp_path / "async_arrow.js"
        src.write_text(
            "const fetchData = async (url) => {\n"
            "  return await fetch(url);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchData"
        assert skels[0].is_async is True

    def test_function_expression(self, tmp_path: Path):
        src = tmp_path / "expr.js"
        src.write_text(
            "const processor = function processData(data) {\n"
            "  return data.map(x => x * 2);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "processor"
        assert skels[0].params[0].name == "data"

    def test_class_methods(self, tmp_path: Path):
        src = tmp_path / "service.js"
        src.write_text(
            "class UserService {\n"
            "  constructor(db) {\n"
            "    this.db = db;\n"
            "  }\n\n"
            "  async getUser(id) {\n"
            "    return this.db.find(id);\n"
            "  }\n\n"
            "  #validate(user) {\n"
            "    return user.isActive;\n"
            "  }\n"
            "}\n"
        )
        skels = scan_file(src)
        methods = [s for s in skels if s.class_name == "UserService"]
        assert len(methods) >= 2
        names = {s.function_name for s in methods}
        assert "getUser" in names
        # Private field methods (# prefix) detected
        assert "#validate" in names or "validate" in names

    def test_module_exports_named_function(self, tmp_path: Path):
        src = tmp_path / "server.js"
        src.write_text(
            "module.exports = function handler(req, res) {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert skels[0].visibility == "public"

    def test_module_exports_anonymous_function(self, tmp_path: Path):
        src = tmp_path / "anon.js"
        src.write_text(
            "module.exports = function(data) {\n"
            "  return process(data);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "default_export"
        assert skels[0].visibility == "public"

    def test_module_exports_arrow(self, tmp_path: Path):
        src = tmp_path / "arrow_export.js"
        src.write_text(
            "module.exports = (req, res) => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "default_export"
        assert skels[0].visibility == "public"

    def test_named_exports_function(self, tmp_path: Path):
        src = tmp_path / "routes.js"
        src.write_text(
            "exports.getUser = function(id) {\n"
            "  return db.find(id);\n"
            "};\n\n"
            "exports.createUser = (name, email) => {\n"
            "  return db.insert({ name, email });\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        names = {s.function_name for s in skels}
        assert "getUser" in names
        assert "createUser" in names
        for s in skels:
            assert s.visibility == "public"

    def test_exports_async_function(self, tmp_path: Path):
        src = tmp_path / "async_exports.js"
        src.write_text(
            "exports.fetch = async function fetchData(url) {\n"
            "  return await get(url);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetch"
        assert skels[0].is_async is True

    def test_multiline_params(self, tmp_path: Path):
        src = tmp_path / "multi.js"
        src.write_text(
            "function createUser(\n"
            "  name,\n"
            "  email,\n"
            "  age\n"
            ") {\n"
            "  return { name, email, age };\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[2].name == "age"

    def test_rest_params(self, tmp_path: Path):
        src = tmp_path / "rest.js"
        src.write_text(
            "function collect(first, ...rest) {\n"
            "  return [first, ...rest];\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "first"
        assert skels[0].params[1].name == "rest"

    def test_default_params(self, tmp_path: Path):
        src = tmp_path / "defaults.js"
        src.write_text(
            "function greet(name = 'World') {\n"
            "  return `Hello ${name}`;\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].name == "name"

    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.js"
        src.write_text("function foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64

    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.js"
        src.write_text("")
        assert scan_file(src) == []

    def test_mixed_patterns(self, tmp_path: Path):
        src = tmp_path / "mixed.js"
        src.write_text(
            "function validate(data) {\n"
            "  return data != null;\n"
            "}\n\n"
            "exports.handler = function(req, res) {\n"
            "  if (validate(req.body)) {\n"
            "    res.send('ok');\n"
            "  }\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        names = {s.function_name for s in skels}
        assert "validate" in names
        assert "handler" in names


class TestScanDirectory:
    def test_walks_js_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("function app() {}\n")
        (tmp_path / "src" / "Button.jsx").write_text(
            "function Button(props) {\n  return <button>{props.label}</button>;\n}\n"
        )
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "Button" in names

    def test_excludes_node_modules(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("function app() {}\n")
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("function internal() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "internal" not in names

    def test_excludes_min_js(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("function app() {}\n")
        (tmp_path / "bundle.min.js").write_text("function minified() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "minified" not in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.js").write_text("function vendored() {}\n")
        (tmp_path / "app.js").write_text("function app() {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names

    def test_does_not_scan_ts_files(self, tmp_path: Path):
        """JavaScript scanner only handles .js/.jsx, not .ts/.tsx."""
        (tmp_path / "app.js").write_text("function jsApp() {}\n")
        (tmp_path / "app.ts").write_text("function tsApp(): void {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "jsApp" in names
        assert "tsApp" not in names
