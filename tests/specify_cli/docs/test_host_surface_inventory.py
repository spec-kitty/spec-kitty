"""WP05 / FR-001 / NFR-003 — Host-surface parity matrix coverage test.

Asserts that every supported host surface from AGENT_DIRS has exactly one row
in docs/architecture/host-surface-parity.md, and that every row has a valid parity_status.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[3]
PARITY_DOC = REPO_ROOT / "docs/architecture/host-surface-parity.md"

# Pulled from src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py::AGENT_DIRS
# plus Agent Skills surfaces.
EXPECTED_SURFACES = frozenset({
    "claude", "copilot", "gemini", "cursor", "qwen",
    "opencode", "windsurf", "kilocode", "auggie",
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    "q", "kiro", "agent", "codex", "vibe", "pi", "letta", "llxprt",
})

VALID_PARITY_STATUS = {"at_parity", "partial", "missing"}


def _parse_rows() -> list[dict[str, str]]:
    """Parse the parity matrix table from docs/architecture/host-surface-parity.md."""
    content = PARITY_DOC.read_text()
    # Find the first markdown table in the doc
    lines = content.splitlines()
    in_table = False
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("| surface_key"):
            header = [c.strip() for c in line.strip("|").split("|")]
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != len(header or []):
                continue
            rows.append(dict(zip(header or [], cells)))
        elif in_table and not line.startswith("|"):
            in_table = False
    return rows


def test_parity_doc_exists() -> None:
    assert PARITY_DOC.exists(), "docs/host-surface-parity.md must exist after WP05"


def test_every_surface_has_a_row() -> None:
    rows = _parse_rows()
    present_surfaces = {row["surface_key"] for row in rows}
    missing = EXPECTED_SURFACES - present_surfaces
    assert not missing, f"Missing rows for surfaces: {sorted(missing)}"


def test_no_duplicate_surface_rows() -> None:
    rows = _parse_rows()
    keys = [row["surface_key"] for row in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"Duplicate rows for surfaces: {sorted(dupes)}"


def test_every_row_has_valid_parity_status() -> None:
    rows = _parse_rows()
    for row in rows:
        assert row["parity_status"] in VALID_PARITY_STATUS, (
            f"Invalid parity_status for {row['surface_key']}: {row['parity_status']}"
        )


def test_every_non_parity_row_has_notes() -> None:
    """FR-006 — pointer/partial/missing rows must explain the gap in notes."""
    rows = _parse_rows()
    for row in rows:
        if row["parity_status"] != "at_parity" or row.get("guidance_style") == "pointer":
            assert row.get("notes"), (
                f"Row {row['surface_key']} (parity_status={row['parity_status']}, "
                f"guidance_style={row.get('guidance_style')}) must have a non-empty notes column."
            )
