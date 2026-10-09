"""Pure decision cores for mission creation (#5634).

Pure. No git, filesystem, subprocess, environment, clock or ULID access.
Guarded by tests/core/test_mission_creation_purity.py.

Every function here decides over plain values that the effectful adapter in
:mod:`specify_cli.core.mission_creation` gathers. The rule content stays with
its authority: protection with ``ProtectionPolicy.is_protected_target``, the
coordination-bearing topologies with ``topology_mints_coordination_branch``,
the branch name with ``mission_branch_name``. The adapter passes their answers
in; nothing here re-derives them.

Lazy facts (no change to when an error is raised): a fact the adapter has not gathered yet is
passed as ``None``. A decision that needs such a fact returns ``None``
("undecided"), and the adapter gathers that fact next and asks again. This keeps
today's probe order and stops at the first probe that decides, so an error a
probe raises still raises at the same point.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Protocol

from mission_runtime import MissionTopology
from specify_cli.meta_keys import PR_BOUND_KEY

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CasReset",
    "CommitFailureKind",
    "Delete",
    "Mint",
    "NoMint",
    "Noop",
    "ProtectedMintDecision",
    "ProtectedMintFacts",
    "ProtectedTargetPolicy",
    "Refuse",
    "candidate_name_matches",
    "classify_scaffold_commit_failure",
    "coord_rollback_action",
    "coord_rollback_needs_current_tip",
    "created_file_sets",
    "decide_protected_mint",
    "is_abandoned",
    "is_coordination_routed",
    "is_same_mission_type",
    "meta_flag_patch",
    "orphan_scaffold_candidates",
    "plan_orphan_scaffold_removal",
    "protected_mint_applies",
    "target_is_protected",
]

# Directory-name suffix for the canonical ``<human-slug>-<mid8>`` mission-dir
# grammar (mirrors the matching convention used by
# ``plan_orphan_scaffold_removal`` below). Captures the mid8 so the duplicate
# guard's refusal message can name it without a second (possibly-failing)
# meta.json read (FR-002).
_MID8_DIR_SUFFIX_PATTERN = r"-([0-9A-Za-z]{8})"
_DEFAULT_MISSION_TYPE = "software-dev"


# ---------------------------------------------------------------------------
# Protection
# ---------------------------------------------------------------------------


class ProtectedTargetPolicy(Protocol):
    """The slice of ``ProtectionPolicy`` the protection decision reads (structural)."""

    def is_protected_target(self, branch: str, *, primary_branch: str) -> bool:
        """``ProtectionPolicy.is_protected_target``: the #5100 "primary plus configured" rule."""
        ...


def target_is_protected(policy: ProtectedTargetPolicy, target_branch: str, primary_for_protection: str) -> bool:
    """True when *target_branch* is a protected target (C-002: one protection authority).

    *primary_for_protection* is the Primary Branch resolved with ``bias=False``
    (follow-up #5707).
    """
    return bool(policy.is_protected_target(target_branch, primary_branch=primary_for_protection))


def protected_mint_applies(
    topology: MissionTopology,
    commit_to_target: bool | None,
    target_protected: bool | None,
) -> bool | None:
    """True when create mints a protected-target mission branch (#5100 WP08).

    Only a ``single_branch`` mission without the ``commit_to_target`` override
    on a protected target mints. ``None`` for a fact means it was not gathered
    yet; the result is ``None`` when that fact is the one that decides.
    """
    if topology is not MissionTopology.SINGLE_BRANCH:
        return False
    if commit_to_target is None:
        return None
    if commit_to_target:
        return False
    return target_protected


# ---------------------------------------------------------------------------
# Protected single_branch mint
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProtectedMintFacts:
    """The facts the protected mint decides on, in probe order (``None`` = not gathered)."""

    target_branch: str
    write_root_display: str
    #: The target is protected (the topology / override gate already passed).
    mint_applies: bool
    target_has_commit: bool | None = None
    #: Uncommitted paths outside this mission's own scaffold.
    dirty_outside_scaffold: tuple[str, ...] | None = None
    #: ``mission_branch_name(...)``, composed by the adapter (the ONE composer).
    branch_name: str | None = None
    branch_exists: bool | None = None


@dataclass(frozen=True, slots=True)
class NoMint:
    """The target is not protected: create commits where it stands."""


@dataclass(frozen=True, slots=True)
class Refuse:
    """Refuse the mint before any ref or meta mutation."""

    kind: Literal["error", "branch_exists"]
    message: str


@dataclass(frozen=True, slots=True)
class Mint:
    """Create *branch_name* at the target's tip and check it out."""

    branch_name: str


ProtectedMintDecision = NoMint | Refuse | Mint


