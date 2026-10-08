"""Integration tests for ``spec-kitty doctor tool-surfaces``.

These run the checkout-local ``specify_cli`` package against a controlled
``.kittify`` fixture, so output never depends on the developer's ambient config.
The ``--json`` output is validated against the published contract schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from ._compat_support import (
    run_spec_kitty,
    write_controlled_project,
)

import pytest

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / "pyproject.toml").exists():
    _REPO_ROOT = _REPO_ROOT.parent
_SCHEMA_PATH = (
    _REPO_ROOT
    / "kitty-specs"
    / "tool-surface-contract-01KV2K2P"
    / "contracts"
    / "doctor-tool-surfaces-output.schema.json"
)


def _schema() -> dict[str, object]:
    data: dict[str, object] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return data


def test_doctor_tool_surfaces_json_schema(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty("doctor", "tool-surfaces", "--json", cwd=project)
    assert result.returncode in (0, 1), result.stderr
    payload = result.json()
    jsonschema.validate(payload, _schema())


def test_doctor_tool_surfaces_runs_with_no_tools(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path, agents=[])
    result = run_spec_kitty("doctor", "tool-surfaces", "--json", cwd=project)
    assert result.returncode in (0, 1), result.stderr
    payload = result.json()
    jsonschema.validate(payload, _schema())
    assert payload["configured_tools"] == []
    assert payload["summary"]["surfaces"] == 0
    assert payload["ok"] is True


def test_doctor_tool_surfaces_kind_filter(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty(
        "doctor", "tool-surfaces", "--kind", "command-skill", "--json", cwd=project
    )
    payload = result.json()
    jsonschema.validate(payload, _schema())
    kinds = {entry["kind"] for entry in payload["surfaces"]}
    assert kinds <= {"command_skill"}
    ids = [entry["id"] for entry in payload["surfaces"]]
    assert len(ids) == len(set(ids))


def test_doctor_tool_surfaces_finding_when_missing(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty(
        "doctor", "tool-surfaces", "--kind", "command-skill", "--json", cwd=project
    )
    payload = result.json()
    codes = {f["code"] for f in payload["findings"]}
    assert "generated-surface-missing" in codes
    assert payload["ok"] is False
    assert result.returncode == 1


def test_doctor_tool_surfaces_reports_doctrine_when_manifest_absent(
    tmp_path: Path,
) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty(
        "doctor",
        "tool-surfaces",
        "--kind",
        "charter-skill",
        "--json",
        cwd=project,
    )
    payload = result.json()

    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["summary"]["surfaces"] > 0
    assert {entry["kind"] for entry in payload["surfaces"]} == {"charter_skill"}
    assert {finding["code"] for finding in payload["findings"]} == {
        "generated-surface-missing"
    }


def test_doctor_tool_surfaces_fix_rebuilds_plan_before_reporting(
    tmp_path: Path,
) -> None:
    project = write_controlled_project(tmp_path)
    old_entry = {
        "path": ".agents/skills/spec-kitty.analyze/SKILL.md",
        "content_hash": "0" * 64,
        "agents": ["codex"],
        "installed_at": "2026-06-14T00:00:00+00:00",
        "spec_kitty_version": "old",
    }
    (project / ".kittify" / "command-skills-manifest.json").write_text(
        json.dumps({"schema_version": 1, "entries": [old_entry]}),
        encoding="utf-8",
    )

    result = run_spec_kitty(
        "doctor",
        "tool-surfaces",
        "--kind",
        "command-skill",
        "--fix",
        "--json",
        cwd=project,
    )
    payload = result.json()

    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_doctor_tool_surfaces_tool_filter(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path, agents=["codex", "claude"])
    result = run_spec_kitty(
        "doctor", "tool-surfaces", "--tool", "codex", "--json", cwd=project
    )
    payload = result.json()
    jsonschema.validate(payload, _schema())
    assert payload["configured_tools"] == ["codex"]


def test_unknown_kind_token_is_rejected(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty(
        "doctor", "tool-surfaces", "--kind", "bogus-kind", "--json", cwd=project
    )
    assert result.returncode == 2
    payload = result.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unknown_kind"


def test_finding_codes_are_kebab_case(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty("doctor", "tool-surfaces", "--json", cwd=project)
    payload = result.json()
    for finding in payload["findings"]:
        code = finding["code"]
        assert code.islower()
        assert "_" not in code


def test_doctor_tool_surfaces_plugin_manifest_kind(tmp_path: Path) -> None:
    """``--kind plugin-manifest`` surfaces the staging bundle manifests (WP09)."""
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty(
        "doctor",
        "tool-surfaces",
        "--kind",
        "plugin-manifest",
        "--json",
        cwd=project,
    )
    payload = result.json()
    jsonschema.validate(payload, _schema())
    kinds = {entry["kind"] for entry in payload["surfaces"]}
    assert kinds <= {"plugin_manifest"}
    # One manifest per distribution target (no bundle staged yet -> missing).
    tools = {entry["tool"] for entry in payload["surfaces"]}
    assert tools == {
        "claude_code_plugin",
        "copilot_skill_package",
        "vscode_extension",
    }
    # OPTIONAL policy: a missing staging bundle must not flip ``ok`` to false.
    assert payload["ok"] is True
    assert all(entry["state"] == "missing" for entry in payload["surfaces"])


def test_migration_compat_still_passes(tmp_path: Path) -> None:
    """doctor skills --json schema is unchanged (re-run the compat assertion)."""
    fixtures = Path(__file__).parent / "fixtures"
    baseline = json.loads(
        (fixtures / "doctor_skills_baseline.json").read_text(encoding="utf-8")
    )
    from ._compat_support import schema_shape

    project = write_controlled_project(tmp_path)
    result = run_spec_kitty("doctor", "skills", "--json", cwd=project)
    assert result.returncode in (0, 1), result.stderr
    assert schema_shape(result.json()) == baseline
