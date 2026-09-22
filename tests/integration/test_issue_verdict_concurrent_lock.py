"""#4884 (P1): concurrent ``issue-verdict`` lost-update -- the issue-matrix
twin of #4858's acceptance-matrix fix.

``do_issue_verdict`` (``cli/commands/agent/issue_verdict.py``) did an
UNLOCKED read-modify-write: read the full ``issue-matrix.json`` row map,
mutate ONE row in memory, then serialize the WHOLE (stale) map back via
``write_issue_matrix``. Two concurrent ``issue-verdict`` calls for DIFFERENT
issues race: the loser's write silently drops the winner's already-committed
row.

The fix (mirrors #4858's ``acceptance_verdict._locked_reread_splice_and_write``
exactly): the candidate row's VALUE is still computed from a pre-lock
snapshot (``_resolve_issue_row_update``), but the actual re-read + splice +
write-and-commit now all happen inside ONE ``feature_status_lock`` critical
section (``_locked_reread_splice_and_write``), keyed on the mission
directory name (never a bare slug), and the write is routed through
``kernel.atomic.atomic_write`` (never a bare ``path.write_text``).

Each guard below is independently falsifiable by a spy/ordering assertion
(RED on base: the lock/atomic seam does not exist yet), not review-only --
same craft #4858 used, reviewer-validated there.

**Test-design concession (mirrors #4858's own precedent, documented there
too):** ``TestConcurrentIssueVerdictLostUpdate`` drives the interleaving by
hooking ``_load_raw_rows`` -- present, under the SAME name, on both base and
fixed code -- rather than a fix-only symbol, and triggers the sibling
(non-reentrant) BEFORE the lock is ever acquired, so it never falls into the
lock-reentrancy trap (a hook fired *inside* the critical section would let a
reentrant nested acquire proceed anyway, proving nothing about the fix). This
keeps the interleaving test both RED-on-base and a genuine, non-vacuous
GREEN-on-fix, so the concurrency-gate spies below are a *complement*, not a
fallback.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git_topology import git_common_dir
from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent import issue_verdict as iv_command
from specify_cli.cli.commands.agent.issue_verdict import IssueVerdictError, do_issue_verdict
from specify_cli.status import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    feature_status_lock,
)
from specify_cli.status.locking import feature_status_lock_path
from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

# Reused verbatim (not duplicated) -- the shared golden-path git+mission-
# creation primitives #2462 already established (C-001 in spirit).
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WORK_BRANCH = "issue-verdict-lock-work"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _head(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").stdout.strip()


def _init_flat_issue_mission(tmp_path: Path, slug: str) -> tuple[Path, Path, str]:
    """A real, flat (non-coord) mission repo for the issue-matrix lock path.

    Returns ``(repo_root, feature_dir, mission_slug)`` -- ``create_mission_
    core`` mints the on-disk slug as ``<slug>-<mid8>`` (never the bare
    request slug), so every caller must resolve missions by the RETURNED
    ``mission_slug``, not the string it passed in.
    """
    _init_git_repo(tmp_path, branch=_WORK_BRANCH)
    result = _create_mission(tmp_path, slug, MissionTopology.SINGLE_BRANCH)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", f"init: {slug} mission baseline")
    return tmp_path, result.feature_dir, result.mission_slug


class _OrderTrackingContext:
    """Wrap a context manager, appending ``"lock_exit"`` on exit.

    Mirrors ``test_acceptance_verdict_command.py``'s helper of the same
    name/shape (#4858) -- lets a single ``order`` list record ``lock_enter``
    before ``__enter__`` and ``lock_exit`` after ``__exit__`` around the
    REAL lock's own body.
    """

    def __init__(self, inner: object, order: list[str]) -> None:
        self._inner = inner
        self._order = order

    def __enter__(self) -> object:
        return self._inner.__enter__()  # type: ignore[attr-defined]

    def __exit__(self, *exc_info: object) -> object:
        result = self._inner.__exit__(*exc_info)  # type: ignore[attr-defined]
        self._order.append("lock_exit")
        return result


# ===========================================================================
# Concurrency-gate spies -- each independently falsifiable, RED on base
# (the lock/atomic seam this suite tests does not exist there).
# ===========================================================================


class TestLockCompositionGateSpies:
    def test_lock_acquired_with_correct_key_and_path_under_common_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The critical section acquires the lock exactly once, keyed on the
        mission DIRECTORY name (never a bare slug), with a resolved lock
        path under the git common dir."""
        slug = "issue-lock-key"
        repo_root, feature_dir, mission_slug = _init_flat_issue_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        calls: list[tuple[Path, str, float]] = []

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            calls.append((repo_root_arg, lock_key, timeout))
            return feature_status_lock(repo_root_arg, lock_key, timeout=timeout)

        monkeypatch.setattr(iv_command, "feature_status_lock", _spy_lock)

        result = do_issue_verdict(
            mission=mission_slug,
            issue="#1",
            verdict="fixed",
            actor="tester",
            evidence_ref="ev",
            repo_root=repo_root,
        )
        assert result["ok"] is True, result

        assert len(calls) == 1, "the critical section must acquire the lock exactly once"
        called_repo_root, lock_key, timeout = calls[0]
        assert lock_key == feature_dir.name
        assert timeout == BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS
        lock_path = feature_status_lock_path(called_repo_root, lock_key)
        common_dir = git_common_dir(repo_root)
        assert lock_path.is_relative_to(common_dir), "the lock file must live under the git common dir"

    def test_reread_and_write_happen_strictly_inside_the_lock(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Strict order ``read -> lock.enter -> read -> write -> lock.exit``:
        the FIRST read is the pre-lock candidate-row computation, the SECOND
        is the locked re-read -- a re-read placed outside the lock would
        still pass a single-threaded harness while reopening the race."""
        slug = "issue-strict-order"
        repo_root, _feature_dir, mission_slug = _init_flat_issue_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        order: list[str] = []

        def _spy_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            order.append("enter")
            cm = feature_status_lock(repo_root_arg, lock_key, timeout=timeout)
            return _OrderTrackingContext(cm, order)

        real_load = iv_command._load_raw_rows

        def _spy_load(json_path: Path):
            order.append("read")
            return real_load(json_path)

        real_write = iv_command.write_issue_matrix

        def _spy_write(**kwargs: object):
            order.append("write")
            return real_write(**kwargs)

        monkeypatch.setattr(iv_command, "feature_status_lock", _spy_lock)
        monkeypatch.setattr(iv_command, "_load_raw_rows", _spy_load)
        monkeypatch.setattr(iv_command, "write_issue_matrix", _spy_write)

        result = do_issue_verdict(mission=mission_slug, issue="#1", verdict="fixed", actor="tester", repo_root=repo_root)
        assert result["ok"] is True, result

        assert order == ["read", "enter", "read", "write", "lock_exit"], order

    def test_write_issue_matrix_routes_through_atomic_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The canonical writer routes through ``kernel.atomic.atomic_write``,
        not a bare ``path.write_text``."""
        from kernel.atomic import atomic_write as real_atomic_write

        slug = "issue-atomic-write"
        repo_root, feature_dir, mission_slug = _init_flat_issue_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        calls: list[Path] = []

        def _spy_atomic_write(path: Path, content: str | bytes, *, mkdir: bool = False) -> None:
            calls.append(path)
            return real_atomic_write(path, content, mkdir=mkdir)

        monkeypatch.setattr("specify_cli.tasks.issue_matrix.atomic_write", _spy_atomic_write)

        result = do_issue_verdict(mission=mission_slug, issue="#1", verdict="fixed", actor="tester", repo_root=repo_root)
        assert result["ok"] is True, result

        assert calls, "write_issue_matrix must route through kernel.atomic.atomic_write"
        assert calls[0] == feature_dir / "issue-matrix.json"

    def test_fail_closed_on_lock_timeout_never_writes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """On a lock-acquisition timeout: no write ever happens, a structured
        ``IssueVerdictError`` (code ``"lock_timeout"``) is raised, and it
        never falls back to an unlocked write."""
        slug = "issue-fail-closed"
        repo_root, _feature_dir, mission_slug = _init_flat_issue_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)
        head_before = _head(repo_root)

        def _timeout_lock(repo_root_arg: Path, lock_key: str, *, timeout: float = -1):
            raise FeatureStatusLockTimeoutError(
                "simulated timeout",
                lock_path=Path("/nonexistent/fake.status.lock"),
                timeout=timeout,
            )

        write_calls: list[object] = []
        real_write = iv_command.write_issue_matrix

        def _spy_write(**kwargs: object):
            write_calls.append(kwargs)
            return real_write(**kwargs)

        monkeypatch.setattr(iv_command, "feature_status_lock", _timeout_lock)
        monkeypatch.setattr(iv_command, "write_issue_matrix", _spy_write)

        with pytest.raises(IssueVerdictError) as excinfo:
            do_issue_verdict(mission=mission_slug, issue="#1", verdict="fixed", actor="tester", repo_root=repo_root)

        assert excinfo.value.code == "lock_timeout"
        assert not write_calls, "a lock-acquisition timeout must never reach the write"
        assert _head(repo_root) == head_before, "no commit must occur on a fail-closed timeout"


# ===========================================================================
# The lost-update itself -- a real, deterministic, non-reentrant interleaving.
# ===========================================================================


class TestConcurrentIssueVerdictLostUpdate:
    def test_sibling_row_survives_stale_snapshot_write(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A sibling ``issue-verdict`` call for issue #B fully commits WHILE
        this invocation (#A) is still holding its pre-lock row snapshot.
        Both rows must survive.

        RED on base: the sibling fires on the (only) unlocked read; the
        outer invocation then serializes its stale (pre-sibling) snapshot
        plus its own row, silently dropping #B.

        GREEN on fix: the sibling fires on the PRE-lock read (candidate-row
        computation only); the invocation's actual write comes from the
        SECOND, freshly re-read (inside-the-lock) row map, which already
        includes #B's committed row.
        """
        slug = "issue-concurrent-flat"
        repo_root, feature_dir, mission_slug = _init_flat_issue_mission(tmp_path, slug)
        monkeypatch.chdir(repo_root)

        triggered = {"done": False}
        real_load = iv_command._load_raw_rows

        def _wrapper(json_path: Path):
            result = real_load(json_path)
            if not triggered["done"]:
                triggered["done"] = True
                # Fires BEFORE any lock is acquired by the outer (#A)
                # invocation -- a completely independent, non-nested lock
                # acquire/release by this sibling, never a reentrant one.
                inner = do_issue_verdict(
                    mission=mission_slug,
                    issue="#B",
                    verdict="fixed",
                    actor="sibling-b",
                    evidence_ref="b-evidence",
                    repo_root=repo_root,
                )
                assert inner["ok"] is True, inner
            return result

        monkeypatch.setattr(iv_command, "_load_raw_rows", _wrapper)

        outer = do_issue_verdict(
            mission=mission_slug,
            issue="#A",
            verdict="in-mission",
            actor="sibling-a",
            evidence_ref="a-evidence",
            repo_root=repo_root,
        )
        assert outer["ok"] is True, outer

        after = {row.issue: row for row in load_issue_matrix(feature_dir)}
        assert set(after) == {"#A", "#B"}, f"a concurrently-committed sibling row must never be dropped by a stale-snapshot overwrite (#4884): got {list(after)}"
        assert after["#B"].verdict.value == "fixed"
        assert after["#B"].evidence_ref == "b-evidence", "sibling evidence must survive intact"
        assert after["#A"].verdict.value == "in-mission"
        assert after["#A"].evidence_ref == "a-evidence"
