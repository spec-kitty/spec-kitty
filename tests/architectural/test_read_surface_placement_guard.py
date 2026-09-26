"""Read-surface placement enforcement gate (coord-write-placement-closure-01KYCF83 WP07).

FR-004 / NFR-002 (contracts/placement-enforcement.md "Read"): every mission-artifact
read must resolve through ``artifact_home_for(kind).read_surface`` and fail loud on a
partition mismatch — the read-side symmetric completion of WP06's write gate. Reuses
the SAME shared whole-tree scanner (``tests/architectural/_placement_whole_tree_scan.py``)
WP06 built (T035), so read and write enforcement share one scan-scope authority rather
than forking a second walk.

Scope (T031 enumeration, honestly bounded): ``mission_runtime.PlacementSeam.read_dir``
is the ONE blessed read entry point ~40+ production call sites already route through
(``placement_seam(...).read_dir(kind)`` — grep confirms no second kind-aware read
authority exists in production; see ``tracers/design-decisions.md`` for the full
site inventory). This gate hardens THAT seam and proves its whitelist of sanctioned
lenient degrades. It does not attempt to migrate the ~50 pre-existing modules that
call the lower-level, kind-BLIND ``candidate_feature_dir_for_mission`` /
``resolve_planning_read_dir`` primitives directly — those predate ``placement_seam``,
are not in this WP's ``owned_files``, and are a separate, future whack-a-read
migration (D-06's own "reads are still fixed one-at-a-time" framing; recorded as an
explicit residual, not silently dropped).

Before WP07, ``read_dir`` projected the LENIENT ``resolve_planning_read_dir``
(→ ``candidate_feature_dir_for_mission``), which never supplies a
``coordination_branch`` to its fail-closed tail — so a coord-partition kind whose
declared coordination branch had been DELETED from git silently substituted the
primary checkout. WP07 routes ``read_dir`` through the EXISTING, already-hardened
``resolve_artifact_surface`` instead (the same authority
``build_gate_execution_context`` already consumes), closing that silent
substitution with the EXISTING typed ``CoordinationBranchDeleted`` exception — no
new exception type needed.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    MissionTopology,
    is_primary_artifact_kind,
    mission_context_for,
    placement_seam,
)
from mission_runtime.artifacts import _PLACEMENT_ARTIFACT_KINDS
from specify_cli.acceptance.execution_context import declared_home_surface
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]

# Realistic identity: a real 26-char Crockford ULID and its 8-char mid8 prefix,
# mirroring tests/mission_runtime/test_placement_seam.py's fixture shape.
_MISSION_ID = "01KWZC0SEDG7XR3H0M6TVJ9BQF"
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = f"read-surface-placement-guard-{_MID8}"
_TARGET_BRANCH = "feat/read-surface-placement-guard"
_COORD_BRANCH = f"kitty/mission-{_MISSION_SLUG}-{_MID8}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return r


def _write_meta(feature_dir: Path, *, topology: MissionTopology, coordination_branch: str | None) -> None:
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "friendly_name": "Read-surface placement guard",
        "topology": topology.value,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _build_mission_deleted_branch(repo_root: Path) -> Path:
    """A coord-topology mission whose declared branch was NEVER created (DELETED).

    ``probe_coord_state`` classifies ``DELETED`` when the coord worktree root is
    absent AND the declared ``coordination_branch`` does not exist in git — the
    genuine partition-mismatch cell this WP's fail-loud fix closes. No coord
    worktree directory is created here (the whole point: nothing materialised).
    """
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, topology=MissionTopology.COORD, coordination_branch=_COORD_BRANCH)
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: declared-but-never-created coord branch")
    # Deliberately do NOT create _COORD_BRANCH and do NOT materialise the coord
    # worktree — this is the DELETED cell (branch declared, never existed).
    return feature_dir


def _build_mission_materialized(repo_root: Path) -> tuple[Path, Path]:
    """A coord-topology mission whose coord worktree IS materialised."""
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, topology=MissionTopology.COORD, coordination_branch=_COORD_BRANCH)
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: materialized coord worktree")
    _git(repo_root, "branch", _COORD_BRANCH)
    coord_dir = coord_feature_dir(repo_root, _MISSION_SLUG, _MID8)
    coord_dir.mkdir(parents=True)
    (coord_dir / "meta.json").write_text(
        (feature_dir / "meta.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return feature_dir, coord_dir


def _build_mission_unmaterialized(repo_root: Path) -> Path:
    """Coord topology, branch declared AND exists in git, but the coord worktree
    root was never materialised — the create-window (``mission create`` → first
    coord materialisation). Sanctioned lenient degrade (T031/T036)."""
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, topology=MissionTopology.COORD, coordination_branch=_COORD_BRANCH)
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: unmaterialized coord create-window")
    _git(repo_root, "branch", _COORD_BRANCH)
    # No coord worktree directory created at all.
    return feature_dir


def _build_mission_empty_coord_root(repo_root: Path) -> Path:
    """Coord worktree ROOT exists but this mission's subdir is absent (EMPTY)."""
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, topology=MissionTopology.COORD, coordination_branch=_COORD_BRANCH)
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: materialised coord root, empty mission dir")
    _git(repo_root, "branch", _COORD_BRANCH)
    coord_root = repo_root / ".worktrees" / f"{_MISSION_SLUG}-coord"
    coord_root.mkdir(parents=True)
    return feature_dir


