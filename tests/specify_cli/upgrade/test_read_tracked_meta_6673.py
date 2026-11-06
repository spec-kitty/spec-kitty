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
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


def _break_git_anchor(root: Path) -> None:
    """Leave an unusable gitdir pointer whose path word is not an ownership diagnosis."""
    git_dir = root / ".git"
    for child in sorted(git_dir.rglob("*"), reverse=True):
        child.unlink() if child.is_file() or child.is_symlink() else child.rmdir()
    git_dir.rmdir()
    (root / ".git").write_text(f"gitdir: {root / 'safe.directory' / 'missing-gitdir'}\n", encoding="utf-8")


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
    assert classified.code == "TRACKED_META_STAGED_DIFFERS"


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
    # A path containing safe.directory must not turn a real repository-layout failure into
    # ownership advice. Git's actual diagnosis, rather than a path word, decides the cause.
    _break_git_anchor(root)

    tracked = read_tracked_meta(mission_dir)

    assert tracked.meta is None
    assert tracked.unavailable is True, "a refusing git was read as 'nothing tracked' (the fabricating branch)"
    # #7131: the notice must not assert that the tracked file is missing (git never established that
    # the path is tracked) and must not prescribe `git checkout --`, which fails for the same reason.
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    classified = classify_missing_tracked_meta(mission_dir, root)
    assert classified is not None
    assert classified.refuse is True
    assert classified.code == "TRACKED_META_UNAVAILABLE"
    assert classified.notice.endswith("[TRACKED_META_UNAVAILABLE]")
    assert "tracked meta.json is missing" not in classified.notice, "it still claims the tracked copy is missing"
    assert "git checkout --" not in classified.notice, "it still offers a restore remedy git cannot perform"
    assert "git status" in classified.notice, "repository-layout faults need a repository diagnosis, not trust advice"
    assert tracked.unreadable_reason == "repository", "the cause git gave was dropped on the way to the notice"
    assert not (mission_dir / "meta.json").exists(), "diagnosing unreadable Git must not mint an identity"


