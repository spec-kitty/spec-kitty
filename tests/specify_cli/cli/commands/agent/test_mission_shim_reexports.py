"""Re-export presence gate for the ``mission`` shim (#2056 WP09 / T040).

After the decomposition (#2056), ``mission.py`` is a thin command-registration
shim: every business symbol now lives in a seam module, and ``mission`` re-exports
the names that history made importable/patchable as ``mission.<name>``. A future
accidental drop of one of those re-exports would silently break a downstream
``from ...mission import X`` edge or a ``@patch("...mission.X")`` seam — and only
that one test would go red, far from the shim.

This gate pins the FULL surveyed surface (derived from grepping
``@patch("...mission.`` + ``from ...mission import`` + ``mission_mod.<attr>``
across ``tests/`` + ``lifecycle.py`` + ``tasks.py`` at WP09 time) so a dropped
re-export fails HERE, loudly, next to the shim. Adding a new public ``mission``
surface? Add it to ``_REQUIRED_MISSION_ATTRS`` in the same PR.
"""

from __future__ import annotations

import pytest

from specify_cli.cli.commands.agent import mission as mission_mod

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# Every symbol that must resolve as ``mission.<name>``. Grouped for readability;
# the test treats the union as one required set.
_COMMANDS = (
    "record_analysis",
    "branch_context",
    "check_prerequisites",
    "create_mission",
    "setup_plan",
    "accept_feature",
    "merge_feature",
    "finalize_tasks",
    "app",
)

_FEATURE_RESOLUTION = (  # Seam D (WP02)
    "_find_feature_directory",
    "_primary_anchored_feature_dir",
    "_read_feature_meta",
    "_resolve_mission_dir_name_primary_anchored",
    "_build_setup_plan_detection_error",
)

_PARSING = (  # Seam C (WP03)
    "_owned_files_yaml_is_explicit_empty_list",
    "_parse_requirement_refs_from_tasks_md",
    "_parse_wp_sections_from_tasks_md",
    "_invalid_kitty_specs_owned_files",
    "INVALID_WP_OWNED_FILES_KITTY_SPECS",
)

_RECORD_ANALYSIS = (  # Seam A (WP04) — incl. the WP09-closed shim gaps
    "_resolve_record_analysis_placement_ref",
    "_enforce_analysis_report_write_preflight",
)

_BRANCH_CONTEXT = (  # Seam B / lifecycle I (WP05)
    "_resolve_planning_branch",
    "_get_current_branch",
    "_inject_branch_contract",
    "_show_branch_context",
    "_resolve_primary_branch_for_recommendation",
    "_read_meta_for_emission",
)

_SETUP_PLAN = (  # Lifecycle II (WP06)
    "CommitToBranchResult",
    "_commit_to_branch",
    "_kind_for_artifact",
)

_ACCEPT_MERGE = (  # Lifecycle II (WP06)
    "_find_feature_worktree",
    "_find_latest_feature_worktree",
    "top_level_accept",
    "top_level_merge",
)

_FINALIZE = (  # WP07
    "_branch_tree_relative_path",
    "_collect_finalize_artifacts",
)

_COMMIT_RESIDUE = (  # WP08 (relocated to commit_router, re-exported here)
    "_planning_commit_worktree",
    "_resolve_planning_placement",
    "_stage_finalize_artifacts_in_coord_worktree",
)

_CROSS_CUTTING = (  # lower-layer re-exports patched/imported via mission
    "locate_project_root",
    "get_main_repo_root",
    "get_feature_target_branch",
    "get_current_branch",
    "is_git_repo",
    "run_command",
    "run_git_preflight",
    "validate_feature_structure",
    "resolve_mission_handle",
    "resolve_template",
    "_enforce_git_preflight",
)

_REQUIRED_MISSION_ATTRS: tuple[str, ...] = (
    _COMMANDS
    + _FEATURE_RESOLUTION
    + _PARSING
    + _RECORD_ANALYSIS
    + _BRANCH_CONTEXT
    + _SETUP_PLAN
    + _ACCEPT_MERGE
    + _FINALIZE
    + _COMMIT_RESIDUE
    + _CROSS_CUTTING
)


@pytest.mark.parametrize("name", _REQUIRED_MISSION_ATTRS)
def test_mission_reexports_required_symbol(name: str) -> None:
    """Every surveyed ``mission.<name>`` surface must resolve on the shim."""
    assert hasattr(mission_mod, name), (
        f"mission.{name} no longer resolves — a re-export was dropped. "
        f"Restore the deliberate `as` re-export in mission.py (it is a historical "
        f"patch target / import edge)."
    )


# ``test_record_analysis_shim_gaps_closed`` (#2056 WP09 one-shot "gap closed"
# pin) was retired here (#2076, WP03): both
# ``_resolve_record_analysis_placement_ref`` and
# ``_enforce_analysis_report_write_preflight`` are literal ``as``-reexports in
# ``mission.py`` (`from .mission_record_analysis import X as X`), so
# ``mission_mod.X is seam.X`` holds by construction; the two symbols already
# live in the ``_RECORD_ANALYSIS`` tuple above and are covered by the
# parametrized ``test_mission_reexports_required_symbol`` battery.


def test_no_required_symbol_duplicated_in_survey() -> None:
    """The required-surface tuples must stay duplicate-free (catches copy-paste)."""
    assert len(_REQUIRED_MISSION_ATTRS) == len(set(_REQUIRED_MISSION_ATTRS))
