"""ATDD baseline for #3867 — coord + unprotected-primary lane-lifecycle loop.

WP01 / T001-T002-T004 (mission ``lane-lifecycle-surface-authority-01M28ZZH``).

FINDING (recorded in the Activity Log, escalated to the operator): the #3867
four-guard deadlock **does not reproduce on current HEAD**. The prompt's own
stopping condition applies verbatim — "If you cannot make the loop genuinely
wedge on current HEAD, STOP and report that finding rather than writing a test
that passes vacuously." Two independent investigations (the WP01 implementer and
a read-only research fork) drove the REAL governed stack and could not wedge
Guard 3 or Guard 4 by any legal ordering. So this file is NOT the planned
red-first driver flipped green by WP05; it is the **confirmation reproduction**
T002 asks for ("First confirm the loop still wedges on current HEAD ... adjust
the reproduction to that reality"), encoding the closed premise as a durable
regression guard.

Why the premise is already closed (evidence, all present on this HEAD):

1. **Topology honesty — the root closure (#2533, commit ``7fbd81b832``,
   authored 2026-09-03, before this mission's base ``acf360e23b``).**
   ``_resolve_default_topology_phase`` (``cli/commands/agent/mission_create.py:417``)
   now consumes :func:`coord_topology_reachable`: a ``--pr-bound`` mission on an
   **unprotected** primary target defaults to ``SINGLE_BRANCH``, never coord —
   "eliminating the stranded coord branch behind the #2533 split-brain." The
   specimen ``coord-commit-surface-authority-01M1M553`` shape (coord + unprotected
   via ``--pr-bound --start-branch``) is therefore structurally uncreatable, and
   THIS mission's own ``meta.json`` records ``topology: single_branch`` for exactly
   that reason. Guarded by ``tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py``.

2. **Guard 1 detection already fixed (FIX-M2-04, ``8a95e2d36e``, #2274/#2980).**
   ``_list_wp_branch_mission_specs_changes`` (``tasks_shared.py``) excludes
   COORD-partition files via ``is_coord_residue_churn`` — Guard 1 cannot flag a
   pure coord-owned status file. (Pinned in
   ``tests/lanes/test_lane_lifecycle_characterization.py``.)

3. **Guard 4 read/write surfaces already unified (FR-010 read-side-seam
   closures).** The approve gate reads the matrix from
   ``st.feature_dir = feature_write_dir(handle)`` = ``resolve_feature_dir_for_mission``
   (``tasks_move_task.py:502/535``, ``_mt_issue_matrix_facts`` :1023). On this
   HEAD that dir EQUALS the affirmative
   :func:`~mission_runtime.resolve_artifact_surface`\\ ``(ISSUE_MATRIX)`` in every
   coord state, and ``issue-verdict`` commits the matrix to the SAME surface
   (COORD when materialized) — so the plan's premise "verdict writes PRIMARY via
   Rule 2 while the gate reads the COORD husk" is FALSE on HEAD.
   ``_issue_matrix_approval_blocker``'s own docstring records the fix: "There is
   NO PRIMARY fallback: a PRIMARY fallback for a COORD kind was the split-brain
   anti-pattern."

4. **Guard 3 dep-lane merge does not wedge on ``status.*``.** ``kitty-specs/`` is
   sparse-excluded from lane worktrees, and the coordination-owned artifacts that
   DO travel in lane trees (``status.events.jsonl`` / ``issue-matrix.json`` /
   ``acceptance-matrix.json`` / ``meta.json`` / ``decisions.events.jsonl`` /
   traces / review-cycle) are all union-/driver-resolved by ``_MERGE_DRIVERS``
   (``lanes/merge.py``) under ``_ephemeral_merge_driver_activation``. The real
   ``allocate_lane_worktree`` dependency merge completes cleanly.

These tests are GREEN on HEAD by construction and drive the REAL production
surfaces (no hand-seeded husk events). They are a regression guard: if a future
change re-opens the four-guard deadlock, the surface-agreement / no-conflict
assertions here flip RED. If the operator re-scopes or closes #3867, this file
documents why.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    resolve_artifact_surface,
)
from specify_cli.coordination.surface_authority import coord_topology_reachable
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    allocate_lane_worktree,
)
from specify_cli.missions._create import ensure_coordination_branch
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# A real ``--start-branch`` / ``--pr-bound`` mission targets a NON-protected
# feature branch (``main`` is protected by default). This is the exact axis
# #2533's topology-honesty turns into ``SINGLE_BRANCH``.
_MISSION_HUMAN = "coord-unprot-lifecycle"
_MISSION_ID = "01M28ZZHLIFECYCLE00000000P"
_MID8 = _MISSION_ID[:8]
_SLUG = f"{_MISSION_HUMAN}-{_MID8}"
_TARGET_BRANCH = "pr/coord-unprot-lifecycle"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "mid8": _MID8,
                "mission_type": "software-dev",
                "target_branch": _TARGET_BRANCH,
                "created_at": "2026-09-14T00:00:00+00:00",
                "friendly_name": "coord+unprotected lifecycle repro",
                # HAND-FORCED coord topology: #2533 would mint SINGLE_BRANCH for
                # this pr-bound + unprotected shape, so the only way to even
                # stand up the specimen is to write topology=coord directly (as
                # the coord_topology_fixture does). That the fixture must FORCE
                # this is itself evidence the wedge is uncreatable through the
                # supported path.
                "topology": "coord",
                "coordination_branch": coordination_branch,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _lanes_manifest(*, with_dependency_chain: bool) -> LanesManifest:
    lanes = [
        ExecutionLane(
            lane_id="lane-a",
            wp_ids=("WP01",),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=(),
            parallel_group=0,
        ),
        ExecutionLane(
            lane_id="lane-b",
            wp_ids=("WP02",),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=(),
            parallel_group=0,
        ),
    ]
    if with_dependency_chain:
        lanes.append(
            ExecutionLane(
                lane_id="lane-c",
                wp_ids=("WP03",),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=("lane-a", "lane-b"),
                parallel_group=1,
            )
        )
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET_BRANCH,
        lanes=lanes,
        computed_at="2026-09-14T00:00:00Z",
        computed_from="wp01-baseline",
    )


def _stand_up_coord_unprotected_mission(tmp_path: Path) -> Path:
    """Materialise a coord-topology mission on an UNPROTECTED primary target.

    Real git + real ``ensure_coordination_branch``; topology is hand-forced to
    ``coord`` (see ``_write_meta``). Returns the repo root.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", _TARGET_BRANCH, "main")
    _git(repo, "checkout", "-q", _TARGET_BRANCH)

    coord = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        target_branch=_TARGET_BRANCH,
    )
    assert coord.created

    feature_dir = repo / "kitty-specs" / _SLUG
    _write_meta(feature_dir, coordination_branch=coord.branch_name)
    (feature_dir / "spec.md").write_text("# Spec\n\nCloses #3867. Substantive content.\n", encoding="utf-8")
    (feature_dir / "status.json").write_text(json.dumps({"schema": 1, "wps": {}}, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", f"chore: planning artifacts for {_SLUG}")
    return repo


# ---------------------------------------------------------------------------
# Root closure (#2533) — the specimen config is uncreatable
# ---------------------------------------------------------------------------


def test_pr_bound_unprotected_primary_does_not_route_to_coordination() -> None:
    """#2533 topology honesty: a ``--pr-bound`` mission on an unprotected primary
    (and not currently on the primary branch) is NOT coord-reachable — it defaults
    to ``SINGLE_BRANCH``, so all lifecycle surfaces route to primary and no
    four-guard surface contradiction can arise. This is the root reason the
    specimen deadlock is uncreatable on HEAD.
    """
    assert coord_topology_reachable(pr_bound=True, primary_protected=False, current_is_primary=False) is False
    # Sanity contrast: a protected primary (or being on the primary branch) DOES
    # keep coordination reachable — the fix is targeted, not a blanket disable.
    assert coord_topology_reachable(pr_bound=True, primary_protected=True, current_is_primary=False) is True


# ---------------------------------------------------------------------------
# Guard 4 — approve-gate read surface vs verdict-write surface AGREE (no FR-004
# split-brain on HEAD)
# ---------------------------------------------------------------------------


class TestGuard4NoSplitBrain:
    def test_gate_read_surface_equals_issue_matrix_authority_unmaterialized(self, tmp_path: Path) -> None:
        """Coord worktree UNMATERIALIZED (the realistic unprotected state): the
        gate's kind-blind read dir (``resolve_feature_dir_for_mission``) equals
        the affirmative ``resolve_artifact_surface(ISSUE_MATRIX)`` surface — both
        PRIMARY. Read and write cannot diverge, so the plan's Guard-4 split-brain
        cannot arise.
        """
        repo = _stand_up_coord_unprotected_mission(tmp_path)

        gate_read_dir = resolve_feature_dir_for_mission(repo, _SLUG)
        matrix_surface = resolve_artifact_surface(repo, _SLUG, MissionArtifactKind.ISSUE_MATRIX)
        assert gate_read_dir == matrix_surface.path, (
            "FR-004 regression: the approve-gate read dir diverged from the issue-matrix authoritative surface (a split-brain would be back)"
        )
        assert str(matrix_surface.surface_kind).endswith("primary") or (matrix_surface.surface_kind.name.lower() == "primary")

    def test_gate_read_surface_equals_issue_matrix_authority_materialized(self, tmp_path: Path) -> None:
        """Coord worktree MATERIALIZED: the gate read dir and the issue-matrix
        authority BOTH resolve the COORD husk — still no divergence. (The
        verdict, written via ``write_target(ISSUE_MATRIX)``, commits to this same
        COORD surface, not PRIMARY — refuting the plan's Rule-2 premise.)
        """
        from specify_cli.coordination.workspace import CoordinationWorkspace

        repo = _stand_up_coord_unprotected_mission(tmp_path)
        coord_root = CoordinationWorkspace.resolve(repo, _SLUG, _MID8)
        coord_fdir = coord_root / "kitty-specs" / _SLUG
        coord_fdir.mkdir(parents=True, exist_ok=True)
        (coord_fdir / "status.events.jsonl").write_text("", encoding="utf-8")

        gate_read_dir = resolve_feature_dir_for_mission(repo, _SLUG)
        matrix_surface = resolve_artifact_surface(repo, _SLUG, MissionArtifactKind.ISSUE_MATRIX)
        assert gate_read_dir == matrix_surface.path, "FR-004 regression: read/write surfaces diverged with a materialized coord worktree"
        assert matrix_surface.surface_kind.name.lower() == "coord"


# ---------------------------------------------------------------------------
# Guard 3 — dependent-lane claim does NOT wedge on coord-owned status files
# ---------------------------------------------------------------------------


class TestGuard3DependentLaneClaimCompletes:
    def test_coord_status_files_are_sparse_excluded_from_lane_worktree(self, tmp_path: Path) -> None:
        """The coord-owned status files are sparse-checkout-excluded from lane
        worktrees (FR-024/025/029) and are not present in the lane branch tree —
        so two lane tips can never become divergent in-tree editors of
        ``status.json`` that a content merge could conflict on. This is the
        structural reason the plan's Guard-3 status.* wedge cannot fire on HEAD.
        """
        repo = _stand_up_coord_unprotected_mission(tmp_path)
        manifest = _lanes_manifest(with_dependency_chain=False)

        lane_wt, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=_SLUG,
            wp_id="WP01",
            lanes_manifest=manifest,
        )
        # Working tree: the coord-owned status files are not materialized.
        assert not (lane_wt / "kitty-specs" / _SLUG / "status.json").exists()
        assert not (lane_wt / "kitty-specs" / _SLUG / "status.events.jsonl").exists()
        # The sparse-checkout config explicitly negates them.
        sparse = subprocess.run(
            ["git", "-C", str(lane_wt), "sparse-checkout", "list"],
            capture_output=True,
            text=True,
        ).stdout
        assert f"!kitty-specs/{_SLUG}/status.json" in sparse
        assert f"!kitty-specs/{_SLUG}/status.events.jsonl" in sparse
        # And they are absent from the lane branch git TREE, so a merge has
        # nothing to conflict on.
        in_tree = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{lane_branch}:kitty-specs/{_SLUG}/status.json"],
            capture_output=True,
            text=True,
        )
        assert in_tree.returncode != 0

    def test_dependency_lane_merge_completes_cleanly(self, tmp_path: Path) -> None:
        """The REAL ``allocate_lane_worktree`` dependency path (lane-c depends on
        sibling lanes lane-a + lane-b, each with its own committed ``src/`` delta)
        completes WITHOUT ``DependencyLaneMergeConflictError`` and propagates both
        siblings' code. Combined with the sparse-exclusion above, this confirms
        the dependent-lane claim does not wedge on HEAD.
        """
        repo = _stand_up_coord_unprotected_mission(tmp_path)
        manifest = _lanes_manifest(with_dependency_chain=True)

        for lane_id, wp_id in (("lane-a", "WP01"), ("lane-b", "WP02")):
            wt, _branch = allocate_lane_worktree(
                repo_root=repo,
                mission_slug=_SLUG,
                wp_id=wp_id,
                lanes_manifest=manifest,
            )
            (wt / "src").mkdir(exist_ok=True)
            (wt / "src" / f"{lane_id}.py").write_text(f"# {lane_id}\n", encoding="utf-8")
            _git(wt, "add", "src")
            _git(wt, "commit", "-q", "-m", f"{lane_id}: src delta")

        # Allocate the dependent lane FRESH: its dependency merge runs against
        # both sibling tips. It MUST complete rather than raise.
        try:
            dep_wt, _dep_branch = allocate_lane_worktree(
                repo_root=repo,
                mission_slug=_SLUG,
                wp_id="WP03",
                lanes_manifest=manifest,
            )
        except DependencyLaneMergeConflictError as exc:  # pragma: no cover
            pytest.fail(f"Guard-3 wedge reproduced on HEAD (unexpected — the #3867 premise was believed closed): {exc.error_code}: {exc}")
        assert dep_wt.exists()
        # The dependency merge genuinely propagated sibling code (proves the merge
        # RAN and resolved, rather than being skipped).
        assert (dep_wt / "src" / "lane-a.py").exists()
        assert (dep_wt / "src" / "lane-b.py").exists()
