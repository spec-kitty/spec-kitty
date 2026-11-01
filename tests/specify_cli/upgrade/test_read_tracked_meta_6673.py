"""#6673: the tracked ``meta.json`` read and the baseline seed that keeps the Mission's identity.

The defect these tests pin: a Mission's ``meta.json`` is tracked by git but absent from the
working tree (an accidental ``rm``, a sparse/partial checkout). The upgrade used to rebuild a
baseline from the directory name and then mint a fresh ``mission_id`` into it, so the Mission
silently acquired a second identity and its history was orphaned.

:func:`specify_cli.mission_metadata.read_tracked_meta` is the one answer to "what does git hold
for this Mission's ``meta.json``"; :func:`specify_cli.upgrade.feature_meta.build_baseline_feature_meta`
seeds itself from it. Every absence assertion here is paired with a positive control on the same
fixture (a readable tracked copy), so a probe that cannot see anything cannot pass by accident.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.mission_metadata import TrackedMeta, read_tracked_meta
from specify_cli.upgrade.feature_meta import build_baseline_feature_meta

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "tracked-meta-01REALMIS"
_MISSION_ID = "01REALMISZZZZZZZZZZZZZZZZZ"
_META = {
    "mission_id": _MISSION_ID,
    "mission_slug": _SLUG,
    "slug": _SLUG,
    "friendly_name": "tracked meta",
    "mission_type": "software-dev",
    "target_branch": "main",
    "created_at": "2026-01-01T00:00:00+00:00",
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _commit_meta(root: Path, slug: str = _SLUG, meta: dict[str, object] | None = None) -> Path:
    """Write and commit a Mission's ``meta.json`` + ``spec.md``; return the Mission directory."""
    mission_dir = root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps(meta or _META, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"mission {slug}")
    return mission_dir


def test_committed_meta_is_read_back_after_the_working_tree_copy_is_deleted(tmp_path: Path) -> None:
    mission_dir = _commit_meta(_repo(tmp_path))
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    assert tracked.unavailable is False
    assert tracked.meta is not None
    assert tracked.meta["mission_id"] == _MISSION_ID
    # Positive control on the same fixture: restore the working-tree copy and the reader sees the
    # same content, so the assertion above cannot pass because the probe sees nothing at all.
    _git(mission_dir, "checkout", "--", "meta.json")
    assert (mission_dir / "meta.json").is_file()
    assert read_tracked_meta(mission_dir).meta == tracked.meta

    # A staged edit is not what `git checkout --` or HEAD would give back: the reader refuses rather than
    # write HEAD's bytes over it, and the notice's remedy keeps the edit.
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    (mission_dir / "meta.json").write_text(json.dumps({**_META, "friendly_name": "staged edit"}) + "\n", encoding="utf-8")
    _git(mission_dir, "add", "meta.json")
    (mission_dir / "meta.json").unlink()
    staged = read_tracked_meta(mission_dir)
    assert (staged.meta, staged.unavailable, staged.staged_differs) == (None, True, True)
    classified = classify_missing_tracked_meta(mission_dir, mission_dir.parent.parent)
    assert classified is not None
    assert classified.refuse is True
    assert "staged edit" in classified.notice
    assert "git restore --staged" in classified.notice


def test_a_staged_only_meta_is_refused_as_index_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text(json.dumps(_META) + "\n", encoding="utf-8")
    _git(root, "add", "-A")
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    assert tracked.meta is None
    assert tracked.unavailable is True
    assert tracked.index_only is True
    # Positive control: committing the staged file makes the same read return its content.
    _git(root, "commit", "-q", "-m", "stage the mission")
    committed = read_tracked_meta(mission_dir)
    assert committed.meta is not None
    assert committed.meta["mission_id"] == _MISSION_ID
    assert committed.index_only is False


