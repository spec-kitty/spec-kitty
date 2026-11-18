"""Retarget verdicts for ``consolidate --target <b> --retarget`` (#7692).

Split out of :mod:`specify_cli.consolidation.preflight` at landing (#7696 NIT): the retarget
record, persisted-retarget, write-branch and target-override verdicts, and the merge-record key.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.git import GitCommandError, status_entries
from specify_cli.consolidation.preflight import (
    checked_out_branch,
    refuse_protected_target_override,
    refuse_unwritable_recorded_target,
)
from specify_cli.consolidation.preflight_skip_worktree import _index_bit
from specify_cli.consolidation.state import ConsolidationStateReadError, load_state

if TYPE_CHECKING:
    from specify_cli.coordination.types import Refused

#: #7692 FR-011: a ``--retarget`` whose record (``meta.json``) cannot be committed on the new target in this run.
RETARGET_RECORD_UNWRITABLE = "RETARGET_RECORD_UNWRITABLE"


#: #7692: ``--resume --target X --retarget`` naming an X other than the retarget the merge record persisted.
RETARGET_RESUME_MISMATCH = "RETARGET_RESUME_MISMATCH"


#: #7692 C-006: ``--retarget`` of a Mission whose write branch IS its recorded target (a commit-to-target
#: ``single_branch`` Mission): the landing would read the old target as the Mission branch and tear it down.
RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET = "RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET"


def _manifest_mission_branch(main_repo: Path, mission_slug: str) -> str | None:
    """The ``mission_branch`` the Mission's ``lanes.json`` names, else ``None`` (absent or corrupt manifest).

    Read through the placement seam (``LANE_STATE`` is a PRIMARY-partition artifact), as the
    forecast does. An unreadable manifest names no Mission branch; the run's own lanes
    preflight reports it.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json

    try:
        manifest = read_lanes_json(placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.LANE_STATE))
    except CorruptLanesError:
        return None
    return manifest.mission_branch if manifest is not None else None


def _branch_tree_carries(main_repo: Path, branch: str, rel_path: str) -> bool:
    """``True`` when *branch* resolves and its tree carries *rel_path* (``git cat-file -e``)."""
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"refs/heads/{branch}:{rel_path}"],
        cwd=str(main_repo),
        capture_output=True,
    )
    return probe.returncode == 0


def _rel_meta_path(main_repo: Path, mission_slug: str) -> Path:
    from specify_cli.missions._read_path_resolver import compose_meta_json_path

    meta_path: Path = compose_meta_json_path(main_repo, mission_slug)
    return meta_path.relative_to(main_repo)


def retarget_record_holders(main_repo: Path, mission_slug: str, *, mission_branch: str | None, effective_target: str) -> tuple[str, ...]:
    """The branches a retarget record is written on: each of the Mission branch and *effective_target* whose tree carries ``meta.json``.

    #7692 holder rule (plan D4/D10, operator ruling 2026-11-17): the record is written at
    every ``meta.json`` the landing reads. That is the Mission branch when its tree carries
    ``kitty-specs/<slug>/meta.json`` (always for a default-topology Mission, whose record lives
    on its topic branch) and the new target when it carries it (an explicit layout whose target
    was cut after the Mission existed). The ONE owner of that decision: the preflight and the
    retarget phase both read it here. Order: Mission branch first; deduplicated; a missing or
    unresolvable branch carries nothing. Read-only.
    """
    rel_meta = _rel_meta_path(main_repo, mission_slug).as_posix()
    candidates = dict.fromkeys(branch for branch in (mission_branch, effective_target) if branch)
    return tuple(branch for branch in candidates if _branch_tree_carries(main_repo, branch, rel_meta))


def _retarget_record_unwritable(recorded_target: str, effective_target: str, reason: str, next_step: str) -> Refused:
    from specify_cli.coordination.types import Refused

    return Refused(
        error_code=RETARGET_RECORD_UNWRITABLE,
        message=(
            f"Refusing to retarget the mission from '{recorded_target}' to '{effective_target}': its record "
            f"(meta.json) cannot be committed on '{effective_target}' in this run: {reason.rstrip('.')}."
        ),
        destination_ref=effective_target,
        next_step=next_step,
    )


def _record_on_neither_reason(rel_meta: Path, mission_branch: str | None, effective_target: str) -> str:
    if mission_branch is None:
        return f"'{effective_target}' does not carry {rel_meta.as_posix()} and the mission's lanes.json names no mission branch"
    return (
        f"neither the mission branch '{mission_branch}' nor '{effective_target}' carries {rel_meta.as_posix()} "
        "(the record lives only on the recorded target, and the new target was cut before the mission existed)"
    )


