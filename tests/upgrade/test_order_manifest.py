"""Red-first unit tests for the order manifest loader (WP01 / IC-02).

Covers FR-006: the checked-in order manifest is the order authority; parsing
ignores blanks/comments, parses tie + runs-first annotations, and reproduces
today's ``registry.get_all()`` order over the existing migrations (NFR-004
parity).
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.upgrade.manifest import (
    MANIFEST_PATH,
    load_manifest_entries,
    load_order_manifest,
)
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

_BACKFILL_ID = "4.0.0rc8_backfill_migration_ledger"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "order_manifest.txt"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_ignores_blanks_and_full_comment_lines(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "# header comment\n\n0.2.0_specify_to_kittify\n   \n# another comment\n0.4.8_gitignore_agents\n",
    )
    assert load_order_manifest(path) == ["0.2.0_specify_to_kittify", "0.4.8_gitignore_agents"]


def test_tie_annotation_is_parsed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "0.8.0_remove_active_mission\n0.8.0_worktree_agents_symlink  # tie: shares target_version 0.8.0\n",
    )
    entries = load_manifest_entries(path)
    assert [e.id for e in entries] == ["0.8.0_remove_active_mission", "0.8.0_worktree_agents_symlink"]
    assert entries[0].tie_reason is None
    assert entries[1].tie_reason == "shares target_version 0.8.0"


def test_runs_first_annotation_is_parsed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        f"{_BACKFILL_ID}  # runs-first: backfill must lead\n0.2.0_specify_to_kittify\n",
    )
    entries = load_manifest_entries(path)
    assert entries[0].runs_first_reason == "backfill must lead"
    assert entries[1].runs_first_reason is None


def _canonical_get_all_ids() -> list[str]:
    """``get_all()`` ids from a freshly rebuilt registry.

    ``get_all()`` still sorts by ``Version(target_version)`` with a *stable* sort,
    so the order among equal-version ties is the registry insertion (auto-
    discovery import) order — which other test modules perturb by importing a
    migration module early during collection. Rebuilding the registry from a
    clean ``auto_discover`` restores the canonical, deterministic order the
    manifest was generated from (the conftest autouse fixture restores the
    collection-time registry afterwards). This is exactly the unstable tiebreak
    the manifest is introduced to replace (ADR 2026-10-17-1 §2).
    """
    MigrationRegistry.clear()
    auto_discover_migrations()
    return [m.migration_id for m in MigrationRegistry.get_all()]


def test_real_manifest_reproduces_get_all_order_over_existing_migrations() -> None:
    """NFR-004 parity: manifest order (minus the backfill lead) == canonical get_all() order (minus the backfill)."""
    manifest_ids = load_order_manifest(MANIFEST_PATH)
    assert manifest_ids[0] == _BACKFILL_ID  # the backfill leads

    get_all_ids = _canonical_get_all_ids()
    manifest_existing = [mid for mid in manifest_ids if mid != _BACKFILL_ID]
    get_all_existing = [mid for mid in get_all_ids if mid != _BACKFILL_ID]
    assert manifest_existing == get_all_existing


def test_manifest_and_registry_cover_the_same_migrations() -> None:
    """Order-independent parity: the manifest and the registry describe the same id set."""
    manifest_ids = set(load_order_manifest(MANIFEST_PATH))
    MigrationRegistry.clear()
    auto_discover_migrations()
    registry_ids = {m.migration_id for m in MigrationRegistry.get_all()}
    assert manifest_ids == registry_ids
