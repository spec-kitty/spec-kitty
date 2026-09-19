"""Regression net for #4724 (mission cli-error-surface-seam-01M2WJD2, WP03):
``mission close`` (and the sibling ``--mission`` sites it shares the ``-f``
alias defect with) must route an invalid ``--mission`` handle cleanly through
the WP01 global error hook, and the ``-f`` short alias must be gone from
``--mission`` everywhere it was a footgun.

Two related defects, both under #4724:

1. ``spec-kitty mission close --mission '<unsafe value>'`` used to crash with
   an ``UnsafePathSegmentError`` traceback. ``close_cmd``
   (``mission_type.py``) calls ``resolve_feature_dir_for_mission`` with no
   local ``try``/``except`` around it, so once WP01 re-parented
   ``UnsafePathSegmentError`` onto ``kernel.errors.GuardedReadError`` and
   registered the global hook (``_run_app_with_error_hook`` in
   ``specify_cli/__init__.py``), the error now propagates straight to that
   hook: clean text on stderr, exit 1, zero traceback frames. This WP made NO
   production changes to reach that state -- confirmed live below and
   recorded in the Activity Log -- the fix is entirely the WP01 hook now
   being registered on this lane's base.
2. ``mission close``'s ``--mission`` option carried a ``-f`` short alias that
   reads as "force" and collided with the destructive ``--discard`` path:
   ``mission close -f --discard`` bound ``--discard``'s value onto
   ``-f``/``--mission`` instead of behaving as an operator would expect. The
   same ``-f``/``--mission`` alias existed on 3 other sites
   (``mission_type.py:139`` / ``mission current``, ``agent/status.py:850`` /
   ``agent status migrate``, ``agent/status.py:1052`` / ``agent status
   reconcile``) and is swept here as one campsite class (FR-006).

These tests drive the real top-level Typer ``app`` through
``specify_cli._run_app_with_error_hook`` -- the same seam WP01's own
``tests/specify_cli/test_error_hook.py`` exercises -- rather than
``typer.testing.CliRunner``, because ``CliRunner.invoke(app, ...)`` calls the
Click app object directly and never passes through the hook (that wrapping
happens one layer up, in ``specify_cli.main()``). Driving the hook directly
is the only way to prove a command's crash actually reaches it.

See ``kitty-specs/cli-error-surface-seam-01M2WJD2/tasks/
WP03-mission-close-accept-f-sweep.md`` (T010/T012/T013).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli import _run_app_with_error_hook, app

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_UNSAFE_MISSION_ERROR_FRAGMENT = "not a safe path segment"

# The 4 confirmed `typer.Option("--mission", "-f", ...)` sites (research.md,
# BINDING SQUAD AMENDMENTS #3) -- the `-f` alias must be gone from all of
# them, expressed here as their real CLI argv paths.
_MISSION_DASH_F_COMMANDS: list[tuple[str, ...]] = [
    ("mission", "current"),
    ("mission", "close"),
    ("agent", "status", "migrate"),
    ("agent", "status", "reconcile"),
]


def _scaffold_project(tmp_path: Path) -> Path:
    """Minimal on-disk shape ``get_project_root_or_exit`` needs to resolve a
    project root -- a bare ``.kittify/`` marker plus an empty ``kitty-specs/``,
    no mission material at all (both commands under test must fail on the bad
    ``--mission`` handle before ever needing a real mission to exist)."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / "kitty-specs").mkdir()
    return tmp_path


def _invoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]) -> int | str | None:
    """Run *argv* through the real app + global hook, from a scratch project
    directory -- never this repository's own live ``kitty-specs/``."""
    project_root = _scaffold_project(tmp_path)
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *argv])
    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)
    return exc_info.value.code


@pytest.mark.parametrize("bad_value", ["bad seg!", ".."])
def test_mission_close_invalid_mission_segment_exits_1_clean(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    bad_value: str,
) -> None:
    """#4724: an unsafe ``--mission`` handle exits 1 through the hook with a
    clean message and zero traceback frames -- not a raw
    ``UnsafePathSegmentError`` traceback."""
    exit_code = _invoke(monkeypatch, tmp_path, ["mission", "close", "--mission", bad_value])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert _UNSAFE_MISSION_ERROR_FRAGMENT in captured.err.lower()


def test_mission_close_f_discard_footgun_is_now_a_clean_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """FR-006: with the ``-f`` alias removed, ``mission close -f --discard``
    can no longer misbind ``--discard``'s value onto ``--mission`` (which
    used to surface as ``'--discard'`` failing the unsafe-path-segment guard).
    It is now a normal Typer usage error -- ``-f`` no longer exists at all --
    exit 2, per D4 (usage errors are untouched by the hook)."""
    exit_code = _invoke(monkeypatch, tmp_path, ["mission", "close", "-f", "--discard"])

    assert exit_code == 2
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()
    assert "no such option: -f" in combined
    assert _UNSAFE_MISSION_ERROR_FRAGMENT not in combined


@pytest.mark.parametrize("argv", _MISSION_DASH_F_COMMANDS, ids=lambda argv: " ".join(argv))
def test_mission_slug_commands_help_shows_no_f_alias(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    """FR-006: none of the 4 swept commands' ``--help`` may show a ``-f``
    short alias for ``--mission`` any more."""
    exit_code = _invoke(monkeypatch, tmp_path, [*argv, "--help"])

    assert exit_code == 0
    help_text = capsys.readouterr().out
    # Rich renders each option as a table row starting with a box-drawing
    # "│" cell border, e.g. "│ --mission  -f      TEXT  ...". Isolate the
    # actual option-declaration row (not prose/usage-example lines that
    # merely mention "--mission", such as a docstring example containing
    # "--mission 034-feature-name", whose "feature-name" substring falsely
    # contains "-f").
    option_rows = [stripped for line in help_text.splitlines() if (stripped := line.strip().strip("│").strip()).startswith("--mission")]
    assert option_rows, f"--help for {' '.join(argv)} must document --mission"
    for row in option_rows:
        first_token, *rest = row.split()
        assert first_token == "--mission"
        short_alias = rest[0] if rest and rest[0].startswith("-") else None
        assert short_alias is None, f"--help for {' '.join(argv)} still advertises a short alias for --mission: {short_alias!r} (row: {row!r})"
