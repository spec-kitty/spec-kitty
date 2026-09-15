"""Artifact-home contract for mission runtime consumers.

This module is internal to :mod:`mission_runtime`; callers import the public
symbols from the package root.
"""

from __future__ import annotations

import enum
import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from mission_runtime.context import (
    CommitTarget,
    MissionTopology,
    routes_through_coordination,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from kernel.paths import to_posix


class TopologySurface(enum.StrEnum):
    """A physical tree a mission artifact resolves to — ``surface`` Sense 2.

    Named ``TopologySurface`` (not bare ``Surface``) because ``surface`` is a
    governed overloaded term: Sense 1 is the agent-facing *tool* surface
    (:class:`specify_cli.tool_surface.enums.ToolSurfaceKind`). See
    ``docs/context/orchestration.md`` and ADR ``2026-07-23-1``.

    ``COORD`` replaces the former ``PLACEMENT`` member: the old name avoided the
    *word* rather than the *concept*. Naming a surface ``COORD`` does NOT breach
    the rule against conditioning behaviour on topology — the label is this
    seam's OUTPUT vocabulary, never a per-call-site branching input. A
    ``if surface is COORD: <inline path derivation>`` at a call site stays
    forbidden.

    The ``str`` mixin keeps ``== "primary"`` comparisons working. Note the
    ``"placement"`` wire value is retired with the member; it was never
    persisted to any mission artifact, so no data migration is implied.

    ``LANE`` / ``CONSOLIDATED`` / ``TEMP`` are declared **with** the
    surface→filesystem translation seam that makes each resolvable
    (:func:`mission_runtime.resolution.translate_surface` — data-model.md
    "TopologySurface", IC-11): every member maps to a real location, so none is a
    phantom. They have no production caller yet — ``CONSOLIDATED`` is wired by the
    consolidation flow (IC-04), ``LANE`` / ``TEMP`` by later work — but the
    seam's totality test (:func:`assert_surface_totality`) exercises every member,
    which is what "declared with the seam, not before it" means.

    ``CONSOLIDATED`` is only meaningful from ``LifecyclePhase.POST_CONSOLIDATION``
    onward (data-model.md); the phase gate belongs to the consolidation consumer,
    not to this vocabulary enum.
    """

    PRIMARY = "primary"
    COORD = "coord"
    LANE = "lane"
    CONSOLIDATED = "consolidated"
    TEMP = "temp"


class MissionArtifactKind(enum.Enum):
    """Mission artifact categories whose home can differ by topology."""

    PRIMARY_METADATA = "primary_metadata"
    FINALIZED_EXECUTION_PLAN = "finalized_execution_plan"
    TASKS_INDEX = "tasks_index"
    WORK_PACKAGE_TASK = "work_package_task"
    LANE_STATE = "lane_state"
    ACCEPTANCE_MATRIX = "acceptance_matrix"
    ISSUE_MATRIX = "issue_matrix"
    STATUS_STATE = "status_state"
    ANALYSIS_REPORT = "analysis_report"
    # Planning SOURCE docs (/spec-kitty.specify + /spec-kitty.plan outputs).
    # write-surface-coherence WP01-04: these are PRIMARY-partition kinds (members
    # of ``_PRIMARY_ARTIFACT_KINDS``). They live with their mission on the primary
    # ``target_branch`` for EVERY topology and NEVER transit the coordination
    # branch, so a stale primary copy is a REAL dirty-tree blocker — not residue.
    SPEC = "spec"
    DATA_MODEL = "data_model"
    RESEARCH = "research"
    CHECKLIST = "checklist"
    # Terminal PRIMARY-partition artifact (FR-002): the post-merge retrospective
    # (``retrospective.yaml``) lives with its mission in the durable
    # ``kitty-specs/<slug>/`` home for EVERY topology and never transits the
    # coordination branch.
    RETROSPECTIVE = "retrospective"
    # coord-write-placement-closure-01KYCF83 WP02 (FR-003): decisions.events.jsonl
    # (the decision-log event stream, ``events/decision_log.py``) is a
    # COORD-partition kind (member of ``_PLACEMENT_ARTIFACT_KINDS``) -- it is
    # coordination-owned bookkeeping, never a PRIMARY planning/identity artifact.
    DECISION_LOG = "decision_log"
    # coord-write-placement-closure-01KYCF83 WP02 (FR-006): traces/ (mission
    # tracer files) is a COORD-partition kind -- doctrine-correct classification
    # corrects the prior unclassified (residue-invisible) state.
    TRACER_FILE = "tracer_file"
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023, ADR 2026-08-03-1):
    # tasks/<wp>/review-cycle-<N>.md is a COORD-partition kind -- per-WP review
    # lifecycle bookkeeping (written repeatedly during execution), not stable
    # planning output. It stops borrowing WORK_PACKAGE_TASK, whose PRIMARY
    # placement was a path coincidence (living under tasks/), not a partition
    # argument. See the file-pattern classifier leg in
    # ``_artifact_kind_for_path`` below -- filename-anchored, never
    # directory-anchored, so ``tasks/<wp>/baseline-tests.json`` stays
    # WORK_PACKAGE_TASK.
    REVIEW_CYCLE = "review_cycle"
    # #3928: the Decision Moment LEDGER directory (``decisions/index.json`` +
    # ``decisions/DM-<ulid>.md``, ``decisions/store.py``) is a COORD-partition
    # kind -- ``decisions/service.py``'s ``_mission_dir`` already documents the
    # ledger as "coord-authority-owned STATUS-partition state" routed through
    # ``placement_seam(...).read_dir(STATUS_STATE)``. Its own kind (NOT
    # STATUS_STATE itself -- ``is_status_state_path`` must keep matching
    # exactly ``status.events.jsonl`` / ``status.json`` and nothing else) so
    # the churn classifier (``kind_for_mission_file`` ->
    # ``kind_is_coordination_residue``) finally agrees with the write side:
    # an uncommitted ledger is coordination residue, not real worktree dirt.
    DECISION_LEDGER = "decision_ledger"


