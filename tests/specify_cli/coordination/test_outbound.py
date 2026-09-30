"""SaaS-sink fanout deferral tests (T041, FR-022, NFR-009, SC-09).

Covers the two critical paths:

1. **Success path**: ``queue_saas_emission`` registers the emission;
   ``BookkeepingTransaction.commit`` succeeds; deferred outbound runs
   and the sink receives the event.
2. **Rollback path**: ``queue_saas_emission`` registers the emission;
   ``BookkeepingTransaction.commit`` fails (forced); rollback runs;
   the sink receives **zero** events (NFR-009 / SC-09).

The forced-failure path uses a pre-commit hook that rejects every
commit — the same mechanism #1348 used to expose the bug, so the test
is faithful to the real-world failure mode.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination.outbound import queue_saas_emission
from specify_cli.coordination.transaction import (
    BookkeepingCommitFailed,
    BookkeepingTransaction,
)
from specify_cli.status.emit import build_status_event
from specify_cli.status.models import StatusEvent

# Import the recording sink fixture by registering its module as a
# pytest plugin.  Equivalent to ``from tests.conftest_saas_sink import
# mock_saas_sink`` but avoids the unused-import warning and is the
# pytest-idiomatic way to expose a cross-package fixture.
pytest_plugins = ("tests.conftest_saas_sink",)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


MISSION_SLUG = "outbound-feature"
MID8 = "01J6OUTBD"
MISSION_ID = "01J6OUTBD00000000000000000"  # 26-char placeholder ULID
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "seed.txt")
    _git(r, "commit", "-q", "-m", "initial")
    _git(r, "branch", COORD_BRANCH)
    return r


def _make_event(wp_id: str = "WP01") -> StatusEvent:
    return build_status_event(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane="claimed",
        actor="outbound-test",
    )


# ---------------------------------------------------------------------------
# T041 — success path
# ---------------------------------------------------------------------------


def test_saas_emits_after_commit_success(repo: Path, mock_saas_sink: Any) -> None:
    """On commit success, the deferred outbound fires and the sink receives
    exactly one event corresponding to the appended StatusEvent."""
    event = _make_event()

    with BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation="test_outbound_success",
    ) as txn:
        txn.append_event(event)
        queue_saas_emission(txn, event)
        # commit() is called by __exit__ on the happy path; the
        # deferred outbound also runs in __exit__ after the commit.

    # After the context manager exits successfully, the sink should
    # have received exactly one call.
    assert mock_saas_sink.call_count == 1, (
        f"expected 1 SaaS emission; got {mock_saas_sink.call_count}"
    )
    assert mock_saas_sink.last_kwargs["metadata"].causation_id == event.event_id
    assert mock_saas_sink.last_kwargs["wp_id"] == event.wp_id
    assert mock_saas_sink.last_kwargs["from_lane"] == str(event.from_lane)
    assert mock_saas_sink.last_kwargs["to_lane"] == str(event.to_lane)


def test_saas_emission_preserves_mission_slug_and_repo_root(
    repo: Path, mock_saas_sink: Any,
) -> None:
    """The deferred call routes through the canonical WPStatusChanged kwargs."""
    event = _make_event()

    with BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation="test_outbound_kwargs",
    ) as txn:
        txn.append_event(event)
        queue_saas_emission(txn, event)

    assert mock_saas_sink.call_count == 1
    _, kwargs = mock_saas_sink.calls[-1]
    assert kwargs["mission_slug"] == MISSION_SLUG
    assert kwargs["mission_id"] == MISSION_ID
    # #125: the emitting checkout root travels with the fan-out kwargs so the
    # Zeitgeist bridge can resolve credentials from it instead of cwd.
    assert kwargs["repo_root"] == repo


# ---------------------------------------------------------------------------
# T041 / NFR-009 / SC-09 — rollback path
# ---------------------------------------------------------------------------


def _install_rejecting_pre_commit_hook(repo: Path, hooks_dir: Path) -> None:
    """Install a pre-commit hook in ``hooks_dir`` that always fails.

    The hook is written into a custom hooks directory so it applies to
    every worktree of ``repo`` (the coord worktree will inherit it via
    git config).
    """
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks_dir))


def test_saas_does_not_emit_on_commit_failure(
    repo: Path,
    tmp_path: Path,
    mock_saas_sink: Any,
) -> None:
    """SC-09 / NFR-009: a forced commit failure leaves the sink untouched."""
    # Install a hook that rejects every commit, then mint the txn.
    _install_rejecting_pre_commit_hook(repo, tmp_path / "hooks")

    event = _make_event()

    with pytest.raises(BookkeepingCommitFailed), BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation="test_outbound_rollback",
    ) as txn:
        txn.append_event(event)
        queue_saas_emission(txn, event)
            # __exit__'s implicit commit will fail because of the hook;
            # BookkeepingCommitFailed propagates and the deferred queue
            # is intentionally SKIPPED.

    # Critical assertion: no SaaS emission for a rolled-back commit.
    assert mock_saas_sink.call_count == 0, (
        f"NFR-009 violated: SaaS sink received {mock_saas_sink.call_count} "
        f"emission(s) after a forced commit failure; expected 0"
    )
