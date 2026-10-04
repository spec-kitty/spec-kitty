"""Pure lane-compute-and-persist core (#4758, WP01).

Extracted from ``mission_finalize_lanes._compute_and_write_lanes`` so the
compute-lanes-then-write-lanes.json step has exactly one implementation,
reusable by:

- ``mission_finalize_lanes._compute_and_write_lanes`` -- becomes a thin CLI
  wrapper: it resolves ``planning_commit_sha`` (via the still-local
  ``_preserve_or_capture_planning_commit_sha``, which owns the #3311
  preserve-vs-capture-vs-refresh decision) and ``mission_id`` (from
  ``meta.json``), calls this core, then reports the decision on the
  console / in the ``--json`` payload.
- the legacy ``agent tasks finalize-tasks`` (``tasks_finalize.py``) -- the
  #4758 minting fix: this command now co-locates a real ``lanes.json``
  write with its event-log bootstrap instead of leaving the mission with
  ``genesis->planned`` events seeded and no ``lanes.json`` (the wedge
  ``move-task`` can then walk a WP straight through).
- WP03's ``doctor mission-state --fix`` recovery action, which rebuilds
  ``lanes.json`` from the event log when the shared wedge predicate
  (:func:`specify_cli.lanes.persistence.is_execution_wedged`) holds.

Layer purity (C-001): this module imports **no** ``typer``, no
console/rich, no ``json``, and no ``specify_cli.policy`` -- it is a plain
function over already-resolved inputs. ``planning_commit_sha`` and
``mission_id`` are supplied by the caller and never re-derived here (no git
subprocess calls, no ``meta.json`` reads). Errors are raised as a plain
exception (:class:`LaneGlobValidationError`) carrying the raw
:class:`~specify_cli.ownership.validation.GlobValidationResult`, so a CLI
caller can render its own console/JSON error surface without this module
depending on either.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from mission_runtime import MissionTopology, assert_topology_matches_manifest

from specify_cli.lanes.branch_naming import InvalidMissionIdentity
from specify_cli.lanes.compute import LaneComputationError, compute_lanes, has_code_lanes
from specify_cli.lanes.frozen_membership import assert_frozen_membership_honoured
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.ownership.validation import validate_glob_matches

if TYPE_CHECKING:
    from pathlib import Path

    from specify_cli.lanes.frozen_membership import FrozenLaneMembership
    from specify_cli.lanes.models import LanesManifest
    from specify_cli.ownership.models import OwnershipManifest
    from specify_cli.ownership.validation import GlobValidationResult
    from specify_cli.status import WPMetadata

__all__ = ["LaneGlobValidationError", "compute_and_write_lanes"]


class LaneGlobValidationError(Exception):
    """A literal-path ``owned_files`` entry matched zero files in the repo.

    Carries the full :class:`GlobValidationResult` (errors/warnings/info)
    so a CLI caller can render its own diagnostics without this module
    importing console/json/typer. No ``lanes.json`` is written when this is
    raised -- the caller's existing on-disk ``lanes.json`` (if any) is left
    untouched.
    """

    def __init__(self, result: GlobValidationResult) -> None:
        self.result = result
        super().__init__("Lane computation aborted: literal-path owned_files entries match zero files. Fix the paths before lanes.json is written.")


def _preserved_mission_branch(previous: LanesManifest | None, computed: str, *, topology: MissionTopology) -> str:
    """FR-011: a re-finalize keeps the Mission branch the first finalize recorded.

    The first finalize defines the Mission branch that lane creation later
    creates from the manifest (``_ensure_mission_branch``); recomputing it from a
    since-backfilled identity would name a branch that was never created.

    #5100 WP05 fold B3 (out-of-map edit to WP03's file, plan "Post-plan squad
    folds"): a ``SINGLE_BRANCH`` mission NEVER preserves a previously-recorded
    ``mission_branch``. ``compute_lanes`` already resolved the correct value
    (``meta.mission_branch`` or ``target_branch``, T022) for THIS topology;
    the FR-011 preserve-on-re-finalize rule below exists to protect a REAL
    mission branch that lane creation already created on disk (research Part
    A §4) -- a single_branch mission never creates that branch, so
    re-injecting a stale ``previous.mission_branch`` (e.g. a ``kitty/mission-
    …`` value recorded before the mission adopted single_branch, or from a
    legacy re-finalize) would defeat the contract
    (``contracts/single-branch-execution.md``, "Finalize") instead of
    honouring it.
    """
    if topology is MissionTopology.SINGLE_BRANCH:
        return computed
    if previous is not None and previous.mission_branch:
        # ``cast``, not a suppression: a narrow-file mypy check resolves
        # ``LanesManifest`` (from ``specify_cli.lanes.models``) through the
        # project-wide ``specify_cli.*`` follow-imports skip, so the field
        # types as ``Any`` here even though it is declared ``str`` on the
        # dataclass; the cast restores the real, already-guaranteed type.
        return cast(str, previous.mission_branch)
    return computed


def compute_and_write_lanes(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
    target_branch: str,
    *,
    planning_commit_sha: str | None,
    mission_id: str | None,
    topology: MissionTopology,
    mission_branch: str | None = None,
    frozen: FrozenLaneMembership | None = None,
) -> tuple[Path, LanesManifest]:
    """Compute execution lanes and persist ``lanes.json`` -- the pure core.

    ``planning_commit_sha`` and ``mission_id`` are **already-resolved**
    inputs: the caller owns deciding whether to capture the current
    ``target_branch`` tip, preserve a previously recorded SHA (#3311), or
    refresh it (#4141); and owns extracting ``mission_id`` from
    ``meta.json``. This function performs no git subprocess calls and no
    ``meta.json`` reads -- it only re-validates ``owned_files`` glob
    matches (the same re-validation the pre-extraction body performed),
    computes lanes, and writes ``lanes.json`` atomically.

    Args:
        planning_dir: The mission's primary-partition directory
            (``kitty-specs/<mission_slug>/``) -- where ``lanes.json`` is
            written.
        repo_root: Repository root, for glob resolution.
        mission_slug: Mission identifier.
        wp_manifests: WP id -> ``OwnershipManifest``.
        wp_dependencies: WP id -> list of dependency WP ids.
        wp_frontmatters: WP id -> ``WPMetadata`` (for ``create_intent``).
        wp_bodies: WP id -> body text, for surface inference.
        target_branch: Branch the mission merges into.
        planning_commit_sha: Already-resolved recorded planning-artifact
            SHA (or ``None``) to freeze into the written manifest.
        mission_id: Already-resolved mission id (or ``None``) from
            ``meta.json``.
        topology: The mission's already-resolved :class:`MissionTopology`
            (#5100 IC-02 / M3), read by the caller via
            :func:`specify_cli.migration.backfill_topology.read_topology`.
            Threaded through by all three callers of this function; a
            LATER work package of this mission (WP05, IC-03) wires it into
            the fail-closed
            :func:`mission_runtime.assert_topology_matches_manifest`
            call this function does not yet make (WP04 promoted that
            assertion to public and wired its first real caller into the
            review path -- ``agent/workflow.py``; #5100 WP05 wires this
            function's own writer chokepoint below). Validated at this
            boundary (``input-validation-fail-fast``) so a caller passing
            the wrong type fails loud here rather than downstream.
        mission_branch: The caller's already-resolved ``meta.json``
            ``mission_branch`` (or ``None``), threaded into
            :func:`~specify_cli.lanes.compute.compute_lanes` for
            ``SINGLE_BRANCH`` only (#5100 WP05 T022). Ignored for every
            other topology.
        frozen: The membership started work packages impose (#5573), passed
            to :func:`~specify_cli.lanes.compute.compute_lanes` and re-checked
            by :func:`~specify_cli.lanes.frozen_membership.assert_frozen_membership_honoured`
            just before ``lanes.json`` is written (defence in depth). ``None``
            keeps the historical behaviour.

    Returns:
        A ``(lanes_path, lanes_manifest)`` tuple.

    Raises:
        LaneGlobValidationError: a literal-path ``owned_files`` entry
            matches zero files in the repository. No ``lanes.json`` is
            written.
        TypeError: *topology* is not a :class:`MissionTopology` member.
        TopologyManifestMismatch: the mission is stamped ``SINGLE_BRANCH``
            but its EXISTING on-disk ``lanes.json`` (the manifest this call
            is about to overwrite) already has a code lane -- Invariant T-1
            (data-model.md), never re-stamped after #5100. No ``lanes.json``
            write happens; the pre-existing manifest on disk is left
            untouched (contracts/single-branch-execution.md, "Finalize").
        LaneMembershipFrozenError: *frozen* cannot be honoured (a started work
            package would change lane). No ``lanes.json`` is written; the
            pre-existing manifest on disk is left byte-identical.
    """
    if not isinstance(topology, MissionTopology):
        raise TypeError(f"compute_and_write_lanes: topology must be a MissionTopology, got {type(topology)!r}")
    create_intent = {wp_id: list(fm.create_intent) for wp_id, fm in wp_frontmatters.items() if fm.create_intent}
    glob_result = validate_glob_matches(wp_manifests, repo_root, create_intent=create_intent)
    if not glob_result.passed:
        raise LaneGlobValidationError(glob_result)

    # WP10 integration (C-4 / #4945): read back any prior ``lanes.json`` so
    # ``compute_lanes`` reuses each WP-group's already-assigned stable lane id
    # instead of re-minting positional ids on a re-finalize (a WP removal must
    # not re-letter a surviving lane's branch out from under its persisted git
    # branch). A first finalize (no prior manifest) passes ``None`` and mints
    # fresh positional ids exactly as before.
    previous_lanes = read_lanes_json(planning_dir)
    try:
        lanes_manifest = compute_lanes(
            dependency_graph=wp_dependencies,
            ownership_manifests=wp_manifests,
            mission_slug=mission_slug,
            target_branch=target_branch,
            wp_bodies=wp_bodies,
            mission_id=mission_id,
            previous_lanes=previous_lanes,
            topology=topology,
            mission_branch=mission_branch,
            frozen=frozen,
        )
    except InvalidMissionIdentity as exc:
        # U1: ``compute_lanes`` (untouched) composes the Mission branch via
        # ``mission_branch_name(..., mission_id=mission_id)``, which raises the
        # typed ``InvalidMissionIdentity`` at the source (``_mid8``) when
        # ``mission_id`` is present but shorter than 8 characters. Preserve
        # this module's own ``LaneComputationError`` contract (callers/tests
        # expect it here — no lanes.json may be written on this failure), but
        # reuse the source error's own correctly-worded remedy rather than
        # inventing a second, potentially-wrong one at this call site.
        raise LaneComputationError(f"cannot compute lanes for mission {mission_slug!r}: {exc.next_step}") from exc

    # #5100 IC-02 / WP05 (T022, writer chokepoint promised by WP03's own
    # docstring above): fail closed BEFORE overwriting an existing on-disk
    # manifest that still has a code lane under a SINGLE_BRANCH stamp -- the
    # #5100 write-path defect the re-stamp migration exists to repair.
    # Checked against ``previous_lanes`` (the manifest ABOUT TO BE
    # OVERWRITTEN), never the freshly-computed ``lanes_manifest`` above: for
    # SINGLE_BRANCH the freshly-computed manifest is ALWAYS the one
    # repo-root lane (T022), so checking it would never catch the drift this
    # guard exists for. ``previous_lanes is None`` (a first finalize, or a
    # caller-level "never rewrite existing lanes" guard already returned
    # before reaching here) has nothing on disk to guard.
    if previous_lanes is not None:
        assert_topology_matches_manifest(
            topology,
            has_code_lanes=has_code_lanes(previous_lanes),
            mission_slug=mission_slug,
        )

    # #5573 writer chokepoint (defence in depth): ``compute_lanes`` already
    # honours ``frozen``; re-check before anything is written.
    assert_frozen_membership_honoured(lanes_manifest, frozen, topology=topology)

    # FR-011 / PD-6 / PD-13: a re-finalize must not recompose the Mission
    # branch from a since-backfilled identity -- the first finalize's recorded
    # branch is what lane creation already created on disk (research Part A
    # §4). ``compute_lanes`` itself stays untouched (Complexity Tracking).
    lanes_manifest.mission_branch = _preserved_mission_branch(previous_lanes, lanes_manifest.mission_branch, topology=topology)
    lanes_manifest.planning_commit_sha = planning_commit_sha
    lanes_path = write_lanes_json(planning_dir, lanes_manifest)
    return lanes_path, lanes_manifest
