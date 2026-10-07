"""AST pin: ``doctor mission-state --fix`` is the sole caller of ``repair_repo`` (#5811).

ADR 2026-10-07-1: ``spec-kitty upgrade`` never runs the mission-state repair,
so the explicit doctor command is the only consent path. The scan reads every
``src/`` module for a call to ``repair_repo`` (as a name or as an attribute such
as ``mission_state.repair_repo``) and asserts the set of calling modules. The
defining module is excluded; the allowlist starts, and stays, at one entry.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli

pytestmark = pytest.mark.fast

_SRC_ROOT = Path(specify_cli.__file__).resolve().parent.parent
_DEFINING_MODULE = "specify_cli/migration/mission_state.py"
_DOCTOR = "specify_cli/cli/commands/_mission_state_doctor.py"
_SOLE_CALLERS = frozenset({_DOCTOR})


def _calls_repair_repo(source: str) -> bool:
    """True when *source* contains a call to ``repair_repo`` by name or attribute."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "repair_repo") or (isinstance(func, ast.Attribute) and func.attr == "repair_repo"):
            return True
    return False


def _calling_modules(root: Path) -> set[str]:
    callers: set[str] = set()
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if relative == _DEFINING_MODULE:
            continue
        if _calls_repair_repo(path.read_text(encoding="utf-8")):
            callers.add(relative)
    return callers


def test_doctor_is_the_sole_repair_repo_caller() -> None:
    callers = _calling_modules(_SRC_ROOT)

    assert callers, "scanner found no repair_repo call at all (vacuous)"
    assert callers == _SOLE_CALLERS, f"repair_repo must be called only from the doctor; found {sorted(callers)}"


@pytest.mark.parametrize(
    "source",
    [
        "repair_repo(project_path)",
        "mission_state.repair_repo(project_path)",
        "def step():\n    from specify_cli.migration.mission_state import repair_repo\n    return repair_repo(root)",
    ],
)
def test_scanner_flags_a_synthetic_extra_caller(source: str) -> None:
    assert _calls_repair_repo(source)


def test_scanner_ignores_a_mere_reference() -> None:
    assert not _calls_repair_repo("from specify_cli.migration.mission_state import repair_repo\nname = repair_repo")
