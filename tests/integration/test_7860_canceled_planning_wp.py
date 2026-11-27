"""#7860 review 5: a dropped, never-claimed planning work package, through the REAL CLI.

Operator ruling R1: a planning lane holding any work package that is not approved credits none of
its Mission-branch work, so its owned content reads as un-attributable at the reconciliation gate.
The refusal must say so (the planning lane, the work package and why), and the remedy it prints
must land the Mission: record the claim (``move-task --to claimed --force``), force the work
package to approved, then ``consolidate --attest-no-implementation``.

Built on the shape-B fixture of ``test_7860_consolidate_planning_lane`` (the planning work package
WP02 owns ``curation/apply_curation.py`` in ``lane-planning``), with WP04 moved into
``lane-planning`` and canceled before anyone claimed it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.integration import test_7860_consolidate_planning_lane as shape

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1500)]

_DROPPED = "WP04"


def _move_dropped_wp_into_the_planning_lane(mission: shape._Mission) -> None:
    lanes_path = mission.feature_dir / "lanes.json"
    manifest = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes = [lane for lane in manifest["lanes"] if lane["wp_ids"] != [_DROPPED]]
    planning = next(lane for lane in lanes if lane["lane_id"] == shape._PLANNING_LANE)
    planning["wp_ids"] = sorted({*planning["wp_ids"], _DROPPED})
    planning["write_scope"] = sorted({*planning["write_scope"], "src/m4/**"})
    manifest["lanes"] = lanes
    manifest["planning_artifact_wps"] = sorted({*manifest.get("planning_artifact_wps", []), _DROPPED})
    lanes_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    task = next((mission.feature_dir / "tasks").glob(f"{_DROPPED}-*.md"))
    text = task.read_text(encoding="utf-8")
    text = re.sub(r"^execution_mode: .*$", "execution_mode: planning_artifact", text, count=1, flags=re.MULTILINE)
    task.write_text(text, encoding="utf-8")
    shape._git(mission.coord, "add", "-A", f"kitty-specs/{mission.slug}")
    shape._git(mission.coord, "commit", "-qm", f"fixture: {_DROPPED} in lane-planning")


def _move(mission: shape._Mission, to: str, agent: str, note: str) -> None:
    shape._sk(mission, "agent", "tasks", "move-task", _DROPPED, "--to", to, "--force", "--agent", agent, "--note", note, "--mission", mission.slug, check=True)
    shape._commit_bookkeeping(mission)


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_a_dropped_planning_work_package_is_named_and_its_printed_remedy_lands(tmp_path: Path) -> None:
    mission = shape.setup_mission(tmp_path, shape._CURATION)
    shape._rebuild_pre_7816_planning_lane(mission)
    _move_dropped_wp_into_the_planning_lane(mission)
    for wp, subtask, _glob, path in shape._CODE_WPS:
        if wp != _DROPPED:
            shape.drive(mission, wp, subtask, path)
    shape.drive(mission, "WP02", "T2", shape._CURATION)
    _move(mission, "canceled", "op", "dropped")
    verdict = ("--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    shape._sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, *verdict)
    shape._commit_bookkeeping(mission)

    refused = shape._sk(mission, "consolidate", "--mission", mission.slug)
    said = _flat(refused.stdout + refused.stderr)

    assert refused.returncode != 0, said[-3000:]
    assert "belongs to NO approved WP" in said, said[-3000:]
    assert f"The planning lane {shape._PLANNING_LANE} credits none of its work on the Mission branch" in said, said[-3000:]
    assert f"{_DROPPED} is canceled" in said, said[-3000:]
    assert "spec-kitty agent tasks move-task <WP> --to claimed --force" in said
    assert "spec-kitty agent tasks move-task <WP> --to approved --force" in said
    assert "spec-kitty consolidate --attest-no-implementation <WP>" in said
    assert not shape.on_target(mission, shape._CURATION), "the refused landing is rolled back"

    # The printed remedy, as printed: record the claim, force the approval, attest no implementation.
    _move(mission, "claimed", "alice", "record the claim of the dropped work package")
    _move(mission, "approved", "bob", "owes no work")
    landed = shape._sk(mission, "consolidate", "--mission", mission.slug, "--attest-no-implementation", _DROPPED, "--attest-reason", "dropped, owes no work")
    output = landed.stdout + landed.stderr

    assert landed.returncode == 0, output[-4000:]
    assert shape._BANNER in output, output[-4000:]
    assert shape.on_target(mission, shape._CURATION)
