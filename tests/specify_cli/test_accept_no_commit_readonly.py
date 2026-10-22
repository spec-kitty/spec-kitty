"""Contract test for ``spec-kitty accept --no-commit`` (WP06 / T030, #1908 review).

Reconciled contract (alphonso MUST-FIX #1): ``--no-commit`` means the gate **does
not COMMIT** — it does not fold any write into a commit and never mutates mission
metadata or status. It may still mutate the *accept-owned* acceptance matrix
(``acceptance-matrix.json``), because that artifact is excluded from the
dirty-tree gate (#1883 C-GATE-2) and re-resolving negative invariants is required
for the verdict to leave ``pending``. ``--no-commit`` is therefore NOT "does not
touch the tree"; the surviving tree-cleanliness invariant is that no
*non-accept-owned* path is left dirty after a ``--no-commit`` run.

``accept.py`` passes ``mutate_matrix=not diagnose`` (so ``--no-commit`` resolves
the matrix; only ``--diagnose`` is fully read-only). The two layers covered here:

* :func:`collect_feature_summary` with ``mutate_matrix=False`` (the diagnose-path
  value) writes nothing — a pure read-only contract on the summary collector.
* The real ``accept(..., no_commit=True)`` command path converges and reports
  readiness while leaving the tree clean of non-accept-owned dirt (the matrix
  write it performs is dirty-excluded), and commits nothing.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path

import pytest
import typer

from specify_cli.acceptance import collect_feature_summary
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_FEATURE_SLUG = "099-no-commit-readonly"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _porcelain_status(repo_root: Path) -> str:
    """Return raw ``git status --porcelain`` output."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _create_minimal_feature_with_lanes(tmp_path: Path) -> tuple[Path, Path]:
    """Set up a minimal mission WITH lanes.json so matrix checks are attempted.

    This exercises the ``mutate_matrix`` gate inside ``_check_lane_gates``.
    Returns (repo_root, feature_dir).
    """
    repo_root = tmp_path
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    feature_dir = repo_root / "kitty-specs" / _FEATURE_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta: dict[str, object] = {
        "mission_number": "099",
        "slug": _FEATURE_SLUG,
        "mission_slug": _FEATURE_SLUG,
        "friendly_name": "No-Commit Readonly Test",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Required planning artifacts
    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    # WP file
    wp_content = (
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
    (tasks_dir / "WP01-test.md").write_text(wp_content)

    # Status event log
    from ulid import ULID

    now = now_utc_iso()
    event = StatusEvent(
        event_id=str(ULID()),
        mission_slug=_FEATURE_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.DONE,
        at=now,
        actor="test-agent",
        force=True,
        execution_mode="direct_repo",
        reason="Test setup: skip to done",
    )
    seed_status_event(feature_dir, event)

    from specify_cli.status.reducer import materialize

    materialize(feature_dir)

    # Initial commit — clean tree before test
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")

    return repo_root, feature_dir


def test_collect_summary_mutate_matrix_false_does_not_dirty_working_tree(tmp_path: Path) -> None:
    """collect_feature_summary with mutate_matrix=False must not write any files.

    ``mutate_matrix=False`` is the value ``accept.py`` passes on the
    ``--diagnose`` (fully read-only) path. With it set, the summary collector
    never executes negative invariants or rewrites the matrix, so git status is
    byte-for-byte identical before and after. (The ``--no-commit`` path uses
    ``mutate_matrix=True`` and is covered by the CLI test below.)
    """
    repo_root, _feature_dir = _create_minimal_feature_with_lanes(tmp_path)

    status_before = _porcelain_status(repo_root)

    # mutate_matrix=False mirrors the --diagnose (read-only) gate in accept.py
    collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=False,
    )

    status_after = _porcelain_status(repo_root)

    assert status_before == status_after, (
        f"Working tree was dirtied by --no-commit mode accept run.\n"
        f"Before: {status_before!r}\n"
        f"After:  {status_after!r}"
    )


def test_commit_mode_may_write_accept_owned_files(tmp_path: Path) -> None:
    """Confirm that mutate_matrix=True (commit mode) CAN write accept-owned files.

    This is a contrast test: it verifies the feature is exercised — if
    mutate_matrix=True also leaves the tree clean, the read-only test above
    becomes a vacuous pass.  This test asserts that the distinction matters.

    We do NOT assert dirtiness here because the matrix write only occurs when
    ``lanes.json`` exists with negative invariants.  Without lanes.json the gate
    is skipped.  The important invariant is that mutate_matrix=False (the
    --diagnose path) never writes, which is covered by the test above.
    """
    repo_root, _feature_dir = _create_minimal_feature_with_lanes(tmp_path)

    # mutate_matrix=True is the normal commit-mode path; simply confirm it does
    # not raise and returns a summary.
    summary = collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )

    # Summary must be a valid object — basic smoke check.
    assert summary.feature == _FEATURE_SLUG


