"""``WalkOnceMissionResolver`` answers like ``FsMissionResolver`` but walks ``kitty-specs/`` once (#6788).

The cross-mission retrospective summary resolved every Mission's slug through
``candidate_feature_dir_for_mission``, and each resolution walked the whole tree up to
five times, so the summary was quadratic in the number of Missions. These tests pin
that the request-scoped resolver gives exactly the answer, error type and ambiguity
candidates of ``FsMissionResolver`` for every handle form; that one instance walks the
tree at most once; that it is anchored like every status read (a lane worktree root
reads the main checkout, #6466); that the read primitive's raw-miss leg uses the
resolver it is given; and that ``build_summary`` walks once per call and still returns
the same snapshot.
"""

from __future__ import annotations

import subprocess
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from specify_cli.context import mission_resolver
from specify_cli.context.mission_resolver import (
    FsMissionResolver,
    ResolvedMission,
    WalkOnceMissionResolver,
)
from specify_cli.missions import _read_path_resolver
from specify_cli.retrospective import summary as summary_module
from specify_cli.retrospective.summary import build_summary
from tests.context._mission_tree import HANDLES, build_mission_tree, outcome, write_meta
from tests.retrospective.test_summary_tolerance import _make_completed_yaml

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    return build_mission_tree(tmp_path)


