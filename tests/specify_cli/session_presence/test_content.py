"""T018 — Tests for SessionPresenceContent.render().

Covers all health states, section delimiters, and frozen-instance invariant.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from specify_cli.session_presence.content import (
    SECTION_CLOSE,
    SECTION_OPEN,
    SessionPresenceContent,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
class TestRenderHealthy:
    def test_contains_version(self, healthy_content: SessionPresenceContent) -> None:
        assert "3.2.0" in healthy_content.render()

    def test_contains_project_slug(self, healthy_content: SessionPresenceContent) -> None:
        assert "my-project" in healthy_content.render()

    def test_contains_healthy_marker(self, healthy_content: SessionPresenceContent) -> None:
        assert "(healthy)" in healthy_content.render()

    def test_contains_full_mission_pattern(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert "spec-kitty.specify" in rendered

    def test_contains_dispatch_command(self, healthy_content: SessionPresenceContent) -> None:
        """T016 pin: orientation block must name spec-kitty dispatch (FR-006/NFR-005)."""
        rendered = healthy_content.render()
        assert "spec-kitty dispatch" in rendered

    def test_no_upgrade_line(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert "Upgrade available" not in rendered

    def test_no_migration_line(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert "migration required" not in rendered.lower()


class TestRenderUpgradeAvailable:
    def test_contains_upgrade_line(self, upgrade_content: SessionPresenceContent) -> None:
        assert "Upgrade available" in upgrade_content.render()

    def test_contains_available_version(self, upgrade_content: SessionPresenceContent) -> None:
        assert "3.3.0" in upgrade_content.render()

    def test_no_migration_line(self, upgrade_content: SessionPresenceContent) -> None:
        rendered = upgrade_content.render()
        assert "migration required" not in rendered.lower()


class TestRenderMigrationRequired:
    def test_contains_migration_warning(self, migration_content: SessionPresenceContent) -> None:
        rendered = migration_content.render()
        assert "migration required" in rendered.lower()

    def test_no_upgrade_line(self, migration_content: SessionPresenceContent) -> None:
        rendered = migration_content.render()
        assert "Upgrade available" not in rendered


class TestRenderAsciiOnly:
    """#5757: the orientation block is injected into agent instruction files
    that some projects require to be ASCII-only, so the rendered text must
    never contain non-ASCII characters (em dash, arrow, warning glyph)."""

    @pytest.mark.parametrize(
        "fixture_name",
        ["healthy_content", "upgrade_content", "migration_content"],
    )
    def test_render_is_ascii_only(self, fixture_name: str, request: pytest.FixtureRequest) -> None:
        rendered = request.getfixturevalue(fixture_name).render()
        assert rendered.isascii()


class TestRenderDelimiters:
    def test_starts_with_section_open(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert rendered.startswith(SECTION_OPEN)

    def test_ends_with_section_close_newline(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert rendered.endswith(SECTION_CLOSE + "\n")

    def test_exactly_one_section_open(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert rendered.count(SECTION_OPEN) == 1

    def test_exactly_one_section_close(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert rendered.count(SECTION_CLOSE) == 1


class TestFrozenInstance:
    def test_frozen_version_attribute(self, healthy_content: SessionPresenceContent) -> None:
        """C-004: SessionPresenceContent must be frozen (immutable value object)."""
        with pytest.raises(FrozenInstanceError):
            healthy_content.version = "x"

    def test_frozen_health_attribute(self, healthy_content: SessionPresenceContent) -> None:
        with pytest.raises(FrozenInstanceError):
            healthy_content.health = "upgrade-available"


class TestNoNextImports:
    def test_no_next_imports(self) -> None:
        """C-004 / D2: session_presence must not import from the deprecated specify_cli.next shim.

        The architectural test at tests/architectural/test_shared_package_boundary.py
        provides repo-wide enforcement. This test validates the session_presence
        package specifically for in-worktree coverage.
        """
        import importlib
        import pkgutil

        import specify_cli.session_presence as pkg

        pkg_path = pkg.__path__
        for _finder, name, _ispkg in pkgutil.walk_packages(pkg_path, prefix="specify_cli.session_presence."):
            try:
                mod = importlib.import_module(name)
            except ImportError:
                continue
            # The module's __spec__.origin points to the file — check no .next. in the path
            origin = getattr(getattr(mod, "__spec__", None), "origin", "") or ""
            assert "specify_cli/next" not in origin.replace("\\", "/"), f"Module {name} originates from the specify_cli/next shim: {origin}"
            # Also verify __file__ doesn't reference the next shim
            mod_file = getattr(mod, "__file__", "") or ""
            assert "specify_cli/next" not in mod_file.replace("\\", "/"), f"Module {name} file is in specify_cli.next: {mod_file}"


class TestRenderCloseContract:
    """WP06 T025/T027 — orientation teaches the open→work→close contract."""

    def test_contains_close_instruction(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert "After finishing the work, close the Op" in rendered
        assert ("spec-kitty profile-invocation complete --invocation-id <id> --outcome <done|failed|abandoned>") in rendered

    def test_says_dispatch_opens_the_op(self, healthy_content: SessionPresenceContent) -> None:
        rendered = healthy_content.render()
        assert "opens the Op" in rendered
        assert "records the Op" not in rendered
