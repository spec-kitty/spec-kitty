"""Decision Moment CLI subgroup — ``spec-kitty agent decision ...``

Exposes six subcommands that map directly to the decisions service, verifier,
and store:

    open      — open a new decision moment
    resolve   — resolve a decision with a final answer
    defer     — defer a decision for later resolution
    cancel    — cancel a decision (no longer relevant)
    verify    — cross-check deferred decisions against inline markers
    list      — list the mission's recorded decision moments

All subcommands output JSON to stdout and exit 0 on success, 1 on structured error.
"""

from __future__ import annotations

from specify_cli.core.paths import locate_project_root
from specify_cli.missions._read_path_resolver import (
    StatusReadPathNotFound,
    resolve_feature_dir_for_mission,
)
import json
import re as _re
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer

if TYPE_CHECKING:
    # TYPE_CHECKING-only (``from __future__ import annotations`` above keeps
    # these out of the runtime namespace): coord-artifact-single-home-01M3V4BE
    # WP09's two new error-rendering helpers need the types for their
    # signatures, but ``specify_cli.coordination.*`` / ``specify_cli.status.*``
    # stay function-local imports at every actual call site (cold-import
    # discipline this module already follows for similar seams).
    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent, CoordSeedForkRefused
    from specify_cli.status import FeatureStatusLockTimeoutError

from mission_runtime import ActionContextError, OwnedCheckout

from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption

from specify_cli.decisions import DecisionIndexReadError
from specify_cli.decisions.models import (
    DecisionErrorCode,
    DecisionOpenResponse,
    DecisionStatus,
    DecisionTerminalResponse,
    IndexEntry,
    OriginFlow,
)
from specify_cli.decisions.service import (
    DecisionError,
    DecisionEventLogReadError,
    cancel_decision,
    defer_decision,
    open_decision,
    resolve_decision,
)
from specify_cli.decisions.service import _ledger_dir as _resolve_ledger_dir
from specify_cli.decisions.verify import verify as _verify_decisions

decision_app = typer.Typer(
    name="decision",
    help="Decision Moment ledger for interview questions.",
    no_args_is_help=True,
)

# Safe slug pattern: must start with an alphanumeric character and contain only
# alphanumeric characters, hyphens, and underscores.  This rejects path traversal
# payloads such as ``../../etc/passwd`` or ``../evil`` before they reach
# filesystem operations.
_SAFE_SLUG_RE = _re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_repo_root_and_slug(mission_handle: str) -> tuple[Path, str]:
    """Return ``(repo_root, mission_slug)`` for a mission handle.

    The mission handle may be a full slug, a bare ``mid8``, a full ULID, or a
    numeric prefix; it is canonicalized to the resolved mission directory's
    name when that directory exists (F-001 — the same boundary pattern as the
    agent ``_find_mission_slug`` helpers), so the slug persisted downstream
    (decisions/index.json, the DM artifact, the DecisionPointOpened event) is
    identical across handle forms. Handles that resolve to no existing mission
    keep their raw form, preserving the historical MISSION_NOT_FOUND path.

    ``repo_root`` is the **canonical root authority** (``locate_project_root``),
    the same authority the read-path resolver itself anchors on — so the root
    used here agrees with the coord-aware resolved path the resolver returns.
    When no project root is found the current working directory is used (test
    fixtures pass ``tmp_path`` as the cwd).

    FR-003 / C-IC03 (single authority): this helper performs NO private
    walk-up-to-``kitty-specs/`` and NO escape-validation of the *resolved* path.
    The resolved mission directory is whatever the single canonical resolver
    returns (it may legitimately live in a coordination worktree, i.e. outside
    ``repo_root/kitty-specs/``); asserting it stays under the primary base was
    the dead second authority that rejected valid coord handles. We validate the
    RAW operator token (the input boundary) and trust the resolver's output
    (DIR-031).

    Security: the mission_handle is validated against ``_SAFE_SLUG_RE`` to
    prevent path-traversal attacks (RISK-1 from mission review 01KPWT8P). This
    rejection on the **raw** token is preserved.

    Raises:
        typer.BadParameter: when the raw handle contains path traversal.
        ActionContextError: when the canonical resolver cannot resolve the
            handle (e.g. ``COORDINATION_BRANCH_DELETED``). Callers structure it
            via :func:`_handle_action_context_error` rather than letting it
            surface as a raw traceback (the live #8 symptom).
    """
    # Reject path-traversal payloads early, before any filesystem access. This
    # guards the RAW operator token only — the resolver's output is trusted.
    if not _SAFE_SLUG_RE.match(mission_handle):
        raise typer.BadParameter(
            f"Invalid --mission value {mission_handle!r}: must match {_SAFE_SLUG_RE.pattern}",
            param_hint="'--mission'",
        )

    # Canonical root authority — agrees with the resolver's own anchor (C-001:
    # adopt the existing root authority, never re-derive via a private walk).
    repo_root = locate_project_root() or Path.cwd()

    # Single authority: resolve the mission directory through the one
    # coord-aware resolver. F-001: the resolved directory's NAME (not the raw
    # handle) is the canonical slug persisted downstream. Handles that resolve
    # to no existing mission keep their raw form so the service's
    # MISSION_NOT_FOUND behaviour is unchanged.
    #
    # WP09/FR-001 (kind-correct — deliberately EXCLUDED from the `read_dir(kind)`
    # migration): this call is NOT a plain "give me kind X's home" read. It
    # relies on `resolve_feature_dir_for_mission`'s wrapped
    # `resolve_action_context` to fail closed with a structured
    # `ActionContextError` (e.g. `COORDINATION_BRANCH_DELETED`) — the #8 live
    # symptom fix pinned by
    # `tests/specify_cli/cli/commands/test_decision_single_authority.py`.
    # Neither `read_dir(kind)` partition leg replicates that validation:
    # `PRIMARY_METADATA` routes through the deliberately topology-blind
    # `primary_feature_dir_for_mission` (no coord-branch liveness check at
    # all), and the STATUS-partition leg's `candidate_feature_dir_for_mission`
    # never raises on an unresolvable coord topology either (it degrades to a
    # best-known candidate for the caller to diagnose). Routing this site onto
    # the seam would silently swallow the fail-closed diagnostic, so it keeps
    # calling the richer resolver directly.
    resolved = resolve_feature_dir_for_mission(repo_root, mission_handle).resolve()
    if resolved.is_dir():
        return repo_root, resolved.name
    return repo_root, mission_handle


