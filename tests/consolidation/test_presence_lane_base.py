"""#5792 review (M1/L1/L2): the presence axis measures each approved lane from the lane's OWN base.

One small repository, real git:

* ``main``: ``c0`` (the target's pre-mutation tip, the presence base);
* the mission branch: ``m1`` adds ``src/scratch.py`` outside every lane, then
  lane-a's ``a1`` (``src/added.py``) is fast-forwarded in (an earlier attempt
  merged the lane), then ``m2`` deletes ``src/added.py`` (the #5788 shape);
* lane-a was cut after ``m1``; its first governed claim stamp is ``m1``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.consolidation import reconciliation as rec
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.lanes.models import ExecutionLane, LanesManifest

pytestmark = pytest.mark.git_repo

_SLUG = "presence-base-01MPB5E3"
_LANE = ExecutionLane(
    lane_id="lane-a",
    wp_ids=("WP01",),
    write_scope=("src/added.py",),
    predicted_surfaces=("code",),
    depends_on_lanes=(),
    parallel_group=0,
)
_MANIFEST = LanesManifest(
    version=1,
    mission_slug=_SLUG,
    mission_id="01MPB5E3000000000000000000",
    mission_branch=f"kitty/mission-{_SLUG}",
    target_branch="main",
    lanes=[_LANE],
    computed_at=now_utc_iso(),
    computed_from="presence-base-test",
)
_APPROVED = {"WP01": {"lane": "approved"}}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, path: str, body: str | None, message: str) -> str:
    target = repo / path
    if body is None:
        _git(repo, "rm", "-q", path)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, str | Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    c0 = _commit(root, "README.md", "base\n", "c0")
    mission = _MANIFEST.mission_branch
    _git(root, "checkout", "-q", "-b", mission)
    m1 = _commit(root, "src/scratch.py", "x = 1\n", "m1 scaffolding outside every lane")
    lane_branch = rec._lane_branch_for(_MANIFEST, "lane-a")
    _git(root, "checkout", "-q", "-b", lane_branch)
    a1 = _commit(root, "src/added.py", "def added() -> int:\n    return 1\n", "a1 WP01")
    _git(root, "checkout", "-q", mission)
    _git(root, "merge", "-q", "--ff-only", lane_branch)
    m2 = _commit(root, "src/added.py", None, "m2 drops WP01's code")
    return {"root": root, "c0": c0, "m1": m1, "a1": a1, "m2": m2, "lane_branch": lane_branch}


def _scope(repo: dict[str, str | Path], *, stamp: str | None, canceled: frozenset[str] = frozenset(), carried: bool = True) -> rec._PresenceScope:
    root = Path(repo["root"])
    scope = rec._presence_scope(root, _MANIFEST, frozenset(), base=str(repo["c0"]), coord_base_ref=str(repo["m2"]), events=None)
    return rec._PresenceScope(
        base=scope.base,
        carried=scope.carried if carried else None,
        lane_bases={"lane-a": stamp},
        canceled=canceled,
    )


def test_presence_spine_keeps_the_lanes_own_merged_commit_and_drops_the_earlier_scaffolding(repo: dict[str, str | Path]) -> None:
    spine = rec._presence_spine(Path(repo["root"]), _scope(repo, stamp=str(repo["m1"])), "lane-a", str(repo["lane_branch"]))
    assert spine == [repo["a1"]]


def test_presence_spine_without_a_lane_base_drops_every_carried_commit(repo: dict[str, str | Path]) -> None:
    """No first-claim stamp: the pre-#5788 reading (the mission branch carries the whole lane)."""
    assert rec._presence_spine(Path(repo["root"]), _scope(repo, stamp=None), "lane-a", str(repo["lane_branch"])) == []


def test_presence_spine_with_an_unreadable_lane_base_drops_every_carried_commit(repo: dict[str, str | Path]) -> None:
    assert rec._presence_spine(Path(repo["root"]), _scope(repo, stamp="0" * 40), "lane-a", str(repo["lane_branch"])) == []