def test_a_corrupt_committed_meta_is_refused(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{not json\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "corrupt mission")
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    assert tracked.meta is None
    assert tracked.unavailable is True
    assert tracked.index_only is False


def test_an_unborn_head_reports_nothing_committed(tmp_path: Path) -> None:
    root = tmp_path / "unborn"
    root.mkdir()
    _git(root, "init", "-q")
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text(json.dumps(_META) + "\n", encoding="utf-8")
    _git(root, "add", "-A")
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    # git knows the path (index) but HEAD has no identity to give: a refusal, never a mint.
    assert tracked.meta is None
    assert tracked.unavailable is True
    assert tracked.index_only is True


def test_nothing_tracked_is_not_a_refusal(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    legacy = root / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "legacy")

    assert read_tracked_meta(legacy) == TrackedMeta(None, unavailable=False)

    outside = tmp_path / "not-a-repo"
    (outside / "kitty-specs" / _SLUG).mkdir(parents=True)
    assert read_tracked_meta(outside / "kitty-specs" / _SLUG) == TrackedMeta(None, unavailable=False)


def test_a_nested_mission_reads_its_own_tracked_path(tmp_path: Path) -> None:
    """The checkout prefix must be honoured (and its trailing newline stripped) for a nested project."""
    root = _repo(tmp_path)
    nested = root / "packages" / "inner"
    mission_dir = nested / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps(_META) + "\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "nested mission")
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    assert tracked.unavailable is False
    assert tracked.meta is not None
    assert tracked.meta["mission_id"] == _MISSION_ID


def test_the_baseline_builder_keeps_the_tracked_identity(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    (mission_dir / "meta.json").unlink()

    built = build_baseline_feature_meta(mission_dir, root)

    assert built is not None
    assert built["mission_id"] == _MISSION_ID
    assert built["target_branch"] == "main"
    assert built["created_at"] == _META["created_at"]


def test_the_baseline_builder_writes_nothing_for_an_unreadable_tracked_meta(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{not json\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "corrupt")
    (mission_dir / "meta.json").unlink()

    assert build_baseline_feature_meta(mission_dir, root) is None


def test_the_baseline_builder_still_repairs_a_pre_identity_mission(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    legacy = root / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "legacy")

    built = build_baseline_feature_meta(legacy, root)

    assert built is not None
    assert "mission_id" not in built  # identity minting stays with the backfill step
    assert built["slug"] == "legacy-mission"
    assert built["mission_type"] == "software-dev"


def test_a_present_copy_that_lost_its_identity_gets_the_tracked_one_back(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    present = dict(_META)
    present.pop("mission_id")
    present["friendly_name"] = "locally edited"
    (mission_dir / "meta.json").write_text(json.dumps(present, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    # `existing_meta` is what the sweep passes in from the working-tree copy.
    built = build_baseline_feature_meta(mission_dir, root, existing_meta=present)

    assert built is not None
    assert built["mission_id"] == _MISSION_ID
    assert built["friendly_name"] == "locally edited"  # only the identity is taken from git


def test_a_present_copy_with_its_identity_is_left_alone(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    local_id = "01LOCALONLYZZZZZZZZZZZZZZZ"
    present = dict(_META, mission_id=local_id)
    (mission_dir / "meta.json").write_text(json.dumps(present, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    built = build_baseline_feature_meta(mission_dir, root, existing_meta=present)

    assert built is not None
    assert built["mission_id"] == local_id


def test_a_path_component_with_leading_space_still_reads_the_tracked_copy(tmp_path: Path) -> None:
    """The prefix's trailing newline is removed, but nothing else: a leading space is path data."""
    root = _repo(tmp_path)
    mission_dir = root / " kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps(_META) + "\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "space-prefixed mission")
    (mission_dir / "meta.json").unlink()

    tracked = read_tracked_meta(mission_dir)

    assert tracked.unavailable is False
    assert tracked.meta is not None
    assert tracked.meta["mission_id"] == _MISSION_ID


def test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked(tmp_path: Path) -> None:
    """A `.git` anchor with git refusing (dubious ownership, garbled repo) must refuse, not fabricate."""
    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    (mission_dir / "meta.json").unlink()
    # Replace the real .git directory with a marker file git cannot follow: git exits 128 with
    # "not a git repository", the same message a non-repository prints.
    git_dir = root / ".git"
    for child in sorted(git_dir.rglob("*"), reverse=True):
        child.unlink() if child.is_file() or child.is_symlink() else child.rmdir()
    git_dir.rmdir()
    (root / ".git").write_text("gitdir: /nonexistent/gitdir\n", encoding="utf-8")

    tracked = read_tracked_meta(mission_dir)

    assert tracked.meta is None
    assert tracked.unavailable is True, "a refusing git was read as 'nothing tracked' (the fabricating branch)"


def test_the_refusal_notice_names_the_index_only_case(tmp_path: Path) -> None:
    """US2 Scenario 3: the staged-only refusal says so, instead of claiming git holds nothing."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text(json.dumps(_META) + "\n", encoding="utf-8")
    _git(root, "add", "-A")
    (mission_dir / "meta.json").unlink()

    classified = classify_missing_tracked_meta(mission_dir, root)

    assert classified is not None
    assert classified.refuse is True
    assert "only in the index (not committed)" in classified.notice
    assert f"git checkout -- kitty-specs/{_SLUG}/meta.json" in classified.notice


def test_the_refusal_notice_for_a_corrupt_committed_copy_does_not_prescribe_checkout_alone(tmp_path: Path) -> None:
    """`git checkout --` would restore the same unusable bytes, so the notice must say to repair it."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{not json\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "corrupt")
    (mission_dir / "meta.json").unlink()

    classified = classify_missing_tracked_meta(mission_dir, root)

    assert classified is not None
    assert classified.refuse is True
    assert "not a JSON object" in classified.notice
    assert f"git show HEAD:kitty-specs/{_SLUG}/meta.json" in classified.notice
