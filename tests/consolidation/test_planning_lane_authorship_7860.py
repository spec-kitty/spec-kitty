"""#7860 (FR-012): the claim attributes a default Mission's planning lane against its Mission branch.

Before a default Mission lands, its planning lane writes to its Mission branch, which the
coordination base (the Mission branch's pre-mutation tip) already carries. Measured
``coord_base..<target>`` the planning lane authored nothing, so owned planning content outside the
bookkeeping paths (the pre-#7816 shape) read as un-attributable at the reconciliation gate. The
claim now walks ``<planning pin>..<coordination base>`` for that lane, keeping only commits and
paths inside the lane's owned paths, so Mission-branch status and stray commits never read as
approved planning authorship. Every other shape keeps its range.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mission_runtime
from specify_cli.consolidation import reconciliation_authorship as authorship
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests._support.git_cli import git_out
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

pytestmark = [pytest.mark.git_repo]

_SLUG = "auth-01M8EEEE"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"
_OWNED = "curation/apply_curation.py"
_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (_OWNED,), (), (), 0)
_EMPTY_PLANNING = ExecutionLane(PLANNING_LANE_ID, ("WP02",), (), (), (), 0)
_CODE = ExecutionLane("lane-a", ("WP01",), ("src/**",), (), (), 0)


def _manifest(pin: str | None = "pin0000") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[_CODE, _PLANNING],
        computed_at="2026-11-26T00:00:00+00:00",
        computed_from="test",
        planning_artifact_wps=["WP02"],
        planning_commit_sha=pin,
    )


def _reader(on_mission_branch: bool) -> object:
    def _read(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        return mission_runtime.PlanningWriteRef(branch=_MISSION_BRANCH if on_mission_branch else "main", on_mission_branch=on_mission_branch, landed=False)

    return _read


# ---------------------------------------------------------------- the walk range


@pytest.mark.unit
def test_a_default_missions_planning_lane_walks_its_mission_branch_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None) == ("pin0000", "coord0000", (_OWNED,))


@pytest.mark.unit
def test_every_other_shape_keeps_its_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(False))

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None) == ("coord0000", "main", ())
    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", ("sb0", "sb1")) == ("sb0", "sb1", ())
    assert authorship._lane_walk_range(Path(), _manifest(), _CODE, "coord0000", None) == ("coord0000", f"kitty/mission-{_SLUG}-lane-a", ())


@pytest.mark.unit
def test_an_empty_write_scope_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty owned scope on the Mission-branch window authors nothing: it never widens to an unscoped walk."""
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(), _EMPTY_PLANNING, "coord0000", None) == ("coord0000", "main", ())


@pytest.mark.unit
def test_no_planning_pin_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    assert authorship._lane_walk_range(Path(), _manifest(pin=None), _PLANNING, "coord0000", None) == ("coord0000", "main", ())


