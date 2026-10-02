"""Integration tests for WP06 (#1348) -- the four migrated workflow call sites.

These tests verify the contract that closes #1348:

1. ``status.events.jsonl`` is byte-identical pre/post a forced commit
   failure (SC-05, NFR-001) -- the surgical-truncate rollback in
   :class:`specify_cli.coordination.transaction.BookkeepingTransaction`
   (and the legacy-fallback truncate in
   ``_commit_workflow_change``) must preserve the SHA-256 digest of
   the event log byte-for-byte.

2. The bookkeeping commit lands on the **coordination branch**, never
   on ``main``, even when the operator is on ``main`` at the time of
   invocation (FR-005, SC-08).

3. Two lanes running in parallel produce events serialised by the
   feature-status lock (SC-02, SC-12).

The tests intentionally avoid spawning the ``spec-kitty`` binary in a
fresh subprocess for every case -- they exercise the same code paths
in-process so the assertions can be cheap and deterministic. The
forced-failure test (SC-05) uses a pre-commit hook installed at the
git level so the failure is **real**, not mocked.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

from specify_cli.coordination.transaction import (
    BookkeepingCommitFailed,
    BookkeepingTransaction,
)
from specify_cli.status.emit import build_status_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process."""
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def _init_git_repo(repo_root: Path) -> None:
    """Initialise an isolated git repo with ``main`` as the default branch."""
    _run(repo_root, "git", "init", "--initial-branch=main")
    _run(repo_root, "git", "config", "user.email", "test@example.invalid")
    _run(repo_root, "git", "config", "user.name", "WP06 Test")
    _run(repo_root, "git", "config", "commit.gpgsign", "false")
    # Seed an initial commit so HEAD exists.
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _run(repo_root, "git", "add", "README.md")
    _run(repo_root, "git", "commit", "-m", "seed")


def _make_mission(
    repo_root: Path,
    *,
    mission_slug: str = "wp06-flow-mission",
    mission_id: str = "01JZZZZZZZZZZZZZZZZZZZZZZZ",
) -> tuple[Path, str, str, str]:
    """Create the kitty-specs mission scaffold and a coord branch.

    Returns ``(feature_dir, mission_slug, mission_id, mid8)``.
    """
    mid8 = mission_id[:8]
    feature_dir = repo_root / "kitty-specs" / f"{mission_slug}-{mid8}"
    feature_dir.mkdir(parents=True, exist_ok=True)

    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "mid8": mid8,
                "coordination_branch": coord_branch,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-05-28T00:00:00+00:00",
                "friendly_name": "WP06 flow mission",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Create the coord branch from main so the coordination worktree
    # can be checked out against it.
    _run(repo_root, "git", "branch", coord_branch)

    return feature_dir, mission_slug, mission_id, mid8


def _sha256(path: Path) -> str | None:
    """Return the SHA-256 of *path*, or None if the file does not exist."""
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 — file-integrity checksum of read_bytes(), not charter freshness hashing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """A fresh git repo with an empty mission scaffold."""
    _init_git_repo(tmp_path)
    return tmp_path


