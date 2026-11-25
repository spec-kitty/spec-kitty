"""Routing pins for the asset-install surface that ``spec-kitty upgrade`` drives (#7775).

``spec-kitty upgrade`` (and ``init``) prepare the agent skills and command
surface through ``src/specify_cli/skills/**``, ``src/specify_cli/tool_surface/**``
and ``src/specify_cli/runtime/**`` (``agent_skills.py``, ``asset_preparation.py``,
``generated_writer.py``, ...). On ``main`` before #7775 none of those paths
selected the ``upgrade`` module: ``tool_surface/**`` routed to ``core_misc``,
``runtime/**`` to ``next`` / ``specify_cli_runtime``, and ``skills/**`` matched no
src group at all. A ``skills/**``-only diff is run-all (FR-004), but the
``unmatched`` signal is per diff, so in #7763 the other src paths masked it and
no ``upgrade`` shard ran. The break reached ``main`` and showed up first in a
nightly.

The fix is a NON-src ``upgrade_asset_surface`` router group fanned out by the
single gate-selection authority (``gate_selection.ASSET_SURFACE_MODULE_FANOUT``)
to ``upgrade`` and to ``cli`` (whose ``tests/init`` runs ``spec-kitty init``,
the other entry that prepares these assets). Every assertion drives the
production entry point ``select_modules``.
"""

from __future__ import annotations

import pytest

from scripts.ci.gate_selection import (
    ASSET_SURFACE_MODULE_FANOUT,
    load_router,
    select_gates,
    select_modules,
)

pytestmark = pytest.mark.fast

ASSET_GROUP = "upgrade_asset_surface"

#: The src paths #7763 changed under the three asset-install packages (a subset of
#: its 98-file diff; the full list is replayed below).
ASSET_PATHS: tuple[str, ...] = (
    "src/specify_cli/skills/installer.py",
    "src/specify_cli/skills/verifier.py",
    "src/specify_cli/tool_surface/repair.py",
    "src/specify_cli/tool_surface/service.py",
    "src/specify_cli/tool_surface/providers/managed_skills.py",
    "src/specify_cli/runtime/agent_skills.py",
    "src/specify_cli/runtime/asset_preparation.py",
    "src/specify_cli/runtime/generated_writer.py",
)

#: #7763's changed-file list at head ``a57e2940`` (src and tests only; its docs,
#: kitty-specs and kitty-ops paths select no module and are left out).
PR_7763_PATHS: tuple[str, ...] = (
    "scripts/skills/build_historical_skill_digests.py",
    "src/charter/offering/skills/README.md",
    "src/charter/offering/skills/spk-meta-skill-map/references/spk-skill-map.md",
    "src/charter/offering/skills/spk-start-first-mission/SKILL.md",
    "src/charter/offering/skills/spk-start-here/SKILL.md",
    "src/specify_cli/cli/commands/_command_surface_doctor.py",
    "src/specify_cli/runtime/agent_commands.py",
    "src/specify_cli/runtime/agent_skills.py",
    "src/specify_cli/runtime/asset_preparation.py",
    "src/specify_cli/runtime/doctor.py",
    "src/specify_cli/skills/command_installer.py",
    "src/specify_cli/skills/data/historical_skill_renders.json",
    "src/specify_cli/skills/historical_renders.py",
    "src/specify_cli/skills/installer.py",
    "src/specify_cli/skills/retired.py",
    "src/specify_cli/skills/verifier.py",
    "src/specify_cli/tool_surface/contracts/migration-compatibility.md",
    "src/specify_cli/tool_surface/findings.py",
    "src/specify_cli/tool_surface/providers/managed_skills.py",
    "src/specify_cli/tool_surface/repair.py",
    "src/specify_cli/tool_surface/service.py",
    "tests/architectural/test_retired_charter_vocabulary.py",
    "tests/charter_offering/test_spk_skill_pack.py",
    "tests/runtime/test_asset_preparation_retire_proof.py",
    "tests/runtime/test_build_serialized.py",
    "tests/runtime/test_global_asset_inventory_anchor.py",
    "tests/specify_cli/cli/commands/test_doctor_legacy_no_agent_list_reports.py",
    "tests/specify_cli/cli/commands/test_doctor_skills.py",
    "tests/specify_cli/cli/commands/test_doctor_stated_empty_reports.py",
    "tests/specify_cli/runtime/test_global_skills_historical_proof.py",
    "tests/specify_cli/runtime/test_old_root_leftovers.py",
    "tests/specify_cli/skills/test_crlf_skill_render_4998.py",
    "tests/specify_cli/skills/test_first_mission_skill_rename.py",
    "tests/specify_cli/skills/test_historical_renders.py",
    "tests/specify_cli/skills/test_project_skills_historical_proof.py",
    "tests/specify_cli/skills/test_retired_skill_completeness.py",
    "tests/specify_cli/skills/test_verify_retired_orphan.py",
    "tests/specify_cli/tool_surface/integration/fixtures/doctor_skills_baseline.json",
    "tests/specify_cli/tool_surface/test_global_skill_kept_findings.py",
)

