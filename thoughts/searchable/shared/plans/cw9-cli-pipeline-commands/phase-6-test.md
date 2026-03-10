╔═══════════════════════════════════════╗
║  PHASE 6: cw9 test                   ║
╚═══════════════════════════════════════╝

## Overview

Runs generated tests. With `--node`, uses `query_affected_tests()` to run only tests affected by that node. Without `--node`, runs all generated tests.

## Changes Required

### 1. `python/registry/cli.py` — `cmd_test()`

```python
def cmd_test(args: argparse.Namespace) -> int:
    import subprocess

    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    test_dir = ctx.test_output_dir

    if not test_dir.exists() or not list(test_dir.glob("test_*.py")):
        print(f"No generated tests in {test_dir}", file=sys.stderr)
        print("Run: cw9 gen-tests <gwt-id>", file=sys.stderr)
        return 1

    test_files = []

    if args.node_id:
        from registry.dag import RegistryDag
        dag_path = ctx.state_root / "dag.json"
        if not dag_path.exists():
            print("No DAG found. Run: cw9 extract", file=sys.stderr)
            return 1
        dag = RegistryDag.load(dag_path)

        # Populate test_artifacts from bridge artifact files
        for artifact_file in ctx.artifact_dir.glob("*_bridge_artifacts.json"):
            data = json.loads(artifact_file.read_text())
            gwt_id = data.get("gwt_id", "")
            test_path = test_dir / f"test_{gwt_id.replace('-', '_')}.py"
            if test_path.exists():
                dag.test_artifacts[gwt_id] = str(test_path)

        affected = dag.query_affected_tests(args.node_id)
        if not affected:
            print(f"No tests affected by {args.node_id}")
            return 0
        test_files = affected
        print(f"Running {len(test_files)} affected test(s) for {args.node_id}")
    else:
        test_files = [str(f) for f in sorted(test_dir.glob("test_*.py"))]
        print(f"Running {len(test_files)} generated test(s)")

    result = subprocess.run(
        ["python3", "-m", "pytest"] + test_files + ["-v"],
        cwd=str(ctx.python_dir),
    )
    return result.returncode
```

### 2. Argparse wiring

```python
p_test = sub.add_parser("test", help="Run generated tests (smart targeting optional)")
p_test.add_argument("--node", dest="node_id", help="Only run tests affected by this node")
p_test.add_argument("target_dir", nargs="?", default=".")
```

## Tests

```python
class TestTest:
    def test_test_no_generated_tests_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["test", str(target_dir)])
        assert rc == 1
        assert "no generated tests" in capsys.readouterr().err.lower()

    def test_test_runs_generated_files(self, target_dir):
        main(["init", str(target_dir)])
        test_dir = target_dir / "tests" / "generated"
        test_dir.mkdir(parents=True)
        (test_dir / "test_sample.py").write_text("def test_pass(): assert True\n")
        rc = main(["test", str(target_dir)])
        assert rc == 0
```

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_cli.py::TestTest -v` — all pass

### Manual:
- [ ] Full pipeline: `cw9 extract && cw9 loop gwt-0024 && cw9 bridge gwt-0024 && cw9 gen-tests gwt-0024 && cw9 test`
- [ ] Smart targeting: `cw9 test --node db-b7r2` runs only affected tests
