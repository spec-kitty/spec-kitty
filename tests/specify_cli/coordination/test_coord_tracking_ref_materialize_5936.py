"""In-process coverage for the #5936 fix: a remote-tracking coordination branch gets a local head.

The end-to-end CLI arms live in ``test_coord_clone_writer_5936.py``. These tests
exercise the same code in-process with real git (a bare origin, a real push and
a real clone), so each new branch is covered without a CLI subprocess:

* :func:`coord_branch_tracking_ref` resolves only the OWNING remote's tracking ref;
* :func:`ensure_coord_branch_local_head` creates a ``--track`` local head from it,
  and writes nothing when no tracking ref exists (fail-closed);
* :func:`materialize_coord_surface_for_write` materializes the coordination worktree
  in a teammate's clone instead of refusing;
* the doctor's ``COORDINATION_WORKTREE_MISSING`` finding leads with ``--fix``;
* ``agent action review`` materializes before its status read.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination import surface_resolver
from specify_cli.coordination.surface_resolver import (
    CoordinationWorktreeUnmaterialized,
    coord_branch_tracking_ref,
    ensure_coord_branch_local_head,
    materialize_coord_surface_for_write,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.specify_cli.coordination.test_coord_branch_remote_probe_4979 import (
    _bare_origin,
    _configure_clone,
    _create_coord_mission,
    _push,
    _repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BRANCH = "kitty/mission-demo-01ABCDEF"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def _is_local_head(repo: Path, branch: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


@pytest.fixture()
def clone_with_tracking_ref(tmp_path: Path) -> Path:
    """A clone whose only ref for ``_BRANCH`` is ``refs/remotes/origin/<branch>``."""
    src = _repo(tmp_path, "src")
    # The coordination tip is a commit of its own, so a branch forked from the
    # clone's default branch can never pass for the tracking ref.
    _git(src, "checkout", "-q", "-b", _BRANCH)
    _git(src, "commit", "-q", "--allow-empty", "-m", "coordination commit")
    _git(src, "checkout", "-q", "remote-probe-4979-work")
    bare = _bare_origin(tmp_path)
    _push(src, bare, "remote-probe-4979-work", _BRANCH)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True)
    _configure_clone(clone)
    assert not _is_local_head(clone, _BRANCH)
    return clone


# --- coord_branch_tracking_ref ------------------------------------------------


def test_tracking_ref_resolves_owning_remote(clone_with_tracking_ref: Path) -> None:
    assert coord_branch_tracking_ref(clone_with_tracking_ref, _BRANCH) == f"refs/remotes/origin/{_BRANCH}"


def test_tracking_ref_none_when_clone_never_fetched_branch(clone_with_tracking_ref: Path) -> None:
    _git(clone_with_tracking_ref, "update-ref", "-d", f"refs/remotes/origin/{_BRANCH}")
    assert coord_branch_tracking_ref(clone_with_tracking_ref, _BRANCH) is None


def test_tracking_ref_none_without_any_remote(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert coord_branch_tracking_ref(repo, _BRANCH) is None


def test_tracking_ref_ignores_a_non_owning_remote(clone_with_tracking_ref: Path) -> None:
    """``branch.<b>.remote`` names another remote: origin's copy is never picked in its place."""
    _git(clone_with_tracking_ref, "remote", "add", "upstream", str(clone_with_tracking_ref))
    _git(clone_with_tracking_ref, "config", f"branch.{_BRANCH}.remote", "upstream")
    assert coord_branch_tracking_ref(clone_with_tracking_ref, _BRANCH) is None


