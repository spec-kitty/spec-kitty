"""Operator-facing conflict reporting of ``spec-kitty migrate`` (#5450).

``execute_migration`` records every user-created legacy file it could not move
onto ``.kittify/overrides/`` in ``MigrationReport.conflicts``. These tests pin
what the per-project step of the command tells the operator about them, in the
dry run and the real run, with and without ``--verbose``, and that the wording
without conflicts is unchanged.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import migrate_cmd
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.runtime.migrate import ConflictReason

pytestmark = pytest.mark.integration

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"
_REAL_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LEGACY = "LEGACY v1"
_OVERRIDE = "OVERRIDE v2"
_ZERO_WARNINGS = "Zero legacy warnings expected"

runner = CliRunner()


def _poisoned_locate_project_root(*_args: Any, **_kwargs: Any) -> Path:
    raise AssertionError("locate_project_root() was called without an explicit test override (hard isolation rule)")


@pytest.fixture(autouse=True)
def _hard_repo_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    resolved_tmp = tmp_path.resolve()
    assert not resolved_tmp.is_relative_to(_REAL_REPO_ROOT), f"tmp_path ({resolved_tmp}) resolves inside the real repository ({_REAL_REPO_ROOT})"
    scratch_cwd = tmp_path / "cwd"
    scratch_cwd.mkdir()
    monkeypatch.chdir(scratch_cwd)
    monkeypatch.setattr(_LOCATE, _poisoned_locate_project_root)
    # The real run would install the global runtime under HOME: never here.
    monkeypatch.setattr(migrate_cmd, "ensure_runtime", lambda *a, **k: None)
    for name in ("HOME", "SPEC_KITTY_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(name, str(tmp_path / "home"))
    monkeypatch.setenv("COLUMNS", "250")
    monkeypatch.setenv("NO_COLOR", "1")
    yield


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _project(tmp_path: Path, *, twin: bool = True) -> Path:
    """A project with one user-created legacy file, optionally shadowed by an override."""
    project = tmp_path / "project"
    kittify = project / ".kittify"
    _write(kittify / "missions" / "erp" / "mission.yaml", _LEGACY)
    _write(kittify / "templates" / "fresh.md", "fresh user template")
    # A second free file keeps the moved count (2) apart from the conflict count (1).
    _write(kittify / "templates" / "fresh2.md", "second fresh user template")
    if twin:
        _write(kittify / "overrides" / "missions" / "erp" / "mission.yaml", _OVERRIDE)
    return project


def _invoke(project: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(_LOCATE, lambda *a, **k: project)
    result = runner.invoke(migrate_app, list(args))
    assert not isinstance(result.exception, AssertionError), result.exception
    return result.exit_code, " ".join(_ANSI.sub("", result.output).split())


@pytest.mark.regression
def test_dry_run_reports_conflict_and_keeps_legacy_off_the_move_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5450: the dry run names the file it would NOT move and writes nothing."""
    project = _project(tmp_path)
    legacy = project / ".kittify" / "missions" / "erp" / "mission.yaml"
    exit_code, out = _invoke(project, monkeypatch, "--dry-run", "--verbose")

    assert exit_code == 0
    assert "1 files would NOT be moved to overrides/" in out
    assert "not moved (override already exists):" in out
    assert f"moved: {legacy}" not in out
    assert legacy.read_text(encoding="utf-8") == _LEGACY
    assert (project / ".kittify" / "overrides" / "missions" / "erp" / "mission.yaml").read_text(encoding="utf-8") == _OVERRIDE


@pytest.mark.regression
def test_real_run_reports_conflict_and_drops_the_zero_warnings_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5450: the real run keeps the override, says what was not moved, exits 0."""
    project = _project(tmp_path)
    legacy = project / ".kittify" / "missions" / "erp" / "mission.yaml"
    override = project / ".kittify" / "overrides" / "missions" / "erp" / "mission.yaml"
    exit_code, out = _invoke(project, monkeypatch, "--force", "--verbose")

    assert exit_code == 0
    assert "2 files customized -- moved to overrides/" in out
    assert "1 files NOT moved to overrides/" in out
    assert f"not moved (override already exists): {legacy} -> {override}" in out
    assert override.read_text(encoding="utf-8") == _OVERRIDE
    assert (project / ".kittify" / "missions" / "erp" / "mission.yaml").read_text(encoding="utf-8") == _LEGACY
    assert _ZERO_WARNINGS not in out
    assert "Migration complete with 1 file(s) not moved." in out


@pytest.mark.regression
def test_conflict_count_line_is_visible_without_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5450: the signal is not hidden behind --verbose."""
    project = _project(tmp_path)
    exit_code, out = _invoke(project, monkeypatch, "--force")

    assert exit_code == 0
    assert "1 files NOT moved to overrides/" in out
    assert "not moved (" not in out
    # Without --verbose nothing is listed, so the closing line must not say it is; it names how to list them.
    assert "listed above" not in out
    assert "run `spec-kitty migrate --dry-run --verbose` to list them" in out
    # The count sits with the other per-category counts, after the kept line.
    assert out.index("files customized -- moved") < out.index("files project-specific -- kept") < out.index("1 files NOT moved")


def test_without_conflicts_wording_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-004: no twin means no conflict line and the original closing claim."""
    project = _project(tmp_path, twin=False)
    exit_code, out = _invoke(project, monkeypatch, "--force")

    assert exit_code == 0
    assert "NOT moved" not in out
    assert "not moved" not in out
    assert _ZERO_WARNINGS in out
    assert (project / ".kittify" / "overrides" / "templates" / "fresh.md").exists()


@pytest.mark.regression
@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need privileges on Windows")
def test_symlink_source_reason_is_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5450: a legacy symbolic link is left in place and the reason says so."""
    project = _project(tmp_path, twin=False)
    templates = project / ".kittify" / "templates"
    os.symlink("fresh.md", templates / "alias.md")
    exit_code, out = _invoke(project, monkeypatch, "--force", "--verbose")

    assert exit_code == 0
    assert "not moved (legacy file is a symbolic link):" in out
    assert (templates / "alias.md").is_symlink()


def test_every_conflict_reason_has_operator_wording() -> None:
    """Each reason renders its own text; a new reason without wording would raise KeyError mid-report."""
    assert set(migrate_cmd._CONFLICT_REASON_TEXT) == set(ConflictReason)
    assert migrate_cmd._CONFLICT_REASON_TEXT == {
        ConflictReason.DESTINATION_EXISTS: "override already exists",
        ConflictReason.DESTINATION_PARENT_BLOCKED: "a non-folder blocks the overrides path",
        ConflictReason.SOURCE_IS_SYMLINK: "legacy file is a symbolic link",
    }
