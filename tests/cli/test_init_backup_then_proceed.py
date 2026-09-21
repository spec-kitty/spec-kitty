"""WP04 — Init backup-then-proceed (FR-006/FR-007, #4759).

`spec-kitty init` must never destroy operator-authored `.kittify/missions/`
or `.kittify/memory/` content. Before this WP, three code paths did an
unconditional `shutil.rmtree` on whatever already lived at the destination:

  1. `template.manager.copy_package_tree` (package-mode init)
  2. `template.manager.copy_specify_base_from_local` (local-checkout init)
  3. the whole-project rollback in `cli.commands.init` on a failed init

Each test below triggers its site *directly* -- calling the function or
constructing its exact precondition -- rather than driving one end-to-end
`init` call (a single CLI run only exercises one of the three sites per
run, so it cannot prove all three are fixed; SC-003).

Spec IDs: FR-006, FR-007, NFR-003, SC-003.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands import init as init_module
from specify_cli.template import manager


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _populate_operator_content(kittify_root: Path) -> None:
    """Seed `.kittify/{missions,memory}` with known operator-authored bytes."""
    mission_file = kittify_root / "missions" / "my-custom-mission" / "mission.yaml"
    mission_file.parent.mkdir(parents=True, exist_ok=True)
    mission_file.write_text("name: my-custom-mission\n", encoding="utf-8")

    memory_file = kittify_root / "memory" / "my-notes.md"
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text("my precious project notes\n", encoding="utf-8")


def _find_backed_up_file(backup_root: Path, *relative_parts: str) -> Path | None:
    """Locate a file by its trailing path parts anywhere under `backup_root`."""
    for candidate in backup_root.rglob(relative_parts[-1]):
        if candidate.parts[-len(relative_parts) :] == relative_parts:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Site 1 — template.manager.copy_package_tree (package-mode init)
# ---------------------------------------------------------------------------


def test_copy_package_tree_preserves_existing_missions_when_dest_already_populated(tmp_path: Path) -> None:
    """Direct call: `copy_package_tree(..., preserve_existing=True)` must back
    up, not delete, a pre-existing populated `missions/` destination."""
    kittify_root = tmp_path / "project" / ".kittify"
    kittify_root.mkdir(parents=True)
    _populate_operator_content(kittify_root)

    # A fresh package-side missions resource being scaffolded in.
    package_missions = tmp_path / "package_data" / "missions"
    (package_missions / "default").mkdir(parents=True)
    (package_missions / "default" / "rules.md").write_text("packaged rules", encoding="utf-8")

    dest = kittify_root / "missions"
    manager.copy_package_tree(package_missions, dest, preserve_existing=True)

    # Fresh scaffold content landed.
    assert (dest / "default" / "rules.md").read_text(encoding="utf-8") == "packaged rules"

    # Operator's original custom mission bytes survive somewhere under a
    # reported .kittify/.backup-<ts>/ directory -- nothing was silently lost.
    backup_dirs = [p for p in kittify_root.iterdir() if p.is_dir() and p.name.startswith(".backup-")]
    assert backup_dirs, "expected a .kittify/.backup-<ts>/ directory to be created"
    preserved = _find_backed_up_file(backup_dirs[0], "missions", "my-custom-mission", "mission.yaml")
    assert preserved is not None, "operator's custom mission was not preserved in the backup"
    assert preserved.read_text(encoding="utf-8") == "name: my-custom-mission\n"


def test_copy_package_tree_default_still_replaces_regenerable_dest(tmp_path: Path) -> None:
    """Without `preserve_existing`, behavior is unchanged (regenerable scaffold,
    e.g. templates/, may still be replaced in place -- T014 note)."""
    dest = tmp_path / "templates"
    dest.mkdir()
    (dest / "stale.md").write_text("stale", encoding="utf-8")

    source = tmp_path / "src_templates"
    source.mkdir()
    (source / "fresh.md").write_text("fresh", encoding="utf-8")

    manager.copy_package_tree(source, dest)

    assert not (dest / "stale.md").exists()
    assert (dest / "fresh.md").read_text(encoding="utf-8") == "fresh"


# ---------------------------------------------------------------------------
# Site 2 — template.manager.copy_specify_base_from_local (local-checkout init)
# ---------------------------------------------------------------------------


def test_copy_specify_base_from_local_preserves_existing_missions_and_memory(tmp_path: Path) -> None:
    """Direct call: a local-checkout init over an operator-populated project
    must preserve both missions/ and memory/, not rmtree them (×subtrees)."""
    repo_root = tmp_path / "repo"
    memory_src = repo_root / ".kittify" / "memory"
    memory_src.mkdir(parents=True)
    (memory_src / "seed.txt").write_text("seed", encoding="utf-8")
    missions_src = repo_root / "packs" / "built-in" / "missions" / "default"
    missions_src.mkdir(parents=True)
    (missions_src / "rules.md").write_text("rules", encoding="utf-8")

    project_path = tmp_path / "project"
    kittify_root = project_path / ".kittify"
    kittify_root.mkdir(parents=True)
    _populate_operator_content(kittify_root)

    manager.copy_specify_base_from_local(repo_root, project_path)

    # Fresh content landed.
    assert (kittify_root / "memory" / "seed.txt").read_text(encoding="utf-8") == "seed"
    assert (kittify_root / "missions" / "default" / "rules.md").read_text(encoding="utf-8") == "rules"

    # Operator bytes for BOTH subtrees survive under a reported backup dir.
    backup_dirs = [p for p in kittify_root.iterdir() if p.is_dir() and p.name.startswith(".backup-")]
    assert backup_dirs, "expected at least one .kittify/.backup-<ts>/ directory"
    preserved_mission = None
    preserved_notes = None
    for backup_dir in backup_dirs:
        preserved_mission = preserved_mission or _find_backed_up_file(backup_dir, "missions", "my-custom-mission", "mission.yaml")
        preserved_notes = preserved_notes or _find_backed_up_file(backup_dir, "memory", "my-notes.md")
    assert preserved_mission is not None, "operator's custom mission was not preserved"
    assert preserved_mission.read_text(encoding="utf-8") == "name: my-custom-mission\n"
    assert preserved_notes is not None, "operator's memory notes were not preserved"
    assert preserved_notes.read_text(encoding="utf-8") == "my precious project notes\n"


# ---------------------------------------------------------------------------
# Site 3 — cli.commands.init rollback-on-failure whole-project rmtree
# ---------------------------------------------------------------------------


def test_discard_failed_project_scaffold_preserves_operator_content(tmp_path: Path) -> None:
    """Direct call: constructing the failure-rollback precondition (a
    project directory with operator .kittify content, `here=False`) must
    preserve missions/memory bytes -- the backup must land OUTSIDE
    `project_path`, since that whole directory is removed."""
    project_path = tmp_path / "myproject"
    kittify_root = project_path / ".kittify"
    kittify_root.mkdir(parents=True)
    _populate_operator_content(kittify_root)

    init_module._discard_failed_project_scaffold(project_path, here=False)

    # The failed scaffold itself is gone (unchanged prior behavior).
    assert not project_path.exists()

    # But the operator's bytes survive, reported, as a sibling backup.
    backup_dirs = [p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith(".backup-")]
    assert backup_dirs, "expected a sibling .backup-<ts>/ directory outside project_path"
    preserved_mission = _find_backed_up_file(backup_dirs[0], "missions", "my-custom-mission", "mission.yaml")
    preserved_notes = _find_backed_up_file(backup_dirs[0], "memory", "my-notes.md")
    assert preserved_mission is not None
    assert preserved_mission.read_text(encoding="utf-8") == "name: my-custom-mission\n"
    assert preserved_notes is not None
    assert preserved_notes.read_text(encoding="utf-8") == "my precious project notes\n"


def test_discard_failed_project_scaffold_is_noop_for_here_mode(tmp_path: Path) -> None:
    """`here=True` (initializing an existing directory in place) must never
    trigger the wholesale rmtree, regardless of what .kittify holds."""
    project_path = tmp_path / "existing_repo"
    kittify_root = project_path / ".kittify"
    kittify_root.mkdir(parents=True)
    _populate_operator_content(kittify_root)

    init_module._discard_failed_project_scaffold(project_path, here=True)

    assert project_path.exists()
    assert (kittify_root / "missions" / "my-custom-mission" / "mission.yaml").exists()
    assert (kittify_root / "memory" / "my-notes.md").exists()


# ---------------------------------------------------------------------------
# Same-second collision — two re-inits within the same second must not clobber
# each other's backup.
# ---------------------------------------------------------------------------


def test_same_second_backups_are_collision_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two back-up-then-proceed calls that land in the same wall-clock second
    must produce two distinct, non-overwriting backup directories."""
    monkeypatch.setattr(manager, "_utc_backup_timestamp", lambda: "20260920T000000Z")

    kittify_root = tmp_path / ".kittify"
    kittify_root.mkdir()
    (kittify_root / "missions").mkdir()
    (kittify_root / "missions" / "first.txt").write_text("first re-init", encoding="utf-8")

    first_backup = manager.back_up_operator_subtrees(kittify_root, ["missions"])
    assert first_backup is not None
    assert first_backup.name == ".backup-20260920T000000Z"

    # Simulate a second re-init landing in the exact same second.
    (kittify_root / "missions").mkdir()
    (kittify_root / "missions" / "second.txt").write_text("second re-init", encoding="utf-8")

    second_backup = manager.back_up_operator_subtrees(kittify_root, ["missions"])
    assert second_backup is not None
    assert second_backup != first_backup
    assert second_backup.name == ".backup-20260920T000000Z-1"

    # Neither backup was overwritten by the other.
    assert (first_backup / "missions" / "first.txt").read_text(encoding="utf-8") == "first re-init"
    assert (second_backup / "missions" / "second.txt").read_text(encoding="utf-8") == "second re-init"


