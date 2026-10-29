"""``orchestrator-api`` lifecycle commands write the structured 4-key actor (#6400, FR-011).

Driven through the real ``orchestrator-api`` Typer app. Only the stored actor
changes: ``{tool, role, profile, model}`` with ``role`` from the hop and
``profile`` only from a compact ``--actor`` segment. The JSON envelopes keep
their exact keys and values (the orchestrator contract version is unchanged),
and the append-history note line stays the ``- [ts] <actor>: <note>`` string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
from specify_cli.status.store import read_events
from tests._support.reconstruction_seed import reduces_as_reconstruction_seed
from tests.agent.test_orchestrator_commands_integration import _make_mission, _valid_policy_json

pytestmark = pytest.mark.git_repo

runner = CliRunner()

_SLUG = "099-test-mission"


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)


def _invoke(repo_root: Path, *args: str) -> dict[str, Any]:
    with patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo_root):
        result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    envelope: dict[str, Any] = json.loads(result.output)
    assert envelope["success"] is True
    assert envelope["contract_version"] == CONTRACT_VERSION
    return envelope


def _wp01_transition_actors(mission_dir: Path) -> list[tuple[str, str, object]]:
    return [(str(e.from_lane), str(e.to_lane), e.actor) for e in read_events(mission_dir) if e.wp_id == "WP01" and str(e.from_lane) != "genesis"]


def _start_implementation(repo_root: Path, actor: str) -> dict[str, Any]:
    return _invoke(repo_root, "start-implementation", "--mission", _SLUG, "--wp", "WP01", "--actor", actor, "--policy", _valid_policy_json())


def _implementer(tool: str, profile: str | None = None, model: str | None = None) -> dict[str, str | None]:
    return {"tool": tool, "role": "implementer", "profile": profile, "model": model}


def _reviewer(tool: str, profile: str | None = None, model: str | None = None) -> dict[str, str | None]:
    return {"tool": tool, "role": "reviewer", "profile": profile, "model": model}


def test_start_implementation_writes_implementer_actor_and_keeps_envelope(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    envelope = _start_implementation(repo_root, "claude")

    assert _wp01_transition_actors(mission_dir) == [
        ("planned", "claimed", _implementer("claude")),
        ("claimed", "in_progress", _implementer("claude")),
    ]
    data = dict(envelope["data"])
    assert data.pop("workspace_path")
    assert data.pop("prompt_path").endswith("WP01.md")
    assert {key: value for key, value in data.items() if key not in {"mission_id", "mid8", "mission_slug", "mission_number", "mission_type"}} == {
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "in_progress",
        "policy_metadata_recorded": True,
        "no_op": False,
    }


def test_start_implementation_compact_actor_records_profile_and_model(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    _start_implementation(repo_root, "claude:opus:python-pedro")

    assert _wp01_transition_actors(mission_dir)[-1] == ("claimed", "in_progress", _implementer("claude", "python-pedro", "opus"))


def test_transition_and_start_review_record_role_from_the_hop(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    _start_implementation(repo_root, "claude")

    to_review = _invoke(repo_root, "transition", "--mission", _SLUG, "--wp", "WP01", "--to", "for_review", "--actor", "claude", "--policy", _valid_policy_json())
    start_review = _invoke(
        repo_root,
        "start-review",
        "--mission",
        _SLUG,
        "--wp",
        "WP01",
        "--actor",
        "codex",
        "--policy",
        _valid_policy_json(),
        "--review-ref",
        "review-001",
    )
    verdict = json.dumps({"reviewer": "codex", "verdict": "changes_requested", "reference": "review-001"})
    reject = _invoke(
        repo_root,
        "transition",
        "--mission",
        _SLUG,
        "--wp",
        "WP01",
        "--to",
        "in_progress",
        "--actor",
        "codex",
        "--policy",
        _valid_policy_json(),
        "--review-result-json",
        verdict,
    )

    assert _wp01_transition_actors(mission_dir)[2:] == [
        ("in_progress", "for_review", _implementer("claude")),
        ("for_review", "in_review", _reviewer("codex")),
        ("in_review", "in_progress", _reviewer("codex")),
    ]
    assert to_review["data"]["to_lane"] == "for_review"
    assert start_review["data"]["to_lane"] == "in_review"
    assert reject["data"]["from_lane"] == "in_review"


def test_append_history_note_records_structured_actor_and_keeps_string_line(tmp_path: Path) -> None:
    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    envelope = _invoke(repo_root, "append-history", "--mission", _SLUG, "--wp", "WP01", "--actor", "claude", "--note", "progress")

    from specify_cli.status.store import read_events_raw

    notes = [raw for raw in read_events_raw(mission_dir) if raw.get("wp_id") == "WP01" and (raw.get("delta") or {}).get("note")]
    assert notes, "append-history wrote no note annotation"
    annotation = notes[-1]
    assert annotation["actor"] == _implementer("claude")
    note = annotation["delta"]["note"]
    assert isinstance(note, str)
    assert note.endswith("] claude: progress")
    assert set(envelope["data"]) >= {"wp_id", "history_entry_id"}


def test_empty_tool_actor_is_accepted_with_an_unchanged_envelope(tmp_path: Path) -> None:
    """An ``--actor`` the compact parser rejects (empty tool) is accepted as on the base (#6400 review)."""
    plain_root, _plain_dir = _make_mission(tmp_path / "plain", _SLUG)
    odd_root, odd_dir = _make_mission(tmp_path / "odd", _SLUG)

    plain = _start_implementation(plain_root, "claude")
    odd = _start_implementation(odd_root, ":x")

    assert _wp01_transition_actors(odd_dir) == [
        ("planned", "claimed", _implementer(":x")),
        ("claimed", "in_progress", _implementer(":x")),
    ]
    path_keys = {"workspace_path", "prompt_path"}
    assert set(odd["data"]) == set(plain["data"])
    assert {k: v for k, v in odd["data"].items() if k not in path_keys} == {k: v for k, v in plain["data"].items() if k not in path_keys}
    assert odd["contract_version"] == plain["contract_version"] == CONTRACT_VERSION
    assert odd["command"] == plain["command"]


def test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed(tmp_path: Path) -> None:
    """A ``migration:`` ``--actor`` is stored whole as ``tool`` so it keeps its seed status (#6400 review F3)."""
    from spec_kitty_events import diary

    from specify_cli.status import is_migration_actor
    from specify_cli.status.store import read_events_raw

    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)

    _start_implementation(repo_root, "migration:backfill")

    raws = [raw for raw in read_events_raw(mission_dir) if raw.get("wp_id") == "WP01" and raw.get("to_lane") in {"claimed", "in_progress"}]
    assert [raw["actor"] for raw in raws] == [_implementer("migration:backfill"), _implementer("migration:backfill")]
    for raw in raws:
        assert is_migration_actor(raw["actor"])
        assert diary._is_reconstruction_seed(diary.StatusEvent.from_dict(dict(raw)))
        assert reduces_as_reconstruction_seed(raw["actor"])


def test_append_history_note_takes_the_reviewer_role_while_in_review(tmp_path: Path) -> None:
    """Notes take the lane rule (operator decision 2026-10-29): ``reviewer`` while the WP is ``in_review`` (#6400 F4)."""
    from specify_cli.status import Lane, StatusEvent
    from specify_cli.status.store import read_events_raw
    from tests._support.status_seed import seed_status_event

    repo_root, mission_dir = _make_mission(tmp_path, _SLUG)
    seed_status_event(
        mission_dir,
        StatusEvent(
            event_id="test-WP01-in-review",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )

    _invoke(repo_root, "append-history", "--mission", _SLUG, "--wp", "WP01", "--actor", "codex", "--note", "reviewing")

    notes = [raw for raw in read_events_raw(mission_dir) if raw.get("wp_id") == "WP01" and (raw.get("delta") or {}).get("note")]
    assert notes, "append-history wrote no note annotation"
    assert notes[-1]["actor"] == _reviewer("codex")
