"""ATDD coverage for the charter-pack ``pack.yaml`` tracking migration (#6076).

The charter-pack cutover rewrites a consumer's ``.kittify/doctrine/**`` +
``!…/graph.yaml`` ignore rules into ``.kittify/charter-packs/**`` +
``!.kittify/charter-packs/graph.yaml``, but adds no allow-rule for ``pack.yaml``.
``m_4_0_0rc7_pack_level_backfill`` then writes
``.kittify/charter-packs/pack.yaml``, which the blanket rule hides — so
``pack_level`` never reaches other contributors and each clone mints its own
``pack_id``.

This migration heals an already-cutover consumer: *where the blanket
``.kittify/charter-packs/**`` rule is present and ``!.kittify/charter-packs/pack.yaml``
is absent, add the allow-rule*.

Acceptance anchor (the issue's required proof): a consumer whose ``.gitignore``
carries the blanket rule ends up **tracking** ``pack.yaml`` after the migration.
Guards: never clobber a user-owned ``.gitignore`` that has no blanket rule;
idempotent on re-run; the sibling ``graph.yaml`` allow-rule is preserved.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from specify_cli.gitignore_manager import is_gitignore_path_ignored
from specify_cli.upgrade.migrations.m_4_0_0rc7_track_charter_pack_yaml import (
    TrackCharterPackYamlMigration,
)

_PACK_YAML = ".kittify/charter-packs/pack.yaml"
_GRAPH_YAML = ".kittify/charter-packs/graph.yaml"
_ALLOW_RULE = "!.kittify/charter-packs/pack.yaml"
# The post-cutover consumer state that hides pack.yaml (the bug).
_BUG_GITIGNORE = ".kittify/charter-packs/**\n!.kittify/charter-packs/graph.yaml\n"


def _make_cutover_consumer(repo_root: Path, gitignore: str = _BUG_GITIGNORE) -> None:
    """A git project in the post-cutover state: pack.yaml on disk, hidden by the blanket rule."""
    pack_root = repo_root / ".kittify" / "charter-packs"
    pack_root.mkdir(parents=True)
    (pack_root / "graph.yaml").write_text("nodes: []\n", encoding="utf-8")
    (pack_root / "pack.yaml").write_text("pack_id: 01ABCDEF\npack_level: project\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text(gitignore, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)


# ---------------------------------------------------------------------------
# ATDD anchor — the issue's required proof
# ---------------------------------------------------------------------------


def test_consumer_with_blanket_rule_tracks_pack_yaml_after_migration(tmp_path: Path) -> None:
    """A consumer with the blanket rule ends up TRACKING pack.yaml after the migration."""
    _make_cutover_consumer(tmp_path)

    # Precondition (the bug): pack.yaml is ignored by the blanket rule.
    assert is_gitignore_path_ignored(tmp_path, _PACK_YAML) is True

    result = TrackCharterPackYamlMigration().apply(tmp_path)

    assert result.success is True
    assert result.changes_made, "migration should report the allow-rule it added"
    # The acceptance criterion: git no longer ignores pack.yaml — it is trackable.
    assert is_gitignore_path_ignored(tmp_path, _PACK_YAML) is False
    assert _ALLOW_RULE in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_graph_yaml_allow_rule_is_preserved(tmp_path: Path) -> None:
    """Healing pack.yaml does not disturb the sibling graph.yaml allow-rule."""
    _make_cutover_consumer(tmp_path)

    TrackCharterPackYamlMigration().apply(tmp_path)

    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "!.kittify/charter-packs/graph.yaml" in ignore
    # graph.yaml stays trackable; pack.yaml joins it.
    assert is_gitignore_path_ignored(tmp_path, _GRAPH_YAML) is False


# ---------------------------------------------------------------------------
# detect() gating + idempotency + user-customization preservation
# ---------------------------------------------------------------------------


def test_detect_true_only_where_blanket_rule_hides_pack_yaml(tmp_path: Path) -> None:
    _make_cutover_consumer(tmp_path)
    assert TrackCharterPackYamlMigration().detect(tmp_path) is True


def test_idempotent_rerun_is_a_noop(tmp_path: Path) -> None:
    _make_cutover_consumer(tmp_path)
    migration = TrackCharterPackYamlMigration()

    first = migration.apply(tmp_path)
    assert first.changes_made

    assert migration.detect(tmp_path) is False
    second = migration.apply(tmp_path)
    assert second.success is True
    assert not second.changes_made


def test_no_blanket_rule_is_left_untouched(tmp_path: Path) -> None:
    """A user-owned .gitignore without the blanket rule is never modified."""
    custom = "# my own rules\n.venv/\nbuild/\n"
    _make_cutover_consumer(tmp_path, gitignore=custom)

    migration = TrackCharterPackYamlMigration()
    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)

    assert result.success is True
    assert not result.changes_made
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == custom


def test_already_allowed_pack_yaml_is_a_noop(tmp_path: Path) -> None:
    """A consumer that already allows pack.yaml needs no change (idempotent across installs)."""
    already = _BUG_GITIGNORE + "!.kittify/charter-packs/pack.yaml\n"
    _make_cutover_consumer(tmp_path, gitignore=already)

    migration = TrackCharterPackYamlMigration()
    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)

    assert result.success is True
    assert not result.changes_made


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    _make_cutover_consumer(tmp_path)
    before = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    result = TrackCharterPackYamlMigration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert result.changes_made
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == before
