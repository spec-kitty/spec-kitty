"""#7553 (FR-007..FR-010, query side): a read-only ``next`` names the next command.

Every read-only envelope carries ``next_command`` except a pending, answerable decision
and a landed Mission. An untouched run whose first runtime decision is
``decision_required`` keeps its prompt fields (``decision_id``/``question``/``input_key``)
and also carries the advance command: the decision is not pending yet, so it is not
answerable until the run is advanced. Every envelope holds the prompt invariant
(``question`` is set iff ``decision_id`` is set, and then ``options`` or ``input_key`` is set).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from runtime.next.decision import Decision, DecisionKind
from specify_cli import app as cli_app
from specify_cli.status.models import Lane
from tests.next.test_finalized_task_routing import _scaffold
from tests.next.test_next_command_integration import _scaffold_project, _write_runtime_input_mission
from tests.runtime._next_mission_scaffold import analysis_is_current

pytestmark = pytest.mark.git_repo

runner = CliRunner()

_CLI_SLUG = "042-test-feature"
_BOARD_SLUG = "001-finalized-routing"


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI fixtures do not run ``charter sync``; patch the preflight hook boundary."""
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort", lambda *_a, **_k: result)
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only", lambda *_a, **_k: result)


def _advance(agent: str, slug: str) -> str:
    return f"spec-kitty next --agent {agent} --mission {slug} --result success"


def _accept(slug: str) -> str:
    return f"spec-kitty accept --mission {slug}"


def _consolidate(slug: str) -> str:
    return f"spec-kitty consolidate --mission {slug}"


def _assert_prompt_invariant(payload: dict[str, Any]) -> None:
    """Cell 10: question iff decision_id, and an answerable prompt carries options or input_key."""
    assert (payload.get("question") is None) == (payload.get("decision_id") is None), payload
    if payload.get("question") is not None:
        assert payload.get("options") or payload.get("input_key"), payload


def _query_cli(repo_root: Path, monkeypatch: pytest.MonkeyPatch, *, agent: str = "claude") -> dict[str, Any]:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(cli_app, ["next", "--agent", agent, "--mission", _CLI_SLUG, "--json"])
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    _assert_prompt_invariant(payload)
    return payload


def _query_board(repo: Path, agent: str | None = "codex") -> dict[str, Any]:
    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state(agent, _BOARD_SLUG, repo, analysis_currency=analysis_is_current)
    assert decision.kind == DecisionKind.query
    payload = decision.to_dict()
    _assert_prompt_invariant(payload)
    return payload


def _set_meta(feature_dir: Path, repo: Path, **fields: object) -> None:
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(fields)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "meta"], cwd=repo, check=True, capture_output=True)


def _board(tmp_path: Path, wps: dict[str, Lane]) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, slug = _scaffold(repo, wps)
    assert slug == _BOARD_SLUG
    return repo, feature_dir


# ---------------------------------------------------------------------------
# Cells 1, 2, 7: through the CLI
# ---------------------------------------------------------------------------


def test_fresh_software_dev_mission_names_the_advance_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cell 1: an untouched software-dev Mission previews its first step and names the advance."""
    repo_root = _scaffold_project(tmp_path)

    payload = _query_cli(repo_root, monkeypatch)

    assert payload["kind"] == DecisionKind.query
    assert payload["mission_state"] == "not_started"
    assert payload["preview_step"] is not None
    assert payload["question"] is None
    assert payload["next_command"] == _advance("claude", _CLI_SLUG)


def test_first_decision_keeps_its_prompt_and_names_the_advance_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cell 2 (FR-009): a first ``decision_required`` keeps its fields; it is answerable only after advancing."""
    repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
    _write_runtime_input_mission(repo_root, mission_type="input-mission")

    payload = _query_cli(repo_root, monkeypatch)

    assert payload["kind"] == DecisionKind.query
    assert payload["mission_state"] == "not_started"
    assert payload["preview_step"] == "collect_input"
    assert payload["decision_id"] == "input:approval"
    assert payload["input_key"] == "approval"
    assert payload["question"]
    assert payload["next_command"] == _advance("claude", _CLI_SLUG)


