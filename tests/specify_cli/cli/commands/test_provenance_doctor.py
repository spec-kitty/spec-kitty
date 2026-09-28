"""Tests for ``spec-kitty doctor provenance`` and the doctor.py auto-discovery
seam (T015, C-PRV-5).

Two concerns:

1. ``_provenance_doctor.py`` itself -- the leak-check reads the exact same
   healable classification the heal migration (``m_3_2_7_heal_provenance_
   paths``) uses, via ``describe_leaks``.
2. ``doctor.py``'s auto-discovery loop -- ``provenance`` must appear as a
   registered command on ``doctor.app`` WITHOUT ``doctor.py`` hand-importing
   ``_provenance_doctor`` or hand-writing an ``@app.command`` shell for it.
   This is the regression guard for the load-bearing WP03/WP04/WP05
   three-lane collision fix.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

import pytest
import typer
from ruamel.yaml import YAML
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from specify_cli.cli.commands import _provenance_doctor
from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError
from specify_cli.upgrade.migrations import m_4_0_0rc5_heal_template_set_provenance as provenance_migration

pytestmark = [pytest.mark.fast]

runner = CliRunner()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _charter_yaml_with_catalog(references_yaml_block: str) -> str:
    return f"""\
schema_version: "2.0.0"
governance:
  testing: {{}}
directives: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references:
{references_yaml_block}
overrides: {{}}
metadata:
  bundle_schema_version: 2