def _open_response_to_dict(
    resp: DecisionOpenResponse,
    *,
    origin_flow: OriginFlow,
    mission_slug: str,
    step_id: str | None,
    slot_key: str | None,
    input_key: str,
) -> dict:  # type: ignore[type-arg]
    """Serialize DecisionOpenResponse to a plain dict."""
    rerun_safe = resp.decision_id != "DRY_RUN"
    return {
        "contract": "decision_open_v2",
        "decision_id": resp.decision_id,
        "idempotent": resp.idempotent,
        "mission_id": resp.mission_id,
        "artifact_path": resp.artifact_path,
        "event_lamport": resp.event_lamport,
        "recovery": {
            "rerun_safe": rerun_safe,
            "idempotency_key": {
                "mission_id": resp.mission_id,
                "mission_slug": mission_slug,
                "origin_flow": origin_flow.value,
                "step_id": step_id,
                "slot_key": slot_key,
                "input_key": input_key,
            },
        },
    }


def _terminal_response_to_dict(resp: DecisionTerminalResponse) -> dict:  # type: ignore[type-arg]
    """Serialize DecisionTerminalResponse to a plain dict."""
    return {
        "decision_id": resp.decision_id,
        "status": resp.status.value,
        "terminal_outcome": resp.terminal_outcome,
        "idempotent": resp.idempotent,
        "event_lamport": resp.event_lamport,
    }


