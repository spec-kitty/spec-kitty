"""Tests for the ClaudeBundleProjector plugin build command (WP04).

Covers:
    - plugin.json contains a real version (not "0.0.0" placeholder)
    - plugin.json passes expected schema shape
    - skills/ directory populated with the full canonical command-skill set
    - agents/ directory populated with at least one rendered profile
    - build is idempotent (second run produces identical output)
    - semver helper correctly classifies version strings
    - BuildError raised when skill count is too low
    - _builder utilities (get_cli_version, is_semver, write_json)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.tool_surface.bundles._builder import (
    MIN_SKILL_COUNT,
    BuildError,
    get_cli_version,
    is_semver,
    write_json,
)
from specify_cli.tool_surface.bundles.claude import ClaudeBundleProjector

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_full_claude_build_preserves_all_node_mtimes(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    projector = ClaudeBundleProjector(tmp_path / "dist")
    projector.build(skip_validate=True)
    before = snapshot({"stage": tmp_path})
    projector.build(skip_validate=True)
    assert_unchanged(before, snapshot({"stage": tmp_path}))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_build(tmp_path: Path, *, skip_validate: bool = True) -> Path:
    """Build a bundle and return the bundle directory."""
    result = ClaudeBundleProjector(tmp_path / "dist").build(skip_validate=skip_validate)
    return Path(result)


# ---------------------------------------------------------------------------
# T016 — plugin.json content / semver
# ---------------------------------------------------------------------------


class TestPluginJson:
    def test_plugin_json_exists(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        manifest_path = bundle_dir / ".claude-plugin" / "plugin.json"
        assert manifest_path.is_file(), "plugin.json must exist under .claude-plugin/"

    def test_plugin_json_has_real_version(self, tmp_path: Path) -> None:
        """Version must not be the '0.0.0' placeholder."""
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        version = payload["version"]
        assert version != "0.0.0", (
            "plugin.json version must come from importlib.metadata, not the placeholder"
        )
        # Must contain at least one dot-separated integer component.
        assert re.match(r"\d+\.\d+", version), (
            f"version {version!r} does not look like a version string"
        )

    def test_plugin_json_schema_shape(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        required_keys = {"name", "displayName", "version", "description", "author", "skills", "agents"}
        missing = required_keys - payload.keys()
        assert not missing, f"plugin.json missing keys: {missing}"
        assert payload["name"] == "spec-kitty"
        assert payload["skills"] == sorted(
            f"./skills/spec-kitty-{command}" for command in CANONICAL_COMMANDS
        )
        assert all(str(path).startswith("./agents/") for path in payload["agents"])

    def test_plugin_json_no_hooks_key_when_hooks_empty(self, tmp_path: Path) -> None:
        """hooks/ key must be absent when hooks/hooks.json is the empty placeholder."""
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        # The hooks placeholder is {"hooks": {}} and contains no hook entries.
        assert "hooks" not in payload


# ---------------------------------------------------------------------------
# T017 — skills/ directory
# ---------------------------------------------------------------------------


class TestSkillsCopy:
    def test_skills_dir_populated(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        skills_dir = bundle_dir / "skills"
        assert skills_dir.is_dir(), "skills/ directory must be created"
        skill_files = list(skills_dir.glob("*/SKILL.md"))
        assert len(skill_files) >= MIN_SKILL_COUNT, (
            f"Expected at least {MIN_SKILL_COUNT} skills, found {len(skill_files)}"
        )

    def test_all_canonical_commands_present(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        for command in CANONICAL_COMMANDS:
            skill_file = bundle_dir / "skills" / f"spec-kitty-{command}" / "SKILL.md"
            assert skill_file.is_file(), (
                f"Missing SKILL.md for canonical command: {command}"
            )

    def test_skill_files_have_frontmatter(self, tmp_path: Path) -> None:
        """Each SKILL.md must start with YAML frontmatter."""
        bundle_dir = _run_build(tmp_path)
        for skill_md in sorted((bundle_dir / "skills").glob("*/SKILL.md")):
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), (
                f"{skill_md.name} does not start with YAML frontmatter"
            )

    def test_command_skills_keep_native_user_invocable(self, tmp_path: Path) -> None:
        """The Claude bundle applies the native projection: ``user-invocable`` stays top-level (A-M4)."""
        bundle_dir = _run_build(tmp_path)
        for command in CANONICAL_COMMANDS:
            skill_md = bundle_dir / "skills" / f"spec-kitty-{command}" / "SKILL.md"
            frontmatter = YAML(typ="safe").load(skill_md.read_text(encoding="utf-8").split("---\n", 2)[1])
            assert list(frontmatter) == ["name", "description", "user-invocable"], skill_md
            assert frontmatter["user-invocable"] is True


# ---------------------------------------------------------------------------
# T018 — agents/ directory
# ---------------------------------------------------------------------------


class TestAgentsCopy:
    def test_agents_dir_populated(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        agents_dir = bundle_dir / "agents"
        assert agents_dir.is_dir(), "agents/ directory must be created"
        agent_files = list(agents_dir.glob("*.md"))
        assert len(agent_files) >= 1, "agents/ must contain at least one rendered profile"

    def test_agent_files_have_frontmatter(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        for agent_md in sorted((bundle_dir / "agents").glob("*.md")):
            content = agent_md.read_text(encoding="utf-8")
            assert content.startswith("---"), (
                f"{agent_md.name} does not start with YAML frontmatter"
            )

    def test_hooks_placeholder_created(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        hooks_json = bundle_dir / "hooks" / "hooks.json"
        assert hooks_json.is_file(), "hooks/hooks.json placeholder must be created"
        payload = json.loads(hooks_json.read_text(encoding="utf-8"))
        assert payload == {"hooks": {}}, (
            "hooks.json placeholder must be an empty hooks record"
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_build_produces_same_output(self, tmp_path: Path) -> None:
        """Running build twice must produce byte-identical output."""
        projector = ClaudeBundleProjector(tmp_path / "dist")
        bundle_dir_1 = projector.build(skip_validate=True)

        # Capture snapshot of files after first run.
        snapshot_1: dict[str, bytes] = {}
        for f in sorted(bundle_dir_1.rglob("*")):
            if f.is_file():
                snapshot_1[str(f.relative_to(bundle_dir_1))] = f.read_bytes()

        # Run again with the same projector (same output_dir).
        bundle_dir_2 = projector.build(skip_validate=True)
        assert bundle_dir_1 == bundle_dir_2

        snapshot_2: dict[str, bytes] = {}
        for f in sorted(bundle_dir_2.rglob("*")):
            if f.is_file():
                snapshot_2[str(f.relative_to(bundle_dir_2))] = f.read_bytes()

        assert snapshot_1 == snapshot_2, (
            "Build is not idempotent: second run produced different files"
        )


# ---------------------------------------------------------------------------
# T019 — validate step
# ---------------------------------------------------------------------------


class TestValidateStep:
    def test_skip_validate_flag_suppresses_claude_cli(self, tmp_path: Path) -> None:
        """With --skip-validate, claude CLI must never be invoked."""
        with patch("subprocess.run") as mock_run:
            _run_build(tmp_path, skip_validate=True)
        mock_run.assert_not_called()

    def test_validate_step_tolerates_missing_claude_cli(self, tmp_path: Path) -> None:
        """FileNotFoundError from missing claude CLI must not crash the build."""
        def _raise_fnf(*args: object, **kwargs: object) -> None:
            raise FileNotFoundError("claude not found")

        with patch("subprocess.run", side_effect=_raise_fnf):
            # Must complete without raising.
            bundle_dir = ClaudeBundleProjector(tmp_path / "dist").build(
                skip_validate=False
            )
        assert (bundle_dir / ".claude-plugin" / "plugin.json").is_file()

    def test_validate_step_raises_exit_on_nonzero(self, tmp_path: Path) -> None:
        """Non-zero exit from claude CLI must raise typer.Exit(code=1)."""
        import subprocess
        from typer import Exit

        fake_result = subprocess.CompletedProcess(
            args=["claude", "plugin", "validate", "--strict"],
            returncode=1,
            stdout="validation error\n",
            stderr="",
        )
        with patch("subprocess.run", return_value=fake_result), pytest.raises(Exit):
            ClaudeBundleProjector(tmp_path / "dist").build(skip_validate=False)


# ---------------------------------------------------------------------------
# _builder utilities
# ---------------------------------------------------------------------------


class TestBuilderUtilities:
    def test_get_cli_version_returns_string(self) -> None:
        version = get_cli_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_cli_version_fallback_on_missing_package(self) -> None:
        from importlib.metadata import PackageNotFoundError

        with patch(
            "specify_cli.tool_surface.bundles._builder.importlib.metadata.version",
            side_effect=PackageNotFoundError("spec-kitty-cli"),
        ):
            version = get_cli_version()
        assert "0.0.0" in version

    def test_is_semver_valid(self) -> None:
        assert is_semver("3.2.0")
        assert is_semver("1.0.0")
        assert is_semver("3.2.0rc44")  # pre-release suffix allowed (loose prefix check)
        assert is_semver("0.0.0+dev")  # starts with MAJOR.MINOR.PATCH — matches prefix

    def test_is_semver_invalid(self) -> None:
        assert not is_semver("dev")   # no numeric prefix at all
        assert not is_semver("")       # empty string never matches
        assert not is_semver("v3.2.0")  # leading 'v' is not allowed

    def test_write_json_creates_parents(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c.json"
        write_json(path, {"key": "value"})
        assert path.is_file()
        assert json.loads(path.read_text())["key"] == "value"

    def test_build_error_is_exception(self) -> None:
        err = BuildError("something went wrong")
        assert isinstance(err, Exception)
        assert "something went wrong" in str(err)
