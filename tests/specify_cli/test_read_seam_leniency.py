"""WP06 — diagnostic-cluster read-seam migration + NFR-001 leniency pins.

Ledger authority: ``docs/development/read-side-seam-classification.md`` (§ WP06).

- **migrate-fail-loud** (must route through ``placement_seam(...).read_dir``):
  ``coordination/status_transition.py`` (3), ``decisions/service.py`` (1),
  ``review/cycle.py`` (1).
- **stay-lenient** (leave bypass; WP08 allow-list descriptors below):
  ``status/aggregate.py``, ``retrospective/summary.py`` (``dashboard/scanner.py``
  and ``dossier/api.py`` left with the bundled dashboard, #5530). ``retrospective/writer.py`` has zero real call sites.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.coordination import status_transition
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.decisions import service as decisions_service
from specify_cli.retrospective import summary as retrospective_summary
from specify_cli.review import cycle as review_cycle
from specify_cli.status import aggregate as status_aggregate

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_ID = "01KYHP67DIAGNOSTICWP06TEST"
MID8 = MISSION_ID[:8]
MISSION_SLUG = "read-seam-diag"
MISSION_DIR_NAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIR_NAME}-coord"
WP_SLUG = "WP01"

# NOTE: the former ``test_diagnostic_cluster_retains_only_ledger_approved_lenient_sites``
# and its private AST visitor lived here. Both are gone: the whole-tree
# structural gate ``tests/architectural/test_no_read_side_bypass.py`` already
# scans every module under ``src/`` (these modules included) with the SAME
# grammar, reconciles the residuals against the WP02 ledger, and REDS on any
# un-allow-listed bypass. This file keeps only behavioural pins.


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_repo(tmp_path: Path, *, deleted_coord: bool) -> Path:
    """Seed a real git repo with a mission; optionally declare a missing coord branch."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "read-seam-diag@example.test")
    _git(tmp_path, "config", "user.name", "Read Seam Diagnostic")
    _git(tmp_path, "commit", "--allow-empty", "-qm", "init")

    mission_dir = tmp_path / "kitty-specs" / MISSION_DIR_NAME
    (mission_dir / "tasks" / WP_SLUG).mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "mid8": MID8,
        "slug": MISSION_DIR_NAME,
        "friendly_name": MISSION_SLUG,
        "mission_type": "software-dev",
    }
    if deleted_coord:
        meta["coordination_branch"] = COORD_BRANCH
        meta["topology"] = "coord"
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# tasks\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "seed mission")
    return mission_dir


# ---------------------------------------------------------------------------
# T014 — NFR-001 leniency (stay-lenient readers must not raise)
# ---------------------------------------------------------------------------


def test_aggregate_find_meta_path_tolerates_deleted_coord(tmp_path: Path) -> None:
    """Stay-lenient ``_find_meta_path`` must not raise on a deleted coord declaration."""
    mission_dir = _seed_repo(tmp_path, deleted_coord=True)

    meta_path, primary_dir = status_aggregate.MissionStatus._find_meta_path(tmp_path, MISSION_DIR_NAME)

    assert meta_path == mission_dir / "meta.json"
    assert primary_dir.resolve() == mission_dir.resolve()


def test_retrospective_summary_proposal_counts_tolerate_deleted_coord(
    tmp_path: Path,
) -> None:
    """Summary statistics reader returns zeros rather than raising on deleted coord."""
    _seed_repo(tmp_path, deleted_coord=True)

    counts = retrospective_summary._read_proposal_events(tmp_path, MISSION_DIR_NAME)

    assert counts == (0, 0, 0)


# ---------------------------------------------------------------------------
# T013/T014 — behavior preservation for migrated sites
# ---------------------------------------------------------------------------


def test_review_cycle_wp_dir_preserves_primary_home(tmp_path: Path) -> None:
    """Migrated WORK_PACKAGE_TASK review-cycle read resolves the primary tasks dir."""
    mission_dir = _seed_repo(tmp_path, deleted_coord=False)

    resolved = review_cycle._review_cycle_wp_dir(tmp_path, MISSION_DIR_NAME, WP_SLUG)

    assert resolved.resolve() == (mission_dir / "tasks" / WP_SLUG).resolve()
    assert placement_seam(tmp_path, MISSION_DIR_NAME).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK).resolve() == mission_dir.resolve()


def test_review_cycle_wp_dir_stays_silent_when_coord_deleted(tmp_path: Path) -> None:
    """PRIMARY-partition migrate site must not raise on a deleted coord branch."""
    mission_dir = _seed_repo(tmp_path, deleted_coord=True)

    resolved = review_cycle._review_cycle_wp_dir(tmp_path, MISSION_DIR_NAME, WP_SLUG)

    assert resolved.resolve() == (mission_dir / "tasks" / WP_SLUG).resolve()


def test_status_transition_primary_anchor_preserves_healthy_resolution(
    tmp_path: Path,
) -> None:
    """Migrated PRIMARY_METADATA anchors resolve the on-disk primary mission dir."""
    mission_dir = _seed_repo(tmp_path, deleted_coord=False)
    fallback = mission_dir

    resolved = status_transition._canonical_primary_feature_dir(tmp_path, MISSION_DIR_NAME, fallback)

    assert resolved.resolve() == mission_dir.resolve()


def test_decisions_mission_dir_fails_loud_when_coord_deleted(tmp_path: Path) -> None:
    """Migrated STATUS_STATE decisions read must raise CoordinationBranchDeleted."""
    _seed_repo(tmp_path, deleted_coord=True)

    with pytest.raises(CoordinationBranchDeleted) as exc_info:
        decisions_service._mission_dir(tmp_path, MISSION_DIR_NAME)

    assert exc_info.value.error_code == "COORDINATION_BRANCH_DELETED"
    assert COORD_BRANCH in str(exc_info.value)


def test_decisions_mission_dir_preserves_healthy_status_home(tmp_path: Path) -> None:
    """Healthy (no coord topology) decisions STATUS read lands on the primary dir."""
    mission_dir = _seed_repo(tmp_path, deleted_coord=False)

    resolved = decisions_service._mission_dir(tmp_path, MISSION_DIR_NAME)

    assert resolved.resolve() == mission_dir.resolve()
