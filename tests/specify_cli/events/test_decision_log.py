"""Tests for DecisionGitLog — FR-001–FR-005 contract verification.

Covers:
  - Append-only JSONL writes on request and answer events
  - safe_commit() called exactly once per answered decision (not on request)
  - Orphaned request: file written, no commit triggered
  - safe_commit() failure does not abort mission execution
  - No PII fields written to decisions.events.jsonl
  - Delegation of all other emit methods to inner emitter
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from spec_kitty_events.mission_next import (
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
    RuntimeActorIdentity,
)
import pytest

from specify_cli.core.commit_guard import GuardCapability
from specify_cli.events.decision_log import DecisionGitLog
from mission_runtime import CommitTarget
from runtime.next._internal_runtime.events import NullEmitter
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    TimeoutExpiredPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# Payload factories
# ---------------------------------------------------------------------------

def _actor() -> RuntimeActorIdentity:
    return RuntimeActorIdentity(actor_id="test-agent", actor_type="llm")


def _requested_payload(
    *,
    run_id: str = "run-001",
    decision_id: str = "dec-001",
    step_id: str = "specify",
    question: str = "Which approach?",
    options: tuple[str, ...] = ("A", "B"),
) -> DecisionInputRequestedPayload:
    return DecisionInputRequestedPayload(
        run_id=run_id,
        decision_id=decision_id,
        step_id=step_id,
        question=question,
        options=options,
        actor=_actor(),
    )


def _answered_payload(
    *,
    run_id: str = "run-001",
    decision_id: str = "dec-001",
    answer: str = "A",
) -> DecisionInputAnsweredPayload:
    return DecisionInputAnsweredPayload(
        run_id=run_id,
        decision_id=decision_id,
        answer=answer,
        actor=_actor(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log(
    tmp_path: Path,
    *,
    inner: Any | None = None,
    mission_slug: str = "my-mission",
    destination_ref: str = "kitty/mission-my-mission",
) -> DecisionGitLog:
    return DecisionGitLog(
        repo_root=tmp_path,
        worktree_root=tmp_path,
        destination_ref=destination_ref,
        mission_slug=mission_slug,
        mission_dir=tmp_path / "kitty-specs" / mission_slug,
        inner=inner or NullEmitter(),
    )


def _decisions_file(tmp_path: Path, mission_slug: str = "my-mission") -> Path:
    return tmp_path / "kitty-specs" / mission_slug / "decisions.events.jsonl"


def _read_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# T011-A: commit triggered on answer but NOT on request
# ---------------------------------------------------------------------------

class TestCommitTriggered:
    def test_commit_triggered_on_answer_not_request(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit") as mock_commit:
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
            mock_commit.assert_not_called()
            log.emit_decision_input_answered(_answered_payload())
            mock_commit.assert_called_once()

    def test_commit_called_with_correct_args(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit") as mock_commit:
            log = _make_log(tmp_path, destination_ref="kitty/mission-abc")
            log.emit_decision_input_answered(_answered_payload())
            assert mock_commit.call_count == 1
            kwargs = mock_commit.call_args.kwargs
            assert kwargs["repo_root"] == tmp_path
            assert kwargs["worktree_root"] == tmp_path
            # T010: destination is carried on the CommitTarget passed in, not a
            # re-derived destination_ref string.
            assert kwargs["target"].ref == "kitty/mission-abc"
            # Decision-record bookkeeping is not the merge flow: it asserts
            # STANDARD, so a protected destination is refused (PR #1850 fix).
            assert kwargs["capability"] is GuardCapability.STANDARD
            assert "[skip ci]" in kwargs["message"]
            assert _decisions_file(tmp_path) in kwargs["paths"]

    def test_multiple_answers_trigger_multiple_commits(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit") as mock_commit:
            log = _make_log(tmp_path)
            log.emit_decision_input_answered(_answered_payload(decision_id="dec-001"))
            log.emit_decision_input_answered(_answered_payload(decision_id="dec-002"))
            assert mock_commit.call_count == 2


# ---------------------------------------------------------------------------
# T011-B: JSONL append behavior — correct lines, valid JSON
# ---------------------------------------------------------------------------

class TestAppendBehavior:
    def test_request_appends_one_line(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
        decisions_file = _decisions_file(tmp_path)
        assert decisions_file.exists()
        lines = _read_lines(decisions_file)
        assert len(lines) == 1

    def test_request_and_answer_append_two_lines(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
            log.emit_decision_input_answered(_answered_payload())
        lines = _read_lines(_decisions_file(tmp_path))
        assert len(lines) == 2

    def test_line_is_valid_json(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
        raw = _decisions_file(tmp_path).read_text(encoding="utf-8").strip()
        assert "\n" not in raw  # single line
        record = json.loads(raw)
        assert isinstance(record, dict)

    def test_event_type_fields_present(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
            log.emit_decision_input_answered(_answered_payload())
        lines = _read_lines(_decisions_file(tmp_path))
        assert lines[0]["event_type"] == "DecisionInputRequested"
        assert lines[1]["event_type"] == "DecisionInputAnswered"

    def test_parent_dir_created(self, tmp_path: Path) -> None:
        """decisions.events.jsonl is created even if kitty-specs/<slug>/ doesn't exist."""
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path, mission_slug="brand-new-mission")
            log.emit_decision_input_requested(_requested_payload())
        assert _decisions_file(tmp_path, "brand-new-mission").exists()


