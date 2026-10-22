"""Always-on regression gate: the ``accept`` COORD stamp leg's two failure-mode pins.

Lifted from ``tests/specify_cli/cli/test_accept_coord_surface_anchor.py``,
whose directory (``tests/specify_cli/cli``) is recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374, #4479).

Two structural properties, both failure-mode claims rather than happy-path
ones (no git-network dependency — the seam and ``run_git`` are monkeypatched):

1. The COORD anchor comes straight off the placement seam — no shell-out to
   ``git rev-parse --show-toplevel``. A non-answering ``git`` used to
   downgrade the anchor to ``None``, silently writing the status seed onto
   the PRIMARY partition.
2. ``CoordinationBranchDeleted`` propagates out of
   ``_coord_status_feature_dir`` rather than being absorbed into ``None``
   (the C3 fail-loud posture) — an inherited resolver behaviour with no
   pinning test is one refactor away from silent absorption.

coord-artifact-single-home-01M3V4BE WP16: the seam now resolves via
:meth:`~mission_runtime.PlacementSeam.write_dir` (a WRITE resolution), not
:meth:`~mission_runtime.PlacementSeam.read_dir` — both pins below are
re-expressed against ``write_dir``, mirroring the sibling file this one lifts
from.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_accept_coord_surface_anchor import surfaces as surfaces
from tests.architectural._lifted_cli_accept_coord_surface_anchor import (
    test_coord_stamp_leg_does_not_round_trip_through_git as test_coord_stamp_leg_does_not_round_trip_through_git,
)
from tests.architectural._lifted_cli_accept_coord_surface_anchor import (
    test_coord_status_feature_dir_propagates_a_deleted_coordination_branch as test_coord_status_feature_dir_propagates_a_deleted_coordination_branch,
)

pytestmark = [pytest.mark.architectural]