"""


def _charter_yaml_path(project_root: Path) -> Path:
    return project_root / ".kittify" / "charter" / "charter.yaml"


def _former_checkout_source(checkout_root: Path) -> Path:
    source = checkout_root / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    _write(source, "name: software-dev\ndescription: Tracked built-in mission.\n")
    _write(
        checkout_root / "pyproject.toml",
        '[project]\nname = "spec-kitty-cli"\n\n[project.urls]\nRepository = "https://github.com/spec-kitty/spec-kitty"\n',
    )
    subprocess.run(["git", "init", "--quiet", str(checkout_root)], check=True)
    subprocess.run(
        ["git", "-C", str(checkout_root), "remote", "add", "origin", "https://github.com/spec-kitty/spec-kitty.git"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(checkout_root), "add", "--", "pyproject.toml", "packs/built-in/missions/software-dev/mission.yaml"],
        check=True,
    )
    return source


@pytest.fixture
def packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "packs"
    (root / "built-in" / "paradigms").mkdir(parents=True)
    (root / "built-in" / "missions" / "software-dev").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


# ---------------------------------------------------------------------------
# Auto-discovery seam regression guard
# ---------------------------------------------------------------------------


def test_provenance_is_registered_on_doctor_app_without_hand_wiring() -> None:
    """``provenance`` is a real command on ``doctor.app``, discovered -- not hand-written."""
    names = {cmd.name for cmd in doctor_module.app.registered_commands}
    assert "provenance" in names


def test_doctor_py_source_never_hand_imports_the_provenance_sibling() -> None:
    """Regression guard: doctor.py must gain this command via discovery, not an edit.

    If a future change reverts to hand-wiring (adding
    ``from ._provenance_doctor import ...`` or an ``@app.command(name=
    "provenance")`` shell to doctor.py), this test catches the regression --
    the whole point of T015 is that WP04/WP05-style siblings touch doctor.py
    ZERO times. AST-based (not a substring scan) so the module's own
    docstring/comments naming ``_provenance_doctor.py`` as the discovery
    seam's worked example do not self-trip the guard.
    """
    import ast

    tree = ast.parse(Path(doctor_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "_provenance_doctor":
            pytest.fail("doctor.py must not hand-import _provenance_doctor (discovery seam regression)")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "command":
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    assert keyword.value.value != "provenance", "doctor.py must not hand-write an @app.command(name='provenance') shell (discovery seam regression)"


def test_register_is_idempotent_safe_to_call_directly() -> None:
    """``register(app)`` (the seam's own contract) adds exactly one command."""
    import typer

    scratch_app = typer.Typer()
    _provenance_doctor.register(scratch_app)

    names = [cmd.name for cmd in scratch_app.registered_commands]
    assert names == ["provenance"]


# ---------------------------------------------------------------------------
# _run_provenance_audit / describe_leaks reuse
# ---------------------------------------------------------------------------


class TestRunProvenanceAudit:
    def test_no_leaks_exits_zero(self, tmp_path: Path, packs_root: Path) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            _provenance_doctor._run_provenance_audit(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 0

    def test_leak_present_exits_one(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))

        with pytest.raises(typer.Exit) as exc_info:
            _provenance_doctor._run_provenance_audit(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 1

    def test_template_set_leak_exits_one(self, tmp_path: Path, packs_root: Path) -> None:
        abs_source = tmp_path / "former-checkout" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))

        with pytest.raises(typer.Exit) as exc_info:
            _provenance_doctor._run_provenance_audit(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 1

    def test_unreadable_charter_is_a_finding_not_a_clean_result(self, tmp_path: Path, packs_root: Path) -> None:
        charter = _charter_yaml_path(tmp_path)
        _write(charter, "catalog: [unclosed\n")

        leaks, unresolved = _provenance_doctor._collect_findings(tmp_path)

        assert leaks == []
        assert len(unresolved) == 1
        assert "unreadable charter.yaml" in unresolved[0]
        assert charter.read_text(encoding="utf-8") == "catalog: [unclosed\n"

    def test_migration_unreadable_error_is_reported_as_a_finding(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise(_root: Path) -> list[str]:
            raise MigrationStateUnreadableError("charter.yaml could not be read (ParserError); provenance was not evaluated")

        monkeypatch.setattr(_provenance_doctor, "describe_template_set_ambiguities", _raise)

        leaks, unresolved = _provenance_doctor._collect_findings(tmp_path)

        assert leaks == []
        assert unresolved == ["unreadable charter.yaml: charter.yaml could not be read (ParserError); provenance was not evaluated; nothing was changed"]


# ---------------------------------------------------------------------------
# CLI surface (human + --json)
# ---------------------------------------------------------------------------


class TestDoctorProvenanceCli:
    def test_human_output_no_leaks(self, tmp_path: Path, packs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance"])

        assert result.exit_code == 0, result.output
        assert "no absolute built-in-pack" in result.output.lower()

    def test_human_output_with_leak_includes_heal_hint(self, tmp_path: Path, packs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance"])

        assert result.exit_code == 1
        assert "PARADIGM:atomic-design" in result.output
        assert "spec-kitty migrate" in result.output

    def test_unverified_template_set_checkout_is_reported_as_ambiguous(self, tmp_path: Path, packs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        external = tmp_path / "external-authority" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
        _write(external, "name: unrelated-mutable-mission\ndescription: Keep this authority.\n")
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {external}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance"])

        assert result.exit_code == 1, result.output
        assert "TEMPLATE_SET:software-dev-default" in result.output
        assert "ambiguous" in result.output.lower() or "unresolved" in result.output.lower()
        assert "not healed" in result.output.lower()

        json_result = runner.invoke(doctor_module.app, ["provenance", "--json"])

        assert json_result.exit_code == 1, json_result.output
        payload = json.loads(json_result.output)
        assert payload["leak_count"] == 0
        assert payload["unresolved_count"] == payload["finding_count"] == 1
        assert payload["heal_hint"] is None
        assert "ambiguous" in payload["unresolved"][0]

    def test_tracked_symlink_template_set_is_unresolved_without_heal_hint(
        self,
        tmp_path: Path,
        packs_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        checkout = tmp_path / "former-checkout"
        source = _former_checkout_source(checkout)
        external = tmp_path / "mutable-external-authority.yaml"
        _write(external, "name: mutable-external-authority\n")
        source.unlink()
        source.symlink_to(external)
        subprocess.run(
            ["git", "-C", str(checkout), "add", "--", "packs/built-in/missions/software-dev/mission.yaml"],
            check=True,
        )
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {source}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance"])

        assert result.exit_code == 1, result.output
        assert "ambiguous" in result.output.lower()
        assert "not healed" in result.output.lower()
        assert "Heal verified built-in paths with" not in result.output

        json_result = runner.invoke(doctor_module.app, ["provenance", "--json"])

        assert json_result.exit_code == 1, json_result.output
        payload = json.loads(json_result.output)
        assert payload["leak_count"] == 0
        assert payload["unresolved_count"] == payload["finding_count"] == 1
        assert payload["heal_hint"] is None
        assert "ambiguous" in payload["unresolved"][0]

    def test_symlinked_former_checkout_root_is_reported_without_heal_hint(
        self,
        tmp_path: Path,
        packs_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_checkout = tmp_path / "external-authority" / "former-checkout"
        real_source = _former_checkout_source(real_checkout)
        checkout_alias = tmp_path / "former-checkout"
        checkout_alias.symlink_to(real_checkout, target_is_directory=True)
        source = checkout_alias / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {source}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        charter_path = _charter_yaml_path(tmp_path)
        original = _charter_yaml_with_catalog(refs)
        _write(charter_path, original)
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload["leak_count"] == 0
        assert payload["unresolved_count"] == payload["finding_count"] == 1
        assert payload["heal_hint"] is None
        assert "ambiguous" in payload["unresolved"][0]
        assert real_source.is_file()
        assert charter_path.read_text(encoding="utf-8") == original

    def test_file_swapped_to_symlink_during_git_query_is_reported_without_heal_hint(
        self,
        tmp_path: Path,
        packs_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        checkout = tmp_path / "former-checkout"
        source = _former_checkout_source(checkout)
        external = tmp_path / "external-authority.yaml"
        _write(external, "name: mutable-external-authority\n")
        refs = (
            "  - id: TEMPLATE_SET:software-dev-default\n"
            "    kind: template_set\n"
            "    title: software-dev-default\n"
            "    summary: x\n"
            f"    source_path: {source}\n"
            "    local_path: _LIBRARY/template-set-software-dev-default.md\n"
        )
        charter_path = _charter_yaml_path(tmp_path)
        original = _charter_yaml_with_catalog(refs)
        _write(charter_path, original)
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)
        original_run = subprocess.run
        swapped = False

        def swap_source_after_git_query(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal swapped
            result = original_run(*args, **kwargs)
            command = args[0] if args else kwargs.get("args")
            if not swapped and isinstance(command, list) and "ls-files" in command:
                source.unlink()
                source.symlink_to(external)
                swapped = True
            return result

        monkeypatch.setattr(provenance_migration.subprocess, "run", swap_source_after_git_query)

        result = runner.invoke(doctor_module.app, ["provenance", "--json"])

        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert swapped is True
        assert source.is_symlink()
        assert payload["leak_count"] == 0
        assert payload["unresolved_count"] == payload["finding_count"] == 1
        assert payload["heal_hint"] is None
        assert "ambiguous" in payload["unresolved"][0]
        assert charter_path.read_text(encoding="utf-8") == original

    def test_json_output_shape(self, tmp_path: Path, packs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        refs = (
            "  - id: PARADIGM:atomic-design\n"
            "    kind: paradigm\n"
            "    title: Atomic Design\n"
            "    summary: x\n"
            f"    source_path: {abs_source}\n"
            "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
        )
        _write(_charter_yaml_path(tmp_path), _charter_yaml_with_catalog(refs))
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

        result = runner.invoke(doctor_module.app, ["provenance", "--json"])

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["leak_count"] == 1
        assert "PARADIGM:atomic-design" in payload["leaks"][0]
        assert "heal_hint" in payload

    def test_not_in_project_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: None)

        result = runner.invoke(doctor_module.app, ["provenance"])

        assert result.exit_code == 1
        assert "Not in a spec-kitty project" in result.output


def test_describe_leaks_matches_yaml_round_trip(tmp_path: Path, packs_root: Path) -> None:
    """Sanity: the fixture charter.yaml this suite writes is valid, loadable YAML."""
    abs_source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
    refs = (
        "  - id: PARADIGM:atomic-design\n"
        "    kind: paradigm\n"
        "    title: Atomic Design\n"
        "    summary: x\n"
        f"    source_path: {abs_source}\n"
        "    local_path: _LIBRARY/paradigm-atomic-design.md\n"
    )
    charter_path = _charter_yaml_path(tmp_path)
    _write(charter_path, _charter_yaml_with_catalog(refs))

    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert data["catalog"]["references"][0]["id"] == "PARADIGM:atomic-design"


def test_unreadable_charter_fails_the_audit_in_human_and_json_output(tmp_path: Path, packs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(_charter_yaml_path(tmp_path), "catalog: [unclosed\n")
    monkeypatch.setattr(_provenance_doctor, "locate_project_root", lambda *a, **k: tmp_path)

    result = runner.invoke(doctor_module.app, ["provenance"])

    assert result.exit_code == 1, result.output
    assert "unreadable charter.yaml" in result.output
    assert "spec-kitty migrate" not in result.output

    json_result = runner.invoke(doctor_module.app, ["provenance", "--json"])

    assert json_result.exit_code == 1, json_result.output
    payload = json.loads(json_result.output)
    assert payload["leak_count"] == 0
    assert payload["unresolved_count"] == payload["finding_count"] == 1
    assert payload["heal_hint"] is None
