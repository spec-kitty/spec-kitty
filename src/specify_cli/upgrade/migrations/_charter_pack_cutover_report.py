"""The charter-pack cutover migration's report and its ``MigrationResult`` mapping (#3732).

Contract: ``kitty-specs/charter-pack-cutover-01M491G6/contracts/upgrade-migration.md``.

Report dict shape (``json.dumps(..., sort_keys=True)`` in ``changes_made[0]``;
``spec-kitty upgrade --json`` decodes it into
``migration_reports["charter_pack_cutover"]``). Every key is always present and
holds an ordered list of strings, one line per item:

==================  ===========================================================
``moved``           project-layer files moved to the project pack root
``rewritten``       config keys and path references rewritten (file and key)
``reset``           stale lists, stale kind gates and ``[]`` reset to absent
``kept_for_review`` customised or near-miss lists and unconvertible entries kept
``matches_minimal`` lists equal to the released ``minimal`` preset, kept
``skills_removed``  installed copies of removed skills deleted
``skills_kept``     edited skill copies kept
``errors``          refusals (collision paths, locked files)
==================  ===========================================================

``MigrationResult`` mapping: ``changes_made`` = the JSON report, then one human
line per moved / rewritten / reset item; ``warnings`` = kept-for-review,
``minimal``-equal and edited-skill lines plus :attr:`CutoverReport.restore_hints`
(the per-key "set it back to ``[]``" lines WP12 adds for every reset ``[]``);
``manual_review_required = bool(warnings)``; ``preserved_paths`` = edited skill
copies; ``success = not errors``. In a dry run every human line starts with
``Would`` and nothing is written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .base import MigrationResult

__all__ = ["CutoverReport"]

#: The report keys, in contract order.
_REPORT_KEYS: tuple[str, ...] = (
    "moved",
    "rewritten",
    "reset",
    "kept_for_review",
    "matches_minimal",
    "skills_removed",
    "skills_kept",
    "errors",
)

#: The report keys whose lines mean the project still needs (or refuses) the cutover.
_ACTIONABLE_KEYS: tuple[str, ...] = ("moved", "rewritten", "reset", "skills_removed", "errors")

#: (report key, human verb, dry-run verb) for the lines that go to ``changes_made``.
_CHANGE_VERBS: tuple[tuple[str, str, str], ...] = (
    ("moved", "Moved", "Would move"),
    ("rewritten", "Rewrote", "Would rewrite"),
    ("reset", "Reset", "Would reset"),
    ("skills_removed", "Removed skill", "Would remove skill"),
)
#: (report key, human prefix, dry-run prefix) for the lines that go to ``warnings``.
_WARNING_PREFIXES: tuple[tuple[str, str, str], ...] = (
    ("kept_for_review", "Kept for review", "Would keep for review"),
    ("matches_minimal", "Matches preset minimal, kept", "Would keep (matches preset minimal)"),
    ("skills_kept", "Kept edited skill copy", "Would keep edited skill copy"),
)


@dataclass
class CutoverReport:
    """Ordered result lines of one cutover run (see the module docstring)."""

    moved: list[str] = field(default_factory=list)
    rewritten: list[str] = field(default_factory=list)
    reset: list[str] = field(default_factory=list)
    kept_for_review: list[str] = field(default_factory=list)
    matches_minimal: list[str] = field(default_factory=list)
    skills_removed: list[str] = field(default_factory=list)
    skills_kept: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    #: Warning-only lines (not a report key): how to restore each reset ``[]`` (WP12).
    restore_hints: list[str] = field(default_factory=list)
    #: Edited skill copies kept in place (``MigrationResult.preserved_paths``).
    preserved_paths: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        """The contract report: every :data:`_REPORT_KEYS` key, each an ordered list."""
        return {key: list(getattr(self, key)) for key in _REPORT_KEYS}

    def is_actionable(self) -> bool:
        """True when the run would change the project or refuses (kept lines alone are not)."""
        return any(getattr(self, key) for key in _ACTIONABLE_KEYS)

    def to_migration_result(self, *, dry_run: bool) -> MigrationResult:
        """Map the report onto a :class:`MigrationResult` (contract mapping)."""
        changes = [json.dumps(self.as_dict(), sort_keys=True)]
        for key, verb, dry_verb in _CHANGE_VERBS:
            prefix = dry_verb if dry_run else verb
            changes.extend(f"{prefix} {line}" for line in getattr(self, key))
        warnings: list[str] = []
        for key, label, dry_label in _WARNING_PREFIXES:
            prefix = dry_label if dry_run else label
            warnings.extend(f"{prefix}: {line}" for line in getattr(self, key))
        warnings.extend(self.restore_hints)
        return MigrationResult(
            success=not self.errors,
            changes_made=changes,
            errors=list(self.errors),
            warnings=warnings,
            manual_review_required=bool(warnings),
            preserved_paths=list(self.preserved_paths),
        )
