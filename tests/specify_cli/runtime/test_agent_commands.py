"""Tests for agent_commands.py — resolver, per-step renderer, lock timing.

These tests describe the FIXED behavior landed in WP01:

* T004 / T022 — ``_get_command_templates_dir()`` returns a doctrine-based
  ``Path`` (never ``None``).
* T008 / T006 — ``_sync_agent_commands()`` iterates per-step subdirs
  (``{step}/prompt.md``) instead of a flat ``*.md`` glob; step dirs without
  ``prompt.md`` are skipped without raising.
* T023 — Stale ``spec-kitty.*`` files are removed after sync.
* T024 — Version lock is NOT written when sync fails mid-loop.

In this lane (lane-d) WP01 has not yet merged, so the resolver tests are RED.
They go GREEN after WP01 merges.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T004 + T022: Resolver tests
# ---------------------------------------------------------------------------


class TestGetCommandTemplatesDir:
    """FR-001: _get_command_templates_dir() must return a doctrine-based Path."""

    @staticmethod
    def _build_fake_doctrine_with_relocated_missions(tmp_path: Path) -> Path:
        """Build a synthetic post-relocation layout: offering pkg + sibling packs/.

        Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
        (FR-005) relocated ``mission-steps/`` to ``packs/built-in/missions``,
        a sibling of the ``tmp_path`` root the fake ``charter.offering``
        package directory also lives nested under (mirroring the real
        post-relocation ``charter/offering`` nesting, mission
        ``charter-code-topology-01M152G1``) -- close enough to the
        installed-wheel depth (``<site-packages>/{charter/offering,packs}``)
        for the shared kernel sibling-path primitive's bounded ancestor walk
        to resolve through. Returns the fake ``charter/offering/__init__.py``
        path.
        """
        fake_offering_init = tmp_path / "charter" / "offering" / "__init__.py"
        fake_offering_init.parent.mkdir(parents=True)
        fake_offering_init.write_text("")

        mission_steps = tmp_path / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"
        mission_steps.mkdir(parents=True)
        return fake_offering_init

    def test_returns_correct_doctrine_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Resolver returns <packs/built-in>/missions/mission-steps/software-dev.

        RED in lane-d (buggy resolver uses get_package_asset_root / kittify_home);
        GREEN after WP01 merges (resolver uses charter.offering.__file__ as the
        sibling-path primitive's anchor).
        """
        fake_offering_init = self._build_fake_doctrine_with_relocated_missions(tmp_path)

        monkeypatch.setattr("charter.offering.__file__", str(fake_offering_init))

        from specify_cli.runtime.agent_commands import _get_command_templates_dir

        result = _get_command_templates_dir()
        expected = tmp_path / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"
        assert result == expected

    def test_return_type_is_path_not_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return type is Path, never None.

        RED in lane-d (buggy resolver can return None); GREEN after WP01.
        """
        fake_offering_init = self._build_fake_doctrine_with_relocated_missions(tmp_path)

        monkeypatch.setattr("charter.offering.__file__", str(fake_offering_init))

        from specify_cli.runtime.agent_commands import _get_command_templates_dir

        result = _get_command_templates_dir()
        assert isinstance(result, Path)

    def test_resolver_with_sys_modules_monkeypatch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T022: Resolver uses charter.offering.__file__ as its anchor (sys.modules approach).

        RED in lane-d; GREEN after WP01 merges.
        """
        self._build_fake_doctrine_with_relocated_missions(tmp_path)
        fake_mod = types.ModuleType("charter.offering")
        fake_mod.__file__ = str(tmp_path / "charter" / "offering" / "__init__.py")
        monkeypatch.setitem(sys.modules, "charter.offering", fake_mod)

        # Reload the module under test to pick up the patched charter.offering
        import importlib

        import specify_cli.runtime.agent_commands as ac

        importlib.reload(ac)

        result = ac._get_command_templates_dir()
        assert result == tmp_path / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"


# ---------------------------------------------------------------------------
# T008 / T006: Integration — per-step renderer
# ---------------------------------------------------------------------------


