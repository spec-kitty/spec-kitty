"""Aggregate scanner — verify the deprecated `/spec-kitty.checklist`
slash-command surface is fully retired (FR-003, FR-004 / WP04 / #815).

This is the future-proofing regression: if a future change recreates the
deprecated surface anywhere under the scanned roots, both tests fail.

Allowlist
---------
Legitimate "checklist" concepts are carved out so the scanner only flags
the retired command surface:

* `kitty-specs/<m>/checklists/` — the canonical mission requirements
  checklist artifact (C-003) MUST keep working.
* `RELEASE_CHECKLIST.md` — repo release checklist, unrelated.
* Any filename containing `release_checklist` / `release-checklist` /
  `review_checklist` / `review-checklist` — generic concepts.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_root_no_checklist_surface.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_root_no_checklist_surface import test_no_checklist_filenames_in_scan_roots as test_no_checklist_filenames_in_scan_roots
from tests.architectural._lifted_root_no_checklist_surface import test_no_checklist_command_string_in_scan_roots as test_no_checklist_command_string_in_scan_roots

pytestmark = [pytest.mark.unit, pytest.mark.fast]
