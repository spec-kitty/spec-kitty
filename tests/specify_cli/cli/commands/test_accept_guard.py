"""Regression net for #4724 (mission cli-error-surface-seam-01M2WJD2, WP03):
``spec-kitty accept --mission '<unsafe value>'`` must route the invalid
handle cleanly through the WP01 global error hook instead of crashing with a
raw ``UnsafePathSegmentError`` traceback.

``accept`` is not an exemplar in the mission's ``spec.md`` Assumptions -- it
is a second, independently-confirmed crash site (confirmed live 2026-09-19)
that the WP01 hook fixes for free once ``UnsafePathSegmentError`` is a
``kernel.errors.GuardedReadError`` subclass: ``accept.py`` resolves its
``--mission`` value via ``resolve_mission_dir_with_bare_modern_fold``
(``cli/selector_resolution.py``), which reads through
``mission_runtime.placement_seam`` -- a call with no local ``try``/``except``
around the unsafe-segment path in ``accept()`` itself, so the (now
subclassed) domain error propagates straight to the hook. This WP made no
production changes to ``accept.py`` to reach that state -- confirmed live
below and recorded in the Activity Log.

Note (D4, ``research.md``): a handled domain error on this path is a
*deliberate* exit 1, not exit 2 -- this test does not touch or assert
anything about ``next``'s (already-clean) exit 2 behavior, which is out of
scope for this WP.

Uses ``specify_cli._run_app_with_error_hook`` directly (not
``typer.testing.CliRunner``) for the same reason
``test_mission_close_guard.py`` does: ``CliRunner.invoke(app, ...)`` bypasses
the hook, which is wired one layer up in ``specify_cli.main()``.

See ``kitty-specs/cli-error-surface-seam-01M2WJD2/tasks/
WP03-mission-close-accept-f-sweep.md`` (T010/T013).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli import _run_app_with_error_hook, app

pytestmark = [pytest.mark.regression, pytest.mark.unit]

_UNSAFE_MISSION_ERROR_FRAGMENT = "not a safe path segment"


def _scaffold_project(tmp_path: Path) -> Path:
    """Minimal on-disk shape ``find_repo_root``/``accept`` needs -- a bare
    ``.kittify/`` marker plus an empty ``kitty-specs/``. Never this
    repository's own live ``kitty-specs/``."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / "kitty-specs").mkdir()
    return tmp_path


def _invoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]) -> int | str | None:
    project_root = _scaffold_project(tmp_path)
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *argv])
    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)
    return exc_info.value.code


@pytest.mark.parametrize("bad_value", ["bad seg!", ".."])
def test_accept_invalid_mission_segment_exits_1_clean(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    bad_value: str,
) -> None:
    """#4724: reproduces the live 2026-09-19 crash and pins the fixed
    behavior -- exit 1, a clean actionable message via the hook, zero
    traceback frames."""
    exit_code = _invoke(monkeypatch, tmp_path, ["accept", "--mission", bad_value])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert _UNSAFE_MISSION_ERROR_FRAGMENT in captured.err.lower()


def test_accept_invalid_mission_segment_json_mode_exits_1_clean(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The same guard under ``--json`` -- one JSON envelope on stdout, no
    prose, no traceback (INV-1 from ``contracts/error-envelope.md``)."""
    project_root = _scaffold_project(tmp_path)
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "accept", "--mission", "bad seg!", "--json"])

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=True)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    assert _UNSAFE_MISSION_ERROR_FRAGMENT in captured.out.lower()
