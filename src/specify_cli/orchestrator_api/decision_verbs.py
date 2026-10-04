"""orchestrator-api decision verbs (#5628).

``open-decision``, ``resolve-decision``, ``defer-decision``,
``cancel-decision`` and ``answer-decision``. Registered on the app by
``commands.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from specify_cli.decisions.models import OriginFlow
    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.store import DecisionIndexReadError

import typer

from runtime.next.decision import VALID_RESULT_VALUES
from specify_cli.core.contract_gate import is_allowed_error_code, validate_outbound_payload

from .envelope import (
    make_envelope,
)


from . import _common
from ._common import (
    _HELP_ACTOR,
    _HELP_MISSION_SLUG,
    _HELP_POLICY,
    _emit,
    _fail,
    _parse_policy_or_fail,
)


# PR-CONTRACT-002 (severity 2): a fallback for the ONE case the allow-list
# guard below exists to catch -- a ``DecisionError`` whose ``code.value`` is
# NOT registered in ``upstream_contract.json``'s ``allowed_error_codes``
# (e.g. ``DecisionErrorCode.VERIFY_DRIFT``, dormant today but reachable the
# moment ``decisions/service.py`` starts raising it). Itself contract-
# registered (see ``upstream_contract.json``), so the guard's own fallback
# can never re-trigger the same violation it exists to prevent.
_DECISION_UNREGISTERED_CODE_FALLBACK = "DECISION_OPERATION_FAILED"


def _fail_from_decision_error(cmd: str, exc: DecisionError) -> NoReturn:
    """Fail from a ``DecisionError``, guarding against an unregistered
    ``exc.code.value`` reaching the public ``error_code`` field verbatim.

    open/resolve/defer/cancel-decision each catch ``DecisionError`` and, pre-
    fix, trusted ``exc.code.value`` unconditionally -- correct for the six
    ``DecisionErrorCode`` members ``decisions/service.py`` actually raises
    today (all six ARE contract-registered), but structurally unsafe: NOTHING
    at runtime cross-checked the propagated code against
    ``upstream_contract.json``'s ``allowed_error_codes`` allow-list, and the
    static ``TestAllowedErrorCodes`` regex check
    (``tests/contract/test_orchestrator_api.py``) only sees a literal quoted
    string passed directly as ``_fail``'s second argument -- a variable
    expression like ``exc.code.value`` is invisible to it. A future code
    path raising the currently-dormant ``DecisionErrorCode.VERIFY_DRIFT``
    (unregistered) -- or any other not-yet-registered member added later --
    would silently emit a CI-invisible contract violation. This is the ONE place that
    membership check happens; an unregistered code degrades to the
    registered ``_DECISION_UNREGISTERED_CODE_FALLBACK`` code instead of
    leaking through, with the real code preserved as diagnostic ``data`` for
    debugging (never silently dropped, never exposed as the public
    ``error_code``).
    """
    code = exc.code.value
    if is_allowed_error_code("orchestrator_api", code):
        _fail(cmd, code, str(exc), exc.details)
    _fail(
        cmd,
        _DECISION_UNREGISTERED_CODE_FALLBACK,
        str(exc),
        {**exc.details, "unregistered_error_code": code},
    )


def _fail_decision_index_unreadable(cmd: str, mission: str, exc: DecisionIndexReadError) -> NoReturn:
    """Fail-closed on a corrupt ``decisions/index.json`` reached from a
    decision WRITE verb (open/resolve/defer/cancel-decision).

    Pre-fix (#4642 follow-up review finding), these four verbs caught ONLY
    ``DecisionError`` -- ``DecisionIndexReadError`` is a ``RuntimeError``, not
    a ``DecisionError``, so it escaped as a raw traceback with EMPTY stdout,
    violating this file's JSON-first machine contract. Reuses the SAME
    ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` envelope the ``design-status``
    read verb already emits for this identical exception (:func:`design_status`)
    -- that code is the one ``DecisionIndexReadError`` code already registered
    in ``upstream_contract.json``'s ``allowed_error_codes`` for this file, so
    reusing it keeps the write verbs' error surface consistent with the read
    verb's without expanding the contract.
    """
    _fail(
        cmd,
        "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
        f"decisions/index.json could not be read cleanly for mission {mission!r}: {exc}",
        {"mission_slug": mission, "error": str(exc)},
    )


def _fail_decision_event_log_unreadable(cmd: str, mission: str, exc: DecisionEventLogReadError) -> NoReturn:
    """Fail-closed on a corrupt ``status.events.jsonl`` reached from a
    decision WRITE verb's idempotent re-open repair path (open/resolve/
    defer/cancel-decision).

    Mirrors :func:`_fail_decision_index_unreadable` (#2899 pre-PR squad
    follow-up): ``DecisionEventLogReadError`` (``decisions/service.py``,
    mission cli-error-surface-seam/WP07/#4746) is a ``RuntimeError``, not a
    ``DecisionError`` -- pre-fix these four verbs caught only ``DecisionError``
    and ``DecisionIndexReadError``, so this exception escaped as a raw
    traceback with EMPTY stdout, violating this file's JSON-first machine
    contract. Reuses the SAME ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` envelope
    code the sibling ``DecisionIndexReadError`` handler and ``design-status``
    already emit -- both are event-log/index read failures registered under
    that one contract code, so reusing it keeps the write verbs' error
    surface consistent without expanding the contract.
    """
    _fail(
        cmd,
        "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
        f"status.events.jsonl could not be read cleanly for mission {mission!r}: {exc}",
        {"mission_slug": mission, "error": str(exc)},
    )


# ── Commands 15-18: open/resolve/defer/cancel-decision (Mechanism A) ────────
#
# WP05: OriginFlow-keyed decisions/index.json ledger verbs (FR-006/007/008/
# 009, FR-012, C-001/003). Wrap ``decisions/service.py``'s four pure
# functions 1:1 -- the SAME functions the host-CLI ``spec-kitty agent
# decision open|resolve|defer|cancel`` subcommands call
# (``cli/commands/decision.py``). Deliberately do NOT reuse
# ``decision.py``'s own ``_open_response_to_dict``/``_terminal_response_to_dict``/
# ``_handle_decision_error`` helpers -- those are CLI-layer presentation code;
# this WP shapes its own ``data`` dict independently and translates
# ``DecisionError`` into this module's ``_fail``/``make_envelope`` shape,
# matching how ``start-review`` independently shapes its own response rather
# than reusing ``next_cmd.py``'s print helpers.
#
# Mechanism A only (spec Clarification 3): unrelated to WP08's
# ``answer-decision`` (run-snapshot ``pending_decisions``, no ``OriginFlow``
# concept at all) -- FR-012's ``INVALID_ORIGIN_FLOW`` guard below must NEVER
# be applied to that verb.

_HELP_DECISION_ID = "Decision ledger entry ID (ULID)"
_HELP_ORIGIN_FLOW = "Origin flow: charter | specify | plan"
_HELP_RATIONALE_REQUIRED = "Explanation of why (required)"
_HELP_RESOLVED_BY = "Identity of the resolving/deferring/canceling party (falls back to --actor)"


def _validate_origin_flow_or_fail(cmd: str, origin: str) -> OriginFlow:
    """Validate ``--origin`` against ``OriginFlow``'s three members (FR-012).

    Rejects BEFORE calling into ``decisions/service.py`` -- an invalid origin
    must never reach the service layer and be silently accepted or
    misfiled. Deliberately a DIFFERENT error_code than the host CLI's own
    ``--flow`` validation (which reuses ``DecisionErrorCode.MISSING_STEP_OR_SLOT``
    for this case, ``decision.py`` ``cmd_open`` -- a confusing reused code
    this WP does not propagate): FR-012 is an orchestrator-api-specific scope
    guard with its own dedicated code.

    Only ``open-decision`` calls this helper (T026): ``resolve``/``defer``/
    ``cancel``-decision operate on an EXISTING ``decision_id`` whose origin
    was already validated at open time, and their
    ``decisions/service.py`` functions take no ``origin_flow`` parameter at
    all (confirmed from ``resolve_decision``/``defer_decision``/
    ``cancel_decision``'s own signatures) -- wiring this guard into those
    verbs would be inventing a flag their service layer does not need.
    """
    from specify_cli.decisions.models import OriginFlow as _OriginFlow

    try:
        return _OriginFlow(origin)
    except ValueError:
        valid = ", ".join(flow.value for flow in _OriginFlow)
        _fail(
            cmd,
            "INVALID_ORIGIN_FLOW",
            f"Invalid --origin value {origin!r}. Must be one of: {valid}",
            {"origin": origin, "valid_values": valid},
        )


def _parse_decision_options_or_fail(cmd: str, options: str | None) -> tuple[str, ...]:
    """Parse ``--options`` (a JSON array string, matching the host CLI's own
    ``cmd_open`` flag shape, ``decision.py``) or ``_fail`` (NoReturn) on
    malformed input.
    """
    if options is None:
        return ()
    try:
        raw = json.loads(options)
    except json.JSONDecodeError as exc:
        _fail(
            cmd,
            "USAGE_ERROR",
            f"--options must be a valid JSON array string, got: {options!r}",
            {"options": options, "parse_error": str(exc)},
        )
    if not isinstance(raw, list):
        _fail(
            cmd,
            "USAGE_ERROR",
            "--options must be a JSON array (list), got a non-list value",
            {"options": options},
        )
    return tuple(str(item) for item in raw)


def _validate_rationale_or_fail(cmd: str, rationale: str) -> None:
    """Reject an empty/whitespace-only ``--rationale`` BEFORE the service
    layer is ever called (WP05-001 review fix).

    Mirrors the host CLI's OWN ``cmd_defer``/``cmd_cancel`` guard verbatim
    (``decision.py:341-348``/``391-398``): identical emptiness check
    (``not rationale.strip()``), identical reused
    ``DecisionErrorCode.MISSING_STEP_OR_SLOT`` code (already registered in
    ``upstream_contract.json`` -- no new code needed), identical
    ``{"field": "rationale"}`` details shape and message text. Pre-fix,
    neither ``defer_decision``/``cancel_decision`` NOR
    ``decisions/service.py``'s own ``_terminal_command`` performed this
    check, so an empty rationale was silently accepted and persisted to the
    ledger on disk -- a live-reproduced behavioural fork from the host CLI
    (WP05 review finding WP05-001).
    """
    if rationale.strip():
        return
    from specify_cli.decisions.models import DecisionErrorCode

    _fail(
        cmd,
        DecisionErrorCode.MISSING_STEP_OR_SLOT.value,
        "--rationale must be a non-empty string",
        {"field": "rationale"},
    )


def open_decision(  # noqa: PLR0913
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    origin: str = typer.Option(..., "--origin", help=_HELP_ORIGIN_FLOW),
    input_key: str = typer.Option(..., "--input-key", help="The input key this decision governs"),
    question: str = typer.Option(..., "--question", help="Human-readable question text"),
    step_id: str = typer.Option(None, "--step-id", help="Interview step identifier"),
    slot_key: str = typer.Option(None, "--slot-key", help="Slot key (use when step_id unavailable)"),
    options: str = typer.Option(None, "--options", help="Candidate answers as a JSON array string"),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Open a new Decision Moment ledger entry, or return idempotently if one
    already exists (FR-006). Wraps ``decisions/service.py.open_decision`` 1:1.
    """
    cmd = "open-decision"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for open-decision")
        return
    _parse_policy_or_fail(cmd, policy)

    origin_flow = _validate_origin_flow_or_fail(cmd, origin)
    parsed_options = _parse_decision_options_or_fail(cmd, options)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.service import open_decision as _svc_open_decision
    from specify_cli.decisions.store import DecisionIndexReadError

    try:
        resp = _svc_open_decision(
            main_repo_root,
            mission,
            origin_flow=origin_flow,
            input_key=input_key,
            question=question,
            options=parsed_options,
            step_id=step_id,
            slot_key=slot_key,
            actor=actor,
        )
    except DecisionError as exc:
        _fail_from_decision_error(cmd, exc)
        return
    except DecisionIndexReadError as exc:
        _fail_decision_index_unreadable(cmd, mission, exc)
        return
    except DecisionEventLogReadError as exc:
        _fail_decision_event_log_unreadable(cmd, mission, exc)
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": "open",
        "idempotent": resp.idempotent,
        "artifact_path": resp.artifact_path,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


def resolve_decision(  # noqa: PLR0913
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    decision_id: str = typer.Option(..., "--decision-id", help=_HELP_DECISION_ID),
    final_answer: str = typer.Option(..., "--final-answer", help="The chosen answer (non-empty)"),
    other_answer: bool = typer.Option(False, "--other-answer", help="True if answer is a write-in"),
    rationale: str = typer.Option(None, "--rationale", help="Explanation of the choice"),
    resolved_by: str = typer.Option(None, "--resolved-by", help=_HELP_RESOLVED_BY),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Resolve a decision with a concrete final answer (FR-007). Wraps
    ``decisions/service.py.resolve_decision`` 1:1.

    Terminal-transition rejection (Edge Cases, spec.md): resolving an
    already-terminal decision with a DIFFERENT outcome/payload is NOT
    pre-checked here -- it is the service layer's own
    ``DecisionError(TERMINAL_CONFLICT)``, propagated verbatim, matching the
    host-CLI ``decision_app resolve`` subcommand's own error code. A
    redundant pre-check here could drift from the service layer's own
    validation.
    """
    cmd = "resolve-decision"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for resolve-decision")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.service import resolve_decision as _svc_resolve_decision
    from specify_cli.decisions.store import DecisionIndexReadError

    try:
        resp = _svc_resolve_decision(
            main_repo_root,
            mission,
            decision_id,
            final_answer=final_answer,
            other_answer=other_answer,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
        )
    except DecisionError as exc:
        _fail_from_decision_error(cmd, exc)
        return
    except DecisionIndexReadError as exc:
        _fail_decision_index_unreadable(cmd, mission, exc)
        return
    except DecisionEventLogReadError as exc:
        _fail_decision_event_log_unreadable(cmd, mission, exc)
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


def defer_decision(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    decision_id: str = typer.Option(..., "--decision-id", help=_HELP_DECISION_ID),
    rationale: str = typer.Option(..., "--rationale", help=_HELP_RATIONALE_REQUIRED),
    resolved_by: str = typer.Option(None, "--resolved-by", help=_HELP_RESOLVED_BY),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Defer a decision for later resolution (FR-008). Wraps
    ``decisions/service.py.defer_decision`` 1:1.
    """
    cmd = "defer-decision"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for defer-decision")
        return
    _parse_policy_or_fail(cmd, policy)
    _validate_rationale_or_fail(cmd, rationale)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.service import defer_decision as _svc_defer_decision
    from specify_cli.decisions.store import DecisionIndexReadError

    try:
        resp = _svc_defer_decision(
            main_repo_root,
            mission,
            decision_id,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
        )
    except DecisionError as exc:
        _fail_from_decision_error(cmd, exc)
        return
    except DecisionIndexReadError as exc:
        _fail_decision_index_unreadable(cmd, mission, exc)
        return
    except DecisionEventLogReadError as exc:
        _fail_decision_event_log_unreadable(cmd, mission, exc)
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


def cancel_decision(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    decision_id: str = typer.Option(..., "--decision-id", help=_HELP_DECISION_ID),
    rationale: str = typer.Option(..., "--rationale", help=_HELP_RATIONALE_REQUIRED),
    resolved_by: str = typer.Option(None, "--resolved-by", help=_HELP_RESOLVED_BY),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Cancel a decision (deemed no longer relevant) (FR-009). Wraps
    ``decisions/service.py.cancel_decision`` 1:1.
    """
    cmd = "cancel-decision"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for cancel-decision")
        return
    _parse_policy_or_fail(cmd, policy)
    _validate_rationale_or_fail(cmd, rationale)

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.service import cancel_decision as _svc_cancel_decision
    from specify_cli.decisions.store import DecisionIndexReadError

    try:
        resp = _svc_cancel_decision(
            main_repo_root,
            mission,
            decision_id,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
        )
    except DecisionError as exc:
        _fail_from_decision_error(cmd, exc)
        return
    except DecisionIndexReadError as exc:
        _fail_decision_index_unreadable(cmd, mission, exc)
        return
    except DecisionEventLogReadError as exc:
        _fail_decision_event_log_unreadable(cmd, mission, exc)
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


# ---------------------------------------------------------------------------
# Command: answer-decision (WP08, FR-013, Mechanism B, full event/lifecycle
# parity)
#
# Resolves a ``spec-kitty next`` control-loop ``decision_required`` moment (a
# blocking ``AuditStep`` checkpoint OR a ``PromptStep`` with an unmet
# ``requires_inputs`` entry) -- the run-snapshot's ``pending_decisions`` map
# (``_internal_runtime.engine._read_snapshot``), distinct from the
# ``decisions/index.json`` ledger the four verbs above operate on (Mechanism
# A, spec Clarification 3). Matches exactly what the real CLI invocation
# ``spec-kitty next --answer <value> --decision-id <id> --agent <name>
# --result <success|failed|blocked>`` does in one pass (``next_cmd.py:
# 213-269``), never just the two engine calls:
#
#   1. ``runtime_bridge.answer_decision_via_runtime`` persists the answer
#      against the (auto-resolved or explicit) ``decision_id``.
#   2. ``pair_previous_lifecycle_record`` pairs the previous issuance's
#      ``started`` lifecycle record BEFORE the DAG advances.
#   3. ``decide_next`` (the ENGINE call, ``runtime.next.decision``, NOT part
#      of WP02's seam) advances the DAG using THIS call's own ``--result``.
#   4. ``emit_mission_next_invoked`` appends a ``MissionNextInvoked`` entry
#      to the mission event log.
#   5. ``write_issuance_lifecycle_record`` writes a new issuance ``started``
#      record. Called unconditionally, exactly like the host CLI -- the
#      function itself self-no-ops when the resulting ``decision.kind`` is
#      not ``"step"``, so the predicate lives in the seam, not in this caller.
#
# Per operator ruling SPEC-FRESH2-001 (``kitty-specs/design-phase-
# orchestrator-api-01M1HE6M/reviews/spec.ruling.md``), steps 2/4/5 are
# REQUIRED, reached EXCLUSIVELY through WP02's extracted seam
# (``runtime.next.next_invocation_lifecycle``) -- never inlined, never
# reimplemented here. A verb performing only steps 1+3 (the two engine
# calls) is precisely the silent-success regression the ruling exists to
# prevent (SC-007/SC-008).
#
# Response shape: ``data`` is ``Decision.to_dict()`` from step 3 (byte-
# identical, field-for-field, to ``next --answer ... --json``) PLUS one
# sibling field, ``answered_decision_id`` (the ``decision_id`` persisted by
# step 1) -- ``answer-decision``'s own self-documenting name for the CLI's
# terser ``answered`` key. ``data`` carries NO ``answer`` key: the CLI's
# second extra key (the echoed submitted answer, the ``d["answer"] = answer``
# assignment inside ``next_cmd.py``'s ``_print_decision``) is intentionally
# OMITTED per SPEC-FRESH2-002's resolution -- the host already possesses the
# value it submitted in its own request.
#
# FR-012 does NOT apply here (spec Acceptance Scenario 6): this mechanism
# operates on the run-snapshot, not ``decisions/index.json`` -- a mission
# whose current phase has no ``OriginFlow`` member (``tasks``, ``analyze``)
# can still have a pending ``decision_required`` moment, and this verb
# resolves it normally. Do NOT apply the ``INVALID_ORIGIN_FLOW`` guard here.
# ---------------------------------------------------------------------------

_HELP_ANSWER_AGENT = "Agent/actor identity performing this call (required)"
_HELP_ANSWER_VALUE = "The answer value to persist for the pending decision"
_HELP_ANSWER_RESULT = "Outcome of the current issuance: success | failed | blocked (required alongside --answer)"
_HELP_ANSWER_DECISION_ID = "Run-snapshot pending decision id to answer (auto-resolved when omitted and exactly one decision is pending)"

# Single canonical source, shared with the host CLI's own
# ``next_cmd._VALID_RESULTS`` (``next_cmd.py:51``) and mirroring
# ``runtime.next._internal_runtime.engine.ResultType``: both CLI-facing
# validators import ``VALID_RESULT_VALUES`` from ``runtime.next.decision``
# instead of each keeping an independent literal copy (fold-in review
# finding: this was previously a THIRD independent copy of the same enum).
_VALID_ANSWER_RESULTS: tuple[str, ...] = VALID_RESULT_VALUES


def _validate_answer_result_or_fail(cmd: str, result: str) -> None:
    """Reject a ``--result`` value outside {success, failed, blocked}
    (WP08-001 fold-in review fix, severity 3).

    Mirrors the host CLI's own ``_validate_result_and_answer`` guard
    (``next_cmd.py:610-613``) verbatim: identical condition
    (``result not in _VALID_RESULTS``), identical message shape
    (``"--result must be one of {...}, got '{result}'"``), and identical
    POSITION in the call sequence -- called AFTER the mission-existence gate
    (``_resolve_mission_dir_or_fail``, this verb's analogue of the host
    CLI's ``_resolve_mission_slug``) but BEFORE any decision
    resolution/auto-resolve or persistence (``get_or_start_run``,
    ``_read_snapshot``, ``answer_decision_via_runtime``,
    ``pair_previous_lifecycle_record``, ``decide_next``) -- exactly where
    the host CLI's own ``_validate_result_and_answer`` runs relative to
    ``_maybe_handle_answer``/``_handle_answer`` (``next_step``,
    ``next_cmd.py:195-220``). Pre-fix, an invalid ``--result`` fell through
    to whatever the decision-resolution logic produced (e.g.
    ``NO_PENDING_DECISION`` for a mission with no pending decision) instead
    of being rejected outright -- silently advancing the DAG when a pending
    decision DID exist, with the garbage value persisted into the lifecycle
    record's ``reason`` field by ``pair_previous_lifecycle_record``.

    A DIFFERENT dedicated error_code than the host CLI's own check (which
    is untyped -- a bare stderr print, no error_code at all): matches this
    module's own precedent (``INVALID_ORIGIN_FLOW`` vs. the host CLI's
    reused ``DecisionErrorCode.MISSING_STEP_OR_SLOT`` for ``--flow``) of
    minting a dedicated, typed code for an orchestrator-api-specific
    validation surface rather than propagating an untyped CLI print.
    """
    if result in _VALID_ANSWER_RESULTS:
        return
    _fail(
        cmd,
        "INVALID_RESULT",
        f"--result must be one of {_VALID_ANSWER_RESULTS}, got '{result}'",
        {"result": result, "valid_values": list(_VALID_ANSWER_RESULTS)},
    )


def answer_decision(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    agent: str = typer.Option(..., "--agent", help=_HELP_ANSWER_AGENT),
    answer: str = typer.Option(..., "--answer", help=_HELP_ANSWER_VALUE),
    result: str = typer.Option(None, "--result", help=_HELP_ANSWER_RESULT),
    decision_id: str = typer.Option(None, "--decision-id", help=_HELP_ANSWER_DECISION_ID),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Resolve a ``spec-kitty next`` ``decision_required`` moment (FR-013,
    Mechanism B) with full CLI event/lifecycle-log parity (FR-014, operator
    ruling SPEC-FRESH2-001). See the module comment block above this
    function for the full five-step composite and the response-shape
    contract.
    """
    cmd = "answer-decision"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for answer-decision")
        return
    _parse_policy_or_fail(cmd, policy)

    if result is None:
        _fail(
            cmd,
            "RESULT_REQUIRED",
            "--result is required alongside --answer for answer-decision",
        )
        return

    main_repo_root = _common._get_main_repo_root()
    # Existence gate FIRST via the coord-aware read seam (consistent
    # MISSION_NOT_FOUND envelope shared with every other read/write endpoint
    # in this module) -- the runtime resolution below is only reached for a
    # mission already known to exist.
    _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    # WP08-001: --result enum validation runs HERE -- after the
    # mission-existence gate above (this verb's analogue of the host CLI's
    # ``_resolve_mission_slug``), but BEFORE any decision resolution or
    # persistence below (mirrors ``next_cmd.py``'s own ordering: mission
    # resolution -> ``_validate_result_and_answer`` -> ``_maybe_handle_
    # answer``). See ``_validate_answer_result_or_fail``'s docstring.
    _validate_answer_result_or_fail(cmd, result)

    from mission_runtime import MissionArtifactKind as _MissionArtifactKind
    from mission_runtime import placement_seam as _placement_seam
    from runtime.next.decision import decide_next
    from runtime.next.next_invocation_lifecycle import (
        AmbiguousPendingDecisionError,
        NoPendingDecisionError,
        emit_mission_next_invoked,
        pair_previous_lifecycle_record,
        resolve_pending_decision_id,
        write_issuance_lifecycle_record,
    )
    from runtime.next.runtime_bridge import answer_decision_via_runtime, get_or_start_run
    from runtime.next.runtime_bridge_engine import _read_snapshot
    from specify_cli.mission import get_mission_type

    # Mirrors ``next_cmd.py``'s ``_handle_answer`` exactly: the
    # PRIMARY-partition read (never the coord-only husk) so ``mission_type``
    # comes from the real ``meta.json``.
    feature_dir = _placement_seam(main_repo_root, mission).read_dir(_MissionArtifactKind.PRIMARY_METADATA)
    mission_type = get_mission_type(feature_dir)
    run_ref = get_or_start_run(mission, main_repo_root, mission_type)
    run_dir = Path(run_ref.run_dir)

    if decision_id is None:
        # Auto-resolve through the ONE shared seam (PR-BOUNDARY-001):
        # ``runtime.next.next_invocation_lifecycle.resolve_pending_decision_id``
        # is the same zero/one/many branch ``next_cmd.py``'s ``_handle_answer``
        # now also calls -- no more independently-maintained duplicate here.
        try:
            resolved_decision_id = resolve_pending_decision_id(run_dir, None)
        except NoPendingDecisionError as exc:
            _fail(cmd, "NO_PENDING_DECISION", str(exc))
            return
        except AmbiguousPendingDecisionError as exc:
            _fail(
                cmd,
                "AMBIGUOUS_PENDING_DECISION",
                str(exc),
                {"pending_decision_ids": exc.pending_ids},
            )
            return
    else:
        # An explicit --decision-id not currently pending (already answered,
        # or naming a different step) must never be silently no-op'd or
        # answer the wrong decision. Orchestrator-api-only guard (the host
        # CLI's own ``_handle_answer`` performs no equivalent check) -- reads
        # via the same ``runtime_bridge_engine`` concentration seam as the
        # auto-resolve path above, never ``_internal_runtime.engine`` directly.
        resolved_decision_id = decision_id
        snapshot = _read_snapshot(run_dir)
        if resolved_decision_id not in snapshot.pending_decisions:
            _fail(
                cmd,
                "DECISION_NOT_PENDING",
                f"Decision {resolved_decision_id!r} is not currently pending for mission {mission!r}",
                {"decision_id": resolved_decision_id},
            )
            return

    # --- Step 1: persist the answer. ---
    answer_decision_via_runtime(mission, resolved_decision_id, answer, agent, main_repo_root)

    # --- Step 2 (WP02 seam, REQUIRED, BEFORE the DAG advances): pair the
    # previous issuance's `started` lifecycle record. ---
    pair_previous_lifecycle_record(agent, mission, result, main_repo_root)

    # --- Step 3 (ENGINE call, NOT part of WP02's seam): advance the DAG. ---
    decision = decide_next(agent, mission, result, main_repo_root)

    # --- Step 4 (WP02 seam, REQUIRED, AFTER decide_next returns): emit the
    # mission event log entry. ---
    emit_mission_next_invoked(agent, result, mission, main_repo_root, decision)

    # --- Step 5 (WP02 seam, REQUIRED): write the new issuance lifecycle
    # record. Called unconditionally, exactly like the host CLI
    # (``next_cmd.py:262``) -- ``write_issuance_lifecycle_record`` itself
    # self-no-ops on a non-"step" decision (``next_invocation_lifecycle.py``,
    # the ``kind != "step"`` guard near its top), so the predicate belongs to
    # the seam, not to each caller. ---
    write_issuance_lifecycle_record(agent, mission, main_repo_root, decision)

    data = decision.to_dict()
    # Sibling field (SPEC-FRESH2-002): the persisted-answer confirmation,
    # self-documenting per this repo's own curated-field-name convention --
    # never a substitute for the full Decision.to_dict() shape above, and
    # deliberately NOT the CLI's terser `answered` key. No `answer` echo key
    # is set here (the host already possesses the value it submitted).
    data["answered_decision_id"] = resolved_decision_id
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)
