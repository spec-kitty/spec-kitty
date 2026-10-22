"""Always-on freshness gate: docs/architecture/host-surface-parity.md stays complete.

Lifted from ``tests/specify_cli/docs/test_host_surface_inventory.py`` (WP05 /
FR-001 / NFR-003), a ``tests/specify_cli/docs`` tree recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` — no per-PR lane
selects it (#4374 disposition ledger, disposition 2 — lift-invariant).

Every supported host surface must have exactly one row with a valid
``parity_status``, and every non-``at_parity``/pointer row must explain the
gap in its notes column.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_parity_doc_exists as test_parity_doc_exists
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_surface_has_a_row as test_every_surface_has_a_row
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_no_duplicate_surface_rows as test_no_duplicate_surface_rows
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_row_has_valid_parity_status as test_every_row_has_valid_parity_status
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_non_parity_row_has_notes as test_every_non_parity_row_has_notes

pytestmark = [pytest.mark.architectural]
