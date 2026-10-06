"""Unit tests for the pure mission-creation decision cores.

Plain inputs only: no git repository, no temporary files, no monkeypatch. Every
branch of every core in :mod:`specify_cli.core.mission_creation_decisions` is
pinned here; the golden matrix and the probe-order test prove the cores are
wired into the create path.
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation_decisions import (
    CasReset,
    CommitFailureKind,
    Delete,
    Mint,
    NoMint,
    Noop,
    ProtectedMintFacts,
    Refuse,
    candidate_name_matches,
    classify_scaffold_commit_failure,
    coord_rollback_action,
    coord_rollback_needs_current_tip,
    created_file_sets,
    decide_protected_mint,
    is_abandoned,
    is_coordination_routed,
    is_same_mission_type,
    meta_flag_patch,
    orphan_scaffold_candidates,
    plan_orphan_scaffold_removal,
    protected_mint_applies,
    target_is_protected,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._create import topology_mints_coordination_branch

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_ALL_TOPOLOGIES = tuple(MissionTopology)
_COORD_TOPOLOGIES = tuple(t for t in MissionTopology if topology_mints_coordination_branch(t))


# ---------------------------------------------------------------------------
# Protection
# ---------------------------------------------------------------------------


def _policy(*branches: str, hatch: bool = False, bypass: str | None = None) -> ProtectionPolicy:
    return ProtectionPolicy(protected_branches=frozenset(branches), operator_hatch_active=hatch, mission_bypass_branch=bypass)


@pytest.mark.parametrize(
    ("policy", "target", "primary", "expected"),
    [
        (_policy(), "main", "main", True),  # the Primary Branch is protected even unconfigured
        (_policy("release"), "release", "main", True),  # a configured non-primary target
        (_policy("release"), "topic", "main", False),
        (_policy("main"), "main", "main", True),
        (_policy("main", hatch=True), "main", "main", False),  # the operator hatch
        (_policy("main", bypass="main"), "main", "main", False),  # commit_to_target bypass
    ],
)
def test_target_is_protected_delegates_to_the_policy(policy: ProtectionPolicy, target: str, primary: str, expected: bool) -> None:
    assert target_is_protected(policy, target, primary) is expected
    assert target_is_protected(policy, target, primary) is policy.is_protected_target(target, primary_branch=primary)


@pytest.mark.parametrize(
    ("topology", "commit_to_target", "target_protected"),
    list(itertools.product(_ALL_TOPOLOGIES, (None, False, True), (None, False, True))),
)
def test_protected_mint_applies_truth_table(topology: MissionTopology, commit_to_target: bool | None, target_protected: bool | None) -> None:
    result = protected_mint_applies(topology, commit_to_target, target_protected)
    if topology is not MissionTopology.SINGLE_BRANCH:
        assert result is False
    elif commit_to_target is None:
        assert result is None  # the override has not been read yet
    elif commit_to_target:
        assert result is False
    else:
        assert result is target_protected  # None while protection is unresolved


def test_protected_mint_applies_only_for_unoverridden_protected_single_branch() -> None:
    assert protected_mint_applies(MissionTopology.SINGLE_BRANCH, False, True) is True
    assert protected_mint_applies(MissionTopology.SINGLE_BRANCH, False, False) is False
    assert protected_mint_applies(MissionTopology.SINGLE_BRANCH, True, True) is False
    assert protected_mint_applies(MissionTopology.LANES, False, True) is False


# ---------------------------------------------------------------------------
# Protected mint decision: every prefix of the probe order
# ---------------------------------------------------------------------------

_BASE = ProtectedMintFacts(target_branch="main", write_root_display="/repo", mint_applies=True)
_NO_COMMIT_MESSAGE = (
    "Cannot mint the protected-target mission branch: target branch 'main' "
    "has no commit in /repo (it does not exist yet, or is still unborn). "
    "Create it with at least one commit (for example: git branch main <start-point>), "
    "or pass --target-branch naming an existing branch, then retry."
)
_DIRTY_MESSAGE = (
    "Cannot mint the protected-target mission branch: the write checkout at /repo has "
    "uncommitted changes outside this mission's own scaffold: stray.txt, src/x.py. "
    "Commit or discard them, then retry."
)
_EXISTS_MESSAGE = (
    "Mission branch 'kitty/mission-demo-01ABCDEF' already exists. Choose a different mission slug, "
    "remove the stale branch, or pass --commit-to-target to commit directly onto the target."
)
_BRANCH = "kitty/mission-demo-01ABCDEF"


def _facts(**fields: Any) -> ProtectedMintFacts:
    return replace(_BASE, **fields)


def test_unprotected_target_decides_no_mint_before_any_probe() -> None:
    assert decide_protected_mint(_facts(mint_applies=False)) == NoMint()


def test_prefix_applies_only_needs_the_target_commit_probe() -> None:
    assert decide_protected_mint(_facts()) is None


def test_target_without_commit_refuses_with_the_exact_message() -> None:
    assert decide_protected_mint(_facts(target_has_commit=False)) == Refuse("error", _NO_COMMIT_MESSAGE)


def test_prefix_through_target_commit_needs_the_dirty_probe() -> None:
    assert decide_protected_mint(_facts(target_has_commit=True)) is None


def test_dirty_checkout_refuses_with_the_exact_message() -> None:
    decision = decide_protected_mint(_facts(target_has_commit=True, dirty_outside_scaffold=("stray.txt", "src/x.py")))
    assert decision == Refuse("error", _DIRTY_MESSAGE)


def test_prefix_through_clean_checkout_needs_the_branch_probe() -> None:
    assert decide_protected_mint(_facts(target_has_commit=True, dirty_outside_scaffold=())) is None
    assert decide_protected_mint(_facts(target_has_commit=True, dirty_outside_scaffold=(), branch_name=_BRANCH)) is None


def test_existing_branch_refuses_as_branch_exists() -> None:
    decision = decide_protected_mint(_facts(target_has_commit=True, dirty_outside_scaffold=(), branch_name=_BRANCH, branch_exists=True))
    assert decision == Refuse("branch_exists", _EXISTS_MESSAGE)


def test_every_fact_clear_mints_the_composed_branch() -> None:
    decision = decide_protected_mint(_facts(target_has_commit=True, dirty_outside_scaffold=(), branch_name=_BRANCH, branch_exists=False))
    assert decision == Mint(_BRANCH)


def test_earlier_refusal_wins_over_later_facts() -> None:
    """A later fact never overrides the first deciding one (probe order)."""
    decision = decide_protected_mint(_facts(target_has_commit=False, dirty_outside_scaffold=("x",), branch_name=_BRANCH, branch_exists=True))
    assert decision == Refuse("error", _NO_COMMIT_MESSAGE)
    assert decide_protected_mint(_facts(mint_applies=False, target_has_commit=False)) == NoMint()


# ---------------------------------------------------------------------------
# Coordination-routed predicate (defined once) and its call sites
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("mints", "owned", "expected"), [(True, False, True), (True, True, False), (False, False, False), (False, True, False)])
def test_is_coordination_routed(mints: bool, owned: bool, expected: bool) -> None:
    assert is_coordination_routed(mints_coordination=mints, owned=owned) is expected


@pytest.mark.parametrize(("topology", "owned"), list(itertools.product(_ALL_TOPOLOGIES, (False, True))))
def test_scaffold_site_result_unchanged(topology: MissionTopology, owned: bool) -> None:
    """``_scaffold_mission_dir``: formerly ``owned is None and topology_mints_coordination_branch(topology)``."""
    legacy = (not owned) and topology_mints_coordination_branch(topology)
    assert is_coordination_routed(mints_coordination=topology_mints_coordination_branch(topology), owned=owned) is legacy


@pytest.mark.parametrize(("topology", "owned"), list(itertools.product(_COORD_TOPOLOGIES, (False, True))))
def test_seed_site_result_unchanged(topology: MissionTopology, owned: bool) -> None:
    """``_seed_coord_surface_for_create``: past its topology gate it formerly returned early on ``owned is not None``."""
    legacy_returns_early = owned
    assert (not is_coordination_routed(mints_coordination=topology_mints_coordination_branch(topology), owned=owned)) is legacy_returns_early


def test_result_site_keeps_its_own_condition() -> None:
    """``_build_create_result`` keys on the seeded log: a skipped seed is not routed there.

    A coordination topology whose seed was skipped (``status_log_path`` unset)
    is routed for the topology predicate but not for the result, so the two
    are not identical and the result site keeps its own condition.
    """
    status_log_path = None
    owned_create_root = None
    result_site = status_log_path is not None and owned_create_root is None
    assert result_site is False
    assert is_coordination_routed(mints_coordination=True, owned=False) is True


# ---------------------------------------------------------------------------
# meta.json flags
# ---------------------------------------------------------------------------

_FLAG_KEYS = ("pr_bound", "retain_branches", "retain_worktrees", "commit_to_target")


@pytest.mark.parametrize("flags", list(itertools.product((False, True), repeat=4)))
def test_meta_flag_patch_writes_only_true_keys_in_order(flags: tuple[bool, bool, bool, bool]) -> None:
    patch = meta_flag_patch(**dict(zip(_FLAG_KEYS, flags, strict=True)))
    assert list(patch) == [key for key, flag in zip(_FLAG_KEYS, flags, strict=True) if flag]
    assert all(value is True for value in patch.values())


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "base_slug", "expected"),
    [
        ("task-list", "task-list", (True, "")),
        ("task-list-01ABCDEF", "task-list", (True, "01ABCDEF")),
        ("task-list-api-01ABCDEF", "task-list", (False, "")),  # same-prefixed neighbour
        ("task-list-01ABCDE", "task-list", (False, "")),  # short mid8
        ("other", "task-list", (False, "")),
        ("a.b-01ABCDEF", "a.b", (True, "01ABCDEF")),
        ("axb-01ABCDEF", "a.b", (False, "")),  # the slug is escaped, not a regex
    ],
)
def test_candidate_name_matches(name: str, base_slug: str, expected: tuple[bool, str]) -> None:
    assert candidate_name_matches(name, base_slug) == expected


@pytest.mark.parametrize(
    ("meta", "mission_type", "expected"),
    [
        ({}, "software-dev", True),  # absent type defaults to software-dev
        ({"mission_type": None}, "software-dev", True),
        ({"mission_type": ""}, "software-dev", True),
        ({"mission_type": "research"}, "software-dev", False),
        ({"mission_type": "research"}, "research", True),
    ],
)
def test_is_same_mission_type(meta: dict[str, object], mission_type: str, expected: bool) -> None:
    assert is_same_mission_type(meta, mission_type) is expected


@pytest.mark.parametrize(
    ("wp_lanes", "event_count", "spec_tracked", "expected"),
    [
        ({"WP01": "canceled", "WP02": "canceled"}, 4, None, True),  # all canceled, no probe needed
        ({"WP01": "canceled", "WP02": "planned"}, 4, None, False),
        ({"WP01": "canceled", "WP02": None}, 0, None, None),  # not all canceled, genesis: needs the probe
        ({}, 0, None, None),
        ({}, 0, False, True),  # genesis and spec never committed
        ({}, 0, True, False),
        ({}, 3, None, False),  # lifecycle progress: live, no probe needed
    ],
)
def test_is_abandoned(wp_lanes: dict[str, str | None], event_count: int, spec_tracked: bool | None, expected: bool | None) -> None:
    assert is_abandoned(wp_lanes=wp_lanes, canceled_lane="canceled", event_count=event_count, spec_tracked=spec_tracked) is expected


@pytest.mark.parametrize(
    ("wp_lanes", "event_count", "spec_tracked", "mission_branch_live", "expected"),
    [
        ({}, 0, False, True, False),  # #5726: genesis with a live minted mission branch is LIVE
        ({}, 0, False, False, True),  # FR-003: untracked spec + live branch but this create does not mint -> still abandoned
        ({}, 0, True, True, False),
        ({}, 0, None, True, None),  # the spec probe still decides first
        ({"WP01": "canceled"}, 2, None, True, True),  # all canceled stays abandoned
        ({}, 3, None, True, False),
    ],
)
def test_is_abandoned_with_a_live_mission_branch(
    wp_lanes: dict[str, str | None], event_count: int, spec_tracked: bool | None, mission_branch_live: bool, expected: bool | None
) -> None:
    verdict = is_abandoned(wp_lanes=wp_lanes, canceled_lane="canceled", event_count=event_count, spec_tracked=spec_tracked, mission_branch_live=mission_branch_live)
    assert verdict is expected


# ---------------------------------------------------------------------------
# Failed-create rollback
# ---------------------------------------------------------------------------

_PRE = frozenset({"old-mission-01AAAAAA", "task-list-01OLDOLD1"})
_POST = _PRE | {"task-list-01ABCDEF", "task-list", "task-list-api-01ABCDEF", "unrelated-01ABCDEF"}


def test_orphan_scaffold_candidates_are_new_sorted_same_stem() -> None:
    assert orphan_scaffold_candidates(post_names=_POST, pre_names=_PRE, mission_slug="task-list") == ("task-list", "task-list-01ABCDEF")


def test_plan_orphan_scaffold_removal_keeps_tracked() -> None:
    planned = plan_orphan_scaffold_removal(post_names=_POST, pre_names=_PRE, mission_slug="task-list", tracked=frozenset({"task-list"}))
    assert planned == ("task-list-01ABCDEF",)
    assert plan_orphan_scaffold_removal(post_names=_POST, pre_names=_POST, mission_slug="task-list", tracked=frozenset()) == ()


@pytest.mark.parametrize(
    ("created", "pre_seed_tip", "needs"),
    [(True, None, False), (True, "a" * 40, False), (False, None, False), (False, "a" * 40, True)],
)
def test_coord_rollback_needs_current_tip(created: bool, pre_seed_tip: str | None, needs: bool) -> None:
    assert coord_rollback_needs_current_tip(created=created, pre_seed_tip=pre_seed_tip) is needs


@pytest.mark.parametrize(
    ("created", "pre_seed_tip", "current_tip", "expected"),
    [
        (True, None, None, Delete()),
        (True, "pre", "moved", Delete()),  # a branch this create minted is deleted, never reset
        (False, None, "moved", Noop()),
        (False, "pre", None, Noop()),  # unreadable tip: leave it
        (False, "pre", "", Noop()),
        (False, "pre", "pre", Noop()),  # did not move
        (False, "pre", "moved", CasReset(expected="moved", to="pre")),
    ],
)
def test_coord_rollback_action(created: bool, pre_seed_tip: str | None, current_tip: str | None, expected: object) -> None:
    assert coord_rollback_action(created=created, pre_seed_tip=pre_seed_tip, current_tip=current_tip) == expected


# ---------------------------------------------------------------------------
# Scaffold commit outcome and result file sets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (CommitFailureKind.BOOTSTRAP_REFUSAL, "skip"),
        (CommitFailureKind.STAGED_TREE_UNCHANGED, "already_exists"),
        (CommitFailureKind.OTHER, "raise"),
    ],
)
def test_classify_scaffold_commit_failure(kind: CommitFailureKind, expected: str) -> None:
    assert classify_scaffold_commit_failure(kind) == expected


_SPEC = Path("m/spec.md")
_META = Path("m/meta.json")
_README = Path("m/tasks/README.md")
_GITKEEP = Path("m/tasks/.gitkeep")
_LOCAL_LOG = Path("m/status.events.jsonl")
_COORD_LOG = Path("coord/m/status.events.jsonl")


@pytest.mark.parametrize(
    ("routed", "skipped", "log", "created", "uncommitted"),
    [
        (False, False, _LOCAL_LOG, [_SPEC, _META, _README], [_SPEC]),
        (True, False, _COORD_LOG, [_SPEC, _META, _README, _COORD_LOG], [_SPEC]),
        (False, True, _LOCAL_LOG, [_SPEC, _META, _README, _GITKEEP, _LOCAL_LOG], [_SPEC, _META, _README, _GITKEEP, _LOCAL_LOG]),
        (True, True, _COORD_LOG, [_SPEC, _META, _README, _COORD_LOG, _GITKEEP], [_SPEC, _META, _README, _GITKEEP]),
    ],
)
def test_created_file_sets(routed: bool, skipped: bool, log: Path, created: list[Path], uncommitted: list[Path]) -> None:
    result = created_file_sets(
        spec_file=_SPEC,
        meta_file=_META,
        tasks_readme=_README,
        tasks_gitkeep=_GITKEEP,
        log_path=log,
        coordination_routed=routed,
        scaffold_commit_skipped=skipped,
    )
    assert result == (created, uncommitted)