def _build_mission_flat(repo_root: Path, *, topology: MissionTopology) -> Path:
    """A coord-less topology (SINGLE_BRANCH / LANES) — AH-2's declared home."""
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, topology=topology, coordination_branch=None)
    (feature_dir / "tasks").mkdir()
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "fixture: coord-less topology")
    return feature_dir


# ---------------------------------------------------------------------------
# T032 / T035 — fail-loud: DELETED coord branch is a genuine partition mismatch,
# not a sanctioned degrade. Parametrized over every COORD-partition kind so the
# gate is non-vacuous across the whole partition (mirrors WP06's all-kinds
# anti-mutant), plus the anti-vacuity check that PRIMARY kinds are immune.
# ---------------------------------------------------------------------------

_COORD_KINDS = sorted(_PLACEMENT_ARTIFACT_KINDS, key=lambda k: k.name)


@pytest.mark.parametrize("kind", _COORD_KINDS, ids=[k.name for k in _COORD_KINDS])
def test_read_dir_fails_loud_on_deleted_coord_branch(repo: Path, kind: MissionArtifactKind) -> None:
    """A COORD-partition kind's read raises when the declared coord branch is gone.

    This is the "synthetic wrong-partition read" T035 requires: the mission
    DECLARES a coordination branch (so the kind's declared home is COORD, per
    ``artifact_home_for(kind).read_surface``) but that branch was never created
    in git and no coord worktree materialised — reading it would silently
    substitute the primary checkout, exactly the residual FR-004 closes.
    """
    _build_mission_deleted_branch(repo)
    seam = placement_seam(repo, _MISSION_SLUG)

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        seam.read_dir(kind)

    # "names the site" (T035 validation criterion): the raised error identifies
    # exactly which mission + branch + candidate surfaces are in conflict.
    err = excinfo.value
    assert err.error_code == "COORDINATION_BRANCH_DELETED"
    assert err.mission_slug == _MISSION_SLUG
    assert err.coordination_branch == _COORD_BRANCH
    assert err.primary_candidate == repo / "kitty-specs" / _MISSION_SLUG


def test_read_dir_primary_partition_kind_is_immune_to_deleted_coord_branch(repo: Path) -> None:
    """Anti-vacuity: a PRIMARY-partition kind never raises, even under a DELETED
    coord branch — AH-1/AH-3, it never transits coordination, so the raise above
    is genuinely partition-scoped and not a blanket read-side failure."""
    feature_dir = _build_mission_deleted_branch(repo)
    seam = placement_seam(repo, _MISSION_SLUG)

    result = seam.read_dir(MissionArtifactKind.SPEC)

    assert is_primary_artifact_kind(MissionArtifactKind.SPEC)
    assert result == feature_dir


# ---------------------------------------------------------------------------
# T031 / T036 — the whitelisted lenient degrades stay lenient (red-first
# counterpart to the mismatch above: these must NOT raise).
# ---------------------------------------------------------------------------


