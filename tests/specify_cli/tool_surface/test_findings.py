"""Unit tests for ``tool_surface.findings``."""

from __future__ import annotations

from pathlib import Path

from specify_cli.tool_surface import findings
from specify_cli.tool_surface.findings import SurfaceFinding, make_finding

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Every published code constant -> its expected kebab-case wire value.
_EXPECTED_CODES = {
    "GENERATED_SURFACE_MISSING": "generated-surface-missing",
    "MANAGED_FILE_DRIFT": "managed-file-drift",
    "STALE_GENERATED_SURFACE": "stale-generated-surface",
    "UNSAFE_MANAGED_PATH": "unsafe-managed-path",
    "UNMANAGED_SPEC_KITTY_SURFACE": "unmanaged-spec-kitty-surface",
    "CONFIGURED_TOOL_SURFACE_UNINSTALLED": "configured-tool-surface-uninstalled",
    "CONTEXT_FILE_MISSING": "context-file-missing",
    "SESSION_PRESENCE_INCOMPLETE": "session-presence-incomplete",
    "NATIVE_CONFIG_MISSING": "native-config-missing",
    "NATIVE_AGENT_PROFILE_MISSING": "native-agent-profile-missing",
    "NATIVE_AGENT_PROFILE_DRIFT": "native-agent-profile-drift",
    "PROFILE_PROJECTION_UNSUPPORTED": "profile-projection-unsupported",
    "RESEARCH_GAP_SURFACE": "research-gap-surface",
    "BUNDLE_COMPONENT_MISSING": "bundle-component-missing",
    "PLUGIN_MANIFEST_STALE_PATH": "plugin-manifest-stale-path",
}


def test_all_codes_are_kebab_case_values() -> None:
    for const_name, expected in _EXPECTED_CODES.items():
        value = getattr(findings, const_name)
        assert value == expected
        assert value.islower()
        assert "_" not in value
        assert " " not in value


def test_make_finding_minimal() -> None:
    finding = make_finding(
        findings.GENERATED_SURFACE_MISSING,
        findings.SEVERITY_ERROR,
        "missing file",
    )
    assert isinstance(finding, SurfaceFinding)
    assert finding.code == "generated-surface-missing"
    assert finding.severity == "error"
    assert finding.tool_key is None
    assert finding.details == {}


def test_make_finding_full_and_to_json() -> None:
    finding = make_finding(
        findings.MANAGED_FILE_DRIFT,
        findings.SEVERITY_WARNING,
        "drift",
        tool_key="codex",
        surface_id="codex.command_skill.SKILL.md",
        path=Path("/nonexistent/x/SKILL.md"),
        repair_command="spec-kitty doctor tool-surfaces --fix",
        docs_ref="docs/x.md",
        details={"k": "v"},
    )
    payload = finding.to_json()
    assert payload["code"] == "managed-file-drift"
    assert payload["severity"] == "warning"
    assert payload["tool_key"] == "codex"
    assert payload["path"] == "/nonexistent/x/SKILL.md"
    assert payload["details"] == {"k": "v"}


def test_to_json_null_path() -> None:
    finding = make_finding(
        findings.RESEARCH_GAP_SURFACE, findings.SEVERITY_INFO, "gap"
    )
    assert finding.to_json()["path"] is None


def test_severity_constants_are_wire_values() -> None:
    assert findings.SEVERITY_ERROR == "error"
    assert findings.SEVERITY_WARNING == "warning"
    assert findings.SEVERITY_INFO == "info"
