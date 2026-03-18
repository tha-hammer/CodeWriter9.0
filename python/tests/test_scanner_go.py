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

    def test_file_hash(self, tmp_path: Path):
        src = tmp_path / "hash.go"
        src.write_text("package main\n\nfunc Foo() {}\n")
        skels = scan_file(src)
        assert len(skels[0].file_hash) == 64

    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.go"
        src.write_text("package main\n")
        assert scan_file(src) == []

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
