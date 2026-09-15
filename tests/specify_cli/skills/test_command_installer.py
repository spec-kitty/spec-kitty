"""Tests for command_installer.py (WP03).

Covers:
- Happy path install (12 SKILL.md files, manifest has 12 entries)
- Idempotent install (second call: already_installed == 12, zero disk writes)
- Reused-shared add (install codex then vibe; agents == ("codex", "vibe"))
- Three-tenant coexistence (NFR-002 load-bearing test)
- Parent-dir preservation (third-party file alongside SKILL.md)
- Collision error (stale manifest entry, on-disk hash mismatch)
- File mutation on remove (InstallerError("file_mutation_detected"))
- verify() drift / orphans / gaps
"""

from __future__ import annotations

import hashlib
import contextlib
import json
import os
import stat
import time
from pathlib import Path

import pytest

from specify_cli.skills.command_installer import (
    CANONICAL_COMMANDS,
    CLI_WRAPPER_COMMANDS,
    PROMPT_BACKED_COMMANDS,
    SUPPORTED_AGENTS,
    InstallReport,
    InstallerError,
    RemoveReport,
    VerifyReport,
    install,
    remove,
    verify,
)
from specify_cli.skills import manifest_store
from specify_cli.skills.manifest_store import ManifestEntry, SkillsManifest
from specify_cli.skills.command_installer import PreparedCommands
from specify_cli.tool_surface.operations import OwnerAssessment
from tests.upgrade.preview_support.snapshot import Snapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_wp04_normalization_does_not_adopt_unknown_content(repo: Path) -> None:
    install(repo, "codex")
    victim = _skill_path(repo, "plan")
    missing = _skill_path(repo, "accept")
    victim.write_bytes(b"operator custom canonical-path content\n")
    missing.unlink()
    manifest = manifest_store.load(repo)
    manifest.remove_path(victim.relative_to(repo).as_posix())
    manifest_store.save(repo, manifest)
    manifest_store.repair_stale_manifest(repo, canonical_commands=list(CANONICAL_COMMANDS))
    with contextlib.suppress(InstallerError):
        install(repo, "codex")
    assert victim.read_bytes() == b"operator custom canonical-path content\n"
    assert manifest_store.load(repo).find(victim.relative_to(repo).as_posix()) is None


@pytest.mark.parametrize("missing_manifest", [False, True])
def test_wp04_normalization_adopts_only_retained_canonical_bytes(repo: Path, missing_manifest: bool) -> None:
    from tests.upgrade.preview_support.snapshot import snapshot, net_delta

    install(repo, "codex")
    path = repo / ".kittify/command-skills-manifest.json"
    if missing_manifest:
        path.unlink()
    else:
        manifest_store.save(repo, SkillsManifest())
        path.chmod(0o400)
    unknown = _skill_path(repo, "plan")
    unknown.write_bytes(b"unknown custom bytes")
    missing = _skill_path(repo, "accept")
    missing.unlink()
    before = snapshot({"project": repo})
    result = manifest_store.repair_stale_manifest(repo, canonical_commands=list(CANONICAL_COMMANDS))
    after = snapshot({"project": repo})
    assert result.changed
    assert len(result.added) == len(CANONICAL_COMMANDS) - 2
    assert {effect.path for effect in net_delta(before, after)} == {".kittify/command-skills-manifest.json"}
    assert unknown.read_bytes() == b"unknown custom bytes"
    assert not missing.exists()
    assert all(entry.agents == ("codex", "vibe") for entry in manifest_store.load(repo).entries)
    if not missing_manifest:
        assert path.stat().st_mode & 0o777 == 0o400


@pytest.mark.parametrize("name", ["spec-kitty.custom", "spec-kitty.plan", "spec-kitty"])
def test_wp04_prefix_is_not_link_ownership(repo: Path, name: str) -> None:
    install(repo, "codex")
    target = repo / "sentinel"
    target.mkdir()
    (target / "keep").write_bytes(b"keep")
    link = repo / ".agents/skills" / name
    if link.exists():
        (link / "SKILL.md").unlink()
        link.rmdir()
        manifest = manifest_store.load(repo)
        manifest.remove_path(f".agents/skills/{name}/SKILL.md")
        manifest_store.save(repo, manifest)
    link.symlink_to(target, target_is_directory=True)
    before = link.lstat()
    manifest_store.remove_unsafe_symlinks(repo)
    assert link.is_symlink(), "An unowned prefixed link was removed"
    assert link.lstat().st_mtime_ns == before.st_mtime_ns
    assert (target / "keep").read_bytes() == b"keep"


def test_wp04_late_collision_rechecked_before_any_write(repo: Path) -> None:
    install(repo, "codex")
    missing = _skill_path(repo, CANONICAL_COMMANDS[0])
    missing.unlink()
    victim = _skill_path(repo, CANONICAL_COMMANDS[-1])
    victim.write_bytes(b"edited owned content")
    with pytest.raises(InstallerError):
        install(repo, "codex")
    assert not missing.exists(), "Installer wrote before checking the whole batch"


def test_wp04_second_install_preserves_manifest_mtime(repo: Path) -> None:
    install(repo, "codex")
    path = repo / ".kittify/command-skills-manifest.json"
    before = path.stat().st_mtime_ns
    install(repo, "codex")
    assert path.stat().st_mtime_ns == before