def test_pending_decision_on_a_touched_run_has_no_next_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cell 7: a pending, answerable decision is answered with ``--answer``; no next_command."""
    repo_root = _scaffold_project(tmp_path, mission_type="input-mission")
    _write_runtime_input_mission(repo_root, mission_type="input-mission")
    monkeypatch.chdir(repo_root)
    advance = runner.invoke(cli_app, ["next", "--agent", "claude", "--mission", _CLI_SLUG, "--result", "success", "--json"])
    assert advance.exit_code == 0, advance.output
    assert json.loads(advance.stdout)["kind"] == DecisionKind.decision_required

    payload = _query_cli(repo_root, monkeypatch)

    assert payload["decision_id"] == "input:approval"
    assert payload["question"]
    assert "next_command" not in payload


# ---------------------------------------------------------------------------
# Cells 3-6, 8, 9: finalized boards through the bridge
# ---------------------------------------------------------------------------


def test_approved_board_not_accepted_names_accept(tmp_path: Path) -> None:
    """Cell 3: a finished software-dev board awaiting acceptance names ``accept``."""
    repo, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})

    payload = _query_board(repo)

    assert payload["mission_state"] == "accept"
    assert payload["next_command"] == _accept(_BOARD_SLUG)


def test_board_accepted_after_latest_transition_names_consolidate(tmp_path: Path) -> None:
    """Cell 4a: an acceptance newer than every WP transition names ``consolidate``."""
    repo, feature_dir = _board(tmp_path, {"WP01": Lane.APPROVED})
    _set_meta(feature_dir, repo, accepted_at="2026-06-01T00:00:00+00:00")

    payload = _query_board(repo)

    assert payload["mission_state"] == "accept"  # mission_state values are unchanged
    assert payload["next_command"] == _consolidate(_BOARD_SLUG)


def test_board_accepted_before_latest_transition_names_accept(tmp_path: Path) -> None:
    """Cell 4b: a stale acceptance (older than the newest WP transition) names ``accept`` again."""
    repo, feature_dir = _board(tmp_path, {"WP01": Lane.APPROVED})
    _set_meta(feature_dir, repo, accepted_at="2025-12-01T00:00:00+00:00")

    payload = _query_board(repo)

    assert payload["next_command"] == _accept(_BOARD_SLUG)


def test_all_canceled_board_names_accept(tmp_path: Path) -> None:
    """Cell 5: an all-canceled board is finished, so it names ``accept``."""
    repo, _ = _board(tmp_path, {"WP01": Lane.CANCELED})

    payload = _query_board(repo)

    assert payload["next_command"] == _accept(_BOARD_SLUG)


def test_landed_mission_has_no_next_command(tmp_path: Path) -> None:
    """Cell 6: a landed Mission (``merged_at``) short-circuits with no next_command."""
    repo, feature_dir = _board(tmp_path, {"WP01": Lane.DONE})
    _set_meta(
        feature_dir,
        repo,
        mission_slug=_BOARD_SLUG,
        mission_number=7,
        merged_at="2026-01-02T00:00:00+00:00",
        accepted_at="2026-01-01T12:00:00+00:00",
    )

    payload = _query_board(repo)

    assert payload["mission_state"] == "done"
    assert "next_command" not in payload


def test_task_error_names_the_advance_command(tmp_path: Path) -> None:
    """Cell 8: an unreadable WP task file blocks the preview; the advance re-surfaces the error."""
    repo, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    (feature_dir / "tasks" / "WP01.md").unlink()
    subprocess.run(["git", "commit", "-am", "drop WP01 task"], cwd=repo, check=True, capture_output=True)

    payload = _query_board(repo)

    assert payload["mission_state"] == "blocked"
    assert payload["next_command"] == _advance("codex", _BOARD_SLUG)


def test_in_flight_board_names_the_advance_command(tmp_path: Path) -> None:
    """A finalized board previewing ``implement`` names the advance command."""
    repo, _ = _board(tmp_path, {"WP01": Lane.PLANNED})

    payload = _query_board(repo)

    assert payload["preview_step"] == "implement"
    assert payload["next_command"] == _advance("codex", _BOARD_SLUG)


def test_blocked_board_names_the_advance_command(tmp_path: Path) -> None:
    """A ``blocked:*`` finalized board (review in progress) names the advance command."""
    repo, _ = _board(tmp_path, {"WP01": Lane.IN_REVIEW})

    payload = _query_board(repo)

    assert payload["mission_state"] == "blocked"
    assert payload["next_command"] == _advance("codex", _BOARD_SLUG)


def test_agent_none_uses_the_placeholder(tmp_path: Path) -> None:
    """Cell 9: with no agent the command carries the literal ``<agent>`` placeholder."""
    repo, _ = _board(tmp_path, {"WP01": Lane.PLANNED})

    payload = _query_board(repo, agent=None)

    assert payload["next_command"] == _advance("<agent>", _BOARD_SLUG)


# ---------------------------------------------------------------------------
# The helper's table rows that a fixture cannot reach cheaply
# ---------------------------------------------------------------------------


def _decision(mission_state: str, **fields: Any) -> Decision:
    return Decision(
        kind=DecisionKind.query,
        agent="claude",
        mission_slug="m",
        mission="software-dev",
        mission_state=mission_state,
        timestamp="2026-11-12T00:00:00+00:00",
        is_query=True,
        **fields,
    )


@pytest.mark.parametrize(
    ("accepted", "expected"),
    [(False, "spec-kitty accept --mission m"), (True, "spec-kitty consolidate --mission m")],
)
def test_runtime_terminal_row_names_accept_or_consolidate(accepted: bool, expected: str) -> None:
    """A run that completed (no finished board) names accept, or consolidate once accepted."""
    from runtime.next.runtime_bridge_cores import FinishedBoardVerdict
    from runtime.next.runtime_bridge_query import _query_next_command

    command = _query_next_command(
        _decision("done"),
        agent="claude",
        mission_slug="m",
        verdict=FinishedBoardVerdict.NONE,
        family_is_software_dev=False,
        accepted=accepted,
    )

    assert command == expected


def test_other_family_finished_board_names_the_advance_command() -> None:
    """The verdict is software-dev only; another family's finished board names the advance."""
    from runtime.next.runtime_bridge_cores import FinishedBoardVerdict
    from runtime.next.runtime_bridge_query import _query_next_command

    command = _query_next_command(
        _decision("accept"),
        agent=None,
        mission_slug="m",
        verdict=FinishedBoardVerdict.AWAITING_ACCEPTANCE,
        family_is_software_dev=False,
        accepted=False,
    )

    assert command == "spec-kitty next --agent <agent> --mission m --result success"


def test_pending_decision_row_has_no_command() -> None:
    """A decision on a touched run (mission_state is its step) is answered, not advanced."""
    from runtime.next.runtime_bridge_cores import FinishedBoardVerdict
    from runtime.next.runtime_bridge_query import _query_next_command

    decision = _decision("collect_input", decision_id="input:approval", question="Approve?", input_key="approval")

    command = _query_next_command(
        decision,
        agent="claude",
        mission_slug="m",
        verdict=FinishedBoardVerdict.NONE,
        family_is_software_dev=True,
        accepted=False,
    )

    assert command is None
