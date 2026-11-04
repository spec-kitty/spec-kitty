"""CLI-level standing test pinning the behaviour of #4891.

``spec-kitty accept`` must fail closed -- never silently skip the entire
acceptance-matrix gate -- when a mission's ``lanes.json`` is absent. The
underlying fix already lives on ``main`` (``gates_core.py`` routes through
``require_lanes_json``); this is the CLI-level pin so a regression can never
again ship unnoticed: it drives the REAL ``spec-kitty accept`` CLI end to
end (not just the domain-level ``collect_feature_summary`` surface
``tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_fails_closed_when_lanes_json_is_absent``
already covers).

This is a standing test, expected GREEN on ``main`` by design (the fix is
already merged); its job is to catch a future regression, not to prove one
exists today.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.acceptance.matrix import write_acceptance_matrix
from specify_cli.cli.commands import accept as accept_module
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import (
    commit_lane_implementation,
    derive_mission_id,
    write_single_lane_manifest,
)
from tests.specify_cli.test_acceptance_regressions import (
    _create_test_feature,
    _passing_acceptance_matrix,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

_MISSION_SLUG = "wp04-4891-cli-pin-mission"

#: A dedicated, never-protected work branch used as BOTH the checked-out
#: branch and the mission's ``target_branch`` for the positive control --
#: mirrors ``test_issue_4974_accept_concurrent_verdict.py``'s ``_WORK_BRANCH``
#: convention, sidestepping ``ProtectionPolicy``'s default-protected ``main``
#: so the acceptance commit takes the simple direct-commit path.
_WORK_BRANCH = "wp04-4891-accept-work"


def _run_accept(repo_root: Path, mission_slug: str, monkeypatch: pytest.MonkeyPatch) -> Result:
    cli = typer.Typer()
    cli.command(name="accept")(accept_module.accept)
    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)
    return CliRunner().invoke(
        cli,
        ["--mission", mission_slug, "--json"],
        catch_exceptions=False,
    )


def _meta(feature_dir: Path) -> dict[str, object]:
    payload: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return payload


def _build_accept_ready_mission(tmp_path: Path) -> tuple[Path, Path]:
    """The ONE fixture both controls below start from: a Mission nothing but ``lanes.json`` can block.

    ``_create_test_feature`` predates #6715/#5939, so its work package declares no
    ``owned_files`` and its status log is one forced ``planned -> done`` hop under a single
    actor. Every landing surface now reads (1) an implementation-evidence window
    (``planning_commit_sha..<lane branch>``) holding a change to the work package's owned
    files and (2) an approval by an identity other than the implementer of record. A fixture
    without them makes ``accept`` refuse for reasons that have nothing to do with
    ``lanes.json``: the negative control would then pass for the wrong reason and the
    positive control could never be reached. So state both here, once, as an implemented and
    independently reviewed mission -- the shape ``test_accept_clean_tree`` uses for the same
    gate.

    Returns ``(repo_root, feature_dir)`` on the dedicated work branch, tree clean, WITHOUT
    ``lanes.json``: the caller adds it for the positive control only. Everything else the two
    controls need -- the ownership, the lane's implementation commit and the review history --
    is built HERE, so the negative and positive fixtures differ by exactly the manifest and the
    acceptance matrix.
    """
    repo_root, feature_dir = _create_test_feature(tmp_path, _MISSION_SLUG, omit_status_events=True)

    # #6715: the evidence axis reads the work package's AUTHORED ownership, and nothing else.
    # Without it no change could ever prove WP01's implementation, whatever its lane branch holds.
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "owned_files:\n"
        '  - "src/**"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n",
        encoding="utf-8",
    )

    # Move onto a dedicated, never-protected work branch and repoint
    # target_branch at it (see ``_WORK_BRANCH`` docstring above).
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-M", _WORK_BRANCH],
        check=True,
        capture_output=True,
    )
    meta_path = feature_dir / "meta.json"
    meta = _meta(feature_dir)
    mission_id = derive_mission_id(_MISSION_SLUG)
    meta["mission_id"] = mission_id
    meta["mid8"] = mission_id[:8]
    meta["target_branch"] = _WORK_BRANCH
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # The implemented-and-reviewed lifecycle the #6715 evidence axis and its review-
    # independence sibling read: an implementer claims the work package, a DIFFERENT
    # identity approves it, and only then is it done. Event ids stay inside the ULID
    # alphabet (hex only, 26 characters): the status store drops a line whose id is not.
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="014891ACCE0000000000000001",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="test-implementer",
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
            event_id="014891ACCE0000000000000002",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:01:00+00:00",
            actor="test-reviewer",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: reviewed and approved by a non-implementer",
        ),
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="014891ACCE0000000000000003",
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.APPROVED,
            to_lane=Lane.DONE,
            at="2026-01-01T00:02:00+00:00",
            actor="test-implementer",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: approved work package lands as done",
        ),
    )
    materialize(feature_dir)

    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "seed implemented, independently reviewed mission"],
        check=True,
        capture_output=True,
    )

    # The lane branch and its implementation commit, in BOTH controls. A real Mission cuts its
    # lanes from the planning commit `lanes.json` records, so the manifest is written here (its
    # recorded planning commit is the commit just made), the canonical helper cuts the lane from
    # it, and the manifest is then removed: the state the negative control tests is this same
    # Mission with its manifest absent, not a Mission that was never implemented.
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch=_WORK_BRANCH)
    commit_lane_implementation(repo_root, feature_dir, path="src/wp01.py")
    (feature_dir / "lanes.json").unlink()
    return repo_root, feature_dir


def test_accept_cli_fails_closed_when_lanes_json_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``lanes.json`` -> the real CLI exits non-zero, stamps nothing, and
    names the blocked ``lanes_manifest`` check in its JSON envelope."""
    repo_root, feature_dir = _build_accept_ready_mission(tmp_path)
    monkeypatch.chdir(repo_root)

    assert not (feature_dir / "lanes.json").exists()

    result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

    assert result.exit_code != 0, result.output
    assert "accepted_at" not in _meta(feature_dir)

    payload = json.loads(result.output)
    assert "accepted_at" not in payload
    blocked_checks = {item["check"] for item in payload.get("blocked_checks", [])}
    assert "lanes_manifest" in blocked_checks, f"the JSON envelope must name the blocked lanes_manifest check. Got: {payload.get('blocked_checks')}"
    assert payload.get("ok") is False


def test_accept_cli_positive_control_with_lanes_json_and_passing_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture, but WITH ``lanes.json`` and a passing acceptance matrix:
    accept succeeds and stamps ``accepted_at`` -- proves the negative test
    above is exercising the ``lanes.json``-absence path specifically, not
    some other unrelated blocker in the shared fixture."""
    repo_root, feature_dir = _build_accept_ready_mission(tmp_path)

    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), target_branch=_WORK_BRANCH)
    write_acceptance_matrix(feature_dir, _passing_acceptance_matrix(_MISSION_SLUG))

    subprocess.run(["git", "-C", str(repo_root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", "seed lanes.json + passing matrix"],
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(repo_root)

    assert (feature_dir / "lanes.json").exists()

    result = _run_accept(repo_root, _MISSION_SLUG, monkeypatch)

    assert result.exit_code == 0, result.output
    assert "accepted_at" in _meta(feature_dir), result.output
