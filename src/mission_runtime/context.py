"""Execution-state context objects (canonical surface, internal module).

This is an **internal** submodule of the :mod:`mission_runtime` umbrella. It is
import-forbidden from outside the package — consumers use the symbols re-exported
from :mod:`mission_runtime` only (see ADR 2026-06-07-1 and
``tests/architectural/test_mission_runtime_surface.py``).

WP03 grows the hardened context value object into the **doc-09 fragment /
op-composite** model
(``docs/plans/engineering-notes/runtime_and_state_overhaul/09-context-decomposition-model.md``).
``MissionExecutionContext`` is NOT a flat field bag: it is a deep module whose
hidden structure is a set of cohesive, domain-owned **value-object fragments**
(Identity, BranchRef, Workspace, StatusSurface, ArtifactPlacement, PromptSource).
An *operation* assembles only the fragments it needs (the op-composite); the
builder lives in :mod:`mission_runtime.resolution` (doc-09 §5 layer law).

Strangler compatibility (C-004 / NFR-001): the historical flat
:class:`MissionExecutionContext` substrate fields
(``feature_dir`` / ``target_branch`` / ``workspace_path`` / ``branch_name`` /
``execution_mode`` / ``mission_slug``) are preserved verbatim so consumers that
have not yet been converted keep reading the same attributes. The fragments are
*attached* to the same object; nothing is removed. The historical
``ActionContext`` alias of :class:`MissionExecutionContext` was retired once its
last consumer was gone (mission dead-port-disposition-01M1TZVN, FR-014).

Single-derivation invariants (T009 / FR-012 / C-CTX-3): ``mid8`` is derived
**exactly once** (in :class:`IdentityFragment`, as ``mission_id[:8]``) and
``target_branch`` is resolved **exactly once** (carried on
:class:`BranchRefFragment`); no other call site recomputes either value.
"""
from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from mission_runtime.artifacts import MissionArtifactKind


class MissionTopology(enum.Enum):
    """The four mission shapes of the orthogonal coordination × lanes grid.

    Names the 2×2 cross-product as ONE stored value (#2069). FLATTENED is NOT a
    member: it is a historical/metadata provenance flag, never a shape value — a
    mission that was COORD and had its coordination_branch dropped is now
    SINGLE_BRANCH/LANES + a `flattened` provenance mark (see spec Domain Language).
    """

    SINGLE_BRANCH = "single_branch"        # no coord, no lanes
    LANES = "lanes"                        # no coord, lanes
    COORD = "coord"                        # coord, no lanes
    LANES_WITH_COORD = "lanes_with_coord"  # coord, lanes


def classify_topology(
    coordination_branch: str | None,
    has_lanes: bool,
) -> MissionTopology:
    """Map the two orthogonal mission signals to one topology cell (FR-001).

    The SINGLE authority that derives a :class:`MissionTopology` from
    ``(coordination_branch, has_lanes)``. WP02/WP03/WP04 consume this — they do
    not re-implement the 2×2 grid. ``FLATTENED`` is never returned: a flattened
    mission classifies as SINGLE_BRANCH/LANES + a separate ``flattened``
    provenance flag. This is distinct from
    :func:`routes_through_coordination` (whole-mission shape vs per-ref routing).
    """
    has_coord = coordination_branch is not None
    if has_coord and has_lanes:
        return MissionTopology.LANES_WITH_COORD
    if has_coord:
        return MissionTopology.COORD
    if has_lanes:
        return MissionTopology.LANES
    return MissionTopology.SINGLE_BRANCH


@dataclass(frozen=True)
class CommitTarget:
    """The ONE ref that artifacts + status events resolve to (ADR-2026-06-03-2).

    A ref-only carrier (C-007): it names the single ``destination_ref`` that
    planning artifacts AND status events resolve to (the FR-004 invariant). The
    per-ref topology classification it once carried (a retired ``kind`` field) is
    no longer here — the coord-routing decision is made from the stored
    :class:`MissionTopology` via the single :func:`routes_through_coordination`
    predicate, never re-derived from a ref-local enum (FR-001b / FR-005).
    """

    ref: str


# The ONE coord-routing topology set (FR-005 / S1192). COORD and LANES_WITH_COORD
# route through a distinct coordination ref; the two coord-less cells
# (SINGLE_BRANCH / LANES) have no primary↔coordination split (C-001). This is the
# SINGLE definition: ``resolution.py`` / ``surface_resolver.py`` /
# ``runtime_bridge.py`` / ``status_transition.py`` import it rather than restating
# the literal ``{COORD, LANES_WITH_COORD}`` set.
_COORD_ROUTING_TOPOLOGIES: frozenset[MissionTopology] = frozenset(
    {MissionTopology.COORD, MissionTopology.LANES_WITH_COORD}
)


