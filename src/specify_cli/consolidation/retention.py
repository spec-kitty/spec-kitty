"""Mission retention-contract enforcement for merge cleanup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mission_runtime import MissionArtifactKind, placement_seam

MISSION_RETENTION_CLEANUP_CONFLICT = "MISSION_RETENTION_CLEANUP_CONFLICT"
_CONSTRAINT_ROW_ID = re.compile(r"^C-\d+$", re.IGNORECASE)
_NEGATED_RETENTION = re.compile(
    r"\b(?:do not|must not|never)\b[^.;\n]*\b(?:keep|retain|preserve)\b",
    re.IGNORECASE,
)
_NEGATED_DELETION = re.compile(
    r"\b(?:do not|must not|never)\b[^.;\n]*\b(?:delete|remove)\b",
    re.IGNORECASE,
)
_RETENTION_VERB = re.compile(r"\b(?:keep|retain|preserve)\b", re.IGNORECASE)
_MERGE_TIMING = re.compile(
    r"\b(?:after merge|after merging|post-merge)\b",
    re.IGNORECASE,
)
_BRANCH = re.compile(r"\bbranch(?:es)?\b", re.IGNORECASE)
_WORKTREE = re.compile(r"\bwork[- ]?trees?\b", re.IGNORECASE)
_ABBREVIATION = re.compile(r"\b(?:e\.g|i\.e|etc)\.", re.IGNORECASE)
_SENTENCE_BOUNDARY = re.compile(r"[.;!?]")
_TERMINAL_STATUSES = frozenset({"accepted", "approved", "confirmed", "binding", "locked"})


@dataclass(frozen=True)
class MissionRetention:
    """A terminal mission constraint that retains merge cleanup artifacts."""

    constraint_id: str
    constraint: str
    retains_branch: bool
    retains_worktree: bool


def load_mission_retention(repo_root: Path, mission_slug: str) -> MissionRetention | None:
    """Read the mission's canonical spec and return its retained artifacts.

    Only a terminal constraint row can retain cleanup artifacts. Terminal
    status values are Accepted, Approved, Confirmed, Binding, and Locked.
    Returning ``None`` means either no spec exists or no terminal retention
    constraint is present; both retain the historical cleanup defaults.
    """

    spec_path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.SPEC) / "spec.md"
    if not spec_path.is_file():
        return None

    constraint_id: str | None = None
    constraint: str | None = None
    retains_branch = False
    retains_worktree = False
    for row in spec_path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        if not _CONSTRAINT_ROW_ID.fullmatch(cells[0]):
            continue
        if cells[-1].casefold() not in _TERMINAL_STATUSES:
            continue
        row_retains_branch, row_retains_worktree = _retained_artifacts(cells[2])
        if not (row_retains_branch or row_retains_worktree):
            continue
        if constraint_id is None:
            constraint_id = cells[0]
            constraint = cells[2]
        retains_branch = retains_branch or row_retains_branch
        retains_worktree = retains_worktree or row_retains_worktree

    if constraint_id is None or constraint is None:
        return None
    return MissionRetention(
        constraint_id=constraint_id,
        constraint=constraint,
        retains_branch=retains_branch,
        retains_worktree=retains_worktree,
    )


def _retained_artifacts(constraint: str) -> tuple[bool, bool]:
    """Return branch and worktree retention from each artifact-specific clause.

    A trailing merge-timing phrase governs every joined clause in its sentence.
    This preserves the branch gate in constraints such as ``Keep branches and
    delete worktrees after merge`` without applying timing across a distinct
    sentence.
    """

    branch_retentions: list[bool] = []
    worktree_retentions: list[bool] = []
    without_abbreviation_periods = _ABBREVIATION.sub(
        lambda match: match.group(0).replace(".", ""),
        constraint,
    )
    for sentence in _SENTENCE_BOUNDARY.split(without_abbreviation_periods):
        if not _MERGE_TIMING.search(sentence):
            continue
        clauses = re.split(
            r"\bbut\b|\band\s+(?=(?:delete|remove)\b)",
            sentence,
            flags=re.IGNORECASE,
        )
        for clause in clauses:
            negated_retention = _NEGATED_RETENTION.search(clause)
            deletion_prohibition = _NEGATED_DELETION.search(clause)
            affirmative_retention = _RETENTION_VERB.search(clause) is not None and not negated_retention
            retains = affirmative_retention or deletion_prohibition is not None

            if _BRANCH.search(clause):
                branch_retentions.append(retains)
            if _WORKTREE.search(clause):
                worktree_retentions.append(retains)

    return any(branch_retentions), any(worktree_retentions)


def retention_cleanup_conflicts(
    retention: MissionRetention | None,
    *,
    delete_branch: bool | None,
    remove_worktree: bool | None,
) -> tuple[str, ...]:
    """Return cleanup fields whose default value conflicts with retention.

    ``None`` means the operator omitted the bidirectional flag. An explicit
    ``--keep-*`` choice honors retention; an explicit ``--delete-branch`` or
    ``--remove-worktree`` choice is the separately directed override allowed by
    the mission constraint.
    """

    conflicts: list[str] = []
    if retention is not None and retention.retains_branch and delete_branch is None:
        conflicts.append("branch")
    if retention is not None and retention.retains_worktree and remove_worktree is None:
        conflicts.append("worktree")
    return tuple(conflicts)
