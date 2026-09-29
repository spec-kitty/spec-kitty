"""map-requirements read-surface authority on a coord topology.

The original #2064 regression (WP06 / FR-008 / SC-005) was a read-surface DESYNC:
``tasks.py::map_requirements`` was the lone read path on
``resolve_feature_dir_for_slug`` (whose slug-only ``mid8_from_slug`` heuristic
misses the coordination worktree when the operator handle carries no mid8 tail),
while ``tasks.py::finalize_tasks`` resolved through
``resolve_feature_dir_for_mission`` (the ``resolve_action_context(action="tasks")``
seam, which reads the declared mid8 from primary ``meta.json``). #2064's fix
unified the two so both resolved the SAME coord ``tasks/`` dir — encoding the
PRE-#2106 model in which planning artifacts transit the coordination worktree.

**#2115 supersedes that coord-agreement invariant.** #2106 moved planning
artifacts (``spec.md`` / ``tasks.md`` / ``tasks/WP*.md`` / ...) onto the PRIMARY
checkout for ALL topologies (INV-5 read/write symmetry), and #2115 consummates it:
WP03 re-pointed ``_map_requirements_feature_dir`` onto
``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` — a PRIMARY-partition kind —
so ``map-requirements`` now reads the PRIMARY planning surface via the seam. On a
coord topology it therefore DIVERGES from the coord-aware
``resolve_feature_dir_for_mission`` (the STATUS-partition seam): the WP frontmatter
authority is the PRIMARY ``tasks/`` dir, NOT the materialized ``-coord`` husk.

These tests are NON-FAKEABLE:
* ``test_pre_fix_resolvers_diverge_on_coord_topology`` proves the raw-resolver
  precondition that made the original #2064 desync real (the two legacy read
  surfaces return different ``Path`` objects for a coord-staged fixture).
* ``test_map_resolves_primary_planning_surface_on_coord_topology`` re-pins the
  #2064 ``map_and_finalize_agree`` test to the post-#2106/#2115 authority: it
  stages WP frontmatter on the PRIMARY ``tasks/`` (post-#2106 reality), proves
  ``map_requirements`` resolves PRIMARY through the seam (NOT the coord husk),
  and asserts the cross-command consequence — full coverage from PRIMARY, while
  the empty coord husk (where the pre-#2115 routing read) would surface every FR
  as unmapped. A bare ``compute_coverage`` assertion in isolation would be
  insufficient (coverage math was never the bug); the test exercises the
  seam-resolved primary surface on a real coord topology.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget, MissionTopology

from specify_cli.cli.commands.agent import tasks as tasks_mod
from specify_cli.cli.commands.agent.tasks import (
    _map_requirements_feature_dir,
    _review_currency_check_branch,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.missions._read_path_resolver import (
    resolve_feature_dir_for_mission,
    resolve_feature_dir_for_slug,
)
from specify_cli.requirement_mapping import (
    compute_coverage,
    read_all_wp_raw_requirement_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Production-shaped identity: a full 26-char Crockford-base32 ULID, NOT a
# handcrafted short slug. The operator HANDLE is the bare slug (no mid8 tail) —
# this is exactly the form that makes ``mid8_from_slug`` return ``""`` and the
# divergent ``resolve_feature_dir_for_slug`` miss the coord worktree.
_MISSION_ID = "01KVPR00ABCDEFGHJKMNPQRSTV"
_MID8 = _MISSION_ID[:8]
_SLUG = "single-planning-surface-authority"
_COORD_BRANCH = f"kitty/mission-{_SLUG}-{_MID8}"
_FUNCTIONAL_IDS = {"FR-001", "FR-002", "FR-003"}


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MID8,
                "coordination_branch": _COORD_BRANCH,
            }
        ),
        encoding="utf-8",
    )


def _write_wp(tasks_dir: Path, wp_id: str, refs: list[str]) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    refs_block = "\n".join(f"- {ref}" for ref in refs)
    (tasks_dir / f"{wp_id}-coord-surface.md").write_text(
        f"---\nwork_package_id: {wp_id}\nrequirement_refs:\n{refs_block}\n---\n",
        encoding="utf-8",
    )


def _build_coord_topology(repo_root: Path) -> Path:
    """Build a coord-topology mission and return the COORD ``tasks/`` dir.

    The planning INPUT invariant: WP frontmatter is authored on PRIMARY and
    staged to coord at commit-time. By the time finalize reads, the canonical WP
    frontmatter lives in the materialized coordination worktree. We plant the
    full FR coverage in the coord ``tasks/`` dir and leave the primary
    ``tasks/`` dir empty — the exact shape that exposes #2064.
    """
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo_root, check=True)

    # Primary checkout: declares identity + coord branch, but no WP frontmatter.
    _write_meta(repo_root / "kitty-specs" / _SLUG)

    # Materialized coordination worktree: the canonical staged WP frontmatter.
    # ``worktree_path`` is annotated ``Any`` upstream — pin the local Path so the
    # derived ``tasks/`` return type stays concrete (no-any-return, boy-scout).
    coord_root: Path = CoordinationWorkspace.worktree_path(repo_root, _SLUG, _MID8)
    coord_feature_dir = coord_root / "kitty-specs" / f"{_SLUG}-{_MID8}"
    _write_meta(coord_feature_dir)
    coord_tasks = coord_feature_dir / "tasks"
    _write_wp(coord_tasks, "WP01", ["FR-001", "FR-002"])
    _write_wp(coord_tasks, "WP02", ["FR-003"])
    return coord_tasks


def _build_coord_topology_with_primary_planning(repo_root: Path) -> Path:
    """Build a coord-topology mission with WP frontmatter on the PRIMARY ``tasks/``.

    The post-#2106/#2115 reality (INV-5 read/write symmetry): planning artifacts —
    including WP frontmatter — are authored AND read on the PRIMARY checkout for
    EVERY topology. We stage the full FR coverage in the PRIMARY ``tasks/`` dir and
    leave the materialized coordination husk's ``tasks/`` EMPTY — the exact shape
    #2115 consummates: ``map_requirements`` must read PRIMARY (full coverage), not
    the stale ``-coord`` husk (zero coverage). Returns the PRIMARY ``tasks/`` dir.

    Distinct from :func:`_build_coord_topology` (which coord-stages the WP
    frontmatter to preserve the raw-resolver divergence precondition); mutating
    that shared fixture would break ``test_pre_fix_resolvers_diverge_on_coord_topology``.
    """
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo_root, check=True)

    # Primary checkout: declares identity + coord branch AND carries the canonical
    # WP frontmatter — the post-#2106 planning surface map_requirements now reads.
    primary_feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(primary_feature_dir)
    primary_tasks = primary_feature_dir / "tasks"
    _write_wp(primary_tasks, "WP01", ["FR-001", "FR-002"])
    _write_wp(primary_tasks, "WP02", ["FR-003"])

    # Materialized coordination worktree: identity husk with an EMPTY ``tasks/`` —
    # the stale shadow the pre-#2115 coord-routed read would have surfaced.
    coord_root = CoordinationWorkspace.worktree_path(repo_root, _SLUG, _MID8)
    coord_feature_dir = coord_root / "kitty-specs" / f"{_SLUG}-{_MID8}"
    _write_meta(coord_feature_dir)
    (coord_feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    return primary_tasks


def test_pre_fix_resolvers_diverge_on_coord_topology(tmp_path: Path) -> None:
    """The #2064 precondition: the two PRE-fix read surfaces disagree.

    ``resolve_feature_dir_for_slug`` (the divergent path map_requirements used
    pre-WP06) resolves the PRIMARY dir because ``mid8_from_slug(<bare-slug>)`` is
    empty; ``resolve_feature_dir_for_mission`` (finalize's seam) reads the
    declared mid8 from primary ``meta.json`` and resolves into the COORD
    worktree. If these two ever returned the same dir for this fixture, the test
    would NOT be exercising the bug — so we assert they DIVERGE.
    """
    _build_coord_topology(tmp_path)

    slug_dir = resolve_feature_dir_for_slug(tmp_path, _SLUG)
    mission_dir = resolve_feature_dir_for_mission(tmp_path, _SLUG)

    assert slug_dir != mission_dir, (
        "Fixture does not reproduce #2064: the divergent resolvers agree, so the "
        "test would pass even on the buggy tree."
    )
    # The divergent path lands on PRIMARY (no coord) — the stale read.
    assert ".worktrees" not in str(slug_dir)
    # The seam finalize uses lands on the coord worktree — the canonical read.
    assert "-coord" in str(mission_dir)


def test_map_resolves_primary_planning_surface_on_coord_topology(
    tmp_path: Path,
) -> None:
    """#2115 (supersedes #2064 ``map_and_finalize_agree``): map reads PRIMARY.

    #2106 moved planning artifacts onto the PRIMARY checkout for all topologies;
    #2115 / WP03 re-pointed ``_map_requirements_feature_dir`` onto
    ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` — a PRIMARY-partition
    kind. So on a coord topology ``map_requirements`` now resolves the PRIMARY
    ``tasks/`` surface and DIVERGES from the coord-aware
    ``resolve_feature_dir_for_mission`` (the STATUS-partition seam, which still
    lands on the ``-coord`` husk). The WP frontmatter authority is PRIMARY.

    The OLD #2064 invariant ``map == resolve_feature_dir_for_mission`` (both
    coord) is obsolete — it encoded the pre-#2106 transit-through-coord model.
    """
    primary_tasks = _build_coord_topology_with_primary_planning(tmp_path)

    map_feature_dir = _map_requirements_feature_dir(tmp_path, _SLUG)
    finalize_feature_dir = resolve_feature_dir_for_mission(tmp_path, _SLUG)

    # NEW invariant: map resolves the PRIMARY surface — NOT the coord husk.
    assert ".worktrees" not in str(map_feature_dir)
    assert "-coord" not in str(map_feature_dir)
    assert (map_feature_dir / "tasks") == primary_tasks
    assert map_feature_dir == tmp_path / "kitty-specs" / _SLUG

    # The coord-agreement of #2064 is SUPERSEDED: finalize's coord-aware seam
    # still lands on the ``-coord`` husk, so map now DIVERGES from it.
    assert map_feature_dir != finalize_feature_dir
    assert "-coord" in str(finalize_feature_dir)

    # Cross-command consequence: reading the WP frontmatter through the
    # seam-resolved PRIMARY surface yields FULL coverage — zero unmapped FRs.
    # WP06 (requirement-id-grammar-01M3NRCA, C6/F13 disposal): the typed
    # normalizing reader this test used (``read_all_wp_requirement_refs``)
    # was deleted with its zero product callers; the raw reader is
    # equivalent here since every seeded ref is already well-formed and
    # canonical (``compute_coverage`` canonicalises via ``grammar.canonical``
    # regardless of reader).
    refs = read_all_wp_raw_requirement_refs(map_feature_dir / "tasks")
    coverage = compute_coverage(refs, _FUNCTIONAL_IDS)
    assert coverage["unmapped_functional"] == []

    # Witness the model flip #2115 consummates: the coord husk (where the
    # pre-#2115 coord-routed read resolved) has an EMPTY ``tasks/`` — reading
    # THERE would surface every FR as unmapped (the spurious-unmapped class of
    # bug). map_requirements no longer routes there.
    coord_refs = read_all_wp_raw_requirement_refs(finalize_feature_dir / "tasks")
    coord_coverage = compute_coverage(coord_refs, _FUNCTIONAL_IDS)
    assert sorted(coord_coverage["unmapped_functional"]) == sorted(_FUNCTIONAL_IDS)


# --- T034: FR-005 predicate routing at the review-currency decision site ------


def _stub_placement(
    monkeypatch: pytest.MonkeyPatch, *, coord: bool
) -> CommitTarget:
    """Stub the ref-only placement + the STORED topology the routing decision reads.

    FR-001b: ``_review_currency_check_branch`` decides coord-vs-primary from the
    stored topology via ``routes_through_coordination(resolve_topology(...))``, not
    a per-ref enum — so both seams are stubbed consistently.
    """
    placement = CommitTarget(ref="kitty/mission-x-coord")
    topology = MissionTopology.COORD if coord else MissionTopology.SINGLE_BRANCH
    # write-surface-coherence WP01: ``resolve_placement_only`` now takes a REQUIRED
    # ``kind`` keyword. ``_review_currency_check_branch`` calls it with
    # ``kind=STATUS_STATE`` (the coord-base read), so the stub must accept ``kind``
    # — a positional-only lambda raises TypeError, gets swallowed by the helper's
    # except arm, and silently falls back to ``target_branch`` (the stale-stub trap).
    monkeypatch.setattr(
        tasks_mod, "resolve_placement_only", lambda _root, _slug, *, kind: placement
    )
    monkeypatch.setattr(tasks_mod, "resolve_topology", lambda _root, _slug: topology)
    return placement


def test_review_currency_returns_placement_ref_for_coordination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-005: the coordination branch is taken via ``routes_through_coordination``.

    Directly exercises the T032 site (not an integration path): when the stored
    topology routes through coordination the placement ref is returned.
    """
    placement = _stub_placement(monkeypatch, coord=True)
    result = _review_currency_check_branch(
        main_repo_root=Path("/repo"),
        mission_slug="x",
        target_branch="feat/x",
        workspace=None,
    )
    assert result == placement.ref


def test_review_currency_returns_target_branch_for_non_coordination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-005: a coord-less topology falls back to ``target_branch``.

    ``routes_through_coordination`` is ``False`` for SINGLE_BRANCH/LANES, so the
    branch identical to the pre-refactor ``.kind is COORDINATION`` read is taken.
    """
    _stub_placement(monkeypatch, coord=False)
    result = _review_currency_check_branch(
        main_repo_root=Path("/repo"),
        mission_slug="x",
        target_branch="feat/x",
        workspace=None,
    )
    assert result == "feat/x"
