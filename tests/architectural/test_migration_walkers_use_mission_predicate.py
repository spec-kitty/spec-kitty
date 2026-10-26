"""#6627: every ``kitty-specs/`` walker on the migration surface decides residue through ``is_mission_dir``.

``test_mission_resolver_walker_gate`` exempts ``upgrade/migrations/`` and
``migration/`` wholesale, so a migration walker could treat every directory as a
Mission (and fabricate an identity into residue) unseen. This gate closes that:

* every raw walker site in those trees is inventoried here with how it handles a
  residue directory. A new site fails until it is classified, so its author has
  to route it through :func:`specify_cli.context.mission_resolver.is_mission_dir`
  or record why a residue directory cannot be written by it;
* the shared seams the walkers hand a directory to (the shipped, byte-frozen
  migrations included) must call ``is_mission_dir`` (or its single-directory
  wrapper ``is_kitty_specs_residue``) themselves.

The rule (#6669): a ``kitty-specs/`` child with ``spec.md`` or ``meta.json`` on
disk is never residue, while one holding only ``status.json``, an event log or
``tasks/`` is residue wherever git tracks some Mission path. A walker is
therefore only safe when it requires ``meta.json`` itself, filters through the
predicate, or is a shipped migration whose registered class is a no-op because
a residue-aware successor walks instead (``_SUPERSEDED``).

Two successors (0.9.0, 0.9.1) take a third route: they SUBCLASS the shipped class, so the shipped walk
still runs and is made safe only by the per-folder predicates and the frontmatter collector they override.
Those entries are ``_SUBCLASS_GUARDED``; each override is pinned in ``_GUARDED_SEAMS`` to reach the residue
predicate (through the inherited ``ResidueSafeLaneSuccessorMixin._is_residue``, itself pinned), and
``test_subclass_guarded_classification_is_true`` fails if an override disappears.

Blind spots of the detector (``_find_raw_walker_calls``), so a walker can hide
from the inventory below:

* ``rglob`` is not an enumeration method it looks for;
* a walker is only seen on a *tainted* name (``kitty_specs``, ``wt_specs``,
  ``main_specs``, ``specs_dir`` and the rest of ``_SPECS_NAME_VOCABULARY``, or a
  name assigned from ``KITTY_SPECS_DIR`` / ``"kitty-specs"``), so any other
  variable name hides an ``iterdir`` or ``glob``;
* a module constant such as ``_KITTY_SPECS_DIRNAME`` is neither of those, so a
  walk built from it is invisible (``_UNDETECTED_WALKERS`` lists them by hand).

Name every new walker variable from the vocabulary so this gate sees it.
"""

from __future__ import annotations

import ast

import pytest

from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS
from tests.architectural.test_mission_resolver_walker_gate import _REPO_ROOT, _find_raw_walker_calls

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SCANNED_DIRS = ("src/specify_cli/upgrade/migrations", "src/specify_cli/migration", "src/specify_cli/upgrade")

_FILTERS = "filters with is_mission_dir"
_REQUIRES_META = "touches only a directory that already has meta.json, which is never residue (is_kitty_specs_residue)"
_READ_ONLY = "read-only"
_GUARDED_DOWNSTREAM = "the shared seam it writes through checks is_mission_dir"
_SUPERSEDED = "shipped migration registered as a no-op; its residue-aware successor walks instead"
_SUBCLASS_GUARDED = "shipped walker live via subclass; guarded by the successor's overridden predicate"

