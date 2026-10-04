"""Seam pins for the ``mission_finalize`` phase-module decomposition (#5627).

``mission_finalize`` was split into sibling phase modules with the bodies moved
verbatim. These tests pin the three properties that keep the split
behaviour-neutral:

1. every name a phase module defines is re-exported by ``mission_finalize``
   (the historical import and patch surface);
2. no phase module imports ``mission_finalize`` at module scope (the routing
   import is lazy, so there is no import cycle);
3. a patch on ``mission_finalize.<name>`` still intercepts a call made from
   inside a phase module.
"""

from __future__ import annotations

import ast
import importlib
import logging
from pathlib import Path

import pytest
import typer

from kernel.git import GitCommandError
from specify_cli.cli.commands.agent import mission_finalize

pytestmark = [pytest.mark.fast]

_PKG = "specify_cli.cli.commands.agent"
PHASE_MODULES = (
    "mission_finalize_seams",
    "mission_finalize_branch_contract",
    "mission_finalize_validation",
    "mission_finalize_bootstrap",
    "mission_finalize_planning_pin",
    "mission_finalize_lanes",
    "mission_finalize_commit",
)


def _top_level_definitions(module_name: str) -> set[str]:
    module = importlib.import_module(f"{_PKG}.{module_name}")
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


@pytest.mark.parametrize("module_name", PHASE_MODULES)
def test_mission_finalize_reexports_every_phase_definition(module_name: str) -> None:
    module = importlib.import_module(f"{_PKG}.{module_name}")
    names = _top_level_definitions(module_name)
    assert names, f"{module_name} defines nothing"
    missing = sorted(n for n in names if getattr(mission_finalize, n, None) is not getattr(module, n))
    assert not missing, f"mission_finalize does not re-export {module_name}: {missing}"


@pytest.mark.parametrize("module_name", PHASE_MODULES)
def test_phase_module_never_imports_mission_finalize_at_module_scope(module_name: str) -> None:
    module = importlib.import_module(f"{_PKG}.{module_name}")
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            imported = {f"{node.module}.{alias.name}" for alias in node.names} | {node.module}
            assert f"{_PKG}.mission_finalize" not in imported, f"{module_name} imports mission_finalize at module scope (line {node.lineno})"


def test_logger_name_is_pinned_to_mission_finalize() -> None:
    assert mission_finalize.logger.name == f"{_PKG}.mission_finalize"
    assert mission_finalize.logger is logging.getLogger(f"{_PKG}.mission_finalize")


def test_emit_json_patch_intercepts_a_phase_module_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    validation = importlib.import_module(f"{_PKG}.mission_finalize_validation")

    with pytest.raises(typer.Exit):
        validation._validate_dependency_graph({"WP01": ["WP02"], "WP02": ["WP01"]}, json_output=True)

    assert len(emitted) == 1
    assert "Circular dependencies detected" in str(emitted[0]["error"])


def test_status_entries_patch_intercepts_the_planning_pin_probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _fail(*_args: object, **_kwargs: object) -> object:
        raise GitCommandError(argv=("git", "status"), cwd=tmp_path, returncode=128, stderr="boom")

    monkeypatch.setattr(mission_finalize, "status_entries", _fail)
    planning_pin = importlib.import_module(f"{_PKG}.mission_finalize_planning_pin")

    entries, diagnostic = planning_pin._read_refresh_worktree_status(tmp_path)

    assert entries is None
    assert diagnostic is not None and "boom" in diagnostic


@pytest.mark.parametrize("module_name", ["mission_finalize_bootstrap", "mission_finalize_commit"])
def test_bootstrap_seam_calls_route_through_mission_finalize(module_name: str) -> None:
    """Review cycle 1: every ``_bootstrap_canonical_state_via_mission`` call in a
    phase module goes through ``_mf.``, so a patch on ``mission_finalize`` intercepts it."""
    module = importlib.import_module(f"{_PKG}.{module_name}")
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    bare = [c.lineno for c in calls if isinstance(c.func, ast.Name) and c.func.id == "_bootstrap_canonical_state_via_mission"]
    routed = [
        c.lineno
        for c in calls
        if isinstance(c.func, ast.Attribute)
        and c.func.attr == "_bootstrap_canonical_state_via_mission"
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id == "_mf"
    ]
    assert not bare, f"{module_name} calls the bootstrap seam unrouted at lines {bare}"
    assert routed, f"{module_name} no longer calls the bootstrap seam -- re-point this pin"


def test_bootstrap_seam_patch_intercepts_the_validate_only_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A patch on ``mission_finalize._bootstrap_canonical_state_via_mission`` is the
    one ``_emit_validate_only_report`` (now in the bootstrap phase module) calls."""
    seen: list[str] = []

    def _fake(_planning_dir: Path, mission_slug: str, **_kwargs: object) -> object:
        seen.append(mission_slug)
        raise RuntimeError("intercepted")

    monkeypatch.setattr(mission_finalize, "_bootstrap_canonical_state_via_mission", _fake)
    state = mission_finalize._BootstrapState(inmemory_frontmatter={})

    with pytest.raises(RuntimeError, match="intercepted"):
        mission_finalize._emit_validate_only_report(tmp_path, "001-mission", None, state, {}, {}, {}, "main", json_output=True)

    assert seen == ["001-mission"]


def test_mission_specs_alias_is_injected_on_mission_finalize() -> None:
    alias = "_invalid_" + "kitty_specs" + "_owned_files"
    assert getattr(mission_finalize, alias) is mission_finalize._invalid_mission_specs_owned_files


_SEAM_FUNCTIONS = frozenset(
    {
        "_emit_json",
        "_read_wp_frontmatter",
        "_resolve_planning_branch_via_mission",
        "_bootstrap_canonical_state_via_mission",
        "_validate_ownership_via_mission",
    }
)


@pytest.mark.parametrize("module_name", [m for m in PHASE_MODULES if m != "mission_finalize_seams"])
def test_phase_modules_never_call_a_seam_function_unrouted(module_name: str) -> None:
    """Before the split each seam was patchable on ``mission_finalize``; a bare
    call from a phase module would silently stop honouring that patch."""
    module = importlib.import_module(f"{_PKG}.{module_name}")
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    bare = sorted(
        (node.func.id, node.lineno) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SEAM_FUNCTIONS
    )
    assert not bare, f"{module_name} calls seam functions without routing through _mf: {bare}"
