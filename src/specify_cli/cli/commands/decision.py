"""Decision Moment CLI subgroup — ``spec-kitty agent decision ...``

Exposes five subcommands that map directly to the decisions service and verifier:

    open      — open a new decision moment
    resolve   — resolve a decision with a final answer
    defer     — defer a decision for later resolution
    cancel    — cancel a decision (no longer relevant)
    verify    — cross-check deferred decisions against inline markers

All subcommands output JSON to stdout and exit 0 on success, 1 on structured error.
"""

from __future__ import annotations

from specify_cli.core.paths import locate_project_root
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission
import json
import re as _re
from pathlib import Path

import typer

from mission_runtime import ActionContextError

from specify_cli.decisions.models import (
    DecisionErrorCode,
    DecisionOpenResponse,
    DecisionTerminalResponse,
    OriginFlow,
)
from specify_cli.decisions.service import (
    DecisionError,
    cancel_decision,
    defer_decision,
    open_decision,
    resolve_decision,
)
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


#: The one-line note every commit-on-record result carries (#4311): the
#: ledger commit is local by design, and the operator owns the push.
_COMMIT_LOCAL_NOTE = "ledger committed locally; push stays under this repo's normal policy"


def _ledger_commit_payload(
    resp: DecisionOpenResponse | DecisionTerminalResponse,
) -> dict[str, object] | None:
    """Serialize the commit-on-record report, plus its local-commit note.

    ``None`` when the operation made no ledger change (dry run, idempotent
    re-record). A refused/errored commit is reported here AND loudly on
    stderr — a decision left uncommitted in the working tree is exactly the
    state #4311 says must never pass silently. The stderr line is JSON, not
    prose: this command's ``--json`` contract keeps BOTH streams parseable
    (``_handle_decision_error`` already emits structured JSON on stderr), and
    a prose line interleaved ahead of the payload breaks JSON-lines consumers
    of the mixed runner output.
    """
    if resp.ledger_commit is None:
        return None
    report = resp.ledger_commit
    if report.status in ("refused", "error"):
        typer.echo(
            json.dumps(
                {
                    "warning": "decision ledger NOT committed",
                    "ledger_commit_status": report.status,
                    "diagnostic": report.diagnostic or "no diagnostic",
                    "note": "the ledger row and its event are on disk uncommitted",
                },
                sort_keys=True,
            ),
            err=True,
        )
    payload: dict[str, object] = report.model_dump()
    payload["note"] = _COMMIT_LOCAL_NOTE
    return payload


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
        "ledger_commit": _ledger_commit_payload(resp),
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
        "ledger_commit": _ledger_commit_payload(resp),
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
    # Read-path mediation (WP08 T037, FR-030): in the coord-branch
    # topology ``decisions/index.json`` lives in the coordination
    # worktree, not the primary checkout.  The resolver returns the
    # coord-worktree mission directory when one exists, and falls back
    # to the primary checkout for legacy missions / early lifecycle.
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    # WP02/FR-002 (D-6 consolidation): the former D-6 factory-boundary bootstrap
    # (raw ``KITTY_SPECS_DIR / mission_slug`` join → ``load_meta`` →
    # ``resolve_mid8`` → ``resolve_mission_read_path``) collapses onto the single
    # guarded read-side seam. ``resolve_handle_to_read_path`` performs the SAME
    # primary-meta probe and the sanctioned mid8 cascade internally (reading the
    # canonical ``mission_id`` from the primary meta, never seeding an empty
    # identity), then routes through the existence-gated topology resolver — and
    # adds the ``assert_safe_path_segment`` guard (FR-004) this bootstrap lacked.
    # M5 (FR-003 / #8 class): ``cmd_verify`` still surfaces the resolver's
    # fail-closed refusals (``StatusReadPathNotFound`` /
    # ``CoordinationBranchDeleted``) and selector ambiguity
    # (``MissionSelectorAmbiguous``) as structured typed diagnostics carrying the
    # real ``error_code`` — never an uncaught traceback.
    try:
        mission_dir = resolve_handle_to_read_path(repo_root, mission_slug)
    except (StatusReadPathNotFound, MissionSelectorAmbiguous) as exc:
        _handle_action_context_error(ActionContextError(exc.error_code, str(exc)))
        return  # unreachable — _handle_action_context_error raises

    result = _verify_decisions(mission_dir, mission_slug)

    findings_list = [
        {
            "kind": f.kind,
            "decision_id_or_ref": f.decision_id_or_ref,
            "location": f.location,
            "detail": f.detail,
        }
        for f in result.findings
    ]

    payload = {
        "status": result.status,
        "deferred_count": result.deferred_count,
        "marker_count": result.marker_count,
        "findings": findings_list,
    }

    typer.echo(json.dumps(payload, sort_keys=True))

    if result.findings and fail_on_stale:
        raise typer.Exit(1)


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
