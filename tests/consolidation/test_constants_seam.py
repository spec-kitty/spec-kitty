"""Seam test for ``specify_cli.consolidation._constants`` (mission #2057, WP02).

Pins the relocated shared literals / type aliases / logger. The re-export-
identity and one-way-import guards, and the tautological literal-equals-
itself pins, live in the consolidated
``tests/merge/test_merge_compat_surface.py`` (WP04,
dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps only the
genuine functional/order pin plus the two external-contract filename literals
(``status.json`` / ``status.events.jsonl`` are read/written on disk by other
tooling, so a silent rename is a real regression, unlike the purely-internal
diagnostic strings that were dropped as tautological).
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation import _constants

pytestmark = pytest.mark.fast


def test_linear_history_rejection_tokens_are_locked() -> None:
    """INV-8 / C-008: the rejection-token tuple order and membership are frozen."""
    assert _constants.LINEAR_HISTORY_REJECTION_TOKENS == (
        "merge commits",
        "linear history",
        "fast-forward only",
        "GH006",
        "non-fast-forward",
    )
    assert isinstance(_constants.LINEAR_HISTORY_REJECTION_TOKENS, tuple)


def test_status_filenames_are_external_contract_pins() -> None:
    """External-contract literal pins: these are the actual on-disk filenames
    (status.json / status.events.jsonl) other tooling reads/writes — a silent
    rename here is a real regression, so they stay pinned even after the
    tautological byte-identical sweep (T002)."""
    assert _constants._STATUS_EVENTS_FILENAME == "status.events.jsonl"
    assert _constants._STATUS_FILENAME == "status.json"


def test_coord_seed_commit_refused_code_is_an_operator_visible_contract() -> None:
    """FR-006 / #5651: the code operators and tests match on is pinned, and it renders as the message suffix."""
    assert _constants.COORD_SEED_COMMIT_REFUSED == "COORD_SEED_COMMIT_REFUSED"
    assert _constants.COORD_SEED_COMMIT_REFUSED_SUFFIX == " Error code: COORD_SEED_COMMIT_REFUSED."


def test_alias_status_events_not_preserved_code_is_an_operator_visible_contract() -> None:
    """#5750: the code of the fold's event-preservation refusal is pinned, and it renders as the message suffix."""
    assert _constants.ALIAS_STATUS_EVENTS_NOT_PRESERVED == "ALIAS_STATUS_EVENTS_NOT_PRESERVED"
    assert _constants.ALIAS_STATUS_EVENTS_NOT_PRESERVED_SUFFIX == " Error code: ALIAS_STATUS_EVENTS_NOT_PRESERVED."


def test_coordination_worktree_branch_mismatch_code_is_the_error_codes_of_the_mismatch_it_renders() -> None:
    """#5750: the refusal for an uncomposed coordination branch carries the code the mismatch error already has, in one spelling."""
    from specify_cli.coordination.workspace import CoordinationWorkspaceBranchMismatch

    assert _constants.COORDINATION_WORKTREE_BRANCH_MISMATCH == "COORDINATION_WORKTREE_BRANCH_MISMATCH"
    assert CoordinationWorkspaceBranchMismatch.error_code == _constants.COORDINATION_WORKTREE_BRANCH_MISMATCH
    assert _constants.COORDINATION_WORKTREE_BRANCH_MISMATCH_SUFFIX == " Error code: COORDINATION_WORKTREE_BRANCH_MISMATCH."
