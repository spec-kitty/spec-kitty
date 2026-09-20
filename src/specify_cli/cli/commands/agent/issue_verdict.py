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
from typing import Annotated, Any

import typer

from mission_runtime import MissionArtifactKind, coord_read_dir_for
from specify_cli.cli.console import console
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.core.paths import locate_project_root
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.tasks.issue_matrix import (
    ISSUE_MATRIX_JSON_FILENAME,
    IssueMatrixEntry,
    parse_issue_matrix_document,
    write_issue_matrix,
)
from specify_cli.tasks.issue_matrix_migration import migrate_issue_matrix_to_json

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
    migrate_result = migrate_issue_matrix_to_json(
        feature_dir,
        repo_root=repo_root,
        mission_slug=mission_slug,
        policy=policy,
        actor=actor,
    )
    migrated = migrate_result is not None and migrate_result.status == "committed"
    # Re-resolve: a first coord-routed write may have materialized the
    # coordination worktree that did not exist a moment ago.
    return _resolve_read_dir(repo_root, mission_slug, feature_dir), migrated


def _upsert_row(
    rows: dict[str, IssueMatrixEntry],
    issue_ref: str,
    *,
    verdict: str,
    evidence_ref: str | None,
    wp: str | None,
) -> None:
    """Set *issue_ref*'s verdict (and optionally evidence_ref/wp) in place.

    Preserves every OTHER field on an existing row (title/scope/fr/nfr/sc/repo)
    -- this command sets stored per-item status only (reviewer guidance);
    derived/computed fields are never touched here because this schema has
    none (``overall_verdict``-style computed fields live on the sibling
    acceptance-matrix entity, not this one).
    """
    existing = rows.get(issue_ref)
    if existing is None:
        rows[issue_ref] = IssueMatrixEntry(
            verdict=verdict,
            evidence_ref=evidence_ref or "",
            wp=wp,
        )
        return
    rows[issue_ref] = replace(
        existing,
        verdict=verdict,
        evidence_ref=evidence_ref if evidence_ref is not None else existing.evidence_ref,
        wp=wp if wp is not None else existing.wp,
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
        IssueVerdictError: invalid ``--verdict`` or empty ``--actor``.
    """
    if not actor.strip():
        raise IssueVerdictError("--actor must be a non-empty string", code="empty_actor")
    verdict = _validate_verdict(verdict)
    issue_ref = _normalize_issue_ref(issue)

    root = repo_root if repo_root is not None else (locate_project_root() or Path.cwd())
    resolved = resolve_mission_handle(mission, root, json_mode=json_mode)
    mission_slug = resolved.mission_slug
    feature_dir = resolved.feature_dir

    read_dir, migrated = _migrate_if_needed(
        repo_root=root, mission_slug=mission_slug, feature_dir=feature_dir, actor=actor
    )
    rows = _load_raw_rows(read_dir / ISSUE_MATRIX_JSON_FILENAME)
    _upsert_row(rows, issue_ref, verdict=verdict, evidence_ref=evidence_ref, wp=wp)

    policy = ProtectionPolicy.resolve(root)
    result = write_issue_matrix(
        repo_root=root,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        rows=rows,
        policy=policy,
        actor=actor,
    )

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
        console.print(
            f"[green]OK[/green] {payload['row_or_entry_ref']} -> {verdict} "
            f"({payload['status']}, surface={payload['destination_surface']})"
        )

    if not payload["ok"]:
        raise typer.Exit(1)


__all__ = ["issue_verdict_command"]