def test_an_ownership_refusal_is_not_reported_as_a_missing_tracked_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A checkout git refuses on ownership grounds is a repository-access fault, not a missing file (#7131).

    Git only refuses ownership for a checkout owned by another uid, which an unprivileged test cannot
    create, so the git invocation seam answers with git's real refusal text — the same technique the
    preflight tests use. The refusal itself must survive untouched; only the diagnosis changes.
    """
    from kernel.git import GitResult
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    (mission_dir / "meta.json").unlink()
    refusal = (
        b"fatal: detected dubious ownership in repository at '/srv/secret-checkout'\n"
        b"to add an exception for this directory, call:\n\n"
        b"\tgit config --global --add safe.directory /srv/secret-checkout\n"
        b"remote credential: https://user:hunter2@example.invalid/repo\n"
    )
    monkeypatch.setattr("specify_cli.mission_metadata.run_git", lambda *_a, **_k: GitResult(returncode=128, stdout=b"", stderr=refusal))

    tracked = read_tracked_meta(mission_dir)
    classified = classify_missing_tracked_meta(mission_dir, root)

    assert (tracked.meta, tracked.unavailable, tracked.unreadable_reason) == (None, True, "ownership")
    assert classified is not None
    assert (classified.refuse, classified.code) == (True, "TRACKED_META_UNAVAILABLE")
    assert "ownership" in classified.notice
    assert _SLUG in classified.notice, "the notice must identify the affected Mission without echoing stderr"
    assert "operator decision" in classified.notice, "trusting a repository is not this tool's decision to make"
    assert "git checkout --" not in classified.notice
    assert "safe.directory *" not in classified.notice
    # NFR-001: nothing of git's own stderr reaches the operator — not a path, not a credential.
    assert "/srv/secret-checkout" not in classified.notice
    assert "hunter2" not in classified.notice


def test_a_present_meta_that_lost_its_identity_keeps_its_own_lead_on_an_unreadable_repository(tmp_path: Path) -> None:
    """The present-file refusal shares the cause tail but not the "missing" lead (#7131)."""
    from specify_cli.upgrade.tracked_meta_notice import tracked_meta_refusal

    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    present = dict(_META)
    present.pop("mission_id")
    (mission_dir / "meta.json").write_text(json.dumps(present, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _break_git_anchor(root)

    tracked = read_tracked_meta(mission_dir)
    refusal = tracked_meta_refusal(mission_dir, root, tracked)

    assert refusal is not None
    assert (refusal.refuse, refusal.code) == (True, "TRACKED_META_UNAVAILABLE")
    assert "has lost its mission_id" in refusal.notice
    assert "is missing from the working tree" not in refusal.notice
    assert "git checkout --" not in refusal.notice


def test_an_unreadable_committed_blob_is_not_reported_as_a_missing_tracked_file(tmp_path: Path) -> None:
    """A repository git can open but whose committed object it cannot read needs an object repair (#7131)."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    root = _repo(tmp_path)
    mission_dir = _commit_meta(root)
    (mission_dir / "meta.json").unlink()
    oid = _git(root, "rev-parse", f"HEAD:kitty-specs/{_SLUG}/meta.json").strip()
    loose_object = root / ".git" / "objects" / oid[:2] / oid[2:]
    loose_object.chmod(0o644)  # git writes objects read-only
    loose_object.write_bytes(b"not a zlib stream")

    tracked = read_tracked_meta(mission_dir)
    classified = classify_missing_tracked_meta(mission_dir, root)

    assert (tracked.meta, tracked.unavailable, tracked.unreadable_reason) == (None, True, "objects")
    assert classified is not None
    assert (classified.refuse, classified.code) == (True, "TRACKED_META_UNAVAILABLE")
    assert "git fsck" in classified.notice, "an unreadable committed copy is repaired in the object store"
    assert "git checkout --" not in classified.notice
    assert "tracked meta.json is missing" not in classified.notice, "it still claims the tracked copy is missing"


@pytest.mark.parametrize(
    ("shape", "phrase", "remedy"),
    [
        ("index-only", "only in the index (not committed)", "git checkout -- kitty-specs/{slug}/meta.json"),
        ("corrupt", "not a JSON object", "git show HEAD:kitty-specs/{slug}/meta.json"),
    ],
)
def test_the_refusal_notice_names_the_unusable_copy_and_its_repair(tmp_path: Path, shape: str, phrase: str, remedy: str) -> None:
    """US2 Scenario 3: each refusal says what is wrong with git's copy, carries a stable code, and names a repair.

    A corrupt committed copy is repaired first because `git checkout --` would restore the same unusable bytes.
    """
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission_dir / "meta.json").write_text("{not json\n" if shape == "corrupt" else json.dumps(_META) + "\n", encoding="utf-8")
    _git(root, "add", "-A")
    if shape == "corrupt":
        _git(root, "commit", "-q", "-m", "corrupt")
    (mission_dir / "meta.json").unlink()

    classified = classify_missing_tracked_meta(mission_dir, root)

    assert classified is not None
    assert classified.refuse is True
    assert classified.code == "TRACKED_META_UNAVAILABLE"
    assert classified.notice.endswith("[TRACKED_META_UNAVAILABLE]")
    assert phrase in classified.notice
    assert remedy.format(slug=_SLUG) in classified.notice


# ---------------------------------------------------------------------------
# #7262: one `.git` classifier — repository, residue or unknown (operator ruling 2026-11-06)
#
# git has already answered "not a work tree" in every case below, so the only question is
# whether a `.git` above the folder could still hold a copy. Residue reads as "nothing tracked"
# (#7093, #7084); a repository, or anything the classifier cannot rule out, refuses and names
# the repair (#7117, #7131). No case may offer `git checkout --`.
# ---------------------------------------------------------------------------


def _mission_under_ancestor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """``(mission_dir, ancestor)``: *ancestor* is the only place a ``.git`` can sit below the ceiling."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    ancestor = tmp_path / "ambient"
    mission_dir = ancestor / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=mission_dir, capture_output=True)
    assert probe.returncode != 0, "the fixture must be outside a worktree, not green through the tracked-prefix path"
    return mission_dir, ancestor


@pytest.mark.parametrize(
    "entries",
    [(), ("hooks",), ("spec-kitty-locks",), ("hooks", "spec-kitty-locks")],
    ids=["empty", "hooks", "locks", "hooks-and-locks"],
)
def test_residue_git_above_a_mission_is_not_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entries: tuple[str, ...]) -> None:
    """#7093 / #7084: an empty or hook/lock-only ``.git`` holds nothing, so nothing is tracked.

    The historical shape is a stray ``.git`` holding ``hooks/`` and ``spec-kitty-locks/``. Read as
    a repository, it stopped the 2.0.6 sweep's baseline repair and refused every backfill below it
    with a ``git checkout --`` that had nothing to restore.
    """
    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    (ancestor / ".git").mkdir()
    for entry in entries:
        (ancestor / ".git" / entry).mkdir()

    assert read_tracked_meta(mission_dir) == TrackedMeta(None, unavailable=False), "residue was read as a refusal"
    assert build_baseline_feature_meta(mission_dir, ancestor) is not None, "the shared repair refused a folder it can rebuild"


def test_a_pointer_file_git_cannot_follow_is_a_repository_and_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7093's positive control: a ``.git`` pointer file names a repository the caller cannot read."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    (ancestor / ".git").write_text("gitdir: /nonexistent/gitdir\n", encoding="utf-8")

    tracked = read_tracked_meta(mission_dir)
    classified = classify_missing_tracked_meta(mission_dir, ancestor)

    assert (tracked.meta, tracked.unavailable, tracked.unreadable_reason) == (None, True, "repository")
    assert classified is not None and classified.refuse is True
    assert "git checkout --" not in classified.notice


def _no_head_but_objects(git_dir: Path) -> None:
    """A repository that lost its ``HEAD``: its objects and refs are still there (#7117)."""
    git_dir.mkdir()
    (git_dir / "objects").mkdir()
    (git_dir / "refs").mkdir()


def _dangling_head(git_dir: Path) -> None:
    _no_head_but_objects(git_dir)
    (git_dir / "HEAD").symlink_to(git_dir / "missing-head-target")


def _dangling_git_symlink(git_dir: Path) -> None:
    git_dir.symlink_to(git_dir.parent / "missing-gitdir", target_is_directory=True)


@pytest.mark.parametrize(
    ("shape", "why"),
    [
        (_no_head_but_objects, "a directory without HEAD that holds more than hooks and locks"),
        (_dangling_head, "a repository whose HEAD is not a regular file"),
        (_dangling_git_symlink, "a symbolic link"),
    ],
    ids=["head-deleted", "head-dangling", "git-dangling-symlink"],
)
def test_an_unknown_git_refuses_and_names_the_git_path_and_both_repairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: Callable[[Path], None], why: str
) -> None:
    """#7262 refuse-on-unknown: the notice names the ``.git`` and the real repair, never a file restore (#7131)."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    shape(ancestor / ".git")

    tracked = read_tracked_meta(mission_dir)
    classified = classify_missing_tracked_meta(mission_dir, ancestor)

    assert (tracked.meta, tracked.unavailable, tracked.unreadable_reason) == (None, True, "anchor")
    assert tracked.anchor is not None and tracked.anchor.path == (ancestor / ".git").resolve()
    assert classified is not None
    assert (classified.refuse, classified.code) == (True, "TRACKED_META_UNAVAILABLE")
    assert "`.git` is " + why in classified.notice
    assert "repair it" in classified.notice and "remove it" in classified.notice
    assert "git checkout --" not in classified.notice
    assert not (mission_dir / "meta.json").exists(), "a refusal must not write metadata"


@pytest.mark.parametrize("seam", ["lstat", "listing"])
def test_an_unreadable_git_stays_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seam: str) -> None:
    """NFR-002: an entry that cannot be inspected is unknown, never residue (#7093, #7117).

    The denial is injected at the read seam, not with ``chmod``, so the verdict is the same for
    every uid (#5622).
    """
    import os

    from tests._support.eacces import deny_path_method

    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    git_dir = (ancestor / ".git").resolve()
    git_dir.mkdir()
    if seam == "lstat":
        deny_path_method(monkeypatch, "lstat", git_dir)
    else:
        real_scandir = os.scandir

        def denied(path: str) -> Any:
            if Path(path) == git_dir:
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        monkeypatch.setattr(os, "scandir", denied)

    tracked = read_tracked_meta(mission_dir)

    assert (tracked.unavailable, tracked.unreadable_reason) == (True, "anchor")


def test_an_explicit_git_redirect_refuses_and_names_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7117: a redirected repository/index/object store cannot be ruled out by the names on disk."""
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "missing-store"))

    tracked = read_tracked_meta(mission_dir)
    classified = classify_missing_tracked_meta(mission_dir, ancestor)

    assert (tracked.unavailable, tracked.unreadable_reason) == (True, "anchor")
    assert classified is not None and classified.refuse is True
    assert "`GIT_DIR`" in classified.notice and "unset it" in classified.notice
    assert "git checkout --" not in classified.notice


@pytest.mark.parametrize("repository_above", [True, False], ids=["repository-above", "residue-only"])
def test_a_git_that_cannot_be_run_refuses_only_under_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository_above: bool
) -> None:
    """Operator ruling on #7262: git that cannot start is classified too; it no longer mints over a repository."""
    from kernel.git import GitCommandError
    from specify_cli.upgrade.tracked_meta_notice import classify_missing_tracked_meta

    mission_dir, ancestor = _mission_under_ancestor(tmp_path, monkeypatch)
    (ancestor / ".git" / "hooks").mkdir(parents=True)
    if repository_above:
        (ancestor / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    def not_run(cwd: Path, *args: str, **_kwargs: object) -> object:
        raise GitCommandError(argv=args, cwd=cwd, returncode=-1, stderr="git: not found")

    monkeypatch.setattr("specify_cli.mission_metadata.run_git", not_run)

    tracked = read_tracked_meta(mission_dir)

    if not repository_above:
        assert tracked == TrackedMeta(None, unavailable=False)
        return
    classified = classify_missing_tracked_meta(mission_dir, ancestor)
    assert (tracked.unavailable, tracked.unreadable_reason) == (True, "git-not-run")
    assert classified is not None and classified.refuse is True
    assert "git could not be started" in classified.notice
    assert "git checkout --" not in classified.notice
