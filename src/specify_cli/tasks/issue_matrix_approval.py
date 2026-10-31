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

The move itself was behaviour-preserving. See
``tasks_parsing_validation.py``'s (much shorter) module docstring for the
seam this module was extracted from. #6653 later changed the ``done`` rule:
every ``in-mission`` row blocks, cited or not, and a present matrix is judged
whole even with zero gating references (ADR
``docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md``).
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
# #6653: at ``done`` the work package is already approved, so the unresolved-entries
# header names the lane the blocker is guarding.
_FILL_VERDICTS_BEFORE_DONE_HINT = "before done"

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
    """Every row whose verdict is ``in-mission``, cited or not (#6653, FR-001).

    Classification decides whether a row is REQUIRED; the verdict decides
    whether an existing row is RESOLVED. An ``in-mission`` row says the
    Mission still owes a fix, so it is unresolved whether or not its issue is
    a discovered gating reference. ``referenced_issues`` no longer filters:
    it only orders the output (cited rows first, then uncited, each sorted),
    and the parameter stays for the compat signature (C-003). Only the
    ``done`` leg consumes this list; the blocker zeroes it for every other
    target lane (C-001).
    """
    in_mission = [row.issue for row in result.rows if row.verdict is in_mission_verdict]
    return sorted(in_mission, key=lambda issue: (issue not in referenced_issues, issue))


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


def _issue_matrix_present(feature_dir: Path, matrix_content: str | None) -> bool:
    """Whether an issue-matrix artifact exists on the read surface.

    T043 (C-008 / B-1 fix): presence is a dir-based check
    (:func:`~specify_cli.tasks.issue_matrix_migration.issue_matrix_artifact_present`),
    not a ``.md``-only ``.exists()`` — the prior precheck made a JSON-only
    mission (B3) hard-fail approval before :func:`_issue_matrix_evaluation`
    (which already resolves JSON-first via WP05's canonical dir-based reader)
    ever ran. ``matrix_content`` is the coordination-ref content source.
    """
    from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

    return issue_matrix_artifact_present(feature_dir, content=matrix_content)


def _missing_issue_matrix_message(feature_dir: Path, issue_list: list[str]) -> str:
    """The "matrix required" blocker for gating references with no matrix."""
    return (
        f"{_issue_matrix_error_prefix(feature_dir)} is required before approval.\n"
        f"Referenced issues: {', '.join(issue_list)}\n"
        f"Fill verdicts {_FILL_VERDICTS_HINT}.\n"
        f"This file is normally scaffolded automatically. If it is missing, "
        f"regenerate it: spec-kitty agent mission finalize-tasks --mission {feature_dir.name}\n"
        f"{_ISSUE_VERDICT_REMEDY}\n"
        f"Schema and worked example: src/specify_cli/cli/commands/review/ERROR_CODES.md"
    )


def terminal_issue_verdicts() -> frozenset[str]:
    """The TERMINAL ``issue-matrix.json`` verdicts (the ``done``-gate vocabulary).

    One authority for "a row whose verdict is settled": every
    :class:`~specify_cli.cli.commands.review._issue_matrix.IssueMatrixVerdict` member except the
    documented non-terminal ``in-mission``. The scaffold placeholder ``unknown`` is not a member at
    all and is therefore non-terminal too -- exactly the pair the
    ``issue_matrix_verdict_terminality`` gate calls "unresolved".

    It lives here, beside the terminality rule itself, because the CONSUMERS are domain-side: the
    policy gate above and the consolidation late-teardown projection, which may not import the CLI
    command layer. The enum's own import stays function-local, like every other read of it in this
    module (#5222 F4: policy -> domain, not policy -> CLI).
    """
    from specify_cli.cli.commands.review._issue_matrix import IssueMatrixVerdict

    return frozenset(member.value for member in IssueMatrixVerdict if member is not IssueMatrixVerdict.IN_MISSION)


