"""``doctor charter-packs`` reports the retired doctrine layouts it no longer reads (#3732, FR-011).

The nested org-pack layout ``<pack>/doctrine/<plural>/<layer>/`` and the
repo-root ``doctrine/`` fallback candidate were read before the cutover; now
they resolve to nothing, so the doctor names them and the flat layout instead
of letting an org pack go empty in silence.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from tests._support.org_pack_config import write_org_packs

pytestmark = [pytest.mark.unit]

runner = CliRunner()
RUNBOOK = "docs/migrations/charter-pack-cutover.md"


def _project(root: Path) -> Path:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    return root


def _doctor_json(root: Path) -> tuple[int, dict[str, object]]:
    with contextlib.chdir(root):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"], catch_exceptions=False)
    return result.exit_code, json.loads(result.stdout)


def test_nested_org_pack_layout_is_reported(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    pack = tmp_path / "acme"
    (pack / "doctrine" / "directives" / "org").mkdir(parents=True)
    write_org_packs(project, [{"name": "acme", "local_path": pack}])

    exit_code, payload = _doctor_json(project)

    assert exit_code == 1
    org_drg = payload["org_drg"]
    assert isinstance(org_drg, dict)
    findings = org_drg["retired_layouts"]
    assert isinstance(findings, list) and len(findings) == 1
    finding = findings[0]
    assert finding["path"] == str(pack / "doctrine")
    assert "acme" in finding["message"] and "flat layout" in finding["message"] and RUNBOOK in finding["message"]
    assert finding["message"] in org_drg["errors"]


def test_nested_layout_is_rendered_in_the_human_output(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    pack = tmp_path / "acme"
    (pack / "doctrine" / "tactics" / "org").mkdir(parents=True)
    write_org_packs(project, [{"name": "acme", "local_path": pack}])

    with contextlib.chdir(project):
        result = runner.invoke(doctor_app, ["charter-packs"], catch_exceptions=False)

    text = " ".join(result.stdout.split())
    assert result.exit_code == 1
    assert "Retired layout" in text and "flat layout" in text, result.stdout


def test_flat_org_pack_is_not_reported(tmp_path: Path) -> None:
    """Control: a flat org pack carries no retired-layout finding."""
    project = _project(tmp_path / "p")
    pack = tmp_path / "acme"
    (pack / "directives").mkdir(parents=True)
    write_org_packs(project, [{"name": "acme", "local_path": pack}])

    _exit, payload = _doctor_json(project)

    org_drg = payload["org_drg"]
    assert isinstance(org_drg, dict) and "retired_layouts" not in org_drg


def test_repo_root_doctrine_fallback_is_reported(tmp_path: Path) -> None:
    project = _project(tmp_path / "p")
    (project / "doctrine" / "directive").mkdir(parents=True)

    exit_code, payload = _doctor_json(project)

    assert exit_code == 1
    org_drg = payload["org_drg"]
    assert isinstance(org_drg, dict)
    [finding] = org_drg["retired_layouts"]
    assert finding["path"] == str(project / "doctrine")
    assert ".kittify/charter-packs" in finding["message"]


def test_repo_root_doctrine_dir_beside_the_project_pack_root_is_not_reported(tmp_path: Path) -> None:
    """Control: the repo-root dir was only read when no earlier candidate existed."""
    project = _project(tmp_path / "p")
    (project / "doctrine").mkdir()
    (project / ".kittify" / "charter-packs").mkdir()

    _exit, payload = _doctor_json(project)

    org_drg = payload["org_drg"]
    assert isinstance(org_drg, dict) and "retired_layouts" not in org_drg


def test_unreadable_registry_or_pack_root_yields_no_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands import _doctrine_collect

    project = _project(tmp_path / "p")
    write_org_packs(project, [{"name": "acme", "local_path": "${SPEC_KITTY_UNSET_PACK_HOME}/acme"}])
    monkeypatch.delenv("SPEC_KITTY_UNSET_PACK_HOME", raising=False)
    assert _doctrine_collect._retired_layout_findings(project) == []

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("registry unreadable")

    monkeypatch.setattr("charter.drg.load_pack_registry", _boom)
    assert _doctrine_collect._retired_layout_findings(project) == []
