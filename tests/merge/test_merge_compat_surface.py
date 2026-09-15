"""Consolidated compat-surface guard for the ``specify_cli.merge`` seam family.

Mission dev-assist-retire-path-hardening-01KXAVR0, WP04 (#2565 / #2071). The
#2057 decomposition left the ``cli.commands.merge`` re-export identity check
fragmented across ``tests/merge/*_seam.py`` -- 8 test functions across 7 of the
8 seam files, under 4 different names, over 4 different constants
(``forecast.py`` has none) -- plus 8 byte-identical one-way-import guards, one
per seam file. Both were real, unique coverage (not duplicated by
``tests/specify_cli/cli/commands/test_merge_cli_golden.py``, which only pins
public commands) but re-broke per-seam instead of failing loudly next to the
shim. This module is the single consolidated guard, shaped after
``test_mission_shim_reexports.py``.

Per the codebase convention for consolidated compat-surface guards this
guard is self-contained -- no cross-family shared helper module.
"""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

import pytest

from specify_cli.cli.commands import merge as shim
from specify_cli.merge import (
    _constants,
    bookkeeping_projection as bp,
    done_bookkeeping as db,
    forecast,
    git_probes,
    ordering,
    preflight,
    push_preflight,
    resolve,
)

pytestmark = pytest.mark.fast


# ===========================================================================
# T001 -- symbol -> residual-module map (NOT a flat name union: each seam
# re-exports from a different residual, and ``preflight`` splits across TWO --
# ``merge.preflight`` and ``merge.push_preflight``, issue #1706 boundary).
# ===========================================================================

_GIT_PROBES_SYMBOLS: tuple[str, ...] = (
    "_lane_already_integrated",
    "_branch_trees_equal",
    "path_is_under_worktrees",
    "_raw_porcelain_status",
    "_classify_porcelain_lines",
    "_is_linear_history_rejection",
    "_emit_remediation_hint",
    "_refresh_primary_checkout_after_merge",
    "_paths_have_status_changes",
    "_is_git_repo",
    "_has_branch_ref",
)

_CONSTANTS_SYMBOLS: tuple[str, ...] = (
    "TARGET_BRANCH_NOT_SYNCHRONIZED",
    "TARGET_BRANCH_SYNC_INVARIANT",
    "_STATUS_EVENTS_FILENAME",
    "_STATUS_FILENAME",
    "_SAFE_PATH_SEGMENT_DIAGNOSTIC",
    "LINEAR_HISTORY_REJECTION_TOKENS",
    "MissionBranchBlocker",
    "HollowReviewWarnings",
    "logger",
)

_RESOLVE_SYMBOLS: tuple[str, ...] = (
    "_resolve_mission_slug",
    "_resolve_target_branch",
    "_load_merge_state_for_mission",
    "_load_merge_state_entry_for_mission",
    "_load_or_create_merge_state",
    "_clear_merge_state_for_mission",
    "_cleanup_merge_workspaces_for_state",
)

_PREFLIGHT_SYMBOLS: tuple[str, ...] = (
    "_check_mission_branch",
    "_effective_push_requested",
    "_enforce_canonical_status_history",
    "_enforce_review_artifact_consistency",
    "_validate_target_branch",
    "_enforce_git_preflight",
    "_enforce_planning_artifact_target_branch",
    "_collect_hollow_review_warnings",
    "_warn_or_confirm_hollow_reviews",
)

_PUSH_PREFLIGHT_SYMBOLS: tuple[str, ...] = (
    "_enforce_target_branch_sync_preflight",
    "_target_branch_sync_payload",
)

_ORDERING_SYMBOLS: tuple[str, ...] = ("_bake_mission_number_into_mission_branch",)

_DONE_BOOKKEEPING_SYMBOLS: tuple[str, ...] = (
    "_mark_wp_merged_done",
    "_assert_merged_wps_reached_done",
    "_assert_merged_wps_done_on_target",
    "_reconcile_completed_wps_for_resume",
    "_has_transition_to",
    "_resolve_merge_actor",
)

# WP09 (T048 / TAO-3): the final-bookkeeping snapshot/restore compensator and its
# merge-side trust helper were retired from ``bookkeeping_projection`` (the executor
# now enrols through the single owner compensator in ``coordination.atomic_write``),
# so those three symbols left this shim's re-export surface.
_BOOKKEEPING_PROJECTION_SYMBOLS: tuple[str, ...] = (
    "_validate_mission_slug_path_segment",
    "_target_bookkeeping_status_paths",
    "_assert_status_path_within_target_surface",
    "_assert_status_surface_path_is_trusted",
    "_target_branch_still_at_baseline",
    "_project_status_bookkeeping_to_target",
)

