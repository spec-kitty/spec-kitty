"""Tests for the skill installer."""

from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.core.config import (
    SKILL_CLASS_NATIVE,
    SKILL_CLASS_SHARED,
)
from specify_cli.skills.installer import install_all_skills, install_skills_for_agent
from specify_cli.skills.manifest import ManagedFileEntry, compute_content_hash
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES


pytestmark = [pytest.mark.unit, pytest.mark.fast]

RETIRED_UPSUN_SKILL = "spk-team-upsun-cli-sync"


def _make_skill(
    root: Path,
    name: str,
    *,
    skill_md_content: str | None = None,
    references: list[str] | None = None,
    scripts: list[str] | None = None,
    assets: list[str] | None = None,
) -> CanonicalSkill:
    """Create a minimal canonical skill on disk and return the dataclass."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        skill_md_content or f"---\nname: {name}\n---\n# {name}\nPlaceholder.\n",
        encoding="utf-8",
    )

    ref_paths: list[Path] = []
    script_paths: list[Path] = []
    asset_paths: list[Path] = []

    for sub, files, out in [
        ("references", references or [], ref_paths),
        ("scripts", scripts or [], script_paths),
        ("assets", assets or [], asset_paths),
    ]:
        if files:
            sub_dir = skill_dir / sub
            sub_dir.mkdir(exist_ok=True)
            for fname in files:
                p = sub_dir / fname
                p.write_text(f"# {fname}\n")
                out.append(p)

    return CanonicalSkill(
        name=name,
        skill_dir=skill_dir,
        skill_md=skill_md,
        references=ref_paths,
        scripts=script_paths,
        assets=asset_paths,
    )


@pytest.mark.parametrize("tamper", ["opaque", "tuple", "bytes", "reason", "values", "observations", "target", "hardlink"])
def test_skill_provisioning_admission_rejects_noncanonical_descriptor(tmp_path: Path, tamper: str) -> None:
    from dataclasses import replace
    import os
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.skills.installer import assess_project_skills
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex]\n")
    if tamper == "hardlink":
        os.link(config, tmp_path / "alias")
    descriptor = prepare_mission_type_activations(project)
    projected: object = descriptor
    if tamper == "opaque":
        with pytest.raises(TypeError, match="deeply immutable"):
            AssessmentInputs(OperationRoot("project", "project", project), projected=object())
        projected = descriptor.write.desired_sha256
    elif tamper == "tuple":
        projected = (descriptor,)
    elif tamper == "bytes":
        projected = replace(descriptor, write=replace(descriptor.write, desired_bytes=b"arbitrary: true\n"))
    elif tamper == "reason":
        projected = replace(descriptor, reason="invented")
    elif tamper == "values":
        projected = replace(descriptor, mission_type_activations=("invented",))
    elif tamper == "observations":
        projected = replace(descriptor, write=replace(descriptor.write, observations=()))
    elif tamper == "target":
        projected = replace(descriptor, write=replace(descriptor.write, target=tmp_path / "elsewhere"))
    _make_skill(tmp_path / "source", "a")
    before = snapshot({"sandbox": tmp_path})
    assessment = assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), projected=projected),
        SkillRegistry(tmp_path / "source"),
        ("codex",),
    )
    assert not assessment.complete and assessment.diagnostics and not assessment.effects
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_skill_provisioning_retained_descriptor_cannot_be_removed(tmp_path: Path) -> None:
    from dataclasses import replace
    from charter.activation.compiler import prepare_mission_type_activations
    from specify_cli.skills.installer import PreparedProjectSkills, assess_project_skills, recheck_project_skills
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    config = project / ".kittify/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("agents:\n  available: [codex]\n")
    _make_skill(tmp_path / "source", "a")
    descriptor = prepare_mission_type_activations(project)
    assessment = assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), projected=descriptor),
        SkillRegistry(tmp_path / "source"),
        ("codex",),
    )
    assert assessment.complete
    assert isinstance(assessment.prepared, PreparedProjectSkills)
    tampered = replace(assessment, prepared=replace(assessment.prepared, provisioning=None))
    with recheck_project_skills(tampered) as errors:
        assert errors


# ── T014 / T017: install_skills_for_agent ────────────────────────────


class TestInstallNativeRootAgent:
    """test_install_native_root_agent -- claude gets .claude/skills/"""

    def test_files_placed_in_native_root(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        entries = install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.is_file()
        assert len(entries) == 1
        assert entries[0].installed_path == ".claude/skills/my-skill/SKILL.md"
        assert entries[0].installation_class == SKILL_CLASS_NATIVE
        assert entries[0].agent_key == "claude"

    def test_content_matches_source(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.read_text() == skill.skill_md.read_text()


class TestInstallSharedRootAgent:
    """test_install_shared_root_agent -- codex gets .agents/skills/"""

    def test_files_placed_in_shared_root(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        entries = install_skills_for_agent(project, "codex", [skill])

        installed = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        assert installed.is_file()
        assert len(entries) == 1
        assert entries[0].installed_path == ".agents/skills/my-skill/SKILL.md"
        assert entries[0].installation_class == SKILL_CLASS_SHARED
        assert entries[0].agent_key == "codex"

    def test_codex_spec_kitty_generation_adds_missing_frontmatter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(
            skills_root,
            "spec-kitty",
            skill_md_content=("# spec-kitty\n\nGet governance context for an action and open an invocation record.\n"),
        )

        entries = install_skills_for_agent(project, "codex", [skill])

        installed = project / ".agents" / "skills" / "spec-kitty" / "SKILL.md"
        content = installed.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "name: spec-kitty\n" in content
        assert "description: Get governance context for an action and open an invocation record.\n" in content
        assert entries[0].content_hash == compute_content_hash(installed)

    def test_native_generation_adds_missing_frontmatter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(
            skills_root,
            "plain-skill",
            skill_md_content="# Plain Skill\n\nUse the plain skill.\n",
        )

        install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "plain-skill" / "SKILL.md"
        content = installed.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "name: plain-skill\n" in content

    def test_reinstall_clears_windows_readonly_global_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "claude", [skill])

        real_rmtree = shutil.rmtree

        def windows_like_rmtree(
            path: str | Path,
            ignore_errors: bool = False,
            onerror: Callable[[Callable[[str], object], str, object], object] | None = None,
            *,
            dir_fd: int | None = None,
        ) -> None:
            readonly_files = [file_path for file_path in Path(path).rglob("*") if file_path.is_file() and not file_path.stat().st_mode & stat.S_IWRITE]
            if readonly_files and onerror is None:
                raise PermissionError(readonly_files[0])
            for readonly_file in readonly_files:
                assert onerror is not None

                def remove_after_chmod(path_str: str) -> None:
                    target = Path(path_str)
                    if not target.stat().st_mode & stat.S_IWRITE:
                        raise PermissionError(path_str)
                    target.unlink()

                onerror(remove_after_chmod, str(readonly_file), PermissionError(str(readonly_file)))
            real_rmtree(path, ignore_errors=ignore_errors, onerror=onerror, dir_fd=dir_fd)

        monkeypatch.setattr(shutil, "rmtree", windows_like_rmtree)

        install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    def test_reinstall_clears_windows_readonly_copied_projection(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        def fail_if_symlinked(self: Path, target: str | Path, target_is_directory: bool = False) -> None:
            pytest.fail("skill projection must never create symlinks (#2412)")

        real_unlink = Path.unlink

        def windows_like_unlink(self: Path, missing_ok: bool = False) -> None:
            if self.exists() and self.is_file() and not self.stat().st_mode & stat.S_IWRITE:
                raise PermissionError(self)
            real_unlink(self, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "symlink_to", fail_if_symlinked)
        monkeypatch.setattr(Path, "unlink", windows_like_unlink)

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "claude", [skill])
        install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.is_file()
        assert not installed.is_symlink()

    def test_install_preserves_unowned_retired_skill_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        for root in [
            tmp_path / "home" / ".claude" / "skills",
            project / ".claude" / "skills",
        ]:
            for retired_name in sorted(RETIRED_CANONICAL_SKILL_NAMES):
                retired_skill = root / retired_name / "SKILL.md"
                retired_skill.parent.mkdir(parents=True, exist_ok=True)
                retired_skill.write_text("# retired\n", encoding="utf-8")
            custom_skill = root / "custom-skill" / "SKILL.md"
            custom_skill.parent.mkdir(parents=True, exist_ok=True)
            custom_skill.write_text("# custom\n", encoding="utf-8")

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "claude", [skill])

        for root in [
            tmp_path / "home" / ".claude" / "skills",
            project / ".claude" / "skills",
        ]:
            for retired_name in RETIRED_CANONICAL_SKILL_NAMES:
                assert (root / retired_name / "SKILL.md").read_text(encoding="utf-8") == "# retired\n"
            assert (root / "custom-skill" / "SKILL.md").is_file()
            assert (root / "my-skill" / "SKILL.md").is_file()

    def test_install_preserves_unowned_stale_upsun_skill(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A retired canonical-looking name is not ownership evidence (WP05)."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        upsun_body = (
            "---\n"
            f"name: {RETIRED_UPSUN_SKILL}\n"
            "description: Point a local Spec Kitty CLI at Spec Kitty SaaS on Upsun.\n"
            "---\n"
            "# Upsun CLI sync\n\nInternal kittyfooding helper.\n"
        )
        for root in [
            tmp_path / "home" / ".claude" / "skills",
            project / ".claude" / "skills",
        ]:
            stale = root / RETIRED_UPSUN_SKILL
            (stale / "scripts").mkdir(parents=True, exist_ok=True)
            (stale / "SKILL.md").write_text(upsun_body, encoding="utf-8")
            (stale / "scripts" / "use-upsun-env.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

        # The currently-shipped pack no longer contains the upsun skill.
        shipped = _make_skill(skills_root, "spk-team-sync")
        install_skills_for_agent(project, "claude", [shipped])

        for root in [
            tmp_path / "home" / ".claude" / "skills",
            project / ".claude" / "skills",
        ]:
            assert (root / RETIRED_UPSUN_SKILL / "SKILL.md").read_text(encoding="utf-8") == upsun_body
            assert (root / RETIRED_UPSUN_SKILL / "scripts/use-upsun-env.sh").read_text(encoding="utf-8") == "#!/usr/bin/env bash\n"
            assert (root / "spk-team-sync" / "SKILL.md").is_file()


class TestInstallWrapperOnlyAgentSkipped:
    """test_install_wrapper_only_agent_skipped -- q gets nothing"""

    def test_returns_empty_list(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        entries = install_skills_for_agent(project, "q", [skill])

        assert entries == []

    def test_no_files_created(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "q", [skill])

        # No directories created under project
        children = list(project.iterdir())
        assert children == []


# ── T016: shared-root deduplication ──────────────────────────────────


class TestSharedRootDeduplication:
    """test_shared_root_deduplication -- two shared agents share one copy"""

    def test_second_agent_skips_file_copy(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        shared_set: set[str] = set()

        # First shared-root agent (codex) copies files
        entries_1 = install_skills_for_agent(project, "codex", [skill], shared_root_installed=shared_set)
        assert "my-skill" in shared_set
        assert len(entries_1) == 1

        # Second shared-root agent (copilot) reuses files
        entries_2 = install_skills_for_agent(project, "copilot", [skill], shared_root_installed=shared_set)
        assert len(entries_2) == 1

        # Both point to the same installed path
        assert entries_1[0].installed_path == entries_2[0].installed_path

        # But have different agent keys
        assert entries_1[0].agent_key == "codex"
        assert entries_2[0].agent_key == "copilot"

    def test_only_one_file_on_disk(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        shared_set: set[str] = set()

        install_skills_for_agent(project, "codex", [skill], shared_root_installed=shared_set)
        install_skills_for_agent(project, "copilot", [skill], shared_root_installed=shared_set)

        # Only one copy on disk (in .agents/skills/)
        installed = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        assert installed.is_file()

        # No vendor-specific copy
        assert not (project / ".codex").exists()
        assert not (project / ".github").exists()


# ── T017: manifest entries ───────────────────────────────────────────


class TestManifestEntriesCreated:
    """test_manifest_entries_created -- verify entry fields"""

    def test_entry_fields_correct(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        entries = install_skills_for_agent(project, "claude", [skill])

        entry = entries[0]
        assert entry.skill_name == "my-skill"
        assert entry.source_file == "SKILL.md"
        assert entry.installed_path == ".claude/skills/my-skill/SKILL.md"
        assert entry.installation_class == SKILL_CLASS_NATIVE
        assert entry.agent_key == "claude"
        assert entry.content_hash.startswith("sha256:")
        assert entry.installed_at != ""

    def test_hash_computed_from_installed_file(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        entries = install_skills_for_agent(project, "claude", [skill])

        installed = project / ".claude" / "skills" / "my-skill" / "SKILL.md"
        expected_hash = compute_content_hash(installed)
        assert entries[0].content_hash == expected_hash


# ── T015: install_all_skills ─────────────────────────────────────────


class TestInstallAllSkillsOrchestration:
    """test_install_all_skills_orchestration -- full flow with mixed agents"""

    def test_mixed_agents(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        _make_skill(skills_root, "alpha")
        _make_skill(skills_root, "beta")

        registry = SkillRegistry(skills_root)
        # claude = native, codex = shared, q = wrapper
        manifest = install_all_skills(project, ["claude", "codex", "q"], registry)

        # claude: native, gets both skills -> 2 entries
        claude_entries = [e for e in manifest.entries if e.agent_key == "claude"]
        assert len(claude_entries) == 2

        # codex: shared, gets both skills -> 2 entries
        codex_entries = [e for e in manifest.entries if e.agent_key == "codex"]
        assert len(codex_entries) == 2

        # q: wrapper, gets nothing -> 0 entries
        q_entries = [e for e in manifest.entries if e.agent_key == "q"]
        assert len(q_entries) == 0

        # Total entries: 4
        assert len(manifest.entries) == 4

    def test_manifest_timestamps_set(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        _make_skill(skills_root, "alpha")
        registry = SkillRegistry(skills_root)

        manifest = install_all_skills(project, ["claude"], registry)
        assert manifest.created_at != ""
        assert manifest.updated_at != ""
        assert manifest.version == 1

    def test_shared_root_deduplication_across_agents(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        _make_skill(skills_root, "alpha")
        registry = SkillRegistry(skills_root)

        # Two shared-root agents: copilot and codex
        manifest = install_all_skills(project, ["copilot", "codex"], registry)

        # Both get entries
        copilot_entries = [e for e in manifest.entries if e.agent_key == "copilot"]
        codex_entries = [e for e in manifest.entries if e.agent_key == "codex"]
        assert len(copilot_entries) == 1
        assert len(codex_entries) == 1

        # Both point to same installed_path
        assert copilot_entries[0].installed_path == codex_entries[0].installed_path

        # Only one copy on disk
        installed = project / ".agents" / "skills" / "alpha" / "SKILL.md"
        assert installed.is_file()

    def test_no_skills_returns_empty_manifest(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        skills_root.mkdir()  # Empty -- no skills
        project = tmp_path / "project"
        project.mkdir()

        registry = SkillRegistry(skills_root)
        manifest = install_all_skills(project, ["claude", "codex"], registry)

        assert len(manifest.entries) == 0
        assert manifest.version == 1


# ── T018: edge cases ────────────────────────────────────────────────


class TestInstallPreservesExistingFiles:
    """test_install_preserves_existing_files -- existing non-managed files not deleted"""

    def test_existing_file_not_removed(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        # Pre-existing file in the skill root
        existing_dir = project / ".claude" / "skills" / "my-skill"
        existing_dir.mkdir(parents=True)
        existing_file = existing_dir / "custom-notes.md"
        existing_file.write_text("user notes")

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "claude", [skill])

        # The existing file should still be there
        assert existing_file.is_file()
        assert existing_file.read_text() == "user notes"

        # And the new skill file should also exist
        assert (existing_dir / "SKILL.md").is_file()


class TestInstallCopiesReferencesAndScripts:
    """test_install_copies_references_and_scripts -- subdirectories copied"""

    def test_all_subdirs_copied(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(
            skills_root,
            "full-skill",
            references=["arch.md", "rfc.txt"],
            scripts=["setup.sh"],
            assets=["logo.png"],
        )
        entries = install_skills_for_agent(project, "claude", [skill])

        base = project / ".claude" / "skills" / "full-skill"

        # Check each sub-file exists
        assert (base / "SKILL.md").is_file()
        assert (base / "references" / "arch.md").is_file()
        assert (base / "references" / "rfc.txt").is_file()
        assert (base / "scripts" / "setup.sh").is_file()
        assert (base / "assets" / "logo.png").is_file()

        # 1 SKILL.md + 2 references + 1 script + 1 asset = 5 entries
        assert len(entries) == 5

    def test_subdir_content_matches(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(
            skills_root,
            "full-skill",
            references=["arch.md"],
        )
        install_skills_for_agent(project, "claude", [skill])

        installed_ref = project / ".claude" / "skills" / "full-skill" / "references" / "arch.md"
        source_ref = skills_root / "full-skill" / "references" / "arch.md"
        assert installed_ref.read_text() == source_ref.read_text()

    def test_entry_source_file_is_relative_within_skill(self, tmp_path: Path) -> None:
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(
            skills_root,
            "full-skill",
            references=["arch.md"],
            scripts=["run.sh"],
        )
        entries = install_skills_for_agent(project, "claude", [skill])

        source_files = {e.source_file for e in entries}
        assert "SKILL.md" in source_files
        assert "references/arch.md" in source_files
        assert "scripts/run.sh" in source_files


# ── #2412: copy delivery, never symlinks ─────────────────────────────


class TestCopyDelivery:
    """Skill projection delivers copies, never symlinks (#2412 / ADR 2026-07-19-1)."""

    def test_projection_is_copy_never_symlink(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        def fail_if_symlinked(self: Path, target: str | Path, target_is_directory: bool = False) -> None:
            pytest.fail("skill projection must never create symlinks (#2412)")

        monkeypatch.setattr(Path, "symlink_to", fail_if_symlinked)

        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill", references=["arch.md"])
        entries = install_skills_for_agent(project, "codex", [skill])

        for entry in entries:
            installed = project / entry.installed_path
            assert not installed.is_symlink()
            assert installed.is_file()
            assert entry.delivery_mode == "copy"

    def test_reinstall_replaces_legacy_symlink_with_copy(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pre-#2412 project carries absolute symlinks into the global root;
        the next install run converts them to copies — no migration needed."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")

        # Simulate the legacy projection: dest is an absolute symlink to a
        # (machine-local) canonical file outside the repo.
        legacy_target = tmp_path / "home" / ".agents" / "skills" / "my-skill" / "SKILL.md"
        legacy_target.parent.mkdir(parents=True, exist_ok=True)
        legacy_target.write_text("legacy canonical content\n", encoding="utf-8")
        dest = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(legacy_target)

        from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest

        entry = ManagedFileEntry(
            "my-skill", "SKILL.md", dest.relative_to(project).as_posix(), SKILL_CLASS_SHARED, "codex", compute_content_hash(legacy_target), "historical", "symlink"
        )
        save_manifest(ManagedSkillManifest(entries=[entry]), project)

        entries = install_skills_for_agent(project, "codex", [skill])

        assert not dest.is_symlink()
        assert dest.is_file()
        assert dest.read_text(encoding="utf-8") == skill.skill_md.read_text(encoding="utf-8")
        assert entries[0].delivery_mode == "copy"

    def test_reinstall_leaves_hash_equal_copy_untouched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Re-running install over an up-to-date copy is a no-op for that file
        (idempotent — no rewrite churn on every upgrade)."""
        from specify_cli.skills.installer import _project_skill_file

        source = tmp_path / "global" / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text("canonical\n", encoding="utf-8")
        project = tmp_path / "project"
        dest = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        dest.parent.mkdir(parents=True)

        mode, _ = _project_skill_file(source, dest, project)
        assert mode == "copy"

        import shutil as shutil_module

        def fail_if_copied(src: object, dst: object, **kwargs: object) -> None:
            pytest.fail("hash-equal destination must not be rewritten")

        monkeypatch.setattr(shutil_module, "copy2", fail_if_copied)
        mode, _ = _project_skill_file(source, dest, project)
        assert mode == "copy"
        assert dest.read_text(encoding="utf-8") == "canonical\n"

    def test_owned_stale_copy_archived_then_replaced(self, tmp_path: Path) -> None:
        """An unmodified recorded copy is archived before a canonical update."""
        from specify_cli.skills.installer import _project_skill_file

        source = tmp_path / "global" / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text("canonical\n", encoding="utf-8")
        project = tmp_path / "project"
        dest = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("user edited\n", encoding="utf-8")
        from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest

        assert _project_skill_file(source, dest, project)[0] == "preserved"
        assert dest.read_text(encoding="utf-8") == "user edited\n"
        entry = ManagedFileEntry(
            "my-skill", "SKILL.md", dest.relative_to(project).as_posix(), SKILL_CLASS_SHARED, "codex", compute_content_hash(dest), "historical"
        )
        save_manifest(ManagedSkillManifest(entries=[entry]), project)

        archived: list[Path] = []
        mode, backup_root = _project_skill_file(source, dest, project, archived_paths=archived)

        assert mode == "copy"
        assert dest.read_text(encoding="utf-8") == "canonical\n"
        assert backup_root is not None
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == "user edited\n"

    def test_copy_preserves_read_only_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Copies inherit the canonical root's read-only mode — the projection
        is managed content, not user-editable (drift is detected and repaired)."""
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        skills_root = tmp_path / "skills_src"
        project = tmp_path / "project"
        project.mkdir()

        skill = _make_skill(skills_root, "my-skill")
        install_skills_for_agent(project, "codex", [skill])

        installed = project / ".agents" / "skills" / "my-skill" / "SKILL.md"
        assert not installed.stat().st_mode & stat.S_IWRITE


def test_wp05_backup_identity_excludes_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import installer
    from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest

    roots = []
    for label, clock in (("left", "20260906T100000Z"), ("right", "20260907T100000Z")):
        project = tmp_path / label
        dest = project / ".claude/skills/sample/SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"previous managed content")
        source = tmp_path / (label + "-source")
        source.write_bytes(b"replacement content")
        entry = ManagedFileEntry("sample", "SKILL.md", dest.relative_to(project).as_posix(), SKILL_CLASS_NATIVE, "claude", compute_content_hash(dest), "2025-01-01")
        save_manifest(ManagedSkillManifest(entries=[entry]), project)
        monkeypatch.setattr(installer, "now_utc_iso", lambda clock=clock: clock)
        _, backup = installer._project_skill_file(source, dest, project)
        assert backup is not None
        assert (backup / dest.relative_to(project)).read_bytes() == b"previous managed content"
        roots.append(backup.relative_to(project).as_posix())
    assert roots[0] == roots[1], roots


def test_wp05_installer_preserves_unknown_canonical_content(tmp_path: Path) -> None:
    project = tmp_path / "project"
    skill = _make_skill(tmp_path / "source", "sample", references=["independent.md"])
    dest = project / ".claude/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("user authored canonical-looking skill")
    before = dest.read_bytes(), dest.stat().st_mtime_ns
    entries = install_skills_for_agent(project, "claude", [skill])
    assert (dest.read_bytes(), dest.stat().st_mtime_ns) == before
    assert not any(entry.source_file == "SKILL.md" for entry in entries)
    assert (dest.parent / "references/independent.md").is_file()


def test_backup_allocator_is_pure_sorted_and_relocation_independent(tmp_path: Path) -> None:
    from dataclasses import replace
    from specify_cli.skills.installer import SkillBackupReplacement, prepare_skill_backup
    from specify_cli.tool_surface.operations import FileState

    before = FileState("file", sha256="a" * 64, mode=0o444, mtime_ns=1)
    after = FileState("file", sha256="b" * 64, mode=0o444, mtime_ns=2)
    first = SkillBackupReplacement(".claude/skills/sample/SKILL.md", before, after)
    second = SkillBackupReplacement(".agents/skills/sample/SKILL.md", before, after)
    left = prepare_skill_backup(tmp_path / "left", (second, first))
    right = prepare_skill_backup(
        tmp_path / "right",
        (
            replace(first, before=replace(before, mtime_ns=99)),
            second,
        ),
    )
    assert left.root.name == right.root.name
    assert left.root.name.startswith("state-v1-")
    assert not list(tmp_path.iterdir())
    changed = prepare_skill_backup(tmp_path / "left", (replace(first, after=replace(after, mode=0o644)), second))
    assert changed.root.name != left.root.name


@pytest.mark.parametrize("kind", ["file", "directory", "symlink"])
def test_backup_allocator_preserves_collisions_and_refuses_races(tmp_path: Path, kind: str) -> None:
    from specify_cli.skills.installer import SkillBackupReplacement, prepare_skill_backup, create_skill_backup
    from specify_cli.tool_surface.operations import FileState

    replacement = SkillBackupReplacement(".claude/skills/sample/SKILL.md", FileState("file", sha256="a" * 64, mode=0o444), FileState("absent"))
    original = prepare_skill_backup(tmp_path, (replacement,))
    original.root.parent.mkdir(parents=True)
    if kind == "file":
        original.root.write_bytes(b"unrelated backup")
    elif kind == "directory":
        original.root.mkdir()
        (original.root / "unknown").write_bytes(b"unrelated backup")
    else:
        original.root.symlink_to("missing-user-target")
    second = prepare_skill_backup(tmp_path, (replacement,))
    assert second.root.name == original.root.name + "-1"
    with pytest.raises(FileExistsError):
        prepare_skill_backup(tmp_path, (replacement,), explicit_root=original.root)
    second.root.write_bytes(b"racing writer")
    with pytest.raises(ValueError, match="input changed"):
        create_skill_backup(second)
    assert second.root.read_bytes() == b"racing writer"
    third = prepare_skill_backup(tmp_path, (replacement,))
    assert third.root.name == original.root.name + "-2"
    created = create_skill_backup(third)
    assert stat.S_IMODE(created.stat().st_mode) == 0o700
    if kind == "file":
        assert original.root.read_bytes() == b"unrelated backup"
    elif kind == "directory":
        assert (original.root / "unknown").read_bytes() == b"unrelated backup"
    else:
        assert original.root.readlink() == Path("missing-user-target")


def test_backup_member_is_exclusive_and_preserves_mode_and_content(tmp_path: Path) -> None:
    from specify_cli.skills.installer import _archive_existing_path

    dest = tmp_path / ".claude/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"original readonly content")
    dest.chmod(0o444)
    stamp = dest.stat().st_mtime_ns
    root = _archive_existing_path(dest, tmp_path, None)
    retained = root / dest.relative_to(tmp_path)
    assert retained.read_bytes() == b"original readonly content"
    assert stat.S_IMODE(retained.stat().st_mode) == 0o444
    assert retained.stat().st_mtime_ns == stamp
    assert not dest.exists()
    dest.write_bytes(b"next content")
    with pytest.raises(FileExistsError):
        _archive_existing_path(dest, tmp_path, root)
    assert dest.read_bytes() == b"next content"
    assert retained.read_bytes() == b"original readonly content"


def test_backup_preserves_literal_dangling_link_and_rejects_escape(tmp_path: Path) -> None:
    from specify_cli.skills.installer import _archive_existing_path, SkillBackupReplacement, prepare_skill_backup
    from specify_cli.tool_surface.operations import FileState

    dest = tmp_path / ".claude/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to("../../../missing")
    before = dest.lstat()
    root = _archive_existing_path(dest, tmp_path, None)
    retained = root / dest.relative_to(tmp_path)
    assert retained.readlink() == Path("../../../missing")
    assert stat.S_IMODE(retained.lstat().st_mode) == stat.S_IMODE(before.st_mode)
    assert retained.lstat().st_mtime_ns == before.st_mtime_ns
    assert not dest.is_symlink()
    replacement = SkillBackupReplacement("../escape", FileState("file", sha256="a" * 64, mode=0o444), FileState("absent"))
    with pytest.raises(ValueError, match="Unsafe"):
        prepare_skill_backup(tmp_path, (replacement,))


def test_projection_preserves_modified_owned_file_and_unknown_link(tmp_path: Path) -> None:
    from specify_cli.skills.installer import _project_skill_file
    from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest

    source = tmp_path / "source"
    source.write_bytes(b"new canonical content")
    project = tmp_path / "project"
    dest = project / ".claude/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"owned content")
    entry = ManagedFileEntry("sample", "SKILL.md", dest.relative_to(project).as_posix(), SKILL_CLASS_NATIVE, "claude", compute_content_hash(dest), "2025-01-01")
    save_manifest(ManagedSkillManifest(entries=[entry]), project)
    dest.write_bytes(b"user edits")
    assert _project_skill_file(source, dest, project)[0] == "preserved"
    assert dest.read_bytes() == b"user edits"
    dest.unlink()
    dest.symlink_to(source)
    assert _project_skill_file(source, dest, project)[0] == "preserved"
    assert dest.is_symlink()
    assert not (project / ".kittify/.migration-backup").exists()


def test_projection_backup_identity_covers_all_skill_replacements(tmp_path: Path) -> None:
    from specify_cli.skills.installer import _project_skill_files, prepare_skill_backup, SkillBackupReplacement
    from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest
    from specify_cli.skills.paths import observe_skill_path

    project = tmp_path / "project"
    project.mkdir()
    skill = _make_skill(tmp_path / "source", "sample", references=["other.md"])
    target = project / ".claude/skills/sample"
    original = _project_skill_files(skill, target, skill.skill_dir, project, SKILL_CLASS_NATIVE, "claude")
    save_manifest(ManagedSkillManifest(entries=original), project)
    replacements = []
    for source in skill.all_files:
        dest = target / source.relative_to(skill.skill_dir)
        source.write_bytes(b"new canonical bytes " + source.name.encode())
        replacements.append(SkillBackupReplacement(dest.relative_to(project).as_posix(), observe_skill_path(dest).state, observe_skill_path(source).state))
    expected = prepare_skill_backup(project, tuple(replacements))
    archives: list[Path] = []
    _project_skill_files(skill, target, skill.skill_dir, project, SKILL_CLASS_NATIVE, "claude", archives)
    assert len(archives) == 2
    assert all(archive.is_relative_to(expected.root) for archive in archives)
    assert len(list(expected.root.parent.iterdir())) == 1
    assert all(archive.read_bytes() != (project / archive.relative_to(expected.root)).read_bytes() for archive in archives)


def test_shared_projection_does_not_adopt_unknown_content(tmp_path: Path) -> None:
    project = tmp_path / "project"
    skill = _make_skill(tmp_path / "source", "sample", references=["independent.md"])
    dest = project / ".agents/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"unknown shared skill")
    shared: set[str] = set()
    first = install_skills_for_agent(project, "codex", [skill], shared_root_installed=shared)
    second = install_skills_for_agent(project, "copilot", [skill], shared_root_installed=shared)
    assert dest.read_bytes() == b"unknown shared skill"
    assert {entry.source_file for entry in first} == {"references/independent.md"}
    assert {entry.source_file for entry in second} == {"references/independent.md"}
    assert first[0].installed_path == second[0].installed_path
    assert first[0].agent_key != second[0].agent_key


def test_project_retired_name_alone_does_not_authorize_deletion(tmp_path: Path) -> None:
    from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

    name = sorted(RETIRED_CANONICAL_SKILL_NAMES)[0]
    dest = tmp_path / ".claude/skills" / name / "SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"unknown retired-name content")
    before = dest.read_bytes(), dest.stat().st_mtime_ns
    assert install_skills_for_agent(tmp_path, "claude", []) == []
    assert (dest.read_bytes(), dest.stat().st_mtime_ns) == before


@pytest.mark.parametrize("change", ["collision", "parent"])
def test_backup_rechecks_collision_and_parent_before_any_write(tmp_path: Path, change: str) -> None:
    from specify_cli.skills.installer import SkillBackupReplacement, prepare_skill_backup, create_skill_backup
    from specify_cli.tool_surface.operations import FileState
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    replacement = SkillBackupReplacement(".claude/skills/sample/SKILL.md", FileState("file", sha256="a" * 64, mode=0o444), FileState("absent"))
    first = prepare_skill_backup(project, (replacement,))
    first.root.parent.mkdir(parents=True)
    first.root.write_bytes(b"prior backup")
    prepared = prepare_skill_backup(project, (replacement,))
    if change == "collision":
        first.root.write_bytes(b"changed collision")
    else:
        outside = tmp_path / "outside"
        (project / ".kittify").rename(outside)
        (project / ".kittify").symlink_to(outside, target_is_directory=True)
    before = snapshot({"sandbox": tmp_path})
    with pytest.raises(ValueError, match="input changed"):
        create_skill_backup(prepared)
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("invalid", ["missing-catalog", "config-yaml", "config-shape"])
def test_project_owner_rejects_missing_required_sources_and_corrupt_config(tmp_path: Path, invalid: str) -> None:
    from specify_cli.skills.installer import assess_project_skills
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    if invalid != "missing-catalog":
        _make_skill(tmp_path / "source", "alpha")
        (project / ".kittify").mkdir()
        (project / ".kittify/config.yaml").write_text("agents: [" if invalid == "config-yaml" else "- invalid\n")
    before = snapshot({"sandbox": tmp_path})
    assessment = assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), consent=ApplyConsent(automatic=True)),
        SkillRegistry(tmp_path / "source"),
        ("claude",),
    )
    assert not assessment.complete and assessment.diagnostics
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_project_owner_exact_effects_shared_and_idempotent(tmp_path: Path) -> None:
    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha", references=["more.md"])
    _make_skill(tmp_path / "source", "beta")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    before = snapshot({"sandbox": tmp_path})
    assessment = assess_project_skills(inputs, registry, ("claude", "codex", "copilot"))
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    physical_before = snapshot({"project": project})
    with recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics
        result = apply_project_skills(assessment, consent)
    assert result.outcome == "applied", result
    assert set(result.succeeded) == {effect.id for effect in assessment.effects}
    actual = net_delta(physical_before, snapshot({"project": project}))
    expected_states = {
        (effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode) for effect in assessment.effects
    }
    assert {(effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode) for effect in actual} == expected_states
    manifest = load_manifest(project, strict=True)
    assert manifest is not None and len(manifest.entries) == 9
    shared = next(effect for effect in assessment.effects if effect.path == ".agents/skills/alpha/SKILL.md")
    assert shared.logical_owners == ("codex", "copilot")
    assert len(shared.surface_ids) == 2
    current = snapshot({"sandbox": tmp_path})
    second = assess_project_skills(inputs, registry, ("claude", "copilot", "codex"))
    assert second.complete and not second.effects
    with recheck_project_skills(second) as diagnostics:
        assert not diagnostics
        assert apply_project_skills(second, consent).outcome == "applied"
    assert_unchanged(current, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("file_present", [False, True])
@pytest.mark.parametrize("unselected_owner", [False, True])
def test_retirement_reconciles_absent_file_manifest_without_phantom_effect(
    tmp_path: Path,
    file_present: bool,
    unselected_owner: bool,
) -> None:
    from specify_cli.skills import installer
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha")
    _make_skill(tmp_path / "source", "beta")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    initial = installer.assess_project_skills(inputs, registry, ("codex", "copilot"))
    with installer.recheck_project_skills(initial) as errors:
        assert not errors
        assert installer.apply_project_skills(initial, consent).outcome == "applied"
    shutil.rmtree(tmp_path / "source/alpha")
    retired = project / ".agents/skills/alpha/SKILL.md"
    if not file_present:
        retired.unlink()
    agents = ("codex",) if unselected_owner else ("codex", "copilot")
    before = snapshot({"project": project})
    assessment = installer.assess_project_skills(inputs, registry, agents)
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": project}))
    path_effects = [e for e in assessment.effects if e.destination == retired]
    assert [e.action for e in path_effects] == (["delete"] if file_present and not unselected_owner else [])
    assert all(not (e.before.kind == e.after.kind == "absent") for e in assessment.effects)
    with installer.recheck_project_skills(assessment) as errors:
        assert not errors, errors
        result = installer.apply_project_skills(assessment, consent)
    assert result.outcome == "applied", result
    assert set(result.succeeded) == {e.id for e in assessment.effects}
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    assert [e.agent_key for e in manifest.find_by_skill("alpha")] == (["copilot"] if unselected_owner else [])
    assert retired.exists() is (file_present and unselected_owner)
    expected = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in assessment.effects}
    actual = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in net_delta(before, snapshot({"project": project}))}
    assert actual == expected
    settled = snapshot({"project": project})
    again = installer.assess_project_skills(inputs, registry, agents)
    assert again.complete and not again.effects
    with installer.recheck_project_skills(again) as errors:
        assert not errors
        assert installer.apply_project_skills(again, consent).outcome == "applied"
    assert_unchanged(settled, snapshot({"project": project}))