#: (module, enclosing function) -> how a residue directory is handled.
_WALKER_INVENTORY: dict[tuple[str, str], str] = {
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "apply"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "apply"): _REQUIRES_META,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "detect"): _READ_ONLY,
    # The four shipped walkers below were _REQUIRES_STATE / _GUARDED_IDENTITY_ONLY ("rewrites only pre-existing
    # mission state"). Under the #6669 rule a folder holding only status.json or tasks/ is residue, so that claim is
    # false for them. 2.0.6 / 3.1.1: the registered class is a recorded no-op and the successor walks through
    # partition_kitty_specs. 0.9.0 / 0.9.1: the successor SUBCLASSES the shipped class, so the shipped walk below
    # still runs; it is safe only because the successor overrides _is_legacy_format / _has_remaining_lane_dirs
    # (and, for 0.9.1, _normalize_all_frontmatter) to decide residue (see _SUBCLASS_SUCCESSORS).
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "_find_features_to_migrate"): _SUBCLASS_GUARDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "detect"): _SUBCLASS_GUARDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "_find_features_with_lanes"): _SUBCLASS_GUARDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "detect"): _SUBCLASS_GUARDED,
    ("src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py", "_iter_feature_dirs"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_3_1_1_normalize_status_json.py", "_iter_feature_dirs"): _SUPERSEDED,
    # The one walk every successor shares (WP02): it splits the children through is_kitty_specs_residue.
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "partition_kitty_specs"): _FILTERS,
    # Unchanged under the new rule: each reads meta.json first (a folder with meta.json is never residue).
    ("src/specify_cli/migration/backfill_identity.py", "backfill_mission_ids"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_identity.py", "backfill_repo"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_mission_type.py", "backfill_mission_type_repo"): _REQUIRES_META,
    # Was _REQUIRES_STATE; the shared walk now drops residue through _without_residue (WP05).
    ("src/specify_cli/migration/backfill_runtime_state.py", "_partition_mission_dirs"): _FILTERS,
    ("src/specify_cli/migration/backfill_topology.py", "_kitty_specs_mission_dirs"): _REQUIRES_META,
    ("src/specify_cli/migration/mission_state.py", "_select_mission_dirs"): _FILTERS,
    ("src/specify_cli/migration/normalize_mission_lifecycle.py", "_discover_candidates"): _GUARDED_DOWNSTREAM,
    ("src/specify_cli/migration/runner.py", "_discover_features"): _REQUIRES_META,
    # Was _REQUIRES_STATE; it now skips residue itself before it moves derived files (WP05).
    ("src/specify_cli/migration/runner.py", "_move_derived_files"): _FILTERS,
    # Was _GUARDED_DOWNSTREAM; cutover_repo now calls the predicate itself before cutover_mission.
    ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_repo"): _FILTERS,
}

#: Walkers the detector cannot see (they enumerate through a module constant, not a tainted name), listed by hand.
#: (module, function) -> why a residue directory is safe.
_UNDETECTED_WALKERS: dict[tuple[str, str], str] = {
    # Walks ``project / _KITTY_SPECS_DIRNAME``; every directory it returns goes through cutover_mission
    # (a guarded seam below), whose is_kitty_specs_residue check leaves residue untouched.
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_iter_mission_dirs"): _GUARDED_DOWNSTREAM,
}

#: The canonical predicate and its one single-directory wrapper.
_PREDICATES = frozenset({"is_mission_dir", "is_kitty_specs_residue"})

#: Shared seams that write (or mint an identity into) a directory a walker hands them; each must decide residue.
_GUARDED_SEAMS = (
    ("src/specify_cli/upgrade/feature_meta.py", "build_baseline_feature_meta"),
    ("src/specify_cli/migration/normalize_mission_lifecycle.py", "normalize_repo"),
    ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_mission"),
    ("src/specify_cli/migration/mission_state.py", "_select_mission_dirs"),
    ("src/specify_cli/context/mission_resolver.py", "is_kitty_specs_residue"),
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "partition_kitty_specs"),
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "partition_checkout_specs"),
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "is_residue"),
    # ResidueSafeLaneSuccessorMixin's residue decision; an override reaches it as an inherited ``self._is_residue``.
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "_is_residue"),
    # Overrides that make the subclassed shipped 0.9.0 / 0.9.1 walks residue-safe (_SUBCLASS_GUARDED).
    ("src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py", "_is_legacy_format"),
    ("src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py", "_has_remaining_lane_dirs"),
    ("src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py", "_normalize_all_frontmatter"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_without_residue"),
)


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]


def _enclosing_function(tree: ast.AST, line: int) -> str:
    owners = [fn for fn in _functions(tree) if fn.lineno <= line <= (fn.end_lineno or fn.lineno)]
    return max(owners, key=lambda fn: fn.lineno).name if owners else "<module>"


def _walker_sites() -> set[tuple[str, str]]:
    sites: set[tuple[str, str]] = set()
    for rel_dir in _SCANNED_DIRS:
        for path in sorted((_REPO_ROOT / rel_dir).glob("*.py")):
            hits = _find_raw_walker_calls(path)
            if not hits:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(_REPO_ROOT).as_posix()
            sites.update((rel, _enclosing_function(tree, line)) for line, _ in hits)
    return sites


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def test_every_migration_walker_is_classified() -> None:
    sites = _walker_sites()
    assert sites, "no walker found; the scan did not execute"
    unclassified = sorted(sites - _WALKER_INVENTORY.keys())
    assert not unclassified, (
        "New kitty-specs/ walker(s) on the migration surface. Route each through "
        "specify_cli.context.mission_resolver.is_mission_dir (residue must never be written, #6627), "
        f"then add it to _WALKER_INVENTORY: {unclassified}"
    )
    stale = sorted(_WALKER_INVENTORY.keys() - sites)
    assert not stale, f"_WALKER_INVENTORY lists walkers that no longer exist; remove them: {stale}"


