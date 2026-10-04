"""Seam pins for the ``mission_finalize`` phase-module decomposition (#5627).

``mission_finalize`` was split into sibling phase modules with the bodies moved
verbatim. These tests pin the three properties that keep the split
behaviour-neutral:

1. every name a phase module defines is re-exported by ``mission_finalize``
   (the historical import and patch surface);
2. no phase module imports ``mission_finalize`` at module scope (the routing
   import is lazy, so there is no import cycle);
3. a patch on ``mission_finalize.<name>`` still intercepts a call made from
   inside a phase module, and a phase module reaches a function another
   finalize module owns only through ``_mf``.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest
import typer

from kernel.git import GitCommandError
from specify_cli.cli.commands.agent import mission_finalize
from tests._support.finalize_source import FINALIZE_MODULE_PATHS

pytestmark = [pytest.mark.fast]

_PKG = "specify_cli.cli.commands.agent"
# One module list for every gate: the family helper minus the facade, so a new
# ``mission_finalize_x.py`` joins them all.
PHASE_MODULES = tuple(path.stem for path in FINALIZE_MODULE_PATHS if path.stem != "mission_finalize")


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


def _imports_mission_finalize(node: ast.stmt) -> bool:
    """True for ``import ..mission_finalize [as x]``, ``from . import mission_finalize``
    and ``from .mission_finalize import X`` (the leaf modules ``mission_finalize_*``
    are different modules and do not match)."""
    if isinstance(node, ast.Import):
        return any(alias.name.rsplit(".", 1)[-1] == "mission_finalize" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module.rsplit(".", 1)[-1] == "mission_finalize":
            return True
        return module in {_PKG, ""} and any(alias.name == "mission_finalize" for alias in node.names)
    return False


@pytest.mark.parametrize("module_name", PHASE_MODULES)
def test_phase_module_never_imports_mission_finalize_at_module_scope(module_name: str) -> None:
    module = importlib.import_module(f"{_PKG}.{module_name}")
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    for node in tree.body:
        assert not _imports_mission_finalize(node), f"{module_name} imports mission_finalize at module scope (line {node.lineno})"


def test_logger_name_is_pinned_to_mission_finalize() -> None:
    assert mission_finalize.logger.name == f"{_PKG}.mission_finalize"


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


# Names a leaf must reach through ``_mf.<name>`` so a patch on ``mission_finalize``
# intercepts the call. A name belongs here when a test patches it on
# ``mission_finalize`` (``patch``, ``patch.object``, ``monkeypatch.setattr``,
# including the dict-driven ``extra_patches`` forms), or when it was a patchable
# attribute of the pre-split module that a leaf already routes (the five seam
# functions plus ``get_main_repo_root``, ``load_meta_fail_closed`` and
# ``err_console``). Add a name in the same change that first patches it.
_ROUTED_NAMES = frozenset(
    {
        # patched by tests
        "_bootstrap_canonical_state_via_mission",
        "_compute_and_write_lanes",
        "_coord_candidate_dirt",
        "_emit_json",
        "_emit_local_canonical_events",
        "_emit_success_report",
        "_emit_tasks_started",
        "_execution_has_begun",
        "_finalize_candidates_dirty",
        "_mission_protection_policy",
        "_preflight_frozen_lane_membership",
        "_prepare_primary_pin_refresh_commit",
        "_preserve_or_capture_planning_commit_sha",
        "_report_parallelization_risk",
        "_resolve_finalize_commit_candidates",
        "_resolve_repo_root",
        "_run_bootstrap_loop",
        "_scaffold_issue_matrix_if_present",
        "_validate_requirement_mapping",
        "capture_branch_tip",
        "classify_recorded_pin",
        "console",
        "resolve_checkout_identity",
        "resolve_owned_or_adopt",
        "status_entries",
        # pre-split patch surface, routed by a leaf today
        "_read_wp_frontmatter",
        "_resolve_planning_branch_via_mission",
        "_validate_ownership_via_mission",
        "err_console",
        "get_main_repo_root",
        "load_meta_fail_closed",
    }
)


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _function_body_name_loads(tree: ast.AST) -> set[tuple[str, int]]:
    """Every bare ``Name`` load inside a function body (nested functions included).

    Module-scope definitions, decorators, defaults and annotations are outside a
    body, so ``TYPE_CHECKING`` imports and signatures never match."""
    loads: set[tuple[str, int]] = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for statement in fn.body:
                loads.update((n.id, n.lineno) for n in ast.walk(statement) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load))
    return loads


def _routing_violations(tree: ast.AST, own_path: Path) -> list[str]:
    """Rule 1: a routed name is never referenced bare (not only called: ``console.print``
    is an attribute on a ``Name``). Rule 2: a function another finalize module owns
    is never referenced bare (classes, constants and ``logger`` may cross)."""
    foreign = set().union(*(_top_level_functions(p) for p in FINALIZE_MODULE_PATHS if p != own_path))
    loads = _function_body_name_loads(tree)
    unrouted = sorted(load for load in loads if load[0] in _ROUTED_NAMES)
    cross_module = sorted(load for load in loads if load[0] in foreign)
    violations = []
    if unrouted:
        violations.append(f"routed name used bare: {unrouted}")
    if cross_module:
        violations.append(f"another module's function used bare: {cross_module}")
    return violations


def _leaf_path(module_name: str) -> Path:
    return next(path for path in FINALIZE_MODULE_PATHS if path.stem == module_name)


@pytest.mark.parametrize("module_name", PHASE_MODULES)
def test_phase_module_routes_patched_and_cross_module_names_through_mf(module_name: str) -> None:
    """A bare reference would silently stop honouring a patch on ``mission_finalize``
    (a name tests patch there) or skip the patch surface another module owns."""
    assert _ROUTED_NAMES, "no routed names declared"
    stale = sorted(name for name in _ROUTED_NAMES if not hasattr(mission_finalize, name))
    assert not stale, f"_ROUTED_NAMES lists names mission_finalize no longer exposes: {stale}"
    path = _leaf_path(module_name)
    assert _routing_violations(ast.parse(path.read_text(encoding="utf-8")), path) == []


def test_routing_gate_flags_an_unrouted_reference() -> None:
    """Planted control: de-route one call in an in-memory copy of the commit leaf."""
    path = _leaf_path("mission_finalize_commit")
    source = path.read_text(encoding="utf-8")
    assert "_mf._compute_and_write_lanes(" in source, "re-point this control: the commit leaf no longer calls _compute_and_write_lanes"
    mutated = source.replace("_mf._compute_and_write_lanes(", "_compute_and_write_lanes(")

    assert len(_routing_violations(ast.parse(mutated), path)) == 2
