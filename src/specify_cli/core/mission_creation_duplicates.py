"""Live-duplicate detection over existing ``kitty-specs/`` scaffolds.

Moved verbatim from ``mission_creation.py`` (#5634). ``mission_creation`` re-exports
every name defined here. A call to a name tests patch on ``mission_creation``, or to a
function another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

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
        verdict = is_abandoned(wp_lanes=wp_lanes, canceled_lane=Lane.CANCELED.value, event_count=snapshot.event_count, spec_tracked=spec_tracked)
    return verdict is True


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

        if _prior_mission_is_abandoned(repo_root, candidate_dir):
            continue  # abandoned prior: auto-allow (FR-003), no flag needed

        return (name, candidate_mid8)

    return None


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
