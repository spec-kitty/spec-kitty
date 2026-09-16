"""CLI command for ``spec-kitty next``.

FR-008 / T031 note: The `next` command dispatches mission-step actions via
``decide_next()``. In the 3.2.x baseline, mission-step invocations (specify,
plan, tasks, implement, review, merge, accept) are opened OUT-OF-PROCESS by
the agent that reads the decision — not by this command directly.

Therefore, this command does NOT open InvocationRecord objects itself.

When a future integration has `next` open an InvocationRecord directly (e.g.
for agent-mode automation), it should use:
    derive_mode(f"next.{action}")  -> ModeOfWork.MISSION_STEP
for any of: next.specify, next.plan, next.tasks, next.implement,
            next.review, next.merge, next.accept

The mapping is registered in _ENTRY_COMMAND_MODE (modes.py).
TODO(future): wire derive_mode(f"next.{action}") when InvocationRecord is
opened directly from the next command.
"""

from __future__ import annotations

import contextlib
import functools
import io
import importlib
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, cast

import typer
from mission_runtime import MissionArtifactKind, placement_seam

# WP01 (T002, #3789-adjacent honest hygiene): checkout_ownership is only
# reachable on the ``owned_checkout is not None`` opt-in path, so it is
# deferred to that call site — this keeps it out of the no-op/startup import
# graph paid on every ``next`` invocation (including a query that never uses
# it). Type-only import here keeps mypy resolving the annotation below.
if TYPE_CHECKING:
    from specify_cli.core.checkout_ownership import CheckoutOwnershipError

from specify_cli.core.context_validation import require_main_repo
from specify_cli.core.paths import (
    UnsafePathSegmentError,
    get_main_repo_root,
    locate_project_root,
)
from runtime.next._runtime_pkg_notice import maybe_emit_runtime_pkg_notice
from runtime.next.decision import VALID_RESULT_VALUES as _VALID_RESULTS

_Command = TypeVar("_Command", bound=Callable[..., Any])


def decide_next(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root,
    *,
    effective_root: Path | None = None,
):
    """Patchable lazy wrapper for the next mutation engine."""
    from runtime.next.decision import decide_next as _decide_next

    if effective_root is None:
        return _decide_next(agent, mission_slug, result, repo_root)
    return _decide_next(
        agent, mission_slug, result, repo_root, effective_root=effective_root
    )


def _runtime_bridge_module():
    """Return the patched bridge when tests/consumers installed one."""
    return sys.modules.get("runtime.next.runtime_bridge") or importlib.import_module(
        "runtime.next.runtime_bridge"
    )


def _require_main_repo_unless_owned(func: _Command) -> _Command:
    """Preserve the legacy guard unless the caller explicitly opts in.

    The owned path bypasses only the syntactic ``.worktrees`` guard. The
    command body validates the claim against git topology before any runtime
    or mission operation. Keeping the guarded call as the no-opt-in branch
    makes that historical behavior byte-for-byte identical.
    """
    guarded = require_main_repo(func)
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        if bound.arguments.get("owned_checkout") is not None:
            return func(*args, **kwargs)
        return guarded(*args, **kwargs)

    return cast(_Command, wrapper)


def _emit_checkout_ownership_error(error: CheckoutOwnershipError, *, json_output: bool) -> None:
    """Render the shared ownership refusal contract and exit fail-closed."""
    if json_output:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_code": error.error_code,
                    "error": str(error),
                }
            )
        )
    else:
        print(f"Error: {error}", file=sys.stderr)
    raise typer.Exit(1)


