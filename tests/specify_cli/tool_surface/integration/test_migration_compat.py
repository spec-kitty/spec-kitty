"""Migration compatibility gate for ``spec-kitty doctor skills --json``.

These tests freeze the ``doctor skills --json`` output **schema** (keys + value
types, not content) as a backward-compatibility baseline for the entire
ToolSurfaceContract epic. Any subsequent WP (WP03-WP09) that changes the schema
breaks these tests and therefore cannot merge.

The tests are deterministic: they run the checkout-local ``specify_cli`` package
against a controlled ``.kittify`` fixture in ``tmp_path``, so the result never
depends on what tools the developer has configured.
"""

from __future__ import annotations

import json
from pathlib import Path

from ._compat_support import (
    project_root,
    run_spec_kitty,
    schema_shape,
    write_controlled_project,
)

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_mod
from specify_cli.cli.commands.doctor import app

pytestmark = [pytest.mark.integration]

_runner = CliRunner()

_FIXTURES = Path(__file__).parent / "fixtures"
_BASELINE = _FIXTURES / "doctor_skills_baseline.json"


def _load_baseline() -> dict[str, object]:
    data: dict[str, object] = json.loads(_BASELINE.read_text(encoding="utf-8"))
    return data


def test_doctor_skills_json_is_valid_json(tmp_path: Path) -> None:
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty("doctor", "skills", "--json", cwd=project)
    # Exit code may be 0 or 1 (1 = healthy schema but agents need install);
    # both produce valid JSON. Anything >=2 is an unexpected error.
    assert result.returncode in (0, 1), result.stderr
    parsed = result.json()  # raises if stdout is not valid JSON
    assert isinstance(parsed, dict)


def test_doctor_skills_json_schema_matches_baseline(tmp_path: Path) -> None:
    """The success-path schema shape must equal the committed baseline."""
    project = write_controlled_project(tmp_path)
    result = run_spec_kitty("doctor", "skills", "--json", cwd=project)
    assert result.returncode in (0, 1), result.stderr
    actual_shape = schema_shape(result.json())
    assert actual_shape == _load_baseline(), (
        "doctor skills --json schema drifted from the frozen baseline. "
        "If this change is intentional and additive, regenerate "
        "doctor_skills_baseline.json and document it per "
        "src/specify_cli/tool_surface/contracts/migration-compatibility.md."
    )


def test_doctor_skills_json_has_frozen_top_level_keys(tmp_path: Path) -> None:
    """Explicit assertions on the frozen field set (not just shape equality)."""
    project = write_controlled_project(tmp_path)
    output = run_spec_kitty("doctor", "skills", "--json", cwd=project).json()
    frozen_keys = {
        "ok",
        "configured_agents",
        "manifest_agents",
        "entries",
        "drift",
        "gaps",
        "orphans",
        "stale",
        "unsafe",
        "slash_commands",
    }
    assert frozen_keys.issubset(output.keys()), (
        f"Missing frozen keys: {frozen_keys - set(output.keys())}"
    )
    assert isinstance(output["ok"], bool)
    for list_key in ("configured_agents", "drift", "gaps", "orphans", "stale", "unsafe"):
        assert isinstance(output[list_key], list), f"{list_key} must be a list"
    assert isinstance(output["slash_commands"], dict)


def test_doctor_skills_json_is_deterministic(tmp_path: Path) -> None:
    """Same controlled fixture => identical output across runs (no ambient state)."""
    project = write_controlled_project(tmp_path)
    first = run_spec_kitty("doctor", "skills", "--json", cwd=project)
    second = run_spec_kitty("doctor", "skills", "--json", cwd=project)
    assert first.returncode == second.returncode
    assert first.json() == second.json()


