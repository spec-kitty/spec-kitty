"""``add-history --note-file`` / stdin: literal Markdown without shell expansion (#2708).

``--note`` is for simple inline text. A shell-based orchestrator that passes
literal Markdown is exposed to shell expansion and mangling before the CLI ever
sees the text, so ``--note-file`` (with ``-`` for stdin) is the shell-safe door.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.agent.tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import _resolve_history_note

pytestmark = pytest.mark.fast

LITERAL_MARKDOWN = "Literal `code` and $HOME and $(not-executed)\n\n- bullet\n"


def test_inline_note_is_returned_verbatim() -> None:
    assert _resolve_history_note("simple note", None, json_output=False) == "simple note"


def test_note_file_is_read_literally(tmp_path: Path) -> None:
    note_path = tmp_path / "NOTES.md"
    note_path.write_text(LITERAL_MARKDOWN, encoding="utf-8")

    assert _resolve_history_note(None, str(note_path), json_output=False) == LITERAL_MARKDOWN.rstrip()


def test_dash_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tasks_module.sys, "stdin", io.StringIO(LITERAL_MARKDOWN))

    assert _resolve_history_note(None, "-", json_output=False) == LITERAL_MARKDOWN.rstrip()


@pytest.mark.parametrize(
    ("note", "note_file"),
    [(None, None), ("inline", "NOTES.md")],
    ids=["neither", "both"],
)
def test_usage_refusals_exit_one(note: str | None, note_file: str | None) -> None:
    with pytest.raises(tasks_module.typer.Exit) as exc_info:
        _resolve_history_note(note, note_file, json_output=False)

    assert exc_info.value.exit_code == 1


def test_empty_file_is_refused(tmp_path: Path) -> None:
    note_path = tmp_path / "EMPTY.md"
    note_path.write_text("  \n", encoding="utf-8")

    with pytest.raises(tasks_module.typer.Exit) as exc_info:
        _resolve_history_note(None, str(note_path), json_output=False)

    assert exc_info.value.exit_code == 1


def test_unreadable_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(tasks_module.typer.Exit) as exc_info:
        _resolve_history_note(None, str(tmp_path / "missing.md"), json_output=False)

    assert exc_info.value.exit_code == 1


def test_cli_refuses_to_write_when_both_note_doors_are_given() -> None:
    """A refusal must happen before any project lookup, so no write is possible."""
    result = CliRunner().invoke(
        tasks_module.app,
        ["add-history", "WP01", "--note", "inline", "--note-file", "NOTES.md", "--json"],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] == "Pass either --note or --note-file, not both"