@pytest.mark.parametrize("change", ["source", "mode", "mtime", "catalog", "config", "manifest", "destination", "parent"])
def test_project_owner_rechecks_whole_batch_before_writes(tmp_path: Path, change: str) -> None:
    import os
    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    skill = _make_skill(tmp_path / "source", "alpha", references=["more.md"])
    (project / ".claude").mkdir()
    (project / ".kittify").mkdir()
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    assessment = assess_project_skills(AssessmentInputs(OperationRoot("project", "project", project), consent=consent), registry, ("claude",))
    assert assessment.complete
    if change == "source":
        skill.skill_md.write_bytes(b"changed source")
    elif change == "mode":
        skill.skill_md.chmod(0o444)
    elif change == "mtime":
        info = skill.skill_md.stat()
        os.utime(skill.skill_md, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
    elif change == "catalog":
        (skill.skill_dir / "references/new.md").write_bytes(b"new source")
    elif change == "config":
        (project / ".kittify/config.yaml").write_bytes(b"changed: true")
    elif change == "manifest":
        (project / ".kittify/skills-manifest.json").write_bytes(b"{}")
    elif change == "destination":
        (project / ".claude/skills").mkdir()
    else:
        (project / ".claude").rename(tmp_path / "outside")
        (project / ".claude").symlink_to(tmp_path / "outside", target_is_directory=True)
    before = snapshot({"sandbox": tmp_path})
    with recheck_project_skills(assessment) as diagnostics:
        assert diagnostics and diagnostics[0].code == "precondition_changed"
        assert apply_project_skills(assessment, consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_project_owner_one_backup_set_and_retained_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import installer
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    project.mkdir()
    skills = [_make_skill(tmp_path / "source", name) for name in ("alpha", "beta")]
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    first = installer.assess_project_skills(inputs, registry, ("claude",))
    with installer.recheck_project_skills(first):
        assert installer.apply_project_skills(first, consent).outcome == "applied"
    for skill in skills:
        skill.skill_md.write_bytes(b"changed canonical " + skill.name.encode())
    assessment = installer.assess_project_skills(inputs, registry, ("claude",))
    assert assessment.complete
    backup_files = [effect for effect in assessment.effects if effect.path.startswith(".kittify/.migration-backup/") and effect.after.kind == "file"]
    assert len(backup_files) == 2
    assert len({Path(effect.path).parts[3] for effect in backup_files}) == 1
    assert isinstance(assessment.prepared, installer.PreparedProjectSkills)
    manifest = next(write for write in assessment.prepared.writes if write.effect.path == ".kittify/skills-manifest.json")

    def clock_forbidden() -> str:
        raise AssertionError("apply sampled clock")

    monkeypatch.setattr(installer, "now_utc_iso", clock_forbidden)
    with installer.recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics
        assert installer.apply_project_skills(assessment, consent).outcome == "applied"
    assert (project / ".kittify/skills-manifest.json").read_bytes() == manifest.content
    assert all((project / effect.path).read_bytes() for effect in backup_files)


@pytest.mark.parametrize("selected", [("codex", "copilot"), ("copilot",)])
def test_existing_shared_owner_update_retains_new_consumers_and_prior_proof(
    tmp_path: Path,
    selected: tuple[str, ...],
) -> None:
    from specify_cli.skills import installer
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot, OwnershipProof
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    project = tmp_path / "project"
    project.mkdir()
    skill = _make_skill(tmp_path / "source", "alpha")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    initial = installer.assess_project_skills(inputs, registry, ("codex",))
    with installer.recheck_project_skills(initial) as errors:
        assert not errors
        assert installer.apply_project_skills(initial, consent).outcome == "applied"
    path = ".agents/skills/alpha/SKILL.md"
    original = (project / path).read_bytes()
    skill.skill_md.write_bytes(b"---\nname: alpha\n---\nupdated canonical\n")
    before = snapshot({"sandbox": tmp_path})
    assessment = installer.assess_project_skills(inputs, registry, selected)
    assert assessment.complete
    updates = [effect for effect in assessment.effects if effect.path == path]
    backups = [effect for effect in assessment.effects if effect.path.startswith(".kittify/.migration-backup/") and effect.after.kind == "file"]
    assert len(updates) == len(backups) == 1
    with installer.recheck_project_skills(assessment) as errors:
        assert not errors
        result = installer.apply_project_skills(assessment, consent)
    assert result.outcome == "applied"
    assert (project / path).read_bytes() == skill.skill_md.read_bytes()
    assert backups[0].destination.read_bytes() == original
    manifest = load_manifest(project)
    assert manifest is not None and {entry.agent_key for entry in manifest.entries} == {"codex", "copilot"}
    for effect in (*updates, *backups):
        assert effect.logical_owners == ("codex", "copilot")
        assert set(effect.surface_ids) == {"codex.doctrine_skill.alpha.SKILL.md", "copilot.doctrine_skill.alpha.SKILL.md"}
        assert effect.ownership == (OwnershipProof("manifest", f".kittify/skills-manifest.json:codex:{path}"),)
    assert {effect.id for effect in assessment.effects} == set(result.succeeded)
    expected = {
        (effect.destination.relative_to(tmp_path).as_posix(), effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
        for effect in assessment.effects
    }
    assert {
        (effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
        for effect in net_delta(before, snapshot({"sandbox": tmp_path}))
    } == expected


def test_project_owner_drift_consent_does_not_block_independent_missing_file(tmp_path: Path) -> None:
    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha", references=["more.md"])
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    initial = assess_project_skills(inputs, registry, ("claude",))
    with recheck_project_skills(initial):
        assert apply_project_skills(initial, consent).outcome == "applied"
    path = ".claude/skills/alpha/SKILL.md"
    dest = project / path
    dest.chmod(0o644)
    dest.write_bytes(b"user edits")
    missing = project / ".claude/skills/alpha/references/more.md"
    missing.unlink()
    assessment = assess_project_skills(inputs, registry, ("claude",))
    assert any(item.path == path and item.state == "consent_required" for item in assessment.dispositions)
    assert not any(effect.path == path for effect in assessment.effects)
    with recheck_project_skills(assessment):
        assert apply_project_skills(assessment, consent).outcome == "applied"
    assert dest.read_bytes() == b"user edits" and missing.is_file()
    explicit = ApplyConsent(automatic=True, overwrite_paths=(path,))
    changed = assess_project_skills(AssessmentInputs(inputs.root, consent=explicit), registry, ("claude",))
    assert any(effect.path == path for effect in changed.effects)
    with recheck_project_skills(changed):
        assert apply_project_skills(changed, explicit).outcome == "applied"
    assert dest.read_bytes() != b"user edits"
    retained = [effect for effect in changed.effects if effect.path.startswith(".kittify/.migration-backup/") and effect.after.kind == "file"]
    assert len(retained) == 1 and retained[0].destination.read_bytes() == b"user edits"
    assert load_manifest(project, strict=True) is not None


def test_project_owner_partial_io_reports_exact_completed_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import installer
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha", references=["more.md"])
    consent = ApplyConsent(automatic=True)
    assessment = installer.assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), consent=consent),
        SkillRegistry(tmp_path / "source"),
        ("claude",),
    )
    assert assessment.complete
    real_write = installer._apply_project_skill_write
    executed: list[str] = []

    def failing_write(write: installer.PreparedProjectSkillWrite) -> None:
        if write.effect.path.endswith("references/more.md"):
            raise OSError("injected owner I/O failure")
        real_write(write)
        executed.append(write.effect.id)

    monkeypatch.setattr(installer, "_apply_project_skill_write", failing_write)
    with installer.recheck_project_skills(assessment):
        result = installer.apply_project_skills(assessment, consent)
    assert result.outcome == "partial"
    assert result.succeeded == tuple(executed)
    assert len(result.failed) == 1 and result.skipped
    assert set(result.succeeded + result.failed + result.skipped) == {effect.id for effect in assessment.effects}
    assert (project / ".claude/skills/alpha/SKILL.md").is_file()
    assert not (project / ".kittify/skills-manifest.json").exists()
    assert "injected owner I/O failure" in result.diagnostics[0].message


@pytest.mark.parametrize("known_target", [True, False])
def test_project_owner_converts_only_proven_managed_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, known_target: bool) -> None:
    from specify_cli.skills import installer
    from specify_cli.skills.manifest import ManagedSkillManifest, save_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    dest = project / ".claude/skills/alpha/SKILL.md"
    dest.parent.mkdir(parents=True)
    _make_skill(tmp_path / "source", "alpha")
    global_root = tmp_path / "global"
    monkeypatch.setattr(installer, "get_primary_global_skill_root", lambda agent: global_root)
    target = global_root / "alpha/SKILL.md" if known_target else tmp_path / "user-link-target"
    dest.symlink_to(target)
    entry = ManagedFileEntry("alpha", "SKILL.md", dest.relative_to(project).as_posix(), SKILL_CLASS_NATIVE, "claude", "sha256:" + "a" * 64, "historical", "symlink")
    save_manifest(ManagedSkillManifest(entries=[entry]), project)
    consent = ApplyConsent(automatic=True, overwrite_paths=(entry.installed_path,))
    assessment = installer.assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), consent=consent), SkillRegistry(tmp_path / "source"), ("claude",)
    )
    assert assessment.complete, assessment.diagnostics
    with installer.recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics
        assert installer.apply_project_skills(assessment, consent).outcome == "applied"
    if known_target:
        assert dest.is_file() and not dest.is_symlink()
        backup = next(effect for effect in assessment.effects if effect.after.kind == "symlink")
        assert backup.destination.readlink() == target
    else:
        assert dest.readlink() == target
        assert any(item.state == "preserve" for item in assessment.dispositions)
    assert not global_root.exists()


