"""Non-vacuity self-tests for the shared owned-checkout fixtures (WP02 T011).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, work package WP02.
These tests are the fixtures' proof of usefulness: every claimed detection or
exclusion is exercised directly, so a later WP that relies on these fixtures
can trust them without re-deriving the guarantee.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specify_cli.context.mission_resolver import resolve_mission
from specify_cli.coordination.surface_resolver import WorktreeTopology, classify_worktree_topology

if TYPE_CHECKING:
    from tests._owned_fixtures import RSnapshotter
    from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def test_p_shares_common_dir_with_r_and_is_on_target_branch(owned_checkouts) -> None:
    from kernel.git_topology import git_common_dir

    assert git_common_dir(owned_checkouts.owned_root) == git_common_dir(owned_checkouts.repository_root)
    assert _git(owned_checkouts.owned_root, "branch", "--show-current") == owned_checkouts.target_branch


def test_meta_topology_matches_request(make_owned_checkouts) -> None:
    checkouts = make_owned_checkouts(topology="lanes")
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(checkouts.mission_dir)
    assert meta is not None
    assert meta["topology"] == "lanes"


def test_under_worktrees_placement_classifies_as_lane_worktree(make_owned_checkouts) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")
    topology = classify_worktree_topology(checkouts.owned_root, repo_root=checkouts.repository_root)
    assert topology is WorktreeTopology.LANE_WORKTREE


def test_each_handle_kind_resolves(owned_checkouts, owned_handle) -> None:
    resolved = resolve_mission(owned_handle, owned_checkouts.owned_root)
    assert resolved.mission_id == owned_checkouts.mission_id
    assert resolved.mission_slug == owned_checkouts.mission_slug


def test_r_snapshot_detects_new_untracked_file(owned_checkouts, r_snapshot) -> None:
    before = r_snapshot.take()
    (owned_checkouts.repository_root / "untracked.txt").write_text("x\n", encoding="utf-8")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


def test_r_snapshot_detects_new_ignored_file(owned_checkouts, r_snapshot) -> None:
    derived = owned_checkouts.repository_root / ".kittify" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    before = r_snapshot.take()
    (derived / "x").write_text("x\n", encoding="utf-8")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


def test_r_snapshot_detects_head_move(owned_checkouts, r_snapshot) -> None:
    """Isolate the HEAD component: an empty commit changes ONLY HEAD.

    ``git commit --allow-empty`` moves HEAD without changing the working
    tree, the index or any file content, so this fails if the ``head``
    component were dropped from the snapshot (the original version of this
    test also changed a file and the index, so it stayed green even without
    the ``head`` comparison -- review cycle 1 nit).
    """
    r_root = owned_checkouts.repository_root
    before = r_snapshot.take()
    _git(r_root, "commit", "--allow-empty", "-qm", "move head only")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


def test_r_snapshot_detects_git_add(owned_checkouts, r_snapshot) -> None:
    r_root = owned_checkouts.repository_root
    (r_root / "staged.txt").write_text("x\n", encoding="utf-8")
    before = r_snapshot.take()
    _git(r_root, "add", "staged.txt")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


def test_r_snapshot_detects_lock_file(owned_checkouts, r_snapshot) -> None:
    from kernel.git_topology import git_common_dir
    from specify_cli.core.checkout_file_lock import LOCK_DIRECTORY

    lock_dir = git_common_dir(owned_checkouts.repository_root) / LOCK_DIRECTORY
    lock_dir.mkdir(parents=True, exist_ok=True)
    before = r_snapshot.take()
    (lock_dir / "x.lock").write_text("x\n", encoding="utf-8")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


# ---------------------------------------------------------------------------
# WP06 review-cycle-1 fix: the named, canonical status-mutex tolerance
# (NFR-001 wording tension, orchestrator-ruled amendment). Lives here, next
# to RSnapshotter's other self-tests, as the mutation proof for
# ``assert_unchanged(..., tolerate_status_mutex_for=...)``.
# ---------------------------------------------------------------------------


def test_assert_unchanged_tolerates_the_named_empty_status_mutex(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    """Accept case: exactly one ADDED, EMPTY lock key named by the canonical
    composer is tolerated when ``tolerate_status_mutex_for`` names it."""
    from specify_cli.status.locking import feature_status_lock_path

    lock_path = feature_status_lock_path(owned_checkouts.repository_root, owned_checkouts.mission_slug)
    before = r_snapshot.take()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"")
    after = r_snapshot.take()
    r_snapshot.assert_unchanged(before, after, tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_assert_unchanged_rejects_a_second_lock_key(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    """Reject case: an EXTRA lock key beyond the tolerated one still fails."""
    from specify_cli.status.locking import feature_status_lock_path

    lock_path = feature_status_lock_path(owned_checkouts.repository_root, owned_checkouts.mission_slug)
    before = r_snapshot.take()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"")
    (lock_path.parent / "extra.status.lock").write_bytes(b"")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after, tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_assert_unchanged_rejects_a_non_empty_status_mutex(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    """Reject case: a NON-EMPTY lock (a holder sidecar / real content) still fails."""
    from specify_cli.status.locking import feature_status_lock_path

    lock_path = feature_status_lock_path(owned_checkouts.repository_root, owned_checkouts.mission_slug)
    before = r_snapshot.take()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"holder-pid-1234")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after, tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_assert_unchanged_rejects_a_removed_lock_key(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    """Reject case: a pre-existing lock key disappearing still fails, even
    alongside the tolerated key being added."""
    from specify_cli.status.locking import feature_status_lock_path

    lock_path = feature_status_lock_path(owned_checkouts.repository_root, owned_checkouts.mission_slug)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    pre_existing = lock_path.parent / "pre-existing.status.lock"
    pre_existing.write_bytes(b"")
    before = r_snapshot.take()
    pre_existing.unlink()
    lock_path.write_bytes(b"")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after, tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_r_snapshot_detects_home_change(owned_checkouts, r_snapshot) -> None:
    home = Path(os.environ["SPEC_KITTY_HOME"])
    before = r_snapshot.take()
    (home / "marker.txt").write_text("x\n", encoding="utf-8")
    after = r_snapshot.take()
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, after)


def test_assert_unchanged_tolerates_only_the_p_keyed_prompt_cache(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    from tests._owned_fixtures import prompt_cache_prefix

    home = Path(os.environ["SPEC_KITTY_HOME"])
    before = r_snapshot.take()
    prompt = home / prompt_cache_prefix(owned_checkouts.owned_root) / "next-prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("prompt\n", encoding="utf-8")
    r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_assert_unchanged_rejects_a_write_elsewhere_under_the_home(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    from tests._owned_fixtures import prompt_cache_prefix

    home = Path(os.environ["SPEC_KITTY_HOME"])
    before = r_snapshot.take()
    (home / prompt_cache_prefix(owned_checkouts.owned_root)).mkdir(parents=True)  # the tolerated subtree exists ...
    (home / "spec-kitty-prompts" / "elsewhere.md").parent.mkdir(parents=True, exist_ok=True)
    (home / "spec-kitty-prompts" / "elsewhere.md").write_text("x\n", encoding="utf-8")  # ... a sibling write is not tolerated
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_assert_unchanged_rejects_a_prompt_dir_keyed_to_another_checkout(owned_checkouts: OwnedCheckouts, r_snapshot: RSnapshotter) -> None:
    from tests._owned_fixtures import prompt_cache_prefix

    home = Path(os.environ["SPEC_KITTY_HOME"])
    before = r_snapshot.take()
    other = home / prompt_cache_prefix(owned_checkouts.repository_root) / "next-prompt.md"  # keyed to R, not P
    other.parent.mkdir(parents=True)
    other.write_text("prompt\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_r_snapshot_detects_another_worktree_change(make_owned_checkouts, make_r_snapshot) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")
    snapshotter = make_r_snapshot(checkouts)
    before = snapshotter.take()
    lane_dir = checkouts.repository_root / ".worktrees" / "some-other-lane"
    _git(checkouts.repository_root, "worktree", "add", "-qb", "codex/other-lane", str(lane_dir))
    after = snapshotter.take()
    with pytest.raises(AssertionError):
        snapshotter.assert_unchanged(before, after)


def test_r_snapshot_ignores_change_inside_p_under_worktrees(make_owned_checkouts, make_r_snapshot) -> None:
    checkouts = make_owned_checkouts(placement="under_worktrees")
    snapshotter = make_r_snapshot(checkouts)
    before = snapshotter.take()
    (checkouts.owned_root / "new-in-p.txt").write_text("x\n", encoding="utf-8")
    after = snapshotter.take()
    snapshotter.assert_unchanged(before, after)


def test_stale_root_copy_lists_five_wps_p_lists_two(owned_checkouts, stale_root_copy) -> None:
    copied = stale_root_copy()
    from specify_cli.core.paths import load_meta_fail_closed

    r_meta = load_meta_fail_closed(copied)
    p_meta = load_meta_fail_closed(owned_checkouts.mission_dir)
    assert r_meta is not None and p_meta is not None
    assert r_meta["mission_id"] == p_meta["mission_id"] == owned_checkouts.mission_id
    r_tasks = sorted(p.name for p in (copied / "tasks").glob("WP*"))
    p_tasks = sorted(p.name for p in (owned_checkouts.mission_dir / "tasks").glob("WP*"))
    assert len(r_tasks) == 5
    assert len(p_tasks) == 2


def test_stale_root_copy_default_has_lanes_json(owned_checkouts, stale_root_copy) -> None:
    copied = stale_root_copy()
    assert (copied / "lanes.json").exists()


def test_stale_root_copy_with_lanes_false_has_no_lanes_json(owned_checkouts, stale_root_copy) -> None:
    copied = stale_root_copy(with_lanes=False)
    assert not (copied / "lanes.json").exists()


def test_stale_root_copy_lane_map_differs_from_p(owned_checkouts, stale_root_copy) -> None:
    """R's stale copy carries a DIFFERENT lane composition than P's own manifest.

    Proves the fixture's claim (spec §Test Layout: "a lane map that differs
    from P's") rather than merely asserting R's file exists: P has a single
    lane covering its (default) WP01-WP02; R's copy has two lanes covering
    WP01-WP05. A base-tree reader that folds to R must see R's own lanes,
    never silently read P's instead.
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.persistence import read_lanes_json

    copied = stale_root_copy()
    p_manifest = read_lanes_json(owned_checkouts.mission_dir)
    r_manifest = read_lanes_json(copied)
    assert p_manifest is not None and r_manifest is not None
    p_lane_map = {lane.lane_id: lane.wp_ids for lane in p_manifest.lanes}
    r_lane_map = {lane.lane_id: lane.wp_ids for lane in r_manifest.lanes}
    assert p_lane_map != r_lane_map
    # #5100 Invariant T-1: P's single_branch manifest is the ONE repo-root lane.
    assert p_lane_map == {PLANNING_LANE_ID: ("WP01", "WP02")}
    assert r_lane_map == {"lane-a": ("WP01", "WP02", "WP03"), "lane-b": ("WP04", "WP05")}


