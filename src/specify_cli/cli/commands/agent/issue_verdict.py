"""``issue-verdict`` command (WP07, FR-003 / FR-012 / NFR-001).

Sets a single row's per-item ``verdict``/``evidence_ref`` on the structured
``issue-matrix.json`` and routes the commit through ``write_target
(ISSUE_MATRIX)`` via WP05's canonical writer
(:func:`specify_cli.tasks.issue_matrix.write_issue_matrix`), which in turn
routes through the WP03 write-seam helper
(:func:`specify_cli.coordination.write_seam.write_artifact`) -- this module
carries NO independent compute-and-commit path (C-001/C-006): it only reads
the current document, mutates one row in memory, and hands the full row map
back to the one canonical writer.

**Vocabulary** (reviewer-confirmed WP05 as-built, see
``docs/development/read-side-seam-classification.md`` history and
``kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/data-model.md``): rows
are keyed by ``issue_ref`` and carry ``verdict``/``evidence_ref`` over the
closed-set :class:`~specify_cli.cli.commands.review._issue_matrix
.IssueMatrixVerdict` (``fixed`` | ``verified-already-fixed`` |
``deferred-with-followup`` | ``in-mission`` | ``not-applicable``) -- NOT the
earlier ``status: open|addressed|not_applicable|verified`` sketch still shown
in the now-stale ``contracts/commands.md`` example. ``--verdict`` accepts
only a genuine :class:`IssueMatrixVerdict` member so the approve gate's
``is`` identity check (``tasks_parsing_validation.py:116``) actually matches.

**Migrate-on-write** (FR-013): when neither ``issue-matrix.json`` nor
``issue-matrix.md`` resolves on the coord-aware read surface, the row is
simply created fresh. When only the legacy ``.md`` is present, this command
migrates it via WP05's :func:`~specify_cli.tasks.issue_matrix_migration
.migrate_issue_matrix_to_json` (a second, black-box call -- reusing the
existing migration writer rather than re-deriving its legacy-row-to-entry
mapping here) before applying the verdict mutation, so a legacy mission is
upgraded to structured JSON on its first ``issue-verdict`` write.

**Idempotence** (FR-012): re-invoking with identical inputs re-serializes a
byte-identical document, so :func:`write_issue_matrix`'s underlying
``commit_for_mission`` call returns ``"unchanged"`` -- this module does not
hand-roll its own idempotence check.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from mission_runtime import MissionArtifactKind, coord_read_dir_for
from specify_cli.cli.console import console
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.core.paths import locate_project_root
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.status import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
)
from specify_cli.tasks.issue_matrix import (
    ISSUE_MATRIX_JSON_FILENAME,
    IssueMatrixEntry,
    parse_issue_matrix_document,
    write_issue_matrix,
)
from specify_cli.tasks.issue_matrix_migration import (
    IssueMatrixMigrationError,
    migrate_issue_matrix_to_json,
)

if TYPE_CHECKING:
    from specify_cli.coordination.write_seam import ProtectionPolicyLike, WriteSeamResult

#: FR-011 deferred-surface disclosure referenced by every write-routing result
#: shape (data-model.md "Entity: Write-routing result").
_ZERO_WRITE_REFUSAL_DEFERRED_TO = "#3033"

_WRITE_SUCCESS_STATUSES = frozenset({"committed", "unchanged"})


class IssueVerdictError(Exception):
    """Structured CLI-input error for ``issue-verdict`` (never a raw traceback)."""

    def __init__(self, message: str, *, code: str) -> None:
        self.code = code
        super().__init__(message)


def _normalize_issue_ref(raw: str) -> str:
    """Return *raw* canonicalized to the ``#NNNN`` row-key form.

    Accepts either ``"#1726"`` or the bare ``"1726"`` -- both forms appear in
    operator usage; the row map is keyed on the ``#``-prefixed form
    (:func:`~specify_cli.tasks.issue_matrix.scaffold_issue_matrix` uses the
    same convention).
    """
    stripped = raw.strip()
    return stripped if stripped.startswith("#") else f"#{stripped}"


def _validate_verdict(verdict: str) -> str:
    """Return *verdict* unchanged if it is a genuine ``IssueMatrixVerdict`` member.

    Raises:
        IssueVerdictError: when *verdict* is not in the closed set -- a
            free-form string would silently never match the approve gate's
            ``is IssueMatrixVerdict.X`` identity check.
    """
    from specify_cli.cli.commands.review._issue_matrix import IssueMatrixVerdict

    try:
        IssueMatrixVerdict(verdict)
    except ValueError:
        allowed = ", ".join(member.value for member in IssueMatrixVerdict)
        raise IssueVerdictError(
            f"--verdict {verdict!r} is not in the allowed set: {allowed}",
            code="invalid_verdict",
        ) from None
    return verdict


def _resolve_read_dir(repo_root: Path, mission_slug: str, feature_dir: Path) -> Path:
    """Return the coord-aware read surface for ``issue-matrix.json``.

    Falls back to the primary ``feature_dir`` for coord-less topologies or a
    not-yet-materialized coordination worktree (the same fallback
    :func:`~specify_cli.tasks.issue_matrix.scaffold_issue_matrix` and
    ``status.doctor`` already use for this kind).
    """
    return coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX) or feature_dir


def _load_raw_rows(json_path: Path) -> dict[str, IssueMatrixEntry]:
    """Parse ``json_path`` preserving EVERY row, including a placeholder verdict.

    Deliberately NOT :func:`~specify_cli.tasks.issue_matrix_migration
    .load_issue_matrix` -- that reader filters out rows whose verdict is not
    (yet) a genuine :class:`IssueMatrixVerdict` member (e.g. a freshly
    scaffolded ``"unknown"`` placeholder). Re-serializing only the filtered
    subset would silently drop those placeholder rows for OTHER issues on
    every mutation. :func:`~specify_cli.tasks.issue_matrix.parse_issue_matrix_document`
    is the round-trip-preserving counterpart this write path needs.
    """
    if not json_path.exists():
        return {}
    data: dict[str, Any] = json.loads(json_path.read_text(encoding="utf-8"))
    return parse_issue_matrix_document(data)


def _migrate_if_needed(
    *,
    repo_root: Path,
    mission_slug: str,
    feature_dir: Path,
    actor: str,
) -> tuple[Path, bool]:
    """Migrate a legacy ``.md``-only mission on this first structured write (FR-013).

    Only invoked when neither ``issue-matrix.json`` nor ``issue-matrix.md``
    resolves as ALREADY migrated on the coord-aware read surface -- checking
    the read surface (not the primary ``feature_dir`` alone) avoids a false
    re-migrate that would clobber a coord-resident JSON already updated by a
    prior ``issue-verdict`` call with data re-derived from the untouched
    legacy ``.md`` residue (:func:`migrate_issue_matrix_to_json` intentionally
    leaves that residue in place).

    Returns:
        ``(read_dir, migrated)`` -- ``read_dir`` re-resolved AFTER a migration
        attempt (a first write may materialize the coordination worktree),
        and ``migrated`` is ``True`` only when a genuine legacy-to-JSON
        conversion was committed by this call.
    """
    read_dir = _resolve_read_dir(repo_root, mission_slug, feature_dir)
    if (read_dir / ISSUE_MATRIX_JSON_FILENAME).exists():
        return read_dir, False

    policy = ProtectionPolicy.resolve(repo_root)
    try:
        migrate_result = migrate_issue_matrix_to_json(
            feature_dir,
            repo_root=repo_root,
            mission_slug=mission_slug,
            policy=policy,
            read_dir=read_dir,
            actor=actor,
        )
    except IssueMatrixMigrationError as exc:
        # #4868: a malformed authoritative .md surfaces as a structured CLI
        # error (caught by ``issue_verdict_command``), never a raw traceback.
        raise IssueVerdictError(str(exc), code="malformed_legacy_matrix") from exc
    migrated = migrate_result is not None and migrate_result.status == "committed"
    # Re-resolve: a first coord-routed write may have materialized the
    # coordination worktree that did not exist a moment ago.
    return _resolve_read_dir(repo_root, mission_slug, feature_dir), migrated


def _resolve_issue_row_update(
    existing: IssueMatrixEntry | None,
    *,
    verdict: str,
    evidence_ref: str | None,
    wp: str | None,
) -> IssueMatrixEntry:
    """Compute the updated row for *issue_ref* (verdict/evidence_ref/wp only).

    Preserves every OTHER field on an existing row (title/scope/fr/nfr/sc/repo)
    -- this command sets stored per-item status only (reviewer guidance);
    derived/computed fields are never touched here because this schema has
    none (``overall_verdict``-style computed fields live on the sibling
    acceptance-matrix entity, not this one).

    #4884 (mirrors #4858's ``_resolve_criterion_update``): the row's VALUE
    never depends on locking -- it is computed once, from the pre-lock
    snapshot -- only the SPLICE of this row into the freshly re-read row map
    (:func:`_splice_issue_row`, run inside the lock) needs to be serialized
    against a concurrent sibling writing a DIFFERENT row.
    """
    if existing is None:
        return IssueMatrixEntry(
            verdict=verdict,
            evidence_ref=evidence_ref or "",
            wp=wp,
        )
    return replace(
        existing,
        verdict=verdict,
        evidence_ref=evidence_ref if evidence_ref is not None else existing.evidence_ref,
        wp=wp if wp is not None else existing.wp,
    )


def _splice_issue_row(rows: dict[str, IssueMatrixEntry], issue_ref: str, updated: IssueMatrixEntry) -> None:
    """Set *issue_ref* to *updated* in *rows* (insert-if-absent).

    #4884 (mirrors #4858's ``_splice_criterion_update``): *rows* is the
    FRESHLY re-read row map (never the pre-lock snapshot) each time this
    runs inside :func:`_locked_reread_splice_and_write`'s critical section,
    so a concurrently-added/removed sibling row is never clobbered by this
    invocation's write (FR-001-equivalent: a verdict write changes only the
    row it owns).
    """
    rows[issue_ref] = updated


def _locked_reread_splice_and_write(
    *,
    repo_root: Path,
    mission_slug: str,
    read_dir: Path,
    feature_dir: Path,
    issue_ref: str,
    updated_entry: IssueMatrixEntry,
    policy: ProtectionPolicyLike,
    actor: str,
) -> WriteSeamResult:
    """#4884 -- the locked re-read + single-row splice + write+commit critical section.

    Mirrors ``acceptance_verdict._locked_reread_splice_and_write`` (#4858):
    ``read_dir`` is resolved ONCE by the caller -- AFTER ``_migrate_if_needed``
    (a slow, one-shot legacy-migration check that is #4868's concern, not
    this lock's) and BEFORE this lock is acquired -- and reused here as both
    the re-read surface and (via ``write_issue_matrix``'s own resolution) the
    write target, so the re-read agrees with ``commit_for_mission``'s
    resolved placement surface. The lock key is ``read_dir.name`` -- the
    mission directory name, matching #4858's ``matrix_dir.name`` convention
    (never a bare mission slug; see ``feature_status_lock_path``'s FR-004 /
    C-003 contract).

    The re-read (:func:`_load_raw_rows`) AND the write+commit both happen
    while the lock is held -- a re-read placed outside the lock would still
    pass a single-threaded serialized harness while reopening the exact
    lost-update race this closes (two concurrent ``issue-verdict`` calls for
    DIFFERENT issues each read the full row map, mutate their own row in
    memory, and serialize the WHOLE map back -- the loser's write silently
    drops the winner's row).

    Fails CLOSED (mirrors #4858's C-012/FR-015): on a lock-acquisition
    timeout this lets :class:`~specify_cli.status.FeatureStatusLockTimeoutError`
    propagate WITHOUT performing the re-read or any write -- the caller
    (:func:`do_issue_verdict`) translates it into a structured
    :class:`IssueVerdictError` rather than falling back to an unlocked write.
    """
    with feature_status_lock(repo_root, read_dir.name, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS):
        fresh_rows = _load_raw_rows(read_dir / ISSUE_MATRIX_JSON_FILENAME)
        _splice_issue_row(fresh_rows, issue_ref, updated_entry)
        return write_issue_matrix(
            repo_root=repo_root,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            rows=fresh_rows,
            policy=policy,
            actor=actor,
        )


def do_issue_verdict(
    *,
    mission: str,
    issue: str,
    verdict: str,
    actor: str,
    wp: str | None = None,
    evidence_ref: str | None = None,
    repo_root: Path | None = None,
    json_mode: bool = False,
) -> dict[str, object]:
    """Pure orchestration core for ``issue-verdict`` -- no typer dependency.

    Args:
        mission: Mission handle (slug, mission_id, or mid8).
        issue: Issue reference (``"#1726"`` or bare ``"1726"``).
        verdict: Must be a genuine ``IssueMatrixVerdict`` member value.
        actor: Non-empty identity of the acting agent.
        wp: Optional owning work-package id to stamp on the row.
        evidence_ref: Optional evidence text/link.
        repo_root: Repository root; defaults to :func:`locate_project_root`.
        json_mode: Formats an unresolvable ``--mission`` handle's error as
            JSON (mirrors ``--json``); that error path calls ``sys.exit(2)``
            inside :func:`resolve_mission_handle` itself.

    Returns:
        A structured result dict: ``{ok, kind, destination_surface,
        row_or_entry_ref, migrated, status, refusal?}``.

    Raises:
        IssueVerdictError: invalid ``--verdict``, empty ``--actor``, or a
            status-lock acquisition timeout (code ``"lock_timeout"`` -- fails
            CLOSED, never falls back to an unlocked write).
    """
    if not actor.strip():
        raise IssueVerdictError("--actor must be a non-empty string", code="empty_actor")
    verdict = _validate_verdict(verdict)
    issue_ref = _normalize_issue_ref(issue)

    root = repo_root if repo_root is not None else (locate_project_root() or Path.cwd())
    resolved = resolve_mission_handle(mission, root, json_mode=json_mode)
    mission_slug = resolved.mission_slug
    feature_dir = resolved.feature_dir

    # #4868's concern: migration is a slow, one-shot legacy-.md conversion --
    # it stays OUTSIDE the lock, exactly like #4858 keeps the pre-lock
    # existence check outside its own critical section.
    read_dir, migrated = _migrate_if_needed(repo_root=root, mission_slug=mission_slug, feature_dir=feature_dir, actor=actor)

    # The candidate row's VALUE never depends on locking (see
    # ``_resolve_issue_row_update``'s docstring) -- computed once, here,
    # from the pre-lock snapshot.
    pre_lock_rows = _load_raw_rows(read_dir / ISSUE_MATRIX_JSON_FILENAME)
    updated_entry = _resolve_issue_row_update(pre_lock_rows.get(issue_ref), verdict=verdict, evidence_ref=evidence_ref, wp=wp)

    policy = ProtectionPolicy.resolve(root)
    try:
        result = _locked_reread_splice_and_write(
            repo_root=root,
            mission_slug=mission_slug,
            read_dir=read_dir,
            feature_dir=feature_dir,
            issue_ref=issue_ref,
            updated_entry=updated_entry,
            policy=policy,
            actor=actor,
        )
    except FeatureStatusLockTimeoutError as exc:
        # #4884 (mirrors #4858's C-012/FR-015): fail CLOSED on a lock-
        # acquisition timeout -- raised by ``feature_status_lock`` BEFORE the
        # re-read or any write happens, so no unlocked fallback write ever
        # occurs.
        raise IssueVerdictError(
            f"Could not acquire the issue-matrix lock for mission {mission_slug!r} within {exc.timeout}s: {exc}",
            code="lock_timeout",
        ) from exc

    payload: dict[str, object] = {
        "ok": result.status in _WRITE_SUCCESS_STATUSES,
        "kind": "ISSUE_MATRIX",
        "destination_surface": result.destination_surface,
        "row_or_entry_ref": issue_ref,
        "migrated": migrated,
        "status": result.status,
    }
    if result.status == "refused":
        payload["refusal"] = {
            "reason": result.diagnostic,
            "deferred_to": _ZERO_WRITE_REFUSAL_DEFERRED_TO,
        }
    return payload


# ---------------------------------------------------------------------------
# Typer wrapper
# ---------------------------------------------------------------------------


def issue_verdict_command(
    mission: Annotated[str, typer.Option("--mission", help="Mission handle (slug, mission_id, or mid8).")],
    issue: Annotated[str, typer.Option("--issue", help='Issue reference, e.g. "#1726".')],
    verdict: Annotated[
        str,
        typer.Option(
            "--verdict",
            help=(
                "fixed | verified-already-fixed | deferred-with-followup | in-mission | "
                "not-applicable (non-gating: cited for context or a PR/commit reference, "
                "no work owed; unlike in-mission it is terminal -- it also passes the "
                "done/merge completeness gate unchanged)"
            ),
        ),
    ],
    actor: Annotated[str, typer.Option("--actor", help="Identity of the acting agent.")],
    wp: Annotated[str | None, typer.Option("--wp", help="Owning work-package id (e.g. WP01).")] = None,
    evidence_ref: Annotated[
        str | None,
        typer.Option(
            "--evidence-ref",
            help=(
                "Evidence text or link for the verdict. Required when --verdict is "
                "deferred-with-followup: the value must contain a follow-up handle "
                "('#NNN' or a 'Follow-up:' substring), or the row fails validation."
            ),
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format.")] = False,
) -> None:
    """Set an issue-matrix row's verdict, routed via ``write_target(ISSUE_MATRIX)``."""
    try:
        payload = do_issue_verdict(
            mission=mission,
            issue=issue,
            verdict=verdict,
            actor=actor,
            wp=wp,
            evidence_ref=evidence_ref,
            json_mode=json_output,
        )
    except IssueVerdictError as exc:
        error_payload = {"error": str(exc), "code": exc.code}
        if json_output:
            console.emit_json(error_payload, indent=None)
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from None

    if json_output:
        console.emit_json(payload, indent=None, sort_keys=True)
    else:
        console.print(f"[green]OK[/green] {payload['row_or_entry_ref']} -> {verdict} ({payload['status']}, surface={payload['destination_surface']})")

    if not payload["ok"]:
        raise typer.Exit(1)


__all__ = ["issue_verdict_command"]
