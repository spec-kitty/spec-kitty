"""Reusable mission-creation logic extracted from the CLI command.

This module provides ``create_mission_core()`` -- the programmatic API
for creating a new mission directory with all scaffolding. The CLI
command ``create()`` is a thin wrapper around this function.
"""

from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ulid import ULID

from specify_cli.core.constants import KITTY_SPECS_DIR
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    MissionTopology,
    WriteLocation,
    placement_seam,
    resolve_create_time_write_target,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.git_ops import get_current_branch, has_unborn_head, is_git_repo
from specify_cli.core.mission_payload import (
    build_mission_created_payload,
    default_mission_display_name,
    default_mission_purpose_context,
)
from specify_cli.core.owned_mission import OwnedCreateMission, OwnedCreateRoot
from specify_cli.core.paths import (
    MissionMetaReadError,
    read_commit_to_target,
    is_worktree_context,
    load_meta_fail_closed,
    locate_project_root,
)
from kernel.clock import now_utc_iso
from kernel.git import GitCommandError, GitPath, status_entries, tracked_paths
from specify_cli.git import preflight_commit, safe_commit
from specify_cli.git.commit_helpers import (
    ProtectedBranchRefused,
    SafeCommitDestinationNotFound,
    SafeCommitHeadMismatch,
    SafeCommitStagedTreeUnchanged,
)
from specify_cli.git.ref_advance import RefRestoreError, restore_branch_ref
from specify_cli.lanes.branch_naming import (
    mission_branch_name,
    mission_dir_name,
    resolve_mid8,
    strip_numeric_prefix,
)
from specify_cli.mission_metadata import load_meta_or_empty, validate_purpose_summary

logger = logging.getLogger(__name__)

# coord-primary-partition-lock WP02 (T009 / S1192): the ``meta`` field names
# repeated across the metadata-assembly block below (default + event-emission
# reads) hoisted to named constants rather than restated as literals.
_META_KEY_MISSION_TYPE = "mission_type"
_META_KEY_CREATED_AT = "created_at"

# WP12 (FR-011 / #3339): coordination branches are the only branch refs a
# mission-create mints, and their names are all ``kitty/mission-<slug>-<mid8>``.
# The glob lets the failure-atomic rollback diff pre- vs post-create refs so it
# deletes exactly the orphan branch an aborted create left behind.
_COORDINATION_BRANCH_GLOB = "kitty/mission-*"
_BOOTSTRAP_META_COMMIT_SKIPS = (
    ProtectedBranchRefused,
    SafeCommitDestinationNotFound,
    SafeCommitHeadMismatch,
)


class MissionCreationError(RuntimeError):
    """Raised when mission creation fails.

    Carries an optional structured ``error_code`` (``None`` on the base class:
    a generic, unclassified creation failure) so JSON/scripted callers can
    consume a typed failure reason instead of pattern-matching the message
    prose (#3861).
    """

    error_code: str | None = None


class MissionAlreadyExistsError(MissionCreationError):
    """A live same-key prior mission already exists (#4033 / #3861).

    The typed already-exists-vs-failed signal on the mission-creation
    surface: raised by the idempotency guard (a live prior mission shares
    the base slug and mission type) and by the scaffold commit's genuine
    empty-changeset refusal (byte-identical scaffold already committed --
    the same duplicate-mission signature). ``error_code`` is the stable
    identifier consumed by the orchestrator-api ``specify`` verb.
    """

    error_code = "MISSION_ALREADY_EXISTS"


@dataclass(slots=True)
class MissionCreationResult:
    """Structured result from ``create_mission_core()``."""

    feature_dir: Path
    mission_slug: str
    mission_number: int | None  # None for pre-merge missions (FR-044)
    meta: dict[str, Any]
    target_branch: str
    current_branch: str
    created_files: list[Path] = field(default_factory=list)
    uncommitted_files: list[Path] = field(default_factory=list)
    origin_binding_attempted: bool = False
    origin_binding_succeeded: bool = False
    origin_binding_error: str | None = None
    # Coordination-branch outcome (WP03 / issue #1348).  ``coordination_branch``
    # is the canonical per-mission ref ``kitty/mission-<slug>-<mid8>`` parented
    # off ``target_branch``; ``coordination_branch_created`` distinguishes a
    # freshly-minted branch from an idempotent reuse on re-run.
    coordination_branch: str | None = None
    coordination_branch_created: bool = False
    # Public result field keeps origin/main's name (``owned_checkout``) so every
    # consumer of the result shape reads one attribute; it now carries the
    # validated owned-create fact rather than a bare path (G5).
    owned_checkout: OwnedCreateRoot | None = None
    canonical_repo_root: Path | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9]*(-[a-z0-9]+)*$")
# Note: Intentionally permissive — bare-digit slugs like "069" are accepted.
# create_mission_core() always prefixes the mission number, so "069" becomes "070-069" in practice.

TASKS_README_TEMPLATE = """\
# Tasks Directory

This directory contains work package (WP) prompt files.

## Directory Structure (v0.9.0+)

```
tasks/
\u251c\u2500\u2500 WP01-setup-infrastructure.md
\u251c\u2500\u2500 WP02-user-authentication.md
\u251c\u2500\u2500 WP03-api-endpoints.md
\u2514\u2500\u2500 README.md
```

All WP files are stored flat in `tasks/`. Status is tracked in `status.events.jsonl`, not in WP frontmatter.

## Work Package File Format

Each WP file **MUST** use YAML frontmatter:

```yaml
---
work_package_id: "WP01"
title: "Work Package Title"
dependencies: []
planning_base_branch: "{planning_branch}"
merge_target_branch: "{planning_branch}"
branch_strategy: "Planning artifacts were generated on {planning_branch}; completed changes must merge back into {planning_branch}."
subtasks:
  - "T001"
  - "T002"
phase: "Phase 1 - Setup"
assignee: ""
agent: ""
shell_pid: ""
history:
  - timestamp: "2025-01-01T00:00:00Z"
    agent: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 \u2013 Work Package Title

[Content follows...]
```

## Status Tracking

Status is tracked via the canonical event log (`status.events.jsonl`), not in WP frontmatter.
Use `spec-kitty agent tasks move-task` to change WP status:

```bash
spec-kitty agent tasks move-task <WPID> --to <lane>
```

Example:
```bash
spec-kitty agent tasks move-task WP01 --to doing
```

## File Naming

- Format: `WP01-kebab-case-slug.md`
- Examples: `WP01-setup-infrastructure.md`, `WP02-user-auth.md`
"""


def render_tasks_readme_content(planning_branch: str) -> str:
    """Render tasks/README.md with branch-aware example frontmatter."""
    return TASKS_README_TEMPLATE.format(planning_branch=planning_branch)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _commit_feature_file(
    file_paths: tuple[Path, ...],
    mission_slug: str,
    artifact_type: str,
    repo_root: Path,
    *,
    worktree_root: Path | None = None,
    create_time_target: CommitTarget | None = None,
    owned: OwnedCreateMission | None = None,
) -> None:
    """Commit one or more create-owned artifacts in ONE transactional commit.

    This is a slim, typer-free version of the ``_commit_to_branch`` helper
    in the CLI module. It delegates straight to ``safe_commit`` with no
    try/except of its own, so it raises on BOTH a hard git failure and an
    empty changeset (``safe_commit`` itself raises ``RuntimeError`` when
    there is nothing to commit -- it does NOT silently no-op). Callers that
    know their changeset is always non-empty (e.g. the FR-001 create-scaffold
    commit call site, where the files genuinely differ from HEAD at create
    time) can safely treat any raise here as a hard failure.

    #2693: ``file_paths`` is a tuple so the whole create-owned generated set
    (``meta.json`` + ``status.events.jsonl`` + ``tasks/README.md`` +
    ``tasks/.gitkeep``) lands in a SINGLE commit rather than committing
    ``meta.json`` alone and leaving the rest untracked. ``safe_commit`` stages
    exactly these paths, so the commit is transactionally complete over the
    set the caller owns.

    coord-primary-partition-lock WP02 (T007 / C-001 / C-006): the commit
    destination is derived from ``placement_seam(...).write_target(SPEC)``,
    NOT from the operator's current checkout. Pre-fix this constructed
    ``CommitTarget(ref=current_branch)`` directly, which is the create-time
    split-brain root (research.md D5) -- under a coord-routing mission whose
    resolved ``target_branch`` differs from the checkout, the metadata commit
    silently landed on whatever branch the operator happened to be parked on
    instead of the mission's actual primary home. ``SPEC`` is a
    ``_PRIMARY_ARTIFACT_KINDS`` member (same as ``PRIMARY_METADATA``, the kind
    the committed ``meta.json`` file itself belongs to): both resolve to the
    identical primary ``target_branch`` for every topology, so this is a pure
    derivation-source fix (seam vs. checkout), not a placement change.
    """
    if get_current_branch(repo_root) is None:
        raise MissionCreationError("Not in a git repository")

    # Mission creation runs pre-spec: the destination is the branch ``create``
    # reports (the planning destination), which is a non-protected planning
    # branch. Capability is STANDARD — the placement-matched commit needs no
    # protected-branch bookkeeping authorization. If a project legitimately
    # plans on a protected branch, WP05's placement projection routes the
    # commit; this caller does not duplicate that decision (T010).
    commit_msg = f"Add {artifact_type} for feature {mission_slug}"
    effective_worktree = worktree_root or repo_root
    seam_target = create_time_target if create_time_target is not None else placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.SPEC)
    safe_commit(
        repo_root=repo_root,
        worktree_root=effective_worktree,
        target=seam_target,
        message=commit_msg,
        paths=file_paths,
        capability=GuardCapability.STANDARD,
        # Owned create: the mission-scoped commit_to_target fold reads the new
        # mission from the validated create fact, never the repository root.
        owned=owned,
    )


# ---------------------------------------------------------------------------
# Failure-atomic git rollback (WP12 / FR-011 / #3339)
# ---------------------------------------------------------------------------


def _list_coordination_branches(repo_root: Path) -> frozenset[str]:
    """Return the local ``kitty/mission-*`` branch names in ``repo_root``.

    Used to diff the coordination branches present before vs after a
    mission-create so the rollback deletes exactly the ref an aborted create
    minted, never a pre-existing one. A non-git or failing ``git`` invocation
    yields an empty set (nothing to roll back).
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "branch",
            "--list",
            _COORDINATION_BRANCH_GLOB,
            "--format=%(refname:short)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def _rev_parse_or_none(repo_root: Path, ref: str) -> str | None:
    """Return ``ref``'s commit SHA in ``repo_root``, or ``None`` on any failure."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _list_mission_scaffolds(repo_root: Path) -> frozenset[str]:
    """Return the mission directory names currently under ``kitty-specs/``.

    Mirrors :func:`_list_coordination_branches`: diffing this before vs after a
    create identifies exactly the scaffold an aborted run wrote, never a
    pre-existing mission. A missing ``kitty-specs/`` yields an empty set.
    """
    specs_root = repo_root / KITTY_SPECS_DIR
    try:
        return frozenset(entry.name for entry in specs_root.iterdir() if entry.is_dir())
    except OSError:
        return frozenset()


# Directory-name suffix for the canonical ``<human-slug>-<mid8>`` mission-dir
# grammar (mirrors the matching convention already used by
# ``_plan_orphan_scaffold_removal`` below). Captures the mid8 so the guard's
# refusal message can name it without a second (possibly-failing) meta.json
# read (FR-002).
_MID8_DIR_SUFFIX_PATTERN = r"-([0-9A-Za-z]{8})"


