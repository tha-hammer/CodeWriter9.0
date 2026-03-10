"""ProjectContext — decouples engine, target, and state paths.

Three roots:
  engine_root — where CW9's own code lives (templates, tools, python/registry)
  target_root — where the external project's source code lives
  state_root  — where the DAG, schemas, specs, and artifacts live for that project

For CW9 self-hosting, all three point to the same directory.
For external projects, state_root defaults to target_root/.cw9.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    engine_root: Path
    target_root: Path
    state_root: Path

    # Derived paths under engine_root (read-only, CW9's own files)
    template_dir: Path
    tools_dir: Path
    python_dir: Path

    # Derived paths under state_root (project-specific state)
    schema_dir: Path
    spec_dir: Path
    artifact_dir: Path
    session_dir: Path

    # Derived path under target_root (generated output for the project)
    test_output_dir: Path

    @classmethod
    def self_hosting(cls, engine_root: Path) -> ProjectContext:
        """CW9 working on itself — all three roots are the same directory."""
        engine_root = Path(engine_root).resolve()
        return cls(
            engine_root=engine_root,
            target_root=engine_root,
            state_root=engine_root,
            # Engine paths
            template_dir=engine_root / "templates" / "pluscal",
            tools_dir=engine_root / "tools",
            python_dir=engine_root / "python",
            # State paths (legacy layout for self-hosting)
            schema_dir=engine_root / "schema",
            spec_dir=engine_root / "templates" / "pluscal" / "instances",
            artifact_dir=engine_root / "python" / "tests" / "generated",
            session_dir=engine_root / "sessions",
            # Target paths
            test_output_dir=engine_root / "python" / "tests" / "generated",
        )

    @classmethod
    def from_target(cls, target_root: Path, engine_root: Path | None = None) -> ProjectContext:
        """Load context for a target directory.

        If target_root has a .cw9/ directory, uses external layout.
        If target_root IS the engine_root, uses self-hosting layout.
        engine_root defaults to auto-detection from this file's location.
        """
        target_root = Path(target_root).resolve()
        if engine_root is None:
            # python/registry/context.py -> python/registry -> python -> engine_root
            engine_root = Path(__file__).resolve().parent.parent.parent
        else:
            engine_root = Path(engine_root).resolve()

        if target_root == engine_root:
            return cls.self_hosting(engine_root)
        return cls.external(engine_root, target_root)

    @classmethod
    def external(cls, engine_root: Path, target_root: Path) -> ProjectContext:
        """CW9 working on an external project."""
        engine_root = Path(engine_root).resolve()
        target_root = Path(target_root).resolve()
        state_root = target_root / ".cw9"
        return cls(
            engine_root=engine_root,
            target_root=target_root,
            state_root=state_root,
            # Engine paths
            template_dir=engine_root / "templates" / "pluscal",
            tools_dir=engine_root / "tools",
            python_dir=engine_root / "python",
            # State paths (.cw9 layout)
            schema_dir=state_root / "schema",
            spec_dir=state_root / "specs",
            artifact_dir=state_root / "bridge",
            session_dir=state_root / "sessions",
            # Target paths
            test_output_dir=target_root / "tests" / "generated",
        )
