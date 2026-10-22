"""Byte-level regressions for human CLI terminal-control sanitization."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.agent_utils import status as status_module
from specify_cli.cli.commands import glossary as glossary_module
from specify_cli.core import git_ops
from specify_cli.status import Lane

# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_cli_terminal_control_sanitization.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_cli_terminal_control_sanitization import (
    SAFE_TEXT,
    HOSTILE_TEXT,
    _console,
)
from tests.architectural._lifted_cli_terminal_control_sanitization import (
    test_machine_json_output_remains_plain_and_round_trips as test_machine_json_output_remains_plain_and_round_trips,
)
from tests.architectural._lifted_cli_terminal_control_sanitization import (
    test_render_str_and_segment_rendering_share_the_policy as test_render_str_and_segment_rendering_share_the_policy,
)


def _assert_clean(output: str) -> None:
    emitted = output.encode("utf-8")
    # Rich may insert a width-dependent line break inside otherwise-safe text.
    # Normalize rendering whitespace so the assertion measures preservation of
    # Unicode content rather than the worker's temporary-path length.
    assert SAFE_TEXT in " ".join(output.split())
    assert b"\x1b" not in emitted
    assert b"[2J" not in emitted
    assert b"]0;x" not in emitted


def test_nested_rich_renderables_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    console, buffer = _console()
    monkeypatch.setattr(status_module, "console", console)
    by_lane = {lane: [] for lane in Lane}
    by_lane[Lane.IN_PROGRESS] = [{"id": HOSTILE_TEXT, "title": HOSTILE_TEXT}]

    status_module._display_status_board(
        mission_slug=HOSTILE_TEXT,
        work_packages=[{"id": HOSTILE_TEXT, "title": HOSTILE_TEXT}],
        by_lane=by_lane,
        total=1,
        done_count=0,
        in_progress=1,
        planned_count=0,
        done_pct=0.0,
        progress_pct=0.0,
        parallel_info={"ready_wps": [], "parallel_groups": []},
    )

    _assert_clean(buffer.getvalue())


def test_glossary_validation_errors_are_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console, buffer = _console()
    monkeypatch.setattr(glossary_module, "console", console)
    seed = tmp_path / f"{SAFE_TEXT}.yaml"
    seed.write_text(
        f"terms:\n  - surface: {HOSTILE_TEXT}\n",
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit):
        glossary_module._validate_single_file(seed, json_output=False)

    _assert_clean(buffer.getvalue())


def test_git_error_output_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    console, buffer = _console()

    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", HOSTILE_TEXT],
            stderr=f"{HOSTILE_TEXT}\n",
        )

    monkeypatch.setattr(git_ops.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        git_ops.run_command(["git", HOSTILE_TEXT], console=console)

    _assert_clean(buffer.getvalue())
