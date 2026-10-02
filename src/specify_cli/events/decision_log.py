"""Decision event git log emitter.

Appends sanitized DecisionInputRequested and DecisionInputAnswered events to
``kitty-specs/<mission>/decisions.events.jsonl`` and triggers ``safe_commit()``
on each answered decision.  All other runtime events are delegated to the inner
emitter unchanged.

Spec references: FR-001, FR-002, FR-003, FR-004, FR-005
See: spec-kitty #1546
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from specify_cli.core.paths import assert_safe_path_segment
from kernel.clock import now_utc_iso

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    resolve_write_target_or_degrade,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.events.sanitizer import sanitize_event_for_log
from specify_cli.git.commit_helpers import SafeCommitError, safe_commit
from runtime.next._internal_runtime.events import (
    DECISION_INPUT_ANSWERED,
    DECISION_INPUT_REQUESTED,
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
    RuntimeEventEmitter,
    seed_runtime_emitter,
)
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    TimeoutExpiredPayload,
)

__all__ = ["DecisionGitLog"]

logger = logging.getLogger(__name__)


def _generate_event_id() -> str:
    """Generate a ULID-format event ID."""
    try:
        import ulid
        return str(ulid.ULID())
    except ImportError:
        # Fallback: use a UUID4-based ID if ulid not available.
        import uuid
        return str(uuid.uuid4()).replace("-", "").upper()


class DecisionGitLog:
    """Wraps an inner RuntimeEventEmitter and writes decision events to git.

    On every ``emit_decision_input_requested`` call: sanitizes the event and
    appends it to ``kitty-specs/<mission>/decisions.events.jsonl``.

    On every ``emit_decision_input_answered`` call: sanitizes and appends the
    event, then calls ``safe_commit()`` to record the request+answer pair
    durably in the coordination branch.  If ``safe_commit()`` raises, the
    error is logged at WARNING level and NOT re-raised — a commit failure
    must never abort mission execution.

    All other emit methods delegate to ``inner`` unchanged.

    coord-artifact-single-home-01M3V4BE WP09 (FR-003/FR-003a, T051):
    ``mission_dir`` is a REQUIRED keyword argument (post-tasks squad R-m5 /
    P-m4 ruling: preferred over an optional kwarg so no caller can silently
    fall back to a stale composition). The caller (``runtime_bridge``) is the
    one place that knows the coordination topology and resolves
    ``write_dir(DECISION_LOG)``; this class no longer composes
    ``worktree_root / KITTY_SPECS_DIR / <slug>`` itself — that legacy
    composer could disagree with the write-location accessor's dir-name
    computation (``coord_mission_dir_name``) for a slug that embeds its
    mid8, forking the stream. There is now exactly one composer.
    """

    def __init__(
        self,
        repo_root: Path,
        worktree_root: Path,
        destination_ref: str,
        mission_slug: str,
        *,
        mission_dir: Path,
        inner: RuntimeEventEmitter,
        mission_id: str | None = None,
        target: CommitTarget | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._worktree_root = worktree_root
        self._destination_ref = destination_ref
        self._mission_slug = mission_slug
        # FR-001: validate mission_slug before joining into a FS path (traversal
        # guard) — validated FIRST, before any placement resolution below, even
        # though the resulting dir no longer composes HERE: an unsafe slug must
        # still fail closed with ValueError at construction, not silently reach
        # the caller-supplied ``mission_dir``.
        assert_safe_path_segment(mission_slug)
        # T010: the CommitTarget is resolved by the calling surface
        # (runtime_bridge) which knows the coordination topology — it is passed
        # in, not re-derived here. When a legacy caller supplies only the string
        # destination_ref (no injected ``target``), the DEFAULT is now derived
        # through the placement port (coord-write-placement-closure-01KYCF83
        # WP03 / FR-003) instead of trusting the ambient ``destination_ref``
        # verbatim: ``decisions.events.jsonl`` classifies to ``DECISION_LOG`` (a
        # COORD-partition kind, WP02), so ``resolve_placement_only`` resolves the
        # SAME coordination-branch ref the classifier owns — never a re-derivation
        # inline here. Only when the mission cannot be resolved (no meta.json yet,
        # or an ad-hoc fixture outside a resolvable mission) does this degrade to
        # the ambient ``destination_ref`` — mirroring the established degrade-path
        # idiom in ``coordination.status_transition._resolve_write_target``.
        self._target = target or self._resolve_default_target(
            repo_root, mission_slug, destination_ref
        )
        # WP04/FR-004: mission_id must be a ULID or None (fail-closed). Never
        # substitute the slug — a slug in a mission_id field is a contract violation.
        self._mission_id = mission_id
        self._inner = inner
        self._decisions_file = mission_dir / "decisions.events.jsonl"

    @staticmethod
    def _resolve_default_target(
        repo_root: Path, mission_slug: str, destination_ref: str
    ) -> CommitTarget:
        """Derive the default commit target via the placement port (FR-003).

        ``decisions.events.jsonl`` is the ``DECISION_LOG`` kind (a
        COORD-partition kind, WP02) — uses the shared helper to resolve
        through the placement port, with caller-supplied degrade ref for
        the bootstrap-window (no ``meta.json`` yet, or ad-hoc fixture).

        This method preserves fail-open behavior: the mission events are
        logged regardless of resolution success (fail-open policy at
        call site).
        """
        return resolve_write_target_or_degrade(
            repo_root,
            mission_slug,
            kind=MissionArtifactKind.DECISION_LOG,
            degrade_ref=destination_ref,
        )

    # ------------------------------------------------------------------
    # Decision event methods (git-logged)
    # ------------------------------------------------------------------

    def emit_decision_input_requested(
        self, payload: DecisionInputRequestedPayload
    ) -> None:
        """Append sanitized DecisionInputRequested to decisions.events.jsonl."""
        self._append_decision_event(DECISION_INPUT_REQUESTED, payload)
        self._inner.emit_decision_input_requested(payload)

    def emit_decision_input_answered(
        self, payload: DecisionInputAnsweredPayload
    ) -> None:
        """Append sanitized DecisionInputAnswered and trigger safe_commit()."""
        self._append_decision_event(DECISION_INPUT_ANSWERED, payload)
        self._trigger_commit()
        self._inner.emit_decision_input_answered(payload)

    # ------------------------------------------------------------------
    # Delegating methods (all other events pass through unchanged)
    # ------------------------------------------------------------------

    def emit_mission_run_started(self, payload: MissionRunStartedPayload) -> None:
        self._inner.emit_mission_run_started(payload)

    def emit_next_step_issued(self, payload: NextStepIssuedPayload) -> None:
        self._inner.emit_next_step_issued(payload)

    def emit_next_step_auto_completed(
        self, payload: NextStepAutoCompletedPayload
    ) -> None:
        self._inner.emit_next_step_auto_completed(payload)

    def emit_mission_run_completed(
        self, payload: MissionRunCompletedPayload
    ) -> None:
        self._inner.emit_mission_run_completed(payload)

    def emit_significance_evaluated(
        self, payload: SignificanceEvaluatedPayload
    ) -> None:
        self._inner.emit_significance_evaluated(payload)

    def emit_decision_timeout_expired(
        self, payload: TimeoutExpiredPayload
    ) -> None:
        self._inner.emit_decision_timeout_expired(payload)

    def seed_from_snapshot(self, snapshot: Any) -> None:
        """Delegate optional seeding; producer failures cannot block mission work."""
        seed_runtime_emitter(self._inner, snapshot)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_envelope(
        self, event_type: str, payload: Any
    ) -> dict[str, Any]:
        """Build a JSON-serialisable event envelope from a payload."""
        payload_dict: dict[str, Any]
        if hasattr(payload, "model_dump"):
            payload_dict = payload.model_dump(mode="json")
        elif hasattr(payload, "dict"):
            payload_dict = payload.dict()
        else:
            payload_dict = dict(payload) if payload is not None else {}

        # canonical-producer-exempt: #1198 -- canonical local-only decision git-log envelope.
        return {
            "at": now_utc_iso(),
            "event_id": _generate_event_id(),
            "event_type": event_type,
            "mission_id": self._mission_id,
            "payload": payload_dict,
        }

    def _append_to_file(self, record: dict[str, Any]) -> None:
        """Write a JSON line to decisions.events.jsonl (creates parents)."""
        self._decisions_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with self._decisions_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _append_decision_event(self, event_type: str, payload: Any) -> None:
        """Build, sanitize, and append an event envelope."""
        try:
            envelope = self._build_envelope(event_type, payload)
            sanitized = sanitize_event_for_log(envelope)
            self._append_to_file(sanitized)
        except Exception:
            logger.warning(
                "DecisionGitLog: failed to append %s event for mission %s",
                event_type,
                self._mission_slug,
                exc_info=True,
            )

    def _trigger_commit(self) -> None:
        """Call safe_commit() to persist the request+answer pair.

        Errors are caught and logged at WARNING level — a commit failure
        must NOT abort mission execution (see spec #1546).
        """
        try:
            safe_commit(
                repo_root=self._repo_root,
                worktree_root=self._worktree_root,
                target=self._target,
                message="chore(decisions): record decision [skip ci]",
                paths=(self._decisions_file,),
                # The decision record lands on the (unprotected) coordination
                # branch; STANDARD refuses a protected destination instead of
                # waiving it — the refusal is logged below and the event line
                # already written to disk is preserved (FR-008).
                capability=GuardCapability.STANDARD,
            )
        except SafeCommitError as exc:
            _observed = getattr(exc, "observed_head", None)
            logger.warning(
                "DecisionGitLog: safe_commit failed for mission %s "
                "(decisions_file=%s, worktree_root=%s, destination_ref=%s, "
                "observed_head=%s, error=%s)",
                self._mission_slug,
                self._decisions_file,
                self._worktree_root,
                self._destination_ref,
                _observed,
                exc,
            )
        except Exception:
            logger.warning(
                "DecisionGitLog: unexpected error in safe_commit for mission %s "
                "(decisions_file=%s, worktree_root=%s, destination_ref=%s)",
                self._mission_slug,
                self._decisions_file,
                self._worktree_root,
                self._destination_ref,
                exc_info=True,
            )
