"""Regression: a successful ``accept`` must leave a clean working tree.

Bug: the acceptance pipeline materializes derived artifacts (e.g.
``acceptance-matrix.json`` and status views) while running readiness checks,
*after* the git-cleanliness snapshot is taken. The acceptance commit created
inside ``perform_acceptance`` only stages ``meta.json``, so those materialized
artifacts were left modified-unstaged. After a successful accept the working
tree was dirty (``git status --porcelain`` non-empty for tracked spec/meta
artifacts), which then blocked the downstream merge preflight.

These tests drive the real top-level ``accept`` command against a lane-based
fixture whose acceptance matrix carries a negative invariant (so the matrix is
rewritten during readiness checks) and assert the tree is clean afterwards.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event

# Marked for mutmut sandbox skip — subprocess CLI/git invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "099-test-feature"
_MISSION_ID = "01JZZZZZZZZZZZZZZZZZZZZZZZ"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _porcelain(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _create_lane_feature(
    repo_root: Path,
    *,
    with_negative_invariant: bool,
) -> Path:
    """Create a clean, accept-ready lane-based feature on its mission branch.

    Returns the feature directory.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    # .kittify marker anchors find_repo_root() to this repo (paired with the
    # SPECIFY_REPO_ROOT env var set by the test) so mission resolution works
    # regardless of where pytest happens to run.
    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    # contracts/ is a mission artifact → under the feature dir, not repo root (#2115)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Test Feature",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n"
    )

    # A real ``planned -> claimed`` leg is required to event-source ``agent``
    # into the resolved snapshot (the reducer's claim exception, FR-004, only
    # extracts ``agent``/``shell_pid`` from THIS transition's
    # ``policy_metadata`` sidecar -- mirroring the real ``spec-kitty implement``
    # claim path). Skipping straight from ``planned`` to ``done`` (as before
    # the #2816 event-sourced cutover) left the strict-accept "missing agent
    # in canonical runtime state" gate permanently red for this fixture.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTCLEANTREE000000",
            mission_slug=_SLUG,
            wp_id="WP01",
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
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTCLEANTREE000001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    # A passing automated-test criterion gives the matrix a 'pass' verdict so
    # acceptance is allowed to proceed to the commit step.
    criteria = [
        AcceptanceCriterion(
            criterion_id="AC1",
            description="feature behaves as specified",
            proof_type="automated_test",
            pass_fail="pass",
        )
    ]
    invariants = []
    if with_negative_invariant:
        # A grep_absence invariant whose pattern matches nothing -> the matrix
        # gets rewritten with the resolved result during readiness checks.
        invariants = [
            NegativeInvariant(
                invariant_id="NI1",
                description="legacy symbol must be absent",
                verification_method="grep_absence",
                verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
            )
        ]
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=criteria,
            negative_invariants=invariants,
        ),
    )

    # Commit a clean baseline, then move onto the mission branch where accept runs.
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)
    return feature_dir


def test_accept_leaves_clean_tree_with_materialized_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The acceptance matrix is rewritten during checks -- accept must clean up.

    Before the fix the acceptance commit only captured meta.json, leaving
    ``acceptance-matrix.json`` modified-unstaged after a successful accept.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    # Successful (non-json) accept returns normally; no Exit is raised.
    accept(
        mission=_SLUG,
        mode="auto",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
    )

    porcelain = _porcelain(repo_root)
    assert porcelain == "", f"accept left a dirty working tree:\n{porcelain}"

    # The materialized matrix must be tracked in HEAD, not floating in the tree.
    show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_SLUG}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0, "acceptance-matrix.json is not committed in HEAD"
    matrix = json.loads(show.stdout)
    # Negative invariant was executed during readiness checks; its result must
    # be the committed value (no longer 'pending').
    assert matrix["negative_invariants"][0]["result"] == "confirmed_absent"


def test_accept_clean_tree_without_negative_invariant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with no matrix rewrite, accept must leave a clean tree."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=False)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    accept(
        mission=_SLUG,
        mode="auto",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
    )

    porcelain = _porcelain(repo_root)
    assert porcelain == "", f"accept left a dirty working tree:\n{porcelain}"


def test_accept_fails_when_residual_commit_fails_after_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful accept must not hide residual commit failure."""
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_lane_feature(repo_root, with_negative_invariant=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    def fail_residual_commit(_repo_root: Path, _mission_slug: str, *, owned: object | None = None) -> bool:
        raise RuntimeError("forced residual failure")

    monkeypatch.setattr(
        "specify_cli.cli.commands.accept._commit_residual_acceptance_artifacts",
        fail_residual_commit,
    )

    with pytest.raises(typer.Exit) as exc_info:
        accept(
            mission=_SLUG,
            mode="auto",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
        )

    assert exc_info.value.exit_code == 1


def test_residual_acceptance_commit_is_scoped_to_mission_paths(
    tmp_path: Path,
) -> None:
    """The residual finalize commit is scoped to the mission's dirty spec
    artifacts only.

    ``_commit_residual_acceptance_artifacts`` stages and commits the mission's
    leftover spec/meta files. The commit uses an explicit pathspec so an
    unrelated file the operator pre-staged is never swept into mission history;
    the operator's staged work must survive uncommitted. (The top-level
    ``accept`` command normally blocks on a dirty tree, but ``--allow-fail`` /
    ``--lenient`` paths can reach the commit step with other changes present, so
    the commit itself must be scoped.)
    """
    from specify_cli.cli.commands.accept import _commit_residual_acceptance_artifacts

    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    matrix_path = feature_dir / "acceptance-matrix.json"
    matrix_path.write_text('{"version": 1}\n')
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "baseline")

    # Mission artifact becomes dirty (tracked, modified) — the residual target.
    matrix_path.write_text('{"version": 2}\n')
    # Operator has unrelated work staged before the residual commit runs.
    unrelated = repo_root / "unrelated.txt"
    unrelated.write_text("operator work in progress\n")
    _git(repo_root, "add", "unrelated.txt")

    created = _commit_residual_acceptance_artifacts(repo_root, _SLUG)
    assert created is True

    # The mission artifact WAS committed at HEAD.
    matrix_show = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:kitty-specs/{_SLUG}/acceptance-matrix.json"],
        capture_output=True,
        text=True,
    )
    assert matrix_show.returncode == 0
    assert json.loads(matrix_show.stdout)["version"] == 2

    # The unrelated file must NOT have been swept into that commit.
    unrelated_show = subprocess.run(
        ["git", "-C", str(repo_root), "show", "HEAD:unrelated.txt"],
        capture_output=True,
        text=True,
    )
    assert unrelated_show.returncode != 0, "residual commit swept an unrelated pre-staged file into mission history"

    # The operator's staged work is preserved (still staged, uncommitted).
    assert "unrelated.txt" in _porcelain(repo_root)
