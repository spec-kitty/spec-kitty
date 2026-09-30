"""Shared preflight for explicitly selected, single-branch mission checkouts.

``resolve_owned_mission`` is the SOLE minter of :class:`mission_runtime.OwnedCheckout`
(gate G3, ``contracts/owned-checkout-carrier.md`` §1). Every owned command
threads its result down instead of re-validating (NFR-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from mission_runtime import (
    ActionContextError,
    MissionTopology,
    OwnedCheckout,
    OwnedRefusalCode,
    routes_through_coordination,
    single_branch_write_ref,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.paths import assert_safe_path_segment, get_status_read_root, load_meta_fail_closed
from specify_cli.core.utils import ensure_within_directory
from specify_cli.git.commit_helpers import _staged_tree_is_empty
from specify_cli.git.protection_policy import ProtectionPolicy

if TYPE_CHECKING:
    # Type-only: keeps the cold-import boundary (#1461) intact -- these two
    # modules are pulled at runtime only inside the function-local imports
    # below, never at module scope.
    from specify_cli.context.mission_resolver import ResolvedMission
    from specify_cli.core.checkout_ownership import OwnershipClaim

# Two pre-existing wire codes this module raises that predate WP01's
# OwnedRefusalCode registry and are NOT part of it (orchestrator decision,
# review cycle 1): values are unchanged (logs_telemetry: do_not_change), each
# defined exactly once here and used at every site instead of repeating the
# literal (Sonar S1192).
# Exported (WP08 review follow-up 2) so ``_owned_checkout.emit_owned_refusal``
# validates against these same module constants instead of repeating either
# string as a fresh literal.
FEATURE_CONTEXT_UNRESOLVED: Final = "FEATURE_CONTEXT_UNRESOLVED"  # pre-existing wire code; not part of OwnedRefusalCode
MISSION_CONTEXT_CONFLICT: Final = "MISSION_CONTEXT_CONFLICT"  # pre-existing wire code; not part of OwnedRefusalCode
# Private aliases so every existing in-module reference below stays a simple
# rename to the now-public constants above, not a second definition.
_FEATURE_CONTEXT_UNRESOLVED = FEATURE_CONTEXT_UNRESOLVED
_MISSION_CONTEXT_CONFLICT = MISSION_CONTEXT_CONFLICT

# owned-checkout-lifecycle-authority WP02 (FR-023, research R-02): the two
# allowed-topology sets a call site chooses from. LANES is deliberately absent
# from LIFECYCLE_OWNED_TOPOLOGIES (today's lifecycle commands only support
# single_branch) but present in NEXT_OWNED_TOPOLOGIES, because today's
# `next --owned-checkout` applies no topology check at all and must keep
# accepting a plain lanes-without-coordination owned mission.
LIFECYCLE_OWNED_TOPOLOGIES: Final[frozenset[MissionTopology]] = frozenset({MissionTopology.SINGLE_BRANCH})
NEXT_OWNED_TOPOLOGIES: Final[frozenset[MissionTopology]] = frozenset(
    {
        MissionTopology.SINGLE_BRANCH,
        MissionTopology.LANES,
        MissionTopology.LANES_WITH_COORD,
        MissionTopology.COORD,
    }
)

_REPOSITORY_ROOT_REFUSAL = "--owned-checkout names the repository root checkout; pass a linked owned checkout instead."
_MISSION_WORKTREE_REFUSAL = (
    "--owned-checkout names a worktree already registered to this mission (coordination worktree or lane worktree); pass a linked owned checkout instead."
)


def _stored_topology(meta: dict[str, Any] | None) -> MissionTopology | None:
    """Parse the stored ``topology`` meta value to the enum; anything else is ``None``.

    Delegates to :meth:`mission_runtime.MissionTopology.from_stored`, the ONE
    stored-value parser shared with ``stored_topology`` and
    ``stored_topology_from_meta``.

    The enum-based front half of the owned single_branch refusal (#3862 item A):
    a missing/corrupt meta (``None``), an absent key, a non-string value, or an
    unknown string all degrade to ``None`` here, which the shared
    :func:`mission_runtime.is_single_branch` predicate refuses — the exact
    outcomes the previous raw ``meta.get("topology") != "single_branch"``
    string comparison produced, now expressed against the ONE
    :class:`mission_runtime.MissionTopology` enum the placement arms use, so
    the two representations cannot drift.
    """
    return MissionTopology.from_stored(meta.get("topology") if meta is not None else None)


def expected_write_branch(meta: dict[str, Any] | None) -> str:
    """The branch a single_branch mission's write checkout must be on (WP08).

    Routes through :func:`mission_runtime.single_branch_write_ref` -- the ONE
    write-branch rule: ``meta["mission_branch"]`` when the mission's STORED
    topology is ``single_branch`` and the field is recorded (the #5100
    protected-target mint at ``mission create`` -- FR-007/012), otherwise the
    mission's ``target_branch`` (``""`` when meta carries none). It is
    deliberately not a function of the protection policy: ``mission_branch``
    is already the create-time-authoritative record of that decision
    (mint-once, read-many; a later protection-config change must never move
    an already-created mission's write branch -- spec.md "Protection config
    changes after create").
    """
    data = meta or {}
    target = data.get("target_branch")
    return single_branch_write_ref(_stored_topology(meta), data.get("mission_branch"), str(target) if isinstance(target, str) and target else "")


def _require_allowed_topology(
    meta: dict[str, Any] | None,
    topology: MissionTopology | None,
    allowed_topologies: frozenset[MissionTopology],
) -> None:
    """Refuse a mission whose stored topology is outside the caller's allowed set."""
    if meta is None or topology is None:
        raise ActionContextError(
            OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED,
            "--owned-checkout could not determine the mission's stored topology.",
        )
    if topology not in allowed_topologies:
        allowed_names = ", ".join(sorted(t.value for t in allowed_topologies))
        raise ActionContextError(
            OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED,
            f"--owned-checkout requires one of: {allowed_names} (mission is {topology.value}).",
        )
    # The coordination_branch refusal applies only when the allowed set
    # contains no coordination-routing topology: an allowed set that already
    # includes COORD/LANES_WITH_COORD is trusted to accept coordination.
    allows_coordination = any(routes_through_coordination(t) for t in allowed_topologies)
    if not allows_coordination and meta.get("coordination_branch"):
        raise ActionContextError(
            OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED,
            "--owned-checkout currently requires a mission with no coordination_branch.",
        )


def _require_owned_claim(repository_root: Path, checkout: Path) -> OwnershipClaim:
    """Validate the checkout-ownership claim; refuse the repository root itself."""
    from specify_cli.core.checkout_ownership import (
        OWNED_CHECKOUT_IS_REPOSITORY_ROOT,
        claims_repository_root,
        error_for_claim,
        resolve_ownership_claim,
    )

    claim = resolve_ownership_claim(checkout, resolved_primary=repository_root)
    error = error_for_claim(claim)
    if error is not None:
        raise ActionContextError(error.error_code, str(error))
    if claims_repository_root(claim):
        raise ActionContextError(OWNED_CHECKOUT_IS_REPOSITORY_ROOT, _REPOSITORY_ROOT_REFUSAL)
    return claim


def _is_coordination_worktree(checkout: Path, repository_root: Path) -> bool:
    """True when ``checkout`` is a registered coordination worktree of ``repository_root``.

    Fails CLOSED (review cycle 1): an unreadable git worktree registry
    (:class:`WorktreeRegistryUnavailable`) is NOT swallowed into ``False``
    here -- that would read as "not coordination" and move toward adoption,
    the opposite of the T009 edge case ("fail closed toward today's
    behaviour, never toward adoption"). It propagates to the caller, which
    decides what "closed" means for its own contract: ``adopt_owned_checkout``
    catches it and returns ``None`` (refuse adoption); the explicit path in
    :func:`_require_not_mission_worktree` lets it propagate as a typed
    refusal (see there).
    """
    from specify_cli.coordination.surface_resolver import (
        WorktreeTopology,
        classify_worktree_topology,
    )

    return classify_worktree_topology(checkout, repo_root=repository_root) is WorktreeTopology.COORD_WORKTREE


def _is_lane_worktree_of_mission(checkout: Path, repository_root: Path, directory: Path) -> bool:
    """True when ``checkout`` is a worktree named in the mission's ``lanes.json``.

    Deliberately does NOT use :class:`WorktreeTopology.LANE_WORKTREE` as the
    test: that classification means "registered and not coordination", so a
    valid owned checkout placed under ``repository_root/.worktrees/`` also
    classifies as ``LANE_WORKTREE`` (the carrier-contract trap, plan §IC-01).
    Instead, resolve every lane's predicted path through the canonical naming
    seam and compare.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    try:
        manifest = read_lanes_json(directory)
    except CorruptLanesError:
        return False
    if manifest is None:
        return False
    resolved_checkout = checkout.resolve()
    for lane in manifest.lanes:
        # #5100: a repo-root lane has no worktree of its own (it runs in the
        # write checkout), so it can never name a lane worktree to refuse.
        if is_repo_root_lane(lane):
            continue
        lane_path, _branch = predict_lane_worktree(repository_root, directory.name, lane.lane_id)
        if lane_path.resolve() == resolved_checkout:
            return True
    return False


def _require_not_mission_worktree(checkout: Path, repository_root: Path, directory: Path | None) -> None:
    """Refuse an explicit ``--owned-checkout`` naming a registered mission worktree.

    A coordination worktree or a lane worktree already registered to the
    mission being resolved is refused with a typed code (data-model.md
    §Validator). Adoption (:func:`adopt_owned_checkout`) reuses the same two
    predicates but returns ``None`` for the same checkouts instead of raising.
    ``directory`` may be ``None`` when the mission handle could not be
    resolved against the repository root yet (the coordination-worktree leg
    of the check does not need it).

    An unreadable worktree registry (:class:`WorktreeRegistryUnavailable`,
    propagated by :func:`_is_coordination_worktree` -- review cycle 1's
    fail-closed fix) is translated to a typed refusal here, carrying that
    exception's own ``error_code``, so this public entry point's contract
    (``ActionContextError`` only) holds even when the registry read fails.
    """
    from specify_cli.core.checkout_ownership import OWNED_CHECKOUT_IS_MISSION_WORKTREE
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    try:
        is_coord = _is_coordination_worktree(checkout, repository_root)
    except WorktreeRegistryUnavailable as exc:
        raise ActionContextError(exc.error_code, str(exc)) from exc
    is_lane = directory is not None and _is_lane_worktree_of_mission(checkout, repository_root, directory)
    if is_coord or is_lane:
        raise ActionContextError(OWNED_CHECKOUT_IS_MISSION_WORKTREE, _MISSION_WORKTREE_REFUSAL)


def _resolve_mission_dir_best_effort(root: Path, handle: str | None) -> Path | None:
    """Resolve ``handle`` against ``root`` without raising; ``None`` on any miss.

    Used only to locate the mission's ``lanes.json`` for the
    ``OWNED_CHECKOUT_IS_MISSION_WORKTREE`` check, which must run before the
    checkout's own mission data is read (T009 step 3a).
    """
    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )

    if not handle or not handle.strip():
        return None
    try:
        resolved_dir: Path = resolve_mission(handle, root).feature_dir.resolve()
    except (MissionNotFoundError, AmbiguousHandleError):
        return None
    return resolved_dir


def _branch_matches_target(current: str | None, write_branch: str, target_override: str | None = None, *, target: str | None = None) -> bool:
    """The minter's branch rule: attached HEAD, non-empty write branch, ``current == write_branch`` (and any override agrees).

    Shared by :func:`_require_write_branch` and the cheap pre-filter
    of :func:`invoking_checkout_would_adopt`, so the rule has one definition.
    ``write_branch`` is :func:`expected_write_branch` -- the #5100 minted
    ``mission_branch`` for a protected-target single_branch mission, else the
    ``target_branch``. ``target_override`` still validates against the
    mission's real ``target`` (defaulting to ``write_branch``): it names which
    TARGET the caller expects, not which branch the write checkout sits on.
    """
    expected_target = write_branch if target is None else target
    return current is not None and bool(write_branch) and current == write_branch and (target_override is None or target_override == expected_target)


def _require_write_branch(root: Path, meta: dict[str, Any], target_override: str | None) -> str:
    """Refuse a branch mismatch or detached HEAD; return the write branch.

    WP08 (#5100 FR-007/012): the branch the checkout must actually be ON --
    and the one the fact carries as ``write_branch``, so every owned write
    arm lands there -- is ``mission_branch`` for a protected-target mint, else
    ``target_branch`` unchanged (:func:`expected_write_branch`).
    """
    current = get_current_branch(root)
    target = str(meta.get("target_branch") or "")
    expected = expected_write_branch(meta)
    if not _branch_matches_target(current, expected, target_override, target=target):
        raise ActionContextError(
            OwnedRefusalCode.OWNED_BRANCH_REFUSED,
            f"The current branch ({current!r}) must match the mission's expected write branch ({expected!r}); detached HEAD is unsupported.",
        )
    return expected


def _require_unprotected_write_branch(fact: OwnedCheckout) -> None:
    """Refuse a protected write branch (#5100 FR-008 mission-scoped ``commit_to_target``).

    Decided by the ONE owned protection authority,
    :meth:`ProtectionPolicy.resolve_for_owned`, over the just-minted fact --
    the same fold every later owned write uses, so the minter can never admit
    a mission its own writes would refuse (or vice versa).
    """
    if ProtectionPolicy.resolve_for_owned(fact).is_protected(fact.write_branch):
        raise ActionContextError(OwnedRefusalCode.OWNED_BRANCH_REFUSED, f"Protected destination refused: {fact.write_branch}")


def _resolve_owned_directory(root: Path, handle: str | None) -> tuple[ResolvedMission, Path]:
    """Resolve the mission handle against ``root`` and validate the mission-dir bound."""
    # Imported lazily: mission_resolver pulls the status orchestration + workspace
    # packages at module scope. owned_mission is cold-imported by task_utils.support
    # (~37 CLI command modules), so module-level imports here break the
    # status-free cold-import boundary (#1461). They are used only in this function.
    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )

    if not handle or not handle.strip():
        raise ActionContextError(_FEATURE_CONTEXT_UNRESOLVED, "--owned-checkout requires an explicit --mission.")
    try:
        mission = resolve_mission(handle, root)
    except (MissionNotFoundError, AmbiguousHandleError) as exc:
        raise ActionContextError(_FEATURE_CONTEXT_UNRESOLVED, str(exc)) from exc
    directory = mission.feature_dir.resolve()
    try:
        ensure_within_directory(directory, root / "kitty-specs")
    except ValueError as exc:
        raise ActionContextError(OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED, "Mission directory escapes the selected checkout.") from exc
    return mission, directory


class OwnedMissionSelectionRequired(Exception):
    """A handle-less ``discover_sole`` resolution found zero or several missions in the claimed checkout.

    Deliberately NOT an :class:`ActionContextError`: it is the discovery signal
    (``listings`` is empty for zero, two or more for several), rendered by the
    caller as the existing missing-handle listing / nudge, not an ownership refusal.
    """

    def __init__(self, listings: list[Any]) -> None:
        self.listings = listings
        super().__init__("mission selection required")


def _discover_sole_handle(claimed_checkout: Path) -> str:
    """The sole mission's slug inside the CLAIMED checkout (called only after the claim check)."""
    from specify_cli.context.mission_resolver import list_missions_for_selection

    listings = list_missions_for_selection(claimed_checkout)
    if len(listings) == 1:
        sole_slug: str = listings[0].mission_slug
        return sole_slug
    raise OwnedMissionSelectionRequired(listings)


def resolve_owned_mission(
    repository_root: Path,
    checkout: Path,
    handle: str | None,
    *,
    target_override: str | None = None,
    allowed_topologies: frozenset[MissionTopology] = LIFECYCLE_OWNED_TOPOLOGIES,
    discover_sole: bool = False,
) -> OwnedCheckout:
    """Validate ownership before reading mission data; never fall back to the repository root.

    The SOLE minter of :class:`mission_runtime.OwnedCheckout` (gate G3). The
    topology decision is by the caller's ``allowed_topologies`` set
    (FR-023, research R-02) instead of a hardcoded single_branch check.

    ``discover_sole`` (handle-less ``next --owned-checkout``): when ``handle`` is
    blank, the sole mission is discovered INSIDE the claimed checkout, strictly
    after the one claim check (never listing an unvalidated checkout), so the
    whole resolution still validates ownership exactly once. Zero or several
    missions raise :class:`OwnedMissionSelectionRequired`.
    """
    claim = _require_owned_claim(repository_root, checkout)
    root = claim.claimed_checkout
    if discover_sole and not (handle and handle.strip()):
        # Listing P precedes ``_require_not_mission_worktree`` on purpose: that check needs the
        # mission's dir (to find its lanes.json), which a handle-less call only knows once the
        # sole mission is discovered. The claim is already validated (the ONE claim check above),
        # the listing is a read of the claimed checkout only, and a coordination/lane worktree of
        # the mission is still refused right after, before any mission data is read.
        handle = _discover_sole_handle(root)
    _require_not_mission_worktree(checkout, repository_root, _resolve_mission_dir_best_effort(repository_root, handle))
    mission, directory = _resolve_owned_directory(root, handle)
    meta = load_meta_fail_closed(directory)
    topology = _stored_topology(meta)
    _require_allowed_topology(meta, topology, allowed_topologies)
    assert meta is not None and topology is not None  # narrowed by _require_allowed_topology
    write_branch = _require_write_branch(root, meta, target_override)
    result = OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=root,
        mission_dir=directory,
        mission_slug=mission.feature_dir.name,
        topology=topology,
        write_branch=write_branch,
    )
    _require_unprotected_write_branch(result)
    # #3866: the resolve-time validation is a bounded top-level tripwire, not a
    # full-tree scan. ``directory.rglob("*")`` stat'd every entry of the mission
    # tree on every resolve (~8 call sites, several calls per command) — an
    # O(tree) latency cliff whose only unique value was catching a symlink
    # escape before write time; ``OwnedCheckout.files`` re-validates the actual
    # written paths at write time anyway, so a nested symlink escape is still
    # refused there. Validating the top level keeps the boundary tripwire (a
    # symlinked mission-root entry escaping the checkout is refused at resolve,
    # before any effects) at O(top-level entries) instead of O(tree).
    result.files(list(directory.iterdir()))
    return result


@dataclass(frozen=True)
class OwnedCreateRoot:
    """The validated owned root for ``agent mission create --owned-checkout`` (data-model.md).

    Construction goes only through :func:`resolve_owned_create_root`; field
    names avoid the G5-banned ``owned_root`` / ``owned_checkout`` /
    ``checkout_root`` names typed ``Path`` outside ``mission_runtime.OwnedCheckout``
    (``contracts/architectural-gate.md``).
    """

    repository_root: Path
    checkout: Path
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _CREATE_ROOT_TOKEN:
            raise TypeError("OwnedCreateRoot is minted only by specify_cli.core.owned_mission.resolve_owned_create_root")
        object.__setattr__(self, "repository_root", self.repository_root.resolve())
        object.__setattr__(self, "checkout", self.checkout.resolve())

    def bind_mission(self, mission_dir: Path) -> OwnedCreateMission:
        """Bind this validated create root to the mission directory the create scaffolds in it.

        ``mission_dir`` must be a direct child of this checkout's ``kitty-specs``
        (the create's own seam-composed directory); anything else is refused, so
        the bound fact can never point the mission-scoped protection fold at a
        directory outside the validated owned checkout.
        """
        resolved = mission_dir.resolve()
        if resolved.parent != self.checkout / KITTY_SPECS_DIR:
            raise ValueError(f"OwnedCreateMission invariant violated: {resolved} is not a mission directory of {self.checkout}")
        return OwnedCreateMission(repository_root=self.repository_root, checkout=self.checkout, mission_dir=resolved, _token=_CREATE_ROOT_TOKEN)


@dataclass(frozen=True)
class OwnedCreateMission:
    """An :class:`OwnedCreateRoot` bound to the mission directory its create scaffolds.

    The owned ``mission create`` counterpart of :class:`mission_runtime.OwnedCheckout`
    for the #5100 mission-scoped protection fold
    (:meth:`specify_cli.git.protection_policy.ProtectionPolicy.resolve_for_owned`):
    the mission does not exist when the create root is validated, so the fold
    cannot use a minted ``OwnedCheckout``; this carries the same three facts it
    needs. Constructed only through :meth:`OwnedCreateRoot.bind_mission`.
    """

    repository_root: Path
    checkout: Path
    mission_dir: Path
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._token is not _CREATE_ROOT_TOKEN:
            raise TypeError("OwnedCreateMission is bound only by OwnedCreateRoot.bind_mission")


_CREATE_ROOT_TOKEN = object()


def resolve_owned_create_root(repository_root: Path, checkout: Path) -> OwnedCreateRoot:
    """Validate a mission-create-time owned checkout, before the mission exists.

    No branch or topology check: the mission does not exist yet, and
    ``create`` keeps its own guards (``mission_creation.py``).
    """
    claim = _require_owned_claim(repository_root, checkout)
    return OwnedCreateRoot(repository_root=repository_root, checkout=claim.claimed_checkout, _token=_CREATE_ROOT_TOKEN)


def _candidate_checkout_root(cwd: Path) -> Path:
    """Return the toplevel checkout root the flagless adoption probe starts from."""
    return get_status_read_root(cwd).resolve()


def _mission_context_conflict_message(primary: ResolvedMission, caller: ResolvedMission) -> str:
    """Build the MISSION_CONTEXT_CONFLICT message text.

    ``specify_cli.missions.operation_context`` (the module that historically
    owned this text, via ``MissionSurfaceConflictError``) was deleted by
    WP08; the text is reproduced verbatim here instead of imported, so
    ``agent/context.py``'s ``except ActionContextError`` handler renders
    unchanged JSON output with the old exception class gone.
    """
    return (
        "Mission selector resolves to different identities in the primary "
        f"checkout ({primary.mission_slug}, {primary.mission_id}) and the "
        "caller-owned checkout "
        f"({caller.mission_slug}, {caller.mission_id}); refusing to guess."
    )


def _adoptable_toplevel(repository_root: Path, cwd: Path) -> Path | None:
    """The handle-independent front of adoption: the invoking checkout's toplevel, or ``None``.

    ``None`` when the toplevel cannot be read, is the repository root itself, is a
    registered coordination worktree, or the worktree registry is unreadable
    (fail toward today's behaviour, never toward adoption). ``repository_root``
    must already be resolved.
    """
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    try:
        toplevel = _candidate_checkout_root(cwd)
    except OSError:
        return None
    if toplevel == repository_root:
        return None
    try:
        if _is_coordination_worktree(toplevel, repository_root):
            return None
    except WorktreeRegistryUnavailable:
        return None
    return toplevel


def adopt_owned_checkout(
    repository_root: Path,
    cwd: Path,
    handle: str | None,
    *,
    allowed_topologies: frozenset[MissionTopology],
) -> OwnedCheckout | None:
    """Validated flagless adoption (FR-021): adopt only what the canonical validator accepts.

    Returns ``None`` whenever adoption does not apply (falls back to today's
    repository-root behaviour), and raises ``ActionContextError`` only for the
    mission-surface conflict case (US7-AS5).
    """
    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
        resolve_mission,
    )

    repository_root = repository_root.resolve()
    if not handle or not handle.strip():
        return None
    toplevel = _adoptable_toplevel(repository_root, cwd)
    if toplevel is None:
        return None

    try:
        toplevel_mission = resolve_mission(handle, toplevel)
    except (MissionNotFoundError, AmbiguousHandleError):
        # Mission absent from (or ambiguous at) toplevel: fall back to R.
        return None

    if _is_lane_worktree_of_mission(toplevel, repository_root, toplevel_mission.feature_dir.resolve()):
        return None

    try:
        primary_mission = resolve_mission(handle, repository_root)
    except (MissionNotFoundError, AmbiguousHandleError):
        primary_mission = None

    if primary_mission is not None and primary_mission.mission_id != toplevel_mission.mission_id:
        raise ActionContextError(
            _MISSION_CONTEXT_CONFLICT,
            _mission_context_conflict_message(primary_mission, toplevel_mission),
        )

    try:
        return resolve_owned_mission(repository_root, toplevel, handle, allowed_topologies=allowed_topologies)
    except ActionContextError:
        return None


def _target_branch_from_meta_file(mission_dir: Path) -> str:
    """Plain-read the expected write branch from ``meta.json`` (no git); ``""`` when absent or unreadable.

    Routes through the canonical silent-empty-dict reader
    (:func:`specify_cli.mission_metadata.load_meta_or_empty`) instead of a
    hand-rolled ``json.loads`` -- ``load_meta_or_empty`` already returns
    ``{}`` on a missing *or* malformed ``meta.json``, matching this
    function's historical ``""`` fallback exactly (inline-meta-read gate,
    ``tests/architectural/test_inline_meta_read_gate.py``). Then routes
    through :func:`expected_write_branch` so the pre-filter applies the SAME
    #5100 write-branch rule the minter does.
    """
    from specify_cli.mission_metadata import load_meta_or_empty

    data = load_meta_or_empty(mission_dir)
    return expected_write_branch(data) if isinstance(data, dict) else ""


def invoking_checkout_would_adopt(
    repository_root: Path,
    cwd: Path,
    *,
    allowed_topologies: frozenset[MissionTopology] = LIFECYCLE_OWNED_TOPOLOGIES,
) -> bool:
    """True when the checkout ``cwd`` sits in owns a mission, per :func:`adopt_owned_checkout` (single adoption authority).

    Declared out-of-map edit (owned-checkout-lifecycle-authority WP09, review
    cycles 3-4): lets a caller without a ``--mission`` handle ask the SAME
    question adoption answers. Adoption needs a handle, so this enumerates the
    invoking checkout's OWN mission directories through the canonical resolver
    boundary (:func:`specify_cli.context.mission_resolver.list_missions_for_selection`)
    instead of a raw ``kitty-specs/`` walk (mission-resolver-port ADR,
    ``tests/architectural/test_mission_resolver_walker_gate.py``). Cost is
    bounded (review cycle 4, NFR-002): the handle-independent front of
    adoption runs once (:func:`_adoptable_toplevel`), the checkout's branch is
    read once, and listings are pre-filtered by plain file reads against the
    minter's own branch rule (:func:`_branch_matches_target`); only survivors
    -- usually none, at most one -- go through full :func:`adopt_owned_checkout`.
    So R, coordination worktrees, listed and stale lanes and plain linked
    checkouts resolve zero ownership claims. A mission-surface conflict raised
    by adoption answers ``True`` (the checkout claims a mission).
    """
    from specify_cli.context.mission_resolver import list_missions_for_selection

    toplevel = _adoptable_toplevel(repository_root.resolve(), cwd)
    if toplevel is None:
        return False
    current = get_current_branch(toplevel)
    for listing in list_missions_for_selection(toplevel):
        safe_slug = assert_safe_path_segment(listing.mission_slug)
        mission_dir = toplevel / KITTY_SPECS_DIR / safe_slug
        if not _branch_matches_target(current, _target_branch_from_meta_file(mission_dir)):
            continue
        try:
            if adopt_owned_checkout(repository_root, cwd, safe_slug, allowed_topologies=allowed_topologies) is not None:
                return True
        except ActionContextError:
            return True
    return False


def require_unstaged_index(context: OwnedCheckout) -> None:
    """Refuse pre-existing staged changes instead of temporarily stashing them."""
    # _staged_tree_is_empty is the canonical staged-tree authority (commit_helpers).
    if not _staged_tree_is_empty(context.owned_root):
        raise ActionContextError(OwnedRefusalCode.OWNED_INDEX_REFUSED, "The selected checkout must have no staged changes before this operation.")