@dataclass(frozen=True)
class MissionArtifactHome:
    """Resolved read/write/commit home for one mission artifact kind."""

    kind: MissionArtifactKind
    read_surface: TopologySurface
    write_surface: TopologySurface
    commit_target: CommitTarget | None


def kind_is_coordination_residue(
    kind: MissionArtifactKind,
    topology: MissionTopology,
) -> bool:
    """Is ``kind`` coordination residue under ``topology`` (stored-topology projection)?

    The #2090-clean residue authority: coord-routing is derived from the **stored**
    :class:`MissionTopology` via the SINGLE :func:`routes_through_coordination`
    predicate over ``COORD`` / ``LANES_WITH_COORD`` — NEVER from a fabricated
    ``CommitTarget`` ``.kind`` shim. A placement-kind artifact whose home ignores
    primary residue is residue iff the mission routes through coordination; the two
    coord-less cells (``SINGLE_BRANCH`` / ``LANES``) have no primary↔coordination
    split, so nothing is residue there (the flat→False cell). The placement ref the
    home carries is irrelevant to the routing decision — only the kind's
    :data:`_PLACEMENT_ARTIFACT_KINDS` membership and the stored topology matter.
    """
    if not routes_through_coordination(topology):
        return False
    return kind in _PLACEMENT_ARTIFACT_KINDS


# FR-004 / data-model.md "The swappable locus (NFR-004)": the single partition
# whose membership routes a kind to the PRIMARY ``target_branch`` for every
# topology shape (read AND write — INV-5 full symmetry). Planning + identity
# artifacts (specify/plan/tasks/finalize/lanes/meta) live with their mission on
# the primary surface; flipping a kind across the two sets is a one-line move,
# never a code change (NFR-004).
_PRIMARY_ARTIFACT_KINDS: frozenset[MissionArtifactKind] = frozenset(
    {
        MissionArtifactKind.SPEC,
        MissionArtifactKind.DATA_MODEL,
        MissionArtifactKind.RESEARCH,
        MissionArtifactKind.CHECKLIST,
        MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
        MissionArtifactKind.TASKS_INDEX,
        MissionArtifactKind.WORK_PACKAGE_TASK,
        # LANE_STATE (lanes.json, finalize output) travels with tasks.md → PRIMARY.
        MissionArtifactKind.LANE_STATE,
        MissionArtifactKind.PRIMARY_METADATA,
        # FR-002: the post-merge retrospective is a terminal PRIMARY-partition
        # artifact — it resolves to the durable mission home for every topology.
        MissionArtifactKind.RETROSPECTIVE,
        # FR-003 (coord-commit-integrity): ANALYSIS_REPORT re-homed COORD→PRIMARY.
        # ``write_analysis_report`` requires spec/plan/tasks as freshness-hash
        # siblings, which are PRIMARY-only — the coord worktree lacks them, so a
        # "write-in-home" on COORD is structurally impossible. The writer + freshness
        # gate already resolve PRIMARY; only the SSOT said COORD. Re-homing makes
        # writer+gate+SSOT agree — a mis-classification correction, NOT a contract
        # redesign. This is the ONE frozenset membership move; the ~9 residue
        # delegators + ``is_primary_artifact_kind`` flip atomically from it. The
        # ``_MISSION_FILE_KIND_BY_BASENAME["analysis-report.md"]`` classifier entry
        # is KEPT (it is the file→kind map, not a residue-only list — deleting it would make
        # ``kind_for_mission_file("analysis-report.md") → None`` and mis-route it).
        MissionArtifactKind.ANALYSIS_REPORT,
    }
)