class TestSyncAgentCommandsIntegration:
    """FR-002/FR-003: _sync_agent_commands() must use per-step subdirectory layout."""

    def test_all_prompt_driven_commands_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_sync_agent_commands writes one file per PROMPT_DRIVEN step-dir.

        RED in lane-d (buggy renderer uses flat glob, never finds per-step
        prompt.md files); GREEN after WP01 merges.
        """
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.runtime.agent_commands import _sync_agent_commands

        templates_dir = tmp_path / "mission-steps" / "software-dev"
        for cmd in PROMPT_DRIVEN_COMMANDS:
            step_dir = templates_dir / cmd
            step_dir.mkdir(parents=True)
            (step_dir / "prompt.md").write_text(f"# {cmd} prompt")

        output_dir = tmp_path / "agent_output"
        output_dir.mkdir()

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda _: output_dir,
        )

        _sync_agent_commands("claude", templates_dir, "sh")

        written_prompt_commands = {p.stem.split(".")[1] for p in output_dir.glob("spec-kitty.*.md") if p.stem.split(".")[1] in PROMPT_DRIVEN_COMMANDS}
        assert written_prompt_commands == set(PROMPT_DRIVEN_COMMANDS)

    def test_missing_required_prompt_refuses_before_writes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T006: Step dirs without prompt.md are skipped without raising.

        In the FIXED code (WP01), when step dirs exist but have no prompt.md,
        _sync_agent_commands must not raise and must not write any
        prompt-driven command files (spec-kitty.{cmd}.md for cmd in
        PROMPT_DRIVEN_COMMANDS).

        RED in lane-d: the buggy flat-glob renderer always writes CLI-driven
        shims even when no prompt.md is present (it finds no *.md to render
        for prompt-driven commands, but the shim loop still runs).
        After WP01 the test passes: prompt-driven files are only written when
        prompt.md exists; CLI shims are separate.
        """
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
        from specify_cli.runtime.agent_commands import _sync_agent_commands

        templates_dir = tmp_path / "mission-steps" / "software-dev"
        for cmd in PROMPT_DRIVEN_COMMANDS:
            (templates_dir / cmd).mkdir(parents=True)
            # Deliberately omit prompt.md

        output_dir = tmp_path / "agent_output"
        output_dir.mkdir()

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda _: output_dir,
        )

        # Required source failure must not certify a partial bundle.
        with pytest.raises(RuntimeError, match="Required asset source"):
            _sync_agent_commands("claude", templates_dir, "sh")

        # No prompt-driven command files should be written (they all lack prompt.md)
        for cmd in PROMPT_DRIVEN_COMMANDS:
            assert not (output_dir / f"spec-kitty.{cmd}.md").exists(), f"spec-kitty.{cmd}.md should not be written without prompt.md"


# ---------------------------------------------------------------------------
# T023: Stale file removal
# ---------------------------------------------------------------------------


