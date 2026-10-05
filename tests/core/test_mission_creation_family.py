"""Seam pins for the ``mission_creation`` module-family split (#5634).

``specify_cli.core.mission_creation`` was split into sibling leaf modules with
the bodies moved verbatim. These tests pin what keeps the split
behaviour-neutral:

1. every name a leaf defines is re-exported by the façade, by identity (public surface),
   and every name the façade exposed before the split still resolves on it;
2. no leaf imports the façade at module scope, and the pure decisions module
   never imports it at all (no import cycle);
3. every family logger is the façade's logger name, and every leaf imports on
   its own (no reliance on the façade being imported first);
4. the lazy-only modules are never imported at module scope;
5. a patch on ``mission_creation.<name>`` intercepts a call made inside a leaf;
6. routing set-equality (the routing rule; patches keep intercepting): a leaf reaches a name tests patch on
   the façade, or a function another family module owns, only as
   ``_mc.<name>``, and routes nothing else. Import aliases are resolved, and
   ``<module alias>.<name>`` and ``sys.modules[...]`` reads are flagged;
7. the seam cleanups (the mint gate, the protection probe, the rollback journal);
8. the seam structural checks, each with a planted control.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from collections.abc import Iterable

from pathlib import Path
from types import SimpleNamespace

import pytest

from kernel.clock import parse_iso
from mission_runtime import MissionTopology
from specify_cli.core import mission_creation
from specify_cli.core.paths import CommitToTargetMetaError
from tests._support.mission_creation_source import DECISIONS, LEAVES, MISSION_CREATION_MODULE_PATHS
from tests._support.patch_census import CensusReport, scan_static

pytestmark = [pytest.mark.fast]

_PKG = "specify_cli.core"
_FACADE_MODULE = f"{_PKG}.mission_creation"
_LAZY_IMPORT = "from specify_cli.core import mission_creation as _mc"
_ROUTING_ALIAS = "_mc"
_TESTS_ROOT = Path(__file__).resolve().parents[1]
LEAF_NAMES = tuple(path.stem for path in LEAVES)

# Every name ``dir(specify_cli.core.mission_creation)`` returned (dunders
# excluded) on 61dd4c56c, before the split: the historical
# import and patch surface (the public surface). Captured once.
# A removal (for example when a name is de-routed) updates this
# tuple in the same commit with a reason. Removed: ``_target_is_protected``
# (an unused one-shot wrapper over ``_ProtectionProbe``; no caller after the split).
_FROZEN_FACADE_ATTRIBUTES = (
    "Any", "CasReset", "CommitFailureKind", "CommitTarget", "Delete", "GitCommandError", "GitPath",
    "GuardCapability", "KEBAB_CASE_PATTERN", "KITTY_SPECS_DIR", "Mint", "MissionAlreadyExistsError",
    "MissionArtifactKind", "MissionBranchExistsError", "MissionCreationError", "MissionCreationResult",
    "MissionMetaReadError", "MissionTopology", "NoMint", "NoReturn", "Noop", "OwnedCreateMission",
    "OwnedCreateRoot", "Path", "ProtectedBranchRefused", "ProtectedMintDecision", "ProtectedMintFacts",
    "ProtectedTargetPolicy", "RefRestoreError", "Refuse", "SafeCommitDestinationNotFound",
    "SafeCommitHeadMismatch", "SafeCommitStagedTreeUnchanged", "TASKS_README_TEMPLATE", "ULID",
    "WriteLocation", "_BOOTSTRAP_META_COMMIT_SKIPS", "_COORDINATION_BRANCH_GLOB", "_CommitOutcome",
    "_CoordCreateRollbackContext", "_CoordCreateSeed", "_CreateRoots", "_Governance",
    "_META_KEY_CREATED_AT", "_META_KEY_MISSION_TYPE", "_MetaBuild", "_Purpose", "_Scaffold",
    "_build_create_meta", "_build_create_result", "_check_out_minted_branch",
    "_commit_coord_create_events", "_commit_create_scaffold", "_commit_failure_kind",
    "_commit_feature_file", "_consume_pending_origin_if_present", "_create_mission_core_impl",
    "_dirty_outside_scaffold", "_emit_create_events", "_failure_is_disposable_create_refusal",
    "_find_live_duplicate_mission", "_gather_and_decide_protected_mint", "_list_coordination_branches",
    "_list_mission_scaffolds", "_local_branch_exists", "_mint_protected_branch_for_topology",
    "_mint_protected_single_branch_mission_branch", "_path_is_tracked_by_git",
    "_plan_orphan_scaffold_removal", "_prior_mission_is_abandoned", "_protected_mint_applies",
    "_raise_refusal", "_refuse_live_duplicate", "_refuse_protected_recreate",
    "_remove_orphan_mission_scaffolds", "_resolve_create_governance", "_resolve_create_roots",
    "_resolve_purpose", "_restore_git_state_after_failed_create", "_rev_parse_or_none",
    "_rollback_coordination_surface", "_scaffold_mission_dir", "_seed_coord_surface_for_create",
    "_target_has_commit", "_validate_create_inputs", "annotations",
    "build_mission_created_payload", "candidate_name_matches", "classify_scaffold_commit_failure",
    "contextlib", "coord_rollback_action", "coord_rollback_needs_current_tip", "create_mission_core",
    "created_file_sets", "dataclass", "decide_protected_mint", "default_mission_display_name",
    "default_mission_purpose_context", "field", "get_current_branch", "has_unborn_head",
    "is_abandoned", "is_coordination_routed", "is_git_repo", "is_same_mission_type",
    "is_worktree_context", "load_meta_fail_closed", "load_meta_or_empty", "locate_project_root",
    "logger", "logging", "meta_flag_patch", "mission_branch_name", "mission_dir_name", "now_utc_iso",
    "orphan_scaffold_candidates", "placement_seam", "plan_orphan_scaffold_removal", "preflight_commit",
    "protected_mint_applies", "re", "read_commit_to_target", "render_tasks_readme_content", "replace",
    "resolve_create_time_write_target", "resolve_mid8", "restore_branch_ref", "safe_commit", "shutil",
    "status_entries", "strip_numeric_prefix", "subprocess", "target_is_protected", "tracked_paths",
    "validate_purpose_summary",
)  # fmt: skip

# Modules that must never be imported at module scope anywhere in the family.
_LAZY_ONLY_MODULES = frozenset(
    {
        "specify_cli.core.adapters",
        "specify_cli.coordination.teardown",
        "specify_cli.missions._read_path_resolver",
        "specify_cli.status",
        "specify_cli.git.protection_policy",
    }
)
# ``resolve_primary_branch`` must stay lazy, while ``specify_cli.core.git_ops``
# itself is a legitimate module-scope import for other names.
_LAZY_ONLY_NAMES = frozenset({("specify_cli.core.git_ops", "resolve_primary_branch")})


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _leaf_path(module_name: str) -> Path:
    return next(path for path in LEAVES if path.stem == module_name)


def _top_level_definitions(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def _top_level_functions(path: Path) -> set[str]:
    return {node.name for node in _tree(path).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _function_nodes(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    return (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _is_type_checking_block(node: ast.stmt) -> bool:
    test = node.test if isinstance(node, ast.If) else None
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _module_scope_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Runtime imports outside every function body (``TYPE_CHECKING`` blocks excluded)."""
    found: list[ast.Import | ast.ImportFrom] = []

    def visit(statements: list[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                found.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or _is_type_checking_block(node):
                continue
            else:
                for field_name in ("body", "orelse", "finalbody", "handlers"):
                    children = getattr(node, field_name, None)
                    if isinstance(children, list):
                        visit([c for c in children if isinstance(c, ast.stmt)] + [s for h in children if isinstance(h, ast.ExceptHandler) for s in h.body])

    visit(tree.body)
    return found


# --------------------------------------------------------------------------- #
# 1. Re-export identity and the frozen façade surface
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("module_name", LEAF_NAMES)
def test_facade_reexports_every_leaf_definition_by_identity(module_name: str) -> None:
    module = importlib.import_module(f"{_PKG}.{module_name}")
    names = _top_level_definitions(_tree(_leaf_path(module_name)))
    assert names, f"{module_name} defines nothing"
    missing = sorted(n for n in names if getattr(mission_creation, n, None) is not getattr(module, n))
    assert not missing, f"mission_creation does not re-export {module_name}: {missing}"


def test_every_pre_split_facade_attribute_still_resolves() -> None:
    missing = sorted(name for name in _FROZEN_FACADE_ATTRIBUTES if not hasattr(mission_creation, name))
    assert not missing, f"mission_creation no longer exposes: {missing}"


# --------------------------------------------------------------------------- #
# 2. No module-scope façade import (no import cycle)
# --------------------------------------------------------------------------- #


def _imports_facade(node: ast.stmt) -> bool:
    """True for ``import specify_cli.core.mission_creation``, ``from specify_cli.core
    import mission_creation`` and ``from specify_cli.core.mission_creation import X``
    (the ``mission_creation_*`` siblings are different modules and do not match)."""
    if isinstance(node, ast.Import):
        return any(alias.name == _FACADE_MODULE for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == _FACADE_MODULE:
            return True
        return module == _PKG and any(alias.name == "mission_creation" for alias in node.names)
    return False


@pytest.mark.parametrize("module_name", LEAF_NAMES)
def test_leaf_never_imports_the_facade_at_module_scope(module_name: str) -> None:
    for node in _module_scope_imports(_tree(_leaf_path(module_name))):
        assert not _imports_facade(node), f"{module_name} imports mission_creation at module scope (line {node.lineno})"


def test_decisions_module_never_imports_the_facade() -> None:
    offenders = [node.lineno for node in ast.walk(_tree(DECISIONS)) if isinstance(node, (ast.Import, ast.ImportFrom)) and _imports_facade(node)]
    assert offenders == [], f"mission_creation_decisions imports the façade at line(s) {offenders}"


# --------------------------------------------------------------------------- #
# 3. Logger pin
# --------------------------------------------------------------------------- #


def _get_logger_names(path: Path) -> list[object]:
    """Arguments of every ``logging.getLogger(...)`` / ``getLogger(...)`` call in *path*."""
    names: list[object] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
        if callee == "getLogger":
            names.append(node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else ast.unparse(node))
    return names


@pytest.mark.parametrize("path", MISSION_CREATION_MODULE_PATHS, ids=lambda path: path.stem)
def test_every_family_logger_is_the_facade_logger(path: Path) -> None:
    """Covers a leaf that logs under another binding (``_log``, ``LOGGER``), not only ``logger``."""
    assert all(name == _FACADE_MODULE for name in _get_logger_names(path))


@pytest.mark.parametrize("module_name", (*LEAF_NAMES, DECISIONS.stem))
def test_leaf_imports_on_its_own(module_name: str) -> None:
    """A fresh interpreter imports the leaf without the façade loaded first."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {_PKG}.{module_name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------- #
# 4. Lazy-only imports stay function-local
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("path", MISSION_CREATION_MODULE_PATHS, ids=lambda p: p.stem)
def test_lazy_only_imports_never_appear_at_module_scope(path: Path) -> None:
    offenders: list[str] = []
    for node in _module_scope_imports(_tree(path)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in _LAZY_ONLY_MODULES or any((node.module, alias.name) in _LAZY_ONLY_NAMES for alias in node.names):
                offenders.append(f"{node.module} (line {node.lineno})")
        elif isinstance(node, ast.Import):
            offenders.extend(f"{alias.name} (line {node.lineno})" for alias in node.names if alias.name in _LAZY_ONLY_MODULES)
    assert offenders == [], f"{path.stem} imports a lazy-only module at module scope: {offenders}"


# --------------------------------------------------------------------------- #
# 5. Behavioural intercepts
# --------------------------------------------------------------------------- #


def _meta_build(tmp_path: Path, *, created_at: str | None) -> mission_creation._MetaBuild:
    return mission_creation._build_create_meta(
        feature_dir=tmp_path,
        mission_id="01J00000000000000000000000",
        mid8="01J00000",
        mission_slug_formatted="probe-01J00000",
        normalized_friendly_name="Probe",
        purpose=mission_creation._Purpose(tldr="Probe the clock input.", context="Probe the meta leaf clock input."),
        mission=None,
        planning_branch="main",
        pr_bound=False,
        retain_branches=False,
        retain_worktrees=False,
        commit_to_target=False,
        resolved_root=tmp_path,
        topology=MissionTopology.LANES,
        force_recreate_coordination_branch=False,
        created_at=created_at,
    )


def test_injected_created_at_reaches_the_meta_leaf(tmp_path: Path) -> None:
    """The clock is an injected input of the meta leaf, not a façade patch
    (the three former façade intercept pins went with the names they pinned:
    no test patches ``now_utc_iso``, ``get_current_branch`` or ``_commit_feature_file``
    any more, so the leaves read them directly)."""
    assert _meta_build(tmp_path, created_at="2026-01-02T03:04:05+00:00").meta["created_at"] == "2026-01-02T03:04:05+00:00"


def test_meta_leaf_reads_the_clock_without_an_injected_stamp(tmp_path: Path) -> None:
    stamp = _meta_build(tmp_path, created_at=None).meta["created_at"]
    assert parse_iso(stamp).tzinfo is not None, stamp


# --------------------------------------------------------------------------- #
# 6. Routing set-equality (hardening (a)-(e))
# --------------------------------------------------------------------------- #


#: ``census`` scans the whole ``tests/`` tree (about 11 s), so every test that
#: depends on it (directly or through ``patched_names``) leaves the fast tier.
_NEEDS_TEST_TREE_CENSUS = pytest.mark.integration


@pytest.fixture(scope="module")
def census() -> CensusReport:
    return scan_static(_TESTS_ROOT, family_prefix=_FACADE_MODULE)


@pytest.fixture(scope="module")
def patched_names(census: CensusReport) -> frozenset[str]:
    # ``subprocess`` is patched as ``mission_creation.subprocess.run``, which
    # patches the process-global module: out of routing scope by design.
    return frozenset(s.name for s in census.sites if s.module == _FACADE_MODULE and not s.name.startswith("<")) - {"subprocess"}


def _foreign_functions(own_path: Path) -> set[str]:
    """Functions another family module owns (the decisions module is pure, never patched, and imported directly)."""
    return set().union(*(_top_level_functions(p) for p in MISSION_CREATION_MODULE_PATHS if p not in (own_path, DECISIONS)))


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    """``{local name: imported name}`` for every ``from ... import x as y`` in a module."""
    return {alias.asname or alias.name: alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}


def _import_bound_names(tree: ast.AST) -> set[str]:
    """Every local name an import binds (``import a.b as m`` binds ``m``; ``import a.b`` binds ``a``),
    plus every name later rebound to one of them (see :func:`_rebound_aliases`)."""
    bound = set(_import_aliases(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return bound | _rebound_aliases(tree, bound)


def _attribute_root(node: ast.Attribute) -> ast.Name | None:
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        value = value.value
    return value if isinstance(value, ast.Name) else None


def _assignment_pairs(tree: ast.AST) -> Iterable[tuple[ast.expr, ast.expr]]:
    """``(target, value)`` for every plain, annotated and walrus assignment, at any scope."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            yield from ((target, node.value) for target in node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
            yield node.target, node.value


def _rebound_aliases(tree: ast.AST, bound: set[str]) -> set[str]:
    """Names rebound to an import-bound name, at module or function scope, transitively:
    ``from specify_cli.core import git_ops; _m = git_ops; _m.is_git_repo(...)`` makes ``_m``
    an alias whose attribute loads are judged like ``git_ops.<attr>`` (a two-step
    rebind must not reach a routed name past ``_mc`` unseen)."""
    known = set(bound)
    while True:
        new = {
            target.id
            for target, value in _assignment_pairs(tree)
            if isinstance(target, ast.Name)
            and target.id not in known
            and (
                (isinstance(value, ast.Name) and value.id in known)
                or (isinstance(value, ast.Attribute) and (root := _attribute_root(value)) is not None and root.id in known)
            )
        }
        if not new:
            return known - bound
        known |= new


def _qualified_loads(tree: ast.AST) -> list[ast.Attribute]:
    """``<import-bound name>[.<...>].<attr>`` loads whose root is not the routing alias."""
    bound = _import_bound_names(tree) - {_ROUTING_ALIAS}
    loads: list[ast.Attribute] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            root = _attribute_root(node)
            if root is not None and root.id in bound:
                loads.append(node)
    return loads


def _names_read(tree: ast.AST) -> set[str]:
    """Names a module reads, by their imported name: bare loads with import aliases resolved,
    ``_mc.<attr>`` loads, and ``<module alias>.<attr>`` loads."""
    aliases = _import_aliases(tree)
    names = {aliases.get(n.id, n.id) for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == _ROUTING_ALIAS}
    names |= {n.attr for n in _qualified_loads(tree)}
    return names


def _leaf_trees(replace: tuple[Path, ast.Module] | None = None) -> list[ast.Module]:
    return [replace[1] if replace is not None and path == replace[0] else _tree(path) for path in LEAVES]


def _routed_set(patched: frozenset[str], trees: Iterable[ast.Module] | None = None) -> frozenset[str]:
    read_by_leaves = set().union(*(_names_read(tree) for tree in (trees if trees is not None else _leaf_trees())))
    return frozenset(patched & read_by_leaves)


def _is_sys_modules(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "modules" and isinstance(node.value, ast.Name) and node.value.id == "sys"


def _facade_reference_violations(tree: ast.Module) -> list[str]:
    """Hardening (c): the façade is reached only as the function-local ``_mc`` import."""
    violations: list[str] = []
    in_function = {id(n) for fn in _function_nodes(tree) for n in ast.walk(fn) if n is not fn}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and _imports_facade(node):
            exact = isinstance(node, ast.ImportFrom) and ast.unparse(node) == _LAZY_IMPORT
            if not exact:
                violations.append(f"façade imported as {ast.unparse(node)!r} (line {node.lineno})")
            elif id(node) not in in_function:
                violations.append(f"routing import at module scope (line {node.lineno})")
        elif _is_sys_modules(node):
            # ``sys.modules[...]`` (or ``.get``) reaches the façade, or any module, past the routing rule.
            violations.append(f"sys.modules access (line {node.lineno})")
        elif isinstance(node, ast.Call):
            func = ast.unparse(node.func)
            if func in {"importlib.import_module", "import_module", "__import__"}:
                violations.append(f"dynamic import {ast.unparse(node)!r} (line {node.lineno})")
            elif func == "getattr" and node.args and ast.unparse(node.args[0]) in {_ROUTING_ALIAS, "mission_creation", _FACADE_MODULE}:
                violations.append(f"getattr on the façade {ast.unparse(node)!r} (line {node.lineno})")
    return violations


def _is_family_module(module: str | None) -> bool:
    return module is not None and module.startswith(f"{_FACADE_MODULE}_") and module != f"{_PKG}.mission_creation_decisions"


def _import_violations(tree: ast.Module, foreign: set[str], routed: frozenset[str], patched: frozenset[str]) -> list[str]:
    """Rule A on imports (a routed or patched name, any alias) and Rule B on imports (another
    family module's function, any alias), both resolved by the imported name."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        hits = sorted(alias.name for alias in node.names if alias.name in routed or alias.name in patched)
        if hits:
            violations.append(f"Rule A: routed name imported {hits} (line {node.lineno})")
        if _is_family_module(node.module):
            owned = sorted(alias.name for alias in node.names if alias.name in foreign)
            if owned:
                violations.append(f"Rule B: another module's function imported {owned} (line {node.lineno})")
    return violations


def _routing_violations(tree: ast.Module, own_path: Path, routed: frozenset[str], patched: frozenset[str] = frozenset()) -> list[str]:
    foreign = _foreign_functions(own_path)
    decision_imports = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == f"{_PKG}.mission_creation_decisions"
        for alias in node.names
    }
    aliases = _import_aliases(tree)
    # (a) a routed (or patched) name, or another module's function, imported under any alias
    violations = _import_violations(tree, foreign, routed, patched)
    # Rules A and B over the WHOLE module (b): bodies, module scope, defaults, class bodies, literals;
    # a bare load is judged by the name it was imported as
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            original = aliases.get(node.id, node.id)
            if original in routed:
                violations.append(f"Rule A: routed name used bare: {node.id} (line {node.lineno})")
            elif original in foreign and node.id not in decision_imports:
                violations.append(f"Rule B: another module's function used bare: {node.id} (line {node.lineno})")
    # Rule D: ``<module alias>.<name>`` reaching a routed/patched name or a foreign function past ``_mc``
    for node in _qualified_loads(tree):
        if node.attr in routed or node.attr in patched or node.attr in foreign:
            violations.append(f"Rule D: {ast.unparse(node)} bypasses _mc (line {node.lineno})")
    # Rule C (stale / over-routing)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == _ROUTING_ALIAS):
            continue
        if node.attr not in routed and node.attr not in foreign:
            violations.append(f"Rule C: over-routed _mc.{node.attr} (line {node.lineno})")
    violations.extend(_facade_reference_violations(tree))
    return violations


@_NEEDS_TEST_TREE_CENSUS
def test_routed_set_is_the_expected_patch_surface(patched_names: frozenset[str]) -> None:
    """Documents the computed routing set; a change here means a test started (or
    stopped) patching a name a leaf reads, and the leaf routing must follow."""
    assert _routed_set(patched_names) == {"build_mission_created_payload"}


@pytest.mark.parametrize("module_name", LEAF_NAMES)
@_NEEDS_TEST_TREE_CENSUS
def test_leaf_routes_exactly_the_patched_and_cross_module_names(module_name: str, patched_names: frozenset[str]) -> None:
    """A bare reference silently stops honouring a patch on ``mission_creation``; an
    ``_mc.`` reference to a name nobody patches hides drift."""
    path = _leaf_path(module_name)
    assert _routing_violations(_tree(path), path, _routed_set(patched_names), patched_names) == []


@_NEEDS_TEST_TREE_CENSUS
def test_no_family_targeting_patch_site_is_unresolved(census: CensusReport) -> None:
    """Hardening (d): a patch the census cannot resolve could target a leaf name unseen."""
    assert census.family_targeting_unresolved() == ()


def _mutated_violations(module_name: str, old: str, new: str, patched: frozenset[str]) -> list[str]:
    path = _leaf_path(module_name)
    source = path.read_text(encoding="utf-8")
    assert old in source, f"re-point this control: {module_name} no longer contains {old!r}"
    tree = ast.parse(source.replace(old, new, 1))
    # The routed set is computed over the family WITH the planted change.
    return _routing_violations(tree, path, _routed_set(patched, _leaf_trees((path, tree))), patched)


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_derouted_reference(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations(_EVENTS, _ROUTED_CALL, _ROUTED_CALL.replace("_mc.", ""), patched_names)
    assert len(violations) == 1 and violations[0].startswith("Rule A"), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_newly_patched_name_read_bare(patched_names: frozenset[str]) -> None:
    path = _leaf_path("mission_creation_roots")
    violations = _routing_violations(_tree(path), path, _routed_set(patched_names | {"has_unborn_head"}))
    assert any("has_unborn_head" in v for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_an_aliased_import_of_a_routed_name(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations(
        "mission_creation_roots",
        _ROOTS_IMPORT,
        _ROOTS_IMPORT + "from specify_cli.core.mission_payload import build_mission_created_payload as _b\n",
        patched_names,
    )
    assert any(v.startswith("Rule A: routed name imported ['build_mission_created_payload']") for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_module_scope_reference(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations(
        "mission_creation_roots",
        "@dataclass(frozen=True, slots=True)\nclass _CreateRoots:",
        "_PROBE = {'probe': build_mission_created_payload}\n\n\n@dataclass(frozen=True, slots=True)\nclass _CreateRoots:",
        patched_names,
    )
    assert any("build_mission_created_payload" in v and v.startswith("Rule A") for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_another_facade_alias(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations(
        "mission_creation_events", f"    {_LAZY_IMPORT}\n", "    from specify_cli.core import mission_creation as _facade\n", patched_names
    )
    assert any("façade imported as" in v for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_over_routing(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations("mission_creation_roots", "has_unborn_head(write_root)", "_mc.has_unborn_head(write_root)", patched_names)
    assert any(v.startswith("Rule C") for v in violations), violations


# --------------------------------------------------------------------------- #
# 7. Seam cleanups
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("topology", [t for t in MissionTopology if t is not MissionTopology.SINGLE_BRANCH], ids=lambda t: t.value)
def test_mint_gate_never_reads_the_override_off_single_branch(topology: MissionTopology, tmp_path: Path) -> None:
    """F2: the topology guard comes first, so a malformed ``commit_to_target`` is never read off single_branch."""
    minted = mission_creation._mint_protected_branch_for_topology(
        tmp_path, "gate-01TESTMI", topology=topology, mission_id="01TESTMISSIONIDXXXXXXXXXX", planning_branch="main", meta={"commit_to_target": "yes"}
    )
    assert minted is None


def test_mint_gate_refuses_a_malformed_override_on_single_branch(tmp_path: Path) -> None:
    """F2: on single_branch the override is read (and refused) before any protection probe."""
    with pytest.raises(CommitToTargetMetaError):
        mission_creation._mint_protected_branch_for_topology(
            tmp_path,
            "gate-01TESTMI",
            topology=MissionTopology.SINGLE_BRANCH,
            mission_id="01TESTMISSIONIDXXXXXXXXXX",
            planning_branch="main",
            meta={"commit_to_target": "yes"},
        )


class _CountingResolvers:
    """Fakes for the two protection resolvers ``_ProtectionProbe`` imports lazily."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    def resolve_policy(self, write_root: Path) -> SimpleNamespace:
        self.calls.append("policy")
        if self.error is not None:
            raise self.error
        return SimpleNamespace(is_protected_target=lambda target, primary_branch: target == primary_branch)

    def resolve_primary(self, write_root: Path, *, bias: bool) -> str:
        assert bias is False
        self.calls.append("primary")
        return "main"

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.core import git_ops
        from specify_cli.git.protection_policy import ProtectionPolicy

        monkeypatch.setattr(ProtectionPolicy, "resolve", staticmethod(self.resolve_policy))
        monkeypatch.setattr(git_ops, "resolve_primary_branch", self.resolve_primary)


def test_protection_probe_resolves_lazily_and_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Making the probe resolves nothing; two answers cost one resolution."""
    fakes = _CountingResolvers()
    fakes.install(monkeypatch)
    probe = mission_creation._ProtectionProbe(tmp_path)
    assert fakes.calls == []
    assert probe.is_protected("main") is True
    assert probe.is_protected("topic") is False
    assert fakes.calls == ["policy", "primary"]


def test_protection_probe_does_not_cache_a_failed_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A resolution that raises raises on every call (nothing is cached)."""
    fakes = _CountingResolvers(error=ValueError("malformed protection block"))
    fakes.install(monkeypatch)
    probe = mission_creation._ProtectionProbe(tmp_path)
    for _ in range(2):
        with pytest.raises(ValueError, match="malformed protection block"):
            probe.is_protected("main")
    assert fakes.calls == ["policy", "policy"]


def test_rollback_journal_records_the_first_coordination_surface(tmp_path: Path) -> None:
    """The journal starts empty and keeps the first record, as the list holder's ``[0]`` did."""
    journal = mission_creation.CreateRollbackJournal()
    assert journal.coord is None
    first, second = (
        mission_creation._CoordCreateRollbackContext(
            repo_root=tmp_path, mission_slug_formatted=f"m-{n}", mid8="01TESTMI", coordination_branch=f"kitty/mission-m-{n}", coordination_branch_created=True
        )
        for n in (1, 2)
    )
    journal.record_coord(first)
    journal.record_coord(second)
    assert journal.coord is first


# --------------------------------------------------------------------------- #
# 8. Structural checks, each with a planted control
# --------------------------------------------------------------------------- #

_COORD_PREDICATE = "is_coordination_routed"
_COORD_MEMBERS = frozenset({"COORD", "LANES_WITH_COORD"})
_META_BUILDER = "_build_create_meta"
_MINT_FUNCTIONS = frozenset({"_mint_protected_branch_for_topology", "_mint_protected_single_branch_mission_branch"})
_ORCHESTRATOR = "_create_mission_core_impl"


def _family_trees(mutate: tuple[str, str, str] | None = None) -> dict[str, ast.Module]:
    """``{module stem: AST}`` for the family; *mutate* = ``(stem, old, new)`` plants a change in memory."""
    trees: dict[str, ast.Module] = {}
    for path in MISSION_CREATION_MODULE_PATHS:
        source = path.read_text(encoding="utf-8")
        if mutate is not None and mutate[0] == path.stem:
            assert mutate[1] in source, f"re-point this control: {path.stem} no longer contains {mutate[1]!r}"
            source = source.replace(mutate[1], mutate[2], 1)
        trees[path.stem] = ast.parse(source)
    return trees


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _called_names(node: ast.AST) -> list[str]:
    """Callee names in source order, ``_mc.<name>`` and bare ``<name>`` alike."""
    calls = sorted((n for n in ast.walk(node) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
    names: list[str] = []
    for call in calls:
        if isinstance(call.func, ast.Name):
            names.append(call.func.id)
        elif isinstance(call.func, ast.Attribute):
            names.append(call.func.attr)
    return names


def _coord_predicate_violations(trees: dict[str, ast.Module]) -> list[str]:
    homes = [stem for stem, tree in trees.items() for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == _COORD_PREDICATE]
    violations = [] if homes == ["mission_creation_decisions"] else [f"{_COORD_PREDICATE} defined in {homes}"]
    for stem, tree in trees.items():
        for node in ast.walk(tree):
            # One comparison naming both members (``topology in (COORD, LANES_WITH_COORD)``),
            # or an ``or``/``and`` of comparisons that names them together between them.
            if isinstance(node, ast.BoolOp) and any(_names_both_members(c) for c in ast.walk(node) if isinstance(c, ast.Compare)):
                continue  # the inner comparison is reported itself
            if isinstance(node, (ast.Compare, ast.BoolOp)) and _names_both_members(node):
                violations.append(f"{stem}: inline coordination-routed test {ast.unparse(node)!r} (line {node.lineno})")
    return violations


def _names_both_members(node: ast.AST) -> bool:
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)} >= _COORD_MEMBERS


def _meta_builder_violations(trees: dict[str, ast.Module]) -> list[str]:
    builder = _function(trees["mission_creation_meta"], _META_BUILDER)
    return [f"{_META_BUILDER} calls {name}" for name in _called_names(builder) if name in _MINT_FUNCTIONS]


def _orchestrator_order_violations(trees: dict[str, ast.Module]) -> list[str]:
    """The mint runs from the orchestrator after the meta build and before the write; the probe resolves nothing there."""
    calls = _called_names(_function(trees["mission_creation"], _ORCHESTRATOR))
    expected = ["_ProtectionProbe", "_scaffold_mission_dir", _META_BUILDER, "_mint_protected_branch_for_topology", "_write_create_meta"]
    order = [name for name in calls if name in expected]
    violations = [] if order == expected else [f"orchestrator order {order} != {expected}"]
    if "is_protected" in calls:
        violations.append("orchestrator resolves protection itself (is_protected call)")
    return violations


def test_coordination_routed_predicate_is_defined_once_and_never_inlined() -> None:
    assert _coord_predicate_violations(_family_trees()) == []


def test_meta_builder_never_calls_the_mint() -> None:
    assert _meta_builder_violations(_family_trees()) == []


def test_orchestrator_calls_the_mint_between_meta_build_and_write() -> None:
    assert _orchestrator_order_violations(_family_trees()) == []


def test_planted_control_flags_an_inlined_coordination_routed_test() -> None:
    trees = _family_trees(
        (
            "mission_creation_scaffold",
            "    coordination_routed = is_coordination_routed(",
            "    _inline = topology in (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD) and owned is None\n"
            "    coordination_routed = is_coordination_routed(",
        )
    )
    violations = _coord_predicate_violations(trees)
    assert len(violations) == 1 and violations[0].startswith("mission_creation_scaffold: inline"), violations


def test_planted_control_flags_a_second_coordination_routed_definition() -> None:
    trees = _family_trees(
        (
            "mission_creation_events",
            "def _seed_coord_surface_for_create(",
            "def is_coordination_routed() -> bool:\n    return True\n\n\ndef _seed_coord_surface_for_create(",
        )
    )
    assert _coord_predicate_violations(trees) == ["is_coordination_routed defined in ['mission_creation_decisions', 'mission_creation_events']"]


def test_planted_control_flags_the_mint_called_from_the_meta_builder() -> None:
    trees = _family_trees(
        (
            "mission_creation_meta",
            '    meta.setdefault("flattened", False)\n',
            '    meta.setdefault("flattened", False)\n'
            "    _mc._mint_protected_branch_for_topology(\n"
            "        resolved_root, mission_slug_formatted, topology=topology, mission_id=mission_id, planning_branch=planning_branch, meta=meta\n"
            "    )\n",
        )
    )
    assert _meta_builder_violations(trees) == ["_build_create_meta calls _mint_protected_branch_for_topology"]


def test_planted_control_flags_the_write_before_the_mint() -> None:
    trees = _family_trees(
        (
            "mission_creation",
            "    minted_mission_branch = _mint_protected_branch_for_topology(",
            "    _write_create_meta(scaffold.feature_dir, meta_build.meta, mission)\n    minted_mission_branch = _mint_protected_branch_for_topology(",
        )
    )
    violations = _orchestrator_order_violations(trees)
    assert len(violations) == 1 and violations[0].startswith("orchestrator order"), violations


def test_planted_control_flags_an_early_protection_resolution() -> None:
    trees = _family_trees(
        (
            "mission_creation",
            "    protection = _ProtectionProbe(write_root)\n",
            "    protection = _ProtectionProbe(write_root)\n    protection.is_protected(planning_branch)\n",
        )
    )
    assert _orchestrator_order_violations(trees) == ["orchestrator resolves protection itself (is_protected call)"]


def test_planted_control_flags_an_inlined_or_of_both_members() -> None:
    trees = _family_trees(
        (
            "mission_creation_scaffold",
            "    coordination_routed = is_coordination_routed(",
            "    _inline = topology is MissionTopology.COORD or topology is MissionTopology.LANES_WITH_COORD\n    coordination_routed = is_coordination_routed(",
        )
    )
    violations = _coord_predicate_violations(trees)
    assert len(violations) == 1 and " or " in violations[0], violations


# Planted controls for the hardened routing rules.

_ROOTS = "mission_creation_roots"
_ROOTS_IMPORT = "from specify_cli.core.git_ops import get_current_branch, has_unborn_head, is_git_repo\n"
_ROOTS_IMPORT_WITHOUT_BRANCH = "from specify_cli.core.git_ops import has_unborn_head, is_git_repo\n"
_EVENTS = "mission_creation_events"
_EVENTS_IMPORT = "from specify_cli.core.owned_mission import OwnedCreateRoot\n"
# The one name a leaf still routes: tests patch it on the façade (branch-coverage row 4).
_ROUTED_CALL = "        expected_created_payload = _mc.build_mission_created_payload(\n"


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_module_alias_attribute_of_a_routed_name(patched_names: frozenset[str]) -> None:
    """``import specify_cli.core.git_ops as _g; _g.get_current_branch()`` bypasses ``_mc``.

    No test patches ``get_current_branch`` any more, so the control adds it to
    the patched set (as if a test started patching it) and drops its direct import."""
    patched = patched_names | {"get_current_branch"}
    path = _leaf_path(_ROOTS)
    source = path.read_text(encoding="utf-8").replace(_ROOTS_IMPORT, _ROOTS_IMPORT_WITHOUT_BRANCH + "import specify_cli.core.git_ops as _g\n", 1)
    source = source.replace("get_current_branch(write_root)", "_g.get_current_branch(write_root)", 1)
    tree = ast.parse(source)
    violations = _routing_violations(tree, path, _routed_set(patched, _leaf_trees((path, tree))), patched)
    assert violations == [f"Rule D: _g.get_current_branch bypasses _mc (line {_line_of(source, '_g.get_current_branch(')})"], violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_dotted_module_attribute_of_a_routed_name(patched_names: frozenset[str]) -> None:
    """``import specify_cli.core.git_ops; specify_cli.core.git_ops.get_current_branch()`` bypasses ``_mc``
    (with ``get_current_branch`` added to the patched set, as above)."""
    patched = patched_names | {"get_current_branch"}
    path = _leaf_path(_ROOTS)
    source = path.read_text(encoding="utf-8").replace(_ROOTS_IMPORT, _ROOTS_IMPORT_WITHOUT_BRANCH + "import specify_cli.core.git_ops\n", 1)
    tree = ast.parse(source.replace("get_current_branch(write_root)", "specify_cli.core.git_ops.get_current_branch(write_root)", 1))
    violations = _routing_violations(tree, path, _routed_set(patched, _leaf_trees((path, tree))), patched)
    assert any(v.startswith("Rule D: specify_cli.core.git_ops.get_current_branch") for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_an_aliased_import_of_a_foreign_function(patched_names: frozenset[str]) -> None:
    """Rule B through an alias: another family module's function imported as ``_cff``."""
    violations = _mutated_violations(
        _ROOTS,
        _ROOTS_IMPORT,
        _ROOTS_IMPORT + "from specify_cli.core.mission_creation_duplicates import _refuse_live_duplicate as _rld\n",
        patched_names,
    )
    assert any(v.startswith("Rule B: another module's function imported ['_refuse_live_duplicate']") for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_read_of_an_aliased_foreign_function(patched_names: frozenset[str]) -> None:
    """A bare read is judged by the imported name: ``_lms`` is ``_list_mission_scaffolds``."""
    violations = _mutated_violations(
        _ROOTS,
        "    if not is_git_repo(resolved_root):",
        "    from specify_cli.core.mission_creation_duplicates import _list_mission_scaffolds as _lms\n\n"
        "    _lms(resolved_root)\n    if not is_git_repo(resolved_root):",
        patched_names,
    )
    assert any(v.startswith("Rule B: another module's function used bare: _lms") for v in violations), violations


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("specify_cli.core.mission_creation_events", "_emit_create_events"),
        ("specify_cli.core.mission_creation_commit", "_commit_create_scaffold"),
        ("specify_cli.core.mission_creation", "create_mission_core"),
    ],
)
@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_an_aliased_import_of_a_patched_but_unread_name(patched_names: frozenset[str], module: str, name: str) -> None:
    """A name tests patch on the façade but no leaf reads today is still caught when a leaf imports it under an alias."""
    assert name in patched_names and name not in _routed_set(patched_names)
    violations = _mutated_violations(_ROOTS, _ROOTS_IMPORT, _ROOTS_IMPORT + f"from {module} import {name} as _aliased\n", patched_names)
    assert any(v.startswith(f"Rule A: routed name imported ['{name}']") for v in violations), violations


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_an_aliased_read_of_a_newly_patched_name(patched_names: frozenset[str]) -> None:
    """The routed set resolves aliases: a patched name read only as ``_hub`` still joins it."""
    patched = patched_names | {"has_unborn_head"}
    path = _leaf_path(_ROOTS)
    source = path.read_text(encoding="utf-8").replace(_ROOTS_IMPORT, "from specify_cli.core.git_ops import has_unborn_head as _hub, is_git_repo\n", 1)
    tree = ast.parse(source.replace("has_unborn_head(write_root)", "_hub(write_root)", 1))
    routed = _routed_set(patched, _leaf_trees((path, tree)))
    assert "has_unborn_head" in routed
    violations = _routing_violations(tree, path, routed, patched)
    assert any(v.startswith("Rule A: routed name imported ['has_unborn_head']") for v in violations), violations
    assert any(v.startswith("Rule A: routed name used bare: _hub") for v in violations), violations


@pytest.mark.parametrize(
    ("module_scope", "label"),
    [(False, "function-local"), (True, "module-level")],
)
@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_a_two_step_rebind_of_an_imported_module(patched_names: frozenset[str], module_scope: bool, label: str) -> None:
    """``from specify_cli.core import mission_payload; _m = mission_payload;
    _m.build_mission_created_payload(...)`` reaches a routed name past ``_mc`` through a rebound
    module alias, at either scope (pinned on the one name a leaf still routes)."""
    path = _leaf_path(_EVENTS)
    source = path.read_text(encoding="utf-8")
    assert _ROUTED_CALL in source, "re-point this control: the events leaf no longer calls _mc.build_mission_created_payload("
    rebound_call = "        expected_created_payload = _m.build_mission_created_payload(\n"
    if module_scope:
        source = source.replace(_EVENTS_IMPORT, _EVENTS_IMPORT + "from specify_cli.core import mission_payload\n\n_m = mission_payload\n", 1)
        source = source.replace(_ROUTED_CALL, rebound_call, 1)
    else:
        source = source.replace(_EVENTS_IMPORT, _EVENTS_IMPORT + "from specify_cli.core import mission_payload\n", 1)
        source = source.replace(_ROUTED_CALL, "        _m = mission_payload\n" + rebound_call, 1)
    tree = ast.parse(source)
    violations = _routing_violations(tree, path, _routed_set(patched_names, _leaf_trees((path, tree))), patched_names)
    expected_line = _line_of(source, "_m.build_mission_created_payload(")
    assert violations == [f"Rule D: _m.build_mission_created_payload bypasses _mc (line {expected_line})"], (label, violations)


def test_rebound_alias_detection_is_transitive_and_ignores_non_import_values() -> None:
    tree = ast.parse("import a.b as m\nx = m\ny = x.sub\nz = some_call()\nw = local\n")
    assert _rebound_aliases(tree, {"m"}) == {"x", "y"}


@_NEEDS_TEST_TREE_CENSUS
def test_planted_control_flags_sys_modules_access_to_the_facade(patched_names: frozenset[str]) -> None:
    violations = _mutated_violations(
        _ROOTS,
        "    if not is_git_repo(resolved_root):",
        '    import sys\n\n    if not sys.modules["specify_cli.core.mission_creation"].is_git_repo(resolved_root):',
        patched_names,
    )
    assert [v for v in violations if not v.startswith("Rule D")] == [f"sys.modules access (line {_line_of_planted(_ROOTS)})"], violations


def _line_of(source: str, needle: str) -> int:
    return source[: source.index(needle)].count("\n") + 1


def _line_of_planted(module_name: str) -> int:
    """Line of the ``sys.modules`` read in that control's planted source (the plant adds two lines above it)."""
    source = _leaf_path(module_name).read_text(encoding="utf-8")
    return _line_of(source, "    if not is_git_repo(resolved_root):") + 2
