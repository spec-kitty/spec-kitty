"""#6753 — a fresh coord-topology lane must report a coordination branch that
has fallen behind the target branch.

The bug: `_resolve_lane_parent` parents a fresh lane on the coordination branch
for coord topology (by design, C-005/FR-006). When the target branch advances
after the coordination branch is minted, the lane is cut behind the target and
**nothing says so**; the gap surfaces only later as a prerequisite missing from
the lane's tree.

This module pins the report, not the parentage:

* FR-001 — a stale fresh cut prints exactly one ``WARNING:`` naming the base ref,
  the target branch, the target commit it lacks, and the ``--base`` remedy.
* FR-002 — the same probe is silent when the base already contains the target
  tip (the same-fixture positive control that makes FR-001 non-vacuous).
* FR-003 — the cut still parents on the coordination branch: the warning informs,
  it does not re-parent.
* NFR-002 — a probe that cannot answer (unresolvable target branch) is silent and
  never changes the allocation's outcome.

Every variant below is built by the ONE fixture builder :func:`_coord_repo` so the
"warns" and "silent" cases cannot silently drift apart.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from kernel.clock import now_utc_iso

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "demo-feature-01J6XW9K"
MISSION_ID = "01J6XW9KABCDEFGHJKMNPQRSTV"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LANE_BRANCH = f"{COORD_BRANCH}-lane-a"
TARGET_BRANCH = "main"
PREREQUISITE_FILE = "prerequisite.txt"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


@dataclass(frozen=True)
class CoordRepo:
    """A coord-topology fixture: repo path, the target tip, and the lane manifest."""

    repo: Path
    target_tip: str | None
    manifest: LanesManifest


def _make_manifest(*, target_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=COORD_BRANCH,
        target_branch=target_branch,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test",
    )


def _coord_repo(
    tmp_path: Path,
    *,
    advance_target: bool = True,
    coord_sees_target: bool = False,
    target_branch: str = TARGET_BRANCH,
) -> CoordRepo:
    """Build the ONE coord fixture every variant below is derived from.

    ``advance_target`` lands a commit on the target branch AFTER the coordination
    branch was minted (the issue's "reviewed prerequisite merge").
    ``coord_sees_target`` additionally merges that commit into the coordination
    branch — the positive control's "base is current" state.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", TARGET_BRANCH)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    spec_dir = repo / "kitty-specs" / MISSION_SLUG
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n")
    (spec_dir / "status.events.jsonl").write_text('{"actor":"test","wp_id":"WP01"}\n')
    (spec_dir / "status.json").write_text("{}\n")
    (spec_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mission_slug": MISSION_SLUG,
                "coordination_branch": COORD_BRANCH,
            }
        )
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", COORD_BRANCH)

    target_tip: str | None = None
    if advance_target:
        (repo / PREREQUISITE_FILE).write_text("prerequisite\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "prerequisite merge")
        target_tip = _git(repo, "rev-parse", TARGET_BRANCH)
        if coord_sees_target:
            _git(repo, "checkout", "-q", COORD_BRANCH)
            _git(repo, "merge", "-q", "--ff-only", TARGET_BRANCH)
            _git(repo, "checkout", "-q", TARGET_BRANCH)

    return CoordRepo(repo=repo, target_tip=target_tip, manifest=_make_manifest(target_branch=target_branch))


def _allocate(fixture: CoordRepo, **kwargs: object) -> tuple[Path, str]:
    worktree_path, branch = allocate_lane_worktree(
        repo_root=fixture.repo,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        lanes_manifest=fixture.manifest,
        **kwargs,  # type: ignore[arg-type]
    )
    return worktree_path, branch


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo,
            capture_output=True,
        ).returncode
        == 0
    )


# ---------------------------------------------------------------------------
# FR-001 / NFR-003 — the stale cut is reported, with everything a reader needs.
# ---------------------------------------------------------------------------


def test_stale_coord_base_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """RED before #6753: the lane was cut behind the target and nothing said so.

    The report goes to STDERR and stdout stays empty: ``spec-kitty implement
    --json`` keeps stdout for its machine-readable payload, so a diagnostic on the
    common stale-coord cut must not share that channel.
    """
    fixture = _coord_repo(tmp_path)
    assert fixture.target_tip is not None
    capsys.readouterr()  # discard fixture noise

    worktree_path, branch = _allocate(fixture)
    captured = capsys.readouterr()
    out = captured.err

    assert branch == LANE_BRANCH
    assert worktree_path.exists()
    assert captured.out == "", f"stdout must stay machine-readable, got: {captured.out!r}"
    # NFR-003: base ref, target branch, the missing target commit, and a
    # runnable remedy carrying the WP id — all four, in the report.
    assert "WARNING" in out, f"expected a stale-base warning, got: {out!r}"
    assert COORD_BRANCH in out, "the warning must name the ref the lane was cut from"
    assert TARGET_BRANCH in out, "the warning must name the target branch"
    assert fixture.target_tip[:8] in out, "the warning must name the target commit the base lacks"
    assert "agent action implement WP01" in out, "the warning must carry a runnable remedy"
    assert f"--base {TARGET_BRANCH}" in out, "the remedy must name the target branch as the base"
    assert "#6753" in out, "the warning must cite the defect"
    # Exactly one report per allocation — no duplicate emission from any helper.
    assert out.count("WARNING") == 1, f"expected exactly one warning, got: {out!r}"


