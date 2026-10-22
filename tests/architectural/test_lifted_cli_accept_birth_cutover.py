"""Always-on regression gate: the accept-time birth-cutover stamp's idempotency and fail-closed contract.

Lifted from ``tests/specify_cli/cli/test_accept_birth_cutover.py``, whose
directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

Per the ledger's narrowed assertion shape ("fixture-driven idempotency +
fail-closed assertions, no full merge simulation needed"), this lift omits
the source suite's GitHub-squash-merge simulation (real git repo + subprocess
merge) and keeps only the two fixture-only invariants:

* **Idempotency (T010 / FR-006)** — re-running the stamp on an already-cut-
  over mission is a no-op: byte-identical ``status.events.jsonl``, no error.
* **Fail-closed (T008 / NFR-003 / R6)** — an absent ``mission_id`` refuses to
  stamp (raises, non-zero), and writes no seed events at all.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home both this gate and its source import
# (#5015); importing them here is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_accept_birth_cutover import (
    test_accept_stamp_fails_closed_when_mission_id_absent as test_accept_stamp_fails_closed_when_mission_id_absent,
)
from tests.architectural._lifted_cli_accept_birth_cutover import (
    test_accept_stamp_idempotent_rerun_is_byte_identical as test_accept_stamp_idempotent_rerun_is_byte_identical,
)

pytestmark = [pytest.mark.architectural]
