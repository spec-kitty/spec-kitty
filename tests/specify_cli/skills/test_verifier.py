"""Tests for skill verification and repair."""

from __future__ import annotations

import os
from pathlib import Path

from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    load_manifest,
    save_manifest,
)
from specify_cli.skills.registry import SkillRegistry
from specify_cli.skills.verifier import VerifyResult, repair_skills, verify_installed_skills


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_wp05_repair_requires_explicit_drift_consent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    entry = _setup_manifest_and_file(project, ".claude/skills/test-skill/SKILL.md", "installed")
    save_manifest(ManagedSkillManifest(entries=[entry]), project)
    dest = project / entry.installed_path
    dest.write_text("user modification")
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": "canonical"})
    result = VerifyResult(ok=False, drifted=[(entry, compute_content_hash(dest))])
    before = dest.read_bytes(), dest.stat().st_mtime_ns
    repaired, failed = repair_skills(project, result, registry)
    assert (dest.read_bytes(), dest.stat().st_mtime_ns) == before
    assert repaired == 0 and failed == 1


def test_wp05_repair_does_not_claim_unknown_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    entry = _make_entry()
    dest = project / entry.installed_path
    dest.mkdir(parents=True)
    (dest / "user-notes").write_bytes(b"unknown")
    save_manifest(ManagedSkillManifest(entries=[entry]), project)
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": "canonical"})
    result = VerifyResult(ok=False, drifted=[(entry, "directory")])
    repaired, failed = repair_skills(project, result, registry)
    assert (dest / "user-notes").read_bytes() == b"unknown"
    assert repaired == 0 and failed == 1


def test_wp05_verification_reports_corruption_and_never_reads_link_targets(tmp_path: Path) -> None:
    target = tmp_path / ".kittify/skills-manifest.json"
    target.parent.mkdir()
    target.write_bytes(b"not a manifest")
    result = verify_installed_skills(tmp_path)
    assert not result.ok and result.errors
    target.unlink()
    entry = _make_entry(delivery_mode="symlink")
    dest = tmp_path / entry.installed_path
    dest.parent.mkdir(parents=True)
    dest.symlink_to(tmp_path / "unknown-target")
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)
    result = verify_installed_skills(tmp_path)
    assert not result.ok and result.drifted[0][0] == entry
    assert result.drifted[0][1].startswith("symlink:")


def _make_entry(
    skill_name: str = "test-skill",
    source_file: str = "SKILL.md",
    installed_path: str = ".claude/skills/test-skill/SKILL.md",
    installation_class: str = "shared-root-capable",
    agent_key: str = "claude",
    content_hash: str = "sha256:abc123",
    installed_at: str = "2026-01-01T00:00:00+00:00",
    delivery_mode: str = "copy",
) -> ManagedFileEntry:
    return ManagedFileEntry(
        skill_name=skill_name,
        source_file=source_file,
        installed_path=installed_path,
        installation_class=installation_class,
        agent_key=agent_key,
        content_hash=content_hash,
        installed_at=installed_at,
        delivery_mode=delivery_mode,
    )


def _setup_manifest_and_file(
    tmp_path: Path,
    installed_path: str,
    content: str,
    skill_name: str = "test-skill",
    source_file: str = "SKILL.md",
) -> ManagedFileEntry:
    """Helper: create a file on disk, compute its hash, save a manifest entry."""
    full = tmp_path / installed_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    h = compute_content_hash(full)
    entry = _make_entry(
        skill_name=skill_name,
        source_file=source_file,
        installed_path=installed_path,
        content_hash=h,
    )
    return entry


def _create_registry(tmp_path: Path, skill_name: str, files: dict[str, str]) -> SkillRegistry:
    """Helper: create a fake registry with a skill containing given files."""
    registry_root = tmp_path / "_registry"
    skill_dir = registry_root / skill_name
    for rel_path, content in files.items():
        fp = skill_dir / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
    return SkillRegistry(registry_root)


# ── verify_installed_skills ──────────────────────────────────────────


def test_verify_no_manifest_returns_ok(tmp_path: Path) -> None:
    """No manifest file → ok=True, no issues."""
    result = verify_installed_skills(tmp_path)
    assert result.ok is True
    assert result.missing == []
    assert result.drifted == []
    assert result.errors == []
    assert result.total_issues == 0