# FR-004: the COORD partition — coordination-owned artifacts that route to the
# coordination branch under coordination topology and whose stale primary copies
# are coordination residue. ACCEPTANCE_MATRIX (accept-time verification) and
# ISSUE_MATRIX (authored verdicts) stay COORD per data-model.md. ANALYSIS_REPORT
# was re-homed to the PRIMARY partition (FR-003, coord-commit-integrity) — see
# ``_PRIMARY_ARTIFACT_KINDS`` above.
_PLACEMENT_ARTIFACT_KINDS: frozenset[MissionArtifactKind] = frozenset(
    {
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        MissionArtifactKind.ISSUE_MATRIX,
        MissionArtifactKind.STATUS_STATE,
        # coord-write-placement-closure-01KYCF83 WP02 (FR-003, FR-006): newly
        # classified COORD-partition kinds -- see the enum member docstrings
        # above for the per-kind rationale.
        MissionArtifactKind.DECISION_LOG,
        MissionArtifactKind.TRACER_FILE,
        # review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023, ADR
        # 2026-08-03-1): review-cycle artifacts are per-WP lifecycle
        # bookkeeping -- COORD-partition, not the WORK_PACKAGE_TASK they used
        # to borrow. See the enum member docstring above.
        MissionArtifactKind.REVIEW_CYCLE,
        # #3928: the Decision Moment ledger (``decisions/``) joins the COORD
        # partition -- see the DECISION_LEDGER enum member docstring above.
        MissionArtifactKind.DECISION_LEDGER,
    }
)

