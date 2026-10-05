"""Mission lifecycle-phase reader (#3033 P0, D2/D3 — internal, not stored).

This module is internal to :mod:`mission_runtime`. It answers exactly one
question — "where in its lifecycle is this mission, from durable signals
alone" — for :mod:`mission_runtime.resolution` to consume. It is **not** a
second write resolver (C-001/C-006): nothing here selects a
:class:`~mission_runtime.context.CommitTarget` or a filesystem path: that
projection stays entirely inside ``resolution.py``, which is the ONLY module
that calls into this one.

Phase is derived from durable state, never threaded as a parameter (D3 /
NFR-001): :func:`resolve_lifecycle_phase` re-reads the same
``meta.json`` + git signals on every call, so the probe
(``resolve_placement_only``) and the materializer (``resolve_artifact_
surface``) — both of which call this function directly — can never disagree
about the phase of a given mission at a given moment (no split-brain).

See ``research.md`` D1-D3, ``data-model.md`` "LifecyclePhase", and ADR
``docs/adr/3.x/2026-07-30-1-consolidated-write-surface-and-consolidate-
terminology.md`` (Decision 1) for the design record.
"""

from __future__ import annotations

import enum
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from mission_runtime.mission_resolver_port import MissionResolver

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)

# ``content_present_at_primary_tip`` is deliberately NOT exported: its only
# caller is in-package (``mission_runtime.resolution``), which imports it by
# module path (demoted, never deleted -- dead-port-disposition-01M1TZVN, FR-014).
__all__ = [
    "LifecyclePhase",
    "resolve_lifecycle_phase",
]

#: git probe timeout (seconds) — matches the sibling probes in
#: ``specify_cli.core.git_ops`` (``_origin_head_branch`` / ``_common_branch_exists``).
_GIT_PROBE_TIMEOUT = 10

_GIT_REV_VALID = 0


class LifecyclePhase(enum.Enum):
    """A mission's consolidation lifecycle phase (data-model.md, D2).

    Derived, never stored: :func:`resolve_lifecycle_phase` recomputes this on
    every call from ``meta.json`` + git branch state.
    """

    #: ``baseline_merge_commit`` absent. Routing is UNCHANGED from #3076 (the
    #: regression floor, C-012 / T012) -- this is also the SAFE DEFAULT a
    #: legacy null-baseline mission (Target Ref never created) resolves to
    #: (C-003).
    PRE_CONSOLIDATION = "pre_consolidation"
    #: ``baseline_merge_commit`` present AND the Target Ref branch still
    #: exists (E1 -- lane consolidation landed, not yet published to trunk).
    CONSOLIDATED = "consolidated"
    #: ``baseline_merge_commit`` present AND the Target Ref is absent AND
    #: terminal-completion evidence a consolidation produces is present (E2
    #: -- published to trunk, Target Ref deleted). C-003 disambiguation: NOT
    #: "Target Ref absent" alone.
    PUBLISHED = "published"


class LifecyclePhaseProbeError(RuntimeError):
    """A git probe this module needed failed for a reason OTHER than "absent".

    Raised when a ``git`` plumbing command exits with a code that is neither
    the documented "found" nor "genuinely absent" signal (e.g. exit 128 --
    bad revision, unreadable object, not a git repository) or times out. This
    must never be swallowed into a false "content absent" verdict (D1) --
    doing so would silently mis-refuse a genuinely valid E2 write for an
    unrelated infrastructure reason.
    """


def _primary_feature_dir(
    mission_slug: str,
    repo_root: Path,
    *,
    resolver: MissionResolver | None = None,
) -> Path:
    """The canonical PRIMARY mission dir every field this module reads anchors on.

    Mirrors :func:`specify_cli.core.paths.get_feature_target_branch`'s own
    canonicalization exactly -- the sibling ``target_branch`` reader this
    module's E1/E2 disambiguation directly depends on -- so every field read
    here (``baseline_merge_commit``, ``mission_number``, the status event
    log) comes from the SAME ``meta.json`` as the target-branch read the
    write path already trusts. This is the existing canonicalization
    primitive applied to sibling fields, never a second resolver (C-006).
    """
    from specify_cli.core.paths import get_main_repo_root
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    main_root = get_main_repo_root(repo_root)
    canonical_handle = _canonicalize_primary_read_handle(
        main_root, mission_slug, resolver=resolver
    )
    # ``_compose_primary_feature_dir`` is typed ``-> Path`` but the
    # ``follow_imports=skip`` boundary on ``specify_cli.*`` widens it to
    # ``Any``; bind explicitly so the declared return narrows back (matches
    # the sibling chokepoint pattern in ``resolution.py``).
    feature_dir: Path = _compose_primary_feature_dir(main_root, canonical_handle)
    return feature_dir


