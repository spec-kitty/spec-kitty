"""Rollback and backup hygiene of the schema-3 migration runner (#4763, #5443).

Filesystem under ``tmp_path`` only: no git, no subprocess.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specify_cli.migration.runner import (
    _BACKUP_DIR_NAME,
    _create_backup,
    _restore_backup,
    _update_gitignore,
    run_migration,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SIBLINGS = {"kitty-specs-backup", "gitignore-backup", "gitignore-absent"}


def _project(root: Path, *, gitignore: str | None) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text(yaml.dump({"spec_kitty": {"version": "2.1.0"}}), encoding="utf-8")
    (kittify / "config.yaml").write_text("agents:\n  available: []\n", encoding="utf-8")
    feature = root / "kitty-specs" / "001-demo"
    (feature / "tasks").mkdir(parents=True)
    (feature / "meta.json").write_text('{"mission_slug": "001-demo"}\n', encoding="utf-8")
    (feature / "tasks" / "WP01-t.md").write_text("---\nwp_code: WP01\nlane: planned\n---\n# WP01\n", encoding="utf-8")
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    return root


def _names(directory: Path) -> set[str]:
    return {entry.name for entry in directory.iterdir()}


def test_full_restore_returns_true_and_leaves_exactly_the_original_entries(tmp_path: Path) -> None:
    root = _project(tmp_path, gitignore="*.pyc\n")
    kittify = root / ".kittify"
    original = _names(kittify)
    backup = _create_backup(root)
    assert backup is not None
    (kittify / "new.txt").write_text("x\n", encoding="utf-8")
    (kittify / "metadata.yaml").write_text("changed: true\n", encoding="utf-8")

    assert _restore_backup(root, backup) is True

    assert _names(kittify) == original | {_BACKUP_DIR_NAME}
    assert not (_SIBLINGS & _names(kittify))
    assert yaml.safe_load((kittify / "metadata.yaml").read_text(encoding="utf-8")) == {"spec_kitty": {"version": "2.1.0"}}


def test_gitignore_created_by_the_migration_is_removed_on_rollback(tmp_path: Path) -> None:
    root = _project(tmp_path, gitignore=None)
    backup = _create_backup(root)
    assert backup is not None
    assert (backup / "gitignore-absent").exists()
    _update_gitignore(root)
    assert (root / ".gitignore").exists()

    assert _restore_backup(root, backup) is True

    assert not (root / ".gitignore").exists()


def test_existing_gitignore_is_restored_byte_identical(tmp_path: Path) -> None:
    root = _project(tmp_path, gitignore="*.pyc\noperator/\n")
    before = (root / ".gitignore").read_bytes()
    backup = _create_backup(root)
    assert backup is not None
    assert not (backup / "gitignore-absent").exists()
    _update_gitignore(root)
    assert (root / ".gitignore").read_bytes() != before

    assert _restore_backup(root, backup) is True

    assert (root / ".gitignore").read_bytes() == before


def test_obsolete_ignore_lines_are_kept_and_new_entries_added(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(".kittify/workspaces/\n.kittify/merge-state.json\n*.pyc\n", encoding="utf-8")

    _update_gitignore(tmp_path)

    lines = (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".kittify/workspaces/" in lines
    assert ".kittify/merge-state.json" in lines
    assert {".kittify/derived/", ".kittify/runtime/", ".kittify/.migration-backup/"} <= set(lines)


def test_failed_run_restores_and_removes_the_backup(tmp_path: Path) -> None:
    root = _project(tmp_path, gitignore=None)
    kittify = root / ".kittify"
    before = _names(kittify)

    with patch("specify_cli.migration.strip_frontmatter.strip_mutable_fields", side_effect=RuntimeError("boom")):
        report = run_migration(root)

    assert report.failed_step == "strip_frontmatter"
    assert not (kittify / _BACKUP_DIR_NAME).exists()
    assert _names(kittify) == before
    assert not (root / ".gitignore").exists()


def test_partial_restore_keeps_the_backup_and_names_it(tmp_path: Path) -> None:
    root = _project(tmp_path, gitignore=None)
    kittify = root / ".kittify"
    real_copy2 = shutil.copy2

    def _copy2(src: object, dst: object, **kwargs: object) -> object:
        if Path(str(src)).name == "config.yaml" and _BACKUP_DIR_NAME in str(src):
            raise OSError("simulated restore failure")
        return real_copy2(src, dst, **kwargs)  # type: ignore[arg-type]

    with (
        patch("specify_cli.migration.strip_frontmatter.strip_mutable_fields", side_effect=RuntimeError("boom")),
        patch("specify_cli.migration.runner.shutil.copy2", side_effect=_copy2),
    ):
        report = run_migration(root)

    backup = kittify / _BACKUP_DIR_NAME
    assert backup.is_dir(), "the only copy of what failed to restore must be kept"
    assert any(str(backup) in warning for warning in report.warnings)