@_require_main_repo_unless_owned
def next_step(
    agent: Annotated[str | None, typer.Option("--agent", help="Agent name (required for advancing mode)")] = None,
    result: Annotated[
        str | None,
        typer.Option(
            "--result",
            help=("Result of previous step: success|failed|blocked. If omitted, returns current state without advancing (query mode)."),
        ),
    ] = None,
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON decision only")] = False,
    answer: Annotated[str | None, typer.Option("--answer", help="Answer to a pending decision")] = None,
    decision_id: Annotated[str | None, typer.Option("--decision-id", help="Decision ID (required if multiple pending)")] = None,
    owned_checkout: Annotated[
        Path | None,
        typer.Option(
            "--owned-checkout",
            help="Explicit checkout root owned by this invocation",
        ),
    ] = None,
) -> None:
    """Decide and emit the next agent action for the current mission.

    Agents call this command repeatedly in a loop.  The system inspects the
    mission state machine, evaluates guards, and returns a deterministic
    decision with an action and prompt file.

    Examples:
        spec-kitty next --mission 034-my-feature --json                            # query mode
        spec-kitty next --agent claude --mission 034-my-feature --result success --json
        spec-kitty next --agent codex --mission 034-my-feature
        spec-kitty next --agent gemini --mission 034-my-feature --result failed --json
        spec-kitty next --agent claude --mission 034-my-feature --answer "yes" --result success --json
        spec-kitty next --agent claude --mission 034-my-feature --answer "approve" --decision-id "input:review" --result success --json
    """
    ambient_root = locate_project_root()
    if ambient_root is None:
        print("Error: Could not locate project root", file=sys.stderr)
        raise typer.Exit(1)

    repo_root = ambient_root
    effective_root: Path | None = None
    if owned_checkout is not None:
        # WP01 (T002): deferred from module scope — this branch is the only
        # reachable use of checkout_ownership; see the TYPE_CHECKING import
        # above for the rationale.
        from specify_cli.core.checkout_ownership import (
            error_for_claim,
            resolve_ownership_claim,
        )

        claim = resolve_ownership_claim(
            owned_checkout,
            resolved_primary=ambient_root,
        )
        refusal = error_for_claim(claim)
        if refusal is not None:
            _emit_checkout_ownership_error(refusal, json_output=json_output)
        repo_root = claim.claimed_checkout
        effective_root = claim.claimed_checkout

    _maybe_emit_runtime_notice(json_output)

    # FR-006 caller contract: charter preflight runs BEFORE any state
    # mutation. On failure, print blocked_reason and exit 1 — the runtime
    # decision engine is never entered. Query mode (result is None) is
    # read-only and follows the dashboard's "log + warn + continue" path
    # so that operators can inspect mission state in repos whose charter
    # has not yet been synthesized (e.g., fresh clones, test envs).
    from pathlib import Path as _Path

    _run_charter_preflight_for_next(_Path(str(repo_root)), advancing=result is not None, json_output=json_output)

    from runtime.next.runtime_bridge import MissionNotFoundError as _MissionNotFoundError
    from specify_cli.missions._read_path_resolver import (
        StatusReadPathNotFound as _StatusReadPathNotFound,
    )

    try:
        mission_slug = _resolve_mission_slug(
            mission, repo_root, effective_root=effective_root
        )
    except _StatusReadPathNotFound as _exc:
        # FR-001 / C-IC02: preserve the typed read-path error (code + checked
        # paths + read-path remediation) instead of collapsing to MISSION_NOT_FOUND.
        _emit_read_path_error(_exc, json_output)
        raise typer.Exit(1) from _exc
    except _MissionNotFoundError as _exc:
        _emit_mission_not_found_error(_exc.handle, json_output)
        raise typer.Exit(1) from _exc
    except UnsafePathSegmentError as _exc:
        # #2878: a traversal-shaped --mission value trips the safe-path-segment
        # guard (assert_safe_path_segment, reached through the placement seam
        # inside _resolve_mission_slug) and raises UnsafePathSegmentError, which the
        # _StatusReadPathNotFound/_MissionNotFoundError handlers above do not
        # cover. Convert it to merge's clean typed-error surface
        # (_resolve_slug_or_exit, cli/commands/merge.py): canonical diagnostic +
        # exit 2, never a raw traceback.
        _emit_unsafe_mission_slug_error(_exc, json_output)
        raise typer.Exit(2) from _exc
    except ValueError as _exc:
        _emit_internal_resolution_error(_exc, json_output)
        raise typer.Exit(2) from _exc
    _validate_result_and_answer(result, answer, json_output)
    answered_id = _maybe_handle_answer(
        agent,
        mission_slug,
        answer,
        decision_id,
        repo_root,
        json_output,
        effective_root=effective_root,
    )

    # Query mode: bare call without --result remains read-only and does not
    # require agent identity.
    if result is None:
        _run_query_mode(
            agent,
            mission_slug,
            repo_root,
            json_output,
            answered_id,
            answer,
            effective_root=effective_root,
        )
        return  # No event emitted, no DAG advancement

    if not agent:
        print("Error: --agent is required when --result is provided", file=sys.stderr)
        raise typer.Exit(1)

    # WP05 (#843): pair the previous issuance's `started` lifecycle record
    # BEFORE we advance the runtime. This must run before decide_next so the
    # pair is observable even if decide_next raises.
    _pair_previous_lifecycle_record(
        agent, mission_slug, result, repo_root, effective_root=effective_root
    )

    decision = decide_next(
        agent, mission_slug, result, repo_root, effective_root=effective_root
    )
    _emit_mission_next_invoked(
        agent,
        result,
        mission_slug,
        repo_root,
        decision,
        effective_root=effective_root,
    )

    # WP05 (#843): write the `started` lifecycle record AFTER the decision is
    # finalised but BEFORE returning to the agent, so the record exists iff
    # the agent actually saw the issued action.
    _write_issuance_lifecycle_record(
        agent,
        mission_slug,
        repo_root,
        decision,
        effective_root=effective_root,
    )
    if effective_root is not None:
        _commit_owned_next_mutations(effective_root, mission_slug)

    _print_decision(decision, json_output, answered_id, answer)

    if not json_output:
        _print_stalled_wp_interventions(mission_slug, repo_root)

    if decision.kind == "blocked":
        raise typer.Exit(1)