def test_tracking_ref_none_when_remote_resolution_fails(clone_with_tracking_ref: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> str:
        raise OSError("git missing")

    monkeypatch.setattr(surface_resolver, "resolve_remote", _boom)
    assert coord_branch_tracking_ref(clone_with_tracking_ref, _BRANCH) is None


def test_tracking_ref_none_when_probe_cannot_run(clone_with_tracking_ref: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(surface_resolver, "resolve_remote", lambda *_a, **_k: "origin")

    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise OSError("git missing")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert coord_branch_tracking_ref(clone_with_tracking_ref, _BRANCH) is None


# --- ensure_coord_branch_local_head --------------------------------------------


def test_ensure_creates_tracking_local_head(clone_with_tracking_ref: Path) -> None:
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is True
    assert _is_local_head(clone_with_tracking_ref, _BRANCH)
    upstream = _git(clone_with_tracking_ref, "rev-parse", "--abbrev-ref", f"{_BRANCH}@{{upstream}}")
    assert upstream.stdout.strip() == f"origin/{_BRANCH}"
    local = _git(clone_with_tracking_ref, "rev-parse", f"refs/heads/{_BRANCH}").stdout
    remote = _git(clone_with_tracking_ref, "rev-parse", f"refs/remotes/origin/{_BRANCH}").stdout
    assert local == remote


def test_ensure_sets_upstream_without_git_autosetup(clone_with_tracking_ref: Path) -> None:
    """``--track`` itself sets the upstream, not git's ``branch.autoSetupMerge`` default."""
    _git(clone_with_tracking_ref, "config", "branch.autoSetupMerge", "false")
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is True
    upstream = _git(clone_with_tracking_ref, "rev-parse", "--abbrev-ref", f"{_BRANCH}@{{upstream}}", check=False)
    assert upstream.stdout.strip() == f"origin/{_BRANCH}", upstream.stderr


def test_ensure_is_a_no_op_for_an_existing_local_head(clone_with_tracking_ref: Path) -> None:
    # A local head created by hand, with no upstream: it must be left exactly as it is.
    _git(clone_with_tracking_ref, "branch", "--no-track", _BRANCH, "refs/remotes/origin/remote-probe-4979-work")
    before = _git(clone_with_tracking_ref, "rev-parse", f"refs/heads/{_BRANCH}").stdout
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is True
    assert _git(clone_with_tracking_ref, "rev-parse", f"refs/heads/{_BRANCH}").stdout == before
    assert _git(clone_with_tracking_ref, "config", f"branch.{_BRANCH}.remote", check=False).returncode != 0


def test_ensure_refuses_and_writes_nothing_without_tracking_ref(clone_with_tracking_ref: Path) -> None:
    _git(clone_with_tracking_ref, "update-ref", "-d", f"refs/remotes/origin/{_BRANCH}")
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is False
    assert not _is_local_head(clone_with_tracking_ref, _BRANCH)


def test_ensure_tolerates_a_concurrent_creation(clone_with_tracking_ref: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``git branch`` fails because another process created the head first: still a local head."""
    real = surface_resolver._coord_branch_is_local_head
    calls = {"n": 0}

    def _first_miss(repo: Path, branch: str) -> bool:
        calls["n"] += 1
        if calls["n"] == 1:
            _git(repo, "branch", "--no-track", branch, f"refs/remotes/origin/{branch}")  # the concurrent writer
            return False
        return real(repo, branch)

    monkeypatch.setattr(surface_resolver, "_coord_branch_is_local_head", _first_miss)
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is True
    assert calls["n"] == 2


def test_ensure_false_when_branch_command_cannot_run(clone_with_tracking_ref: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(surface_resolver, "coord_branch_tracking_ref", lambda *_a: f"refs/remotes/origin/{_BRANCH}")
    real_run = subprocess.run

    def _fail_branch(argv: list[str], *a: Any, **k: Any) -> Any:
        if "branch" in argv:
            raise OSError("git missing")
        return real_run(argv, *a, **k)

    monkeypatch.setattr(subprocess, "run", _fail_branch)
    assert ensure_coord_branch_local_head(clone_with_tracking_ref, _BRANCH) is False


# --- the write seam and the doctor on a real coordination Mission ---------------


@pytest.fixture()
def teammate_clone(tmp_path: Path) -> tuple[Path, str, str, str]:
    """A real coord Mission pushed by its author and cloned by a teammate (no local coordination head)."""
    author = _repo(tmp_path, "author")
    result = _create_coord_mission(author, "clone-writer-5936")
    coord_branch = result.coordination_branch
    assert coord_branch is not None
    bare = _bare_origin(tmp_path)
    _push(author, bare, result.target_branch, coord_branch)
    clone = tmp_path / "teammate"
    subprocess.run(["git", "clone", "-q", "-b", result.target_branch, str(bare), str(clone)], check=True)
    _configure_clone(clone)
    assert not _is_local_head(clone, coord_branch)
    return clone, result.mission_slug, coord_branch, str(result.meta["mission_id"])


def test_write_seam_materializes_in_teammate_clone(teammate_clone: tuple[Path, str, str, str]) -> None:
    clone, slug, coord_branch, mission_id = teammate_clone

    remote_tip = _git(clone, "rev-parse", f"refs/remotes/origin/{coord_branch}").stdout.strip()
    main_tip = _git(clone, "rev-parse", "HEAD").stdout.strip()
    assert remote_tip != main_tip, "fixture precondition: the coordination tip differs from the default branch"

    materialize_coord_surface_for_write(clone, slug)

    assert _is_local_head(clone, coord_branch)
    local_tip = _git(clone, "rev-parse", f"refs/heads/{coord_branch}").stdout.strip()
    ancestry = _git(clone, "merge-base", "--is-ancestor", remote_tip, local_tip, check=False)
    assert ancestry.returncode == 0, "the local coordination branch must start from the tracking ref, never from main"
    worktree = CoordinationWorkspace.worktree_path(clone, slug, mission_id[:8])
    assert (worktree / ".git").exists()
    assert _git(worktree, "symbolic-ref", "--short", "HEAD").stdout.strip() == coord_branch


def test_write_seam_still_refuses_without_any_local_ref(teammate_clone: tuple[Path, str, str, str]) -> None:
    clone, slug, coord_branch, _ = teammate_clone
    _git(clone, "update-ref", "-d", f"refs/remotes/origin/{coord_branch}")

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        materialize_coord_surface_for_write(clone, slug)
    assert not _is_local_head(clone, coord_branch)


def test_doctor_finding_leads_with_fix_for_tracking_ref(teammate_clone: tuple[Path, str, str, str]) -> None:
    from specify_cli.cli.commands._coordination_doctor import _check_coordination_worktree_health

    clone, slug, coord_branch, mission_id = teammate_clone
    meta: dict[str, object] = {"coordination_branch": coord_branch, "mission_slug": slug, "mission_id": mission_id}

    findings = _check_coordination_worktree_health(clone, meta)

    missing = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_MISSING"]
    assert len(missing) == 1
    assert missing[0].next_step is not None
    assert missing[0].next_step.startswith(f"Run: `spec-kitty doctor coordination --mission {slug} --fix`")
    assert not _is_local_head(clone, coord_branch), "the read-only health check must not write a branch"


def test_doctor_finding_keeps_fetch_steps_without_tracking_ref(teammate_clone: tuple[Path, str, str, str]) -> None:
    from specify_cli.cli.commands._coordination_doctor import _check_coordination_worktree_health

    clone, slug, coord_branch, mission_id = teammate_clone
    _git(clone, "update-ref", "-d", f"refs/remotes/origin/{coord_branch}")
    meta: dict[str, object] = {"coordination_branch": coord_branch, "mission_slug": slug, "mission_id": mission_id}

    findings = _check_coordination_worktree_health(clone, meta)

    missing = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_MISSING"]
    assert len(missing) == 1
    assert missing[0].next_step is not None
    assert "fetch" in missing[0].next_step


# --- agent action review materializes before its status read --------------------


class _MaterializeCalled(Exception):
    pass


def test_review_materializes_before_auto_detecting_the_wp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``agent action review`` with no WP id: the surface is materialized before the for_review auto-detection reads status."""
    from specify_cli.cli.commands.agent import workflow

    seen: list[tuple[Path, str]] = []

    def _record(repo_root: Path, mission_slug: str) -> None:
        seen.append((repo_root, mission_slug))
        raise _MaterializeCalled

    def _read_must_not_run(*_a: object, **_k: object) -> None:
        raise AssertionError("the status read ran before the coordination surface was materialized")

    monkeypatch.setattr(surface_resolver, "materialize_coord_surface_for_write", _record)
    monkeypatch.setattr(workflow, "locate_project_root", lambda: tmp_path / "wt")
    monkeypatch.setattr(workflow, "_find_mission_slug", lambda **_k: "demo-01ABCDEF")
    monkeypatch.setattr(workflow, "_ensure_target_branch_checked_out", lambda *_a: (tmp_path, "main"))
    monkeypatch.setattr(workflow, "_find_first_for_review_wp", _read_must_not_run)

    with pytest.raises((_MaterializeCalled, SystemExit, Exception)) as excinfo:
        workflow.review(wp_id=None, mission="demo-01ABCDEF", agent="teammate")
    assert not isinstance(excinfo.value, AssertionError), excinfo.value
    assert seen == [(tmp_path, "demo-01ABCDEF")]