def decide_protected_mint(facts: ProtectedMintFacts) -> ProtectedMintDecision | None:
    """Decide the protected mint; ``None`` while the next fact in probe order is needed.

    Order (unchanged): applies, target has a commit, dirty outside the
    scaffold, branch exists, mint.
    """
    if not facts.mint_applies:
        return NoMint()
    if facts.target_has_commit is None:
        return None
    if not facts.target_has_commit:
        target_branch = facts.target_branch
        return Refuse(
            "error",
            f"Cannot mint the protected-target mission branch: target branch {target_branch!r} "
            f"has no commit in {facts.write_root_display} (it does not exist yet, or is still unborn). "
            f"Create it with at least one commit (for example: git branch {target_branch} <start-point>), "
            "or pass --target-branch naming an existing branch, then retry.",
        )
    if facts.dirty_outside_scaffold is None:
        return None
    if facts.dirty_outside_scaffold:
        return Refuse(
            "error",
            "Cannot mint the protected-target mission branch: the write "
            f"checkout at {facts.write_root_display} has uncommitted changes outside "
            f"this mission's own scaffold: {', '.join(facts.dirty_outside_scaffold)}. Commit or "
            "discard them, then retry.",
        )
    if facts.branch_name is None or facts.branch_exists is None:
        return None
    if facts.branch_exists:
        return Refuse(
            "branch_exists",
            f"Mission branch {facts.branch_name!r} already exists. Choose a "
            "different mission slug, remove the stale branch, or pass "
            "--commit-to-target to commit directly onto the target.",
        )
    return Mint(facts.branch_name)


# ---------------------------------------------------------------------------
# Coordination-routed scaffold (defined once)
# ---------------------------------------------------------------------------


def is_coordination_routed(*, mints_coordination: bool, owned: bool) -> bool:
    """True when the create's status log lives on the coordination surface (D6).

    *mints_coordination* is ``topology_mints_coordination_branch(topology)``
    (the topology authority). An owned create is never coordination-routed
    (INV-COORD-HOME residual): its status log stays in the owned checkout.
    """
    return mints_coordination and not owned


# ---------------------------------------------------------------------------
# meta.json flags
# ---------------------------------------------------------------------------


def meta_flag_patch(
    *,
    pr_bound: bool,
    retain_branches: bool,
    retain_worktrees: bool,
    commit_to_target: bool,
) -> dict[str, bool]:
    """The create-time ``meta.json`` flags, in today's insertion order.

    A flag is written only when True; absent means never default-written
    (#3131 FR-009, #5100 FR-008).
    """
    flags = {
        PR_BOUND_KEY: pr_bound,
        "retain_branches": retain_branches,
        "retain_worktrees": retain_worktrees,
        "commit_to_target": commit_to_target,
    }
    return {key: True for key, value in flags.items() if value}


# ---------------------------------------------------------------------------
# Duplicate detection (#4033)
# ---------------------------------------------------------------------------


def candidate_name_matches(name: str, base_slug: str) -> tuple[bool, str]:
    """``(matches, mid8)`` for a ``kitty-specs/`` directory name against *base_slug*.

    A match is the bare base slug or ``<base_slug>-<mid8>``; the mid8 is
    ``""`` for the bare form.
    """
    suffix_pattern = re.compile(re.escape(base_slug) + _MID8_DIR_SUFFIX_PATTERN + "$")
    match = suffix_pattern.fullmatch(name)
    if name != base_slug and match is None:
        return False, ""
    return True, match.group(1) if match is not None else ""


def is_same_mission_type(candidate_meta: Mapping[str, object], mission_type: str) -> bool:
    """True when the candidate's ``mission_type`` (default ``software-dev``) is *mission_type*."""
    return str(candidate_meta.get("mission_type") or _DEFAULT_MISSION_TYPE) == mission_type


def is_abandoned(
    *,
    wp_lanes: Mapping[str, str | None],
    canceled_lane: str,
    event_count: int,
    spec_tracked: bool | None,
    mission_branch_live: bool = False,
) -> bool | None:
    """Classify a same-key prior mission as abandoned (#4033 research.md D-2).

    Abandoned = every recorded work package sits in *canceled_lane*, OR no
    lifecycle progress (zero events) AND the spec was never committed AND
    *mission_branch_live* is false. ``spec_tracked`` is ``None`` until probed;
    the result is ``None`` when it is the deciding fact.

    *mission_branch_live* (#5726): the prior's protected-target mint created
    its ``mission_branch``, that branch still exists (its scaffold is committed
    there), and the create asking would run the protected mint too. That is
    real create state, not a never-touched scaffold, even while ``spec.md`` is
    untracked under the #846 create boundary.
    """
    if wp_lanes and all(lane == canceled_lane for lane in wp_lanes.values()):
        return True
    if event_count != 0:
        return False
    if spec_tracked is None:
        return None
    return not spec_tracked and not mission_branch_live