def test_verify_all_files_present_and_matching(tmp_path: Path) -> None:
    """All manifest entries match on disk → ok=True."""
    entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=".claude/skills/test-skill/SKILL.md",
        content="# Test Skill\nHello world.\n",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    result = verify_installed_skills(tmp_path)
    assert result.ok is True
    assert result.missing == []
    assert result.drifted == []
    assert result.total_issues == 0


def test_verify_detects_missing_file(tmp_path: Path) -> None:
    """File referenced in manifest does not exist on disk → missing."""
    entry = _make_entry(
        installed_path=".claude/skills/test-skill/SKILL.md",
        content_hash="sha256:deadbeef",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    result = verify_installed_skills(tmp_path)
    assert result.ok is False
    assert len(result.missing) == 1
    assert result.missing[0].installed_path == ".claude/skills/test-skill/SKILL.md"
    assert result.drifted == []


def test_verify_detects_drifted_file(tmp_path: Path) -> None:
    """File exists but content hash differs → drifted."""
    entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=".claude/skills/test-skill/SKILL.md",
        content="original content",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    # Modify the file after manifest was saved
    modified = tmp_path / ".claude/skills/test-skill/SKILL.md"
    modified.write_text("modified content", encoding="utf-8")

    result = verify_installed_skills(tmp_path)
    assert result.ok is False
    assert result.missing == []
    assert len(result.drifted) == 1
    drifted_entry, actual_hash = result.drifted[0]
    assert drifted_entry.installed_path == ".claude/skills/test-skill/SKILL.md"
    assert actual_hash == compute_content_hash(modified)
    assert actual_hash != entry.content_hash


def test_verify_multiple_issues(tmp_path: Path) -> None:
    """Mix of missing and drifted entries."""
    # Entry 1: will be present and matching
    good_entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=".claude/skills/skill-a/SKILL.md",
        content="good content",
        skill_name="skill-a",
    )
    # Entry 2: will be missing
    missing_entry = _make_entry(
        skill_name="skill-b",
        installed_path=".claude/skills/skill-b/SKILL.md",
        content_hash="sha256:missing",
    )
    # Entry 3: will be drifted
    drifted_entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=".claude/skills/skill-c/SKILL.md",
        content="original",
        skill_name="skill-c",
    )

    manifest = ManagedSkillManifest(entries=[good_entry, missing_entry, drifted_entry])
    save_manifest(manifest, tmp_path)

    # Drift entry 3
    (tmp_path / ".claude/skills/skill-c/SKILL.md").write_text("changed", encoding="utf-8")

    result = verify_installed_skills(tmp_path)
    assert result.ok is False
    assert len(result.missing) == 1
    assert result.missing[0].skill_name == "skill-b"
    assert len(result.drifted) == 1
    assert result.drifted[0][0].skill_name == "skill-c"
    assert result.total_issues == 2


# ── repair_skills ────────────────────────────────────────────────────