@pytest.fixture()
def mission(repo_root: Path) -> dict[str, Any]:
    """Create a mission with a coordination branch and return its handles."""
    feature_dir, mission_slug, mission_id, mid8 = _make_mission(repo_root)
    return {
        "feature_dir": feature_dir,
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "coord_branch": f"kitty/mission-{mission_slug}-{mid8}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestImplementWPHappyPath:
    """`test_implement_wp_happy_path` (SC-08 + SC-12): the implement flow

    routes status writes through BookkeepingTransaction and lands the
    commit on the coordination branch, NOT on main.
    """

    def test_event_written_and_commit_lands_on_coord_branch(
        self,
        repo_root: Path,
        mission: dict[str, Any],
    ) -> None:
        coord_branch = mission["coord_branch"]
        # The event log lives inside the coord worktree, NOT the
        # planning feature_dir on main. This is the FR-024 contract:
        # the coordination branch is the canonical writer.
        coord_worktree = (
            repo_root / ".worktrees"
            / f"{mission['mission_slug']}-{mission['mid8']}-coord"
        )
        events_path = (
            coord_worktree
            / "kitty-specs"
            / f"{mission['mission_slug']}-{mission['mid8']}"
            / "status.events.jsonl"
        )

        # Capture main HEAD before the transaction so we can prove the
        # bookkeeping commit did NOT land on main.
        main_head_before = _run(repo_root, "git", "rev-parse", "main").stdout.strip()

        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation="planned -> claimed for WP01",
        ) as txn:
            event = build_status_event(
                mission_slug=mission["mission_slug"],
                mission_id=mission["mission_id"],
                wp_id="WP01",
                from_lane="planned",
                to_lane="claimed",
                actor="claude",
            )
            txn.append_event(event)
            receipt = txn.commit("chore: WP01 claimed for implementation [claude]")

        # 1. The event landed in the on-disk JSONL log in the coord worktree.
        assert events_path.exists(), f"events file missing at {events_path}"
        recorded = [json.loads(line) for line in events_path.read_text().splitlines()]
        assert recorded[-1]["wp_id"] == "WP01"
        assert recorded[-1]["to_lane"] == "claimed"

        # 2. The commit landed on the coord branch.
        coord_head = _run(repo_root, "git", "rev-parse", coord_branch).stdout.strip()
        assert receipt.commit_sha == coord_head

        # 3. main was untouched.
        main_head_after = _run(repo_root, "git", "rev-parse", "main").stdout.strip()
        assert main_head_after == main_head_before


class TestImplementFromMainCheckout:
    """`test_implement_from_main_checkout` (SC-08): even when the operator

    is on ``main``, the bookkeeping commit lands on the coord branch.
    """

    def test_commit_does_not_land_on_main(
        self,
        repo_root: Path,
        mission: dict[str, Any],
    ) -> None:
        # Operator is on main.
        _run(repo_root, "git", "checkout", "main")
        main_head_before = _run(repo_root, "git", "rev-parse", "main").stdout.strip()

        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=mission["coord_branch"],
            operation="status: WP01 claimed",
        ) as txn:
            event = build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP01",
                from_lane="planned",
                to_lane="claimed",
                actor="claude",
                mission_id=mission["mission_id"],
            )
            txn.append_event(event)

        # The commit lands on the coord branch, NOT main.
        main_head_after = _run(repo_root, "git", "rev-parse", "main").stdout.strip()
        coord_head_after = _run(
            repo_root, "git", "rev-parse", mission["coord_branch"]
        ).stdout.strip()

        assert main_head_after == main_head_before, "main must not advance"
        assert coord_head_after != main_head_before, "coord branch must advance"