def test_project_owner_retirement_preserves_shared_owners_and_unknown_members(tmp_path: Path) -> None:
    from specify_cli.skills import installer
    from specify_cli.skills.manifest import load_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import net_delta, snapshot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha")
    _make_skill(tmp_path / "source", "beta")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    initial = installer.assess_project_skills(inputs, registry, ("codex", "copilot"))
    with installer.recheck_project_skills(initial):
        assert installer.apply_project_skills(initial, consent).outcome == "applied"
    shutil.rmtree(tmp_path / "source/alpha")
    dest = project / ".agents/skills/alpha/SKILL.md"
    notes = dest.parent / "user-notes"
    notes.write_bytes(b"preserve unknown member")
    partial = installer.assess_project_skills(inputs, registry, ("codex",))
    assert partial.complete
    assert not any(effect.path == dest.relative_to(project).as_posix() for effect in partial.effects)
    with installer.recheck_project_skills(partial):
        assert installer.apply_project_skills(partial, consent).outcome == "applied"
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    assert [entry.agent_key for entry in manifest.find_by_skill("alpha")] == ["copilot"]
    assert dest.is_file()
    final = installer.assess_project_skills(inputs, registry, ("copilot",))
    assert final.complete
    before = snapshot({"project": project})
    with installer.recheck_project_skills(final):
        assert installer.apply_project_skills(final, consent).outcome == "applied"
    assert not dest.exists() and notes.read_bytes() == b"preserve unknown member"
    assert {(effect.path, effect.action) for effect in net_delta(before, snapshot({"project": project}))} == {
        (effect.path, effect.action) for effect in final.effects
    }


