"""Shared write-target degrade helper (FR-005, C-004).

Unifies the ``_mission_meta_exists`` pre-gate and port-resolution logic across
three call sites, extracting a single kind-parameterized helper while preserving
each caller's distinct degrade policy (fail-open vs. fail-closed).

The three callers:
* ``decision_log._resolve_default_target`` (fail-open) — passes a concrete
  ``degrade_ref``; an unresolvable mission returns that ref.
* ``bookkeeping_commit._resolve_bookkeeping_commit_target`` (fail-closed) —
  passes ``degrade_ref=branch`` (which may be ``None``); an unresolvable
  mission with no ``branch`` raises ``ActionContextError``.
* ``status_transition._resolve_write_target`` (WP05, fail-closed) — adds pre-gate; preserves degrade

Resolution is always attempted FIRST regardless of ``degrade_ref`` — a
resolvable mission returns the placement-port target even when the caller
passed ``degrade_ref=None`` (fail-closed callers still get the real target
whenever one exists; ``degrade_ref``/the raise is consulted only once
resolution has genuinely failed). This preserves the pre-WP04 semantics of
the two callers this helper replaces.

See spec: FR-005, C-004; plan IC-06a, IC-06b.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mission_runtime.artifacts import MissionArtifactKind
from mission_runtime.context import CommitTarget
from mission_runtime.resolution import (
    _FEATURE_CONTEXT_UNRESOLVED_CODE,
    ActionContextError,
    resolve_placement_only,
)

if TYPE_CHECKING:
    # Type-checking-only: satisfies the ``StatusReadPathNotFound`` annotation
    # below without a real module-level import (see the deferred-import note
    # further down for why a runtime module-level import here is unsafe).
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

__all__ = ["assert_coord_write_materialized", "resolve_write_target_or_degrade"]

# S-C fail-closed WRITE gate (FR-006; #4970). A terminus WRITE that resolves to
# the coordination branch must land on a *materialized* coordination surface. On
# a checkout where that surface is absent AND the coordination branch is not a
# local head (the fresh-clone / CI shape where the lane exists only on
# ``origin/<lane>``), materializing it would fork from the primary branch and
# overwrite committed coordination state (teammates' verdicts). The single stable
# ``error_code`` lets callers route on it without string parsing.
_COORD_WRITE_UNMATERIALIZED_CODE = "COORD_WRITE_SURFACE_UNMATERIALIZED"

# NOTE on the ``specify_cli.missions._read_path_resolver`` imports below: they
# are deliberately LOCAL (function-scoped), matching the established
# ``mission_runtime -> specify_cli`` upward-edge convention every other site
# under the ledgered "missions" exception uses (see
# ``resolution.py``'s repeated in-function
# ``from specify_cli.missions._read_path_resolver import (...)`` calls and
# ``tests/architectural/test_layer_rules.py``'s
# ``_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI["missions"]`` ledger entry). A
# MODULE-LEVEL import here creates a genuine circular import: whenever
# ``specify_cli.missions._read_path_resolver`` is the module that FIRST
# touches the ``mission_runtime`` package (its own line importing
# ``MissionArtifactKind`` triggers ``mission_runtime/__init__.py``, which
# imports this module, which would then import BACK from
# ``_read_path_resolver`` while it is still mid-initialization -- an
# ``ImportError: cannot import name 'StatusReadPathNotFound' from partially
# initialized module`` at whatever call site happens to touch
# ``specify_cli.acceptance`` (or any other consumer) first). Deferring the
# import to call time (well after both modules have finished initializing)
# closes that hole exactly the way every sibling ``resolution.py`` call site
# already does.


def resolve_write_target_or_degrade(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    degrade_ref: str | None,
    terminus_write: bool = False,
) -> CommitTarget:
    """Resolve write target via the placement port, or degrade to a caller-supplied ref.

    Unifies port-resolution + the ``_mission_meta_exists`` pre-gate (NOT the degrade
    policy). Each caller supplies its own ``degrade_ref`` so that fail-open vs.
    fail-closed behavior is preserved at the call site.

    Resolution is attempted first: when ``mission_slug`` has a ``meta.json`` and
    ``resolve_placement_only`` succeeds, its target is returned regardless of
    ``degrade_ref`` — including when ``degrade_ref`` is ``None``. ``degrade_ref``
    (or the fail-closed raise) is consulted only once resolution has actually
    failed (no ``meta.json`` yet, or a caught resolution error).

    Args:
        repo_root: Path to the primary git repository.
        mission_slug: The mission slug to resolve.
        kind: The artifact kind (determines partition routing: PRIMARY_METADATA → primary
            ``target_branch``; other kinds → topology-routed destination, e.g. COORD).
        degrade_ref: The ref to return if the mission cannot be resolved (no ``meta.json``
            yet, or an ad-hoc fixture outside a resolvable mission). The caller decides
            the policy: fail-open passes a concrete ref, fail-closed passes ``None`` to
            raise instead of silently degrading.
        terminus_write: Fail-closed WRITE mode (S-C / FR-006 / #4970). When ``True``
            the caller is a terminus WRITE, so this NEVER degrades to ``degrade_ref``
            on a resolution failure (it raises, regardless of ``degrade_ref``), AND —
            once resolution succeeds — it additionally asserts that a coord-routing
            target is a *materialized* coordination surface via
            :func:`assert_coord_write_materialized`, refusing the wrong-surface write
            #4970 exploits. Default ``False`` preserves every existing (fail-open /
            fail-closed-via-``degrade_ref``) caller byte-identically.

    Returns:
        A ``CommitTarget`` resolved for ``kind`` through the placement port, or
        ``CommitTarget(ref=degrade_ref)`` if the mission is not resolvable and
        ``degrade_ref`` is not ``None`` (fail-open, non-``terminus_write`` callers).

    Raises:
        ``ActionContextError`` when the mission cannot be resolved AND either
        ``degrade_ref`` is ``None`` or ``terminus_write`` is ``True`` (fail-closed
        policy — never silently degrades to a null ref, and a terminus write never
        degrades to a caller-supplied ref). When a *caught-set* resolution failure
        (``ActionContextError`` / ``StatusReadPathNotFound`` / ``FileNotFoundError``)
        is what triggered the fail-closed path, the fresh ``ActionContextError``
        raised here preserves that failure's concrete ``error_code`` (or
        ``.code`` for an ``ActionContextError``) and chains it as the cause
        (``from exc``) — mirroring ``mission_runtime.resolution``'s own
        boundary-translation idiom (e.g. ``resolve_action_context`` /
        ``resolve_placement_only``: ``raise ActionContextError(exc.error_code,
        str(exc)) from exc``) — so a data-loss signal like
        ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound`` subclass)
        never gets flattened into a generic, chain-less error. Only failures
        *outside* the caught set (ambiguous/malformed mission, etc.) propagate
        verbatim. Additionally raises ``ActionContextError`` (code
        ``COORD_WRITE_SURFACE_UNMATERIALIZED``) when ``terminus_write`` is ``True``
        and the resolved coord surface is unmaterialized/unresolved (#4970).
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    resolution_exc: ActionContextError | StatusReadPathNotFound | FileNotFoundError | None = None
    if _mission_meta_exists(repo_root, mission_slug):
        try:
            resolved = resolve_placement_only(repo_root, mission_slug, kind=kind)
        except (ActionContextError, StatusReadPathNotFound, FileNotFoundError) as exc:
            resolution_exc = exc
        else:
            if terminus_write:
                assert_coord_write_materialized(repo_root, mission_slug, kind, resolved)
            return resolved
    if degrade_ref is None or terminus_write:
        raise _fail_closed_error(mission_slug, resolution_exc) from resolution_exc
    return CommitTarget(ref=degrade_ref)


def assert_coord_write_materialized(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    resolved: CommitTarget,
) -> None:
    """Fail-closed WRITE gate: refuse a coord-routing write onto an unmaterialized surface.

    The single decision locus for S-C (FR-006 / #4970), consulted by
    :func:`resolve_write_target_or_degrade`'s ``terminus_write`` mode and by the
    real write chain (``coordination.write_seam.write_artifact``) on its
    already-probed target. It is a NARROW materialization assertion, NOT a second
    resolver: ``resolved`` is the target the ONE placement authority already
    produced (C-006).

    No-op unless this is genuinely a coordination-branch write:

    * no primary ``meta.json`` (a stub / ad-hoc fixture / legacy mission) → return
      (nothing to gate — the resolver's own policy already applied);
    * no declared ``coordination_branch``, or ``resolved.ref`` is not that branch
      (a PRIMARY write, a flattened mission, or an E2 CONSOLIDATED write that
      resolves to the Primary Branch) → return;
    * a coord-routing write whose coordination worktree is ``MATERIALIZED`` /
      ``EMPTY`` (the worktree exists — the write populates/updates it), or is
      ``UNMATERIALIZED`` while the coordination branch is a *local head* (the
      sanctioned ``mission create`` → first-write self-materialization window on
      the creating host) → return.

    Raises ``ActionContextError`` (``COORD_WRITE_SURFACE_UNMATERIALIZED``) only for
    the #4970 shape: a coord-routing write whose coordination worktree is absent
    AND whose coordination branch is not a local head (deleted, or the fresh-clone
    / CI checkout where it exists only on ``origin/<lane>``). Materializing there
    would fork from the primary branch and overwrite committed coordination state.
    """
    from specify_cli.coordination.surface_resolver import (
        _coord_branch_is_local_head,
        resolve_declared_mid8,
    )
    from specify_cli.missions._read_path_resolver import (
        CoordState,
        probe_coord_state,
        read_primary_meta,
    )

    primary_meta, _declares_coordination = read_primary_meta(repo_root, mission_slug)
    raw_branch = primary_meta.get("coordination_branch")
    coord_branch = str(raw_branch) if raw_branch else None
    if coord_branch is None or resolved.ref != coord_branch:
        # PRIMARY / flattened / E2 CONSOLIDATED write — not a coordination-branch
        # write, so the coord-materialization gate does not apply.
        return

    mid8 = resolve_declared_mid8(primary_meta, mission_slug)
    state = probe_coord_state(repo_root, mission_slug, mid8, coordination_branch=coord_branch)
    if state in (CoordState.MATERIALIZED, CoordState.EMPTY):
        return
    if state is CoordState.UNMATERIALIZED and _coord_branch_is_local_head(repo_root, coord_branch):
        return

    raise ActionContextError(
        _COORD_WRITE_UNMATERIALIZED_CODE,
        f"Refusing a terminus WRITE of {kind.value!r} for mission {mission_slug!r}: "
        f"its authoritative coordination surface (branch {coord_branch!r}) is "
        f"unresolved or unmaterialized on this checkout — the coordination worktree "
        f"is absent and {coord_branch!r} is not a local branch head (e.g. a fresh "
        f"clone / CI checkout where the lane exists only on origin). Writing would "
        f"degrade to the primary directory and overwrite committed coordination "
        f"state (#4970). Materialize the coordination surface first: run `git fetch` "
        f"then `spec-kitty doctor workspaces --fix`, or check out {coord_branch!r} "
        f"locally before retrying.",
    )


def _fail_closed_error(
    mission_slug: str,
    resolution_exc: ActionContextError | StatusReadPathNotFound | FileNotFoundError | None,
) -> ActionContextError:
    """Build the fail-closed ``ActionContextError``, preserving a caught cause's
    concrete ``error_code``/``.code`` when one triggered the fail-closed path.

    ``resolution_exc`` is ``None`` when the mission had no ``meta.json`` at all
    (nothing was caught to preserve); it is the concrete caught exception when
    ``resolve_placement_only`` genuinely failed. Chaining (``from
    resolution_exc``) is the caller's job (:func:`resolve_write_target_or_degrade`)
    since ``raise ... from ...`` cannot be expressed inside a plain constructor
    call.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    if isinstance(resolution_exc, ActionContextError):
        return ActionContextError(resolution_exc.code, str(resolution_exc))
    if isinstance(resolution_exc, StatusReadPathNotFound):
        # Covers ``CoordinationBranchDeleted`` too (a ``StatusReadPathNotFound``
        # subclass) -- its distinct ``error_code`` (``COORDINATION_BRANCH_DELETED``)
        # survives instead of being collapsed into the generic unresolved code.
        return ActionContextError(resolution_exc.error_code, str(resolution_exc))
    return ActionContextError(
        _FEATURE_CONTEXT_UNRESOLVED_CODE,
        f"resolve_write_target_or_degrade: mission {mission_slug!r} requires "
        "a degrade-path ref because it could not be resolved via the "
        "placement port and no degrade_ref was supplied (fail-closed).",
    )


def _mission_meta_exists(repo_root: Path, mission_slug: str) -> bool:
    """Return True when ``mission_slug`` has a primary ``meta.json`` on disk.

    A cheap, read-only existence gate — NOT a ref derivation — that
    distinguishes a genuinely bootstrapped mission from an ad-hoc fixture or
    the create→first-write window. ``resolve_placement_only`` never raises
    for a merely-absent mission (:func:`candidate_feature_dir_for_mission`'s
    own contract): it silently degrades to the repo's generic default branch
    instead of signalling unresolvability, so this gate is checked BEFORE
    consulting the classifier rather than relying on an exception that would
    never fire.
    """
    from specify_cli.missions._read_path_resolver import (
        candidate_feature_dir_for_mission,
    )

    try:
        # Explicit ``Path`` annotation: under the project's
        # ``follow_imports = "skip"`` mypy config the cross-module
        # ``candidate_feature_dir_for_mission`` return is seen as ``Any``; the
        # annotation re-narrows it (the function IS typed ``-> Path``).
        candidate: Path = candidate_feature_dir_for_mission(repo_root, mission_slug)
    except Exception:  # noqa: BLE001 — any resolution hiccup means "not resolvable"
        return False
    return (candidate / "meta.json").exists()
