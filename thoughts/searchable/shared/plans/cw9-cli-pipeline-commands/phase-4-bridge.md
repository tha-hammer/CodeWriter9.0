╔═══════════════════════════════════════╗
║  PHASE 4: cw9 bridge <gwt-id>        ║
╚═══════════════════════════════════════╝

## Overview

Reads a verified `.tla` spec from `.cw9/specs/<gwt-id>.tla`, runs `run_bridge()`, saves bridge artifacts to `.cw9/bridge/<gwt-id>_bridge_artifacts.json`.

## Changes Required

### 1. `python/registry/cli.py` — `cmd_bridge()`

```python
def cmd_bridge(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    gwt_id = args.gwt_id

    spec_path = ctx.spec_dir / f"{gwt_id}.tla"
    if not spec_path.exists():
        print(f"No verified spec found: {spec_path}", file=sys.stderr)
        print(f"Run: cw9 loop {gwt_id}", file=sys.stderr)
        return 1

    from registry.bridge import run_bridge
    tla_text = spec_path.read_text()
    result = run_bridge(tla_text)

    artifacts = {
        "gwt_id": gwt_id,
        "module_name": result.module_name,
        "data_structures": result.data_structures,
        "operations": result.operations,
        "verifiers": result.verifiers,
        "assertions": result.assertions,
    }
    artifact_path = ctx.artifact_dir / f"{gwt_id}_bridge_artifacts.json"
    artifact_path.write_text(json.dumps(artifacts, indent=2) + "\n")

    print(f"Bridge artifacts saved: {artifact_path}")
    print(f"  data_structures: {len(result.data_structures)}")
    print(f"  operations: {len(result.operations)}")
    print(f"  verifiers: {len(result.verifiers)}")
    print(f"  assertions: {len(result.assertions)}")

    return 0
```

### 2. Argparse wiring

```python
p_bridge = sub.add_parser("bridge", help="Translate verified spec → bridge artifacts")
p_bridge.add_argument("gwt_id", help="GWT behavior ID")
p_bridge.add_argument("target_dir", nargs="?", default=".")
```

## Tests

```python
class TestBridge:
    def test_bridge_no_cw9_fails(self, target_dir):
        rc = main(["bridge", "gwt-0001", str(target_dir)])
        assert rc == 1

    def test_bridge_no_spec_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["bridge", "gwt-0001", str(target_dir)])
        assert rc == 1
        assert "no verified spec" in capsys.readouterr().err.lower()

    def test_bridge_with_spec(self, target_dir):
        main(["init", str(target_dir)])
        spec_dir = target_dir / ".cw9" / "specs"
        spec_dir.mkdir(exist_ok=True)
        spec_path = spec_dir / "gwt-test.tla"
        spec_path.write_text(_MINIMAL_TLA_SPEC)  # defined as test fixture
        rc = main(["bridge", "gwt-test", str(target_dir)])
        assert rc == 0
        artifact_path = target_dir / ".cw9" / "bridge" / "gwt-test_bridge_artifacts.json"
        assert artifact_path.exists()
        data = json.loads(artifact_path.read_text())
        assert data["gwt_id"] == "gwt-test"
```

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_cli.py::TestBridge -v` — all pass

### Manual:
- [ ] After `cw9 loop gwt-0021`, `cw9 bridge gwt-0021` produces artifact JSON
