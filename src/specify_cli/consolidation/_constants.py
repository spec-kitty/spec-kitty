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

# The logger is bound to the command-module name so log records keep a stable
# namespace (``specify_cli.cli.commands.consolidate``) regardless of which seam
# module emits them. Updated for the merge->consolidate rename (#3080); existing
# log filters/handlers should key on the new name going forward.
logger = logging.getLogger("specify_cli.cli.commands.consolidate")

# Target-branch sync preflight diagnostic codes (issue #017 family).
TARGET_BRANCH_NOT_SYNCHRONIZED = "TARGET_BRANCH_NOT_SYNCHRONIZED"
TARGET_BRANCH_SYNC_INVARIANT = "local_target_branch_must_match_tracking_branch"

# Squash integration would clobber newer target-branch content (#4892). Shared
# by the dry-run forecast and the real mission→target merge so both emit the
# SAME diagnostic code and remediation, not divergent prose.
TARGET_BRANCH_CONTENT_CONFLICT = "TARGET_BRANCH_CONTENT_CONFLICT"
# The operator-facing header + first remediation line for that conflict. Shared
# so the dry-run forecast and the real merge stay byte-identical (the second
# remediation line intentionally differs per surface: the dry-run says rerun
# ``--dry-run``, the real merge says rerun ``spec-kitty consolidate``).
TARGET_BRANCH_CONTENT_CONFLICT_HEADER = "Default squash integration would conflict with newer target-branch content."
TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE = "Update the mission branch against the current target branch."

# The shared global consolidation lock key: held by a live consolidation
# (``executor``) and taken/released owner-gated by ``consolidate --abort``.
# One definition so the two sides can never drift apart (slice-10 F6).
GLOBAL_MERGE_LOCK_ID = "__global_merge__"

# Stable code of the #5570 refusal (#5613): the mission or coordination branch moved
# after the landing was verified, so the compare-and-swap delete kept it instead of
# deleting it over the late commit. The landing itself stands. Raised and rendered on
# both terminus paths (``spec-kitty consolidate`` via ``run_state.CoordMovedAfterLanding``,
# ``orchestrator-api consolidate-mission`` via ``data["teardown_error_code"]``).
# What finishes the cleanup depends on the variant, as each message says:
#   * coordination branch: ``spec-kitty consolidate --resume`` projects the late
#     commit(s) onto the target and finishes the teardown;
#   * mission branch without a coordination topology (and the orchestrator-api path):
#     the operator lands the late commit(s) and deletes the branch by hand.
COORD_MOVED_AFTER_LANDING = "COORD_MOVED_AFTER_LANDING"
# The code is rendered as a SUFFIX of the refusal: the message text before it is the
# pre-#5613 wording, whose prefix the upstream tests assert, so it stays byte-identical.
COORD_MOVED_AFTER_LANDING_SUFFIX = f" Error code: {COORD_MOVED_AFTER_LANDING}."
# Exit code ``spec-kitty consolidate`` returns for that refusal: 75 = EX_TEMPFAIL
# (sysexits.h, "temporary failure, retry later"): nothing was lost and the cleanup can
# be completed afterwards. Every other teardown refusal keeps exit 1.
COORD_MOVED_AFTER_LANDING_EXIT_CODE = 75

# The #5965 refusal (``COORD_TEARDOWN_KEPT_ONLY_COPY``, exit 76) is defined WITH its exception in
# ``specify_cli.coordination.teardown`` (the lower layer, which this module may not be imported
# from without dragging the consolidation package in). The landing is done and verified; the
# coordination worktree holds the only copy of operator-authored files, so teardown kept the
# coordination branch, worktree and marker and the target is NOT rolled back. 76 is unused
# elsewhere (75 is the code above); the operator commits inside ``kitty-specs/<mission>/`` or
# moves the files out, then runs ``spec-kitty consolidate --resume``. Not added to ``__all__``
# (its set is pinned); import it from ``coordination.teardown``.
# Stable code of the FR-006 / #5651 refusal: the coordination seed commit was refused
# (a rejecting git hook, a protection policy, a transient git failure), so the seeded
# status files sit uncommitted in the coordination worktree. ``spec-kitty consolidate``
# stops before any branch moves with exit 1. Nothing is deleted: the files are kept and
# the next run retries the commit (I-SEED-10). Rendered as a SUFFIX, like the code above.
COORD_SEED_COMMIT_REFUSED = "COORD_SEED_COMMIT_REFUSED"
COORD_SEED_COMMIT_REFUSED_SUFFIX = f" Error code: {COORD_SEED_COMMIT_REFUSED}."

# Stable code of the #5750 refusal: the one-directory fold of a bare-slug coordination
# Mission found an event in the composed ``<slug>-<mid8>`` directory's status log that
# the primary Mission directory's event log lacks (or a log it cannot read), so it removed nothing.
# ``spec-kitty consolidate`` rolls the run back and exits 1. Rendered as a SUFFIX, like
# the codes above.
ALIAS_STATUS_EVENTS_NOT_PRESERVED = "ALIAS_STATUS_EVENTS_NOT_PRESERVED"
ALIAS_STATUS_EVENTS_NOT_PRESERVED_SUFFIX = f" Error code: {ALIAS_STATUS_EVENTS_NOT_PRESERVED}."

# Stable code of the sibling refusal (#5651): the one-directory fold found a coordination-kind
# file in the composed directory (a trace, a matrix, the decision log, a review cycle) that it
# cannot prove the primary Mission directory also holds, with the same content, so it removed
# nothing. ``spec-kitty consolidate`` rolls the run back and exits 1. Rendered as a SUFFIX.
ALIAS_FILE_NOT_PRESERVED = "ALIAS_FILE_NOT_PRESERVED"
ALIAS_FILE_NOT_PRESERVED_SUFFIX = f" Error code: {ALIAS_FILE_NOT_PRESERVED}."

# Stable code of the #5750 refusal for a Mission whose declared coordination branch is not
# the one the product composes (``kitty/mission-<slug>-<mid8>``): the coordination worktree
# is on the declared branch, so no coordination status write can resolve it. It is the code
# ``CoordinationWorkspaceBranchMismatch.error_code`` already carries, spelled once here for
# the ``spec-kitty consolidate`` rendering (exit 1). Rendered as a SUFFIX, like the codes above.
COORDINATION_WORKTREE_BRANCH_MISMATCH = "COORDINATION_WORKTREE_BRANCH_MISMATCH"
COORDINATION_WORKTREE_BRANCH_MISMATCH_SUFFIX = f" Error code: {COORDINATION_WORKTREE_BRANCH_MISMATCH}."

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
    "TARGET_BRANCH_CONTENT_CONFLICT_HEADER",
    "TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE",
    "_STATUS_EVENTS_FILENAME",
    "_STATUS_FILENAME",
    "_SAFE_PATH_SEGMENT_DIAGNOSTIC",
    "LINEAR_HISTORY_REJECTION_TOKENS",
    "MissionBranchBlocker",
    "HollowReviewWarnings",
]