def test_wp04_assessment_has_no_transient_writes(repo: Path) -> None:
    import sys
    from tests.upgrade.preview_support.write_observer import EVENTS

    events: list[str] = []
    active = True

    def observe(event: str, args: tuple[object, ...]) -> None:
        write_open = event == "open" and isinstance(args[2], int) and bool(args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if active and (event in EVENTS or write_open):
            events.append(event)

    sys.addaudithook(observe)
    try:
        assessment = _wp04_assess(repo)
        assert assessment.complete, assessment.diagnostics
        assert not events, events
        transient = repo / "transient-control"
        transient.write_bytes(b"temporary")
        transient.unlink()
        assert "open" in events and "os.remove" in events
    finally:
        active = False


def test_wp04_clock_resampling_mutant_is_detected(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    original = manifest_store.save_prepared

    def resample(root: Path, encoded: bytes, *, mode: int = 0o644) -> None:
        data = json.loads(encoded)
        for entry in data["entries"]:
            entry["installed_at"] = "2099-01-01T00:00:00+00:00"
        original(root, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode(), mode=mode)

    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo)
    monkeypatch.setattr(manifest_store, "save_prepared", resample)
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    with pytest.raises(AssertionError):
        _wp04_equal_effects(assessment, before, snapshot({"project": repo}))


def _wp04_assess(repo: Path, agents: tuple[str, ...] = ("codex", "vibe")) -> OwnerAssessment:
    from specify_cli.skills.command_installer import prepare_commands
    from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

    inputs = AssessmentInputs(OperationRoot("project", "project", repo), consent=ApplyConsent(automatic=True))
    return prepare_commands(inputs, agents, prune=True)


def _wp04_equal_effects(assessment: OwnerAssessment, before: Snapshot, after: Snapshot) -> None:
    from tests.upgrade.preview_support.snapshot import net_delta

    actual = {(e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in net_delta(before, after)}
    planned = {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in assessment.effects}
    assert actual == planned


def test_wp04_prepared_exact_bytes_shared_owners_and_repeat(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo)
    assert assessment.complete, assessment.diagnostics
    assert_unchanged(before, snapshot({"project": repo}))
    assert len({e.path for e in assessment.effects}) == len(assessment.effects)
    assert any(e.path == ".kittify/command-skills-manifest.json" for e in assessment.effects)
    monkeypatch.setattr(owner, "now_utc_iso", lambda: "2099-01-01T00:00:00+00:00")
    result = owner.apply_commands(assessment, assessment.consent)
    assert result.outcome == "applied", result
    _wp04_equal_effects(assessment, before, snapshot({"project": repo}))
    assert isinstance(assessment.prepared, PreparedCommands)
    assert (repo / ".kittify/command-skills-manifest.json").read_bytes() == assessment.prepared.manifest_bytes
    assert all(e.agents == ("codex", "vibe") for e in manifest_store.load(repo).entries)
    second = _wp04_assess(repo)
    assert second.complete and not second.effects
    before = snapshot({"project": repo})
    assert owner.apply_commands(second, second.consent).outcome == "applied"
    assert_unchanged(before, snapshot({"project": repo}))


@pytest.mark.parametrize("changed", ["manifest", "config", "destination", "parent", "mode", "mtime"])
def test_wp04_changed_batch_refuses_zero_writes(repo: Path, changed: str) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    install(repo, "codex")
    missing = _skill_path(repo, "plan")
    missing.unlink()
    assessment = _wp04_assess(repo)
    assert assessment.complete
    if changed == "manifest":
        path = repo / ".kittify/command-skills-manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif changed == "config":
        path = repo / ".kittify/config.yaml"
        path.write_text(path.read_text() + "# changed\n")
    elif changed == "destination":
        missing.write_bytes(b"racing custom content")
    elif changed == "parent":
        missing.parent.rmdir()
        target = repo / "escape-sentinel"
        target.mkdir()
        missing.parent.symlink_to(target, target_is_directory=True)
    elif changed == "mode":
        _skill_path(repo, "status").chmod(0o400)
    else:
        os.utime(_skill_path(repo, "status"), ns=(1, 1))
    before = snapshot({"project": repo})
    result = owner.apply_commands(assessment, assessment.consent)
    assert result.outcome == "precondition_changed"
    assert not result.succeeded
    assert_unchanged(before, snapshot({"project": repo}))


def test_wp04_drift_and_unknown_preserved_while_gap_repaired(repo: Path) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    drift = _skill_path(repo, "plan")
    drift.write_bytes(b"edited owned command")
    custom = _skill_path(repo, "status")
    custom.write_bytes(b"unknown custom command")
    manifest = manifest_store.load(repo)
    manifest.remove_path(custom.relative_to(repo).as_posix())
    manifest_store.save(repo, manifest)
    missing = _skill_path(repo, "accept")
    missing.unlink()
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo)
    assert assessment.complete
    assert {d.state for d in assessment.dispositions} >= {"preserve", "consent_required"}
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    assert missing.is_file()
    assert drift.read_bytes() == b"edited owned command"
    assert custom.read_bytes() == b"unknown custom command"
    assert manifest_store.load(repo).find(custom.relative_to(repo).as_posix()) is None
    _wp04_equal_effects(assessment, before, snapshot({"project": repo}))


def test_wp04_missing_manifest_adopts_only_canonical_bytes(repo: Path) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    (repo / ".kittify/command-skills-manifest.json").unlink()
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo, ("vibe",))
    assert [e.path for e in assessment.effects] == [".kittify/command-skills-manifest.json"]
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    assert all(e.agents == ("vibe",) for e in manifest_store.load(repo).entries)
    _wp04_equal_effects(assessment, before, snapshot({"project": repo}))