def test_read_dir_coord_worktree_absent_on_flat_topology_stays_lenient(repo: Path) -> None:
    """AH-2: SINGLE_BRANCH has no coordination split at all — a coord-partition
    kind's declared home IS primary, so it resolves primary with no raise."""
    feature_dir = _build_mission_flat(repo, topology=MissionTopology.SINGLE_BRANCH)
    seam = placement_seam(repo, _MISSION_SLUG)

    result = seam.read_dir(MissionArtifactKind.STATUS_STATE)

    assert result == feature_dir


def test_read_dir_lanes_topology_stays_lenient(repo: Path) -> None:
    """AH-2's other coord-less cell: LANES (no coordination branch declared)."""
    feature_dir = _build_mission_flat(repo, topology=MissionTopology.LANES)
    seam = placement_seam(repo, _MISSION_SLUG)

    result = seam.read_dir(MissionArtifactKind.ISSUE_MATRIX)

    assert result == feature_dir


def test_read_dir_fails_loud_on_unmaterialized_coord_worktree(repo: Path) -> None:
    """The declared-but-not-yet-materialised window now FAILS CLOSED.

    Contract reversal (ADR ``docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md``,
    #4959, operator decision DM-01M38VWD): the coord branch exists in git but its
    worktree was never materialised. Before the ADR this cell stayed lenient
    (#1718 KEEP: return the primary ``feature_dir``, no raise) — but that
    empty-PRIMARY substitution is exactly what let a coord-partition reader act on
    an empty document as authoritative and clobber a real coord-side file. A
    coord-partition read on ``CoordState.UNMATERIALIZED`` now raises
    ``CoordinationWorktreeUnmaterialized`` (a distinct ``StatusReadPathNotFound``
    sibling of ``CoordinationBranchDeleted``) whose ``next_step`` names the truthful
    recovery — materialise, not flatten. ``EMPTY``/``NONE`` stay lenient (see
    ``test_read_dir_empty_coord_root_stays_lenient``); ``DELETED`` still raises
    ``CoordinationBranchDeleted``.
    """
    _build_mission_unmaterialized(repo)
    seam = placement_seam(repo, _MISSION_SLUG)

    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        seam.read_dir(MissionArtifactKind.DECISION_LOG)

    # "names the site": the raise identifies the mission + branch + candidate
    # surfaces, and routes on a code distinct from the DELETED sibling so a
    # caller never confuses "not yet checked out" with "gone from git".
    err = excinfo.value
    assert err.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert err.mission_slug == _MISSION_SLUG
    assert err.coordination_branch == _COORD_BRANCH
    assert err.primary_candidate == repo / "kitty-specs" / _MISSION_SLUG


def test_read_dir_empty_coord_root_stays_lenient(repo: Path) -> None:
    """#1716: the coord worktree ROOT is materialised but this mission's subdir is
    not (e.g. a lane hasn't run yet) — primary stays authoritative, no raise."""
    feature_dir = _build_mission_empty_coord_root(repo)
    seam = placement_seam(repo, _MISSION_SLUG)

    result = seam.read_dir(MissionArtifactKind.TRACER_FILE)

    assert result == feature_dir


def test_read_dir_materialized_coord_resolves_coord_dir(repo: Path) -> None:
    """Sanity/positive cell: a genuinely materialised coord surface still
    resolves the coord dir (unchanged by WP07 — regression guard)."""
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    feature_dir, coord_dir = _build_mission_materialized(repo)
    seam = placement_seam(repo, _MISSION_SLUG)

    result = seam.read_dir(MissionArtifactKind.STATUS_STATE)

    assert result == coord_feature_dir(repo, _MISSION_SLUG, _MID8)
    assert result == coord_dir
    assert result != feature_dir


# ---------------------------------------------------------------------------
# T033 — resolution.py's sole ``home.commit_target`` consumer is CONFIRMED
# INERT to WP02's PRIMARY_METADATA non-None flip (WP02 T005 handoff).
# ---------------------------------------------------------------------------


