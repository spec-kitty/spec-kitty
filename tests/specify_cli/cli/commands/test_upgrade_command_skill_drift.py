"""Real-CLI proofs for command-skill drift under ``spec-kitty upgrade`` (#5574).

A command skill whose bytes equal today's canonical rendering is fresh,
whatever hash the manifest recorded (an older release's render leaves such a
hash behind). The adoption pass inside ``spec-kitty upgrade`` refreshes the
recorded hash, so a following ``upgrade --yes`` exits 0.

The ratchet leg proves the other half of the contract: a *genuinely edited*
command skill is never rewritten by an unattended ``upgrade --yes``, which
still reports the drift and exits non-zero.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.skills import manifest_store

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_runner = CliRunner()

_SKILL_REL = ".agents/skills/spec-kitty.plan/SKILL.md"
_DRIFT_BANNER = "Not updated, your local edit was kept"
_STALE_HASH = "0" * 64


@pytest.fixture(scope="module")
def initialized_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real ``spec-kitty init --ai codex`` shared (read-only) by the module."""
    real_home = os.environ.get("SPEC_KITTY_REAL_HOME_FOR_TESTS")
    assert real_home is None or Path.home() != Path(real_home), "per-worker HOME isolation is not active"
    base = tmp_path_factory.mktemp("skill_drift_template")
    project = base / "project"
    project.mkdir()
    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["init", "--ai", "codex", "--non-interactive"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert (project / _SKILL_REL).is_file()
    return project


@pytest.fixture()
def project(initialized_project: Path, tmp_path: Path) -> Path:
    """A private copy of the initialized project so each test may mutate it."""
    copy = tmp_path / "project"
    shutil.copytree(initialized_project, copy, symlinks=True)
    return copy


def _entry_hash(project: Path) -> str:
    entry = manifest_store.load(project).find(_SKILL_REL)
    assert entry is not None, f"{_SKILL_REL} is not manifest-tracked"
    return entry.content_hash


def _set_entry_hash(project: Path, content_hash: str) -> None:
    manifest = manifest_store.load(project)
    entry = manifest.find(_SKILL_REL)
    assert entry is not None
    manifest.upsert(replace(entry, content_hash=content_hash))
    manifest_store.save(project, manifest)


def _upgrade_yes(project: Path, *extra: str) -> tuple[int, str]:
    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["upgrade", "--yes", *extra], catch_exceptions=False)
    return result.exit_code, result.output


def _upgrade_yes_json(project: Path) -> tuple[int, dict[str, Any]]:
    """Run ``upgrade --yes --json`` and decode the payload.

    The machine payload carries the reported paths (``surface_repair``) next to the
    same error strings the human renderer prints, so both are asserted against the
    one run state.
    """
    exit_code, output = _upgrade_yes(project, "--json")
    return exit_code, json.loads(output)


def test_canonical_bytes_with_stale_recorded_hash_converge_via_real_upgrade(project: Path) -> None:
    """#5574: canonical bytes + an older recorded hash is not drift."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()
    canonical_hash = manifest_store.fingerprint_file(skill)
    _set_entry_hash(project, _STALE_HASH)
    assert _entry_hash(project) != canonical_hash

    exit_code, payload = _upgrade_yes_json(project)

    assert exit_code == 0, payload
    assert payload["surface_repair"]["drifted_reported"] == [], payload
    assert _DRIFT_BANNER not in " ".join(payload["errors"]), payload
    assert _entry_hash(project) == manifest_store.fingerprint_file(skill) == canonical_hash
    assert skill.read_bytes() == canonical_bytes

    # A second unattended (human-mode) run is a clean no-op.
    second_exit, second_output = _upgrade_yes(project)
    assert second_exit == 0, second_output
    assert skill.read_bytes() == canonical_bytes


def test_real_edit_is_kept_and_reported_by_unattended_upgrade(project: Path) -> None:
    """FR-002 ratchet: an unattended upgrade never rewrites a genuine edit."""
    skill = project / _SKILL_REL
    skill.write_bytes(skill.read_bytes() + b"\n<!-- local edit -->\n")
    edited_bytes = skill.read_bytes()
    recorded_before = _entry_hash(project)
    assert manifest_store.fingerprint_file(skill) != recorded_before

    human_exit, human_output = _upgrade_yes(project)
    assert human_exit != 0, human_output
    assert f"{_DRIFT_BANNER}: {_SKILL_REL}" in human_output, human_output
    assert "already up to date" not in human_output.lower(), human_output
    json_exit, payload = _upgrade_yes_json(project)

    assert json_exit != 0, payload
    assert any("doctor tool-surfaces" in error for error in payload["errors"]), payload
    assert any(path.endswith(_SKILL_REL) for path in payload["surface_repair"]["drifted_reported"]), payload
    assert skill.read_bytes() == edited_bytes
    assert _entry_hash(project) == recorded_before
