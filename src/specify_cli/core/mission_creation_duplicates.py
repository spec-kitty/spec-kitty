"""Live-duplicate detection over existing ``kitty-specs/`` scaffolds.

Moved verbatim from ``mission_creation.py`` (#5634). ``mission_creation`` re-exports
every name defined here. A call to a name tests patch on ``mission_creation``, or to a
function another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.mission_creation_decisions import (
    candidate_name_matches,
    is_abandoned,
    is_same_mission_type,
)
from specify_cli.core.paths import (
    MissionMetaReadError,
    load_meta_fail_closed,
)
from specify_cli.lanes.branch_naming import (
    strip_numeric_prefix,
)
from specify_cli.core.mission_creation_errors import MissionAlreadyExistsError


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


def _minted_mission_branch_is_live(repo_root: Path, meta: dict[str, object]) -> bool:
    """True when *meta* records a minted ``mission_branch`` that exists in *repo_root* (#5726)."""
    from specify_cli.core import mission_creation as _mc

    mission_branch = meta.get("mission_branch")
    if not isinstance(mission_branch, str) or not mission_branch:
        return False
    live: bool = _mc._local_branch_exists(repo_root, mission_branch)
    return live


def _prior_mission_is_abandoned(
    repo_root: Path,
    feature_dir: Path,
    meta: dict[str, object] | None = None,
    protected_mint_applies: Callable[[], bool] | None = None,
) -> bool:
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
    One narrowing (#5726): when THIS create would run the protected mint
    (*protected_mint_applies*, resolved only when it decides), a prior whose
    *meta* records a minted ``mission_branch`` that still exists is LIVE. Its
    scaffold is committed on that branch, and the mint would otherwise refuse
    on the prior's own untracked ``spec.md`` with a mid8-dependent code; the
    re-run refuses MISSION_ALREADY_EXISTS instead. A re-create that does not
    mint (for example one made on the prior's mission branch) keeps FR-003.

    Fail closed (C-002): any status-log read failure means abandonment
    cannot be established, so this returns ``False`` (treated as LIVE) and
    the guard refuses rather than silently allowing a duplicate.
    """
    from specify_cli.core import mission_creation as _mc

    from specify_cli.status import Lane, StoreError, materialize_snapshot

    try:
        snapshot = materialize_snapshot(feature_dir)
    except StoreError:
        return False

    wp_lanes = {wp_id: wp_state.get("lane") for wp_id, wp_state in snapshot.work_packages.items()}
    verdict = is_abandoned(wp_lanes=wp_lanes, canceled_lane=Lane.CANCELED.value, event_count=snapshot.event_count, spec_tracked=None)
    if verdict is None:
        # genesis candidate: the spec's git tracking decides, probed only now.
        spec_tracked = _mc._path_is_tracked_by_git(repo_root, feature_dir / "spec.md")
        branch_live = (
            meta is not None
            and protected_mint_applies is not None
            and not spec_tracked
            and _minted_mission_branch_is_live(repo_root, meta)
            and protected_mint_applies()
        )
        verdict = is_abandoned(
            wp_lanes=wp_lanes,
            canceled_lane=Lane.CANCELED.value,
            event_count=snapshot.event_count,
            spec_tracked=spec_tracked,
            mission_branch_live=branch_live,
        )
    return verdict is True


def _find_live_duplicate_mission(
    repo_root: Path,
    *,
    mission_slug: str,
    mission_type: str,
    protected_mint_applies: Callable[[], bool] | None = None,
) -> tuple[str, str] | None:
    """Find a live same-key prior mission, if any (#4033 idempotency guard).

    Duplicate key = same base ``mission_slug`` (mid8 stripped, FR-001) AND
    same ``mission_type`` read from the candidate's ``meta.json``. A
    ``research`` and a ``software-dev`` mission sharing a name are not a
    duplicate (edge case in spec.md).

    Returns ``(dir_name, mid8)`` for the first live match, or ``None`` when
    no same-key prior mission exists or every one is abandoned (see
    :func:`_prior_mission_is_abandoned`, which receives
    *protected_mint_applies*).

    Fail closed (C-002): a same-slug candidate whose ``meta.json`` is
    missing or corrupt is treated as LIVE -- its type/abandonment cannot be
    established, so refusing is the safe default. An explicit
    ``--allow-duplicate`` always overrides this guard regardless.
    """
    base_slug = strip_numeric_prefix(mission_slug)

    for name in sorted(_list_mission_scaffolds(repo_root)):
        matches, candidate_mid8 = candidate_name_matches(name, base_slug)
        if not matches:
            continue
        candidate_dir = repo_root / KITTY_SPECS_DIR / name

        try:
            candidate_meta = load_meta_fail_closed(candidate_dir)
        except MissionMetaReadError:
            return (name, candidate_mid8)  # fail closed: unreadable meta.json
        if candidate_meta is None:
            return (name, candidate_mid8)  # fail closed: missing meta.json

        if not is_same_mission_type(candidate_meta, mission_type):
            continue  # different mission_type: not a duplicate key

        if not candidate_mid8:
            candidate_mid8 = str(candidate_meta.get("mid8") or "")

        if _prior_mission_is_abandoned(repo_root, candidate_dir, candidate_meta, protected_mint_applies):
            continue  # abandoned prior: auto-allow (FR-003), no flag needed

        return (name, candidate_mid8)

    return None


def _refuse_live_duplicate(
    write_root: Path,
    mission_slug: str,
    mission: str | None,
    allow_duplicate: bool,
    protected_mint_applies: Callable[[], bool] | None = None,
) -> None:
    """Idempotency guard (#4033, FR-001..004, C-001, C-002).

    Section 2.5 of the pre-decomposition body (T051): refuse a same-key (same
    base ``mission_slug`` AND same ``mission_type``) LIVE prior mission HERE
    -- before any scaffold/branch write (NFR-002: no orphan scaffold on
    refusal). "Live" excludes abandoned priors (canceled, genesis / no
    lifecycle progress, or spec never committed, see
    :func:`_prior_mission_is_abandoned`), so the common gave-up-and-re-ran
    path just works with no flag (FR-003). *protected_mint_applies* (#5726)
    says whether this create will run the protected mint; see
    :func:`_prior_mission_is_abandoned`.
    """
    if allow_duplicate:
        return
    effective_mission_type = mission or "software-dev"
    duplicate = _find_live_duplicate_mission(
        write_root,
        mission_slug=mission_slug,
        mission_type=effective_mission_type,
        protected_mint_applies=protected_mint_applies,
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
