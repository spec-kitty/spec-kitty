"""T020 — CLI integration tests for ``spec-kitty agent decision`` subgroup.

Uses ``typer.testing.CliRunner`` to exercise all six subcommands against
isolated tmp_path fixtures.  Real service calls are used where practical;
emitting events is mocked to avoid side effects outside the decisions module.

Coverage:
  - open: dry-run, happy-path, missing step/slot error, ALREADY_CLOSED error
  - resolve: happy-path, --other-answer flag
  - defer: happy-path
  - cancel: happy-path
  - verify: clean, drift (exit 1), drift + --no-fail-on-stale (exit 0)
  - list: empty mission, post-open entry, --status filter, invalid --status
  - invalid --flow value produces structured error
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import DecisionErrorCode
from specify_cli.decisions.service import DecisionError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
MISSION_SLUG = "test-decision-cli-mission"
MISSION_ID = "01KTESTCLIMDECISION00001"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _setup_mission(tmp_path: Path) -> Path:
    """Create kitty-specs/<slug>/meta.json so service can resolve mission_id."""
    # Topology-true project root marker (WP04 / FR-003): ``decision``'s repo-root
    # resolution now uses the canonical root authority (``locate_project_root``),
    # which anchors on the ``.kittify/`` marker — not a bare ``kitty-specs/``
    # walk. A real spec-kitty project always has ``.kittify/``; declaring it here
    # makes the fixture resolve ``tmp_path`` as the root (instead of walking up to
    # an ancestor) just like a real checkout.
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def _invoke(args: list[str], cwd: Path | None = None) -> object:
    """Invoke the agent_app with given args, optionally setting cwd."""
    old_cwd = os.getcwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        return runner.invoke(agent_app, args, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def _parse_open_output(output: str) -> dict:  # type: ignore[type-arg]
    """Parse ``decision open`` stdout as exactly one JSON object."""
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly 1 JSON line, got: {output!r}"
    return json.loads(lines[0])


def _open_decision(
    tmp_path: Path,
    *,
    step_id: str = "step-1",
    slot_key: str | None = None,
    input_key: str = "team_size",
    dry_run: bool = False,
) -> str:
    """Helper: run ``agent decision open`` and return decision_id."""
    base_args = [
        "decision",
        "open",
        "--mission",
        MISSION_SLUG,
        "--flow",
        "charter",
        "--input-key",
        input_key,
        "--question",
        "How large is the team?",
    ]
    if step_id is not None:
        base_args += ["--step-id", step_id]
    if slot_key is not None:
        base_args += ["--slot-key", slot_key]
    if dry_run:
        base_args.append("--dry-run")

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result = _invoke(base_args, cwd=tmp_path)

    assert result.exit_code == 0, f"open failed: {result.output}"
    data = _parse_open_output(result.output)
    return data["decision_id"]


# ---------------------------------------------------------------------------
# T020a — open --dry-run exits 0 and returns decision_id="DRY_RUN"
# ---------------------------------------------------------------------------


def test_open_dry_run_returns_dry_run_id(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, dry_run=True)
    assert decision_id == "DRY_RUN"


def test_open_dry_run_recovery_is_not_rerun_safe(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    result = _invoke(
        [
            "decision",
            "open",
            "--mission",
            MISSION_SLUG,
            "--flow",
            "charter",
            "--step-id",
            "dry-run-step",
            "--input-key",
            "dry_run_key",
            "--question",
            "Dry run?",
            "--dry-run",
        ],
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    data = _parse_open_output(result.output)
    assert data["decision_id"] == "DRY_RUN"
    assert data["recovery"]["rerun_safe"] is False


def test_open_dry_run_no_index_written(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    _open_decision(tmp_path, dry_run=True)
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    index_file = _store.index_path(mission_dir)
    assert not index_file.exists()


# ---------------------------------------------------------------------------
# T020b — open (non-dry-run) exits 0 and returns valid JSON shape
# ---------------------------------------------------------------------------


def test_open_happy_path_exit_0(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=42):
        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "specify",
                "--slot-key",
                "my-slot",
                "--input-key",
                "team_size",
                "--question",
                "Team size?",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = _parse_open_output(result.output)
    assert data["decision_id"] != "DRY_RUN"
    assert len(data["decision_id"]) == 26
    assert data["contract"] == "decision_open_v2"
    assert data["idempotent"] is False
    assert data["mission_id"] == MISSION_ID
    assert "artifact_path" in data
    assert data["recovery"]["rerun_safe"] is True
    assert data["recovery"]["idempotency_key"] == {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "origin_flow": "specify",
        "step_id": None,
        "slot_key": "my-slot",
        "input_key": "team_size",
    }


def test_open_happy_path_event_lamport(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=57):
        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "plan",
                "--step-id",
                "s-1",
                "--input-key",
                "budget",
                "--question",
                "What budget?",
                "--options",
                '["low", "medium", "high"]',
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = _parse_open_output(result.output)
    assert data["event_lamport"] == 57


# ---------------------------------------------------------------------------
# T020c — open without --step-id and --slot-key exits 1 with structured error
# ---------------------------------------------------------------------------


def test_open_missing_step_and_slot_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    result = _invoke(
        [
            "decision",
            "open",
            "--mission",
            MISSION_SLUG,
            "--flow",
            "charter",
            "--input-key",
            "team_size",
            "--question",
            "Q?",
        ],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    err_data = json.loads(result.stderr)
    assert err_data["code"] == DecisionErrorCode.MISSING_STEP_OR_SLOT.value


# ---------------------------------------------------------------------------
# T020d — open with ALREADY_CLOSED (mocked service) exits 1
# ---------------------------------------------------------------------------


def test_open_already_closed_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    already_closed = DecisionError(
        code=DecisionErrorCode.ALREADY_CLOSED,
        details={"decision_id": "01FAKE00000000000000000001", "status": "resolved"},
    )

    with patch("specify_cli.cli.commands.decision.open_decision", side_effect=already_closed):
        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s1",
                "--input-key",
                "k",
                "--question",
                "Q?",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 1
    err_data = json.loads(result.stderr)
    assert err_data["code"] == "DECISION_ALREADY_CLOSED"
    assert "decision_id" in err_data["details"]


# ---------------------------------------------------------------------------
# T020e — resolve happy path exits 0, terminal_outcome="resolved"
# ---------------------------------------------------------------------------


def test_resolve_happy_path(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path)

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=10):
        result = _invoke(
            [
                "decision",
                "resolve",
                decision_id,
                "--mission",
                MISSION_SLUG,
                "--final-answer",
                "6-20",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["terminal_outcome"] == "resolved"
    assert data["status"] == "resolved"
    assert data["decision_id"] == decision_id
    assert data["idempotent"] is False


# ---------------------------------------------------------------------------
# T020f — resolve with --other-answer exits 0, response includes terminal_outcome=resolved
# ---------------------------------------------------------------------------


def test_resolve_with_other_answer(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, input_key="fav_color")

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=11):
        result = _invoke(
            [
                "decision",
                "resolve",
                decision_id,
                "--mission",
                MISSION_SLUG,
                "--final-answer",
                "magenta",
                "--other-answer",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["terminal_outcome"] == "resolved"

    # Verify other_answer persisted in index
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    index = _store.load_index(mission_dir)
    entry = next(e for e in index.entries if e.decision_id == decision_id)
    assert entry.other_answer is True


# ---------------------------------------------------------------------------
# T020g — defer exits 0, terminal_outcome="deferred"
# ---------------------------------------------------------------------------


def test_defer_happy_path(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, input_key="arch_choice")

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=20):
        result = _invoke(
            [
                "decision",
                "defer",
                decision_id,
                "--mission",
                MISSION_SLUG,
                "--rationale",
                "We need more info first.",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["terminal_outcome"] == "deferred"
    assert data["status"] == "deferred"
    assert data["decision_id"] == decision_id


# ---------------------------------------------------------------------------
# T020h — cancel exits 0, terminal_outcome="canceled"
# ---------------------------------------------------------------------------


def test_cancel_happy_path(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, input_key="feature_x")

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=30):
        result = _invoke(
            [
                "decision",
                "cancel",
                decision_id,
                "--mission",
                MISSION_SLUG,
                "--rationale",
                "No longer needed.",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["terminal_outcome"] == "canceled"
    assert data["status"] == "canceled"


# ---------------------------------------------------------------------------
# T020i — verify with clean index exits 0, status="clean"
# ---------------------------------------------------------------------------


def test_verify_clean(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    # No decisions at all → clean
    result = _invoke(
        ["decision", "verify", "--mission", MISSION_SLUG],
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "clean"
    assert data["findings"] == []
    assert data["deferred_count"] == 0


# ---------------------------------------------------------------------------
# T020j — verify with drift finding exits 1, status="drift"
# ---------------------------------------------------------------------------


def test_verify_drift_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)

    # Create a deferred decision (no inline marker) → DEFERRED_WITHOUT_MARKER
    decision_id = _open_decision(tmp_path, input_key="orphan_q")
    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=5):
        _invoke(
            [
                "decision",
                "defer",
                decision_id,
                "--mission",
                MISSION_SLUG,
                "--rationale",
                "TBD",
            ],
            cwd=tmp_path,
        )

    result = _invoke(
        ["decision", "verify", "--mission", MISSION_SLUG],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["status"] == "drift"
    assert len(data["findings"]) >= 1
    assert data["findings"][0]["kind"] == "DEFERRED_WITHOUT_MARKER"


# ---------------------------------------------------------------------------
# T020k — verify with drift + --no-fail-on-stale exits 0
# ---------------------------------------------------------------------------


def test_verify_no_fail_on_stale_exits_0(tmp_path: Path) -> None:
    _setup_mission(tmp_path)

    # Create stale marker situation (marker in spec.md without matching decision)
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    fake_id = "01FAKE00000000000000000002"
    (mission_dir / "spec.md").write_text(
        f"[NEEDS CLARIFICATION: foo] <!-- decision_id: {fake_id} -->\n",
        encoding="utf-8",
    )

    result = _invoke(
        ["decision", "verify", "--mission", MISSION_SLUG, "--no-fail-on-stale"],
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "drift"
    assert len(data["findings"]) >= 1


# ---------------------------------------------------------------------------
# T020l — invalid --flow value exits 1 with structured error
# ---------------------------------------------------------------------------


def test_open_invalid_flow_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    result = _invoke(
        [
            "decision",
            "open",
            "--mission",
            MISSION_SLUG,
            "--flow",
            "badvalue",
            "--step-id",
            "s1",
            "--input-key",
            "k",
            "--question",
            "Q?",
        ],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    err_data = json.loads(result.stderr)
    assert "code" in err_data
    assert "badvalue" in err_data.get("error", "") or "badvalue" in str(err_data.get("details", ""))


# ---------------------------------------------------------------------------
# T020m — defer with empty rationale exits 1
# ---------------------------------------------------------------------------


def test_defer_empty_rationale_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, input_key="deferred_q")

    result = _invoke(
        [
            "decision",
            "defer",
            decision_id,
            "--mission",
            MISSION_SLUG,
            "--rationale",
            "   ",
        ],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    err_data = json.loads(result.stderr)
    assert err_data["code"] == DecisionErrorCode.MISSING_STEP_OR_SLOT.value


# ---------------------------------------------------------------------------
# T020n — cancel with empty rationale exits 1
# ---------------------------------------------------------------------------


def test_cancel_empty_rationale_exits_1(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path, input_key="cancel_q")

    result = _invoke(
        [
            "decision",
            "cancel",
            decision_id,
            "--mission",
            MISSION_SLUG,
            "--rationale",
            "",
        ],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    err_data = json.loads(result.stderr)
    assert err_data["code"] == DecisionErrorCode.MISSING_STEP_OR_SLOT.value


# ---------------------------------------------------------------------------
# T020o — idempotent open: second call returns idempotent=True
# ---------------------------------------------------------------------------


def test_open_idempotent_second_call(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result1 = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s-idem",
                "--input-key",
                "idem_key",
                "--question",
                "Same Q?",
            ],
            cwd=tmp_path,
        )
        result2 = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s-idem",
                "--input-key",
                "idem_key",
                "--question",
                "Same Q?",
            ],
            cwd=tmp_path,
        )

    assert result1.exit_code == 0
    assert result2.exit_code == 0

    data1 = _parse_open_output(result1.output)
    data2 = _parse_open_output(result2.output)
    assert data2["idempotent"] is True
    assert data2["decision_id"] == data1["decision_id"]


def test_open_idempotent_single_json_uses_persisted_decision_id(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result1 = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s-idem-minted",
                "--input-key",
                "idem_minted_key",
                "--question",
                "Same Q?",
            ],
            cwd=tmp_path,
        )
        result2 = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "s-idem-minted",
                "--input-key",
                "idem_minted_key",
                "--question",
                "Same Q?",
            ],
            cwd=tmp_path,
        )

    assert result1.exit_code == 0
    assert result2.exit_code == 0

    first_response = _parse_open_output(result1.output)
    second_response = _parse_open_output(result2.output)
    assert second_response["idempotent"] is True
    assert second_response["decision_id"] == first_response["decision_id"]
    assert second_response["contract"] == "decision_open_v2"


# ---------------------------------------------------------------------------
# T020p — resolve dry-run exits 0 with decision_id echoed back
# ---------------------------------------------------------------------------


def test_resolve_dry_run(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    fake_id = "01FAKE00000000000000000003"

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=1):
        result = _invoke(
            [
                "decision",
                "resolve",
                fake_id,
                "--mission",
                MISSION_SLUG,
                "--final-answer",
                "yes",
                "--dry-run",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["decision_id"] == fake_id
    assert data["terminal_outcome"] == "resolved"


# ---------------------------------------------------------------------------
# T020r — RISK-1: path traversal via --mission is rejected
# ---------------------------------------------------------------------------


def test_open_mission_path_traversal_rejected(tmp_path: Path) -> None:
    """RISK-1: --mission values with path traversal components are rejected before
    any filesystem access.  typer.BadParameter causes a non-zero exit."""
    traversal_values = [
        "../../etc/passwd",
        "../evil",
        "/abs/path",
        "foo/bar",
        ".hidden",
    ]
    for bad_mission in traversal_values:
        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                bad_mission,
                "--flow",
                "charter",
                "--step-id",
                "s1",
                "--input-key",
                "k",
                "--question",
                "Q?",
            ],
            cwd=tmp_path,
        )
        assert result.exit_code != 0, (
            f"Expected non-zero exit for traversal value {bad_mission!r}, got 0"
        )


# ---------------------------------------------------------------------------
# T020q-fr003 — FR-003: open emits a single JSON object on stdout
# ---------------------------------------------------------------------------


def test_open_emits_single_parseable_json_object(tmp_path: Path) -> None:
    """FR-003: decision open stdout is one stable machine JSON object."""
    _setup_mission(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result = _invoke(
            [
                "decision",
                "open",
                "--mission",
                MISSION_SLUG,
                "--flow",
                "charter",
                "--step-id",
                "fr003-step",
                "--input-key",
                "fr003_key",
                "--question",
                "FR-003 ordering test?",
            ],
            cwd=tmp_path,
        )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected 1 JSON line, got: {result.output!r}"

    payload = json.loads(result.output)
    assert len(payload["decision_id"]) == 26, "decision_id must be a ULID"
    assert payload["contract"] == "decision_open_v2"
    assert payload["recovery"]["idempotency_key"]["step_id"] == "fr003-step"


# ---------------------------------------------------------------------------
# T020q — verify JSON shape matches schema
# ---------------------------------------------------------------------------


def test_verify_json_shape(tmp_path: Path) -> None:
    _setup_mission(tmp_path)
    result = _invoke(
        ["decision", "verify", "--mission", MISSION_SLUG],
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)

    # Required keys
    assert "status" in data
    assert "deferred_count" in data
    assert "marker_count" in data
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert data["status"] in ("clean", "drift")


# ---------------------------------------------------------------------------
# #3951 — decision list (read-only listing of the mission's moments)
# ---------------------------------------------------------------------------


def _list_decisions(tmp_path: Path, *extra_args: str) -> dict:
    """Run ``agent decision list`` and parse its single JSON line."""
    result = _invoke(
        ["decision", "list", "--mission", MISSION_SLUG, *extra_args],
        cwd=tmp_path,
    )
    assert result.exit_code == 0, f"list failed: {result.output}"
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly 1 JSON line, got: {result.output!r}"
    return json.loads(lines[0])


def test_list_empty_mission_returns_zero_decisions(tmp_path: Path) -> None:
    """A mission with no decision moments lists cleanly (count 0, exit 0)."""
    _setup_mission(tmp_path)

    data = _list_decisions(tmp_path)

    assert data["contract"] == "decision_list_v1"
    assert data["mission_slug"] == MISSION_SLUG
    assert data["count"] == 0
    assert data["decisions"] == []


def test_list_after_open_shows_entry(tmp_path: Path) -> None:
    """An opened decision appears with its id, status, and question."""
    _setup_mission(tmp_path)
    decision_id = _open_decision(tmp_path)

    data = _list_decisions(tmp_path)

    assert data["count"] == 1
    entry = data["decisions"][0]
    assert entry["decision_id"] == decision_id
    assert entry["status"] == "open"
    assert entry["origin_flow"] == "charter"
    assert entry["input_key"] == "team_size"
    assert entry["question"] == "How large is the team?"
    assert entry["final_answer"] is None
    assert data["mission_id"] == MISSION_ID


def test_list_status_filter_and_resolved_fields(tmp_path: Path) -> None:
    """--status filters the listing; a resolved decision carries its answer."""
    _setup_mission(tmp_path)
    resolved_id = _open_decision(tmp_path, input_key="team_size")
    _open_decision(tmp_path, input_key="fav_color", step_id=None, slot_key="slot-1")

    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=7):
        result = _invoke(
            [
                "decision",
                "resolve",
                resolved_id,
                "--mission",
                MISSION_SLUG,
                "--final-answer",
                "6-20",
            ],
            cwd=tmp_path,
        )
    assert result.exit_code == 0, f"resolve failed: {result.output}"

    data = _list_decisions(tmp_path, "--status", "resolved")

    assert data["count"] == 1
    entry = data["decisions"][0]
    assert entry["decision_id"] == resolved_id
    assert entry["status"] == "resolved"
    assert entry["final_answer"] == "6-20"
    assert entry["resolved_at"] is not None

    # Unfiltered listing still shows both decisions.
    assert _list_decisions(tmp_path)["count"] == 2


def test_list_invalid_status_exits_1_structured(tmp_path: Path) -> None:
    """An invalid --status value is a structured JSON error naming valid values."""
    _setup_mission(tmp_path)

    result = _invoke(
        ["decision", "list", "--mission", MISSION_SLUG, "--status", "bogus"],
        cwd=tmp_path,
    )

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["code"] == "DECISION_MISSING_STEP_OR_SLOT"
    assert "open" in payload["details"]["valid_values"]
    assert "bogus" in payload["error"]