# ---------------------------------------------------------------------------
# Failed-create rollback
# ---------------------------------------------------------------------------


def orphan_scaffold_candidates(
    *,
    post_names: frozenset[str],
    pre_names: frozenset[str],
    mission_slug: str,
) -> tuple[str, ...]:
    """New ``kitty-specs/`` names this create may have written, sorted.

    ``mission_slug_formatted`` is ``<slug>-<mid8>``, so match the stem and
    never a same-prefixed neighbour ("task-list" must not match
    "task-list-api-01ABCDEF").
    """
    return tuple(name for name in sorted(post_names - pre_names) if name == mission_slug or re.fullmatch(re.escape(mission_slug) + r"-[0-9A-Za-z]{8}", name))


def plan_orphan_scaffold_removal(
    *,
    post_names: frozenset[str],
    pre_names: frozenset[str],
    mission_slug: str,
    tracked: frozenset[str],
) -> tuple[str, ...]:
    """The candidate scaffolds a failed create may delete: those git does not track."""
    candidates = orphan_scaffold_candidates(post_names=post_names, pre_names=pre_names, mission_slug=mission_slug)
    return tuple(name for name in candidates if name not in tracked)


@dataclass(frozen=True, slots=True)
class Delete:
    """Delete the coordination branch: this create minted it."""


@dataclass(frozen=True, slots=True)
class CasReset:
    """Compare-and-swap the reused coordination branch from *expected* back to *to*."""

    expected: str
    to: str


@dataclass(frozen=True, slots=True)
class Noop:
    """Leave the coordination branch as it is."""


def coord_rollback_needs_current_tip(*, created: bool, pre_seed_tip: str | None) -> bool:
    """True when :func:`coord_rollback_action` depends on the branch's current tip."""
    return not created and pre_seed_tip is not None


def coord_rollback_action(
    *,
    created: bool,
    pre_seed_tip: str | None,
    current_tip: str | None,
) -> Delete | CasReset | Noop:
    """What a failed create does to its coordination branch (T032/FR-002a).

    A branch this create minted is deleted. A pre-existing branch it reused is
    CAS-reset to its own pre-create tip when it moved, never deleted (it may
    belong to another mission's history). An unreadable tip is left alone.
    """
    if created:
        return Delete()
    if pre_seed_tip is None:
        return Noop()
    if current_tip and current_tip != pre_seed_tip:
        return CasReset(expected=current_tip, to=pre_seed_tip)
    return Noop()


# ---------------------------------------------------------------------------
# Scaffold commit outcome and result file sets
# ---------------------------------------------------------------------------


class CommitFailureKind(Enum):
    """The adapter's classification of a scaffold-commit exception."""

    #: A bootstrap refusal main permits and discloses (protected, HEAD mismatch, missing destination).
    BOOTSTRAP_REFUSAL = "bootstrap_refusal"
    #: The byte-identical scaffold is already committed (#3861).
    STAGED_TREE_UNCHANGED = "staged_tree_unchanged"
    #: Any other failure.
    OTHER = "other"


def classify_scaffold_commit_failure(kind: CommitFailureKind) -> Literal["skip", "already_exists", "raise"]:
    """Skip a disclosed bootstrap refusal, type the duplicate signature, raise the rest (FR-001)."""
    if kind is CommitFailureKind.BOOTSTRAP_REFUSAL:
        return "skip"
    if kind is CommitFailureKind.STAGED_TREE_UNCHANGED:
        return "already_exists"
    return "raise"


def created_file_sets(
    *,
    spec_file: Path,
    meta_file: Path,
    tasks_readme: Path,
    tasks_gitkeep: Path,
    log_path: Path,
    coordination_routed: bool,
    scaffold_commit_skipped: bool,
) -> tuple[list[Path], list[Path]]:
    """``(created_files, uncommitted_files)`` of a create result.

    A coordination-routed create's status log is committed separately on the
    coordination branch, so it is created but never in the skipped target
    scaffold.
    """
    created_files = [spec_file, meta_file, tasks_readme]
    if coordination_routed:
        created_files.append(log_path)
    uncommitted_files = [spec_file]
    if scaffold_commit_skipped:
        skipped_scaffold = [meta_file, tasks_readme, tasks_gitkeep]
        if not coordination_routed:
            skipped_scaffold.append(log_path)
        created_files.extend(path for path in skipped_scaffold if path not in created_files)
        uncommitted_files.extend(skipped_scaffold)
    return created_files, uncommitted_files
