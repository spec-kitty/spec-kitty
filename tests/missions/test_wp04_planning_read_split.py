"""WP04 (FR-006 / INV-4) — planning read-path per-kind split.

After WP01 re-partitioned the planning + identity kinds to the PRIMARY surface
(read AND write — INV-5 full symmetry), a coordination-topology mission's
planning artifacts (``spec.md`` / ``tasks.md`` / ``tasks/WP*.md`` / ...) live on
the PRIMARY feature dir. The read path, however, resolved ONE mission dir by
topology — for a coord-topology mission it returned the materialized ``-coord``
husk, where a stale pre-mission copy could shadow the real primary planning
truth (the #2062 stale-coord class on the read side).

This module pins the per-kind read split:

* a **planning** read (``_PRIMARY_ARTIFACT_KINDS``) resolves PRIMARY regardless
  of topology, even with a materialized coord husk carrying STALE content — the
  headline coord-topology variant AND the flattened-with-stale-husk variant;
* the C-005 KEEP **status** transients (#1718 create-window, #1848
  coord-deleted) are untouched — STATUS reads keep the topology-aware seam.

Red-first (DIRECTIVE_034): the coord-topology planning read resolves the stale
husk content on the pre-fix resolver (proved by reverting the planning-read leg
and observing the husk content); post-fix it resolves the primary truth. This is
a genuine behavior change, not a green-pin.

Discipline (#2071 CTn): assertions are over the **observable contract** — the
resolved planning content / directory and the unchanged transient verdicts —
never the internal call graph. Fixtures use a production-shaped real 26-char ULID
+ 8-char mid8, the canonical ``meta.json`` serializer, and real ``.worktrees``
husk paths.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.missions._read_path_resolver import (
    CoordState,
    _compose_primary_feature_dir,
    probe_coord_state,
    resolve_planning_read_dir,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVTVZS9C4D5E6F7G8H9J0K1M"
MID8 = MISSION_ID[:8]  # "01KVTVZS"
SLUG = "wp04-planning-read"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

PRIMARY_TRUTH = "# spec.md — PRIMARY TRUTH (authored on primary post-WP01)\n"
STALE_HUSK = "# spec.md — STALE pre-mission coord husk copy\n"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "wp04@example.test")
    _git(repo_root, "config", "user.name", "WP04 Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (NOT a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_coord_topology_with_stale_husk(repo_root: Path) -> tuple[Path, Path]:
    """Seed a COORD-topology mission: PRIMARY truth + a materialized STALE husk.

    Returns ``(primary_dir, coord_husk_dir)``. The primary ``spec.md`` carries the
    truth; the materialized ``-coord`` husk carries the stale copy.
    """
    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": COORD_BRANCH,
        "topology": MissionTopology.COORD.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "spec.md").write_text(PRIMARY_TRUTH, encoding="utf-8")

    coord_husk_dir = (
        repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord" / "kitty-specs" / SLUG_WITH_MID8
    )
    _write_meta(coord_husk_dir, meta)
    (coord_husk_dir / "spec.md").write_text(STALE_HUSK, encoding="utf-8")
    return primary_dir, coord_husk_dir


def _seed_flattened_with_stale_husk(repo_root: Path) -> tuple[Path, Path]:
    """Seed a FLATTENED (single-branch) mission with a lingering STALE husk."""
    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "topology": MissionTopology.SINGLE_BRANCH.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "spec.md").write_text(PRIMARY_TRUTH, encoding="utf-8")

    coord_husk_dir = (
        repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord" / "kitty-specs" / SLUG_WITH_MID8
    )
    _write_meta(coord_husk_dir, meta)
    (coord_husk_dir / "spec.md").write_text(STALE_HUSK, encoding="utf-8")
    return primary_dir, coord_husk_dir


# --------------------------------------------------------------------------- #
# (T019) Red-first headline: a coord-topology planning read resolves PRIMARY,
#        NOT the stale coord husk. Pre-fix this returned the husk (STALE_HUSK).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kind",
    [
        MissionArtifactKind.SPEC,
        MissionArtifactKind.TASKS_INDEX,
        MissionArtifactKind.WORK_PACKAGE_TASK,
        MissionArtifactKind.DATA_MODEL,
        MissionArtifactKind.RESEARCH,
    ],
)
def test_coord_topology_planning_read_resolves_primary_not_stale_husk(
    tmp_path: Path, kind: MissionArtifactKind
) -> None:
    """Headline #2062 read-side: a planning read of a coord mission → PRIMARY.

    The materialized ``-coord`` husk carries STALE content; the planning read
    must resolve the PRIMARY feature dir whose ``spec.md`` carries the truth.
    Every primary-partition kind resolves the same primary dir (parametrized as
    mutual controls — none is allowed to leak the husk).
    """
    primary_dir, coord_husk_dir = _seed_coord_topology_with_stale_husk(tmp_path)

    resolved = resolve_planning_read_dir(tmp_path, SLUG_WITH_MID8, kind=kind)

    assert resolved.resolve() == primary_dir.resolve()
    assert resolved.resolve() != coord_husk_dir.resolve()
    # Observable content contract: the planning artifact read is the PRIMARY truth.
    assert (resolved / "spec.md").read_text(encoding="utf-8") == PRIMARY_TRUTH


def test_flattened_with_stale_husk_planning_read_resolves_primary(
    tmp_path: Path,
) -> None:
    """A flattened mission with a lingering husk still reads PRIMARY (NFR-001)."""
    primary_dir, coord_husk_dir = _seed_flattened_with_stale_husk(tmp_path)

    resolved = resolve_planning_read_dir(
        tmp_path, SLUG_WITH_MID8, kind=MissionArtifactKind.SPEC
    )

    assert resolved.resolve() == primary_dir.resolve()
    assert (resolved / "spec.md").read_text(encoding="utf-8") == PRIMARY_TRUTH


def test_planning_read_dir_matches_primary_primitive(tmp_path: Path) -> None:
    """INV-5 symmetry: the planning READ dir equals the primary WRITE dir.

    The planning read resolves the SAME surface the write side authors to
    (the module-private ``_compose_primary_feature_dir`` leaf, read-side-seam-
    primary-primitive-closure-01KYKMMT WP08 T035 -- the deleted public wrapper's
    topology-blind compose, unchanged) — no read(coord)/write(primary) split.
    """
    _seed_coord_topology_with_stale_husk(tmp_path)
    assert (
        resolve_planning_read_dir(
            tmp_path, SLUG_WITH_MID8, kind=MissionArtifactKind.TASKS_INDEX
        ).resolve()
        == _compose_primary_feature_dir(tmp_path, SLUG_WITH_MID8).resolve()
    )


# --------------------------------------------------------------------------- #
# (T018) C-005 KEEP transients are untouched — status reads keep the topology
#        seam. A STATUS kind through the planning-read seam still routes the
#        topology-aware path (the planning split does NOT subsume status).
# --------------------------------------------------------------------------- #
def test_status_kind_keeps_topology_aware_coord_surface(tmp_path: Path) -> None:
    """A STATUS-partition kind through the seam resolves the COORD husk dir.

    The per-kind split is ASYMMETRIC: only ``_PRIMARY_ARTIFACT_KINDS`` route to
    primary. ``STATUS_STATE`` keeps the topology-aware seam (C-001 / C-005), so a
    coord-topology mission's status read still lands on the materialized coord
    worktree — the negative control proving planning ≠ status.
    """
    _primary_dir, coord_husk_dir = _seed_coord_topology_with_stale_husk(tmp_path)

    resolved = resolve_planning_read_dir(
        tmp_path, SLUG_WITH_MID8, kind=MissionArtifactKind.STATUS_STATE
    )

    assert resolved.resolve() == coord_husk_dir.resolve()


def test_keep_c005_probe_transients_unchanged_after_planning_split(
    tmp_path: Path,
) -> None:
    """C-005 KEEP: the #1718/#1848 transient probes are untouched by WP04.

    ``probe_coord_state`` still discriminates EMPTY (create-window #1718) and
    DELETED (coord-deleted #1848) — the planning-read split routes around these
    probes for planning kinds but must not weaken them for status reads.
    """
    _init_repo(tmp_path)
    coord_root = tmp_path / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    coord_root.mkdir(parents=True)
    # EMPTY: coord root materialized, mission dir absent (#1718 family).
    assert probe_coord_state(tmp_path, SLUG_WITH_MID8, MID8) is CoordState.EMPTY
    # DELETED: coord root absent AND declared branch gone (#1848 data-loss guard).
    other = f"deleted-{MID8}"
    assert (
        probe_coord_state(
            tmp_path, other, MID8, coordination_branch="kitty/mission-gone-deadbeef"
        )
        is CoordState.DELETED
    )
