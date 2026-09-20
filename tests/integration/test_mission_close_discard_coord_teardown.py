"""Regression: ``mission close --discard`` must tear down a coordination mission.

Reproduces a silent no-op: on a coordination-topology mission whose coordination
worktree is present, ``spec-kitty mission close --discard`` prints
``✓ Mission <slug> discarded`` but leaves the coordination worktree AND branch in
place.

Root cause exercised by this fixture (the split-brain surface layout):

* planning/identity artifacts (``meta.json`` / ``lanes.json``) live on the
  PRIMARY branch's mission dir;
* the coordination branch's mission dir is status-only (``status.events.jsonl`` /
  ``status.json``) — the coordination worktree is a full checkout of that branch;
* ``close_cmd`` resolves ``feature_dir`` via ``resolve_feature_dir_for_mission``
  (the ``tasks``-action context), which returns the coordination worktree's
  status-only dir → ``meta.json`` is absent → ``_read_mission_mid8`` returns
  ``""`` → ``_teardown_coordination_worktree`` early-returns → nothing is torn
  down, yet the command reports success.

This test asserts the CORRECT post-condition (worktree + branch gone). It FAILS
on the current code (the bug); the fix flips it green.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import mission_type
from specify_cli.coordination import CoordinationWorkspace
from tests._support.eacces import mode_bits_enforced

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

MISSION_ID = "01J6XW9K000000000000000000"
MID8 = MISSION_ID[:8]
# Mission dir / slug follows the real `<base>-<mid8>` identity convention so the
# coord-surface resolver composes the same mission-dir name on both branches.
SLUG = f"demo-coord-mission-{MID8}"
# Branch + worktree names come from the canonical helpers the runtime uses, so
# the fixture matches exactly what ``CoordinationWorkspace.resolve`` expects.
COORD_BRANCH = CoordinationWorkspace.branch_name(SLUG, MID8)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


@pytest.fixture
def coord_mission(tmp_path: Path) -> Path:
    """A coordination mission in the split-brain surface layout.

    Primary branch carries meta.json + lanes.json; the coordination branch's
    mission dir is status-only; a real coordination worktree is materialised.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    (fdir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "mission_branch": COORD_BRANCH,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    (fdir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": SLUG,
                "mission_id": MISSION_ID,
                "mission_branch": COORD_BRANCH,
                "target_branch": "main",
                "computed_at": "2026-01-01T00:00:00+00:00",
                "computed_from": "test",
                "lanes": [
                    {"lane_id": "lane-a", "wp_ids": ["WP01"], "write_scope": [],
                     "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    (fdir / "status.events.jsonl").write_text("", encoding="utf-8")
    (fdir / "status.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed primary mission surface")

    # Coordination branch: status-only mission dir (drop planning artifacts).
    _git(repo, "branch", COORD_BRANCH)
    _git(repo, "checkout", "-q", COORD_BRANCH)
    _git(repo, "rm", "-q", f"kitty-specs/{SLUG}/meta.json", f"kitty-specs/{SLUG}/lanes.json")
    _git(repo, "commit", "-q", "-m", "coord: status-only mission surface")
    _git(repo, "checkout", "-q", "main")

    # Materialise the real coordination worktree (full checkout of coord branch).
    CoordinationWorkspace.resolve(repo, SLUG, MID8)
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)
    return repo


def test_close_discard_tears_down_coordination_worktree_and_branch(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = coord_mission
    monkeypatch.chdir(repo)

    result = runner.invoke(
        mission_type.app,
        ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert result.exit_code == 0, result.output

    # The command must actually tear down what it claims to.
    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8), (
        "coordination worktree still present after `close --discard` "
        f"(command output: {result.output!r})"
    )
    branches = _git(repo, "branch", "--list", COORD_BRANCH).stdout.strip()
    assert branches == "", f"coordination branch leaked after `close --discard`: {branches!r}"


def test_close_discard_is_idempotent_on_rerun(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second `close --discard` after a successful one is a clean success —
    the residual verifier must not false-fail when there is nothing left."""
    repo = coord_mission
    monkeypatch.chdir(repo)

    first = runner.invoke(
        mission_type.app, ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert first.exit_code == 0, first.output

    second = runner.invoke(
        mission_type.app, ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert second.exit_code == 0, second.output


def test_close_discard_flattens_coordination_branch_from_meta(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a discard deletes the coord branch, meta.json must no longer declare
    `coordination_branch` — otherwise subsequent commands trip
    CoordinationBranchDeleted (the dangling-reference data-loss guard)."""
    repo = coord_mission
    monkeypatch.chdir(repo)
    meta_path = repo / "kitty-specs" / SLUG / "meta.json"
    assert "coordination_branch" in json.loads(meta_path.read_text())

    result = runner.invoke(
        mission_type.app, ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert result.exit_code == 0, result.output
    assert "coordination_branch" not in json.loads(meta_path.read_text())


def test_close_without_discard_tears_down_coord_worktree(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The non-discard `close` (re-anchored too) must tear down the coordination
    worktree on a coord mission — pre-fix it silently no-op'd as well — while
    leaving the branches intact (no --discard).

    terminus-safety-invariant WP06 (#4765, FR-004/FR-005) amendment: a
    non-discard close now fail-closes on `is_mission_merged` BEFORE teardown
    — an unmerged mission (this fixture's default) refuses instead of
    fabricating completion. This test's own intent has always been to prove
    the *teardown routing* for a coord mission on the non-discard path (the
    `--mission` re-anchor above), not to assert merge-status-agnostic
    behaviour, so the fixture is stamped merged here to keep exercising that
    routing under the new precondition. The unmerged-refusal case itself is
    covered by `tests/integration/test_issue_4765_close_guard.py`.
    """
    repo = coord_mission
    meta_path = repo / "kitty-specs" / SLUG / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["merged_at"] = "2026-09-20T08:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mark mission merged for teardown-routing test")
    monkeypatch.chdir(repo)

    result = runner.invoke(
        mission_type.app, ["close", "--mission", SLUG], env={"PWD": str(repo)}
    )
    assert result.exit_code == 0, result.output
    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8)
    # Non-discard leaves branches in place.
    assert _git(repo, "branch", "--list", COORD_BRANCH).stdout.strip() != ""


def test_close_discard_fails_closed_on_corrupt_lanes_json(
    coord_mission: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt lanes.json must abort the discard (non-zero, no teardown) rather
    than silently degrade a modern mission to the legacy single-branch path and
    leave its lane branches/worktrees behind."""
    repo = coord_mission
    (repo / "kitty-specs" / SLUG / "lanes.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(
        mission_type.app, ["close", "--mission", SLUG, "--discard", "--force"],
        env={"PWD": str(repo)},
    )
    assert result.exit_code != 0
    assert "corrupt" in result.output.lower()
    # Aborted before teardown — coord worktree untouched.
    assert CoordinationWorkspace.is_present(repo, SLUG, MID8)


def test_verify_discard_complete_flags_leaks(tmp_path: Path) -> None:
    """The residual verifier raises (non-zero) when an expected branch survives,
    and is silent when everything is gone."""
    from specify_cli.cli.commands.mission_type import _verify_discard_complete

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    meta_path = fdir / "meta.json"
    meta_path.write_text(
        json.dumps({"mission_slug": SLUG, "coordination_branch": COORD_BRANCH}),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")

    # No leftover branch/worktree → clean (no raise).
    _verify_discard_complete(repo, SLUG, MID8, fdir, meta_path)

    # A surviving coordination branch is a leak → typer.Exit (non-zero).
    import typer

    _git(repo, "branch", COORD_BRANCH)
    with pytest.raises(typer.Exit):
        _verify_discard_complete(repo, SLUG, MID8, fdir, meta_path)


def _single_lane_manifest(slug: str):
    from specify_cli.lanes.models import ExecutionLane, LanesManifest

    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=slug,
        mission_branch=f"kitty/mission-{slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a", wp_ids=("WP01",), write_scope=(),
                predicted_surfaces=(), depends_on_lanes=(), parallel_group=0,
            )
        ],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def test_expected_lane_worktree_dir_names_are_exact() -> None:
    """The expected-name set is exact (no `<slug>-*` prefix) and excludes the
    planning lane — so it can never match a sibling mission's worktree."""
    from specify_cli.cli.commands.mission_type import _expected_lane_worktree_dir_names
    from specify_cli.lanes.models import ExecutionLane

    manifest = _single_lane_manifest("alpha")
    manifest.lanes.append(
        ExecutionLane(
            lane_id="lane-planning", wp_ids=(), write_scope=(),
            predicted_surfaces=(), depends_on_lanes=(), parallel_group=0,
        )
    )
    assert _expected_lane_worktree_dir_names("alpha", manifest) == {"alpha-lane-a"}


def test_remove_lane_worktrees_does_not_delete_sibling_mission(tmp_path: Path) -> None:
    """Data-loss guard (#2120 follow-up): discarding mission `alpha` removes only
    its OWN lane worktree, never sibling `alpha-beta`'s worktree (whose dir name
    shares the `alpha-` prefix) — preserving the sibling's uncommitted work. The
    pre-fix `<slug>-*` prefix scan deleted it."""
    from specify_cli.cli.commands.mission_type import _remove_lane_worktrees

    repo = _init_repo(tmp_path)
    _git(repo, "worktree", "add", "--detach", str(repo / ".worktrees" / "alpha-lane-a"))
    sibling_wt = repo / ".worktrees" / "alpha-beta-lane-a"
    _git(repo, "worktree", "add", "--detach", str(sibling_wt))
    (sibling_wt / "uncommitted.txt").write_text("precious sibling work\n", encoding="utf-8")

    _remove_lane_worktrees(repo, "alpha", _single_lane_manifest("alpha"))

    assert not (repo / ".worktrees" / "alpha-lane-a").exists(), "target worktree must be removed"
    assert sibling_wt.exists(), "SIBLING worktree must be preserved (no prefix over-match)"
    assert (sibling_wt / "uncommitted.txt").read_text(encoding="utf-8") == "precious sibling work\n"


def test_remove_lane_worktrees_unstattable_entry_is_not_silently_skipped(
    tmp_path: Path,
) -> None:
    """`#3194`: the `entry.is_dir()` filter must not use the EACCES-divergent
    predicate.

    `Path.is_dir()` answers `False` for an unreadable candidate on Python 3.14
    only (RAISES on 3.11-3.13). Before this fix, an unstattable lane worktree
    entry would be silently treated as "not present" on 3.14 and `git worktree
    remove` would never be invoked on it — a stale/leaked worktree that discard
    reports as cleaned up with no signal at all, the same shape `#3177` fixed in
    `specify_cli.decisions.ownership`. `safe_is_dir` makes this raise on every
    interpreter instead of only on 3.11-3.13.
    """
    from specify_cli.cli.commands.mission_type import _remove_lane_worktrees

    repo = _init_repo(tmp_path)
    vault = tmp_path / "vault"
    (vault / "m-target").mkdir(parents=True)
    worktrees_root = repo / ".worktrees"
    worktrees_root.mkdir(parents=True, exist_ok=True)
    (worktrees_root / "alpha-lane-a").symlink_to(vault / "m-target", target_is_directory=True)

    canary = vault / "canary"
    canary.write_text("{}", encoding="utf-8")
    os.chmod(vault, 0o000)
    try:
        if not mode_bits_enforced(canary):
            pytest.skip(
                "SKIPPED HONESTLY, not passed: this process can stat through a "
                "0o000 directory (running as root, or a filesystem that ignores "
                "mode bits), so the branch cannot be constructed here."
            )
        with pytest.raises(OSError):
            _remove_lane_worktrees(repo, "alpha", _single_lane_manifest("alpha"))
    finally:
        os.chmod(vault, 0o700)


def test_verify_flags_stale_coordination_worktree_registration(tmp_path: Path) -> None:
    """A broken coord teardown (directory gone, git registration left behind) is
    still a leak: `is_present` (on-disk) returns False, so the verifier must also
    check the git worktree registry — else discard falsely reports success."""
    import shutil

    import typer

    from specify_cli.cli.commands.mission_type import _verify_discard_complete

    repo = _init_repo(tmp_path)
    fdir = repo / "kitty-specs" / SLUG
    fdir.mkdir(parents=True)
    # No coordination_branch / lanes.json → the ONLY possible leak is the
    # stale coord worktree registration.
    (fdir / "meta.json").write_text(json.dumps({"mission_slug": SLUG}), encoding="utf-8")

    coord_path = CoordinationWorkspace.worktree_path(repo, SLUG, MID8)
    _git(repo, "worktree", "add", "--detach", str(coord_path))
    shutil.rmtree(coord_path)  # broken teardown: dir removed, registration remains

    assert not CoordinationWorkspace.is_present(repo, SLUG, MID8)  # on-disk gone ...
    with pytest.raises(typer.Exit):  # ... but the stale registration is still a leak
        _verify_discard_complete(repo, SLUG, MID8, fdir, fdir / "meta.json")
