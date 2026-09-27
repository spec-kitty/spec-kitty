"""Issue-matrix approval rule: the terminal-verdict gating lever (#5222, F4).

Moved verbatim out of ``cli.commands.agent.tasks_parsing_validation`` (WP06's
#2058 CLI seam), which had grown a policy dependency
(``specify_cli.policy.merge_gates``) reaching UP into the CLI ``agent``
command tree for a rule that has nothing to do with CLI argument parsing --
the merge gate needed the SAME terminal-verdict rule ``move-task`` uses (reuse,
not re-implementation, per the sibling gate's own docstring), so it imported
a private CLI-layer name. This module gives the rule a domain home under
``specify_cli.tasks`` instead: ``policy.merge_gates`` now imports it from
here (a policy -> domain edge, not policy -> CLI), and
``tasks_parsing_validation.py`` re-exports every name verbatim so its own
callers (``tasks.py``, ``tasks_move_task.py``) are unaffected byte-for-byte.

Behaviour-preserving move only -- no logic changed. See
``tasks_parsing_validation.py``'s (much shorter) module docstring for the
seam this module was extracted from.
"""

from __future__ import annotations

import logging
from pathlib import Path
from kernel._safe_re import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.cli.commands.review._issue_matrix import (
        IssueMatrixValidationResult,
        IssueMatrixVerdict,
    )

from specify_cli.status import Lane

logger = logging.getLogger(__name__)

# Mirror of the constant defined in ``tasks``/``tasks_parsing_validation``.
# Hoisted as a module-local constant so this seam has no back-import.
SPEC_MD_FILENAME = "spec.md"

# S1192: the "ERROR: <artifact>" prefix and the "before approving" hint each
# recur across the approval-blocker error strings below -- hoisted so a 4th
# message does not reintroduce the duplication.
_FILL_VERDICTS_HINT = "before approving"

# #3951 (F-36): the remedy command for an unfilled verdict row. The
# approve-gate blocker previously said only "Fill in verdicts" without naming
# the command that does it, so orchestrating agents guessed at
# ``agent mission issue-verdict`` / ``agent tasks issue-verdict`` and hit
# "No such command". Shared by the two "Fill verdicts" blocker messages.
_ISSUE_VERDICT_REMEDY = (
    "Record a verdict per row with: spec-kitty agent issue-verdict --mission "
    "<handle> --issue <#NNN> --verdict "
    "<fixed|verified-already-fixed|deferred-with-followup|in-mission|not-applicable> "
    "--actor <actor> [--wp <WPnn>] [--evidence-ref <evidence>]"
)


def _issue_matrix_error_prefix(feature_dir: Path) -> str:
    """``"ERROR: <actual-artifact>"`` for the approve-gate messages (#4330).

    Names the artifact the gate actually reads, mirroring the canonical
    dir-based reader's JSON-first resolution (:func:`load_issue_matrix`):
    ``issue-matrix.json`` when one exists, else the legacy
    ``issue-matrix.md``. When NEITHER exists the canonical, scaffolded
    artifact is named (``issue-matrix.json`` — C-008: no new ``.md`` is ever
    emitted), which is also what the regenerate hint in the missing-artifact
    message tells the operator to produce. The old hardcoded
    ``issue-matrix.md`` prefix reported the wrong filename for every
    JSON-format mission.
    """
    from specify_cli.tasks.issue_matrix import (
        ISSUE_MATRIX_JSON_FILENAME,
        ISSUE_MATRIX_MD_FILENAME,
    )

    if (feature_dir / ISSUE_MATRIX_MD_FILENAME).exists() and not (feature_dir / ISSUE_MATRIX_JSON_FILENAME).exists():
        return f"ERROR: {ISSUE_MATRIX_MD_FILENAME}"
    return f"ERROR: {ISSUE_MATRIX_JSON_FILENAME}"


