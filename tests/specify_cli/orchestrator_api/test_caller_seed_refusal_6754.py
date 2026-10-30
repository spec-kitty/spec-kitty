"""The orchestrator-api half of the seed-refusal matrix (#6754).

Every lifecycle verb that takes a free-text ``--actor`` and records it verbatim
must refuse a caller-supplied identity shaped like a reconstruction seed:
``start-implementation``, ``start-review``, ``transition`` and ``append-history``.

The refusal is the first statement of each command body, so it fires before the
mission is resolved, before the policy is parsed, before the write lock and
before any lane allocation. The tests assert both halves of that: the structured
failure envelope (``error_code: USAGE_ERROR``, the code the outbound contract
already allows) *and* that nothing was written.

Red on the base: all four verbs exit 0 with a stored seed actor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from specify_cli.status.models import MIGRATION_ACTOR_PREFIX, SEED_SHAPED_IDENTITY_REFUSAL
from tests.specify_cli.cli.commands.test_single_branch_implement_refusals import _build_mission, _init_repo

runner = CliRunner()

_REFUSAL = SEED_SHAPED_IDENTITY_REFUSAL.format(option="--actor", prefix=MIGRATION_ACTOR_PREFIX)
_SLUG = "orch-seed-refusal"


def _refusal_for(command: str, *args: str) -> dict[str, object]:
    result = runner.invoke(app, [command, "--mission", _SLUG, "--wp", "WP01", "--actor", "migration:backfill", *args])

    assert result.exit_code == 1, result.output
    envelope = json.loads(result.stdout.strip().splitlines()[-1])
    assert envelope["success"] is False
    assert envelope["error_code"] == "USAGE_ERROR"
    assert envelope["command"] == f"orchestrator-api.{command}"
    assert envelope["data"]["message"] == _REFUSAL
    return envelope


@pytest.mark.fast
def test_start_implementation_refuses_a_caller_supplied_seed() -> None:
    _refusal_for("start-implementation", "--policy", "{}")


@pytest.mark.fast
def test_start_review_refuses_a_caller_supplied_seed() -> None:
    _refusal_for("start-review", "--policy", "{}")


@pytest.mark.fast
def test_transition_refuses_a_caller_supplied_seed() -> None:
    _refusal_for("transition", "--to", "claimed", "--policy", "{}")


@pytest.mark.fast
def test_append_history_refuses_a_caller_supplied_seed() -> None:
    _refusal_for("append-history", "--note", "seeded")


@pytest.mark.integration
@pytest.mark.git_repo
def test_a_refused_transition_leaves_the_event_log_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal precedes resolution, the lock and the emit: the log does not move at all."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    feature_dir = _build_mission(repo, _SLUG, "01ORCHREFUSAL0000000000001")
    events_path = feature_dir / "status.events.jsonl"
    before = events_path.read_bytes() if events_path.exists() else None

    result = runner.invoke(
        app,
        ["transition", "--mission", _SLUG, "--wp", "WP01", "--to", "claimed", "--actor", "migration:backfill", "--policy", "{}"],
    )

    assert result.exit_code == 1, result.output
    assert _REFUSAL in result.stdout
    after = events_path.read_bytes() if events_path.exists() else None
    assert after == before
    assert not (repo / ".worktrees").exists()
