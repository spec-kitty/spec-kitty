"""``spec-kitty accept --mode pr --merge-commit`` integration tests (issue #4231).

A mission accepted through a GitHub PR never passes through
``spec-kitty merge``, so its ``meta.json`` never carried
``baseline_merge_commit`` — leaving post-merge review unreachable and the
lightweight dead-code gate failing a cleanly merged mission. These tests pin
the accept-side repair:

* ``--merge-commit`` outside ``--mode pr`` is a clean usage error (exit 2).
* An unverifiable SHA is a clean error (exit 1) raised BEFORE any acceptance
  write — nothing is mutated on the refused paths.
* An unmerged Specify-only branch commit is refused: first introduction is
  not landing, so only the target-branch membership check separates it from
  a real PR merge (#4231 monitor finding).
* A verified merge commit is recorded into the mission's ``meta.json``
  (``baseline_merge_commit`` = the merge commit's first parent,
  ``pr_merge_commit`` = the landing commit) and the tree stays clean.

The fixture builds the real elements-first shape: a mission branch merged
into ``main`` by a PR-shaped ``--no-ff`` merge commit whose first parent
predates the mission corpus, with accept running on the mission branch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from kernel.clock import now_utc_iso
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.status.reducer import materialize
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import commit_lane_implementation

# Real git + the real accept pipeline: mutmut's forked sandbox cannot host it.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "321-pr-accepted-mission-01TEST"
_MISSION_ID = "01TESTPRACCEPTMUTATION00000"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _lane_branch(lane_id: str = "lane-a") -> str:
    """The branch `finalize-tasks` would have the lane allocator create for *lane_id*."""
    return lane_branch_name(_SLUG, lane_id, target_branch="main")


def _branch_resolves(repo_root: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _write_wp_file(tasks_dir: Path, wp_id: str, owned_glob: str) -> None:
    """Write one work-package file whose authored ownership is *owned_glob*."""
    (tasks_dir / f"{wp_id}-test.md").write_text(
        "---"
        f'\nwork_package_id: "{wp_id}"'
        '\ntitle: "Test WP"'
        '\nlane: "done"'
        '\nassignee: "test-agent"'
        '\nagent: "test-agent"'
        '\nshell_pid: "12345"'
        f"\nowned_files:\n  - {owned_glob}"
        "\nsubtasks: []"
        "\n---"
        f"\n# {wp_id}\nDone.\n"
    )


def _seed_done_lifecycle(feature_dir: Path, wp_id: str, *, claim_id: str, review_id: str, done_id: str) -> None:
    """Seed the claimed -> approved(independent reviewer) -> done legs of *wp_id*."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=claim_id,
            mission_slug=_SLUG,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="direct_repo",
            policy_metadata=build_claim_policy_metadata(
                shell_pid=12345,
                shell_pid_created_at="2026-01-01T00:00:00+00:00",
                agent="test-agent",
            ),
        ),
    )
    # #6715: an independent reviewer approved the WP (accept refuses an approval by the implementer).
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=review_id,
            mission_slug=_SLUG,
            wp_id=wp_id,
            from_lane=Lane.CLAIMED,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:01+00:00",
            actor="test-reviewer",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: reviewed",
        ),
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=done_id,
            mission_slug=_SLUG,
            wp_id=wp_id,
            from_lane=Lane.APPROVED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )


