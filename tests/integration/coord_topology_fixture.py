"""Shared un-stubbed coordination-topology test fixture (FR-014, WP01).

Materialises a post-#2106 coordination-topology mission shape:

* PRIMARY checkout: ``meta.json`` (``topology=coord`` + ``coordination_branch``),
  ``tasks/WP01.md``, ``lanes.json``, and a DECOY ``status.events.jsonl``.
* Coord worktree (STATUS-only husk): ``status.events.jsonl`` only —
  no ``tasks/``, no ``lanes.json``, no ``meta.json``.

A decoy events file with a DIFFERENT marker on primary makes wrong-leg status
reads fail LOUDLY rather than silently pass.

Also provides a flat/single-branch mission fixture for neutrality tests.

**No resolver is patched anywhere in this module.** All topology routing uses
real git + filesystem state — verifiable via the smoke test (T003).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

# ---------------------------------------------------------------------------
# Marker constants — coord vs. primary decoy must be distinct so wrong-leg
# reads are detectable in assert_status_from_coord.
# ---------------------------------------------------------------------------

_COORD_EVENT_MARKER = "COORD_AUTHORITY_MARKER_WP01_01KW2E7A"
_DECOY_EVENT_MARKER = "PRIMARY_DECOY_MARKER_WP01_01KW2E7A"

# ---------------------------------------------------------------------------
# FR-009 sentinel-husk-meta divergence (coord-read-residuals WP01 / T001).
#
# The base coord husk is STATUS-only (no meta.json) — a wrong-leg identity read
# RAISES (missing meta), which a defensive ``except`` would silently swallow to a
# no-op. That makes an identity-routing bug INVISIBLE. The sentinel variant
# instead WRITES a husk ``meta.json`` that is PRESENT-but-WRONG: it carries a
# sentinel ``mission_id`` (and a distinct ``mission_type``) that differ from the
# PRIMARY values, so a wrong-leg read returns a SILENT-WRONG-VALUE rather than
# raising. The identity proof then asserts a returned DOMAIN VALUE (mission_id /
# mission_type), and reverting a routed read to the coord-aware resolver surfaces
# the sentinel/wrong type → the test goes RED (FR-009 / NFR-004).
#
# 26-char Crockford-base32 ULID, intentionally distinct from the fixture's
# resolved PRIMARY id (``01KW2E7AFC0000000000000001``).
SENTINEL_HUSK_MISSION_ID = "6KERGF2ZNFBPR91YEZMARG99KS"
# Distinct from the PRIMARY ``software-dev`` so a ``get_mission_type`` revert is
# falsifiable on a returned domain value (not just the mission_id leg).
SENTINEL_HUSK_MISSION_TYPE = "research"


# ---------------------------------------------------------------------------
# Context dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoordTopologyContext:
    """All paths for a coord-topology mission fixture (T001).

    Holds the repo root and all derived paths so per-site tests can assert
    specific surfaces without re-deriving git paths.
    """

    repo: Path
    """Git repository root (primary checkout)."""

    slug: str
    """Full composed mission slug ``<human>-<mid8>``."""

    mid8: str
    """8-character mission ID prefix (first 8 chars of ``mission_id``)."""

    mission_id: str
    """Full 26-character ULID mission ID."""

    coord_branch: str
    """Coordination branch ``kitty/mission-<slug>``."""

    primary_feature_dir: Path
    """``<repo>/kitty-specs/<slug>/`` on the PRIMARY checkout."""

    coord_feature_dir: Path
    """``<repo>/.worktrees/<slug>-coord/kitty-specs/<slug>/`` in the coord husk."""

    status_events_path: Path
    """Canonical ``status.events.jsonl`` on the coord husk (authoritative STATUS)."""

    decoy_events_path: Path
    """Decoy ``status.events.jsonl`` on the primary (distinct content — wrong-leg probe)."""

    coord_husk_meta_path: Path | None = None
    """Husk ``meta.json`` path when the SENTINEL variant wrote one, else ``None``.

    Present only for the ``coord_topology_mission_sentinel_meta`` variant (FR-009 /
    T001): the husk carries a PRESENT-but-WRONG ``meta.json`` (``mission_id`` =
    :data:`SENTINEL_HUSK_MISSION_ID`, ``mission_type`` =
    :data:`SENTINEL_HUSK_MISSION_TYPE`). For the base (STATUS-only) fixture this is
    ``None`` and no husk ``meta.json`` exists (the base invariant)."""


@dataclass(frozen=True)
class FlatTopologyContext:
    """All paths for a flat/single-branch mission fixture.

    For neutrality tests: a mission with ``topology=single_branch`` and no coord
    worktree. Both resolvers should return the primary dir.
    """

    repo: Path
    """Git repository root."""

    slug: str
    """Full composed mission slug ``<human>-<mid8>``."""

    mid8: str
    """8-character mission ID prefix."""

    mission_id: str
    """Full 26-character ULID mission ID."""

    primary_feature_dir: Path
    """``<repo>/kitty-specs/<slug>/`` on the PRIMARY checkout."""

    status_events_path: Path
    """``status.events.jsonl`` on the primary checkout."""


# ---------------------------------------------------------------------------
# Private git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run ``git -C <repo> <args>`` and return stripped stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_git_repo(parent: Path) -> Path:
    """Create a minimal initialised git repo with one commit under *parent*.

    Returns the absolute repo root path (``parent / "repo"``).
    """
    repo = parent / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    _git(repo, "config", "user.email", "coord-fixture@spec-kitty.test")
    _git(repo, "config", "user.name", "Coord Fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "README.md").write_text("coord-topology fixture repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init: coord-topology-fixture baseline")
    return repo


# ---------------------------------------------------------------------------
# Private artifact helpers
# ---------------------------------------------------------------------------


def _write_wp_task(tasks_dir: Path, wp_id: str, *, execution_mode: str | None = None) -> None:
    """Write a minimal WP task file to *tasks_dir* (``execution_mode`` declared when given)."""
    mode = f"execution_mode: {execution_mode}\n" if execution_mode is not None else ""
    content = (
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} fixture task\n"
        f"{mode}subtasks: []\n---\n# {wp_id}\n"
    )
    (tasks_dir / f"{wp_id}.md").write_text(content, encoding="utf-8")


def _write_lanes_json(feature_dir: Path, *, slug: str, mission_id: str) -> None:
    """Write a minimal but fully-parseable ``lanes.json`` to *feature_dir*.

    Includes all fields required by ``LanesManifest.from_dict``
    (``computed_at``, ``computed_from``) so tests that read lanes.json through
    the planning-read seam (LANE_STATE kind) get a valid manifest.
    """
    payload = {
        "version": 1,
        "mission_slug": slug,
        "mission_id": mission_id,
        "mission_branch": f"kitty/mission-{slug}",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": ["WP01"],
                "write_scope": [],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-06-26T00:00:00+00:00",
        "computed_from": "coord-topology-fixture",
        "planning_artifact_wps": [],
    }
    (feature_dir / "lanes.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _write_single_branch_lanes_json(feature_dir: Path, *, slug: str, mission_id: str, mission_branch: str | None = None) -> None:
    """Write the ``lanes.json`` a real ``single_branch`` Mission carries (#7224).

    Built by the canonical finalize computation (``compute_lanes`` with
    ``topology=SINGLE_BRANCH``): ONE repo-root ``lane-planning`` lane holding every
    WP, ``mission_branch`` equal to the target unless a recorded write branch is
    passed (the protected-target mint). There is no code lane and no lane branch, so the fixture never trips
    ``SINGLE_BRANCH_CODE_LANES_UNMIGRATED``.
    """
    from mission_runtime import MissionTopology
    from specify_cli.lanes.compute import compute_lanes
    from specify_cli.lanes.persistence import write_lanes_json
    from specify_cli.ownership.models import OwnershipManifest, WorkProductKind

    manifest = compute_lanes(
        dependency_graph={"WP01": []},
        ownership_manifests={
            "WP01": OwnershipManifest(execution_mode=WorkProductKind.CODE_CHANGE, owned_files=(), authoritative_surface="")
        },
        mission_slug=slug,
        target_branch="main",
        mission_id=mission_id,
        topology=MissionTopology.SINGLE_BRANCH,
        mission_branch=mission_branch,
    )
    write_lanes_json(feature_dir, manifest)


def _write_meta(
    feature_dir: Path,
    *,
    slug: str,
    mission_id: str,
    topology: str,
    coordination_branch: str | None,
    mission_type: str = "software-dev",
) -> None:
    """Write ``meta.json`` for a mission to *feature_dir*.

    ``mission_type`` defaults to the PRIMARY ``software-dev``; the FR-009 sentinel
    husk passes a distinct value so a wrong-leg ``get_mission_type`` read is
    falsifiable on a returned domain value.
    """
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": slug,
        "slug": slug,
        "mission_type": mission_type,
        "target_branch": "main",
        "vcs": "git",
        "topology": topology,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _status_event_line(
    slug: str,
    wp_id: str,
    *,
    marker: str,
    to_lane: str = "claimed",
) -> str:
    """Return one JSONL status-event line with *marker* in its reason."""
    return json.dumps(
        {
            "actor": "coord-fixture",
            "at": "2026-06-26T00:00:00+00:00",
            "event_id": "01KW2E7A0FIXTURE000000000" + marker[-1],
            "evidence": None,
            "execution_mode": "code_change",
            "feature_slug": slug,
            "force": False,
            "from_lane": "planned",
            "reason": marker,
            "review_ref": None,
            "to_lane": to_lane,
            "wp_id": wp_id,
        }
    )


# ---------------------------------------------------------------------------
# Fixtures (T001)
# ---------------------------------------------------------------------------


def _build_coord_topology(
    tmp_path: Path, *, write_husk_meta: bool, write_husk_tasks: bool = False
) -> CoordTopologyContext:
    """Materialise a post-#2106 coordination-topology mission (FR-014 / FR-009 / FR-007).

    ONE divergence definition shared by the base (STATUS-only husk) fixture, the
    FR-009 sentinel-husk-meta variant, and the FR-007 ``tasks/``-present-non-legacy
    husk variant — every consumer imports this single shape (T001: define
    divergence in ONE place).

    FR-007 variant (``write_husk_tasks=True``): the coord husk additionally carries
    a post-3.0 ``tasks/`` dir with a real ``WP01.md`` (and NO legacy
    ``planned``/``doing``/``for_review``/``done`` lane subdirs) alongside a
    correct-identity husk ``meta.json`` and the real ``status.events.jsonl``. This
    exercises the ``LEGACY_LANE_DIRS``/``.md`` branch of ``is_legacy_format`` (a
    coord husk that IS post-3.0 must classify NON-legacy), distinct from the base
    husk which short-circuits on the absent ``tasks/`` dir.

    Shape on disk after this builder runs:

    * ``<repo>/kitty-specs/<slug>/`` (PRIMARY):
      - ``meta.json``  — ``topology=coord``, ``coordination_branch`` set,
        ``mission_id = 01KW2E7AFC0000000000000001``, ``mission_type=software-dev``
      - ``tasks/WP01.md``
      - ``lanes.json``
      - ``status.events.jsonl``  — DECOY (distinct content from coord)

    * ``<repo>/.worktrees/<slug>-coord/kitty-specs/<slug>/`` (coord husk):
      - ``status.events.jsonl``  — AUTHORITATIVE (coord marker)
      - NO ``tasks/``, NO ``lanes.json``
      - ``meta.json`` — ONLY when ``write_husk_meta`` (the FR-009 sentinel: a
        PRESENT-but-WRONG meta whose ``mission_id`` / ``mission_type`` differ from
        PRIMARY). When ``write_husk_meta`` is ``False`` the husk carries NO
        ``meta.json`` (the base STATUS-only invariant).

    **No resolver is patched** — topology routing uses real git + filesystem.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    # --- Identity constants for this fixture instance ---
    mission_id = "01KW2E7AFC0000000000000001"
    mid8 = "01KW2E7A"
    human_slug = "coord-topo-fixture"
    slug = f"{human_slug}-{mid8}"
    coord_branch = f"kitty/mission-{slug}"

    # 1. Initialise repo under a coord-specific subdir so a test that also
    #    requests flat_topology_mission does not collide on tmp_path/repo.
    #    The sentinel variant uses a distinct subdir so a single test may request
    #    both the base and sentinel fixtures without a worktree-path collision.
    if write_husk_tasks:
        repo_subdir = "coord-tasks-husk"
    elif write_husk_meta:
        repo_subdir = "coord-sentinel"
    else:
        repo_subdir = "coord"
    repo = _make_git_repo(tmp_path / repo_subdir)

    # 2. Create the coord branch pointing at the initial commit (no mission
    #    files yet).  The worktree checked out at this branch will carry
    #    ONLY the baseline content — no kitty-specs/ directory.
    _git(repo, "branch", coord_branch)

    # 3. Build the primary mission dir with all planning + decoy artifacts.
    primary_feature_dir = repo / "kitty-specs" / slug
    primary_feature_dir.mkdir(parents=True)

    _write_meta(
        primary_feature_dir,
        slug=slug,
        mission_id=mission_id,
        topology="coord",
        coordination_branch=coord_branch,
    )

    tasks_dir = primary_feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_task(tasks_dir, "WP01")

    _write_lanes_json(primary_feature_dir, slug=slug, mission_id=mission_id)

    # DECOY: primary carries a status.events.jsonl with a distinct marker.
    # A wrong-leg read that returns the primary path will expose the decoy marker,
    # causing assert_status_from_coord to fail LOUDLY.
    decoy_events_path = primary_feature_dir / "status.events.jsonl"
    decoy_events_path.write_text(
        _status_event_line(
            slug,
            "WP01",
            marker=_DECOY_EVENT_MARKER,
            to_lane="blocked",
        )
        + "\n",
        encoding="utf-8",
    )

    # 4. Commit the primary planning artifacts so the repo HEAD is clean.
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: coord-topology primary planning artifacts")

    # 5. Materialise the coord worktree via the REAL CoordinationWorkspace
    #    helper (no stub, no monkeypatch).  The worktree checks out the
    #    coord branch (initial commit) → no kitty-specs/ in its working tree.
    coord_worktree_root = CoordinationWorkspace.resolve(repo, slug, mid8)

    # 6. Create the mission dir inside the coord husk and write STATUS-only content.
    #    (In the real workflow BookkeepingTransaction does this; here we write
    #    directly so the fixture is self-contained.)
    coord_mission_dir = coord_worktree_root / "kitty-specs" / slug
    coord_mission_dir.mkdir(parents=True)

    status_events_path = coord_mission_dir / "status.events.jsonl"
    status_events_path.write_text(
        _status_event_line(slug, "WP01", marker=_COORD_EVENT_MARKER) + "\n",
        encoding="utf-8",
    )

    # 7. Husk meta variant select: the FR-009 sentinel (present-but-WRONG identity),
    #    the FR-007 tasks-husk correct-identity meta, or the base STATUS-only
    #    invariant (no husk meta). ``lanes.json`` is NEVER written to the husk.
    coord_husk_meta_path: Path | None = None
    if write_husk_meta:
        _write_meta(
            coord_mission_dir,
            slug=slug,
            mission_id=SENTINEL_HUSK_MISSION_ID,
            topology="coord",
            coordination_branch=coord_branch,
            mission_type=SENTINEL_HUSK_MISSION_TYPE,
        )
        coord_husk_meta_path = coord_mission_dir / "meta.json"
    elif write_husk_tasks:
        # FR-007: a production-shaped post-3.0 husk carries a correct-identity
        # meta.json (matching the PRIMARY id — NOT the sentinel divergence) so the
        # no-op proof runs against a realistic coord husk, not an empty dir.
        _write_meta(
            coord_mission_dir,
            slug=slug,
            mission_id=mission_id,
            topology="coord",
            coordination_branch=coord_branch,
        )
        coord_husk_meta_path = coord_mission_dir / "meta.json"

    # FR-007: the post-3.0 ``tasks/`` dir (WP .md, NO legacy lane subdirs).
    if write_husk_tasks:
        husk_tasks_dir = coord_mission_dir / "tasks"
        husk_tasks_dir.mkdir()
        _write_wp_task(husk_tasks_dir, "WP01")

    # 8. Structural self-checks. ``lanes.json`` is absent on the husk for EVERY
    #    variant. ``tasks/`` is absent for base + sentinel (STATUS-only) and
    #    present-but-non-legacy for the FR-007 variant. The sentinel variant
    #    OVERRIDES the base ``no meta.json`` invariant with the HARD divergence
    #    triad (FR-009 / T001).
    if write_husk_tasks:
        husk_tasks_dir = coord_mission_dir / "tasks"
        assert husk_tasks_dir.is_dir(), (
            "FR-007 variant invariant violated: coord husk must carry tasks/"
        )
        assert list(husk_tasks_dir.glob("WP*.md")), (
            "FR-007 variant invariant violated: husk tasks/ must carry a WP .md file"
        )
        assert not any(child.is_dir() for child in husk_tasks_dir.iterdir()), (
            "FR-007 variant invariant violated: husk tasks/ must carry NO legacy "
            "lane subdirs (planned/doing/for_review/done) — it must classify "
            "NON-legacy via is_legacy_format"
        )
    else:
        assert not (coord_mission_dir / "tasks").exists(), (
            "Fixture invariant violated: coord husk must not carry tasks/"
        )
    assert not (coord_mission_dir / "lanes.json").exists(), (
        "Fixture invariant violated: coord husk must not carry lanes.json"
    )
    if write_husk_meta:
        # HARD divergence triad (asserted BEFORE any routed-path drive): the husk
        # lacks lanes.json + tasks/ (above), AND its meta carries the sentinel id
        # that is distinct from the resolved PRIMARY id (a silent-wrong-value, not
        # a missing file).
        assert coord_husk_meta_path is not None
        husk_meta = json.loads(coord_husk_meta_path.read_text(encoding="utf-8"))
        assert husk_meta["mission_id"] == SENTINEL_HUSK_MISSION_ID, (
            "Sentinel triad violated: husk meta mission_id must be the sentinel "
            f"{SENTINEL_HUSK_MISSION_ID!r}, got {husk_meta['mission_id']!r}."
        )
        assert husk_meta["mission_id"] != mission_id, (
            "Sentinel triad violated: husk meta mission_id must DIFFER from the "
            f"resolved PRIMARY id {mission_id!r} (else the identity proof is "
            "non-falsifiable)."
        )
    elif not write_husk_tasks:
        assert not (coord_mission_dir / "meta.json").exists(), (
            "Fixture invariant violated: base coord husk must not carry meta.json"
        )

    return CoordTopologyContext(
        repo=repo,
        slug=slug,
        mid8=mid8,
        mission_id=mission_id,
        coord_branch=coord_branch,
        primary_feature_dir=primary_feature_dir,
        coord_feature_dir=coord_mission_dir,
        status_events_path=status_events_path,
        decoy_events_path=decoy_events_path,
        coord_husk_meta_path=coord_husk_meta_path,
    )


@pytest.fixture()
def coord_topology_mission(tmp_path: Path) -> CoordTopologyContext:
    """Base coord-topology mission: STATUS-only husk (no ``meta.json``).

    Thin wrapper over :func:`_build_coord_topology` — the shared divergence
    definition. Behaviour is byte-identical to the pre-refactor fixture (the
    husk carries NO ``tasks/`` / ``lanes.json`` / ``meta.json``).
    """
    return _build_coord_topology(tmp_path, write_husk_meta=False)


@pytest.fixture()
def coord_topology_mission_sentinel_meta(tmp_path: Path) -> CoordTopologyContext:
    """FR-009 sentinel-husk-meta variant (coord-read-residuals WP01 / T001).

    Same topology as :func:`coord_topology_mission` BUT the coord husk carries a
    PRESENT-but-WRONG ``meta.json`` (``mission_id`` = :data:`SENTINEL_HUSK_MISSION_ID`,
    ``mission_type`` = :data:`SENTINEL_HUSK_MISSION_TYPE`), distinct from the
    resolved PRIMARY id/type. This OVERRIDES the base ``no meta.json`` invariant so
    a wrong-leg identity read returns a SILENT-WRONG-VALUE (the sentinel) instead
    of raising — making an identity-routing bug falsifiable on a returned domain
    value (FR-009 / NFR-004). ``lanes.json`` + ``tasks/`` stay PRIMARY-only (the
    HARD divergence triad, asserted in the builder before return).
    """
    return _build_coord_topology(tmp_path, write_husk_meta=True)


@pytest.fixture()
def coord_topology_mission_tasks_husk(tmp_path: Path) -> CoordTopologyContext:
    """FR-007 ``tasks/``-present-non-legacy husk variant (WP04 / T016).

    Same topology as :func:`coord_topology_mission` BUT the coord husk additionally
    carries a post-3.0 ``tasks/WP01.md`` (NO ``planned``/``doing``/``for_review``/
    ``done`` lane subdirs) and a correct-identity husk ``meta.json`` alongside the
    authoritative ``status.events.jsonl``. This exercises the ``LEGACY_LANE_DIRS``/
    ``.md`` branch of ``is_legacy_format`` — a coord husk that IS post-3.0 must
    classify NON-legacy, so :func:`check_pre30_layout` is a clean no-op against it
    (FR-007(b) / SC-004). WP04 is the SOLE consumer of this variant.
    """
    return _build_coord_topology(
        tmp_path, write_husk_meta=False, write_husk_tasks=True
    )


#: The flat fixture's Mission slug (``<human-slug>-<mid8>``).
FLAT_TOPOLOGY_SLUG = "flat-topo-fixture-01KW2E7B"


def build_flat_topology_mission(
    tmp_path: Path,
    *,
    topology: Literal["single_branch", "lanes"] = "single_branch",
    mission_branch: str | None = None,
) -> FlatTopologyContext:
    """Materialise a flat (coordination-less) mission for neutrality tests.

    Shape on disk:

    * ``<repo>/kitty-specs/<slug>/`` (PRIMARY only — no coord worktree):
      - ``meta.json``  — ``topology=<topology>``, no ``coordination_branch``
      - ``tasks/WP01.md`` (``execution_mode: code_change`` on single_branch)
      - ``lanes.json``
      - ``status.events.jsonl``

    ``topology="single_branch"`` (the default, #7224) writes the manifest a real
    single_branch Mission carries: one repo-root ``lane-planning`` lane, no code lane
    and no lane branch. ``mission_branch`` records a write branch distinct from the
    ``main`` target (the protected-target mint shape) in both ``meta.json`` and
    ``lanes.json``; the branch itself is not created. ``topology="lanes"`` keeps a
    coordination-less mission with one ``lane-a`` code lane, for tests whose subject
    is lane-branch or lane-worktree behaviour.

    Both ``candidate_feature_dir_for_mission`` and
    ``resolve_planning_read_dir(kind=WORK_PACKAGE_TASK)`` should return the
    primary dir for either topology.
    """
    mission_id = "01KW2E7BFC0000000000000001"
    mid8 = "01KW2E7B"
    slug = FLAT_TOPOLOGY_SLUG

    # Use a distinct subdir to avoid colliding with coord_topology_mission's repo.
    repo = _make_git_repo(tmp_path / "flat")

    primary_feature_dir = repo / "kitty-specs" / slug
    primary_feature_dir.mkdir(parents=True)

    _write_meta(
        primary_feature_dir,
        slug=slug,
        mission_id=mission_id,
        topology=topology,
        coordination_branch=None,
    )

    tasks_dir = primary_feature_dir / "tasks"
    tasks_dir.mkdir()
    if topology == "single_branch":
        # A single_branch lane is a repo-root lane, so "does this Mission carry code" is
        # read from the WP kind; a finalized code WP declares it.
        _write_wp_task(tasks_dir, "WP01", execution_mode="code_change")
        _write_single_branch_lanes_json(primary_feature_dir, slug=slug, mission_id=mission_id, mission_branch=mission_branch)
        if mission_branch is not None:
            meta_path = primary_feature_dir / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["mission_branch"] = mission_branch
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    else:
        assert mission_branch is None, "mission_branch is a single_branch knob"
        _write_wp_task(tasks_dir, "WP01")
        _write_lanes_json(primary_feature_dir, slug=slug, mission_id=mission_id)

    status_events_path = primary_feature_dir / "status.events.jsonl"
    status_events_path.write_text(
        _status_event_line(slug, "WP01", marker="FLAT_MARKER") + "\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: flat-topology mission")

    return FlatTopologyContext(
        repo=repo,
        slug=slug,
        mid8=mid8,
        mission_id=mission_id,
        primary_feature_dir=primary_feature_dir,
        status_events_path=status_events_path,
    )


@pytest.fixture()
def flat_topology_mission(tmp_path: Path) -> FlatTopologyContext:
    """A real single_branch mission (#7224); see :func:`build_flat_topology_mission`."""
    return build_flat_topology_mission(tmp_path)


def record_wp01_implementation(ctx: CoordTopologyContext) -> tuple[str, str]:
    """Opt-in (#6715): give WP01 the implementation evidence a real Mission carries.

    Declares WP01's ``owned_files`` (``src/wp01/**``) and pins the planning commit on PRIMARY
    (committed), then commits an owned change on the ``lane-a`` branch. ``move-task`` toward
    review and the consolidation claim refuse a work package without this evidence. Returns
    ``(planning_commit, lane_tip)``.
    """
    from tests.lane_test_utils import commit_lane_implementation
    from tests.terminus.conftest import record_evidence_prerequisites

    pin = record_evidence_prerequisites(ctx.repo, ctx.primary_feature_dir, globs=("src/wp01/**",))
    tip = commit_lane_implementation(ctx.repo, ctx.primary_feature_dir, lane_id="lane-a", path="src/wp01/impl.py")
    return pin, tip


# ---------------------------------------------------------------------------
# Dual-leg asserter helpers (T002)
# ---------------------------------------------------------------------------


def assert_reads_primary(
    resolved_path: Path,
    ctx: CoordTopologyContext | FlatTopologyContext,
    *,
    wp_id: str = "WP01",
) -> None:
    """Assert *resolved_path* equals the PRIMARY mission dir with tasks/ present.

    For a coord-topology mission this verifies that the resolver did NOT land on
    the STATUS-only coord husk (which lacks ``tasks/``). For a flat mission this
    is a simple identity check.

    Fails loudly if:
    - ``resolved_path`` differs from ``ctx.primary_feature_dir``
    - ``tasks/<wp_id>.md`` is absent at the resolved path (husk-read indicator)
    """
    assert resolved_path == ctx.primary_feature_dir, (
        f"PRIMARY dir mismatch.\n"
        f"  Expected : {ctx.primary_feature_dir}\n"
        f"  Got      : {resolved_path}\n"
        "A coord-topology bug routes to the STATUS-only husk instead of primary."
    )
    task_file = resolved_path / "tasks" / f"{wp_id}.md"
    assert task_file.exists(), (
        f"tasks/{wp_id}.md absent at {resolved_path}.\n"
        "Resolver landed on the coord husk (STATUS-only), not the primary dir.\n"
        f"  Primary dir : {ctx.primary_feature_dir}\n"
        f"  Resolved to : {resolved_path}"
    )


def assert_status_from_coord(
    events_path: Path,
    ctx: CoordTopologyContext,
) -> None:
    """Assert *events_path* is the authoritative coord-husk events file.

    The assertion is TWO-PRONGED so a wrong-leg read fails LOUDLY:

    1. **Path check**: ``events_path`` must equal ``ctx.status_events_path``
       (the coord husk path), NOT the primary decoy.
    2. **Content check**: the events file must contain the coord marker
       (``_COORD_EVENT_MARKER``) and must NOT contain the decoy marker.

    A wrong-leg read that returns the primary decoy path — or ANY path that
    holds the decoy content — triggers an AssertionError with a clear message.
    """
    assert events_path == ctx.status_events_path, (
        f"STATUS read path mismatch.\n"
        f"  Expected (coord husk) : {ctx.status_events_path}\n"
        f"  Got                   : {events_path}\n"
        "The resolver landed on the PRIMARY decoy instead of the coord husk."
    )
    content = events_path.read_text(encoding="utf-8")
    assert _COORD_EVENT_MARKER in content, (
        f"Coord marker absent in {events_path}.\n"
        f"  Marker expected : {_COORD_EVENT_MARKER!r}\n"
        "Wrong-leg read: the events file content looks like the primary decoy."
    )
    assert _DECOY_EVENT_MARKER not in content, (
        f"Primary DECOY marker found in {events_path}.\n"
        f"  Decoy marker    : {_DECOY_EVENT_MARKER!r}\n"
        "Wrong-leg read confirmed: reading from the primary decoy, not the coord husk."
    )


def assert_both_legs(
    resolved_primary_path: Path,
    events_path: Path,
    ctx: CoordTopologyContext,
    *,
    wp_id: str = "WP01",
) -> None:
    """Assert the full PRIMARY+STATUS split for a coord-topology mission.

    Combines :func:`assert_reads_primary` (tasks from PRIMARY) and
    :func:`assert_status_from_coord` (events from COORD) so per-site tests
    can assert the complete routing invariant in one call.
    """
    assert_reads_primary(resolved_primary_path, ctx, wp_id=wp_id)
    assert_status_from_coord(events_path, ctx)


__all__ = [
    "SENTINEL_HUSK_MISSION_ID",
    "SENTINEL_HUSK_MISSION_TYPE",
    "CoordTopologyContext",
    "FLAT_TOPOLOGY_SLUG",
    "FlatTopologyContext",
    "build_flat_topology_mission",
    "assert_both_legs",
    "assert_reads_primary",
    "assert_status_from_coord",
    "coord_topology_mission",
    "coord_topology_mission_sentinel_meta",
    "coord_topology_mission_tasks_husk",
    "flat_topology_mission",
    "record_wp01_implementation",
]
