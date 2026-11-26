"""#7860: the planning lane's one write-branch rule (``mission_runtime.planning_write_ref``).

Before a default Mission (``topology_source: default``) lands, its planning lane writes to its
Mission branch (FR-061 extended to the planning lane, ADR 2026-11-06-3 Amendment 2026-11-25).
Every other Mission keeps today's write ref (``resolve_single_branch_write_ref``). Nothing falls
back silently (NFR-002): an unreadable ``meta.json`` or landing record raises
``PlanningWriteRefUnavailable``; a missing local ``meta.json`` while a branch's own ``meta.json``
records it as the Mission branch raises ``PlanningCheckoutMissing``; only a Mission with no
``meta.json`` anywhere (legacy) keeps the target. The placement reader stays non-raising.
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


def _init(repo: Path) -> None:
    repo.mkdir()
    git_out(repo, "init", "-q", "-b", _TARGET)
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-q", "-m", "init")


def _write_meta(checkout: Path, slug: str, meta: dict[str, object] | str, *, commit: bool = True) -> Path:
    mission_dir = checkout / "kitty-specs" / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(meta if isinstance(meta, str) else json.dumps(meta), encoding="utf-8")
    if commit:
        git_out(checkout, "add", "-A")
        git_out(checkout, "commit", "-q", "-m", "meta")
    return mission_dir


def _repo(tmp_path: Path, meta: dict[str, object] | str | None) -> Path:
    repo = tmp_path / "repo"
    _init(repo)
    if meta is not None:
        _write_meta(repo, _SLUG, meta)
    return repo


def _meta(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {"mission_slug": _SLUG, "mission_id": "01M8AAAAAAAAAAAAAAAAAAAAAA", "target_branch": _TARGET, "topology": "lanes_with_coord"}
    base.update(fields)
    return base


def _default_meta(slug: str, branch: str) -> dict[str, object]:
    return {
        "mission_slug": slug,
        "mission_id": "01M8AAAAAAAAAAAAAAAAAAAAAA",
        "target_branch": _TARGET,
        "topology": "lanes_with_coord",
        "topology_source": "default",
        "mission_branch": branch,
        "coordination_branch": branch,
    }


# ---------------------------------------------------------------- the rule


def test_a_default_mission_before_landing_writes_on_its_mission_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH, coordination_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert ref == mission_runtime.PlanningWriteRef(branch=_MISSION_BRANCH, on_mission_branch=True, landed=False)


def test_a_landed_default_mission_writes_on_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH, merged_at="2026-11-25T00:00:00+00:00"))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert ref == mission_runtime.PlanningWriteRef(branch=_TARGET, on_mission_branch=False, landed=True)


def test_an_explicit_topology_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(mission_branch=_MISSION_BRANCH, coordination_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


def test_an_explicit_single_branch_keeps_its_minted_write_branch_off_the_default_rule(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology="single_branch", mission_branch=_MISSION_BRANCH))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_MISSION_BRANCH, False)


def test_a_default_mission_without_a_mission_branch_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _meta(topology_source="default"))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


def test_the_rule_and_the_primary_ref_share_one_predicate() -> None:
    """C-004: ``default_mission_primary_ref`` and ``planning_write_ref`` read ``default_mission_rule_applies``."""
    from mission_runtime.resolution import default_mission_primary_ref, default_mission_rule_applies

    cases = [
        ("default", _MISSION_BRANCH, False),
        ("default", _MISSION_BRANCH, True),
        (None, _MISSION_BRANCH, False),
        ("default", "", False),
        ("default", None, False),
    ]
    for case in cases:
        expected = _MISSION_BRANCH if default_mission_rule_applies(*case) else _TARGET
        assert default_mission_primary_ref(*case, _TARGET) == expected, case


# ---------------------------------------------------------------- fail closed


def test_a_malformed_meta_refuses(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "{not json")

    with pytest.raises(mission_runtime.PlanningWriteRefUnavailable, match="meta.json is unreadable"):
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)


def test_an_unreadable_landing_record_reads_as_not_landed_and_keeps_the_mission_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``mission_has_landed`` is non-raising: a landing record it cannot read answers "not landed".

    Non-vacuous: the meta carries ``merged_at``, so a readable record answers "landed" and the
    target (see the landed test). The Mission branch is kept; a reader of a deleted Mission
    branch then fails closed downstream (the evidence window, WP04).
    """
    import specify_cli.status as status
    from specify_cli.status import StoreError

    repo = _repo(tmp_path, _meta(topology_source="default", mission_branch=_MISSION_BRANCH, merged_at="2026-11-25T00:00:00+00:00"))

    def _unreadable(_dir: Path) -> bool:
        raise StoreError("the lifecycle log cannot be read")

    monkeypatch.setattr(status, "is_mission_merged", _unreadable)

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch, ref.landed) == (_MISSION_BRANCH, True, False)


def test_the_placement_reader_stays_non_raising_on_a_malformed_meta(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "{not json")

    assert _default_mission_facts(repo, _SLUG) == (None, None, False)