def test_doctor_skills_json_error_schema_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The structured error envelope is frozen too: {ok, error:{code, message}}.

    Post-#1965, ``locate_project_root`` treats an existing-directory
    ``SPECIFY_REPO_ROOT`` as authoritative even without ``.kittify/`` — so the
    old approach of pointing the override at an empty dir now *succeeds* (the
    dir becomes the root) instead of reaching ``not_in_project``. Reaching the
    error path via the resolver would require a failing Tier-2 walk-up, which is
    non-deterministic: a leaked ``.kittify`` in the OS temp directory (E2E test
    pollution) above a temp cwd would resolve and pass.

    To freeze the *error envelope* deterministically we force the resolver's
    ``None`` outcome directly and assert doctor's formatting of it. This pins
    ``doctor.py``'s ``not_in_project`` branch (code + message keys), which is a
    distinct contract from the success-path schema frozen by the tests above.
    """
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: None)
    result = _runner.invoke(app, ["skills", "--json"])
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert isinstance(payload["error"], dict)
    assert payload["error"]["code"] == "not_in_project"
    assert "message" in payload["error"]
    assert isinstance(payload["error"]["code"], str)
    assert isinstance(payload["error"]["message"], str)


# ---------------------------------------------------------------------------
# T043 — doctor tool-surfaces --json surface-kind stability contract
# ---------------------------------------------------------------------------

# Additive-only contract (FR-042/NFR-005): new surface kinds are welcome, but
# any kind in this frozen set must continue to be a recognised surface kind.
# ``agent_profile`` was added in the agent-profile-projection mission.
# One deliberate break: ``doctrine_skill`` was renamed to ``charter_skill`` by
# #3732 (FR-009), an owner-ruled full cutover per ADR 2026-10-06-1 section 7:
# no alias member, no read alias (C-001). The rename is listed in the
# changelog Before/After. Surface ids are not persisted (the skills manifest
# stores installed paths), so no stored value carries the old kind.
EXPECTED_SURFACE_KINDS = frozenset(
    {
        "command_skill",
        "command_file",
        "charter_skill",
        "context_file",
        "hook",
        "rule",
        "native_config",
        "plugin_manifest",
        "agent_profile",
    }
)


def test_doctor_surface_kinds_are_known_enum_members() -> None:
    """Every frozen surface kind must remain a valid ``ToolSurfaceKind`` value."""
    from specify_cli.tool_surface.enums import ToolSurfaceKind

    valid = {kind.value for kind in ToolSurfaceKind}
    missing = EXPECTED_SURFACE_KINDS - valid
    assert not missing, (
        f"frozen surface kinds no longer exist in ToolSurfaceKind enum: {missing}"
    )


def test_doctor_emits_agent_profile_kind(tmp_path: Path) -> None:
    """``doctor tool-surfaces --json`` must surface ``agent_profile`` after renderers land.

    A claude+codex project has native agent-profile surfaces, so the kind must
    appear in the report. FR-016: Codex no longer reports ``research_gap`` once
    its renderer is wired.
    """
    project = write_controlled_project(tmp_path, agents=["claude", "codex"])
    result = run_spec_kitty("doctor", "tool-surfaces", "--json", cwd=project)
    assert result.returncode in (0, 1), result.stderr
    payload = result.json()

    actual_kinds = {surface["kind"] for surface in payload["surfaces"]}
    assert "agent_profile" in actual_kinds, (
        "doctor tool-surfaces must report the agent_profile surface kind"
    )
    # Additive-only: nothing emitted may be an unknown kind.
    from specify_cli.tool_surface.enums import ToolSurfaceKind

    valid = {kind.value for kind in ToolSurfaceKind}
    assert actual_kinds <= valid, (
        f"doctor emitted unknown surface kinds: {actual_kinds - valid}"
    )

    # FR-016: agent_profile states for codex are concrete (not research_gap).
    codex_profile_states = {
        surface["state"]
        for surface in payload["surfaces"]
        if surface["kind"] == "agent_profile" and surface["tool"] == "codex"
    }
    assert "research_gap" not in codex_profile_states, (
        "Codex agent-profile must not report research_gap after its renderer lands"
    )


def test_baseline_fixture_is_machine_independent() -> None:
    """The baseline must not leak machine-specific paths or ambient config."""
    raw = _BASELINE.read_text(encoding="utf-8")
    assert str(Path.home()) not in raw
    assert str(project_root()) not in raw
    # Shape-only: leaf values are type names or empty containers, never content.
    baseline = _load_baseline()
    assert baseline["configured_agents"] == ["str"]
    assert baseline["ok"] == "bool"
