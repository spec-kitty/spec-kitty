"""Tests for RefreshOrientationBlockMigration.

Covers detect/apply/dry_run/idempotency and the two key scenarios:
  1. AGENTS.md stale block → refreshed
  2. Non-AGENTS writer (cursor) stale block → refreshed
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.fast]

import specify_cli.upgrade.migrations.m_3_2_0rc39_refresh_orientation_block  # noqa: F401
from specify_cli.session_presence.content import SECTION_CLOSE, SECTION_OPEN
from specify_cli.upgrade.migrations.m_3_2_0rc39_refresh_orientation_block import (
    RefreshOrientationBlockMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

# ---------------------------------------------------------------------------
# Stale block fixture — mimics a pre-3.2.0rc39 orientation block
# ---------------------------------------------------------------------------

_OLD_BLOCK = (
    f"{SECTION_OPEN}\n"
    "**Spec Kitty v3.2.0rc38** — project: example (healthy)\n\n"
    "Two usage patterns:\n"
    "- **Full mission** (spec → plan → tasks → implement → review → merge):\n"
    '  trigger: "spec out", "create a mission", "write a spec", "plan this"\n'
    "  → run `/spec-kitty.specify`\n"
    "- **Lightweight dispatch** (ad-hoc fix, question, or advice — no mission created):\n"
    '  trigger: "hey spec kitty", "use spec kitty to", "spec kitty <anything>"\n'
    '  → run `spec-kitty dispatch "<request verbatim>"`\n'
    f"{SECTION_CLOSE}\n"
)

# Literal current managed body with a stale version, not a renderer-derived oracle.
# The older single-line body above has no current ownership proof.
_MANAGED_OLD_BLOCK = _OLD_BLOCK.replace(
    '  → run `spec-kitty dispatch "<request verbatim>"`\n',
    '  → **ALWAYS run `spec-kitty dispatch "<request verbatim>"` — do NOT answer directly.**\n'
    "  If you know the right profile, pass it to skip routing:\n"
    '  `spec-kitty dispatch "<request verbatim>" --profile <profile-id>`\n'
    "  Reason: `spec-kitty dispatch` loads governance context, routes the request,\n"
    "  and opens the Op. Skipping it produces ungoverned, untracked responses.\n"
    "  After finishing the work, close the Op with the command printed in the capsule\n"
    "  (`spec-kitty profile-invocation complete --invocation-id <id> --outcome <done|failed|abandoned>`).\n",
)
_CUSTOM_BEFORE = "# Local instructions\nKeep the bespoke workflow.\n\n"
_CUSTOM_AFTER = "\n## Local policy\nRetain the human review step.\n"


def _assert_refreshed(text: str) -> None:
    assert text.count(SECTION_OPEN) == text.count(SECTION_CLOSE) == 1
    before, section = text.split(SECTION_OPEN)
    block, after = section.split(SECTION_CLOSE)
    assert before == _CUSTOM_BEFORE
    assert after == "\n" + _CUSTOM_AFTER
    assert "**Spec Kitty v3.2.0rc39**" in block
    assert "v3.2.0rc38" not in block
    assert "**Full mission**" in block and "`/spec-kitty.specify`" in block
    assert "**Lightweight dispatch**" in block and "no mission created" in block
    assert 'spec-kitty dispatch "<request verbatim>"' in block
    assert "do NOT answer directly" in block
    assert "--profile <profile-id>" in block
    assert "loads governance context" in block and "opens the Op" in block
    assert "close the Op" in block
    assert "profile-invocation complete --invocation-id <id>" in block
    assert "--outcome <done|failed|abandoned>" in block
    assert '  → run `spec-kitty dispatch "<request verbatim>"`\n' not in block


def _seed_managed_block(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CUSTOM_BEFORE + _MANAGED_OLD_BLOCK + _CUSTOM_AFTER, encoding="utf-8")


# ---------------------------------------------------------------------------
# Project factory helpers
# ---------------------------------------------------------------------------


def _make_project(
    tmp_path: Path,
    agents: list[str] | None = None,
    agent_dirs: list[str] | None = None,
) -> Path:
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    avail = agents or []
    lines = "agents:\n  available:\n" + "".join(f"    - {a}\n" for a in avail) if avail else "agents:\n  available: []\n"
    (tmp_path / ".kittify" / "config.yaml").write_text(lines, encoding="utf-8")
    for d in agent_dirs or []:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _apply_with_mocks(
    migration: RefreshOrientationBlockMigration,
    project_path: Path,
    dry_run: bool = False,
) -> object:
    with (
        patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
        patch("importlib.metadata.version", return_value="3.2.0rc39"),
        patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
    ):
        mock_checker_cls.return_value.get_available_version.return_value = None
        return migration.apply(project_path, dry_run=dry_run)


def _detect_with_mocks(migration: RefreshOrientationBlockMigration, project_path: Path) -> bool:
    with (
        patch("specify_cli.session_presence.manager.UpgradeChecker") as mock_checker_cls,
        patch("importlib.metadata.version", return_value="3.2.0rc39"),
        patch("specify_cli.compat.plan", side_effect=Exception("no compat")),
    ):
        mock_checker_cls.return_value.get_available_version.return_value = None
        return migration.detect(project_path)


# ---------------------------------------------------------------------------
# TestDetect
# ---------------------------------------------------------------------------


class TestDetect:
    def test_false_when_no_kittify(self, tmp_path: Path) -> None:
        migration = RefreshOrientationBlockMigration()
        assert migration.detect(tmp_path) is False

    def test_false_when_no_presence_installed(self, tmp_path: Path) -> None:
        """Absent blocks are the install migration's job — detect() must be False."""
        project = _make_project(tmp_path, agents=["codex"])
        # No AGENTS.md written → has_presence() is False → not our job
        migration = RefreshOrientationBlockMigration()
        assert _detect_with_mocks(migration, project) is False

    def test_false_when_block_already_current(self, tmp_path: Path) -> None:
        """detect() is False when the installed block already matches render()."""
        project = _make_project(tmp_path, agents=["codex"])
        migration = RefreshOrientationBlockMigration()
        # First write fresh content via apply
        _seed_managed_block(project / "AGENTS.md")
        _apply_with_mocks(migration, project)
        _assert_refreshed((project / "AGENTS.md").read_text(encoding="utf-8"))
        # Now detect() must see no staleness
        assert _detect_with_mocks(migration, project) is False

    def test_true_when_agents_md_block_is_stale(self, tmp_path: Path) -> None:
        """detect() is True when AGENTS.md contains an old orientation block."""
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        migration = RefreshOrientationBlockMigration()
        assert _detect_with_mocks(migration, project) is True

    def test_true_when_non_agents_writer_block_is_stale(self, tmp_path: Path) -> None:
        """detect() is True when a cursor block contains old orientation content."""
        project = _make_project(tmp_path, agents=["cursor"], agent_dirs=[".cursor"])
        rules_file = project / ".cursor" / "rules" / "spec-kitty.mdc"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        _seed_managed_block(rules_file)
        migration = RefreshOrientationBlockMigration()
        assert _detect_with_mocks(migration, project) is True