@pytest.mark.parametrize("existing_readonly_manifest", [False, True])
def test_wp04_partial_failure_keeps_truthful_manifest(repo: Path, monkeypatch: pytest.MonkeyPatch, existing_readonly_manifest: bool) -> None:
    from specify_cli.skills import command_installer as owner

    if existing_readonly_manifest:
        manifest_store.save(repo, manifest_store.SkillsManifest())
        (repo / ".kittify/command-skills-manifest.json").chmod(0o400)
    assessment = _wp04_assess(repo)
    original = owner._atomic_write
    calls: list[Path] = []

    def fail_second(path: Path, content: bytes, *, mode: int = 0o644) -> None:
        calls.append(path)
        if len(calls) == 2:
            raise OSError("injected second command failure")
        original(path, content, mode=mode)

    monkeypatch.setattr(owner, "_atomic_write", fail_second)
    result = owner.apply_commands(assessment, assessment.consent)
    assert result.outcome == "partial" and result.failed and result.skipped
    manifest = manifest_store.load(repo)
    assert len(manifest.entries) == 1
    assert manifest.entries[0].agents == ("codex", "vibe")
    assert (repo / manifest.entries[0].path).read_bytes()
    assert not calls[1].exists()
    if existing_readonly_manifest:
        assert (repo / ".kittify/command-skills-manifest.json").stat().st_mode & 0o777 == 0o400


def test_wp04_owned_link_converts_without_touching_target(repo: Path) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    path = _skill_path(repo, "plan")
    target = repo / "target"
    path.rename(target)
    path.symlink_to(target)
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo, ("codex",))
    assert any(e.path == path.relative_to(repo).as_posix() and e.action == "replace" for e in assessment.effects)
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    after = snapshot({"project": repo})
    assert before[("project", "target")] == after[("project", "target")]
    _wp04_equal_effects(assessment, before, after)


@pytest.mark.parametrize("owned", [False, True])
def test_wp04_package_link_exact_ownership(repo: Path, owned: bool) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    path = _skill_path(repo, "plan")
    target = repo / "target-package"
    path.parent.rename(target)
    path.parent.symlink_to(target, target_is_directory=True)
    if not owned:
        manifest = manifest_store.load(repo)
        manifest.remove_path(path.relative_to(repo).as_posix())
        manifest_store.save(repo, manifest)
    _skill_path(repo, "accept").unlink()
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo, ("codex",))
    assert assessment.complete, assessment.diagnostics
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    after = snapshot({"project": repo})
    assert path.parent.is_symlink() is not owned
    assert before[("project", "target-package/SKILL.md")] == after[("project", "target-package/SKILL.md")]
    assert _skill_path(repo, "accept").is_file()
    _wp04_equal_effects(assessment, before, after)


def test_wp04_reused_shared_owner_is_manifest_only(repo: Path) -> None:
    install(repo, "codex")
    assessment = _wp04_assess(repo, ("vibe",))
    assert [e.path for e in assessment.effects] == [".kittify/command-skills-manifest.json"]


def test_wp04_unknown_dangling_link_survives_independent_repair(repo: Path) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    path = _skill_path(repo, "plan")
    path.unlink()
    path.symlink_to(repo / "absent-target")
    manifest = manifest_store.load(repo)
    manifest.remove_path(path.relative_to(repo).as_posix())
    manifest_store.save(repo, manifest)
    _skill_path(repo, "accept").unlink()
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo, ("codex",))
    assert assessment.complete
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    after = snapshot({"project": repo})
    assert before[("project", path.relative_to(repo).as_posix())] == after[("project", path.relative_to(repo).as_posix())]
    assert not (repo / "absent-target").exists()
    _wp04_equal_effects(assessment, before, after)


@pytest.mark.parametrize("change", ["bytes", "selection", "missing"])
def test_wp04_source_changes_refuse_before_writes(repo: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    import shutil
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    templates = repo / "source-templates"
    shutil.copytree(owner._package_templates_dir(), templates)
    monkeypatch.setattr(owner, "_package_templates_dir", lambda: templates)
    assessment = _wp04_assess(repo)
    assert assessment.complete, assessment.diagnostics
    path = templates / "plan/prompt.md"
    if change == "bytes":
        path.write_bytes(path.read_bytes() + b"\nchanged\n")
    elif change == "missing":
        path.unlink()
    else:
        alternative = repo / "alternative-templates"
        shutil.copytree(templates, alternative)
        monkeypatch.setattr(owner, "_package_templates_dir", lambda: alternative)
    before = snapshot({"project": repo})
    assert owner.apply_commands(assessment, assessment.consent).outcome == "precondition_changed"
    assert_unchanged(before, snapshot({"project": repo}))


@pytest.mark.parametrize("state", ["corrupt_manifest", "manifest_link", "bad_config", "missing_template"])
def test_wp04_unreadable_inputs_are_incomplete(repo: Path, monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    if state == "corrupt_manifest":
        (repo / ".kittify/command-skills-manifest.json").write_bytes(b"{")
    elif state == "manifest_link":
        (repo / ".kittify/command-skills-manifest.json").symlink_to(repo / "dangling")
    elif state == "bad_config":
        (repo / ".kittify/config.yaml").write_text("agents: [\n")
    else:
        monkeypatch.setattr(owner, "_package_templates_dir", lambda: repo / "absent-source")
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo)
    assert not assessment.complete and assessment.diagnostics
    assert not assessment.effects
    assert_unchanged(before, snapshot({"project": repo}))


def test_wp04_effect_oracle_detects_omitted_manifest(repo: Path) -> None:
    from dataclasses import replace
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo)
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    after = snapshot({"project": repo})
    _wp04_equal_effects(assessment, before, after)
    omitted = replace(assessment, effects=tuple(e for e in assessment.effects if e.path != ".kittify/command-skills-manifest.json"))
    with pytest.raises(AssertionError):
        _wp04_equal_effects(omitted, before, after)


