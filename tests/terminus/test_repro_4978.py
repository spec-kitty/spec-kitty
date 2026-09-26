"""Repro #4978 — the dirty-preflight residue classifier is topology-blind.

Mechanism (DEBRIEF §4, root R2 / companion C-3): ``is_coord_residue_churn``
hard-fixes ``MissionTopology.COORD`` (its own docstring says it is only valid under
coord), yet the merge dirty gate passes the full union topology-blind
(``executor.py``). On a LANES / single-branch mission (no coordination topology) a
dirty *tracked planning artifact* is therefore misclassified as coordination
residue and ``reset --hard``-ed away instead of being treated as real uncommitted
work that must block or be preserved. Fixed by threading the stored topology into
the classifier (C-3, WP08).

RED-first: driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking). A non-coord mission (meta.json without ``coordination_branch``)
carries a dirty, tracked *coord-residue-kind* artifact (``issue-matrix.md``). On a
coord mission that file's stale primary copy is legitimate residue excluded from
the dirty gate and reset away; on a NON-coord mission it is REAL uncommitted work.
Because the classifier is topology-blind (fixed at COORD) the merge excludes it
from the dirty check and ``reset --hard``s it — destroying uncommitted work. The
corrected invariant: the merge NEVER silently discards it (preserve, or refuse —
never reset). Today it is destroyed → ``xfail(strict=True)``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_DIRTY_SENTINEL = "DIRTY-UNCOMMITTED-RESIDUE-KIND-WORK-4978\n"


def _make_non_coord(mission: CoordMission) -> None:
    """Turn the fixture into a genuine LANES mission: drop ``coordination_branch``
    from meta.json, tear down the materialized coord worktree + branch, and commit
    so the only dirty entry later is the planted artifact (not coord residue)."""
    # Remove only the coordination WORKTREE (a LANES mission has no coord surface),
    # but KEEP the mission integration branch (lanes still consolidate onto it).
    coord_wt = mission.repo / ".worktrees" / f"{mission.slug}-coord"
    subprocess.run(
        ["git", "-C", str(mission.repo), "worktree", "remove", "--force", str(coord_wt)],
        capture_output=True,
        text=True,
        check=False,
    )
    meta_path = mission.feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.pop("coordination_branch", None)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(mission.repo), "add", "-A"], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(mission.repo), "commit", "-qm", "chore: LANES topology (no coord)"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_4978_dirty_planning_artifact_not_reset_as_coord_residue(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M4978A")
    _make_non_coord(mission)

    # A dirty, tracked coord-residue-KIND artifact carrying real uncommitted work.
    # (issue-matrix is a COORD-partition kind; on a non-coord mission its churn is
    # NOT residue — but the topology-blind classifier treats it as such.)
    residue_kind = mission.feature_dir / "issue-matrix.md"
    residue_kind.write_text("# issue matrix\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(mission.repo), "add", str(residue_kind)], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(mission.repo), "commit", "-qm", "docs: issue matrix"],
        check=True,
        capture_output=True,
        text=True,
    )
    residue_kind.write_text(_DIRTY_SENTINEL, encoding="utf-8")  # now dirty, uncommitted

    run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "merge", "--yes"])

    # The dirty uncommitted work must NOT have been silently reset --hard away.
    surviving = residue_kind.read_text(encoding="utf-8") if residue_kind.exists() else ""
    assert surviving == _DIRTY_SENTINEL, (
        f"dirty tracked coord-residue-kind artifact was reset --hard on a NON-coord mission (topology-blind classifier, #4978); content now: {surviving!r}"
    )
