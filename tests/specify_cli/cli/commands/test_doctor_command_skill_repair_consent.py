"""Entry-point tests for #5575: the explicit repair replaces a real command-skill edit.

Drives the real ``spec-kitty doctor tool-surfaces`` CLI (through ``CliRunner``)
against a project whose ``.agents/skills/spec-kitty.<command>/SKILL.md`` was
installed by the real command installer and then edited by the operator.

Contract: ``kitty-specs/upgrade-windows-drift-01M40959/contracts/command-skill-drift.md``.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.skills import command_installer, manifest_store

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_runner = CliRunner()
_COMMAND = "accept"
_SKILL_REL = f".agents/skills/spec-kitty.{_COMMAND}/SKILL.md"
_REPAIR_COMMAND = "spec-kitty doctor tool-surfaces --fix"
_AUDIT_ARGS = ["tool-surfaces", "--kind", "command-skill", "--json"]
_FIX_ARGS = ["tool-surfaces", "--kind", "command-skill", "--fix", "--json"]


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    return home


def _installed_project(tmp_path: Path) -> tuple[Path, Path, bytes]:
    """Install the canonical command skills for ``codex``; return the project, one skill, its bytes."""
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".kittify" / "config.yaml").write_text("vcs:\n  type: git\nagents:\n  available:\n    - codex\n", encoding="utf-8")
    command_installer.install(project, "codex")
    skill = project / _SKILL_REL
    assert skill.is_file()
    return project, skill, skill.read_bytes()


def _rewrite_recorded_hash(project: Path, new_hash: str) -> None:
    manifest = manifest_store.load(project)
    entries = [replace(entry, content_hash=new_hash) if entry.path == _SKILL_REL else entry for entry in manifest.entries]
    manifest_store.save(project, manifest_store.SkillsManifest(entries=entries))


def _invoke(project: Path, args: list[str]) -> tuple[int, dict[str, Any]]:
    with contextlib.chdir(project):
        result = _runner.invoke(doctor_app, args, catch_exceptions=False)
    return result.exit_code, json.loads(result.output)


def _skill_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for finding in payload["findings"] if _COMMAND in json.dumps(finding)]


def test_explicit_fix_replaces_a_real_command_skill_edit(tmp_path: Path) -> None:
    project, skill, canonical = _installed_project(tmp_path)
    edited = canonical + b"\n<!-- local operator edit -->\n"
    skill.write_bytes(edited)
    recorded = manifest_store.fingerprint(canonical)

    # Audit: reports the drift (a warning, so the exit code stays 0), writes nothing.
    _, audit = _invoke(project, _AUDIT_ARGS)
    drift = [f for f in _skill_findings(audit) if f["code"] == "managed-file-drift"]
    assert len(drift) == 1, audit
    assert skill.read_bytes() == edited

    # Explicit repair: replaces the edit with the canonical rendering.
    exit_code, fixed = _invoke(project, _FIX_ARGS)
    assert exit_code == 0, fixed
    assert fixed["ok"] is True, fixed
    assert skill.read_bytes() == canonical
    entry = manifest_store.load(project).find(_SKILL_REL)
    assert entry is not None
    assert entry.content_hash == manifest_store.fingerprint_file(skill) == recorded

    # A second run is a clean no-op.
    exit_code, again = _invoke(project, _FIX_ARGS)
    assert exit_code == 0, again
    assert again["findings"] == [], again
    assert again["repair"]["repaired"] == [], again["repair"]
    assert skill.read_bytes() == canonical


def test_drift_finding_names_the_explicit_repair(tmp_path: Path) -> None:
    project, skill, canonical = _installed_project(tmp_path)
    skill.write_bytes(canonical + b"\nlocal edit\n")

    _, audit = _invoke(project, _AUDIT_ARGS)

    (drift,) = [f for f in _skill_findings(audit) if f["code"] == "managed-file-drift"]
    assert drift["repair_command"] == _REPAIR_COMMAND, drift


def test_canonical_bytes_with_an_old_recorded_hash_are_not_reported_as_drift(tmp_path: Path) -> None:
    project, skill, canonical = _installed_project(tmp_path)
    _rewrite_recorded_hash(project, "0" * 64)  # the file is canonical today; the record is old

    exit_code, audit = _invoke(project, _AUDIT_ARGS)

    assert _skill_findings(audit) == [], audit
    assert exit_code == 0, audit
    assert skill.read_bytes() == canonical
