"""Disposable aborted creation removes only its new, untracked scaffold.

Main deliberately permits bootstrap commits to be skipped; those successful
creations are not rolled back. These tests cover exceptions that escape create.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from specify_cli.core.mission_creation import create_mission_core
from specify_cli.git.commit_helpers import ProtectedBranchRefused

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_ORIGINAL_BRANCH = "operator-work"


def _init_git_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "branch", "-M", _ORIGINAL_BRANCH], cwd=repo, capture_output=True, check=True)


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (f"This mission delivers {title} so product and engineering can move forward with a clear outcome and shared understanding."),
    }


def _scaffolds(repo: Path) -> list[str]:
    specs = repo / "kitty-specs"
    return sorted(entry.name for entry in specs.iterdir() if entry.is_dir()) if specs.exists() else []


def _fail_at_meta_write(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Fail after the scaffold exists, with the exception the real defect raises.

    Deliberately the real ``ProtectedBranchRefused`` rather than a stand-in:
    the cleanup is scoped to that failure class, so a generic error here would
    let the test pass while the production path did nothing.
    """

    def _explode(*_args: object, **_kwargs: object) -> None:
        raise ProtectedBranchRefused(
            destination_ref="main",
            worktree_root=repo,
            commit_message="scaffold",
        )

    monkeypatch.setattr("specify_cli.mission_metadata.write_meta", _explode)


@pytest.mark.parametrize("slug", ["orphan-check", "068-orphan-check"])
def test_failed_create_leaves_no_orphan_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slug: str) -> None:
    """The #4035 defect: the scaffold outlived the failed create."""
    _init_git_repo(tmp_path)
    assert _scaffolds(tmp_path) == []

    _fail_at_meta_write(monkeypatch, tmp_path)

    with pytest.raises(Exception, match="refusing to commit to protected branch"):
        create_mission_core(
            tmp_path,
            slug,
            allow_worktree_context=True,
            **_mission_summary(slug),
        )

    assert _scaffolds(tmp_path) == [], "a failed create must leave no mission directory behind"


def test_retry_after_failure_yields_exactly_one_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The user-visible consequence: one intended mission, one directory.

    This is the assertion that actually encodes the bug report. Without the
    scaffold rollback the retry produces two directories with different ULIDs,
    and the reporter has to work out by hand which one is real.
    """
    _init_git_repo(tmp_path)

    _fail_at_meta_write(monkeypatch, tmp_path)
    with pytest.raises(Exception, match="refusing to commit to protected branch"):
        create_mission_core(
            tmp_path,
            "retry-check",
            allow_worktree_context=True,
            **_mission_summary("retry-check"),
        )

    monkeypatch.undo()  # the operator fixes the cause and retries
    # mid8 is the first 8 Crockford chars of a ULID = the top 40 bits of a 48-bit
    # millisecond timestamp, so two creates inside the same 256 ms bucket mint the
    # SAME directory name and the retry silently reuses the orphan. That made this
    # test pass on pristine 3.2.6 (squad R3, #4051). Cross the bucket boundary so
    # the retry mints a distinct name and an undeleted orphan shows as a second dir.
    time.sleep(0.3)
    create_mission_core(
        tmp_path,
        "retry-check",
        allow_worktree_context=True,
        **_mission_summary("retry-check"),
    )

    assert len(_scaffolds(tmp_path)) == 1, f"expected exactly one mission after retry, got {_scaffolds(tmp_path)}"


def test_rollback_preserves_a_pre_existing_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only what THIS call created is removed.

    The rollback diffs the scaffold set, so a mission that already existed must
    survive a later unrelated failure. Deleting a directory is irreversible;
    this pins the blast radius.
    """
    _init_git_repo(tmp_path)
    create_mission_core(
        tmp_path,
        "keep-me",
        allow_worktree_context=True,
        **_mission_summary("keep-me"),
    )
    survivors = _scaffolds(tmp_path)
    assert len(survivors) == 1

    _fail_at_meta_write(monkeypatch, tmp_path)
    with pytest.raises(Exception, match="refusing to commit to protected branch"):
        create_mission_core(
            tmp_path,
            "doomed",
            allow_worktree_context=True,
            **_mission_summary("doomed"),
        )

    assert _scaffolds(tmp_path) == survivors, "rollback removed a mission it did not create"


