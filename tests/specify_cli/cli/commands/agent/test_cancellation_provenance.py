"""FR-001: operator-authored cancellation provenance (``reason_source``).

Post-spec squad **F1 BLOCKER**: the canonical ``move-task`` command auto-forges a
non-empty ``reason`` for every move, so "non-empty reason" cannot tell a
documented replan from a bare force-cancel. This module pins the fix — a durable
``operator`` / ``synthetic`` discriminator on the emitted **canceled** event —
by driving the **real** ``move-task`` entry point (Typer ``CliRunner``) and
reading the **persisted** :attr:`StatusEvent.reason_source` off
``status.events.jsonl`` (never the plan object). The raw-event read is
mandatory: it proves the discriminator survives the whole emit round-trip, not
only the reducer projection.

Cases:

* ``--note "x"`` on a cancel  → persisted ``reason_source == "operator"``.
* ``--force`` cancel, no note  → persisted ``reason_source == "synthetic"``
  (this is what makes FR-003's blocker reachable through the canonical command).
* whitespace-only ``--note``   → persisted ``reason_source == "synthetic"``
  (T002: trim before deciding; ``validate.py`` truthiness alone would fake-green).
* legacy compat (NFR-002): a ``canceled`` event that predates the field
  (``reason_source is None``) is classified by the reducer from its ``reason`` —
  a synthetic-template reason reads ``synthetic``, any other non-empty reason
  reads ``operator``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import reduce
from specify_cli.status.store import read_events
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env

if TYPE_CHECKING:
    from click.testing import Result

pytestmark = [pytest.mark.integration, pytest.mark.fast]

runner = CliRunner()


def _seed_wp_in_lane(tmp_path: Path, *, mission_slug: str, wp_id: str, lane: str) -> Path:
    """Seed a feature dir with ``wp_id`` at ``lane`` in the canonical event log."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n"
        f"execution_mode: code_change\nagent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            reason=f"seed to {lane}",
        ),
    )
    return feature_dir


def _invoke(tmp_path: Path, mission_slug: str, args: list[str]) -> Result:
    with setup_mocked_env(tmp_path, mission_slug=mission_slug, workspace_resolution=FileNotFoundError):
        return runner.invoke(app, args, catch_exceptions=False)


def _last_canceled_event(feature_dir: Path, wp_id: str) -> StatusEvent:
    events = [e for e in read_events(feature_dir) if e.wp_id == wp_id and e.to_lane == Lane.CANCELED]
    assert events, f"no persisted canceled event for {wp_id}"
    return events[-1]


# ---------------------------------------------------------------------------
# Canonical command path — the mandatory raw-event assertions.
# ---------------------------------------------------------------------------


def test_operator_note_cancel_persists_reason_source_operator(tmp_path: Path) -> None:
    mission_slug = "prov-cancel-operator"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_progress")
    note = "replan: superseded by WP07, capturing the operator rationale"

    result = _invoke(
        tmp_path,
        mission_slug,
        [
            "move-task",
            wp_id,
            "--to",
            "canceled",
            "--note",
            note,
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    event = _last_canceled_event(feature_dir, wp_id)
    # Mandatory: assert the RAW persisted event, not only the reducer.
    assert event.reason_source == "operator"
    assert event.reason == note

    # And the reducer projects the same provenance into the canceled snapshot.
    wp_state = reduce(read_events(feature_dir)).work_packages[wp_id]
    assert wp_state["lane"] == "canceled"
    assert wp_state["reason_source"] == "operator"
    assert wp_state["cancellation_reason"] == note


def test_force_cancel_without_note_persists_reason_source_synthetic(
    tmp_path: Path,
) -> None:
    mission_slug = "prov-cancel-force"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_progress")

    result = _invoke(
        tmp_path,
        mission_slug,
        [
            "move-task",
            wp_id,
            "--to",
            "canceled",
            "--force",
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    event = _last_canceled_event(feature_dir, wp_id)
    # A bare force-cancel forges a non-empty synthetic reason — but the durable
    # discriminator marks it synthetic, so FR-003's blocker stays reachable.
    assert event.reason_source == "synthetic"
    # The force=true audit (actor + timestamp) is preserved (T002).
    assert event.force is True

    wp_state = reduce(read_events(feature_dir)).work_packages[wp_id]
    assert wp_state["reason_source"] == "synthetic"


def test_whitespace_note_cancel_persists_reason_source_synthetic(
    tmp_path: Path,
) -> None:
    mission_slug = "prov-cancel-whitespace"
    wp_id = "WP05"
    feature_dir = _seed_wp_in_lane(tmp_path, mission_slug=mission_slug, wp_id=wp_id, lane="in_progress")

    result = _invoke(
        tmp_path,
        mission_slug,
        [
            "move-task",
            wp_id,
            "--to",
            "canceled",
            "--note",
            "   ",
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
    )

    assert result.exit_code == 0, f"move-task failed:\n{result.output}"
    event = _last_canceled_event(feature_dir, wp_id)
    # Whitespace is trimmed before deciding — not operator-authored (T002).
    assert event.reason_source == "synthetic"


# ---------------------------------------------------------------------------
# Legacy compatibility (NFR-002): events predating the field.
# ---------------------------------------------------------------------------


def _legacy_canceled_event(reason: str | None) -> StatusEvent:
    """A canceled event as written before ``reason_source`` existed."""
    event = StatusEvent(
        event_id="legacy-cancel-0000000000000000000000",
        mission_slug="legacy",
        wp_id="WP01",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.CANCELED,
        at="2026-01-01T00:00:00+00:00",
        actor="operator",
        force=False,
        execution_mode="worktree",
        reason=reason,
    )
    assert event.reason_source is None  # the legacy shape under test
    return event


@pytest.mark.parametrize(
    "reason, expected",
    [
        ("Superseded by WP07 — documented replan", "operator"),
        ("Force move to canceled", "synthetic"),
        ("move-task: in_progress -> canceled", "synthetic"),
        (None, "synthetic"),
        ("   ", "synthetic"),
    ],
)
def test_legacy_canceled_event_reason_source_inferred_by_reducer(reason: str | None, expected: str) -> None:
    snapshot = reduce([_legacy_canceled_event(reason)])
    wp_state = snapshot.work_packages["WP01"]
    assert wp_state["lane"] == "canceled"
    assert wp_state["reason_source"] == expected
    assert wp_state["cancellation_reason"] == reason
