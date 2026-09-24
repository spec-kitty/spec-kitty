"""Repro #4970 — ``agent issue-verdict`` from an UNMATERIALIZED coord overwrites
the committed coordination surface (data loss).

Mechanism (DEBRIEF §4, root R2 / S-C): the surface-authority resolver's
loud-primary-fallback is correct for READS, but the WRITE callers (``issue-verdict``,
``implement``) reuse it with no fail-closed write gate. When the coordination
worktree is not materialized (but the coord branch still exists and carries a
committed ``issue-matrix.json``), a new ``issue-verdict`` write re-seeds the
surface from a degraded/empty read and re-materializes coord — clobbering the
previously-committed rows instead of merging into them. It should REFUSE (fail
closed) or preserve the committed surface; it must never silently overwrite it.
Backstopped by the surface-authority WRITE gate (S-C, WP07) (+ S-D detects).

RED-first: driven through the REAL ``spec-kitty agent issue-verdict`` CLI (no
``_run_git`` / subprocess mocking). Today the second verdict exits 0 and the first
committed row is lost → the "prior row preserved" assertion fails →
``xfail(strict=True)``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _coord_issue_rows(mission: CoordMission) -> set[str]:
    """Issue keys committed on the coordination surface's ``issue-matrix.json``."""
    result = subprocess.run(
        ["git", "-C", str(mission.repo), "show", f"{mission.coord_branch}:kitty-specs/{mission.slug}/issue-matrix.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return set(json.loads(result.stdout).get("rows", {}).keys())


def test_4970_issue_verdict_must_not_overwrite_unmaterialized_coord_surface(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4970A")

    # Seed a first verdict — commits row #1111 onto the coordination surface.
    seed = run_terminus(
        mission,
        ["agent", "issue-verdict", "--mission", mission.slug, "--issue", "#1111", "--verdict", "fixed", "--actor", "tester", "--wp", "WP01"],
    )
    assert seed.returncode == 0, f"seed verdict should succeed:\n{seed.stdout}\n{seed.stderr}"
    assert _coord_issue_rows(mission) == {"#1111"}, "fixture precondition: #1111 committed on coord"

    # Unmaterialize the coordination worktree; the coord BRANCH (with #1111) remains.
    coord_wt = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    subprocess.run(
        ["git", "-C", str(mission.repo), "worktree", "remove", "--force", str(coord_wt)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not coord_wt.exists(), "coord worktree should be unmaterialized for the repro"

    # A new verdict from the unmaterialized surface must not destroy #1111.
    second = run_terminus(
        mission,
        ["agent", "issue-verdict", "--mission", mission.slug, "--issue", "#2222", "--verdict", "fixed", "--actor", "tester", "--wp", "WP01"],
    )

    rows = _coord_issue_rows(mission)
    if second.returncode == 0:
        assert "#1111" in rows, (
            f"issue-verdict from an unmaterialized coord clobbered the committed coord surface "
            f"(#1111 lost; rows now {sorted(rows)}) — a WRITE degraded to a fresh/empty surface (#4970)"
        )
    else:
        # Post-fix refusal: the committed coord surface must be left intact.
        assert "#1111" in rows, "a refusal must leave the committed coord surface intact"
