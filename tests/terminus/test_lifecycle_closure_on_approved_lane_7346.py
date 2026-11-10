"""#7346 operator ruling: a lifecycle closure committed on an approved lane does not trip the approval bound.

``doctor ops --close-stale`` closes stale lifecycle records in every checkout and
commits each closure where the record lives, so an approved lane branch can gain a
commit that only adds ``kitty-ops/lifecycle/<ULID>.json``. That is spec-kitty's own
bookkeeping, not unreviewed work: ``consolidate`` must still pass. A content commit
beside it is still refused (the same fixture, :mod:`test_post_approval_commit_refused`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, run_terminus
from tests.terminus.mixed_lane_support import collapse
from tests.terminus.post_approval_support import Topology, add_post_approval_commit, build_post_approval_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CLOSURE_PATH = "kitty-ops/lifecycle/01M72B89ABCDEFGHJKMNPQRSTV.json"
_CLOSURE = json.dumps({"phase": "abandoned", "metadata": {"closed_by": "doctor_sweep"}}) + "\n"


def _consolidate(mission: CoordMission, strategy: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--strategy", strategy])
    return result.returncode, collapse(result.stdout + "\n" + result.stderr)


@pytest.mark.parametrize("strategy", ["squash", "merge"])
@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_a_lifecycle_closure_on_an_approved_lane_consolidates(tmp_path: Path, topology: Topology, strategy: str) -> None:
    mission = build_post_approval_mission(tmp_path / "closure", topology)
    add_post_approval_commit(mission, path=_CLOSURE_PATH, content=_CLOSURE)

    rc, flat = _consolidate(mission, strategy)

    assert rc == 0, f"a lifecycle closure on an approved lane must not be refused ({topology}/{strategy}):\n{flat}"
    assert "LANE_MOVED_AFTER_APPROVAL" not in flat
    assert "Reconciliation verified" in flat
