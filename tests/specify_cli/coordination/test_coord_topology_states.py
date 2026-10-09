"""T029 (#2250) — regression lock for the three coordination-surface states.

``data-model.md`` (Domain State — Coordination surface state,
``_read_path_resolver.py:663-706``) names three states the read path MUST
distinguish and behave correctly for:

| State           | Meaning                                              | Correct behavior                          |
|------------------|------------------------------------------------------|--------------------------------------------|
| ``never-created`` | mission never declared a ``coordination_branch``    | resolve to primary; **no** ``COORDINATION_BRANCH_DELETED`` |
| ``UNMATERIALIZED``| coord branch exists, worktree not yet created        | resolve lifecycle reads via the branch ref |
| ``DELETED``       | coord worktree removed mid-mission                    | actionable error / re-materialize, not stale-primary fallback |

The underlying discriminator (``missions._read_path_resolver.probe_coord_state``
/ ``CoordState``) is already unit-tested exhaustively in
``tests/missions/test_coord_feature_dir_helpers.py``. This module instead locks
the END-TO-END behavior at the two consumer seams (the existence-gated read
path and the canonical coordination surface) so the three states cannot
silently collapse into each other again — in particular the historical #2250
defect where ``never-created`` (no ``coordination_branch`` declared at all,
non-coord topology) was misclassified and could reach the same hard-fail as a
genuinely ``DELETED`` coordination branch.

No mocks: a real ``git init`` repo drives every branch, including the real
``git branch`` / ``git branch -D`` calls that split UNMATERIALIZED from
DELETED (the single ``git rev-parse`` arm inside ``probe_coord_state``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    resolve_status_surface_with_anchor,
)
from specify_cli.coordination.workspace import CoordinationWorkspaceBranchMismatch
from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

pytestmark = pytest.mark.git_repo

# Production-shaped identity (NFR-005): a real 26-char Crockford ULID, mid8 =
# its first 8 chars (Mission Identity Model 083+).
MISSION_ID = "01KWZ46VTY9CVJ8G10ERTMPVRH"
MID8 = MISSION_ID[:8]
MISSION_SLUG = "coord-topology-states"
SLUG_WITH_MID8 = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "coord-topology@example.test")
    _git(repo_root, "config", "user.name", "Coord Topology States")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(repo_root: Path, slug: str, meta: dict[str, object]) -> Path:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


# ---------------------------------------------------------------------------
# never-created: no ``coordination_branch`` declared at all (flat/single_branch
# topology). Must resolve PRIMARY on both legs and must NEVER raise
# CoordinationBranchDeleted — the historical #2250 misclassification risk.
# ---------------------------------------------------------------------------


def test_never_created_resolves_primary_on_both_legs(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    feature_dir = _write_meta(
        tmp_path,
        SLUG_WITH_MID8,
        {"mission_id": MISSION_ID, "mission_slug": SLUG_WITH_MID8},
    )

    surface = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
    assert surface.primary_anchor == feature_dir
    assert surface.surface_path.parent == feature_dir

    read_path = resolve_handle_to_read_path(
        tmp_path, SLUG_WITH_MID8, require_exists=True
    )
    assert read_path == feature_dir


def test_never_created_never_raises_coordination_branch_deleted(
    tmp_path: Path,
) -> None:
    """The never-created state must be structurally unreachable from the
    DELETED hard-fail (#2250): with no ``coordination_branch`` declared, the
    topology short-circuit in ``_resolve_not_found`` (FR-006 / #2062) routes to
    PRIMARY before the coord-state probe (and its DELETED arm) is even
    consulted."""
    _init_repo(tmp_path)
    _write_meta(
        tmp_path,
        SLUG_WITH_MID8,
        {"mission_id": MISSION_ID, "mission_slug": SLUG_WITH_MID8},
    )

    try:
        resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
        resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True)
    except CoordinationBranchDeleted as exc:  # pragma: no cover - regression guard
        pytest.fail(
            "never-created (no declared coordination_branch) must NEVER raise "
            f"CoordinationBranchDeleted; got {exc!r} (#2250 regression)."
        )


# ---------------------------------------------------------------------------
# UNMATERIALIZED: coord branch declared AND present in git, but the coord
# worktree has not been created yet (the mission-create -> first-materialize
# window, #1718). Must resolve PRIMARY on the existence-gated read leg and
# must NOT raise DELETED.
# ---------------------------------------------------------------------------


def test_unmaterialized_resolves_primary_never_deleted(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    feature_dir = _write_meta(
        tmp_path,
        SLUG_WITH_MID8,
        {
            "mission_id": MISSION_ID,
            "mission_slug": SLUG_WITH_MID8,
            "coordination_branch": COORD_BRANCH,
        },
    )
    # The declared branch DOES exist in git — only the coord worktree is
    # missing (never materialized yet).
    _git(tmp_path, "branch", COORD_BRANCH)

    read_path = resolve_handle_to_read_path(
        tmp_path, SLUG_WITH_MID8, require_exists=True
    )
    assert read_path == feature_dir, (
        "#1718 create-window: a declared-but-unmaterialized coord (branch "
        "present in git) must resolve PRIMARY on the existence-gated leg, "
        f"got {read_path}."
    )

    # The canonical surface composes the (not-yet-materialized) coord path
    # rather than existence-gating, but it must not hard-fail DELETED either.
    surface = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
    assert surface.primary_anchor == feature_dir


# ---------------------------------------------------------------------------
# MATERIALIZED: the worktree exists but HEAD names another branch. Refuse
# before reading or writing against that tree.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("leave_branch", "actual_fragment"),
    [
        (("checkout", "-q", "-b", "other-branch"), "other-branch"),
        (("checkout", "-q", "--detach"), "detached or unreadable HEAD"),
    ],
    ids=["other-branch", "detached"],
)
def test_materialized_coord_on_wrong_branch_refuses_reads_and_surface(
    tmp_path: Path, leave_branch: tuple[str, ...], actual_fragment: str
) -> None:
    _init_repo(tmp_path)
    _write_meta(
        tmp_path,
        SLUG_WITH_MID8,
        {
            "mission_id": MISSION_ID,
            "mission_slug": SLUG_WITH_MID8,
            "coordination_branch": COORD_BRANCH,
            "topology": "coord",
        },
    )
    coord_root = tmp_path / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    _git(tmp_path, "worktree", "add", "-q", "-b", COORD_BRANCH, str(coord_root))
    (coord_root / "kitty-specs" / SLUG_WITH_MID8).mkdir(parents=True)
    assert resolve_handle_to_read_path(
        tmp_path, SLUG_WITH_MID8, require_exists=True
    ) == coord_root / "kitty-specs" / SLUG_WITH_MID8
    assert (
        resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8).surface_path.parent
        == coord_root / "kitty-specs" / SLUG_WITH_MID8
    )
    _git(coord_root, *leave_branch)

    with pytest.raises(CoordinationWorkspaceBranchMismatch) as read_exc:
        resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True)
    assert read_exc.value.error_code == "COORDINATION_WORKTREE_BRANCH_MISMATCH"
    assert read_exc.value.expected_ref == COORD_BRANCH
    assert actual_fragment in read_exc.value.actual_ref

    with pytest.raises(CoordinationWorkspaceBranchMismatch) as surface_exc:
        resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
    assert surface_exc.value.error_code == "COORDINATION_WORKTREE_BRANCH_MISMATCH"
    with pytest.raises(CoordinationWorkspaceBranchMismatch):
        resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8, for_write=True)


# ---------------------------------------------------------------------------
# DELETED: coord branch declared but GONE from git (removed mid-mission), no
# coord worktree on disk. Must hard-fail loudly and distinctly from the other
# two states (full convergence contract lives in
# tests/status/test_aggregate_coord_deleted_contract.py; this is the
# 3-state-in-one-file cross-reference).
# ---------------------------------------------------------------------------


def test_deleted_hard_fails_distinctly_from_never_created_and_unmaterialized(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    _write_meta(
        tmp_path,
        SLUG_WITH_MID8,
        {
            "mission_id": MISSION_ID,
            "mission_slug": SLUG_WITH_MID8,
            "coordination_branch": COORD_BRANCH,
        },
    )
    # Declared but never created (equivalent to created-then-removed for the
    # git rev-parse arm the probe uses) -> DELETED, not UNMATERIALIZED.

    with pytest.raises(CoordinationBranchDeleted) as surface_exc:
        resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
    assert surface_exc.value.error_code == "COORDINATION_BRANCH_DELETED"

    with pytest.raises(CoordinationBranchDeleted) as read_path_exc:
        resolve_handle_to_read_path(tmp_path, SLUG_WITH_MID8, require_exists=True)
    assert read_path_exc.value.error_code == "COORDINATION_BRANCH_DELETED"


# ---------------------------------------------------------------------------
# T030 (FR-012, verify-only — SUBSUMED by #2062): a coord-less STORED topology
# resolves PRIMARY before any husk probe, even with a REAL, materialized stale
# ``-coord`` husk on disk carrying its OWN (different) status content. This
# does not re-implement any guard (a fork would be a C-001 violation) — it
# locks the OBSERVABLE end-to-end contract through
# ``resolve_status_surface_with_anchor`` for the EXPLICITLY backfilled case
# (``topology: "single_branch"`` stored in meta.json), the shape a real
# ``mission flatten`` leaves behind.
#
# Verified live (not asserted here, to keep this a black-box behavioral pin
# rather than a white-box call-graph test — feedback_refactor_stable_arch_tests):
# TWO independent gates cooperate to produce this result. (1) The primary gate
# — the shared FR-006 stored-topology short-circuit in
# ``_read_path_resolver._resolve_existing_for_slug`` (also used by
# ``candidate_feature_dir_for_mission``) — already prevents a coord-less
# stored topology from ever landing on the husk path, so
# ``resolve_status_surface_with_anchor``'s ``feature_dir_is_husk`` branch is
# not even entered for this scenario. (2) ``_husk_is_authoritative_surface``
# (``surface_resolver.py:508``) is a genuine SECOND, independent gate, not
# dead code: disabling gate (1) alone (so ``candidate_feature_dir_for_mission``
# lands on the husk) still resolves PRIMARY, because gate (2) then catches it.
# ---------------------------------------------------------------------------


def test_flatten_transition_resolves_primary_ignores_stale_husk(
    tmp_path: Path,
) -> None:
    """A flattened mission (stored ``topology=single_branch``) must resolve
    PRIMARY on the canonical surface even though a real, materialized ``-coord``
    husk with DIFFERENT status content still exists on disk (the pre-flatten
    coord worktree, not yet garbage-collected). Two independent gates enforce
    this (see module comment above) — the observable contract is what this
    test pins (FR-012 / #2062)."""
    _init_repo(tmp_path)
    primary = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    primary.mkdir(parents=True)
    (primary / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mission_slug": SLUG_WITH_MID8,
                "topology": "single_branch",
                "flattened": True,
                # No coordination_branch — genuinely flattened.
            }
        ),
        encoding="utf-8",
    )
    (primary / "status.events.jsonl").write_text(
        '{"wp_id":"WP01","to_lane":"approved"}\n', encoding="utf-8"
    )

    # A REAL, materialized stale coord worktree (the pre-flatten husk), with its
    # OWN, DIFFERENT status content — a real ``git worktree add``, not a bare dir.
    coord_root = tmp_path / ".worktrees" / f"{SLUG_WITH_MID8}-coord"
    _git(tmp_path, "worktree", "add", "-q", "-b", COORD_BRANCH, str(coord_root))
    husk = coord_root / "kitty-specs" / SLUG_WITH_MID8
    husk.mkdir(parents=True)
    (husk / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID}), encoding="utf-8"
    )
    (husk / "status.events.jsonl").write_text(
        '{"wp_id":"WP01","to_lane":"planned"}\n', encoding="utf-8"
    )

    # Negative control: the husk is a genuinely distinct, present directory —
    # otherwise "resolves primary" would pass vacuously.
    assert husk.exists()
    assert husk.resolve() != primary.resolve()

    surface = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)

    assert surface.primary_anchor.resolve() == primary.resolve(), (
        "flatten-transition: the canonical surface must resolve the PRIMARY "
        f"anchor {primary.resolve()}, not the stale husk {husk.resolve()}."
    )
    assert surface.surface_path.parent.resolve() == primary.resolve(), (
        "flatten-transition: the surface path must live under PRIMARY, never "
        f"under the stale husk {husk.resolve()} (FR-012 / #2062)."
    )