#: A src path that a named src group routes, so a diff carrying it is not run-all.
#: Paired with each asset path it reproduces #7763's masking of the per-diff
#: ``unmatched`` signal.
ROUTED_COMPANION = "src/specify_cli/cli/commands/_command_surface_doctor.py"


def test_replaying_pr_7763_selects_upgrade() -> None:
    """#7775 Done-when: #7763's changed files, replayed, select the ``upgrade`` module."""
    selected = select_modules(PR_7763_PATHS)
    assert "upgrade" in selected
    assert "cli" in selected


@pytest.mark.parametrize("path", ASSET_PATHS)
def test_asset_path_selects_upgrade_even_beside_a_routed_src_path(path: str) -> None:
    """Each asset path selects ``upgrade`` and ``cli``, also when a routed src path masks ``unmatched``."""
    assert {"upgrade", "cli"} <= select_modules([path, ROUTED_COMPANION])


@pytest.mark.parametrize(
    "path",
    [
        "src/specify_cli/tool_surface/repair.py",
        "src/specify_cli/runtime/agent_skills.py",
        "src/specify_cli/runtime/asset_preparation.py",
    ],
)
def test_single_asset_path_selects_upgrade(path: str) -> None:
    """A tool_surface-only and an agent_skills-only diff select ``upgrade`` on their own."""
    assert {"upgrade", "cli"} <= select_modules([path])


def test_skills_only_diff_selects_upgrade_without_run_all() -> None:
    """Since #7775 routed ``skills/**`` to the modules whose tests import it, a skills-only diff is narrow."""
    selection = select_gates(["src/specify_cli/skills/installer.py"])
    assert ASSET_GROUP in selection.matched_groups
    assert not selection.unmatched_src
    assert {"upgrade", "cli"} <= select_modules(["src/specify_cli/skills/installer.py"])


def test_group_is_non_src_and_wired() -> None:
    """The router group exists, carries only ``**/``-prefixed globs and fans out to ``upgrade`` + ``cli``."""
    router = load_router()
    assert ASSET_SURFACE_MODULE_FANOUT[ASSET_GROUP] == frozenset({"upgrade", "cli"})
    globs = router.filters[ASSET_GROUP]
    assert globs, "the asset-surface group must not be empty"
    assert all(glob.startswith("**/") for glob in globs), globs
    assert ASSET_GROUP not in router.src_backed_groups


@pytest.mark.parametrize(
    "path",
    [
        "src/charter/offering/skills/spk-start-here/SKILL.md",
        "src/runtime/next/_internal_runtime/engine.py",
        "src/specify_cli/review/verdict.py",
    ],
)
def test_lookalike_paths_do_not_join_the_group(path: str) -> None:
    """Only ``specify_cli``'s own skills/tool_surface/runtime packages match, not lookalikes."""
    assert ASSET_GROUP not in select_gates([path]).matched_groups
