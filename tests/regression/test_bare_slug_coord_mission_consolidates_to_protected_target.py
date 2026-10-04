"""A bare-slug coordination Mission must consolidate onto a protected target.

OPEN, red-first reproduction pinned to
https://github.com/spec-kitty/spec-kitty/issues/5651 (release-blocking per the
regression-suite entry rule; ADR 2026-07-17-1).

Contract
--------
``spec-kitty consolidate`` of a coordination-topology Mission whose primary
directory is the BARE slug (``kitty-specs/<slug>``, no ``-<mid8>`` suffix) while
its coordination branch is the composed ``kitty/mission-<slug>-<mid8>`` must
land on the protected target (``main``) and honor an explicit
``--delete-branch`` / ``--remove-worktree`` override over the Mission's
retention policy.

Root cause (traced in the nightly-reds-b research memo)
-------------------------------------------------------
The consolidate executor resolves its STATUS leg through ``write_dir``, which
seeds the composed ``<slug>-<mid8>`` coordination directory.
``coord_seed._commit_seed`` commits that seed through
``commit_for_mission(..., mission_slug=<bare slug>)``, but
``partition_for_mission_path`` classifies by the ``kitty-specs/<segment>`` name
and does not recognise ``<slug>-<mid8>``. The seed files therefore regroup to
PRIMARY, which is refused on a protected ``main``, and are left untracked in the
coordination worktree. The pre-mutation preflight then stops with
``MERGE_UNSAFE_WORKTREE_DIRTY``. Regression introduced by commit ``5b5699e50``;
it consolidates at ``5b5699e50^``.

Desired outcome
---------------
The merge exits 0: the seed lands on the coordination partition (not PRIMARY),
the reconciliation gate attributes it as bookkeeping rather than as content, and
the explicit delete override removes the mission branch, lane branch and lane
worktree. A partition-only fix is not enough, because the reconciliation gate's
``_is_bookkeeping`` is anchored on the same bare segment; where a bare-slug
Mission's coordination records land is a design decision, hence the issue.

Fixture shape
-------------
This is the realistic bare-slug shape that ``coordination/transaction.py::
_canonical_coord_mission_slug`` documents as genuine: primary directory
``retention-override``, coordination branch
``kitty/mission-retention-override-<mid8>``. (The test it was extracted from,
``tests/integration/test_merge_lane_planning_data_loss.py``, embedded the mid8
mid-slug with an uncomposed branch, which is off-grammar.)

Exit rule: once #5651 is fixed this test goes green and leaves this directory
(``tests/regression/README.md``), moving back next to its retention siblings in
``tests/integration/test_merge_lane_planning_data_loss.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.integration.test_merge_lane_planning_data_loss import (
    _RETENTION_MID8,
    _branch_exists,
    _commit_file,
    _git,
    _init_git_repo,
    _invoke_merge_cli,
    _real_merge_external_mocks,
    _seed_wp_approved,
    _write_coord_retaining_meta,
    _write_lanes_manifest,
    _write_wp_file,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BARE_SLUG = "retention-override"
_COMPOSED_BRANCH = f"kitty/mission-{_BARE_SLUG}-{_RETENTION_MID8}"


@pytest.mark.regression
def test_bare_slug_coord_mission_explicit_delete_override_consolidates(tmp_path: Path) -> None:
    """#5651: a bare-slug coordination Mission consolidates and honors ``--delete-branch``."""
    slug = _BARE_SLUG
    mission_branch = _COMPOSED_BRANCH
    _init_git_repo(tmp_path)

    feature_dir = tmp_path / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    _write_coord_retaining_meta(feature_dir, slug)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["coordination_branch"] = mission_branch
    meta["mission_branch"] = mission_branch
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_lanes_manifest(
        feature_dir,
        slug,
        code_wp_ids=["WP01"],
        planning_wp_ids=[],
        mission_branch=mission_branch,
    )
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, slug, "WP01")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", f"chore({slug}): bootstrap bare-slug coord mission")

    _git(tmp_path, "branch", mission_branch, "main")
    from specify_cli.coordination.workspace import CoordinationWorkspace

    _git(
        tmp_path,
        "worktree",
        "add",
        "-q",
        str(CoordinationWorkspace.worktree_path(tmp_path, slug, _RETENTION_MID8)),
        mission_branch,
    )
    lane_a_branch = f"kitty/mission-{slug}-lane-a"
    _git(tmp_path, "branch", lane_a_branch, "main")
    _commit_file(
        tmp_path,
        branch=lane_a_branch,
        relpath="src/retention_repro_override.py",
        content="def bar():\n    return 2\n",
        message=f"feat({slug}): add bar function (WP01)",
    )
    _git(tmp_path, "checkout", "main")

    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    lane_worktree, _lane_branch = predict_lane_worktree(tmp_path, slug, "lane-a")
    _git(tmp_path, "worktree", "add", str(lane_worktree), lane_a_branch)

    with (
        _real_merge_external_mocks(tmp_path),
        patch("specify_cli.consolidation.executor._assert_merged_wps_done_on_target"),
        patch("specify_cli.consolidation.executor._assert_baseline_merge_commit_on_target"),
    ):
        result = _invoke_merge_cli(
            tmp_path,
            ["--mission", slug, "--yes", "--allow-sparse-checkout", "--delete-branch", "--remove-worktree"],
        )

    exit_code = getattr(result, "exit_code", None)
    assert exit_code == 0, f"#5651: consolidate must succeed (output: {getattr(result, 'output', None)!r}, exception: {getattr(result, 'exception', None)!r})"
    assert not _branch_exists(tmp_path, mission_branch), "explicit --delete-branch must still delete the mission/coordination branch"
    assert not _branch_exists(tmp_path, lane_a_branch), "explicit --delete-branch must still delete the lane branch"
    assert not lane_worktree.exists(), "explicit --remove-worktree must still remove the lane worktree"
    output = getattr(result, "output", "") or ""
    assert "explicit delete overrode retention policy for branches" in output
    assert "explicit delete overrode retention policy for worktrees" in output