def _commit_owned_next_mutations(effective_root: Path, mission_slug: str) -> None:
    """Durably close the explicit-root advancement changeset.

    Runtime advancement writes mission scaffolding/events plus the lifecycle
    record before returning its decision.  The ordinary path retains its
    historical behavior; the opted-in ownership contract must leave the owned
    checkout clean and therefore commits only those two declared surfaces to
    that mission's seam-resolved primary target.
    """
    from mission_runtime import MissionArtifactKind, mission_context_for
    from specify_cli.core.commit_guard import GuardCapability
    from specify_cli.git.commit_helpers import safe_commit
    from specify_cli.missions._read_path_resolver import compose_meta_json_path

    mission_dir = compose_meta_json_path(effective_root, mission_slug).parent
    lifecycle = effective_root / "kitty-ops" / "lifecycle.jsonl"
    mission_files = tuple(
        path for path in sorted(mission_dir.rglob("*")) if path.is_file()
    )
    paths = mission_files + ((lifecycle,) if lifecycle.is_file() else ())
    if not paths:
        return
    target = mission_context_for(
        effective_root,
        mission_slug,
        effective_root=effective_root,
    ).artifact(MissionArtifactKind.PRIMARY_METADATA).commit_target
    if target is None:
        raise RuntimeError(
            f"Owned checkout {effective_root} has no primary commit target for {mission_slug}"
        )
    try:
        safe_commit(
            repo_root=effective_root,
            worktree_root=effective_root,
            target=target,
            message=f"chore(next): persist {mission_slug} advancement [skip ci]",
            paths=paths,
            capability=GuardCapability.STANDARD,
        )
    except RuntimeError as exc:
        # safe_commit's benign no-op sentinel: the staged tree already
        # matches HEAD (e.g. a terminal owned advance that writes no new
        # mission content and appends no lifecycle record). That is a
        # successful no-op here, not a command failure. Any OTHER
        # RuntimeError (protection refusal, HEAD mismatch, genuine commit
        # failure, ...) must stay fail-closed and propagate unchanged.
        if "empty changeset" not in str(exc):
            raise


def _pair_previous_lifecycle_record(
    agent: str,
    mission_slug: str,
    result: str,
    repo_root: object,
    *,
    effective_root: Path | None = None,
) -> None:
    """Thin delegating wrapper over the FR-014 shared seam.

    Kept as a private, patchable module-level name (rather than removed) so
    external tests that ``monkeypatch``/``unittest.mock.patch`` this exact
    name (e.g. ``tests/contract/test_next_no_implicit_success.py``,
    ``tests/agent/cli/commands/test_next_preflight.py``,
    ``tests/integration/test_next_lifecycle_records.py``,
    ``tests/integration/test_identity_coord_read.py``,
    ``tests/specify_cli/cli/commands/test_lifecycle_read_seam_migration.py``)
    keep intercepting the real call path — the body itself is the whole
    seam extraction (FR-014, operator ruling SPEC-FRESH2-001): the actual
    logic lives in ``runtime.next.next_invocation_lifecycle``, the ONE
    shared implementation both this CLI and orchestrator-api's WP08
    ``answer-decision`` verb call, never a second copy.
    """
    from runtime.next.next_invocation_lifecycle import (
        pair_previous_lifecycle_record as _seam_pair_previous_lifecycle_record,
    )

    _seam_pair_previous_lifecycle_record(
        agent, mission_slug, result, repo_root, effective_root=effective_root
    )


def _write_issuance_lifecycle_record(
    agent: str,
    mission_slug: str,
    repo_root: object,
    decision: object,
    *,
    effective_root: Path | None = None,
) -> None:
    """Thin delegating wrapper over the FR-014 shared seam.

    Kept as a private, patchable module-level name for the same external
    -test-compatibility reason documented on ``_pair_previous_lifecycle_
    record`` above — the real implementation lives in ``runtime.next.
    next_invocation_lifecycle.write_issuance_lifecycle_record``.
    """
    from runtime.next.next_invocation_lifecycle import (
        write_issuance_lifecycle_record as _seam_write_issuance_lifecycle_record,
    )

    _seam_write_issuance_lifecycle_record(
        agent, mission_slug, repo_root, decision, effective_root=effective_root
    )


