"""``MissionStatus.load`` over every Mission is linear in the number of Missions (#6517).

A project-wide read loads each Mission by its directory name. Each load canonicalizes the
handle three to four times through the Mission resolver, and each canonicalization used to
walk ``kitty-specs/`` and parse every ``meta.json``: N loads cost about 3.5 * N * N meta reads
(about 1.4 million for the 639 Missions of this repository) and pushed the nightly corpus run
past its 120 s bound. These tests pin that loading N Missions by name never walks the tree and
reads a constant number of ``meta.json`` files per Mission, and that a handle the ladder finds
ambiguous still fails closed through ``load``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context import mission_resolver
from specify_cli.mission_metadata import OnMalformed, load_meta
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.status.aggregate import MissionStatus

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

SMALL, LARGE = 6, 12


def _repo_with_missions(root: Path, count: int) -> list[str]:
    names = [f"{index:03d}-mission" for index in range(count)]
    for index, name in enumerate(names):
        directory = root / "kitty-specs" / name
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(json.dumps({"mission_id": f"01{index:024d}", "mission_slug": name}), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    return names


def _meta_reads_for_loading_every_mission(root: Path, names: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    """Load every Mission by name; return the resolver's ``meta.json`` reads, failing on any full walk."""
    reads = 0

    def counted(path: Path, *, on_malformed: OnMalformed = "raise") -> dict[str, Any] | None:
        nonlocal reads
        reads += 1
        meta: dict[str, Any] | None = load_meta(path, on_malformed=on_malformed)
        return meta

    def no_walk(_root: Path) -> list[mission_resolver.ResolvedMission]:
        raise AssertionError("loading a Mission by its directory name walked the whole kitty-specs/ tree")

    with monkeypatch.context() as patch:
        patch.setattr("specify_cli.context.mission_resolver.load_meta", counted)
        patch.setattr(mission_resolver, "_build_index", no_walk)
        for name in names:
            assert MissionStatus.load(root, name).mission_slug == name
    return reads


def test_loading_every_mission_reads_a_constant_number_of_metas_per_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    small = _meta_reads_for_loading_every_mission(tmp_path / "small", _repo_with_missions(tmp_path / "small", SMALL), monkeypatch)
    large = _meta_reads_for_loading_every_mission(tmp_path / "large", _repo_with_missions(tmp_path / "large", LARGE), monkeypatch)
    assert small > 0, "the counter saw no resolver read, so the scaling claim would prove nothing"
    # Linear: doubling the Missions doubles the reads. Quadratic growth would quadruple them.
    assert large == 2 * small, f"{SMALL} Missions cost {small} meta reads, {LARGE} cost {large}"


def test_an_ambiguous_human_slug_still_fails_closed_through_load(tmp_path: Path) -> None:
    for name, mission_id in (("080-shared", "01SHAREDA0000000000000000A"), ("081-shared", "01SHAREDB0000000000000000B")):
        directory = tmp_path / "kitty-specs" / name
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(json.dumps({"mission_id": mission_id}), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    with pytest.raises(MissionSelectorAmbiguous) as raised:
        MissionStatus.load(tmp_path, "shared")
    assert sorted(raised.value.candidates) == ["080-shared", "081-shared"]
