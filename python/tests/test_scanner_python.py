"""Tests for the Python skeleton scanner and entry point discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_python import scan_file, scan_directory
from registry.entry_points import (
    detect_codebase_type,
    discover_entry_points,
)
from registry.crawl_types import EntryType


# ── Scanner tests ─────────────────────────────────────────────────

class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "simple.py"
        src.write_text("def hello(name: str) -> str:\n    return f'Hello {name}'\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "hello"
        assert s.line_number == 1
        assert s.class_name is None
        assert s.is_async is False
        assert len(s.params) == 1
        assert s.params[0].name == "name"
        assert s.params[0].type == "str"
        assert s.return_type == "str"
        assert s.file_hash != ""

    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "async_fn.py"
        src.write_text("async def fetch(url: str) -> bytes:\n    pass\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "fetch"

    def test_class_methods(self, tmp_path: Path):
        src = tmp_path / "cls.py"
        src.write_text(
            "class MyClass:\n"
            "    def __init__(self, value: int):\n"
            "        self.value = value\n"
            "\n"
            "    def get_value(self) -> int:\n"
            "        return self.value\n"
            "\n"
            "    def _private(self):\n"
            "        pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        names = {s.function_name for s in skels}
        assert names == {"__init__", "get_value", "_private"}
        for s in skels:
            assert s.class_name == "MyClass"
        private = [s for s in skels if s.function_name == "_private"][0]
        assert private.visibility == "private"

    def test_nested_classes(self, tmp_path: Path):
        src = tmp_path / "nested.py"
        src.write_text(
            "class Outer:\n"
            "    class Inner:\n"
            "        def inner_method(self):\n"
            "            pass\n"
            "    def outer_method(self):\n"
            "        pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        inner = [s for s in skels if s.function_name == "inner_method"][0]
        assert inner.class_name == "Inner"
        outer = [s for s in skels if s.function_name == "outer_method"][0]
        assert outer.class_name == "Outer"

    def test_multiline_params(self, tmp_path: Path):
        src = tmp_path / "multiline.py"
        src.write_text(
            "def create_user(\n"
            "    name: str,\n"
            "    email: str,\n"
            "    age: int = 0,\n"
            ") -> dict:\n"
            "    pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "create_user"
        params = skels[0].params
        assert len(params) == 3
        assert params[0].name == "name"
        assert params[1].name == "email"
        assert params[2].name == "age"
        assert skels[0].return_type == "dict"

    def test_no_type_hints(self, tmp_path: Path):
        src = tmp_path / "no_types.py"
        src.write_text("def add(a, b):\n    return a + b\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].type == ""

    def test_self_param_detected(self, tmp_path: Path):
        src = tmp_path / "self_param.py"
        src.write_text(
            "class Foo:\n"
            "    def bar(self, x: int):\n"
            "        pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].is_self is True
        assert skels[0].params[0].name == "self"

    def test_cls_param_detected(self, tmp_path: Path):
        src = tmp_path / "cls_param.py"
        src.write_text(
            "class Foo:\n"
            "    @classmethod\n"
            "    def create(cls, data: dict):\n"
            "        pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].is_self is True  # cls is also flagged
        assert skels[0].params[0].name == "cls"

    def test_star_args(self, tmp_path: Path):
        src = tmp_path / "stars.py"
        src.write_text("def f(*args, **kwargs):\n    pass\n")
        skels = scan_file(src)
        assert len(skels) == 1
        params = skels[0].params
        assert params[0].name == "args"
        assert params[1].name == "kwargs"

    def test_complex_type_hints(self, tmp_path: Path):
        src = tmp_path / "complex_types.py"
        src.write_text("def f(data: dict[str, list[int]], cb: Callable[[int], bool]) -> None:\n    pass\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].name == "data"
        assert "dict" in skels[0].params[0].type

    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.py"
        src.write_text("")
        assert scan_file(src) == []

    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash_test.py"
        src.write_text("def f(): pass\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash

    def test_top_level_and_class_methods(self, tmp_path: Path):
        src = tmp_path / "mixed.py"
        src.write_text(
            "def top_level():\n"
            "    pass\n"
            "\n"
            "class Service:\n"
            "    def method(self):\n"
            "        pass\n"
            "\n"
            "def another_top():\n"
            "    pass\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        top = [s for s in skels if s.class_name is None]
        methods = [s for s in skels if s.class_name is not None]
        assert len(top) == 2
        assert len(methods) == 1
        assert methods[0].class_name == "Service"

    def test_dunder_methods_public(self, tmp_path: Path):
        src = tmp_path / "dunder.py"
        src.write_text("class X:\n    def __init__(self): pass\n    def __str__(self): pass\n")
        skels = scan_file(src)
        for s in skels:
            assert s.visibility == "public"  # dunder methods are public


class TestScanDirectory:
    def test_scans_recursively(self, tmp_path: Path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "module.py").write_text("def func(): pass\n")
        (tmp_path / "top.py").write_text("def top(): pass\n")

        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "func" in names
        assert "top" in names

    def test_excludes_pycache(self, tmp_path: Path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("def cached(): pass\n")
        (tmp_path / "real.py").write_text("def real(): pass\n")

        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "real" in names
        assert "cached" not in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.py").write_text("def vendored(): pass\n")
        (tmp_path / "app.py").write_text("def app(): pass\n")

        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names


# ── Entry point discovery tests ───────────────────────────────────

class TestDetectCodebaseType:
    def test_fastapi_detected(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100\nuvicorn\n")
        assert detect_codebase_type(tmp_path) == "web_app"

    def test_flask_detected(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["flask"]\n')
        assert detect_codebase_type(tmp_path) == "web_app"

    def test_click_detected(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("click>=8.0\n")
        assert detect_codebase_type(tmp_path) == "cli"

    def test_celery_detected(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("celery>=5.0\n")
        assert detect_codebase_type(tmp_path) == "event_driven"

    def test_library_default(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = []\n')
        assert detect_codebase_type(tmp_path) == "library"

    def test_console_scripts_is_cli(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project.scripts]\nmycli = "mypackage:main"\n'
            '[project]\ndependencies = []\n'
        )
        # console_scripts check won't match — it looks for the literal string
        # but [project.scripts] uses a different TOML key. Let's use setup.py
        (tmp_path / "setup.py").write_text(
            'setup(entry_points={"console_scripts": ["cli=app:main"]})\n'
        )
        assert detect_codebase_type(tmp_path) == "cli"


class TestDiscoverWebRoutes:
    def test_fastapi_routes(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        (tmp_path / "api.py").write_text(
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "\n"
            '@app.get("/users")\n'
            "async def list_users():\n"
            "    pass\n"
            "\n"
            '@app.post("/users")\n'
            "async def create_user():\n"
            "    pass\n"
        )
        eps = discover_entry_points(tmp_path)
        routes = [e for e in eps if e.entry_type == EntryType.HTTP_ROUTE]
        assert len(routes) == 2
        assert routes[0].function_name == "list_users"
        assert routes[0].route == "/users"
        assert routes[0].method == "GET"
        assert routes[1].method == "POST"

    def test_flask_routes(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "app.py").write_text(
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "\n"
            '@app.route("/hello")\n'
            "def hello():\n"
            "    return 'Hello'\n"
        )
        eps = discover_entry_points(tmp_path)
        routes = [e for e in eps if e.entry_type == EntryType.HTTP_ROUTE]
        assert len(routes) == 1
        assert routes[0].route == "/hello"


class TestDiscoverCliCommands:
    def test_click_commands(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("click\n")
        (tmp_path / "cli.py").write_text(
            "import click\n"
            "\n"
            "@click.command()\n"
            "def main():\n"
            "    pass\n"
        )
        eps = discover_entry_points(tmp_path)
        cmds = [e for e in eps if e.entry_type == EntryType.CLI_COMMAND]
        assert len(cmds) == 1
        assert cmds[0].function_name == "main"


class TestDiscoverMainFunctions:
    def test_main_function(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = []\n')
        (tmp_path / "app.py").write_text("def main():\n    pass\n")
        eps = discover_entry_points(tmp_path)
        mains = [e for e in eps if e.entry_type == EntryType.MAIN]
        assert len(mains) == 1
        assert mains[0].function_name == "main"

    def test_main_module(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = []\n')
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__main__.py").write_text("print('hello')\n")
        eps = discover_entry_points(tmp_path)
        mains = [e for e in eps if e.entry_type == EntryType.MAIN]
        assert any(e.function_name == "__main__" for e in mains)


class TestDiscoverPublicApi:
    def test_all_exports(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = []\n')
        pkg = tmp_path / "mylib"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["create", "delete"]\n')
        eps = discover_entry_points(tmp_path)
        api = [e for e in eps if e.entry_type == EntryType.PUBLIC_API]
        names = {e.function_name for e in api}
        assert "create" in names
        assert "delete" in names
