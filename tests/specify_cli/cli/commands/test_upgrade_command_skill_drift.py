"""Real-CLI proofs for command-skill drift under ``spec-kitty upgrade`` (#5574, #702).

A command skill whose bytes equal today's canonical rendering is fresh,
whatever hash the manifest recorded (an older release's render leaves such a
hash behind). The adoption pass inside ``spec-kitty upgrade`` refreshes the
recorded hash, so a following ``upgrade --yes`` exits 0.

The regeneration leg (#702) proves the other half of the contract: the
``.agents/skills/spec-kitty.<command>/SKILL.md`` projection is DERIVED,
git-ignored generated state, so a *drifted* projection is regenerated to the
canonical render by an unattended ``upgrade --yes`` (exit 0, no drift banner),
keeping the surface idempotent against the manifest rather than keeping the
stale bytes.
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


def test_real_drift_is_regenerated_by_unattended_upgrade(project: Path) -> None:
    """#702: an unattended upgrade regenerates a drifted DERIVED command-skill projection to
    the canonical render instead of keeping it and reporting drift. The surface is generated,
    git-ignored state (never a committed user edit), so this keeps it idempotent against the
    manifest."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()
    canonical_hash = manifest_store.fingerprint_file(skill)
    skill.write_bytes(canonical_bytes + b"\n<!-- stale generated output from another checkout -->\n")
    assert manifest_store.fingerprint_file(skill) != canonical_hash

    human_exit, human_output = _upgrade_yes(project)
    assert human_exit == 0, human_output
    assert _DRIFT_BANNER not in human_output, human_output
    assert skill.read_bytes() == canonical_bytes
    assert _entry_hash(project) == canonical_hash

    # The --json leg must see drift too, not just re-run against the regenerated file.
    skill.write_bytes(canonical_bytes + b"\n<!-- stale generated output from another checkout -->\n")
    json_exit, payload = _upgrade_yes_json(project)
    assert json_exit == 0, payload
    assert payload["surface_repair"]["drifted_reported"] == [], payload
    assert skill.read_bytes() == canonical_bytes
    assert _entry_hash(project) == canonical_hash


# ---------------------------------------------------------------------------
# #6155 item 1 — each regenerated projection is named once (human + --json),
# in-sync / recorded-hash-equal stay silent, exit code and outcome unchanged.
# ---------------------------------------------------------------------------

_REGEN_LINE = "Regenerated a generated command skill that differed from the current version"
_STALE_EDIT = b"\n<!-- stale generated output from another checkout -->\n"


def test_6155_regenerated_projection_named_once_human_and_json(project: Path) -> None:
    """A drifted DERIVED command-skill projection regenerated by ``upgrade --yes`` is named
    exactly once in the human output and once under ``--json`` ``surface_repair['regenerated']``.
    RED on the base (the regenerate is silent)."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()

    skill.write_bytes(canonical_bytes + _STALE_EDIT)
    human_exit, human_output = _upgrade_yes(project)
    assert human_exit == 0, human_output
    regen_lines = [line for line in human_output.splitlines() if _REGEN_LINE in line]
    assert len(regen_lines) == 1, human_output
    assert _SKILL_REL in regen_lines[0], regen_lines
    assert skill.read_bytes() == canonical_bytes

    skill.write_bytes(canonical_bytes + _STALE_EDIT)
    json_exit, payload = _upgrade_yes_json(project)
    assert json_exit == 0, payload
    regenerated = payload["surface_repair"]["regenerated"]
    named = [path for path in regenerated if path.endswith(_SKILL_REL)]
    assert len(named) == 1, payload
    assert skill.read_bytes() == canonical_bytes


def test_6155_in_sync_projection_emits_no_regenerated_line(project: Path) -> None:
    """Negative control (US1 scenario 2): an in-sync projection regenerates nothing and emits
    no regenerated line in either output surface."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()

    human_exit, human_output = _upgrade_yes(project)
    assert human_exit == 0, human_output
    assert _REGEN_LINE not in human_output

    json_exit, payload = _upgrade_yes_json(project)
    assert json_exit == 0, payload
    assert payload["surface_repair"]["regenerated"] == [], payload
    assert skill.read_bytes() == canonical_bytes


def test_6155_recorded_hash_equal_projection_emits_no_regenerated_line(project: Path) -> None:
    """Negative control (US1 scenario 3 / #5574): bytes equal the recorded manifest hash but
    not today's render (a version-bump re-render). It is re-rendered silently — no regenerated
    line — because it never enters the drift branch."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()
    canonical_hash = manifest_store.fingerprint_file(skill)
    _set_entry_hash(project, _STALE_HASH)
    assert _entry_hash(project) != canonical_hash

    human_exit, human_output = _upgrade_yes(project)
    assert human_exit == 0, human_output
    assert _REGEN_LINE not in human_output

    skill.write_bytes(canonical_bytes)  # restore canonical bytes; recorded hash stale again
    _set_entry_hash(project, _STALE_HASH)
    json_exit, payload = _upgrade_yes_json(project)
    assert json_exit == 0, payload
    assert payload["surface_repair"]["regenerated"] == [], payload


def test_6155_exit_code_and_outcome_kind_unchanged_by_regeneration(project: Path) -> None:
    """NFR-001: regenerating a drifted projection leaves the process exit code and the
    ``outcome`` kind identical to a clean (in-sync) run on the same fixture."""
    skill = project / _SKILL_REL
    canonical_bytes = skill.read_bytes()

    baseline_exit, baseline_payload = _upgrade_yes_json(project)

    skill.write_bytes(canonical_bytes + _STALE_EDIT)
    regen_exit, regen_payload = _upgrade_yes_json(project)

    assert regen_exit == baseline_exit == 0, (baseline_payload, regen_payload)
    assert regen_payload["outcome"] == baseline_payload["outcome"], (baseline_payload, regen_payload)
    assert regen_payload["status"] == baseline_payload["status"], (baseline_payload, regen_payload)
    assert [p for p in regen_payload["surface_repair"]["regenerated"] if p.endswith(_SKILL_REL)]