# ``forecast`` re-exports nothing (no identity battery in test_forecast_seam.py
# today) -- intentionally absent from the map. It still gets the one-way-import
# guard below (Guard-B-adjacent, but that guard is import-boundary, not
# identity, so ``forecast`` participates in ``_SEAM_IMPORT_TARGETS`` only).

SYMBOL_RESIDUAL_MAP: dict[str, ModuleType] = {
    **dict.fromkeys(_GIT_PROBES_SYMBOLS, git_probes),
    **dict.fromkeys(_CONSTANTS_SYMBOLS, _constants),
    **dict.fromkeys(_RESOLVE_SYMBOLS, resolve),
    **dict.fromkeys(_PREFLIGHT_SYMBOLS, preflight),
    **dict.fromkeys(_PUSH_PREFLIGHT_SYMBOLS, push_preflight),
    **dict.fromkeys(_ORDERING_SYMBOLS, ordering),
    **dict.fromkeys(_DONE_BOOKKEEPING_SYMBOLS, db),
    **dict.fromkeys(_BOOKKEEPING_PROJECTION_SYMBOLS, bp),
}


def test_map_has_no_duplicate_source_symbol() -> None:
    """Catches an accidental symbol collision across the ``_*_SYMBOLS`` tuples
    above, which ``dict.fromkeys`` merging would otherwise silently overwrite."""
    all_names = (
        _GIT_PROBES_SYMBOLS
        + _CONSTANTS_SYMBOLS
        + _RESOLVE_SYMBOLS
        + _PREFLIGHT_SYMBOLS
        + _PUSH_PREFLIGHT_SYMBOLS
        + _ORDERING_SYMBOLS
        + _DONE_BOOKKEEPING_SYMBOLS
        + _BOOKKEEPING_PROJECTION_SYMBOLS
    )
    assert len(all_names) == len(set(all_names)), (
        f"duplicate symbol across seam batteries: "
        f"{sorted({n for n in all_names if all_names.count(n) > 1})}"
    )
    assert len(all_names) == len(SYMBOL_RESIDUAL_MAP) == 51


# ===========================================================================
# T003 -- superset proof: the map must not have dropped a symbol relative to
# the retired per-seam batteries. Transcribed INDEPENDENTLY from the
# ``_*_SYMBOLS`` tuples above (not derived from them) so an accidental shrink
# of one of those tuples still trips this assertion -- NFR-002.
# ===========================================================================

_RETIRED_BATTERY_UNION: frozenset[str] = frozenset(
    {
        # test_git_probes_seam.py RELOCATED_NAMES (11)
        "_lane_already_integrated",
        "_branch_trees_equal",
        "path_is_under_worktrees",
        "_raw_porcelain_status",
        "_classify_porcelain_lines",
        "_is_linear_history_rejection",
        "_emit_remediation_hint",
        "_refresh_primary_checkout_after_merge",
        "_paths_have_status_changes",
        "_is_git_repo",
        "_has_branch_ref",
        # test_constants_seam.py identity-parametrize list (9)
        "TARGET_BRANCH_NOT_SYNCHRONIZED",
        "TARGET_BRANCH_SYNC_INVARIANT",
        "_STATUS_EVENTS_FILENAME",
        "_STATUS_FILENAME",
        "_SAFE_PATH_SEGMENT_DIAGNOSTIC",
        "LINEAR_HISTORY_REJECTION_TOKENS",
        "MissionBranchBlocker",
        "HollowReviewWarnings",
        "logger",
        # test_resolve_seam.py SHIM_REEXPORTED (7)
        "_resolve_mission_slug",
        "_resolve_target_branch",
        "_load_merge_state_for_mission",
        "_load_merge_state_entry_for_mission",
        "_load_or_create_merge_state",
        "_clear_merge_state_for_mission",
        "_cleanup_merge_workspaces_for_state",
        # test_preflight_seam.py SHIM_REEXPORTED_FROM_PREFLIGHT (9)
        "_check_mission_branch",
        "_effective_push_requested",
        "_enforce_canonical_status_history",
        "_enforce_review_artifact_consistency",
        "_validate_target_branch",
        "_enforce_git_preflight",
        "_enforce_planning_artifact_target_branch",
        "_collect_hollow_review_warnings",
        "_warn_or_confirm_hollow_reviews",
        # test_preflight_seam.py SHIM_REEXPORTED_FROM_PUSH_PREFLIGHT (2)
        "_enforce_target_branch_sync_preflight",
        "_target_branch_sync_payload",
        # test_ordering_bake_seam.py test_shim_re_exports_bake_entrypoint (1)
        "_bake_mission_number_into_mission_branch",
        # test_done_bookkeeping_seam.py SHIM_REEXPORTED (6)
        "_mark_wp_merged_done",
        "_assert_merged_wps_reached_done",
        "_assert_merged_wps_done_on_target",
        "_reconcile_completed_wps_for_resume",
        "_has_transition_to",
        "_resolve_merge_actor",
        # test_bookkeeping_projection_seam.py SHIM_REEXPORTED (6; WP09 T048 retired
        # the 3 snapshot/restore-compensator symbols to the owner compensator)
        "_validate_mission_slug_path_segment",
        "_target_bookkeeping_status_paths",
        "_assert_status_path_within_target_surface",
        "_assert_status_surface_path_is_trusted",
        "_target_branch_still_at_baseline",
        "_project_status_bookkeeping_to_target",
        # test_forecast_seam.py -- no identity battery (none retired).
    }
)


