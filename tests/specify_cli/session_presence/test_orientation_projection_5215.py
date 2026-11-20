"""Acceptance tests for the committed-orientation content authority (#5215).

The committed orientation block names the recorded project (``project.slug``),
else the git remote repository name, else ``"unknown"`` -- never the checkout
directory name. Committed health is deterministic (``healthy``); only the live
SessionStart hook shows live health, with the same project name.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core.agent_config import AgentConfig
from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.manager import SessionPresenceManager
from specify_cli.session_presence.projection import (
    expected_orientation,
    orientation_writer,
    resolve_project_slug,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "local-agent-bus"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _project(tmp_path: Path, *, slug: str | None = _SLUG) -> Path:
    """A project checked out in a directory whose name differs from its slug."""
    root = tmp_path / "dirname-differs"
    (root / ".kittify").mkdir(parents=True)
    (root / ".claude").mkdir()
    lines = ["agents:", "  available:", "  - claude"]
    if slug is not None:
        lines += ["project:", f"  slug: {slug}"]
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


class TestResolveProjectSlug:
    def test_recorded_slug_wins_over_directory_name(self, tmp_path: Path) -> None:
        assert resolve_project_slug(_project(tmp_path)) == _SLUG

    def test_missing_slug_uses_git_remote_repository_name(self, tmp_path: Path) -> None:
        root = _project(tmp_path, slug=None)
        _git("init", "-q", cwd=root)
        _git("remote", "add", "origin", "https://example.invalid/acme/acme-widgets.git", cwd=root)

        assert resolve_project_slug(root) == "acme-widgets"

    def test_missing_slug_and_no_remote_is_unknown_never_the_directory(self, tmp_path: Path) -> None:
        root = _project(tmp_path, slug=None)
        _git("init", "-q", cwd=root)

        slug = resolve_project_slug(root)

        assert slug == "unknown"
        assert slug != root.name

    def test_recorded_slug_spawns_no_git_subprocess(self, tmp_path: Path) -> None:
        """NFR-003: a recorded slug costs no ``git`` call."""
        root = _project(tmp_path)
        with patch("subprocess.run", side_effect=AssertionError("git spawned")):
            assert resolve_project_slug(root) == _SLUG


class TestExpectedOrientation:
    def test_names_the_identity_slug_not_the_directory(self, tmp_path: Path) -> None:
        content = expected_orientation(_project(tmp_path))

        assert content.project_slug == _SLUG
        assert "dirname-differs" not in content.render()

    def test_health_is_deterministic_even_when_an_upgrade_is_cached(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        with patch(
            "specify_cli.session_presence.upgrade_check.UpgradeChecker.get_available_version",
            return_value="999.0.0",
        ):
            content = expected_orientation(root)

        assert content.health == "healthy"
        assert content.available_version is None
        assert "Upgrade available" not in content.render()

    def test_unknown_installed_version_refuses(self, tmp_path: Path) -> None:
        from importlib.metadata import PackageNotFoundError

        with (
            patch("specify_cli.session_presence.projection.version", side_effect=PackageNotFoundError("spec-kitty-cli")),
            pytest.raises(ValueError, match="version is unavailable"),
        ):
            expected_orientation(_project(tmp_path))

    def test_manager_build_content_is_the_committed_content(self, tmp_path: Path) -> None:
        """The shipped migrations write through ``_build_content`` (#5215 (h))."""
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
        with patch(
            "specify_cli.session_presence.upgrade_check.UpgradeChecker.get_available_version",
            return_value="999.0.0",
        ):
            assert manager._build_content() == expected_orientation(root)

    def test_dry_run_preview_and_write_use_the_same_content(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
        manager.update()
        written = (root / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")

        assert expected_orientation(root).render().rstrip("\n") in written


class TestLiveContentAgreesWithFiles:
    def test_hook_and_committed_block_name_the_same_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))

        live = manager.live_content()

        assert live.project_slug == expected_orientation(root).project_slug == _SLUG

    def test_hook_still_shows_live_health(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
        with patch(
            "specify_cli.session_presence.manager.UpgradeChecker.get_available_version",
            return_value="999.0.0",
        ):
            live = manager.live_content()

        assert live.health == "upgrade-available"
        assert live.available_version == "999.0.0"


class TestOrientationWriter:
    def test_configured_markdown_writer_with_harness_dir(self, tmp_path: Path) -> None:
        assert orientation_writer(_project(tmp_path), "claude", {"claude"}) is not None

    def test_unconfigured_key_is_not_applicable(self, tmp_path: Path) -> None:
        assert orientation_writer(_project(tmp_path), "claude", {"codex"}) is None

    def test_missing_harness_dir_is_not_applicable(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / ".claude").rmdir()
        assert orientation_writer(root, "claude", None) is None

    def test_writer_without_orientation_mechanism_is_not_applicable(self, tmp_path: Path) -> None:
        assert orientation_writer(_project(tmp_path), "not-a-harness", None) is None


def test_content_value_is_a_session_presence_content(tmp_path: Path) -> None:
    assert isinstance(expected_orientation(_project(tmp_path)), SessionPresenceContent)
