"""Unit tests for ``specify_cli.lanes.lane_tip`` (#5115, ``contracts/lane-work-tip.md``).

Real tmp git repos throughout (C-c: no independent repos compared by HEAD --
every scenario is a single repo with a shared history, matching the
production ``is_absorbed(repo_root, tip, target, base)`` contract exactly).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from specify_cli.lanes.models import ExecutionLane

from specify_cli.policy.lane_tip_recorder import install_lane_tip_recorder
from specify_cli.lanes.lane_tip import (
    AbsorptionUnsupported,
    clear_tip,
    is_absorbed,
    read_tip,
    record_tip,
    record_tip_for_wp,
    tip_ref,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def test_tip_ref_names_the_hidden_namespace() -> None:
    assert tip_ref("kitty/mission-foo-lane-a") == "refs/spec-kitty/lane-tip/kitty/mission-foo-lane-a"


def test_record_and_read_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-q", "-b", "kitty/mission-foo-lane-a")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "work")
    head = _rev(repo, "HEAD")

    recorded = record_tip(repo, "kitty/mission-foo-lane-a")

    assert recorded == head
    assert read_tip(repo, "kitty/mission-foo-lane-a") == head


def test_record_with_explicit_sha_does_not_need_a_live_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    sha = _rev(repo, "HEAD")

    recorded = record_tip(repo, "kitty/mission-foo-lane-gone", sha=sha)

    assert recorded == sha
    assert read_tip(repo, "kitty/mission-foo-lane-gone") == sha


def test_record_returns_none_for_a_branch_that_does_not_resolve(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert record_tip(repo, "kitty/mission-foo-lane-nope") is None
    assert read_tip(repo, "kitty/mission-foo-lane-nope") is None


def test_read_tip_returns_none_when_never_recorded(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    assert read_tip(repo, "kitty/mission-foo-lane-a") is None


def test_clear_tip_deletes_the_ref_and_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    sha = _rev(repo, "HEAD")
    record_tip(repo, "kitty/mission-foo-lane-a", sha=sha)
    assert read_tip(repo, "kitty/mission-foo-lane-a") == sha

    clear_tip(repo, "kitty/mission-foo-lane-a")
    assert read_tip(repo, "kitty/mission-foo-lane-a") is None

    # Idempotent: clearing an already-absent ref does not raise.
    clear_tip(repo, "kitty/mission-foo-lane-a")
    assert read_tip(repo, "kitty/mission-foo-lane-a") is None


def test_is_absorbed_true_when_tip_equals_base_and_the_recorder_is_active(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    base = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=base, target="main", base=base) is True


def test_is_absorbed_false_when_tip_equals_base_but_no_recorder_is_installed(tmp_path: Path) -> None:
    """``tip == base`` proves "no work" only if commits WOULD have moved the tip.

    Without the recorder, work committed on the lane never advanced the tip ref,
    so an unmoved tip is no evidence of an empty lane (the #5115 fail-open).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=base, target="main", base=base) is False


def test_is_absorbed_false_when_tip_equals_base_under_a_foreign_post_commit_hook(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    install_lane_tip_recorder(repo)  # leaves the foreign hook untouched
    base = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=base, target="main", base=base) is False


def test_is_absorbed_false_when_tip_equals_base_and_the_recorder_hook_is_not_executable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    install_lane_tip_recorder(repo)
    (repo / ".git" / "hooks" / "post-commit").chmod(0o644)
    base = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=base, target="main", base=base) is False


def test_is_absorbed_true_when_tip_is_ancestor_of_target(tmp_path: Path) -> None:
    """A real (non-squash) merge already carried the lane's tip into target."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "lane.txt").write_text("work\n", encoding="utf-8")
    _git(repo, "add", "lane.txt")
    _git(repo, "commit", "-q", "-m", "lane work")
    tip = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "--no-ff", "-q", "-m", "merge lane", "lane")

    assert is_absorbed(repo, tip=tip, target="main", base=base) is True


def test_is_absorbed_true_for_a_squash_absorbed_lane_with_later_unrelated_target_edits(tmp_path: Path) -> None:
    """The architecture lens's own verified case: squash + unrelated edits still absorbed."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "lane commit 1")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-q", "-m", "lane commit 2")
    tip = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "--squash", "-q", "lane")
    _git(repo, "commit", "-q", "-m", "squash lane")
    # Later, unrelated target-branch progress.
    (repo / "unrelated.txt").write_text("later\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-q", "-m", "later unrelated work")

    assert is_absorbed(repo, tip=tip, target="main", base=base) is True


def test_is_absorbed_false_for_destroyed_unique_work(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "unique.txt").write_text("never merged\n", encoding="utf-8")
    _git(repo, "add", "unique.txt")
    _git(repo, "commit", "-q", "-m", "unique lane work")
    tip = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=tip, target="main", base=base) is False


def test_is_absorbed_false_on_conflict(tmp_path: Path) -> None:
    """Contract: conflict means not absorbed (fails closed, never a guess)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "seed.txt").write_text("lane change\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "lane conflicting edit")
    tip = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "main")
    (repo / "seed.txt").write_text("target change\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "target conflicting edit")

    assert is_absorbed(repo, tip=tip, target="main", base=base) is False


def test_is_absorbed_skips_the_base_leg_when_base_is_none(tmp_path: Path) -> None:
    """``base=None`` (a deleted WorkspaceContext) never produces a false ``tip == base`` match."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "unique.txt").write_text("never merged\n", encoding="utf-8")
    _git(repo, "add", "unique.txt")
    _git(repo, "commit", "-q", "-m", "unique lane work")
    tip = _rev(repo, "HEAD")

    assert is_absorbed(repo, tip=tip, target="main", base=None) is False


