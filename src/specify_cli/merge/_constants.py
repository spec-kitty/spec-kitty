"""Shared constants, type aliases, and the module logger for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-02 / WP02.

Every literal, type alias, and the logger that the relocated merge seams share
lives here so later seam modules import them from a single home instead of
re-declaring them (S1192-safe). The values are moved byte-for-byte from the
pre-refactor ``cli/commands/merge.py``; the shim re-exports them so the public
``__all__`` and every importer stay byte-stable (FR-003, C-008, INV-8).
"""

from __future__ import annotations

import logging

# The logger is bound to the historical command-module name so log records keep
# their pre-refactor namespace (``specify_cli.cli.commands.merge``) regardless of
# which seam module emits them. This preserves operator-facing log behavior
# byte-for-byte (NFR-003): existing log filters / handlers keyed on that name
# continue to match.
logger = logging.getLogger("specify_cli.cli.commands.merge")

# Target-branch sync preflight diagnostic codes (issue #017 family).
TARGET_BRANCH_NOT_SYNCHRONIZED = "TARGET_BRANCH_NOT_SYNCHRONIZED"
TARGET_BRANCH_SYNC_INVARIANT = "local_target_branch_must_match_tracking_branch"

# Squash integration would clobber newer target-branch content (#4892). Shared
# by the dry-run forecast and the real mission→target merge so both emit the
# SAME diagnostic code and remediation, not divergent prose.
TARGET_BRANCH_CONTENT_CONFLICT = "TARGET_BRANCH_CONTENT_CONFLICT"

# Canonical status-surface filenames.
_STATUS_EVENTS_FILENAME = "status.events.jsonl"
_STATUS_FILENAME = "status.json"

# Mission-slug path-segment guard diagnostic prefix.
_SAFE_PATH_SEGMENT_DIAGNOSTIC = "Mission slug is not a single safe path segment"

# T011 — FR-009: push-error parser tokens (locked tuple — do not reorder or
# extend without a spec change). INV-8 freezes this tuple's order and membership.
LINEAR_HISTORY_REJECTION_TOKENS: tuple[str, ...] = (
    "merge commits",
    "linear history",
    "fast-forward only",
    "GH006",
    "non-fast-forward",
)

# Shared structural type aliases for merge payloads.
MissionBranchBlocker = dict[str, str | bool]
HollowReviewWarnings = dict[str, list[str]]

__all__ = [
    "logger",
    "TARGET_BRANCH_NOT_SYNCHRONIZED",
    "TARGET_BRANCH_SYNC_INVARIANT",
    "TARGET_BRANCH_CONTENT_CONFLICT",
    "_STATUS_EVENTS_FILENAME",
    "_STATUS_FILENAME",
    "_SAFE_PATH_SEGMENT_DIAGNOSTIC",
    "LINEAR_HISTORY_REJECTION_TOKENS",
    "MissionBranchBlocker",
    "HollowReviewWarnings",
]