# The file→kind CLASSIFIER: the ONE map :func:`kind_for_mission_file` consults to
# classify a bare mission-file basename to its :class:`MissionArtifactKind`. It is
# a plain basename→kind lookup that holds BOTH partitions' kinds — PRIMARY
# (``spec.md``, ``analysis-report.md``, ``baseline-tests.json``, …) and COORD
# (``issue-matrix.md``, ``status.events.jsonl``, …). The residue/partition question
# is answered SEPARATELY by the kind's frozenset membership
# (:data:`_PRIMARY_ARTIFACT_KINDS` / :data:`_PLACEMENT_ARTIFACT_KINDS`), so an entry
# here says only "this basename maps to this kind", never "this kind is coord
# residue". KEEP every entry: dropping one makes the classifier return ``None`` for
# that path → it mis-routes via the unrecognized-path fallback.
_MISSION_FILE_KIND_BY_BASENAME: dict[str, MissionArtifactKind] = {
    "plan.md": MissionArtifactKind.FINALIZED_EXECUTION_PLAN,
    "tasks.md": MissionArtifactKind.TASKS_INDEX,
    # partition-authority-residuals-01M021K9 WP06 (#2937 / FR-009): wps.yaml is
    # the finalize INPUT manifest (the structured source ``finalize-tasks``
    # regenerates ``tasks.md`` from). It lives at ``feature_dir/wps.yaml`` on the
    # PRIMARY surface, travels with ``tasks.md`` → classify to the PRIMARY-partition
    # ``TASKS_INDEX`` kind so finalize versions it (INV-5: read-from-PRIMARY must
    # be written-back-to-PRIMARY, else the finalized checkpoint cannot reproduce
    # its own state). A membership ADD for a previously-unclassified file (the
    # ``None``→PRIMARY fallback coincidence is now a derivable classification) —
    # NOT a predicate fork, and TASKS_INDEX is already in ``_PRIMARY_ARTIFACT_KINDS``
    # so the P-1 partition invariant is unchanged.
    "wps.yaml": MissionArtifactKind.TASKS_INDEX,
    "lanes.json": MissionArtifactKind.LANE_STATE,
    "acceptance-matrix.json": MissionArtifactKind.ACCEPTANCE_MATRIX,
    "issue-matrix.md": MissionArtifactKind.ISSUE_MATRIX,
    # write-side-seam-matrix-tracer-01KYP3MH WP05 (B2 / T019 / FR-002): the
    # issue-matrix migrates from free markdown to a structured JSON artifact
    # (see ``specify_cli.tasks.issue_matrix``). Added BESIDE the ``.md`` entry
    # above -- NOT a replacement -- so failover-read (FR-013) keeps working for
    # a mission that has not migrated yet. Without this entry
    # ``kind_for_mission_file("issue-matrix.json")`` returns ``None`` and the
    # file silently fails to stage to coord / row-merge (the B2 linchpin).
    "issue-matrix.json": MissionArtifactKind.ISSUE_MATRIX,
    "status.events.jsonl": MissionArtifactKind.STATUS_STATE,
    "status.json": MissionArtifactKind.STATUS_STATE,
    # KEPT after the COORD→PRIMARY re-home (FR-003): this is the file→kind
    # classifier entry, not a residue flag. ``ANALYSIS_REPORT`` is now a
    # PRIMARY-partition kind (see ``_PRIMARY_ARTIFACT_KINDS``), so its residue
    # predicates flip via the frozenset — this entry must stay so the basename
    # still classifies to ``ANALYSIS_REPORT`` instead of degrading to ``None``.
    "analysis-report.md": MissionArtifactKind.ANALYSIS_REPORT,
    "spec.md": MissionArtifactKind.SPEC,
    "data-model.md": MissionArtifactKind.DATA_MODEL,
    "research.md": MissionArtifactKind.RESEARCH,
    "retrospective.yaml": MissionArtifactKind.RETROSPECTIVE,
    # ``baseline-tests.json`` is the move-task post-merge stale-assertion baseline
    # (``review/baseline.py``); it lives with its WP ``tasks/`` siblings on the
    # PRIMARY ``target_branch`` for every topology, so it classifies to the PRIMARY
    # ``WORK_PACKAGE_TASK`` partition. Listing it here makes that partition
    # DERIVABLE from the basename rather than caller-asserted at the read site.
    "baseline-tests.json": MissionArtifactKind.WORK_PACKAGE_TASK,
    # coord-write-placement-closure-01KYCF83 WP02 (FR-003): decisions.events.jsonl
    # is the decision-log event stream (``events/decision_log.py``) -- a
    # COORD-partition kind (see ``_PLACEMENT_ARTIFACT_KINDS``).
    "decisions.events.jsonl": MissionArtifactKind.DECISION_LOG,
}

_COORD_RESIDUE_DIRS: dict[str, MissionArtifactKind] = {
    "tasks": MissionArtifactKind.WORK_PACKAGE_TASK,
    "checklists": MissionArtifactKind.CHECKLIST,
    # coord-write-placement-closure-01KYCF83 WP02 (FR-006): traces/ (mission
    # tracer files) is a COORD-partition kind (see ``_PLACEMENT_ARTIFACT_KINDS``).
    "traces": MissionArtifactKind.TRACER_FILE,
    # #3928: decisions/ (the Decision Moment ledger -- ``index.json`` +
    # ``DM-<ulid>.md``, the only two shapes ``decisions/store.py`` writes) is
    # a COORD-partition kind, matching the write side's own placement
    # (``decisions/service.py`` routes the directory through
    # ``read_dir(STATUS_STATE)``). Directory-anchored like traces/ -- unlike
    # tasks/, nothing under decisions/ is deliberately PRIMARY, so there is no
    # review-cycle-style filename leg to draw.
    "decisions": MissionArtifactKind.DECISION_LEDGER,
}

