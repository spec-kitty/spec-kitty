"""Byte-level regressions for human CLI terminal-control sanitization."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
import typer
from rich.table import Table

from specify_cli.agent_utils import status as status_module
from specify_cli.cli.console import CliConsole
from specify_cli.cli.commands import glossary as glossary_module
from specify_cli.core import git_ops
from specify_cli.status import Lane


SAFE_TEXT = "Zoë Ölafsdóttir 日本語 🐱"
HOSTILE_SUFFIX = "\x1b[2J\x1b]0;x\x07\x1b"
HOSTILE_TEXT = f"{SAFE_TEXT}{HOSTILE_SUFFIX}"


def _console() -> tuple[CliConsole, io.StringIO]:
    buffer = io.StringIO()
    return CliConsole(
        file=buffer,
        width=160,
        no_color=True,
        highlight=False,
    ), buffer


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


def test_machine_json_output_remains_plain_and_round_trips() -> None:
    console, buffer = _console()
    console.emit_json({"value": HOSTILE_TEXT})
    emitted = buffer.getvalue().encode("utf-8")

    assert SAFE_TEXT.encode("utf-8") in emitted
    assert b"\\u001b[2J" in emitted
    assert b"\\u001b]0;x" in emitted
    assert b"\x1b" not in emitted


def test_render_str_and_segment_rendering_share_the_policy() -> None:
    console, _ = _console()
    rendered_text = console.render_str(f"[red]{HOSTILE_TEXT}[/red]")
    assert SAFE_TEXT in rendered_text.plain
    assert "\x1b" not in rendered_text.plain

    table = Table()
    table.add_column("Value")
    table.add_row(HOSTILE_TEXT)
    segments = list(console.render(table))
    rendered = "".join(segment.text for segment in segments)
    assert SAFE_TEXT in rendered
    assert "\x1b" not in rendered