def test_stale_lane_lacks_the_target_commit(tmp_path: Path) -> None:
    """The defect itself, pinned independently of the message (#6753 Actual Behavior)."""
    fixture = _coord_repo(tmp_path)
    assert fixture.target_tip is not None

    _, branch = _allocate(fixture)

    assert _is_ancestor(fixture.repo, fixture.target_tip, TARGET_BRANCH), "fixture invariant: the target branch holds the prerequisite commit"
    assert not _is_ancestor(fixture.repo, fixture.target_tip, branch), (
        "documented default: a fresh coord lane is cut from the coordination branch, which does not contain the target tip"
    )
    assert not _is_ancestor(fixture.repo, fixture.target_tip, COORD_BRANCH), "fixture invariant: the coordination branch is behind the target"


# ---------------------------------------------------------------------------
# FR-002 — positive control on the SAME fixture: a current base is silent.
# ---------------------------------------------------------------------------


def test_current_coord_base_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Same fixture, coordination branch holds the target tip: no warning."""
    fixture = _coord_repo(tmp_path, coord_sees_target=True)
    assert fixture.target_tip is not None
    capsys.readouterr()

    _, branch = _allocate(fixture)
    captured = capsys.readouterr()

    assert "WARNING" not in captured.out + captured.err, f"a current base must not warn, got: {captured!r}"
    assert _is_ancestor(fixture.repo, fixture.target_tip, branch), (
        "control invariant: with a current base the lane DOES contain the target tip, "
        "so the probe used by test_stale_coord_base_is_reported can observe both states"
    )


def test_unresolvable_target_branch_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """NFR-002: a probe that cannot answer must neither warn nor block."""
    fixture = _coord_repo(tmp_path, target_branch="no-such-target-branch")
    capsys.readouterr()

    worktree_path, branch = _allocate(fixture)
    captured = capsys.readouterr()

    assert "WARNING" not in captured.out + captured.err, f"an unresolvable target must stay silent, got: {captured!r}"
    assert worktree_path.exists() and branch == LANE_BRANCH, "an unresolvable target must not change the allocation's outcome"


def test_explicit_current_base_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An explicit ``--base`` that already contains the target tip reports nothing."""
    fixture = _coord_repo(tmp_path)
    assert fixture.target_tip is not None
    capsys.readouterr()

    _, branch = _allocate(fixture, base=TARGET_BRANCH)
    captured = capsys.readouterr()

    assert "WARNING" not in captured.out + captured.err, f"a current explicit base must not warn, got: {captured!r}"
    assert _is_ancestor(fixture.repo, fixture.target_tip, branch)


# ---------------------------------------------------------------------------
# FR-003 — the report never re-parents the lane.
# ---------------------------------------------------------------------------


def test_stale_report_keeps_the_coordination_parent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C-001/FR-003: the warning informs; the lane still descends from coord."""
    fixture = _coord_repo(tmp_path)
    capsys.readouterr()

    _, branch = _allocate(fixture)
    capsys.readouterr()

    assert _is_ancestor(fixture.repo, COORD_BRANCH, branch), "the fresh cut must still parent on the coordination branch (C-005/FR-006)"


def test_explicit_stale_base_names_the_ref_it_used(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An explicit ``base`` that is ALSO stale warns, naming that base.

    Independent-review follow-up: the spec's "explicit base that is also stale"
    edge case was unpinned. The message must describe the ref the lane was really
    cut from, not the coordination branch by name.
    """
    fixture = _coord_repo(tmp_path)
    # A branch off the pre-advance commit: stale, and not the coordination branch.
    _git(fixture.repo, "branch", "stale-explicit", f"{COORD_BRANCH}")
    capsys.readouterr()

    _, branch = _allocate(fixture, base="stale-explicit")
    captured = capsys.readouterr()

    assert "WARNING" in captured.err, f"expected a stale-base warning, got: {captured!r}"
    assert "'stale-explicit'" in captured.err, "the warning must name the base it actually used"
    assert captured.out == ""
    assert _is_ancestor(fixture.repo, "stale-explicit", branch), "the explicit base must still be the parent the lane was cut from"


# ---------------------------------------------------------------------------
# NFR-002 — every unanswerable probe arm is silent and never blocks.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    ["os_error", "timeout", "git_error"],
    ids=["git-unavailable", "git-wedged", "ambiguous-revision"],
)
def test_unanswerable_probe_is_silent_and_never_blocks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """The three non-``0``/``1`` probe outcomes degrade to "unknown".

    ``OSError`` (no git), ``TimeoutExpired`` (wedged git) and any other git exit
    (an ambiguous or unreadable revision) must each stay silent AND leave the
    allocation's outcome untouched -- an unanswerable probe never invents a
    warning and never blocks a lane.
    """
    fixture = _coord_repo(tmp_path)
    real_run = subprocess.run

    def _failing_probe(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(cmd, list) and "merge-base" in cmd and "--is-ancestor" in cmd:
            if failure == "os_error":
                raise OSError("git is not installed")
            if failure == "timeout":
                raise subprocess.TimeoutExpired(cmd="git merge-base", timeout=10)
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: ambiguous argument")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("specify_cli.lanes.worktree_allocator.subprocess.run", _failing_probe)
    capsys.readouterr()

    worktree_path, branch = _allocate(fixture)
    captured = capsys.readouterr()

    assert "WARNING" not in captured.out + captured.err, f"an unanswerable probe must stay silent, got: {captured!r}"
    assert worktree_path.exists() and branch == LANE_BRANCH, "an unanswerable probe must not change the allocation's outcome"
