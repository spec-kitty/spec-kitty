"""CLI-path non-UTF-8 stdin regression for ``spec-kitty intake -`` (#4739).

Real-world repro: ``head -c 500 /dev/urandom | spec-kitty intake -`` crashes
with an unhandled ``UnicodeDecodeError`` instead of the clean typed error the
file-path variant of the same intake already produces for the same bytes.

Root cause: ``read_stdin_capped`` (``specify_cli.intake.scanner``) already
guards the *bytes*-branch decode in a ``try/except UnicodeDecodeError``, but
the CLI's stdin call site passed ``sys.stdin`` — a text stream — so the UTF-8
decode happened inside Python's text-IO layer during ``stream.read()``,
entirely outside any of ``read_stdin_capped``'s own guards. The fix routes
the CLI call site through ``sys.stdin.buffer`` (bytes) so the existing
guarded bytes-branch always covers stdin decode failures, giving parity with
the file-path route (both raise ``IntakeFileUnreadableError``, a
``GuardedReadError`` subclass).

This module uses a deterministic non-UTF-8 byte sequence (not a random
source) so the regression is reproducible in CI.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.intake import intake
from specify_cli.mission_brief import MISSION_BRIEF_FILENAME

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]


_runner = CliRunner()

# Deterministic non-UTF-8 byte sequence: 0xFF is never a valid UTF-8 lead
# byte, so decoding always fails. Fixed content (not /dev/urandom) keeps the
# regression reproducible.
_NON_UTF8_PAYLOAD = b"\xff\xfe\x00\x01" + b"x" * 100


@pytest.fixture()
def intake_app() -> typer.Typer:
    app = typer.Typer()
    app.command()(intake)
    return app


def _stub_repo_root_to(tmp_path: Path):
    """Pin ``_resolve_repo_root`` to the test's tmp_path."""
    return patch(
        "specify_cli.cli.commands.intake._resolve_repo_root",
        return_value=tmp_path,
    )


def _assert_clean_typed_exit(result) -> None:
    """Assert the CLI exited via a typed ``typer.Exit`` (``SystemExit``), not
    an unhandled crash such as ``UnicodeDecodeError``.

    ``CliRunner`` surfaces a deliberate ``typer.Exit(1)`` as
    ``result.exception`` being a ``SystemExit`` — that is the "clean, no
    traceback" shape this WP requires parity on. Any other exception type
    means the command crashed instead of raising a typed error.
    """
    if result.exception is not None:
        assert isinstance(result.exception, SystemExit), f"expected a clean typed exit (SystemExit), got an unhandled crash: {result.exception!r}"


# ---------------------------------------------------------------------------
# T017 — red-first: stdin crashes, file-path baseline is already clean
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_stdin_non_utf8_does_not_crash_with_unhandled_error(intake_app: typer.Typer, tmp_path: Path) -> None:
    """#4739: non-UTF-8 stdin must not surface an unhandled ``UnicodeDecodeError``.

    Before the fix this raised ``UnicodeDecodeError`` from inside Click's
    text-mode stdin wrapper, never reaching any of the intake CLI's own
    ``except`` clauses. After the fix it is a clean, typed exit 1.
    """
    with _stub_repo_root_to(tmp_path):
        result = _runner.invoke(intake_app, ["-"], input=_NON_UTF8_PAYLOAD)

    _assert_clean_typed_exit(result)
    assert result.exit_code == 1, f"non-UTF-8 stdin must exit 1. stdout={result.output!r}"
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


def test_file_path_non_utf8_baseline_already_clean(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Parity baseline: the file-path route already handles the same bytes cleanly.

    This establishes the pre-existing, already-correct behavior that the
    stdin fix must match — it should pass unmodified on both base and fix.
    """
    bad_file = tmp_path / "bad-brief.md"
    bad_file.write_bytes(_NON_UTF8_PAYLOAD)

    with _stub_repo_root_to(tmp_path):
        result = _runner.invoke(intake_app, [str(bad_file)])

    _assert_clean_typed_exit(result)
    assert result.exit_code == 1
    assert "could not read file" in result.output.lower()
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()


# ---------------------------------------------------------------------------
# T019 — green: stdin parity with file-path handling
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_stdin_non_utf8_exits_clean_with_typed_error_message(intake_app: typer.Typer, tmp_path: Path) -> None:
    """#4739: non-UTF-8 stdin exits 1 with a clean ``Could not read stdin: ...``
    line and no traceback — same shape as the file-path route's message.

    ``spec-kitty intake`` has no ``--json`` mode, so there is no JSON-envelope
    assertion to add here (per ``contracts/error-envelope.md``, that
    assertion only applies to commands that expose ``--json``).
    """
    with _stub_repo_root_to(tmp_path):
        result = _runner.invoke(intake_app, ["-"], input=_NON_UTF8_PAYLOAD)

    _assert_clean_typed_exit(result)
    assert result.exit_code == 1
    assert "could not read stdin" in result.output.lower()
    assert "traceback" not in result.output.lower()


def test_stdin_and_file_path_parity_for_same_non_utf8_bytes(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Direct parity assertion: identical non-UTF-8 bytes via stdin and via a
    file argument both exit 1 with the same error family (``IntakeFileUnreadableError``,
    surfaced as "could not read ...") and no traceback.
    """
    bad_file = tmp_path / "bad-brief.md"
    bad_file.write_bytes(_NON_UTF8_PAYLOAD)

    with _stub_repo_root_to(tmp_path):
        stdin_result = _runner.invoke(intake_app, ["-"], input=_NON_UTF8_PAYLOAD)
        file_result = _runner.invoke(intake_app, [str(bad_file)])

    _assert_clean_typed_exit(stdin_result)
    _assert_clean_typed_exit(file_result)
    assert stdin_result.exit_code == file_result.exit_code == 1
    assert "could not read" in stdin_result.output.lower()
    assert "could not read" in file_result.output.lower()
    assert "traceback" not in stdin_result.output.lower()
    assert "traceback" not in file_result.output.lower()


def test_stdin_valid_utf8_happy_path_still_works(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Guard against the fix accidentally breaking the normal stdin path."""
    payload = "# a perfectly valid UTF-8 brief\n\nSome content."

    with _stub_repo_root_to(tmp_path):
        result = _runner.invoke(intake_app, ["-"], input=payload)

    _assert_clean_typed_exit(result)
    assert result.exit_code == 0, f"stdout={result.output!r}"
    brief = tmp_path / ".kittify" / MISSION_BRIEF_FILENAME
    assert brief.exists()
    # The brief is prefixed with provenance comment lines (mission_brief.py);
    # the original payload must survive intact as the tail of the file.
    assert brief.read_text(encoding="utf-8").endswith(payload)


def test_stdin_cap_overflow_still_works_unchanged(intake_app: typer.Typer, tmp_path: Path) -> None:
    """The cap-plus-one overflow detection must be unaffected by the fix."""
    cap = 1024
    payload = "y" * (cap + 1)

    with (
        _stub_repo_root_to(tmp_path),
        patch(
            "specify_cli.cli.commands.intake.load_max_brief_bytes",
            return_value=cap,
        ),
    ):
        result = _runner.invoke(intake_app, ["-"], input=payload)

    _assert_clean_typed_exit(result)
    assert result.exit_code == 1
    assert "too large" in result.output.lower()
    assert not (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).exists()