def _read_baseline_merge_commit(feature_dir: Path) -> str:
    """Read the raw ``baseline_merge_commit`` field, ``""`` when absent/blank.

    Routed through the ONE public fail-closed reader
    (:func:`specify_cli.core.paths.load_meta_fail_closed`, FR-007 / #3140) so a
    corrupt ``meta.json`` surfaces the typed :class:`MissionMetaReadError`
    rather than a raw :class:`ValueError`.

    The typed error is then degraded to the absent-baseline answer (``""``).
    That is deliberate and matches the sibling placement probes in
    ``mission_runtime.resolution`` (``_mid8_from_primary_meta``, ``_resolve_coordination_branch``,
    ``_resolve_mission_id``): this function is a *phase probe* consumed by
    surface resolution, not the meta-trust authority.  Pre-empting the read with
    a hard failure here is precisely the #3140 leak -- it fired inside
    ``resolve_artifact_surface`` and denied
    ``specify_cli.status.aggregate.MissionStatus._read_meta`` the chance to raise
    its own typed ``MissionMetadataUnavailable``.  Degrading here keeps the
    corruption verdict with that fail-closed seam, which reports it with the
    mission slug and primary candidate attached.
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        # Corrupt meta.json: the baseline is unknowable, so report the
        # absent-baseline answer (PRE_CONSOLIDATION) and let the downstream
        # fail-closed reader own the typed corruption verdict.
        _logger.warning(
            "lifecycle phase probe: unreadable meta.json at %s — treating "
            "baseline_merge_commit as absent; the meta-trust verdict is owned "
            "by the mission-status fail-closed reader.",
            feature_dir / "meta.json",
        )
        return ""
    if not meta:
        return ""
    value = meta.get("baseline_merge_commit")
    return str(value).strip() if value else ""


def _target_ref_exists(repo_root: Path, target_branch: str) -> bool:
    """Local-branch existence probe for the Target Ref (D2 E1/E2 split).

    A direct ``git rev-parse --verify --quiet refs/heads/<branch>`` call
    (the same trivial primitive :func:`specify_cli.lanes._git.branch_exists`
    wraps) rather than importing that helper: ``mission_runtime`` -> `
    `specify_cli.lanes`` is a CLOSED layering edge (test_layer_rules.py
    ``_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI`` — the coord-trust-2841 ledger
    explicitly retired it), so this stays self-contained rather than
    reopening it for one boolean check.
    """
    try:
        # ``--end-of-options`` keeps the ref positional so a crafted
        # ``target_branch`` cannot be parsed as a git option (Sonar S6350); the
        # ``refs/heads/`` prefix already prevents a leading ``-`` and argv form
        # precludes shell injection, so this is belt-and-suspenders.
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"refs/heads/{target_branch}"],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_PROBE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LifecyclePhaseProbeError(
            f"git rev-parse --verify refs/heads/{target_branch!r} timed out in {repo_root}"
        ) from exc
    return result.returncode == _GIT_REV_VALID


def _terminal_completion_evidence(feature_dir: Path) -> bool:
    """C-003 disambiguation signal: does this mission show consolidation completed?

    ``True`` when ``mission_number`` is assigned (merge-time bookkeeping) OR
    every work package in the status event log is ``done``. Either signal a
    *never-created* mission cannot fake -- only a real consolidation produces
    them (D2).
    """
    from specify_cli.mission_metadata import resolve_mission_identity

    identity = resolve_mission_identity(feature_dir)
    if identity.mission_number is not None:
        return True
    return _all_work_packages_done(feature_dir)


def _all_work_packages_done(feature_dir: Path) -> bool:
    """``True`` iff the status event log has at least one WP and every WP is ``done``."""
    from specify_cli.status.reducer import reduce
    from specify_cli.status.store import read_events

    events = read_events(feature_dir)
    if not events:
        return False
    snapshot = reduce(events)
    if not snapshot.work_packages:
        return False
    return all(
        str(state.get("lane", "")) == "done" for state in snapshot.work_packages.values()
    )


def resolve_lifecycle_phase(
    mission_slug: str,
    repo_root: Path,
    *,
    resolver: MissionResolver | None = None,
) -> LifecyclePhase:
    """Derive a mission's :class:`LifecyclePhase` from durable signals (D2).

    The ONE phase-derivation authority (renata M1): both the write-side probe
    (:func:`mission_runtime.resolution.resolve_placement_only`) and the
    materializer (:func:`mission_runtime.resolution.resolve_artifact_surface`)
    call this SAME function -- neither re-derives phase independently -- so
    the two can never disagree (NFR-001, no split-brain).

    Signal (NFR-004 -- no new git subprocess on the pre-consolidation happy
    path):

    1. ``baseline_merge_commit`` absent → :attr:`LifecyclePhase.PRE_CONSOLIDATION`
       (zero subprocess calls -- the common case).
    2. ``baseline_merge_commit`` present AND the Target Ref branch exists →
       :attr:`LifecyclePhase.CONSOLIDATED` (E1).
    3. ``baseline_merge_commit`` present AND the Target Ref is absent AND
       terminal-completion evidence is present →
       :attr:`LifecyclePhase.PUBLISHED` (E2).
    4. ``baseline_merge_commit`` present AND the Target Ref is absent AND NO
       terminal-completion evidence → :attr:`LifecyclePhase.PRE_CONSOLIDATION`
       (C-003: a never-created Target Ref is also "absent"; the safe default
       is pre-consolidation, never a false E2).

    ``get_feature_target_branch`` itself stays UNROUTED (C-003) -- the
    branch-existence probe lives here, not in that foundation reader.

    Args:
        mission_slug: The mission slug/handle (any canonicalizable form).
        repo_root: Repository root (may be a worktree; resolved to the
            canonical primary root internally).
        resolver: Optional :class:`MissionResolver` threaded through handle
            canonicalization. ``None`` preserves historical behaviour.
    """
    feature_dir = _primary_feature_dir(mission_slug, repo_root, resolver=resolver)
    baseline = _read_baseline_merge_commit(feature_dir)
    if not baseline:
        return LifecyclePhase.PRE_CONSOLIDATION

    from specify_cli.core.paths import get_feature_target_branch, get_main_repo_root

    main_root = get_main_repo_root(repo_root)
    target_branch = get_feature_target_branch(repo_root, mission_slug)
    if _target_ref_exists(main_root, target_branch):
        return LifecyclePhase.CONSOLIDATED

    if _terminal_completion_evidence(feature_dir):
        return LifecyclePhase.PUBLISHED
    return LifecyclePhase.PRE_CONSOLIDATION


def _rev_is_valid(repo_root: Path, rev: str) -> bool:
    """``True`` iff ``rev`` resolves to a real object (``git rev-parse --verify -q``)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", rev],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_PROBE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LifecyclePhaseProbeError(f"git rev-parse --verify {rev!r} timed out in {repo_root}") from exc
    return result.returncode == _GIT_REV_VALID


