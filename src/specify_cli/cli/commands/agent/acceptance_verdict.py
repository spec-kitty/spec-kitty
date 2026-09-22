"""``agent mission acceptance-verdict`` command (WP04 / T015; WP05 / T019-T020).

write-side-seam-matrix-tracer-01KYP3MH, FR-001/FR-002/FR-012.
post-merge-write-authoring-finish-01KYRRM5, FR-007/FR-008 (#2318).

Records ONE acceptance-criterion verdict (a ``pass``/``fail``/``pending``
result plus its verification method/actor/evidence) into the mission's
``acceptance-matrix.json``, then commits it through the WP03 write seam
(:func:`specify_cli.acceptance.matrix.write_and_commit_acceptance_matrix`,
which composes :func:`~specify_cli.coordination.write_seam.write_artifact`).

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

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from specify_cli.acceptance.matrix import (
    CRITERION_VERDICTS,
    AcceptanceCriterion,
    AcceptanceMatrix,
    NegativeInvariant,
    enforce_negative_invariants,
    read_acceptance_matrix,
    write_and_commit_acceptance_matrix,
)
from specify_cli.agent_tasks_ports import RealRender
from specify_cli.cli.console import console
from specify_cli.cli.selector_resolution import resolve_mission_handle
from kernel.clock import now_utc_iso
from specify_cli.status import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
)
from specify_cli.task_utils import TaskCliError, find_repo_root

if TYPE_CHECKING:
    from specify_cli.coordination.write_seam import WriteSeamResult

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
        console.print(f"{_RED_ERROR_PREFIX}{message}")


def _matrix_read_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the matrix's current read/write surface via the ONE kind-aware seam.

    Mirrors ``acceptance/gates_core.py::_acceptance_matrix_read_dir`` — the
    same :func:`mission_runtime.placement_seam` authority, never a hand-derived
    ``kitty-specs/<slug>`` join.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    return placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.ACCEPTANCE_MATRIX
    )


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


def _replace_or_append_negative_invariant(
    matrix: AcceptanceMatrix, judged: NegativeInvariant
) -> None:
    """Splice an ALREADY-JUDGED row into ``matrix`` (insert-if-absent).

    #4858 (FR-002/C-4858-modes): unlike :func:`_register_negative_invariant`
    (which synthesizes a fresh ``pending`` row for a NEW registration), this
    replaces-or-appends a row that has ALREADY been through
    :func:`~specify_cli.acceptance.matrix.enforce_negative_invariants` — it
    must never reset the judged result back to ``pending``. Used exclusively
    inside :func:`_locked_reread_splice_and_write`'s critical section to
    merge the invocation's own judged row into the freshly re-read on-disk
    matrix, leaving every sibling row untouched (FR-001).
    """
    for idx, existing in enumerate(matrix.negative_invariants):
        if existing.invariant_id == judged.invariant_id:
            matrix.negative_invariants[idx] = judged
            return
    matrix.negative_invariants.append(judged)


def _splice_criterion_update(
    matrix: AcceptanceMatrix, criterion_id: str, updated: AcceptanceCriterion
) -> None:
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


def _locked_reread_splice_and_write(
    *,
    repo_root: Path,
    mission_slug: str,
    matrix_dir: Path,
    entry_id: str,
    message: str,
    splice: Callable[[AcceptanceMatrix], None],
) -> tuple[AcceptanceMatrix, WriteSeamResult]:
    """#4858 — the locked re-read + single-row splice + write+commit critical section.

    This is the ONE critical section shared by both verdict modes
    (C-4858-lock / C-4858-reread-in-lock): ``matrix_dir`` is resolved ONCE
    by the caller — BEFORE any slow check/seam call and BEFORE this lock is
    acquired — and reused here as both the re-read base and the write
    target (FR-003/FR-017/C-013), so the re-read surface agrees with
    ``commit_for_mission``'s resolved placement surface. On a coordination
    topology this holds once the coordination worktree is materialized —
    the normal state once a mission has passed ``finalize-tasks`` (the
    degrade-to-primary read documented in ``mission_runtime.resolution``
    applies only to the pre-materialization creation window).

    The re-read (:func:`~specify_cli.acceptance.matrix.read_acceptance_matrix`)
    AND the write+commit both happen while the lock is held — a re-read
    placed outside the lock would still pass a single-threaded serialized
    harness while reopening the exact lost-update race this closes.

    Fails CLOSED (C-012/FR-015): on a lock-acquisition timeout this lets
    :class:`~specify_cli.status.locking.FeatureStatusLockTimeoutError`
    propagate WITHOUT performing the re-read or any write — the caller
    translates it into a structured, non-zero exit rather than falling back
    to an unlocked write.
    """
    with feature_status_lock(
        repo_root, matrix_dir.name, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
    ):
        fresh_matrix = read_acceptance_matrix(matrix_dir)
        if fresh_matrix is None:
            # The matrix vanished between the pre-lock existence check and
            # this re-read (an external actor removed it mid-flight) — start
            # from an empty, schema-valid matrix rather than crashing; the
            # splice below still inserts exactly the row this invocation owns.
            fresh_matrix = AcceptanceMatrix(mission_slug=mission_slug)
        splice(fresh_matrix)
        write_result = write_and_commit_acceptance_matrix(
            repo_root,
            mission_slug,
            matrix_dir,
            fresh_matrix,
            entry_id=entry_id,
            message=message,
        )
    return fresh_matrix, write_result


def _emit_write_outcome(
    write_result: WriteSeamResult, *, mission_slug: str, json_output: bool
) -> None:
    """Report a refused/error write outcome and exit; a no-op on success.

    Shared by both the criterion and the negative-invariant mode — the two
    non-success ``WriteSeamResult`` statuses mean the same thing regardless
    of which row this invocation was recording.
    """
    if write_result.status == "refused":
        _emit_error(
            f"Could not route the acceptance-verdict write for {mission_slug!r}: "
            f"{write_result.diagnostic or 'unroutable target'}",
            json_output=json_output,
        )
        raise typer.Exit(1)
    if write_result.status == "error":
        _emit_error(
            f"Failed to commit acceptance verdict for {mission_slug!r}: "
            f"{write_result.diagnostic or 'unknown error'}",
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
            _emit_error(
                "--description is required with --negative-invariant", json_output=json_output
            )
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
            f"Unknown criterion {criterion!r} for mission {mission_slug!r}. "
            f"Available criteria: {available}",
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

    fresh_matrix, write_result = _locked_reread_splice_and_write(
        repo_root=repo_root,
        mission_slug=mission_slug,
        matrix_dir=matrix_dir,
        entry_id=criterion,
        message=f"chore(acceptance): record {criterion}={result} for {mission_slug}",
        splice=lambda fresh: _splice_criterion_update(fresh, criterion, updated),
    )
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
    }
    if json_output:
        _emit_json(payload)
    else:
        console.print(
            f"[green]✓[/green] {criterion}={result} recorded for {mission_slug} "
            f"(overall_verdict={fresh_matrix.overall_verdict}, write={write_result.status})"
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
        matrix.negative_invariants = enforce_negative_invariants(
            repo_root, matrix.negative_invariants
        )

    judged = next(ni for ni in matrix.negative_invariants if ni.invariant_id == invariant_id)

    fresh_matrix, write_result = _locked_reread_splice_and_write(
        repo_root=repo_root,
        mission_slug=mission_slug,
        matrix_dir=matrix_dir,
        entry_id=invariant_id,
        message=f"chore(acceptance): register negative invariant {invariant_id} for {mission_slug}",
        splice=lambda fresh: _replace_or_append_negative_invariant(fresh, judged),
    )
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
    }
    if json_output:
        _emit_json(payload)
    else:
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
    result: Annotated[
        str | None, typer.Option("--result", help="pass | fail | pending (required with --criterion)")
    ] = None,
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
        typer.Option(
            "--verification-command", help="grep pattern or command verifying the invariant's absence"
        ),
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

    matrix_dir = _matrix_read_dir(repo_root, mission_slug)
    matrix = read_acceptance_matrix(matrix_dir)
    if matrix is None:
        _emit_error(
            f"No acceptance-matrix.json found for mission {mission_slug!r}. "
            "Run `spec-kitty agent mission finalize-tasks` to scaffold it first.",
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
        # this is raised by ``feature_status_lock`` BEFORE the re-read or any
        # write happens (see ``_locked_reread_splice_and_write``), so no
        # unlocked fallback write ever occurs. Translated into a structured,
        # non-zero exit rather than an unhandled traceback.
        _emit_error(
            f"Could not acquire the acceptance-matrix lock for mission "
            f"{mission_slug!r} within {exc.timeout}s: {exc}",
            json_output=json_output,
        )
        raise typer.Exit(1) from None


__all__ = ["acceptance_verdict"]
