"""#6750 WP02: the lane auto-collector requests exact files and reports the truth.

``move-task --to for_review``'s auto-commit collector read ``git status`` with a
new directory **collapsed** (``?? .zig-cache/``), forwarded that directory to
``safe_commit``, and git expanded it: the children landed, then the post-landing
extra-path guard -- built to compare exact file paths -- reported a superset and
asserted a pre-commit hook had done it. The collector then printed "could not
auto-commit" for a commit that had already landed.

These tests drive the REAL ``_mt_commit_lane_deliverables``:

* the issue's fixture (untracked directory, **empty** hooks dir) must commit
  exactly the directory's files, say so, and never mention a hook (SC-001);
* a genuine hook-swept path must still be caught, naming only that path, and the
  collector must report that the commit LANDED (SC-002) -- the guard must not go
  vacuous to fix a false positive;
* the expansion is one ``--untracked-files=all`` probe and adds no git round trip
  (NFR-001).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "mt-6750-repro-01M67HVC"
_LANE_BRANCH = "kitty/mission-mt-6750-lane-a"
_README = "README.md"
_UNRELATED = "unrelated.txt"
_CACHE_DIR = ".zig-cache"
_CACHE_FILES = (".zig-cache/one.bin", ".zig-cache/two.bin")

#: A hook that stages a modified tracked file the operation did not request
#: (the #5903 class), and one that stages a path it created itself.
_SWEEPING_HOOK = "#!/bin/sh\ngit add -u\nexit 0\n"
_INJECTING_HOOK = '#!/bin/sh\necho "hook-injected" > hook-injected.txt\ngit add hook-injected.txt\nexit 0\n'
_INJECTED = "hook-injected.txt"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _make_fixture(tmp_path: Path, *, hook: str | None = None) -> Path:
    """A lane worktree: committed README + an unrelated tracked file, an untracked
    directory of two files, and (optionally) one real pre-commit hook."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    hooks_dir = repo / ".hooks"
    hooks_dir.mkdir()
    _git(repo, "init", "-q", "-b", _LANE_BRANCH)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.hooksPath", str(hooks_dir))
    (repo / _README).write_text("readme\n", encoding="utf-8")
    (repo / _UNRELATED).write_text("v1\n", encoding="utf-8")
    _git(repo, "add", _README, _UNRELATED)
    _git(repo, "commit", "-q", "-m", "seed")

    if hook is not None:
        hook_path = hooks_dir / "pre-commit"
        hook_path.write_text(hook, encoding="utf-8")
        hook_path.chmod(0o755)

    (repo / _CACHE_DIR).mkdir()
    for rel in _CACHE_FILES:
        (repo / rel).write_text("generated\n", encoding="utf-8")
    return repo


def _drive_collector(repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Run the real collector against ``repo``; return (head_before, head_after)."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import (
        _MoveTaskState,
        _mt_commit_lane_deliverables,
    )
    from specify_cli.workspace.context import ResolvedWorkspace

    resolved = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name=f"{_MISSION_SLUG}-lane-a",
        worktree_path=repo,
        branch_name=_LANE_BRANCH,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )
    monkeypatch.setattr(_tasks, "resolve_workspace_for_wp", lambda *a, **k: resolved)
    st = _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=_MISSION_SLUG,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=True,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=True,
        json_output=False,
    )
    st.main_repo_root = repo
    st.mission_slug = _MISSION_SLUG
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    _mt_commit_lane_deliverables(st)
    return head_before, _git(repo, "rev-parse", "HEAD").strip()