# ---------------------------------------------------------------------------
# T011-C: Orphaned request (crash before answer) — one line, no commit
# ---------------------------------------------------------------------------

class TestOrphanedRequest:
    def test_orphaned_request_no_commit(self, tmp_path: Path) -> None:
        with patch("specify_cli.events.decision_log.safe_commit") as mock_commit:
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
            mock_commit.assert_not_called()
        lines = _read_lines(_decisions_file(tmp_path))
        assert len(lines) == 1
        assert lines[0]["event_type"] == "DecisionInputRequested"


# ---------------------------------------------------------------------------
# T011-D: PII fields absent from decisions.events.jsonl
# ---------------------------------------------------------------------------

_PII_FIELDS = frozenset(
    {"machine_name", "hostname", "workspace_path", "developer_name", "developer_email"}
)


class TestNoPII:
    def _payload_with_pii(self) -> DecisionInputRequestedPayload:
        """Payload wrapping PII data in the question field (not a real field but
        the sanitizer operates on the full envelope dict)."""
        return _requested_payload(question="Who asked?")

    def test_no_pii_in_written_line(self, tmp_path: Path) -> None:
        """PII fields must not appear in any key across the written JSON line."""
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(self._payload_with_pii())
        line_text = _decisions_file(tmp_path).read_text(encoding="utf-8")
        for field in _PII_FIELDS:
            assert field not in line_text, f"PII field {field!r} found in decisions log"

    def test_sanitizer_called_with_envelope(self, tmp_path: Path) -> None:
        with (
            patch("specify_cli.events.decision_log.safe_commit"),
            patch(
                "specify_cli.events.decision_log.sanitize_event_for_log",
                wraps=lambda x: x,
            ) as mock_sanitize,
        ):
            log = _make_log(tmp_path)
            log.emit_decision_input_requested(_requested_payload())
        mock_sanitize.assert_called_once()
        envelope = mock_sanitize.call_args.args[0]
        assert envelope.get("event_type") == "DecisionInputRequested"


# ---------------------------------------------------------------------------
# T011-E: safe_commit failure is swallowed, not re-raised
# ---------------------------------------------------------------------------