def test_rollback_never_deletes_tracked_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A directory git tracks is never removed, even if this call created it.

    A late refusal may follow a scaffold commit. The deletion decision must
    inspect the index before rollback restores it, preserving that evidence.
    """
    _init_git_repo(tmp_path)

    created: dict[str, Path] = {}
    real_write_meta = __import__("specify_cli.mission_metadata", fromlist=["write_meta"]).write_meta

    def _commit_then_explode(feature_dir: Path, meta: dict[str, object], *args: object, **kwargs: object) -> None:
        real_write_meta(feature_dir, meta, *args, **kwargs)
        created["dir"] = Path(feature_dir)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "operator committed the scaffold"], cwd=tmp_path, capture_output=True, check=True)
        raise ProtectedBranchRefused(
            destination_ref="main",
            worktree_root=tmp_path,
            commit_message="scaffold",
        )

    monkeypatch.setattr("specify_cli.mission_metadata.write_meta", _commit_then_explode)

    with pytest.raises(Exception, match="refusing to commit to protected branch"):
        create_mission_core(
            tmp_path,
            "tracked-check",
            allow_worktree_context=True,
            **_mission_summary("tracked-check"),
        )

    assert created, "the injected hook never ran; the test is not exercising the path it claims"
    assert created["dir"].exists(), "rollback deleted a directory whose contents git tracks"


def test_tracking_probe_launch_failure_preserves_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unavailable Git executable cannot establish permission to delete."""
    from specify_cli.core.mission_creation import _plan_orphan_scaffold_removal

    scaffold = tmp_path / "kitty-specs" / "orphan-check-01KABCDE"
    scaffold.mkdir(parents=True)

    def unavailable(*args: object, **kwargs: object) -> None:
        raise OSError("git unavailable")

    monkeypatch.setattr("specify_cli.core.mission_creation.subprocess.run", unavailable)
    assert _plan_orphan_scaffold_removal(tmp_path, mission_slug="orphan-check", pre_existing_scaffolds=frozenset()) == ()
    assert scaffold.exists()


def test_persistence_failure_retains_scaffold_for_resume_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented non-disposable path: local MissionCreated persistence fails.

    Its error text tells the operator NOT to retry and to use
    ``agent mission check-prerequisites``, which reads the scaffold. So the
    scaffold — meta.json already written — must survive rollback. This is the
    negative case for ``_failure_is_disposable_create_refusal``; without it a
    predicate that always returned True passed the whole suite (squad R3, #4051).
    """
    _init_git_repo(tmp_path)

    def _persist_explodes(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("injected MissionCreated persistence failure")

    monkeypatch.setattr("specify_cli.status.emit_mission_created_local", _persist_explodes)
    with pytest.raises(Exception, match="MissionCreated persistence failed"):
        create_mission_core(tmp_path, "keep-for-probe", allow_worktree_context=True, **_mission_summary("keep-for-probe"))

    survivors = _scaffolds(tmp_path)
    assert survivors and all(name.startswith("keep-for-probe-") for name in survivors), survivors
    assert (tmp_path / "kitty-specs" / survivors[0] / "meta.json").exists(), "resume-probe evidence was deleted"


def test_unclassified_oserror_before_meta_does_not_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure that is neither a commit refusal nor the persistence path is not disposable.

    ``OSError`` from ``write_meta`` lands between mkdir and meta.json. It is not one
    of the retry-prescribed refusals, so the rollback must leave it alone — the
    delete is irreversible and only fires for classes whose own message says
    "retry". Second negative case for the predicate.
    """
    _init_git_repo(tmp_path)

    def _disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError("injected: no space left on device")

    monkeypatch.setattr("specify_cli.mission_metadata.write_meta", _disk_full)
    with pytest.raises(OSError, match="no space left"):
        create_mission_core(tmp_path, "unclassified", allow_worktree_context=True, **_mission_summary("unclassified"))

    assert [n for n in _scaffolds(tmp_path) if n.startswith("unclassified-")], "non-disposable failure had its scaffold deleted"