def is_single_branch(topology: MissionTopology | None) -> bool:
    """The SINGLE owned-placement topology predicate (#3862 item A).

    The ONE predicate every ``single_branch`` invariant check flows through —
    the owned-placement arms of ``mission_context_for`` /
    ``resolve_placement_only`` / ``resolve_artifact_surface`` and the owned
    checkout preflight (``specify_cli.core.owned_mission``) dispose against
    this enum member rather than restating a raw ``"single_branch"`` meta
    string or a second enum comparison, so the string and enum
    representations cannot drift apart. A ``None`` (absent / malformed /
    degraded) stored-topology read is refused — fail-closed, the same
    refusal the owned preflight has always applied to a missing value.

    Distinct from :func:`routes_through_coordination` (the coord-routing
    half of the same grid): this names the owned-placement eligibility of
    the coord-less, lane-less cell only.
    """
    return topology is MissionTopology.SINGLE_BRANCH


def routes_through_coordination(topology: MissionTopology) -> bool:
    """The SINGLE routing predicate: does this topology route through coordination? (FR-005).

    The ONE predicate every coord-routing decision flows through, over the ONE
    canonical :data:`_COORD_ROUTING_TOPOLOGIES` set: ``True`` iff the stored shape
    is ``COORD`` / ``LANES_WITH_COORD``. Every owned call site
    (``_topology_uses_coord_surface``, ``_mission_routes_through_coordination``,
    ``_read_contract_routes_through_coordination``, the runtime-bridge audit site)
    disposes against this predicate over the stored topology — no module restates
    the 2×2 routing subset, and no per-ref enum is consulted (the retired
    transitional arm, FR-001b).

    Distinct from :func:`classify_topology`, which names the whole-mission shape
    from ``(coordination_branch, has_lanes)``.
    """
    return topology in _COORD_ROUTING_TOPOLOGIES


@dataclass(frozen=True)
class IdentityFragment:
    """F0 — the canonical mission identity every other fragment keys on.

    ``mid8`` is the **single derivation point** for the 8-char branch/worktree
    disambiguator: it is computed as ``mission_id[:8]`` here and nowhere else
    (FR-012 / C-CTX-3). The ``__post_init__`` invariant guards against a caller
    constructing an inconsistent fragment.
    """

    mission_id: str
    mid8: str
    mission_slug: str

    def __post_init__(self) -> None:
        expected = self.mission_id[:8]
        if self.mid8 != expected:
            raise ValueError(
                "IdentityFragment.mid8 must be mission_id[:8] "
                f"(got mid8={self.mid8!r}, mission_id={self.mission_id!r}); "
                "mid8 is single-derived (FR-012 / C-CTX-3)."
            )

    @classmethod
    def derive(cls, *, mission_id: str, mission_slug: str) -> IdentityFragment:
        """Construct the fragment, deriving ``mid8`` once from ``mission_id``."""
        return cls(
            mission_id=mission_id,
            mid8=mission_id[:8],
            mission_slug=mission_slug,
        )


@dataclass(frozen=True)
class BranchRefFragment:
    """F3 — version-control scape: the branch/ref fields for a mission.

    ``target_branch`` is the **single resolution source** (FR-012): it is
    resolved once by the builder and carried here; no surface re-derives it from
    ``meta.json`` or git independently. ``coordination_branch`` is ``None`` under
    flattened topology (C-001). ``destination_ref`` is the ONE
    :class:`CommitTarget` artifacts + status resolve to.
    """

    target_branch: str
    coordination_branch: str | None
    destination_ref: CommitTarget


@dataclass(frozen=True)
class WorkspaceFragment:
    """F2 — filesystem layout: the path fields for a mission/operation.

    ``primary_root`` is the **canonical** main-checkout root (IC-04): it is
    resolved via the single worktree-pointer parser so consumers never trust a
    lane-supplied root for coord topology (WP02 reviewer carry-forward).
    ``current_cwd`` is where the command is actually running; the two differ
    whenever the operator sits in a lane worktree.
    """

    primary_root: Path
    current_cwd: Path
    coord_worktree: Path | None
    execution_workspace: Path | None
    allowed_command_cwd: Path


@dataclass(frozen=True)
class StatusSurfaceFragment:
    """F5 (read locus) — where status events are read from / written to.

    Resolved by WP02's :func:`resolve_status_surface` (IC-01) and **carried** on
    the context — consumers (esp. ``status_transition._identity_for_request``)
    must NOT re-derive it (FR-003/FR-008/#1737). Under flattened topology
    ``status_read_dir == status_write_dir``.
    """

    status_read_dir: Path
    status_write_dir: Path


@dataclass(frozen=True)
class ArtifactPlacementFragment:
    """Where planning artifacts (spec/plan/tasks/analysis) commit (IC-05).

    ``placement_ref`` is the same :class:`CommitTarget` that status events
    resolve to (C-PLACE-1): one artifact-placement ref, no independent
    primary/coord logic.
    """

    placement_ref: CommitTarget


