"""Regression test for issue #4907: ``agent config remove`` deletes user content.

Pre-fix, ``_remove_project_agent_surface`` (``cli/commands/agent/config.py``)
unconditionally ``shutil.rmtree``'d (or ``unlink``'d) a configured agent's managed
command surface -- e.g. ``.claude/commands/`` -- with no ownership check at all.
Because that directory is gitignored by default, any user-authored file living
there (a hand-written custom command, a locally-tweaked copy) was permanently,
unrecoverably destroyed by a routine ``agent config remove claude``.

The fix routes the removal through the single ``guard_destructive_removal``
prove-or-preserve chokepoint (``asset_preservation/guard.py``) with
``ManifestProver(check_command=True)``: a surface is deleted only when the
command-skills manifest proves the package installed exactly those bytes;
otherwise it is preserved in place and the CLI reports "Preserved", never
"Removed" (FR-014/FR-015). Dir-level routing means a directory that mixes a
manifest-proven file with an untracked user file is preserved WHOLE (no
partial ``rmtree`` that keeps the "owned" bytes but throws away the sibling
user file).

RED on base (main@d57619a900): the "preserve" tests below fail because the
file is deleted and the output says "Removed", not "Preserved".
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.asset_preservation.provers import ManifestProver, OwnershipProof
from specify_cli.cli.commands.agent.config import app
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.skills import manifest_store

pytestmark = [pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _init_project(tmp_path: Path, agents: list[str]) -> Path:
    """Minimal project scaffold: ``.kittify/config.yaml`` with *agents* available."""
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(tmp_path, AgentConfig(available=agents))
    return tmp_path


def _invoke(tmp_path: Path, args: list[str]) -> Result:
    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=tmp_path):
        return runner.invoke(app, args)


class TestIssue4907RemovePreservesUserContent:
    """#4907 core repro: ``agent config remove`` must never delete an unproven file."""

    def test_remove_preserves_untracked_user_command_file(self, tmp_path: Path) -> None:
        """Arrange: claude configured, a user-authored command file with no manifest
        entry; Act: ``agent config remove claude``; Assert: file survives byte-for-byte,
        exit 0, output says "Preserved" (never "Removed")."""
        _init_project(tmp_path, ["claude"])
        user_file = tmp_path / ".claude" / "commands" / "my-deploy.md"
        user_file.parent.mkdir(parents=True)
        original = "# my custom deploy command\n\nDo the thing.\n"
        user_file.write_text(original, encoding="utf-8")

        result = _invoke(tmp_path, ["remove", "claude"])

        assert result.exit_code == 0, result.output
        assert "Removed" not in result.output
        assert "Preserved" in result.output
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == original

    def test_remove_preserves_mixed_manifest_and_user_dir(self, tmp_path: Path) -> None:
        """Arrange: a manifest-proven file AND an untracked user file share the same
        managed subdir; Act: remove; Assert: the whole dir is preserved -- no partial
        rmtree that keeps the proven file's bytes but destroys the user file."""
        _init_project(tmp_path, ["claude"])
        managed_dir = tmp_path / ".claude" / "commands"
        managed_dir.mkdir(parents=True)

        proven = managed_dir / "spec-kitty.implement.md"
        proven_content = b"# implement\n"
        proven.write_bytes(proven_content)

        user_file = managed_dir / "my-notes.md"
        user_original = "private notes, not package content\n"
        user_file.write_text(user_original, encoding="utf-8")

        rel = proven.relative_to(tmp_path).as_posix()
        digest = manifest_store.fingerprint(proven_content)
        manifest = manifest_store.SkillsManifest(entries=[manifest_store.ManifestEntry(rel, digest, ("codex",), "2020-01-01T00:00:00+00:00", "3.9.0")])
        # Directly write the raw manifest JSON: the schema restricts
        # ``ManifestEntry.path``/``agents`` to the skill-only shape, but
        # ``ManifestProver._command_owned`` only checks path+hash equality, so a
        # hand-authored manifest still exercises the exact lookup the guard uses.
        import json as _json

        (tmp_path / ".kittify" / "command-skills-manifest.json").write_text(
            _json.dumps(
                {
                    "schema_version": 1,
                    "entries": [
                        {
                            "path": rel,
                            "content_hash": digest,
                            "agents": list(manifest.entries[0].agents),
                            "installed_at": manifest.entries[0].installed_at,
                            "spec_kitty_version": manifest.entries[0].spec_kitty_version,
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        result = _invoke(tmp_path, ["remove", "claude"])

        assert result.exit_code == 0, result.output
        assert "Removed" not in result.output
        assert proven.exists(), "mixed dir must be preserved WHOLE, not partially rmtree'd"
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == user_original

    def test_remove_preserves_non_claude_agent_dir(self, tmp_path: Path) -> None:
        """AGENT_DIRS generality (T008): the preserve behavior is table-driven, not
        claude-special-cased. copilot's ``.github/prompts/`` gets the same treatment."""
        _init_project(tmp_path, ["copilot"])
        user_file = tmp_path / ".github" / "prompts" / "spec-kitty.custom.prompt.md"
        user_file.parent.mkdir(parents=True)
        original = "# a hand-written copilot prompt\n"
        user_file.write_text(original, encoding="utf-8")

        result = _invoke(tmp_path, ["remove", "copilot"])

        assert result.exit_code == 0, result.output
        assert "Removed" not in result.output
        assert "Preserved" in result.output
        assert user_file.exists()
        assert user_file.read_text(encoding="utf-8") == original


class TestIssue4907OwnedDeleteAnchor:
    """A genuinely package-owned surface IS still removed (both verbs)."""

    def test_remove_owned_surface_is_removed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Arrange: claude's managed surface, ownership proven via a substituted
        prover (the real manifest schema cannot express a command-layer path --
        see docstring); Act: remove; Assert: the surface IS removed and the CLI
        reports "Removed" -- so a preserve-everything fix cannot pass this test."""
        _init_project(tmp_path, ["claude"])
        surface = tmp_path / ".claude" / "commands"
        surface.mkdir(parents=True)
        (surface / "spec-kitty.implement.md").write_text("# implement\n", encoding="utf-8")

        real_prove = ManifestProver.prove

        def _fake_prove(self: ManifestProver, path: Path, project_path: Path) -> OwnershipProof | None:
            if path == surface:
                return OwnershipProof("manifest", "test-fixture:owned")
            return real_prove(self, path, project_path)

        monkeypatch.setattr(ManifestProver, "prove", _fake_prove)

        result = _invoke(tmp_path, ["remove", "claude"])

        assert result.exit_code == 0, result.output
        assert "Removed" in result.output
        assert not surface.exists()

    def test_sync_owned_surface_is_removed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same anchor via the ``sync`` orphan sweep (#2691's call site)."""
        _init_project(tmp_path, [])  # claude orphaned: present but not configured
        surface = tmp_path / ".claude" / "commands"
        surface.mkdir(parents=True)
        (surface / "spec-kitty.implement.md").write_text("# implement\n", encoding="utf-8")

        real_prove = ManifestProver.prove

        def _fake_prove(self: ManifestProver, path: Path, project_path: Path) -> OwnershipProof | None:
            if path == surface:
                return OwnershipProof("manifest", "test-fixture:owned")
            return real_prove(self, path, project_path)

        monkeypatch.setattr(ManifestProver, "prove", _fake_prove)

        result = _invoke(tmp_path, ["sync"])

        assert result.exit_code == 0, result.output
        assert "Removed orphaned" in result.output
        assert not surface.exists()