def test_project_owner_refuses_unguarded_and_changed_consent(tmp_path: Path) -> None:
    from specify_cli.skills import installer
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha")
    consent = ApplyConsent(automatic=True)
    assessment = installer.assess_project_skills(
        AssessmentInputs(OperationRoot("project", "project", project), consent=consent), SkillRegistry(tmp_path / "source"), ("claude",)
    )
    before = snapshot({"sandbox": tmp_path})
    assert installer.apply_project_skills(assessment, consent).outcome == "precondition_changed"
    with installer.recheck_project_skills(assessment):
        assert installer.apply_project_skills(assessment, ApplyConsent()).outcome == "skipped"
        assert installer.apply_project_skills(assessment, consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))


def test_real_consumer_uses_one_selected_global_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.runtime import asset_preparation
    from specify_cli.runtime.agent_skills import GlobalSkillSelection
    from specify_cli.skills.manifest import save_manifest
    from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "project"
    project.mkdir()
    alpha = _make_skill(tmp_path / "source", "caller-alpha")
    _make_skill(tmp_path / "source", "caller-beta")
    unknown = home / ".claude/skills/caller-beta/SKILL.md"
    unknown.parent.mkdir(parents=True)
    unknown.write_bytes(b"untracked global user content")
    registry = SkillRegistry(tmp_path / "source")
    calls: list[GlobalSkillSelection] = []
    real_assess = asset_preparation.assess_global_assets

    def observed_assess(
        *,
        runtime: bool = True,
        commands: bool = True,
        skills: bool = True,
        agent_keys: list[str] | None = None,
        skill_selection: GlobalSkillSelection | None = None,
        consent: ApplyConsent = ApplyConsent(),
    ) -> OwnerAssessment:
        assert skill_selection is not None
        calls.append(skill_selection)
        return real_assess(runtime=runtime, commands=commands, skills=skills, agent_keys=agent_keys, skill_selection=skill_selection, consent=consent)

    monkeypatch.setattr(asset_preparation, "assess_global_assets", observed_assess)
    # #4174 landing-pass: apply_skill_installation now re-assesses the global
    # half ONCE more under the held lock whenever the assess it just rechecked
    # actually carries effects (concurrent-peer convergence, see
    # tests/specify_cli/skills/test_installer_global_reassess_convergence.py)
    # -- a cold/drifted install now takes 2 calls (ordinary assess + the
    # re-assess-under-lock), never just 1; a genuinely warm/no-op install
    # still takes exactly 1 (the re-assess is skipped when there is nothing
    # to converge, mirroring the ensure_*() owners' own guard). The invariant
    # this test actually guards -- ONE COHERENT selected batch, never
    # fragmented per-skill/per-caller -- is checked below by requiring every
    # call made to share the correct agent_keys, not a literal call count.
    manifest = install_all_skills(project, ["claude"], registry)
    assert calls and all(call.agent_keys == ("claude",) for call in calls)
    assert len(calls) == 2, "a cold install must take exactly one assess plus one re-assess-under-lock"
    save_manifest(manifest, project)
    assert {entry.skill_name for entry in manifest.entries} == {"caller-alpha", "caller-beta"}
    assert unknown.read_bytes() == b"untracked global user content"
    assert not (home / ".agents").exists()
    global_alpha = home / ".claude/skills/caller-alpha/SKILL.md"
    assert global_alpha.read_bytes() == alpha.skill_md.read_bytes()
    alpha.skill_md.write_bytes(b"---\nname: caller-alpha\n---\nupdated source\n")
    save_manifest(install_all_skills(project, ["claude"], registry), project)
    assert len(calls) == 4, "a drifted (alpha updated) install must also take one assess plus one re-assess-under-lock"
    assert global_alpha.read_bytes() == alpha.skill_md.read_bytes()
    assert (project / ".claude/skills/caller-alpha/SKILL.md").read_bytes() == alpha.skill_md.read_bytes()
    assert unknown.read_bytes() == b"untracked global user content"
    before = snapshot({"sandbox": tmp_path})
    save_manifest(install_all_skills(project, ["claude"], registry), project)
    assert len(calls) == 5, "a genuinely warm/no-op install must take exactly one assess, no re-assess"
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    empty = tmp_path / "empty-source"
    empty.mkdir()
    before_empty = snapshot({"sandbox": tmp_path})
    save_manifest(install_all_skills(project, ["claude"], SkillRegistry(empty)), project)
    save_manifest(install_all_skills(project, [], registry), project)
    assert len(calls) == 7, "each of these two remaining installs also drifts (retiring skills), so each takes one assess plus one re-assess-under-lock"
    assert_unchanged(before_empty, snapshot({"sandbox": tmp_path}))


