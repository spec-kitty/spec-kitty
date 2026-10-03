"""coord-artifact-single-home-01M3V4BE WP09: the two new decision CLI refusal arms.

Covers the ``COORD_SEED_FORK_REFUSED`` and ``STATUS_LOCK_HELD`` except arms
``open_decision``/``_terminal_command`` can now reach (via ``write_dir``),
on all four verbs (open / resolve / defer / cancel) -- previously only
``StatusReadPathNotFound`` was caught, so both would have surfaced as raw
tracebacks instead of the structured ``{"error", "code", "next_step"}``
envelope every other refusal on this module renders.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.coordination.coord_seed import CoordSeedForkRefused
from specify_cli.status.locking import FeatureStatusLockTimeoutError
from tests._factories.coord_mission import make_fork_fixture, make_prefix_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _invoke(args: list[str], cwd: Path) -> Any:
    with contextlib.chdir(cwd):
        return runner.invoke(agent_app, args, catch_exceptions=True)


def _last_json(output: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(output.strip().splitlines()[-1])
    return payload


# ---------------------------------------------------------------------------
# COORD_SEED_FORK_REFUSED -- real fixture, real genuine fork, on cmd_open.
# ---------------------------------------------------------------------------


def test_decision_open_renders_coord_seed_fork_refused() -> None:
    """A genuinely EMPTY-with-pending-seed, forked Mission (WP02 fork builder
    (a): both copies present, NEITHER committed in the coord worktree yet --
    the coordination tip carries no COORD-kind blob, so a seed IS pending and
    the fork-check runs) refuses with the structured envelope, not a raw
    traceback."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fixture = make_fork_fixture(Path(tmp), "root_uncommitted_coord_untracked", MissionTopology.COORD, stream="status_log")

        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                fixture.mission_slug,
                "--flow",
                "specify",
                "--slot-key",
                "s.new",
                "--input-key",
                "new",
                "--question",
                "New?",
                "--actor",
                "test",
            ],
            fixture.repo_root,
        )

        assert result.exit_code != 0
        payload = _last_json(result.output)
        assert payload["code"] == "COORD_SEED_FORK_REFUSED"
        assert "doctor coordination" in payload["next_step"]
        ledger_dir = fixture.root_mission_dir / "decisions"
        assert not ledger_dir.exists() or list(ledger_dir.glob("DM-*.md")) == [], "a refused write_dir resolution must leave the ledger untouched (NFR-002)"


# ---------------------------------------------------------------------------
# STATUS_LOCK_HELD -- monkeypatched at the service boundary (deterministic;
# a genuine lock-contention race is covered by status/locking's own tests).
# ---------------------------------------------------------------------------


def _lock_timeout_error() -> FeatureStatusLockTimeoutError:
    return FeatureStatusLockTimeoutError(
        "mission status lock held by another process",
        lock_path=Path("/worktrees/fixture/fake.lock"),
        timeout=5.0,
        holder={"pid": 12345},
    )