def _maybe_emit_runtime_notice(json_output: bool) -> None:
    """Emit the stale-runtime notice only for human-readable output."""
    # FR-020 of mission shared-package-boundary-cutover-01KQ22DS: emit a
    # one-time deprecation notice if the retired spec-kitty-runtime package
    # is still installed in the operator's environment. The check uses
    # importlib.metadata, which does NOT import spec_kitty_runtime, so it
    # does not violate FR-002 / C-001. JSON mode is a machine contract:
    # stdout must be exactly one JSON document, and Typer's CliRunner may
    # combine stderr into result.output.
    if not json_output:
        maybe_emit_runtime_pkg_notice()


def _run_charter_preflight_for_next(repo_root, *, advancing: bool, json_output: bool) -> None:
    """Run charter preflight without letting advisory text contaminate JSON stdout."""
    if advancing:
        from specify_cli.charter_runtime.preflight.hook import run_preflight_or_abort

        if json_output:
            stderr_buffer = io.StringIO()
            error_payload: dict[str, str] | None = None
            advisory_output = ""
            with (
                contextlib.redirect_stdout(sys.stderr),
                contextlib.redirect_stderr(stderr_buffer),
            ):
                try:
                    run_preflight_or_abort(repo_root, consumer="next")
                except typer.Exit:
                    message = stderr_buffer.getvalue().strip() or "charter preflight failed"
                    blocked_reason = message.removeprefix("Error: ").strip()
                    error_payload = {
                        "error_code": "CHARTER_PREFLIGHT_FAILED",
                        "error": message,
                        "blocked_reason": blocked_reason,
                    }
                else:
                    advisory_output = stderr_buffer.getvalue()
            if advisory_output:
                sys.stderr.write(advisory_output)
            if error_payload is not None:
                print(json.dumps(error_payload))
                raise typer.Exit(1)
            return
        run_preflight_or_abort(repo_root, consumer="next")
        return

    from specify_cli.charter_runtime.preflight.hook import (
        emit_advisory_warnings,
        run_preflight_for_dashboard,
    )

    # Query mode is read-only: warn-and-continue, like dashboard.
    stdout_redirect = contextlib.redirect_stdout(sys.stderr) if json_output else contextlib.nullcontext()
    with stdout_redirect:
        result = run_preflight_for_dashboard(repo_root)
    # #3971: scope the single surfaced ambient warning to this consumer.
    emit_advisory_warnings(result, consumer="next", repo_root=repo_root)