def _committed_paths(repo: Path, sha: str) -> set[str]:
    out = _git(repo, "show", "--name-only", "--pretty=format:", sha)
    return {line for line in out.splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# SC-001: the issue's fixture -- untracked directory, empty hooks dir
# ---------------------------------------------------------------------------


def test_collector_commits_an_untracked_directory_without_blaming_a_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """RED on the pre-fix collector: it forwards ``.zig-cache`` and reports "could
    not auto-commit ... a pre-commit hook staged them" although the commit landed."""
    repo = _make_fixture(tmp_path)

    head_before, head_after = _drive_collector(repo, monkeypatch)
    output = "".join(capsys.readouterr())

    assert head_after != head_before, "the collector must commit the lane's deliverables"
    committed = _committed_paths(repo, head_after)
    assert committed == set(_CACHE_FILES), f"the commit must carry exactly the directory's files; got {sorted(committed)!r}"
    assert "pre-commit hook" not in output, f"git expanded the requested directory; no hook is involved. Output: {output!r}"
    assert "could not auto-commit" not in output, f"the commit landed, so it cannot be reported as failed. Output: {output!r}"
    assert "Committed lane deliverables" in output, f"the collector must report the commit; got {output!r}"
    assert not _git(repo, "status", "--porcelain").strip(), "the lane tree is clean after the commit"


# ---------------------------------------------------------------------------
# SC-002: a GENUINE unrequested-path commit is still caught and truthful
# ---------------------------------------------------------------------------


def test_genuine_hook_sweep_still_raises_unrequested_paths(tmp_path: Path) -> None:
    """Seam-level negative control: the extra-path guard must not go vacuous.

    Same fixture shape as the regression, but with a real ``pre-commit`` hook that
    runs ``git add -u``: committing explicit files, the guard still fires and names
    ONLY the swept path.
    """
    from specify_cli.git.commit_helpers import SafeCommitUnrequestedPaths, safe_commit

    repo = _make_fixture(tmp_path, hook=_SWEEPING_HOOK)
    (repo / _UNRELATED).write_text("v2 (operator edit)\n", encoding="utf-8")

    with pytest.raises(SafeCommitUnrequestedPaths) as excinfo:
        safe_commit(
            repo_root=repo,
            worktree_root=repo,
            destination_ref=_LANE_BRANCH,
            message="commit the requested files",
            paths=tuple(repo / rel for rel in _CACHE_FILES),
        )

    err = excinfo.value
    assert err.error_code == "SAFE_COMMIT_UNREQUESTED_PATHS"
    assert err.extra_paths == (_UNRELATED,), f"only the genuinely swept path may be reported; got {err.extra_paths!r}"
    assert err.commit_sha, "the error must carry the SHA of the commit that landed"


def test_collector_reports_a_landed_commit_after_a_hook_sweep(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """FR-004: a landed commit is never rendered as an untouched failed attempt.

    The hook stages a path the collector never requested, so the post-landing guard
    fires after HEAD moved; the collector must say the deliverables landed, name the
    SHA, and name the swept path.
    """
    repo = _make_fixture(tmp_path, hook=_INJECTING_HOOK)

    head_before, head_after = _drive_collector(repo, monkeypatch)
    output = "".join(capsys.readouterr())

    assert head_after != head_before, "the commit landed even though a hook staged an extra path"
    assert _INJECTED in _committed_paths(repo, head_after), "fixture precondition: the hook's staged path landed"
    assert "could not auto-commit" not in output, f"a landed commit must not be reported as failed; got {output!r}"
    assert head_after[:7] in output or head_after in output, f"the report must name the landed SHA ({head_after}); got {output!r}"
    assert _INJECTED in output, f"the report must name the swept path; got {output!r}"


# ---------------------------------------------------------------------------
# NFR-001: one expanded status probe, no added git round trip
# ---------------------------------------------------------------------------


def test_collector_uses_one_expanded_status_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The expansion is the SAME single ``git status`` invocation, widened flag only."""
    from specify_cli.cli.commands.agent import tasks_move_task as _mt

    calls: list[dict[str, object]] = []
    real_status_entries = _mt.status_entries

    def _spy(*args: object, **kwargs: object):
        calls.append(dict(kwargs))
        return real_status_entries(*args, **kwargs)

    monkeypatch.setattr(_mt, "status_entries", _spy)

    git_argv: list[list[str]] = []
    real_run = subprocess.run

    def _run(argv, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(argv, (list, tuple)) and argv and str(argv[0]).endswith("git"):
            git_argv.append([str(part) for part in argv])
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _run)

    repo = _make_fixture(tmp_path)
    _drive_collector(repo, monkeypatch)

    assert calls == [{"untracked": "all"}], f"the collector must read untracked entries EXPANDED (one probe); got {calls!r}"
    status_calls = [argv for argv in git_argv if "status" in argv]
    assert len(status_calls) == 1, f"exactly one git status probe may run; got {status_calls!r}"


def test_collector_reports_a_pre_mutation_failure_as_not_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The other half of the truthful-reporting arm: no landed SHA means no commit.

    ``SafeCommitRecoveryFailed`` is also raised BEFORE any commit when the requested
    paths' staged state could not be captured; that one must keep the "could not
    auto-commit" wording, or the operator is told to look at a commit that does not
    exist.
    """
    from specify_cli.git import commit_helpers

    def _raise_pre_mutation_failure(*args: object, **kwargs: object) -> None:
        # The collector imports ``safe_commit`` from ``specify_cli.git`` at call time,
        # so the seam symbol to patch is the one in ``commit_helpers``.
        raise commit_helpers.SafeCommitRecoveryFailed("safe_commit: refusing to mutate index; could not capture pre-existing staged state.")

    monkeypatch.setattr("specify_cli.git.safe_commit", _raise_pre_mutation_failure)
    repo = _make_fixture(tmp_path)

    head_before, head_after = _drive_collector(repo, monkeypatch)
    output = "".join(capsys.readouterr())

    assert head_after == head_before, "a pre-mutation failure cannot move HEAD"
    assert "could not auto-commit" in output, f"no commit landed, so the failure wording must stay; got {output!r}"
    assert "landed on" not in output, f"nothing landed; the report must not claim otherwise. Got {output!r}"