# ---------------------------------------------------------------- missing meta.json


def test_a_legacy_mission_with_no_meta_anywhere_keeps_the_target(tmp_path: Path) -> None:
    repo = _repo(tmp_path, None)

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


@pytest.mark.parametrize(
    ("slug", "branch"),
    [
        pytest.param(_SLUG, _MISSION_BRANCH, id="slug-with-mid8"),
        # Review finding 1: a modern slug without a mid8 has branch ``kitty/mission-<slug>-<mid8>``;
        # the legacy ``mission_branch_name(slug)`` form would miss it.
        pytest.param("kernel-clock-single-door", "kitty/mission-kernel-clock-single-door-01M8AAAA", id="slug-without-mid8"),
    ],
)
def test_a_mission_branch_with_no_checkout_refuses_and_names_the_real_branch(tmp_path: Path, slug: str, branch: str) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    git_out(repo, "branch", branch)
    holder = tmp_path / "holder"
    git_out(repo, "worktree", "add", "-q", str(holder), branch)
    _write_meta(holder, slug, _default_meta(slug, branch))
    git_out(repo, "worktree", "remove", "--force", str(holder))

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(repo, slug, _TARGET)

    assert refused.value.mission_branch == branch
    assert refused.value.error_code == "PLANNING_CHECKOUT_MISSING"
    assert f"spec-kitty doctor coordination --mission {slug} --fix" in str(refused.value)


def test_a_lane_branch_carrying_the_missions_meta_is_not_taken_for_the_mission_branch(tmp_path: Path) -> None:
    """A lane branch that merged the Mission branch carries its ``meta.json``, which names another branch."""
    repo = tmp_path / "repo"
    _init(repo)
    lane = f"{_MISSION_BRANCH}-lane-a"
    git_out(repo, "branch", lane)
    holder = tmp_path / "holder"
    git_out(repo, "worktree", "add", "-q", str(holder), lane)
    _write_meta(holder, _SLUG, _default_meta(_SLUG, _MISSION_BRANCH))
    git_out(repo, "worktree", "remove", "--force", str(holder))

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


@pytest.mark.parametrize("broken", ["run_git", "blob_at"])
def test_a_git_failure_while_probing_the_mission_branches_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str) -> None:
    import kernel.git
    from kernel.git import GitCommandError

    repo = _repo(tmp_path, None)
    git_out(repo, "branch", _MISSION_BRANCH)
    real = getattr(kernel.git, broken)

    def _failing(cwd: Path, *args: object, **kwargs: object) -> object:
        if broken == "run_git" and args[:1] != ("for-each-ref",):
            return real(cwd, *args, **kwargs)
        raise GitCommandError(argv=(broken,), cwd=cwd, returncode=128, stderr="boom")

    monkeypatch.setattr(kernel.git, broken, _failing)

    with pytest.raises(mission_runtime.PlanningWriteRefUnavailable, match="could not probe the Mission branches"):
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)


# ---------------------------------------------------------------- review cycle 2


def _branch_with_meta(repo: Path, tmp_path: Path, branch: str, meta: dict[str, object], slug: str = _SLUG) -> None:
    """Commit *meta* for *slug* on a new local *branch* without leaving a checkout behind."""
    git_out(repo, "branch", branch)
    holder = tmp_path / f"holder-{branch.replace('/', '-')}"
    git_out(repo, "worktree", "add", "-q", str(holder), branch)
    _write_meta(holder, slug, meta)
    git_out(repo, "worktree", "remove", "--force", str(holder))


def test_an_explicit_single_branch_mission_off_its_branch_keeps_todays_behaviour(tmp_path: Path) -> None:
    """FR-006: a branch carrying an explicit Mission's meta never makes the probe refuse."""
    repo = tmp_path / "repo"
    _init(repo)
    branch = "kitty/mission-sb-01M8BBBB"
    _branch_with_meta(repo, tmp_path, branch, {"mission_slug": _SLUG, "target_branch": _TARGET, "topology": "single_branch", "mission_branch": branch})

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


def test_a_landed_default_missions_branch_is_not_claimed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _branch_with_meta(repo, tmp_path, _MISSION_BRANCH, _default_meta(_SLUG, _MISSION_BRANCH) | {"merged_at": "2026-11-25T00:00:00+00:00"})

    ref = mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (ref.branch, ref.on_mission_branch) == (_TARGET, False)


def test_a_fresh_clone_with_a_remote_only_mission_branch_refuses_with_the_fetch_remedy(tmp_path: Path) -> None:
    """NFR-002: the Mission branch exists only as ``origin/<branch>``; never a silent fallback to the target."""
    upstream = tmp_path / "upstream"
    _init(upstream)
    _branch_with_meta(upstream, tmp_path, _MISSION_BRANCH, _default_meta(_SLUG, _MISSION_BRANCH))
    clone = tmp_path / "clone"
    git_out(tmp_path, "clone", "-q", str(upstream), str(clone))

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(clone, _SLUG, _TARGET)

    assert (refused.value.mission_branch, refused.value.remote) == (_MISSION_BRANCH, "origin")
    assert f"git branch {_MISSION_BRANCH} origin/{_MISSION_BRANCH}" in str(refused.value)
    assert f"spec-kitty doctor coordination --mission {_SLUG} --fix" in str(refused.value)