@pytest.mark.parametrize(
    ("verb", "service_fn", "args"),
    [
        (
            "open",
            "open_decision",
            ["decision", "open", "--mission", "m", "--flow", "specify", "--slot-key", "s.a", "--input-key", "a", "--question", "Q?", "--actor", "t"],
        ),
        ("resolve", "resolve_decision", ["decision", "resolve", "dec-1", "--mission", "m", "--final-answer", "a", "--actor", "t"]),
        ("defer", "defer_decision", ["decision", "defer", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
        ("cancel", "cancel_decision", ["decision", "cancel", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
    ],
)
def test_decision_verb_renders_status_lock_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, service_fn: str, args: list[str]) -> None:
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    cli_args = [a if a != "m" else coord.mission_slug for a in args]

    def _raise(*_a: object, **_k: object) -> None:
        raise _lock_timeout_error()

    monkeypatch.setattr(f"specify_cli.cli.commands.decision.{service_fn}", _raise)

    result = _invoke(cli_args, coord.repo_root)

    assert result.exit_code != 0, f"{verb} must exit non-zero on a lock timeout"
    payload = _last_json(result.output)
    assert payload["code"] == "STATUS_LOCK_HELD"
    assert "retry" in payload["next_step"].lower()


@pytest.mark.parametrize(
    ("verb", "service_fn", "args"),
    [
        ("resolve", "resolve_decision", ["decision", "resolve", "dec-1", "--mission", "m", "--final-answer", "a", "--actor", "t"]),
        ("defer", "defer_decision", ["decision", "defer", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
        ("cancel", "cancel_decision", ["decision", "cancel", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
    ],
)
def test_decision_verb_renders_coord_seed_fork_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, service_fn: str, args: list[str]) -> None:
    """resolve/defer/cancel each reach the SAME ``_write_events_path`` pre-resolve
    (``_terminal_command``) ``open`` does -- exercised here via monkeypatch for
    determinism (the real-fixture reproduction above already proves the
    production fork-check itself raises this on ``open``)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    cli_args = [a if a != "m" else coord.mission_slug for a in args]

    def _raise(*_a: object, **_k: object) -> None:
        raise CoordSeedForkRefused(
            root_path=coord.repo_root,
            coord_path="kitty-specs/demo/status.events.jsonl",
            coord_ref=coord.coordination_branch,
            first_divergence_root="A",
            first_divergence_coord="B",
            reconcile_steps=("inspect with `spec-kitty doctor decisions`",),
        )

    monkeypatch.setattr(f"specify_cli.cli.commands.decision.{service_fn}", _raise)

    result = _invoke(cli_args, coord.repo_root)

    assert result.exit_code != 0, f"{verb} must exit non-zero on a coordination fork refusal"
    payload = _last_json(result.output)
    assert payload["code"] == "COORD_SEED_FORK_REFUSED"
    assert "doctor coordination" in payload["next_step"]


# ---------------------------------------------------------------------------
# COORD_BRANCH_UNDECLARED_AND_ABSENT -- review cycle 2 (B1-residual, Decision
# plan.design.undeclared-coord-branch). Monkeypatched at the service boundary
# (deterministic; the real-fixture reproduction lives in
# tests/coordination/test_coord_seed.py).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verb", "service_fn", "args"),
    [
        (
            "open",
            "open_decision",
            ["decision", "open", "--mission", "m", "--flow", "specify", "--slot-key", "s.a", "--input-key", "a", "--question", "Q?", "--actor", "t"],
        ),
        ("resolve", "resolve_decision", ["decision", "resolve", "dec-1", "--mission", "m", "--final-answer", "a", "--actor", "t"]),
        ("defer", "defer_decision", ["decision", "defer", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
        ("cancel", "cancel_decision", ["decision", "cancel", "dec-1", "--mission", "m", "--rationale", "why", "--actor", "t"]),
    ],
)
def test_decision_verb_renders_coord_branch_undeclared_and_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, service_fn: str, args: list[str]
) -> None:
    from specify_cli.coordination.coord_seed import CoordBranchUndeclaredAndAbsent

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    cli_args = [a if a != "m" else coord.mission_slug for a in args]

    def _raise(*_a: object, **_k: object) -> None:
        raise CoordBranchUndeclaredAndAbsent(mission_slug=coord.mission_slug, derived_branch="kitty/mission-demo-01ABCDEF")

    monkeypatch.setattr(f"specify_cli.cli.commands.decision.{service_fn}", _raise)

    result = _invoke(cli_args, coord.repo_root)

    assert result.exit_code != 0, f"{verb} must exit non-zero on an undeclared-and-absent coordination branch"
    payload = _last_json(result.output)
    assert payload["code"] == "COORD_BRANCH_UNDECLARED_AND_ABSENT"
    assert "backfill-topology" in payload["next_step"]
