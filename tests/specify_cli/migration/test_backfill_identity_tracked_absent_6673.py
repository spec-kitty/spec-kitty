"""#6673: ``backfill_mission`` never mints over an identity git already holds.

Three shapes, all reachable through ``migrate backfill-identity`` regardless of which ``upgrade``
migrations still run: a tracked ``meta.json`` missing from the working tree is restored from git,
a present copy that lost its ``mission_id`` takes the tracked one back, and a copy git cannot give
back is refused with the restore command. The controls on the same fixtures keep the pre-identity
behaviour: a folder git holds nothing for still has its identity minted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.migration.backfill_identity import backfill_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "tracked-meta-01REALMIS"
_MISSION_ID = "01REALMISZZZZZZZZZZZZZZZZZ"


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


def _mission(root: Path) -> Path:
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "friendly_name": "tracked meta",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "mission")
    return mission_dir


def test_a_tracked_absent_meta_is_restored_with_its_identity(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    (mission_dir / "meta.json").unlink()

    result = backfill_mission(mission_dir)

    assert result.action in {"wrote", "skip"}
    assert result.mission_id in {None, _MISSION_ID}
    restored = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert restored["mission_id"] == _MISSION_ID, "backfill_mission minted over a tracked identity"


@pytest.mark.parametrize("tracked_state", ["usable", "corrupt", "staged-edit", "missing-head", "dangling-head", "garbled-head"])
def test_a_present_copy_that_lost_its_identity_takes_the_tracked_one(tmp_path: Path, tracked_state: str) -> None:
    """A usable tracked copy gives its id back; a copy git cannot supply one from is a coded refusal, never a mint."""
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    without_id = {
        "mission_slug": _SLUG,
        "slug": _SLUG,
        "friendly_name": "tracked meta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    lost = json.dumps(without_id, sort_keys=True, indent=2) + "\n"
    if tracked_state == "corrupt":
        (mission_dir / "meta.json").write_text("{not json\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "corrupt the committed copy")
    elif tracked_state == "staged-edit":
        (mission_dir / "meta.json").write_text(json.dumps({**without_id, "mission_id": _MISSION_ID}) + "\n", encoding="utf-8")
        _git(root, "add", "-A")
    (mission_dir / "meta.json").write_text(lost, encoding="utf-8")
    head = root / ".git" / "HEAD"
    saved_head = head.read_bytes()
    damaged_head = tracked_state in {"missing-head", "dangling-head", "garbled-head"}
    if damaged_head:
        head.unlink()
        if tracked_state == "dangling-head":
            head.symlink_to(root / "missing-head-target")
        elif tracked_state == "garbled-head":
            head.write_text("not a ref\n", encoding="utf-8")
    try:
        result = backfill_mission(mission_dir)
    finally:
        if damaged_head:
            head.unlink(missing_ok=True)
            head.write_bytes(saved_head)

    if damaged_head:
        recovered = json.loads(_git(root, "show", f"HEAD:kitty-specs/{_SLUG}/meta.json"))
        assert recovered["mission_id"] == _MISSION_ID, "the original identity must remain recoverable"
    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    if tracked_state == "usable":
        assert result.action == "wrote"
        assert result.mission_id == _MISSION_ID
        assert written["mission_id"] == _MISSION_ID
        return
    expected_code = "TRACKED_META_STAGED_DIFFERS" if tracked_state == "staged-edit" else "TRACKED_META_UNAVAILABLE"
    assert result.action == "skip"
    assert result.mission_id is None
    assert result.reason is not None
    assert f"[{expected_code}]" in result.reason
    assert "mission_id" not in written, "backfill_mission minted over an identity git holds"
    assert (mission_dir / "meta.json").read_text(encoding="utf-8") == lost, "refusal must not change metadata"


def test_an_untracked_copy_without_identity_is_still_minted(tmp_path: Path) -> None:
    """Positive control: nothing tracked means nothing to preserve, so the mint is still right."""
    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"slug": _SLUG, "mission_slug": _SLUG, "mission_type": "software-dev"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    result = backfill_mission(mission_dir)

    assert result.action == "wrote"
    assert result.mission_id is not None
    assert result.mission_id != _MISSION_ID
    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["mission_id"] == result.mission_id


def test_nothing_tracked_keeps_the_original_skip_reason(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    legacy = root / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "legacy")

    result = backfill_mission(legacy)

    assert result.action == "skip"
    assert result.reason == "meta.json not found"
    assert not (legacy / "meta.json").exists()


@pytest.mark.parametrize("redirected", [False, True], ids=["ordinary", "external-git-dir"])
def test_stray_directory_mints_only_without_a_repository_redirect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, redirected: bool) -> None:
    """#7084: an ancestor ``.git`` that is not a repository holds nothing, so the identity is minted.

    Reported as ``tests/lanes/test_refinalize_mission_branch.py`` expecting ``wrote`` and getting
    ``skip``: the skipping call was this one, refusing with ``TRACKED_META_UNAVAILABLE`` because a
    directory named ``.git`` somewhere above the mission folder was mistaken for a repository git
    could not read. The refusal controls live in the anchor-shape tests and the real damaged
    repositories above. An explicit external gitdir is unknown, not proof that nothing is tracked.
    """
    ancestor = tmp_path / "ambient"
    mission_dir = ancestor / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (ancestor / ".git" / "spec-kitty-locks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"slug": _SLUG, "mission_slug": _SLUG, "mission_type": "software-dev"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=mission_dir, capture_output=True)
    assert probe.returncode != 0, "the fixture must not bypass the anchor probe through an enclosing worktree"
    before = (mission_dir / "meta.json").read_bytes()
    head: Path | None = None
    saved_head = b""
    if redirected:
        repository = _repo(tmp_path)
        _mission(repository)
        head = repository / ".git" / "HEAD"
        saved_head = head.read_bytes()
        head.unlink()
        monkeypatch.setenv("GIT_DIR", str(repository / ".git"))
    try:
        result = backfill_mission(mission_dir)
    finally:
        if head is not None:
            head.write_bytes(saved_head)

    if redirected:
        assert result.action == "skip"
        assert result.reason is not None and "[TRACKED_META_UNAVAILABLE]" in result.reason
        assert (mission_dir / "meta.json").read_bytes() == before
        assert head is not None
        recovered = json.loads(_git(head.parent.parent, "show", f"HEAD:kitty-specs/{_SLUG}/meta.json"))
        assert recovered["mission_id"] == _MISSION_ID
        return
    assert result.reason is None, f"the mint was refused: {result.reason}"
    assert result.action == "wrote"
    assert result.mission_id is not None
    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["mission_id"] == result.mission_id