def test_repair_restores_missing_file(tmp_path: Path) -> None:
    """Repair copies a missing file from the registry."""
    skill_content = "---\nname: test-skill\n---\n# Test Skill\nCanonical content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": skill_content})

    # Create manifest entry pointing to a file that doesn't exist
    entry = _make_entry(
        skill_name="test-skill",
        source_file="SKILL.md",
        installed_path=".claude/skills/test-skill/SKILL.md",
        content_hash="sha256:stale",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(tmp_path, verify_result, registry)
    assert repaired == 1
    assert failed == 0

    restored = tmp_path / ".claude/skills/test-skill/SKILL.md"
    assert restored.exists()
    assert restored.read_text(encoding="utf-8") == skill_content


def test_repair_restores_drifted_file(tmp_path: Path) -> None:
    """Only exact-path consent permits overwriting modified managed content."""
    from specify_cli.tool_surface.operations import ApplyConsent
    canonical = "---\nname: test-skill\n---\n# Canonical\nCorrect content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    installed_path = ".claude/skills/test-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=installed_path,
        content="old content before drift",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    # Simulate drift
    (tmp_path / installed_path).write_text("user edited this", encoding="utf-8")
    actual_hash = compute_content_hash(tmp_path / installed_path)

    verify_result = VerifyResult(ok=False, drifted=[(entry, actual_hash)])

    assert repair_skills(tmp_path, verify_result, registry) == (0, 1)
    assert (tmp_path / installed_path).read_text() == "user edited this"
    repaired, failed = repair_skills(
        tmp_path, verify_result, registry,
        consent=ApplyConsent(automatic=True, overwrite_paths=(installed_path,)),
    )
    assert repaired == 1
    assert failed == 0

    restored = tmp_path / installed_path
    assert restored.read_text(encoding="utf-8") == canonical


def test_repair_handles_missing_source(tmp_path: Path) -> None:
    """Registry cannot find the skill → counted as failed, not repaired."""
    # Empty registry (no skills)
    registry = SkillRegistry(tmp_path / "_empty_registry")

    entry = _make_entry(
        skill_name="nonexistent-skill",
        installed_path=".claude/skills/nonexistent-skill/SKILL.md",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(tmp_path, verify_result, registry)
    assert repaired == 0
    assert failed == 1


def test_repair_heals_external_symlink_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A symlink at the managed path is replaced with a copy; its target is
    never written (#2412 — repairs always land copies)."""
    canonical = "---\nname: test-skill\n---\n# Canonical\nCorrect content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    external = tmp_path / "home" / ".claude" / "skills" / "test-skill" / "SKILL.md"
    external.parent.mkdir(parents=True, exist_ok=True)
    external.write_text("EXTERNAL", encoding="utf-8")
    monkeypatch.setattr("specify_cli.skills.installer.get_primary_global_skill_root", lambda _agent: external.parent.parent)

    repo = tmp_path / "repo"
    installed_path = ".claude/skills/test-skill/SKILL.md"
    link_path = repo / installed_path
    link_path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(external, link_path)

    entry = _make_entry(
        skill_name="test-skill",
        source_file="SKILL.md",
        installed_path=installed_path,
        content_hash="sha256:stale",
        delivery_mode="symlink",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), repo)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(repo, verify_result, registry)
    assert repaired == 1
    assert failed == 0
    # The security property: the symlink target is never written.
    assert external.read_text(encoding="utf-8") == "EXTERNAL"
    # The link itself is replaced by a real, repo-local copy.
    assert not link_path.is_symlink()
    assert link_path.read_text(encoding="utf-8") == canonical


def test_repair_refuses_external_symlinked_ancestor(tmp_path: Path) -> None:
    """An ancestor directory that symlink-escapes the repo makes every path
    operation act outside the repo — repair must refuse, not heal."""
    canonical = "---\nname: test-skill\n---\n# Canonical\nCorrect content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    external_dir = tmp_path / "home" / "hijacked-skills" / "test-skill"
    external_dir.mkdir(parents=True, exist_ok=True)
    external_file = external_dir / "SKILL.md"
    external_file.write_text("EXTERNAL", encoding="utf-8")

    repo = tmp_path / "repo"
    skills_root = repo / ".claude" / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    # The skill DIRECTORY is a symlink out of the repo.
    os.symlink(external_dir, skills_root / "test-skill", target_is_directory=True)

    entry = _make_entry(
        skill_name="test-skill",
        source_file="SKILL.md",
        installed_path=".claude/skills/test-skill/SKILL.md",
        content_hash="sha256:stale",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), repo)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(repo, verify_result, registry)
    assert repaired == 0
    assert failed == 1
    assert external_file.read_text(encoding="utf-8") == "EXTERNAL"


def test_repair_converts_legacy_symlink_entry_to_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-#2412 manifest entry (delivery_mode=symlink, dangling link on
    disk) repairs to a real copy and the manifest entry flips to copy."""
    canonical = "---\nname: test-skill\n---\n# Canonical\nCorrect content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    repo = tmp_path / "repo"
    installed_path = ".agents/skills/test-skill/SKILL.md"
    dest = repo / installed_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Dangling absolute symlink — the classic dev-container failure mode.
    global_root = tmp_path / "gone-global-root"
    monkeypatch.setattr("specify_cli.skills.installer.get_primary_global_skill_root", lambda _agent: global_root)
    os.symlink(global_root / "test-skill" / "SKILL.md", dest)

    entry = _make_entry(
        skill_name="test-skill",
        source_file="SKILL.md",
        installed_path=installed_path,
        agent_key="codex",
        content_hash="sha256:stale",
        delivery_mode="symlink",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), repo)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(repo, verify_result, registry)
    assert repaired == 1
    assert failed == 0
    assert not dest.is_symlink()
    assert dest.read_text(encoding="utf-8") == canonical

    reloaded = load_manifest(repo)
    assert reloaded is not None
    assert reloaded.entries[0].delivery_mode == "copy"


def test_repair_overwrites_read_only_copy(tmp_path: Path) -> None:
    """Installer-delivered copies inherit the canonical root's read-only
    mode; repair must still be able to replace a drifted one."""
    canonical = "---\nname: test-skill\n---\n# Canonical\nCorrect content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    installed_path = ".claude/skills/test-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path,
        installed_path=installed_path,
        content="drifted content",
    )
    dest = tmp_path / installed_path
    dest.chmod(0o444)
    actual_hash = compute_content_hash(dest)
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    verify_result = VerifyResult(ok=False, drifted=[(entry, actual_hash)])

    repaired, failed = repair_skills(tmp_path, verify_result, registry)
    assert repaired == 1
    assert failed == 0
    assert dest.read_text(encoding="utf-8") == canonical


def test_repair_updates_manifest(tmp_path: Path) -> None:
    """After repair, manifest entries have updated content hashes."""
    canonical = "---\nname: test-skill\n---\n# Canonical\nFresh content.\n"
    registry = _create_registry(tmp_path, "test-skill", {"SKILL.md": canonical})

    entry = _make_entry(
        skill_name="test-skill",
        source_file="SKILL.md",
        installed_path=".claude/skills/test-skill/SKILL.md",
        content_hash="sha256:old-stale-hash",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repair_skills(tmp_path, verify_result, registry)

    # Reload manifest and check hash was updated
    reloaded = load_manifest(tmp_path)
    assert reloaded is not None
    assert len(reloaded.entries) == 1

    # Hash should match the canonical file
    expected_hash = compute_content_hash(tmp_path / ".claude/skills/test-skill/SKILL.md")
    assert reloaded.entries[0].content_hash == expected_hash
    assert reloaded.entries[0].content_hash != "sha256:old-stale-hash"


def test_repair_adds_frontmatter_to_plain_skill(tmp_path: Path) -> None:
    """Repair normalizes plain Markdown SKILL.md files from older generated packs."""
    canonical = "# spec-kitty\n\nGet governance context for an action.\n"
    registry = _create_registry(tmp_path, "spec-kitty", {"SKILL.md": canonical})

    entry = _make_entry(
        skill_name="spec-kitty",
        source_file="SKILL.md",
        installed_path=".agents/skills/spec-kitty/SKILL.md",
        agent_key="codex",
        content_hash="sha256:old-stale-hash",
        delivery_mode="copy",
    )
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(tmp_path, verify_result, registry)
    assert repaired == 1
    assert failed == 0

    restored = tmp_path / ".agents/skills/spec-kitty/SKILL.md"
    content = restored.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "name: spec-kitty\n" in content
    assert "description: Get governance context for an action.\n" in content


def test_verify_rejects_path_traversal(tmp_path: Path) -> None:
    """Manifest entries with path traversal are reported as errors, not followed."""
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    entry = _make_entry(installed_path="../../../etc/passwd")
    manifest = ManagedSkillManifest(entries=[entry])
    save_manifest(manifest, tmp_path)

    result = verify_installed_skills(tmp_path)
    assert not result.ok
    assert len(result.errors) == 1
    assert "Unsafe path" in result.errors[0]


def test_repair_rejects_path_traversal(tmp_path: Path) -> None:
    """Repair refuses to write to paths that escape the project root."""
    registry = SkillRegistry(tmp_path / "_empty_registry")
    entry = _make_entry(installed_path="../../../escaped/evil")
    verify_result = VerifyResult(ok=False, missing=[entry])

    repaired, failed = repair_skills(tmp_path, verify_result, registry)
    assert repaired == 0
    assert failed == 1


def test_find_source_file_rejects_escaping_source_file(tmp_path: Path) -> None:
    """A ``source_file`` that escapes the skill dir is refused, not read (Sonar S2083).

    This is the *source* read vector (the canonical file hashed for drift
    detection), distinct from the ``installed_path`` write vector the two tests
    above cover. The containment is pre-existing and unchanged by this PR:
    ``_find_source_file`` delegates to ``skill_path_observations``, which computes
    ``candidate.relative_to(skill_dir)`` and raises ``ValueError`` on any
    ``..``/``.`` segment or an absolute ``source_file`` (caught here → ``None``).
    This test pins that previously-untested source-read vector: a readable file
    above the skill dir must yield ``None`` even though it exists.
    """
    from specify_cli.skills.verifier import _find_source_file

    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "my-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("ok", encoding="utf-8")
    (skill_dir / "references" / "note.md").write_text("note", encoding="utf-8")
    # A real, readable file one level above the skill dir: skill_dir/../secret.txt.
    (skills_root / "secret.txt").write_text("TOP SECRET", encoding="utf-8")

    # Legitimate in-dir files (flat and nested) still resolve.
    assert _find_source_file(skill_dir, "SKILL.md") == skill_dir / "SKILL.md"
    assert (
        _find_source_file(skill_dir, "references/note.md")
        == skill_dir / "references" / "note.md"
    )

    # An escaping source_file is refused even though the target exists on disk.
    assert _find_source_file(skill_dir, "../secret.txt") is None
    assert _find_source_file(skill_dir, "../../etc/hostname") is None


def test_repair_unsafe_skill_name_never_touches_global_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repair never builds global-root paths from the manifest skill name.

    Pre-#2412, repairing a delivery_mode=symlink entry resynced the global
    root using the skill name as a path segment, so an unsafe name had to be
    rejected. Copy-only repair takes source from the registry (traversal-
    guarded) and dest from installed_path (traversal-guarded); the skill name
    is never a filesystem path, and the global root is never written.
    """
    registry = _create_registry(tmp_path, "..evil", {"SKILL.md": "# bad\n"})
    entry = _make_entry(
        skill_name="..evil",
        installed_path=".claude/skills/..evil/SKILL.md",
        delivery_mode="symlink",
    )
    verify_result = VerifyResult(ok=False, missing=[entry])
    monkeypatch.setattr(
        "specify_cli.skills.verifier.get_primary_global_skill_root",
        lambda _agent_key: tmp_path / "_global",
    )

    repaired, failed = repair_skills(tmp_path, verify_result, registry)

    assert repaired == 1
    assert failed == 0
    # The repaired copy stays inside the repo under the literal dirname...
    dest = tmp_path / ".claude" / "skills" / "..evil" / "SKILL.md"
    assert dest.is_file() and not dest.is_symlink()
    # ...and the global root is never created or written.
    assert not (tmp_path / "_global").exists()


