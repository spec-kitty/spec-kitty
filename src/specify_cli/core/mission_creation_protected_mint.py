"""Protected-target mission-branch mint for ``single_branch`` missions.

Moved from ``mission_creation.py`` (#5634); reshaped by the decision-core and seam
cleanups. ``mission_creation`` re-exports every name defined here. A call to a name
tests patch on ``mission_creation``, or to a function another ``mission_creation*``
module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, NoReturn

from specify_cli.core.constants import KITTY_SPECS_DIR
from mission_runtime import (
    MissionTopology,
)
from specify_cli.core.mission_creation_decisions import (
    Mint,
    NoMint,
    ProtectedMintFacts,
    ProtectedTargetPolicy,
    Refuse,
    decide_protected_mint,
    protected_mint_applies,
    target_is_protected,
)
from specify_cli.core.paths import (
    read_commit_to_target,
)
from specify_cli.lanes.branch_naming import (
    mission_branch_name,
)
from specify_cli.core.mission_creation_errors import (
    MissionAlreadyExistsError,
    MissionBranchExistsError,
    MissionCreationError,
    ProtectedMintRefusedError,
    TargetReplacement,
    WriteCheckoutSwitchDirtyError,
)
from specify_cli.core.write_checkout_switch import switch_write_checkout


def _target_has_commit(write_root: Path, target_branch: str) -> bool:
    """Probe: does *target_branch* name a commit in *write_root*?"""
    probe = subprocess.run(
        ["git", "-C", str(write_root), "rev-parse", "--verify", "--quiet", f"{target_branch}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def _raise_refusal(decision: Refuse) -> NoReturn:
    """Raise a protected-mint refusal as a :class:`ProtectedMintRefusedError` (error codes unchanged).

    The type is what marks the refusal disposable for the failure-atomic
    rollback (#5704): no scaffold outlives it.
    """
    if decision.kind == "branch_exists":
        raise MissionBranchExistsError(decision.message)
    raise ProtectedMintRefusedError(decision.message)


class _ProtectionProbe:
    """The protection facts of one create, resolved lazily on first use and then memoised.

    The orchestrator makes one probe per create and hands it to the recreate
    guard and the mint, so protection is resolved at most once, at the first
    point that needs it (today's point: never earlier). A resolution that
    raises (a malformed protection config) is not cached: it raises from that
    first point, as before.
    """

    __slots__ = ("_write_root", "_facts", "_mints_on_every_target")

    def __init__(self, write_root: Path, *, mints_on_every_target: bool = False) -> None:
        self._write_root = write_root
        self._facts: tuple[ProtectedTargetPolicy, str] | None = None
        # S7 #7282 (FR-051): a create without ``--topology`` mints its Mission topic
        # branch on every target, so the mint gate reads every target as one that
        # mints and protection itself is never resolved.
        self._mints_on_every_target = mints_on_every_target

    def is_protected(self, target_branch: str) -> bool:
        """True when *target_branch* is a protected target under the #5100 rule (C-002).

        Always ``True`` for the probe of a create without ``--topology``.
        """
        if self._mints_on_every_target:
            return True
        if self._facts is None:
            self._facts = self._resolve()
        policy, primary_branch = self._facts
        # Typed binding (the ``_consume_pending_origin_if_present`` idiom): mypy uses
        # follow_imports=skip for specify_cli.*, so the decisions core reads as Any.
        protected: bool = target_is_protected(policy, target_branch, primary_branch)
        return protected

    def _resolve(self) -> tuple[ProtectedTargetPolicy, str]:
        from specify_cli.core.git_ops import resolve_primary_branch
        from specify_cli.git.protection_policy import ProtectionPolicy

        policy: ProtectedTargetPolicy = ProtectionPolicy.resolve(self._write_root)
        # bias=False (mission_branch_context._resolve_primary_branch_for_recommendation's
        # rationale applies verbatim here): the CURRENT checkout is virtually
        # ALWAYS the target branch at create time (single_branch missions are
        # created from wherever the operator is standing), so the default
        # feature-bias resolution would treat EVERY target as "primary" and mint
        # unconditionally. The genuine repository primary (main/master/origin
        # default) is what the #5100 rule means by "primary".
        primary_branch: str = resolve_primary_branch(self._write_root, bias=False)
        return policy, primary_branch


def _protected_mint_applies(
    write_root: Path,
    *,
    topology: MissionTopology,
    commit_to_target: bool,
    target_branch: str,
    protection: _ProtectionProbe | None = None,
) -> bool:
    """True when create will mint a protected-target mission branch (#5100 WP08).

    Only then does a re-create of an already-scaffolded mission collide on the
    deterministic mission branch (same slug + mid8), so only then must the
    re-create be refused up front as MISSION_ALREADY_EXISTS rather than surface
    the mint's MISSION_BRANCH_EXISTS. Every other shape keeps origin/main's
    idempotent resume (the #4033 guard already refuses a LIVE duplicate).
    """
    # ``bool()`` keeps an unset override fail-closed (falsy, as before the split):
    # ``None`` would otherwise read as "override not gathered" and never decide.
    override = bool(commit_to_target)
    applies = protected_mint_applies(topology, override, None)
    if applies is None:
        # Protection is resolved only when it decides (a malformed protection
        # config raises only on this path, as it always did).
        probe = protection if protection is not None else _ProtectionProbe(write_root)
        applies = protected_mint_applies(topology, override, probe.is_protected(target_branch))
    return applies is True


def _mint_protected_single_branch_mission_branch(
    write_root: Path,
    mission_slug_formatted: str,
    *,
    mission_id: str,
    target_branch: str,
    meta: dict[str, Any],
    protection: _ProtectionProbe | None = None,
    repository_root: Path | None = None,
) -> None:
    """Mint + check out the mission branch for a protected single_branch target.

    #5100 FR-007/FR-012 (WP08 / IC-05, research.md R-5/R-8). A no-op unless
    the target is protected under the #5100 "primary plus configured" rule
    (:meth:`~specify_cli.git.protection_policy.ProtectionPolicy.is_protected_target`,
    C-002: the single protection authority). When it fires:

    0. Refuses ``WRITE_CHECKOUT_OCCUPIED`` when another ``single_branch``
       Mission has a WP ``in_progress`` in the write checkout (#5676; the
       occupancy rule ``implement`` applies, #5550 included).
    1. Refuses ``WRITE_CHECKOUT_DIRTY`` if the write checkout (*write_root*) has uncommitted
       changes outside this mission's own (still-untracked) scaffold --
       switching branches under the operator's unrelated dirty work would be
       unsafe (mirrors FR-009's write-checkout dirty refusal, scoped here to
       the narrower create-time question).
    2. Composes the deterministic name via :func:`mission_branch_name` (the
       ONE composer -- never re-derived here) and refuses with
       :class:`MissionBranchExistsError` if that ref already exists.
    3. Creates the branch at ``target_branch``'s tip and checks it out in
       *write_root* -- no worktree.
    4. Records ``meta["mission_branch"]``.

    Mutates *meta* in place; raises on any refusal (fail-closed, no partial
    mutation of *meta* on the refusal paths -- the git branch/checkout writes
    only happen after every refusal check passed). Steps 0, 1 and 3 are
    :func:`switch_write_checkout`, the one switch core; steps 1 and 2 are decided by
    :func:`decide_protected_mint` in its probe order.
    """
    probe = protection if protection is not None else _ProtectionProbe(write_root)
    facts = ProtectedMintFacts(
        target_branch=target_branch,
        write_root_display=str(write_root),
        mint_applies=probe.is_protected(target_branch),
    )
    decision = decide_protected_mint(facts)
    if decision is None:
        facts = replace(facts, target_has_commit=_target_has_commit(write_root, target_branch))
        decision = decide_protected_mint(facts)
    match decision:
        case NoMint():
            return
        case Refuse():
            _raise_refusal(decision)
        case None:
            pass
        case _:  # fail closed: a Mint before the dirty and branch facts is impossible
            raise MissionCreationError(f"Protected-mint decision for {target_branch!r} is premature: {decision!r}.")
    branch_name = mission_branch_name(mission_slug_formatted, mission_id=mission_id)
    switch_write_checkout(
        write_root,
        branch_name,
        start_point=target_branch,
        repository_root=repository_root if repository_root is not None else write_root,
        owned_paths=_scaffold_owned_paths(mission_slug_formatted),
        decide=lambda dirty: _decide_mint_switch(write_root, replace(facts, dirty_outside_scaffold=dirty, branch_name=branch_name)),
    )
    meta["mission_branch"] = branch_name


def _decide_mint_switch(write_root: Path, facts: ProtectedMintFacts) -> None:
    """Decide the mint from the dirty fact, then the branch-exists fact; raise its refusal.

    The *decide* step of :func:`switch_write_checkout` for create: it runs after the
    occupancy refusal and before any git write, so the probe order stays
    applies, target has a commit, occupied, dirty, branch exists, mint.
    """
    decision = decide_protected_mint(facts)
    if isinstance(decision, Refuse):
        raise WriteCheckoutSwitchDirtyError(decision.message)
    if decision is None and facts.branch_name is not None:
        decision = decide_protected_mint(replace(facts, branch_exists=_local_branch_exists(write_root, facts.branch_name)))
    match decision:
        case Mint():
            return
        case Refuse():
            _raise_refusal(decision)
        case _:  # unreachable: every fact is gathered by now; fail closed
            raise MissionCreationError(f"Protected-mint decision for {facts.target_branch!r} is incomplete.")


def _local_branch_exists(write_root: Path, branch_name: str) -> bool:
    """Probe: does ``refs/heads/<branch_name>`` exist in *write_root*?"""
    return (
        subprocess.run(
            ["git", "-C", str(write_root), "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _scaffold_owned_paths(mission_slug_formatted: str) -> tuple[str, ...]:
    """The paths a create owns in the write checkout: ``.kittify`` and this Mission's own scaffold.

    Only the operator's unrelated uncommitted work is "dirty" for the switch. The
    overlap test of :func:`~specify_cli.core.write_checkout_switch.switch_write_checkout` is bidirectional and component-wise
    (unlike ``lanes.checkout_occupancy.dirty_paths``'s one-directional
    ``_is_owned_path``): on a freshly-scaffolded ``kitty-specs/`` (this Mission is
    the first ever created), git's default ``--untracked-files=normal`` collapses
    the whole new directory to the single line ``kitty-specs/`` -- an ANCESTOR of,
    not a match for, the Mission-scoped path.
    """
    return (".kittify", f"{KITTY_SPECS_DIR}/{mission_slug_formatted}")


def _refuse_protected_recreate(
    write_root: Path,
    feature_dir: Path,
    *,
    topology: MissionTopology,
    commit_to_target: bool,
    planning_branch: str,
    protection: _ProtectionProbe | None = None,
) -> None:
    """Refuse a re-create the #5100 protected-target mint would collide on (T051 port).

    A re-create of an already-scaffolded mission that the protected-target
    mint (:func:`_mint_protected_branch_for_topology`) would handle must
    report MISSION_ALREADY_EXISTS. This runs BEFORE any write and before the
    mint, whose "mission branch exists" refusal would otherwise mask it: the
    mission branch name is derived from the same slug + mid8, so such a
    re-create always collides on the branch too. Scoped to the mint's own
    predicate: every other shape keeps the idempotent resume of a genesis-only
    prior (the #4033 guard already refused a LIVE one).

    Called by :func:`_scaffold_mission_dir` on the directory it just composed
    (origin/main's order: right after the directory name, before the preflight
    and any write), so the mission directory is composed exactly once.
    """
    mission_slug_formatted = feature_dir.name
    if (feature_dir / "meta.json").exists() and _protected_mint_applies(
        write_root,
        topology=topology,
        commit_to_target=commit_to_target,
        target_branch=planning_branch,
        protection=protection,
    ):
        raise MissionAlreadyExistsError(
            f"Mission directory {mission_slug_formatted} already exists ({KITTY_SPECS_DIR}/{mission_slug_formatted}/meta.json is present). "
            "Refusing to overwrite an existing mission."
        )


def _mint_protected_branch_for_topology(
    write_root: Path,
    mission_slug_formatted: str,
    *,
    topology: MissionTopology,
    mission_id: str,
    planning_branch: str,
    meta: dict[str, Any],
    protection: _ProtectionProbe | None = None,
    repository_root: Path | None = None,
) -> str | None:
    """Step 6.7: protected-target mission branch (#5100 FR-007/FR-012, WP08 / IC-05).

    Mint and check out the mission branch BEFORE any mission file is committed:
    commit-router rule 3 refuses a coordination-less commit to a protected
    target, planning artifacts included, so a branch that did not exist until
    implement could never receive the spec, plan or tasks. Scoped to
    SINGLE_BRANCH only (COORD/LANES_WITH_COORD already mint their OWN,
    unconditional coordination branch; LANES keeps committing straight to
    target_branch per its own contract). Returns the minted branch name, or
    ``None`` when no mint fired. A create without ``--topology`` passes a
    :class:`_TopicBranchProbe`, so its topic branch is minted on every target (S7 #7282).
    """
    # Two guards, in this order: ``read_commit_to_target`` (which refuses a
    # non-boolean value) must run only for a single_branch create.
    if protected_mint_applies(topology, None, None) is False:
        return None  # not single_branch: no mint, meta's override is never read
    if protected_mint_applies(topology, read_commit_to_target(meta), None) is False:
        return None  # the commit_to_target override opts out of the mint
    _mint_protected_single_branch_mission_branch(
        write_root,
        mission_slug_formatted,
        mission_id=mission_id,
        target_branch=planning_branch,
        meta=meta,
        protection=protection,
        repository_root=repository_root,
    )
    minted_branch = meta.get("mission_branch")
    if isinstance(minted_branch, str) and minted_branch:
        return minted_branch
    return None


# ---------------------------------------------------------------------------
# Create-time target resolution guard (S7 #7282 IC-13, research R-6 risk)
# ---------------------------------------------------------------------------


def _recorded_mission_branches(write_root: Path) -> dict[str, tuple[str, str | None]]:
    """Every ``mission_branch`` / ``coordination_branch`` a Mission in *write_root* records.

    Maps each to its owning Mission's directory name and ``target_branch`` (``None``
    when unrecorded). A branch equal to the Mission's own ``target_branch`` is not a
    Mission branch. A Mission whose ``meta.json`` cannot be read is skipped.
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
    from specify_cli.meta_keys import COORDINATION_BRANCH_KEY

    specs = write_root / KITTY_SPECS_DIR
    if not specs.is_dir():
        return {}
    recorded: dict[str, tuple[str, str | None]] = {}
    for feature_dir in specs.iterdir():
        try:
            meta = load_meta_fail_closed(feature_dir) if feature_dir.is_dir() else None
        except MissionMetaReadError:
            continue
        if not meta:
            continue
        target = meta.get("target_branch")
        for key in ("mission_branch", COORDINATION_BRANCH_KEY):
            value = meta.get(key)
            if isinstance(value, str) and value and value != target:
                recorded[value] = (feature_dir.name, target if isinstance(target, str) and target else None)
    return recorded


def _resolve_planning_branch(write_root: Path, target_branch: str | None, current_branch: str, *, guard: bool) -> tuple[str, TargetReplacement | None]:
    """The create's target: the explicit ``--target-branch``, else the checked-out branch.

    IC-13 guard (*guard*: a create without ``--topology``): a default create leaves the
    write checkout on its Mission topic branch, so a second default create run from
    there would record that topic branch as its target (research R-6 risk). An implicit
    target that another Mission records as its ``mission_branch`` or
    ``coordination_branch`` is replaced by the Primary Branch (resolved without the
    checked-out-branch bias), or, when that too is a Mission branch (a repository with
    no common primary name), by the owning Mission's own ``target_branch``. An explicit
    ``--target-branch`` always wins, and an explicit ``--topology`` keeps today's
    resolution (FR-052).

    Returns the target and, when the guard replaced the checked-out branch, the
    :class:`TargetReplacement` the create reports to the operator (``None`` otherwise).
    """
    if target_branch:
        return target_branch, None
    if not guard:
        return current_branch, None
    recorded = _recorded_mission_branches(write_root)
    if current_branch not in recorded:
        return current_branch, None
    from specify_cli.core.git_ops import resolve_primary_branch

    owning_mission, owner_target = recorded[current_branch]
    primary: str = resolve_primary_branch(write_root, bias=False)
    chosen = primary if primary not in recorded else owner_target
    if chosen is None or chosen in recorded:
        raise MissionCreationError(
            f"The checked-out branch {current_branch!r} is another Mission's branch, and no target outside "
            "the Missions' branches could be resolved. Pass --target-branch <branch>."
        )
    return chosen, TargetReplacement(replaced_branch=current_branch, owning_mission=owning_mission, target_branch=chosen)


def _record_create_return_branch(meta: dict[str, Any], *, minted_branch: str | None, return_branch: str | None) -> None:
    """Record ``create_return_branch`` for a default create that switched the write checkout.

    Written only when the topic branch was minted and the checkout was on a branch
    (never a detached ``HEAD``); settlement to ``lanes_with_coord`` moves the
    repository root checkout back to it (ADR 2026-11-06-3 Decision 3).
    """
    from specify_cli.meta_keys import CREATE_RETURN_BRANCH_KEY

    if minted_branch is None or not return_branch or return_branch == "HEAD":
        return
    meta[CREATE_RETURN_BRANCH_KEY] = return_branch