def _resolve_mission_slug(
    mission: str | None,
    repo_root: Path,
    *,
    effective_root: Path | None = None,
) -> str:
    mission_norm = mission.strip() if isinstance(mission, str) else None
    if not mission_norm:
        raise typer.BadParameter("--mission <slug> is required")
    mission_slug = mission_norm

    raw_handle = mission_slug
    # F-001: ``--mission`` accepts handles (bare mid8, full ULID, numeric
    # prefix). Canonicalize at this boundary — the same pattern as the agent
    # ``_find_mission_slug`` helpers — so every downstream consumer
    # (``decide_next``, ``get_or_start_run`` keying ``.kittify/runtime/
    # feature-runs.json``, its persisted ``mission_slug``, and the run-scoped
    # event emitter) receives the canonical directory name. A raw mid8 here
    # creates a split-brain duplicate run vs the full-slug invocation.
    # Handles that resolve to no existing directory keep their raw form,
    # preserving the historical not-found behaviour downstream; an ambiguous
    # handle propagates MissionSelectorAmbiguous (C-CTX-4 — structured error,
    # never a silent fallback).
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        # Ledger WP04: migrate-fail-loud via PRIMARY_METADATA (slug-canon idiom).
        # The except StatusReadPathNotFound branch re-raises. Under the prior
        # candidate_feature_dir_for_mission call this branch WAS reachable, but
        # only in the narrow corrupt-meta fail-closed window (topology is None,
        # primary_candidate.exists(), mid8 set, coord_state EMPTY, and
        # _declares_coordination_branch(...) true) — not dead code. This
        # migration to PRIMARY_METADATA via placement_seam deliberately drops
        # that arm: PRIMARY_METADATA never raises CoordinationBranchDeleted, so
        # the branch is unreachable in the new code path. Kept so a future
        # STATUS-partition regression still surfaces typed.
        if effective_root is None:
            candidate = placement_seam(
                get_main_repo_root(repo_root), raw_handle
            ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        else:
            from mission_runtime import mission_context_for

            candidate = mission_context_for(
                effective_root,
                raw_handle,
                effective_root=effective_root,
            ).artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
    except StatusReadPathNotFound:
        # FR-001 / C-IC02: the read resolver produced a precise typed error
        # (e.g. COORDINATION_BRANCH_DELETED / STATUS_READ_PATH_NOT_FOUND) with the
        # real read-path remediation. Do NOT collapse it into a generic
        # MISSION_NOT_FOUND ("run mission list") — that mis-routes the operator
        # (the mission is not missing; its read path is broken). Re-raise the
        # typed error so the command layer surfaces ``error_code`` + the checked
        # candidate paths verbatim.
        raise
    if candidate.exists():
        return candidate.name
    return raw_handle


def _print_error(message: str, json_output: bool) -> None:
    if json_output:
        print(json.dumps({"error": message}))
    else:
        print(message, file=sys.stderr)


def _emit_mission_not_found_error(
    handle: str, json_output: bool, next_step: str | None = None
) -> None:
    """Emit a structured MISSION_NOT_FOUND error in the appropriate format.

    Human mode writes to stderr; JSON mode writes a structured envelope to
    stdout.  Both paths exit non-zero (FR-004 / WP03).

    ``next_step`` carries the actionable operator remediation lifted from the
    raised :class:`MissionNotFoundError`; it is surfaced in both the JSON
    payload (alongside ``error_code``) and as a ``Next:`` line in human mode,
    restoring the affordance the superseded ``QueryModeValidationError`` gave
    (#1911). It also remains under the legacy ``remediation`` key for
    backward compatibility.
    """
    remediation = next_step or "Run 'spec-kitty mission list' to see available missions."
    if json_output:
        from specify_cli import __version__

        payload = {
            "result": "error",
            "error_code": "MISSION_NOT_FOUND",
            "handle": handle,
            "next_step": remediation,
            "remediation": remediation,
            "spec_kitty_version": __version__,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"Error: Mission not found: '{handle}'\n"
            f"No mission matching '{handle}' exists in this repository.",
            file=sys.stderr,
        )
        print(f"  Next: {remediation}", file=sys.stderr)


def _emit_unsafe_mission_slug_error(exc: UnsafePathSegmentError, json_output: bool) -> None:
    """Surface a traversal-unsafe ``--mission`` slug as a clean typed error.

    #2878: the safe-path-segment guard inside the read resolver raises
    ``UnsafePathSegmentError`` for traversal-shaped slugs (``../x``, ``a/b``, leading-dot,
    …). Mirrors merge's ``_resolve_slug_or_exit`` handling (the in-repo
    exemplar): the canonical safe-path-segment diagnostic, a single
    ``Error:`` line on stderr in human mode, a structured JSON envelope in
    ``--json`` mode — never an unhandled-traceback dump. The
    ``merge._constants`` import stays function-local so the ``next`` fast path
    (``next --help``, tests/specify_cli/next/test_next_import_footprint.py)
    never pays the merge package's import graph.
    """
    from specify_cli.merge._constants import _SAFE_PATH_SEGMENT_DIAGNOSTIC

    message = f"{_SAFE_PATH_SEGMENT_DIAGNOSTIC}: {exc}"
    if json_output:
        from specify_cli import __version__

        payload: dict[str, object] = {
            "result": "error",
            "error_code": "UNSAFE_MISSION_SLUG",
            "error": message,
            "spec_kitty_version": __version__,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Error: {message}", file=sys.stderr)


def _emit_internal_resolution_error(exc: ValueError, json_output: bool) -> None:
    """Preserve the CLI error envelope for an unexpected resolver failure."""
    message = str(exc)
    if json_output:
        from specify_cli import __version__

        payload: dict[str, object] = {
            "result": "error",
            "error_code": "INTERNAL_RESOLUTION_ERROR",
            "error": message,
            "spec_kitty_version": __version__,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Error: {message}", file=sys.stderr)


def _read_path_signal(exc: Exception) -> tuple[str, list[str], str | None]:
    """Extract ``(code, checked_paths, next_step)`` from a typed read-path error.

    FR-001 / C-IC02: both the ``StatusReadPathNotFound`` family (raised by the
    read resolver / ``_resolve_mission_slug``) and the ``ActionContextError``
    boundary type (raised by ``query_current_state`` /
    ``answer_decision_via_runtime``) carry the same underlying signal. The
    boundary ``ActionContextError`` flattens the candidate paths into its message,
    so its ``__cause__`` (the original ``StatusReadPathNotFound``) is the
    structured source of ``coord_candidate`` / ``primary_candidate`` /
    ``next_step``. This reads whichever shape is present without inventing a new
    error type (C-001).
    """
    # The structured carrier is either the exception itself (StatusReadPathNotFound
    # family) or its cause (the boundary ActionContextError wraps it).
    carrier = exc if hasattr(exc, "coord_candidate") else exc.__cause__
    code = getattr(exc, "code", None) or getattr(exc, "error_code", None) or "STATUS_READ_PATH_NOT_FOUND"
    checked: list[str] = []
    for attr in ("coord_candidate", "primary_candidate"):
        candidate = getattr(carrier, attr, None)
        if candidate is not None:
            checked.append(str(candidate))
    next_step = getattr(carrier, "next_step", None) or str(exc)
    return code, checked, next_step


def _emit_read_path_error(exc: Exception, json_output: bool) -> None:
    """Surface a typed read-path error verbatim (FR-001 / FR-002 / C-IC02).

    Mirrors the ``QueryModeValidationError`` branch (a typed ``error_code`` +
    actionable ``next_step`` reach the JSON envelope) instead of collapsing the
    error into ``MISSION_NOT_FOUND`` / "run mission list". The remediation is the
    real read-path repair the resolver produced, never a mission-list hint.
    """
    code, checked_paths, next_step = _read_path_signal(exc)
    remediation = next_step or str(exc)
    if json_output:
        from specify_cli import __version__

        payload: dict[str, object] = {
            "result": "error",
            "error_code": code,
            "error": str(exc),
            "checked_paths": checked_paths,
            "next_step": remediation,
            "remediation": remediation,
            "spec_kitty_version": __version__,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Error: {exc}", file=sys.stderr)
        if checked_paths:
            print(f"  Checked: {', '.join(checked_paths)}", file=sys.stderr)
        if remediation:
            print(f"  Next: {remediation}", file=sys.stderr)


def _validate_result_and_answer(result: str | None, answer: str | None, json_output: bool) -> None:
    if result is not None and result not in _VALID_RESULTS:
        print(f"Error: --result must be one of {_VALID_RESULTS}, got '{result}'", file=sys.stderr)
        raise typer.Exit(1)

    if answer is not None and result is None:
        _print_error("Error: --answer requires --result because query mode is read-only", json_output)
        raise typer.Exit(1)


def _maybe_handle_answer(
    agent: str | None,
    mission_slug: str,
    answer: str | None,
    decision_id: str | None,
    repo_root: object,
    json_output: bool,
    *,
    effective_root: Path | None = None,
) -> str | None:
    if answer is None:
        return None
    if not agent:
        _print_error("Error: --agent is required when --answer is provided", json_output)
        raise typer.Exit(1)

    from mission_runtime import ActionContextError

    stderr_buffer = io.StringIO() if json_output else None
    redirect = contextlib.redirect_stderr(stderr_buffer) if stderr_buffer is not None else contextlib.nullcontext()
    try:
        with redirect:
            return _handle_answer(
                agent,
                mission_slug,
                answer,
                decision_id,
                repo_root,
                effective_root=effective_root,
            )
    except ActionContextError as exc:
        # FR-001 / C-IC02: the decision-answer path must preserve the typed
        # read-path code IDENTICALLY to the query path — not flatten it into a
        # generic ``error`` string. Surface code + checked paths + remediation.
        _emit_read_path_error(exc, json_output)
        raise typer.Exit(1) from exc
    except typer.Exit as exc:
        if json_output:
            message = (stderr_buffer.getvalue().strip() if stderr_buffer is not None else "") or str(exc) or "Answer handling failed"
            print(json.dumps({"error": message}))
            raise typer.Exit(1) from exc
        raise
    except Exception as exc:
        if json_output:
            print(json.dumps({"error": str(exc)}))
            raise typer.Exit(1) from exc
        raise


def _run_query_mode(
    agent: str | None,
    mission_slug: str,
    repo_root: object,
    json_output: bool,
    answered_id: str | None,
    answer: str | None,
    *,
    effective_root: Path | None = None,
) -> None:
    runtime_bridge = _runtime_bridge_module()
    QueryModeValidationError = runtime_bridge.QueryModeValidationError
    # Import MissionNotFoundError from the canonical module so tests that
    # install a fake ``runtime.next.runtime_bridge`` shim still work.
    from mission_runtime import ActionContextError
    from runtime.next.runtime_bridge import MissionNotFoundError

    try:
        if effective_root is None:
            decision = runtime_bridge.query_current_state(
                agent, mission_slug, repo_root
            )
        else:
            decision = runtime_bridge.query_current_state(
                agent,
                mission_slug,
                repo_root,
                effective_root=effective_root,
            )
    except ActionContextError as exc:
        # FR-001 / C-IC02: the resolver produced a precise typed read-path error
        # (e.g. COORDINATION_BRANCH_DELETED). Surface its code + checked paths +
        # read-path remediation verbatim — never collapse to MISSION_NOT_FOUND.
        _emit_read_path_error(exc, json_output)
        raise typer.Exit(1) from exc
    except MissionNotFoundError as exc:
        _emit_mission_not_found_error(
            exc.handle, json_output, next_step=getattr(exc, "next_step", None)
        )
        raise typer.Exit(1) from exc
    except QueryModeValidationError as exc:
        # C-ERR-1 / FR-003: emit a structured payload (error_code + next_step)
        # rather than a silent unknown stub when a handle is unresolvable.
        if json_output:
            payload = {
                "error": str(exc),
                "error_code": getattr(exc, "error_code", "QUERY_MODE_VALIDATION_FAILED"),
            }
            next_step = getattr(exc, "next_step", None)
            if next_step is not None:
                payload["next_step"] = next_step
            print(json.dumps(payload, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
            next_step = getattr(exc, "next_step", None)
            if next_step:
                print(f"  Next: {next_step}", file=sys.stderr)
        raise typer.Exit(1) from exc
    _print_decision(decision, json_output, answered_id, answer)


def _emit_mission_next_invoked(
    agent: str,
    result: str,
    mission_slug: str,
    repo_root: object,
    decision,
    *,
    effective_root: Path | None = None,
) -> None:
    """Thin delegating wrapper over the FR-014 shared seam.

    Kept as a private, patchable module-level name for the same external
    -test-compatibility reason documented on ``_pair_previous_lifecycle_
    record`` above — the real implementation lives in ``runtime.next.
    next_invocation_lifecycle.emit_mission_next_invoked``.
    """
    from runtime.next.next_invocation_lifecycle import (
        emit_mission_next_invoked as _seam_emit_mission_next_invoked,
    )

    _seam_emit_mission_next_invoked(
        agent, result, mission_slug, repo_root, decision, effective_root=effective_root
    )


def _print_decision(decision, json_output: bool, answered_id: str | None, answer: str | None) -> None:
    if json_output:
        d = decision.to_dict()
        if answered_id is not None:
            d["answered"] = answered_id
            d["answer"] = answer
        print(json.dumps(d, indent=2))
    else:
        if answered_id is not None:
            print(f"  Answered decision: {answered_id}")
        _print_human(decision)


def _handle_answer(
    agent: str,
    mission_slug: str,
    answer: str,
    decision_id: str | None,
    repo_root: object,
    *,
    effective_root: Path | None = None,
) -> str:
    """Handle the --answer flow for pending decisions.

    Returns the resolved decision_id.
    """
    from pathlib import Path

    repo_root_path = Path(str(repo_root)) if not isinstance(repo_root, Path) else repo_root

    try:
        runtime_bridge = _runtime_bridge_module()
        from specify_cli.mission import get_mission_type

        # FR-004 (#2186): the mission TYPE drives ``get_or_start_run``. Reading it
        # off ``resolve_feature_dir_for_mission`` (the KIND-BLIND, topology-aware
        # resolver) lands on the STATUS-only coord husk (no meta.json) →
        # ``get_mission_type`` returns the default ``software-dev``, starting the
        # run with the WRONG type for a non-default mission — that failure mode is
        # real and stays true of that resolver. It is FALSE of the kind-aware
        # seam below: for a PRIMARY-partition kind (``PRIMARY_METADATA``) the
        # decision layer short-circuits straight to the PRIMARY anchor before any
        # coord probe (read-side-seam-primary-primitive-closure-01KYKMMT WP06,
        # T030 — corrects the prior wording, which conflated the two). Anchor on
        # the PRIMARY dir so the type is read from the real meta.json. WP08
        # (T036): dropped the caller-side canonicalizer fold — redundant with
        # the seam's own internal fold for a PRIMARY-partition kind.
        #
        # Owned-checkout note: ``placement_seam(...).read_dir(...)`` folds a
        # linked-worktree root back to the primary checkout
        # (``get_main_repo_root``) — the "old way" the ADR forbids for
        # opted-in owned layers (mirrors the established idiom in
        # ``_pair_previous_lifecycle_record`` / ``_write_issuance_lifecycle_
        # record`` / ``_emit_mission_next_invoked`` elsewhere in this file).
        # When ``effective_root`` is supplied, resolve against it directly via
        # ``mission_context_for`` instead so an owned ``--answer`` reads the
        # owned checkout's mission content, not primary's.
        if effective_root is None:
            feature_dir = placement_seam(
                repo_root_path, mission_slug
            ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        else:
            from mission_runtime import mission_context_for

            feature_dir = mission_context_for(
                repo_root_path,
                mission_slug,
                effective_root=effective_root,
            ).artifact(MissionArtifactKind.PRIMARY_METADATA).read_dir
        mission_type = get_mission_type(feature_dir)
        run_ref = runtime_bridge.get_or_start_run(mission_slug, repo_root_path, mission_type)

        # If no decision_id provided, try to auto-resolve via the ONE shared
        # seam (PR-BOUNDARY-001): the same zero/one/many branch
        # orchestrator-api's ``answer_decision`` now also calls -- no more
        # independently-maintained duplicate here.
        if decision_id is None:
            from runtime.next.next_invocation_lifecycle import (
                AmbiguousPendingDecisionError,
                NoPendingDecisionError,
                resolve_pending_decision_id,
            )

            try:
                decision_id = resolve_pending_decision_id(Path(run_ref.run_dir), None)
            except (NoPendingDecisionError, AmbiguousPendingDecisionError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                raise typer.Exit(1) from exc

        runtime_bridge.answer_decision_via_runtime(
            mission_slug,
            decision_id,
            answer,
            agent,
            repo_root_path,
        )

        return decision_id

    except typer.Exit:
        raise
    except Exception as exc:
        print(f"Error answering decision: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc


def _print_human(decision) -> None:
    """Print a human-readable summary."""
    if getattr(decision, "is_query", False):
        _print_query_human(decision)
        return
    _print_standard_human(decision)


def _print_query_human(decision) -> None:
    # SC-003: query mode output must begin with the full verbatim label.
    print("[QUERY \u2014 no result provided, state not advanced]")
    print(f"  Mission: {decision.mission_slug} @ {decision.mission_state}")
    if getattr(decision, "mission", None):
        print(f"  Mission Type: {decision.mission}")
    if getattr(decision, "preview_step", None):
        print(f"  Next step: {decision.preview_step}")
    _print_query_details(decision)
    _print_progress(decision)
    if decision.run_id:
        print(f"  Run ID: {decision.run_id}")


def _print_query_details(decision) -> None:
    if getattr(decision, "question", None):
        print(f"  Question: {decision.question}")
        if getattr(decision, "options", None):
            print(f"  Options: {', '.join(decision.options)}")
        if getattr(decision, "decision_id", None):
            print(f"  Decision ID: {decision.decision_id}")
    elif getattr(decision, "reason", None):
        print(f"  Reason: {decision.reason}")


def _print_standard_human(decision) -> None:
    kind = decision.kind.upper()
    print(f"[{kind}] {decision.mission_slug} @ {decision.mission_state}")
    if getattr(decision, "mission", None):
        print(f"  Mission Type: {decision.mission}")

    if decision.action:
        if decision.wp_id:
            print(f"  Action: {decision.action} {decision.wp_id}")
        else:
            print(f"  Action: {decision.action}")

    if decision.workspace_path:
        print(f"  Workspace: {decision.workspace_path}")

    if decision.guard_failures:
        print(f"  Guards pending: {', '.join(decision.guard_failures)}")

    if decision.reason:
        print(f"  Reason: {decision.reason}")

    if getattr(decision, "question", None):
        print(f"  Question: {decision.question}")
    if getattr(decision, "options", None):
        for i, opt in enumerate(decision.options, 1):
            print(f"    {i}. {opt}")
    if decision.decision_id:
        print(f"  Decision ID: {decision.decision_id}")

    _print_progress(decision)

    if decision.run_id:
        print(f"  Run ID: {decision.run_id}")

    if decision.prompt_file:
        print()
        print("  Next step: read the prompt file:")
        print(f"    cat {decision.prompt_file}")


def _print_progress(decision) -> None:
    if decision.progress:
        p = decision.progress
        total = p.get("total_wps", 0)
        done = p.get("done_wps", 0)
        if total > 0:
            pct = int(p.get("weighted_percentage", 0))
            print(f"  Progress: {pct}% ({done}/{total} done)")


def _print_stalled_wp_interventions(mission_slug: str, repo_root: object) -> None:
    """Print intervention commands for any stalled in_review WPs.

    Calls show_kanban_status() in silent mode and surfaces stalled WPs found
    in the return dict.  Failures are swallowed — this is observability only.
    """
    try:
        import io
        import contextlib
        from specify_cli.agent_utils.status import show_kanban_status

        # Suppress board output — we only want the stalled_wps data
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            status_result = show_kanban_status(mission_slug)

        stalled = status_result.get("stalled_wps", [])
        for stall in stalled:
            wp_id = stall["wp_id"]
            age_m = stall["age_minutes"]
            slug = stall.get("mission_slug", mission_slug)
            print(
                f"\n⚠  {wp_id} has been in_review for {age_m}m — reviewer may be stalled.\n"
                f"   Intervention options:\n"
                f"     spec-kitty agent tasks move-task {wp_id} --to approved --force "
                f"--note 'Approved after {age_m}m stall' --mission {slug}\n"
                f"     spec-kitty agent tasks move-task {wp_id} --to planned "
                f"--review-feedback-file <path> --mission {slug}"
            )
    except Exception:  # noqa: BLE001 — stall check is observability only
        pass
