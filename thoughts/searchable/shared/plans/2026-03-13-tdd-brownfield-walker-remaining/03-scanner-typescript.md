---
component: 3
title: "TypeScript Skeleton Scanner"
new_files: ["python/registry/scanner_typescript.py"]
test_files: ["python/tests/test_scanner_typescript.py"]
behaviors: 10
beads: ["replication_ab_bench-opd", "replication_ab_bench-cfq", "replication_ab_bench-9z9", "replication_ab_bench-tvn", "replication_ab_bench-5i1", "replication_ab_bench-b20", "replication_ab_bench-wur", "replication_ab_bench-ur6", "replication_ab_bench-ex0", "replication_ab_bench-5qu"]
depends_on: []
---

## Component 3: TypeScript Skeleton Scanner

**New file**: `python/registry/scanner_typescript.py`
**Test file**: `python/tests/test_scanner_typescript.py`

Follows the same interface as `scanner_python.py`: `scan_file(path) -> list[Skeleton]` and
`scan_directory(root, excludes) -> list[Skeleton]`. Uses line-by-line text scanning with
brace-depth counting for function boundaries.

### Behavior 3.1: scan_file extracts simple function declarations

**Given**: A TypeScript file with `function greet(name: string): string { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="greet", params, return_type="string"

```python
"""Tests for the TypeScript skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_typescript import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "greet.ts"
        src.write_text("function greet(name: string): string {\n  return `Hello ${name}`;\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "greet"
        assert s.params[0].name == "name"
        assert s.params[0].type == "string"
        assert s.return_type == "string"
        assert s.file_path == str(src)
        assert s.line_number == 1
```

### Behavior 3.2: scan_file extracts exported functions

**Given**: `export function fetchUser(id: number): Promise<User> { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with visibility="public" (export implies public)

```python
    def test_exported_function(self, tmp_path: Path):
        src = tmp_path / "user.ts"
        src.write_text("export function fetchUser(id: number): Promise<User> {\n  return db.get(id);\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchUser"
        assert skels[0].visibility == "public"
        assert skels[0].return_type == "Promise<User>"
```

### Behavior 3.3: scan_file extracts async functions

**Given**: `async function loadData(): Promise<Data[]> { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with is_async=True

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "data.ts"
        src.write_text("async function loadData(): Promise<Data[]> {\n  return await fetch('/api');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "loadData"
```

### Behavior 3.4: scan_file extracts class methods

**Given**: A TypeScript class with public and private methods
**When**: `scan_file(path)` is called
**Then**: Returns Skeletons with correct class_name, one method per entry

```python
    def test_class_methods(self, tmp_path: Path):
        src = tmp_path / "service.ts"
        src.write_text(
            "class UserService {\n"
            "  constructor(private db: Database) {}\n"
            "\n"
            "  async getUser(id: number): Promise<User> {\n"
            "    return this.db.find(id);\n"
            "  }\n"
            "\n"
            "  private validate(user: User): boolean {\n"
            "    return user.isActive;\n"
            "  }\n"
            "}\n"
        )
        skels = scan_file(src)
        methods = [s for s in skels if s.class_name == "UserService"]
        assert len(methods) >= 2
        names = {s.function_name for s in methods}
        assert "getUser" in names
        assert "validate" in names

        validate = next(s for s in methods if s.function_name == "validate")
        assert validate.visibility == "private"
```

### Behavior 3.5: scan_file extracts arrow functions assigned to const/let

**Given**: `export const handler = (req: Request): Response => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler"

```python
    def test_arrow_function(self, tmp_path: Path):
        src = tmp_path / "handler.ts"
        src.write_text(
            "export const handler = (req: Request, res: Response): void => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "req"
        assert skels[0].params[0].type == "Request"
```

### Behavior 3.6: scan_file handles multiline signatures

**Given**: A function with parameters split across multiple lines
**When**: `scan_file(path)` is called
**Then**: All parameters are captured

```python
    def test_multiline_signature(self, tmp_path: Path):
        src = tmp_path / "multi.ts"
        src.write_text(
            "function createUser(\n"
            "  name: string,\n"
            "  email: string,\n"
            "  age: number\n"
            "): User {\n"
            "  return { name, email, age };\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[2].name == "age"
        assert skels[0].params[2].type == "number"
```

### Behavior 3.7: scan_file computes file hash

**Given**: A TypeScript file
**When**: `scan_file(path)` is called twice on the same file
**Then**: The file_hash is identical and is a valid SHA-256 hex string

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.ts"
        src.write_text("function foo(): void {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64  # SHA-256 hex
```

### Behavior 3.8: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.ts"
        src.write_text("")
        assert scan_file(src) == []
```

### Behavior 3.9: scan_file handles export default function

```python
    def test_export_default_function(self, tmp_path: Path):
        src = tmp_path / "default.ts"
        src.write_text("export default function main(): void {\n  console.log('hi');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "main"
```

### Behavior 3.10: scan_directory walks .ts and .tsx files, excludes node_modules

```python
class TestScanDirectory:
    def test_walks_ts_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.ts").write_text("function a(): void {}\n")
        (tmp_path / "src" / "b.tsx").write_text("function B(): JSX.Element { return <div/>; }\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "a" in names
        assert "B" in names

    def test_excludes_node_modules(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.ts").write_text("function app(): void {}\n")
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.ts").write_text("function internal(): void {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "internal" not in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.ts").write_text("function vendored(): void {}\n")
        (tmp_path / "app.ts").write_text("function app(): void {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names
```

### Success Criteria — Component 3

**Automated:**
- [x] All tests in `test_scanner_typescript.py` pass
- [x] All existing tests still pass
- [x] `from registry.scanner_typescript import scan_file, scan_directory` works

---
