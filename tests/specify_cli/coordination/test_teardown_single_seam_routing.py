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

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.consolidation.state import ConsolidationState

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


def test_mission_type_routes_teardown_through_the_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavioural seam-routing guard (#5346 row 7, FIX): a literal grep for the
    string ``teardown_coordination_topology`` is a Literal-Scan Trap — moving the
    function reds it, and a caller that imports the name but stops calling it
    passes. ``mission_type.py`` imports the seam LAZILY inside the function, so
    intercepting it by dotted path and calling the real caller proves the actual
    routing behaviourally instead of textually."""
    from specify_cli.cli.commands import mission_type
    from specify_cli.coordination.workspace import CoordinationWorkspace

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        "specify_cli.coordination.teardown.teardown_coordination_topology",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(CoordinationWorkspace, "is_present", classmethod(lambda cls, *a, **kw: False))

    slug = "seam-routing-repro"
    mid8 = "01SEAMR0"
    mission_type._teardown_coordination_worktree(tmp_path, slug, mid8, quiet=True)

    assert len(calls) == 1, f"expected exactly one teardown_coordination_topology call, got {len(calls)}"
    args, _kwargs = calls[0]
    assert args[:3] == (tmp_path, slug, mid8), f"seam not called with the resolved mission identity: {args[:3]}"


_ABORT_MISSION_ID = "01SEAMABORT00000000000001"


def _init_seam_abort_repo(tmp_path: Path, slug: str) -> Path:
    """Minimal real git repo + primary meta.json, enough for ``--abort`` teardown
    resolution to reach the seam call (mirrors ``test_executor_coverage.py``'s
    ``_init_abort_repo`` fixture)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    fdir = repo / "kitty-specs" / slug
    fdir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_id": _ABORT_MISSION_ID,
        "mid8": "01SEAMAB",
        "coordination_branch": f"kitty/mission-{slug}",
        "target_branch": "main",
    }
    (fdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed mission"], check=True)
    return repo


def test_consolidate_abort_routes_teardown_through_the_seam(tmp_path: Path) -> None:
    """Behavioural seam-routing guard (#5346 row 7, FIX): the ``consolidate.py``
    sibling of the mission_type case above. ``_teardown_coordination_for_abort``
    also imports the seam lazily inside the function, so intercepting it by
    dotted path over a minimal real git+meta fixture proves the routing without
    a literal string scan."""
    from specify_cli.cli.commands.consolidate import _teardown_coordination_for_abort

    slug = "seam-routing-abort-repro"
    repo = _init_seam_abort_repo(tmp_path, slug)
    state = ConsolidationState(
        mission_id=_ABORT_MISSION_ID,
        mission_slug=slug,
        target_branch="main",
        wp_order=[],
    )

    with patch("specify_cli.coordination.teardown.teardown_coordination_topology") as mock_teardown:
        _teardown_coordination_for_abort(repo, slug, (_ABORT_MISSION_ID, state))

    mock_teardown.assert_called_once()
    args, kwargs = mock_teardown.call_args
    assert args[:3] == (repo, slug, "01SEAMAB"), f"seam not called with the resolved mission identity: {args[:3]}"
    assert kwargs.get("persist") is False, "abort must disable the seam's completion persistence (#4863)"