def _create_pr_merged_feature(
    repo_root: Path,
    *,
    merged: bool = True,
    squash: bool = False,
    lane_merged: bool = False,
    prune_lane: bool = False,
    hollow_wp: bool = False,
    dependency_lane: bool = False,
    mission_side_path: str | None = None,
) -> tuple[Path, str, str]:
    """Create an accept-ready mission whose PR already merged into main.

    Returns ``(feature_dir, merge_commit, pre_merge_parent)``. The base
    commit on main predates ``kitty-specs/`` entirely; the mission branch
    carries the corpus; a ``--no-ff`` merge lands it on main (the PR-shaped
    merge commit); accept then runs on the mission branch, as it does in the
    elements-first programme. With ``squash=True`` the landing is a
    single-parent squash commit instead — the shape that needs the
    operator's ``--attest-first-landing-commit`` attestation.

    With ``merged=False`` the branch is NEVER merged and the returned
    "merge commit" is the single corpus commit on the unmerged branch — the
    #4231 monitor repro shape: it introduces the corpus (parent lacks it) but
    never landed on the target branch.

    #6780 shapes: ``lane_merged=True`` merges the implemented lane branch into
    the mission branch before the landing (what `spec-kitty consolidate` or a
    hand-merge of the lanes does), so the work package's deliverable is on the
    target. ``prune_lane=True`` deletes the lane branch after the landing (the
    normal post-merge cleanup) — the state in which the evidenced window's tip
    no longer resolves. ``hollow_wp=True`` adds an approved-but-never-
    implemented WP02 (owning ``tools/**``) in lane-a, so a test can prove the #6715 gate still
    refuses a hollow work package. ``dependency_lane=True`` adds an implemented WP03 in
    ``lane-b`` and makes ``lane-a`` depend on it, so the dependency widening has to use the same
    stand-in tip when lane-a's branch is pruned and lane-b's still resolves. ``mission_side_path``
    commits an unrelated path on the mission branch AFTER the lane branch was cut, so it sits in
    ``planning_commit..<landing commit>`` but not in ``planning_commit..<lane branch>`` — the shape
    that separates the two windows.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")
    # #6715: the planning commit lanes.json records (accept refuses a work package whose evidence
    # window, planning commit..lane branch, is uncomputable or holds no owned change).
    _git(repo_root, "commit", "--allow-empty", "-m", "planning base")
    planning_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    # .kittify marker anchors find_repo_root() to this repo (paired with the
    # SPECIFY_REPO_ROOT env var set by the test).
    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    # Base commit on main WITHOUT the mission corpus.
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base")

    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "321",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "PR Accepted Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    _write_wp_file(tasks_dir, "WP01", "src/**")
    if hollow_wp:
        # Owned files nothing in this fixture ever creates or changes, so the hollow arm
        # cannot pass by way of the base commit's own scaffolding.
        _write_wp_file(tasks_dir, "WP02", "tools/**")
    if dependency_lane:
        # An implemented WP in the lane that lane-a depends on: its branch must still exist
        # after lane-a's is pruned, which is the state that exercises the dependency widening.
        _write_wp_file(tasks_dir, "WP03", "vendor/**")

    # Event-sourced done state (the same planned -> claimed -> done legs the
    # clean-tree regression fixture seeds).
    _seed_done_lifecycle(
        feature_dir,
        "WP01",
        claim_id="01TESTPRACCEPTMUTATION0001",
        review_id="01TESTPRACCEPTMUTATION000R",
        done_id="01TESTPRACCEPTMUTATION0002",
    )
    if hollow_wp:
        # Approved by an independent reviewer, but never implemented: its lane has no
        # commit touching docs/**, so the #6715 axis must keep refusing it.
        _seed_done_lifecycle(
            feature_dir,
            "WP02",
            claim_id="01TESTPRACCEPTMUTATION0003",
            review_id="01TESTPRACCEPTMUTATION000S",
            done_id="01TESTPRACCEPTMUTATION0004",
        )
    if dependency_lane:
        _seed_done_lifecycle(
            feature_dir,
            "WP03",
            claim_id="01TESTPRACCEPTMUTATION0005",
            review_id="01TESTPRACCEPTMUTATION000T",
            done_id="01TESTPRACCEPTMUTATION0006",
        )
    materialize(feature_dir)

    lane_a_wps = ("WP01", *(("WP02",) if hollow_wp else ()))
    lane_a_scope = ("src/**", *(("tools/**",) if hollow_wp else ()))
    lanes = [
        ExecutionLane(
            lane_id="lane-a",
            wp_ids=lane_a_wps,
            write_scope=lane_a_scope,
            predicted_surfaces=("test",),
            depends_on_lanes=("lane-b",) if dependency_lane else (),
            parallel_group=0,
        )
    ]
    if dependency_lane:
        lanes.append(
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=("WP03",),
                write_scope=("vendor/**",),
                predicted_surfaces=("api",),
                depends_on_lanes=(),
                parallel_group=1,
            )
        )
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_SLUG,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=lanes,
        computed_at="2026-04-05T12:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit,
    )
    write_lanes_json(feature_dir, manifest)

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "mission corpus")
    commit_lane_implementation(repo_root, feature_dir, path="src/wp01.py")  # #6715: WP01's implementation
    if dependency_lane:
        commit_lane_implementation(repo_root, feature_dir, lane_id="lane-b", path="vendor/wp03.py")
    lane_branch = _lane_branch("lane-a")
    if lane_merged:
        # The lanes' reviewed content lands on the mission branch, as a lane merge does.
        if dependency_lane:
            _git(repo_root, "merge", "--no-ff", "-m", f"Merge {_lane_branch('lane-b')} into the mission", _lane_branch("lane-b"))
        _git(repo_root, "merge", "--no-ff", "-m", f"Merge {lane_branch} into the mission", lane_branch)
    if mission_side_path:
        # Target-side work committed after the lane branch was cut: inside
        # planning_commit..<landing commit>, outside planning_commit..<lane branch>.
        side_path = repo_root / mission_side_path
        side_path.parent.mkdir(parents=True, exist_ok=True)
        side_path.write_text("# unrelated target-side work\n")
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-m", f"unrelated work touching {mission_side_path}")

    # The PR-shaped landing on main: first parent predates the corpus.
    _git(repo_root, "checkout", "main")
    if merged and squash:
        _git(repo_root, "merge", "--squash", "-q", _MISSION_BRANCH)
        _git(repo_root, "commit", "-m", f"Squash PR: land {_SLUG}")
        merge_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()
    elif merged:
        _git(
            repo_root,
            "merge",
            "--no-ff",
            "-m",
            f"Merge PR: land {_SLUG}",
            _MISSION_BRANCH,
        )
        merge_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()
    else:
        # The unmerged branch's single corpus commit; its parent is the base.
        merge_commit = _git(repo_root, "rev-parse", _MISSION_BRANCH).stdout.strip()
        pre_merge_parent = _git(repo_root, "rev-parse", f"{_MISSION_BRANCH}^1").stdout.strip()

    # Accept runs on the mission branch (the elements-first operator flow).
    _git(repo_root, "checkout", _MISSION_BRANCH)
    if prune_lane:
        # Post-merge cleanup: the lane branch is gone, its work is on the target.
        _git(repo_root, "branch", "-D", lane_branch)
    return feature_dir, merge_commit, pre_merge_parent


def _porcelain(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_accept_pr_mode_records_verified_merge_as_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``accept --mode pr --merge-commit <sha> --attest-first-landing-commit`` records real merge evidence.

    A two-parent merge landing is recordable only under the operator's
    attestation (two parents alone do not prove the first parent is the
    pre-landing target tip — the internal-merge landing is graph-identical),
    and the persisted evidence class names the attestation.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, pre_merge_parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # Unattested: a clean pre-write exit-1 refusal, nothing recorded.
    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
        )
    assert exit_info.value.exit_code == 1
    assert "baseline_merge_commit" not in (feature_dir / "meta.json").read_text(encoding="utf-8")

    # Successful (non-json) attested accept returns normally; no Exit is raised.
    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=merge_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_merge_parent, (
        f"baseline must be the merge commit's first parent (the pre-landing target tip), not the merge commit itself: {meta}"
    )
    assert meta["pr_merge_commit"] == merge_commit
    assert meta["pr_merge_evidence"] == "merge-commit-parent-attested"
    assert meta["acceptance_mode"] == "pr"

    # The recording is swept into the residual finalize commit: clean tree.
    assert _porcelain(repo_root) == "", "accept left a dirty working tree"


def test_accept_merge_commit_outside_pr_mode_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--merge-commit`` with a non-pr mode is a clean exit-2 usage error."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="local",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
        )

    assert exc_info.value.exit_code == 2
    # Refused before any acceptance write: meta.json carries no baseline.
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_unverifiable_merge_commit_fails_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A SHA that resolves to nothing is a clean exit-1 error, pre-write."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, _merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit="deadbeef" * 5,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_no_commit_verifies_but_does_not_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-commit`` is report-only: the evidence is verified, nothing recorded."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=True,
        lenient=False,
        no_commit=True,
        diagnose=False,
        allow_fail=False,
        merge_commit=merge_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_unmerged_specify_commit_fails_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unmerged Specify-only branch commit is not merge evidence (#4231 monitor).

    The branch's single corpus commit introduces ``meta.json`` (its parent
    lacks it), so every first-introduction check passes — but it never landed
    on the target branch, so the accept-side verification refuses it before
    any acceptance write.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, specify_commit, _parent = _create_pr_merged_feature(repo_root, merged=False)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=specify_commit,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta


def test_accept_single_parent_landing_needs_attestation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A squash landing is single-parent: attested, never presented as proven.

    The squash commit's parent IS the pre-landing tip, but git cannot prove
    that (an impl-before-corpus replay is graph-identical), so the bare call
    is a clean pre-write exit-1 refusal, and the attested call records the
    anchor with ``pr_merge_evidence: corpus-parent-attested`` naming the
    operator's attestation — never a git proof (#4231 fix round).
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, squash_commit, pre_squash_tip = _create_pr_merged_feature(repo_root, squash=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=squash_commit,
        )

    assert exc_info.value.exit_code == 1
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta
    assert "pr_merge_commit" not in meta
    assert "pr_merge_evidence" not in meta

    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=squash_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_squash_tip
    assert meta["pr_merge_commit"] == squash_commit
    assert meta["pr_merge_evidence"] == "corpus-parent-attested"


def test_accept_pr_mode_judges_evidence_against_the_landing_when_lane_branch_is_pruned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#6780: a PR-landed Mission accepts after its lane branches are pruned.

    ``accept --mode pr --merge-commit`` never runs ``consolidate``; the Mission landed
    through the pull request and the lane branches were cleaned up afterwards. The
    evidence window's tip no longer resolves, so it must be judged against the verified
    landing commit instead of refusing every done work package as unreadable.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, pre_merge_parent = _create_pr_merged_feature(repo_root, lane_merged=True, prune_lane=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    assert not _branch_resolves(repo_root, _lane_branch()), "the fixture must really have pruned the lane branch"

    accept(
        mission=_SLUG,
        mode="pr",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        merge_commit=merge_commit,
        attest_first_landing=True,
    )

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_merge_parent
    assert meta["pr_merge_commit"] == merge_commit
    assert _porcelain(repo_root) == "", "accept left a dirty working tree"


def test_accept_pr_mode_keeps_the_lane_window_when_the_branch_still_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The lane-branch window stays the first choice (#6780 control arm).

    With the lane branch readable the accept judges ``planning_commit..<lane branch>`` — the
    same window it takes today — so the landed-window stand-in cannot reinterpret an intact
    Mission. To make that discriminate, unrelated work committed on the mission branch AFTER
    the lane branch was cut touches WP02's ``tools/**``: it is inside
    ``planning_commit..<landing commit>`` and outside ``planning_commit..<lane branch>``, so
    only an inverted precedence (always prefer the supplied landing commit) would let the
    hollow WP02 through.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root, lane_merged=True, hollow_wp=True, mission_side_path="tools/unrelated.py")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    assert _branch_resolves(repo_root, _lane_branch()), "the control arm needs the lane branch to exist"
    assert "tools/unrelated.py" not in _git(repo_root, "ls-tree", "-r", "--name-only", _lane_branch()).stdout.split(), (
        "the discriminating path must NOT be on the lane branch, or the lane window would carry it too"
    )
    assert "tools/unrelated.py" in _git(repo_root, "ls-tree", "-r", "--name-only", merge_commit).stdout.split(), (
        "...and must be on the landed tree, or the landed window would not carry it either"
    )

    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
            attest_first_landing=True,
        )

    assert exit_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "IMPLEMENTATION_MISSING"
    assert "IMPLEMENTATION_MISSING: WP02" in payload["error"], "the lane window, not the landed one, must judge WP02"
    assert "IMPLEMENTATION_MISSING: WP01" not in payload["error"], "WP01 is implemented on the lane branch and must pass"
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta


def test_accept_pr_mode_still_refuses_a_hollow_wp_after_pruning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#6715 keeps its teeth on the landed window (#6780).

    WP02 was approved by an independent reviewer but never implemented; its owned files
    changed nowhere between the planning commit and the landing commit, so the accept
    refuses it with ``IMPLEMENTATION_MISSING`` and writes nothing — the wider tip must not
    turn the gate into a rubber stamp.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root, lane_merged=True, prune_lane=True, hollow_wp=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
            attest_first_landing=True,
        )

    assert exit_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "IMPLEMENTATION_MISSING"
    assert "IMPLEMENTATION_MISSING: WP02" in payload["error"]
    assert "IMPLEMENTATION_UNREADABLE" not in payload["error"]
    assert "IMPLEMENTATION_MISSING: WP01" not in payload["error"], "WP01 is implemented and must pass"
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta


def test_accept_pr_mode_refuses_a_landing_commit_that_does_not_contain_the_planning_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#6780 ancestor guard: a landing commit that is not descended from ``planning_commit_sha`` refuses.

    The lane branch is gone, so the supplied verified commit would stand in for it — but its
    history does not contain the recorded planning commit, so the window ``planning..landing``
    would not describe this Mission's work. The accept must report ``IMPLEMENTATION_UNREADABLE``
    with nothing diffed and no crash. Non-vacuity: disabling
    ``sha_reachable_from`` in ``_landed_window`` turns this into a diff over unrelated history,
    which flips both the code and the recorded diff calls.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root, lane_merged=True, prune_lane=True)
    assert not _branch_resolves(repo_root, _lane_branch()), "the stand-in only applies to a pruned tip"

    # A "verified-looking" landing commit whose history does not carry the planning commit: a
    # descendant of the landing is enough (the real landing cannot contain it either way).
    _git(repo_root, "commit", "--allow-empty", "-m", "a planning commit the landing does not contain")
    stray_planning = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    manifest.planning_commit_sha = stray_planning
    write_lanes_json(feature_dir, manifest)

    diffs: list[tuple[str, str]] = []

    def _record(_repo: Path, base: str, tip: str) -> list[tuple[str, str]]:
        diffs.append((base, tip))
        return []

    monkeypatch.setattr("specify_cli.consolidation.wp_evidence.changed_paths_in_range", _record)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
            attest_first_landing=True,
        )

    assert exit_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "IMPLEMENTATION_UNREADABLE"
    assert "does not contain the recorded planning commit" in payload["error"], payload["error"]
    assert "IMPLEMENTATION_MISSING" not in payload["error"], "an unproven stand-in must be refused, never judged"
    assert diffs == [], f"no window may be diffed against an unproven stand-in, got {diffs}"
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta


def test_accept_pr_mode_without_merge_commit_names_the_pruned_lane_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a verified landing commit the refusal is honest about the cause (#6780).

    The window cannot be read because the lane branch no longer exists; the refusal names
    that absent ref as the cause, and both remedies (restore/fetch the branch, or pass the
    verified PR landing commit), instead of a blanket 'could not be diffed' that only
    happened to carry the ref because git echoes its refspec. The assertions below pin the
    shipped sentence, not the incidental words.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir, _merge_commit, _parent = _create_pr_merged_feature(repo_root, lane_merged=True, prune_lane=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
        )

    assert exit_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "IMPLEMENTATION_UNREADABLE"
    assert f"the window tip {_lane_branch()} no longer exists" in payload["error"], (
        "the refusal must name the absent lane branch as the cause, not leave it to git's own paraphrase of the refspec"
    )
    assert "could not be diffed" not in payload["error"], "a pruned tip is diagnosed, not reported as an unreadable diff"
    assert "--merge-commit" in payload["error"], "the refusal must name the landing-commit remedy"
    assert "--mode pr" in payload["error"]
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert "baseline_merge_commit" not in meta


def test_accept_pr_mode_widens_dependencies_against_the_landing_not_the_pruned_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The dependency widening uses the effective tip too (#6780).

    lane-a depends on lane-b. lane-a's branch is pruned while lane-b's still resolves, and
    lane-a carries a hollow WP, so the widening runs. Probing ``merge-base(lane-b, <pruned
    lane branch>)`` would raise and report the whole lane as unreadable; the widening must ask
    against the same window tip that was judged, so the hollow WP is the only refusal.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _feature_dir, merge_commit, _parent = _create_pr_merged_feature(repo_root, lane_merged=True, prune_lane=True, hollow_wp=True, dependency_lane=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    assert not _branch_resolves(repo_root, _lane_branch("lane-a")), "lane-a's branch must be pruned"
    assert _branch_resolves(repo_root, _lane_branch("lane-b")), "lane-b's branch must still resolve to exercise the widening"

    with pytest.raises(typer.Exit) as exit_info:
        accept(
            mission=_SLUG,
            mode="pr",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
            merge_commit=merge_commit,
            attest_first_landing=True,
        )

    assert exit_info.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "IMPLEMENTATION_UNREADABLE" not in payload["error"], "the widening must not probe the pruned lane branch"
    assert "IMPLEMENTATION_MISSING: WP02" in payload["error"]
    assert "IMPLEMENTATION_MISSING: WP03" not in payload["error"], "WP03 is implemented and must pass"
