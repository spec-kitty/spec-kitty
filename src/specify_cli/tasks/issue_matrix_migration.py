"""Issue-matrix migration sub-module (FR-013, NFR-006 back-compat).

Hosts:

- **Failover-read**: read the legacy ``issue-matrix.md`` when
  ``issue-matrix.json`` is absent.
- **The ONE canonical dir-based reader** (:func:`load_issue_matrix`, M7 /
  T023): every live consumer (doctor, post-merge review, move-task/approval,
  finalize-lint) reads THROUGH this function -- no second reader.
- **Migrate-on-write** (:func:`migrate_issue_matrix_to_json`): the first
  structured write converts a legacy ``.md``-only mission to JSON.
- **Bulk migration**: a dedicated CLI command
  (``spec-kitty issue-matrix migrate [--mission <handle>] --json``) for a
  one-shot swap-over, backed by the SAME helpers above.

write-side-seam-matrix-tracer-01KYP3MH WP05 (T022/T023).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from specify_cli.cli.console import console
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.tasks.issue_matrix import (
    ISSUE_MATRIX_JSON_FILENAME,
    ISSUE_MATRIX_MD_FILENAME,
    IssueMatrixEntry,
    write_issue_matrix,
)

if TYPE_CHECKING:
    from specify_cli.cli.commands.review._issue_matrix import IssueMatrixRow
    from specify_cli.coordination.write_seam import ProtectionPolicyLike, WriteSeamResult

_ROWS_KEY = "rows"


class IssueMatrixMigrationError(Exception):
    """A legacy ``issue-matrix.md`` cannot be faithfully migrated to JSON.

    Raised (rather than silently serializing an empty/lossy matrix) when the
    authoritative legacy markdown fails structural validation and yields no
    usable rows -- migrating it would drop every existing verdict (#4868). The
    ``issue-verdict`` command path translates this into a structured
    ``IssueVerdictError`` so the operator sees a clear message, not a raw
    traceback or a silent data loss.
    """


# ---------------------------------------------------------------------------
# Structured (.json) parsing -- shared by load_issue_matrix and the validator
# ---------------------------------------------------------------------------


def _parse_structured_rows(
    json_path: Path,
) -> tuple[list[IssueMatrixRow], list[dict[str, str]]]:
    """Parse ``issue-matrix.json`` into ``(valid rows, diagnostics)``.

    An entry whose ``verdict`` is not a valid :class:`IssueMatrixVerdict`
    member (e.g. a freshly-scaffolded ``"unknown"`` placeholder) is EXCLUDED
    from the row list -- mirroring the legacy markdown parser's existing
    filtering contract (``tasks_parsing_validation.py`` relies on
    ``row.verdict is IssueMatrixVerdict.X`` identity, which only a genuine
    enum member satisfies) -- but IS surfaced as a diagnostic so a lint/
    validation caller still sees it.
    """
    import re

    from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic
    from specify_cli.cli.commands.review._issue_matrix import (
        IssueMatrixRow,
        IssueMatrixVerdict,
    )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [
            {
                "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT),
                "message": f"issue-matrix.json could not be parsed: {exc}",
            }
        ]

    raw_rows = data.get(_ROWS_KEY, {}) if isinstance(data, dict) else {}
    if not isinstance(raw_rows, dict):
        return [], [
            {
                "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT),
                "message": "issue-matrix.json 'rows' must be an object keyed by issue ref.",
            }
        ]

    rows: list[IssueMatrixRow] = []
    diagnostics: list[dict[str, str]] = []
    for issue_ref, entry in raw_rows.items():
        if not isinstance(entry, dict):
            diagnostics.append(
                {
                    "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT),
                    "message": f"Row for issue '{issue_ref}': malformed entry (expected an object).",
                }
            )
            continue

        evidence_ref = str(entry.get("evidence_ref") or "")
        if not evidence_ref:
            diagnostics.append(
                {
                    "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_EVIDENCE_REF_EMPTY),
                    "message": f"Row for issue '{issue_ref}': evidence_ref is empty.",
                }
            )

        raw_verdict = str(entry.get("verdict") or "").strip().lower()
        try:
            verdict = IssueMatrixVerdict(raw_verdict)
        except ValueError:
            diagnostics.append(
                {
                    "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_VERDICT_UNKNOWN),
                    "message": (
                        f"Row for issue '{issue_ref}': verdict '{entry.get('verdict')}' is not in the allowed set: {[v.value for v in IssueMatrixVerdict]}"
                    ),
                }
            )
            continue

        if verdict is IssueMatrixVerdict.DEFERRED_WITH_FOLLOWUP:
            has_handle = bool(re.search(r"#\d+", evidence_ref)) or ("Follow-up:" in evidence_ref)
            if not has_handle:
                diagnostics.append(
                    {
                        "diagnostic_code": str(MissionReviewDiagnostic.ISSUE_MATRIX_DEFERRED_WITHOUT_HANDLE),
                        "message": (
                            f"Row for issue '{issue_ref}': verdict is 'deferred-with-followup' "
                            f"but evidence_ref contains no follow-up handle "
                            f"(expected '#NNN' or 'Follow-up:' substring); got: '{evidence_ref}'"
                        ),
                    }
                )

        rows.append(
            IssueMatrixRow(
                issue=str(issue_ref),
                verdict=verdict,
                evidence_ref=evidence_ref,
                title=entry.get("title"),
                scope=entry.get("scope"),
                wp=entry.get("wp"),
                fr=entry.get("fr"),
                nfr=entry.get("nfr"),
                sc=entry.get("sc"),
                repo=entry.get("repo"),
            )
        )
    return rows, diagnostics


def diagnose_structured_issue_matrix(json_path: Path) -> list[dict[str, str]]:
    """Business-rule diagnostics for ``issue-matrix.json`` (used by ``validate_issue_matrix``)."""
    _rows, diagnostics = _parse_structured_rows(json_path)
    return diagnostics


# ---------------------------------------------------------------------------
# T023 / M7 -- the ONE canonical dir-based reader
# ---------------------------------------------------------------------------


def load_issue_matrix(feature_dir: Path) -> list[IssueMatrixRow]:
    """Canonical dir-based issue-matrix reader (M7 / T023).

    Resolves ``feature_dir/issue-matrix.json`` first; when absent,
    failover-reads the legacy ``feature_dir/issue-matrix.md`` (FR-013).
    Returns ``[]`` when neither is present.

    ``feature_dir`` is whatever directory the CALLER has already resolved as
    the correct READ surface (the coordination worktree under coord /
    lanes-with-coord topology via :func:`mission_runtime.coord_read_dir_for`,
    or the primary ``feature_dir`` for coord-less topologies) -- this reader
    does not itself perform topology resolution (B-1: every live consumer
    already resolves its own read surface today; the bug this WP closes is
    that each one then hardcoded the ``.md`` FILENAME on top of that correct
    directory, so this function collapses only the ``.json``-then-``.md``
    filename fork, uniformly, in one place).
    """
    json_path = feature_dir / ISSUE_MATRIX_JSON_FILENAME
    if json_path.exists():
        rows, _diagnostics = _parse_structured_rows(json_path)
        return rows

    md_path = feature_dir / ISSUE_MATRIX_MD_FILENAME
    if md_path.exists():
        from specify_cli.cli.commands.review._issue_matrix import validate_issue_matrix

        legacy_rows: list[IssueMatrixRow] = validate_issue_matrix(md_path).rows
        return legacy_rows

    return []


def issue_matrix_artifact_present(feature_dir: Path) -> bool:
    """True when an issue-matrix artifact (either format) exists at ``feature_dir``.

    A dir-based EXISTENCE precheck -- distinct from :func:`load_issue_matrix`'s
    ROW-returning contract. A structurally malformed legacy ``.md`` (e.g. two
    tables) exists but parses to zero rows; a precheck gated on "has rows"
    would wrongly skip validating/linting it. Use this for "is there anything
    to look at" and :func:`load_issue_matrix` for "what does it say".
    """
    json_exists: bool = (feature_dir / ISSUE_MATRIX_JSON_FILENAME).exists()
    md_exists: bool = (feature_dir / ISSUE_MATRIX_MD_FILENAME).exists()
    return json_exists or md_exists


# ---------------------------------------------------------------------------
# T022 -- migrate-on-write
# ---------------------------------------------------------------------------


def migrate_issue_matrix_to_json(
    feature_dir: Path,
    *,
    repo_root: Path,
    mission_slug: str,
    policy: ProtectionPolicyLike,
    read_dir: Path | None = None,
    target_branch: str | None = None,
    actor: str = "issue-matrix-migrate",
) -> WriteSeamResult | None:
    """Migrate a legacy ``issue-matrix.md`` mission to structured JSON (FR-013).

    Reads the legacy matrix (failover-read), converts each row to
    :class:`~specify_cli.tasks.issue_matrix.IssueMatrixEntry`, and writes it
    via the canonical writer (:func:`~specify_cli.tasks.issue_matrix.
    write_issue_matrix`, ``write_target(ISSUE_MATRIX)``). The legacy ``.md``
    file is left in place (harmless historical residue; C-008 requires no NEW
    ``.md`` is ever emitted, not that an old one is deleted).

    ``read_dir`` (#4868): the authoritative READ surface for the legacy matrix.
    Under coord / lanes-with-coord topology the legacy ``.md`` lives on the
    coordination worktree, NOT the primary ``feature_dir`` -- the caller
    resolves that surface (via :func:`mission_runtime.coord_read_dir_for`) and
    threads it here so the existence check and the markdown parse read
    ``source_dir = read_dir or feature_dir``. The WRITE deliberately stays
    staged on the primary ``feature_dir`` (C-011): the write-seam materializes
    the coord copy and cleans the primary residue, so passing ``read_dir`` as
    the write ``feature_dir`` would break that residue-cleanup contract.
    ``read_dir`` is keyword-only and defaults to ``None`` (the pre-#4868
    behaviour: read and write both on ``feature_dir``), keeping every existing
    caller unaffected (NFR-006 back-compat).

    Returns ``None`` (nothing to migrate) when ``issue-matrix.json`` already
    exists on the read surface or no legacy ``.md`` is present there.

    Raises:
        IssueMatrixMigrationError: the legacy ``.md`` is structurally malformed
            and yields no usable rows -- migrating it would silently drop every
            existing verdict, so it fails loud instead (#4868).
    """
    source_dir = read_dir or feature_dir
    if (source_dir / ISSUE_MATRIX_JSON_FILENAME).exists():
        return None
    md_path = source_dir / ISSUE_MATRIX_MD_FILENAME
    if not md_path.exists():
        return None

    from specify_cli.cli.commands.review._issue_matrix import validate_issue_matrix

    validation = validate_issue_matrix(md_path)
    legacy_rows = validation.rows
    if not validation.passed and not legacy_rows:
        raise IssueMatrixMigrationError(
            f"legacy issue-matrix.md at {md_path} is malformed and yields no rows; refusing to migrate it to an empty (lossy) issue-matrix.json"
        )
    rows = {
        row.issue: IssueMatrixEntry(
            verdict=row.verdict.value,
            evidence_ref=row.evidence_ref,
            title=row.title,
            scope=row.scope,
            wp=row.wp,
            fr=row.fr,
            nfr=row.nfr,
            sc=row.sc,
            repo=row.repo,
        )
        for row in legacy_rows
    }
    return write_issue_matrix(
        repo_root=repo_root,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        rows=rows,
        policy=policy,
        actor=actor,
        target_branch=target_branch,
    )


# ---------------------------------------------------------------------------
# T022 -- bulk migration command (`spec-kitty issue-matrix migrate`)
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="issue-matrix",
    help="Issue-matrix commands (structured issue-matrix.json).",
    no_args_is_help=True,
)


def _iter_primary_mission_dirs(repo_root: Path) -> list[Path]:
    """Every ``kitty-specs/<slug>/`` directory that carries a ``meta.json``."""
    specs_root = repo_root / KITTY_SPECS_DIR
    if not specs_root.is_dir():
        return []
    return sorted(p for p in specs_root.iterdir() if p.is_dir() and (p / "meta.json").exists())


def _migrate_one_mission(feature_dir: Path, *, repo_root: Path, policy: ProtectionPolicyLike) -> tuple[str, bool]:
    """Attempt migration for a single mission dir; returns ``(mission_slug, migrated)``."""
    mission_slug = feature_dir.name
    try:
        result = migrate_issue_matrix_to_json(
            feature_dir,
            repo_root=repo_root,
            mission_slug=mission_slug,
            policy=policy,
        )
    except IssueMatrixMigrationError:
        # Bulk migration is best-effort: a malformed mission is skipped, never
        # aborts the sweep over its siblings (#4868).
        return mission_slug, False
    migrated = result is not None and result.status in ("committed", "unchanged")
    return mission_slug, migrated


@app.command("migrate")
def migrate_issue_matrix_cmd(
    mission: Annotated[
        str | None,
        typer.Option("--mission", help="Scope to a single mission handle. Omit to migrate all missions."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit structured JSON output.")] = False,
) -> None:
    """Bulk-migrate legacy ``issue-matrix.md`` missions to ``issue-matrix.json`` (FR-013)."""
    from specify_cli.core.paths import locate_project_root
    from specify_cli.git.protection_policy import ProtectionPolicy

    repo_root = locate_project_root()
    if repo_root is None:
        payload: dict[str, Any] = {"error": "Could not locate project root"}
        if json_output:
            console.print(json.dumps(payload))
        else:
            console.print("[red]Error:[/red] Could not locate project root")
        raise typer.Exit(1)

    policy = ProtectionPolicy.resolve(repo_root)

    if mission is not None:
        from specify_cli.cli.selector_resolution import resolve_mission_handle

        resolved = resolve_mission_handle(mission, repo_root, json_mode=json_output)
        mission_dirs = [resolved.feature_dir]
    else:
        mission_dirs = _iter_primary_mission_dirs(repo_root)

    migrated: list[str] = []
    skipped: list[str] = []
    for feature_dir in mission_dirs:
        mission_slug, was_migrated = _migrate_one_mission(feature_dir, repo_root=repo_root, policy=policy)
        (migrated if was_migrated else skipped).append(mission_slug)

    result_payload = {"ok": True, "migrated_missions": migrated, "skipped": skipped}
    if json_output:
        console.print(json.dumps(result_payload))
        return
    console.print(f"[green]Migrated {len(migrated)} mission(s)[/green]: {', '.join(migrated) or '(none)'}")
    console.print(f"[dim]Skipped {len(skipped)} mission(s)[/dim]: {', '.join(skipped) or '(none)'}")


# NOTE: ``migrate_issue_matrix_cmd`` is reachable via the ``@app.command``
# registration (``app`` is exported) and ``migrate_issue_matrix_to_json`` has
# no cross-module caller YET (WP07's issue-verdict command is a downstream
# WP) -- neither belongs in ``__all__`` per the symbol-level dead-code gate
# (tests/architectural/test_no_dead_symbols.py); both stay importable
# directly (as the tests here do), just not declared as the module's public
# surface.
__all__ = [
    "app",
    "diagnose_structured_issue_matrix",
    "issue_matrix_artifact_present",
    "load_issue_matrix",
]
