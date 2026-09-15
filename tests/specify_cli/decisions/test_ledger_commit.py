"""Commit-on-record for the Decision Moment ledger (#4311).

Robert's 2026-09-14 ruling (planning#2269): decisions must be real time AND a
permanent record. These tests pin the permanent half — every ledger change a
decision record makes is committed through the coordination write seam in the
same operation, exactly once, idempotently (never an empty commit), and the
commit is local (no push — GOAL.md defers auto-push permanently).

Two layers, mirroring the repo's split convention:

* unit tests (``TestServiceWiring``, ``TestRefusalSurfacing``) over the
  service with the seam mocked — the wiring contract: which actions commit,
  which are no-ops, and how a refusal is surfaced, never raised;
* integration tests (``TestRealRepoCommit``, ``git_repo``) over a REAL flat
  git repo (``tests.specify_cli.write_side.topology_fixtures.build_primary``)
  exercising the unmodified seam — the issue's first two required tests
  verbatim: a recorded decision is committed exactly once, and re-recording
  the same decision is a no-op (no second commit, no empty commit).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import (
    cancel_decision,
    open_decision,
    resolve_decision,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KTEST_MISSION_ID_000001"
MISSION_SLUG = "test-mission"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup_meta(repo_root: Path) -> None:
    """Create meta.json so the service can resolve mission_id."""
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _open(repo_root: Path, **overrides: object):
    _setup_meta(repo_root)
    kwargs: dict = {
        "origin_flow": OriginFlow.CHARTER,
        "step_id": "step-1",
        "input_key": "team_size",
        "question": "How large is the team?",
        "options": ("1-5", "6-20"),
        "actor": "alice",
    }
    kwargs.update(overrides)
    return open_decision(repo_root, MISSION_SLUG, **kwargs)


def _committed_result(entry_id: str) -> WriteSeamResult:
    return WriteSeamResult(
        status="committed",
        entry_id=entry_id,
        destination_surface="main",
        commit_hash="abc1234",
    )


def _unchanged_result() -> WriteSeamResult:
    return WriteSeamResult(status="unchanged", entry_id="dm", destination_surface="main")


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


_FEATURE_BRANCH = "feature/decisions-demo"


def _retarget_to_feature_branch(repo: Path, slug: str) -> str:
    """Move a ``build_primary`` fixture mission onto a feature branch.

    The fixture declares ``target_branch: main``, and ``main``/``master`` are
    protected by default (``git.protection_policy``) — the write seam then
    (correctly) refuses the commit. The realistic routable mission carries a
    non-protected feature target, so the success-path tests retarget: new
    branch, meta.json's ``target_branch`` pointed at it, committed.
    """
    _git(repo, "checkout", "-q", "-b", _FEATURE_BRANCH)
    meta = repo / "kitty-specs" / slug / "meta.json"
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["target_branch"] = _FEATURE_BRANCH
    meta.write_text(json.dumps(data), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "retarget to feature branch")
    return _FEATURE_BRANCH


def _head_subjects(repo_root: Path, count: int = 10) -> list[str]:
    return _git(repo_root, "log", f"-{count}", "--pretty=%s").splitlines()


# ---------------------------------------------------------------------------
# Service wiring (unit, seam mocked)
# ---------------------------------------------------------------------------


class TestServiceWiring:
    def test_fresh_open_commits_the_ledger_exactly_once(self, tmp_path: Path) -> None:
        # emit runs for real so the event row exists: the commit batch must
        # carry the whole record (ledger + its event), not just the ledger.
        with patch(
            "specify_cli.coordination.write_seam.write_artifact",
            return_value=_committed_result("dm"),
        ) as seam:
            resp = _open(tmp_path)

        assert resp.ledger_commit is not None
        assert resp.ledger_commit.status == "committed"
        assert resp.ledger_commit.commit_hash == "abc1234"
        assert seam.call_count == 1
        # The seam is addressed with the DECISION_LEDGER kind and the store's
        # materialized ledger files, through the one write seam.
        kwargs = seam.call_args.kwargs
        assert kwargs["kind"] is MissionArtifactKind.DECISION_LEDGER
        committed_paths = {p.name for p in kwargs["files"]}
        assert "index.json" in committed_paths
        assert any(name.startswith("DM-") for name in committed_paths)
        assert "status.events.jsonl" in committed_paths
        assert kwargs["entry_id"] == resp.decision_id
        assert "open" in kwargs["message"]

    def test_idempotent_reopen_is_a_no_op_commit(self, tmp_path: Path) -> None:
        # emit runs for real on the first open so the opened event exists —
        # otherwise the re-open would (correctly) repair the missing event
        # and commit THAT; this test pins the pure no-op re-record.
        results = [_committed_result("dm"), _unchanged_result()]
        with patch(
            "specify_cli.coordination.write_seam.write_artifact",
            side_effect=results,
        ) as seam:
            first = _open(tmp_path)
            second = _open(tmp_path)

        assert second.idempotent is True
        assert second.decision_id == first.decision_id
        # The re-record re-ATTEMPTS the commit (a first record whose commit
        # failed converges on the rerun) and the seam answers "unchanged" —
        # a no-op, never an empty commit.
        assert second.ledger_commit is not None
        assert second.ledger_commit.status == "unchanged"
        assert seam.call_count == 2

    def test_terminal_record_commits_the_ledger(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1),
            patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2),
            patch(
                "specify_cli.coordination.write_seam.write_artifact",
                return_value=_committed_result("dm"),
            ) as seam,
        ):
            opened = _open(tmp_path)
            resolved = resolve_decision(
                tmp_path,
                MISSION_SLUG,
                opened.decision_id,
                final_answer="6-20",
                actor="alice",
            )

        assert resolved.ledger_commit is not None
        assert resolved.ledger_commit.status == "committed"
        assert seam.call_count == 2  # one for the open, one for the resolve
        assert "resolved" in seam.call_args.kwargs["message"]

    def test_idempotent_terminal_rerun_is_a_no_op_commit(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1),
            patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2),
            patch(
                "specify_cli.coordination.write_seam.write_artifact",
                side_effect=[
                    _committed_result("dm"),
                    _committed_result("dm"),
                    _unchanged_result(),
                ],
            ) as seam,
        ):
            opened = _open(tmp_path)
            resolve_decision(
                tmp_path,
                MISSION_SLUG,
                opened.decision_id,
                final_answer="6-20",
                actor="alice",
            )
            rerun = resolve_decision(
                tmp_path,
                MISSION_SLUG,
                opened.decision_id,
                final_answer="6-20",
                actor="alice",
            )

        assert rerun.idempotent is True
        assert rerun.ledger_commit is not None
        assert rerun.ledger_commit.status == "unchanged"
        # open + resolve committed; the rerun re-attempted and was told
        # "unchanged" — no third commit, never an empty commit.
        assert seam.call_count == 3

    def test_dry_run_never_commits(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.coordination.write_seam.write_artifact",
            side_effect=AssertionError("dry run must not commit"),
        ) as seam:
            resp = _open(tmp_path, dry_run=True)

        assert resp.decision_id == "DRY_RUN"
        assert resp.ledger_commit is None
        seam.assert_not_called()


class TestRefusalSurfacing:
    def test_unroutable_refusal_is_reported_never_raised(self, tmp_path: Path) -> None:
        refusal = WriteSeamResult(
            status="refused",
            entry_id="dm",
            destination_surface=None,
            diagnostic="write_seam: refusing a zero-write on an unroutable target",
        )
        with (
            patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1),
            patch(
                "specify_cli.coordination.write_seam.write_artifact",
                return_value=refusal,
            ),
        ):
            resp = _open(tmp_path)

        # The record itself succeeded — the ledger row and its event are on
        # disk; the refusal is a structured report the CLI prints loudly.
        assert resp.idempotent is False
        assert resp.ledger_commit is not None
        assert resp.ledger_commit.status == "refused"
        assert resp.ledger_commit.diagnostic is not None
        assert "refusing" in resp.ledger_commit.diagnostic

    def test_seam_exception_is_an_error_report_never_raised(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1),
            patch(
                "specify_cli.coordination.write_seam.write_artifact",
                side_effect=RuntimeError("git exploded"),
            ),
        ):
            resp = _open(tmp_path)

        assert resp.ledger_commit is not None
        assert resp.ledger_commit.status == "error"

    def test_no_materialized_files_is_an_error_report(self, tmp_path: Path) -> None:
        from specify_cli.decisions.ledger_commit import commit_ledger_change

        report = commit_ledger_change(
            tmp_path,
            MISSION_SLUG,
            _mission_dir(tmp_path),
            "01NOSUCHDECISIONID0000000",
            action="open",
        )
        assert report.status == "error"
        assert report.diagnostic is not None

    def test_unknown_action_is_a_usage_error(self, tmp_path: Path) -> None:
        from specify_cli.decisions.ledger_commit import commit_ledger_change

        with pytest.raises(ValueError, match="unknown ledger commit action"):
            commit_ledger_change(
                tmp_path,
                MISSION_SLUG,
                _mission_dir(tmp_path),
                "01ANYDECISIONID00000000000",
                action="exploded",
            )


# ---------------------------------------------------------------------------
# CLI output (the "say so in the command output" requirement)
# ---------------------------------------------------------------------------


class TestCliOutput:
    def _setup_cli_mission(self, tmp_path: Path) -> Path:
        (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
        mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text(
            json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
            encoding="utf-8",
        )
        return mission_dir

    def _invoke(self, tmp_path: Path, *args: str):
        import os

        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent import app as agent_app

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            return CliRunner().invoke(agent_app, ["decision", *args], catch_exceptions=False)
        finally:
            os.chdir(old_cwd)

    def test_open_output_carries_commit_report_and_local_note(self, tmp_path: Path) -> None:
        self._setup_cli_mission(tmp_path)
        with patch(
            "specify_cli.coordination.write_seam.write_artifact",
            return_value=_committed_result("dm"),
        ):
            result = self._invoke(
                tmp_path,
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s1",
                "--input-key",
                "team_size",
                "--question",
                "How large?",
            )

        assert result.exit_code == 0
        data = json.loads(result.output.strip().splitlines()[-1])
        report = data["ledger_commit"]
        assert report["status"] == "committed"
        assert report["commit_hash"] == "abc1234"
        # The command output SAYS the commit is local and push is the
        # operator's (#4311 Required 1).
        assert "push" in report["note"]
        assert "locally" in report["note"]

    def test_refused_commit_is_a_loud_stderr_warning(self, tmp_path: Path) -> None:
        self._setup_cli_mission(tmp_path)
        refusal = WriteSeamResult(
            status="refused",
            entry_id="dm",
            destination_surface=None,
            diagnostic="write_seam: refusing a zero-write on an unroutable target",
        )
        with patch(
            "specify_cli.coordination.write_seam.write_artifact",
            return_value=refusal,
        ):
            result = self._invoke(
                tmp_path,
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s1",
                "--input-key",
                "team_size",
                "--question",
                "How large?",
            )

        # The record itself succeeded (exit 0, decision_id minted) — the
        # uncommitted ledger is the loud part, on stderr.
        assert result.exit_code == 0
        assert "NOT committed" in result.stderr
        assert "refusing" in result.stderr
        # The warning is a JSON line, not prose: both streams stay parseable
        # under the --json contract (mixed-runner consumers parse every line).
        stderr_payload = json.loads(result.stderr.strip().splitlines()[-1])
        assert stderr_payload["warning"] == "decision ledger NOT committed"
        assert stderr_payload["ledger_commit_status"] == "refused"
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["ledger_commit"]["status"] == "refused"

    def test_dry_run_output_has_no_commit_section(self, tmp_path: Path) -> None:
        self._setup_cli_mission(tmp_path)
        result = self._invoke(
            tmp_path,
            "open",
            "--mission",
            MISSION_SLUG,
            "--flow",
            "charter",
            "--step-id",
            "s1",
            "--input-key",
            "team_size",
            "--question",
            "How large?",
            "--dry-run",
        )

        assert result.exit_code == 0
        data = json.loads(result.output.strip().splitlines()[-1])
        assert data["ledger_commit"] is None


# ---------------------------------------------------------------------------
# Real-repo integration (the issue's required tests 1 and 2, verbatim)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
class TestRealRepoCommit:
    def test_recorded_decision_is_committed_exactly_once_and_rerecord_is_a_noop(self, tmp_path: Path) -> None:
        from tests.specify_cli.write_side.topology_fixtures import build_primary

        top = build_primary(tmp_path)
        repo = top.repo_root
        slug = top.mission_slug
        surface = _retarget_to_feature_branch(repo, slug)

        # emit runs for real (event row + fan-out): no origin remote on the
        # fixture repo, so credential resolution stays silent and the whole
        # record — ledger files AND the event row — lands in the commit.
        first = open_decision(
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )
        # Required test 2: re-recording the same decision is a no-op.
        second = open_decision(
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )

        assert second.idempotent is True
        assert second.decision_id == first.decision_id
        # The re-record re-attempts the commit; the real seam answers
        # "unchanged" — no second commit, never an empty commit.
        assert second.ledger_commit is not None
        assert second.ledger_commit.status == "unchanged"

        # Required test 1: committed exactly once — ONE new commit on the
        # target branch beyond the fixture's, carrying the whole ledger
        # change (index + DM artifact + the event row).
        subjects = _head_subjects(repo, count=5)
        ledger_commits = [s for s in subjects if "chore(decisions): record open of" in s]
        assert len(ledger_commits) == 1
        assert first.ledger_commit is not None
        assert first.ledger_commit.status == "committed"
        assert first.ledger_commit.surface == surface

        # The commit actually contains the ledger files, and the working
        # tree is clean for them afterwards (nothing left uncommitted).
        committed = _git(repo, "show", "--name-only", "--pretty=", "HEAD").split()
        assert any(p.endswith("/decisions/index.json") or p == "index.json" for p in committed)
        assert any("/DM-" in p for p in committed)
        assert any(p.endswith("status.events.jsonl") for p in committed)
        status = _git(repo, "status", "--porcelain", "--", "kitty-specs")
        assert status == ""

    def test_resolved_decision_is_committed_terminal_rerun_is_a_noop(self, tmp_path: Path) -> None:
        from tests.specify_cli.write_side.topology_fixtures import build_primary

        top = build_primary(tmp_path)
        repo = top.repo_root
        slug = top.mission_slug
        _retarget_to_feature_branch(repo, slug)

        opened = open_decision(
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )
        resolved = resolve_decision(
            repo,
            slug,
            opened.decision_id,
            final_answer="6-20",
            actor="alice",
        )
        # Same outcome, same payload: the terminal re-run is a no-op.
        rerun = resolve_decision(
            repo,
            slug,
            opened.decision_id,
            final_answer="6-20",
            actor="alice",
        )

        assert resolved.ledger_commit is not None
        assert resolved.ledger_commit.status == "committed"
        assert rerun.idempotent is True
        assert rerun.ledger_commit is not None
        assert rerun.ledger_commit.status == "unchanged"

        subjects = _head_subjects(repo, count=6)
        assert len([s for s in subjects if "record open of" in s]) == 1
        assert len([s for s in subjects if "record resolved of" in s]) == 1

        # A resolved decision is never left uncommitted in the working tree.
        status = _git(repo, "status", "--porcelain", "--", "kitty-specs")
        assert status == ""

    def test_defer_and_cancel_carry_their_action_in_the_commit_message(self, tmp_path: Path) -> None:
        from tests.specify_cli.write_side.topology_fixtures import build_primary

        top = build_primary(tmp_path)
        repo = top.repo_root
        slug = top.mission_slug
        _retarget_to_feature_branch(repo, slug)

        opened = open_decision(
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )
        deferred = open_decision(  # a second, independent decision point
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-2",
            input_key="deadline",
            question="When is the deadline?",
            actor="alice",
        )
        from specify_cli.decisions.service import defer_decision

        defer_decision(
            repo,
            slug,
            opened.decision_id,
            rationale="wait for the survey",
            actor="alice",
        )
        canceled = cancel_decision(
            repo,
            slug,
            deferred.decision_id,
            rationale="no longer relevant",
            actor="alice",
        )

        assert canceled.ledger_commit is not None
        assert canceled.ledger_commit.status == "committed"
        subjects = _head_subjects(repo, count=8)
        assert len([s for s in subjects if "record deferred of" in s]) == 1
        assert len([s for s in subjects if "record canceled of" in s]) == 1
