---
component: 4
title: "Go Skeleton Scanner"
new_files: ["python/registry/scanner_go.py"]
test_files: ["python/tests/test_scanner_go.py"]
behaviors: 10
beads: ["replication_ab_bench-7ig", "replication_ab_bench-gwo", "replication_ab_bench-yuo", "replication_ab_bench-uj6", "replication_ab_bench-86n", "replication_ab_bench-zz9", "replication_ab_bench-gb8", "replication_ab_bench-q0w", "replication_ab_bench-51v", "replication_ab_bench-7rj"]
depends_on: []
---

## Component 4: Go Skeleton Scanner

**New file**: `python/registry/scanner_go.py`
**Test file**: `python/tests/test_scanner_go.py`

Same interface as the Python and TypeScript scanners. Go-specific:
brace-depth counting, method receivers, multiple return values, exported
(capitalized) vs unexported visibility.

### Behavior 4.1: scan_file extracts simple func declarations

```python
"""Tests for the Go skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_go import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "main.go"
        src.write_text("package main\n\nfunc Hello(name string) string {\n\treturn \"Hello \" + name\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "Hello"
        assert s.params[0].name == "name"
        assert s.params[0].type == "string"
        assert s.return_type == "string"
        assert s.visibility == "public"  # capitalized = exported
```

### Behavior 4.2: scan_file extracts method receivers

**Given**: `func (s *UserService) GetUser(id int) (*User, error) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with class_name="UserService", params excluding receiver

```python
    def test_method_receiver(self, tmp_path: Path):
        src = tmp_path / "service.go"
        src.write_text(
            "package service\n\n"
            "func (s *UserService) GetUser(id int) (*User, error) {\n"
            "\treturn s.db.Find(id)\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "GetUser"
        assert s.class_name == "UserService"
        assert s.params[0].name == "id"
        assert s.params[0].type == "int"
        assert s.return_type == "(*User, error)"
```

### Behavior 4.3: scan_file handles multiple return values

```python
    def test_multiple_returns(self, tmp_path: Path):
        src = tmp_path / "multi.go"
        src.write_text(
            "package main\n\n"
            "func Divide(a, b float64) (float64, error) {\n"
            "\tif b == 0 { return 0, fmt.Errorf(\"division by zero\") }\n"
            "\treturn a / b, nil\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].return_type == "(float64, error)"
```

### Behavior 4.4: scan_file detects exported vs unexported

**Given**: Functions `GetUser` (exported) and `validateInput` (unexported)
**When**: `scan_file(path)` is called
**Then**: Visibility is "public" for exported, "private" for unexported

```python
    def test_exported_vs_unexported(self, tmp_path: Path):
        src = tmp_path / "api.go"
        src.write_text(
            "package api\n\n"
            "func GetUser(id int) *User {\n\treturn nil\n}\n\n"
            "func validateInput(data []byte) error {\n\treturn nil\n}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        get_user = next(s for s in skels if s.function_name == "GetUser")
        validate = next(s for s in skels if s.function_name == "validateInput")
        assert get_user.visibility == "public"
        assert validate.visibility == "private"
```

### Behavior 4.5: scan_file handles named return values

```python
    def test_named_returns(self, tmp_path: Path):
        src = tmp_path / "named.go"
        src.write_text(
            "package main\n\n"
            "func ParseConfig(path string) (cfg *Config, err error) {\n"
            "\treturn nil, nil\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        # Named returns are still captured as return type
        assert "Config" in skels[0].return_type
        assert "error" in skels[0].return_type
```

### Behavior 4.6: scan_file handles parameters with shared types

**Given**: `func Add(a, b int) int`  (Go shorthand: `a, b int` means both are int)
**When**: `scan_file(path)` is called
**Then**: Both params have type "int"

```python
    def test_shared_type_params(self, tmp_path: Path):
        src = tmp_path / "math.go"
        src.write_text("package main\n\nfunc Add(a, b int) int {\n\treturn a + b\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "a"
        assert skels[0].params[0].type == "int"
        assert skels[0].params[1].name == "b"
        assert skels[0].params[1].type == "int"
```

### Behavior 4.7: scan_file computes file hash

```python
    def test_file_hash(self, tmp_path: Path):
        src = tmp_path / "hash.go"
        src.write_text("package main\n\nfunc Foo() {}\n")
        skels = scan_file(src)
        assert len(skels[0].file_hash) == 64
```

### Behavior 4.8: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.go"
        src.write_text("package main\n")
        assert scan_file(src) == []
```

### Behavior 4.9: scan_file handles interface methods (skips them — no body)

```python
    def test_skips_interface_methods(self, tmp_path: Path):
        src = tmp_path / "iface.go"
        src.write_text(
            "package api\n\n"
            "type Repository interface {\n"
            "\tFind(id int) (*User, error)\n"
            "\tSave(user *User) error\n"
            "}\n\n"
            "func Concrete(x int) int {\n\treturn x + 1\n}\n"
        )
        skels = scan_file(src)
        # Only the concrete function, not interface method signatures
        assert len(skels) == 1
        assert skels[0].function_name == "Concrete"
```

### Behavior 4.10: scan_directory walks .go files, excludes vendor and _test.go

```python
class TestScanDirectory:
    def test_walks_go_files(self, tmp_path: Path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "handler.go").write_text("package pkg\n\nfunc Handle() {}\n")
        (tmp_path / "pkg" / "util.go").write_text("package pkg\n\nfunc Util() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Handle" in names
        assert "Util" in names

    def test_excludes_vendor(self, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n\nfunc Main() {}\n")
        vendor = tmp_path / "vendor" / "lib"
        vendor.mkdir(parents=True)
        (vendor / "lib.go").write_text("package lib\n\nfunc Vendored() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Main" in names
        assert "Vendored" not in names

    def test_excludes_test_files(self, tmp_path: Path):
        (tmp_path / "handler.go").write_text("package main\n\nfunc Handler() {}\n")
        (tmp_path / "handler_test.go").write_text("package main\n\nfunc TestHandler() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Handler" in names
        assert "TestHandler" not in names
```

### Success Criteria — Component 4

**Automated:**
- [x] All tests in `test_scanner_go.py` pass
- [x] All existing tests still pass
- [x] `from registry.scanner_go import scan_file, scan_directory` works

---