# ── retired-skill reconciliation (#2409) ─────────────────────────────


def _registry_with_kept_skill(tmp_path: Path) -> SkillRegistry:
    """A live registry that positively lacks the retired skill."""
    return _create_registry(
        tmp_path, "kept-skill", {"SKILL.md": "---\nname: kept-skill\n---\n# Kept\n"}
    )


def test_retired_skill_broken_symlink_drained_without_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #2409 loop: a retired skill's projection symlink breaks when the
    global root drops the skill; repair used to warn 'not found in registry'
    on every upgrade and leave the orphan. It must now drain it silently."""
    registry = _registry_with_kept_skill(tmp_path)

    installed_path = ".agents/skills/spk-team-upsun-cli-sync/SKILL.md"
    dest = tmp_path / installed_path
    dest.parent.mkdir(parents=True)
    global_root = tmp_path / "gone-global-root"
    monkeypatch.setattr("specify_cli.skills.installer.get_primary_global_skill_root", lambda agent: global_root)
    dest.symlink_to(global_root / "spk-team-upsun-cli-sync/SKILL.md")  # proven managed, broken

    entry = _make_entry(
        skill_name="spk-team-upsun-cli-sync",
        installed_path=installed_path,
        delivery_mode="symlink",
        agent_key="codex",
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    verify_result = verify_installed_skills(tmp_path)
    assert entry.installed_path in [e.installed_path for e, _ in verify_result.drifted]

    with caplog.at_level("WARNING"):
        repaired, failed = repair_skills(tmp_path, verify_result, registry)

    assert failed == 0
    assert repaired == 1
    assert "not found in registry" not in caplog.text
    assert not dest.is_symlink() and not dest.exists()
    assert not dest.parent.exists(), "emptied skill dir must be pruned"
    manifest = load_manifest(tmp_path)
    assert manifest is not None
    assert manifest.find_by_skill("spk-team-upsun-cli-sync") == []
    # Re-running is a no-op: nothing left to reconcile, still no warning.
    repaired2, failed2 = repair_skills(tmp_path, verify_installed_skills(tmp_path), registry)
    assert (repaired2, failed2) == (0, 0)


def test_retired_skill_clean_copy_removed(tmp_path: Path) -> None:
    """A hash-clean copy-mode file of a retired skill is deleted outright."""
    registry = _registry_with_kept_skill(tmp_path)
    installed_path = ".claude/skills/retired-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path, installed_path, "# Retired\n", skill_name="retired-skill"
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    # Force the repair path with an unrelated missing entry so verify is not ok.
    verify_result = VerifyResult(ok=False, missing=[])
    repaired, failed = repair_skills(tmp_path, verify_result, registry)

    assert (repaired, failed) == (1, 0)
    assert not (tmp_path / installed_path).exists()
    manifest = load_manifest(tmp_path)
    assert manifest is not None
    assert manifest.find_by_skill("retired-skill") == []


def test_retired_skill_modified_copy_archived_not_deleted(tmp_path: Path) -> None:
    """A user-MODIFIED copy of a retired skill is archived, never deleted."""
    registry = _registry_with_kept_skill(tmp_path)
    installed_path = ".claude/skills/retired-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path, installed_path, "# Retired\n", skill_name="retired-skill"
    )
    dest = tmp_path / installed_path
    dest.write_text("# Retired — with my local edits\n", encoding="utf-8")
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    from specify_cli.tool_surface.operations import ApplyConsent

    repaired, failed = repair_skills(tmp_path, VerifyResult(ok=False), registry)
    assert (repaired, failed) == (0, 1)
    assert dest.read_text(encoding="utf-8") == "# Retired — with my local edits\n"
    repaired, failed = repair_skills(tmp_path, VerifyResult(ok=False), registry,
                                     consent=ApplyConsent(automatic=True, overwrite_paths=(installed_path,)))

    assert (repaired, failed) == (1, 0)
    assert not dest.exists()
    backups = list(
        (tmp_path / ".kittify" / ".migration-backup" / "agent-skills").rglob("SKILL.md")
    )
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "# Retired — with my local edits\n"


@pytest.mark.parametrize("absent", [True, False])
def test_empty_registry_never_retires(tmp_path: Path, absent: bool) -> None:
    """An empty registry signals a broken canonical source, not mass
    retirement — the manifest and files must be left untouched."""
    registry = SkillRegistry(tmp_path / "_empty_registry")
    if not absent:
        (tmp_path / "_empty_registry").mkdir()
    installed_path = ".claude/skills/some-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path, installed_path, "# Skill\n", skill_name="some-skill"
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    repaired, failed = repair_skills(tmp_path, VerifyResult(ok=False), registry)

    assert (repaired, failed) == (0, int(absent))
    assert (tmp_path / installed_path).exists()
    manifest = load_manifest(tmp_path)
    assert manifest is not None
    assert len(manifest.find_by_skill("some-skill")) == 1


def test_user_authored_skill_in_projection_root_untouched(tmp_path: Path) -> None:
    """Retirement is manifest-driven: a user-authored skill sharing the
    projection root (absent from the manifest) is never scanned or removed."""
    registry = _registry_with_kept_skill(tmp_path)

    user_skill = tmp_path / ".claude" / "skills" / "my-own-skill" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("# Mine, not spec-kitty's\n", encoding="utf-8")

    retired_path = ".claude/skills/retired-skill/SKILL.md"
    entry = _setup_manifest_and_file(
        tmp_path, retired_path, "# Retired\n", skill_name="retired-skill"
    )
    save_manifest(ManagedSkillManifest(entries=[entry]), tmp_path)

    repaired, failed = repair_skills(tmp_path, VerifyResult(ok=False), registry)

    assert (repaired, failed) == (1, 0)
    assert not (tmp_path / retired_path).exists()
    assert user_skill.exists()
    assert user_skill.read_text(encoding="utf-8") == "# Mine, not spec-kitty's\n"
