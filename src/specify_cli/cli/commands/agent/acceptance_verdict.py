"""``agent mission acceptance-verdict`` command (WP04 / T015; WP05 / T019-T020).

write-side-seam-matrix-tracer-01KYP3MH, FR-001/FR-002/FR-012.
post-merge-write-authoring-finish-01KYRRM5, FR-007/FR-008 (#2318).
accept-fails-closed-01M3HS4V, FR-002 (#4887): the command-local locked
critical section is retired -- both verdict modes now call the ONE shared
seam, :func:`specify_cli.acceptance.matrix.locked_reread_splice_and_write`,
with ``commit=True``.

Records ONE acceptance-criterion verdict (a ``pass``/``fail``/``pending``
result plus its verification method/actor/evidence) into the mission's
``acceptance-matrix.json``, then commits it through the shared write seam
(:func:`specify_cli.acceptance.matrix.locked_reread_splice_and_write`,
which composes :func:`~specify_cli.coordination.write_seam.write_artifact`
via :func:`~specify_cli.acceptance.matrix.write_and_commit_acceptance_matrix`).

This command *materializes and routes* — it never re-authors verdict
semantics. ``overall_verdict`` stays a computed
:pyattr:`~specify_cli.acceptance.matrix.AcceptanceMatrix.overall_verdict`
property (``acceptance/matrix.py``); the criterion mode only ever mutates one
``AcceptanceCriterion`` row inside ``matrix.criteria`` and never touches
``matrix.negative_invariants`` (so negative-invariant provenance, #2743's
integrity guard, is passed through untouched on every invocation).

Idempotence (FR-012): ``verified_at`` is bumped ONLY when the row's
observable state (result / verification method / actor / evidence) actually
changes. An identical re-invocation therefore serializes byte-identical JSON,
so the underlying commit resolves to ``"unchanged"`` (no duplicate commit) —
inherited straight from ``commit_for_mission``'s own idempotence contract, not
re-implemented here.

**WP05 / T019-T020 (#2318, C-008 additive)**: ``--negative-invariant`` is a
second, mutually-exclusive mode on this SAME command (no new command; the
``NegativeInvariant`` dataclass already carries every field, so this is a
pure materialize-and-route extension, exactly like the criterion mode). It
registers (or replaces, by ``invariant_id``) a well-shaped
:class:`~specify_cli.acceptance.matrix.NegativeInvariant` row — zero
hand-edited JSON — and, by default, immediately EXECUTES its verification
through the existing :func:`~specify_cli.acceptance.matrix.
enforce_negative_invariants` engine (never reimplemented here), recording its
``result``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from specify_cli.acceptance.matrix import (
    CRITERION_VERDICTS,
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    enforce_negative_invariants,
    locked_reread_splice_and_write,
    read_acceptance_matrix,
)
from specify_cli.agent_tasks_ports import RealRender
from specify_cli.cli.console import console
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.coordination.commit_outcome import (
    commit_outcome_exit_code,
    commit_outcome_payload,
    render_commit_outcome,
)
from specify_cli.coordination.write_seam import WriteSeamResult
from kernel.clock import now_utc_iso
from specify_cli.status import FeatureStatusLockTimeoutError
from specify_cli.task_utils import TaskCliError, find_repo_root

_PAYLOAD_KEY_SUCCESS = "success"
_PAYLOAD_KEY_ERROR = "error"
_RED_ERROR_PREFIX = "[red]Error:[/red] "


def _emit_json(payload: dict[str, object]) -> None:
    # Routed through the sanctioned RealRender.json_envelope adapter — the ONE
    # blessed json.dumps home in the agent command surface (FR-007 /
    # test_no_inline_json_dumps_outside_allowlist); never an inline json.dumps
    # here (tasks-py-degod-wave2-01KWH9EQ contracts/gate-contracts.md Gate 1).
    print(RealRender().json_envelope(payload))


def _emit_error(message: str, *, json_output: bool) -> None:
    if json_output:
        _emit_json({_PAYLOAD_KEY_SUCCESS: False, _PAYLOAD_KEY_ERROR: message})
    else:
        # WP10 cycle 2 (B1 sibling): some callers build ``message`` from a
        # caller-controlled diagnostic (e.g. ``write_result.diagnostic``,
        # which can echo raw git/lock error text) -- ``escape()`` neutralises
        # any bracketed substring that would otherwise be parsed as a
        # (potentially unbalanced) Rich markup tag.
        console.print(f"{_RED_ERROR_PREFIX}{escape(message)}")


def _matrix_write_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the matrix's WRITE surface via the ONE kind-aware write-location authority.

    WP10 (T057, binding correction -- lost-update fix): this command's two
    ``commit=True`` call sites (``_run_criterion_mode`` / ``_run_negative_
    invariant_mode``) both route through :func:`~specify_cli.acceptance.
    matrix.locked_reread_splice_and_write`, whose contract requires
    ``matrix_dir`` to be resolved ONCE, before the lock, and reused UNCHANGED
    as both the re-read base and the write target -- never split into a
    separate read dir / write dir, and never re-resolved inside the locked
    splice. Routes through :meth:`~mission_runtime.PlacementSeam.write_dir`
    (``MissionArtifactKind.ACCEPTANCE_MATRIX``) rather than the former
    ``read_dir`` projection (which can fall back to the PRIMARY dir on an
    EMPTY/UNMATERIALIZED coordination surface -- a transient state that must
    still route through ``write_dir``'s materialize/seed/restore contract,
    not silently write to the wrong surface).

    ``acceptance/gates_core.py::_acceptance_matrix_read_dir`` is a DIFFERENT,
    deliberately read-side resolution for the ``--no-commit``/``--diagnose``
    accept legs (which must never commit, and must never seed/materialize a
    coordination surface as a side effect of a read-only evaluation pass) --
    not migrated here; see that function's own docstring.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    location = placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.ACCEPTANCE_MATRIX)
    return location.path


def _resolve_criterion_update(
    existing: AcceptanceCriterion,
    *,
    result: str,
    verification_method: str | None,
    actor: str | None,
    evidence: str | None,
) -> AcceptanceCriterion:
    """Compute the updated row, bumping ``verified_at`` only on a real change (FR-012).

    A candidate is built with every field the CLI can set applied, but
    ``verified_at`` held at the EXISTING value. If that candidate is
    dataclass-equal to ``existing``, nothing observable changed, so
    ``verified_at`` (and ``notes``, the change-log line) are left untouched —
    a re-invocation with identical inputs serializes byte-identical JSON,
    which is what makes the underlying commit resolve to ``"unchanged"``.
    """
    candidate = replace(
        existing,
        pass_fail=result,
        proof_type=verification_method if verification_method is not None else existing.proof_type,
        verified_by=actor if actor is not None else existing.verified_by,
        evidence=evidence if evidence is not None else existing.evidence,
    )
    if candidate == existing:
        return existing
    return replace(
        candidate,
        verified_at=now_utc_iso(),
    )


def _register_negative_invariant(
    matrix: AcceptanceMatrix,
    *,
    invariant_id: str,
    description: str,
    verification_method: str,
    verification_command: str | None,
    scope: str | None,
) -> None:
    """Insert (or replace, by ``invariant_id``) a well-shaped row (FR-007).

    Re-registering an existing id replaces its row with a freshly-``pending``
    invariant — the CLI is the one door for this shape, mirroring
    ``_resolve_criterion_update``'s "materialize and route" contract for the
    negative-invariant half of the schema.
    """
    new_ni = NegativeInvariant(
        invariant_id=invariant_id,
        description=description,
        verification_method=verification_method,
        verification_command=verification_command,
        scope=scope,
    )
    for idx, existing in enumerate(matrix.negative_invariants):
        if existing.invariant_id == invariant_id:
            matrix.negative_invariants[idx] = new_ni
            return
    matrix.negative_invariants.append(new_ni)


def _replace_or_append_negative_invariant(matrix: AcceptanceMatrix, judged: NegativeInvariant) -> None:
    """Splice an ALREADY-JUDGED row into ``matrix`` (insert-if-absent).

    #4858 (FR-002/C-4858-modes): unlike :func:`_register_negative_invariant`
    (which synthesizes a fresh ``pending`` row for a NEW registration), this
    replaces-or-appends a row that has ALREADY been through
    :func:`~specify_cli.acceptance.matrix.enforce_negative_invariants` — it
    must never reset the judged result back to ``pending``. Used exclusively
    as the ``splice`` callable inside
    :func:`~specify_cli.acceptance.matrix.locked_reread_splice_and_write`'s
    critical section to merge the invocation's own judged row into the
    freshly re-read on-disk matrix, leaving every sibling row untouched
    (FR-001).
    """
    for idx, existing in enumerate(matrix.negative_invariants):
        if existing.invariant_id == judged.invariant_id:
            matrix.negative_invariants[idx] = judged
            return
    matrix.negative_invariants.append(judged)


def _splice_criterion_update(matrix: AcceptanceMatrix, criterion_id: str, updated: AcceptanceCriterion) -> None:
    """Splice ``updated`` into ``matrix.criteria`` by id (insert-if-absent).

    #4858 (FR-002/C-4858-modes): the index is recomputed against the
    FRESHLY re-read matrix (never the pre-lock snapshot) each time this
    runs, so a concurrently-reshaped criteria list cannot cause a wrong-row
    splice or an ``IndexError``.
    """
    for idx, existing in enumerate(matrix.criteria):
        if existing.criterion_id == criterion_id:
            matrix.criteria[idx] = updated
            return
    matrix.criteria.append(updated)


def _require_write_seam_result(write_result: WriteSeamResult | Path) -> WriteSeamResult:
    """Narrow the seam's ``WriteSeamResult | Path`` union for a ``commit=True`` call.

    :func:`~specify_cli.acceptance.matrix.locked_reread_splice_and_write`
    returns a bare :class:`~pathlib.Path` only for a ``commit=False`` caller
    (the accept gate's ``--no-commit``/``--diagnose`` legs); this command
    always calls it with ``commit=True``, so a :class:`~pathlib.Path` here
    means the seam's own contract broke, not a normal outcome.
    """
    if not isinstance(write_result, WriteSeamResult):
        raise TypeError(f"expected a WriteSeamResult from a commit=True seam call, got {type(write_result)!r}")
    return write_result


def _emit_outcome_error(write_result: WriteSeamResult, message: str, *, json_output: bool) -> None:
    """Render EVERY surface (rule 6) and carry the additive ``surfaces`` JSON
    key on an error/refusal arm (WP10 cycle 2, B2).

    ``markup=False`` (B1): a surface diagnostic can legitimately contain a
    bracketed substring -- without it, Rich's markup parser raises
    ``rich.errors.MarkupError`` mid-refusal, crashing the very error report
    it was rendering.
    """
    if json_output:
        payload: dict[str, object] = {_PAYLOAD_KEY_SUCCESS: False, _PAYLOAD_KEY_ERROR: message}
        payload.update(commit_outcome_payload(write_result))
        _emit_json(payload)
    else:
        for line in render_commit_outcome(write_result):
            console.print(line, markup=False)
        console.print(f"{_RED_ERROR_PREFIX}{escape(message)}")


def _emit_write_outcome(write_result: WriteSeamResult, *, mission_slug: str, json_output: bool) -> None:
    """Report a refused/error write outcome and exit; a no-op on success.

    Shared by both the criterion and the negative-invariant mode — the two
    non-success ``WriteSeamResult`` statuses mean the same thing regardless
    of which row this invocation was recording.

    WP10 (T057, contracts/commit-outcome.md rule 5): the exit-code rule now
    additionally consults ``commit_outcome_exit_code`` so a MIXED outcome
    (e.g. the PRIMARY group committed while the coordination group was
    refused) still exits non-zero even though the legacy top-level
    ``write_result.status`` alone would read ``"committed"``.

    WP10 cycle 2 (B2): every non-success arm renders the FULL per-surface
    outcome (not just the legacy ``diagnostic`` string) -- the router's
    ``error``/``refused`` results carry named per-path reason codes
    (``PROTECTED_BRANCH_REFUSED``, ``STATUS_LOCK_HELD``, ...) that were
    previously dropped.
    """
    if write_result.status == "refused":
        _emit_outcome_error(
            write_result,
            f"Could not route the acceptance-verdict write for {mission_slug!r}: {write_result.diagnostic or 'unroutable target'}",
            json_output=json_output,
        )
        raise typer.Exit(1)
    if write_result.status == "error":
        _emit_outcome_error(
            write_result,
            f"Failed to commit acceptance verdict for {mission_slug!r}: {write_result.diagnostic or 'unknown error'}",
            json_output=json_output,
        )
        raise typer.Exit(1)
    if commit_outcome_exit_code(write_result) != 0:
        _emit_outcome_error(
            write_result,
            f"A per-surface commit for {mission_slug!r} was refused; see 'surfaces' for detail.",
            json_output=json_output,
        )
        raise typer.Exit(1)


def _validate_mode_selection(
    *,
    criterion: str | None,
    negative_invariant: str | None,
    result: str | None,
    description: str | None,
    verification_method: str | None,
    json_output: bool,
) -> None:
    """Validate the flag SHAPE before any repo/mission resolution.

    Mirrors the pre-existing "validate before touching I/O" ordering the
    criterion-only command had (``--result`` was checked first): the
    mutual-exclusion and required-together checks for BOTH modes happen here,
    so a shape error never depends on there being a real repo/mission to
    resolve.
    """
    if criterion is not None and negative_invariant is not None:
        _emit_error(
            "--criterion and --negative-invariant are mutually exclusive",
            json_output=json_output,
        )
        raise typer.Exit(2)
    if criterion is None and negative_invariant is None:
        _emit_error(
            "one of --criterion or --negative-invariant is required",
            json_output=json_output,
        )
        raise typer.Exit(2)
    if criterion is not None:
        if result is None:
            _emit_error("--result is required with --criterion", json_output=json_output)
            raise typer.Exit(2)
        if result not in CRITERION_VERDICTS:
            allowed = ", ".join(sorted(CRITERION_VERDICTS))
            _emit_error(f"--result must be one of {allowed}; got {result!r}", json_output=json_output)
            raise typer.Exit(2)
    if negative_invariant is not None:
        if description is None:
            _emit_error("--description is required with --negative-invariant", json_output=json_output)
            raise typer.Exit(2)
        if verification_method is None:
            _emit_error(
                "--verification-method is required with --negative-invariant",
                json_output=json_output,
            )
            raise typer.Exit(2)


def _run_criterion_mode(
    *,
    repo_root: Path,
    mission_slug: str,
    matrix_dir: Path,
    matrix: AcceptanceMatrix,
    criterion: str,
    result: str,
    verification_method: str | None,
    actor: str | None,
    evidence: str | None,
    json_output: bool,
) -> None:
    index_by_id = {c.criterion_id: idx for idx, c in enumerate(matrix.criteria)}
    if criterion not in index_by_id:
        available = ", ".join(sorted(index_by_id)) or "(none)"
        _emit_error(
            f"Unknown criterion {criterion!r} for mission {mission_slug!r}. Available criteria: {available}",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # #4858: compute the candidate row from the PRE-LOCK snapshot (the same
    # shape as before) — the row's VALUE never depends on locking; only the
    # SPLICE into the current on-disk matrix (below) needs the lock. This is
    # also the seam a concurrent-interleaving test wraps to force a sibling
    # invocation to fully commit before this one proceeds (US3).
    existing = matrix.criteria[index_by_id[criterion]]
    updated = _resolve_criterion_update(
        existing,
        result=result,
        verification_method=verification_method,
        actor=actor,
        evidence=evidence,
    )

    fresh_matrix, raw_write_result = locked_reread_splice_and_write(
        repo_root=repo_root,
        mission_slug=mission_slug,
        matrix_dir=matrix_dir,
        splice=lambda fresh: _splice_criterion_update(fresh, criterion, updated),
        commit=True,
        entry_id=criterion,
        message=f"chore(acceptance): record {criterion}={result} for {mission_slug}",
    )
    write_result = _require_write_seam_result(raw_write_result)
    _emit_write_outcome(write_result, mission_slug=mission_slug, json_output=json_output)

    payload = {
        _PAYLOAD_KEY_SUCCESS: True,
        "mission": mission_slug,
        "criterion": criterion,
        "result": result,
        "overall_verdict": fresh_matrix.overall_verdict,
        "write_status": write_result.status,
        "destination_surface": write_result.destination_surface,
        "commit_hash": write_result.commit_hash,
        **commit_outcome_payload(write_result),
    }
    if json_output:
        _emit_json(payload)
    else:
        for line in render_commit_outcome(write_result):
            console.print(line, markup=False)
        console.print(
            f"[green]✓[/green] {criterion}={result} recorded for {mission_slug} (overall_verdict={fresh_matrix.overall_verdict}, write={write_result.status})"
        )


def _run_negative_invariant_mode(
    *,
    repo_root: Path,
    mission_slug: str,
    matrix_dir: Path,
    matrix: AcceptanceMatrix,
    invariant_id: str,
    description: str,
    verification_method: str,
    verification_command: str | None,
    scope: str | None,
    execute: bool,
    json_output: bool,
) -> None:
    """FR-007 register + FR-008 execute, in one deterministic invocation."""
    _register_negative_invariant(
        matrix,
        invariant_id=invariant_id,
        description=description,
        verification_method=verification_method,
        verification_command=verification_command,
        scope=scope,
    )

    if execute:
        # #4858 (FR-008): the slow custom check (a subprocess grep/command)
        # runs OUTSIDE the lock, against the PRE-LOCK snapshot — this is also
        # the seam a concurrent-interleaving test wraps to force a sibling
        # invocation to fully commit before this one proceeds (US1). T020 /
        # FR-008: reuse the existing enforcement engine verbatim — this
        # command never reimplements verification logic. A prior TERMINAL
        # result on an unrelated invariant already in the matrix is preserved
        # by the engine's own NI-2 guard; only the just-registered (freshly
        # ``pending``) row is actually (re-)judged. Only THIS invocation's own
        # judged row is used below — every sibling result the check happens
        # to (re-)compute here is discarded in favour of the fresh re-read
        # (FR-001: a verdict write changes only the row it owns).
        matrix.negative_invariants = enforce_negative_invariants(repo_root, matrix.negative_invariants)

    judged = next(ni for ni in matrix.negative_invariants if ni.invariant_id == invariant_id)

    fresh_matrix, raw_write_result = locked_reread_splice_and_write(
        repo_root=repo_root,
        mission_slug=mission_slug,
        matrix_dir=matrix_dir,
        splice=lambda fresh: _replace_or_append_negative_invariant(fresh, judged),
        commit=True,
        entry_id=invariant_id,
        message=f"chore(acceptance): register negative invariant {invariant_id} for {mission_slug}",
    )
    write_result = _require_write_seam_result(raw_write_result)
    _emit_write_outcome(write_result, mission_slug=mission_slug, json_output=json_output)

    payload = {
        _PAYLOAD_KEY_SUCCESS: True,
        "mission": mission_slug,
        "negative_invariant": invariant_id,
        "result": judged.result,
        "overall_verdict": fresh_matrix.overall_verdict,
        "write_status": write_result.status,
        "destination_surface": write_result.destination_surface,
        "commit_hash": write_result.commit_hash,
        **commit_outcome_payload(write_result),
    }
    if json_output:
        _emit_json(payload)
    else:
        for line in render_commit_outcome(write_result):
            console.print(line, markup=False)
        console.print(
            f"[green]✓[/green] negative invariant {invariant_id}={judged.result} recorded for "
            f"{mission_slug} (overall_verdict={fresh_matrix.overall_verdict}, write={write_result.status})"
        )


def acceptance_verdict(
    mission: Annotated[str, typer.Option("--mission", help="Mission slug, mid8, or mission_id")],
    criterion: Annotated[
        str | None,
        typer.Option(
            "--criterion",
            help="Acceptance criterion id (e.g. FR-001); mutually exclusive with --negative-invariant",
        ),
    ] = None,
    result: Annotated[str | None, typer.Option("--result", help="pass | fail | pending (required with --criterion)")] = None,
    verification_method: Annotated[
        str | None,
        typer.Option(
            "--verification-method",
            help=(
                "Criterion mode: how this was verified (updates proof_type). "
                "Negative-invariant mode: grep_absence | route_check | custom_command "
                "(required with --negative-invariant)."
            ),
        ),
    ] = None,
    actor: Annotated[str | None, typer.Option("--actor", help="Actor recording this verdict")] = None,
    evidence: Annotated[str | None, typer.Option("--evidence", help="Evidence reference (URL/path/etc.)")] = None,
    negative_invariant: Annotated[
        str | None,
        typer.Option(
            "--negative-invariant",
            help="Negative invariant id to register/execute (FR-007/FR-008); mutually exclusive with --criterion",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Negative invariant description (required with --negative-invariant)"),
    ] = None,
    verification_command: Annotated[
        str | None,
        typer.Option("--verification-command", help="grep pattern or command verifying the invariant's absence"),
    ] = None,
    scope: Annotated[
        str | None,
        typer.Option("--scope", help="Whitespace-separated repo-relative search root(s); grep_absence only"),
    ] = None,
    execute: Annotated[
        bool,
        typer.Option(
            "--execute/--no-execute",
            help="Run the invariant's verification immediately after registering (FR-008; default: on)",
        ),
    ] = True,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
) -> None:
    """Record an acceptance-criterion verdict, or register/execute a negative
    invariant (FR-007/FR-008) — exactly one of ``--criterion``/
    ``--negative-invariant``, both routed through the WP03 write seam."""
    _validate_mode_selection(
        criterion=criterion,
        negative_invariant=negative_invariant,
        result=result,
        description=description,
        verification_method=verification_method,
        json_output=json_output,
    )

    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        _emit_error(str(exc), json_output=json_output)
        raise typer.Exit(1) from None

    resolved = resolve_mission_handle(mission, repo_root, json_mode=json_output)
    mission_slug = resolved.mission_slug

    matrix_dir = _matrix_write_dir(repo_root, mission_slug)
    matrix = read_acceptance_matrix(matrix_dir)
    if matrix is None:
        _emit_error(
            f"No acceptance-matrix.json found for mission {mission_slug!r}. Run `spec-kitty agent mission finalize-tasks` to scaffold it first.",
            json_output=json_output,
        )
        raise typer.Exit(1)

    try:
        if negative_invariant is not None:
            assert description is not None and verification_method is not None  # _validate_mode_selection
            _run_negative_invariant_mode(
                repo_root=repo_root,
                mission_slug=mission_slug,
                matrix_dir=matrix_dir,
                matrix=matrix,
                invariant_id=negative_invariant,
                description=description,
                verification_method=verification_method,
                verification_command=verification_command,
                scope=scope,
                execute=execute,
                json_output=json_output,
            )
            return

        assert criterion is not None and result is not None  # guaranteed by _validate_mode_selection
        _run_criterion_mode(
            repo_root=repo_root,
            mission_slug=mission_slug,
            matrix_dir=matrix_dir,
            matrix=matrix,
            criterion=criterion,
            result=result,
            verification_method=verification_method,
            actor=actor,
            evidence=evidence,
            json_output=json_output,
        )
    except FeatureStatusLockTimeoutError as exc:
        # #4858 (C-012/FR-015): fail CLOSED on a lock-acquisition timeout —
        # this is raised by the shared seam
        # (``specify_cli.acceptance.matrix.locked_reread_splice_and_write``)
        # BEFORE the re-read or any write happens, so no unlocked fallback
        # write ever occurs. Translated into a structured, non-zero exit
        # rather than an unhandled traceback.
        _emit_error(
            f"Could not acquire the acceptance-matrix lock for mission {mission_slug!r} within {exc.timeout}s: {exc}",
            json_output=json_output,
        )
        raise typer.Exit(1) from None


__all__ = ["acceptance_verdict"]