@dataclass(frozen=True)
class MissionArtifactContext:
    """Resolved context for one mission artifact kind."""

    kind: MissionArtifactKind
    read_dir: Path
    write_dir: Path
    commit_target: CommitTarget | None


@dataclass(frozen=True)
class MissionContext:
    """Mission-level artifact read context.

    Callers ask for an artifact kind; the context returns a value object with
    read/write/commit placement and hides worktree/naming details.
    """

    mission_slug: str
    mission_type: str
    topology: MissionTopology
    artifacts: Sequence[MissionArtifactContext]

    def artifact(self, kind: MissionArtifactKind) -> MissionArtifactContext:
        """Return resolved context for ``kind``."""
        for artifact in self.artifacts:
            if artifact.kind is kind:
                return artifact
        raise ValueError(f"Unhandled mission artifact kind: {kind!r}")


@dataclass(frozen=True)
class MissionExecutionContext:
    """Fully-resolved context for a single action — a doc-09 op-composite.

    The canonical surface is expressed over **this object**, never over loose
    path fragments: consumers receive a resolved context and never reconstruct
    the mission-spec directory from ``main_repo_root`` + the specs dir name +
    ``mission_slug`` themselves (FR-009).

    **Immutable post-build (C-IC01 / FR-009 / D-2).** The composite is a frozen
    dataclass: it is constructed once — through the package-private factory
    :func:`mission_runtime.resolution.build_execution_context` — and never
    mutated afterwards. Assigning any field on a built context raises. This
    forecloses the historical split-brain where the WP-bearing fields were
    patched onto an already-emitted context (``resolution.py`` post-build
    mutator); the factory now assembles every field in one shot.

    The flat fields below are the historical substrate (NFR-001 / C-004): they
    are preserved so every existing consumer continues to read the same
    attributes while the Strangler conversion proceeds. The doc-09 **fragments**
    (``identity`` / ``branch_ref`` / ``workspace`` / ``status_surface`` /
    ``artifact_placement``) are *attached* by the builder
    (:func:`mission_runtime.resolution.build_execution_context`); each operation
    assembles only the fragments it needs (op-composite). A fragment is ``None``
    only when the operation does not consume it.

    **Write-projection boundary contract (D-6, declared here + on the factory).**
    Write surfaces compose names/paths/identity from a factory-projected
    :class:`IdentityFragment` + :class:`BranchRefFragment` (+ workspace/surface);
    they **MUST NOT** re-derive ``mission_id`` / ``mid8`` / ``primary_root``
    independently. ``branch_naming`` is the grammar collaborator; the factory is
    the identity/topology authority that feeds it. The deferred write-side
    (#1716 / #1878, Mission B) adopts against this frozen seam — not a rewrite.
    """

    action: str
    mission_slug: str
    feature_dir: str
    target_branch: str
    detection_method: str
    wp_id: str | None = None
    wp_file: str | None = None
    lane: str | None = None
    lane_id: str | None = None
    branch_name: str | None = None
    execution_mode: str | None = None
    resolution_kind: str | None = None
    dependencies: list[str] = field(default_factory=list)
    resolved_base: str | None = None
    auto_merge: bool = False
    workspace_path: str | None = None
    commands: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # doc-09 fragments (op-composite). Attached by the builder; ``None`` when the
    # operation does not consume the fragment. Excluded from ``to_dict`` so the
    # historical serialized shape (NFR-001) is byte-for-byte preserved.
    identity: IdentityFragment | None = field(default=None)
    branch_ref: BranchRefFragment | None = field(default=None)
    workspace: WorkspaceFragment | None = field(default=None)
    status_surface: StatusSurfaceFragment | None = field(default=None)
    artifact_placement: ArtifactPlacementFragment | None = field(default=None)

    _FRAGMENT_FIELDS: ClassVar[tuple[str, ...]] = (
        "identity",
        "branch_ref",
        "workspace",
        "status_surface",
        "artifact_placement",
    )

    def to_dict(self) -> dict[str, Any]:
        """Return the historical flat-substrate mapping.

        The doc-09 fragments are intentionally excluded so the serialized shape
        is identical to the pre-fragment context (NFR-001) — fragments are an
        in-process composition concern, not a wire-format change. ``asdict`` is
        retained (rather than a shallow ``getattr`` copy) so the deep-copy
        semantics of the historical implementation are preserved for the
        substrate collections (``dependencies`` / ``commands`` / ``warnings``).
        """
        data = asdict(self)
        for fragment_field in self._FRAGMENT_FIELDS:
            data.pop(fragment_field, None)
        return data


__all__ = [
    "ArtifactPlacementFragment",
    "BranchRefFragment",
    "CommitTarget",
    "IdentityFragment",
    "MissionArtifactContext",
    "MissionContext",
    "MissionExecutionContext",
    "MissionTopology",
    "StatusSurfaceFragment",
    "WorkspaceFragment",
    "classify_topology",
    "routes_through_coordination",
]
