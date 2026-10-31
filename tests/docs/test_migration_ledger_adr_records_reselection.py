"""ADR ``2026-10-17-1`` names the code's own identifiers for the ledger lock and the reselection (#6613).

The amendment exists because the ADR once described selection and the append in
terms the code did not match. This guard ties the ADR to the code's real names:
the timeout error class is derived from the module, and the other two are the
identifiers the amendment is about, each checked to still exist in the code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.locks import machine_file_lock
from specify_cli.upgrade.ledger import MigrationLedgerLockTimeoutError
from specify_cli.upgrade.migrations.base import BaseMigration

pytestmark = [pytest.mark.unit]

ADR = Path(__file__).resolve().parents[2] / "docs" / "adr" / "4.x" / "2026-10-17-1-explicit-migration-ledger.md"


def test_the_adr_names_the_identifiers_the_code_uses() -> None:
    adr = ADR.read_text(encoding="utf-8")

    for identifier in (BaseMigration.structural_detect.__name__, machine_file_lock.__name__, MigrationLedgerLockTimeoutError.__name__):
        assert identifier in adr, f"ADR 2026-10-17-1 no longer names `{identifier}`"