def retarget_record_refusal(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
) -> Refused | None:
    """The ``RETARGET_RECORD_UNWRITABLE`` refusal for a retarget whose record cannot be written, else ``None``.

    #7692 FR-011: a retarget rewrites ``meta.json`` (``target_branch``) on every branch
    :func:`retarget_record_holders` names, before anything else moves. It is refused up front
    when that write cannot happen in this run:

    * neither the Mission branch nor *effective_target* carries ``meta.json`` (the only shape
      that genuinely cannot be written: the record lives only on the recorded target);
    * *effective_target* carries it, but the repository root checkout cannot take the commit:
      the bookkeeping write's own hold check
      (:func:`~specify_cli.coordination.transaction.write_checkout_refusal`), then the shared
      primary-checkout precheck
      (:func:`~specify_cli.consolidation.meta_write.primary_checkout_refusal`: on
      *effective_target*, not detached, ``meta.json`` tracked, clean and not skip-worktree), with
      a skip-worktree or assume-unchanged BIT refused even with no edit (:func:`_index_bit`;
      retarget only, the bake's own precheck is unchanged);
    * *effective_target* is not a holder, but the root checkout on it holds untracked copies of
      the Mission directory the landing would overwrite (:func:`_untracked_mission_copies_refusal`).

    When only the Mission branch carries the record, the root checkout is not required to
    hold it: the landing carries the record to *effective_target*. ``None`` when the two
    targets agree (FR-012: restating the record is not a retarget). Read-only and lock-free,
    like its #5783 sibling :func:`refuse_unwritable_recorded_target`.
    """
    if effective_target == recorded_target:
        return None

    mission_branch = _manifest_mission_branch(main_repo, mission_slug)
    holders = retarget_record_holders(main_repo, mission_slug, mission_branch=mission_branch, effective_target=effective_target)
    rel_meta = _rel_meta_path(main_repo, mission_slug)
    if not holders:
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            _record_on_neither_reason(rel_meta, mission_branch, effective_target),
            next_step=(
                f"Consolidate into the recorded target '{recorded_target}' (drop '--target {effective_target} --retarget'); "
                f"or first bring the mission onto '{effective_target}' so it carries {rel_meta.parent.as_posix()}/ "
                f"(integrate '{recorded_target}' into '{effective_target}'), then re-run with '--target {effective_target} --retarget'."
            ),
        )
    if effective_target not in holders:
        return _untracked_mission_copies_refusal(main_repo, rel_meta, recorded_target=recorded_target, effective_target=effective_target)
    return _new_target_checkout_refusal(main_repo, mission_slug, rel_meta, recorded_target=recorded_target, effective_target=effective_target)


def _untracked_mission_copies_refusal(main_repo: Path, rel_meta: Path, *, recorded_target: str, effective_target: str) -> Refused | None:
    """The refusal when the landing would overwrite untracked copies of the Mission directory, else ``None`` (#7692 FR-011).

    *effective_target* is not a holder (it was cut before the Mission existed), so the landing
    writes ``kitty-specs/<slug>/`` into the repository root checkout. When that checkout is on
    *effective_target* and holds untracked files under that directory, the landing's resync
    would overwrite them: the run would mutate first and then fail. Only the root checkout on
    *effective_target* is judged; the off-target preflight owns a checkout on another branch.
    """
    if checked_out_branch(main_repo) != effective_target:
        return None
    mission_dir = rel_meta.parent.as_posix()
    try:
        entries = status_entries(main_repo, pathspecs=(mission_dir,), untracked="all")
    except GitCommandError:
        entries = ()
    untracked = [entry.path.as_posix() for entry in entries if entry.is_untracked]
    if not untracked:
        return None
    return _retarget_record_unwritable(
        recorded_target,
        effective_target,
        (
            f"the repository root checkout holds {len(untracked)} untracked file(s) under {mission_dir}/ (e.g. {untracked[0]}) "
            f"that the landing would overwrite, because '{effective_target}' does not carry the mission yet"
        ),
        next_step=f"Remove the untracked copies under {mission_dir}/ (or move them aside), then re-run with '--target {effective_target} --retarget'.",
    )