def test_stale_root_copy_different_id_variant_diverges_from_p(owned_checkouts, stale_root_copy) -> None:
    """US7-AS5: a ``different_id=True`` copy carries a DIFFERENT ``mission_id`` than P's.

    Pairs with ``test_stale_root_copy_lists_five_wps_p_lists_two`` (the
    default, same-id case) so both halves of the US1-AS1/US7-AS5 contrast are
    pinned in this module.
    """
    from specify_cli.core.paths import load_meta_fail_closed

    copied = stale_root_copy(different_id=True)
    r_meta = load_meta_fail_closed(copied)
    p_meta = load_meta_fail_closed(owned_checkouts.mission_dir)
    assert r_meta is not None and p_meta is not None
    assert r_meta["mission_id"] != p_meta["mission_id"]
    assert r_meta["mission_id"] == "01M2D900000000000000000099"


def test_wp_ids_controls_task_file_count(make_owned_checkouts) -> None:
    """``wp_ids`` drives exactly the requested set of WP task files, in P."""
    checkouts = make_owned_checkouts(wp_ids=("WP01", "WP02", "WP03"))
    task_names = sorted(p.stem.split("-owned")[0] for p in (checkouts.mission_dir / "tasks").glob("WP*"))
    assert task_names == ["WP01", "WP02", "WP03"]


def test_protected_target_protects_the_branch(make_owned_checkouts) -> None:
    """``protected_target=True`` makes R's config actually protect the target branch."""
    from specify_cli.git.protection_policy import ProtectionPolicy

    checkouts = make_owned_checkouts(protected_target=True)
    assert ProtectionPolicy.resolve(checkouts.repository_root).is_protected(checkouts.target_branch)


def test_protected_target_false_by_default_leaves_branch_unprotected(make_owned_checkouts) -> None:
    from specify_cli.git.protection_policy import ProtectionPolicy

    checkouts = make_owned_checkouts()
    assert not ProtectionPolicy.resolve(checkouts.repository_root).is_protected(checkouts.target_branch)


def test_owned_cwd_chdirs_to_the_requested_root(owned_checkouts, owned_cwd) -> None:
    """The NFR-001 cwd matrix: each ``owned_cwd`` param lands the process there."""
    assert Path.cwd().resolve() == owned_cwd.resolve()
    assert owned_cwd.resolve() in {
        owned_checkouts.repository_root.resolve(),
        owned_checkouts.owned_root.resolve(),
        owned_checkouts.sibling.resolve(),
    }
