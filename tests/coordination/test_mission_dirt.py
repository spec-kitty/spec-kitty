"""Mission-scoped dirt classification (#7545 / #7556, FR-001).

Pins the one structural rule every Mission-write gate uses to decide whose
uncommitted path it is looking at, and pins that the destructive guards'
private wrapper (``coherence._is_other_mission_path``) keeps its old answers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import CheckoutRole, ResidueContext, _is_other_mission_path
from specify_cli.coordination.mission_dirt import (
    DirtScope,
    MissionDirt,
    classify_dirt,
    derived_view_mission_dir,
    mission_dir_segments,
    partition_mission_dirt,
)

pytestmark = pytest.mark.fast

OWN = "mine-01ABCDEF"
ALIAS = "mine-01ABCDEF-01ABCDEF"
OTHER = "other-01GHJKMN"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (f"kitty-specs/{OWN}/spec.md", DirtScope.OWN),
        (f"kitty-specs/{OWN}/", DirtScope.OWN),
        (f"kitty-specs/{OWN}/tasks/WP01-a.md", DirtScope.OWN),
        (f"kitty-specs/{ALIAS}/status.events.jsonl", DirtScope.OWN),
        (f".kittify/derived/{OWN}/status.json", DirtScope.OWN),
        (f"kitty-specs/{OTHER}/notes.md", DirtScope.OTHER_MISSION),
        (f"kitty-specs/{OTHER}/", DirtScope.OTHER_MISSION),
        (f"kitty-specs/{OTHER}/decisions/index.json", DirtScope.OTHER_MISSION),
        (f".kittify/derived/{OTHER}/status.json", DirtScope.OTHER_MISSION),
        (f"kitty-specs\\{OTHER}\\notes.md", DirtScope.OTHER_MISSION),
        (f".worktrees/x-coord/kitty-specs/{OTHER}/a.md", DirtScope.OTHER_MISSION),
        ("src/app.py", DirtScope.OUTSIDE),
        ("dirty.txt", DirtScope.OUTSIDE),
        (".kittify/evidence/01ABCDEFGHJKMNPQRSTVWXYZ00/log.txt", DirtScope.OUTSIDE),
        ("kitty-ops/lifecycle/01ABCDEFGHJKMNPQRSTVWXYZ00.json", DirtScope.OUTSIDE),
        ("kitty-specs/", DirtScope.OUTSIDE),
        ("kitty-specs/README.md", DirtScope.OUTSIDE),
        (".kittify/derived/status.json", DirtScope.OUTSIDE),
    ],
)
def test_classify_dirt(path: str, expected: DirtScope) -> None:
    assert classify_dirt(path, own_dir_names={OWN, ALIAS}) is expected


def test_classify_accepts_path_objects() -> None:
    assert classify_dirt(Path("kitty-specs") / OTHER / "a.md", own_dir_names={OWN}) is DirtScope.OTHER_MISSION


def test_partition_keeps_input_order_per_scope() -> None:
    paths = [
        "src/b.py",
        f"kitty-specs/{OTHER}/",
        f"kitty-specs/{OWN}/plan.md",
        "src/a.py",
        f"kitty-specs/{OWN}/spec.md",
    ]

    dirt = partition_mission_dirt(paths, own_dir_names={OWN})

    assert dirt == MissionDirt(
        own=(f"kitty-specs/{OWN}/plan.md", f"kitty-specs/{OWN}/spec.md"),
        other_mission=(f"kitty-specs/{OTHER}/",),
        outside=("src/b.py", "src/a.py"),
    )
    assert dirt.foreign == (f"kitty-specs/{OTHER}/", "src/b.py", "src/a.py")


def test_partition_of_nothing_is_empty() -> None:
    assert partition_mission_dirt([], own_dir_names={OWN}) == MissionDirt()


def test_helpers() -> None:
    assert mission_dir_segments("src/a.py") is None
    assert mission_dir_segments("kitty-specs/") == ()
    assert mission_dir_segments(f"kitty-specs/{OWN}/") == (OWN,)
    assert derived_view_mission_dir(f".kittify/derived/{OWN}/v.json") == OWN
    assert derived_view_mission_dir(f".kittify/derived/{OWN}/deep/v.json") is None


_CONTEXT = ResidueContext(role=CheckoutRole.REPOSITORY_ROOT, mission_slug=OWN, topology=MissionTopology.SINGLE_BRANCH)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # The destructive guards' answers before WP01, unchanged.
        (f"kitty-specs/{OTHER}/a.md", True),
        (f".worktrees/x/kitty-specs/{OTHER}/a.md", True),
        (f".kittify/derived/{OTHER}/status.json", True),
        (f"kitty-specs/{OWN}/a.md", False),
        (f".kittify/derived/{OWN}/status.json", False),
        # A bare Mission directory entry stays False there: those guards list
        # every untracked file and never see the collapsed shape.
        (f"kitty-specs/{OTHER}/", False),
        (f"kitty-specs/{OTHER}", False),
        ("kitty-specs/README.md", False),
        ("src/a.py", False),
    ],
)
def test_destructive_guard_wrapper_answers_are_unchanged(path: str, expected: bool) -> None:
    assert _is_other_mission_path(path, _CONTEXT) is expected
