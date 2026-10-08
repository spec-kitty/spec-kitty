"""Charter-pack cutover: installed copies of removed skills (#3732, T063).

The step is tested directly (and through the migration's ``apply()``), never
through ``spec-kitty upgrade``: until WP18 deletes the sources, the upgrade
finalizer reinstalls these skills from the catalog.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.content_digest import sha256_digest
from specify_cli.upgrade.migrations._charter_pack_cutover_skills import _shipped_skill_names as real_shipped_skill_names
from specify_cli.upgrade.migrations._charter_pack_cutover_skills import (
    REMOVED_SKILL_NAMES,
    SHIPPED_SKILL_HASHES,
    find_removed_skill_copies,
    remove_skill_copies,
)
from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError
from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration

pytestmark = [pytest.mark.unit]

_MODULE = "specify_cli.upgrade.migrations._charter_pack_cutover_skills"

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_SOURCES = REPO_ROOT / "src" / "charter" / "offering" / "skills"
MANIFEST = ".kittify/skills-manifest.json"


#: A synthetic shipped skill tree (relative path -> bytes), the same for every removed
#: name, so the removal and keep tests do not read the live sources WP18 deletes.
SYNTHETIC_TREE: dict[str, bytes] = {
    "SKILL.md": b"---\nname: synthetic\n---\n# A shipped skill\n",
    "references/guide.md": b"# Reference\n",
    "assets/template.md": b"# Asset\n",
}


@pytest.fixture(autouse=True)
def _sources_deleted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behave as after WP18: the catalog no longer ships the removed names; the frozen
    hashes describe :data:`SYNTHETIC_TREE` (the constitution name keeps no hashes)."""
    monkeypatch.setattr(f"{_MODULE}._shipped_skill_names", frozenset)
    synthetic = {rel: sha256_digest(body).removeprefix("sha256:") for rel, body in SYNTHETIC_TREE.items()}
    hashes = {name: synthetic for name in REMOVED_SKILL_NAMES if name != "spec-kitty-constitution-doctrine"}
    monkeypatch.setattr(f"{_MODULE}.SHIPPED_SKILL_HASHES", hashes)


def _config(project: Path, agents: list[str]) -> None:
    path = project / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("agents:\n  available:\n" + "".join(f"  - {a}\n" for a in agents), encoding="utf-8")


def _install(project: Path, root: str, name: str) -> Path:
    """A byte copy of the (synthetic) shipped source, as the installer makes it."""
    target = project / root / name
    for rel, body in SYNTHETIC_TREE.items():
        (target / rel).parent.mkdir(parents=True, exist_ok=True)
        (target / rel).write_bytes(body)
    return target


def _manifest(project: Path, files: list[tuple[str, str, Path]]) -> None:
    """``(skill name, agent, installed file)`` entries, hashed from the bytes on disk."""
    entries = [
        {
            "skill_name": name,
            "source_file": path.name,
            "installed_path": path.relative_to(project).as_posix(),
            "installation_class": "native-root-required",
            "agent_key": agent,
            "content_hash": sha256_digest(path.read_bytes()),
            "installed_at": "2026-10-01T00:00:00+00:00",
            "delivery_mode": "copy",
        }
        for name, agent, path in files
    ]
    data = {
        "version": 1,
        "created_at": "2026-10-01T00:00:00+00:00",
        "updated_at": "2026-10-01T00:00:00+00:00",
        "spec_kitty_version": "4.0.0rc5",
        "entries": entries,
    }
    (project / MANIFEST).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _manifest_paths(project: Path) -> list[str]:
    return [entry["installed_path"] for entry in json.loads((project / MANIFEST).read_text(encoding="utf-8"))["entries"]]


# --------------------------------------------------------------------------- #
# Frozen data
# --------------------------------------------------------------------------- #


def test_thirteen_removed_names() -> None:
    assert len(REMOVED_SKILL_NAMES) == len(set(REMOVED_SKILL_NAMES)) == 13
    assert "spec-kitty-constitution-doctrine" in REMOVED_SKILL_NAMES
    assert set(SHIPPED_SKILL_HASHES) == set(REMOVED_SKILL_NAMES) - {"spec-kitty-constitution-doctrine"}


@pytest.mark.skipif(not (SKILL_SOURCES / "spk-doctrine-charter").is_dir(), reason="sources deleted by WP18; the frozen hashes stay")
@pytest.mark.parametrize("name", sorted(SHIPPED_SKILL_HASHES))
def test_frozen_hashes_match_the_shipped_sources(name: str) -> None:
    source = SKILL_SOURCES / name
    actual = {p.relative_to(source).as_posix(): sha256_digest(p.read_bytes()).removeprefix("sha256:") for p in source.rglob("*") if p.is_file()}
    assert actual == dict(SHIPPED_SKILL_HASHES[name])


# --------------------------------------------------------------------------- #
# Removal
# --------------------------------------------------------------------------- #


