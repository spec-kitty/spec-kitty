"""Tests for ``spec-kitty doctor env-file`` and the doctor.py auto-discovery
seam (T019).

Three concerns, mirroring ``test_provenance_doctor.py``'s structure:

1. ``doctor.py``'s auto-discovery loop -- ``env-file`` must appear as a
   registered command on ``doctor.app`` WITHOUT ``doctor.py`` hand-importing
   ``_env_file_doctor`` or hand-writing an ``@app.command`` shell for it.
2. ``_env_file_doctor.py``'s own reporting logic -- tier resolution, governed
   var presence, and C-SEC-1 fail-closed redaction.
3. C-SEC-2 -- ``.kitty.env`` ignore coverage is surfaced as an issue when
   missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from specify_cli.cli.commands import _env_file_doctor

pytestmark = [pytest.mark.fast]

runner = CliRunner()


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the home tier at an isolated, empty directory (no real ~/.kitty.env leak)."""
    home = tmp_path / "spec-kitty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


def _repo_env_path(project_root: Path) -> Path:
    return project_root / ".kittify" / ".kitty.env"


# ---------------------------------------------------------------------------
# Auto-discovery seam regression guard
# ---------------------------------------------------------------------------


def test_env_file_is_registered_on_doctor_app_without_hand_wiring() -> None:
    """``env-file`` is a real command on ``doctor.app``, discovered -- not hand-written."""
    names = {cmd.name for cmd in doctor_module.app.registered_commands}
    assert "env-file" in names


