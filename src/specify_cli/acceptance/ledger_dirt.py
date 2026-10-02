"""Uncommitted decision-ledger dirt is accept's to commit (FR-009b, operator decision G1).

``accept`` is a committer of the Mission's PRIMARY decision ledger
(``plan.scope.ledger-committers``: ``spec-commit`` and ``accept`` only). A decision
opened after the last ``spec-commit`` leaves ``decisions/index.json`` modified and a
new ``decisions/DM-*.md`` untracked. Two consumers must agree on exactly those paths:

* the accept dirty gate must NOT treat them as blocking dirt, and
* the residual acceptance commit must pick them up -- including the untracked
  ``DM-*.md``, which the tracked-only residual scan would otherwise skip.

Both ask :func:`mission_decision_ledger_files`, which classifies with the mission
artifact taxonomy (``MissionArtifactKind.DECISION_LEDGER``) scoped to the CURRENT
Mission. Another Mission's ledger, and every non-ledger path, is not matched and
still blocks (fail-closed, NFR-003).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kernel.git import StatusEntry
from kernel.paths import to_posix


def _expand_entry(entry: StatusEntry, repo_root: Path) -> list[str]:
    """Return the file paths a status entry names (a collapsed ``?? dir/`` expands to its files)."""
    path = str(entry.path)
    if not entry.is_directory:
        return [path]
    directory = repo_root / path
    if not directory.is_dir():
        return []
    return sorted(to_posix(item.relative_to(repo_root)) for item in directory.rglob("*") if item.is_file())


def _is_ledger_file(path: str, mission_slug: str) -> bool:
    from mission_runtime import MissionArtifactKind, kind_for_mission_file

    return kind_for_mission_file(path, mission_slug=mission_slug) is MissionArtifactKind.DECISION_LEDGER


def is_mission_decision_ledger_entry(entry: StatusEntry, *, repo_root: Path, mission_slug: str) -> bool:
    """True when the status *entry* names only the current Mission's decision-ledger files."""
    files = _expand_entry(entry, repo_root)
    return bool(files) and all(_is_ledger_file(path, mission_slug) for path in files)


def mission_decision_ledger_files(entries: Iterable[StatusEntry], *, repo_root: Path, mission_slug: str) -> list[str]:
    """Repo-relative decision-ledger files of the current Mission that are dirty (modified or untracked)."""
    found: list[str] = []
    for entry in entries:
        for path in _expand_entry(entry, repo_root):
            if _is_ledger_file(path, mission_slug) and path not in found:
                found.append(path)
    return found