def _path_present_at_rev(repo_root: Path, object_spec: str) -> bool:
    """``True`` iff ``object_spec`` (``<rev>:<path>``) resolves to a blob.

    Callers MUST have already confirmed ``rev`` itself is a valid revision
    (:func:`_rev_is_valid`) before calling this — see
    :func:`_git_object_present`'s docstring for why: ``git cat-file -e
    <rev>:<path>`` exits ``128`` (not ``1``) for BOTH "path absent in a
    valid rev" and "rev itself is invalid" (verified empirically against
    git 2.43 — the exit-1-vs-128 split the design intended does not hold
    for the ``<rev>:<path>`` object-spec form), so this function alone
    cannot distinguish the two; once the caller has independently confirmed
    ``rev`` is valid, ANY non-zero exit here unambiguously means "path
    absent at this (valid) rev".
    """
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", object_spec],
            cwd=repo_root,
            capture_output=True,
            timeout=_GIT_PROBE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LifecyclePhaseProbeError(
            f"git cat-file -e {object_spec!r} timed out in {repo_root}"
        ) from exc
    return result.returncode == _GIT_REV_VALID


def _git_object_present(repo_root: Path, rev: str, path: str) -> bool:
    """Squash-robust content-presence check, distinguishing absent from broken.

    A two-step probe (renata B1): a naive single ``git cat-file -e
    <rev>:<path>`` cannot distinguish "the path is genuinely absent at a
    VALID rev" (D1's documented "content absent" signal) from "the rev
    itself does not exist" (a genuine plumbing failure that must raise
    LOUDLY, never be silently read as "content absent") -- both fail with
    exit ``128`` ("fatal: path ... does not exist" vs "fatal: invalid
    object name ..."), so the exit code alone is not the discriminator.

    1. :func:`_rev_is_valid` confirms ``rev`` itself resolves. If it does
       NOT, :class:`LifecyclePhaseProbeError` is raised -- an unrelated bug
       (e.g. ``resolve_primary_branch`` returning a name that is not
       actually a ref in this repository) must still surface loudly (mirrors
       ``write_seam.py``'s ``_UNROUTABLE_EXCEPTIONS`` "unrelated bug must
       still raise" discipline).
    2. With ``rev`` confirmed valid, :func:`_path_present_at_rev` checks
       ``<rev>:<path>``. Any failure at this stage is unambiguously "path
       absent at this rev" (D1) -- ``False``, never a raise.
    """
    if not _rev_is_valid(repo_root, rev):
        raise LifecyclePhaseProbeError(
            f"git rev {rev!r} does not resolve to a valid revision in {repo_root} "
            "-- expected the resolved Primary Branch to be a real ref"
        )
    return _path_present_at_rev(repo_root, f"{rev}:{path}")


