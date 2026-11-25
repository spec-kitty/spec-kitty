"""#7860: the planning lane's one write-branch rule (``mission_runtime.planning_write_ref``).

Before a default Mission (``topology_source: default``) lands, its planning lane writes to its
Mission branch (FR-061 extended to the planning lane, ADR 2026-11-06-3 Amendment 2026-11-25).
Every other Mission keeps today's write ref (``resolve_single_branch_write_ref``). An unreadable
PRIMARY ``meta.json`` raises instead of reading as "not a default Mission" (NFR-002); the
placement reader ``_default_mission_facts`` stays non-raising.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mission_runtime
from mission_runtime.resolution import _default_mission_facts
from tests._support.git_cli import git_out

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "fx-01M8AAAA"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_TARGET = "main"


def _repo(tmp_path: Path, meta: dict[str, object] | str | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", _TARGET)
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    if meta is not None:
        mission_dir = repo / "kitty-specs" / _SLUG
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(meta if isinstance(meta, str) else json.dumps(meta), encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-q", "-m", "baseline")
    return repo


def _meta(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {"mission_slug": _SLUG, "mission_id": "01M8AAAAAAAAAAAAAAAAAAAAAA", "target_branch": _TARGET, "topology": "lanes_with_coord"}
    base.update(fields)
    return base


def test_a_default_mission_before_landing_writes_on_its_mission_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH, coordination_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert ref == mission_runtime.PlanningWriteRef(branch=_MISSION_BRANCH, on_mission_branch=True, landed=False, meta_found=True)


def test_a_landed_default_mission_writes_on_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH, merged_at="2026-11-25T00:00:00+00:00"))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch, ref.landed) == (_TARGET, False, True)


def test_an_explicit_topology_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(mission_branch=_MISSION_BRANCH, coordination_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch, ref.meta_found) == (_TARGET, False, True)


def test_an_explicit_single_branch_keeps_its_minted_write_branch_off_the_default_rule(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology="single_branch", mission_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_MISSION_BRANCH, False)


def test_a_default_mission_without_a_mission_branch_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default"))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


def test_a_malformed_meta_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "{not json")

    with pytest.raises(mission_runtime.PlanningWriteRefUnavailable, match="meta.json is unreadable"):
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)


def test_a_missing_meta_reports_meta_not_found_and_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, None)

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch, ref.meta_found) == (_TARGET, False, False)


def test_the_placement_reader_stays_non_raising_on_a_malformed_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "{not json")

    assert _default_mission_facts(repo, _SLUG) == (None, None, False)


def test_an_unreadable_landing_record_reads_as_not_landed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``mission_has_landed`` is non-raising: an unreadable record keeps the Mission branch (the caller fails closed downstream)."""
    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH))
    import mission_runtime.landing as landing

    monkeypatch.setattr(landing, "mission_has_landed", lambda _dir: False)

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.landed) == (_MISSION_BRANCH, False)