def _new_target_checkout_refusal(main_repo: Path, mission_slug: str, rel_meta: Path, *, recorded_target: str, effective_target: str) -> Refused | None:
    """The refusal when the root checkout cannot take the record commit on *effective_target*, else ``None``."""
    from specify_cli.consolidation.meta_write import primary_checkout_refusal
    from specify_cli.coordination.transaction import write_checkout_refusal

    hold = write_checkout_refusal(main_repo, mission_slug, effective_target, operation=f"retarget record for {mission_slug}")
    if hold is not None:
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            hold.message,
            next_step=f"Check out '{effective_target}' in the repository root checkout (`git checkout {effective_target}`), then re-run.",
        )
    bit = _index_bit(main_repo, rel_meta)
    if bit is not None:
        name, clear = bit
        return _retarget_record_unwritable(
            recorded_target,
            effective_target,
            f"{rel_meta.as_posix()} carries the {name} bit in the repository root checkout, so git cannot be trusted to read or rewrite it",
            next_step=f"Clear the bit (`{clear}`), then re-run with '--target {effective_target} --retarget'.",
        )
    reason = primary_checkout_refusal(main_repo, rel_meta, effective_target)
    if reason is None:
        return None
    return _retarget_record_unwritable(
        recorded_target,
        effective_target,
        reason,
        next_step=(
            f"Check out '{effective_target}' in the repository root checkout (`git checkout {effective_target}`) and make sure "
            f"{rel_meta.as_posix()} is tracked there with no uncommitted or skip-worktree edit (commit or discard the edit), then re-run."
        ),
    )


def retarget_write_branch_refusal(*, mission_branch: str | None, recorded_target: str, effective_target: str) -> Refused | None:
    """``RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET`` when the Mission's write branch is its recorded target, else ``None`` (#7692, C-006).

    A commit-to-target ``single_branch`` Mission writes on its target: ``lanes.json`` names the
    recorded target as its ``mission_branch``. Retargeted, the run would treat the old target as
    the Mission branch, land it on the new one and then delete it with the Mission's other
    branches. Witnessed end to end before this guard: ``main`` was deleted. Pure; equal targets
    are never a retarget (FR-012).
    """
    if effective_target == recorded_target or mission_branch != recorded_target:
        return None
    from specify_cli.coordination.types import Refused

    return Refused(
        error_code=RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET,
        message=(
            f"Refusing to retarget the mission from '{recorded_target}' to '{effective_target}': its work is written on "
            f"'{recorded_target}' itself (a commit-to-target single_branch mission), so this run would land "
            f"'{recorded_target}' as the mission branch and then delete it."
        ),
        destination_ref=effective_target,
        next_step=(
            f"Consolidate into the recorded target '{recorded_target}' (drop '--target {effective_target} --retarget'), "
            f"then integrate '{recorded_target}' into '{effective_target}' with git."
        ),
    )


def merge_record_key(main_repo: Path, mission_slug: str) -> str:
    """The key the executor stores this Mission's merge record under: the ``meta.json`` ``mission_id``, else the slug.

    The same rule as ``executor._run_lane_based_consolidation`` (``resolve_mission_identity`` on the
    PRIMARY_METADATA directory), so a caller holding a legacy ``lanes.json`` without ``mission_id``
    still finds the record (#7692 review OA-1). An unreadable ``meta.json`` keys on the slug, as the
    executor's own fallback does for a Mission with no identity.
    """
    from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.mission_metadata import resolve_mission_identity

    try:
        identity = resolve_mission_identity(placement_seam(main_repo, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA))
    except (ActionContextError, MissionMetaReadError, ValueError):
        return mission_slug
    return record_key_for_identity(identity.mission_id, mission_slug)


def record_key_for_identity(mission_id: str | None, mission_slug: str) -> str:
    """The one rule for the merge-record key: the ``mission_id`` when the Mission has one, else the slug.

    ``executor._run_lane_based_consolidation`` (which resolves the identity itself) and
    :func:`merge_record_key` (forecast, orchestrator-api) both call this, so the key a record is
    stored under and the key it is looked up by cannot drift apart (#7692 landing fold).
    """
    return mission_id if mission_id is not None else mission_slug


def persisted_retarget_pair(main_repo: Path, canonical_id: str) -> tuple[str, str] | None:
    """``(from, to)`` of the retarget an existing merge record persisted, else ``None`` (#7692).

    An unreadable record contributes none: the run's resume code owns that error.
    """
    try:
        state = load_state(main_repo, canonical_id)
    except (ConsolidationStateReadError, OSError):
        return None
    return state.retarget_pair() if state is not None else None


@dataclass(frozen=True)
class RetargetMode:
    """How a run is judged against a retarget (#7692): the ONE decision the entry preflight and the forecast share.

    ``pair`` is the ``(recorded, new)`` target pair when the run is a retarget, else ``None``.
    ``mismatch`` is the ``RETARGET_RESUME_MISMATCH`` refusal when a merge record persisted a
    retarget and this run's target is not that retarget's new target; each caller renders it its
    own way.
    """

    pair: tuple[str, str] | None
    mismatch: Refused | None = None