def content_present_at_primary_tip(
    mission_slug: str,
    repo_root: Path,
    *,
    resolver: MissionResolver | None = None,
) -> bool:
    """D1 squash-robust content-presence predicate (renata B1).

    Checks the mission's committed ``meta.json`` is present at the RESOLVED
    Primary-Branch tip -- never literal ``HEAD`` (a lane/coord worktree
    checkout's ``HEAD`` is not the Primary Branch) -- keyed by the resolved
    CANONICAL primary dir name (``<slug>-<mid8>``), never the bare
    ``mission_slug`` (bare-vs-suffixed drift is a false-negative that wrongly
    refuses a valid E2 write).

    This is content-PRESENCE, not commit-ANCESTRY (D1): it succeeds
    regardless of commit topology (squash, rebase, or merge-commit), unlike
    ``git merge-base --is-ancestor``, which a squash publish-to-trunk breaks
    (the E1 consolidation commit is not a commit-ancestor of a squashed
    Primary Branch tip).

    Args:
        mission_slug: The mission slug/handle (any canonicalizable form).
        repo_root: Repository root (may be a worktree; resolved to the
            canonical primary root internally).
        resolver: Optional :class:`MissionResolver` threaded through handle
            canonicalization. ``None`` preserves historical behaviour.

    Raises:
        LifecyclePhaseProbeError: When the underlying ``git`` probe fails for
            a reason other than "the path is genuinely absent at this rev".
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR
    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.core.paths import get_main_repo_root

    main_root = get_main_repo_root(repo_root)
    primary_dir = _primary_feature_dir(mission_slug, repo_root, resolver=resolver)
    # bias=False: the TRUE Primary Branch, never "whichever branch a lane
    # worktree happens to be standing on" (the feature-bias default would
    # defeat the purpose of an off-checkout content-presence probe).
    primary_branch = resolve_primary_branch(main_root, bias=False)
    marker_path = f"{KITTY_SPECS_DIR}/{primary_dir.name}/meta.json"
    return _git_object_present(main_root, primary_branch, marker_path)
