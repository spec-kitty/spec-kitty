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

import pytest
import typer
from ruamel.yaml import YAML
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_module
from specify_cli.cli.commands import _provenance_doctor

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
# run_provenance_audit / describe_leaks reuse
# ---------------------------------------------------------------------------


class TestRunProvenanceAudit:
    def test_no_leaks_exits_zero(self, tmp_path: Path, packs_root: Path) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            _provenance_doctor.run_provenance_audit(tmp_path, json_output=False)
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
            _provenance_doctor.run_provenance_audit(tmp_path, json_output=False)
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
            _provenance_doctor.run_provenance_audit(tmp_path, json_output=False)
        assert exc_info.value.exit_code == 1


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