class TestForcedPreCommitHookFailure:
    """`test_forced_pre_commit_hook_failure` (SC-05, SC-06, NFR-001):

    when a real pre-commit hook rejects the commit, the event log is
    rolled back **byte-identically** -- SHA-256 pre/post must match.
    No commits land on any branch.
    """

    def test_sha256_byte_equality_after_forced_failure(
        self,
        repo_root: Path,
        mission: dict[str, Any],
    ) -> None:
        coord_branch = mission["coord_branch"]
        coord_worktree = (
            repo_root / ".worktrees"
            / f"{mission['mission_slug']}-{mission['mid8']}-coord"
        )
        events_path = (
            coord_worktree
            / "kitty-specs"
            / f"{mission['mission_slug']}-{mission['mid8']}"
            / "status.events.jsonl"
        )

        # First, run a successful transaction so the event log has
        # non-trivial pre-emit state to roll back to. The first
        # transaction also creates the coord worktree on disk so the
        # events_path is real.
        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation="planned -> claimed for WP00",
        ) as txn:
            txn.append_event(build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP00", from_lane="planned", to_lane="claimed",
                actor="claude", mission_id=mission["mission_id"],
            ))

        assert events_path.exists()
        pre_sha = _sha256(events_path)
        coord_head_before = _run(
            repo_root, "git", "rev-parse", coord_branch
        ).stdout.strip()
        main_head_before = _run(repo_root, "git", "rev-parse", "main").stdout.strip()

        # Install a real pre-commit hook in the COORD worktree that
        # rejects every commit. The worktree shares the same .git dir
        # via gitlinks, but git --hooks runs from the worktree's
        # core.hooksPath which defaults to the main .git/hooks.
        hooks_dir = repo_root / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'WP06 forced rejection' >&2\nexit 1\n")
        hook.chmod(0o755)

        # Second transaction: append + commit. The pre-commit hook
        # rejects the commit; rollback truncates the event log.
        with pytest.raises(BookkeepingCommitFailed), BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation="planned -> claimed for WP01",
        ) as txn:
            event = build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP01",
                from_lane="planned",
                to_lane="claimed",
                actor="claude",
                mission_id=mission["mission_id"],
            )
            txn.append_event(event)
            txn.commit("status: WP01 claimed for implementation")

        # 1. The event log is byte-identical to the pre-emit state.
        post_sha = _sha256(events_path)
        assert post_sha == pre_sha, (
            f"event log SHA-256 changed: {pre_sha} -> {post_sha}"
        )

        # 2. No commits landed on the coord branch.
        coord_head_after = _run(
            repo_root, "git", "rev-parse", coord_branch
        ).stdout.strip()
        assert coord_head_after == coord_head_before, "coord branch must not advance"

        # 3. No commits landed on main.
        main_head_after = _run(repo_root, "git", "rev-parse", "main").stdout.strip()
        assert main_head_after == main_head_before, "main must not advance"

    def test_real_workflow_helper_restores_canonical_status_after_forced_failure(
        self,
        repo_root: Path,
        mission: dict[str, Any],
    ) -> None:
        """The real workflow helper must roll back the canonical status files."""
        import typer

        from specify_cli.coordination.workspace import CoordinationWorkspace
        from specify_cli.cli.commands.agent.workflow import _commit_workflow_change

        # WP07 re-pin (coord-artifact-single-home-01M3V4BE): the coordination
        # arm now resolves through the single write-location accessor, which
        # carries any root-checkout content onto the coordination branch the
        # FIRST time a coord-routed mission is written to (contracts/seed.md).
        # Pre-seeding the coordination surface here (an empty, already-
        # committed Mission dir with the seed trailer) means this mission is
        # no longer "first write ever" by the time the forced-failure call
        # below runs, so that one-time seed commit -- itself subject to the
        # SAME pre-commit hook this test installs -- never interleaves with
        # the rollback this test actually exercises.
        coord_worktree = CoordinationWorkspace.resolve(repo_root, mission["mission_slug"], mission["mid8"])
        coord_mission_dir = coord_worktree / "kitty-specs" / f"{mission['mission_slug']}-{mission['mid8']}"
        coord_mission_dir.mkdir(parents=True, exist_ok=True)
        (coord_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
        _run(coord_worktree, "git", "add", "kitty-specs")
        _run(
            coord_worktree,
            "git",
            "commit",
            "-m",
            f"chore({mission['mission_slug']}): seed coordination surface\n\nSpec-Kitty-Coordination-Seed: {mission['mission_id']}",
        )

        feature_dir = mission["feature_dir"]
        events_path = feature_dir / "status.events.jsonl"
        status_path = feature_dir / "status.json"
        events_path.write_text('{"event_id":"before"}\n', encoding="utf-8")
        status_path.write_text('{"before": true}\n', encoding="utf-8")
        pre_size = events_path.stat().st_size
        pre_events_sha = _sha256(events_path)
        pre_status_bytes = status_path.read_bytes()

        events_path.write_text(
            events_path.read_text(encoding="utf-8") + '{"event_id":"after"}\n',
            encoding="utf-8",
        )
        status_path.write_text('{"after": true}\n', encoding="utf-8")

        hooks_dir = repo_root / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'workflow forced rejection' >&2\nexit 1\n")
        hook.chmod(0o755)

        with pytest.raises(typer.Exit):
            _commit_workflow_change(
                repo_root=repo_root,
                feature_dir=feature_dir,
                mission_slug=mission["mission_slug"],
                target_branch="main",
                paths=[events_path, status_path],
                message="chore: Start WP01 implementation [claude]",
                operation="planned -> claimed for WP01",
                wp_id="WP01",
                pre_emit_event_size=pre_size,
                pre_emit_status_bytes=pre_status_bytes,
            )

        assert _sha256(events_path) == pre_events_sha
        assert status_path.read_bytes() == pre_status_bytes

    @pytest.mark.parametrize("iteration", list(range(10)))  # 10 of the SC-05 100
    def test_sha256_byte_equality_parametric(
        self,
        repo_root: Path,
        mission: dict[str, Any],
        iteration: int,
    ) -> None:
        """Parametric reduction of SC-05 (full 100 forced failures).

        The full 100-iteration SC-05 is enforced by the unit suite in
        ``tests/specify_cli/coordination/test_transaction.py``; this
        sample covers the end-to-end git layer.
        """
        coord_branch = mission["coord_branch"]
        coord_worktree = (
            repo_root / ".worktrees"
            / f"{mission['mission_slug']}-{mission['mid8']}-coord"
        )
        events_path = (
            coord_worktree
            / "kitty-specs"
            / f"{mission['mission_slug']}-{mission['mid8']}"
            / "status.events.jsonl"
        )

        # Seed with one successful transaction first to materialise the
        # coord worktree + non-trivial pre-emit state.
        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation=f"seed iter {iteration}",
        ) as seed_txn:
            seed_txn.append_event(build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP00", from_lane="planned", to_lane="claimed",
                actor="claude", mission_id=mission["mission_id"],
            ))

        pre_sha = _sha256(events_path)

        hooks_dir = repo_root / ".git" / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)

        with pytest.raises(BookkeepingCommitFailed), BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation=f"iter {iteration}",
        ) as txn:
            event = build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP01",
                from_lane="planned",
                to_lane="claimed",
                actor="claude",
                mission_id=mission["mission_id"],
            )
            txn.append_event(event)
            txn.commit(f"iter {iteration}")

        assert _sha256(events_path) == pre_sha