@pytest.mark.parametrize("all_families", [False, True])
def test_coordinated_skill_installation_exact_delta_and_project_precheck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    all_families: bool,
) -> None:
    from specify_cli.skills import installer
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(home / ".config/opencode"))
    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "caller-alpha", references=["more.md"])
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)
    before = snapshot({"sandbox": tmp_path})
    installation = installer.assess_skill_installation(
        inputs,
        registry,
        ("codex", "copilot"),
        runtime=all_families,
        commands=all_families,
        command_agent_keys=["claude"],
    )
    assert installation.global_assets.complete and installation.project_skills.complete
    assert_unchanged(before, snapshot({"sandbox": tmp_path}))
    results = installer.apply_skill_installation(installation, consent)
    assert all(result.outcome == "applied" for result in results), results
    effects = installation.global_assets.effects + installation.project_skills.effects
    expected = {
        (effect.destination.relative_to(tmp_path).as_posix(), effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
        for effect in effects
    }
    actual = {
        (effect.path, effect.action, effect.after.kind, effect.after.sha256, effect.after.target, effect.after.mode)
        for effect in net_delta(before, snapshot({"sandbox": tmp_path}))
    }
    assert actual == expected
    assert {effect.id for effect in effects} == {effect_id for result in results for effect_id in result.succeeded}
    if all_families:
        assert (home / ".kittify/cache/runtime_bootstrap-assets.json").is_file()
        assert (home / ".kittify/cache/slash_commands-assets.json").is_file()
        assert (home / ".kittify/cache/global_skills-assets.json").is_file()
    source = tmp_path / "source/caller-alpha/SKILL.md"
    source.write_bytes(b"new source")
    changed = installer.assess_skill_installation(inputs, registry, ("codex", "copilot"))
    (project / ".agents/skills/caller-alpha/references/more.md").unlink()
    current = snapshot({"sandbox": tmp_path})
    refused = installer.apply_skill_installation(changed, consent)
    assert all(result.outcome == "precondition_changed" for result in refused)
    assert_unchanged(current, snapshot({"sandbox": tmp_path}))


def test_backup_member_windows_fchmod_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no ``os.fchmod``): the archived-backup write still applies mode.

    Before the fix ``_archive_existing_path`` raised ``AttributeError:
    module 'os' has no attribute 'fchmod'`` on a platform without the
    syscall.
    """
    import os

    from specify_cli.skills.installer import _archive_existing_path

    monkeypatch.delattr(os, "fchmod", raising=False)
    dest = tmp_path / ".claude/skills/sample/SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"original content")
    dest.chmod(0o640)

    root = _archive_existing_path(dest, tmp_path, None)

    retained = root / dest.relative_to(tmp_path)
    assert retained.read_bytes() == b"original content"
    assert stat.S_IMODE(retained.stat().st_mode) == 0o640
    assert not dest.exists()


def test_apply_project_skill_write_windows_fchmod_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows: creating a new project skill file applies mode via fallback.

    Exercises ``_apply_project_skill_write``'s create branch (installer.py
    site #918), which previously called ``os.fchmod`` unconditionally.
    """
    import os

    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    monkeypatch.delattr(os, "fchmod", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)

    assessment = assess_project_skills(inputs, registry, ("claude",))
    assert assessment.complete, assessment.diagnostics
    with recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics
        result = apply_project_skills(assessment, consent)

    assert result.outcome == "applied", result
    written = project / ".claude/skills/alpha/SKILL.md"
    assert written.is_file()
    expected_mode = next(e.after.mode for e in assessment.effects if e.path == ".claude/skills/alpha/SKILL.md")
    assert expected_mode is not None
    assert stat.S_IMODE(written.stat().st_mode) == expected_mode