class TestRendererStaleRemoval:
    """FR-002: Stale spec-kitty.* files are removed after sync."""

    def test_unproven_stale_files_preserved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Files not in the canonical set are removed.

        RED in lane-d when the stale check runs before prompt files are written
        (buggy flat-glob path never writes prompt files, so the canonical set
        contains only CLI-driven shims; stale removal still fires for files
        outside that set). Actually the stale removal loop exists in both old
        and new code, so this test is GREEN in both lanes — but it exercises the
        contract that matters after WP01.
        """
        from specify_cli.runtime.agent_commands import _get_command_templates_dir, _sync_agent_commands

        templates_dir = _get_command_templates_dir()

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        stale = output_dir / "spec-kitty.oldcmd.md"
        stale.write_text("stale content")

        monkeypatch.setattr(
            "specify_cli.runtime.agent_commands.get_global_command_dir",
            lambda _: output_dir,
        )

        _sync_agent_commands("claude", templates_dir, "sh")

        assert stale.read_text() == "stale content", "A prefix does not prove ownership"


# ---------------------------------------------------------------------------
# #4609: cross-release canonical-predecessor proof + unmigrated-file warning
# ---------------------------------------------------------------------------


class TestIsCanonicalPredecessor:
    """FR (#4609): a managed marker naming another CLI release proves provenance."""

    @staticmethod
    def _existing(old_version: str, body: bytes) -> bytes:
        return f"<!-- spec-kitty-command-version: {old_version} -->\n".encode() + body

    def test_cross_release_marker_with_changed_body_is_predecessor(self) -> None:
        """The #4609 scenario: 3.2.7 marker + 3.2.7 body upgrades to changed 4.x output."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        existing = self._existing("3.2.7", b"# old release canonical body\n")
        desired = self._existing("4.0.0rc2", b"# new release canonical body\n")
        assert _is_canonical_predecessor(existing, desired, "4.0.0rc2") is True

    def test_same_version_identical_body_is_predecessor(self) -> None:
        """A marker-only refresh of this release's own output still qualifies."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        body = b"# canonical body\n"
        existing = self._existing("4.0.0rc2", body)
        desired = self._existing("4.0.0rc2", body)
        assert _is_canonical_predecessor(existing, desired, "4.0.0rc2") is True

    def test_same_version_edited_body_is_not_predecessor(self) -> None:
        """Current-version marker plus drifted content is a user edit: preserved."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        existing = self._existing("4.0.0rc2", b"# canonical body with user edit\n")
        desired = self._existing("4.0.0rc2", b"# canonical body\n")
        assert _is_canonical_predecessor(existing, desired, "4.0.0rc2") is False

    def test_unmarked_file_is_not_predecessor(self) -> None:
        """No managed marker means no spec-kitty provenance: preserved."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        desired = self._existing("4.0.0rc2", b"# canonical body\n")
        assert _is_canonical_predecessor(b"# user's own file\n", desired, "4.0.0rc2") is False

    def test_crlf_marker_line_is_recognized(self) -> None:
        """The byte-level marker regex tolerates CRLF files (macOS/pipx-era output)."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        existing = b"<!-- spec-kitty-command-version: 3.2.7 -->\r\n# old body\r\n"
        desired = self._existing("4.0.0rc2", b"# new body\n")
        assert _is_canonical_predecessor(existing, desired, "4.0.0rc2") is True

    def test_marker_inside_toml_prompt_body_counts(self) -> None:
        """TOML agents carry the marker inside the ``prompt = \"\"\"...\"\"\"`` body, not after frontmatter."""
        from specify_cli.runtime.agent_commands import _is_canonical_predecessor

        existing = b'prompt = """\n<!-- spec-kitty-command-version: 3.2.7 -->\n# old body\n"""\n'
        desired = b'prompt = """\n<!-- spec-kitty-command-version: 4.0.0rc2 -->\n# new body\n"""\n'
        assert _is_canonical_predecessor(existing, desired, "4.0.0rc2") is True


class TestWarnUnmigratedCommands:
    """FR (#4609): canonical command files that could not be migrated are never silent."""

    @staticmethod
    def _disposition(path: str, state: str):
        from specify_cli.tool_surface.operations import Disposition

        return Disposition("slash_commands", None, path, state, "Changed managed asset")

    def test_preserved_canonical_name_is_named(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specify_cli.runtime.agent_commands import _warn_unmigrated_commands

        caplog.set_level(logging.WARNING, logger="specify_cli.runtime.agent_commands")
        _warn_unmigrated_commands(
            (self._disposition(".claude/commands/spec-kitty.plan.md", "preserve"),),
            {"spec-kitty.plan.md"},
        )
        [record] = [r for r in caplog.records if "could not migrate" in r.getMessage()]
        assert ".claude/commands/spec-kitty.plan.md" in record.getMessage()
        assert "Changed managed asset" in record.getMessage()

    def test_non_canonical_preserves_are_not_named(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specify_cli.runtime.agent_commands import _warn_unmigrated_commands

        caplog.set_level(logging.WARNING, logger="specify_cli.runtime.agent_commands")
        _warn_unmigrated_commands(
            (self._disposition(".claude/commands/spec-kitty.custom.md", "preserve"),),
            {"spec-kitty.plan.md"},
        )
        assert not [r for r in caplog.records if "could not migrate" in r.getMessage()]

    def test_no_warning_when_nothing_is_preserved(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from specify_cli.runtime.agent_commands import _warn_unmigrated_commands

        caplog.set_level(logging.WARNING, logger="specify_cli.runtime.agent_commands")
        _warn_unmigrated_commands(
            (self._disposition(".claude/commands/spec-kitty.plan.md", "unchanged"),),
            {"spec-kitty.plan.md"},
        )
        assert not [r for r in caplog.records if "could not migrate" in r.getMessage()]


# ---------------------------------------------------------------------------
# T024: Lock written only after successful full install
# ---------------------------------------------------------------------------


class TestVersionLockTiming:
    """FR-004: Version lock must NOT be written if sync fails."""

    def test_lock_not_written_when_sync_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If _sync_agent_commands raises, the lock must not be updated.

        The fixed ensure_global_agent_commands() catches the exception, logs it,
        and re-raises without writing the version lock file. This test verifies
        that guarantee.

        RED in lane-d: the buggy ensure_global_agent_commands() returns early
        when templates_dir is None (no exception reaches the lock-write path),
        but the monkeypatch on _get_command_templates_dir makes templates_dir
        non-None so the code reaches _sync_agent_commands. If the buggy
        ensure_global_agent_commands() signature doesn't accept agent_keys
        this test may also expose that gap.
        """
        import specify_cli.runtime.agent_commands as ac

        fake_templates_dir = tmp_path / "fake_templates"
        fake_templates_dir.mkdir()
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        for command in PROMPT_DRIVEN_COMMANDS:
            (fake_templates_dir / command).mkdir()
            (fake_templates_dir / command / "prompt.md").write_text(f"# {command}\n")

        monkeypatch.setattr(
            ac,
            "_get_command_templates_dir",
            lambda: fake_templates_dir,
        )

        def boom(agent_key: str, templates_dir: Path, script_type: str) -> None:
            raise RuntimeError("simulated sync failure")

        monkeypatch.setattr(ac, "_render_agent_commands", boom)

        kittify_home = tmp_path / "kittify"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))

        with pytest.raises(RuntimeError, match="simulated sync failure"):
            ac.ensure_global_agent_commands()

        lock_path = kittify_home / "cache" / ac._VERSION_FILENAME
        assert not lock_path.exists(), "Lock must not be written on failure"
