"""Characterization golden for the internalized runtime, plus its layer ban.

The golden loads the JSON snapshots committed under
``tests/fixtures/runtime_parity/`` (captured from the upstream
``spec_kitty_runtime`` 0.4.x source) and replays the equivalent scenarios
through ``runtime.next._internal_runtime`` (``start_mission_run`` /
``next_step`` / ``provide_decision_answer``). The internalized output must
match byte-for-byte modulo timestamp / path normalization (handled inside the
capture script). A diff means runtime behaviour drifted from the captured
characterization.

The module also owns the rich/typer layer ban: presentation belongs in the CLI
layer, never in ``_internal_runtime``. The ``spec_kitty_runtime`` import ban is
owned by ``tests/architectural/test_shared_package_boundary.py``.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "runtime_parity"

# Scan target of the rich/typer layer ban.
_RUNTIME_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "runtime" / "next" / "_internal_runtime"
# Planning-base count of ``.py`` files under ``_RUNTIME_PACKAGE`` (NFR-002 floor).
# A deliberate shrink of the package is a one-line edit here.
_RUNTIME_PACKAGE_FILE_FLOOR = 16
_FORBIDDEN_IMPORT_ROOTS = frozenset({"rich", "typer"})


def _imported_roots(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Top-level module segments an ``import`` / ``from ... import`` statement loads."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


def _rich_typer_import_offenders(root: Path) -> tuple[int, list[str]]:
    """Return ``(files_inspected, offenders)`` for rich/typer imports under ``root``.

    Walks the AST (not line prefixes), so ``import os, typer`` and lazy
    function-local imports are caught. Fails loudly on a missing or empty
    target: a ban that inspects nothing must never pass (SC-005).
    """
    assert root.is_dir(), f"rich/typer ban: missing target {root} (0 files inspected)"
    files = sorted(root.rglob("*.py"))
    assert files, f"rich/typer ban: empty target {root} (0 files inspected)"
    offenders: list[str] = []
    for py_file in files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            hits = [r for r in _imported_roots(node) if r in _FORBIDDEN_IMPORT_ROOTS]
            offenders.extend(f"{py_file}:{node.lineno}: {r}" for r in hits)
    return len(files), offenders


def _load_capture_module() -> ModuleType:
    """Import ``_capture_baselines.py`` from disk by file path.

    The fixtures directory is intentionally not a Python package, so we
    can't use a normal ``import`` statement. importlib's spec_from_file_location
    avoids the namespace-package vs. package ambiguity entirely.
    """
    spec = importlib.util.spec_from_file_location(
        "_capture_baselines",
        FIXTURE_DIR / "_capture_baselines.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SNAPSHOT_FILES = (
    "snapshot_start_mission_run.json",
    "snapshot_next_step_1.json",
    "snapshot_provide_decision_answer.json",
    "snapshot_next_step_2.json",
)


@pytest.fixture(scope="module")
def captured_snapshots() -> dict[str, dict]:
    """Run the internalized runtime against the reference fixture in-process."""
    capture_module = _load_capture_module()
    return capture_module.capture(target="internal", out_dir=None)


@pytest.fixture(scope="module")
def golden_baselines() -> dict[str, dict]:
    """Load the committed golden baselines from disk."""
    baselines: dict[str, dict] = {}
    for name in SNAPSHOT_FILES:
        path = FIXTURE_DIR / name
        baselines[name] = json.loads(path.read_text(encoding="utf-8"))
    return baselines


@pytest.mark.parametrize("snapshot_name", SNAPSHOT_FILES)
def test_internalized_runtime_matches_upstream_snapshot(
    snapshot_name: str,
    captured_snapshots: dict[str, dict],
    golden_baselines: dict[str, dict],
) -> None:
    """Each captured snapshot from the internalized runtime must equal the golden."""
    captured = captured_snapshots[snapshot_name]
    expected = golden_baselines[snapshot_name]

    # Byte-equal comparison via canonical JSON encoding (sort_keys, indent=2)
    captured_text = json.dumps(captured, sort_keys=True, indent=2)
    expected_text = json.dumps(expected, sort_keys=True, indent=2)

    assert captured_text == expected_text, f"Parity drift in {snapshot_name}:\n--- expected\n{expected_text}\n+++ captured\n{captured_text}"


def test_no_rich_or_typer_imports_in_internal_package() -> None:
    """Layer-rule gate: presentation belongs in the CLI layer, not the runtime.

    The file-count floor that keeps this gate non-vacuous is asserted once, in
    :func:`test_rich_typer_ban_inspects_live_runtime_package`.
    """
    _, offenders = _rich_typer_import_offenders(_RUNTIME_PACKAGE)
    assert offenders == [], "rich/typer imports must not appear inside _internal_runtime/:\n" + "\n".join(f"  {o}" for o in offenders)


def test_rich_typer_ban_inspects_live_runtime_package() -> None:
    """The ban's scan target is the live runtime package, not a vanished path."""
    files_inspected, _ = _rich_typer_import_offenders(_RUNTIME_PACKAGE)
    assert files_inspected >= _RUNTIME_PACKAGE_FILE_FLOOR, (
        f"rich/typer ban inspected {files_inspected} files under {_RUNTIME_PACKAGE}; expected >= {_RUNTIME_PACKAGE_FILE_FLOOR}"
    )


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_rich_typer_ban_fails_on_missing_or_empty_target(tmp_path: Path, kind: str) -> None:
    """A missing or empty scan target fails the ban instead of passing vacuously."""
    target = tmp_path / "pkg"
    if kind == "empty":
        target.mkdir()
    with pytest.raises(AssertionError, match="0 files inspected"):
        _rich_typer_import_offenders(target)


def test_rich_typer_ban_flags_planted_import(tmp_path: Path) -> None:
    """Planted rich/typer imports are named by the same helper the ban calls."""
    (tmp_path / "mod.py").write_text("import os, typer\n", encoding="utf-8")
    (tmp_path / "view.py").write_text("from rich.console import Console\n", encoding="utf-8")
    (tmp_path / "clean.py").write_text("import os\n", encoding="utf-8")
    files_inspected, offenders = _rich_typer_import_offenders(tmp_path)
    assert files_inspected == 3
    assert len(offenders) == 2, offenders
    assert any("mod.py:1: typer" in o for o in offenders), offenders
    assert any("view.py:1: rich" in o for o in offenders), offenders