def test_mission_context_primary_metadata_commit_target_is_non_none_and_inert(
    repo: Path,
) -> None:
    """The sole port consumer (``mission_context_for``, ~resolution.py:950) copies
    ``home.commit_target`` verbatim into ``MissionArtifactContext.commit_target``.

    Post WP02 T006 (the ``PRIMARY_METADATA`` special-case ``commit_target=None``
    arm was deleted), the resolved value is the routed ``CommitTarget`` — not
    ``None``. This locks in BOTH halves of the CONFIRMED-INERT verdict WP02's
    T005 audit recorded and handed to WP07: (a) the flip landed at this
    consumer (non-None), and (b) it is a no-op for behaviour because nothing
    branches on it — the only two ``MissionContext.artifact(...)`` production
    callers (``runtime/next/runtime_bridge.py``) read ONLY ``.read_dir``, never
    ``.commit_target`` (grep-verified; no consumer to regress).
    """
    _build_mission_flat(repo, topology=MissionTopology.SINGLE_BRANCH)

    ctx = mission_context_for(repo, _MISSION_SLUG)
    artifact = ctx.artifact(MissionArtifactKind.PRIMARY_METADATA)

    assert artifact.commit_target is not None
    assert artifact.commit_target == CommitTarget(ref=_TARGET_BRANCH)


# ---------------------------------------------------------------------------
# T034 — fold: #2906's accept-time guard DELEGATES to the shared
# ``declared_read_surface`` predicate; it does not reimplement it (no
# double-guard).
# ---------------------------------------------------------------------------


