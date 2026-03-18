---
component: 6
title: "JavaScript Skeleton Scanner"
new_files: ["python/registry/scanner_javascript.py"]
test_files: ["python/tests/test_scanner_javascript.py"]
behaviors: 14
beads: ["replication_ab_bench-55q", "replication_ab_bench-52w", "replication_ab_bench-vhs", "replication_ab_bench-afm", "replication_ab_bench-4a6", "replication_ab_bench-xjr", "replication_ab_bench-jax", "replication_ab_bench-97z", "replication_ab_bench-1p5", "replication_ab_bench-zxs", "replication_ab_bench-wgm", "replication_ab_bench-2h7", "replication_ab_bench-4zu", "replication_ab_bench-8mb"]
depends_on: []
---

## Component 6: JavaScript Skeleton Scanner

**New file**: `python/registry/scanner_javascript.py`
**Test file**: `python/tests/test_scanner_javascript.py`

Fully independent scanner for JavaScript (not a wrapper around the TypeScript
scanner). Same interface: `scan_file(path) -> list[Skeleton]` and
`scan_directory(root, excludes) -> list[Skeleton]`. JavaScript-specific: no type
annotations, CommonJS `module.exports`/`exports.name` patterns, `.js`/`.jsx` extensions.

**Design decisions:**
- Fully independent regex set (not importing from scanner_typescript)
- No type annotations → simpler param parsing (just param names)
- CommonJS patterns detected: `module.exports = function name(...)`, `exports.name = function(...)`,
  `module.exports = (...)  =>`, `exports.name = (...) =>`
- `module.exports = function(...)` without a name → function_name derived as "default_export"
- `module.exports = (...)  =>` → function_name = "default_export"
- Class methods detected via same brace-depth approach as TypeScript
- File extensions: `*.js`, `*.jsx`
- Skip `.min.js` minified files
- Don't skip test files (matches TS scanner convention)

### Regex Patterns (design reference)

```python
# function greet(name) {
# export function greet(name) {
# export default function main() {
# async function loadData() {
_FUNC_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(async\s+)?"                      # optional async
    r"function\s+(\w+)"                 # function keyword + name
    r"\s*\("                            # opening paren
)

# const handler = (req, res) => {
# export const handler = async (req) => {
# let processor = function(data) {
_ARROW_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(?:const|let|var)\s+(\w+)"        # binding keyword + name
    r"\s*=\s*"                          # assignment
    r"(async\s+)?"                      # optional async
    r"(?:function\s*)?(?:\w+\s*)?"      # optional function keyword + name (function expression)
    r"\("                               # opening paren
)

# class UserService {
# export class UserService extends Base {
_CLASS_RE = re.compile(
    r"^(\s*)"
    r"(?:export\s+)?(?:default\s+)?"
    r"class\s+(\w+)"
)

# Method inside a class (must be indented):
#   async getUser(id) {
#   #privateMethod(data) {
_METHOD_RE = re.compile(
    r"^(\s+)"                           # must be indented
    r"(?:static\s+)?(?:get\s+|set\s+)?"  # optional static/getter/setter
    r"(async\s+)?"                      # optional async
    r"(#?\w+)"                          # method name (# for private fields)
    r"\s*\("                            # opening paren
)

# module.exports = function handler(req, res) {
# module.exports = function(req, res) {
# module.exports = (req, res) => {
# module.exports = async (req) => {
_MODULE_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"module\.exports\s*=\s*"
    r"(async\s+)?"
    r"(?:function\s+(\w+)\s*)?"         # optional function + name
    r"\("                               # opening paren
)

# exports.handler = function(req, res) {
# exports.handler = (req, res) => {
# exports.handler = async function process(req) {
_NAMED_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"exports\.(\w+)\s*=\s*"            # exports.name =
    r"(async\s+)?"                      # optional async
    r"(?:function\s*(?:\w+\s*)?)?"      # optional function keyword + optional name
    r"\("                               # opening paren
)
```

### Behavior 6.1: scan_file extracts simple function declarations

**Given**: A JavaScript file with `function greet(name) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="greet", params=[name], no return type

```python
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
```

### Behavior 6.2: scan_file extracts exported functions

**Given**: `export function fetchUser(id) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with visibility="public"

```python
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
```

### Behavior 6.3: scan_file extracts async functions

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "data.js"
        src.write_text("async function loadData() {\n  return await fetch('/api');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "loadData"
```

### Behavior 6.4: scan_file extracts arrow functions assigned to const/let/var

**Given**: `export const handler = (req, res) => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler"

```python
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
```

### Behavior 6.5: scan_file extracts function expressions

**Given**: `const processor = function processData(data) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="processor" (the binding name)

```python
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
```

### Behavior 6.6: scan_file extracts class methods

**Given**: A JavaScript class with methods
**When**: `scan_file(path)` is called
**Then**: Methods have correct class_name

```python
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
```

### Behavior 6.7: scan_file extracts module.exports function

**Given**: `module.exports = function handler(req, res) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler", visibility="public"

```python
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
```

### Behavior 6.8: scan_file extracts exports.name patterns

**Given**: `exports.handler = function(req, res) { ... }` and `exports.validate = (data) => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeletons with function names from the exports property

```python
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
```

### Behavior 6.9: scan_file handles multiline signatures

```python
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
```

### Behavior 6.10: scan_file handles destructured and rest parameters

```python
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
```

### Behavior 6.11: scan_file computes file hash

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.js"
        src.write_text("function foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64
```

### Behavior 6.12: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.js"
        src.write_text("")
        assert scan_file(src) == []
```

### Behavior 6.13: scan_file handles mixed CommonJS and ES module patterns

**Given**: A file mixing `exports.name = ...` and `function` declarations
**When**: `scan_file(path)` is called
**Then**: All functions are captured without duplicates

```python
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
```

### Behavior 6.14: scan_directory walks .js and .jsx files

```python
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
```

### Success Criteria — Component 6

**Automated:**
- [x] All tests in `test_scanner_javascript.py` pass
- [x] All existing tests still pass: `python -m pytest tests/ -x`
- [x] `from registry.scanner_javascript import scan_file, scan_directory` works

---