def _retarget_resume_mismatch(persisted: tuple[str, str], effective_target: str, *, retarget: bool) -> Refused:
    from specify_cli.coordination.types import Refused

    recorded, persisted_to = persisted
    asked = f"'--target {effective_target} --retarget'" if retarget else f"'--target {effective_target}'"
    instead = f"retarget onto '{effective_target}'" if retarget else f"consolidate into '{effective_target}'"
    return Refused(
        error_code=RETARGET_RESUME_MISMATCH,
        message=(f"this mission's interrupted consolidation retargets it from '{recorded}' to '{persisted_to}', but this run asks for {asked}."),
        destination_ref=effective_target,
        next_step=(
            f"re-run with '--target {persisted_to} --retarget' (or a bare `spec-kitty consolidate --resume`) to finish "
            f"that retarget, or run `spec-kitty consolidate --abort` first to {instead} instead."
        ),
    )


def retarget_mode(main_repo: Path, canonical_id: str, *, retarget: bool, recorded: str, effective: str) -> RetargetMode:
    """Judge whether this run is a retarget (#7692); the single owner both the run and ``--dry-run`` read.

    A merge record that persisted a retarget binds every later run: a target other than that
    retarget's new target is a mismatch, with or without ``--retarget`` (mission review RISK-1:
    ``--target <recorded>`` used to pass this check and then have the locked run re-apply the
    persisted retarget anyway). Equal targets are never a retarget (FR-012). Otherwise the run is a
    retarget when ``--retarget`` asks for one, or when the merge record persisted this very
    retarget (a bare ``--resume``, or a re-run after a re-baselined failure).
    """
    persisted = persisted_retarget_pair(main_repo, canonical_id)
    if persisted is not None and persisted[1] != effective:
        return RetargetMode(pair=None, mismatch=_retarget_resume_mismatch(persisted, effective, retarget=retarget))
    if recorded == effective:
        return RetargetMode(pair=None)
    if retarget or persisted == (recorded, effective):
        return RetargetMode(pair=(recorded, effective))
    return RetargetMode(pair=None)


def persisted_retarget_refusal(main_repo: Path, canonical_id: str, mission_slug: str) -> Refused | None:
    """``RETARGET_RESUME_MISMATCH`` for a command with no ``--retarget`` facing a persisted retarget, else ``None`` (#7692).

    ``orchestrator-api consolidate-mission`` can neither finish a persisted retarget (it runs no
    retarget preflight and has no rollback door) nor land on any target while the merge record
    names one (mission review RISK-1), so every persisted retarget refuses there, whatever its
    ``--target``. The next step names the ``spec-kitty consolidate`` commands that can.
    """
    persisted = persisted_retarget_pair(main_repo, canonical_id)
    if persisted is None:
        return None
    from specify_cli.coordination.types import Refused

    source, to = persisted
    return Refused(
        error_code=RETARGET_RESUME_MISMATCH,
        message=(f"this mission's interrupted consolidation retargets it from '{source}' to '{to}', and only `spec-kitty consolidate` can finish a retarget."),
        destination_ref=to,
        next_step=(
            f"run `spec-kitty consolidate --mission {mission_slug} --resume` to finish that retarget, or "
            f"`spec-kitty consolidate --mission {mission_slug} --abort` first to drop it."
        ),
    )


def target_override_verdict(
    main_repo: Path,
    mission_slug: str,
    *,
    recorded_target: str,
    effective_target: str,
    retarget: bool = False,
) -> Refused | None:
    """The ONE owner of the ``--target`` override verdict (#7692, plan D1), else ``None``.

    #6464 (:func:`refuse_protected_target_override`) runs first, then the record check:

    * a plain ``--target`` (``retarget=False``): the #5783 recorded-target check
      (:func:`refuse_unwritable_recorded_target`), exactly today's chain (C-002);
    * ``--retarget``: :func:`retarget_record_refusal`; a retarget never consults #5783.

    Pure verdict: each caller keeps its own rendering and exception type.
    """
    protected = refuse_protected_target_override(main_repo, mission_slug, recorded_target=recorded_target, effective_target=effective_target)
    if protected is not None:
        return protected
    record_check = retarget_record_refusal if retarget else refuse_unwritable_recorded_target
    return record_check(main_repo, mission_slug, recorded_target=recorded_target, effective_target=effective_target)
