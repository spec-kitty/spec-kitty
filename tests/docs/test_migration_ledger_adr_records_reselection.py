"""The ADR and the developer reference record the ledger's real behaviour (#6613, gap G-15).

Two facts about the migration ledger were true in the code and absent from the doctrine:

* `BaseMigration.reselect_when_recorded` re-selects a `runs_first` migration whose
  `structural_detect` reports the old state present, while ADR ``2026-10-17-1`` §1 says
  selection "collapses to 'is this id in the applicable ledger'". `structural_detect`
  appeared nowhere in the ADR.
* The append took no lock, and §1 said `kernel.locks` was "deliberately not built".

WP01 built the lock; WP02 records both facts. These guards keep the record honest: they read
the real files (no fixtures) and assert the *substance* a reader needs, not a token. A missing
or emptied file fails loudly through the shared existence check rather than passing vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR = REPO_ROOT / "docs" / "adr" / "4.x" / "2026-10-17-1-explicit-migration-ledger.md"
DEVELOPER_REFERENCE = REPO_ROOT / "docs" / "development" / "reference" / "events-in-core.md"


def _read(path: Path) -> str:
    """Read a doctrine page, failing loudly when it is missing or empty.

    The same-fixture positive control for every assertion below: a page that was
    deleted or blanked can never satisfy a ``in`` check by accident.
    """
    assert path.is_file(), f"{path} is missing"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"{path} is empty"
    return text


def test_the_adr_still_describes_the_two_partition_ledger() -> None:
    """Positive control: the guard is reading the ADR it thinks it is reading."""
    adr = _read(ADR)

    assert "two-partition" in adr or "two partitions" in adr
    assert ".kittify/migration-ledger.jsonl" in adr


def test_the_adr_records_the_runs_first_structural_reselection() -> None:
    """The one unrecorded selection rule: a recorded `runs_first` migration can re-run."""
    adr = _read(ADR)

    assert "structural_detect" in adr, "the ADR must name the structural predicate the code consults"
    assert "reselect_when_recorded" in adr, "the ADR must name the hook that decides reselection"
    assert "runs_first" in adr
    assert "re-select" in adr or "reselected" in adr or "re-selected" in adr


def test_the_adr_records_the_single_runs_first_guard_and_the_detect_boundary() -> None:
    """Reselection is bounded: at most one such migration, and `detect()` stays a guard, not authority."""
    adr = _read(ADR)

    assert "at most one" in adr.lower()
    assert "`detect()`" in adr or "detect()" in adr
    assert "idempotency guard" in adr or "idempotency check" in adr


def test_the_adr_records_that_removing_the_reselection_is_an_open_operator_decision() -> None:
    """The amendment records behaviour; it does not decide to keep or remove it (C-004)."""
    adr = _read(ADR)

    assert "operator" in adr.lower()
    assert "removing" in adr.lower() or "remove" in adr.lower()


def test_the_adr_records_the_ledger_append_lock() -> None:
    """The §1 "single-writer, lock deliberately not built" claim is superseded in the record."""
    adr = _read(ADR)

    assert "machine_file_lock" in adr
    assert ".kittify/migrations/" in adr
    assert "MigrationLedgerLockTimeoutError" in adr or "LEDGER_LOCK_TIMEOUT_S" in adr


def test_the_developer_reference_states_the_ledger_lock_and_the_reselection() -> None:
    """The live reference a contributor reads must not contradict the code either."""
    reference = _read(DEVELOPER_REFERENCE)

    assert "migration ledger" in reference.lower()
    assert "lock" in reference.lower()
    assert "structural_detect" in reference or "runs_first" in reference
