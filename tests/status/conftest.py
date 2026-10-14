"""Shared fixtures for status model and transition tests."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.core.paths import WorkspaceRootNotFound, resolve_canonical_root
from specify_cli.status.models import (
    DoneEvidence,
    Lane,
    RepoEvidence,
    ReviewApproval,
    StatusEvent,
    StatusSnapshot,
    VerificationResult,
)
from specify_cli.status.store import append_event
from specify_cli.status.wp_state import wp_state_for

_THIS_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Hermetic canonical-root resolution (#142)
# ---------------------------------------------------------------------------


def pin_canonical_root_inside_sandbox(root: Path) -> bool:
    """Make *root* itself the git root so root resolution stops inside it.

    Lifecycle and status writers resolve their lock root by walking up from a
    log path to the nearest ``.git`` (``resolve_canonical_root``) and then
    ``mkdir`` ``<root>/.git/spec-kitty-locks/``. Mission fixtures in this
    package build feature directories under plain ``tmp_path`` without a
    repo, so when an ancestor of basetemp is itself a git checkout, the lock
    lands in *that* checkout -- and if it is read-only,
    :func:`append_lifecycle_event` swallows the resulting ``PermissionError``
    as a best-effort ``OSError`` and persists nothing, silently failing every
    event-recording assertion (130 nodes red in the #142 repro).

    Returns ``True`` when pinning happened: *root* had no ``.git`` of its own
    and resolution escaped above it. Hosts without an ambient ancestor repo
    (the common case -- basetemp lives under ``/tmp``) are untouched.
    """
    try:
        resolved = resolve_canonical_root(root)
    except WorkspaceRootNotFound:
        return False
    if resolved == root or (root / ".git").exists():
        return False
    completed = subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        # No usable git binary: a bare marker directory is still enough for
        # resolve_canonical_root's rule 1 (a .git directory ends the walk).
        (root / ".git").mkdir(exist_ok=True)
    return True


@pytest.fixture(autouse=True)
def _hermetic_canonical_root(tmp_path: Path) -> None:
    """Keep canonical-root resolution inside this test's sandbox (#142).

    Runs before the mission fixtures so every feature directory built under
    ``tmp_path`` resolves to a lock root inside the sandbox instead of into
    whatever git checkout happens to sit above basetemp. See
    :func:`pin_canonical_root_inside_sandbox` for the failure mode.
    """
    pin_canonical_root_inside_sandbox(tmp_path)


# ---------------------------------------------------------------------------
# T027 — shared seed helper + fixture (replaces ~12 per-file _seed_planned copies)
# ---------------------------------------------------------------------------

# Unique event-id counter (module-level, monotonic).
_SEED_COUNTER = 0


def _make_seed_event_id() -> str:
    global _SEED_COUNTER  # noqa: PLW0603 — intentional module-level counter for unique IDs
    _SEED_COUNTER += 1
    return f"01SEED{_SEED_COUNTER:020d}"


def seed_wp_to_planned(
    feature_dir: Path,
    wp_id: str,
    slug: str = "test-feature",
) -> None:
    """Seed a WP from genesis -> planned (the finalize-tasks seed).

    Writes directly to the event log (no emit pipeline), so no fan-out,
    no git transaction, and no emit side-effects are triggered. This mirrors
    what ``finalize-tasks`` does before the lane lifecycle begins.

    T029 (FR-017) — validates the source state via the operator-mandated FSM
    API (``wp_state_for(...).current_lane`` / ``.may_transition_to()``) before
    writing, locking those methods in as real callers.

    Importable directly from this module for test files that prefer plain
    function calls over the pytest fixture form.
    """
    # T029: validate via the mandated FSM interface before writing.
    genesis_state = wp_state_for(Lane.GENESIS)
    assert genesis_state.current_lane == Lane.GENESIS
    assert genesis_state.may_transition_to(Lane.PLANNED)

    # A finalized WP always has an authored roster surface. Most lifecycle
    # tests exercise lane mechanics rather than subtask completion, so seed an
    # explicit empty roster ("nothing to block on") instead of relying on the
    # retired caller-supplied ``subtasks_complete`` bypass.
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}.md"
    existing_wp_files = [
        candidate
        for candidate in tasks_dir.glob("*.md")
        if candidate.stem == wp_id or candidate.stem.startswith(f"{wp_id}-") or candidate.stem.startswith(f"{wp_id}_") or candidate.stem.startswith(f"{wp_id}.")
    ]
    if not existing_wp_files:
        wp_file.write_text(
            f"---\nwork_package_id: {wp_id}\nsubtasks: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    append_event(
        feature_dir,
        StatusEvent(
            event_id=_make_seed_event_id(),
            mission_slug=slug,
            wp_id=wp_id,
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="seed",
            force=False,
            execution_mode="worktree",
            reason="seed",
        ),
    )


@pytest.fixture
def seed_to_planned() -> Callable[[Path, str, str], None]:
    """Pytest fixture returning the shared WP seed callable.

    Usage::

        def test_something(feature_dir, seed_to_planned):
            seed_to_planned(feature_dir, "WP01")
            seed_to_planned(feature_dir, "WP02", slug="my-mission")

    Delegates to :func:`seed_wp_to_planned`. Test files that prefer a plain
    import can use ``from tests.status.conftest import seed_wp_to_planned``
    directly.
    """
    return seed_wp_to_planned


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark all tests in this directory as fast."""
    for item in items:
        if _THIS_DIR in Path(item.fspath).parents:
            item.add_marker(pytest.mark.fast)


# (Removed: the _restore_zeitgeist_moment_handlers_around_every_status_test
# autouse fixture. It re-registered the Zeitgeist moment handlers around every
# status test after a test's adapters.reset_handlers() wipe. #6164 removed the
# hosted drain bridge and adapters.ensure_zeitgeist_moment_handlers() with it,
# so there is no drain producer to re-register — the empty registry a
# reset_handlers() leaves is now the correct production state.)


@pytest.fixture(autouse=True)
def _disable_saas_fanout_for_local_status_tests(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep status persistence tests local even when SaaS sync is enabled.

    The dedicated fan-out preservation tests opt out by file name because they
    intentionally exercise the adapter registry. Ordinary status tests assert
    JSONL/materialization semantics and should not start auth, tracker, or
    dashboard-daemon flows.
    """
    if Path(str(request.node.fspath)).name in ("test_emit_fanout_after_adapter.py",):
        # (test_zeitgeist_moment_handler.py was removed with the hosted drain
        # bridge, #6164; only the general emit -> adapters fan-out test remains.)
        return

    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_saas_fan_out", lambda *args, **kwargs: None)


@pytest.fixture
def sample_review_approval() -> ReviewApproval:
    return ReviewApproval(
        reviewer="reviewer-1",
        verdict="approved",
        reference="review-ref-001",
    )


@pytest.fixture
def sample_repo_evidence() -> RepoEvidence:
    return RepoEvidence(
        repo="my-org/my-repo",
        branch="kitty/mission-034-feature-lane-a",
        commit="abc1234",
        files_touched=["src/models.py", "tests/test_models.py"],
    )


@pytest.fixture
def sample_verification_result() -> VerificationResult:
    return VerificationResult(
        command="pytest tests/ -x -q",
        result="pass",
        summary="42 tests passed",
    )


@pytest.fixture
def sample_done_evidence(
    sample_review_approval: ReviewApproval,
    sample_repo_evidence: RepoEvidence,
    sample_verification_result: VerificationResult,
) -> DoneEvidence:
    return DoneEvidence(
        review=sample_review_approval,
        repos=[sample_repo_evidence],
        verification=[sample_verification_result],
    )


@pytest.fixture
def sample_status_event() -> StatusEvent:
    return StatusEvent(
        event_id="01HXYZ0123456789ABCDEFGHJK",
        mission_slug="034-feature-name",
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-02-08T12:00:00Z",
        actor="claude-opus",
        force=False,
        execution_mode="worktree",
    )


@pytest.fixture
def sample_status_event_with_evidence(
    sample_done_evidence: DoneEvidence,
) -> StatusEvent:
    return StatusEvent(
        event_id="01HXYZ0123456789ABCDEFGHJL",
        mission_slug="034-feature-name",
        wp_id="WP01",
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.DONE,
        at="2026-02-08T14:00:00Z",
        actor="reviewer-1",
        force=False,
        execution_mode="worktree",
        evidence=sample_done_evidence,
    )


@pytest.fixture
def sample_status_snapshot() -> StatusSnapshot:
    return StatusSnapshot(
        mission_slug="034-feature-name",
        materialized_at="2026-02-08T15:00:00Z",
        event_count=5,
        last_event_id="01HXYZ0123456789ABCDEFGHJM",
        work_packages={
            "WP01": {
                "lane": "done",
                "actor": "reviewer-1",
                "last_transition_at": "2026-02-08T14:00:00Z",
                "last_event_id": "01HXYZ0123456789ABCDEFGHJL",
                "force_count": 0,
            },
            "WP02": {
                "lane": "in_progress",
                "actor": "claude-opus",
                "last_transition_at": "2026-02-08T13:00:00Z",
                "last_event_id": "01HXYZ0123456789ABCDEFGHJK",
                "force_count": 0,
            },
        },
        summary={
            "planned": 0,
            "claimed": 0,
            "in_progress": 1,
            "for_review": 0,
            "in_review": 0,
            "approved": 0,
            "done": 1,
            "blocked": 0,
            "canceled": 0,
        },
    )
