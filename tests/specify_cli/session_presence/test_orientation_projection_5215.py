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
from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN, SessionPresenceContent
from specify_cli.session_presence.manager import SessionPresenceManager
from specify_cli.session_presence.projection import (
    expected_orientation,
    orientation_drift,
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

    def test_committed_content_never_consults_live_health(self, tmp_path: Path) -> None:
        """Before #5215 ``_build_content`` read the upgrade cache and the compat planner."""
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
        with (
            patch("specify_cli.session_presence.manager.UpgradeChecker", side_effect=AssertionError("upgrade cache read")),
            patch("specify_cli.compat.plan", side_effect=AssertionError("compat planner run")),
        ):
            content = manager._build_content()

        assert content.health == "healthy"
        assert content.available_version is None
        assert "Upgrade available" not in content.render()

    def test_unknown_installed_version_refuses(self, tmp_path: Path) -> None:
        from importlib.metadata import PackageNotFoundError

        with (
            patch("importlib.metadata.version", side_effect=PackageNotFoundError("spec-kitty-cli")),
            pytest.raises(ValueError, match="version is unavailable"),
        ):
            expected_orientation(_project(tmp_path))

    def test_empty_installed_version_refuses(self, tmp_path: Path) -> None:
        with (
            patch("importlib.metadata.version", return_value=""),
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
        target = root / ".claude" / "CLAUDE.md"
        with patch.object(SessionPresenceManager, "_build_content", wraps=manager._build_content) as build:
            preview = manager.update(dry_run=True)

        build.assert_called_once_with()
        assert preview.changes == ["Would write orientation for claude"]
        assert not target.exists()

        manager.update()
        assert expected_orientation(root).render().rstrip("\n") in target.read_text(encoding="utf-8")


def _live(manager: SessionPresenceManager, available: str | None) -> SessionPresenceContent:
    """``live_content`` with the upgrade cache and the compat planner pinned (no host state)."""
    from specify_cli.compat import Decision

    with (
        patch("specify_cli.session_presence.manager.UpgradeChecker") as checker,
        patch("specify_cli.compat.plan") as planner,
    ):
        checker.return_value.get_available_version.return_value = available
        planner.return_value.decision = Decision.ALLOW
        return manager.live_content()


class TestLiveContentAgreesWithFiles:
    def test_hook_and_committed_block_name_the_same_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))

        live = _live(manager, "999.0.0")

        assert live.project_slug == expected_orientation(root).project_slug == _SLUG

    def test_hook_still_shows_live_health(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
        live = _live(manager, "999.0.0")

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


class TestOrientationDrift:
    """Branches of ``projection.orientation_drift`` the provider acceptance tests do not reach."""

    _RULES = ".claude/CLAUDE.md"

    def _write(self, root: Path, text: str) -> None:
        (root / self._RULES).write_text(text, encoding="utf-8", newline="")

    def test_absent_file_is_not_drift(self, tmp_path: Path) -> None:
        assert not orientation_drift(_project(tmp_path), self._RULES)

    def test_file_without_block_is_not_drift(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        self._write(root, "# notes\n")
        assert not orientation_drift(root, self._RULES)

    def test_duplicate_markers_are_not_judged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        block = SessionPresenceContent("0.0.1", _SLUG, "healthy", None).render()
        self._write(root, block + block)
        assert not orientation_drift(root, self._RULES)

    def test_unknown_installed_version_is_not_judged(self, tmp_path: Path) -> None:
        from importlib.metadata import PackageNotFoundError

        root = _project(tmp_path)
        self._write(root, SessionPresenceContent("0.0.1", _SLUG, "healthy", None).render())
        with patch("importlib.metadata.version", side_effect=PackageNotFoundError("spec-kitty-cli")):
            assert not orientation_drift(root, self._RULES)

    def test_block_without_version_stamp_is_not_drift(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        self._write(root, f"{SECTION_OPEN}\nhand-written\n{SECTION_CLOSE}\n")
        assert not orientation_drift(root, self._RULES)

    def test_unterminated_version_stamp_is_not_drift(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        self._write(root, f"{SECTION_OPEN}\n**Spec Kitty v0.0.1 - no closing bold\n{SECTION_CLOSE}\n")
        assert not orientation_drift(root, self._RULES)

    def test_mixed_newlines_agree_with_the_writer(self, tmp_path: Path) -> None:
        """Reviewer LOW B / squad: CRLF outside the block, LF inside -- no pending rewrite either way."""
        from specify_cli.session_presence.writers.registry import get_writer

        root = _project(tmp_path)
        self._write(root, "# notes\r\n\r\n" + expected_orientation(root).render())

        assert not orientation_drift(root, self._RULES)
        assert not get_writer("claude").prepare(root, expected_orientation(root)).changed


def test_enclosing_repository_never_names_the_project(tmp_path: Path) -> None:
    """A project that is not its own repository does not borrow the parent repository's name."""
    _git("init", "-q", cwd=tmp_path)
    _git("remote", "add", "origin", "https://example.invalid/acme/dotfiles.git", cwd=tmp_path)
    root = _project(tmp_path, slug=None)

    with patch("subprocess.run", side_effect=AssertionError("git spawned")):
        assert resolve_project_slug(root) == "unknown"


def test_slug_lookup_survives_a_wedged_git(tmp_path: Path) -> None:
    root = _project(tmp_path, slug=None)
    _git("init", "-q", cwd=root)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["git"], 10)):
        assert resolve_project_slug(root) == "unknown"


@pytest.mark.parametrize("operation", ["install", "update"])
def test_writer_selection_failure_is_a_warning_not_a_crash(tmp_path: Path, operation: str) -> None:
    """The manager never raises: a failing applicability check is reported per agent."""
    root = _project(tmp_path)
    manager = SessionPresenceManager(root, AgentConfig(available=["claude"]))
    with patch("specify_cli.session_presence.manager.orientation_writer", side_effect=OSError("boom")):
        result = getattr(manager, operation)()

    assert result.changes == []
    assert any("boom" in warning for warning in result.warnings)


def test_linked_worktree_with_a_git_file_uses_its_own_remote(tmp_path: Path) -> None:
    """#5215 review L3: in a linked worktree (or submodule) ``.git`` is a file, not a directory."""
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "init", cwd=main)
    _git("remote", "add", "origin", "https://example.invalid/acme/acme-widgets.git", cwd=main)
    _git("worktree", "add", "-q", str(tmp_path / "wt"), cwd=main)
    root = tmp_path / "wt"
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n  - claude\n", encoding="utf-8")

    assert (root / ".git").is_file()
    assert resolve_project_slug(root) == "acme-widgets"