def test_is_absorbed_raises_absorption_unsupported_on_old_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    base = _rev(repo, "HEAD")
    _git(repo, "checkout", "-q", "-b", "lane")
    (repo / "unique.txt").write_text("work\n", encoding="utf-8")
    _git(repo, "add", "unique.txt")
    _git(repo, "commit", "-q", "-m", "lane work")
    tip = _rev(repo, "HEAD")

    monkeypatch.setattr("specify_cli.lanes.lane_tip._git_supports_merge_tree_write_tree", lambda _repo_root: False)

    with pytest.raises(AbsorptionUnsupported):
        is_absorbed(repo, tip=tip, target="main", base=base)


# ---------------------------------------------------------------------------
# record_tip_for_wp -- safety branches (#5115 review cycle 3, Issue 1 / M9)
#
# review-feedback-3.md's mutation M9 removed BOTH the planning-lane skip
# (``or is_planning_lane(lane)``) AND the broad ``except Exception: return``
# swallow together and found all tests green. The two lines are NOT
# independently observable through a plain "does it raise" test, because
# with the swallow still present, removing ONLY the skip is masked (the
# ValueError ``code_lane_branch_name`` raises for the planning lane id is
# still caught). So M9-a (the skip) needs a white-box spy that fails via
# ``pytest.fail`` -- a ``BaseException``, NOT an ``Exception`` subclass, so
# the production swallow cannot mask it -- while M9-b (the swallow) is
# caught by the corrupt-lanes.json case below, independent of the skip.
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path, mission_slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        f'{{"mission_id": "{mission_slug}", "mission_slug": "{mission_slug}", "topology": "lanes", "target_branch": "main"}}\n',
        encoding="utf-8",
    )


def _write_lanes(feature_dir: Path, mission_slug: str, lanes: list[ExecutionLane]) -> None:
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-01-01T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)


def _no_lane_tip_refs_exist(repo: Path) -> bool:
    """True iff NO ``refs/spec-kitty/lane-tip/*`` ref exists anywhere in *repo*."""
    result = subprocess.run(
        ["git", "-C", str(repo), "for-each-ref", "refs/spec-kitty/lane-tip/"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == ""


def test_record_tip_for_wp_no_op_when_lanes_json_missing(tmp_path: Path) -> None:
    """No ``lanes.json`` at all -- ``read_lanes_json`` returns ``None``."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-missing-lanes"
    _write_meta(repo / "kitty-specs" / mission_slug, mission_slug)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: meta.json only")

    record_tip_for_wp(repo, mission_slug, "WP01")

    assert _no_lane_tip_refs_exist(repo)


def test_record_tip_for_wp_no_op_when_lanes_json_corrupt(tmp_path: Path) -> None:
    """A malformed ``lanes.json`` raises ``CorruptLanesError`` -- M9-b's independent catcher."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-corrupt-lanes"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    (feature_dir / "lanes.json").write_text("{not valid json", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: corrupt lanes.json")

    record_tip_for_wp(repo, mission_slug, "WP01")

    assert _no_lane_tip_refs_exist(repo)


def test_record_tip_for_wp_no_op_when_wp_not_in_any_lane(tmp_path: Path) -> None:
    from specify_cli.lanes.models import ExecutionLane

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-wp-not-in-lane"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    _write_lanes(
        feature_dir,
        mission_slug,
        [ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: lanes.json")

    record_tip_for_wp(repo, mission_slug, "WP99")

    assert _no_lane_tip_refs_exist(repo)


def test_record_tip_for_wp_no_op_when_lane_branch_does_not_exist(tmp_path: Path) -> None:
    """The lane resolves, but its branch was never created -- ``record_tip``'s own
    ``rev-parse`` returns ``None``, quietly, with nothing written.
    """
    from specify_cli.lanes.models import ExecutionLane

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-no-branch"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    _write_lanes(
        feature_dir,
        mission_slug,
        [ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: lanes.json")

    record_tip_for_wp(repo, mission_slug, "WP01")

    assert _no_lane_tip_refs_exist(repo)


def test_record_tip_for_wp_skips_planning_lane(tmp_path: Path) -> None:
    """A planning_artifact WP (repo-root lane) is skipped -- no raise, no ref."""
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-planning-lane"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    _write_lanes(
        feature_dir,
        mission_slug,
        [ExecutionLane(lane_id=PLANNING_LANE_ID, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: lanes.json with the planning lane")

    record_tip_for_wp(repo, mission_slug, "WP01")

    assert _no_lane_tip_refs_exist(repo)


def test_record_tip_for_wp_planning_lane_never_resolves_a_branch_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M9-a: the planning-lane skip must short-circuit BEFORE
    ``code_lane_branch_name`` is ever attempted -- independent of the M9-b
    swallow. The spy raises via ``pytest.fail`` (a ``BaseException``, not an
    ``Exception``), so ``record_tip_for_wp``'s broad ``except Exception``
    cannot mask a call that should never happen: removing the skip alone
    (M9-a) makes this test red even with the swallow left intact.
    """
    from specify_cli.lanes import branch_naming
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane

    def _must_not_be_called(*_args: object, **_kwargs: object) -> str:
        pytest.fail("code_lane_branch_name must not be called for the planning lane (M9-a)")

    monkeypatch.setattr(branch_naming, "code_lane_branch_name", _must_not_be_called)

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "m9-planning-lane-spy"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    _write_lanes(
        feature_dir,
        mission_slug,
        [ExecutionLane(lane_id=PLANNING_LANE_ID, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: lanes.json with the planning lane")

    record_tip_for_wp(repo, mission_slug, "WP01")  # must return quietly, never call the spy

    assert _no_lane_tip_refs_exist(repo)