# ---------------------------------------------------------------------------
# TestApply
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_refreshes_stale_agents_md_block(self, tmp_path: Path) -> None:
        """Stale AGENTS.md block is replaced with current content."""
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project)

        assert result.success  # type: ignore[union-attr]
        text = (project / "AGENTS.md").read_text(encoding="utf-8")
        _assert_refreshed(text)

    def test_apply_refreshes_stale_non_agents_writer_block(self, tmp_path: Path) -> None:
        """Stale cursor block is replaced with current content."""
        project = _make_project(tmp_path, agents=["cursor"], agent_dirs=[".cursor"])
        rules_file = project / ".cursor" / "rules" / "spec-kitty.mdc"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        _seed_managed_block(rules_file)
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project)

        assert result.success  # type: ignore[union-attr]
        text = rules_file.read_text(encoding="utf-8")
        _assert_refreshed(text)

    def test_apply_skips_current_block(self, tmp_path: Path) -> None:
        """apply() is a no-op when the block is already current."""
        project = _make_project(tmp_path, agents=["codex"])
        migration = RefreshOrientationBlockMigration()
        # Write current block
        _seed_managed_block(project / "AGENTS.md")
        _apply_with_mocks(migration, project)
        current = (project / "AGENTS.md").read_bytes()
        _assert_refreshed(current.decode("utf-8"))
        before = (project / "AGENTS.md").stat()
        # Second call — nothing stale
        result = _apply_with_mocks(migration, project)
        assert result.success  # type: ignore[union-attr]
        assert result.changes_made == []  # type: ignore[union-attr]
        assert (project / "AGENTS.md").read_bytes() == current
        assert (project / "AGENTS.md").stat().st_mtime_ns == before.st_mtime_ns

    def test_apply_skips_missing_presence(self, tmp_path: Path) -> None:
        """apply() does not write anything when no block is installed."""
        project = _make_project(tmp_path, agents=["codex"])
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project)
        assert result.success  # type: ignore[union-attr]
        assert result.changes_made == []  # type: ignore[union-attr]
        assert not (project / "AGENTS.md").exists()

    def test_apply_dry_run_no_filesystem_changes(self, tmp_path: Path) -> None:
        """dry_run=True reports pending refreshes but writes nothing."""
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        before = (project / "AGENTS.md").read_bytes()
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project, dry_run=True)
        assert result.success  # type: ignore[union-attr]
        assert len(result.changes_made) >= 1  # type: ignore[union-attr]
        # File must be unchanged
        assert (project / "AGENTS.md").read_bytes() == before

    def test_apply_dry_run_change_describes_harness(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project, dry_run=True)
        assert any("codex" in change for change in result.changes_made)  # type: ignore[union-attr]

    def test_apply_idempotent(self, tmp_path: Path) -> None:
        """Applying twice on a stale block leaves exactly one orientation section."""
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        migration = RefreshOrientationBlockMigration()
        _apply_with_mocks(migration, project)
        first = (project / "AGENTS.md").read_text(encoding="utf-8")
        _assert_refreshed(first)
        _apply_with_mocks(migration, project)
        text = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert text == first
        _assert_refreshed(text)

    def test_apply_returns_change_entry_per_stale_key(self, tmp_path: Path) -> None:
        """apply() reports one change entry per refreshed harness key."""
        project = _make_project(tmp_path, agents=["codex"])
        _seed_managed_block(project / "AGENTS.md")
        migration = RefreshOrientationBlockMigration()
        result = _apply_with_mocks(migration, project)
        assert len(result.changes_made) == 1  # type: ignore[union-attr]
        assert "codex" in result.changes_made[0]  # type: ignore[union-attr]
        _assert_refreshed((project / "AGENTS.md").read_text(encoding="utf-8"))

    @pytest.mark.parametrize(
        "agent,relative_path",
        [
            ("codex", "AGENTS.md"),
            ("cursor", ".cursor/rules/spec-kitty.mdc"),
        ],
    )
    @pytest.mark.parametrize(
        "block",
        [
            pytest.param(_OLD_BLOCK, id="unproven-historical-body"),
            pytest.param(_MANAGED_OLD_BLOCK.replace("Two usage patterns:", "My usage policy:"), id="edited-body"),
            pytest.param(_MANAGED_OLD_BLOCK.replace(SECTION_CLOSE, ""), id="missing-close"),
        ],
    )
    def test_apply_preserves_unproven_block(
        self,
        tmp_path: Path,
        agent: str,
        relative_path: str,
        block: str,
    ) -> None:
        project = _make_project(tmp_path, agents=[agent])
        path = project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        original = _CUSTOM_BEFORE + block + _CUSTOM_AFTER
        path.write_text(original, encoding="utf-8")
        before = path.stat()
        if SECTION_CLOSE not in block:
            with pytest.raises(ValueError, match="Duplicate or unbalanced orientation markers"):
                _apply_with_mocks(RefreshOrientationBlockMigration(), project)
        else:
            _apply_with_mocks(RefreshOrientationBlockMigration(), project)
        # Do not approve the migration's change reporting for preserved content.
        assert path.read_text(encoding="utf-8") == original
        assert path.stat().st_mtime_ns == before.st_mtime_ns

    def test_refresh_assertions_reject_output_regressions(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, agents=["codex"])
        path = project / "AGENTS.md"
        _seed_managed_block(path)
        _apply_with_mocks(RefreshOrientationBlockMigration(), project)
        text = path.read_text(encoding="utf-8")
        _assert_refreshed(text)
        mutations = [
            text.replace("v3.2.0rc39", "v3.2.0rc38"),
            text.replace(SECTION_CLOSE, ""),
            text.replace(SECTION_OPEN, SECTION_OPEN + SECTION_OPEN),
            text.replace(_CUSTOM_BEFORE, ""),
            text.replace(_CUSTOM_AFTER, ""),
            text.replace("/spec-kitty.specify", "/other"),
            text.replace('spec-kitty dispatch "<request verbatim>"', "answer directly"),
            text.replace("do NOT answer directly", "answer directly"),
            text.replace("--profile <profile-id>", ""),
            text.replace("loads governance context", ""),
            text.replace("opens the Op", ""),
            text.replace("profile-invocation complete --invocation-id <id>", ""),
        ]
        for mutated in mutations:
            assert mutated != text
            with pytest.raises(AssertionError):
                _assert_refreshed(mutated)


# ---------------------------------------------------------------------------
# TestMigrationAttributes
# ---------------------------------------------------------------------------


class TestMigrationAttributes:
    def test_migration_id(self) -> None:
        assert RefreshOrientationBlockMigration.migration_id == "3_2_0rc39_refresh_orientation_block"

    def test_runs_on_worktrees_is_false(self) -> None:
        assert RefreshOrientationBlockMigration.runs_on_worktrees is False

    def test_target_version(self) -> None:
        assert RefreshOrientationBlockMigration.target_version == "3.2.0rc39"

    def test_migration_registered_in_registry(self) -> None:
        migration_ids = {m.migration_id for m in MigrationRegistry.get_all()}
        assert "3_2_0rc39_refresh_orientation_block" in migration_ids
