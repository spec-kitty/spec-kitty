"""Regression test for issue #2691: ``agent config sync`` deletes tracked fixtures
and rewrites repository-pinned manifests.

Issue #2691 documents two distinct losses through two different call sites:

1. **Removal half** -- ``sync``'s default-on orphan sweep
   (``_remove_orphaned_agent_dirs``) called the same unguarded
   ``_remove_project_agent_surface`` helper as ``remove`` (#4907), so a bare
   ``spec-kitty agent config sync`` could silently rmtree a tracked/user
   command-agent directory. Fixed by the same guard routing as #4907.

2. **Manifest half** -- even the "safe-looking" ``sync --create-missing
   --keep-orphaned`` invocation unconditionally re-ran
   ``command_installer.install()`` for every configured skill-only agent
   (codex/vibe/pi/letta), regardless of whether that agent was already fully
   installed. Because ``install()`` renders fresh command-skill content and
   writes whatever the *executing host CLI's own* release/hashes are, a
   different host CLI running a routine sync could replace
   ``.kittify/command-skills-manifest.json``'s repository-pinned
   ``spec_kitty_version``/``content_hash`` values -- a compatibility-contract
   mutation the operator never asked for. The fix: ``sync`` only installs a
   skill-only agent that owns *zero* manifest entries yet (genuinely
   "missing"); an already-installed agent is left untouched, so a normal sync
   can never again act as an implicit manifest refresh.

RED on base (main@d57619a900): the removal-half tests fail exactly as in
#4907 (file deleted, "Removed" reported); the manifest-half test fails
because a second, already-installed ``install()`` call is issued and
(depending on package version drift) can mutate pinned metadata -- pinned
here by directly editing the manifest, which is byte-identical only if
``sync`` never re-touches it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.config import app
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.skills import command_installer, manifest_store

pytestmark = [pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _init_project(tmp_path: Path, agents: list[str]) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(tmp_path, AgentConfig(available=agents))
    return tmp_path


def _invoke(tmp_path: Path, args: list[str]) -> Result:
    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        return runner.invoke(app, args)


class TestIssue2691SyncRemovalPreservesUserContent:
    """#2691 removal half: bare ``sync`` must not delete an unproven orphan dir."""

    def test_sync_preserves_untracked_user_command_file(self, tmp_path: Path) -> None:
        """Arrange: claude present on disk but NOT configured (orphaned), with a
        user-authored file and no manifest entry; Act: bare ``agent config sync``
        (remove_orphaned defaults True); Assert: file survives, exit 0, output
        says "Preserved" (never "Removed")."""
        _init_project(tmp_path, [])
        user_file = tmp_path / ".claude" / "commands" / "my-deploy.md"
        user_file.parent.mkdir(parents=True)
        original = "# my custom deploy command\n"
        user_file.write_text(original, encoding="utf-8")

        result = _invoke(tmp_path, ["sync"])

        assert result.exit_code == 0, result.output
        assert "Removed orphaned" not in result.output
        assert "Preserved" in result.output
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == original

    def test_sync_preserves_non_claude_orphan_dir(self, tmp_path: Path) -> None:
        """AGENT_DIRS generality (T008): copilot's ``.github/prompts/`` orphan gets
        the same table-driven preserve treatment as claude."""
        _init_project(tmp_path, [])
        user_file = tmp_path / ".github" / "prompts" / "spec-kitty.custom.prompt.md"
        user_file.parent.mkdir(parents=True)
        original = "# a hand-written copilot prompt\n"
        user_file.write_text(original, encoding="utf-8")

        result = _invoke(tmp_path, ["sync"])

        assert result.exit_code == 0, result.output
        assert "Removed orphaned" not in result.output
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == original


class TestIssue2691ManifestPinsAreNeverRewritten:
    """#2691 manifest half: a normal sync leaves pinned manifest values byte-identical."""

    def _installed_project(self, tmp_path: Path) -> Path:
        _init_project(tmp_path, ["codex"])
        command_installer.install(tmp_path, "codex")
        return tmp_path

    def test_bare_sync_leaves_manifest_byte_identical(self, tmp_path: Path) -> None:
        project = self._installed_project(tmp_path)
        manifest_path = project / ".kittify" / "command-skills-manifest.json"
        before = manifest_path.read_bytes()

        result = _invoke(project, ["sync"])

        assert result.exit_code == 0, result.output
        assert manifest_path.read_bytes() == before

    def test_safe_looking_create_missing_keep_orphaned_leaves_manifest_byte_identical(self, tmp_path: Path) -> None:
        """The exact reproduction from the GitHub issue: the "safe-looking"
        ``--create-missing --keep-orphaned`` form must not touch an
        already-installed agent's pinned manifest entries."""
        project = self._installed_project(tmp_path)
        manifest_path = project / ".kittify" / "command-skills-manifest.json"

        # Simulate a repository-pinned manifest recorded by a DIFFERENT host CLI
        # release than the one running this test: only the metadata pins
        # (version/timestamp) are rewritten -- content_hash still matches the
        # bytes actually on disk, which is exactly the "byte-identical content,
        # different host CLI" scenario #2691 describes.
        from dataclasses import replace

        manifest = manifest_store.load(project)
        pinned_entries = [replace(entry, spec_kitty_version="3.9.0-pinned", installed_at="2020-01-01T00:00:00+00:00") for entry in manifest.entries]
        manifest_store.save(project, manifest_store.SkillsManifest(entries=pinned_entries))
        pinned_bytes = manifest_path.read_bytes()

        result = _invoke(project, ["sync", "--create-missing", "--keep-orphaned", "--json"])

        assert result.exit_code == 0, result.output
        assert manifest_path.read_bytes() == pinned_bytes
        assert '"tracked_mutations": []' in result.output

    def test_json_output_enumerates_zero_mutations_on_non_refreshing_sync(self, tmp_path: Path) -> None:
        project = self._installed_project(tmp_path)

        result = _invoke(project, ["sync", "--create-missing", "--json"])

        assert result.exit_code == 0, result.output
        assert '"tracked_mutations": []' in result.output


class TestIssue2691CreateMissingStillInstallsGenuinelyMissingAgent:
    """Owned-delete-style anchor for the manifest half: a genuinely un-installed
    skill agent IS installed by ``--create-missing`` -- a fix that makes sync a
    no-op for every skill agent (not just already-installed ones) cannot pass."""

    def test_create_missing_installs_a_never_installed_configured_agent(self, tmp_path: Path) -> None:
        project = _init_project(tmp_path, ["codex"])
        manifest_path = project / ".kittify" / "command-skills-manifest.json"
        assert not manifest_path.exists()

        result = _invoke(project, ["sync", "--create-missing"])

        assert result.exit_code == 0, result.output
        manifest = manifest_store.load(project)
        assert len(manifest.entries) == len(command_installer.CANONICAL_COMMANDS)
        for entry in manifest.entries:
            assert entry.agents == ("codex",)