def test_doctor_py_source_never_hand_imports_the_env_file_sibling() -> None:
    """Regression guard: doctor.py must gain this command via discovery, not an edit.

    AST-based (not a substring scan) so the module's own docstring/comments
    naming ``_env_file_doctor.py`` do not self-trip the guard.
    """
    import ast

    tree = ast.parse(Path(doctor_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "_env_file_doctor":
            pytest.fail("doctor.py must not hand-import _env_file_doctor (discovery seam regression)")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "command":
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    assert keyword.value.value != "env-file", (
                        "doctor.py must not hand-write an @app.command(name='env-file') "
                        "shell (discovery seam regression)"
                    )


def test_register_is_idempotent_safe_to_call_directly() -> None:
    """``register(app)`` (the seam's own contract) adds exactly one command."""
    scratch_app = typer.Typer()
    _env_file_doctor.register(scratch_app)

    names = [cmd.name for cmd in scratch_app.registered_commands]
    assert names == ["env-file"]


# ---------------------------------------------------------------------------
# run_env_file_health -- tier resolution + presence
# ---------------------------------------------------------------------------


class TestRunEnvFileHealth:
    def test_no_repo_env_file_exits_zero(self, tmp_path: Path, isolated_home: Path) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            _env_file_doctor.run_env_file_health(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 0

    def test_repo_env_file_present_but_ungitignored_exits_one(self, tmp_path: Path, isolated_home: Path) -> None:
        env_path = _repo_env_path(tmp_path)
        env_path.parent.mkdir(parents=True)
        env_path.write_text("SPEC_KITTY_NON_INTERACTIVE=1\n", encoding="utf-8")

        with pytest.raises(typer.Exit) as exc_info:
            _env_file_doctor.run_env_file_health(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 1

    def test_repo_env_file_present_and_fully_ignored_exits_zero(self, tmp_path: Path, isolated_home: Path) -> None:
        env_path = _repo_env_path(tmp_path)
        env_path.parent.mkdir(parents=True)
        env_path.write_text("SPEC_KITTY_NON_INTERACTIVE=1\n", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")
        (tmp_path / ".claudeignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")

        with pytest.raises(typer.Exit) as exc_info:
            _env_file_doctor.run_env_file_health(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 0


# ---------------------------------------------------------------------------
# CLI surface (human + --json)
# ---------------------------------------------------------------------------


class TestDoctorEnvFileCli:
    def test_json_output_shape(self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_path = _repo_env_path(tmp_path)
        env_path.parent.mkdir(parents=True)
        env_path.write_text("SPEC_KITTY_NON_INTERACTIVE=1\n", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")
        (tmp_path / ".claudeignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["repo_env_file"]["exists"] is True
        assert payload["gitignored"] is True
        assert payload["claudeignored"] is True
        assert payload["issues"] == []
        assert "governed_vars" in payload

    def test_json_output_flags_missing_ignore_coverage(
        self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_path = _repo_env_path(tmp_path)
        env_path.parent.mkdir(parents=True)
        env_path.write_text("SPEC_KITTY_NON_INTERACTIVE=1\n", encoding="utf-8")
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["gitignored"] is False
        assert payload["claudeignored"] is False
        assert len(payload["issues"]) == 2

    def test_not_in_project_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: None)

        result = runner.invoke(doctor_module.app, ["env-file"])

        assert result.exit_code == 1
        assert "Not in a spec-kitty project" in result.output

    def test_human_output_no_env_file(self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file"])

        assert result.exit_code == 0, result.output
        assert "not provisioned" in result.output.lower()


# ---------------------------------------------------------------------------
# C-SEC-1: governed-var tier reporting is fail-closed
# ---------------------------------------------------------------------------


class TestGovernedVarRedaction:
    def test_printable_var_from_real_env_shows_value(
        self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_NON_INTERACTIVE", "1")
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])
        payload = json.loads(result.output)

        entry = next(v for v in payload["governed_vars"] if v["name"] == "SPEC_KITTY_NON_INTERACTIVE")
        assert entry["present"] is True
        assert entry["tier"] == "real_env"
        assert entry["value"] == "1"

    def test_secret_var_from_real_env_never_shows_value(
        self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_ORG_TOKEN", "tok_fixture_supersecret_notreal")
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])
        payload = json.loads(result.output)

        entry = next(v for v in payload["governed_vars"] if v["name"] == "SPEC_KITTY_ORG_TOKEN")
        assert entry["present"] is True
        assert entry["value"] is None
        assert "tok_fixture_supersecret_notreal" not in result.output

    def test_second_secret_var_from_real_env_never_shows_value(
        self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-SEC-1 holds for every GOVERNED_SECRET_VARS member, not just the first:
        SPEC_KITTY_ORG_AUTH_HEADER is also redacted (#6164 hosted->org retirement)."""
        monkeypatch.setenv("SPEC_KITTY_ORG_AUTH_HEADER", "Bearer fixture_header_notreal")
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])
        payload = json.loads(result.output)

        entry = next(v for v in payload["governed_vars"] if v["name"] == "SPEC_KITTY_ORG_AUTH_HEADER")
        assert entry["present"] is True
        assert entry["value"] is None
        assert "fixture_header_notreal" not in result.output

    def test_var_set_only_in_repo_tier_shows_repo_tier(
        self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_path = _repo_env_path(tmp_path)
        env_path.parent.mkdir(parents=True)
        env_path.write_text("SPEC_KITTY_NO_BANNER=1\n", encoding="utf-8")
        (tmp_path / ".gitignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")
        (tmp_path / ".claudeignore").write_text(".kittify/.kitty.env\n", encoding="utf-8")
        monkeypatch.delenv("SPEC_KITTY_NO_BANNER", raising=False)
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])
        payload = json.loads(result.output)

        entry = next(v for v in payload["governed_vars"] if v["name"] == "SPEC_KITTY_NO_BANNER")
        assert entry["tier"] == "repo"
        assert entry["value"] == "1"

    def test_unset_var_reports_unset_tier(self, tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_NON_INTERACTIVE", raising=False)
        monkeypatch.setattr(_env_file_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["env-file", "--json"])
        payload = json.loads(result.output)

        entry = next(v for v in payload["governed_vars"] if v["name"] == "SPEC_KITTY_NON_INTERACTIVE")
        assert entry["present"] is False
        assert entry["tier"] == "unset"
        assert entry["value"] is None
