"""#7860 review 10: a Mission that records no Mission base, through the REAL CLI.

The planning lane's taint walk starts only at a recorded Mission base (``mission_base_sha`` in
meta.json, written at create since #7560). A base derived from the scaffold commit (its first
parent) can sit above a commit made on the Mission branch before that scaffold, which the landing
carries, so a derived base starts nothing and the planning lane authors nothing. The refusal names
that reason and the remedy, and the remedy, run as printed, lands the Mission: run the printed
``git merge-base <target> <start>`` command, record the commit it prints (a commit on the target,
review 11: a recorded base off the target starts nothing either) as ``mission_base_sha`` and commit
it on the Mission branch. No command records the base yet (#7892).

Built on the shape-B fixture of ``test_7860_consolidate_planning_lane`` (the planning work package
WP02 owns ``curation/apply_curation.py`` in ``lane-planning``), with ``mission_base_sha`` removed
from meta.json before any work package is claimed, as a Mission created before #7560 has it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.integration import test_7860_consolidate_planning_lane as shape

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1500)]

_KEY = "mission_base_sha"


def _write_base(mission: shape._Mission, base: str | None, message: str) -> None:
    meta_path = mission.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if base is None:
        del meta[_KEY]
    else:
        meta[_KEY] = base
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    shape._git(mission.coord, "add", "--", f"kitty-specs/{mission.slug}/meta.json")
    shape._git(mission.coord, "commit", "-qm", message)


def _flat(text: str) -> str:
    return " ".join(text.split())


#: The remedy command the planning-lane note prints (``planning_lane_scope._RECORD_BASE``).
_PRINTED_COMMAND = re.compile(r"which `git merge-base (\S+) ([0-9a-f]{40})` prints")


def test_a_mission_with_no_recorded_base_is_named_and_lands_once_the_base_is_recorded(tmp_path: Path) -> None:
    mission = shape.setup_mission(tmp_path, shape._CURATION)
    shape._rebuild_pre_7816_planning_lane(mission)
    cut = json.loads((mission.feature_dir / "meta.json").read_text(encoding="utf-8"))[_KEY]
    _write_base(mission, None, "fixture: a Mission created before #7560 records no Mission base")

    refused = shape._drive_all_and_consolidate(mission, shape._CURATION)
    said = _flat(refused.stdout + refused.stderr)

    assert refused.returncode != 0, said[-3000:]
    assert f"The planning lane {shape._PLANNING_LANE} credits none of its work on the Mission branch" in said, said[-3000:]
    assert "the Mission records no usable Mission base (no mission_base_sha recorded)" in said, said[-3000:]
    assert "Record a commit on `main` as `mission_base_sha` in the Mission's meta.json" in said, said[-3000:]
    assert "(no command records it yet, #7892)" in said, said[-3000:]
    assert not shape.on_target(mission, shape._CURATION), "the refused landing is rolled back"

    # The printed remedy, run as printed: the merge base of the target and the derived start (the
    # scaffold commit's first parent) is the ``main`` commit the branch was cut from.
    match = _PRINTED_COMMAND.search(said)
    assert match is not None, said[-3000:]
    target, start = match.groups()
    assert target == "main"
    scaffold = shape._git(
        mission.repo, "log", "--reverse", "--first-parent", "--diff-filter=A", "--format=%H", mission.mission_branch, "--", f"kitty-specs/{mission.slug}/"
    )
    assert start == shape._git(mission.repo, "rev-parse", f"{scaffold.splitlines()[0]}^"), "the printed start is the scaffold commit's first parent"
    recorded = shape._git(mission.repo, "merge-base", target, start)
    assert recorded == cut, "the printed command yields the commit the Mission branch was cut from"
    _write_base(mission, recorded, "record the Mission base")
    landed = shape._sk(mission, "consolidate", "--mission", mission.slug)

    shape._assert_landed(mission, landed, shape._CURATION)