@pytest.mark.unit
@pytest.mark.parametrize(
    "error", [mission_runtime.PlanningWriteRefUnavailable(_SLUG, "meta.json is unreadable"), mission_runtime.PlanningCheckoutMissing(_SLUG, _MISSION_BRANCH)]
)
def test_an_undecidable_write_branch_keeps_the_target_range(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """The planning lane then authors nothing, so the gate still refuses content it cannot attribute (fail closed)."""

    def _raise(*_args: object, **_kwargs: object) -> mission_runtime.PlanningWriteRef:
        raise error

    monkeypatch.setattr(mission_runtime, "planning_write_ref", _raise)

    assert authorship._lane_walk_range(Path(), _manifest(), _PLANNING, "coord0000", None) == ("coord0000", "main", ())


@pytest.mark.unit
def test_a_scoped_walk_keeps_only_owned_paths() -> None:
    walk = ({(_OWNED, "b1"), ("stray.py", "b2")}, {"curation/old.py", "stray_gone.py"})

    assert authorship._scoped_walk(walk, ("curation/**",)) == ({(_OWNED, "b1")}, {"curation/old.py"})
    assert authorship._scoped_walk(walk, ()) is walk


# ---------------------------------------------------------------- real git


def _git(repo: Path, *args: str) -> str:
    return git_out(repo, *args).strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for relpath, text in files.items():
        (repo / relpath).parent.mkdir(parents=True, exist_ok=True)
        (repo / relpath).write_text(text, encoding="utf-8")
        _git(repo, "add", "--", relpath)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _mission(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    """A default, not-landed Mission on its Mission branch: a status commit, an owned commit, a mixed one and a stray one."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _commit(repo, {"README.md": "x\n"}, "init")
    _git(repo, "switch", "-qc", _MISSION_BRANCH)
    meta = {"mission_slug": _SLUG, "target_branch": "main", "topology": "lanes_with_coord", "topology_source": "default", "mission_branch": _MISSION_BRANCH}
    pin = _commit(repo, {f"kitty-specs/{_SLUG}/meta.json": json.dumps(meta)}, "planning")
    shas = {
        "status": _commit(repo, {f"kitty-specs/{_SLUG}/status.events.jsonl": "{}\n"}, "chore: status"),
        "owned": _commit(repo, {_OWNED: "VALUE = 1\n"}, "feat(WP02): curation"),
        "mixed": _commit(repo, {_OWNED: "VALUE = 2\n", "sneaky.py": "X = 1\n"}, "feat(WP02): curation and more"),
        "stray": _commit(repo, {"stray.py": "Y = 1\n"}, "stray commit on the Mission branch"),
    }
    return repo, pin, shas


@pytest.mark.integration
def test_only_commits_touching_the_owned_paths_are_kept(tmp_path: Path) -> None:
    repo, pin, shas = _mission(tmp_path)
    spine = git_out(repo, "rev-list", "--first-parent", f"{pin}..HEAD").split()

    kept = authorship._commits_touching(repo, spine, (_OWNED,))

    assert kept == [shas["mixed"], shas["owned"]]


@pytest.mark.integration
def test_an_unreadable_commit_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _pin, shas = _mission(tmp_path)

    def _broken(_repo: Path, _sha: str) -> list[str]:
        raise GitProbeError("git show failed")

    setattr_reconciliation_family(monkeypatch, "changed_paths_of", _broken)

    assert authorship._commits_touching(repo, [shas["owned"]], (_OWNED,)) == []


@pytest.mark.integration
def test_the_claim_attributes_the_owned_planning_content_and_nothing_else(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the collector: the owned file's final blob is approved authorship; the stray and sneaked-in paths are not."""
    repo, pin, shas = _mission(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    manifest = _manifest(pin=pin)
    manifest.lanes = [_PLANNING]
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    claim = authorship._collect_authored(repo, manifest, {"WP02": {"lane": "approved"}}, coord_base, None, canceled_lane_commits=frozenset())

    owned_blob = _git(repo, "rev-parse", f"{coord_base}:{_OWNED}")
    assert (_OWNED, owned_blob) in claim.blobs
    assert {path for path, _blob in claim.blobs} == {_OWNED}
    assert {shas["owned"], shas["mixed"]} <= claim.shas
    assert shas["stray"] not in claim.shas and shas["status"] not in claim.shas


@pytest.mark.integration
def test_without_the_mission_branch_rule_the_planning_lane_authors_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the pre-#7860 range ``coord_base..<target>`` is empty for work that sits on the Mission branch."""
    repo, pin, _shas = _mission(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    manifest = _manifest(pin=pin)
    manifest.lanes = [_PLANNING]
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(False))

    claim = authorship._collect_authored(repo, manifest, {"WP02": {"lane": "approved"}}, coord_base, None, canceled_lane_commits=frozenset())

    assert not claim.blobs


@pytest.mark.integration
def test_an_empty_planning_write_scope_authors_nothing_on_the_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``planning_artifact`` WP with ``owned_files: []`` gives the planning lane an empty scope: status, stray and code commits stay unattributed."""
    repo, pin, shas = _mission(tmp_path)
    coord_base = _git(repo, "rev-parse", "HEAD")
    manifest = _manifest(pin=pin)
    manifest.lanes = [_EMPTY_PLANNING]
    monkeypatch.setattr(mission_runtime, "planning_write_ref", _reader(True))

    claim = authorship._collect_authored(repo, manifest, {"WP02": {"lane": "approved"}}, coord_base, None, canceled_lane_commits=frozenset())

    paths = {path for path, _blob in claim.blobs}
    assert not paths & {"stray.py", "sneaky.py", f"kitty-specs/{_SLUG}/status.events.jsonl", _OWNED}
    assert not claim.shas & set(shas.values())