def _count_walks(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every ``_build_index`` call while still running the real walk."""
    calls: list[Path] = []
    real = mission_resolver._build_index

    def counting(root: Path) -> list[ResolvedMission]:
        calls.append(root)
        rows: list[ResolvedMission] = real(root)
        return rows

    monkeypatch.setattr(mission_resolver, "_build_index", counting)
    return calls


# ---------------------------------------------------------------------------
# Equivalence with FsMissionResolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", HANDLES)
def test_resolve_matches_fs_resolver_for_every_handle(tree: Path, handle: str) -> None:
    expected = outcome(lambda: FsMissionResolver(tree).resolve(handle))
    assert outcome(lambda: WalkOnceMissionResolver(tree).resolve(handle)) == expected


def test_one_instance_matches_fs_resolver_across_all_handles(tree: Path) -> None:
    """Reusing one instance (the memoized walk) changes no answer."""
    shared = WalkOnceMissionResolver(tree)
    for handle in HANDLES:
        expected = outcome(partial(FsMissionResolver(tree).resolve, handle))
        assert outcome(partial(shared.resolve, handle)) == expected, handle


def test_all_missions_matches_fs_resolver_and_is_a_copy(tree: Path) -> None:
    shared = WalkOnceMissionResolver(tree)
    first = shared.all_missions()
    assert first == FsMissionResolver(tree).all_missions()
    first.clear()
    assert shared.all_missions() == FsMissionResolver(tree).all_missions()


def test_a_failed_walk_is_not_memoized(tree: Path) -> None:
    """A walk that raises (non-string ``mission_id``) raises again, as the uncached walk does."""
    write_meta(tree / "kitty-specs" / "092-numeric-id", {"mission_id": 12345})
    shared = WalkOnceMissionResolver(tree)
    for _ in range(2):
        with pytest.raises(TypeError):
            shared.resolve("foo")


# ---------------------------------------------------------------------------
# Walk count
# ---------------------------------------------------------------------------


def test_one_instance_walks_at_most_once(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    walks = _count_walks(monkeypatch)
    shared = WalkOnceMissionResolver(tree)
    for handle in HANDLES:
        outcome(partial(shared.resolve, handle))
    shared.all_missions()
    assert len(walks) == 1


def test_fs_resolver_walks_per_call_as_control(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control for the test above: the uncached resolver walks on every non-exact handle."""
    walks = _count_walks(monkeypatch)
    fs = FsMissionResolver(tree)
    for handle in ("x", "foo", "missing"):
        outcome(partial(fs.resolve, handle))
    assert len(walks) == 3


def test_exact_directory_names_never_walk(tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    walks = _count_walks(monkeypatch)
    assert WalkOnceMissionResolver(tree).resolve("001-foo").mission_slug == "001-foo"
    assert walks == []


# ---------------------------------------------------------------------------
# Root anchoring (#6466)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _repo_with_lane_worktree(root: Path) -> tuple[Path, Path]:
    """A main checkout plus a registered lane worktree forked before a second Mission existed."""
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    write_meta(repo / "kitty-specs" / "001-early", {"mission_id": "01EARLYAAAAAAAAAAAAAAAAAAB"})
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    lane = repo / ".worktrees" / "001-early-lane-a"
    lane.parent.mkdir()
    _git(repo, "worktree", "add", "-q", "-b", "kitty/mission-001-early-lane-a", str(lane), "main")
    # Created on the main checkout after the lane forked: absent from the lane's copy.
    write_meta(repo / "kitty-specs" / "002-late", {"mission_id": "01LATEAAAAAAAAAAAAAAAAAAAC"})
    return repo, lane


def test_a_lane_worktree_root_reads_the_main_checkout(tmp_path: Path) -> None:
    """A lane root must not walk the lane's fork-time copy of ``kitty-specs/``."""
    repo, lane = _repo_with_lane_worktree(tmp_path)
    assert not (lane / "kitty-specs" / "002-late").exists()
    resolved = WalkOnceMissionResolver(lane).resolve("late")
    assert resolved.feature_dir.resolve() == (repo / "kitty-specs" / "002-late").resolve()
    slugs = {m.mission_slug for m in WalkOnceMissionResolver(lane).all_missions()}
    assert slugs == {"001-early", "002-late"}


def test_the_read_primitive_answers_alike_with_and_without_the_resolver_from_a_lane(tmp_path: Path) -> None:
    """``candidate_feature_dir_for_mission`` anchors the fresh resolver it builds; a passed one must agree."""
    _, lane = _repo_with_lane_worktree(tmp_path)
    for handle in ("late", "early", "002-late", "001-early", "01LATEAA"):
        expected = _read_path_resolver.candidate_feature_dir_for_mission(lane, handle)
        given = _read_path_resolver.candidate_feature_dir_for_mission(lane, handle, resolver=WalkOnceMissionResolver(lane))
        assert given == expected, handle


def test_anchoring_is_deferred_until_first_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An instance that is never asked anything never reads the worktree registry; one that is, reads it once."""
    calls: list[Path] = []

    def anchoring(root: Path) -> Path:
        calls.append(root)
        return root

    monkeypatch.setattr(_read_path_resolver, "canonical_status_read_root", anchoring)
    shared = WalkOnceMissionResolver(tmp_path)
    assert calls == []
    shared.all_missions()
    shared.all_missions()
    assert calls == [tmp_path]


# ---------------------------------------------------------------------------
# read_primary_meta threading
# ---------------------------------------------------------------------------


class _SpyResolver:
    def __init__(self, inner: WalkOnceMissionResolver) -> None:
        self.inner = inner
        self.handles: list[str] = []

    def resolve(self, handle: str) -> ResolvedMission:
        self.handles.append(handle)
        return self.inner.resolve(handle)

    def all_missions(self) -> list[ResolvedMission]:
        rows: list[ResolvedMission] = self.inner.all_missions()
        return rows


def test_read_primary_meta_threads_the_resolver(tree: Path) -> None:
    """A raw miss canonicalizes through the given resolver; the answer is unchanged."""
    spy = _SpyResolver(WalkOnceMissionResolver(tree))
    expected = _read_path_resolver.read_primary_meta(tree, "x-not-a-dir")
    assert _read_path_resolver.read_primary_meta(tree, "x-not-a-dir", resolver=spy) == expected
    assert spy.handles


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------


def _record(directory: Path, mission_id: str, slug: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "retrospective.yaml").write_text(_make_completed_yaml(mission_id=mission_id, slug=slug), encoding="utf-8")


def _events(directory: Path, name: str) -> None:
    (directory / "status.events.jsonl").write_text(f'{{"event_name": "{name}"}}\n', encoding="utf-8")


def _corpus(root: Path, count: int) -> Path:
    """Records whose slug resolves to nothing, to an exact directory, and only through the index."""
    specs = root / "kitty-specs"
    for i in range(count):
        mission_id = f"01KQ6YEGT4YBZ3GZF7X{i:07d}"
        _record(specs / mission_id, mission_id, f"walk-mission-{i:04d}")
    named = specs / "named-mission"
    write_meta(named, {"mission_id": "01KQ6YEGT4YBZ3GZF7XNAMED00", "mission_slug": "named-mission"})
    _record(named, "01KQ6YEGT4YBZ3GZF7XNAMED00", "named-mission")
    _events(named, "retrospective.proposal.generated")
    # The record's slug is the human slug of a numbered directory: the lookup misses
    # the exact-directory short-circuit and resolves at a lower ladder priority.
    for number, mission_id in (("080", "01KQ6YEGT4YBZ3GZF7XHVMAN01"), ("081", "01KQ6YEGT4YBZ3GZF7XHVMAN02")):
        directory = specs / f"{number}-human-{number}"
        write_meta(directory, {"mission_id": mission_id, "mission_slug": directory.name})
        _record(directory, mission_id, f"human-{number}")
        _events(directory, "retrospective.proposal.applied")
    return root


def _comparable(snapshot: Any) -> dict[str, Any]:
    data: dict[str, Any] = snapshot.model_dump()
    data.pop("generated_at", None)
    return data


def test_the_corpus_resolves_some_slugs_through_the_index(tmp_path: Path) -> None:
    """Without index-resolved slugs the equivalence below would only exercise misses."""
    root = _corpus(tmp_path, 3)
    resolved = FsMissionResolver(root).resolve("human-080")
    assert resolved.feature_dir == root / "kitty-specs" / "080-human-080"


def test_build_summary_walks_kitty_specs_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The #6788 regression: the walk count no longer grows with the number of Missions."""
    root = _corpus(tmp_path, 12)
    walks = _count_walks(monkeypatch)
    snapshot = build_summary(project_path=root)
    assert snapshot.mission_count == 15
    assert len(walks) == 1


def test_build_summary_shares_a_passed_resolver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller-supplied resolver is used, so a command can share one walk across its reads."""
    root = _corpus(tmp_path, 4)
    shared = WalkOnceMissionResolver(root)
    shared.all_missions()
    walks = _count_walks(monkeypatch)
    build_summary(project_path=root, resolver=shared)
    assert walks == []


def _record_lookups(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Path]]:
    """Record every ``(slug, resolved feature dir)`` the summary's per-Mission lookup returns."""
    lookups: list[tuple[str, Path]] = []
    real = summary_module.candidate_feature_dir_for_mission

    def recording(project_path: Path, mission_slug: str, **kwargs: Any) -> Path:
        resolved: Path = real(project_path, mission_slug, **kwargs)
        lookups.append((mission_slug, resolved))
        return resolved

    monkeypatch.setattr(summary_module, "candidate_feature_dir_for_mission", recording)
    return lookups


def test_build_summary_output_is_unchanged_by_the_shared_walk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The snapshot and every resolved Mission directory equal a fresh walk per lookup (pre-#6788).

    The snapshot alone cannot catch a wrong resolver answer: ``build_summary`` discards
    the proposal-event counts its lookups feed. So the resolved directories themselves
    are compared, lookup by lookup.
    """
    root = _corpus(tmp_path, 12)
    shared_lookups = _record_lookups(monkeypatch)
    shared = _comparable(build_summary(project_path=root))
    monkeypatch.undo()
    fresh_lookups = _record_lookups(monkeypatch)
    monkeypatch.setattr(mission_resolver, "WalkOnceMissionResolver", FsMissionResolver)
    assert _comparable(build_summary(project_path=root)) == shared
    assert shared_lookups, "the corpus must exercise the per-Mission lookup"
    assert any(directory.name == "080-human-080" for _, directory in shared_lookups)
    assert shared_lookups == fresh_lookups
