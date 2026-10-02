"""Red-first: ``tracer-append`` renders the per-surface commit outcome (WP10, T055).

Mission coord-artifact-single-home-01M3V4BE, WP10 (contracts/commit-outcome.md,
FR-007 / SC-003). At base, ``tracer_append.py`` hand-renders the legacy
top-level ``WriteSeamResult`` fields only, so a one-surface-skipped/refused
outcome (a mixed batch where the PRIMARY group committed but the
coordination group was refused) is invisible to the operator even though
the command exits 0. This pins: the shared ``render_commit_outcome`` /
``commit_outcome_payload`` / ``commit_outcome_exit_code`` trio renders every
surface, the JSON payload carries the additive ``surfaces`` key, and the
command exits non-zero when any surface is refused/error -- even when the
legacy top-level ``status`` alone reads ``"committed"``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tracer_append import tracer_append
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.write_seam import WriteSeamResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]

RUNNER = CliRunner()
_APP = typer.Typer()
_APP.command()(tracer_append)

_TRACER_MODULE = "specify_cli.cli.commands.agent.tracer_append"


def _one_surface_skipped_result() -> WriteSeamResult:
    """A mixed outcome: PRIMARY committed, coordination refused."""
    committed = SurfaceOutcome(
        surface="primary",
        branch="topic",
        status="committed",
        commit_hash="abc1234",
        committed=("kitty-specs/demo/traces/tooling-friction.md",),
    )
    refused = SurfaceOutcome(
        surface="coordination",
        branch="kitty/mission-demo-01ABCDEF",
        status="refused",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
    )
    return WriteSeamResult(
        status="committed",
        entry_id="tooling-friction-abc123",
        destination_surface="topic",
        commit_hash="abc1234",
        surfaces=(committed, refused),
    )


def _run(tmp_path: Path, *, json_output: bool) -> Result:
    args = [
        "--mission",
        "demo",
        "--category",
        "tooling-friction",
        "--entry",
        "A finding.",
        "--actor",
        "claude",
    ]
    if json_output:
        args.append("--json")
    with (
        patch(f"{_TRACER_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_main_repo_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_feature_target_branch", return_value="topic"),
        patch(f"{_TRACER_MODULE}.ProtectionPolicy") as policy_cls,
        patch(f"{_TRACER_MODULE}.append_tracer_finding", return_value=_one_surface_skipped_result()),
    ):
        policy_cls.resolve.return_value = object()
        return RUNNER.invoke(_APP, args)


def test_json_output_carries_additive_surfaces_key(tmp_path: Path) -> None:
    result = _run(tmp_path, json_output=True)

    assert result.exit_code == 1, result.output
    import json

    payload = json.loads(result.output)
    assert "surfaces" in payload
    assert len(payload["surfaces"]) == 2
    statuses = {surface["status"] for surface in payload["surfaces"]}
    assert statuses == {"committed", "refused"}
    # The refused surface names its reason.
    refused_surface = next(s for s in payload["surfaces"] if s["status"] == "refused")
    assert refused_surface["refused"][0]["reason"] == "STATUS_LOCK_HELD"


def test_exit_code_is_nonzero_on_a_refused_surface_even_when_legacy_status_committed(tmp_path: Path) -> None:
    """The shared exit-code rule (contract rule 5) looks at EVERY surface,
    not just the legacy top-level ``status`` (which reads "committed" here)."""
    result = _run(tmp_path, json_output=True)

    assert result.exit_code == 1


def _clean_committed_result() -> WriteSeamResult:
    """A clean, single-surface ``committed`` result -- no refusal anywhere."""
    committed = SurfaceOutcome(
        surface="coordination",
        branch="kitty/mission-demo-01ABCDEF",
        status="committed",
        commit_hash="abc1234",
        committed=("kitty-specs/demo/traces/tooling-friction.md",),
    )
    return WriteSeamResult(
        status="committed",
        entry_id="tooling-friction-abc123",
        destination_surface="kitty/mission-demo-01ABCDEF",
        commit_hash="abc1234",
        surfaces=(committed,),
    )


def test_clean_success_text_mode_renders_the_green_tick_line(tmp_path: Path) -> None:
    """WP10 cycle 2 coverage: the ``ok=True`` text branch (never reached by
    the mixed-outcome fixture above, which always exits non-zero)."""
    with (
        patch(f"{_TRACER_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_main_repo_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_feature_target_branch", return_value="topic"),
        patch(f"{_TRACER_MODULE}.ProtectionPolicy") as policy_cls,
        patch(f"{_TRACER_MODULE}.append_tracer_finding", return_value=_clean_committed_result()),
    ):
        policy_cls.resolve.return_value = object()
        result = RUNNER.invoke(
            _APP,
            ["--mission", "demo", "--category", "tooling-friction", "--entry", "A finding.", "--actor", "claude"],
        )

    assert result.exit_code == 0, result.output
    assert "✓" in result.output
    assert "tooling-friction-abc123" in result.output


def test_text_output_renders_every_surface_line(tmp_path: Path) -> None:
    result = _run(tmp_path, json_output=False)

    assert "primary (topic): committed" in result.output
    assert "coordination (kitty/mission-demo-01ABCDEF)" in result.output
    assert "STATUS_LOCK_HELD" in result.output


# ---------------------------------------------------------------------------
# WP10 cycle 2, B1: a surface diagnostic containing Rich-markup-shaped text
# (``[/red]``) must never crash the refusal report it is part of.
# ---------------------------------------------------------------------------


def _error_result_with_markup_like_reason() -> WriteSeamResult:
    """An ``error`` result whose one named ``refused`` fate's reason string
    contains a bracketed substring that LOOKS like a Rich closing tag."""
    error_surface = SurfaceOutcome(
        surface="coordination",
        branch="kitty/mission-demo-01ABCDEF",
        status="error",
        commit_hash=None,
        refused=(PathFate(path="kitty-specs/demo/status.events.jsonl", reason="closing tag [/red] found unexpectedly"),),
        diagnostic="commit failed",
    )
    return WriteSeamResult(
        status="error",
        entry_id="tooling-friction-abc123",
        destination_surface=None,
        diagnostic="commit failed",
        surfaces=(error_surface,),
    )


def _refused_result_with_markup_like_diagnostic() -> WriteSeamResult:
    """The FR-011 zero-write ``refused`` result, whose top-level diagnostic
    itself contains a bracketed substring."""
    return WriteSeamResult(
        status="refused",
        entry_id="tooling-friction-abc123",
        destination_surface=None,
        diagnostic="refusing a zero-write: original cause was [/red] unparseable",
    )


def _run_with_result(tmp_path: Path, result: WriteSeamResult, *, json_output: bool) -> Result:
    args = ["--mission", "demo", "--category", "tooling-friction", "--entry", "A finding.", "--actor", "claude"]
    if json_output:
        args.append("--json")
    with (
        patch(f"{_TRACER_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_main_repo_root", return_value=tmp_path),
        patch(f"{_TRACER_MODULE}.get_feature_target_branch", return_value="topic"),
        patch(f"{_TRACER_MODULE}.ProtectionPolicy") as policy_cls,
        patch(f"{_TRACER_MODULE}.append_tracer_finding", return_value=result),
    ):
        policy_cls.resolve.return_value = object()
        return RUNNER.invoke(_APP, args, catch_exceptions=False)


def test_error_arm_with_markup_like_surface_reason_does_not_crash_text_mode(tmp_path: Path) -> None:
    """B1: the error arm's ``render_commit_outcome`` loop must use
    ``markup=False`` -- a bracketed reason string must render literally,
    never raise ``rich.errors.MarkupError``."""
    result = _run_with_result(tmp_path, _error_result_with_markup_like_reason(), json_output=False)

    assert result.exit_code == 1, result.output
    assert "closing tag [/red] found unexpectedly" in result.output


def test_refused_arm_with_markup_like_diagnostic_does_not_crash_text_mode(tmp_path: Path) -> None:
    """B1 sibling: the top-level FR-011 ``refused`` diagnostic can also
    contain bracketed text; the refusal report must not crash either."""
    result = _run_with_result(tmp_path, _refused_result_with_markup_like_diagnostic(), json_output=False)

    assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# WP10 cycle 2, B2: the ``refused``/``error`` arms render every surface and
# carry the additive ``surfaces`` JSON key -- a named per-path reason code
# must not be dropped.
# ---------------------------------------------------------------------------


def test_error_arm_exposes_named_reason_in_json(tmp_path: Path) -> None:
    result = _run_with_result(tmp_path, _error_result_with_markup_like_reason(), json_output=True)

    assert result.exit_code == 1, result.output
    import json

    payload = json.loads(result.output)
    assert "surfaces" in payload
    assert len(payload["surfaces"]) == 1
    assert payload["surfaces"][0]["refused"][0]["reason"] == "closing tag [/red] found unexpectedly"


def test_error_arm_renders_named_reason_in_text(tmp_path: Path) -> None:
    result = _run_with_result(tmp_path, _error_result_with_markup_like_reason(), json_output=False)

    assert "coordination (kitty/mission-demo-01ABCDEF)" in result.output
    assert "kitty-specs/demo/status.events.jsonl" in result.output


def test_refused_arm_carries_empty_surfaces_key_in_json(tmp_path: Path) -> None:
    """The FR-011 zero-write refusal has no router call, so ``surfaces`` is
    empty -- but the key is still present (additive contract)."""
    result = _run_with_result(tmp_path, _refused_result_with_markup_like_diagnostic(), json_output=True)

    assert result.exit_code == 1, result.output
    import json

    payload = json.loads(result.output)
    assert payload["surfaces"] == []
