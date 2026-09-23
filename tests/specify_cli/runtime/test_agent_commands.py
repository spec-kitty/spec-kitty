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

import json
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


# ---------------------------------------------------------------------------
# WP04 T012/T013/T015: Lever C primary -- freshness pre-check on
# assess_global_agent_commands()/ensure_global_agent_commands() (Ruling 6,
# reviews/plan.ruling.md). Every test in this class was proven RED first
# against a deliberately naive/broken stub of the pre-check (one that
# short-circuits without checking the field the test targets) before this
# WP's real four-condition implementation existed -- see the WP04 report for
# the recorded red pytest output. These tests exercise the REAL
# implementation only; the naive stub was never committed.
# ---------------------------------------------------------------------------


class TestFreshnessPrecheck:
    """FR-003/Ruling 6: a missed refresh must never be silent.

    Every staleness test below follows the same shape: bootstrap a fully
    rendered, stamped, healthy state via one real ``assess_global_agent_commands()``
    + ``_apply_command_assessment()`` cycle, perturb exactly ONE of the
    conditions the freshness stamp's contract names, then assert the very
    next ``assess_global_agent_commands()`` call renders again (never
    silently skips). Uses real, isolated ``HOME``/``SPEC_KITTY_HOME`` dirs
    (never the operator's real home) per the existing pattern in this file
    and in ``test_agent_commands_routing.py``.
    """

    @staticmethod
    def _write_prompt_templates(templates_dir: Path) -> None:
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        for cmd in PROMPT_DRIVEN_COMMANDS:
            step_dir = templates_dir / cmd
            step_dir.mkdir(parents=True)
            (step_dir / "prompt.md").write_text(f"---\ndescription: {cmd}\n---\n# {cmd}\n", encoding="utf-8")

    @classmethod
    def _isolated_project(cls, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
        """Return (home, kittify_home, templates_dir) with isolated env vars.

        Mirrors ``test_agent_commands_routing.py``'s isolation pattern: real
        ``HOME``/``SPEC_KITTY_HOME`` env vars pointed at ``tmp_path``
        subdirectories, never the operator's actual home directory.
        """
        home = tmp_path / "home"
        kittify_home = tmp_path / "kittify"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))
        monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
        templates_dir = tmp_path / "templates"
        cls._write_prompt_templates(templates_dir)
        return home, kittify_home, templates_dir

    @staticmethod
    def _bootstrap_fresh_state(ac: types.ModuleType, templates_dir: Path) -> None:
        """One full assess+apply cycle: renders everything and writes the stamp."""
        first = ac.assess_global_agent_commands(templates_dir=templates_dir)
        assert first.complete
        ac._apply_command_assessment(first, rebuild=lambda: ac.assess_global_agent_commands(templates_dir=templates_dir))

    @staticmethod
    def _count_renders(ac: types.ModuleType, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
        """Wrap ``_render_agent_commands`` with a call counter."""
        calls = {"n": 0}
        original = ac._render_agent_commands

        def _counting(*args: object, **kwargs: object) -> object:
            calls["n"] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(ac, "_render_agent_commands", _counting)
        return calls

    # -- (a) Template-change staleness (Ruling 6, mandatory) ----------------

    def test_template_content_change_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """(a) Mutating a template's source content, with cli_version and
        agent_keys unchanged, must be detected and force a re-render -- never
        a silent skip."""
        import specify_cli.runtime.agent_commands as ac

        _home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        changed_command = sorted(PROMPT_DRIVEN_COMMANDS)[0]
        (templates_dir / changed_command / "prompt.md").write_text(
            f"---\ndescription: {changed_command}\n---\n# {changed_command} CHANGED\n",
            encoding="utf-8",
        )

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "a changed command template must force a re-render, never a silent skip"
        assert assessment.complete

    # -- (b) Version-change staleness (Ruling 6, mandatory) ------------------

    def test_cli_version_change_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """(b) A spec-kitty version change, with no template content change,
        must be detected and force a re-render -- never a silent skip."""
        import specify_cli.runtime.agent_commands as ac

        _home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        monkeypatch.setattr(ac, "_get_cli_version", lambda: "99.0.0-wp04-staleness-test")

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "a spec-kitty version change must force a re-render, never a silent skip"
        assert assessment.complete

    def test_cli_version_change_forces_rerender_isolated_from_destination_health(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """(b, isolated) WP04-C1-001 (review cycle 1, sev4/Ruling-6 violation):
        the ORIGINAL (b) test above is masked by ``_all_global_agent_commands_healthy()``
        independently re-verifying the CLI-version marker embedded in each
        rendered destination file -- the bootstrapped files still carry the OLD
        marker after ``_get_cli_version`` is monkeypatched, so destination-health
        (condition 4) forces the fall-through for an unrelated reason even if
        ``_freshness_stamp_matches`` stopped comparing ``cli_version`` at all
        (mutation M2: proven RED against that exact mutation, see the WP04
        report). This test patches ``_all_global_agent_commands_healthy`` to
        unconditionally report healthy, so ONLY the stamp's own cli_version
        comparison can be the thing forcing the re-render -- isolating
        ``_freshness_stamp_matches``'s cli_version condition from the
        destination-health safety net Ruling 6's binding condition also names
        as its OWN, separate, fourth disposition."""
        import specify_cli.runtime.agent_commands as ac

        _home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        monkeypatch.setattr(ac, "_get_cli_version", lambda: "99.0.0-wp04-c1-001-isolated-test")
        monkeypatch.setattr(ac, "_all_global_agent_commands_healthy", lambda *args, **kwargs: True)

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, (
            "a cli_version stamp mismatch must force a re-render on its own, even when "
            "destination health unconditionally reports healthy -- the stamp comparison "
            "itself must check cli_version, independent of the marker-based safety net"
        )
        assert assessment.complete

    # -- (c) Destination-health staleness (Ruling 6, mandatory) --------------

    def test_destination_file_altered_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """(c1) A rendered destination file hand-edited on disk, with a stamp
        that still matches on all three source-side fields, must be detected
        (via ``_all_global_agent_commands_healthy()``, the stamp contract's
        fourth condition) and force a re-render -- this is PLAN-ARCH-001's
        named failure mode: a stamp-only short-circuit that ignores
        destination drift."""
        import specify_cli.runtime.agent_commands as ac

        home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        claude_commands = home / ".claude" / "commands"
        target = next(claude_commands.glob("spec-kitty.*.md"))
        target.chmod(0o644)
        target.write_text("hand-edited outside spec-kitty, no version marker", encoding="utf-8")

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "an altered rendered destination file must force a re-render, never a silent skip"
        assert assessment.complete

    def test_destination_file_missing_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """(c2) A rendered destination file deleted from disk, with a stamp
        that still matches on all three source-side fields, must be detected
        and force a re-render that repairs it (the documented
        ``ensure_global_agent_commands()`` self-heal contract)."""
        import specify_cli.runtime.agent_commands as ac

        home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        claude_commands = home / ".claude" / "commands"
        target = next(claude_commands.glob("spec-kitty.*.md"))
        target.chmod(0o644)
        target.unlink()

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "a missing rendered destination file must force a re-render, never a silent skip"
        ac._apply_command_assessment(assessment, rebuild=lambda: ac.assess_global_agent_commands(templates_dir=templates_dir))
        assert target.exists(), "ensure_global_agent_commands() must self-heal a deleted command file"

    # -- T015: agent_keys staleness (plan.md Diff-cover, not itself Ruling 6) --

    def test_agent_keys_mismatch_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T015: ``agent_keys`` is the THIRD source-side stamp field
        (alongside ``cli_version`` and ``template_source_signature``) and
        must have its own dedicated, non-vacuous coverage -- Ruling 6's (a)
        and (b) tests only exercise the first two fields. Directly rewrites
        the on-disk stamp's ``agent_keys`` list (dropping one real key)
        while leaving ``cli_version``/``template_source_signature`` matching,
        proving the comparison genuinely inspects all three fields
        independently rather than e.g. only checking two of them."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        stamp_path = kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME
        payload = json.loads(stamp_path.read_text(encoding="utf-8"))
        assert "claude" in payload["agent_keys"], "fixture assumption: claude is a real configured agent key"
        payload["agent_keys"] = [key for key in payload["agent_keys"] if key != "claude"]
        stamp_path.write_text(json.dumps(payload), encoding="utf-8")

        calls = self._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "an agent_keys mismatch (stamp vs current resolved key set) must force a re-render, never a silent skip"
        assert assessment.complete

    # -- T015: Match disposition (all four conditions exercised as distinct tests) --

    def test_match_short_circuits_without_render_or_asset_preparation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Match: a genuinely fresh, matching stamp with a healthy destination
        short-circuits with ZERO renders and ZERO ``AssetPreparation``
        construction -- the SK-243 immunity property (data-model.md): this
        path never enters ``check_assets()``'s drift-recheck machinery
        because it never constructs the object that machinery operates on."""
        import specify_cli.runtime.agent_commands as ac
        from specify_cli.runtime.asset_preparation import AssetPreparation

        _home, _kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        self._bootstrap_fresh_state(ac, templates_dir)

        constructions = {"n": 0}
        original_init = AssetPreparation.__init__

        def _counting_init(self: AssetPreparation, *args: object, **kwargs: object) -> None:
            constructions["n"] += 1
            original_init(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(AssetPreparation, "__init__", _counting_init)
        calls = self._count_renders(ac, monkeypatch)

        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] == 0, "a fresh, healthy stamp must skip the render entirely"
        assert constructions["n"] == 0, "a fresh, healthy stamp must never construct AssetPreparation (SK-243 immunity)"
        assert assessment.effects == ()
        assert assessment.complete

    # -- T013 step 3: Unreadable/malformed disposition (required, not optional) --

    def test_malformed_stamp_degrades_to_render_without_raising(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unreadable/malformed: a corrupt stamp file (e.g. a torn write, or
        -- since every existing installation's ``_VERSION_FILENAME`` starts
        life as a plain version string -- legacy-shaped content) must
        degrade gracefully to the render-then-diff path and be overwritten
        with a correctly-shaped stamp afterward, WITHOUT raising. The narrow
        read-only catch this proves must not widen into swallowing genuine
        render/write errors elsewhere."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        cache_dir = kittify_home / "cache"
        cache_dir.mkdir(parents=True)
        stamp_path = cache_dir / ac._FRESHNESS_STAMP_FILENAME
        stamp_path.write_text("not json at all {{{", encoding="utf-8")

        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)
        assert assessment.complete, "a malformed stamp must degrade to the render path, never raise"

        ac._apply_command_assessment(assessment, rebuild=lambda: ac.assess_global_agent_commands(templates_dir=templates_dir))

        restamped = json.loads(stamp_path.read_text(encoding="utf-8"))
        assert set(restamped) == {"cli_version", "template_source_signature", "agent_keys"}

    def test_legacy_plain_version_stamp_degrades_to_render_without_raising(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unreadable/malformed, the specific legacy-shape variant: a stamp
        file containing plain version-string bytes (the exact shape
        ``_VERSION_FILENAME`` writes today) is invalid JSON and must degrade
        identically to absent, never raise."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = self._isolated_project(tmp_path, monkeypatch)
        cache_dir = kittify_home / "cache"
        cache_dir.mkdir(parents=True)
        stamp_path = cache_dir / ac._FRESHNESS_STAMP_FILENAME
        stamp_path.write_text("4.0.0rc5", encoding="utf-8")

        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)
        assert assessment.complete, "legacy plain-version-string stamp content must degrade to the render path, never raise"


# ---------------------------------------------------------------------------
# WP04-C1-002 (review cycle 1, sev3): diff-cover was 89.6% at cf3dcca54,
# missing the ``_read_freshness_stamp`` malformed-payload branches and the
# two ``except OSError: return None`` fallback branches in
# ``_freshness_short_circuit``. Each test below exercises exactly one of
# those uncovered branches and asserts it degrades to the render path.
# ---------------------------------------------------------------------------


class TestReadFreshnessStampMalformedPayload:
    """WP04-C1-002: ``_read_freshness_stamp``'s malformed-payload branches.

    Each variant is valid JSON (so it clears the ``json.loads`` ``except
    ValueError`` branch already covered elsewhere) but fails one of the
    shape checks that follow, and must read back as ``None`` (absent) --
    never raise.
    """

    @staticmethod
    def _stamp_path(kittify_home: Path, ac_module: types.ModuleType) -> Path:
        cache_dir = kittify_home / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / ac_module._FRESHNESS_STAMP_FILENAME

    def test_payload_not_a_dict_reads_as_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A JSON array (or any non-object top level) is not a dict."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        stamp_path = self._stamp_path(kittify_home, ac)
        stamp_path.write_text("[]", encoding="utf-8")

        result = ac._read_freshness_stamp(stamp_path)
        assert result is None, "a non-dict JSON payload must read as absent, never raise"

        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)
        assert assessment.complete, "a non-dict stamp payload must degrade to the render path, never raise"

    def test_non_string_cli_version_reads_as_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``cli_version`` present but not a string fails the isinstance check."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        stamp_path = self._stamp_path(kittify_home, ac)
        stamp_path.write_text(
            json.dumps({"cli_version": 123, "template_source_signature": "abc", "agent_keys": ["claude"]}),
            encoding="utf-8",
        )

        result = ac._read_freshness_stamp(stamp_path)
        assert result is None, "a non-string cli_version must read as absent, never raise"

    def test_non_string_template_source_signature_reads_as_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``template_source_signature`` present but not a string fails the isinstance check."""
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        stamp_path = self._stamp_path(kittify_home, ac)
        stamp_path.write_text(
            json.dumps({"cli_version": "4.0.0rc5", "template_source_signature": None, "agent_keys": ["claude"]}),
            encoding="utf-8",
        )

        result = ac._read_freshness_stamp(stamp_path)
        assert result is None, "a non-string template_source_signature must read as absent, never raise"

    def test_agent_keys_not_a_list_of_strings_reads_as_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``agent_keys`` present but not a list of strings fails the isinstance check.

        Covers both sub-shapes: not a list at all, and a list containing a
        non-string element.
        """
        import specify_cli.runtime.agent_commands as ac

        _home, kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        stamp_path = self._stamp_path(kittify_home, ac)

        stamp_path.write_text(
            json.dumps({"cli_version": "4.0.0rc5", "template_source_signature": "abc", "agent_keys": "claude"}),
            encoding="utf-8",
        )
        assert ac._read_freshness_stamp(stamp_path) is None, "a non-list agent_keys must read as absent, never raise"

        stamp_path.write_text(
            json.dumps({"cli_version": "4.0.0rc5", "template_source_signature": "abc", "agent_keys": ["claude", 7]}),
            encoding="utf-8",
        )
        assert ac._read_freshness_stamp(stamp_path) is None, "a list agent_keys with a non-string element must read as absent, never raise"


class TestFreshnessShortCircuitOSErrorFallthrough:
    """WP04-C1-002: the two narrowly-scoped ``except OSError: return None``
    branches inside ``_freshness_short_circuit`` -- an unreadable
    command-templates source tree during signature computation, and an
    unreadable destination during the health check. Both must fall through
    to the render path, never raise and never silently claim freshness."""

    def test_template_source_signature_oserror_falls_through_to_render(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An unreadable command-templates source tree during the
        short-circuit's OWN signature read (real filesystem permission
        errors during ``Path.rglob`` traversal are silently swallowed by
        pathlib itself on this platform -- verified directly, see the WP04
        report -- so this raises the same ``OSError`` a genuinely unreadable
        tree's read step would, at the exact call site
        ``_freshness_short_circuit`` wraps, only on the first call) must
        fall through to the render path rather than raising or silently
        short-circuiting as fresh. The render path's OWN later signature
        computation (needed for the post-render stamp write) is a SEPARATE,
        real call that succeeds normally, matching the transient/one-shot
        nature of a genuine race (e.g. a concurrent peer's rewrite) rather
        than a permanently corrupted install."""
        import specify_cli.runtime.agent_commands as ac

        _home, _kittify_home, templates_dir = self._isolated_project_for_this_class(tmp_path, monkeypatch, ac)

        original_signature = ac._template_source_signature
        calls = {"n": 0}

        def _flaky_signature(dir_arg: Path) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("simulated unreadable command-templates source tree")
            return original_signature(dir_arg)

        monkeypatch.setattr(ac, "_template_source_signature", _flaky_signature)

        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)
        assert calls["n"] >= 1, "the short-circuit's own signature read must have been attempted"
        assert assessment.complete, "an unreadable template-source tree must degrade to the render path, never raise"

    def test_destination_health_check_oserror_falls_through_to_render(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A genuinely unreadable destination command directory (real chmod,
        not a mock: ``Path.iterdir()`` raises ``PermissionError`` -- an
        ``OSError`` subclass -- immediately, unlike ``rglob``) during the
        health check must fall through to attempting a render, never raise
        and never silently claim freshness. The directory stays genuinely
        unreadable for the whole call, so the render for THAT ONE agent
        (``claude``) can legitimately fail too, same as it would in real
        life -- what this test proves is that the short-circuit itself never
        raises and never returns a spurious "fresh" result; it does not
        require the overall (still genuinely broken) render to complete."""
        import specify_cli.runtime.agent_commands as ac

        home, _kittify_home, templates_dir = self._isolated_project_for_this_class(tmp_path, monkeypatch, ac)
        TestFreshnessPrecheck._bootstrap_fresh_state(ac, templates_dir)

        claude_commands = home / ".claude" / "commands"
        claude_commands.chmod(0o000)
        try:
            calls = TestFreshnessPrecheck._count_renders(ac, monkeypatch)
            assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)
        finally:
            claude_commands.chmod(0o755)

        assert calls["n"] > 0, (
            "an unreadable destination directory during the health check must force a render "
            "attempt for at least the agents processed before it, never a silent fresh skip"
        )
        assert assessment.owner_key == "slash_commands"

    @staticmethod
    def _isolated_project_for_this_class(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _ac: types.ModuleType) -> tuple[Path, Path, Path]:
        return TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)


# ---------------------------------------------------------------------------
# WP04-C1-003 (review cycle 1, sev3): the freshness stamp must apply
# strictly AFTER every other effect in the same render-and-apply batch, so a
# partial/failed cycle never leaves a stale stamp claiming freshness.
# ---------------------------------------------------------------------------


class TestFreshnessStampAppliesLast:
    """WP04-C1-003: red-first proof that the stamp write is ordered last.

    Red-first history (see the WP04 report for the recorded pytest output):
    with ``_FRESHNESS_STAMP_FILENAME`` temporarily reverted to the pre-fix
    ``"agent-commands-freshness.json"`` name, this test FAILS -- the ``.json``
    name sorts into ``asset_preparation._write_order``'s default stage 3
    (the same stage as rendered command files) at a shallower path depth
    than every one of them, so it applies to disk BEFORE the command file
    this test forces to fail, not after. Restoring the ``.lock`` suffix
    (its real, committed value) makes the stamp sort into stage 6 -- dead
    last, after every other effect including the inventory -- and this test
    passes.
    """

    def test_stamp_absent_when_a_command_write_fails_partway(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.runtime.agent_commands as ac
        from specify_cli.runtime import asset_preparation as ap

        _home, kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        monkeypatch.setattr(ac, "_get_command_templates_dir", lambda: templates_dir)

        original_write_asset = ap._write_asset

        def _flaky_write_asset(write: object) -> None:
            destination_name = write.effect.destination.name  # type: ignore[attr-defined]
            if destination_name == "spec-kitty.plan.md":
                raise OSError("simulated disk failure mid-apply")
            original_write_asset(write)  # type: ignore[arg-type]

        monkeypatch.setattr(ap, "_write_asset", _flaky_write_asset)

        with pytest.raises(RuntimeError):
            ac.ensure_global_agent_commands()

        stamp_path = kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME
        assert not stamp_path.exists(), "a partial/failed render-and-apply cycle must never leave a freshness stamp behind"


# ---------------------------------------------------------------------------
# WP04-C1-004 (review cycle 1, sev2, advisory): the freshness stamp's
# signature must also cover the rendering pipeline's own code, not only the
# command-templates source tree, so an editable-install code change within
# the same CLI version does not go silently undetected.
# ---------------------------------------------------------------------------


class TestRenderingPipelineSignatureFoldedIn:
    """WP04-C1-004: a rendering-code change (same templates, same cli_version,
    same agent_keys) must still force a re-render -- proving
    ``_template_source_signature`` folds in ``_rendering_pipeline_signature()``
    rather than depending only on template-tree content."""

    def test_rendering_pipeline_signature_change_forces_rerender(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.runtime.agent_commands as ac

        _home, _kittify_home, templates_dir = TestFreshnessPrecheck._isolated_project(tmp_path, monkeypatch)
        TestFreshnessPrecheck._bootstrap_fresh_state(ac, templates_dir)

        # Simulate an editable-install rendering-code change: same template
        # tree, same cli_version, same agent_keys, but the rendering pipeline
        # code hash now differs.
        monkeypatch.setattr(ac, "_rendering_pipeline_signature", lambda: b"simulated-rendering-code-change")

        calls = TestFreshnessPrecheck._count_renders(ac, monkeypatch)
        assessment = ac.assess_global_agent_commands(templates_dir=templates_dir)

        assert calls["n"] > 0, "a rendering-pipeline code change must force a re-render even when the template tree, cli_version, and agent_keys are all unchanged"
        assert assessment.complete

    def test_rendering_pipeline_signature_hashes_this_module_and_renderers(self) -> None:
        """Direct unit check: the signature is a real hash over readable module
        source files, not a constant/no-op, and covers at least this module
        plus the two renderer modules it calls."""
        import specify_cli.runtime.agent_commands as ac

        first = ac._rendering_pipeline_signature()
        second = ac._rendering_pipeline_signature()
        assert first == second, "the signature must be deterministic for unchanged source"
        assert isinstance(first, bytes)
        assert len(first) == 32, "sha256 digest must be 32 bytes"