def _prior_mission_is_abandoned(repo_root: Path, feature_dir: Path) -> bool:
    """Classify a same-key prior mission as abandoned (#4033 research.md D-2).

    Abandoned = canceled (every recorded work package sits in the
    ``CANCELED`` lane), OR genesis / no lifecycle progress -- the status
    event log carries zero work-package transitions AND the spec was never
    committed to git, i.e. the prior mission was never actually worked, so a
    re-create should just succeed with no flag (FR-003).

    The genesis facet requires BOTH signals together, not either alone: a
    prior mission with a committed spec but no work packages yet (still in
    the specify/plan phase) is real, live work -- exactly the #4033 repro
    (a same-key create run twice back to back) -- and must still be refused,
    while a bare, never-touched scaffold (spec.md left uncommitted, no WP
    ever seeded) is the common "gave up and re-ran" case and must auto-allow.

    Fail closed (C-002): any status-log read failure means abandonment
    cannot be established, so this returns ``False`` (treated as LIVE) and
    the guard refuses rather than silently allowing a duplicate.
    """
    from specify_cli.status import Lane, StoreError, materialize_snapshot

    try:
        snapshot = materialize_snapshot(feature_dir)
    except StoreError:
        return False

    work_packages = snapshot.work_packages
    if work_packages and all(wp_state.get("lane") == Lane.CANCELED.value for wp_state in work_packages.values()):
        return True  # canceled: every recorded work package was called off

    # genesis / no lifecycle progress: zero WP transitions AND spec never committed.
    return snapshot.event_count == 0 and not _path_is_tracked_by_git(repo_root, feature_dir / "spec.md")


def _find_live_duplicate_mission(
    repo_root: Path,
    *,
    mission_slug: str,
    mission_type: str,
) -> tuple[str, str] | None:
    """Find a live same-key prior mission, if any (#4033 idempotency guard).

    Duplicate key = same base ``mission_slug`` (mid8 stripped, FR-001) AND
    same ``mission_type`` read from the candidate's ``meta.json``. A
    ``research`` and a ``software-dev`` mission sharing a name are not a
    duplicate (edge case in spec.md).

    Returns ``(dir_name, mid8)`` for the first live match, or ``None`` when
    no same-key prior mission exists or every one is abandoned (see
    :func:`_prior_mission_is_abandoned`).

    Fail closed (C-002): a same-slug candidate whose ``meta.json`` is
    missing or corrupt is treated as LIVE -- its type/abandonment cannot be
    established, so refusing is the safe default. An explicit
    ``--allow-duplicate`` always overrides this guard regardless.
    """
    base_slug = strip_numeric_prefix(mission_slug)
    suffix_pattern = re.compile(re.escape(base_slug) + _MID8_DIR_SUFFIX_PATTERN + "$")

    for name in sorted(_list_mission_scaffolds(repo_root)):
        match = suffix_pattern.fullmatch(name)
        if name != base_slug and match is None:
            continue
        candidate_mid8 = match.group(1) if match is not None else ""
        candidate_dir = repo_root / KITTY_SPECS_DIR / name

        try:
            candidate_meta = load_meta_fail_closed(candidate_dir)
        except MissionMetaReadError:
            return (name, candidate_mid8)  # fail closed: unreadable meta.json
        if candidate_meta is None:
            return (name, candidate_mid8)  # fail closed: missing meta.json

        candidate_type = str(candidate_meta.get(_META_KEY_MISSION_TYPE) or "software-dev")
        if candidate_type != mission_type:
            continue  # different mission_type: not a duplicate key

        if not candidate_mid8:
            candidate_mid8 = str(candidate_meta.get("mid8") or "")

        if _prior_mission_is_abandoned(repo_root, candidate_dir):
            continue  # abandoned prior: auto-allow (FR-003), no flag needed

        return (name, candidate_mid8)

    return None


class MissionBranchExistsError(MissionCreationError):
    """Raised when the deterministically-composed mission branch already exists.

    #5100 FR-007 (WP08): a protected-target ``single_branch`` mission mints
    ``kitty/mission-<slug>-<mid8>`` and refuses outright rather than reusing
    or recreating a same-named branch -- an existing branch under that exact
    name could hold unrelated content (a stale branch from a prior, deleted
    mission whose mid8 happened to collide, or an operator's own local
    branch), and silently checking it out would corrupt the mission's history.
    """

    error_code: str = "MISSION_BRANCH_EXISTS"