def test_consolidated_map_is_superset_of_retired_batteries() -> None:
    """NFR-002: the consolidated map must cover every symbol the 8 retired
    per-seam identity batteries bound -- a dropped symbol fails here, loudly,
    next to the shim, instead of silently vanishing when the fragmented tests
    were deleted."""
    # The union's members are already fully enumerated above via named literal
    # sets; this pins the union produced no accidental duplicate-symbol
    # collisions across the 8 retired per-seam batteries (a count invariant,
    # not a membership one -- membership is pinned by the literals themselves).
    assert len(_RETIRED_BATTERY_UNION) == 51
    missing = _RETIRED_BATTERY_UNION - set(SYMBOL_RESIDUAL_MAP)
    assert not missing, f"consolidated guard dropped symbols: {sorted(missing)}"
    assert set(SYMBOL_RESIDUAL_MAP) >= _RETIRED_BATTERY_UNION


# ===========================================================================
# T001 -- identity re-export guard (per-symbol, over the map).
# ===========================================================================


def test_no_map_symbol_is_natively_defined_on_the_shim() -> None:
    """Anti-hazard confirmation (T001): before trusting an ``is``-identity
    assertion, confirm the symbol is a genuine import binding on the shim, not
    a native ``def``/``class`` that happens to share a name with a residual
    symbol (the ``_load_feature_runs`` hazard class documented in
    ``tests/runtime/test_bridge_io.py`` -- there, the residual keeps a native
    thin delegate rather than a plain re-export, which would make an
    ``is``-identity assertion wrong). A native redefine on ``merge.py`` would
    make the identity check below meaningless (it would simply fail for the
    wrong reason). Verified here by AST rather than assumed."""
    tree = ast.parse(inspect.getsource(shim))
    natively_defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    hazards = natively_defined & set(SYMBOL_RESIDUAL_MAP)
    assert not hazards, (
        f"symbols natively defined on the shim, not re-exported: {sorted(hazards)} -- "
        "remove from SYMBOL_RESIDUAL_MAP (they are not identity re-exports; a native "
        "redefine needs a different guard shape, cf. the _load_feature_runs hazard)."
    )


@pytest.mark.parametrize(
    "name,residual",
    sorted(SYMBOL_RESIDUAL_MAP.items()),
    ids=[name for name, _residual in sorted(SYMBOL_RESIDUAL_MAP.items())],
)
def test_shim_reexports_identical_object(name: str, residual: ModuleType) -> None:
    """Guard (B) identity re-export: ``merge.<name>`` must be the exact same
    object as ``<residual>.<name>`` -- never a copy. A copy is a false-green
    under ``monkeypatch.setattr``/``mocker.patch`` seams that target the shim."""
    assert getattr(shim, name) is getattr(residual, name), (
        f"merge.{name} is not the identical object as {residual.__name__}.{name} -- "
        "the shim re-export is a copy, not an identity re-export."
    )


# ===========================================================================
# T002 -- consolidated one-way-import guard (replaces the 8 byte-identical
# ``test_<seam>_does_not_import_the_command_shim`` copies).
# ===========================================================================

_SEAM_IMPORT_TARGETS: tuple[tuple[str, ModuleType], ...] = (
    ("git_probes", git_probes),
    ("_constants", _constants),
    ("resolve", resolve),
    ("preflight", preflight),
    ("forecast", forecast),
    ("ordering", ordering),
    ("done_bookkeeping", db),
    ("bookkeeping_projection", bp),
)


@pytest.mark.parametrize(
    "alias,module",
    _SEAM_IMPORT_TARGETS,
    ids=[alias for alias, _module in _SEAM_IMPORT_TARGETS],
)
def test_seam_does_not_import_the_command_shim(alias: str, module: ModuleType) -> None:
    """One-way import (C-006/INV-2): no merge seam module may import the
    ``cli.commands.merge`` shim back (would create an import cycle). Importing
    shared helpers (e.g. ``cli.helpers.console``) is fine -- only reaching back
    into the shim itself is forbidden."""
    tree = ast.parse(inspect.getsource(module))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.update(a.name for a in node.names)
    assert not any(m.startswith("specify_cli.cli.commands.merge") for m in imported_modules), (
        f"{alias} imports the command shim (cycle risk): {sorted(imported_modules)}"
    )