def _issue_matrix_evaluation(
    feature_dir: Path,
    *,
    spec_feature_dir: Path | None = None,
    matrix_content: str | None = None,
) -> tuple[IssueMatrixValidationResult, set[str], list[str], list[str]]:
    """Evaluate the issue-matrix against discovered gating references.

    ``matrix_content`` (MAJOR-1, issue-matrix-partition-integrity-01M3H10A
    WP04): an OPTIONAL coordination-ref content source (the WP02 shared
    helper's post-consolidation arm,
    :func:`~mission_runtime.issue_matrix_partition.resolve_issue_matrix_partition`),
    for the case where the matrix has no on-disk worktree to read. When
    supplied, it is validated DIRECTLY as structured content and
    ``feature_dir`` is never touched for the matrix read (``validate_issue_matrix``'s
    existing content-source arm, IC-01b/T008). ``None`` (the default)
    preserves the historical dir-based read byte-for-byte, so the existing
    ``move-task`` caller (which never passes this kwarg) is unaffected.
    """
    from specify_cli.cli.commands.review._issue_matrix import (
        IssueMatrixVerdict,
        validate_issue_matrix,
    )
    from specify_cli.tasks.issue_reference_discovery import (
        discover_issue_references,
        is_gating,
    )

    # WP08 T029/FR-004: discovery scans every PRIMARY-partition mission
    # artifact (spec.md, plan.md, research.md, analysis-report.md,
    # tasks/*.md, contracts/*.md) under the resolved primary dir, not
    # spec.md alone.
    refs = discover_issue_references(spec_feature_dir or feature_dir)
    result = validate_issue_matrix(feature_dir / "issue-matrix.md", content=matrix_content)
    # FR-012/FR-013 (move-task-approval-ergonomics-01M302R0 WP02, #3469):
    # classification decides row-REQUIREMENT -- only the WP01 classifier's
    # ``implementation_target`` references ever require an issue-matrix row.
    # ``context_only``/``pr_or_commit_ref`` references are cited but owed no
    # work, so they never contribute to "missing" or "unresolved in-mission".
    referenced_issues = {f"#{ref.number}" for ref in refs if is_gating(ref)}
    matrix_issues = _issue_matrix_row_issues(result)
    unresolved_in_mission = _issue_matrix_in_mission_rows(
        result,
        referenced_issues,
        IssueMatrixVerdict.IN_MISSION,
    )
    missing_issues = sorted(referenced_issues - matrix_issues)
    return result, referenced_issues, missing_issues, unresolved_in_mission


def _issue_matrix_row_issues(result: IssueMatrixValidationResult) -> set[str]:
    matrix_issues = {row.issue for row in result.rows}
    for diagnostic in result.diagnostics:
        match = re.search(r"Row for issue '([^']+)'", diagnostic.get("message", ""))
        if match:
            matrix_issues.add(match.group(1))
    return matrix_issues


def _issue_matrix_in_mission_rows(
    result: IssueMatrixValidationResult,
    referenced_issues: set[str],
    in_mission_verdict: IssueMatrixVerdict,
) -> list[str]:
    return sorted(row.issue for row in result.rows if row.verdict is in_mission_verdict and row.issue in referenced_issues)


def _issue_matrix_diagnostic_lines(result: IssueMatrixValidationResult) -> list[str]:
    """Render every diagnostic as a surfaced message line (#4330).

    Each validator diagnostic already names the failing row and the concrete
    rule it broke (e.g. ``Row for issue '#1582': verdict is
    'deferred-with-followup' but evidence_ref contains no follow-up handle
    (expected '#NNN' or 'Follow-up:' substring)``), so each is passed through
    verbatim — the old VERDICT_UNKNOWN reduction to a bare ``Unknown: #NNN``
    id list is exactly the per-row-cause masking #4330 files. FR-007
    (#2555.5): a ``ISSUE_MATRIX_SCHEMA_DRIFT`` diagnostic (e.g. a mandatory
    column spelled non-canonically) carries a ``detail`` payload naming the
    found/normalized columns; appending it lets the approval blocker name the
    offending column instead of leaving the caller to infer schema drift from
    an all-issues "Missing rows" list.
    """
    from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic

    messages: list[str] = []
    for diagnostic in result.diagnostics:
        message = diagnostic.get("message", "")
        code = diagnostic.get("diagnostic_code")
        if code == str(MissionReviewDiagnostic.ISSUE_MATRIX_SCHEMA_DRIFT):
            detail = diagnostic.get("detail")
            messages.append(f"{message} ({detail})" if detail else message)
        else:
            messages.append(message)
    return messages