class TestTwoLanesSerialised:
    """`test_two_lanes_parallel` (SC-02, SC-12): the feature-status lock

    serialises concurrent emit attempts so events are ordered.
    """

    def test_two_concurrent_transactions_serialise(
        self,
        repo_root: Path,
        mission: dict[str, Any],
    ) -> None:
        coord_branch = mission["coord_branch"]
        coord_worktree = (
            repo_root / ".worktrees"
            / f"{mission['mission_slug']}-{mission['mid8']}-coord"
        )
        events_path = (
            coord_worktree
            / "kitty-specs"
            / f"{mission['mission_slug']}-{mission['mid8']}"
            / "status.events.jsonl"
        )

        # Seed the coord worktree by running one transaction first so
        # both concurrent threads see a pre-existing worktree (no race
        # on ``git worktree add``).
        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission["mission_id"],
            mission_slug=mission["mission_slug"],
            mid8=mission["mid8"],
            destination_ref=coord_branch,
            operation="seed coord worktree",
        ) as seed_txn:
            seed_txn.append_event(build_status_event(
                mission_slug=mission["mission_slug"],
                wp_id="WP00", from_lane="planned", to_lane="claimed",
                actor="claude", mission_id=mission["mission_id"],
            ))

        results: list[str] = []
        errors: list[BaseException] = []

        def _emit(wp_id: str) -> None:
            try:
                with BookkeepingTransaction.acquire(
                    repo_root=repo_root,
                    mission_id=mission["mission_id"],
                    mission_slug=mission["mission_slug"],
                    mid8=mission["mid8"],
                    destination_ref=coord_branch,
                    operation=f"planned -> claimed for {wp_id}",
                    timeout=20.0,
                ) as txn:
                    event = build_status_event(
                        mission_slug=mission["mission_slug"],
                        wp_id=wp_id,
                        from_lane="planned",
                        to_lane="claimed",
                        actor="claude",
                        mission_id=mission["mission_id"],
                    )
                    txn.append_event(event)
                results.append(wp_id)
            except BaseException as exc:  # noqa: BLE001 — surface in main thread
                errors.append(exc)

        t1 = threading.Thread(target=_emit, args=("WP01",))
        t2 = threading.Thread(target=_emit, args=("WP02",))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert not errors, f"parallel transactions raised: {errors}"
        assert sorted(results) == ["WP01", "WP02"]

        # Both events should be present in the event log, ordered.
        lines = events_path.read_text().splitlines()
        wp_ids_recorded = [json.loads(line)["wp_id"] for line in lines]
        assert "WP01" in wp_ids_recorded
        assert "WP02" in wp_ids_recorded