# ---------------------------------------------------------------------------
# FR-007 — the "already initialized" predicate must not treat a populated
# .kittify/ (missions/memory present, no config.yaml) as blank.
# ---------------------------------------------------------------------------


def test_has_operator_authored_content_true_when_populated_without_config(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    kittify_root = project_path / ".kittify"
    kittify_root.mkdir(parents=True)
    _populate_operator_content(kittify_root)
    assert not (kittify_root / "config.yaml").exists()

    assert init_module._has_operator_authored_content(project_path) is True


def test_has_operator_authored_content_false_for_truly_blank_kittify(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    (project_path / ".kittify").mkdir(parents=True)

    assert init_module._has_operator_authored_content(project_path) is False


def test_has_operator_authored_content_false_when_no_kittify_at_all(tmp_path: Path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()

    assert init_module._has_operator_authored_content(project_path) is False


def test_has_operator_authored_content_false_for_empty_subtree_dirs(tmp_path: Path) -> None:
    """A bare `mkdir missions` with no files inside is not itself content."""
    project_path = tmp_path / "project"
    kittify_root = project_path / ".kittify"
    (kittify_root / "missions").mkdir(parents=True)
    (kittify_root / "memory").mkdir(parents=True)

    assert init_module._has_operator_authored_content(project_path) is False