def test_a_local_mission_branch_wins_over_its_remote_tracking_copy(tmp_path: Path) -> None:
    upstream = tmp_path / "upstream"
    _init(upstream)
    _branch_with_meta(upstream, tmp_path, _MISSION_BRANCH, _default_meta(_SLUG, _MISSION_BRANCH))
    clone = tmp_path / "clone"
    git_out(tmp_path, "clone", "-q", str(upstream), str(clone))
    git_out(clone, "branch", _MISSION_BRANCH, f"origin/{_MISSION_BRANCH}")

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(clone, _SLUG, _TARGET)

    assert refused.value.remote is None
    assert "git branch" not in str(refused.value)


def test_a_tag_sharing_the_branch_name_does_not_hide_the_mission_branch(tmp_path: Path) -> None:
    """``refname:short`` would print ``heads/<branch>`` here; full refnames keep the match."""
    repo = tmp_path / "repo"
    _init(repo)
    _branch_with_meta(repo, tmp_path, _MISSION_BRANCH, _default_meta(_SLUG, _MISSION_BRANCH))
    git_out(repo, "tag", _MISSION_BRANCH)

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert refused.value.mission_branch == _MISSION_BRANCH


# ---------------------------------------------------------------- review cycle 3


def test_an_uncoordinated_default_mission_gets_the_switch_remedy_not_the_coordination_doctor(tmp_path: Path) -> None:
    """A default Mission settled ``single_branch`` has no coordination branch: switch the root checkout back."""
    repo = tmp_path / "repo"
    _init(repo)
    meta = _default_meta(_SLUG, _MISSION_BRANCH) | {"topology": "single_branch"}
    del meta["coordination_branch"]
    _branch_with_meta(repo, tmp_path, _MISSION_BRANCH, meta)

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert refused.value.coordinated is False
    assert str(refused.value) == (
        f"PLANNING_CHECKOUT_MISSING: the Mission branch {_MISSION_BRANCH} of Mission {_SLUG!r} is not checked out anywhere; "
        "its planning work is written there until it lands. Its planning work is done in the repository root checkout: "
        f"run `git switch {_MISSION_BRANCH}` there, then retry."
    )


def test_a_remote_whose_name_contains_a_slash_is_still_probed(tmp_path: Path) -> None:
    """NFR-002: ``refs/remotes/my/fork/kitty/mission-*`` is found; the remote is ``my/fork``."""
    upstream = tmp_path / "upstream"
    _init(upstream)
    _branch_with_meta(upstream, tmp_path, _MISSION_BRANCH, _default_meta(_SLUG, _MISSION_BRANCH))
    repo = tmp_path / "repo"
    _init(repo)
    git_out(repo, "remote", "add", "my/fork", str(upstream))
    git_out(repo, "fetch", "-q", "my/fork")

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert (refused.value.mission_branch, refused.value.remote) == (_MISSION_BRANCH, "my/fork")
    assert f"git branch {_MISSION_BRANCH} my/fork/{_MISSION_BRANCH}" in str(refused.value)


def test_remote_refs_off_the_mission_namespace_are_ignored() -> None:
    from mission_runtime.resolution import _branch_and_remote

    assert _branch_and_remote("refs/remotes/origin/HEAD") is None
    assert _branch_and_remote("refs/remotes/origin/main") is None
    assert _branch_and_remote(f"refs/remotes/a/b/{_MISSION_BRANCH}") == (_MISSION_BRANCH, "a/b")
    assert _branch_and_remote(f"refs/heads/{_MISSION_BRANCH}") == (_MISSION_BRANCH, None)


def test_a_stored_coordination_topology_without_a_coordination_branch_field_gets_the_doctor_remedy(tmp_path: Path) -> None:
    """Review cycle 4: one coordination check (the stored topology), never the ``coordination_branch`` field alone."""
    repo = tmp_path / "repo"
    _init(repo)
    meta = _default_meta(_SLUG, _MISSION_BRANCH)
    del meta["coordination_branch"]
    _branch_with_meta(repo, tmp_path, _MISSION_BRANCH, meta)

    with pytest.raises(mission_runtime.PlanningCheckoutMissing) as refused:
        mission_runtime.planning_write_ref(repo, _SLUG, _TARGET)

    assert refused.value.coordinated is True
    assert str(refused.value) == (
        f"PLANNING_CHECKOUT_MISSING: the Mission branch {_MISSION_BRANCH} (the coordination branch) of Mission {_SLUG!r} "
        "is not checked out anywhere; its planning work is written there until it lands. To restore the coordination "
        f"worktree, run `spec-kitty doctor coordination --mission {_SLUG} --fix`, then retry."
    )
