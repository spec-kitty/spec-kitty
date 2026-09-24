"""``issue-verdict`` self-materialization hardening (WP02, FR-006 / FR-007 / #4970).

Two halves land together (see ``work/epic-5001-research/followup-paula.md`` §2/§3):

* FR-006 — the S-C coord write gate refuses a self-materialization write onto a
  stale local-head coord branch that already carries committed matrix rows, so a
  second ``issue-verdict`` from an UNMATERIALIZED coord surface can no longer
  clobber committed coordination state.
* FR-007 — ``do_issue_verdict`` resolves its write surface through the fail-closed
  ``resolve_for_write`` up-front (translating ``ActionContextError`` →
  ``IssueVerdictError``), instead of silently degrading its read to the primary
  surface and relying on the tail write-seam gate to catch the clobber.

These are INTEGRATION tests: they drive the REAL write-seam
(``do_issue_verdict`` → ``write_issue_matrix`` → ``commit_for_mission``) against a
real on-disk coord mission, because a faked write never materializes the coord
JSON. The coord fixture (``_build_coord_mission_for_matrix``) and the flat/no-coord
primitives are reused verbatim from the sibling integration suites (C-001 — one
canonical construction sequence, not a parallel one); those files are NOT edited.
``tests/integration/conftest.py`` is likewise not touched (post-tasks paula M1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.issue_verdict import (
    IssueVerdictError,
    do_issue_verdict,
)

# Reused verbatim — do NOT duplicate the coord/flat fixture-construction sequences.
from tests.integration.test_accept_matrix_coord_partition import (
    _build_coord_mission_for_matrix,
)
from tests.integration.test_placement_partition_golden_path import (
    _commit,
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FLAT_WORK_BRANCH = "mission-work"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)


def _coord_committed_rows(repo_root: Path, coord_branch: str, slug: str) -> set[str]:
    """Issue keys committed on the coordination surface's ``issue-matrix.json``."""
    result = _git(repo_root, "show", f"{coord_branch}:kitty-specs/{slug}/issue-matrix.json")
    if result.returncode != 0:
        return set()
    return set(json.loads(result.stdout).get("rows", {}).keys())


def _coord_branch(repo_root: Path, slug: str) -> str:
    meta = json.loads((repo_root / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    return str(meta["coordination_branch"])


# ===========================================================================
# (e) second verdict on a stale local-head coord ⇒ committed rows survive
# ===========================================================================


def test_second_verdict_from_stale_coord_preserves_committed_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-006/#4970 core: unmaterialize a coord branch that carries #1111, then a
    second ``issue-verdict`` must REFUSE (fail-closed) and leave #1111 intact."""
    result, coord_root, _coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug
    coord_branch = _coord_branch(tmp_path, slug)
    monkeypatch.chdir(tmp_path)

    # Seed #1111 — materializes the coord worktree and commits the row on coord.
    seed = do_issue_verdict(mission=slug, issue="#1111", verdict="fixed", actor="tester", wp="WP01", repo_root=tmp_path)
    assert seed["ok"] is True, seed
    assert _coord_committed_rows(tmp_path, coord_branch, slug) == {"#1111"}, "fixture precondition: #1111 committed on coord"

    # Unmaterialize the coord worktree; the coord BRANCH (with #1111) stays a local head.
    removed = _git(tmp_path, "worktree", "remove", "--force", str(coord_root))
    assert removed.returncode == 0, removed.stderr
    assert not coord_root.exists(), "coord worktree must be unmaterialized for the repro"

    # A second verdict from the unmaterialized surface must fail CLOSED, not clobber.
    with pytest.raises(IssueVerdictError) as excinfo:
        do_issue_verdict(mission=slug, issue="#2222", verdict="fixed", actor="tester", wp="WP01", repo_root=tmp_path)
    assert excinfo.value.code == "coord_surface_unmaterialized", excinfo.value.code

    # The committed coordination surface is intact — #1111 survives, #2222 never landed.
    rows = _coord_committed_rows(tmp_path, coord_branch, slug)
    assert rows == {"#1111"}, f"a refusal must leave the committed coord surface intact, got {sorted(rows)}"


# ===========================================================================
# (f) a normal materialized-coord verdict still succeeds (no false-refuse)
# ===========================================================================


def test_materialized_coord_verdicts_succeed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: repeated verdicts against a MATERIALIZED coord surface merge and
    succeed — the hardened gate never false-refuses the legitimate flow."""
    result, _coord_root, _coord_feature_dir = _build_coord_mission_for_matrix(tmp_path)
    slug = result.mission_slug
    coord_branch = _coord_branch(tmp_path, slug)
    monkeypatch.chdir(tmp_path)

    first = do_issue_verdict(mission=slug, issue="#3333", verdict="fixed", actor="tester", wp="WP01", repo_root=tmp_path)
    assert first["ok"] is True, first

    second = do_issue_verdict(mission=slug, issue="#4444", verdict="in-mission", actor="tester", wp="WP01", repo_root=tmp_path)
    assert second["ok"] is True, second

    rows = _coord_committed_rows(tmp_path, coord_branch, slug)
    assert rows == {"#3333", "#4444"}, f"both rows must survive a merge write on a materialized coord, got {sorted(rows)}"


# ===========================================================================
# (g) a flat / no-coord mission is not false-refused (F12)
# ===========================================================================


def test_flat_mission_verdict_is_not_false_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F12: a SINGLE_BRANCH mission declares no ``coordination_branch``; the
    fail-closed reroute + gate must no-op (return early), never refuse."""
    _init_git_repo(tmp_path, branch=_FLAT_WORK_BRANCH)
    result = _create_mission(tmp_path, "flat-selfmat-hardening", MissionTopology.SINGLE_BRANCH)
    spec_file = result.feature_dir / "spec.md"
    spec_file.write_text("# Spec — flat-selfmat-hardening\n", encoding="utf-8")
    _commit(tmp_path, str(spec_file.relative_to(tmp_path)), "feat: add spec")
    monkeypatch.chdir(tmp_path)

    payload = do_issue_verdict(mission=result.mission_slug, issue="#5555", verdict="fixed", actor="tester", repo_root=tmp_path)
    assert payload["ok"] is True, payload

    # The row lands on the PRIMARY feature dir for a flat mission.
    matrix = result.feature_dir / "issue-matrix.json"
    assert matrix.exists(), f"flat mission must write the matrix to the primary surface at {matrix}"
    rows = set(json.loads(matrix.read_text(encoding="utf-8")).get("rows", {}).keys())
    assert rows == {"#5555"}, f"the flat verdict must record #5555 without refusal, got {sorted(rows)}"
