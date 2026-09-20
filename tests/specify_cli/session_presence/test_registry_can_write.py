"""WP01 Seam A — registry writability + detect/repair parity (FR-001..004, NFR-002).

The root-level orientation writers (``gemini`` → ``GEMINI.md``, ``llxprt`` →
``LLXPRT.md``) must be writable at the repo root even when the harness command
directory (``.gemini/`` / ``.llxprt/``) is absent, so ``doctor tool-surfaces
--fix`` / ``upgrade`` refresh a stale root-level block instead of silently
skipping it.  These tests pin:

* T001 — the registry ``gemini`` / ``llxprt`` writers report ``can_write`` at a
  bare repo root (no harness dir).
* T004 — NFR-002 parity: for every ``MarkdownRulesWriter`` in the registry, the
  disk state that makes the provider probe report ``STALE`` is the same state
  that makes the writer repair-applicable (``can_write`` True).
* T005 — a configured ``gemini`` / ``llxprt`` project with the harness dir
  absent now backfills the root context file (migration ``detect`` and manager
  ``update`` both flip to writable).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
from specify_cli.session_presence.writers.registry import WRITER_REGISTRY, get_writer
from specify_cli.tool_surface.providers.session_presence import (
    SessionPresenceProvider,
    context_file_definition,
    rule_definition,
)
from specify_cli.tool_surface.status import STATE_STALE

pytestmark = [pytest.mark.unit, pytest.mark.fast]


_STALE_VERSION = "0.1.0"


def _seed_stale(target: Path) -> None:
    """Write a full, canonical orientation block stamped at an old version."""
    target.parent.mkdir(parents=True, exist_ok=True)
    block = SessionPresenceContent(
        version=_STALE_VERSION,
        project_slug="unknown",
        health="healthy",
        available_version=None,
    ).render()
    target.write_text(block, encoding="utf-8")


# ---------------------------------------------------------------------------
# T001 — registry writers writable at a bare repo root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("harness", ["gemini", "llxprt"])
def test_root_context_writer_can_write_without_harness_dir(harness: str, tmp_path: Path) -> None:
    """gemini/llxprt must be writable at the repo root with no harness dir present."""
    writer = get_writer(harness)
    assert isinstance(writer, MarkdownRulesWriter)
    # No .gemini/ or .llxprt/ directory exists under tmp_path.
    assert writer.can_write(tmp_path) is True


# ---------------------------------------------------------------------------
# T004 — NFR-002 parity: detect-applicable == repair-applicable
# ---------------------------------------------------------------------------


def _markdown_registry_writers() -> list[tuple[str, MarkdownRulesWriter]]:
    return [(key, w) for key, w in WRITER_REGISTRY.items() if isinstance(w, MarkdownRulesWriter)]


@pytest.mark.parametrize(
    ("harness", "writer"),
    _markdown_registry_writers(),
    ids=[key for key, _ in _markdown_registry_writers()],
)
def test_detect_stale_state_is_repair_applicable(harness: str, writer: MarkdownRulesWriter, tmp_path: Path) -> None:
    """The disk state that makes probe report STALE must also be repair-applicable.

    Seeding an outdated managed block at the writer's own ``rules_path`` (creating
    only the parents the file itself needs) is the exact detect-input the provider
    reads.  In that same state the writer must report ``can_write`` — otherwise a
    detected-stale surface would be silently skipped at repair.
    """
    _seed_stale(tmp_path / writer.rules_path)

    provider = SessionPresenceProvider()
    instances = provider.expand(context_file_definition(), harness, tmp_path) + provider.expand(rule_definition(), harness, tmp_path)
    statuses = [provider.probe(instance) for instance in instances]

    # detect side: the seeded outdated block is observed as STALE.
    assert [s.state for s in statuses] == [STATE_STALE]
    # repair side: the same on-disk state is repair-applicable.
    assert writer.can_write(tmp_path) is True


# ---------------------------------------------------------------------------
# T005 — configured harness backfills the root context file when dir is absent
# ---------------------------------------------------------------------------


def _write_config(root: Path, available: list[str]) -> None:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    listing = ", ".join(available)
    (root / ".kittify" / "config.yaml").write_text(f"agents:\n  available: [{listing}]\n", encoding="utf-8")


@pytest.mark.parametrize("harness", ["gemini", "llxprt"])
def test_migration_detects_pending_root_context_without_harness_dir(harness: str, tmp_path: Path) -> None:
    """m_3_3_0 migration must detect a pending root context file with no harness dir."""
    from specify_cli.upgrade.migrations.m_3_3_0_session_presence_all_harnesses import (
        SessionPresenceAllHarnessesMigration,
    )

    _write_config(tmp_path, [harness])
    # No .gemini/ or .llxprt/ directory, and no root context file yet.
    migration = SessionPresenceAllHarnessesMigration()
    assert migration.detect(tmp_path) is True


@pytest.mark.parametrize("harness", ["gemini", "llxprt"])
def test_manager_update_backfills_root_context_without_harness_dir(harness: str, tmp_path: Path) -> None:
    """SessionPresenceManager treats the root context writer as writable (backfill)."""
    from specify_cli.core.agent_config import AgentConfig
    from specify_cli.session_presence.manager import SessionPresenceManager

    _write_config(tmp_path, [harness])
    manager = SessionPresenceManager(project_root=tmp_path, agent_config=AgentConfig(available=[harness]))
    result = manager.update(dry_run=True)

    assert any(harness in change for change in result.changes)
    assert not result.warnings