def _handle_decision_error(exc: DecisionError) -> None:
    """Emit structured JSON error to stderr and raise Exit(1)."""
    payload = {
        "error": str(exc),
        "code": exc.code.value,
        "details": exc.details,
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_action_context_error(exc: ActionContextError) -> None:
    """Render a read-path resolver failure as a structured typed diagnostic.

    FR-003 / C-IC03: the canonical resolver raises :class:`ActionContextError`
    carrying its real ``code`` (e.g. ``COORDINATION_BRANCH_DELETED``,
    ``MISSION_AMBIGUOUS_SELECTOR``, ``STATUS_READ_PATH_NOT_FOUND``). The operator
    MUST see that structured payload — never an uncaught Rich traceback (the
    live #8 symptom). Mirrors the GOOD-citizen pattern in
    ``agent context resolve`` (``agent/context.py``).
    """
    payload = {
        "error": str(exc),
        "code": exc.code,
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_status_read_path_error(exc: StatusReadPathNotFound) -> None:
    """Render a coord-surface resolution failure as a structured diagnostic.

    #5113 (FR-013/FR-014): ``materialize_coord_surface_for_write`` (called by
    ``open_decision``/``_terminal_command`` before any ledger write) raises
    :class:`~specify_cli.coordination.surface_resolver.CoordinationWorktreeUnmaterialized`
    (a :class:`StatusReadPathNotFound` subclass) when the coordination surface
    cannot be safely materialized (a remote-only branch, or a real
    materialization failure). That MUST surface as the same
    ``{"error", "code", "next_step"}`` JSON shape every other structured
    handler on this module emits — never an uncaught Rich traceback (the #8 /
    #5113 symptom class). No new ``DecisionErrorCode`` is introduced (the
    orchestrator ``upstream_contract.json`` stays unchanged).
    """
    payload = {
        "error": str(exc),
        "code": exc.error_code,
        "next_step": getattr(exc, "next_step", None),
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_coord_seed_fork_refused(exc: CoordSeedForkRefused) -> NoReturn:
    """Render a ``COORD_SEED_FORK_REFUSED`` write-location refusal.

    coord-artifact-single-home-01M3V4BE WP09: ``open_decision`` /
    ``_terminal_command`` now resolve the decision-event WRITE location
    through ``write_dir`` (replacing the former direct
    ``materialize_coord_surface_for_write`` call), which raises
    :class:`CoordSeedForkRefused` -- an :class:`ActionContextError` subclass,
    ``.code == "COORD_SEED_FORK_REFUSED"`` -- when the coordination
    decision/status log has genuinely diverged from its root-checkout
    counterpart (D3), BEFORE anything is written. The generic
    :func:`_handle_action_context_error` renders ``.code`` with no recovery
    guidance; a genuine fork needs an operator reconcile step, not a bare
    retry, so this gets its own ``next_step``.

    Review cycle 1 (B2): ``-> NoReturn`` (this always raises ``typer.Exit``)
    instead of ``-> None`` + a dead ``return`` at every call site -- mypy
    then knows the arm terminates, so there is nothing left to suppress for
    coverage (no ``# pragma: no cover`` needed; NFR-005 forbids suppression
    to reach a coverage number).
    """
    payload = {
        "error": str(exc),
        "code": exc.code,
        "next_step": (
            "The coordination decision/status log has diverged from the "
            "repository-root checkout and cannot be auto-reconciled. Run "
            "'spec-kitty doctor coordination --fix' or inspect both logs "
            "manually, then retry this command."
        ),
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_status_lock_timeout(exc: FeatureStatusLockTimeoutError) -> NoReturn:
    """Render a ``STATUS_LOCK_HELD`` mission-status-lock timeout.

    coord-artifact-single-home-01M3V4BE WP09: ``write_dir``'s seed path takes
    the mission status lock (I-SEED-1); a contended lock surfaces as
    :class:`FeatureStatusLockTimeoutError` (``error_code ==
    "STATUS_LOCK_HELD"``) instead of a bare traceback. Transient by nature —
    the recovery hint is "retry", unlike the genuine-fork refusal above.

    Review cycle 1 (B2): ``-> NoReturn`` -- see the sibling
    ``_handle_coord_seed_fork_refused`` docstring.
    """
    payload = {
        "error": str(exc),
        "code": exc.error_code,
        "next_step": ("Another process holds the mission status lock. Wait for it to finish and retry this command."),
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_coord_branch_undeclared_and_absent(exc: CoordBranchUndeclaredAndAbsent) -> NoReturn:
    """Render a ``COORD_BRANCH_UNDECLARED_AND_ABSENT`` write-location refusal.

    Review cycle 2 (B1-residual, Decision ``plan.design.undeclared-coord-
    branch``): ``write_dir``'s topology gate derives the canonical
    coordination branch (``lanes.branch_naming``) when a coordination-routed
    Mission's ``meta.json`` declares no ``coordination_branch`` -- and refuses
    with :class:`CoordBranchUndeclaredAndAbsent` when that derived branch does
    not exist in git either, rather than silently degrading to the PRIMARY
    checkout. The generic :func:`_handle_action_context_error` renders
    ``.code`` with no recovery guidance; this gets its own ``next_step``
    naming the two concrete fixes (declare the branch, or flatten the
    topology).
    """
    payload = {
        "error": str(exc),
        "code": exc.code,
        "next_step": (
            "No coordination_branch is declared in meta.json for this coordination-routed "
            "mission, and the deterministically-derived branch does not exist in git either. "
            "Declare 'coordination_branch' in meta.json if that branch should exist, or run "
            "'spec-kitty migrate backfill-topology' to flatten this mission to a coord-less "
            "topology if it never had one."
        ),
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_index_read_error(exc: DecisionIndexReadError) -> None:
    """Render a corrupt ``decisions/index.json`` as a structured diagnostic.

    FR-003/FR-004/FR-005 (#4642): every subcommand reaches
    :func:`specify_cli.decisions.store.load_index` (directly, via the
    verifier, or via the decisions service), which raises
    :class:`DecisionIndexReadError` fail-closed when the index exists but is
    corrupt (malformed JSON, non-UTF-8 bytes, or schema-invalid). That
    exception MUST NOT escape as a raw traceback — mirrors
    :func:`_handle_decision_error`: a structured ``{code, error, details}``
    payload to stderr, then ``typer.Exit(1)``. ``str(exc)`` already carries
    the fail-closed explanation and the ``run: spec-kitty doctor`` recovery
    hint (see :class:`DecisionIndexReadError.__init__`).
    """
    payload = {
        "code": "DECISION_INDEX_UNREADABLE",
        "error": str(exc),
        "details": {
            "index_path": str(exc.index_path),
            "cause": str(exc.cause),
        },
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


def _handle_event_log_read_error(exc: DecisionEventLogReadError) -> None:
    """Render a corrupt ``status.events.jsonl`` as a structured diagnostic.

    #2899 landing squad (MAJOR): ``decision open``'s idempotent re-open repair
    path (``_repair_missing_opened_event`` → ``_opened_event_exists``) reads
    ``status.events.jsonl`` and, when it exists but is corrupt, fails closed
    with :class:`DecisionEventLogReadError` (a ``RuntimeError``, NOT a
    ``DecisionError``). WP07 introduced that type and the orchestrator-api
    mirror caught it on all four write verbs, but this CLI catcher was not
    updated — so it regressed to the global hook's plain ``Error:`` line. This
    restores parity with the sibling :func:`_handle_index_read_error` on the
    same command: a structured ``{code, error, details}`` payload to stderr,
    then ``typer.Exit(1)``. Reuses the ``DESIGN_STATUS_EVENT_LOG_UNREADABLE``
    envelope code the orchestrator handler and ``design-status`` already emit.
    """
    payload = {
        "code": "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
        "error": str(exc),
        "details": {
            "events_path": exc.path,
        },
    }
    typer.echo(json.dumps(payload, sort_keys=True), err=True)
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Subcommand: open
# ---------------------------------------------------------------------------


@decision_app.command("open")
def cmd_open(  # noqa: PLR0913
    mission: str = typer.Option(..., "--mission", help="Mission handle (slug, mission_id, or mid8)"),
    flow: str = typer.Option(..., "--flow", help="Origin flow: charter | specify | plan"),
    input_key: str = typer.Option(..., "--input-key", help="The input key this decision governs"),
    question: str = typer.Option(..., "--question", help="Human-readable question text"),
    step_id: str | None = typer.Option(None, "--step-id", help="Interview step identifier"),
    slot_key: str | None = typer.Option(None, "--slot-key", help="Slot key (use when step_id unavailable)"),
    options: str | None = typer.Option(None, "--options", help="Candidate answers as a JSON array string"),
    actor: str = typer.Option("cli", "--actor", help="Identity of the opening actor"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """Open a new Decision Moment or return idempotently if one already exists."""
    # Validate flow
    try:
        origin_flow = OriginFlow(flow)
    except ValueError:
        valid = ", ".join(f.value for f in OriginFlow)
        err = DecisionError(
            code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
            details={"flow": flow, "valid_values": valid},
            message=f"Invalid --flow value {flow!r}. Must be one of: {valid}",
        )
        _handle_decision_error(err)
        return  # unreachable — _handle_decision_error raises

    # Parse options JSON
    parsed_options: tuple[str, ...] = ()
    if options is not None:
        try:
            raw = json.loads(options)
        except json.JSONDecodeError as json_exc:
            err = DecisionError(
                code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
                details={"options": options, "parse_error": str(json_exc)},
                message=f"--options must be a valid JSON array string, got: {options!r}",
            )
            _handle_decision_error(err)
            return
        if not isinstance(raw, list):
            err = DecisionError(
                code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
                details={"options": options},
                message="--options must be a JSON array (list), got a non-list value",
            )
            _handle_decision_error(err)
            return
        parsed_options = tuple(str(item) for item in raw)

    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent, CoordSeedForkRefused
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        resp = open_decision(
            repo_root,
            mission_slug,
            origin_flow=origin_flow,
            input_key=input_key,
            question=question,
            options=parsed_options,
            step_id=step_id,
            slot_key=slot_key,
            actor=actor,
            dry_run=dry_run,
        )
    except DecisionError as exc:
        _handle_decision_error(exc)
        return
    except CoordSeedForkRefused as exc:
        # coord-artifact-single-home-01M3V4BE WP09: ``write_dir``'s pre-write
        # placement resolution refused a genuine fork — before any ledger
        # write. Before ``StatusReadPathNotFound`` below: not a subclass of
        # it, but ordered to read alongside the other write-location refusals.
        _handle_coord_seed_fork_refused(exc)
    except CoordBranchUndeclaredAndAbsent as exc:
        _handle_coord_branch_undeclared_and_absent(exc)
    except FeatureStatusLockTimeoutError as exc:
        _handle_status_lock_timeout(exc)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises
    except DecisionEventLogReadError as exc:
        # #2899 landing squad: corrupt status.events.jsonl reached via the
        # idempotent re-open repair path — only ``open`` reaches
        # ``_opened_event_exists`` (resolve/defer/cancel cannot), so the catch
        # lives here, not on the other verbs (catch the type the callee raises).
        _handle_event_log_read_error(exc)
        return  # unreachable — _handle_event_log_read_error raises
    except StatusReadPathNotFound as exc:
        # #5113: the pre-write materialization gate refused (remote-only
        # branch, or a real materialization failure) — after the more
        # specific excepts above so ``DecisionEventLogReadError`` (also
        # reachable from this call) is not shadowed.
        _handle_status_read_path_error(exc)
        return  # unreachable — _handle_status_read_path_error raises

    typer.echo(
        json.dumps(
            _open_response_to_dict(
                resp,
                origin_flow=origin_flow,
                mission_slug=mission_slug,
                step_id=step_id,
                slot_key=slot_key,
                input_key=input_key,
            ),
            sort_keys=True,
        )
    )


# ---------------------------------------------------------------------------
# Subcommand: resolve
# ---------------------------------------------------------------------------


@decision_app.command("resolve")
def cmd_resolve(  # noqa: PLR0913
    decision_id: str = typer.Argument(..., help="ULID identifier of the decision to resolve"),
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    final_answer: str = typer.Option(..., "--final-answer", help="The chosen answer (non-empty)"),
    other_answer: bool = typer.Option(False, "--other-answer", help="True if answer is a write-in"),
    rationale: str | None = typer.Option(None, "--rationale", help="Explanation of the choice"),
    resolved_by: str | None = typer.Option(None, "--resolved-by", help="Identity of resolver"),
    actor: str = typer.Option("cli", "--actor", help="Identity of the acting agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """Resolve a decision with a concrete final answer."""
    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent, CoordSeedForkRefused
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        resp = resolve_decision(
            repo_root,
            mission_slug,
            decision_id,
            final_answer=final_answer,
            other_answer=other_answer,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
            dry_run=dry_run,
        )
    except DecisionError as exc:
        _handle_decision_error(exc)
        return
    except CoordSeedForkRefused as exc:
        _handle_coord_seed_fork_refused(exc)
    except CoordBranchUndeclaredAndAbsent as exc:
        _handle_coord_branch_undeclared_and_absent(exc)
    except FeatureStatusLockTimeoutError as exc:
        _handle_status_lock_timeout(exc)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises
    except StatusReadPathNotFound as exc:
        # #5113: the pre-write materialization gate refused.
        _handle_status_read_path_error(exc)
        return  # unreachable — _handle_status_read_path_error raises

    typer.echo(json.dumps(_terminal_response_to_dict(resp), sort_keys=True))


# ---------------------------------------------------------------------------
# Subcommand: defer
# ---------------------------------------------------------------------------


@decision_app.command("defer")
def cmd_defer(
    decision_id: str = typer.Argument(..., help="ULID identifier of the decision to defer"),
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    rationale: str = typer.Option(..., "--rationale", help="Explanation of why it's being deferred (required)"),
    resolved_by: str | None = typer.Option(None, "--resolved-by", help="Identity of deferring party"),
    actor: str = typer.Option("cli", "--actor", help="Identity of the acting agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """Defer a decision for later resolution."""
    if not rationale.strip():
        err = DecisionError(
            code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
            details={"field": "rationale"},
            message="--rationale must be a non-empty string",
        )
        _handle_decision_error(err)
        return

    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent, CoordSeedForkRefused
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        resp = defer_decision(
            repo_root,
            mission_slug,
            decision_id,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
            dry_run=dry_run,
        )
    except DecisionError as exc:
        _handle_decision_error(exc)
        return
    except CoordSeedForkRefused as exc:
        _handle_coord_seed_fork_refused(exc)
    except CoordBranchUndeclaredAndAbsent as exc:
        _handle_coord_branch_undeclared_and_absent(exc)
    except FeatureStatusLockTimeoutError as exc:
        _handle_status_lock_timeout(exc)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises
    except StatusReadPathNotFound as exc:
        # #5113: the pre-write materialization gate refused.
        _handle_status_read_path_error(exc)
        return  # unreachable — _handle_status_read_path_error raises

    typer.echo(json.dumps(_terminal_response_to_dict(resp), sort_keys=True))


# ---------------------------------------------------------------------------
# Subcommand: cancel
# ---------------------------------------------------------------------------


@decision_app.command("cancel")
def cmd_cancel(
    decision_id: str = typer.Argument(..., help="ULID identifier of the decision to cancel"),
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    rationale: str = typer.Option(..., "--rationale", help="Explanation of why it's being canceled (required)"),
    resolved_by: str | None = typer.Option(None, "--resolved-by", help="Identity of canceling party"),
    actor: str = typer.Option("cli", "--actor", help="Identity of the acting agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """Cancel a decision (deemed no longer relevant)."""
    if not rationale.strip():
        err = DecisionError(
            code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
            details={"field": "rationale"},
            message="--rationale must be a non-empty string",
        )
        _handle_decision_error(err)
        return

    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent, CoordSeedForkRefused
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        resp = cancel_decision(
            repo_root,
            mission_slug,
            decision_id,
            rationale=rationale,
            resolved_by=resolved_by,
            actor=actor,
            dry_run=dry_run,
        )
    except DecisionError as exc:
        _handle_decision_error(exc)
        return
    except CoordSeedForkRefused as exc:
        _handle_coord_seed_fork_refused(exc)
    except CoordBranchUndeclaredAndAbsent as exc:
        _handle_coord_branch_undeclared_and_absent(exc)
    except FeatureStatusLockTimeoutError as exc:
        _handle_status_lock_timeout(exc)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises
    except StatusReadPathNotFound as exc:
        # #5113: the pre-write materialization gate refused.
        _handle_status_read_path_error(exc)
        return  # unreachable — _handle_status_read_path_error raises

    typer.echo(json.dumps(_terminal_response_to_dict(resp), sort_keys=True))


# ---------------------------------------------------------------------------
# Subcommand: verify
# ---------------------------------------------------------------------------


@decision_app.command("verify")
def cmd_verify(
    mission: str = typer.Option(..., "--mission", help="Mission handle"),
    fail_on_stale: bool = typer.Option(
        True,
        "--fail-on-stale/--no-fail-on-stale",
        help="Exit non-zero when findings are present (default true)",
    ),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """Cross-check deferred decisions against inline sentinel markers."""
    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    # #4966/FR-003 fold (pre-PR squad, completing WP03's residual): the
    # decision LEDGER content (``decisions/index.json``, and the ``spec.md`` /
    # ``plan.md`` docs this verifier cross-checks against it) lives in the
    # SAME PRIMARY-partition dir the write path (``open``/``resolve``/
    # ``defer``/``cancel`` in ``decisions/service.py``) already resolves via
    # ``_ledger_dir`` (``DECISION_LEDGER``, a PRIMARY-partition kind). Previously this
    # read routed through ``resolve_handle_to_read_path``, which on a
    # MATERIALIZED status-only coord husk returns the COORD worktree — a
    # directory the ledger writer never touches — so ``verify`` silently
    # reported a false "clean" (empty ledger, no markers) on a mission with a
    # real deferred decision. Reuse the ONE existing ledger-dir authority
    # (do not add a second/third resolver here).
    mission_dir = _resolve_ledger_dir(repo_root, mission_slug)

    try:
        result = _verify_decisions(mission_dir, mission_slug)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises

    findings_list = [
        {
            "kind": f.kind,
            "decision_id_or_ref": f.decision_id_or_ref,
            "location": f.location,
            "detail": f.detail,
        }
        for f in result.findings
    ]

    # WP17 (FR-010a, contract rule 5): a forked decision-event stream is a
    # distinct, honest-verify finding from the marker/decision drift rules
    # above. Resolved here (not in ``decisions.verify.verify``, whose
    # ``mission_slug`` parameter stays reserved/unused per the module
    # docstring) because ``cmd_verify`` already has ``repo_root`` in scope —
    # see "Binding corrections" (WP17): adding a fork check here avoids
    # widening ``verify()``'s public signature.
    from specify_cli.decisions.fork import detect_decision_forks  # noqa: PLC0415 — cold-import discipline

    fork_report = detect_decision_forks(repo_root, mission_slug)
    if fork_report.forked:
        forked_decision_ids = sorted(
            {
                decision_id
                for finding in fork_report.streams
                if finding.state == "forked"
                for decision_id in (
                    *finding.decisions_only_on_primary,
                    *finding.decisions_only_on_coordination,
                )
            }
        )
        fork_detail = "A decision-event stream diverges between the PRIMARY and coordination surfaces (never auto-merged, C-003): " + "; ".join(
            fork_report.reconcile_steps
        )
        findings_list.append(
            {
                "kind": "DECISION_LOG_FORKED",
                "decision_id_or_ref": ", ".join(forked_decision_ids) or None,
                "location": None,
                "detail": fork_detail,
            }
        )

    payload = {
        "status": "drift" if findings_list else "clean",
        "deferred_count": result.deferred_count,
        "marker_count": result.marker_count,
        "findings": findings_list,
    }

    typer.echo(json.dumps(payload, sort_keys=True))

    # WP17 precedence decision (documented, per the binding-corrections
    # instruction to decide and document ``--no-fail-on-stale`` vs a fork):
    # a forked decision stream ALWAYS exits 1, independent of
    # ``--fail-on-stale/--no-fail-on-stale`` -- that flag only governs the
    # marker/decision drift rules in ``decisions.verify.verify`` (contract
    # rule 5: "exits 1 by default", read here as "unconditionally", since a
    # fork is a data-loss risk, not a staleness nit an operator can opt out
    # of reporting as a failure).
    if fork_report.forked:
        raise typer.Exit(1)
    if result.findings and fail_on_stale:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: IndexEntry) -> dict[str, object]:
    """Serialize one IndexEntry for ``decision list`` output."""
    return {
        "decision_id": entry.decision_id,
        "status": entry.status.value,
        "origin_flow": entry.origin_flow.value,
        "input_key": entry.input_key,
        "question": entry.question,
        "step_id": entry.step_id,
        "slot_key": entry.slot_key,
        "final_answer": entry.final_answer,
        "rationale": entry.rationale,
        "created_at": entry.created_at.isoformat(),
        "resolved_at": entry.resolved_at.isoformat() if entry.resolved_at else None,
        "resolved_by": entry.resolved_by,
    }


@decision_app.command("list")
def cmd_list(
    mission: str = typer.Option(..., "--mission", help="Mission handle (slug, mission_id, or mid8)"),
    status: str | None = typer.Option(None, "--status", help="Only list decisions in this status: open | resolved | deferred | canceled"),
    json_out: bool = typer.Option(True, "--json/--no-json", help="Output JSON (default true)"),  # noqa: ARG001
) -> None:
    """List the mission's recorded decision moments (read-only)."""
    # Optional status filter — validated at the CLI boundary the same way
    # ``cmd_open`` validates ``--flow`` (structured error naming the valid
    # values, never a raw traceback).
    status_filter: DecisionStatus | None = None
    if status is not None:
        try:
            status_filter = DecisionStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in DecisionStatus)
            _handle_decision_error(
                DecisionError(
                    code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
                    details={"status": status, "valid_values": valid},
                    message=f"Invalid --status value {status!r}. Must be one of: {valid}",
                )
            )
            return  # unreachable — _handle_decision_error raises

    try:
        repo_root, mission_slug = _resolve_repo_root_and_slug(mission)
    except ActionContextError as exc:
        _handle_action_context_error(exc)
        return  # unreachable — _handle_action_context_error raises

    # #4966/FR-003 fold (pre-PR squad, completing WP03's residual): read the
    # ledger from the SAME PRIMARY-partition dir the write path resolves via
    # ``decisions/service.py::_ledger_dir`` — see the identical rationale in
    # ``cmd_verify`` above. Previously this read routed through
    # ``resolve_handle_to_read_path``, which on a MATERIALIZED status-only
    # coord husk returns the COORD worktree the ledger writer never touches,
    # so ``list`` silently reported an empty ledger.
    mission_dir = _resolve_ledger_dir(repo_root, mission_slug)

    from specify_cli.decisions.store import load_index

    try:
        index = load_index(mission_dir)
    except DecisionIndexReadError as exc:
        _handle_index_read_error(exc)
        return  # unreachable — _handle_index_read_error raises

    entries = sorted(index.entries, key=lambda e: (e.created_at, e.decision_id))
    if status_filter is not None:
        entries = [e for e in entries if e.status is status_filter]

    payload = {
        "contract": "decision_list_v1",
        "mission_slug": mission_slug,
        "mission_id": index.mission_id or None,
        "count": len(entries),
        "decisions": [_entry_to_dict(e) for e in entries],
    }
    typer.echo(json.dumps(payload, sort_keys=True))


# ---------------------------------------------------------------------------
# Subcommand: widen  (hidden — internal / automation use only)
# ---------------------------------------------------------------------------


@decision_app.command("widen", hidden=True)
def cmd_widen(
    decision_id: str = typer.Argument(..., help="ULID of the DecisionPoint to widen"),
    invited: str = typer.Option(..., "--invited", help="Comma-separated Teamspace user IDs to invite"),
    mission_slug: str | None = typer.Option(None, "--mission-slug", help="Mission slug"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be called without calling it"),
) -> None:
    """[internal] Call the widen endpoint for a decision. Not for end users."""
    from specify_cli.decisions.ownership import (
        is_well_formed_decision_id,
        ownership_refusal,
        resolve_decision_ownership,
    )
    from specify_cli.saas_client import SaasClient, SaasClientError

    # FR-005 — one shape check, at the CLI boundary, reusing ONE existing ULID
    # regex (Q7). This is the boundary where the value's provenance changes from
    # keyboard to store, and it is **defence-in-depth only**: it does not
    # establish ownership, and a bare regex would leave the consent-laundering
    # defect entirely open. SC-003: an id that fails it never reaches a
    # constructed request line, because nothing downstream of here runs.
    if not is_well_formed_decision_id(decision_id):
        typer.echo(
            "Error: decision_id must be a 26-character Crockford-base32 ULID (digits and A-Z excluding I, L, O, U)",
            err=True,
        )
        raise typer.Exit(1)

    invited_raw = [n.strip() for n in invited.split(",") if n.strip()]
    if not invited_raw:
        typer.echo("Error: --invited must be a non-empty comma-separated list of user IDs", err=True)
        raise typer.Exit(1)
    try:
        invited_list = [int(value) for value in invited_raw]
    except ValueError:
        typer.echo("Error: --invited must contain Teamspace user IDs, not display names", err=True)
        raise typer.Exit(1) from None

    # FR-001/FR-002 — establish ownership from local files under the acting root
    # only, and do it BEFORE any URL is built. Resolved once and shared by both
    # branches so dry-run reports the same verdict the live path enforces.
    repo_root = locate_project_root() or Path.cwd()
    ownership = resolve_decision_ownership(repo_root, decision_id, mission_slug=mission_slug)
    refusal = ownership_refusal(ownership)

    if dry_run:
        # Q5 — dry-run WARNS, it does not refuse. Dry-run transmits nothing, so it
        # is not an egress path and refusing would remove its inspection value.
        # But the verdict must be surfaced, or dry-run becomes a way to get the id
        # formatted for copy-paste into a real invocation without ever seeing the
        # mismatch. It rides in the payload rather than on stderr because this
        # command's dry-run contract is "stdout is one JSON document".
        typer.echo(
            json.dumps(
                {
                    "dry_run": True,
                    "decision_id": decision_id,
                    "endpoint": f"POST /a/<team_slug>/collaboration/decision-points/{decision_id}/widen",
                    "invited": invited_list,
                    "mission_slug": mission_slug,
                    "ownership": {
                        "acting_root": str(ownership.repo_root),
                        "missions_searched": list(ownership.missions_searched),
                        "owned": ownership.owned,
                        "owning_mission_slug": ownership.owning_mission_slug,
                        "unreadable_ledgers": list(ownership.unreadable_ledgers),
                        "warning": refusal,
                    },
                    "payload": {"invited_user_ids": invited_list},
                },
                indent=2,
            )
        )
        raise typer.Exit(0)

    # No fall-through. "Found nothing" is *ownership not established*, and falling
    # through to the acting root here — in the broad form or in the narrow "this
    # checkout has no kitty-specs/ at all, so allow it" form — reinstates exactly
    # the leak this check closes.
    if refusal is not None:
        typer.echo(f"Error: {refusal}", err=True)
        raise typer.Exit(1)

    try:
        client = SaasClient.from_env(repo_root=repo_root)
        response = client.post_widen(decision_id=decision_id, invited=invited_list)
        typer.echo(
            json.dumps(
                {
                    "decision_id": response["decision_id"],
                    "invited_count": response["invited_count"],
                    "slack_thread_url": response["slack_thread_url"],
                    "success": True,
                    "widened_at": response["widened_at"],
                },
                indent=2,
            )
        )
    except SaasClientError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


__all__ = ["decision_app"]


def _runtime_lock_git(root: Path, *args: str) -> str:
    """Read selected Git state, refusing an incomplete observation."""
    import subprocess

    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _runtime_lock_preflight(owned: OwnedCheckout) -> tuple[Path, Path, bool, bool]:
    """Validate only the service-owned lock and its local ignore file."""
    from kernel.git import status_entries, tracked_paths
    from specify_cli.decisions.service import _decisions_lock_path

    from specify_cli.decisions.service import _runtime_lock_ignore_state

    lock = _decisions_lock_path(owned.mission_dir)
    ignore, ignored = _runtime_lock_ignore_state(owned)
    relative_lock = str(lock.relative_to(owned.owned_root))
    relative_ignore = str(ignore.relative_to(owned.owned_root))
    for entry in status_entries(owned.owned_root, pathspecs=(relative_lock, relative_ignore), untracked="all"):
        # An untracked service lock is normal; operator ignore edits and
        # any staged/unstaged tracked-lock change belong to the operator.
        if not (entry.is_untracked and str(entry.path) == relative_lock):
            raise ValueError("Runtime lock repair refuses preexisting changes or staging on its lock or .gitignore")
    tracked = bool(tracked_paths(owned.owned_root, pathspecs=(relative_lock,)))
    return lock, ignore, tracked, ignored


def _repair_runtime_lock(owned: OwnedCheckout, *, dry_run: bool) -> dict[str, object]:
    """Untrack one exact service lock without unlinking its synchronization inode."""
    from kernel.git import tracked_paths
    from kernel.locks import machine_file_lock
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.decisions.service import _LOCK_ACQUIRE_TIMEOUT_S
    from specify_cli.git.commit_helpers import preflight_commit, safe_commit
    from specify_cli.decisions.service import _ensure_runtime_lock_ignore, _restore_runtime_lock_ignore, _runtime_lock_ignore_state

    lock, ignore, tracked, ignored = _runtime_lock_preflight(owned)
    paths = (ignore, lock) if tracked else (ignore,)
    target = placement_seam(owned.repository_root, owned.mission_slug, owned=owned).write_target(MissionArtifactKind.PRIMARY_METADATA)
    message = f"chore(decisions): stop tracking runtime lock for {owned.mission_slug}"
    preflight_commit(repo_root=owned.owned_root, worktree_root=owned.owned_root, target=target, message=message, paths=paths, owned=owned)
    payload: dict[str, object] = {
        "status": "ok",
        "mission_slug": owned.mission_slug,
        "dry_run": dry_run,
        "tracked": tracked,
        "ignored": ignored,
        "changed": tracked or not ignored,
    }
    if dry_run or not payload["changed"]:
        return payload
    # All destinations have been validated before creating the owner lock.
    lock.parent.mkdir(parents=True, exist_ok=True)
    with machine_file_lock(lock, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):
        # The OS lock holder metadata itself changes the tracked lock bytes;
        # don't interpret that owned write as an operator modification.
        ignore, ignored_now = _runtime_lock_ignore_state(owned)
        relative_lock = str(lock.relative_to(owned.owned_root))
        if bool(tracked_paths(owned.owned_root, pathspecs=(relative_lock,))) != tracked:
            raise RuntimeError("Runtime lock index changed while waiting for the owner lock")
        if _runtime_lock_git(owned.owned_root, "diff", "--cached", "HEAD", "--", relative_lock):
            raise RuntimeError("Runtime lock staging changed while waiting for the owner lock")
        parent = _runtime_lock_git(owned.owned_root, "rev-parse", "HEAD")
        old_ignore = ignore.read_bytes() if ignore.exists() else None
        written_ignore: bytes | None = None
        try:
            if not ignored_now:
                _ensure_runtime_lock_ignore(owned)
            written_ignore = ignore.read_bytes() if ignore.exists() else None
            commit_paths = paths if written_ignore is not None else (lock,)
            result = safe_commit(
                repo_root=owned.owned_root,
                worktree_root=owned.owned_root,
                target=target,
                message=message,
                paths=commit_paths,
                owned=owned,
                expected_parent_sha=parent,
                expected_path_bytes={ignore: written_ignore} if written_ignore is not None else {},
                index_only_removals=(lock,) if tracked else (),
            )
        except Exception:
            # Ref updates are conditional. Restore our ignore bytes only when
            # the branch has not moved and nobody subsequently changed them.
            if _runtime_lock_git(owned.owned_root, "rev-parse", "HEAD") == parent and written_ignore is not None and ignore.read_bytes() == written_ignore:
                _restore_runtime_lock_ignore(ignore, old_ignore, written_ignore)
            raise
        payload["commit"] = result.sha
        if result.diagnostic:
            raise RuntimeError(result.diagnostic)
    return payload


@decision_app.command("repair-runtime-lock")
def cmd_repair_runtime_lock(
    mission: str = typer.Option(..., "--mission", help="Mission whose decision runtime lock needs repair"),
    owned_checkout: OwnedCheckoutOption = None,
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and inspect without acquiring the lock or writing"),
) -> None:
    """Stop tracking the exact decision lock in an explicitly owned mission."""
    from typing import cast
    from specify_cli.cli.commands._owned_checkout import resolve_owned_or_refuse
    from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES

    if owned_checkout is None:
        raise typer.BadParameter("repair-runtime-lock requires explicit --owned-checkout")
    owned = resolve_owned_or_refuse(
        locate_project_root() or Path.cwd(),
        cast(Path, owned_checkout),
        mission,
        cwd=Path.cwd(),
        allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        json_output=True,
        envelope=lambda code, message: {"status": "error", "code": code, "message": message},
    )
    assert owned is not None
    try:
        payload = _repair_runtime_lock(owned, dry_run=dry_run)
    except Exception as exc:
        typer.echo(json.dumps({"status": "error", "message": str(exc)}))
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(payload))
