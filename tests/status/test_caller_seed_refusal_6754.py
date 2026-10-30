"""The refusal/allowed matrix for caller-supplied reconstruction-seed identities (#6754).

A reconstruction seed is an event row whose actor starts with ``migration:``. It is a
best-effort restatement of history, written in-process by a migration, and it is treated
differently from a live decision (it yields to live history, skips timestamp continuity,
never opens or closes a consolidation work window, and is exempt from the review-exit
note rule). Before this mission any caller could pass ``--actor migration:x`` to a status
writer and manufacture one.

The matrix, arm by arm:

* **Refused** — a caller-supplied identity that would be recorded verbatim as a seed:
  ``agent status emit --actor``, the four ``orchestrator-api`` lifecycle verbs (pinned in
  ``tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py``), the hidden
  ``implement --actor`` (pinned in
  ``tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py``), and the
  shared lenient builder ``actor_from_option`` unless the caller replays a recorded value.
* **Allowed** — an explicit compact ``--agent`` (strict parse: tool ``migration``, never a
  seed); a recorded identity replayed with ``recorded=True``; and the in-process migration
  writers, which build their rows directly and never touch the emit shell.

Every refused arm asserts the event log is byte-identical afterwards: a refusal that still
writes is not a refusal.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.status import actor_from_option, build_status_actor, is_migration_actor
from specify_cli.status.models import MIGRATION_ACTOR_PREFIX
from specify_cli.status.store import read_events_raw
from tests._support.reconstruction_seed import reduces_as_reconstruction_seed
from tests.status.conftest import seed_wp_to_planned

runner = CliRunner()

_SLUG = "017-test-mission"


def _refusal(option: str = "--actor") -> str:
    """The one canonical refusal message (#6754) — imported lazily so the arms run on the base."""
    from specify_cli.status.models import SEED_SHAPED_IDENTITY_REFUSAL

    return SEED_SHAPED_IDENTITY_REFUSAL.format(option=option, prefix=MIGRATION_ACTOR_PREFIX)


def _refuse(value: str | None, *, option: str = "--actor") -> None:
    from specify_cli.status.models import refuse_seed_shaped_identity

    refuse_seed_shaped_identity(value, option=option)


def _emit_app():
    from specify_cli.cli.commands.agent.status import app

    return app


@pytest.fixture
def mission_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (repo / ".kittify").mkdir()
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nagent_profile: python-pedro\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
    return repo


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


def _feature_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _SLUG


def _invoke_emit(repo: Path, *args: str):
    with (
        patch("specify_cli.cli.commands.agent.status.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.status._find_mission_slug", return_value=_SLUG),
    ):
        return runner.invoke(_emit_app(), ["emit", "WP01", "--mission", _SLUG, *args])


# ---------------------------------------------------------------------------
# The refusal authority (FR-001, NFR-005, SC-004)
# ---------------------------------------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize("value", ["migration:x", "migration:", "migration:backfill_wp_status", "migration:backfill:extra"])
def test_the_leaf_refuses_every_seed_shaped_identity(value: str) -> None:
    with pytest.raises(ValueError, match="must not start with") as excinfo:
        _refuse(value)

    assert str(excinfo.value) == _refusal()


@pytest.mark.fast
@pytest.mark.parametrize("value", ["claude", "claude:opus:python-pedro", "user", "operator", "migration", "Migration:x", " migration:x", ""])
def test_the_leaf_accepts_everything_that_is_not_a_seed(value: str) -> None:
    """The guard is the exact, case-sensitive prefix — the classifier's rule, not a looser one."""
    _refuse(value)
    _refuse(None)


@pytest.mark.fast
def test_the_message_names_the_option_the_rule_and_the_issue() -> None:
    from specify_cli.status.models import SEED_SHAPED_IDENTITY_REFUSAL

    message = _refusal()
    assert "'migration:'" in message
    assert "--actor" in message
    assert "#6754" in message
    assert "in-process" in message
    assert SEED_SHAPED_IDENTITY_REFUSAL.count("{option}") == 1


# ---------------------------------------------------------------------------
# The lenient builder fails closed, with two explicit replays (FR-005, FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_actor_from_option_refuses_a_caller_supplied_seed() -> None:
    with pytest.raises(ValueError, match="must not start with") as excinfo:
        actor_from_option("migration:backfill", "implementer")

    assert str(excinfo.value) == _refusal()


@pytest.mark.fast
def test_actor_from_option_replays_a_recorded_seed_unchanged() -> None:
    """A recorded identity (a value read back from the log) keeps its seed status (#6400)."""
    actor = actor_from_option("migration:backfill", "reviewer", recorded=True)

    assert actor == {"tool": "migration:backfill", "role": "reviewer", "profile": None, "model": None}
    assert is_migration_actor(actor) is True
    assert reduces_as_reconstruction_seed(actor) is True


@pytest.mark.fast
@pytest.mark.parametrize("value", ["user", "operator", "claude"])
def test_actor_from_option_replays_a_recorded_live_identity_unchanged(value: str) -> None:
    assert actor_from_option(value, "implementer", recorded=True) == {"tool": value, "role": "implementer", "profile": None, "model": None}


@pytest.mark.fast
def test_actor_from_option_still_parses_a_caller_supplied_compact_identity() -> None:
    assert actor_from_option("claude:opus:python-pedro", "implementer") == {
        "tool": "claude",
        "role": "implementer",
        "profile": "python-pedro",
        "model": "opus",
    }


@pytest.mark.fast
def test_an_explicit_agent_is_never_a_seed() -> None:
    """The operator's 2026-10-29 ruling: ``--agent migration:x`` is a compact value, not a seed."""
    actor = build_status_actor(role="implementer", agent="migration:x", fallback_tool=None, binding=None)

    assert actor == {"tool": "migration", "role": "implementer", "profile": None, "model": "x"}
    assert is_migration_actor(actor) is False
    assert reduces_as_reconstruction_seed(actor) is False


# ---------------------------------------------------------------------------
# The emit surface (FR-002, FR-010, NFR-001)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_status_emit_refuses_a_seed_and_writes_nothing(mission_repo: Path) -> None:
    before = read_events_raw(_feature_dir(mission_repo))

    result = _invoke_emit(mission_repo, "--to", "claimed", "--actor", "migration:backfill")

    assert result.exit_code == 1, result.output
    assert _refusal() in result.output
    assert read_events_raw(_feature_dir(mission_repo)) == before


@pytest.mark.fast
def test_status_emit_json_refusal_is_a_machine_envelope(mission_repo: Path) -> None:
    before = read_events_raw(_feature_dir(mission_repo))

    result = _invoke_emit(mission_repo, "--to", "claimed", "--actor", "migration:backfill", "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"] == _refusal()
    assert read_events_raw(_feature_dir(mission_repo)) == before


@pytest.mark.fast
def test_status_emit_still_accepts_a_live_actor_on_the_same_fixture(mission_repo: Path) -> None:
    """Positive control for the refusal arms: the same command and fixture still works."""
    result = _invoke_emit(mission_repo, "--to", "claimed", "--actor", "claude", "--json")

    assert result.exit_code == 0, result.output
    stored = [event for event in read_events_raw(_feature_dir(mission_repo)) if event.get("to_lane") == "claimed"]
    assert stored[-1]["actor"] == {"tool": "claude", "role": "implementer", "profile": None, "model": None}
    assert is_migration_actor(stored[-1]["actor"]) is False


# ---------------------------------------------------------------------------
# The in-process migration writers are unchanged (FR-008, SC-003)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_the_backfill_writer_still_builds_a_seed_row() -> None:
    """The writer bypasses the emit shell (its own row builder + the `_unsafe` append door)."""
    from specify_cli.migration.wp_status_backfill import _planned_event

    event = _planned_event(_SLUG, None, "seed-probe", "WP01", "2026-01-01T00:00:00+00:00")

    assert event.actor == "migration:backfill_wp_status"
    assert is_migration_actor(event.actor) is True
    assert reduces_as_reconstruction_seed(event.actor) is True


# ---------------------------------------------------------------------------
# The move-task `--agent` arm, through the real CLI (FR-007, SC-002)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_move_task_explicit_agent_migration_is_not_a_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.specify_cli.cli.commands.agent import _rework_loop_harness as h

    mission = h.build_mission(tmp_path, monkeypatch)
    before = len(h.events(mission))

    result = h.move(mission, h.WP, "claimed", "migration:x")

    assert result.exit_code == 0, result.output
    actors = [event["actor"] for event in h.events(mission)[before:] if event.get("to_lane") == "claimed"]
    assert actors == [{"tool": "migration", "role": "implementer", "profile": None, "model": "x"}]
    assert is_migration_actor(actors[0]) is False
    assert reduces_as_reconstruction_seed(actors[0]) is False
