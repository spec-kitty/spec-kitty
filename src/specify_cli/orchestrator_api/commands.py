"""Machine-contract API commands for external orchestrators.

All commands emit a single JSON object to stdout via the canonical envelope.
Non-zero exit on any failure. Output is always JSON (no prose mode).

Error codes used:
  USAGE_ERROR                 -- CLI parse/usage error (missing required arg, bad option, etc.)
  POLICY_METADATA_REQUIRED    -- --policy missing on a run-affecting command
  POLICY_VALIDATION_FAILED    -- policy JSON invalid or contains secrets
  INVALID_MISSION             -- #2879: --mission value is not a safe path segment
                                 (traversal guard: '..', separators, leading dot,
                                 non-ASCII) — JSON envelope, never a raw traceback
  MISSION_NOT_FOUND           -- mission slug does not resolve to a kitty-specs dir
  STATUS_READ_PATH_NOT_FOUND  -- coord topology with a stale/unaddressable primary surface
                                 (fail-closed read-path guard fired; carries coord/primary candidates)
  WP_NOT_FOUND                -- WP ID does not exist in the mission
  TRANSITION_REJECTED         -- transition not allowed by state machine
  WP_ALREADY_CLAIMED          -- WP claimed by a different actor
  MISSION_NOT_READY           -- not all WPs approved/done (for accept-mission)
  HISTORY_COMMIT_FAILED       -- append-history could not create its commit
  PLACEMENT_RESOLUTION_REQUIRED -- append-history's write placement could not be
                                 resolved (D11 fail-closed; FR-004 -- never a
                                 silent current-branch fallback)
  SAFE_COMMIT_*               -- structured safe_commit refusal/failure
  PREFLIGHT_FAILED            -- preflight checks failed (for merge-mission)
  CONTRACT_VERSION_MISMATCH   -- provider version is below MIN_PROVIDER_VERSION
  UNSUPPORTED_STRATEGY        -- merge strategy not implemented
  ANCESTRY_NOT_ESTABLISHED    -- #3281/FR-007: the recorded planning commit or an
                                 approved dependency lane's tip is not (yet) a git
                                 ancestor of the claimed workspace's HEAD, even
                                 after self-heal re-ran the reuse-path merges
  MISSION_ALREADY_EXISTS      -- specify: the delegate mission-creation call
                                 failed with its own typed duplicate signal
                                 (MissionAlreadyExistsError, #3861)
  MISSION_CREATE_FAILED       -- specify: mission creation failed for a reason
                                 other than a typed duplicate signal (WP03)
  PLAN_SETUP_FAILED           -- plan: the delegate plan-scaffold call failed and
                                 carried no more specific error_code of its own (WP03)
  TASKS_FINALIZE_FAILED       -- tasks: the delegate finalize-tasks call failed and
                                 carried no more specific error_code of its own (WP03)
  CHECK_PREREQUISITES_FAILED  -- check-prerequisites: the delegate validation call
                                 failed and carried no more specific error_code of
                                 its own (WP04)
  RECORD_ANALYSIS_EMPTY_BODY  -- record-analysis: --input-file/stdin body was empty
                                 (WP04)
  RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND -- record-analysis: --input-file could not
                                 be read (WP04)
  RECORD_ANALYSIS_MALFORMED_CARRIER -- record-analysis: the submitted body carried
                                 a present-but-invalid analysis-findings/v1 carrier
                                 (WP04)
  RECORD_ANALYSIS_WRITE_NOT_CONFIRMED -- record-analysis: no analysis-report.md
                                 generated AFTER this call's start timestamp was
                                 found on disk -- the write did not happen (or could
                                 not be confirmed), regardless of the underlying
                                 call's own return/raise/hang behavior (NFR-004 /
                                 SK-93 / WP04)
  RECORD_ANALYSIS_VERDICT_UNRELIABLE -- record-analysis: a write WAS confirmed
                                 (fresh generated_at) but the re-read verdict is not
                                 a trustworthy match for this call -- either it
                                 diverges from the submitted verdict, or the
                                 submitted verdict was itself `unknown` (no valid
                                 carrier); `unknown` is NEVER reported as success
                                 (SK-06 / #3133 / WP04)
  DIRTY_WORKTREE               -- record-analysis: pre-existing uncommitted changes
                                 block the write (classified from the delegate
                                 preflight's own structured payload; WP04)
  INVALID_ORIGIN_FLOW          -- open-decision: FR-012 scope guard -- --origin is
                                 outside {charter, specify, plan}, rejected BEFORE
                                 the decisions/service.py layer is ever called (WP05)
  DECISION_MISSING_STEP_OR_SLOT -- open-decision: neither --step-id nor --slot-key
                                 supplied (propagated verbatim from
                                 decisions/service.py's DecisionError; WP05)
  DECISION_ALREADY_CLOSED      -- open-decision: a matching logical-key entry
                                 already exists in a terminal state (propagated
                                 verbatim from DecisionError; WP05)
  DECISION_NOT_FOUND           -- resolve/defer/cancel-decision: --decision-id is
                                 not present in the mission's ledger (propagated
                                 verbatim from DecisionError; WP05)
  DECISION_TERMINAL_CONFLICT   -- resolve/defer/cancel-decision: the decision is
                                 already terminal with a DIFFERENT outcome/payload
                                 than requested -- the terminal-transition rejection
                                 (propagated verbatim from DecisionError, same code
                                 the host-CLI ``decision_app`` subcommands raise for
                                 this case; WP05)
  DECISION_EVENT_REPAIR_FAILED -- open-decision (idempotent-open path): the missing
                                 DecisionPointOpened event could not be re-emitted
                                 (propagated verbatim from DecisionError; WP05)
  DESIGN_STATUS_EVENT_LOG_UNREADABLE -- design-status: status.events.jsonl could
                                 not be read cleanly (a torn/truncated line --
                                 ledger SK-131) while deriving the tasks/-finalized
                                 signal; NEVER silently reported as "not finalized"
                                 (WP06). ALSO emitted, verbatim, by open/resolve/
                                 defer/cancel-decision when decisions/index.json
                                 itself exists but is corrupt (malformed JSON,
                                 non-UTF-8, or schema-invalid) -- the SAME
                                 ``DecisionIndexReadError`` design-status already
                                 fails closed on (#4642), reused here rather than
                                 registering a second contract code for the
                                 identical failure shape (see
                                 ``_fail_decision_index_unreadable``).
  RESULT_REQUIRED              -- answer-decision: --result is required alongside
                                 --answer (WP08)
  INVALID_RESULT                -- answer-decision: --result is not one of the host
                                 CLI's {success, failed, blocked} enum
                                 (next_cmd.py:53,610-613), rejected BEFORE decision
                                 resolution/persistence -- mirrors the host CLI's
                                 own ``_validate_result_and_answer`` verbatim,
                                 including its call-sequence position
                                 (WP08-001 fold-in fix)
  NO_PENDING_DECISION          -- answer-decision: no run-snapshot pending_decisions
                                 entry exists to answer (WP08)
  AMBIGUOUS_PENDING_DECISION   -- answer-decision: more than one pending decision
                                 and --decision-id was omitted (WP08)
  DECISION_NOT_PENDING         -- answer-decision: --decision-id does not match any
                                 entry in the current run's pending_decisions (WP08)
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import threading
import uuid
from kernel.clock import now_utc_iso, now_utc_stamp
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NoReturn, cast

if TYPE_CHECKING:
    from specify_cli.analysis_report import AnalysisReportResult
    from specify_cli.core.paths import RetentionDecision
    from specify_cli.decisions.models import OriginFlow
    from specify_cli.decisions.service import DecisionError, DecisionEventLogReadError
    from specify_cli.decisions.store import DecisionIndexReadError
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.status import StatusSnapshot

import typer

from mission_runtime import CommitTarget, MissionTopology
from runtime.next.decision import VALID_RESULT_VALUES
from specify_cli.core.contract_gate import is_allowed_error_code, validate_outbound_payload
from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.status import wp_state_for
from specify_cli.status import Lane
from specify_cli.status import ReviewResult
from specify_cli.status import parse_review_result_json

from .envelope import (
    CONTRACT_VERSION,
    MIN_PROVIDER_VERSION,
    make_envelope,
    parse_and_validate_policy,
    policy_to_dict,
)

import click
from typer import core as typer_core
from typer.core import TyperGroup

# Typer 0.26+ vendors click as ``typer._click``; exceptions raised by that copy
# are distinct classes from the standalone ``click`` package's, so every catch
# below must name both.  The vendored module's surface is itself a moving
# target: 0.26.x exposed ``exceptions.Abort``/``exceptions.Exit``, while 0.27.x
# exposes only ``exceptions.UsageError`` and raises typer's own public
# ``typer.Abort``/``typer.Exit`` instead (spec-kitty#713).  Every class is
# therefore resolved with ``getattr`` and a ``None`` default — never as an
# eagerly evaluated default expression such as ``getattr(m, "Abort",
# m.exceptions.Abort)``, which raised ``AttributeError`` at import time — and
# typer's stable public ``typer.Abort``/``typer.Exit`` are always included.


def _vendored_click_exception(name: str) -> type[BaseException] | None:
    """Return ``typer._click``'s exception class ``name``, or ``None`` if absent.

    Looks in the vendored ``exceptions`` submodule first, then the package
    root, and never touches an attribute it has not confirmed exists.
    """
    module = getattr(typer_core, "_click", None)
    if module is None:
        return None
    for holder in (getattr(module, "exceptions", None), module):
        candidate = getattr(holder, name, None) if holder is not None else None
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            return candidate
    return None


def _exception_classes(*candidates: type[BaseException] | None) -> tuple[type[BaseException], ...]:
    """Deduplicate ``candidates`` into an ``except``-clause tuple, dropping ``None``."""
    classes: list[type[BaseException]] = []
    for candidate in candidates:
        if candidate is not None and candidate not in classes:
            classes.append(candidate)
    return tuple(classes)


_CLICK_USAGE_ERRORS = _exception_classes(click.UsageError, _vendored_click_exception("UsageError"))
_CLICK_ABORTS = _exception_classes(click.Abort, typer.Abort, _vendored_click_exception("Abort"))
# ``typer.Exit`` is click's ``Exit`` on typer <= 0.25 and typer's own class on
# >= 0.26, so it covers the standalone-click spelling in both eras (TID251).
_EXIT = _exception_classes(typer.Exit, _vendored_click_exception("Exit"))


class _JSONErrorGroup(TyperGroup):
    """Click Group that guarantees JSON envelopes for all error paths.

    The orchestrator-api contract requires *every* stdout emission to be a
    single JSON envelope, including parser-level failures (missing required
    args, unknown options, etc.).  Three overrides cooperate to cover every
    dispatch path:

    ``make_context(info_name, args, parent, **extra)``
        Catches errors during *group-level argument parsing* when nested.
        When the parent group calls ``make_context()`` on this sub-group
        (e.g. ``orchestrator-api --bogus``), the error would otherwise
        propagate to the parent's ``BannerGroup``.  This is the outermost
        catch for the nested path.

    ``invoke(ctx)``
        Catches errors during *subcommand dispatch*.  When this group is
        registered as a sub-group of the root CLI via ``add_typer()``, Click
        dispatches through ``invoke()``, not ``main()``.  Without this
        override the root ``BannerGroup`` would format the error as prose.

    ``main(*args, **kwargs)``
        Catches errors during *direct invocation* and group-level argument
        parsing (e.g. ``orchestrator-api --unknown-flag``).  Uses
        ``standalone_mode=False`` so ``click.UsageError`` propagates as an
        exception rather than being printed as plain text.

    Interaction: when both paths are active (direct invocation), a subcommand
    error is caught by ``invoke()`` first, which calls ``ctx.exit(2)``
    (raising ``SystemExit(2)``).  ``main()`` passes ``SystemExit`` through
    via ``except SystemExit: raise``, so no double emission occurs.
    """

    def _emit_error(self, message: str) -> None:
        """Emit a USAGE_ERROR JSON envelope to stdout."""
        _emit(
            make_envelope(
                command="unknown",
                success=False,
                data={"message": message},
                error_code="USAGE_ERROR",
            )
        )

    def make_context(self, info_name, args, parent=None, **extra):
        """Catch group-level parse errors when nested (e.g. orchestrator-api --bogus).

        When nested as a sub-group, the parent's invoke() calls
        make_context() on this group to parse its own arguments.  Errors
        here would propagate to the parent's BannerGroup, producing prose.
        """
        try:
            return super().make_context(info_name, args, parent=parent, **extra)
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            raise SystemExit(2) from exc

    def invoke(self, ctx):
        """Catch errors during subcommand dispatch (nested invocation path).

        When this group is registered as a sub-group of the root CLI via
        add_typer(), Click dispatches to invoke(), not main(). This override
        ensures parse/usage errors produce JSON envelopes even when the root
        CLI's BannerGroup would otherwise emit prose.
        """
        try:
            return super().invoke(ctx)
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            ctx.exit(2)
        except _CLICK_ABORTS:
            self._emit_error("Command aborted")
            ctx.exit(2)

    def main(self, *args, standalone_mode: bool = True, **kwargs):  # type: ignore[override]
        try:
            rv = super().main(*args, standalone_mode=False, **kwargs)
            # With standalone_mode=False, typer.Exit(code) is caught by
            # Typer's _main() and returned as an integer.  Re-raise it so
            # that CliRunner (and real invocations) see the correct exit code.
            if isinstance(rv, int) and rv != 0:
                raise SystemExit(rv)
            return rv
        except _CLICK_USAGE_ERRORS as exc:
            self._emit_error(exc.format_message())
            raise SystemExit(2) from exc
        except _CLICK_ABORTS:
            self._emit_error("Command aborted")
            raise SystemExit(2)
        except _EXIT as exc:
            raise SystemExit(exc.exit_code) from exc
        except SystemExit:
            raise


# The public ``app`` used by the main CLI to register orchestrator-api.
# Uses _JSONErrorGroup so that Click/Typer parse errors become JSON envelopes.
app = typer.Typer(
    name="orchestrator-api",
    help="Machine-contract API for external orchestrators (JSON-first)",
    no_args_is_help=False,
    cls=_JSONErrorGroup,
)

# Boy Scout (DIRECTIVE_025): deduplicated CLI help strings.
_HELP_MISSION_SLUG = "Mission slug"
# Deduplicated genuine-not-found message (Sonar S1192: emitted by 8 endpoints).
_MISSION_NOT_FOUND_MESSAGE = "Mission '{mission}' not found in kitty-specs/"
_HELP_WP_ID = "Work package ID"
_HELP_ACTOR = "Actor identity"
_HELP_POLICY = "Policy metadata JSON (required)"
_HELP_ANALYZER_AGENT = "Agent name that produced the analysis report"

# WP04 / NFR-004 / SK-93: the enforced wall-clock bound record-analysis's
# underlying write path (write_analysis_report + the best-effort commit) is
# run under -- Thread.join(timeout=...) actually returns control to the
# caller even if the worker thread is still running (a REAL bound; see
# `_run_write_with_timeout`). Module-level so tests can monkeypatch it down
# for a fast, genuine hang proof (T020).
_RECORD_ANALYSIS_TIMEOUT_SECONDS = 10.0


def _transition_requires_policy(lane: str) -> bool:
    """Return True if transitioning to *lane* requires ``--policy`` metadata.

    A transition requires policy when the target's WPState is neither terminal,
    blocked, nor not-yet-started — i.e. claimed/in_progress/for_review/in_review/
    approved. Note this is intentionally NARROWER than ``WPState.is_run_affecting``
    (which also counts ``planned`` as active): a transition to ``planned`` does not
    require policy. The two are distinct concepts despite the historical shared name
    (#1775 review FSM-7); do not collapse them.
    """
    state = wp_state_for(lane)
    return state.progress_bucket() not in ("not_started", "terminal") and not state.is_blocked


@dataclass
class _MergePreflightResult:
    target_branch: str
    errors: list[str]


def _emit(envelope: dict) -> None:
    """Print canonical JSON envelope to stdout."""
    print(json.dumps(envelope))


def _fail(command: str, error_code: str, message: str, data: dict | None = None) -> NoReturn:
    """Print failure envelope and exit non-zero.

    Typed ``NoReturn`` (FR-004 / S5747): this always raises ``typer.Exit``, so
    mypy proves any code after a ``_fail(...)`` call is unreachable — callers
    need no sentinel ``raise`` to satisfy their return type.
    """
    # #3548 (fail-loud / silent-drop, epics #3410/#3549): the retired
    # ``data or {"message": message}`` expression DROPPED the human-readable
    # ``message`` whenever a caller passed truthy structured ``data`` — silencing
    # 16 of 33 call sites, preferentially the most actionable errors. Merge the
    # explanation INTO the payload so BOTH reach the operator; ``message`` (the
    # param, the canonical explanation) is guaranteed present and last-wins over
    # any caller-supplied ``data["message"]``. The two callers that seed their own
    # ``data["message"]`` (the read-path seam, and the LANE_ALLOCATION_FAILED site
    # via ``StructuredError.to_dict()``) both pass the identical ``str(exc)`` the
    # param already carries, so param-wins never destroys distinct information — it
    # only guarantees the explanation is never dropped. The structured
    # ``data["error_code"]`` those callers carry is untouched (NFR-003).
    payload = {**(data or {}), "message": message}
    envelope = make_envelope(
        command=command,
        success=False,
        data=payload,
        error_code=error_code,
    )
    _emit(envelope)
    raise typer.Exit(1)


def _fail_wp_not_found(cmd: str, wp: str, mission: str) -> NoReturn:
    """The ONE ``WP_NOT_FOUND`` emission (S1192 5×; locks error-surface parity)."""
    _fail(cmd, "WP_NOT_FOUND", f"Work package '{wp}' not found in {mission}")


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


#: Fallback code for a :class:`DestructiveOpRefused` whose real
#: ``error_code`` (``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` /
#: ``MERGE_UNSAFE_PRIMARY_DIRTY`` / ``MERGE_UNSAFE_WORKTREE_DIRTY``) is not
#: (yet) registered in ``upstream_contract.json``'s ``allowed_error_codes`` --
#: that file is a derived artifact of the upstream ``spec-kitty-events`` /
#: ``spec-kitty-saas`` contract (client-repo inversion) and is not this
#: mission's to extend. Reuses the already-registered code this same command
#: emits for every OTHER merge preflight refusal, so the envelope shape stays
#: within contract while the real code survives as diagnostic ``data``
#: (mirrors ``_fail_from_decision_error``'s ``_DECISION_UNREGISTERED_CODE_FALLBACK``
#: pattern -- never a silently-dropped, never a leaked-unregistered code).
_DESTRUCTIVE_OP_REFUSED_FALLBACK = "PREFLIGHT_FAILED"


def _fail_from_destructive_op_refused(cmd: str, mission_dir: Path, target_branch: str, exc: DestructiveOpRefused) -> NoReturn:
    """Envelope a :class:`DestructiveOpRefused` refusal instead of letting it
    escape as a raw traceback (#4753 finding B).

    ``merge_mission`` previously caught ONLY ``RuntimeError`` around
    ``_execute_lane_merge`` -- but the pre-mutation safety preflight
    (``guarded_worktree_remove`` / ``assert_worktree_clean``, reached through
    ``_apply_lane_merge_cleanup``) raises ``DestructiveOpRefused``, a plain
    ``Exception`` subclass (C-002: deliberately NOT a ``RuntimeError``, so it
    is never conflated with ``SafeCommitHeadMismatch``). That refusal is
    exactly the module's own destructive-op safety mechanism doing its job --
    it must reach the external orchestrator as a structured failure envelope,
    not a broken JSON-first contract.
    """
    real_code = exc.error_code
    envelope_code = real_code if is_allowed_error_code("orchestrator_api", real_code) else _DESTRUCTIVE_OP_REFUSED_FALLBACK
    data: dict[str, object] = {
        **_mission_identity_payload(mission_dir),
        "target_branch": target_branch,
        "errors": [str(exc)],
        "destructive_op_error_code": real_code,
        "remediation": exc.remediation,
    }
    if exc.worktree_path is not None:
        data["worktree_path"] = str(exc.worktree_path)
    if exc.dirty_entries:
        data["dirty_entries"] = list(exc.dirty_entries)
    _fail(cmd, envelope_code, "Merge refused: destructive operation safety check failed", data)


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


def _parse_policy_or_fail(cmd: str, policy: str) -> dict:
    """Parse+validate a ``--policy`` JSON string, or ``_fail`` (NoReturn) on invalid JSON.

    The ONE ``POLICY_VALIDATION_FAILED`` emission (WP03/#3281 campsite): before
    this extraction, ``start_implementation``'s required-policy parse and
    ``transition``'s two (required + optional) policy-parse blocks each
    duplicated the identical try/``parse_and_validate_policy``/except/``_fail``
    shape. Folding them into one call keeps ``transition`` at its pre-WP03
    complexity (14) after this WP adds the post-materialize ancestry gate,
    rather than pushing it over the Sonar S3776/Ruff C901 ceiling of 15.
    """
    try:
        policy_obj = parse_and_validate_policy(policy)
    except ValueError as exc:
        _fail(cmd, "POLICY_VALIDATION_FAILED", str(exc))
    return policy_to_dict(policy_obj)


def _get_main_repo_root() -> Path:
    """Resolve main repository root from current working directory."""
    from specify_cli.core.paths import get_main_repo_root, locate_project_root

    cwd = Path.cwd()
    root = locate_project_root(cwd)
    if root is None:
        # Fall back to canonical resolver for worktree-aware behavior.
        return get_main_repo_root(cwd)
    return root


def _resolve_mission_dir(main_repo_root: Path, mission_slug: str) -> Path | None:
    """Return the coord-aware mission status directory if it exists, else None.

    For modern missions (coord-branch topology), returns the coordination
    worktree path. For legacy missions, returns the primary checkout path.
    Falls back to ``None`` only when the mission genuinely does not exist.

    This is now a thin consumer of the ONE guarded read-side seam
    :func:`resolve_handle_to_read_path` (WP01 / IC-01 / NFR-004): the seam owns
    the prototype cascade this endpoint pioneered — ``assert_safe_path_segment``
    → primary-``meta.json`` probe → the single sanctioned ``resolve_declared_mid8``
    cascade (NFR-005) → fail-closed coord-declared gate → the existence-gated
    :func:`resolve_mission_read_path`. The orchestrator's old inline duplicate of
    that cascade is GONE; only this ``.exists() → None`` adapter (the endpoint's
    own "absent ⇒ None, not a path" contract) remains here.

    Read-path SAFETY (FR-011 / M3, #2016) and the M5 fail-closed semantics are
    UNCHANGED — they are exactly the seam's invariants (the seam was lifted from
    this very prototype). ``require_exists`` is left at its default ``False`` so
    the seam returns the best-known candidate; this adapter decides absence by a
    single ``.exists()`` stat, preserving the historical ``Path | None`` contract.

    Typed-error fidelity (FR-001 / M2): :class:`StatusReadPathNotFound` from the
    seam's fail-closed gate is NOT caught here — it propagates so the calling
    endpoint surfaces the resolver's typed ``error_code`` (+ ``coord_candidate`` /
    ``primary_candidate``) instead of flattening every miss to
    ``MISSION_NOT_FOUND``.
    """
    from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

    mission_dir = resolve_handle_to_read_path(main_repo_root, mission_slug)
    return mission_dir if mission_dir.exists() else None


def _resolve_mission_dir_or_fail(command: str, main_repo_root: Path, mission_slug: str) -> Path:
    """Resolve the mission status dir, emitting the correct failure envelope on a miss.

    PR-BOUNDARY-002: this is the ONE seam every mission-scoped
    orchestrator-api endpoint routes through to resolve an EXISTING
    mission's directory -- reads and MUTATING verbs alike
    (``record-analysis``, ``open-decision``/``resolve-decision``/
    ``defer-decision``/``cancel-decision``/``answer-decision``), not only
    reads. Deliberately NOT documented as a call-site count: a hardcoded
    number in this docstring has drifted twice already (an original "all 8
    read endpoints" framing, both undercounted and miscategorized once this
    mission added mutating call sites; then a "17 call sites" snapshot whose
    own suggested verification grep matched its own quoted example text and
    undercounted the true count by one). The invariant that matters is
    structural, not numeric, and is asserted directly -- re-derived from the
    live AST on every run, so it cannot silently drift the way a number in
    prose does -- by
    ``tests/specify_cli/orchestrator_api/test_resolve_mission_dir_or_fail_invariant.py``:
    every mission-scoped endpoint routes through this ONE seam, avoiding one
    divergent existence-resolution pattern per call site:

    * a typed :class:`StatusReadPathNotFound` (coord topology + stale/unaddressable
      primary) surfaces the resolver's real ``error_code`` plus the
      ``coord_candidate`` / ``primary_candidate`` paths — the M2 fidelity fix; the
      external envelope *shape* is unchanged, only the code/data fidelity is raised
      (C-IC02 applied to the external surface).
    * a genuine absence (no such mission, no coord topology) keeps the historical
      ``MISSION_NOT_FOUND`` envelope.

    ``_fail`` is typed ``NoReturn`` (always raises ``typer.Exit``), so mypy proves
    the post-call paths unreachable — no sentinel ``raise`` is needed to satisfy
    the ``Path`` return type.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        mission_dir = _resolve_mission_dir(main_repo_root, mission_slug)
    except StatusReadPathNotFound as exc:
        _fail(
            command,
            exc.error_code,
            str(exc),
            data={
                "message": str(exc),
                "mission_slug": exc.mission_slug,
                "mid8": exc.mid8,
                "coord_candidate": str(exc.coord_candidate),
                "primary_candidate": str(exc.primary_candidate),
            },
        )
    except ValueError as exc:
        # #2879 (machine contract): the read-side seam's traversal guard
        # (``assert_safe_path_segment``, the FIRST step — before any
        # ``KITTY_SPECS_DIR`` join or meta probe) raises ``ValueError`` for an
        # unsafe ``--mission`` value (``..``, ``../traversal``, separators,
        # leading dot, non-ASCII). Pre-fix that escaped to the top level and
        # was rendered as a raw Python traceback — NOT JSON — breaking every
        # programmatic consumer of this JSON-first surface. Fail closed with
        # the structured ``INVALID_MISSION`` envelope instead (non-zero exit,
        # parseable stdout), mirroring how the host CLI's ``merge`` renders the
        # same guard (``cli/commands/merge.py:_resolve_slug_or_exit``).
        # ``_fail`` merges the *message* param into ``data`` last-wins, so the
        # guard's own diagnostic travels under a distinct ``reason`` key rather
        # than being silently overwritten by the canonical message.
        _fail(
            command,
            "INVALID_MISSION",
            f"Mission slug is not a safe path segment: {mission_slug!r}",
            data={"reason": str(exc), "mission_slug": mission_slug},
        )
    if mission_dir is None:
        _fail(command, "MISSION_NOT_FOUND", _MISSION_NOT_FOUND_MESSAGE.format(mission=mission_slug))
    return mission_dir


def _planning_read_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """Return the PRIMARY-surface mission dir for planning-artifact reads (#2118).

    PRIMARY-partition artifacts — ``lanes.json`` (``LANE_STATE``) and the WP
    ``tasks/`` files (``WORK_PACKAGE_TASK``) — live with their mission on the
    primary ``target_branch`` for EVERY topology since the write-surface-coherence
    work (#2090): planning never transits the coordination branch. The coord-aware
    :func:`_resolve_mission_dir` returns the *coordination worktree*, which carries
    ONLY the coordination-partition artifacts — the status views
    (``status.events.jsonl`` / ``status.json``) and the accept/review matrices
    (``acceptance-matrix.json`` / ``issue-matrix.md``). (``analysis-report.md`` was
    re-homed COORD→PRIMARY, FR-003 coord-commit-integrity, so it is NOT here.)
    Reading ``lanes.json`` or
    ``tasks/`` off that surface under coordination topology silently no-ops — the
    dependency graph comes back empty and the orchestrator stalls with every WP
    stuck at ``lane=planned`` (#2118).

    This routes PRIMARY-partition reads through the canonical kind-aware
    placement seam (:func:`mission_runtime.placement_seam`, coord-primary-
    partition-lock WP01 T004 — DRY-only repoint, out-of-map edit; this file is
    not a WP01 owned file), the read-side twin of the write-side partition
    (``mission_runtime.is_primary_artifact_kind``): a PRIMARY kind resolves the
    topology-blind primary dir, so both ``LANE_STATE`` and ``WORK_PACKAGE_TASK``
    co-resolve here. STATUS reads (``read_events`` / ``reduce`` / ``materialize``
    / status-event writes) MUST keep the coord-aware :func:`_resolve_mission_dir`
    — the append-only event log stays on coordination for coord-topology
    missions. This mirrors the meta.json treatment already in
    :func:`_resolve_merge_target_branch`.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    return placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)


def _mission_identity_payload(mission_dir: Path) -> dict[str, str]:
    """Return canonical mission identity fields for machine-facing payloads."""
    identity = resolve_mission_identity(mission_dir)
    return {
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
    }


def _get_last_actor(mission_dir: Path, wp_id: str) -> str | None:
    """Get the actor of the most recent event for this WP."""
    from specify_cli.status import read_events

    events = read_events(mission_dir)
    for event in reversed(events):
        if event.wp_id == wp_id:
            return event.actor
    return None


_WP_ID_RE = re.compile(r"^(WP\d+)")


def _extract_wp_id(stem: str) -> str | None:
    """Extract canonical WP ID from a task filename stem.

    Examples:
        "WP07"                         -> "WP07"
        "WP07-adapter-implementations" -> "WP07"
        "README"                       -> None
    """
    m = _WP_ID_RE.match(stem)
    return m.group(1) if m else None


def _resolve_wp_file(tasks_dir: Path, wp_id: str) -> Path | None:
    """Locate the task file for a WP, accepting suffixed filenames.

    Checks for an exact match first (WP07.md), then falls back to any
    file whose name starts with '<wp_id>-' (e.g. WP07-adapter-implementations.md).
    Returns the first match found, or None if no file exists.
    """
    exact = tasks_dir / f"{wp_id}.md"
    if exact.exists():
        return exact
    for p in sorted(tasks_dir.glob(f"{wp_id}-*.md")):
        return p
    return None


def _resolve_merge_target_branch(main_repo_root: Path, mission_slug: str, target: str | None) -> str:
    """Resolve the branch ``merge-mission`` integrates into.

    Order: explicit ``--target`` > meta ``merge_target_branch`` > meta
    ``target_branch`` > repo default.

    The mission target lives in the PRIMARY-checkout meta.json (like
    ``coordination_branch``), so it is read via ``primary_feature_dir_for_mission``
    — NOT the topology-aware candidate. Under coordination topology that candidate
    resolves to the coordination worktree, whose mission dir has no meta.json; the
    prior code read that surface, missed the mission's ``target_branch``, and
    silently fell back to the repo default (main) — merging into the wrong branch.
    """
    from specify_cli.core.paths import resolve_merge_target_branch

    return resolve_merge_target_branch(main_repo_root, mission_slug, target)[0]


def _build_merge_preflight(
    main_repo_root: Path,
    mission_slug: str,
    target: str | None,
) -> _MergePreflightResult:
    """Validate merge prerequisites and collect machine-readable errors."""
    from specify_cli.core.git_preflight import build_git_preflight_failure_payload, run_git_preflight
    from specify_cli.core.git_ops import run_command
    from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError, require_lanes_json

    resolved_target = _resolve_merge_target_branch(main_repo_root, mission_slug, target)
    errors: list[str] = []

    if (main_repo_root / ".git").exists():
        preflight = run_git_preflight(main_repo_root, check_worktree_list=True)
        if not preflight.passed:
            payload = build_git_preflight_failure_payload(preflight, command_name="orchestrator-api merge-mission")
            errors.append(payload["error"])
            errors.extend(payload.get("remediation", []))

        ret_local, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/heads/{resolved_target}"],
            capture=True,
            check_return=False,
            cwd=main_repo_root,
        )
        ret_remote, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/remotes/origin/{resolved_target}"],
            capture=True,
            check_return=False,
            cwd=main_repo_root,
        )
        if ret_local != 0 and ret_remote != 0:
            errors.append(f"Target branch '{resolved_target}' does not exist locally or on origin.")

    try:
        # lanes.json is a PRIMARY-partition artifact — read from the primary
        # surface, NOT the coord worktree mission_dir (#2118).
        require_lanes_json(_planning_read_dir(main_repo_root, mission_slug))
    except (MissingLanesError, CorruptLanesError) as exc:
        errors.append(str(exc))

    return _MergePreflightResult(target_branch=resolved_target, errors=errors)


def _execute_planning_only_merge(
    main_repo_root: Path,
    mission_slug: str,
    target_branch: str,
    *,
    strategy: object,
    push: bool,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> None:
    """Run the hardened CLI closeout path while preserving JSON-only stdout."""
    import typer

    from specify_cli.cli.commands import merge as merge_command

    try:
        with merge_command.console.capture():
            merge_command._run_lane_based_merge(
                repo_root=main_repo_root,
                mission_slug=mission_slug,
                push=push,
                delete_branch=delete_branch,
                remove_worktree=remove_worktree,
                target_override=target_branch,
                strategy=strategy,
                assume_yes=True,
            )
    except typer.Exit as exc:
        raise RuntimeError(f"Planning-artifact closeout failed with exit code {exc.exit_code}") from exc


def _resolve_lane_merge_retention(
    main_repo_root: Path,
    mission_slug: str,
    *,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> tuple[RetentionDecision, bool]:
    """Resolve the retention decision + mission-branch-deletable flag (C-007/T010).

    ``_execute_lane_merge`` is a genuine SECOND deletion implementation (not a
    passthrough to ``merge/executor.py``), so NFR-003 ("all cleanup paths")
    requires it to route through the same
    :func:`~specify_cli.core.paths.resolve_merge_retention` authority rather
    than deleting unconditionally. This mirrors the executor's topology-aware
    coupling **GATE** (#3131 T008 / INV-2): for a coord-topology mission (its
    primary meta.json carries a ``coordination_branch`` key) the
    mission/coordination branch is only deletable when BOTH ``delete_branch``
    and ``remove_worktree`` resolve True (``teardown_coordination``); for a
    non-coord mission it stays keyed to ``delete_branch`` alone. This guarantees
    a **retaining** coord mission's branch is never deleted here (NFR-003).

    Scope note: only the deletion GATE mirrors the executor. The orchestrator
    does NOT perform the executor's full coordination-triple teardown
    (``_teardown_coordination_triple``: coord-marker flatten + coord-worktree
    removal) — it only deletes the mission branch. A NON-retaining coord mission
    merged through orchestrator-api therefore leaves the ``coordination_branch``
    marker/worktree un-torn-down (a pre-existing orchestrator-api limitation,
    tracked separately, NOT introduced by #3131). Full coord teardown is the
    executor/CLI ``spec-kitty merge`` path's responsibility.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.core.paths import resolve_merge_retention
    from specify_cli.mission_metadata import load_meta_or_empty

    primary_meta_dir = placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    retention = resolve_merge_retention(
        primary_meta_dir,
        explicit_delete_branch=delete_branch,
        explicit_remove_worktree=remove_worktree,
    )
    is_coord = "coordination_branch" in load_meta_or_empty(primary_meta_dir)
    mission_branch_deletable = retention.teardown_coordination if is_coord else retention.delete_branch
    return retention, mission_branch_deletable


def _apply_lane_merge_cleanup(
    main_repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    *,
    retention: RetentionDecision,
    mission_branch_deletable: bool,
) -> None:
    """Worktree removal + lane/mission branch deletion, gated on the RESOLVED
    retention decision (#3131 T010) — extracted from ``_execute_lane_merge``
    to stay under the complexity ceiling; not a passthrough (see there)."""
    import functools

    from specify_cli.coordination.coherence import is_toolchain_generated_churn
    from specify_cli.core.git_ops import run_command
    from specify_cli.git.destructive_guard import guarded_worktree_remove
    from specify_cli.lanes.branch_naming import lane_branch_name, worktree_path
    from specify_cli.lanes.compute import is_planning_lane

    if retention.remove_worktree:
        for lane in lanes_manifest.lanes:
            # Legacy lane-worktree grammar ({slug}-{lane}, no mid8) ⇒ mission_id=None
            # reproduces the historical name byte-identically (FR-005).
            wt_path = worktree_path(main_repo_root, mission_slug, mission_id=None, lane_id=lane.lane_id)
            if wt_path.exists():
                # #4753 C-003: ``retention.remove_worktree`` is the upstream
                # decision of WHETHER to remove at all (already resolved
                # above, and already honors the operator's
                # --keep-worktree/retain_worktrees policy); the guard's own
                # ``retain`` is a DIFFERENT axis (dirty-worktree handling) and
                # always stays False here (review ADVISORY-3) so a dirty lane
                # worktree refuses instead of being force-removed.
                guarded_worktree_remove(
                    wt_path,
                    retain=False,
                    is_residue=functools.partial(
                        is_toolchain_generated_churn,
                        mission_slug=mission_slug,
                    ),
                )

    # LANE branches stay keyed to the plain resolved ``delete_branch`` (no
    # topology coupling — only the mission/coordination branch is coupled).
    if retention.delete_branch:
        for lane in lanes_manifest.lanes:
            if is_planning_lane(lane):
                continue
            run_command(
                [
                    "git",
                    "branch",
                    "-D",
                    lane_branch_name(
                        mission_slug,
                        lane.lane_id,
                        planning_base_branch=lanes_manifest.target_branch,
                    ),
                ],
                cwd=main_repo_root,
                check_return=False,
            )

    # MISSION/coordination branch: the DELETION GATE is topology-aware (#3131
    # T008/T010 — see ``_resolve_lane_merge_retention``), so a retaining coord
    # mission's branch is never deleted here. NOTE: unlike the executor's
    # ``_teardown_coordination_triple``, this path does NOT flatten the
    # ``coordination_branch`` marker or remove the coord worktree — full coord
    # teardown is the executor/CLI path's job (pre-existing orchestrator-api
    # limitation, tracked separately).
    if mission_branch_deletable:
        run_command(
            ["git", "branch", "-D", lanes_manifest.mission_branch],
            cwd=main_repo_root,
            check_return=False,
        )


def _execute_lane_merge(
    main_repo_root: Path,
    mission_dir: Path,
    mission_slug: str,
    target_branch: str,
    *,
    strategy: str,
    push: bool,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> None:
    """Execute the lane-based merge flow without emitting console prose."""
    from specify_cli.cli.commands.merge import _mark_wp_merged_done
    from specify_cli.core.git_ops import has_remote, run_command
    from specify_cli.lanes.compute import is_planning_artifact_only
    from specify_cli.lanes.merge import consolidate_lane_into_mission, integrate_mission_into_target
    from specify_cli.lanes.persistence import require_lanes_json
    from specify_cli.merge.config import MergeStrategy
    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.merge_gates import evaluate_merge_gates

    # lanes.json is PRIMARY-partition — read from the primary surface, not the
    # coord worktree mission_dir (#2118).
    lanes_manifest = require_lanes_json(_planning_read_dir(main_repo_root, mission_slug))
    lanes_manifest.target_branch = target_branch
    merge_strategy = MergeStrategy(strategy)

    if is_planning_artifact_only(lanes_manifest):
        _execute_planning_only_merge(
            main_repo_root,
            mission_slug,
            target_branch,
            strategy=merge_strategy,
            push=push,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
        )
        return

    # #3131 C-007/T010: resolve once, before any gate/merge work, so the
    # cleanup gates below never delete unconditionally.
    retention, mission_branch_deletable = _resolve_lane_merge_retention(
        main_repo_root,
        mission_slug,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
    )

    policy = load_policy_config(main_repo_root)
    all_wp_ids = [wp for lane in lanes_manifest.lanes for wp in lane.wp_ids]
    gate_eval = evaluate_merge_gates(
        mission_dir,
        mission_slug,
        all_wp_ids,
        policy.merge_gates,
        main_repo_root,
    )
    if not gate_eval.overall_pass:
        blocking = [gate.details for gate in gate_eval.gates if gate.blocking]
        raise RuntimeError("; ".join(blocking) or "Merge gates failed.")

    for lane in lanes_manifest.lanes:
        lane_result = consolidate_lane_into_mission(main_repo_root, mission_slug, lane.lane_id, lanes_manifest)
        if not lane_result.success:
            raise RuntimeError("; ".join(lane_result.errors) or f"Lane {lane.lane_id} merge failed.")

    mission_result = integrate_mission_into_target(
        main_repo_root,
        mission_slug,
        lanes_manifest,
        strategy=merge_strategy,
    )
    if not mission_result.success:
        raise RuntimeError("; ".join(mission_result.errors) or "Mission merge failed.")

    for lane in lanes_manifest.lanes:
        for wp_id in lane.wp_ids:
            _mark_wp_merged_done(main_repo_root, mission_slug, wp_id, lanes_manifest.target_branch)

    if push and has_remote(main_repo_root):
        run_command(["git", "push", "origin", lanes_manifest.target_branch], cwd=main_repo_root)

    # #3131 T010: gated on the RESOLVED decision, not the raw (possibly unset)
    # caller args — a retaining mission's branches/worktree survive.
    _apply_lane_merge_cleanup(
        main_repo_root,
        mission_slug,
        lanes_manifest,
        retention=retention,
        mission_branch_deletable=mission_branch_deletable,
    )


# ── Command 1: contract-version ────────────────────────────────────────────


@app.command(name="contract-version")
def contract_version(
    provider_version: str = typer.Option(
        None,
        "--provider-version",
        help="Caller's provider version; returns CONTRACT_VERSION_MISMATCH if below minimum",
    ),
) -> None:
    """Return the current API contract version.

    Pass --provider-version to check compatibility before running state-mutating commands.
    """
    cmd = "contract-version"

    if provider_version is not None:
        from packaging.version import Version, InvalidVersion

        try:
            if Version(provider_version) < Version(MIN_PROVIDER_VERSION):
                _fail(
                    cmd,
                    "CONTRACT_VERSION_MISMATCH",
                    f"Provider version {provider_version!r} is below minimum {MIN_PROVIDER_VERSION!r}",
                    {
                        "provider_version": provider_version,
                        "min_supported_provider_version": MIN_PROVIDER_VERSION,
                        "api_version": CONTRACT_VERSION,
                    },
                )
                return
        except InvalidVersion:
            _fail(
                cmd,
                "CONTRACT_VERSION_MISMATCH",
                f"Provider version {provider_version!r} is not a valid version string",
                {"provider_version": provider_version},
            )
            return

    envelope = make_envelope(
        command=cmd,
        success=True,
        data={
            "api_version": CONTRACT_VERSION,
            "min_supported_provider_version": MIN_PROVIDER_VERSION,
        },
    )
    _emit(envelope)


# ── Command 2: mission-state ────────────────────────────────────────────────


@app.command(name="mission-state")
def mission_state(
    mission: str = typer.Option(
        ...,
        "--mission",
        help=_HELP_MISSION_SLUG,
    ),
) -> None:
    """Return the full state of a mission (all WPs, lanes, dependencies)."""
    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail("mission-state", main_repo_root, mission)

    from specify_cli.status import reduce
    from specify_cli.status import read_events
    from specify_cli.core.dependency_graph import build_dependency_graph

    # STATUS reads stay on the coord-aware dir; PRIMARY reads (dep graph from WP
    # frontmatter, tasks/ enumeration) come from the primary surface (#2118).
    planning_dir = _planning_read_dir(main_repo_root, mission)

    # Query endpoint: reduce from event log without rewriting status.json.
    snapshot = reduce(read_events(mission_dir))
    dep_graph = build_dependency_graph(planning_dir)

    # Build the full WP set from task files + dep graph + snapshot
    # so that untouched WPs (no events yet) still appear as "planned"
    tasks_dir = planning_dir / "tasks"
    task_file_wp_ids: set[str] = set()
    if tasks_dir.exists():
        for p in tasks_dir.iterdir():
            if p.suffix == ".md":
                wp_id = _extract_wp_id(p.stem)
                if wp_id is not None:
                    task_file_wp_ids.add(wp_id)

    all_wp_ids = task_file_wp_ids | set(dep_graph.keys()) | set(snapshot.work_packages.keys())

    work_packages = []
    for wp_id in sorted(all_wp_ids):
        wp_snapshot = snapshot.work_packages.get(wp_id, {})
        work_packages.append(
            {
                "wp_id": wp_id,
                "lane": wp_snapshot.get("lane", Lane.PLANNED),
                "dependencies": dep_graph.get(wp_id, []),
                "last_actor": wp_snapshot.get("last_actor"),
            }
        )

    data = {
        **_mission_identity_payload(mission_dir),
        "summary": snapshot.summary,
        "work_packages": work_packages,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command="mission-state",
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 3: list-ready ──────────────────────────────────────────────────


@app.command(name="list-ready")
def list_ready(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
) -> None:
    """List WPs that are ready to start (planned and all deps approved or done)."""
    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail("list-ready", main_repo_root, mission)

    from specify_cli.status import reduce
    from specify_cli.status import read_events
    from specify_cli.core.dependency_graph import build_dependency_graph, dependency_readiness_for_wp

    # Query endpoint: reduce from event log without rewriting status.json.
    # STATUS read off the coord-aware dir; the dependency graph (WP frontmatter,
    # PRIMARY-partition) off the primary surface (#2118 — an empty dep graph here
    # is exactly what stalls the orchestrator under coordination topology).
    snapshot = reduce(read_events(mission_dir))
    dep_graph = build_dependency_graph(_planning_read_dir(main_repo_root, mission))
    wp_states = snapshot.work_packages
    wp_lanes = {dep_id: wp_state_for(state.get("lane", Lane.PLANNED)).lane for dep_id, state in wp_states.items()}

    ready_wps = []
    for wp_id, deps in dep_graph.items():
        wp_snapshot = wp_states.get(wp_id, {})
        lane = wp_snapshot.get("lane", Lane.PLANNED)
        state = wp_state_for(lane)
        if state.progress_bucket() != "not_started":
            continue

        # Advisory display parity (FR-009): a canceled-with-operator-provenance
        # dependency is a documented removal, so surface its dependent as ready
        # rather than blocked. `wp_states` is the reduced snapshot already read
        # above, so this reuses the authoritative provenance with no extra I/O.
        # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
        # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
        readiness = dependency_readiness_for_wp(wp_id, deps, wp_lanes, provenance=wp_states)

        ready_wps.append(
            {
                "wp_id": wp_id,
                "lane": lane,
                "dependencies_satisfied": readiness.satisfied,
            }
        )

    # Filter to only truly ready ones
    ready_wps = [wp for wp in ready_wps if wp["dependencies_satisfied"]]

    data = {
        **_mission_identity_payload(mission_dir),
        "ready_work_packages": ready_wps,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command="list-ready",
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 4: start-implementation ────────────────────────────────────────


@dataclass(frozen=True)
class _StartWorkspace:
    """The workspace resolved for a WP at start-implementation.

    For a lane WP (lanes.json present and the WP is assigned to a lane) the lane
    fields are populated and ``workspace_path`` is a real lane worktree. For a
    legacy / non-lane mission (no lanes.json, or a planning-artifact WP) the lane
    fields stay ``None`` and ``workspace_path`` is the historical bare path —
    preserving the prior contract for those missions.
    """

    workspace_path: str
    lane_id: str | None = None
    lane_branch: str | None = None
    lane_base_ref: str | None = None


def _lane_base_ref(main_repo_root: Path, mission: str, manifest: object) -> str:
    """Back-compat delegator to the hoisted single base-ref authority.

    The lane-base resolution now lives with the shared ``for_review`` gate
    (:func:`specify_cli.lanes.for_review_gate.resolve_lane_base_ref`) so the gate
    leaf and this surface's workspace resolvers consult ONE implementation. Kept
    as a module-level name for the two workspace resolvers below (and existing
    callers) that already reference it.
    """
    from specify_cli.lanes.for_review_gate import resolve_lane_base_ref

    return resolve_lane_base_ref(main_repo_root, mission, manifest)


def _enforce_claim_ancestry(
    cmd: str,
    main_repo_root: Path,
    mission: str,
    mission_dir: Path,
    wp: str,
    workspace_path: Path,
) -> None:
    """POST-materialize claim-ancestry gate (C-WP03/FR-007/C-005) -- the ONE
    call site shared by both of THIS module's claim paths
    (``start_implementation``'s composite and ``transition``'s raw
    ``--to claimed``), boundary-leak fix: the allocator's reuse-path self-heal
    already reached ``orchestrator_api`` via ``_resolve_start_workspace``
    (always calls ``allocate_lane_worktree``), but the ancestry GATE did not.

    Delegates the predicate + self-heal-retry contract to
    :func:`specify_cli.lanes.implement_support.resolve_claim_ancestry_gate` --
    the same shared helper the CLI seam (``workflow.py``'s ``implement()``)
    calls -- so this module and the CLI can never independently diverge on
    the ancestry decision. Fails with the structured ``ANCESTRY_NOT_ESTABLISHED``
    envelope (never a bare exception) so an external orchestrator gets the
    same contract every other claim-time refusal here already provides.
    """
    from specify_cli.lanes.implement_support import resolve_claim_ancestry_gate

    result = resolve_claim_ancestry_gate(main_repo_root, mission, mission_dir, wp, workspace_path)
    if result.ok:
        return
    _fail(
        cmd,
        "ANCESTRY_NOT_ESTABLISHED",
        (f"cannot claim {wp}: ancestry could not be established after self-heal for: {', '.join(result.missing_refs)}"),
        {
            **_mission_identity_payload(mission_dir),
            "wp_id": wp,
            "missing_refs": list(result.missing_refs),
        },
    )


def _lane_assignment_or_legacy(main_repo_root: Path, mission: str, wp: str) -> tuple[LanesManifest, ExecutionLane] | _StartWorkspace:
    """Shared prologue of the two workspace resolvers (ONE fallback grammar).

    Returns the ``(manifest, lane)`` pair when ``wp`` is lane-assigned;
    otherwise the legacy bare-path ``_StartWorkspace`` — the WP-based worktree
    form ``{mission}-{wp}`` with no mid8 (the seam's ``mission_id=None``
    grammar reproduces the historical name byte-identically) — so legacy /
    non-lane missions keep working unchanged.

    lanes.json is PRIMARY-partition — read from the primary surface (#2118).
    SSOT: this is the ONLY place this surface decides lane-vs-legacy; a future
    fallback-grammar change is a single edit.
    """
    from specify_cli.lanes.branch_naming import worktree_path as _wt_path
    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(_planning_read_dir(main_repo_root, mission))
    lane = manifest.lane_for_wp(wp) if manifest is not None else None
    if manifest is None or lane is None:
        return _StartWorkspace(workspace_path=str(_wt_path(main_repo_root, mission, mission_id=None, lane_id=wp)))
    return manifest, lane


def _resolve_start_workspace(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str) -> _StartWorkspace:
    """Resolve (allocating if needed) the workspace for ``wp``.

    When the mission has a lanes manifest and ``wp`` is assigned to a lane, this
    mirrors spec-kitty's native implement flow: it allocates (or reuses) the lane
    worktree on its lane branch — parented on the coordination branch, with
    approved dependency-lane tips merged into the base — so ``merge-mission`` has
    a real lane branch to integrate and dependent WPs see their dependencies'
    code. Idempotent: re-invoking reuses the existing lane worktree and re-merges
    any newly-approved dependency tips.

    When there is no lanes.json (legacy / non-lane missions) or ``wp`` is not in
    any lane (planning-artifact WP), it falls back to the historical bare-path
    behaviour (via :func:`_lane_assignment_or_legacy`) so those missions keep
    working unchanged.

    A genuine allocation failure for a lane WP (dirty reuse, dependency-merge
    conflict) fails closed with ``LANE_ALLOCATION_FAILED``.
    """
    assignment = _lane_assignment_or_legacy(main_repo_root, mission, wp)
    if isinstance(assignment, _StartWorkspace):
        return assignment
    manifest, lane = assignment

    from specify_cli.lanes.worktree_allocator import (
        DependencyLaneMergeConflictError,
        DirtyWorktreeError,
        LaneNotFoundError,
        UnhonorableBaseError,
        allocate_lane_worktree,
    )

    try:
        worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=main_repo_root,
            mission_slug=mission,
            wp_id=wp,
            lanes_manifest=manifest,
        )
    except (
        LaneNotFoundError,
        DirtyWorktreeError,
        DependencyLaneMergeConflictError,
        UnhonorableBaseError,
        RuntimeError,
    ) as exc:
        # NFR-004: a StructuredError refusal (UnhonorableBaseError,
        # DestroyedLaneError) carries a machine-readable error_code (and
        # route/wp_id/base, or lane_id/branch_name/next_step) via to_dict() —
        # merge it into the data payload so a caller can branch on
        # data["error_code"] == "UNHONORABLE_BASE" / "DESTROYED_LANE" rather
        # than substring-matching the message (#4889: the destroyed-lane P0
        # exists to protect this orchestrator caller, so its structured fields
        # must reach it, not just str(exc)). The top-level envelope error_code
        # stays "LANE_ALLOCATION_FAILED" (the generic allocation-failure
        # surface). The plain-RuntimeError members of this tuple lack to_dict(),
        # so `hasattr` leaves their payload untouched.
        _fail(
            cmd,
            "LANE_ALLOCATION_FAILED",
            str(exc),
            # #2512: include the refusal reason in the data payload so the
            # orchestrator can surface a diagnostic without parsing the envelope
            # message string.  The message field already carries str(exc) but is
            # not structurally queryable; "reason" makes the cause machine-readable.
            {
                **_mission_identity_payload(mission_dir),
                "wp_id": wp,
                "reason": str(exc),
                **(exc.to_dict() if hasattr(exc, "to_dict") else {}),
            },
        )

    # _fail is NoReturn (always raises typer.Exit), so this is reached only on the
    # success path, where worktree_path / lane_branch are bound.
    return _StartWorkspace(
        workspace_path=str(worktree_path),
        lane_id=lane.lane_id,
        lane_branch=lane_branch,
        lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
    )


def _resolve_existing_workspace(main_repo_root: Path, mission: str, wp: str) -> _StartWorkspace:
    """Read-only companion of :func:`_resolve_start_workspace` (#2337).

    Resolves the WP's lane ``workspace_path`` + ``lane_branch`` for its EXISTING
    lane via the canonical naming seams (``lane_branch_name`` + ``worktree_path``)
    — WITHOUT allocating, creating, validating-clean, or merging dependency tips.
    Lets a caller obtain the workspace for a WP already past start-implementation
    (e.g. an external orchestrator resuming a ``for_review`` WP) without the
    ``planned->claimed->in_progress`` composite transition start-implementation
    performs. Shares start-implementation's legacy/non-lane fallback via
    :func:`_lane_assignment_or_legacy`, and takes placement from the allocator's
    own :func:`~specify_cli.lanes.worktree_allocator.predict_lane_worktree` seam
    so the read-only mirror can never diverge from what the write authority
    would create.
    """
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    assignment = _lane_assignment_or_legacy(main_repo_root, mission, wp)
    if isinstance(assignment, _StartWorkspace):
        return assignment
    manifest, lane = assignment

    worktree_path, lane_branch = predict_lane_worktree(main_repo_root, mission, lane.lane_id)
    return _StartWorkspace(
        workspace_path=str(worktree_path),
        lane_id=lane.lane_id,
        lane_branch=lane_branch,
        lane_base_ref=_lane_base_ref(main_repo_root, mission, manifest),
    )


@app.command(name="resolve-workspace")
def resolve_workspace(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
) -> None:
    """Read-only: resolve a WP's lane workspace_path + prompt_path (+ lane fields).

    Does NOT allocate/create/validate-clean/transition — the read-only companion
    of ``start-implementation`` for a WP already past implementation (e.g. a
    ``for_review`` WP an external orchestrator wants to review on resume, where
    calling start-implementation would wrongly re-transition it). Contract >= 1.2.0.
    """
    cmd = "resolve-workspace"
    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    ws = _resolve_existing_workspace(main_repo_root, mission, wp)
    # --mission accepts mission_id / mid8 / slug; the payload's mission_slug is
    # the RESOLVED identity, never the raw selector echoed back.
    data: dict = {
        **_mission_identity_payload(mission_dir),
        "wp_id": wp,
        "workspace_path": ws.workspace_path,
        "prompt_path": str(wp_path),
    }
    if ws.lane_id is not None:
        data["lane_id"] = ws.lane_id
        data["lane_branch"] = ws.lane_branch
        data["lane_base_ref"] = ws.lane_base_ref
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


@app.command(name="start-implementation")
def start_implementation(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Composite transition: planned->claimed->in_progress (idempotent)."""
    cmd = "start-implementation"

    # Policy required
    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for start-implementation")
        return

    policy_dict = _parse_policy_or_fail(cmd, policy)

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.core.dependency_graph import dependency_readiness_for_wp, parse_wp_dependencies
    from specify_cli.status import reduce
    from specify_cli.status import read_events

    # Reduce once off the same (coord-aware) status surface the lane map already
    # reads, so the provenance map threaded into the gate is consistent with the
    # lanes it decides against.
    _snapshot = reduce(read_events(mission_dir))
    wp_lanes = {wp_id: state.get("lane", Lane.PLANNED) for wp_id, state in _snapshot.work_packages.items()}
    # Only gate the not-yet-started claim transition. Re-invoking start-implementation
    # on a WP that is already in_progress/for_review/.../approved is a no-op resume
    # in the lifecycle layer and must not be rejected just because a dependency later
    # regressed out of approved/done.
    _self_lane = wp_state_for(wp_lanes.get(wp, Lane.PLANNED)).lane
    if _self_lane in (Lane.PLANNED, Lane.CLAIMED):
        # Thread per-dependency provenance (FR-009): start-implementation is the
        # external-API CLAIM gate (mutating planned→claimed→in_progress), the
        # equivalent of implement.py's `_ensure_wp_claim_preconditions`. Without
        # this a dependent of a canceled-with-operator-provenance WP reproduces
        # the #2945 strand on the orchestrator-api claim path.
        # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
        # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
        dependency_readiness = dependency_readiness_for_wp(
            wp,
            parse_wp_dependencies(wp_path),
            wp_lanes,
            provenance=_snapshot.work_packages,
        )
        if not dependency_readiness.satisfied:
            blocked = ", ".join(dependency_readiness.unsatisfied)
            _fail(
                cmd,
                "DEPENDENCIES_NOT_SATISFIED",
                (f"dependencies_not_satisfied: {wp} depends on {blocked}; all dependencies must be approved or done before implementation can start"),
                {
                    **_mission_identity_payload(mission_dir),
                    "wp_id": wp,
                    "unsatisfied_dependencies": list(dependency_readiness.unsatisfied),
                },
            )
            return

    from specify_cli.status import TransitionError
    from specify_cli.status import WorkPackageClaimConflict, start_implementation_status

    # Allocate the REAL lane worktree (lane branch + dependency-lane tips merged)
    # when the mission has lanes, mirroring the native implement flow so
    # merge-mission has a lane branch to integrate. Legacy / non-lane missions
    # keep the historical bare path.
    start_ws = _resolve_start_workspace(cmd, main_repo_root, mission, mission_dir, wp)
    workspace_path = start_ws.workspace_path
    prompt_path = str(wp_path)

    # Seam C-005 (#3281/FR-007): POST-materialize, after allocation/self-heal
    # above, BEFORE the claim transition below emits any status event. Never
    # move this above ``_resolve_start_workspace`` -- see
    # ``_enforce_claim_ancestry``'s docstring for the deadlock hazard.
    _enforce_claim_ancestry(cmd, main_repo_root, mission, mission_dir, wp, Path(workspace_path))

    # #3946 (F-78): a reused lane's persisted workspace context must follow the
    # WP that just claimed it, exactly as the native ``implement`` flow refreshes
    # it via the same helper — otherwise every later lane commit warns
    # ACTIVE_WP_CONTEXT_STALE and the guard scopes against the prior WP. No-op
    # when the lane has no context (an orchestrator-driven mission never created
    # one; that shape is unchanged). ``mission_dir.name`` is the canonical
    # mission directory name the native flow saves the context under.
    from specify_cli.lanes.implement_support import refresh_reused_lane_context

    refresh_reused_lane_context(
        main_repo_root,
        mission_dir.name,
        start_ws.lane_id,
        wp,
        parse_wp_dependencies(wp_path),
    )

    try:
        start_result = start_implementation_status(
            feature_dir=mission_dir,
            mission_slug=mission,
            wp_id=wp,
            actor=actor,
            workspace_context=workspace_path,
            execution_mode="worktree",
            repo_root=main_repo_root,
            policy_metadata=policy_dict,
            ensure_sync_daemon=False,
        )
    except WorkPackageClaimConflict as exc:
        _fail(
            cmd,
            "WP_ALREADY_CLAIMED",
            str(exc),
            {
                **_mission_identity_payload(mission_dir),
                "claimed_by": exc.claimed_by,
                "requesting_actor": exc.requesting_actor,
            },
        )
        return
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    data = {
        **_mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": start_result.from_lane,
        "to_lane": Lane.IN_PROGRESS,
        "workspace_path": workspace_path,
        "prompt_path": prompt_path,
        "policy_metadata_recorded": True,
        "no_op": start_result.no_op,
    }
    if start_ws.lane_id is not None:
        # Lane WP: carry the lane identity the orchestrator needs to commit and
        # gate. Omitted for legacy / non-lane missions (unchanged contract).
        data["lane_id"] = start_ws.lane_id
        data["lane_branch"] = start_ws.lane_branch
        data["lane_base_ref"] = start_ws.lane_base_ref
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 5: start-review ────────────────────────────────────────────────


@app.command(name="start-review")
def start_review(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
    review_ref: str = typer.Option(None, "--review-ref", help="Review feedback reference (optional, not required for for_review→in_review)"),
) -> None:
    """Transition a WP from for_review to in_review (reviewer claims review)."""
    cmd = "start-review"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for start-review")
        return

    try:
        policy_obj = parse_and_validate_policy(policy)
    except ValueError as exc:
        _fail(cmd, "POLICY_VALIDATION_FAILED", str(exc))
        return

    policy_dict = policy_to_dict(policy_obj)

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.status import TransitionError
    from specify_cli.status import WorkPackageClaimConflict, start_review_status

    prompt_path = str(wp_path)

    try:
        start_result = start_review_status(
            feature_dir=mission_dir,
            mission_slug=mission,
            wp_id=wp,
            actor=actor,
            review_ref=review_ref,
            workspace_context=f"orchestrator-api:{main_repo_root}",
            execution_mode="worktree",
            repo_root=main_repo_root,
            policy_metadata=policy_dict,
            ensure_sync_daemon=False,
        )
    except WorkPackageClaimConflict as exc:
        _fail(
            cmd,
            "WP_ALREADY_CLAIMED",
            str(exc),
            {
                **_mission_identity_payload(mission_dir),
                "claimed_by": exc.claimed_by,
                "requesting_actor": exc.requesting_actor,
            },
        )
        return
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    data = {
        **_mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": start_result.from_lane,
        "to_lane": Lane.IN_REVIEW,
        "prompt_path": prompt_path,
        "policy_metadata_recorded": True,
        "no_op": start_result.no_op,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 6: transition ──────────────────────────────────────────────────


def _enforce_for_review_commit_gate(cmd: str, main_repo_root: Path, mission: str, mission_dir: Path, wp: str, force: bool) -> None:
    """Reject an in_progress->for_review transition that has no commit on the lane.

    Thin orchestrator adapter over the shared, surface-neutral gate leaf
    (:func:`specify_cli.lanes.for_review_gate.evaluate_for_review_gate`): the leaf
    decides (returning a :class:`GateDecision`) and THIS surface renders the
    envelope ``_fail`` from that decision. The envelope (``NoReturn``) never
    leaks into the leaf, so ``agent status emit`` (WP09) can consume the same
    gate and render its own CLI error. No-ops when bypassed (``--force``) or when
    the gate does not apply (no lanes.json, or the WP is not in any lane).
    """
    from specify_cli.lanes.for_review_gate import (
        GateDecision,
        evaluate_for_review_gate,
    )

    decision: GateDecision = evaluate_for_review_gate(main_repo_root, mission, wp, force=force)
    if not decision.passed:
        _fail(
            cmd,
            "TRANSITION_REJECTED",
            decision.reason,
            {
                **_mission_identity_payload(mission_dir),
                "wp_id": wp,
                "lane_id": decision.lane_id,
            },
        )


@app.command(name="transition")
def transition(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    to: str = typer.Option(..., "--to", help="Target lane"),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    note: str = typer.Option(None, "--note", help="Reason/note for the transition"),
    policy: str = typer.Option(None, "--policy", help="Policy metadata JSON (required for run-affecting lanes)"),
    force: bool = typer.Option(False, "--force", help="Force the transition"),
    review_ref: str = typer.Option(None, "--review-ref", help="Review reference"),
    review_result_json: str = typer.Option(
        None,
        "--review-result-json",
        help="JSON structured review outcome for transitions from in_review",
    ),
    evidence_json: str = typer.Option(None, "--evidence-json", help="JSON string with done evidence"),
    subtasks_complete: bool = typer.Option(None, "--subtasks-complete", help="Whether required subtasks are complete for in_progress->for_review"),
    implementation_evidence_present: bool = typer.Option(
        None, "--implementation-evidence-present", help="Whether implementation evidence exists for in_progress->for_review"
    ),
) -> None:
    """Emit a single lane transition for a WP."""
    cmd = "transition"

    from specify_cli.status import resolve_lane_alias

    to_lane = resolve_lane_alias(to)

    # Policy required for transitions into active-execution lanes (not planned).
    policy_dict: dict | None = None
    if _transition_requires_policy(to_lane):
        if not policy:
            _fail(
                cmd,
                "POLICY_METADATA_REQUIRED",
                f"--policy is required when transitioning to '{to_lane}'",
            )
            return
        policy_dict = _parse_policy_or_fail(cmd, policy)
    elif policy:
        # Optional policy for non-run-affecting lanes
        policy_dict = _parse_policy_or_fail(cmd, policy)

    evidence: dict | None = None
    if evidence_json is not None:
        try:
            parsed_evidence = json.loads(evidence_json)
        except json.JSONDecodeError as exc:
            _fail(cmd, "USAGE_ERROR", f"Invalid JSON in --evidence-json: {exc}")
            return
        if not isinstance(parsed_evidence, dict):
            _fail(cmd, "USAGE_ERROR", "--evidence-json must decode to a JSON object")
            return
        evidence = parsed_evidence

    review_result: ReviewResult | None = None
    if review_result_json is not None:
        try:
            review_result = parse_review_result_json(review_result_json)
        except ValueError as exc:
            _fail(cmd, "USAGE_ERROR", str(exc))
            return

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    wp_path = _resolve_wp_file(_planning_read_dir(main_repo_root, mission) / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    if to_lane == Lane.FOR_REVIEW:
        _enforce_for_review_commit_gate(cmd, main_repo_root, mission, mission_dir, wp, force)
    elif to_lane == Lane.CLAIMED:
        # Seam C-005 (#3281/FR-007): early-return-equivalent for every OTHER
        # target lane -- this predicate only ever runs for a raw `--to
        # claimed` transition. Allocates/self-heals the lane workspace
        # (mirrors start_implementation's own `_resolve_start_workspace`
        # call) and enforces ancestry BEFORE the `claimed` event below.
        claim_ws = _resolve_start_workspace(cmd, main_repo_root, mission, mission_dir, wp)
        _enforce_claim_ancestry(cmd, main_repo_root, mission, mission_dir, wp, Path(claim_ws.workspace_path))

    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status import TransitionError
    from specify_cli.status import TransitionRequest

    try:
        event = emit_status_transition_transactional(
            TransitionRequest(
                feature_dir=mission_dir,
                mission_slug=mission,
                wp_id=wp,
                to_lane=to_lane,
                actor=actor,
                reason=note,
                force=force,
                evidence=evidence,
                review_ref=review_ref,
                review_result=review_result,
                subtasks_complete=subtasks_complete,
                implementation_evidence_present=implementation_evidence_present,
                execution_mode="worktree",
                repo_root=main_repo_root,
                policy_metadata=policy_dict,
            ),
            ensure_sync_daemon=False,
        )
    except TransitionError as exc:
        _fail(cmd, "TRANSITION_REJECTED", str(exc))
        return

    data = {
        **_mission_identity_payload(mission_dir),
        "wp_id": wp,
        "from_lane": str(event.from_lane),
        "to_lane": str(event.to_lane),
        "policy_metadata_recorded": policy_dict is not None,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 7: append-history ──────────────────────────────────────────────


def _resolve_history_commit_args(main_repo_root: Path, mission: str) -> tuple[Path, CommitTarget]:
    """Resolve (worktree_root, target) for committing a WP prompt-file edit.

    The WP prompt file is a ``WORK_PACKAGE_TASK`` — a PRIMARY artifact kind
    (write-surface-coherence WP03 / T013). So it commits to the primary
    ``target_branch`` for every topology, via the kind-aware
    :func:`resolve_placement_only`, NOT through the coordination worktree: the
    planning→coord transit is removed (FR-003 / C-005). The WP prompt edit is
    committed directly from the primary checkout.

    FR-004 (read-surface-ssot-closeout, C-005): a placement-resolution
    failure (:class:`ActionContextError`) is FAIL-CLOSED — it raises
    :class:`PlacementResolutionRequired` and propagates. It must never
    silently degrade to ``CommitTarget(ref=<current checked-out branch>)``: a
    resolver failure is a real defect (missing mission, corrupt state, a
    ``coordination_branch`` declared in meta.json but torn down in git, ...),
    and committing the WP history entry to whatever branch the operator
    happens to have checked out is a shadow write path, not a legitimate
    fallback.
    """
    from mission_runtime import (
        ActionContextError,
        MissionArtifactKind,
        resolve_placement_only,
    )

    try:
        # WORK_PACKAGE_TASK is a primary kind: the placement resolves to the
        # primary target branch for every topology (no coord transit). The WP
        # prompt edit therefore commits directly to the primary checkout.
        placement = resolve_placement_only(main_repo_root, mission, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
    except ActionContextError as exc:
        raise PlacementResolutionRequired(
            "Cannot resolve the canonical write placement for this mission's "
            "WP prompt-file history commit -- refusing to commit to the "
            "currently checked-out branch (D11 fail-closed / FR-004). This "
            "usually means the mission's stored topology could not be "
            "resolved (e.g. a coordination branch declared in meta.json is "
            "missing/torn down in git). Run `spec-kitty doctor workspaces "
            "--fix`, or flatten the mission by removing `coordination_branch` "
            "from meta.json if the coordination topology was never used, "
            "then retry."
        ) from exc

    return main_repo_root, placement


@app.command(name="append-history")
def append_history(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    wp: str = typer.Option(..., "--wp", help=_HELP_WP_ID),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
    note: str = typer.Option(..., "--note", help="History note to append"),
) -> None:
    """Append a history entry via an ``InnerStateChanged`` ``note`` annotation.

    WP08 / FR-007 / T031: this cross-package (ACL-boundary) writer no longer
    mutates the WP prompt file's ``## Activity Log`` section directly -- it
    emits a ``note``-append delta through WP01's ``emit_inner_state_changed``.
    The write target is the coord-aware STATUS-partition mission directory
    (:func:`_resolve_mission_dir_or_fail` -- the SAME seam every other STATUS
    read/write in this module uses, e.g. ``accept_mission``'s
    ``materialize(mission_dir)``), never a ``Path.cwd()``-derived join
    (C-003 / #2647 -- see the SC-008 test).
    """
    cmd = "append-history"

    main_repo_root = _get_main_repo_root()
    # Existence/identity gate via the coord-aware read seam (typed miss
    # envelope). This is also the STATUS-partition mission directory the
    # annotation below is emitted into.
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    # FR-003 / T013: the WP prompt file is a WORK_PACKAGE_TASK (primary kind),
    # so its EXISTENCE is checked on the PRIMARY checkout -- never the
    # coordination worktree (the planning→coord transit is removed, C-005).
    # Resolve it through the canonical per-kind read seam (``_planning_read_dir``
    # → ``resolve_planning_read_dir``, the same seam the sibling planning reads
    # use), NOT a raw handle-blind ``primary_feature_dir_for_mission`` call: that
    # primitive composes the handle verbatim, so a bare ``mid8`` / full ULID /
    # numeric handle would land on a DIVERGENT dir than where the WP prompt
    # actually lives (the #2136/#2164 write/placement divergence). The seam
    # folds the handle to its canonical ``<slug>-<mid8>`` dir for every form
    # (and propagates ``MissionSelectorAmbiguous`` -- no silent pick).
    primary_mission_dir = _planning_read_dir(main_repo_root, mission)
    wp_path = _resolve_wp_file(primary_mission_dir / "tasks", wp)
    if wp_path is None:
        _fail_wp_not_found(cmd, wp, mission)
        return

    from specify_cli.status import WPInnerStateDelta
    from specify_cli.status import StoreError
    from specify_cli.status import emit_inner_state_changed

    timestamp = now_utc_stamp()
    # Byte-identical to the historical rendered Activity Log line (FR-007
    # no-content-loss): the note carries the fully-formatted entry so no
    # information is lost even before a dedicated notes-render surface lands.
    entry_text = f"- [{timestamp}] {actor}: {note}"

    try:
        emit_inner_state_changed(
            mission_dir,
            wp,
            WPInnerStateDelta(note=entry_text),
            actor=actor,
            mission_slug=mission,
            repo_root=main_repo_root,
        )
    except (ValueError, StoreError) as exc:
        # A failed emit still surfaces the orchestrator-api's own structured
        # envelope (never a bare traceback) -- ``_fail`` is typed ``NoReturn``.
        _fail(cmd, "HISTORY_COMMIT_FAILED", str(exc))
        return

    entry_id = "hist-" + uuid.uuid4().hex

    data = {
        **_mission_identity_payload(primary_mission_dir),
        "wp_id": wp,
        "history_entry_id": entry_id,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 8: accept-mission ──────────────────────────────────────────────


@app.command(name="accept-mission")
def accept_mission(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    actor: str = typer.Option(..., "--actor", help=_HELP_ACTOR),
) -> None:
    """Accept a mission after all WPs are approved or done."""
    cmd = "accept-mission"

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.status import materialize
    from specify_cli.core.dependency_graph import build_dependency_graph

    # STATUS read off the coord-aware dir; dependency graph (WP frontmatter,
    # PRIMARY-partition) off the primary surface (#2118).
    snapshot = materialize(mission_dir)
    dep_graph = build_dependency_graph(_planning_read_dir(main_repo_root, mission))

    # Check all WPs (from dep_graph) are approved/done; WPs with no events are implicitly planned.
    all_wp_ids = set(dep_graph.keys()) | set(snapshot.work_packages.keys())
    incomplete = [
        wp_id
        for wp_id in sorted(all_wp_ids)
        if wp_state_for(snapshot.work_packages.get(wp_id, {}).get("lane", Lane.PLANNED)).lane not in {Lane.APPROVED, Lane.DONE}
    ]
    if incomplete:
        _fail(
            cmd,
            "MISSION_NOT_READY",
            f"Mission has {len(incomplete)} incomplete WP(s)",
            {
                **_mission_identity_payload(mission_dir),
                "incomplete_wps": sorted(incomplete),
            },
        )
        return

    from specify_cli.acceptance import collect_feature_summary
    from specify_cli.config.path_conventions import PathConventionsConfigError
    from specify_cli.upgrade.pre30_guard import Pre30LayoutError

    try:
        summary = collect_feature_summary(main_repo_root, mission)
    except Pre30LayoutError as exc:
        # #1057 / squad Blocker 1: pre-3.0 lane-directory missions hard-reject
        # rather than producing a vacuous all-done summary. A mission whose layout
        # the runtime no longer reads is not acceptable until migrated, so it maps
        # to MISSION_NOT_READY; the full `spec-kitty upgrade` instruction rides in
        # the message field (keeping the orchestrator JSON envelope contract).
        _fail(cmd, "MISSION_NOT_READY", str(exc), _mission_identity_payload(mission_dir))
        return
    except PathConventionsConfigError as exc:
        _fail(
            cmd,
            "MISSION_NOT_READY",
            str(exc),
            {
                "message": str(exc),
                **_mission_identity_payload(mission_dir),
            },
        )
        return
    # Write acceptance record via centralized metadata writer
    from specify_cli.mission_metadata import record_acceptance

    meta = record_acceptance(
        mission_dir,
        accepted_by=actor,
        mode="orchestrator",
    )
    accepted_at = str(meta["accepted_at"])
    approved_wps = list(summary.lanes.get("approved", []))
    done_wps = list(summary.lanes.get("done", []))

    data = {
        **_mission_identity_payload(mission_dir),
        "accepted": True,
        "mode": "auto",
        "accepted_at": accepted_at,
        "accepted_wps": [*approved_wps, *done_wps],
        "approved_wps": approved_wps,
        "done_wps": done_wps,
        "merge_pending_wps": approved_wps,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── Command 9: merge-mission ───────────────────────────────────────────────


@app.command(name="merge-mission")
def merge_mission(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    target: str = typer.Option(None, "--target", help="Target branch to merge into (auto-detected from meta.json)"),
    strategy: str = typer.Option("merge", "--strategy", help="Merge strategy: merge, squash, or rebase"),
    push: bool = typer.Option(False, "--push", help="Push target branch after merge"),
) -> None:
    """Merge a lane-based mission into target."""
    cmd = "merge-mission"

    _SUPPORTED_STRATEGIES = frozenset(["merge", "squash", "rebase"])
    if strategy not in _SUPPORTED_STRATEGIES:
        _fail(
            cmd,
            "UNSUPPORTED_STRATEGY",
            f"Strategy '{strategy}' is not supported. Supported strategies: {sorted(_SUPPORTED_STRATEGIES)}",
            {"strategy": strategy, "supported": sorted(_SUPPORTED_STRATEGIES)},
        )
        return

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    preflight = _build_merge_preflight(main_repo_root, mission, target)
    if preflight.errors:
        _fail(
            cmd,
            "PREFLIGHT_FAILED",
            "Merge failed",
            {
                **_mission_identity_payload(mission_dir),
                "target_branch": preflight.target_branch,
                "errors": preflight.errors,
            },
        )
        return

    try:
        # #3131 C-007/T010: unset (None) so the mission's meta.json retention
        # policy governs — this CLI has no --delete-branch/--remove-worktree
        # flags of its own, so hardcoding True/True here silently bypassed a
        # retaining mission's policy every time (the exact NFR-003 gap).
        _execute_lane_merge(
            main_repo_root,
            mission_dir,
            mission,
            preflight.target_branch,
            strategy=strategy,
            push=push,
            delete_branch=None,
            remove_worktree=None,
        )
    except DestructiveOpRefused as exc:
        # #4753 finding B: DestructiveOpRefused is NOT a RuntimeError
        # (C-002) -- the except clause below never sees it, so this must be
        # caught first or it escapes as a raw traceback.
        _fail_from_destructive_op_refused(cmd, mission_dir, preflight.target_branch, exc)
    except RuntimeError as exc:
        _fail(
            cmd,
            "PREFLIGHT_FAILED",
            "Merge failed",
            {
                **_mission_identity_payload(mission_dir),
                "target_branch": preflight.target_branch,
                "errors": [str(exc)],
            },
        )
        return

    data = {
        **_mission_identity_payload(mission_dir),
        "merged": True,
        "target_branch": preflight.target_branch,
        "strategy": strategy,
        "worktree_removed": False,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(
        command=cmd,
        success=True,
        data=data,
    )
    _emit(envelope)


# ── specify / plan / tasks (WP03) ────────────────────────────────────────
#
# Thin, in-process adapters over the SAME JSON-mode service functions the
# host CLI's own ``specify``/``plan``/``tasks`` shims
# (``specify_cli.cli.commands.lifecycle``) already delegate to. NEVER shell
# out to the host CLI: each verb captures the delegate's single ``--json``
# stdout line, then re-emits it (enriched for ``specify``, raw for
# ``plan``/``tasks``) inside the canonical orchestrator-api envelope.


def _extract_json_payload(raw_output: str) -> dict[str, Any] | None:
    """Parse the one JSON object a delegate command printed to its stdout.

    Mirrors ``lifecycle._create_mission_for_specify_json``'s own line-scan
    (first line starting with ``{`` that parses as a JSON object) rather than
    assuming line 1 verbatim -- tolerant of incidental non-JSON stdout noise
    from the delegate without duplicating its parsing logic wholesale.
    """
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _classify_delegate_error(
    payload: dict[str, Any] | None,
    raw_output: str,
    *,
    fallback_code: str,
    fallback_message: str,
) -> tuple[str, str, dict[str, Any]]:
    """Classify a failed ``plan``/``tasks``/``specify`` delegate call, trusting
    any typed ``error_code`` the delegate already carries and falling back to
    a verb-specific structured code otherwise -- never a bare exception.

    ``specify`` uses the same seam (#3861): the mission-creation delegate now
    surfaces its duplicate-mission refusal as a typed
    ``MissionAlreadyExistsError`` whose ``error_code`` travels in the JSON
    error payload, so this trust-the-typed-code path is the ONLY
    already-exists classification -- the retired substring heuristic over
    the delegate's message prose could silently mislabel when wording
    changed.
    """
    if payload is None:
        message = raw_output.strip() or fallback_message
        return fallback_code, message, {"raw_output": raw_output}
    message = str(payload.get("error") or payload.get("message") or fallback_message)
    error_code = payload.get("error_code")
    if error_code:
        return str(error_code), message, payload
    return fallback_code, message, payload


# ── Command 10: specify ──────────────────────────────────────────────────


@app.command(name="specify")
def specify(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    mission_type: str = typer.Option(..., "--mission-type", help="Mission type (e.g., software-dev)"),
    topology: MissionTopology | None = typer.Option(
        None,
        "--topology",
        help=(
            "Create-time mission shape: single_branch | lanes | coord | lanes_with_coord. Default: context-derived (matches the host CLI's own --topology default)."
        ),
    ),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Create a mission scaffold, matching the host CLI's enriched ``specify --json`` contract.

    In-process only (FR-001): calls
    ``specify_cli.cli.commands.lifecycle._create_mission_for_specify_json``,
    the SAME enrichment step the host CLI's ``--json`` path runs (adds
    ``scaffold_only``/``spec_state``/``next_action``/``next_step`` on top of
    ``agent_feature.create_mission``'s raw payload) -- never the unenriched
    payload one layer beneath it.
    """
    cmd = "specify"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for specify")
        return
    _parse_policy_or_fail(cmd, policy)

    from specify_cli.cli.commands.lifecycle import _create_mission_for_specify_json

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _create_mission_for_specify_json(mission, mission_type, topology)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="MISSION_CREATE_FAILED",
            fallback_message="mission creation failed",
        )
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "MISSION_CREATE_FAILED",
            "specify produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # Belt-and-brace, matching ``plan``/``tasks``/``check_prerequisites``
    # (~2320/2383/2536): ``_create_mission_for_specify_json``'s own payload
    # already carries ``mission_slug`` (verified against production), so this
    # is a structural no-op on the normal path -- NOT business-payload
    # enrichment, it fills the ONE transport-contract identity field
    # (``upstream_contract.json``'s ``required_payload_fields``) every
    # orchestrator-api response must carry, only when the delegate omits it.
    #
    # Deliberately NOT a plain ``setdefault("mission_slug", mission)``: the
    # raw ``mission`` input is the PRE-mid8-suffix handle
    # (``mission_dir_name`` appends ``-<mid8>`` at creation --
    # ``lanes/branch_naming.py:488``), so it is not itself the canonical
    # slug once the mission exists on disk. Only resolve (and pay the extra
    # disk lookup) in the fallback branch, using the SAME
    # ``_mission_identity_payload(mission_dir)["mission_slug"]`` the siblings
    # read post-resolution -- the real, mid8-suffixed value -- rather than a
    # guess that could be wrong. Never overwrites a delegate-supplied value.
    if "mission_slug" not in payload:
        main_repo_root = _get_main_repo_root()
        mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
        payload["mission_slug"] = _mission_identity_payload(mission_dir)["mission_slug"]
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 11: plan ─────────────────────────────────────────────────────


@app.command(name="plan")
def plan(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Scaffold plan.md for a mission -- an unenriched pass-through of ``setup_plan``.

    FR-002 / Clarification 1: deliberately asymmetric with ``specify`` -- the
    host CLI's own ``--json`` path returns ``agent_feature.setup_plan``'s raw
    dict verbatim (``lifecycle.py`` adds no enrichment here), so this verb
    does the same. Do not add fields ``setup_plan`` does not already return.
    """
    cmd = "plan"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for plan")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent import mission as agent_feature

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            agent_feature.setup_plan(feature=mission, json_output=True)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="PLAN_SETUP_FAILED",
            fallback_message="plan scaffolding failed",
        )
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "PLAN_SETUP_FAILED",
            "plan produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # ``setup_plan``'s own payload already carries ``mission_slug`` (verified
    # against production); ``setdefault`` is a structural no-op belt-and-brace
    # here -- this is NOT business-payload enrichment (T011's asymmetry bar),
    # it fills the ONE transport-contract identity field
    # (``upstream_contract.json``'s ``required_payload_fields``) every
    # orchestrator-api response must carry, using the already-resolved input
    # identity -- never overwriting a delegate-supplied value.
    payload.setdefault("mission_slug", _mission_identity_payload(mission_dir)["mission_slug"])
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 12: tasks ────────────────────────────────────────────────────


@app.command(name="tasks")
def tasks(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Finalize WP task metadata -- an unenriched pass-through of ``finalize_tasks``.

    FR-003 / Clarification 1: same deliberate asymmetry as ``plan`` -- the
    host CLI's own ``--json`` path returns ``agent_feature.finalize_tasks``'s
    raw dict verbatim, so this verb does the same.
    """
    cmd = "tasks"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for tasks")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent import mission as agent_feature

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            agent_feature.finalize_tasks(feature=mission, json_output=True)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="TASKS_FINALIZE_FAILED",
            fallback_message="tasks finalization failed",
        )
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "TASKS_FINALIZE_FAILED",
            "tasks produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # finalize_tasks' raw payload does NOT carry ``mission_slug`` (verified
    # against production) -- unlike ``plan``, this is a genuine gap the
    # transport contract's ``required_payload_fields`` requires filling. Same
    # non-enrichment rationale as ``plan`` above: fills the one identity field
    # from the already-resolved input, adds nothing else.
    payload.setdefault("mission_slug", _mission_identity_payload(mission_dir)["mission_slug"])
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 13: check-prerequisites ─────────────────────────────────────────


_FEATURE_CONTEXT_UNRESOLVED = "FEATURE_CONTEXT_UNRESOLVED"


def _sanitize_forbidden_error_code(value: Any, forbidden: str, replacement: str) -> Any:
    """Recursively replace every occurrence of *forbidden* with *replacement*,
    at any depth of nested dicts/lists (PR-TESTS-002), including as a dict
    KEY and as a SUBSTRING of a larger string -- not only a whole-value
    match.

    ``_classify_check_prerequisites_error`` translates the top-level
    ``error_code`` correctly, but the raw delegate ``payload`` it also
    returns (spread verbatim into the envelope's ``data``) still carries its
    OWN ``error_code`` key with the untranslated forbidden value -- a leak
    of the terminology-canon-forbidden string one level down, in the SAME
    response whose top-level ``error_code`` claims to have translated it.
    Sanitizing recursively (not just the payload's top-level ``error_code``
    key) closes the leak at whatever nesting level it appears, matching the
    "no forbidden token anywhere in the serialized response" bar this fix's
    regression test asserts.

    A verifier (PR-TESTS-002 residual) defeated an earlier whole-value-only,
    values-only version of this function two ways: the forbidden token as a
    dict KEY (never visited -- only ``.items()`` VALUES were recursed), and
    the forbidden token as a SUBSTRING of a longer string (an exact ``==``
    match against the whole string never fires). Both are closed here: keys
    are sanitized by substring replacement exactly like values, and string
    values use ``str.replace`` (containment) rather than ``==`` (whole-value
    equality), so a forbidden token embedded in a larger string is scrubbed
    without needing the whole string to equal it.
    """
    if isinstance(value, dict):
        return {
            (_sanitize_forbidden_error_code(k, forbidden, replacement) if isinstance(k, str) else k): (_sanitize_forbidden_error_code(v, forbidden, replacement))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_forbidden_error_code(v, forbidden, replacement) for v in value]
    if isinstance(value, str) and forbidden in value:
        return value.replace(forbidden, replacement)
    return value


def _classify_check_prerequisites_error(payload: dict[str, Any] | None, raw_output: str) -> tuple[str, str, dict[str, Any]]:
    """Classify a failed ``check-prerequisites`` delegate call.

    The host CLI's own detection-failure payload carries
    ``error_code: "FEATURE_CONTEXT_UNRESOLVED"`` (``mission_check_prerequisites.py``)
    -- a feature-named code that must NEVER cross onto the orchestrator-api
    surface verbatim (Terminology Canon; ``upstream_contract.json``'s
    ``forbidden_error_codes`` bans the sibling ``FEATURE_NOT_FOUND``/
    ``FEATURE_NOT_READY`` for the identical reason). This is the ONE place
    that code is translated to this file's canonical ``MISSION_NOT_FOUND`` --
    every other typed ``error_code`` the delegate carries is trusted verbatim,
    mirroring ``_classify_delegate_error``. The translation is applied to the
    WHOLE returned payload (``_sanitize_forbidden_error_code``), not just the
    top-level ``error_code`` this function returns as its first tuple
    element -- the untranslated payload's own nested ``error_code`` key was
    leaking the forbidden string into ``data.error_code`` (PR-TESTS-002).
    """
    if payload is None:
        message = raw_output.strip() or "check-prerequisites failed"
        return "CHECK_PREREQUISITES_FAILED", message, {"raw_output": raw_output}
    message = str(payload.get("error") or payload.get("message") or "check-prerequisites failed")
    error_code = payload.get("error_code")
    if error_code == _FEATURE_CONTEXT_UNRESOLVED:
        sanitized = cast(
            "dict[str, Any]",
            _sanitize_forbidden_error_code(payload, _FEATURE_CONTEXT_UNRESOLVED, "MISSION_NOT_FOUND"),
        )
        return "MISSION_NOT_FOUND", message, sanitized
    if error_code:
        return str(error_code), message, payload
    return "CHECK_PREREQUISITES_FAILED", message, payload


@app.command(name="check-prerequisites")
def check_prerequisites(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    include_tasks: bool = typer.Option(
        False,
        "--include-tasks",
        help="Include tasks.md validation (matches the host CLI's own --include-tasks default)",
    ),
) -> None:
    """Read-only mission-prerequisite context for ``/spec-kitty.analyze`` (FR-004).

    C-002: this verb supplies context ONLY -- it never performs `analyze`'s
    cross-artifact reasoning itself (mirrors ``start-review``'s "cannot
    perform WP implementation itself" pattern). No ``--policy`` is required
    (read-only, per spec Edge Cases: "Read-only verbs (check-prerequisites,
    design-status) do not require --policy").

    In-process only (FR-001-style parity): calls the host CLI's OWN
    ``check_prerequisites`` Typer command function
    (``mission_check_prerequisites.py:498``) directly -- the exact
    established pattern WP03's ``plan``/``tasks`` verbs already use for a
    registered ``agent mission`` Typer command (``setup_plan``/
    ``finalize_tasks`` are registered identically:
    ``app.command(...)(func)`` in ``mission.py``), so field-parity with
    ``agent mission check-prerequisites --json --include-tasks`` is
    guaranteed by construction rather than by re-deriving
    ``validate_feature_structure``'s shaping logic a second time.
    """
    cmd = "check-prerequisites"

    main_repo_root = _get_main_repo_root()
    # Existence gate FIRST via the coord-aware read seam (consistent
    # MISSION_NOT_FOUND envelope shared with every other read endpoint in
    # this module) -- the delegate below is only reached for a mission that
    # is already known to exist.
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

    from specify_cli.cli.commands.agent.mission_check_prerequisites import (
        check_prerequisites as _host_check_prerequisites,
    )

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _host_check_prerequisites(feature=mission, json_output=True, include_tasks=include_tasks)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_check_prerequisites_error(payload, raw_output)
        _fail(cmd, error_code, message, error_data)
        return

    raw_output = capture.getvalue()
    payload = _extract_json_payload(raw_output)
    if payload is None:
        _fail(
            cmd,
            "CHECK_PREREQUISITES_FAILED",
            "check-prerequisites produced no parseable JSON payload",
            {"raw_output": raw_output},
        )
        return
    # validate_feature_structure()'s own shape does not carry ``mission_slug``
    # (verified against production) -- same transport-contract identity fill
    # as ``plan``/``tasks`` above, never business-payload enrichment.
    payload.setdefault("mission_slug", _mission_identity_payload(mission_dir)["mission_slug"])
    validate_outbound_payload(payload, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=payload)
    _emit(envelope)


# ── Command 14: record-analysis ─────────────────────────────────────────────


@dataclass
class _TimedWriteOutcome:
    """Outcome of a timeout-bounded call to the underlying write path (SK-93).

    ``completed`` is set by the worker thread itself in a ``finally`` block
    (never inferred from ``Thread.is_alive()`` after ``join`` -- a TOCTOU-safe
    signal). NEITHER field drives ``record-analysis``'s ``success`` verdict --
    that is determined SOLELY by re-reading the artifact off disk afterward;
    this dataclass exists only to enrich the failure envelope's diagnostic
    ``data`` (e.g. surfacing whether the underlying call raised or is still
    running in a leaked daemon thread).
    """

    completed: bool = False
    result: AnalysisReportResult | None = None
    raised: Exception | None = None


def _run_write_with_timeout(fn: Callable[[], AnalysisReportResult], *, timeout_seconds: float) -> _TimedWriteOutcome:
    """Run ``fn`` bounded by ``timeout_seconds`` in a daemon worker thread.

    A REAL enforced bound (NFR-004(b) / T020): ``Thread.join(timeout=...)``
    returns control to the caller once ``timeout_seconds`` elapses regardless
    of whether the worker thread has finished -- this is not a decorative
    ``try/except TimeoutError`` that never actually fires (Python offers no
    safe thread-kill primitive, so a still-running worker is left as a leaked
    daemon thread, never blocking process exit). Never re-raises: any
    exception the underlying call raises is captured as diagnostic data, not
    propagated -- ``record-analysis``'s success determination never depends
    on whether this call raised, returned, or is still hanging (SK-93).
    """
    outcome = _TimedWriteOutcome()

    def _worker() -> None:
        try:
            outcome.result = fn()
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: captures
            # ANY failure from the underlying write path (including a test
            # double's injected raise) as diagnostic data. Never re-raised;
            # the re-read off disk is the sole success signal (SK-93).
            outcome.raised = exc
        finally:
            outcome.completed = True

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    return outcome


@dataclass(frozen=True)
class _AnalysisReportReread:
    """The re-read artifact state -- the SOLE success signal (SK-93)."""

    path: Path
    verdict: str | None
    generated_at: str | None


def _reread_analysis_report(path: Path) -> _AnalysisReportReread | None:
    """Re-read ``analysis-report.md`` off disk, or ``None`` if absent.

    Never trusts the write call's own return/raise/hang behavior (SK-93) --
    this reads whatever landed on disk, if anything, after the write
    attempt returned or the enforced timeout fired.
    """
    if not path.exists():
        return None
    from specify_cli.frontmatter import FrontmatterError, FrontmatterManager

    try:
        frontmatter, _body = FrontmatterManager().read(path)
    except FrontmatterError:
        return _AnalysisReportReread(path=path, verdict=None, generated_at=None)
    verdict = frontmatter.get("verdict")
    generated_at = frontmatter.get("generated_at")
    return _AnalysisReportReread(
        path=path,
        verdict=str(verdict) if verdict is not None else None,
        generated_at=str(generated_at) if generated_at is not None else None,
    )


def _is_strictly_after(candidate_iso: str, reference_iso: str) -> bool:
    """True if ``candidate_iso`` is a strictly later instant than ``reference_iso``.

    Parses both through :func:`kernel.clock.parse_iso` (the single wall-clock
    door, C-008) rather than comparing raw strings -- an explicit, honest
    comparison instead of relying on ISO-8601 lexicographic-ordering luck.
    """
    from kernel.clock import parse_iso

    try:
        return parse_iso(candidate_iso) > parse_iso(reference_iso)
    except ValueError:
        return False


def _read_record_analysis_body(input_file: str) -> str:
    """Read the analysis report body from ``--input-file``, or stdin for ``-``.

    Mirrors the host CLI's own ``record_analysis``'s ``--input-file`` flag
    semantics exactly (``mission_record_analysis.py``).
    """
    if input_file == "-":
        import sys

        return sys.stdin.read()
    return Path(input_file).read_text(encoding="utf-8")


def _classify_record_analysis_failure(
    *,
    submitted_verdict: str,
    reread: _AnalysisReportReread | None,
    call_start: str,
) -> tuple[str, str]:
    """Classify a ``record-analysis`` failure into a structured ``(error_code, message)``.

    Distinguishes "write did not happen" (no artifact re-read confirms a
    fresh write after ``call_start`` -- SC-005(c)'s stale-but-matching-verdict
    shape included) from "write happened, signal was noise" (a confirmed
    fresh write whose verdict is not trustworthy -- either it disagrees with
    what THIS call submitted, or the submission itself carried no valid
    carrier and computed to ``unknown``, SK-06/#3133) -- never collapsed into
    one generic code (T018 step 3).
    """
    from specify_cli.analysis_report import VERDICT_UNKNOWN

    write_confirmed = reread is not None and reread.generated_at is not None and _is_strictly_after(reread.generated_at, call_start)
    if not write_confirmed:
        return "RECORD_ANALYSIS_WRITE_NOT_CONFIRMED", (
            "record-analysis could not confirm a fresh write: no analysis-report.md with a generated_at timestamp later than this call's start was found on disk."
        )
    if submitted_verdict == VERDICT_UNKNOWN:
        return "RECORD_ANALYSIS_VERDICT_UNRELIABLE", (
            "The submitted analysis report carried no valid "
            "analysis-findings/v1 carrier, so no reliable verdict could be "
            "recorded (verdict: unknown is never reported as success)."
        )
    return "RECORD_ANALYSIS_VERDICT_UNRELIABLE", (
        f"analysis-report.md was written but its verdict ({reread.verdict if reread else None!r}) does not match the submitted verdict ({submitted_verdict!r})."
    )


def _do_record_analysis_write(
    *,
    write_feature_dir: Path,
    main_repo_root: Path,
    body: str,
    agent: str | None,
    mission_slug: str,
) -> AnalysisReportResult:
    """The underlying write path: ``write_analysis_report`` + a best-effort commit.

    Option (a) from plan.md § (j) (NFR-004(b)'s explicitly offered
    mitigation): calls ``write_analysis_report``/``commit_for_mission``
    directly rather than going through ``record_analysis``'s full CLI
    wrapper, so ``record_analysis``'s own unbounded
    ``trigger_feature_dossier_sync_if_enabled`` tail
    (``mission_record_analysis.py:384-388``, bounded only against a *raised*
    exception via ``contextlib.suppress(Exception)`` -- NOT against a *hang*)
    is never invoked at all. This function itself additionally runs under
    :func:`_run_write_with_timeout` as defense-in-depth against any OTHER
    hang (e.g. a wedged git subprocess inside ``commit_for_mission``).
    """
    from specify_cli.analysis_report import write_analysis_report

    result = write_analysis_report(
        feature_dir=write_feature_dir,
        repo_root=main_repo_root,
        body=body,
        analyzer_agent=agent,
    )

    # Best-effort commit -- mirrors mission_record_analysis.py's own narrowed
    # exception set (WP03/#3128 there): a commit failure (e.g. a protected
    # target ref) never undoes the write already on disk.
    with contextlib.suppress(subprocess.CalledProcessError, OSError, RuntimeError, ValueError):
        from mission_runtime import MissionArtifactKind
        from specify_cli.coordination.commit_router import commit_for_mission
        from specify_cli.core.paths import get_feature_target_branch
        from specify_cli.git.protection_policy import ProtectionPolicy

        commit_for_mission(
            repo_root=main_repo_root,
            mission_slug=mission_slug,
            files=(result.path,),
            message=f"docs(record-analysis): record analysis report for mission {mission_slug}",
            policy=ProtectionPolicy.resolve(main_repo_root),
            kind=MissionArtifactKind.ANALYSIS_REPORT,
            target_branch=get_feature_target_branch(main_repo_root, mission_slug),
        )
    return result


@app.command(name="record-analysis")
def record_analysis(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
    input_file: str = typer.Option(
        "-",
        "--input-file",
        help="Markdown report path, or '-' to read the report body from stdin",
    ),
    agent: str | None = typer.Option(None, "--agent", help=_HELP_ANALYZER_AGENT),
    policy: str = typer.Option(None, "--policy", help=_HELP_POLICY),
) -> None:
    """Persist an ``/spec-kitty.analyze`` report, verified against disk (FR-005).

    NFR-004 / SK-93 (verified): a subprocess/call-level success signal
    (return code, "did not raise") is UNTRUSTWORTHY -- SK-93 documented
    ``record-analysis`` reporting a false timeout FAILURE after a write had
    already genuinely succeeded. This verb instead:

    1. Captures ``now_utc_iso()`` immediately before invoking the write path.
    2. Calls ``write_analysis_report``/``commit_for_mission`` directly
       (bypassing ``record_analysis``'s own unbounded dossier-sync trigger
       entirely -- option (a), plan.md § (j)), under an enforced
       :func:`_run_write_with_timeout` bound as defense-in-depth.
    3. Re-reads ``analysis-report.md`` off disk unconditionally afterward.
       ``success: true`` ONLY if BOTH (a) the re-read ``verdict`` matches
       what THIS call submitted, AND (b) the re-read ``generated_at`` is
       STRICTLY LATER than the call-start timestamp -- a verdict-string
       match alone is never sufficient (distinguishes a genuine fresh write
       from a stale, coincidentally-matching pre-existing artifact).

    SK-06 / #3133: an ``unknown`` verdict (no valid ``analysis-findings/v1``
    carrier in the submitted body) is NEVER reported as ``success: true``,
    even when the write genuinely, freshly succeeds -- silently writing
    ``verdict: unknown`` for an explicitly-intended report is this repo's
    dominant failure mode and this verb refuses to propagate it as success.

    A mutating verb: ``--policy`` is required (``POLICY_METADATA_REQUIRED``
    pattern, matching ``specify``/``plan``/``tasks``).
    """
    cmd = "record-analysis"

    if not policy:
        _fail(cmd, "POLICY_METADATA_REQUIRED", "--policy is required for record-analysis")
        return
    _parse_policy_or_fail(cmd, policy)

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
    mission_slug = _mission_identity_payload(mission_dir)["mission_slug"]

    # PR-CONTRACT-001 (host-CLI parity, R3-confirmed live ordering fork):
    # placement resolution + the dirty-worktree preflight run BEFORE the
    # body is read/validated -- matching the host CLI's own
    # ``mission_record_analysis.record_analysis`` ordering EXACTLY
    # (placement -> dirty-tree preflight -> THEN ``body = sys.stdin.read()``,
    # mission_record_analysis.py's ``record_analysis`` function). Pre-fix,
    # this verb read/validated the body FIRST, so an identical on-disk state
    # (dirty tree + empty/malformed body) reported a DIFFERENT first
    # error_code than the host CLI for the same request -- this is the
    # THIRD instance of that ordering-fork class in this mission (after
    # WP05-001/WP08-001). See ``tests/specify_cli/orchestrator_api/
    # test_check_prerequisites_record_analysis.py``'s
    # ``_host_record_analysis_error_code`` helper and its docstring
    # for the reusable, verb-agnostic parity-test pattern added alongside
    # this fix (and for why a production-code "by construction" ordering
    # guard was judged infeasible within this diff, not silently skipped).
    from specify_cli.cli.commands.agent.mission_feature_resolution import _kind_for_artifact
    from specify_cli.cli.commands.agent.mission_record_analysis import (
        _enforce_analysis_report_write_preflight,
        _require_record_analysis_placement,
        _resolve_record_analysis_placement_ref,
    )
    from mission_runtime import placement_seam

    placement_ref = _resolve_record_analysis_placement_ref(main_repo_root, mission_dir)
    try:
        placement_ref = _require_record_analysis_placement(placement_ref, mission_slug=mission_slug)
    except PlacementResolutionRequired as exc:
        _fail(cmd, "PLACEMENT_RESOLUTION_REQUIRED", str(exc), {"mission_slug": mission_slug})
        return

    capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(capture):
            _enforce_analysis_report_write_preflight(main_repo_root, json_output=True, placement_ref=placement_ref, mission_slug=mission_slug)
    except typer.Exit:
        raw_output = capture.getvalue()
        payload = _extract_json_payload(raw_output)
        error_code, message, error_data = _classify_delegate_error(
            payload,
            raw_output,
            fallback_code="DIRTY_WORKTREE",
            fallback_message="record-analysis dirty-tree preflight failed",
        )
        error_data.setdefault("mission_slug", mission_slug)
        _fail(cmd, error_code, message, error_data)
        return

    try:
        body = _read_record_analysis_body(input_file)
    except OSError as exc:
        _fail(
            cmd,
            "RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND",
            f"Could not read --input-file {input_file!r}: {exc}",
            {"mission_slug": mission_slug},
        )
        return
    if not body.strip():
        _fail(cmd, "RECORD_ANALYSIS_EMPTY_BODY", "Analysis report body is empty", {"mission_slug": mission_slug})
        return

    from specify_cli.analysis_report import VERDICT_UNKNOWN, FindingsCarrierError, parse_structured_findings

    try:
        structured = parse_structured_findings(body)
    except FindingsCarrierError as exc:
        _fail(cmd, "RECORD_ANALYSIS_MALFORMED_CARRIER", str(exc), {"mission_slug": mission_slug})
        return
    submitted_verdict = structured.verdict if structured is not None else VERDICT_UNKNOWN

    write_feature_dir = placement_seam(main_repo_root, mission_slug).read_dir(_kind_for_artifact("spec"))

    # Step 1 (NFR-004 / SK-93): the call-start timestamp, captured
    # IMMEDIATELY before invoking the write path -- everything above this
    # line is preflight/validation, not "the underlying write call".
    call_start = now_utc_iso()

    def _do_write() -> AnalysisReportResult:
        return _do_record_analysis_write(
            write_feature_dir=write_feature_dir,
            main_repo_root=main_repo_root,
            body=body,
            agent=agent,
            mission_slug=mission_slug,
        )

    write_outcome = _run_write_with_timeout(_do_write, timeout_seconds=_RECORD_ANALYSIS_TIMEOUT_SECONDS)

    # Step 3 (NFR-004 / SK-93): unconditional re-read -- the SOLE success
    # signal, regardless of whether the call above returned, raised, or is
    # still hanging in a leaked daemon thread.
    report_path = write_feature_dir / "analysis-report.md"
    reread = _reread_analysis_report(report_path)

    write_confirmed = reread is not None and reread.generated_at is not None and _is_strictly_after(reread.generated_at, call_start)
    success = write_confirmed and submitted_verdict != VERDICT_UNKNOWN and reread is not None and reread.verdict == submitted_verdict

    if success and reread is not None:
        data = {
            **_mission_identity_payload(mission_dir),
            "path": str(reread.path),
            "verdict": reread.verdict,
            "generated_at": reread.generated_at,
        }
        validate_outbound_payload(data, "orchestrator_api")
        envelope = make_envelope(command=cmd, success=True, data=data)
        _emit(envelope)
        return

    error_code, message = _classify_record_analysis_failure(submitted_verdict=submitted_verdict, reread=reread, call_start=call_start)
    failure_data: dict[str, Any] = {"mission_slug": mission_slug, "submitted_verdict": submitted_verdict}
    if reread is not None:
        failure_data["reread_verdict"] = reread.verdict
        failure_data["reread_generated_at"] = reread.generated_at
    if not write_outcome.completed:
        failure_data["underlying_call_timed_out"] = True
    elif write_outcome.raised is not None:
        failure_data["underlying_call_error"] = str(write_outcome.raised)
    _fail(cmd, error_code, message, failure_data)


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


@app.command(name="open-decision")
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

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

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
        **_mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": "open",
        "idempotent": resp.idempotent,
        "artifact_path": resp.artifact_path,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


@app.command(name="resolve-decision")
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

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

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
        **_mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


@app.command(name="defer-decision")
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

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

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
        **_mission_identity_payload(mission_dir),
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


@app.command(name="cancel-decision")
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

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

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
        **_mission_identity_payload(mission_dir),
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


@app.command(name="answer-decision")
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

    main_repo_root = _get_main_repo_root()
    # Existence gate FIRST via the coord-aware read seam (consistent
    # MISSION_NOT_FOUND envelope shared with every other read/write endpoint
    # in this module) -- the runtime resolution below is only reached for a
    # mission already known to exist.
    _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)

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


# ---------------------------------------------------------------------------
# Command: design-status (WP06, FR-010)
#
# A narrow, design-phase-only reduction over on-disk artifact presence
# (spec.md/plan.md/tasks/-finalized/analysis-report.md, all PRIMARY-partition)
# and the decisions/index.json ledger (COORD-partition) -- spec Clarification
# 6. Mirrors list-ready's own "no state transition, no event emission"
# read-only contract: no --policy required, reduces state rather than
# invoking the full DAG engines.
#
# HARD CONSTRAINT (Clarification 6): never import or call
# resolve_next_workflow_action (_internal_runtime/planner.py) or
# decide_next/_resolve_next_unified_step/runtime_bridge.query_current_state --
# both return a WP-loop/run-state-shaped payload (action/wp_id/prompt_file),
# not FR-010's four design-phase fields, and decide_next's query path
# materializes/reads a runtime run (get_or_start_run) as a side effect this
# read-only verb must not depend on. A reviewer should reject any import of
# either.
# ---------------------------------------------------------------------------


def _tasks_are_finalized(mission_dir: Path) -> bool:
    """True once ``finalize-tasks`` has bootstrapped canonical status for at
    least one WP -- the SAME signal ``bootstrap_canonical_state``
    (``status/bootstrap.py``) writes, and the SAME reduction ``list-ready``
    already performs via ``reduce(read_events(mission_dir))`` (T029: reuse
    finalize-tasks's own signal, not a new heuristic). A ``tasks/`` directory
    merely populated by an earlier tasks-outline/tasks-packages pass does
    NOT set this -- only finalize-tasks's own bootstrap write does (verified
    against ``status/bootstrap.py``: ``bootstrap_canonical_state`` is called
    exclusively from the finalize-tasks command family, never from the
    outline/packages phases).

    Torn/truncated read handling (ledger SK-131, WP06-001 review finding):
    two DISTINCT corruption shapes, two distinct defenses --

    1. A genuinely torn line (an unlocked-writer race landing mid-read;
       historically -- as of 2026-08 -- only 2 of 6 ``status.events.jsonl``
       writers took the mission status lock; WP01 of
       fsm-write-path-integrity-01M1TZV6 serialized all seven writer
       families, see that mission's ``design-notes/WP01-lock-rules.md``)
       breaks JSON parsing itself: ``read_events`` raises
       ``StoreError`` on a malformed JSON line or invalid event structure.
       This function does NOT catch that exception -- it propagates to
       ``design_status``, which turns it into a structured
       ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` failure envelope instead of
       guessing.
    2. A rollback-truncated log (``coordination/transaction.py``'s
       ``_rollback``: ``fh.truncate(self._pre_emit_size)``, a byte offset
       captured BEFORE the append began) does NOT break JSON parsing --
       the file is append-only, so truncating to a pre-append offset
       always lands on a line boundary and every remaining line is still
       valid JSON. ``StoreError`` never fires for this shape, so (1)'s
       defense does not catch it: silently reducing the truncated log
       would return a plausible-but-wrong ``current_phase``/
       ``next_action`` snapshot, exactly the silent-success failure class
       this repo names as dominant (live-reproduced: dropping a real
       tasks-finalized mission's trailing bootstrap event line whole
       returned ``current_phase: "plan"`` with no error).

       Defense: a structural drift check against ``status.json`` --
       finalize-tasks's own ``bootstrap_canonical_state`` already
       materializes it (``status/bootstrap.py``) as a persisted,
       INDEPENDENT record of "these WP ids are known", written via
       atomic tmp-then-rename (``status/reducer.py::materialize``), so it
       cannot itself be torn. If the persisted ``work_packages`` set
       names a WP id the FRESH event-log reduction no longer contains,
       the event log lost information relative to the last durable
       materialization -- the SAME ``SNAPSHOT_DRIFT`` concept
       ``audit/classifiers/status_json.py`` already names for
       ``doctor mission-state --fix`` (issue #1782), reused here for this
       read path rather than inventing a parallel one. That drift is
       surfaced as ``StoreError`` so it flows through the SAME
       ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` handling as (1) -- one
       failure code for "the log cannot be trusted", regardless of which
       of the two shapes broke it.

       This does not require modeling ``_rollback`` exactly: its own
       truncate-then-restore-status.json sequence is two independently
       ``try/except OSError``-guarded steps (transaction.py:922-971), not
       one atomic operation, so a crash or I/O failure between them
       leaves precisely this asymmetric state on disk -- truncated events,
       stale-but-larger status.json -- on the real rollback path itself,
       not only via the live reproduction's direct file edit.

    Inode replacement (adjacent hazard, examined): CANNOT occur for
    ``status.events.jsonl`` specifically, because every writer mutates the
    file'S CONTENT in place through the SAME inode -- ``append_event``
    opens in ``"a"`` mode, ``_rollback`` opens in ``"ab"`` mode and
    truncates -- neither ever ``os.replace()``s a new inode over this
    path (unlike ``status.json``/``decisions/index.json``, which DO use
    tmp-then-rename, and are safe for the opposite reason: a reader who
    already holds an fd open before a rename keeps reading the old
    inode's complete content; a reader who opens after gets the fully-new
    inode's complete content -- either way, no torn/mixed read is
    possible via rename). No reader here can observe a page composed of
    two different inodes' bytes, because only one inode ever exists for
    this file.
    """
    from specify_cli.status import StoreError, read_events, reduce

    snapshot = reduce(read_events(mission_dir))
    _check_no_snapshot_drift(mission_dir, snapshot)
    return bool(snapshot.work_packages)


def _check_no_snapshot_drift(mission_dir: Path, snapshot: StatusSnapshot) -> None:
    """Raise ``StoreError`` if persisted ``status.json`` knows about a WP the
    freshly-reduced event log no longer contains (WP06-001 remediation).

    ``status.json`` is written by ``status/reducer.py::materialize`` via
    tmp-then-rename atomic replace, so a reader always sees either the
    fully-old or fully-new file, never a partial one -- there is no
    torn-read hazard on THIS side of the comparison. Its absence (no
    finalize-tasks bootstrap has ever run for this mission) is not drift;
    there is simply no persisted record yet to compare against.
    """
    from specify_cli.status import SNAPSHOT_FILENAME, StoreError

    status_json_path = mission_dir / SNAPSHOT_FILENAME
    if not status_json_path.exists():
        return

    try:
        persisted = json.loads(status_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(f"status.json could not be read for snapshot-drift comparison: {exc}") from exc

    persisted_wp_ids = set(persisted.get("work_packages") or {})
    fresh_wp_ids = set(snapshot.work_packages)
    missing = persisted_wp_ids - fresh_wp_ids
    if missing:
        raise StoreError(
            "snapshot drift: status.json's persisted work_packages set "
            f"names {sorted(missing)!r}, which the freshly-reduced "
            "status.events.jsonl no longer contains -- treating this as a "
            "torn/truncated event-log read (SNAPSHOT_DRIFT, cf. "
            "audit/classifiers/status_json.py, issue #1782) rather than "
            "trusting a silently-shrunk reduction"
        )


def _open_decisions(mission_dir: Path) -> list[dict[str, str]]:
    """Return ``{decision_id, origin}`` for every OPEN entry in the
    decisions ledger, regardless of which design phase opened it (spec
    Acceptance Scenario 2: an open decision from an earlier phase still
    blocks phase advancement).

    ``decisions/index.json`` is written via ``tmp-then-rename`` atomic
    replace (``decisions/store.py::_atomic_write``), so -- unlike
    ``status.events.jsonl`` -- there is no torn-read hazard here: a reader
    always sees either the fully-old or fully-new file, never a partial one.
    """
    from specify_cli.decisions.store import load_index

    index = load_index(mission_dir)
    return [{"decision_id": entry.decision_id, "origin": entry.origin_flow.value} for entry in index.entries if entry.status.value == "open"]


def _reduce_design_status(planning_dir: Path, mission_dir: Path) -> dict[str, Any]:
    """The core FR-010 reduction: ``current_phase``/``next_action`` from
    on-disk artifact presence, ``open_decisions`` from the ledger.

    ``planning_dir`` is the PRIMARY-surface mission dir (``spec.md``/
    ``plan.md``/``tasks/``/``analysis-report.md`` -- all PRIMARY-partition
    kinds per ``mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS``).
    ``mission_dir`` is the COORD-aware status dir (``status.events.jsonl``/
    ``decisions/index.json`` -- both STATUS_STATE-kind), the SAME
    resolution ``list-ready`` already uses for its own event-log reduction.

    Phase naming: ``current_phase`` names the phase whose artifact is
    present but not yet superseded by the next phase's artifact (matching
    spec Acceptance Scenario 1's literal "spec.md scaffolded ->
    current_phase: specify" example); ``next_action`` always names the VERB
    the host should call next. An open decision overrides ``next_action``
    to ``resolve-decision`` regardless of phase (Acceptance Scenario 2).
    """
    spec_exists = (planning_dir / "spec.md").exists()
    plan_exists = (planning_dir / "plan.md").exists()
    tasks_finalized = _tasks_are_finalized(mission_dir)
    analysis_exists = (planning_dir / "analysis-report.md").exists()

    current_phase: str
    next_action: str | None
    if not spec_exists:
        current_phase, next_action = "specify", "specify"
    elif not plan_exists:
        current_phase, next_action = "specify", "plan"
    elif not tasks_finalized:
        current_phase, next_action = "plan", "tasks"
    elif not analysis_exists:
        current_phase, next_action = "tasks", "check-prerequisites"
    else:
        current_phase, next_action = "analyze", None

    open_decisions = _open_decisions(mission_dir)
    if open_decisions:
        next_action = "resolve-decision"

    return {
        "current_phase": current_phase,
        "next_action": next_action,
        "open_decisions": open_decisions,
    }


@app.command(name="design-status")
def design_status(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
) -> None:
    """Read-only design-phase status query (FR-010) -- mirrors ``list-ready``'s
    no-state-transition, no-event-emission, no-``--policy`` contract for the
    design pipeline instead of the WP loop.

    Never delegates to ``resolve_next_workflow_action`` or
    ``decide_next``/``query_current_state`` -- see the Clarification-6
    module comment above ``_tasks_are_finalized``.
    """
    cmd = "design-status"

    main_repo_root = _get_main_repo_root()
    mission_dir = _resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
    planning_dir = _planning_read_dir(main_repo_root, mission)

    from pydantic import ValidationError

    from specify_cli.decisions.store import DecisionIndexReadError
    from specify_cli.status import StoreError

    try:
        reduction = _reduce_design_status(planning_dir, mission_dir)
    except StoreError as exc:
        _fail(
            cmd,
            "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
            f"status.events.jsonl could not be read cleanly for mission {mission!r}: {exc}",
            {"mission_slug": mission, "error": str(exc)},
        )
        return
    except (json.JSONDecodeError, ValidationError, DecisionIndexReadError) as exc:
        # ``_open_decisions`` -> ``decisions.store.load_index`` reads
        # ``decisions/index.json`` inside the SAME reduction this ``try``
        # guards -- a hand-corrupted index (malformed JSON, non-UTF-8, or
        # schema-invalid) now fails closed as the wrapping
        # ``DecisionIndexReadError`` (#4642); the raw ``json.JSONDecodeError`` /
        # pydantic ``ValidationError`` are retained defensively. None is a
        # ``StoreError``. Reuse the SAME typed STORE error envelope the
        # torn-``status.events.jsonl`` shapes above already produce, rather
        # than letting either exception escape un-enveloped.
        _fail(
            cmd,
            "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
            f"decisions/index.json could not be read cleanly for mission {mission!r}: {exc}",
            {"mission_slug": mission, "error": str(exc)},
        )
        return

    data = {
        **_mission_identity_payload(mission_dir),
        **reduction,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)


__all__ = ["app"]