def test_unmanifested_byte_copy_is_removed(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-show-me")
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert not copy.exists()
    assert report.skills_removed == [".claude/skills/spk-doctrine-show-me (spk-doctrine-show-me; package-owned (canonical_content))"]
    assert (tmp_path / ".claude" / "skills").is_dir(), "the root itself stays"


def test_manifested_copy_is_removed_and_its_entries_dropped(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    (tmp_path / ".claude" / "skills" / "spec-kitty-constitution-doctrine").mkdir(parents=True)
    skill = tmp_path / ".claude" / "skills" / "spec-kitty-constitution-doctrine" / "SKILL.md"
    skill.write_text("an older release's text\n", encoding="utf-8")
    other = tmp_path / ".claude" / "skills" / "spk-run-next" / "SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("a skill that stays\n", encoding="utf-8")
    _manifest(tmp_path, [("spec-kitty-constitution-doctrine", "claude", skill), ("spk-run-next", "claude", other)])
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert not skill.parent.exists()
    assert report.skills_removed == [".claude/skills/spec-kitty-constitution-doctrine (spec-kitty-constitution-doctrine; package-owned (manifest))"]
    assert ".claude/skills/spec-kitty-constitution-doctrine/SKILL.md" not in _manifest_paths(tmp_path)
    assert _manifest_paths(tmp_path) == [".claude/skills/spk-run-next/SKILL.md"], "other entries are untouched"


@pytest.mark.parametrize("change", ["edited", "extra_file", "missing_file"])
def test_edited_copy_is_kept_in_place_and_reported(tmp_path: Path, change: str) -> None:
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-show-me")
    if change == "edited":
        (copy / "SKILL.md").write_text((copy / "SKILL.md").read_text(encoding="utf-8") + "\n<!-- mine -->\n", encoding="utf-8")
    elif change == "extra_file":
        (copy / "notes.md").write_text("mine\n", encoding="utf-8")
    else:
        (copy / "assets" / "template.md").unlink()
    before = {p.relative_to(copy).as_posix(): p.read_bytes() for p in copy.rglob("*") if p.is_file()}
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert {p.relative_to(copy).as_posix(): p.read_bytes() for p in copy.rglob("*") if p.is_file()} == before
    assert report.skills_removed == []
    (line,) = report.skills_kept
    assert line.startswith(".claude/skills/spk-doctrine-show-me (spk-doctrine-show-me; edited or not a shipped copy, left in place")
    assert report.preserved_paths == [".claude/skills/spk-doctrine-show-me"]


def test_kept_copy_is_released_from_the_skills_manifest(tmp_path: Path) -> None:
    """Owner ruling A (US4): the kept copy becomes user-owned, so the finalizer never nags about it."""
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-show-me")
    other = tmp_path / ".claude" / "skills" / "spk-run-next" / "SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("a skill that stays\n", encoding="utf-8")
    _manifest(tmp_path, [*(("spk-doctrine-show-me", "claude", copy / rel) for rel in SYNTHETIC_TREE), ("spk-run-next", "claude", other)])
    (copy / "SKILL.md").write_text("mine\n", encoding="utf-8")
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert (copy / "SKILL.md").read_text(encoding="utf-8") == "mine\n"
    assert _manifest_paths(tmp_path) == [".claude/skills/spk-run-next/SKILL.md"]
    (line,) = report.skills_kept
    assert "no longer managed by spec-kitty" in line
    assert report.errors == []


def test_dry_run_keeps_the_manifest_entries_of_a_kept_copy(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-show-me")
    _manifest(tmp_path, [("spk-doctrine-show-me", "claude", copy / rel) for rel in SYNTHETIC_TREE])
    (copy / "SKILL.md").write_text("mine\n", encoding="utf-8")
    manifest_before = (tmp_path / MANIFEST).read_bytes()
    report = remove_skill_copies(tmp_path, dry_run=True)
    assert (tmp_path / MANIFEST).read_bytes() == manifest_before
    (line,) = report.skills_kept
    assert "no longer managed by spec-kitty" in line


def test_symlinked_copy_is_kept(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    real = _install(tmp_path, "elsewhere", "spk-doctrine-charter")
    root = tmp_path / ".claude" / "skills"
    root.mkdir(parents=True)
    (root / "spk-doctrine-charter").symlink_to(real, target_is_directory=True)
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert (root / "spk-doctrine-charter").is_symlink()
    assert report.preserved_paths == [".claude/skills/spk-doctrine-charter"]


def test_unmanifested_constitution_copy_is_kept(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    copy = tmp_path / ".claude" / "skills" / "spec-kitty-constitution-doctrine"
    copy.mkdir(parents=True)
    (copy / "SKILL.md").write_text("old\n", encoding="utf-8")
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert copy.is_dir() and report.preserved_paths == [".claude/skills/spec-kitty-constitution-doctrine"]


def test_shared_root_is_visited_once_and_unconfigured_roots_are_ignored(tmp_path: Path) -> None:
    _config(tmp_path, ["codex", "copilot"])
    _install(tmp_path, ".agents/skills", "spk-doctrine-charter")
    ignored = _install(tmp_path, ".claude/skills", "spk-doctrine-charter")
    copies = find_removed_skill_copies(tmp_path)
    assert [c.path.relative_to(tmp_path).as_posix() for c in copies] == [".agents/skills/spk-doctrine-charter"]
    remove_skill_copies(tmp_path, dry_run=False)
    assert ignored.is_dir(), "claude is not configured"
    assert not (tmp_path / ".github" / "skills").exists(), "a missing root is never created"


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-glossary")
    _manifest(tmp_path, [("spk-doctrine-glossary", "claude", copy / rel) for rel in SYNTHETIC_TREE])
    manifest_before = (tmp_path / MANIFEST).read_bytes()
    report = remove_skill_copies(tmp_path, dry_run=True)
    assert copy.is_dir() and (tmp_path / MANIFEST).read_bytes() == manifest_before
    assert report.skills_removed == [".claude/skills/spk-doctrine-glossary (spk-doctrine-glossary; package-owned (manifest))"]


def test_unreadable_agent_config_raises(tmp_path: Path) -> None:
    path = tmp_path / ".kittify" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("agents: [not, a, mapping]\n", encoding="utf-8")
    with pytest.raises(MigrationStateUnreadableError):
        find_removed_skill_copies(tmp_path)


def test_removal_failure_is_a_report_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _config(tmp_path, ["claude"])
    _install(tmp_path, ".claude/skills", "spk-doctrine-charter")

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("locked")

    monkeypatch.setattr(f"{_MODULE}.guard_destructive_removal", refuse)
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert report.errors == [".claude/skills/spk-doctrine-charter could not be removed (locked); close any program holding it, then run `spec-kitty upgrade` again"]


def test_failed_removal_keeps_its_manifest_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A copy that could not be removed stays managed, so the next upgrade can still prove it."""
    _config(tmp_path, ["claude"])
    copy = _install(tmp_path, ".claude/skills", "spk-doctrine-charter")
    _manifest(tmp_path, [("spk-doctrine-charter", "claude", copy / rel) for rel in SYNTHETIC_TREE])
    manifest_before = (tmp_path / MANIFEST).read_bytes()

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("locked")

    monkeypatch.setattr(f"{_MODULE}.guard_destructive_removal", refuse)
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert report.errors and (tmp_path / MANIFEST).read_bytes() == manifest_before


def test_manifest_update_failure_is_a_report_error(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    _install(tmp_path, ".claude/skills", "spk-doctrine-charter")
    (tmp_path / MANIFEST).write_text("{not json", encoding="utf-8")
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert report.skills_removed and report.errors and "skills-manifest.json could not be updated" in report.errors[0]


# --------------------------------------------------------------------------- #
# Through the migration: detect() turns false once only kept copies remain
# --------------------------------------------------------------------------- #


def test_migration_removes_proven_copies_and_detect_turns_false_with_an_edited_copy(tmp_path: Path) -> None:
    _config(tmp_path, ["claude"])
    removed = _install(tmp_path, ".claude/skills", "spk-doctrine-bulk-edit")
    edited = _install(tmp_path, ".claude/skills", "ad-hoc-profile-load")
    (edited / "SKILL.md").write_text("mine\n", encoding="utf-8")
    migration = CharterPackCutoverMigration()
    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    assert result.success
    assert not removed.exists() and edited.is_dir()
    assert result.preserved_paths == [".claude/skills/ad-hoc-profile-load"]
    assert any(w.startswith("Kept edited skill copy: .claude/skills/ad-hoc-profile-load") for w in result.warnings)
    assert result.manual_review_required
    assert migration.detect(tmp_path) is False


# --------------------------------------------------------------------------- #
# A name the installed catalog still ships is left alone (the finalizer reinstalls it)
# --------------------------------------------------------------------------- #


def test_still_shipped_name_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f"{_MODULE}._shipped_skill_names", lambda: frozenset({"spk-doctrine-charter"}))
    _config(tmp_path, ["claude"])
    shipped = _install(tmp_path, ".claude/skills", "spk-doctrine-charter")
    retired = _install(tmp_path, ".claude/skills", "spk-doctrine-glossary")
    report = remove_skill_copies(tmp_path, dry_run=False)
    assert shipped.is_dir() and not retired.exists()
    assert [line.split(" ")[0] for line in report.skills_removed] == [".claude/skills/spk-doctrine-glossary"]


def test_real_catalog_lists_shipped_skills() -> None:
    names = real_shipped_skill_names()
    assert "spk-run-next" in names
    assert "spec-kitty-constitution-doctrine" not in names


def test_no_builtin_catalog_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a shipped catalog nothing can tell which removed skills are still shipped: refuse, never guess."""
    monkeypatch.setattr("specify_cli.skills.catalog.resolve_builtin_skill_catalog", lambda: None)
    with pytest.raises(MigrationStateUnreadableError, match="no skill catalog.*spec-kitty upgrade"):
        real_shipped_skill_names()