def _issue_matrix_approval_blocker(
    feature_dir: Path,
    *,
    target_lane: Lane | None = None,
    primary_feature_dir: Path | None = None,
    matrix_content: str | None = None,
) -> str | None:
    """Return a blocking message when referenced issues still lack final verdicts.

    ``target_lane`` controls how the non-terminal ``in-mission`` verdict is
    treated. At ``approved`` (or when unspecified) an ``in-mission`` row is
    acceptable — the issue is being closed by a later WP in this same mission,
    so a dependency chain is not blocked on its own downstream work. At ``done``
    (mission merge/acceptance) ``in-mission`` is rejected: every issue must have
    reached a terminal verdict (``fixed`` / ``verified-already-fixed`` /
    ``deferred-with-followup`` / ``not-applicable``) before the mission lands.

    Lever SSOT (FR-013, move-task-approval-ergonomics-01M302R0 WP02, #3469):
    classification decides whether a row is REQUIRED, verdict decides whether
    an existing row is RESOLVED. Only a reference the WP01 classifier
    (:mod:`specify_cli.tasks.issue_reference_discovery`) calls
    ``implementation_target`` ever requires a row at all — a mission that
    references only ``context_only``/``pr_or_commit_ref`` issues needs no
    issue-matrix artifact, let alone a row, and is never blocked here. Once a
    row exists, ``not-applicable`` is the mirror image of ``in-mission``: it
    is non-gating at ``approved`` (nothing special needed — it simply is not
    added to ``unresolved_in_mission``) AND terminal at ``done`` (unlike
    ``in-mission``, it never re-blocks at merge).

    Placement (coord-commit-integrity SURFACE A #1c): ``issue-matrix.md`` is a
    COORD-partition kind, so the matrix is read from ``feature_dir`` — the
    caller's topology-resolved read surface (the coordination worktree under
    coord / lanes-with-coord topology; the primary dir when coord-less). There is
    NO PRIMARY fallback: a PRIMARY fallback for a COORD kind was the split-brain
    anti-pattern (a stale primary copy silently satisfying a stale/unfilled coord
    matrix). ``primary_feature_dir`` is consulted ONLY for discovery (WP08
    T029/FR-004: spec.md, plan.md, research.md, analysis-report.md,
    tasks/*.md, contracts/*.md — all genuine PRIMARY-partition kinds) — to
    detect the referenced issues.

    ``matrix_content`` (MAJOR-1, issue-matrix-partition-integrity-01M3H10A
    WP04): an OPTIONAL coordination-ref content source (the WP02 shared
    helper's post-consolidation arm, threaded through
    :func:`issue_matrix_artifact_present` and :func:`_issue_matrix_evaluation`)
    for the case where the coord matrix has no on-disk worktree at all —
    ``feature_dir`` then serves only as a label for the error-prefix message,
    never touched on disk. Defaults to ``None``, which preserves the
    historical dir-based read byte-for-byte, so the existing ``move-task``
    caller (:func:`~specify_cli.cli.commands.agent.tasks_move_task`, which
    never passes this kwarg) is unaffected.
    """
    spec_feature_dir = primary_feature_dir if primary_feature_dir is not None and (primary_feature_dir / SPEC_MD_FILENAME).exists() else feature_dir

    try:
        from specify_cli.tasks.issue_reference_discovery import (
            discover_issue_references,
            is_gating,
        )

        refs = discover_issue_references(spec_feature_dir)
    except Exception as exc:  # noqa: BLE001 -- approval guard must fail closed
        logger.debug("Could not evaluate issue-matrix approval blocker: %s", exc)
        return (
            f"{_issue_matrix_error_prefix(feature_dir)} could not be evaluated before approval.\nReason: {exc}\nFix the issue-matrix check {_FILL_VERDICTS_HINT}."
        )

    # FR-013 lever SSOT (move-task-approval-ergonomics-01M302R0 WP02, #3469):
    # classification decides row-REQUIREMENT -- only a reference the WP01
    # classifier calls ``implementation_target`` ever requires an
    # issue-matrix row or artifact. A mission that references ONLY
    # ``context_only``/``pr_or_commit_ref`` issues needs no matrix at all.
    gating_refs = [ref for ref in refs if is_gating(ref)]
    if not gating_refs:
        return None

    # T043 (C-008 / B-1 fix): presence is a dir-based check
    # (:func:`issue_matrix_artifact_present`), not a ``.md``-only
    # ``.exists()`` — the prior precheck made a JSON-only mission (B3) hard-
    # fail approval before ``_issue_matrix_evaluation`` (which already
    # resolves JSON-first via WP05's canonical dir-based reader,
    # :func:`~specify_cli.tasks.issue_matrix_migration.load_issue_matrix`)
    # ever ran.
    from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

    if not issue_matrix_artifact_present(feature_dir, content=matrix_content):
        issue_list = ", ".join(f"#{ref.number}" for ref in gating_refs)
        return (
            f"{_issue_matrix_error_prefix(feature_dir)} is required before approval.\n"
            f"Referenced issues: {issue_list}\n"
            f"Fill verdicts {_FILL_VERDICTS_HINT}.\n"
            f"This file is normally scaffolded automatically. If it is missing, "
            f"regenerate it: spec-kitty agent mission finalize-tasks --mission {feature_dir.name}\n"
            f"{_ISSUE_VERDICT_REMEDY}\n"
            f"Schema and worked example: src/specify_cli/cli/commands/review/ERROR_CODES.md"
        )

    result, _, missing_issues, unresolved_in_mission = _issue_matrix_evaluation(
        feature_dir,
        spec_feature_dir=spec_feature_dir,
        matrix_content=matrix_content,
    )
    if target_lane != Lane.DONE:
        unresolved_in_mission = []

    if result.passed and not missing_issues and not unresolved_in_mission:
        return None

    # #4330: every diagnostic line already carries the failing row + the
    # concrete rule it broke, so they are surfaced FIRST, directly under the
    # header that names the actual artifact — no bare-id reduction between
    # the operator and the per-row cause.
    diagnostic_lines = _issue_matrix_diagnostic_lines(result)

    lines = [f"{_issue_matrix_error_prefix(feature_dir)} has unresolved entries. Fill in verdicts {_FILL_VERDICTS_HINT}."]
    for message in diagnostic_lines:
        lines.append(f"- {message}")
    # FR-007 (#2555.5): only claim rows are "missing" when rows were actually
    # parsed. A malformed mandatory column (schema drift) makes the parser
    # bail out with zero rows, at which point every referenced issue looks
    # "missing" even though the real problem is the header — that signal is
    # already surfaced via ``diagnostic_lines`` (schema-drift detail) above.
    if missing_issues and result.rows:
        lines.append(f"Missing rows: {', '.join(missing_issues)}")
    if unresolved_in_mission:
        lines.append(f"Still 'in-mission' (resolve to fixed / verified-already-fixed / deferred-with-followup before done): {', '.join(unresolved_in_mission)}")
    lines.append(_ISSUE_VERDICT_REMEDY)
    return "\n".join(lines)


__all__ = [
    "SPEC_MD_FILENAME",
    "_issue_matrix_approval_blocker",
    "_issue_matrix_diagnostic_lines",
    "_issue_matrix_error_prefix",
    "_issue_matrix_evaluation",
    "_issue_matrix_in_mission_rows",
    "_issue_matrix_row_issues",
]