def test_wp04_recheck_bypass_is_detected(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_installer as owner

    monkeypatch.setattr(owner, "recheck_commands", lambda assessment, **phase: ())
    with pytest.raises(AssertionError):
        test_wp04_changed_batch_refuses_zero_writes(repo, "manifest")


def test_wp04_readonly_modes_and_temp_collision(repo: Path) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    install(repo, "codex")
    path = _skill_path(repo, "plan")
    path.chmod(0o400)
    manifest_path = repo / ".kittify/command-skills-manifest.json"
    manifest_path.chmod(0o400)
    assessment = _wp04_assess(repo)
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    assert stat.S_IMODE(path.stat().st_mode) == 0o400
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o400
    path.unlink()
    temp = path.with_suffix(".md.tmp")
    temp.write_bytes(b"unowned temporary-path occupant")
    before = snapshot({"project": repo})
    assert not _wp04_assess(repo).complete
    assert_unchanged(before, snapshot({"project": repo}))


def test_wp04_pruning_includes_empty_directory_and_preserves_shared_owner(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills import command_installer as owner
    from tests.upgrade.preview_support.snapshot import snapshot

    install(repo, "codex")
    install(repo, "vibe")
    monkeypatch.setattr(owner, "CANONICAL_COMMANDS", ())
    assessment = _wp04_assess(repo, ("codex",))
    assert [e.path for e in assessment.effects] == [".kittify/command-skills-manifest.json"]
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    assert all(e.agents == ("vibe",) for e in manifest_store.load(repo).entries)
    before = snapshot({"project": repo})
    assessment = _wp04_assess(repo, ("vibe",))
    assert any(e.before.kind == "directory" and e.action == "delete" for e in assessment.effects)
    assert owner.apply_commands(assessment, assessment.consent).outcome == "applied"
    _wp04_equal_effects(assessment, before, snapshot({"project": repo}))


_TEMPLATE_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # tests/specify_cli/skills/../../.. → repo root


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 — skills installer content fingerprint (raw SHA-256 by definition), not charter freshness


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _write_config(repo_root: Path) -> None:
    """Write a minimal .kittify/config.yaml so agent config checks pass."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - codex\n    - vibe\n",
        encoding="utf-8",
    )


def _skill_path(repo_root: Path, command: str) -> Path:
    return repo_root / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal project root with .kittify/ ready.

    Templates are located inside the installed ``specify_cli`` package via
    ``_package_templates_dir()``; a real user project never contains
    ``src/specify_cli/missions/`` under its own root, so we deliberately
    do **not** seed that path here. If a test fails because templates cannot
    be located, the production code — not the fixture — is the suspect.
    """
    _write_config(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Happy path install
# ---------------------------------------------------------------------------


class TestHappyPathInstall:
    def test_creates_all_skill_md_files(self, repo: Path) -> None:
        report = install(repo, "vibe")

        for command in CANONICAL_COMMANDS:
            path = _skill_path(repo, command)
            assert path.exists(), f"Expected SKILL.md for command {command!r}"

    def test_install_report_has_11_added(self, repo: Path) -> None:
        report = install(repo, "vibe")

        assert len(report.added) == len(CANONICAL_COMMANDS)
        assert report.already_installed == []
        assert report.reused_shared == []
        assert report.errors == []

    def test_manifest_has_11_entries(self, repo: Path) -> None:
        install(repo, "vibe")

        manifest = manifest_store.load(repo)
        assert len(manifest.entries) == len(CANONICAL_COMMANDS)

    def test_manifest_entries_have_correct_agent(self, repo: Path) -> None:
        install(repo, "vibe")

        manifest = manifest_store.load(repo)
        for entry in manifest.entries:
            assert entry.agents == ("vibe",), f"Entry {entry.path!r} has unexpected agents {entry.agents!r}"

    @pytest.mark.parametrize("agent_key", ["pi", "letta"])
    def test_new_command_skill_agents_install_manifest_entries(self, repo: Path, agent_key: str) -> None:
        report = install(repo, agent_key)

        assert len(report.added) == len(CANONICAL_COMMANDS)
        manifest = manifest_store.load(repo)
        assert len(manifest.entries) == len(CANONICAL_COMMANDS)
        for entry in manifest.entries:
            assert entry.agents == (agent_key,)

    def test_manifest_entries_have_correct_paths(self, repo: Path) -> None:
        install(repo, "vibe")

        manifest = manifest_store.load(repo)
        paths = {e.path for e in manifest.entries}
        expected = {f".agents/skills/spec-kitty.{cmd}/SKILL.md" for cmd in CANONICAL_COMMANDS}
        assert paths == expected

    def test_content_hash_matches_disk(self, repo: Path) -> None:
        install(repo, "vibe")

        manifest = manifest_store.load(repo)
        for entry in manifest.entries:
            disk_hash = _sha256_file(repo / entry.path)
            assert disk_hash == entry.content_hash, f"Hash mismatch for {entry.path!r}"

    def test_skill_md_has_frontmatter(self, repo: Path) -> None:
        install(repo, "vibe")

        skill_path = _skill_path(repo, "specify")
        content = skill_path.read_text(encoding="utf-8")
        assert content.startswith("---\n"), "SKILL.md should start with YAML frontmatter"
        assert "name: spec-kitty.specify" in content


# ---------------------------------------------------------------------------
# Idempotent install
# ---------------------------------------------------------------------------


class TestIdempotentInstall:
    def test_second_call_reports_already_installed(self, repo: Path) -> None:
        install(repo, "vibe")
        report2 = install(repo, "vibe")

        assert len(report2.already_installed) == len(CANONICAL_COMMANDS)
        assert report2.added == []
        assert report2.reused_shared == []

    def test_second_call_does_not_change_file_content(self, repo: Path) -> None:
        install(repo, "vibe")

        # Capture file hashes after first install.
        hashes_before: dict[str, str] = {}
        for cmd in CANONICAL_COMMANDS:
            p = _skill_path(repo, cmd)
            hashes_before[cmd] = _sha256_file(p)

        install(repo, "vibe")

        for cmd in CANONICAL_COMMANDS:
            p = _skill_path(repo, cmd)
            assert _sha256_file(p) == hashes_before[cmd], f"File content changed on second install for {cmd!r}"

    def test_second_call_does_not_change_manifest(self, repo: Path) -> None:
        install(repo, "vibe")
        manifest_path = repo / ".kittify" / "command-skills-manifest.json"
        content_after_first = manifest_path.read_bytes()

        install(repo, "vibe")
        content_after_second = manifest_path.read_bytes()

        assert content_after_first == content_after_second, "Manifest changed on idempotent install"

    def test_second_call_no_disk_writes(self, repo: Path) -> None:
        install(repo, "vibe")

        # Capture mtimes.
        mtimes_before: dict[str, float] = {}
        for cmd in CANONICAL_COMMANDS:
            p = _skill_path(repo, cmd)
            mtimes_before[cmd] = p.stat().st_mtime

        # Small delay to make mtime changes detectable on coarse-resolution FSes.
        time.sleep(0.01)
        install(repo, "vibe")

        for cmd in CANONICAL_COMMANDS:
            p = _skill_path(repo, cmd)
            assert p.stat().st_mtime == mtimes_before[cmd], f"File mtime changed (unexpected write) for {cmd!r}"

    def test_second_call_repairs_missing_manifest_entry_file(self, repo: Path) -> None:
        install(repo, "vibe")
        skill_path = _skill_path(repo, "tasks")
        rel_path = ".agents/skills/spec-kitty.tasks/SKILL.md"
        skill_path.unlink()

        report = install(repo, "vibe")

        assert skill_path.exists()
        assert rel_path in report.added
        assert rel_path not in report.already_installed
        assert verify(repo).gaps == []


# ---------------------------------------------------------------------------
# Reused-shared (two agents, one set of files)
# ---------------------------------------------------------------------------


class TestReusedShared:
    def test_second_agent_reported_as_reused_shared(self, repo: Path) -> None:
        install(repo, "codex")
        report2 = install(repo, "vibe")

        assert len(report2.reused_shared) == len(CANONICAL_COMMANDS)
        assert report2.added == []
        assert report2.already_installed == []

    def test_manifest_entries_have_both_agents(self, repo: Path) -> None:
        install(repo, "codex")
        install(repo, "vibe")

        manifest = manifest_store.load(repo)
        for entry in manifest.entries:
            assert entry.agents == ("codex", "vibe"), f"Entry {entry.path!r} has unexpected agents {entry.agents!r}"

    def test_file_bytes_unchanged_after_second_agent(self, repo: Path) -> None:
        install(repo, "codex")

        hashes_after_codex: dict[str, str] = {}
        for cmd in CANONICAL_COMMANDS:
            hashes_after_codex[cmd] = _sha256_file(_skill_path(repo, cmd))

        install(repo, "vibe")

        for cmd in CANONICAL_COMMANDS:
            assert _sha256_file(_skill_path(repo, cmd)) == hashes_after_codex[cmd], f"File bytes changed when adding vibe to {cmd!r}"


# ---------------------------------------------------------------------------
# Three-tenant coexistence (NFR-002 — the load-bearing test)
# ---------------------------------------------------------------------------


class TestThreeTenantCoexistence:
    """Third-party dirs under .agents/skills/ must survive the full
    install(codex) + install(vibe) + remove(codex) + remove(vibe) lifecycle
    byte-for-byte unchanged."""

    def _setup_third_party_files(self, repo: Path) -> dict[str, str]:
        """Seed three third-party entries and return {rel_path: sha256}."""
        skills_root = repo / ".agents" / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)

        files: dict[Path, bytes] = {
            skills_root / "handwritten-review" / "SKILL.md": (b"# handwritten review\nThis is a hand-crafted review skill.\nContents: detailed review steps.\n"),
            skills_root / "another-tool.lint" / "SKILL.md": (b"# another-tool lint\nLinting workflow from another tool.\nDo not delete me!\n"),
            skills_root / "my-stuff" / "other-file.txt": (b"This is my personal notes file.\nKeep it here forever.\n"),
        }

        result: dict[str, str] = {}
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            rel = str(path.relative_to(repo)).replace("\\", "/")
            result[rel] = _sha256(content)

        return result

    def _assert_third_party_unchanged(self, repo: Path, expected: dict[str, str], step: str) -> None:
        for rel_path, expected_hash in expected.items():
            abs_path = repo / rel_path
            assert abs_path.exists(), f"[{step}] Third-party file missing: {rel_path!r}"
            actual_hash = _sha256_file(abs_path)
            assert actual_hash == expected_hash, (
                f"[{step}] Third-party file mutated: {rel_path!r}\n  expected SHA-256: {expected_hash}\n  actual  SHA-256: {actual_hash}"
            )

    def test_full_lifecycle_preserves_third_party_files(self, repo: Path) -> None:
        third_party_hashes = self._setup_third_party_files(repo)

        # Step 1: install codex
        install(repo, "codex")
        self._assert_third_party_unchanged(repo, third_party_hashes, "after install(codex)")

        # Step 2: install vibe
        install(repo, "vibe")
        self._assert_third_party_unchanged(repo, third_party_hashes, "after install(vibe)")

        # Step 3: remove codex
        remove(repo, "codex")
        self._assert_third_party_unchanged(repo, third_party_hashes, "after remove(codex)")

        # Step 4: remove vibe
        remove(repo, "vibe")
        self._assert_third_party_unchanged(repo, third_party_hashes, "after remove(vibe)")

    def test_spec_kitty_files_gone_after_full_remove(self, repo: Path) -> None:
        self._setup_third_party_files(repo)
        install(repo, "codex")
        install(repo, "vibe")
        remove(repo, "codex")
        remove(repo, "vibe")

        for cmd in CANONICAL_COMMANDS:
            path = _skill_path(repo, cmd)
            assert not path.exists(), f"spec-kitty skill file should be deleted: {path}"

    def test_manifest_empty_after_full_remove(self, repo: Path) -> None:
        self._setup_third_party_files(repo)
        install(repo, "codex")
        install(repo, "vibe")
        remove(repo, "codex")
        remove(repo, "vibe")

        manifest = manifest_store.load(repo)
        assert manifest.entries == [], f"Manifest should be empty after full remove, got: {manifest.entries!r}"

    def test_spec_kitty_dirs_gone_after_full_remove(self, repo: Path) -> None:
        self._setup_third_party_files(repo)
        install(repo, "codex")
        install(repo, "vibe")
        remove(repo, "codex")
        remove(repo, "vibe")

        skills_root = repo / ".agents" / "skills"
        if skills_root.exists():
            remaining = [d.name for d in skills_root.iterdir() if d.is_dir() and d.name.startswith("spec-kitty.")]
            assert remaining == [], f"spec-kitty.* directories should be gone, found: {remaining!r}"

    def test_third_party_dirs_still_present_after_full_remove(self, repo: Path) -> None:
        self._setup_third_party_files(repo)
        install(repo, "codex")
        install(repo, "vibe")
        remove(repo, "codex")
        remove(repo, "vibe")

        skills_root = repo / ".agents" / "skills"
        assert (skills_root / "handwritten-review" / "SKILL.md").exists()
        assert (skills_root / "another-tool.lint" / "SKILL.md").exists()
        assert (skills_root / "my-stuff" / "other-file.txt").exists()


# ---------------------------------------------------------------------------
# Parent-dir preservation
# ---------------------------------------------------------------------------


class TestParentDirPreservation:
    """When a third-party file exists inside a spec-kitty.* dir, remove()
    must delete SKILL.md (if agents empties) but leave the dir and the
    third-party file intact."""

    def test_remove_deletes_skill_md_but_keeps_extra_file(self, repo: Path) -> None:
        install(repo, "vibe")

        # Place a third-party file inside a spec-kitty.specify dir.
        specify_dir = repo / ".agents" / "skills" / "spec-kitty.specify"
        extra_file = specify_dir / "extra.txt"
        extra_file.write_bytes(b"User-authored content.\n")
        extra_hash = _sha256_file(extra_file)

        remove(repo, "vibe")

        # SKILL.md should be gone.
        skill_path = specify_dir / "SKILL.md"
        assert not skill_path.exists(), "SKILL.md should have been deleted"

        # extra.txt must survive byte-identical.
        assert extra_file.exists(), "Third-party extra.txt must not be deleted"
        assert _sha256_file(extra_file) == extra_hash, "extra.txt was mutated"

        # The parent dir must stay (it contains extra.txt).
        assert specify_dir.exists(), "Parent dir must be preserved when non-empty"

    def test_remove_deletes_empty_parent_dir(self, repo: Path) -> None:
        """When no third-party files exist, the parent dir should be removed."""
        install(repo, "vibe")

        # Verify SKILL.md and its parent exist before remove.
        specify_dir = repo / ".agents" / "skills" / "spec-kitty.specify"
        assert specify_dir.exists()

        remove(repo, "vibe")

        # The parent dir should be gone (it was empty after SKILL.md deletion).
        assert not specify_dir.exists(), "Empty spec-kitty.specify/ dir should be removed"


# ---------------------------------------------------------------------------
# Collision error
# ---------------------------------------------------------------------------


class TestCollisionError:
    def test_unmanaged_canonical_file_is_not_overwritten(self, repo: Path) -> None:
        skill_path = _skill_path(repo, "analyze")
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_bytes(b"CUSTOM LOCAL SKILL\n")

        with pytest.raises(InstallerError) as exc_info:
            install(repo, "codex")

        assert exc_info.value.code == "unexpected_collision"
        assert skill_path.read_bytes() == b"CUSTOM LOCAL SKILL\n"

    def test_unexpected_collision_raised_when_disk_hash_differs(self, repo: Path) -> None:
        """Seed a stale manifest entry; install() should raise unexpected_collision."""
        # Build a manifest with a stale entry (wrong hash) pointing to a real path.
        kittify = repo / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        rel_path = ".agents/skills/spec-kitty.specify/SKILL.md"
        abs_path = repo / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(b"# stale content\n")

        stale_hash = "a" * 64  # obviously wrong SHA-256
        stale_entry = ManifestEntry(
            path=rel_path,
            content_hash=stale_hash,
            agents=("vibe",),
            installed_at="2024-01-01T00:00:00+00:00",
            spec_kitty_version="0.0.1",
        )
        manifest = SkillsManifest(entries=[stale_entry])
        manifest_store.save(repo, manifest)

        with pytest.raises(InstallerError) as exc_info:
            install(repo, "vibe")

        assert exc_info.value.code == "unexpected_collision"
        assert exc_info.value.context.get("path") == rel_path


# ---------------------------------------------------------------------------
# File mutation on remove
# ---------------------------------------------------------------------------


class TestFileMutationOnRemove:
    def test_file_mutation_detected_error_raised(self, repo: Path) -> None:
        install(repo, "vibe")

        # Edit the SKILL.md by hand to simulate drift.
        skill_path = _skill_path(repo, "specify")
        original_content = skill_path.read_bytes()
        skill_path.write_bytes(original_content + b"\n# injected line\n")

        with pytest.raises(InstallerError) as exc_info:
            remove(repo, "vibe")

        assert exc_info.value.code == "file_mutation_detected"
        assert ".agents/skills/spec-kitty.specify/SKILL.md" in (exc_info.value.context.get("path", ""))

    def test_manifest_unchanged_when_mutation_detected(self, repo: Path) -> None:
        install(repo, "vibe")

        manifest_path = repo / ".kittify" / "command-skills-manifest.json"
        manifest_before = manifest_path.read_bytes()

        # Mutate the first command's SKILL.md.
        first_cmd = CANONICAL_COMMANDS[0]
        skill_path = _skill_path(repo, first_cmd)
        skill_path.write_bytes(skill_path.read_bytes() + b"\n# mutated\n")

        with pytest.raises(InstallerError):
            remove(repo, "vibe")

        assert manifest_path.read_bytes() == manifest_before, "Manifest must not be modified when file_mutation_detected is raised"


class TestPathConfinement:
    def test_install_rejects_symlinked_managed_path(self, repo: Path) -> None:
        outside = repo.parent / f"{repo.name}-outside-install"
        outside.mkdir()
        protected = outside / "SKILL.md"
        protected.write_bytes(b"DO_NOT_OVERWRITE\n")
        skills_root = repo / ".agents" / "skills"
        skills_root.mkdir(parents=True)
        (skills_root / "spec-kitty.analyze").symlink_to(outside, target_is_directory=True)

        with pytest.raises(InstallerError) as exc_info:
            install(repo, "codex")

        assert exc_info.value.code == "unsafe_path"
        assert protected.read_bytes() == b"DO_NOT_OVERWRITE\n"

    def test_remove_rejects_symlinked_managed_path(self, repo: Path) -> None:
        install(repo, "codex")
        skill_path = _skill_path(repo, "analyze")
        original = skill_path.read_bytes()
        skill_path.unlink()
        skill_path.parent.rmdir()
        outside = repo.parent / f"{repo.name}-outside-remove"
        outside.mkdir()
        protected = outside / "SKILL.md"
        protected.write_bytes(original)
        skill_path.parent.symlink_to(outside, target_is_directory=True)

        with pytest.raises(InstallerError) as exc_info:
            remove(repo, "codex")

        assert exc_info.value.code == "unsafe_path"
        assert protected.read_bytes() == original


# ---------------------------------------------------------------------------
# verify() — drift, gaps, orphans (T017)
# ---------------------------------------------------------------------------


class TestVerifyDrift:
    def test_clean_install_has_no_drift(self, repo: Path) -> None:
        install(repo, "vibe")
        report = verify(repo)

        assert report.drift == []
        assert report.orphans == []
        assert report.gaps == []

    def test_mutated_file_reported_as_drift(self, repo: Path) -> None:
        install(repo, "vibe")

        # Mutate one SKILL.md.
        skill_path = _skill_path(repo, "specify")
        skill_path.write_bytes(skill_path.read_bytes() + b"\n# drifted\n")

        report = verify(repo)

        assert ".agents/skills/spec-kitty.specify/SKILL.md" in report.drift
        assert report.gaps == []
        assert report.orphans == []

    def test_verify_does_not_modify_disk(self, repo: Path) -> None:
        install(repo, "vibe")
        skill_path = _skill_path(repo, "specify")
        skill_path.write_bytes(skill_path.read_bytes() + b"\n# drifted\n")
        content_before = skill_path.read_bytes()

        verify(repo)

        assert skill_path.read_bytes() == content_before, "verify() must not modify files on disk"


class TestVerifyGaps:
    def test_deleted_file_reported_as_gap(self, repo: Path) -> None:
        install(repo, "vibe")

        # Delete one SKILL.md.
        skill_path = _skill_path(repo, "tasks")
        skill_path.unlink()

        report = verify(repo)

        assert ".agents/skills/spec-kitty.tasks/SKILL.md" in report.gaps
        assert report.drift == []
        assert report.orphans == []

    def test_verify_does_not_recreate_missing_file(self, repo: Path) -> None:
        install(repo, "vibe")
        skill_path = _skill_path(repo, "tasks")
        skill_path.unlink()

        verify(repo)

        assert not skill_path.exists(), "verify() must not write missing files"


class TestVerifyOrphans:
    def test_unregistered_spec_kitty_file_is_orphan(self, repo: Path) -> None:
        # Write a spec-kitty.* file without registering it in the manifest.
        orphan_path = repo / ".agents" / "skills" / "spec-kitty.unknown" / "SKILL.md"
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_bytes(b"# unknown skill\n")

        report = verify(repo)

        assert ".agents/skills/spec-kitty.unknown/SKILL.md" in report.orphans

    def test_third_party_file_is_not_an_orphan(self, repo: Path) -> None:
        """Files in non-spec-kitty dirs must not appear in orphans."""
        third_party = repo / ".agents" / "skills" / "handwritten-review" / "SKILL.md"
        third_party.parent.mkdir(parents=True, exist_ok=True)
        third_party.write_bytes(b"# handwritten\n")

        report = verify(repo)

        assert report.orphans == [], f"Third-party file wrongly flagged as orphan: {report.orphans!r}"

    def test_installed_skill_is_not_orphan(self, repo: Path) -> None:
        install(repo, "vibe")
        report = verify(repo)

        assert report.orphans == []


# ---------------------------------------------------------------------------
# SUPPORTED_AGENTS and CANONICAL_COMMANDS shape
# ---------------------------------------------------------------------------


class TestConstants:
    def test_supported_agents_contains_command_skill_agents(self) -> None:
        assert set(SUPPORTED_AGENTS) == {"codex", "vibe", "pi", "letta"}

    def test_command_layer_agents_are_not_command_skill_agents(self) -> None:
        """Agents in AGENT_COMMAND_CONFIG get command files, never skill packages.

        ``llxprt`` is the newest such agent; it renders TOML slash commands into
        the envPaths('llxprt-code') user-global root
        (``~/Library/Preferences/llxprt-code/commands/`` on macOS) and must not
        claim ``.agents/skills/`` entries.
        """
        from specify_cli.core.config import AGENT_COMMAND_CONFIG

        assert set(SUPPORTED_AGENTS).isdisjoint(AGENT_COMMAND_CONFIG)
        assert "llxprt" not in SUPPORTED_AGENTS

    def test_canonical_commands_count(self) -> None:
        assert len(CANONICAL_COMMANDS) == 15

    def test_canonical_commands_match_consumer_registry(self) -> None:
        from specify_cli.shims.registry import CONSUMER_SKILLS

        assert set(CANONICAL_COMMANDS) == set(CONSUMER_SKILLS)
        assert set(PROMPT_BACKED_COMMANDS).isdisjoint(CLI_WRAPPER_COMMANDS)

    def test_canonical_commands_excludes_checklist(self) -> None:
        # /spec-kitty.checklist was retired in 3.2.0a5 (#815, supersedes #635).
        assert "checklist" not in CANONICAL_COMMANDS

    def test_canonical_commands_no_duplicates(self) -> None:
        assert len(set(CANONICAL_COMMANDS)) == len(CANONICAL_COMMANDS)


# ---------------------------------------------------------------------------
# InstallerError unsupported_agent
# ---------------------------------------------------------------------------


class TestUnsupportedAgent:
    def test_install_raises_for_unknown_agent(self, repo: Path) -> None:
        with pytest.raises(InstallerError) as exc_info:
            install(repo, "unknown-agent")
        assert exc_info.value.code == "unsupported_agent"

    def test_install_raises_for_claude_agent(self, repo: Path) -> None:
        with pytest.raises(InstallerError) as exc_info:
            install(repo, "claude")
        assert exc_info.value.code == "unsupported_agent"


# ---------------------------------------------------------------------------
# Selective remove (FR-008) — intermediate state checks
# ---------------------------------------------------------------------------


class TestSelectiveRemove:
    def test_remove_codex_leaves_vibe_files_intact(self, repo: Path) -> None:
        install(repo, "codex")
        install(repo, "vibe")

        # Capture hashes before removing codex.
        hashes_before: dict[str, str] = {cmd: _sha256_file(_skill_path(repo, cmd)) for cmd in CANONICAL_COMMANDS}

        remove(repo, "codex")

        # Files must still exist and be byte-identical.
        for cmd in CANONICAL_COMMANDS:
            path = _skill_path(repo, cmd)
            assert path.exists(), f"File missing after remove(codex): {cmd}"
            assert _sha256_file(path) == hashes_before[cmd], f"File mutated during remove(codex): {cmd}"

    def test_remove_codex_updates_agents_in_manifest(self, repo: Path) -> None:
        install(repo, "codex")
        install(repo, "vibe")
        remove(repo, "codex")

        manifest = manifest_store.load(repo)
        for entry in manifest.entries:
            assert entry.agents == ("vibe",), f"Entry {entry.path!r}: expected agents==('vibe',), got {entry.agents!r}"

    def test_remove_report_deref_and_kept(self, repo: Path) -> None:
        install(repo, "codex")
        install(repo, "vibe")

        report = remove(repo, "codex")

        assert len(report.deref) == len(CANONICAL_COMMANDS)
        assert len(report.kept) == len(CANONICAL_COMMANDS)
        assert report.deleted == []

    def test_remove_last_agent_clears_all_entries(self, repo: Path) -> None:
        install(repo, "vibe")
        report = remove(repo, "vibe")

        assert len(report.deleted) == len(CANONICAL_COMMANDS)
        assert report.kept == []

        manifest = manifest_store.load(repo)
        assert manifest.entries == []


def test_atomic_write_windows_fchmod_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no ``os.fchmod``): ``_atomic_write`` still writes and applies mode.

    Before the fix ``_atomic_write`` raised ``AttributeError: module 'os'
    has no attribute 'fchmod'`` on a platform without the syscall.
    """
    from specify_cli.skills import command_installer as owner

    monkeypatch.delattr(os, "fchmod", raising=False)
    target = tmp_path / "SKILL.md"

    owner._atomic_write(target, b"skill content", mode=0o640)

    assert target.read_bytes() == b"skill content"
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
