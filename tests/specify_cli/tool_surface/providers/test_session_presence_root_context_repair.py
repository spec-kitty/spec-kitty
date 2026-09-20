"""WP01 Seam A — root context repair regression (FR-001..004, FR-009).

A stale root-level orientation file (``GEMINI.md`` / ``LLXPRT.md``) with the
harness command dir (``.gemini/`` / ``.llxprt/``) absent must be *repaired* by
``SessionPresenceProvider.repair``, not dispositioned ``not_applicable`` and
silently skipped.  This is the observable end of the surgical registry fix: once
the writer is applicable, a detected-stale surface flows to ``repaired`` (or
``failed`` on a real write error), never to ``skipped``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.tool_surface.providers.session_presence import (
    SessionPresenceProvider,
    context_file_definition,
)
from specify_cli.tool_surface.status import STATE_STALE, _surface_id

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _seed_stale(target: Path) -> None:
    """Write a canonical orientation block stamped at an outdated version."""
    target.parent.mkdir(parents=True, exist_ok=True)
    block = SessionPresenceContent(
        version="0.1.0",
        project_slug="unknown",
        health="healthy",
        available_version=None,
    ).render()
    target.write_text(block, encoding="utf-8")


@pytest.mark.parametrize(
    ("harness", "context_file"),
    [("gemini", "GEMINI.md"), ("llxprt", "LLXPRT.md")],
)
def test_stale_root_context_is_repaired_without_harness_dir(harness: str, context_file: str, tmp_path: Path) -> None:
    """A stale root context file with no harness dir lands in repaired, not skipped."""
    _seed_stale(tmp_path / context_file)
    # Configure the harness so the repair path treats it as selected.
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(f"agents:\n  available: [{harness}]\n", encoding="utf-8")

    provider = SessionPresenceProvider()
    instances = provider.expand(context_file_definition(), harness, tmp_path)
    statuses = [provider.probe(instance) for instance in instances]
    assert [s.state for s in statuses] == [STATE_STALE]

    surface_id = _surface_id(statuses[0].instance)
    result = provider.repair(tmp_path, statuses)

    assert surface_id in result.repaired
    assert surface_id not in result.skipped
    assert not result.failed
