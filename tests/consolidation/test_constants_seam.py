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
