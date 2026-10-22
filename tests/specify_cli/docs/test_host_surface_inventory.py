"""WP05 / FR-001 / NFR-003 — Host-surface parity matrix coverage test.

Asserts that every supported host surface from AGENT_DIRS has exactly one row
in docs/architecture/host-surface-parity.md, and that every row has a valid parity_status.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_specify_cli_docs_host_surface_inventory.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_parity_doc_exists as test_parity_doc_exists
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_surface_has_a_row as test_every_surface_has_a_row
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_no_duplicate_surface_rows as test_no_duplicate_surface_rows
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_row_has_valid_parity_status as test_every_row_has_valid_parity_status
from tests.architectural._lifted_specify_cli_docs_host_surface_inventory import test_every_non_parity_row_has_notes as test_every_non_parity_row_has_notes

pytestmark = [pytest.mark.unit, pytest.mark.fast]