def _refuse_target_without_commit(write_root: Path, target_branch: str) -> None:
    """Refuse a protected mint whose *target_branch* names no commit (#5100 WP08 follow-up).

    The mission branch forks from the target's tip, so a target that resolves to
    no commit -- never created, or the operator's still-unborn default branch
    while this checkout sits on another -- cannot be minted from. (An unborn
    HEAD in the write checkout itself is refused earlier by
    :func:`_create_mission_core_impl`'s #4033 guard.) Raise an actionable
    :class:`MissionCreationError` naming the target BEFORE any ref or meta
    mutation, instead of surfacing git's raw "'<target>' is not a commit".
    """
    probe = subprocess.run(
        ["git", "-C", str(write_root), "rev-parse", "--verify", "--quiet", f"{target_branch}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        return
    raise MissionCreationError(
        f"Cannot mint the protected-target mission branch: target branch {target_branch!r} "
        f"has no commit in {write_root} (it does not exist yet, or is still unborn). "
        f"Create it with at least one commit (for example: git branch {target_branch} <start-point>), "
        "or pass --target-branch naming an existing branch, then retry."
    )


def _target_is_protected(write_root: Path, target_branch: str) -> bool:
    """True when *target_branch* is a protected target under the #5100 rule (C-002).

    The ONE protection decision the protected single_branch mint and the
    create-time re-create refusal both consult (:func:`_protected_mint_applies`).
    """
    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy.resolve(write_root)
    # bias=False (mission_branch_context._resolve_primary_branch_for_recommendation's
    # rationale applies verbatim here): the CURRENT checkout is virtually
    # ALWAYS the target branch at create time (single_branch missions are
    # created from wherever the operator is standing), so the default
    # feature-bias resolution would treat EVERY target as "primary" and mint
    # unconditionally. The genuine repository primary (main/master/origin
    # default) is what the #5100 rule means by "primary".
    primary_branch = resolve_primary_branch(write_root, bias=False)
    return bool(policy.is_protected_target(target_branch, primary_branch=primary_branch))


def _protected_mint_applies(
    write_root: Path,
    *,
    topology: MissionTopology,
    commit_to_target: bool,
    target_branch: str,
) -> bool:
    """True when create will mint a protected-target mission branch (#5100 WP08).

    Only then does a re-create of an already-scaffolded mission collide on the
    deterministic mission branch (same slug + mid8), so only then must the
    re-create be refused up front as MISSION_ALREADY_EXISTS rather than surface
    the mint's MISSION_BRANCH_EXISTS. Every other shape keeps origin/main's
    idempotent resume (the #4033 guard already refuses a LIVE duplicate).
    """
    if topology is not MissionTopology.SINGLE_BRANCH or commit_to_target:
        return False
    return _target_is_protected(write_root, target_branch)


def _mint_protected_single_branch_mission_branch(
    write_root: Path,
    mission_slug_formatted: str,
    *,
    mission_id: str,
    target_branch: str,
    meta: dict[str, Any],
) -> None:
    """Mint + check out the mission branch for a protected single_branch target.

    #5100 FR-007/FR-012 (WP08 / IC-05, research.md R-5/R-8). A no-op unless
    the target is protected under the #5100 "primary plus configured" rule
    (:meth:`~specify_cli.git.protection_policy.ProtectionPolicy.is_protected_target`,
    C-002: the single protection authority). When it fires:

    1. Refuses if the write checkout (*write_root*) has uncommitted
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
    only happen after both refusal checks pass).
    """
    if not _target_is_protected(write_root, target_branch):
        return
    _refuse_target_without_commit(write_root, target_branch)

    # This mission's own (still-untracked) scaffold is never "dirty" here --
    # only the operator's unrelated uncommitted work is. A bidirectional
    # component-wise overlap (unlike ``lanes.checkout_occupancy.dirty_paths``'s
    # one-directional ``_is_owned_path``) is required: on a freshly-scaffolded
    # ``kitty-specs/`` (this mission is the first ever created), git's default
    # ``--untracked-files=normal`` collapses the whole new directory to the
    # single line ``kitty-specs/`` -- an ANCESTOR of, not a match for, the
    # mission-scoped path below.
    owned_paths = (GitPath.parse(".kittify"), GitPath.parse(f"{KITTY_SPECS_DIR}/{mission_slug_formatted}"))
    dirty: list[str] = []
    # Guard: a failed ``git status`` raises ``GitCommandError`` (a ``RuntimeError``,
    # as the helper this replaces raised) rather than reading as "clean".
    for entry in status_entries(write_root, untracked=None):
        if any(owned.overlaps(entry.path) for owned in owned_paths):
            continue
        dirty.append(str(entry.path))
    if dirty:
        raise MissionCreationError(
            "Cannot mint the protected-target mission branch: the write "
            f"checkout at {write_root} has uncommitted changes outside "
            f"this mission's own scaffold: {', '.join(dirty)}. Commit or "
            "discard them, then retry."
        )

    branch_name = mission_branch_name(mission_slug_formatted, mission_id=mission_id)
    exists = (
        subprocess.run(
            ["git", "-C", str(write_root), "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if exists:
        raise MissionBranchExistsError(
            f"Mission branch {branch_name!r} already exists. Choose a "
            "different mission slug, remove the stale branch, or pass "
            "--commit-to-target to commit directly onto the target."
        )

    create_result = subprocess.run(
        ["git", "-C", str(write_root), "checkout", "-b", branch_name, target_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if create_result.returncode != 0:
        detail = (create_result.stderr or create_result.stdout or "").strip()
        raise MissionCreationError(f"Failed to create and check out mission branch {branch_name!r} from {target_branch!r}: {detail}")
    meta["mission_branch"] = branch_name


def _path_is_tracked_by_git(repo_root: Path, path: Path) -> bool:
    """True when git tracks any file under ``path``.

    Ordinary early refusals precede staging. A late refusal can follow the
    first scaffold commit, however, so preserve any indexed content. Refuse
    deletion whenever Git cannot establish that the path is disposable.
    """
    try:
        return bool(tracked_paths(repo_root, pathspecs=(str(path),)))
    except GitCommandError:
        # Refuse deletion whenever Git cannot establish that the path is disposable.
        return True


def _failure_is_disposable_create_refusal(exc: BaseException) -> bool:
    """Recognize commit preconditions whose recovery permits another create.

    Protection, checkout mismatch, and missing destination normally fail at
    preflight. Repeat checks at commit time can still refuse, so clean up only
    their new, untracked scaffolds. Persistence failures retain their explicit
    resume-probe evidence. Both scaffold and origin commits wrap exceptions;
    inspect their causes rather than only the surface type.
    """
    from specify_cli.git.commit_helpers import (
        ProtectedBranchRefused,
        SafeCommitDestinationNotFound,
        SafeCommitHeadMismatch,
    )

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, (ProtectedBranchRefused, SafeCommitHeadMismatch, SafeCommitDestinationNotFound)):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _plan_orphan_scaffold_removal(
    repo_root: Path,
    *,
    mission_slug: str,
    pre_existing_scaffolds: frozenset[str],
) -> tuple[Path, ...]:
    """Decide which scaffolds a failed create may delete — BEFORE any rollback.

    Rollback restores the original index as well as the branch ref. The index
    check must happen first, before it forgets files indexed by this create.
    """
    mission_slug = strip_numeric_prefix(mission_slug)
    removable: list[Path] = []
    for name in sorted(_list_mission_scaffolds(repo_root) - pre_existing_scaffolds):
        # ``mission_slug_formatted`` is ``<slug>-<mid8>``, so match the stem and
        # never a same-prefixed neighbour ("task-list" must not match
        # "task-list-api-01ABCDEF").
        if name != mission_slug and not re.fullmatch(re.escape(mission_slug) + r"-[0-9A-Za-z]{8}", name):
            continue
        candidate = repo_root / KITTY_SPECS_DIR / name
        if _path_is_tracked_by_git(repo_root, candidate):
            continue
        removable.append(candidate)
    return tuple(removable)


def _remove_orphan_mission_scaffolds(planned: tuple[Path, ...]) -> None:
    """Remove only the disposable scaffolds identified before git rollback.

    Main's skipped bootstrap commits are successful creations and never reach
    this cleanup. An actual aborted create must not leave a second, untracked
    mission on retry. Indexed content and diagnostic failures are retained.
    Deletion is best-effort and must never mask the original failure.
    """
    for candidate in planned:
        with contextlib.suppress(OSError):
            shutil.rmtree(candidate)


@dataclass(frozen=True, slots=True)
class _CoordCreateRollbackContext:
    """Snapshot T032/FR-002a needs to undo a coordination surface a failed create produced.

    ``mission_slug_formatted`` and ``mid8`` are minted inside
    ``_create_mission_core_impl`` (brownfield scout, "Rollback (top risk)"),
    so the outer ``create_mission_core`` wrapper cannot name the coordination
    worktree any other way. The impl populates this through the mutable
    holder list the outer function passes in, as soon as the coordination
    branch name is known (right after ``_build_create_meta`` returns) --
    before the seed or the creation-events commit can fail.
    """

    #: The REPOSITORY root -- the coordination worktree always lives under it
    #: (``<repo_root>/.worktrees/...``), never under an owned checkout, so
    #: this is carried explicitly rather than reusing the caller's rollback
    #: root (which is the owned checkout for an owned create).
    repo_root: Path
    mission_slug_formatted: str
    mid8: str
    coordination_branch: str
    #: ``True`` when THIS create minted (or force-recreated) the branch --
    #: safe to delete on rollback. ``False`` means a pre-existing branch was
    #: silently reused (idempotent re-run); rollback must CAS-reset it to
    #: ``pre_seed_coord_tip`` instead of deleting another create's branch.
    coordination_branch_created: bool
    #: The branch's tip immediately after ``ensure_coordination_branch``
    #: returned, before this create's own seed/creation-events commit could
    #: move it. ``None`` when the branch did not exist yet (always true when
    #: ``coordination_branch_created`` is ``True``).
    pre_seed_coord_tip: str | None = None


def _rollback_coordination_surface(ctx: _CoordCreateRollbackContext) -> None:
    """Best-effort: undo the coordination worktree/branch a failed create produced (T032/US1.5).

    Never raises — a failure here must not mask the original creation
    failure. The worktree is torn down BEFORE the branch is touched, because
    git refuses to delete (or reset, while checked out) a branch that is
    checked out in a worktree.

    Every byte the coordination worktree holds at this point was written by
    THIS create (the seed and/or the creation-events commit — or nothing, if
    the failure struck before either ran): clearing the Mission dir before
    teardown is therefore sanctioned (D6), not a destructive-guard bypass —
    ``CoordinationWorkspace.teardown`` refuses a dirty worktree, and the
    untracked seed content left behind by an interrupted create would
    otherwise orphan the worktree forever.
    """
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    repo_root = ctx.repo_root
    coord_mission_dir = coord_feature_dir(repo_root, ctx.mission_slug_formatted, ctx.mid8)
    if coord_mission_dir.exists():
        with contextlib.suppress(OSError):
            shutil.rmtree(coord_mission_dir)
    with contextlib.suppress(Exception):
        # The single shared teardown seam; a half-created mission has no retrospective to persist,
        # and the surface being discarded is this create's own, so the ledger guard is skipped.
        teardown_coordination_topology(repo_root, ctx.mission_slug_formatted, ctx.mid8, persist=False, check_ledger=False)
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "prune"],
        capture_output=True,
        text=True,
        check=False,
    )
    if ctx.coordination_branch_created:
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", "-D", ctx.coordination_branch],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    if ctx.pre_seed_coord_tip is None:
        return
    current_tip = _rev_parse_or_none(repo_root, ctx.coordination_branch)
    if current_tip and current_tip != ctx.pre_seed_coord_tip:
        # A pre-existing coordination branch this create reused is CAS-reset
        # to its own pre-create tip, never deleted (it may belong to another
        # mission's history, e.g. a prior ``force_recreate`` run).
        with contextlib.suppress(RefRestoreError):
            restore_branch_ref(
                repo_root,
                ctx.coordination_branch,
                ctx.pre_seed_coord_tip,
                expected_current_sha=current_tip,
            )


def _restore_git_state_after_failed_create(
    repo_root: Path,
    *,
    original_branch: str | None,
    original_commit: str | None,
    original_index_tree: str | None,
    pre_existing_coordination_branches: frozenset[str],
    coord_rollback: _CoordCreateRollbackContext | None = None,
) -> None:
    """Best-effort rollback of a failed mission-create's git side-effects.

    Restores the operator's original checkout and deletes any coordination
    branch this create-run minted (FR-011, #3339), so a failed create leaves
    the operator on their original branch with no orphan branch.
    ``coord_rollback`` (T032/FR-002a), when supplied, additionally tears down
    the coordination worktree this create materialized before any branch is
    touched — see :func:`_rollback_coordination_surface`.

    Rollback is best-effort and never raises — it must not mask the original
    creation failure. The checkout is restored *before* any branch delete
    because git refuses to delete a branch that is currently checked out.

    Single-writer assumption: mission-create is an operator action, so the
    coordination-branch diff (present now minus present before) identifies
    exactly the ref this call minted.
    """
    # 1. Restore the operator's checkout first (a checked-out branch cannot be
    #    deleted).
    if original_branch is not None:
        current = get_current_branch(repo_root)
        if current is not None and current != original_branch:
            subprocess.run(
                ["git", "-C", str(repo_root), "checkout", original_branch],
                capture_output=True,
                text=True,
                check=False,
            )
        if original_commit is not None:
            current_tip_result = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            current_tip = current_tip_result.stdout.strip() if current_tip_result.returncode == 0 else None
            if current_tip and current_tip != original_commit:
                # A late failure can occur after the metadata commit. Restore
                # only this branch ref with compare-and-swap; keep the partial
                # scaffold in the worktree for resume-probe diagnosis.
                with contextlib.suppress(RefRestoreError):
                    restore_branch_ref(
                        repo_root,
                        original_branch,
                        original_commit,
                        expected_current_sha=current_tip,
                    )
            if original_index_tree is not None:
                # Restore the exact pre-invocation index, including unrelated
                # staged user changes, without touching worktree files.
                subprocess.run(
                    ["git", "-C", str(repo_root), "read-tree", original_index_tree],
                    capture_output=True,
                    text=True,
                    check=False,
                )
    # 1.5. Undo the coordination worktree (and, for a branch THIS create
    #      minted, the branch too) before the generic branch-diff sweep below
    #      -- git refuses to delete a branch still checked out in a worktree.
    if coord_rollback is not None:
        _rollback_coordination_surface(coord_rollback)
    # 2. Delete only the coordination branches that appeared during this create.
    orphaned = _list_coordination_branches(repo_root) - pre_existing_coordination_branches
    for branch in sorted(orphaned):
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", "-D", branch],
            capture_output=True,
            text=True,
            check=False,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_mission_core(
    repo_root: Path | None,
    mission_slug: str,
    *,
    mission: str | None = None,
    target_branch: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    pr_bound: bool = False,
    topology: MissionTopology = MissionTopology.COORD,
    force_recreate_coordination_branch: bool = False,
    allow_worktree_context: bool = False,
    owned_create_root: OwnedCreateRoot | None = None,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
) -> MissionCreationResult:
    """Create a new mission, restoring git state if creation fails (FR-011).

    Failure-atomic wrapper around :func:`_create_mission_core_impl`. It captures
    the operator's branch/checkout, the pre-existing coordination branches, and
    the pre-existing ``kitty-specs/`` scaffolds *before* any mutation. On ANY
    failure it restores the original checkout, deletes the orphan coordination
    branch the aborted run minted (#3339). Disposable commit refusals also
    remove newly created untracked scaffolds; diagnostic failures retain them.
    See :func:`_create_mission_core_impl` for the full parameter contract.
    """
    # An explicit owned checkout is the write/commit surface. Snapshot that
    # checkout rather than the canonical primary so a late failure restores
    # the branch ref and index that this invocation actually mutated.
    rollback_root = owned_create_root.checkout if owned_create_root is not None else repo_root
    if rollback_root is None:
        rollback_root = locate_project_root()
    original_branch: str | None = None
    original_commit: str | None = None
    original_index_tree: str | None = None
    pre_existing_coordination_branches: frozenset[str] = frozenset()
    pre_existing_scaffolds: frozenset[str] = frozenset()
    if rollback_root is not None:
        # Snapshot the scaffold set even when the path is not a git repo: the
        # scaffold is written to disk regardless, so the orphan is possible
        # regardless (#4035).
        pre_existing_scaffolds = _list_mission_scaffolds(rollback_root)
    if rollback_root is not None and is_git_repo(rollback_root):
        original_branch = get_current_branch(rollback_root)
        original_commit_result = subprocess.run(
            ["git", "-C", str(rollback_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if original_commit_result.returncode == 0:
            original_commit = original_commit_result.stdout.strip()
        original_index_result = subprocess.run(
            ["git", "-C", str(rollback_root), "write-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if original_index_result.returncode == 0:
            original_index_tree = original_index_result.stdout.strip()
        pre_existing_coordination_branches = _list_coordination_branches(rollback_root)

    # T032/FR-002a: ``_create_mission_core_impl`` mints ``mission_slug_formatted``
    # and ``mid8`` internally, so this mutable holder is how it reports the
    # coordination surface it materialized back to this failure-atomic wrapper
    # -- populated as soon as the coordination branch name is known, before
    # the seed or the creation-events commit can fail.
    coord_rollback_holder: list[_CoordCreateRollbackContext] = []
    try:
        return _create_mission_core_impl(
            repo_root,
            mission_slug,
            mission=mission,
            target_branch=target_branch,
            friendly_name=friendly_name,
            purpose_tldr=purpose_tldr,
            purpose_context=purpose_context,
            pr_bound=pr_bound,
            topology=topology,
            force_recreate_coordination_branch=force_recreate_coordination_branch,
            allow_worktree_context=allow_worktree_context,
            owned_create_root=owned_create_root,
            retain_branches=retain_branches,
            retain_worktrees=retain_worktrees,
            commit_to_target=commit_to_target,
            allow_duplicate=allow_duplicate,
            _coord_rollback_holder=coord_rollback_holder,
        )
    except BaseException as _create_exc:
        # Re-raised below; the rollback is pure cleanup and must not swallow or
        # replace the original failure (that is why we re-raise unconditionally).
        if rollback_root is not None:
            # Plan before rollback restores the index and branch ref; indexed
            # scaffold content must remain available for diagnosis.
            planned_scaffold_removal: tuple[Path, ...] = ()
            if _failure_is_disposable_create_refusal(_create_exc):
                planned_scaffold_removal = _plan_orphan_scaffold_removal(
                    rollback_root,
                    mission_slug=mission_slug,
                    pre_existing_scaffolds=pre_existing_scaffolds,
                )
            _restore_git_state_after_failed_create(
                rollback_root,
                original_branch=original_branch,
                original_commit=original_commit,
                original_index_tree=original_index_tree,
                pre_existing_coordination_branches=pre_existing_coordination_branches,
                coord_rollback=coord_rollback_holder[0] if coord_rollback_holder else None,
            )
            # #4035: git state alone is not the whole side effect. On a
            # disposable commit refusal the on-disk scaffold outlives the failed
            # create and turns the documented recovery into a second mission,
            # so it goes too. Other failure classes keep theirs (see
            # ``_failure_is_disposable_create_refusal``).
            _remove_orphan_mission_scaffolds(planned_scaffold_removal)
        raise


def _validate_create_inputs(mission_slug: str, friendly_name: str | None) -> str:
    """Validate ``mission_slug``/``friendly_name`` and return the resolved friendly name.

    Section 1 of the pre-decomposition body (FR-026 / T051): the kebab-case
    slug check, the explicitly-empty-``friendly_name`` refusal, and the
    default-to-``default_mission_display_name(mission_slug)`` fallback. The
    fallback is a pure computation with no observable side effect before it,
    so folding it in here (rather than leaving it at its original later call
    site) does not change what raises or when.
    """
    if not KEBAB_CASE_PATTERN.match(mission_slug):
        raise MissionCreationError(
            f"Invalid feature slug '{mission_slug}'. "
            "Must be kebab-case (lowercase letters, numbers, hyphens only)."
            "\n\nValid examples:"
            "\n  - user-auth"
            "\n  - fix-bug-123"
            "\n  - 068-feature-name"
            "\n  - new-dashboard"
            "\n\nInvalid examples:"
            "\n  - User-Auth (uppercase)"
            "\n  - user_auth (underscores)"
        )

    friendly_name_was_provided = friendly_name is not None
    normalized_friendly_name = " ".join((friendly_name or "").split())
    if friendly_name_was_provided and not normalized_friendly_name:
        raise MissionCreationError("Mission creation requires a non-empty friendly_name.")
    if not normalized_friendly_name:
        normalized_friendly_name = default_mission_display_name(mission_slug)
    return normalized_friendly_name


@dataclass(frozen=True, slots=True)
class _CreateRoots:
    """Resolved roots + current branch for one ``create_mission_core`` call (T051).

    ``owned`` carries the caller-supplied, already-validated owned-checkout
    fact (WP02's :class:`OwnedCreateRoot`), or ``None`` for an unowned
    (repository root) create. Validation happens exactly once, in the
    caller that mints ``owned_create_root`` (FR-003 spirit); this function
    never re-validates a caller-supplied fact.
    """

    repository_root: Path
    write_root: Path
    owned: OwnedCreateRoot | None
    current_branch: str


def _resolve_create_roots(
    repo_root: Path | None,
    owned_create_root: OwnedCreateRoot | None,
    allow_worktree_context: bool,
) -> _CreateRoots:
    """Resolve the repository-root / write-root pair and validate context guards.

    Section 2 of the pre-decomposition body (FR-026 / T051; owned-checkout
    resolution re-expressed for FR-016 / T053, #5009 1f42f76ea; typed
    ``owned_create_root`` parameter T055): the worktree-context guard (skipped
    for an owned create, matching the pre-decomposition behaviour), the
    not-a-git-repo guard, the unborn-HEAD guard (checked against the WRITE
    root, since linked checkouts can have different HEAD states in the same
    repository), and the detached-HEAD guard. ``owned_create_root`` is minted
    ONCE by the caller through WP02's
    :func:`specify_cli.core.owned_mission.resolve_owned_create_root` -- which
    raises :class:`mission_runtime.ActionContextError` carrying the SAME error
    codes the pre-decomposition ``resolve_ownership_claim`` +
    ``error_for_claim`` call (a G1 floor offender) used to raise -- and is
    never re-validated here.
    """
    cwd = Path.cwd().resolve()
    resolved_root = repo_root

    if owned_create_root is None:
        if not allow_worktree_context and is_worktree_context(cwd):
            raise MissionCreationError("Cannot create missions from inside a worktree. Run from the project root checkout.")
        if resolved_root is None:
            resolved_root = locate_project_root()
    else:
        # HIGH-2 fix-cycle-1 regression repair: the already-validated fact is
        # the SINGLE source of the repository root on the owned path -- never
        # a caller-supplied `repo_root` left unresolved. Before this WP,
        # a supplied `repo_root` was `.resolve()`d before use; T055
        # accidentally left it as the caller's bare (possibly symlinked)
        # path when `repo_root` was not ``None``. Cross-check rather than
        # silently preferring one over the other: a caller-supplied
        # `repo_root` that resolves to a DIFFERENT path than the fact's own
        # `repository_root` is a caller bug (roots that disagree must never
        # be silently mixed) and fails closed.
        if resolved_root is not None and resolved_root.resolve() != owned_create_root.repository_root:
            raise MissionCreationError(
                f"Owned-create repository root mismatch: the supplied repo_root "
                f"({resolved_root.resolve()}) does not match the validated owned "
                f"checkout's repository root ({owned_create_root.repository_root})."
            )
        resolved_root = owned_create_root.repository_root

    if resolved_root is None:
        raise MissionCreationError("Could not locate project root. Run from within spec-kitty repository.")

    write_root = owned_create_root.checkout if owned_create_root is not None else resolved_root

    if not is_git_repo(resolved_root):
        raise MissionCreationError("Not in a git repository. Mission creation requires git.")
    # Every topology commits its scaffold. Inspect the selected write checkout:
    # linked checkouts can have different HEAD states in the same repository.
    if has_unborn_head(write_root):
        raise MissionCreationError(
            "This checkout has no commits yet, so Spec Kitty cannot commit the mission scaffold.\n\n"
            "Make an initial commit first, then create the mission:\n"
            "  git commit --allow-empty -m 'Initial commit'\n\n"
            "If the repository already has files staged, commit those instead."
        )

    current_branch = get_current_branch(write_root)
    if not current_branch or current_branch == "HEAD":
        raise MissionCreationError("Must be on a branch to create missions (detached HEAD detected).")

    return _CreateRoots(
        repository_root=resolved_root,
        write_root=write_root,
        owned=owned_create_root,
        current_branch=current_branch,
    )


def _refuse_live_duplicate(
    write_root: Path,
    mission_slug: str,
    mission: str | None,
    allow_duplicate: bool,
) -> None:
    """Idempotency guard (#4033, FR-001..004, C-001, C-002).

    Section 2.5 of the pre-decomposition body (T051): refuse a same-key (same
    base ``mission_slug`` AND same ``mission_type``) LIVE prior mission HERE
    -- before any scaffold/branch write (NFR-002: no orphan scaffold on
    refusal). "Live" excludes abandoned priors (canceled, genesis / no
    lifecycle progress, or spec never committed, see
    :func:`_prior_mission_is_abandoned`), so the common gave-up-and-re-ran
    path just works with no flag (FR-003).
    """
    if allow_duplicate:
        return
    effective_mission_type = mission or "software-dev"
    duplicate = _find_live_duplicate_mission(
        write_root,
        mission_slug=mission_slug,
        mission_type=effective_mission_type,
    )
    if duplicate is None:
        return
    duplicate_dir_name, duplicate_mid8 = duplicate
    raise MissionAlreadyExistsError(
        f"A mission named '{strip_numeric_prefix(mission_slug)}' of type "
        f"'{effective_mission_type}' already exists and is not "
        f"abandoned: {duplicate_dir_name} (mid8 {duplicate_mid8}). "
        "Refusing to silently create a duplicate (#4033).\n\n"
        "If the prior mission is genuinely abandoned (canceled, or "
        "never actually worked), re-run this create with no flag --"
        " abandoned priors are auto-allowed.\n\n"
        "To deliberately create a second mission with the same name, "
        "pass --allow-duplicate (create_mission_core(allow_duplicate=True)"
        " for programmatic callers)."
    )


@dataclass(frozen=True, slots=True)
class _Purpose:
    """Normalized, validated purpose fields for one create call (section 3, T051)."""

    tldr: str
    context: str


def _resolve_purpose(
    normalized_friendly_name: str,
    purpose_tldr: str | None,
    purpose_context: str | None,
    planning_branch: str,
) -> _Purpose:
    """Normalize and validate the purpose TL;DR/context (section 3, T051)."""
    normalized_purpose_tldr = " ".join((purpose_tldr or "").split()) if purpose_tldr is not None else normalized_friendly_name
    normalized_purpose_context = (
        " ".join((purpose_context or "").split()) if purpose_context is not None else default_mission_purpose_context(normalized_friendly_name, planning_branch)
    )
    purpose_errors = validate_purpose_summary(normalized_purpose_tldr, normalized_purpose_context)
    if purpose_errors:
        raise MissionCreationError(" ".join(purpose_errors))
    return _Purpose(tldr=normalized_purpose_tldr, context=normalized_purpose_context)


@dataclass(frozen=True, slots=True)
class _Governance:
    """Resolved mission-type context + spec template for one create call (section 4, T051)."""

    mission_type_context: Any
    spec_template: Any


def _resolve_create_governance(governance_root: Path, mission: str | None) -> _Governance:
    """Resolve the activated mission's spec template before any mission state exists.

    Section 4 of the pre-decomposition body (T051; FR-016 governance-root
    argument re-expressed by T053, #5009 1f42f76ea). A configuration failure
    must not leave a directory, metadata, or lifecycle events that look like
    a successful creation, so this runs before any create-side-effect helper.

    ``governance_root`` is the SINGLE root every read below uses: the
    validated owned checkout when the create is owned, the repository root
    checkout otherwise (FR-016) -- the validated write checkout owns charter
    and template configuration, and its activation may intentionally differ
    from the repository root checkout's.

    Fail-closed at the mission-create / mission-type-use boundary (WP04
    re-architecture): ``PackContext`` construction is now total (an absent
    or empty ``mission_type_activations`` key reads as ``frozenset()``
    without raising), so the actionable "provision your charter" error fires
    HERE, at the narrowest funnel every mission-create path passes through.
    """
    from charter.activation.mission_type_profiles import (
        existing_mission_types,
        resolve_mission_type_context,
    )
    from charter.activation.pack_context import CharterPackConfigError
    from specify_cli.runtime.resolver import resolve_configured_template

    if not existing_mission_types(governance_root):
        raise CharterPackConfigError(
            "This project has no activated mission types, so a mission cannot "
            "be created. A mission requires at least one activated mission "
            "type. Provision the project's charter: run `spec-kitty init` "
            "(new project) or `spec-kitty upgrade` (existing project), or add a "
            "non-empty `mission_type_activations` list to .kittify/config.yaml "
            "(or the charter.yaml it points to)."
        )

    selected_mission_type = mission or "software-dev"
    mission_type_context = resolve_mission_type_context(
        governance_root,
        mission_type=selected_mission_type,
    )
    spec_template = resolve_configured_template(
        "spec",
        governance_root,
        mission_type_context,
    )
    return _Governance(mission_type_context=mission_type_context, spec_template=spec_template)


@dataclass(frozen=True, slots=True)
class _Scaffold:
    """Paths written by the directory-creation + spec-template phase (sections 4/5, T051)."""

    feature_dir: Path
    scaffold_paths: tuple[Path, ...]
    tasks_readme: Path
    spec_file: Path
    #: The owned create root bound to ``feature_dir`` (``None`` for an unowned
    #: create): every create commit folds the mission-scoped protection hatch
    #: through this fact, never a re-derived repository root.
    owned_mission: OwnedCreateMission | None = None


def _scaffold_mission_dir(
    *,
    write_root: Path,
    resolved_root: Path,
    mission_slug_formatted: str,
    planning_branch: str,
    create_time_target: CommitTarget,
    spec_template: Any,
    owned: OwnedCreateRoot | None = None,
    topology: MissionTopology,
    commit_to_target: bool,
) -> _Scaffold:
    """Create the mission directory tree and the (uncommitted) spec.md scaffold.

    Sections 4 and 5 of the pre-decomposition body (T051): human-slug + mid8
    directory naming (FR-032/FR-044), the preflight commit-authority check
    (same authority as ``safe_commit``, so a bootstrap refusal is disclosed
    before any write), and the spec.md scaffold copy. ``spec.md`` is
    intentionally NOT committed here (#846): the agent commits it from
    ``/spec-kitty.specify`` once it holds substantive content.
    """
    feature_dir = write_root / KITTY_SPECS_DIR / mission_slug_formatted
    _refuse_protected_recreate(
        write_root,
        feature_dir,
        topology=topology,
        commit_to_target=commit_to_target,
        planning_branch=planning_branch,
    )
    owned_mission = owned.bind_mission(feature_dir) if owned is not None else None
    # D6 / T031: for a coordination-routed topology, ``status.events.jsonl``
    # (a COORD-partition kind) is never scaffolded on the target branch at
    # all -- the coordination surface carries it from birth (see
    # ``_materialize_and_commit_coord_create_events``). ``lanes`` /
    # ``single_branch`` keep today's root-checkout scaffolding byte-identical
    # (C-008).
    #
    # ``owned is None`` (review cycle 2, B5' ruling reversed): an OWNED
    # coordination-topology create is a supported, ratcheted path (FR-022,
    # ``TestFr022CoordinationTwin`` -- an owned sibling-checkout
    # ``create --topology lanes_with_coord`` followed by ``next`` must be a
    # non-error decision), NOT merely an operator override to refuse. An
    # ``OwnedCreateMission`` does not satisfy the ``mission_runtime.
    # OwnedCheckout`` contract ``placement_seam``/the coordination
    # write-location accessor require, so ``_seed_coord_surface_for_create``
    # already never seeds the coordination surface for an owned create
    # (``owned is not None`` short-circuits it to ``status_dir=None``) --
    # its ``MissionCreated``/``SpecifyStarted`` events land on
    # ``feature_dir`` in the owned checkout instead (``_emit_create_events``'s
    # own ``status_dir`` default). The scaffold step must therefore ALSO
    # treat an owned create as non-coordination-routed, so
    # ``status.events.jsonl`` is scaffolded AND included in the owned
    # checkout's own scaffold commit exactly as at base (``e7b085d26c``) --
    # otherwise it is written by the event emitter but never committed,
    # leaving the owned checkout with an uncommitted/untracked log. This is
    # a known, named residual (INV-COORD-HOME): an owned coordination
    # create's status log lives in the owned PRIMARY dir, never the
    # coordination surface -- follow-up tracked separately, not fixed here.
    from specify_cli.missions._create import topology_mints_coordination_branch

    is_coordination_routed = owned is None and topology_mints_coordination_branch(topology)
    scaffold_paths = (
        (feature_dir / "meta.json",)
        + (() if is_coordination_routed else (feature_dir / "status.events.jsonl",))
        + (feature_dir / "tasks" / "README.md", feature_dir / "tasks" / ".gitkeep")
    )
    # Validate before scaffold writes using the same authority as safe_commit.
    # Main permits these bootstrap refusals and discloses the uncommitted
    # scaffold; preserve that contract while rejecting other invalid targets.
    # The actual commit repeats validation, so this grants no stale authority.
    with contextlib.suppress(*_BOOTSTRAP_META_COMMIT_SKIPS):
        preflight_commit(
            repo_root=resolved_root,
            worktree_root=write_root,
            target=create_time_target,
            message=f"Add scaffold for mission {mission_slug_formatted}",
            paths=scaffold_paths,
            capability=GuardCapability.STANDARD,
            # Owned create: the mission-scoped fold reads the new mission's own
            # (not-yet-written) meta through the validated create fact, never
            # the repository root's copy (owned-checkout-lifecycle-authority).
            owned=owned_mission,
        )
    feature_dir.mkdir(parents=True, exist_ok=True)

    (feature_dir / "checklists").mkdir(exist_ok=True)
    (feature_dir / "research").mkdir(exist_ok=True)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    (tasks_dir / ".gitkeep").touch()

    # Initialize empty event log so the feature has canonical status from
    # birth -- ONLY for a non-coordination-routed create (``is_coordination_
    # routed`` already folds in ``owned is None`` above). An unowned
    # coordination-routed Mission's status log is seeded straight into the
    # coordination Mission dir instead (D6); touching one here would
    # resurrect #5440 by giving the target-branch scaffold commit a (now
    # stale, empty) copy to carry. An OWNED coordination-routed create keeps
    # today's root-checkout-shaped scaffolding (INV-COORD-HOME residual).
    if not is_coordination_routed:
        (feature_dir / "status.events.jsonl").touch(exist_ok=True)

    tasks_readme = tasks_dir / "README.md"
    tasks_readme.write_text(
        render_tasks_readme_content(planning_branch),
        encoding="utf-8",
    )

    spec_file = feature_dir / "spec.md"
    if not spec_file.exists():
        shutil.copy2(spec_template.path, spec_file)

    return _Scaffold(
        feature_dir=feature_dir,
        scaffold_paths=scaffold_paths,
        tasks_readme=tasks_readme,
        spec_file=spec_file,
        owned_mission=owned_mission,
    )


@dataclass(frozen=True, slots=True)
class _MetaBuild:
    """``meta.json`` contents plus the coordination-branch mint outcome (T051)."""

    meta: dict[str, Any]
    coordination_branch_created: bool
    # #5100 (6.7): the protected-target mission branch the mint checked out,
    # or ``None`` when no mint fired.
    minted_mission_branch: str | None = None
    # T031/T032 (coord-artifact-single-home-01M3V4BE): ``None`` unless
    # ``ensure_coordination_branch`` returned a ``skipped_reason`` (the
    # target branch does not resolve to a ref -- synthetic/test contexts).
    # When set, there is no real coordination branch to seed or write to;
    # the create-time seed step must fall through to the old PRIMARY path
    # rather than calling ``write_dir`` (which would otherwise raise
    # ``CoordinationBranchDeleted`` for a branch that was never minted).
    coordination_branch_skipped_reason: str | None = None
    # The coordination branch's tip right after ``ensure_coordination_branch``
    # returned -- before this create's own seed/creation-events commit can
    # move it. Used by T032 rollback to CAS-reset (never delete) a
    # pre-existing branch this create silently reused. ``None`` when the
    # branch was newly minted this run (``coordination_branch_created=True``)
    # or when there is no real coordination branch.
    coordination_branch_pre_seed_tip: str | None = None


def _build_create_meta(
    *,
    feature_dir: Path,
    mission_id: str,
    mid8: str,
    mission_slug_formatted: str,
    normalized_friendly_name: str,
    purpose: _Purpose,
    mission: str | None,
    planning_branch: str,
    pr_bound: bool,
    retain_branches: bool,
    retain_worktrees: bool,
    commit_to_target: bool,
    resolved_root: Path,
    write_root: Path,
    topology: MissionTopology,
    force_recreate_coordination_branch: bool,
) -> _MetaBuild:
    """Assemble, mint the coordination branch for, and persist ``meta.json``.

    Sections 6, 6.5 and 6.6 of the pre-decomposition body (T051): the
    canonical machine-facing identity fields, the create-time retention
    opt-in (#3131 FR-009, field-absent-unless-True), the per-mission
    coordination branch mint (WP03 / issue #1348, #2218 -- ONLY for the
    coordination-bearing shapes), and the topology corroboration (FR-002 /
    #2069, #2218): the operator's explicit choice is stored verbatim and
    only CORROBORATED (never re-derived) against the minted coordination
    state.
    """
    meta: dict[str, Any] = load_meta_or_empty(feature_dir)

    # Mint canonical machine-facing identity. The ULID was already generated
    # by the caller (needed for mid8 directory naming). The ULID is immutable
    # after creation. mission_number is null pre-merge; a dense display
    # number is assigned only at merge time (single-writer context on main).
    # See FR-044.
    meta.setdefault("mission_id", mission_id)
    # Backfill the canonical mid8 (first 8 chars of the ULID) so meta.json is
    # the single canonical identity source: the directory name already embeds
    # it, and any surface reading ``mid8`` from meta.json saw absence where
    # the value was knowable (#3474).
    meta.setdefault("mid8", mid8)
    meta.setdefault("mission_number", None)  # JSON null — pre-merge missions have no number
    meta.setdefault("slug", mission_slug_formatted)
    meta.setdefault("mission_slug", mission_slug_formatted)
    meta.setdefault("friendly_name", normalized_friendly_name)
    meta.setdefault("purpose_tldr", purpose.tldr)
    meta.setdefault("purpose_context", purpose.context)
    meta.setdefault(_META_KEY_MISSION_TYPE, mission or "software-dev")
    meta.setdefault("target_branch", planning_branch)
    meta.setdefault(_META_KEY_CREATED_AT, now_utc_iso())
    if pr_bound:
        meta["pr_bound"] = True
    if retain_branches:
        meta["retain_branches"] = True
    if retain_worktrees:
        meta["retain_worktrees"] = True
    # #5100 FR-008 (WP08): mirrors the retention pattern above -- mint ONLY
    # when True, never a written ``false``.
    if commit_to_target:
        meta["commit_to_target"] = True

    from specify_cli.missions._create import topology_mints_coordination_branch

    coordination_branch_created_flag = False
    coordination_branch_skipped_reason: str | None = None
    coordination_branch_pre_seed_tip: str | None = None
    if topology_mints_coordination_branch(topology):
        from specify_cli.missions._create import ensure_coordination_branch

        coordination_outcome = ensure_coordination_branch(
            repo_root=resolved_root,
            mission_slug=mission_slug_formatted,
            mission_id=mission_id,
            target_branch=planning_branch,
            force_recreate=force_recreate_coordination_branch,
        )
        coordination_branch_created_flag = coordination_outcome.created
        coordination_branch_skipped_reason = coordination_outcome.skipped_reason
        meta["coordination_branch"] = coordination_outcome.branch_name
        # T032: a reused (not-created-this-run) branch's tip, captured before
        # this create's own seed/creation-events commit can move it -- the
        # CAS-reset anchor if this create later fails.
        if coordination_outcome.skipped_reason is None and not coordination_branch_created_flag:
            coordination_branch_pre_seed_tip = _rev_parse_or_none(resolved_root, coordination_outcome.branch_name)

    from mission_runtime import classify_topology

    if topology in (MissionTopology.COORD, MissionTopology.SINGLE_BRANCH):
        corroborated = classify_topology(meta.get("coordination_branch") or None, has_lanes=False)
        if corroborated is not topology:
            raise MissionCreationError(
                f"Topology corroboration failed for '{mission_slug_formatted}': stored "
                f"'{topology.value}' but the minted coordination state classifies as "
                f"'{corroborated.value}'."
            )
    meta["topology"] = topology.value
    meta.setdefault("flattened", False)

    minted_mission_branch = _mint_protected_branch_for_topology(
        write_root,
        mission_slug_formatted,
        topology=topology,
        mission_id=mission_id,
        planning_branch=planning_branch,
        meta=meta,
    )

    from specify_cli.mission_metadata import set_documentation_state, write_meta

    write_meta(feature_dir, meta)

    if mission == "documentation":
        meta.setdefault(_META_KEY_MISSION_TYPE, "documentation")
        if "documentation_state" not in meta:
            doc_state: dict[str, Any] = {
                "iteration_mode": "initial",
                "divio_types_selected": [],
                "generators_configured": [],
                "target_audience": "developers",
                "last_audit_date": None,
                "coverage_percentage": 0.0,
            }
            set_documentation_state(feature_dir, doc_state)

    return _MetaBuild(
        meta=meta,
        coordination_branch_created=coordination_branch_created_flag,
        minted_mission_branch=minted_mission_branch,
        coordination_branch_skipped_reason=coordination_branch_skipped_reason,
        coordination_branch_pre_seed_tip=coordination_branch_pre_seed_tip,
    )


def _refuse_protected_recreate(
    write_root: Path,
    feature_dir: Path,
    *,
    topology: MissionTopology,
    commit_to_target: bool,
    planning_branch: str,
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
) -> str | None:
    """Step 6.7: protected-target mission branch (#5100 FR-007/FR-012, WP08 / IC-05).

    Mint and check out the mission branch BEFORE any mission file is committed:
    commit-router rule 3 refuses a coordination-less commit to a protected
    target, planning artifacts included, so a branch that did not exist until
    implement could never receive the spec, plan or tasks. Scoped to
    SINGLE_BRANCH only (COORD/LANES_WITH_COORD already mint their OWN,
    unconditional coordination branch; LANES keeps committing straight to
    target_branch per its own contract). Returns the minted branch name, or
    ``None`` when no mint fired.
    """
    if topology is not MissionTopology.SINGLE_BRANCH or read_commit_to_target(meta):
        return None
    _mint_protected_single_branch_mission_branch(
        write_root,
        mission_slug_formatted,
        mission_id=mission_id,
        target_branch=planning_branch,
        meta=meta,
    )
    minted_branch = meta.get("mission_branch")
    if isinstance(minted_branch, str) and minted_branch:
        return minted_branch
    return None


def _emit_create_events(
    *,
    feature_dir: Path,
    mission_slug_formatted: str,
    meta: dict[str, Any],
    planning_branch: str,
    resolved_root: Path,
    write_root: Path,
    purpose: _Purpose,
    normalized_friendly_name: str,
    spec_file: Path,
    lifecycle_root: Path | None = None,
    status_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Emit ``MissionCreated`` then ``SpecifyStarted`` to the local canonical log.

    ``lifecycle_root`` (WP13 item 6, out-of-map): the owned create root's
    ``repository_root`` when the create is owned, ``None`` otherwise. Passed as
    ``repo_root=`` to both emitters so the lifecycle log is written against the
    fact's repository root instead of re-deriving R from the owned checkout's
    path (``get_main_repo_root`` walk) after the claim was validated.

    ``status_dir`` (T031, coord-artifact-single-home-01M3V4BE): the directory
    ``status.events.jsonl`` is read from/written to. Defaults to
    ``feature_dir`` (every PRIMARY-partition caller: ``lanes`` /
    ``single_branch``, and ``spec.md``'s own relative-path computation below,
    which always uses ``write_root``/``spec_file`` -- never the status
    location). A coordination-routed create passes the coordination Mission
    dir here instead, so the creation events land on the coordination
    surface from birth (D6) while ``feature_dir`` keeps naming the PRIMARY
    scaffold directory for every other purpose.
    """
    status_dir = status_dir if status_dir is not None else feature_dir
    try:
        from specify_cli.identity.project import load_identity
        from specify_cli.status import (
            MISSION_CREATED,
            _resolve_local_actor,
            emit_mission_created_local,
            read_lifecycle_events,
        )

        _identity = load_identity(resolved_root / ".kittify" / "config.yaml")
        creation_actor = _resolve_local_actor()
        expected_created_payload = build_mission_created_payload(
            mission_slug=mission_slug_formatted,
            mission_id=meta.get("mission_id"),
            mission_number=None,
            mission_type=str(meta.get(_META_KEY_MISSION_TYPE) or "software-dev"),
            target_branch=planning_branch,
            wp_count=0,
            friendly_name=normalized_friendly_name,
            purpose_tldr=purpose.tldr,
            purpose_context=purpose.context,
            created_at=str(meta[_META_KEY_CREATED_AT]) if meta.get(_META_KEY_CREATED_AT) else None,
            actor=creation_actor,
        )
        created_event = emit_mission_created_local(
            status_dir,
            mission_slug=mission_slug_formatted,
            mission_id=meta.get("mission_id"),
            mission_number=None,
            mission_type=str(meta.get(_META_KEY_MISSION_TYPE) or "software-dev"),
            target_branch=planning_branch,
            wp_count=0,
            project_uuid=str(_identity.project_uuid) if _identity.project_uuid else None,
            project_slug=_identity.project_slug,
            friendly_name=normalized_friendly_name,
            purpose_tldr=purpose.tldr,
            purpose_context=purpose.context,
            created_at=str(meta[_META_KEY_CREATED_AT]) if meta.get(_META_KEY_CREATED_AT) else None,
            actor=creation_actor,
            fanout=False,
            repo_root=lifecycle_root,
        )
        created_events = [event for event in read_lifecycle_events(status_dir / "status.events.jsonl") if event.get("event_type") == MISSION_CREATED]
        if len(created_events) != 1:
            raise MissionCreationError(f"expected exactly one persisted MissionCreated event, found {len(created_events)}")
        persisted_created = created_events[0]
        if (
            persisted_created.get("aggregate_id") != meta.get("mission_id")
            or persisted_created.get("aggregate_type") != "Mission"
            or persisted_created.get("payload") != expected_created_payload
        ):
            raise MissionCreationError("persisted MissionCreated event does not match the canonical creation snapshot")
    except Exception as _local_evt_exc:  # noqa: BLE001
        raise MissionCreationError(
            "Local canonical MissionCreated persistence failed for "
            f"{mission_slug_formatted!r}: {_local_evt_exc}. The partial scaffold "
            "is retained for explicit resume-probe diagnosis; do not retry create "
            "until it is repaired or removed."
        ) from _local_evt_exc

    # Mission creation immediately scaffolds ``spec.md`` and opens the specify
    # phase. Record ``SpecifyStarted`` against the canonical local log so that
    # TeamSpace replay can show "currently specifying" before the agent
    # commits substantive spec content (which is where ``setup-plan`` later
    # emits ``SpecifyCompleted``). Without this event the canonical lifecycle
    # stream skips straight from ``MissionCreated`` to ``SpecifyCompleted``,
    # leaving the specify-phase entry point invisible to dashboards and
    # TeamSpace -- see issue #1067.
    phase_event: dict[str, Any] | None = None
    try:
        from specify_cli.status import (
            SPECIFY_STARTED,
            emit_artifact_phase_local,
        )

        phase_event = emit_artifact_phase_local(
            status_dir,
            event_type=SPECIFY_STARTED,
            mission_slug=mission_slug_formatted,
            actor="spec-kitty mission create",
            artifact_path=(str(spec_file.relative_to(write_root)) if spec_file.is_relative_to(write_root) else "spec.md"),
            repo_root=lifecycle_root,
        )
    except Exception as _phase_evt_exc:  # noqa: BLE001
        logger.debug(
            "Local SpecifyStarted persistence skipped for %s: %s",
            mission_slug_formatted,
            _phase_evt_exc,
        )

    return created_event, phase_event


@dataclass(slots=True)
class _CommitOutcome:
    """Outcome of the scaffold commit + pending-origin consumption (T051)."""

    scaffold_commit_skipped: bool
    origin_binding_attempted: bool
    origin_binding_succeeded: bool
    origin_binding_error: str | None
    meta: dict[str, Any]


def _commit_create_scaffold(
    *,
    scaffold: _Scaffold,
    resolved_root: Path,
    write_root: Path,
    create_time_target: CommitTarget,
    mission_slug_formatted: str,
    planning_branch: str,
    meta: dict[str, Any],
) -> _CommitOutcome:
    """Commit the scaffold, then consume + commit a pending origin binding.

    Sections 8.5, 9 and 9.5 of the pre-decomposition body (T051): ONE
    transactional commit for the create-owned generated set (#2693), then the
    ticket-first pending-origin consumption, then -- only on a successful
    bind -- a SECOND commit landing the updated ``origin_ticket`` subtree
    through the same sanctioned commit surface (squad follow-on to
    #2739/#2693), so the tree never sits modified-uncommitted after a
    successful origin bind.

    FR-001 (#3673): do NOT suppress -- a hard git failure must raise so
    ``create_mission_core``'s rollback
    (``_restore_git_state_after_failed_create``) fires. ``_commit_feature_file``
    calls ``safe_commit`` directly (no empty-changeset no-op); every path here
    genuinely differs from HEAD at create time, so the commit is non-empty.
    """
    scaffold_commit_skipped = False
    try:
        _commit_feature_file(
            scaffold.scaffold_paths,
            mission_slug_formatted,
            "scaffold",
            resolved_root,
            worktree_root=write_root,
            create_time_target=create_time_target,
            owned=scaffold.owned_mission,
        )
    except _BOOTSTRAP_META_COMMIT_SKIPS as exc:
        scaffold_commit_skipped = True
        logger.info(
            "Skipping bootstrap scaffold commit for %s on planning branch %s: %s",
            mission_slug_formatted,
            planning_branch,
            exc,
        )
    except SafeCommitStagedTreeUnchanged as exc:
        # #3861: a byte-identical scaffold already committed is the same
        # duplicate-mission signature the #4033 guard refuses pre-write (the
        # residual path the guard can allow through, e.g. ``allow_duplicate``
        # callers re-running with a frozen ``mission_id``). Surface the TYPED
        # already-exists signal, never the prose.
        raise MissionAlreadyExistsError(f"meta.json commit failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"meta.json commit failed: {exc}") from exc

    (
        origin_binding_attempted,
        origin_binding_succeeded,
        origin_binding_error,
        meta,
    ) = _consume_pending_origin_if_present(
        repo_root=resolved_root,
        feature_dir=scaffold.feature_dir,
        meta=meta,
    )

    if origin_binding_succeeded:
        meta_file = scaffold.feature_dir / "meta.json"
        try:
            _commit_feature_file(
                (meta_file,),
                mission_slug_formatted,
                "origin-ticket binding",
                resolved_root,
                worktree_root=write_root,
                create_time_target=create_time_target,
                owned=scaffold.owned_mission,
            )
        except _BOOTSTRAP_META_COMMIT_SKIPS as exc:
            scaffold_commit_skipped = True
            logger.info(
                "Skipping origin-ticket binding commit for %s on planning branch %s: %s",
                mission_slug_formatted,
                planning_branch,
                exc,
            )
        except Exception as exc:
            raise RuntimeError(f"origin-ticket binding commit failed: {exc}") from exc

    return _CommitOutcome(
        scaffold_commit_skipped=scaffold_commit_skipped,
        origin_binding_attempted=origin_binding_attempted,
        origin_binding_succeeded=origin_binding_succeeded,
        origin_binding_error=origin_binding_error,
        meta=meta,
    )


def _build_create_result(
    *,
    scaffold: _Scaffold,
    commit_outcome: _CommitOutcome,
    mission_slug_formatted: str,
    planning_branch: str,
    current_branch: str,
    coordination_branch_created: bool,
    resolved_root: Path,
    owned_create_root: OwnedCreateRoot | None,
    created_event: dict[str, Any],
    phase_event: dict[str, Any] | None,
    status_log_path: Path | None = None,
) -> MissionCreationResult:
    """Build the final result and fan out the local events (section 10, T051).

    Publishing happens after local creation has fully succeeded, including
    main's explicitly disclosed bootstrap skips: a hard scaffold/origin
    failure must leave no hosted events whose local authority was rolled
    back.

    ``status_log_path`` (T031): the ``status.events.jsonl`` a reader should
    follow for this create -- the coordination Mission dir's copy for an
    UNOWNED coordination-routed create (already committed separately, on the
    coordination branch, unconditionally), ``scaffold.feature_dir``'s for
    every other topology (unchanged, C-008) -- including an OWNED
    coordination-routed create (review cycle 2, B5' ruling reversed): the
    caller never passes a non-``None`` ``status_log_path`` for one (the
    coordination surface is never seeded when ``owned`` is set), but
    ``owned_create_root is None`` is checked explicitly here too, not only
    relied on transitively, so this function's own invariant holds even if a
    future caller's wiring drifts. Defaults to the latter.
    """
    is_coordination_routed = status_log_path is not None and owned_create_root is None
    log_path = status_log_path if status_log_path is not None else scaffold.feature_dir / "status.events.jsonl"
    meta_file = scaffold.feature_dir / "meta.json"
    created_files = [scaffold.spec_file, meta_file, scaffold.tasks_readme]
    if is_coordination_routed:
        created_files.append(log_path)
    uncommitted_files = [scaffold.spec_file]
    if commit_outcome.scaffold_commit_skipped:
        # The coordination log already committed separately (unconditionally,
        # outside the target scaffold commit's own bootstrap-skip handling,
        # T032), so a coordination-routed create's skipped-scaffold list never
        # repeats it here -- it was never part of the target scaffold tuple.
        skipped_scaffold = [meta_file, scaffold.tasks_readme, scaffold.feature_dir / "tasks" / ".gitkeep"]
        if not is_coordination_routed:
            skipped_scaffold.append(log_path)
        created_files.extend(path for path in skipped_scaffold if path not in created_files)
        uncommitted_files.extend(skipped_scaffold)

    from specify_cli.status import fanout_lifecycle_event_hosted

    if created_event is not None:
        fanout_lifecycle_event_hosted(created_event, log_path=log_path)
    if phase_event is not None:
        fanout_lifecycle_event_hosted(phase_event, log_path=log_path)

    return MissionCreationResult(
        feature_dir=scaffold.feature_dir,
        mission_slug=mission_slug_formatted,
        mission_number=None,  # pre-merge: no display number assigned (FR-044)
        meta=commit_outcome.meta,
        target_branch=planning_branch,
        current_branch=current_branch,
        created_files=created_files,
        uncommitted_files=uncommitted_files,
        origin_binding_attempted=commit_outcome.origin_binding_attempted,
        origin_binding_succeeded=commit_outcome.origin_binding_succeeded,
        origin_binding_error=commit_outcome.origin_binding_error,
        coordination_branch=commit_outcome.meta.get("coordination_branch"),
        coordination_branch_created=coordination_branch_created,
        owned_checkout=owned_create_root,
        canonical_repo_root=resolved_root,
    )


def _commit_coord_create_events(
    resolved_root: Path,
    mission_slug_formatted: str,
    mission_id: str,
    status_dir: Path,
) -> None:
    """Commit the just-emitted creation events onto the coordination branch (T031/D6/D4).

    Runs UNCONDITIONALLY for every coordination-routed create, even when the
    target scaffold commit itself is a disclosed bootstrap skip (T032,
    FR-002a) -- the coordination surface must carry ``MissionCreated`` +
    ``SpecifyStarted`` from birth regardless of what happens to the target
    branch. Raises (never silently swallows) on anything but a genuine
    commit or a benign already-committed no-op, so the outer failure-atomic
    wrapper's rollback (:func:`_rollback_coordination_surface`) runs.

    Carries the ONE shared seed-marker trailer (``COORD_SEED_TRAILER``, D4):
    this is one of the two commit kinds research decision D4 names as
    trailer-bearing (the other is a pre-fix Mission's carry-over seed commit,
    owned by ``coord_seed.py``), so a coordination branch this create minted
    is post-fix from birth and is never later mistaken for one needing the
    pre-fix carry-over seed.
    """
    from specify_cli.coordination.commit_outcome import STATUS_COMMITTED, STATUS_UNCHANGED
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.coordination.coord_seed import COORD_SEED_TRAILER
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy.resolve_for_mission(resolved_root, mission_slug_formatted)
    message = f"chore({mission_slug_formatted}): record mission creation\n\n{COORD_SEED_TRAILER}: {mission_id}"
    result = commit_for_mission(
        resolved_root,
        mission_slug_formatted,
        files=(status_dir / "status.events.jsonl",),
        message=message,
        policy=policy,
        kind=MissionArtifactKind.STATUS_STATE,
    )
    if result.status not in (STATUS_COMMITTED, STATUS_UNCHANGED):
        raise MissionCreationError(
            f"Failed to commit mission-creation events onto the coordination branch "
            f"for {mission_slug_formatted!r}: status={result.status!r} diagnostic={result.diagnostic!r}"
        )


@dataclass(frozen=True, slots=True)
class _CoordCreateSeed:
    """Where T031's create-time coordination seed landed, or that it did not run."""

    status_dir: Path | None
    rollback_ctx: _CoordCreateRollbackContext | None


def _seed_coord_surface_for_create(
    *,
    resolved_root: Path,
    mission_slug_formatted: str,
    mid8: str,
    topology: MissionTopology,
    meta_build: _MetaBuild,
    owned: OwnedCreateRoot | None,
    coord_rollback_holder: list[_CoordCreateRollbackContext] | None,
) -> _CoordCreateSeed:
    """T031 (D6): materialize + seed the coordination surface for a coordination-routed create.

    Runs ONLY for ``COORD`` / ``LANES_WITH_COORD`` -- ``lanes`` /
    ``single_branch`` return ``_CoordCreateSeed(None, None)`` unchanged
    (C-008). Two further guards keep this a no-op without crashing:

    * ``coordination_branch_skipped_reason`` is set -- ``ensure_coordination_branch``
      declined to mint a real branch (the target does not resolve to a ref;
      synthetic/test contexts). There is no coordination branch to seed.
    * ``owned`` is not ``None`` -- an owned create's ``OwnedCreateMission`` is
      not the ``mission_runtime.OwnedCheckout`` :func:`placement_seam` / the
      coordination write-location accessor require, so an owned
      coordination-routed create (a SUPPORTED path, FR-022's
      ``TestFr022CoordinationTwin`` ratchet -- review cycle 2, B5' ruling
      reversed) never seeds the coordination surface. Its ``MissionCreated``
      / ``SpecifyStarted`` events land on ``feature_dir`` in the owned
      checkout instead (``_emit_create_events``'s own ``status_dir``
      default), and ``_scaffold_mission_dir`` / ``_build_create_result``
      both ALSO gate their own coordination-routed branches on ``owned is
      None`` so that log is scaffolded AND committed in the owned checkout
      exactly as at base (``e7b085d26c``). This is a named residual
      (INV-COORD-HOME): an owned coordination create's status log lives in
      its own PRIMARY dir, never the coordination surface itself --
      follow-up tracked separately, not fixed here.

    ``coord_rollback_holder`` (review cycle 2 B2, HIGH): the context is
    appended to this mutable holder IMMEDIATELY after it is built, BEFORE
    :meth:`~mission_runtime.PlacementSeam.write_dir` is called below.
    ``write_dir`` can itself raise AFTER it has already materialized the
    coordination worktree and/or run the pre-fix seed (a seed failure,
    ``STATUS_LOCK_HELD``, a git-probe failure) -- appending only once this
    function RETURNS successfully would lose the rollback context for
    exactly the half-built-coordination-surface failure T032/US1.5 exists to
    prevent (the minted branch is then left orphaned: the generic rollback's
    ``git branch -D`` fails because the branch is still checked out in the
    worktree).
    """
    from specify_cli.missions._create import topology_mints_coordination_branch

    if not topology_mints_coordination_branch(topology):
        return _CoordCreateSeed(status_dir=None, rollback_ctx=None)
    coordination_branch = meta_build.meta.get("coordination_branch")
    if not isinstance(coordination_branch, str) or meta_build.coordination_branch_skipped_reason is not None:
        return _CoordCreateSeed(status_dir=None, rollback_ctx=None)
    rollback_ctx = _CoordCreateRollbackContext(
        repo_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        mid8=mid8,
        coordination_branch=coordination_branch,
        coordination_branch_created=meta_build.coordination_branch_created,
        pre_seed_coord_tip=meta_build.coordination_branch_pre_seed_tip,
    )
    if coord_rollback_holder is not None:
        coord_rollback_holder.append(rollback_ctx)
    if owned is not None:
        return _CoordCreateSeed(status_dir=None, rollback_ctx=rollback_ctx)
    location: WriteLocation = placement_seam(resolved_root, mission_slug_formatted, owned=None).write_dir(MissionArtifactKind.STATUS_STATE)
    return _CoordCreateSeed(status_dir=location.path, rollback_ctx=rollback_ctx)


def _create_mission_core_impl(
    repo_root: Path | None,
    mission_slug: str,
    *,
    mission: str | None = None,
    target_branch: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    pr_bound: bool = False,
    topology: MissionTopology = MissionTopology.COORD,
    force_recreate_coordination_branch: bool = False,
    allow_worktree_context: bool = False,
    owned_create_root: OwnedCreateRoot | None = None,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
    _coord_rollback_holder: list[_CoordCreateRollbackContext] | None = None,
) -> MissionCreationResult:
    """Create a new feature with all scaffolding.

    This is the programmatic API for feature creation.  Unlike the CLI
    command, it returns a structured result and raises domain exceptions
    instead of calling ``typer.Exit()``.

    Parameters
    ----------
    repo_root:
        Absolute path to the project root (must contain ``.kittify/`` and
        ``kitty-specs/``).  When *None*, ``locate_project_root()`` is called
        automatically.
    mission_slug:
        Bare slug such as ``"user-auth"`` or ``"068-feature"`` (kebab-case).
    mission:
        Optional mission key (e.g. ``"documentation"``, ``"software-dev"``).
        Defaults to ``"software-dev"`` when not provided.
    target_branch:
        Explicit target branch for the feature.  When *None* the current
        git branch is used.
    friendly_name:
        Optional mission title shown on operator-facing surfaces. When omitted,
        it is derived from ``mission_slug``.
    purpose_tldr:
        Optional one-line product/CXO summary for the mission. When omitted,
        it defaults to the resolved ``friendly_name``.
    purpose_context:
        Optional short paragraph explaining the mission in stakeholder terms.
        When omitted, it defaults to a branch-aware summary sentence.
    pr_bound:
        Persist the confirmed pull-request binding in the initial metadata
        write and commit. Defaults to ``False``.
    topology:
        Operator's create-time mission shape (#2218). Defaults to
        :attr:`MissionTopology.COORD` for backward-compat. The coordination
        branch is minted only for the coordination-bearing shapes
        (``COORD`` / ``LANES_WITH_COORD``); ``SINGLE_BRANCH`` / ``LANES`` skip
        the mint and never write ``coordination_branch``. The explicit choice
        is persisted verbatim into ``meta.json`` — never re-derived from
        ``classify_topology`` (which cannot reproduce ``LANES`` pre-finalize).
    allow_worktree_context:
        Bypass the worktree-context guard (step 2) that otherwise raises when
        the *process* ``cwd`` resolves inside a git worktree. Defaults to
        ``False``, preserving the interactive/CLI guard that protects
        operators from accidentally scaffolding a mission inside a lane
        worktree instead of the project root checkout. Intended for
        programmatic callers — notably ``tests/_factories.make_mission()``
        (FR-008) — that pass an explicit ``repo_root`` pointing at an
        isolated (often temporary) repository while the test process itself
        happens to be running from within a lane worktree checkout, which is
        this project's normal execution context for its own test suite.
    owned_create_root:
        The already-validated owned root (WP02's :class:`OwnedCreateRoot`) for
        this invocation, or ``None`` for an unowned (repository root) create.
        Callers holding only a raw ``--owned-checkout`` path resolve it through
        :func:`specify_cli.core.owned_mission.resolve_owned_create_root` first
        (validated exactly once per command, FR-003 spirit) and pass the typed
        result here. ``None`` preserves the existing worktree-context guard and
        write-root behavior exactly.
    retain_branches:
        Create-time retention opt-in (#3131 FR-009). When ``True``, mints
        ``retain_branches: true`` into ``meta.json`` so downstream ``spec-kitty
        merge`` cleanup honors the policy from creation. Defaults to
        ``False``, in which case the field is left ABSENT from ``meta.json``
        (never written as ``false``) so non-retaining missions stay
        byte-identical to pre-#3131 output (FR-010, SC-004).
    retain_worktrees:
        Create-time retention opt-in (#3131 FR-009) for worktrees, mirroring
        ``retain_branches``. Defaults to ``False`` (field left ABSENT).
    commit_to_target:
        Operator override (#5100 FR-008, WP08). When ``True`` on a
        ``SINGLE_BRANCH`` mission, skips the protected-target mission-branch
        mint below and mints ``commit_to_target: true`` into ``meta.json`` so
        the override is durable across the mission's lifetime. Defaults to
        ``False``, in which case the field is left ABSENT from ``meta.json``
        (mirrors ``retain_branches``/``retain_worktrees`` -- never written as
        ``false``).
    allow_duplicate:
        Escape hatch for the idempotency guard (#4033, FR-004). Defaults to
        ``False``, preserving the guard: creation is refused with
        :class:`MissionAlreadyExistsError` when a LIVE prior mission shares the
        same base ``mission_slug`` AND ``mission_type`` (FR-001). Abandoned
        priors (canceled, genesis, or spec never committed) never trigger
        the guard regardless of this flag (FR-003). Pass ``True`` to
        deliberately create a second same-key mission -- programmatic/volume
        callers (e.g. the ``tests/_factories`` mission factory) opt in via
        this keyword when they intentionally need more than one.
    _coord_rollback_holder:
        Private (T032/FR-002a). A mutable, initially-empty list the
        failure-atomic wrapper :func:`create_mission_core` passes in; this
        function appends ONE :class:`_CoordCreateRollbackContext` to it as
        soon as a real coordination branch is known (right after
        ``_build_create_meta`` returns), so a later failure in THIS call can
        still be rolled back by the wrapper's ``except`` clause even though
        ``mission_slug_formatted``/``mid8`` are minted only inside this
        function. ``None`` (the default) disables rollback reporting; never
        pass a non-empty list.

    Returns
    -------
    MissionCreationResult
        Structured result with all paths and metadata.

    Raises
    ------
    MissionCreationError
        On any validation or creation failure.
    charter.activation.pack_context.CharterPackConfigError
        When the project has no activated mission types (an absent or empty
        ``mission_type_activations`` set). This is the WP04 fail-closed at the
        mission-create / mission-type-use boundary: ``PackContext``
        construction is total, so the "provision your charter" error is
        raised here rather than at construction time.
    specify_cli.runtime.resolver.TemplateConfigurationError
        If the activated mission type cannot resolve its configured ``spec``
        template. Resolution happens before any mission state is created.
    """
    normalized_friendly_name = _validate_create_inputs(mission_slug, friendly_name)
    if commit_to_target and topology is not MissionTopology.SINGLE_BRANCH:
        raise MissionCreationError(
            f"--commit-to-target is only valid for a single_branch mission (got topology '{topology.value}'). "
            "Pass --topology single_branch, or drop --commit-to-target."
        )
    roots = _resolve_create_roots(repo_root, owned_create_root, allow_worktree_context)
    resolved_root = roots.repository_root
    write_root = roots.write_root
    current_branch = roots.current_branch

    # B5' (review cycle 2, ruling reversed): an owned-checkout create
    # combined with a coordination-routed topology (``coord`` /
    # ``lanes_with_coord``) is a SUPPORTED, ratcheted path (FR-022,
    # ``tests/integration/test_owned_lifecycle_acceptance_next.py::
    # TestFr022CoordinationTwin`` -- an owned sibling-checkout
    # ``create --topology lanes_with_coord`` followed by ``next`` must be a
    # non-error decision), not an operator override to refuse. ADR
    # 2026-09-03-1's "owned mode mints only single_branch" covers lifecycle
    # commands (``LIFECYCLE_OWNED_TOPOLOGIES``), not create + ``next``
    # (``NEXT_OWNED_TOPOLOGIES`` includes ``LANES_WITH_COORD``). A prior
    # cycle-2 fix refused this combination with
    # ``ActionContextError(OWNED_TOPOLOGY_UNSUPPORTED)``; that refusal broke
    # the ratchet and was removed. The real gap it was trying to close --
    # ``_scaffold_mission_dir`` keying its coordination-routed scaffold
    # change on ``topology`` alone, dropping ``status.events.jsonl`` from an
    # owned create's own scaffold commit -- is fixed at the source instead
    # (``_scaffold_mission_dir`` / ``_build_create_result`` now also gate on
    # ``owned is None``), so an owned coordination-routed create's status log
    # stays in its own PRIMARY dir, committed exactly as at base
    # (``e7b085d26c``). This is a named residual (INV-COORD-HOME): an owned
    # coordination create is never seeded onto the coordination surface
    # itself -- tracked as a follow-up, not fixed here.

    _refuse_live_duplicate(write_root, mission_slug, mission, allow_duplicate)

    planning_branch = target_branch if target_branch else current_branch
    create_time_target = resolve_create_time_write_target(planning_branch)
    purpose = _resolve_purpose(normalized_friendly_name, purpose_tldr, purpose_context, planning_branch)

    # FR-016 (#5009 1f42f76ea, re-expressed on the decomposed pipeline): the
    # validated write checkout owns charter and template configuration; its
    # activation may intentionally differ from the repository root checkout's.
    governance_root = roots.owned.checkout if roots.owned is not None else resolved_root
    governance = _resolve_create_governance(governance_root, mission)

    # Mint the ULID first so we can derive mid8 for the directory name.
    # resolve_mid8 derives the mid8 from the declared mission_id (authoritative,
    # FR-004/NFR-003); mission_dir_name composes <human-slug>-<mid8> canonically,
    # stripping any NNN- prefix (FR-032, FR-044).
    mission_id = str(ULID())
    # One authoritative derivation (FR-004/NFR-003) feeds both consumers: the
    # directory name below and the ``mid8`` meta backfill in
    # ``_build_create_meta`` (#3474), so the two can never drift.
    mid8 = resolve_mid8("", mission_id=mission_id)
    mission_slug_formatted = mission_dir_name(mission_slug, mid8=mid8)

    scaffold = _scaffold_mission_dir(
        write_root=write_root,
        resolved_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        create_time_target=create_time_target,
        spec_template=governance.spec_template,
        owned=roots.owned,
        topology=topology,
        commit_to_target=commit_to_target,
    )

    meta_build = _build_create_meta(
        feature_dir=scaffold.feature_dir,
        mission_id=mission_id,
        mid8=mid8,
        mission_slug_formatted=mission_slug_formatted,
        normalized_friendly_name=normalized_friendly_name,
        purpose=purpose,
        mission=mission,
        planning_branch=planning_branch,
        pr_bound=pr_bound,
        retain_branches=retain_branches,
        retain_worktrees=retain_worktrees,
        commit_to_target=commit_to_target,
        resolved_root=resolved_root,
        write_root=write_root,
        topology=topology,
        force_recreate_coordination_branch=force_recreate_coordination_branch,
    )
    if meta_build.minted_mission_branch is not None:
        # #5100 (6.7): the scaffold commit must land on the branch the mint
        # just checked out -- `create_time_target` was resolved BEFORE the
        # mint, from the (protected) planning branch. Without this,
        # `safe_commit`'s HEAD-vs-destination check sees the write checkout on
        # the minted branch but a destination of the protected
        # `planning_branch`, raises `SafeCommitHeadMismatch`, and the scaffold
        # commit silently treats it as an ordinary protected-target skip --
        # leaving the just-minted branch with no scaffold commit at all.
        # Re-derived through the SAME create-time seam (no mission identity is
        # readable yet), never a hand-built CommitTarget.
        create_time_target = resolve_create_time_write_target(meta_build.minted_mission_branch)

    # D6/T031: for a coordination-routed topology, materialize + seed the
    # coordination surface BEFORE the creation events are emitted, so they
    # land on the coordination Mission dir from birth instead of the target
    # branch's scaffold (#5440). Runs after ``_build_create_meta`` (the
    # coordination branch must already be minted and ``meta.json`` written,
    # since ``write_dir`` reads it back) and before the target scaffold
    # commit below (D6 "create order").
    coord_seed = _seed_coord_surface_for_create(
        resolved_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        mid8=mid8,
        topology=topology,
        meta_build=meta_build,
        owned=roots.owned,
        coord_rollback_holder=_coord_rollback_holder,
    )

    created_event, phase_event = _emit_create_events(
        feature_dir=scaffold.feature_dir,
        mission_slug_formatted=mission_slug_formatted,
        meta=meta_build.meta,
        planning_branch=planning_branch,
        resolved_root=resolved_root,
        write_root=write_root,
        purpose=purpose,
        normalized_friendly_name=normalized_friendly_name,
        spec_file=scaffold.spec_file,
        lifecycle_root=roots.owned.repository_root if roots.owned is not None else None,
        status_dir=coord_seed.status_dir,
    )

    if coord_seed.status_dir is not None:
        # T031/T032: committed unconditionally, outside the target scaffold
        # commit's bootstrap-skip handling (FR-002a) -- a refusal here raises
        # so the failure-atomic wrapper's rollback (coord_seed.rollback_ctx,
        # appended above) runs.
        _commit_coord_create_events(resolved_root, mission_slug_formatted, mission_id, coord_seed.status_dir)

    commit_outcome = _commit_create_scaffold(
        scaffold=scaffold,
        resolved_root=resolved_root,
        write_root=write_root,
        create_time_target=create_time_target,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        meta=meta_build.meta,
    )

    return _build_create_result(
        scaffold=scaffold,
        commit_outcome=commit_outcome,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        current_branch=current_branch,
        coordination_branch_created=meta_build.coordination_branch_created,
        resolved_root=resolved_root,
        owned_create_root=roots.owned,
        created_event=created_event,
        phase_event=phase_event,
        status_log_path=(coord_seed.status_dir / "status.events.jsonl") if coord_seed.status_dir is not None else None,
    )


def _consume_pending_origin_if_present(
    *,
    repo_root: Path,
    feature_dir: Path,
    meta: dict[str, Any],
) -> tuple[bool, bool, str | None, dict[str, Any]]:
    """Bind a staged pending origin after mission creation, if present.

    Dispatches to the registered PendingOriginConsumer via
    ``core.adapters.consume_pending_origin`` so that this module carries no
    direct INTEGRATION imports (FR-004/FR-006).  The concrete implementation
    lives in ``tracker/origin_consumer.py`` and is registered at tracker
    startup.  When no consumer is registered the call is a safe no-op
    that returns ``(False, False, None, meta)``.
    """
    from specify_cli.core.adapters import consume_pending_origin

    # Typed binding required: mypy uses follow_imports=skip for specify_cli.*
    # so the return of consume_pending_origin is seen as Any here; the
    # explicit annotation re-introduces the correct return type so the caller
    # does not propagate Any (no blanket suppression needed).
    result: tuple[bool, bool, str | None, dict[str, Any]] = consume_pending_origin(repo_root, feature_dir, meta)
    return result