@pytest.mark.parametrize(("module", "function"), _GUARDED_SEAMS)
def test_guarded_seam_calls_is_mission_dir(module: str, function: str) -> None:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    matches = [fn for fn in _functions(tree) if fn.name == function]
    assert matches, f"{module}::{function} not found"
    assert all(_reaches_predicate(tree, fn) for fn in matches), f"{module}::{function} must decide residue through is_mission_dir or is_kitty_specs_residue (#6627)"


_GUARDED_SEAM_NAMES = frozenset(function for _module, function in _GUARDED_SEAMS)


_SEAM_STEMS = frozenset((module.rsplit("/", 1)[-1].removesuffix(".py"), function) for module, function in _GUARDED_SEAMS)


def _imported_seam_names(tree: ast.AST) -> frozenset[str]:
    """Names the module imports from a module that pins that very function in ``_GUARDED_SEAMS``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        stem = node.module.rsplit(".", 1)[-1]
        names.update(alias.asname or alias.name for alias in node.names if (stem, alias.name) in _SEAM_STEMS)
    return frozenset(names)


_SEAM_MODULES = {module.rsplit("/", 1)[-1].removesuffix(".py"): module for module, _function in _GUARDED_SEAMS}


def _inherited_seam_methods(tree: ast.AST, fn: ast.AST) -> frozenset[str]:
    """Methods ``_GUARDED_SEAMS`` pins that *fn*'s class inherits from a base imported from the pinning module.

    Only a method the imported base class itself defines counts, only when *fn*'s own class lists that
    base, and never when that class defines the method itself (a local override shadows the seam), so a
    ``self.<name>`` call vouches only through a pinned seam the class really inherits.
    """
    owner = next((node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and fn in node.body), None)
    if owner is None:
        return frozenset()
    bases = {base.id for base in owner.bases if isinstance(base, ast.Name)}
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        stem = node.module.rsplit(".", 1)[-1]
        if stem not in _SEAM_MODULES:
            continue
        imported = {alias.name for alias in node.names if (alias.asname or alias.name) in bases}
        seam_tree = ast.parse((_REPO_ROOT / _SEAM_MODULES[stem]).read_text(encoding="utf-8"))
        for cls in ast.walk(seam_tree):
            if isinstance(cls, ast.ClassDef) and cls.name in imported:
                names.update(f.name for f in cls.body if isinstance(f, ast.FunctionDef) and (stem, f.name) in _SEAM_STEMS)
    # A method the class defines itself shadows the inherited seam, so it earns no credit from the base.
    names -= {f.name for f in owner.body if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)}
    return frozenset(names)


def _is_self_call(call: ast.Call, names: frozenset[str]) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self" and func.attr in names


def _reaches_predicate(tree: ast.AST, fn: ast.AST, seen: frozenset[int] = frozenset()) -> bool:
    """True when *fn* calls a predicate, directly or through a ``_GUARDED_SEAMS`` function.

    A function imported from the module that pins it in ``_GUARDED_SEAMS`` counts as reaching it, and so
    does a ``self.<method>`` call to a pinned method of an imported base class (``_inherited_seam_methods``).

    A same-module hop is followed only into a function listed in ``_GUARDED_SEAMS``: those are
    individually pinned to call the predicate, so an arbitrary helper that happens to share a name
    with a predicate-calling function cannot vouch for a walker.
    """
    if id(fn) in seen:
        return False
    seen = seen | {id(fn)}
    local = {f.name: f for f in _functions(tree) if f.name in _GUARDED_SEAM_NAMES}
    imported = _imported_seam_names(tree)
    inherited = _inherited_seam_methods(tree, fn)
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        if name in _PREDICATES or name in imported or _is_self_call(node, inherited):
            return True
        if name in local and _reaches_predicate(tree, local[name], seen):
            return True
    return False


def test_filters_classification_is_true() -> None:
    """An inventory entry that claims to filter must actually reach is_mission_dir / is_kitty_specs_residue."""
    claimed = [(module, function) for (module, function), how in _WALKER_INVENTORY.items() if how == _FILTERS]
    assert claimed, "no _FILTERS entry; the check did not execute"
    for module, function in claimed:
        tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
        assert any(fn.name == function and _reaches_predicate(tree, fn) for fn in _functions(tree)), f"{module}::{function}"


def _parse_fn(source: str, name: str) -> tuple[ast.AST, ast.AST]:
    tree = ast.parse(source)
    return tree, next(fn for fn in _functions(tree) if fn.name == name)


def test_reaches_predicate_follows_guarded_seams_only() -> None:
    """Self-mutation: a hop into an unlisted helper does not count, a hop into a guarded seam does."""
    via_seam = "def walk(x):\n    return _without_residue(x)\n\ndef _without_residue(x):\n    return is_kitty_specs_residue(x)\n"
    via_helper = "def walk(x):\n    return _helper(x)\n\ndef _helper(x):\n    return is_kitty_specs_residue(x)\n"
    direct = "def walk(x):\n    return is_mission_dir(x)\n"
    none = "def walk(x):\n    return x\n\ndef _without_residue(x):\n    return x\n"
    assert _reaches_predicate(*_parse_fn(via_seam, "walk"))
    assert not _reaches_predicate(*_parse_fn(via_helper, "walk"))
    assert _reaches_predicate(*_parse_fn(direct, "walk"))
    assert not _reaches_predicate(*_parse_fn(none, "walk"))


def _declared_migration_ids(module: str) -> set[str]:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    return {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "migration_id" for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_superseded_classification_is_true() -> None:
    """A _SUPERSEDED entry's shipped migration must really be registered as a no-op (#6589)."""
    modules = {module for (module, _function), how in _WALKER_INVENTORY.items() if how == _SUPERSEDED}
    assert modules, "no _SUPERSEDED entry; the check did not execute"
    for module in sorted(modules):
        ids = _declared_migration_ids(module)
        assert ids, f"{module} declares no migration_id"
        assert ids <= SUPERSEDED_MIGRATIONS.keys(), f"{module}: {sorted(ids - SUPERSEDED_MIGRATIONS.keys())} is not in SUPERSEDED_MIGRATIONS"


