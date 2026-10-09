"""Retrospective / learning-capture seam for ``runtime.next.runtime_bridge`` (#2531 WP04).

**Sole home of the self-contained retrospective/learning-capture cluster**:
``RetrospectiveGateRefused``, ``_BufferingRuntimeEmitter``, ``_rich_hic_prompt``, ``_resolve_mission_id_for_terminus``,
``_build_retrospective_facilitator_callback``, ``_resolve_retrospective_policy_for_runtime``,
``_retrospective_blocks_completion``, ``_run_retrospective_learning_capture``,
``_classify_exc``, ``_remediation_hint``, ``_classify_and_emit_failure`` — moved
here verbatim (identical call semantics, C-001) from ``runtime_bridge.py``.

The bridge (``runtime_bridge.py``) no longer carries any forwarding delegate
for these names (#2561): its call sites reach them on this module
(``_retrospective_seam.<name>(...)``), and callers outside the package import
them from here. ``_retrospective_blocks_completion`` is read the same way.

**Intra-cluster calls are direct.** Several of the 9 names call each other
(``_run_retrospective_learning_capture`` calls
``_build_retrospective_facilitator_callback``; the built facilitator's
``_facilitator`` closure calls ``_classify_and_emit_failure``; that in turn
calls ``_classify_exc``/``_remediation_hint``). Each is a plain module-level
call inside this module, so a test that wants to intercept one patches it on
``runtime.next.runtime_bridge_retrospective``, the single binding the code
looks up. Nothing here reads a name back off ``runtime_bridge``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specify_cli.mission_metadata import load_meta_or_empty

if TYPE_CHECKING:
    from specify_cli.retrospective.schema import ProvenanceKind

logger = logging.getLogger(__name__)


class RetrospectiveGateRefused(Exception):
    """The retrospective gate refused (or could not clear) a terminal advance.

    The one typed refusal every failure of the engine's ``before_run_completed``
    hook is mapped to, on the legacy and the composition path alike: the gate's
    own :class:`MissionCompletionBlocked`, the policy-resolution error and an
    arbitrary capture exception. The original error is ``__cause__`` and
    ``cause``; ``guard_failures`` is the gate's ``code: detail`` when the cause
    carries a gate decision, else empty.
    """

    def __init__(self, cause: BaseException) -> None:
        self.cause = cause
        self.guard_failures = _gate_guard_failures(cause)
        super().__init__(str(cause))


def _gate_guard_failures(cause: BaseException) -> list[str]:
    """``["<code>: <detail>"]`` for a cause that carries a gate decision, else ``[]``."""
    reason = getattr(getattr(cause, "decision", None), "reason", None)
    code = getattr(reason, "code", None)
    if code is None:
        return []
    return [f"{code}: {getattr(reason, 'detail', '')}"]


class _BufferingRuntimeEmitter:
    """Records runtime emit calls in order and replays them on a one-shot flush.

    The decision-log emitter disposition (ADR ``2026-09-06-2`` (c)): the engine
    emits every runtime event -- decision requests, lane/state moments,
    ``MissionRunCompleted`` and its sync side-effects -- into this buffer during
    the advance, and :func:`runtime_bridge._dn_decision_materialize` flushes the
    buffer into the ``DecisionGitLog``-wrapped engine emitter
    (``ctx.emitter_for_engine``) only once the advance has returned a result and
    the abort-only ``before_run_completed`` gate has passed. So decision events
    are durably recorded through the wrap in original order, and an advance that
    the engine refuses (a stale/lock-contended plan) or the gate aborts emits
    nothing: the buffer is discarded, never flushed.

    It performs NO file capture, truncation or rollback of
    ``run.events.jsonl`` / ``state.json`` -- the engine owns those writes under
    its run-cursor lock, and the abort-only gate raises before the completion
    write (FR-009/FR-010/FR-011). This buffer only orders the emitter replay.

    Implements the ``RuntimeEventEmitter`` Protocol structurally -- every emit
    method records ``(method_name, payload)`` and returns ``None``.
    """

    def __init__(self) -> None:
        self._calls: list[tuple[str, Any]] = []
        self._flushed = False

    def _record(self, method_name: str, payload: Any) -> None:
        self._calls.append((method_name, payload))

    def emit_mission_run_started(self, payload: Any) -> None:
        self._record("emit_mission_run_started", payload)

    def emit_next_step_issued(self, payload: Any) -> None:
        self._record("emit_next_step_issued", payload)

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self._record("emit_next_step_auto_completed", payload)

    def emit_decision_input_requested(self, payload: Any) -> None:
        self._record("emit_decision_input_requested", payload)

    def emit_decision_input_answered(self, payload: Any) -> None:
        self._record("emit_decision_input_answered", payload)

    def emit_mission_run_completed(self, payload: Any) -> None:
        self._record("emit_mission_run_completed", payload)

    def emit_significance_evaluated(self, payload: Any) -> None:
        self._record("emit_significance_evaluated", payload)

    def emit_decision_timeout_expired(self, payload: Any) -> None:
        self._record("emit_decision_timeout_expired", payload)

    def seed_from_snapshot(self, snapshot: Any) -> None:
        # Pass-through for SyncRuntimeEventEmitter compatibility; not buffered
        # because seed is idempotent and side-effect-free.
        del snapshot

    def call_count(self) -> int:
        return len(self._calls)

    def discard(self) -> None:
        """Drop all buffered calls without replaying them."""
        self._calls.clear()
        self._flushed = True

    def flush(self, target: Any) -> None:
        """Replay all buffered calls into ``target`` and mark as flushed.

        Re-flushing is a no-op so the same buffer can safely be passed through
        multiple paths without double-emitting.
        """
        if self._flushed:
            return
        for method_name, payload in self._calls:
            method = getattr(target, method_name, None)
            if method is None:
                continue
            method(payload)
        self._calls.clear()
        self._flushed = True


def _rich_hic_prompt() -> tuple[bool, str | None]:
    """Operator-facing Rich prompt for the HiC retrospective lifecycle.

    Lives in the bridge layer so the ``_internal_runtime/`` package keeps a
    rich/typer-free import surface (test_internal_runtime_parity).
    """
    from rich.prompt import Confirm, Prompt

    run_now: bool = Confirm.ask("Run retrospective now?", default=True)
    if run_now:
        return True, None

    skip_reason: str = ""
    while not skip_reason.strip():
        skip_reason = Prompt.ask("Skip reason (required, must be non-empty)")
    return False, skip_reason.strip()


def _resolve_mission_id_for_terminus(feature_dir: Path) -> str:
    """Read the canonical ULID mission_id from ``meta.json`` next to the feature.

    Used by the retrospective terminus wiring to identify the mission for
    event emission and gate consultation. Falls back to the feature_dir name
    when meta.json is missing or malformed (older missions predating the
    ULID identity rollout); the gate handles missing identities defensively.
    """
    # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
    # malformed meta.json to {}, matching the prior try/except-fallback.
    meta = load_meta_or_empty(feature_dir)
    mission_id = meta.get("mission_id") if isinstance(meta, dict) else None
    if isinstance(mission_id, str) and mission_id.strip():
        return mission_id
    return feature_dir.name


_RESOLUTION_ERROR = "<resolution_error>"


def _resolution_error_source_map() -> dict[str, str]:
    """Return a minimal policy source map for malformed policy failures."""
    return {
        "enabled": _RESOLUTION_ERROR,
        "timing": _RESOLUTION_ERROR,
        "failure_policy": _RESOLUTION_ERROR,
    }


def _build_retrospective_facilitator_callback(
    mission_slug: str,
    repo_root: Path,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
) -> Any:
    """Build the facilitator callback that wires WP01/02/03 surfaces into the terminus.

    Returns a callable suitable for ``facilitator_callback=`` in ``run_terminus()``.
    When invoked by the terminus, it:

    1. Resolves policy via WP01 ``resolve_policy()``.
    2. Dispatches to the generator via WP02 ``generate_retrospective()``.
    3. Writes the record via WP03 ``write_gen_record(mode="error")``.
    4. Emits a ``RetrospectiveCaptured`` lifecycle event (WP03 ``emit_captured()``).

    The callback returns a ``RetrospectiveRecord`` (the old pydantic-based schema type)
    to satisfy the terminus contract.  Generator failures are classified and logged;
    the caller (terminus) decides whether to block or continue based on the exception
    propagating upward.

    WP04 — T018/T019/T020/T021
    """
    del repo_root
    # Late imports to keep the module-level import graph clean and to allow
    # the terminus to remain the single import point for heavy optional deps.
    from specify_cli.retrospective.policy import (
        PolicyResolutionError,
        resolve_policy,
    )
    from specify_cli.retrospective.generator import generate_retrospective
    from specify_cli.retrospective.writer import RecordExistsError, write_gen_record
    from specify_cli.retrospective.lifecycle_events import (
        Actor as RetroActor,
        emit_captured,
        emit_capture_failed,
    )

    _prov: ProvenanceKind = provenance_kind  # captured in closure

    def _facilitator(
        *,
        mission_id: str,
        feature_dir: Path,  # noqa: ARG001
        repo_root: Path,
        **_kwargs: Any,
    ) -> Any:
        """WP04 facilitator: policy-resolve → generate → write → emit."""
        # Step 1: Resolve policy.
        try:
            policy, source_map = resolve_policy(repo_root)
        except PolicyResolutionError as exc:
            source_map = _resolution_error_source_map()
            _classify_and_emit_failure(
                mission_id=mission_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                exc=exc,
                source_map=source_map,
                provenance_kind=_prov,
                emit_capture_failed=emit_capture_failed,
            )
            raise

        # Short-circuit if policy disabled.
        if not policy.enabled:
            return None  # terminus interprets None as no-op for disabled paths

        # Step 2: Generate.
        try:
            record = generate_retrospective(
                mission_slug,
                policy,
                repo_root,
                provenance_kind=_prov,
                policy_source=source_map,
            )
        except FileNotFoundError as exc:
            _classify_and_emit_failure(
                mission_id=mission_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                exc=exc,
                source_map=source_map,
                provenance_kind=_prov,
                emit_capture_failed=emit_capture_failed,
            )
            raise

        except Exception as exc:  # noqa: BLE001
            _classify_and_emit_failure(
                mission_id=mission_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                exc=exc,
                source_map=source_map,
                provenance_kind=_prov,
                emit_capture_failed=emit_capture_failed,
            )
            raise

        # Step 3: Write record.
        try:
            write_gen_record(record, repo_root=repo_root, mode="error")
        except RecordExistsError:
            # Record already written (e.g. backfill ran first).  Treat as
            # non-fatal: emit Captured with existing record path and continue.
            logger.debug(
                "Retrospective record already exists for mission %s — skipping write.",
                mission_slug,
            )
        except Exception as exc:  # noqa: BLE001
            _classify_and_emit_failure(
                mission_id=mission_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                exc=exc,
                source_map=source_map,
                provenance_kind=_prov,
                emit_capture_failed=emit_capture_failed,
            )
            raise

        # Step 4: Emit RetrospectiveCaptured lifecycle event.
        # Guard against emit failure after a successful record write — without
        # this guard, an emit-side failure (event log corruption, disk full
        # during JSONL append, etc.) leaves an orphan retrospective.yaml on
        # disk with no corresponding RetrospectiveCaptured event in the log.
        # That breaks the summary classifier (read on disk + absence of
        # Captured/Failed event → state misreported as "missing" or "failed").
        # Mission review (TOCTOU finding) caught this; we now downgrade to a
        # Failed event so the on-disk record AND the event log agree.
        runtime_actor = RetroActor(kind="runtime", id="spec-kitty-generator")
        try:
            emit_captured(
                record,
                repo_root,
                provenance_kind=_prov,
                actor=runtime_actor,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Retrospective record written but RetrospectiveCaptured emit "
                "failed for mission %s; emitting RetrospectiveCaptureFailed.",
                mission_slug,
                exc_info=exc,
            )
            _classify_and_emit_failure(
                mission_id=mission_id,
                mission_slug=mission_slug,
                repo_root=repo_root,
                exc=exc,
                source_map=source_map,
                provenance_kind=_prov,
                emit_capture_failed=emit_capture_failed,
            )
            # Do NOT re-raise — the record is on disk; mission completion
            # should proceed under default-warn policy. Strict-block policy
            # would have already raised before reaching this step.

        # Return a minimal stub satisfying the terminus protocol.
        # The terminus uses this as a truthy "record was produced" sentinel.
        return record

    return _facilitator


def _resolve_retrospective_policy_for_runtime(
    repo_root: Path,
) -> tuple[Any, dict[str, str], Exception | None]:
    """Resolve retrospective policy for runtime dispatch without raising."""
    from specify_cli.retrospective.policy import default_policy, resolve_policy

    try:
        policy, source_map = resolve_policy(repo_root)
    except Exception as exc:  # noqa: BLE001
        return default_policy(), _resolution_error_source_map(), exc
    return policy, source_map, None


def _retrospective_blocks_completion(policy: Any) -> bool:
    """Return True for the explicit strict pre-completion gate policy."""
    return (
        bool(getattr(policy, "enabled", False))
        and getattr(policy, "timing", None) == "before_completion"
        and getattr(policy, "failure_policy", None) == "block"
    )


def _run_retrospective_learning_capture(
    *,
    mission_id: str,
    mission_slug: str,
    feature_dir: Path,
    repo_root: Path,
    block_on_failure: bool,
    provenance_kind: ProvenanceKind | None = None,
) -> None:
    """Run the policy-driven retrospective capture path.

    The default product path is best-effort post-completion learning: write the
    record and emit canonical RetrospectiveCaptured/CaptureFailed events, but do
    not hold mission completion hostage. Strict projects opt into blocking by
    policy via timing=before_completion + failure_policy=block.

    ``provenance_kind`` lets a caller stamp a non-default provenance on the
    captured record (#3716): the ``mission close --discard`` leg passes
    ``"runtime_abandoned"`` so an abandoned mission is not tagged with completion
    provenance. When ``None`` the kind is derived from ``block_on_failure`` as
    before (``runtime_strict_gate`` under the strict gate, else
    ``runtime_post_completion``).
    """
    resolved_provenance: ProvenanceKind = provenance_kind or (
        "runtime_strict_gate" if block_on_failure else "runtime_post_completion"
    )
    try:
        # Built inside the ``try``: a failure while building the capture (a late
        # import, say) follows the same policy as a failure while running it.
        callback = _build_retrospective_facilitator_callback(
            mission_slug=mission_slug,
            repo_root=repo_root,
            provenance_kind=resolved_provenance,
        )
    except Exception as exc:
        _log_capture_failure(mission_slug, block_on_failure)
        # The built facilitator records its own failures as events; one that never
        # got built cannot, so the event is recorded here.
        _emit_build_failure(
            exc,
            mission_id=mission_id,
            mission_slug=mission_slug,
            repo_root=repo_root,
            provenance_kind=resolved_provenance,
        )
        if block_on_failure:
            raise
        return
    try:
        callback(mission_id=mission_id, feature_dir=feature_dir, repo_root=repo_root)
    except Exception:
        _log_capture_failure(mission_slug, block_on_failure)
        if block_on_failure:
            raise


def _log_capture_failure(mission_slug: str, block_on_failure: bool) -> None:
    logger.exception(
        "retrospective capture failed for mission %s (block_on_failure=%s)",
        mission_slug,
        block_on_failure,
    )


def _emit_build_failure(
    exc: Exception,
    *,
    mission_id: str,
    mission_slug: str,
    repo_root: Path,
    provenance_kind: str,
) -> None:
    """Record a ``RetrospectiveCaptureFailed`` event for a capture that could not be built.

    Goes through :func:`_classify_and_emit_failure`, the one place a capture
    failure is turned into the event. No policy was resolved yet, so the source map
    is empty.
    """
    from specify_cli.retrospective.lifecycle_events import emit_capture_failed

    _classify_and_emit_failure(
        mission_id=mission_id,
        mission_slug=mission_slug,
        repo_root=repo_root,
        exc=exc,
        source_map={},
        provenance_kind=provenance_kind,
        emit_capture_failed=emit_capture_failed,
    )


def _classify_exc(exc: Exception) -> str:
    """Map an exception to a failure_category string per T019 classify() table."""
    from specify_cli.retrospective.writer import RecordExistsError  # noqa: PLC0415

    if isinstance(exc, RecordExistsError):
        return "other"
    if isinstance(exc, (FileNotFoundError, IsADirectoryError)):
        return "missing_artifacts"
    # Default: generator_exception
    return "generator_exception"


def _remediation_hint(exc: Exception, source_map: dict[str, str]) -> str | None:
    """Return a remediation hint appropriate for the given exception."""
    from specify_cli.retrospective.writer import RecordExistsError  # noqa: PLC0415

    if isinstance(exc, RecordExistsError):
        return "Re-run with --overwrite to replace the existing record."
    if isinstance(exc, (FileNotFoundError, IsADirectoryError)):
        return "Run `spec-kitty migrate normalize-lifecycle` to repair missing artifacts."
    # PolicyResolutionError: surface the source
    sources = ", ".join(sorted(set(source_map.values()))) if source_map else "unknown"
    return f"Check policy configuration at: {sources}"


def _classify_and_emit_failure(
    *,
    mission_id: str,
    mission_slug: str,
    repo_root: Path,
    exc: Exception,
    source_map: dict[str, str],
    provenance_kind: str,
    emit_capture_failed: Any,
) -> None:
    """Classify ``exc`` and emit a ``RetrospectiveCaptureFailed`` event."""
    from specify_cli.retrospective.lifecycle_events import Actor as RetroActor  # noqa: PLC0415

    failure_category = _classify_exc(exc)
    hint = _remediation_hint(exc, source_map)
    runtime_actor = RetroActor(kind="runtime", id="spec-kitty-generator")

    # Trim message — no stack traces in events (T019).
    message = str(exc)[:400] if exc else "Unknown error"

    missing: list[str] | None = None
    if isinstance(exc, FileNotFoundError):
        missing = [str(exc.filename)] if getattr(exc, "filename", None) else None

    try:
        emit_capture_failed(
            mission_id=mission_id,
            mission_slug=mission_slug,
            repo_root=repo_root,
            failure_category=failure_category,
            failure_message=message,
            remediation_hint=hint,
            policy_source=source_map,
            attempted_provenance_kind=provenance_kind,
            missing_artifacts=missing,
            actor=runtime_actor,
        )
    except Exception:  # noqa: BLE001
        # If emission itself fails, log but don't mask the original exception.
        logger.warning("Failed to emit RetrospectureCaptureFailed event", exc_info=True)