# review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023, ADR 2026-08-03-1):
# the FILENAME-anchored classifier leg for review-cycle artifacts. Deliberately
# NOT a ``_COORD_RESIDUE_DIRS["tasks"]`` entry (that dict is a DIRECTORY-kind
# fallback keyed on ``mission_rel_parts[0]`` alone, which would also swallow
# ``tasks/<wp>/baseline-tests.json`` -- deliberately PRIMARY -- and any other
# non-review-cycle file under ``tasks/``). The permissive glob (not a stricter
# numeric ``review-cycle-\d+.md``) matches the ADR's own text verbatim; see
# ``test_review_cycle_pattern_classifies_non_numeric_suffix`` for the explicit
# boundary this choice draws.
_REVIEW_CYCLE_FILENAME_GLOB = "review-cycle-*.md"


def artifact_home_for(
    kind: MissionArtifactKind,
    placement_ref: CommitTarget,
) -> MissionArtifactHome:
    """Resolve the artifact-home contract for ``kind`` under ``placement_ref``."""
    # FR-002 / FR-004: planning + identity kinds resolve to the PRIMARY surface.
    # coord-write-placement-closure-01KYCF83 WP02 (T006): ``PRIMARY_METADATA``
    # no longer gets a special-case ``commit_target=None`` arm ahead of this
    # one -- it is a ``_PRIMARY_ARTIFACT_KINDS`` member like every other primary
    # planning kind, so it now falls through here and carries the resolved
    # ``placement_ref`` as its commit target too, making meta writes routable
    # through the port (``write_meta`` / ``_flip_phase`` / `_bake_mission_number`).
    # The pre-fix read-anchored ``None`` sentinel was audited (T005) and
    # confirmed inert: the sole port consumer (``resolution.py:949``) copies
    # ``home.commit_target`` verbatim into ``MissionArtifactContext`` without
    # branching on ``None``-as-skip-commit.
    if kind in _PRIMARY_ARTIFACT_KINDS:
        return MissionArtifactHome(
            kind=kind,
            read_surface=TopologySurface.PRIMARY,
            write_surface=TopologySurface.PRIMARY,
            commit_target=placement_ref,
        )

    if kind in _PLACEMENT_ARTIFACT_KINDS:
        return MissionArtifactHome(
            kind=kind,
            read_surface=TopologySurface.COORD,
            write_surface=TopologySurface.COORD,
            commit_target=placement_ref,
        )

    raise ValueError(f"Unhandled mission artifact kind: {kind!r}")


def assert_partition_invariant() -> None:
    """Guard P-1: the partition frozensets are disjoint AND jointly exhaustive.

    ``_PRIMARY_ARTIFACT_KINDS`` and ``_PLACEMENT_ARTIFACT_KINDS`` must never
    overlap (no kind double-classified) and their union must cover every
    :class:`MissionArtifactKind` member (no kind left unclassified) —
    data-model.md Invariant P-1. The placement seam (T002,
    coord-primary-partition-lock WP01) asserts this at construction so a future
    kind added to the enum without a partition entry fails LOUD at the seam
    boundary rather than surfacing as a deep ``ValueError: Unhandled mission
    artifact kind`` inside :func:`artifact_home_for`.

    Raises:
        AssertionError: When the partition is not disjoint-and-total.
    """
    overlap = _PRIMARY_ARTIFACT_KINDS & _PLACEMENT_ARTIFACT_KINDS
    if overlap:
        raise AssertionError(
            "P-1 violated: kind(s) classified in BOTH partitions: "
            f"{sorted(kind.value for kind in overlap)}"
        )
    covered = _PRIMARY_ARTIFACT_KINDS | _PLACEMENT_ARTIFACT_KINDS
    all_kinds = frozenset(MissionArtifactKind)
    if covered != all_kinds:
        missing = all_kinds - covered
        raise AssertionError(
            "P-1 violated: kind(s) classified in NEITHER partition: "
            f"{sorted(kind.value for kind in missing)}"
        )


def assert_surface_totality(handled: frozenset[TopologySurface]) -> None:
    """Guard: the translation seam handles every :class:`TopologySurface` member.

    The anti-phantom totality guard for the surface→filesystem translation seam
    (data-model.md "TopologySurface" — the three planned members are declared
    *with* the seam, never before it; a member no caller can resolve is a
    phantom). It mirrors :func:`assert_partition_invariant`: pure in-memory set
    arithmetic, cheap enough to run on every :func:`translate_surface` call, so a
    future member added to :class:`TopologySurface` without a translation entry
    fails LOUD at the seam boundary rather than surfacing as a silent miss.

    ``handled`` is the set of members the caller's translation map covers. It must
    equal the full :class:`TopologySurface` membership exactly — neither a missing
    member (a phantom the seam cannot locate) nor a surplus member (a translation
    for a value the enum does not define).

    Raises:
        AssertionError: When ``handled`` is not exactly the enum membership.
    """
    all_surfaces = frozenset(TopologySurface)
    missing = all_surfaces - handled
    if missing:
        raise AssertionError(
            "Phantom TopologySurface member(s) with no translation: "
            f"{sorted(member.value for member in missing)}"
        )
    surplus = handled - all_surfaces
    if surplus:
        raise AssertionError(
            "Translation entry for non-member surface(s): "
            f"{sorted(str(member) for member in surplus)}"
        )