#: shipped module -> (successor module, methods the successor overrides).
_SUBCLASS_SUCCESSORS: dict[str, tuple[str, tuple[str, ...]]] = {
    "src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py": (
        "src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py",
        ("_is_legacy_format",),
    ),
    "src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py": (
        "src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py",
        ("_has_remaining_lane_dirs", "_normalize_all_frontmatter"),
    ),
}


def _subclasses_module(tree: ast.AST, shipped_module: str) -> list[ast.ClassDef]:
    """Classes whose base is an attribute of an alias bound to *shipped_module* (``from . import <shipped> as _x``)."""
    stem = shipped_module.rsplit("/", 1)[-1].removesuffix(".py")
    aliases = {alias.asname or alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names if alias.name == stem}
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and any(isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name) and b.value.id in aliases for b in node.bases)
    ]


def _overridden_methods(source: str, shipped_module: str) -> set[str]:
    return {fn.name for cls in _subclasses_module(ast.parse(source), shipped_module) for fn in cls.body if isinstance(fn, ast.FunctionDef)}


def test_subclass_guarded_classification_is_true() -> None:
    """A _SUBCLASS_GUARDED shipped walker runs live through a subclass that overrides, and pins, its residue predicates."""
    modules = {module for (module, _function), how in _WALKER_INVENTORY.items() if how == _SUBCLASS_GUARDED}
    assert modules == set(_SUBCLASS_SUCCESSORS), "every _SUBCLASS_GUARDED module needs a _SUBCLASS_SUCCESSORS row, and no other"
    for shipped, (successor, overrides) in _SUBCLASS_SUCCESSORS.items():
        source = (_REPO_ROOT / successor).read_text(encoding="utf-8")
        defined = _overridden_methods(source, shipped)
        assert defined >= set(overrides), f"{successor} must keep overriding {sorted(set(overrides) - defined)}"
        for override in overrides:
            assert (successor, override) in _GUARDED_SEAMS, f"{successor}::{override} must be pinned in _GUARDED_SEAMS"


def test_subclass_detector_notices_a_dropped_override() -> None:
    """Self-mutation: a subclass without the override, or without the shipped base, no longer vouches."""
    shipped = "src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py"
    kept = "from . import m_0_9_0_frontmatter_only_lanes as _s\nclass A(_s.X):\n    def _is_legacy_format(self, p):\n        return 1\n"
    dropped = "from . import m_0_9_0_frontmatter_only_lanes as _s\nclass A(_s.X):\n    def other(self, p):\n        return 1\n"
    unrelated = "class A(X):\n    def _is_legacy_format(self, p):\n        return 1\n"
    assert "_is_legacy_format" in _overridden_methods(kept, shipped)
    assert "_is_legacy_format" not in _overridden_methods(dropped, shipped)
    assert not _overridden_methods(unrelated, shipped)