def test_declared_home_surface_delegates_not_reimplements(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``declared_home_surface`` (the #2906 guard's input) is a THIN wrapper over
    ``mission_runtime.declared_read_surface`` — spying on the shared predicate
    proves delegation; the guard would not be exercisable via the spy if the
    accept-time module still carried its own independent inline computation."""
    import mission_runtime as mission_runtime_pkg
    import specify_cli.acceptance.execution_context as execution_context_mod

    calls: list[tuple[str, MissionArtifactKind]] = []
    original = mission_runtime_pkg.declared_read_surface

    def _spy(repo_root: Path, mission_slug: str, kind: MissionArtifactKind, **kwargs: object) -> object:
        calls.append((mission_slug, kind))
        return original(repo_root, mission_slug, kind, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(execution_context_mod, "declared_read_surface", _spy)
    _build_mission_flat(repo, topology=MissionTopology.SINGLE_BRANCH)

    result = declared_home_surface(repo, _MISSION_SLUG, MissionArtifactKind.STATUS_STATE)

    assert calls == [(_MISSION_SLUG, MissionArtifactKind.STATUS_STATE)]
    from mission_runtime import TopologySurface

    assert result is TopologySurface.PRIMARY  # AH-2: SINGLE_BRANCH has no coord split


# ---------------------------------------------------------------------------
# T055 — the ``traces/`` read leg (FR-006 read-side). WP02 reclassified
# ``traces/`` PRIMARY -> COORD; this proves the retrospective generator's
# reader (the one live, documented-leeway edit T055 required) now resolves
# the COORD surface instead of the stale PRIMARY location.
# ---------------------------------------------------------------------------


def test_retrospective_generator_reads_traces_from_materialized_coord_surface(
    repo: Path,
) -> None:
    """A tracer file written ONLY to the coord worktree (never the primary
    checkout) still feeds the retrospective's tooling findings.

    Before WP07, ``_load_traces(feature_dir)`` read ``<primary_feature_dir>/
    traces`` unconditionally — invisible to a coord-topology mission's
    tracer files, which WP03's writers land on the coordination surface.
    ``coordination/teardown.py``'s persist-before-destroy ordering means the
    coord worktree is still materialised when the retrospective is
    generated, so this is a live, reachable gap this WP closes (not a
    hypothetical).
    """
    from specify_cli.retrospective.generator import generate_retrospective
    from specify_cli.retrospective.policy import default_policy

    feature_dir, coord_dir = _build_mission_materialized(repo)
    # The tracer file exists ONLY on the coord surface -- never on primary.
    coord_traces_dir = coord_dir / "traces"
    coord_traces_dir.mkdir(parents=True)
    (coord_traces_dir / "T01-hardening.md").write_text(
        "- **Coord-only tracer read** — no gap, worked as designed.\n",
        encoding="utf-8",
    )
    assert not (feature_dir / "traces").exists()

    record = generate_retrospective(_MISSION_SLUG, default_policy(), repo)

    summaries = [f.summary for f in record.helped]
    assert any("Coord-only tracer read" in s for s in summaries), (
        f"tracer finding not present -- traces/ was not read from the coord "
        f"surface (helped={summaries!r})"
    )


# ---------------------------------------------------------------------------
# Owned-checkout (``effective_root``) threading — checkout-ownership landing
# branch (#3328). ``mission_context_for(..., effective_root=...)`` folds the
# VALIDATED owned checkout as the primary root instead of
# ``get_main_repo_root(repo_root)`` (C-002: never silently cross-read a
# sibling checkout). Every fixture below reuses the SAME ``_build_mission_*``
# helpers the non-owned tests above already exercise, so the only variable is
# the ``effective_root`` fork through ``mission_context_for`` ->
# ``_assemble_core_fragments`` -> ``_resolve_mission_id`` /
# ``_resolve_coordination_branch`` / ``_resolve_status_surface_dir`` (and
# ``mission_context_for``'s own ``primary_read_dir`` / ``target_branch``
# forks) -- the exact branches the checkout-ownership landing PR's e2e
# (subprocess, invisible to pytest-cov) exercises only end-to-end.
# ``decoy_repo_root`` is deliberately a never-created, unrelated path: since
# ``effective_root`` is supplied, ``repo_root`` must never be read (a
# regression that folded it back through ``get_main_repo_root`` would try to
# touch this path and fail loud).
# ---------------------------------------------------------------------------


def test_mission_context_for_owned_checkout_flat_topology_resolves_primary(
    repo: Path, tmp_path: Path
) -> None:
    """Owned checkout, coord-less topology: every artifact resolves off the
    validated owned checkout's own primary dir (FR-004/FR-005 owned branches:
    ``_resolve_status_surface_dir``'s ``not routes_through_coordination(...)``
    early return)."""
    feature_dir = _build_mission_flat(repo, topology=MissionTopology.SINGLE_BRANCH)
    decoy_repo_root = tmp_path / "decoy-primary-never-read"

    ctx = mission_context_for(decoy_repo_root, _MISSION_SLUG, effective_root=repo)

    assert ctx.mission_slug == _MISSION_SLUG
    assert ctx.topology is MissionTopology.SINGLE_BRANCH
    status_artifact = ctx.artifact(MissionArtifactKind.STATUS_STATE)
    assert status_artifact.read_dir == feature_dir
    assert status_artifact.write_dir == feature_dir


def test_mission_context_for_owned_checkout_materialized_coord_resolves_coord_dir(
    repo: Path, tmp_path: Path
) -> None:
    """Owned checkout, materialized coord surface: resolves the coord dir
    (the ``CoordState.MATERIALIZED`` -> ``return coord_dir`` owned tail)."""
    _feature_dir, coord_dir = _build_mission_materialized(repo)
    decoy_repo_root = tmp_path / "decoy-primary-never-read"

    ctx = mission_context_for(decoy_repo_root, _MISSION_SLUG, effective_root=repo)

    assert ctx.topology is MissionTopology.COORD
    status_artifact = ctx.artifact(MissionArtifactKind.STATUS_STATE)
    assert status_artifact.read_dir == coord_dir


def test_mission_context_for_owned_checkout_empty_coord_root_falls_back_to_primary(
    repo: Path, tmp_path: Path
) -> None:
    """Owned checkout, coord root materialized but this mission's subdir is
    not (``CoordState.EMPTY``): the owned branch degrades to the primary dir,
    never raises (FR-006 fail-closed is reserved for DELETED, not EMPTY)."""
    feature_dir = _build_mission_empty_coord_root(repo)
    decoy_repo_root = tmp_path / "decoy-primary-never-read"

    ctx = mission_context_for(decoy_repo_root, _MISSION_SLUG, effective_root=repo)

    status_artifact = ctx.artifact(MissionArtifactKind.STATUS_STATE)
    assert status_artifact.read_dir == feature_dir


def test_mission_context_for_owned_checkout_deleted_branch_fails_loud(
    repo: Path, tmp_path: Path
) -> None:
    """Owned checkout, declared coordination branch deleted from git
    (``CoordState.DELETED``): fails loud with ``CoordinationBranchDeleted``
    instead of silently substituting the primary checkout (#1889/#1848)."""
    _build_mission_deleted_branch(repo)
    decoy_repo_root = tmp_path / "decoy-primary-never-read"

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        mission_context_for(decoy_repo_root, _MISSION_SLUG, effective_root=repo)

    assert excinfo.value.mission_slug == _MISSION_SLUG
    assert excinfo.value.coordination_branch == _COORD_BRANCH