def test_presence_spine_refuses_to_fall_back_when_the_mission_branch_range_is_unreadable(repo: dict[str, str | Path]) -> None:
    """Fail closed (#5792): an unreadable range never reads as 'the mission branch carries nothing' (the pre-#5788 authorship walk)."""
    scope = _scope(repo, stamp=str(repo["m1"]), carried=False)
    with pytest.raises(GitProbeError):
        rec._presence_spine(Path(repo["root"]), scope, "lane-a", str(repo["lane_branch"]))
    with pytest.raises(GitProbeError):
        rec._presence_lane_content(Path(repo["root"]), _MANIFEST, _LANE, _APPROVED, _empty_walk(repo), scope, frozenset())


def test_unreadable_mission_branch_range_refuses_the_claim_only_when_an_approved_code_lane_needs_it(repo: dict[str, str | Path]) -> None:
    unreadable = rec._presence_scope(Path(repo["root"]), _MANIFEST, frozenset(), base=str(repo["c0"]), coord_base_ref="no-such-branch", events=None)
    assert unreadable.carried is None, "an unreadable range is None, never an empty set"
    assert rec._presence_scope(Path(repo["root"]), _MANIFEST, frozenset(), base=str(repo["c0"]), coord_base_ref=str(repo["m2"]), events=None).carried

    refusal = rec._presence_range_unreadable_refusal(_MANIFEST, _APPROVED, unreadable, "no-such-branch")
    assert refusal is not None and "no-such-branch" in refusal and "Recovery: restore or repair that branch" in refusal
    not_approved = {"WP01": {"lane": "planned"}}
    assert rec._presence_range_unreadable_refusal(_MANIFEST, not_approved, unreadable, "no-such-branch") is None, "no approved code lane: nothing to measure"
    readable = _scope(repo, stamp=None)
    assert readable.carried is not None
    assert rec._presence_range_unreadable_refusal(_MANIFEST, _APPROVED, readable, str(repo["m2"])) is None


def _empty_walk(repo: dict[str, str | Path]) -> rec._LaneWalk:
    """lane-a's authorship walk from the mission-branch tip: empty, the mission branch already carries the lane."""
    return rec._LaneWalk(str(repo["m2"]), str(repo["lane_branch"]), [], set(), set())


def test_lane_content_holds_the_lanes_own_change_only(repo: dict[str, str | Path]) -> None:
    root = Path(repo["root"])
    content = rec._presence_lane_content(root, _MANIFEST, _LANE, _APPROVED, _empty_walk(repo), _scope(repo, stamp=str(repo["m1"])), frozenset())
    assert set(content.final_state) == {"src/added.py"}, "the scaffolding is no lane's content; the lane's own merged commit is"
    assert content.tip == repo["a1"]


def test_lane_content_subtracts_canceled_commits_measured_from_the_presence_base(repo: dict[str, str | Path]) -> None:
    """L1: a canceled commit on the presence spine is dropped even when the claim's own set (measured from the mission branch) misses it."""
    root = Path(repo["root"])
    scope = _scope(repo, stamp=str(repo["m1"]), canceled=frozenset({str(repo["a1"])}))
    content = rec._presence_lane_content(root, _MANIFEST, _LANE, _APPROVED, _empty_walk(repo), scope, frozenset())
    assert dict(content.final_state) == {}


def test_lane_content_reuses_the_authorship_walk_when_the_spines_agree(repo: dict[str, str | Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """L2: no second diff walk when the presence spine is the authorship spine."""
    root = Path(repo["root"])
    walk = rec._LaneWalk(str(repo["m1"]), str(repo["lane_branch"]), [str(repo["a1"])], {("src/added.py", "f" * 40)}, set())
    scope = rec._PresenceScope(base=str(repo["m1"]), carried=frozenset(), lane_bases={}, canceled=frozenset())

    def _no_second_walk(*_args: object) -> object:
        raise AssertionError("the authorship walk must be reused")

    monkeypatch.setattr(rec, "_final_authored_walk", _no_second_walk)
    content = rec._presence_lane_content(root, _MANIFEST, _LANE, _APPROVED, walk, scope, frozenset())
    assert dict(content.final_state) == {"src/added.py": "f" * 40}


def test_lane_content_without_a_presence_scope_is_the_authorship_walk(repo: dict[str, str | Path]) -> None:
    content = rec._presence_lane_content(Path(repo["root"]), _MANIFEST, _LANE, _APPROVED, _empty_walk(repo), None, frozenset())
    assert dict(content.final_state) == {}