def test_override_dropping_its_predicate_call_fails_the_gate() -> None:
    """Self-mutation: an override that stops reaching the predicate (directly or through its seam) is caught."""
    legacy = "def _is_legacy_format(self, p):\n    return super()._is_legacy_format(p){}\n\n"
    seam = "def _is_residue(self, p):\n    return {}\n"
    keeps = legacy.format(" and not self._is_residue(p)") + seam.format("is_kitty_specs_residue(p)")
    drops_call = legacy.format("") + seam.format("is_kitty_specs_residue(p)")
    drops_seam_body = legacy.format(" and not self._is_residue(p)") + seam.format("False")
    imports_seam = "from ._residue_successor import partition_checkout_specs\ndef _normalize_all_frontmatter(self, p):\n    return partition_checkout_specs(p)\n"
    mixin = "from ._residue_successor import ResidueSafeLaneSuccessorMixin as _M\nclass A({}):\n    def _is_legacy_format(self, p):\n        return {}\n"
    assert _reaches_predicate(*_parse_fn(keeps, "_is_legacy_format"))
    assert not _reaches_predicate(*_parse_fn(drops_call, "_is_legacy_format"))
    assert not _reaches_predicate(*_parse_fn(drops_seam_body, "_is_legacy_format"))
    assert _reaches_predicate(*_parse_fn(imports_seam, "_normalize_all_frontmatter"))
    # The inherited mixin seam vouches only for a class that lists the mixin, and only through the pinned method.
    assert _reaches_predicate(*_parse_fn(mixin.format("_M, _s.X", "not self._is_residue(p)"), "_is_legacy_format"))
    assert not _reaches_predicate(*_parse_fn(mixin.format("_M, _s.X", "True"), "_is_legacy_format"))
    assert not _reaches_predicate(*_parse_fn(mixin.format("_s.X", "not self._is_residue(p)"), "_is_legacy_format"))
    assert not _reaches_predicate(*_parse_fn(mixin.format("_M, _s.X", "not self.detect(p)"), "_is_legacy_format"))
    shadowed = mixin.format("_M, _s.X", "not self._is_residue(p)") + "    def _is_residue(self, p):\n        return False\n"
    assert not _reaches_predicate(*_parse_fn(shadowed, "_is_legacy_format")), "a local _is_residue must not inherit the mixin's credit"


#: The guarded seam each hand-listed walker's directories reach through its writing caller (``apply``).
_UNDETECTED_WALKER_SEAMS: dict[tuple[str, str], tuple[str, str]] = {
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_iter_mission_dirs"): (
        "src/specify_cli/migration/runtime_state_cutover.py",
        "cutover_mission",
    ),
}


def _calls_reaching(tree: ast.AST, fn: ast.AST, target: str, seen: frozenset[int] = frozenset()) -> bool:
    """True when *fn* calls *target*, directly or through same-module functions."""
    if id(fn) in seen:
        return False
    seen = seen | {id(fn)}
    local = {f.name: f for f in _functions(tree)}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _called_name(node)
            if name == target or (name in local and _calls_reaching(tree, local[name], target, seen)):
                return True
    return False


@pytest.mark.parametrize(("module", "function"), sorted(_UNDETECTED_WALKERS))
def test_undetected_walker_still_exists_and_is_guarded(module: str, function: str) -> None:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    assert any(fn.name == function for fn in _functions(tree)), f"{module}::{function} is gone; remove it from _UNDETECTED_WALKERS"
    seam = _UNDETECTED_WALKER_SEAMS[(module, function)]
    assert seam in _GUARDED_SEAMS
    writers = [fn for fn in _functions(tree) if fn.name == "apply" and _calls_reaching(tree, fn, function)]
    assert writers, f"{module}: no apply() walks through {function}; re-check the classification"
    assert all(_calls_reaching(tree, fn, seam[1]) for fn in writers), f"{module}: apply() must hand {function}'s directories to {seam[1]}"


def test_detector_blind_spots_stay_blind_to_hand_listed_walkers() -> None:
    """If the detector ever learns to see a hand-listed walker, it belongs in _WALKER_INVENTORY instead."""
    assert not set(_UNDETECTED_WALKERS) & _walker_sites()
