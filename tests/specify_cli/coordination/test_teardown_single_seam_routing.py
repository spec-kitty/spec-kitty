"""FR-004 anti-rename structural guard: ONE production teardown seam.

The coordination-worktree destroy primitive
(``CoordinationWorkspace.teardown(...)``) must be invoked from exactly ONE
production location — the shared seam ``coordination/teardown.py``. Any other
production call site re-introduces the duplication this WP consolidated (and the
persist-before-destroy ordering bug it cured).

Scope (load-bearing): the guard greps **production code only**
(``src/specify_cli/**`` + ``src/runtime/**``), EXCLUDING ``tests/**`` and the
seam file itself. There are legitimate ``CoordinationWorkspace.teardown(`` calls
in tests that exercise the primitive directly (5 in
``tests/integration/test_mission_close.py`` + 5 in
``tests/specify_cli/coordination/test_workspace.py``); those are primitive-level
unit tests, NOT production teardown sites, and must survive. The scope is the
directory boundary — production dirs minus the seam file — NOT a per-call
exclusion allow-list (which would rot and silently re-admit a leaked call).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Source-scan structural (anti-rename) guard over production teardown call sites.
# Lives in the gated `tests/specify_cli/coordination/` home — the `specify-cli-rest`
# shard's `(git_repo or integration or architectural)` marker expr selects
# `architectural`. Its prior `unit` marker is selected by NO CI gate, and the
# former top-level `tests/coordination/` directory is selected by no shard at all,
# so this file ran in zero gates (gate-coverage orphan ratchet).
pytestmark = [pytest.mark.architectural]

# Locate the repo root from this test file:
# tests/specify_cli/coordination/<this> → repo.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Production source roots scanned by the guard.
_PRODUCTION_ROOTS = (
    _REPO_ROOT / "src" / "specify_cli",
    _REPO_ROOT / "src" / "runtime",
)

# The single sanctioned home for the production teardown call.
_SEAM_FILE = _REPO_ROOT / "src" / "specify_cli" / "coordination" / "teardown.py"

# Matches a real call: ``CoordinationWorkspace.teardown(`` (allowing whitespace
# between the dot members so a reformat does not slip a call past the guard).
_TEARDOWN_CALL = re.compile(r"CoordinationWorkspace\s*\.\s*teardown\s*\(")


def _production_teardown_call_sites() -> list[Path]:
    """Return every production .py file that calls CoordinationWorkspace.teardown(.

    Excludes the seam file (the one sanctioned home). Dynamically derived over
    the production directory boundary — no hardcoded site list.
    """
    seam = _SEAM_FILE.resolve()
    offenders: list[Path] = []
    for root in _PRODUCTION_ROOTS:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            if py.resolve() == seam:
                continue
            if _TEARDOWN_CALL.search(py.read_text(encoding="utf-8")):
                offenders.append(py)
    return offenders


def test_seam_file_exists_and_calls_the_primitive() -> None:
    """The seam file exists and is the one place that calls the primitive."""
    assert _SEAM_FILE.exists(), f"teardown seam missing at {_SEAM_FILE}"
    assert _TEARDOWN_CALL.search(_SEAM_FILE.read_text(encoding="utf-8")), (
        "the seam file must invoke CoordinationWorkspace.teardown( — it is the "
        "single production home for the destroy primitive"
    )


def test_zero_production_teardown_calls_outside_the_seam() -> None:
    """No production code calls CoordinationWorkspace.teardown( except the seam.

    Re-adding a direct call at any former production site (``consolidate.py``,
    ``mission_type.py``) FAILS this test.
    """
    offenders = _production_teardown_call_sites()
    rendered = "\n".join(f"  - {p.relative_to(_REPO_ROOT)}" for p in offenders)
    assert offenders == [], (
        "CoordinationWorkspace.teardown( must only be called from the shared "
        f"seam {_SEAM_FILE.relative_to(_REPO_ROOT)}; found leaked production "
        f"call site(s):\n{rendered}\n"
        "Route the teardown through coordination.teardown.teardown_coordination_topology."
    )


def test_former_production_sites_route_through_the_seam() -> None:
    """The three former production sites import the seam, not the primitive call."""
    consolidate_py = (_REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "consolidate.py").read_text(
        encoding="utf-8"
    )
    mission_type_py = (
        _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "mission_type.py"
    ).read_text(encoding="utf-8")

    for name, text in (("consolidate.py", consolidate_py), ("mission_type.py", mission_type_py)):
        assert "teardown_coordination_topology" in text, (
            f"{name} must route coordination teardown through the shared seam "
            "teardown_coordination_topology"
        )
        assert not _TEARDOWN_CALL.search(text), (
            f"{name} must NOT call CoordinationWorkspace.teardown( directly — "
            "route it through the seam"
        )
