"""Always-on gate: the retired ``/spec-kitty.checklist`` surface stays fully retired.

Source: ``tests/specify_cli/test_no_checklist_surface.py`` (FR-003, FR-004 /
WP04 / #815), which lives directly under ``tests/specify_cli`` — recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374,
decide-out-of-matrix-test-dirs ledger, lift-invariant disposition).

Future-proofing regression scan: if a future change recreates the deprecated
checklist command surface (filenames or the literal ``/spec-kitty.checklist``
token) anywhere under the scanned roots, this fails. Legitimate "checklist"
concepts (the mission requirements checklist under ``kitty-specs/``, release
and review checklists) are allowlisted.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_root_no_checklist_surface import test_no_checklist_filenames_in_scan_roots as test_no_checklist_filenames_in_scan_roots
from tests.architectural._lifted_root_no_checklist_surface import test_no_checklist_command_string_in_scan_roots as test_no_checklist_command_string_in_scan_roots

pytestmark = [pytest.mark.architectural]