def test_command_parent_receipts_host_aware_dir_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Twin-gate (#4776/NFR-003): installer._command_parent_receipts is host-aware.

    A freshly-created shared parent whose only divergence from the plan is a
    host-unrepresentable POSIX mode (Windows) is accepted so the doctrine apply
    converges; on a POSIX host the same mode divergence is genuine drift and the
    receipt check STILL refuses. Mirrors the managed_skills :179 relaxation via
    the shared kernel.paths.is_windows()-gated helper.
    """
    from kernel import paths as kernel_paths
    from specify_cli.skills import installer
    from specify_cli.skills.paths import observe_skill_path
    from specify_cli.tool_surface.operations import (
        FileState,
        OperationRoot,
        OwnerAssessment,
        OwnershipProof,
        PhysicalEffect,
    )

    root = OperationRoot("project", "project", tmp_path)
    parent = tmp_path / ".agents" / "skills"
    parent.mkdir(parents=True)
    parent.chmod(0o700)
    receipt = observe_skill_path(parent)
    assert receipt.state.kind == "directory" and receipt.state.mode == 0o700 and receipt.identity is not None
    effect = PhysicalEffect(
        "command_skills",
        "surface_repair",
        root,
        ".agents/skills",
        "create",
        FileState("absent"),
        FileState("directory", mode=0o755),
        "create shared parent",
        (OwnershipProof("managed_path", "parent:.agents/skills"),),
        ("command_skills",),
    )
    assessment = OwnerAssessment("command_skills", root, (effect,))

    # POSIX host: 0o700 vs planned 0o755 is real drift -> refuse (NFR-003).
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    with installer._completed_command_parents(assessment, (receipt,)), pytest.raises(ValueError, match="Invalid command-created skill parent"):
        installer._command_parent_receipts(assessment)

    # Windows host: the same divergence is host-inherent -> accepted (FR-006).
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    with installer._completed_command_parents(assessment, (receipt,)):
        result = installer._command_parent_receipts(assessment)
    assert set(result) == {parent}


# ── #4923: follow_symlinks=False crash class (T003) ─────────────────────
#
# On a host lacking follow_symlinks support (Windows for both chmod/utime;
# Linux already for chmod on a symlink), the pre-fix code passes the flag
# unconditionally and raises NotImplementedError. These tests patch
# Path.chmod / os.utime to raise deterministically when follow_symlinks=False
# is requested -- proving the crash through the real, pre-existing entry
# point (`_apply_project_skill_write` / `_archive_existing_path`), never a
# no-op mock that would mask it (DIRECTIVE_041).


def _install_raise_on_no_follow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make chmod/utime raise exactly like an unsupported host, for any caller."""
    real_chmod = Path.chmod

    def chmod_guard(self: Path, mode: int, *, follow_symlinks: bool = True) -> None:
        if not follow_symlinks:
            raise NotImplementedError("chmod: follow_symlinks unavailable on this platform")
        real_chmod(self, mode)

    real_utime = os.utime

    def utime_guard(path: object, *args: object, **kwargs: object) -> None:
        if kwargs.get("follow_symlinks") is False:
            raise NotImplementedError("utime: follow_symlinks unavailable on this platform")
        real_utime(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "chmod", chmod_guard)
    monkeypatch.setattr(os, "utime", utime_guard)


def test_apply_project_skill_write_symlink_chmod_survives_unsupported_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4923 (installer.py:969): the symlink mode-fix chmod must not crash.

    A freshly created symlink always lands at the filesystem's fixed link
    mode, so a planned mode that differs (0o600 here) drives the mode-fix
    branch -- a real, non-suppressed vector (Phase B only removes the
    :963 file-chmod vector, not this one). Pre-fix this raised
    ``NotImplementedError`` on a host lacking ``follow_symlinks`` support;
    post-fix ``chmod_no_follow`` falls back to a default-follow chmod there.
    """
    from specify_cli.skills.installer import PreparedProjectSkillWrite, _apply_project_skill_write
    from specify_cli.tool_surface.operations import FileState, OperationRoot, OwnershipProof, PhysicalEffect

    _install_raise_on_no_follow(monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    (project / "target.md").write_text("target\n", encoding="utf-8")
    root = OperationRoot("project", "project", project)
    effect = PhysicalEffect(
        "managed_skills",
        "surface_repair",
        root,
        "link.md",
        "create",
        FileState("absent"),
        FileState("symlink", target="target.md", mode=0o600),
        "test symlink create",
        (OwnershipProof("managed_path", "managed-skills:link.md"),),
        ("managed_skills",),
    )

    _apply_project_skill_write(PreparedProjectSkillWrite(effect, None, 1))

    assert (project / "link.md").is_symlink()


def test_apply_project_skill_write_file_utime_survives_unsupported_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4923 (installer.py:981): applying a carried mtime must not crash.

    An ordinary reconcile write carries ``after.mtime_ns=None`` and never
    reaches line 981; a backup-restore write (``after`` copies the replaced
    file's real ``before`` state, mtime included) does. This reproduces that
    mtime-carrying shape directly against the real write function. Pre-fix
    this raised ``NotImplementedError`` on a host lacking ``follow_symlinks``
    support; post-fix ``utime_no_follow`` falls back to a plain ``os.utime``
    call there.
    """
    from specify_cli.skills.installer import PreparedProjectSkillWrite, _apply_project_skill_write
    from specify_cli.tool_surface.operations import FileState, OperationRoot, OwnershipProof, PhysicalEffect

    _install_raise_on_no_follow(monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    root = OperationRoot("project", "project", project)
    effect = PhysicalEffect(
        "managed_skills",
        "surface_repair",
        root,
        "restored.md",
        "create",
        FileState("absent"),
        FileState("file", sha256="a" * 64, mode=0o644, mtime_ns=1_700_000_000_000_000_000),
        "test backup-restore create carrying mtime",
        (OwnershipProof("managed_path", "managed-skills:restored.md"),),
        ("managed_skills",),
    )

    _apply_project_skill_write(PreparedProjectSkillWrite(effect, b"content", 1))

    assert (project / "restored.md").read_bytes() == b"content"


def test_archive_existing_symlink_chmod_survives_unsupported_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4923 (installer.py:172): the symlink-backup chmod must not crash.

    ``_archive_existing_path`` is the other symlink-backup entry point (used
    when retaining an unowned file before an overwrite). Force the observed
    "before" mode to diverge from the freshly created backup link's real
    mode, so the chmod guard actually fires. Pre-fix this raised
    ``NotImplementedError`` on a host lacking ``follow_symlinks`` support;
    post-fix ``chmod_no_follow`` falls back to a default-follow chmod there.
    """
    from specify_cli.skills import paths as skills_paths
    from specify_cli.skills.installer import _archive_existing_path
    from specify_cli.skills.paths import SkillPathObservation

    project = tmp_path / "project"
    dest = project / ".agents" / "skills" / "my-skill" / "LINK.md"
    dest.parent.mkdir(parents=True)
    target = tmp_path / "target.md"
    target.write_text("target\n", encoding="utf-8")
    dest.symlink_to(target)

    real_observe = skills_paths.observe_skill_path

    def forced_mode_observe(path: Path, *, members: bool = False) -> SkillPathObservation:
        observation = real_observe(path, members=members)
        if path == dest and observation.state.kind == "symlink":
            return SkillPathObservation(observation.path, replace(observation.state, mode=0o600), observation.identity, observation.children)
        return observation

    monkeypatch.setattr(skills_paths, "observe_skill_path", forced_mode_observe)
    _install_raise_on_no_follow(monkeypatch)

    _archive_existing_path(dest, project, None)

    assert not dest.exists()


# ── #4927: phantom mode divergence on a converged Windows project (T008) ──


def _install_one_converged_skill(tmp_path: Path) -> tuple[Path, object, object]:
    """Install one canonical skill and return (installed_file, inputs, registry)."""
    from specify_cli.skills.installer import assess_project_skills, apply_project_skills, recheck_project_skills
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    project = tmp_path / "project"
    project.mkdir()
    _make_skill(tmp_path / "source", "alpha")
    registry = SkillRegistry(tmp_path / "source")
    consent = ApplyConsent(automatic=True)
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=consent)

    assessment = assess_project_skills(inputs, registry, ("claude",))
    assert assessment.complete, assessment.diagnostics
    with recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics
        result = apply_project_skills(assessment, consent)
    assert result.outcome == "applied", result

    installed = project / ".claude" / "skills" / "alpha" / "SKILL.md"
    assert installed.is_file()
    return installed, inputs, registry


def test_converged_windows_project_emits_zero_supporting_surface_repairs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4927 (FR-004/006, SC-002): a converged project on simulated Windows must
    report zero repairs, matching a clean `doctor tool-surfaces`.

    Pre-T005/T006 this re-planned a `chmod` effect for the managed file whose
    Windows-observed mode differs from the fixed POSIX plan, even though the
    project is otherwise fully converged; post-fix the divergence is
    recognized as host-inherent and suppressed.
    """
    from kernel import paths as kernel_paths
    from specify_cli.skills.installer import assess_project_skills

    installed, inputs, registry = _install_one_converged_skill(tmp_path)
    # Simulate a Windows-observed mode for the already-installed, converged
    # file: the real host mode is host-representable but differs from the
    # fixed POSIX plan (`_expected_project_entries` strips write bits).
    installed.chmod(0o666)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    next_assessment = assess_project_skills(inputs, registry, ("claude",))

    assert next_assessment.complete, next_assessment.diagnostics
    assert next_assessment.effects == (), next_assessment.effects


def test_posix_genuine_mode_divergence_still_repairs(tmp_path: Path) -> None:
    """FR-007: the exact same divergence on a real POSIX host is still repaired.

    Suppression is strictly host-conditional (NFR-003) -- this pins the
    negative case alongside the T008 positive one above.
    """
    from specify_cli.skills.installer import assess_project_skills

    installed, inputs, registry = _install_one_converged_skill(tmp_path)
    installed.chmod(0o666)

    next_assessment = assess_project_skills(inputs, registry, ("claude",))

    assert next_assessment.complete, next_assessment.diagnostics
    assert any(effect.action == "chmod" for effect in next_assessment.effects), next_assessment.effects


def test_converged_windows_project_stable_across_repeated_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4927 (FR-006): the zero-repair count is stable across repeated dry-runs."""
    from kernel import paths as kernel_paths
    from specify_cli.skills.installer import assess_project_skills

    installed, inputs, registry = _install_one_converged_skill(tmp_path)
    installed.chmod(0o666)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    first = assess_project_skills(inputs, registry, ("claude",))
    second = assess_project_skills(inputs, registry, ("claude",))

    assert first.effects == () and second.effects == (), (first.effects, second.effects)