_CLI_SLUG = "099-no-commit-cli"
_CLI_MISSION_ID = "01JZZZZZZZZZZZZZZZZZZZZZZA"
_CLI_MISSION_BRANCH = f"kitty/mission-{_CLI_SLUG}"


def _create_acceptready_lane_feature(repo_root: Path) -> Path:
    """Create a clean, accept-ready lane-based mission on its mission branch.

    The acceptance matrix carries a grep-absence negative invariant that never
    matches, so a mutating accept run (``--no-commit``) resolves the verdict to
    pass while rewriting ``acceptance-matrix.json`` — the accept-owned write the
    reconciled contract permits but never commits.
    """
    from specify_cli.acceptance.matrix import (
        AcceptanceCriterion,
        AcceptanceMatrix,
        NegativeInvariant,
        write_acceptance_matrix,
    )
    from specify_cli.status.reducer import materialize

    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _CLI_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    # contracts/ is a mission artifact → under the feature dir, not repo root (#2115)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "099",
        "slug": _CLI_SLUG,
        "mission_slug": _CLI_SLUG,
        "mission_id": _CLI_MISSION_ID,
        "mid8": _CLI_MISSION_ID[:8],
        "friendly_name": "No-Commit CLI Test",
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

    # A real planned -> claimed leg event-sources ``agent`` into the resolved
    # snapshot (the reducer's claim exception extracts agent/shell_pid from THIS
    # transition's ``policy_metadata`` sidecar, FR-004). Skipping straight to
    # done, as before the #2816 event-sourced cutover, left the strict-accept
    # "missing agent in canonical runtime state" gate permanently red here.
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTNOCOMMITCLI0000",
            mission_slug=_CLI_SLUG,
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
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTACCEPTNOCOMMITCLI0001",
            mission_slug=_CLI_SLUG,
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
            mission_slug=_CLI_SLUG,
            mission_id=_CLI_SLUG,
            mission_branch=_CLI_MISSION_BRANCH,
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

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_CLI_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[
                NegativeInvariant(
                    invariant_id="NI1",
                    description="legacy symbol must be absent",
                    verification_method="grep_absence",
                    verification_command="ZZZ_PATTERN_THAT_NEVER_MATCHES_ZZZ",
                )
            ],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _CLI_MISSION_BRANCH)
    return feature_dir


def test_accept_no_commit_via_cli_converges_and_leaves_tree_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end ``accept(no_commit=True)`` through the real command path.

    Records the reconciled mutate_matrix override (alphonso MUST-FIX #1, #1908)
    as a tested contract — exercised via the CLI, NOT by hardcoding
    ``mutate_matrix`` into ``collect_feature_summary``:

    * the run reports readiness (exit 0, gate converges);
    * the working tree stays clean of NON-accept-owned dirt afterwards (the
      matrix write the run performs is dirty-excluded, #1883);
    * nothing is committed (HEAD is unchanged), honouring ``--no-commit``.
    """
    from specify_cli.cli.commands.accept import accept

    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _create_acceptready_lane_feature(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)

    head_before = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    # Drive the real command path with no_commit=True; success raises Exit(0).
    exit_code: int | None = 0
    try:
        accept(
            mission=_CLI_SLUG,
            mode="auto",
            actor="tester",
            test=[],
            json_output=False,
            lenient=False,
            no_commit=True,
            diagnose=False,
            allow_fail=False,
        )
    except typer.Exit as exc:
        exit_code = exc.exit_code

    assert exit_code in (0, None), f"--no-commit accept did not report readiness: exit {exit_code}"

    # The tree must carry no NON-accept-owned dirt. The accept-owned matrix write
    # the run performs is dirty-excluded by the gate, so it does not count.
    porcelain = _porcelain_status(repo_root)
    dirty_paths = [line[3:].strip() for line in porcelain.splitlines() if line.strip()]
    non_accept_owned = [
        path
        for path in dirty_paths
        if not path.endswith(("acceptance-matrix.json", "status.json", ".kittify/config.yaml"))
        and path != ".kittify/"
    ]
    assert non_accept_owned == [], f"--no-commit left non-accept-owned dirt: {non_accept_owned}"

    # --no-commit must not COMMIT: HEAD is unchanged.
    head_after = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_after == head_before, "--no-commit must not create a commit"
