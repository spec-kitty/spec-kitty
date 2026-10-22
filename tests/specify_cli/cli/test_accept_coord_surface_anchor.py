"""Two residual properties of the ``accept`` birth-cutover COORD leg.

``_coord_status_feature_dir`` and its direct properties are covered by
``tests/specify_cli/cli/commands/test_accept_birth_cutover_seam.py`` (the seam
is asked with ``STATUS_STATE`` via ``write_dir``; ``None`` off the declared
PRIMARY surface; an unsafe handle is refused before the seam; the stamp
receives the seam's dir). This file does **not** restate those.

It pins the two properties that suite does not assert, both of which are
failure-mode claims rather than happy-path ones:

1. **No ``git`` round trip.** The historical bug was not only a wrong join — it
   was that the join's anchor came from ``git rev-parse --show-toplevel``, and a
   ``git`` call that did not answer downgraded the anchor to ``None``, silently
   writing the status seed onto the PRIMARY partition. Routing through the seam
   removes the shell-out; nothing else pins that it stays removed.

2. **``CoordinationBranchDeleted`` propagates.** ``_coord_status_feature_dir``'s
   docstring states the C3 fail-loud posture — accept must refuse rather than
   stamp a stale primary — but the behaviour is inherited from the write-seam's
   own resolution, and an inherited behaviour with no test is one refactor away
   from being absorbed into a ``None`` the way ``coord_read_dir_for`` absorbs it.

Both were RED before the routing change and are cheap to keep.

coord-artifact-single-home-01M3V4BE WP16: the seam now resolves via
:meth:`~mission_runtime.PlacementSeam.write_dir` (a WRITE resolution), not
:meth:`~mission_runtime.PlacementSeam.read_dir` — see
``accept._coord_status_feature_dir``'s docstring for why a write must never
inherit the read projection's declared EMPTY/UNMATERIALIZED fallback to the
PRIMARY checkout. Both pins below are re-expressed against ``write_dir``.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_cli_accept_coord_surface_anchor.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_cli_accept_coord_surface_anchor import surfaces as surfaces
from tests.architectural._lifted_cli_accept_coord_surface_anchor import (
    test_coord_stamp_leg_does_not_round_trip_through_git as test_coord_stamp_leg_does_not_round_trip_through_git,
)
from tests.architectural._lifted_cli_accept_coord_surface_anchor import (
    test_coord_status_feature_dir_propagates_a_deleted_coordination_branch as test_coord_status_feature_dir_propagates_a_deleted_coordination_branch,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