def issue_matrix_done_outcome(
    feature_dir: Path,
    *,
    primary_feature_dir: Path | None = None,
    matrix_content: str | None = None,
) -> tuple[str | None, int | None]:
    """The ``done`` verdict of the issue-matrix: ``(blocker, judged_rows)`` (#6711).

    The one authority the terminality merge gate asks. ``blocker`` is the
    refusal, exactly as :func:`_issue_matrix_approval_blocker` returns it at
    ``Lane.DONE``. ``judged_rows`` is the number of rows that one evaluation
    judged, or ``None`` when no matrix exists. ``matrix_content=""`` means the
    coordination ref was read and holds no matrix
    (``IssueMatrixRefReadError.NOT_AUTHORED``): zero gating references then
    mean nothing to enforce, and gating references get the "matrix required"
    refusal, both decided here rather than by the caller.
    """
    return _issue_matrix_blocker_outcome(
        feature_dir,
        target_lane=Lane.DONE,
        primary_feature_dir=primary_feature_dir,
        # Empty content reads as an absent artifact (issue_matrix_artifact_present).
        matrix_content=matrix_content,
    )


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

    #6653 (FR-001/FR-002): at ``done`` the VERDICT decides resolution for
    every existing row, cited or not -- an uncited (or ``context_only``)
    ``in-mission`` row blocks. With zero gating references a PRESENT matrix
    is still judged whole at ``done`` (row diagnostics and ``in-mission``
    rows); a MISSING matrix is nothing to enforce. ``approved`` is unchanged
    (C-001), and only gating references ever make a row "missing" (C-002).

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
    blocker, _judged_rows = _issue_matrix_blocker_outcome(
        feature_dir,
        target_lane=target_lane,
        primary_feature_dir=primary_feature_dir,
        matrix_content=matrix_content,
    )
    return blocker


def _issue_matrix_blocker_outcome(
    feature_dir: Path,
    *,
    target_lane: Lane | None,
    primary_feature_dir: Path | None,
    matrix_content: str | None,
) -> tuple[str | None, int | None]:
    """``(blocker, judged_rows)`` from one evaluation; see :func:`_issue_matrix_approval_blocker`."""
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
            f"{_issue_matrix_error_prefix(feature_dir)} could not be evaluated before approval.\nReason: {exc}\nFix the issue-matrix check {_FILL_VERDICTS_HINT}.",
            None,
        )

    # FR-013 lever SSOT (move-task-approval-ergonomics-01M302R0 WP02, #3469):
    # classification decides row-REQUIREMENT -- only a reference the WP01
    # classifier calls ``implementation_target`` ever requires an
    # issue-matrix row or artifact. A mission that references ONLY
    # ``context_only``/``pr_or_commit_ref`` issues needs no matrix at all.
    gating_refs = [ref for ref in refs if is_gating(ref)]
    if not gating_refs:
        # #6653 (FR-002/FR-003, C-001): with zero gating references nothing
        # REQUIRES a matrix. At ``approved`` (or an unspecified lane) that is
        # the end of it, byte-identical to before. At ``done`` a PRESENT
        # matrix is still judged whole (diagnostics and ``in-mission`` rows);
        # a missing one is nothing to enforce.
        if target_lane != Lane.DONE or not _issue_matrix_present(feature_dir, matrix_content):
            return None, None
    elif not _issue_matrix_present(feature_dir, matrix_content):
        return _missing_issue_matrix_message(feature_dir, [f"#{ref.number}" for ref in gating_refs]), None

    result, _, missing_issues, unresolved_in_mission = _issue_matrix_evaluation(
        feature_dir,
        spec_feature_dir=spec_feature_dir,
        matrix_content=matrix_content,
    )
    if target_lane != Lane.DONE:
        unresolved_in_mission = []

    judged_rows = len(result.rows)
    if result.passed and not missing_issues and not unresolved_in_mission:
        return None, judged_rows

    # #4330: every diagnostic line already carries the failing row + the
    # concrete rule it broke, so they are surfaced FIRST, directly under the
    # header that names the actual artifact — no bare-id reduction between
    # the operator and the per-row cause.
    diagnostic_lines = _issue_matrix_diagnostic_lines(result)

    hint = _FILL_VERDICTS_BEFORE_DONE_HINT if target_lane == Lane.DONE else _FILL_VERDICTS_HINT
    lines = [f"{_issue_matrix_error_prefix(feature_dir)} has unresolved entries. Fill in verdicts {hint}."]
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
        lines.append(
            "Still 'in-mission' (resolve to fixed / verified-already-fixed / deferred-with-followup before done, "
            f"or not-applicable when this Mission owes the issue no work): {', '.join(unresolved_in_mission)}"
        )
    lines.append(_ISSUE_VERDICT_REMEDY)
    return "\n".join(lines), judged_rows


__all__ = [
    "SPEC_MD_FILENAME",
    "issue_matrix_done_outcome",
    "_issue_matrix_approval_blocker",
    "_issue_matrix_diagnostic_lines",
    "_issue_matrix_error_prefix",
    "_issue_matrix_evaluation",
    "_issue_matrix_in_mission_rows",
    "_issue_matrix_row_issues",
]