def is_primary_artifact_kind(kind: MissionArtifactKind) -> bool:
    """Return True if ``kind`` is a PRIMARY-partition kind (lands on target_branch).

    The public predicate over the swappable partition
    (:data:`_PRIMARY_ARTIFACT_KINDS`, NFR-004): a primary kind (planning + identity
    artifacts) resolves to the primary ``target_branch`` for every topology and
    NEVER transits coordination. Consumers outside ``mission_runtime`` query the
    partition through this package-root predicate rather than importing the
    private set (shared-package-boundary).
    """
    return kind in _PRIMARY_ARTIFACT_KINDS


def kind_for_mission_file(
    path: str | Path,
    *,
    mission_slug: str | None = None,
) -> MissionArtifactKind | None:
    """Classify a ``kitty-specs/<slug>/`` file path to its :class:`MissionArtifactKind`.

    The ONE public file→kind classification authority (write-surface-coherence
    WP03 / NFR-004). Write-side callers that hold a *path* (the ``safe-commit``
    command, ``append-history``) consume this helper so the kind partition is
    derived from a single classifier instead of re-deriving it per call site.

    Returns the kind for a recognised mission artifact (``spec.md`` → ``SPEC``,
    ``tasks/WP*.md`` → ``WORK_PACKAGE_TASK``, ``status.events.jsonl`` →
    ``STATUS_STATE``, …) and ``None`` for an unrecognised path or another
    mission's artifact (when ``mission_slug`` is supplied). The returned kind's
    partition membership (:data:`_PRIMARY_ARTIFACT_KINDS`) then selects the
    primary vs topology-routed placement via :func:`resolve_placement_only`.
    """
    return _artifact_kind_for_path(path, mission_slug=mission_slug)


def _artifact_kind_for_path(
    path: str | Path,
    *,
    mission_slug: str | None,
) -> MissionArtifactKind | None:
    normalized = to_posix(path).rstrip("/")
    parts = PurePosixPath(normalized).parts
    try:
        specs_index = parts.index(KITTY_SPECS_DIR)
    except ValueError:
        return None

    mission_index = specs_index + 1
    rel_index = mission_index + 1
    if rel_index >= len(parts):
        return None

    path_mission_slug = parts[mission_index]
    if mission_slug is not None and path_mission_slug != mission_slug:
        return None

    mission_rel_parts = parts[rel_index:]
    if len(mission_rel_parts) == 1:
        name = mission_rel_parts[0]
        return _MISSION_FILE_KIND_BY_BASENAME.get(name) or _COORD_RESIDUE_DIRS.get(name)

    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (FR-023, T014): a
    # nested-pattern leg keyed PURELY on the final path component's filename
    # shape -- never on directory depth or the WP-slug segment's spelling (a
    # WP directory named e.g. ``review-cycle-something`` must not itself
    # trigger this; only the FILE's own basename does), and it runs BEFORE the
    # unconditional ``_COORD_RESIDUE_DIRS`` directory-kind fallback below. Only
    # ``tasks/`` is in scope (review-cycle files never live under
    # ``checklists/`` / ``traces/``); anything under ``tasks/`` that does NOT
    # match the glob (``baseline-tests.json``, ``WP*.md`` when nested -- not a
    # real shape today but defensive) falls through unchanged to the
    # directory-kind fallback, exactly as before this WP.
    if mission_rel_parts[0] == "tasks" and fnmatch.fnmatch(
        mission_rel_parts[-1], _REVIEW_CYCLE_FILENAME_GLOB
    ):
        return MissionArtifactKind.REVIEW_CYCLE

    return _COORD_RESIDUE_DIRS.get(mission_rel_parts[0])