class TestSafeCommitFailureSwallowed:
    def test_refused_pre_commit_hook_reports_uncommitted_answer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A real hook refusal leaves the answer on disk and visible in JSON mode."""
        from specify_cli.events.decision_log import capture_commit_warnings
        from specify_cli.cli.commands import next_cmd

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

        git("init", "-b", "kitty/mission-my-mission")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.com")
        (tmp_path / "README.md").write_text("initial\n", encoding="utf-8")
        git("add", "README.md")
        git("commit", "-m", "initial")
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        before = git("rev-parse", "HEAD")
        log = DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref="kitty/mission-my-mission",
            mission_slug="my-mission",
            mission_dir=tmp_path / "kitty-specs" / "my-mission",
            inner=NullEmitter(),
            target=CommitTarget(ref="kitty/mission-my-mission"),
        )

        with capture_commit_warnings() as warnings:
            log.emit_decision_input_answered(_answered_payload())

        assert git("rev-parse", "HEAD") == before
        assert _read_lines(_decisions_file(tmp_path))[0]["event_type"] == "DecisionInputAnswered"
        assert len(warnings) == 1
        assert "commit failed" in warnings[0]
        assert "uncommitted" in warnings[0]

        class DecisionForOutput:
            def to_dict(self) -> dict[str, str]:
                return {"kind": "terminal"}

        next_cmd._print_decision(DecisionForOutput(), True, "dec-001", "A", commit_warnings=warnings)
        output = capsys.readouterr()
        assert output.err == ""
        assert json.loads(output.out)["warnings"] == warnings

    def test_protected_branch_refused_does_not_reraise(self, tmp_path: Path) -> None:
        from specify_cli.git.commit_helpers import ProtectedBranchRefused

        exc = ProtectedBranchRefused(
            destination_ref="main",
            worktree_root=tmp_path,
            commit_message="chore(decisions): record decision [skip ci]",
        )
        with patch(
            "specify_cli.events.decision_log.safe_commit",
            side_effect=exc,
        ):
            log = _make_log(tmp_path)
            # Must not raise
            log.emit_decision_input_answered(_answered_payload())

    def test_generic_safe_commit_error_does_not_reraise(self, tmp_path: Path) -> None:
        from specify_cli.git.commit_helpers import SafeCommitError

        with patch(
            "specify_cli.events.decision_log.safe_commit",
            side_effect=SafeCommitError("head mismatch"),
        ):
            log = _make_log(tmp_path)
            log.emit_decision_input_answered(_answered_payload())  # must not raise

    def test_unexpected_exception_does_not_reraise(self, tmp_path: Path) -> None:
        with patch(
            "specify_cli.events.decision_log.safe_commit",
            side_effect=RuntimeError("disk full"),
        ):
            log = _make_log(tmp_path)
            log.emit_decision_input_answered(_answered_payload())  # must not raise

    def test_answer_still_written_after_commit_failure(self, tmp_path: Path) -> None:
        """The JSONL line must be appended even when safe_commit fails."""
        with patch(
            "specify_cli.events.decision_log.safe_commit",
            side_effect=RuntimeError("boom"),
        ):
            log = _make_log(tmp_path)
            log.emit_decision_input_answered(_answered_payload())
        lines = _read_lines(_decisions_file(tmp_path))
        assert len(lines) == 1
        assert lines[0]["event_type"] == "DecisionInputAnswered"


# ---------------------------------------------------------------------------
# T011-G: Delegation — other events reach inner emitter
# ---------------------------------------------------------------------------

class TestDelegation:
    def _make_tracking_inner(self) -> MagicMock:
        inner = MagicMock(spec=NullEmitter)
        return inner

    def test_mission_run_started_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=MissionRunStartedPayload)
        log.emit_mission_run_started(payload)
        inner.emit_mission_run_started.assert_called_once_with(payload)

    def test_next_step_issued_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=NextStepIssuedPayload)
        log.emit_next_step_issued(payload)
        inner.emit_next_step_issued.assert_called_once_with(payload)

    def test_next_step_auto_completed_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=NextStepAutoCompletedPayload)
        log.emit_next_step_auto_completed(payload)
        inner.emit_next_step_auto_completed.assert_called_once_with(payload)

    def test_mission_run_completed_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=MissionRunCompletedPayload)
        log.emit_mission_run_completed(payload)
        inner.emit_mission_run_completed.assert_called_once_with(payload)

    def test_decision_requested_also_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path, inner=inner)
            payload = _requested_payload()
            log.emit_decision_input_requested(payload)
        inner.emit_decision_input_requested.assert_called_once_with(payload)

    def test_decision_answered_also_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        with patch("specify_cli.events.decision_log.safe_commit"):
            log = _make_log(tmp_path, inner=inner)
            payload = _answered_payload()
            log.emit_decision_input_answered(payload)
        inner.emit_decision_input_answered.assert_called_once_with(payload)

    def test_significance_evaluated_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=SignificanceEvaluatedPayload)
        log.emit_significance_evaluated(payload)
        inner.emit_significance_evaluated.assert_called_once_with(payload)

    def test_decision_timeout_expired_delegated(self, tmp_path: Path) -> None:
        inner = self._make_tracking_inner()
        log = _make_log(tmp_path, inner=inner)
        payload = MagicMock(spec=TimeoutExpiredPayload)
        log.emit_decision_timeout_expired(payload)
        inner.emit_decision_timeout_expired.assert_called_once_with(payload)

    def test_seed_from_snapshot_delegates_to_inner(self, tmp_path: Path) -> None:
        """F6 (dead-port-disposition-01M1VRA2): the composition advancement
        helper seeds whichever emitter it is handed; the wrap forwards that
        seed to an inner seam that supports it."""
        inner = MagicMock(spec=NullEmitter)
        inner.seed_from_snapshot = MagicMock()
        log = _make_log(tmp_path, inner=inner)
        snapshot = object()
        log.seed_from_snapshot(snapshot)
        inner.seed_from_snapshot.assert_called_once_with(snapshot)

    def test_seed_from_snapshot_tolerates_inner_without_seed(self, tmp_path: Path) -> None:
        """F6: an inner sink without ``seed_from_snapshot`` is a no-op, never an error."""
        inner = MagicMock(spec=["emit_decision_input_requested"])
        log = _make_log(tmp_path, inner=inner)
        log.seed_from_snapshot(object())
        assert not hasattr(inner, "seed_from_snapshot")


# ---------------------------------------------------------------------------
# T011-H: decisions_file path is correct
# ---------------------------------------------------------------------------

class TestDecisionsFilePath:
    def test_decisions_file_under_kitty_specs(self, tmp_path: Path) -> None:
        log = _make_log(tmp_path, mission_slug="some-mission-01KT11")
        expected = tmp_path / "kitty-specs" / "some-mission-01KT11" / "decisions.events.jsonl"
        assert log._decisions_file == expected


# ---------------------------------------------------------------------------
# T011-I: mission_id in envelope uses ULID, not slug (RISK-2 fix)
# ---------------------------------------------------------------------------


class TestMissionIdInEnvelope:
    """Verify that the ULID mission_id is written to event envelopes, not the slug."""

    def _make_log_with_ulid(
        self,
        tmp_path: Path,
        mission_slug: str = "my-feature-01KT119Y",
        mission_id: str = "01KT119YA7GD2Y0D7MZRH5JSS3",
    ) -> DecisionGitLog:
        return DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref="kitty/mission-my-feature-01KT119Y",
            mission_slug=mission_slug,
            mission_dir=tmp_path / "kitty-specs" / mission_slug,
            inner=NullEmitter(),
            mission_id=mission_id,
        )

    def test_ulid_written_to_envelope(self, tmp_path: Path) -> None:
        """The envelope mission_id must be the ULID, not the human slug."""
        ulid = "01KT119YA7GD2Y0D7MZRH5JSS3"
        slug = "my-feature-01KT119Y"
        log = self._make_log_with_ulid(tmp_path, mission_slug=slug, mission_id=ulid)

        with patch("specify_cli.events.decision_log.safe_commit"):
            log.emit_decision_input_requested(_requested_payload())

        decisions_file = tmp_path / "kitty-specs" / slug / "decisions.events.jsonl"
        lines = _read_lines(decisions_file)
        assert lines[0]["mission_id"] == ulid, (
            f"envelope must use ULID '{ulid}', got '{lines[0]['mission_id']}'"
        )
        assert lines[0]["mission_id"] != slug, "slug must not be used as mission_id"

    def test_no_slug_fallback_when_no_mission_id(self, tmp_path: Path) -> None:
        """When mission_id is not provided, the envelope must NOT contain the slug.

        WP04 / T015: inverted from the stale contract that certified slug-as-mission_id.
        The corrected contract is fail-closed: an absent ULID yields mission_id=None
        in the event envelope (null in JSON), never the slug (FR-004).
        """
        slug = "fallback-slug-mission"
        log = DecisionGitLog(
            repo_root=tmp_path,
            worktree_root=tmp_path,
            destination_ref="kitty/mission-fallback-slug-mission",
            mission_slug=slug,
            mission_dir=tmp_path / "kitty-specs" / slug,
            inner=NullEmitter(),
        )

        with patch("specify_cli.events.decision_log.safe_commit"):
            log.emit_decision_input_requested(_requested_payload())

        decisions_file = tmp_path / "kitty-specs" / slug / "decisions.events.jsonl"
        lines = _read_lines(decisions_file)
        assert lines[0]["mission_id"] is None, (
            f"mission_id must be None (null), not the slug {slug!r}; "
            f"got {lines[0]['mission_id']!r}"
        )
        assert lines[0]["mission_id"] != slug, "slug must never be persisted as mission_id"


# ---------------------------------------------------------------------------
# FR-001 traversal guard — unsafe mission_slug rejected at construction (WP03)
# ---------------------------------------------------------------------------


class TestMissionSlugTraversalGuard:
    """Negative tests: untrusted traversal slugs must not reach the filesystem.

    Each test asserts that constructing a DecisionGitLog with an unsafe
    mission_slug raises ValueError (fail-closed) rather than silently writing
    to an escaped path.  Mutation check: neutralising the guard in
    decision_log.py (removing the assert_safe_path_segment call) would cause
    these tests to fail because no ValueError would be raised.
    """

    @pytest.mark.parametrize("bad_slug", [
        "../escaped",
        "../../etc/passwd",
        "foo/bar",
        "foo\\bar",
        ".hidden",
        "a..b",
        "",
        "   ",
    ])
    def test_traversal_slug_rejected_at_construction(
        self, tmp_path: Path, bad_slug: str
    ) -> None:
        """A traversal mission_slug must raise ValueError, no file created."""
        with pytest.raises(ValueError):
            DecisionGitLog(
                repo_root=tmp_path,
                worktree_root=tmp_path,
                destination_ref="kitty/mission-safe",
                mission_slug=bad_slug,
                # Not slug-derived on purpose: FR-001 validates ``mission_slug``
                # BEFORE this value is ever consulted, so an arbitrary valid
                # directory proves the guard fires on the slug itself.
                mission_dir=tmp_path / "kitty-specs" / "safe",
                inner=NullEmitter(),
            )
        # No escaped path may have been created anywhere under tmp_path
        assert not any(tmp_path.rglob("decisions.events.jsonl"))
