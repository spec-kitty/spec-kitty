"""Mission-slug / merge-state / target-branch resolution for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-04 / WP04.

Slug extraction, merge-state load/clear/cleanup, and target-branch resolution
moved byte-for-byte out of the command shim. Consumes ``merge/state.py`` for
``MergeState`` I/O and ``merge/workspace.py`` for runtime cleanup. The shim
re-exports the test-imported resolvers (``_resolve_mission_slug``,
``_resolve_target_branch`` and the state-load helpers) so importers need zero
edits (FR-006, C-002). One-way import: this module never imports the command shim.
"""

from __future__ import annotations

import re
from pathlib import Path

from specify_cli.core.constants import KITTIFY_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import get_main_repo_root
from specify_cli.merge._constants import logger
from specify_cli.merge.state import (
    MergeState,
    MergeStateReadError,
    clear_state,
    load_state,
    save_state,
)
from specify_cli.merge.workspace import cleanup_merge_workspace
from specify_cli.mission_metadata import resolve_mission_identity
from mission_runtime import MissionArtifactKind, placement_seam


def _extract_mission_slug(branch_name: str) -> str | None:
    """Infer a feature slug from a feature, mission, or lane branch name."""
    from specify_cli.lanes.branch_naming import parse_mission_slug_from_branch

    parsed = parse_mission_slug_from_branch(branch_name)
    if parsed:
        # BranchParseResult(slug, mid8_token, lane_id) — return the slug portion
        slug: str = parsed.slug
        return slug

    match = re.match(r"^(\d{3}-[a-z0-9][a-z0-9-]*?)(?:-(?:lane-[a-z]))?$", branch_name)
    if match:
        return match.group(1)
    return None


def _resolve_mission_slug(repo_root: Path, mission_slug: str | None) -> str | None:
    if mission_slug:
        # F-001: ``--mission`` accepts handles (bare mid8, full ULID, numeric
        # prefix). Canonicalize at this boundary — the same pattern as the
        # agent ``_find_mission_slug`` helpers — so every downstream
        # composition (merge state, the committed ``kitty-specs/<slug>/
        # meta.json`` read, ``primary_feature_dir_for_mission``, the dry-run
        # payload) consumes the canonical directory name, never the raw
        # operator handle. Handles that resolve to no existing directory keep
        # their raw form, preserving the historical no-lanes / not-found
        # error behaviour downstream.
        from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

        try:
            candidate: Path = placement_seam(
                get_main_repo_root(repo_root), mission_slug
            ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        except StatusReadPathNotFound:
            # Fail-closed coordination window (coord worktree root
            # materialized, mission dir absent): fall back to the raw handle —
            # ``merge --abort`` relies on slug resolution staying non-raising
            # to clean up exactly that broken state.
            return mission_slug
        if candidate.exists():
            return candidate.name
        return mission_slug

    retcode, current_branch, _stderr = run_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if retcode != 0:
        return None
    return _extract_mission_slug(current_branch.strip())


def _merge_state_key_candidates(repo_root: Path, mission_slug: str | None) -> list[str]:
    """Return merge-state keys to try for a resolved mission slug.

    Modern merge state is keyed by mission ULID, while operators usually pass
    the mission directory slug. Legacy interrupted state may still be keyed by
    slug, so callers must try both.
    """
    if not mission_slug:
        return []
    keys: list[str] = []
    try:
        # FR-001 (#2185): the merge-state key is the canonical ``mission_id`` from
        # ``meta.json`` (PRIMARY_METADATA, PRIMARY-partition) — it lives ONLY on the
        # PRIMARY checkout post-#2106. The kind-blind resolver lands on the
        # STATUS-only ``-coord`` husk for a coord-topology mission, where reading
        # identity yields a missing/sentinel id → the wrong merge-state key. Route by
        # kind. This deliberately overturns the earlier documented carve-out that
        # kept the ``:63`` handle→dir-name canonicalization in
        # ``_resolve_mission_slug`` on the kind-blind ``candidate_`` resolver as the
        # no-silent-fallback boundary: that call now also routes through
        # PRIMARY_METADATA. It is safe because PRIMARY_METADATA never routes coord —
        # the old kind-blind call could land on the coord husk for a
        # coord-topology mission, this one always lands on primary — and the
        # ``.exists()`` check plus raw-handle fallback in ``_resolve_mission_slug``
        # preserve the non-raising ``merge --abort`` contract. Note for the next
        # reader: the surviving ``except StatusReadPathNotFound`` arm there is
        # currently unreachable for this kind (PRIMARY_METADATA never raises
        # CoordinationBranchDeleted); it would become live again if the kind
        # this call resolves against ever changed.
        feature_dir = placement_seam(
            get_main_repo_root(repo_root), mission_slug
        ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        if feature_dir.exists():
            identity = resolve_mission_identity(feature_dir)
            if identity.mission_id:
                keys.append(identity.mission_id)
    except Exception as exc:  # noqa: BLE001 - resume/abort must stay cleanup-safe
        logger.debug("Could not resolve merge state key for %s: %s", mission_slug, exc)
    keys.append(mission_slug)
    return list(dict.fromkeys(keys))


def _iter_merge_states_for_slug(
    repo_root: Path,
    mission_slug: str,
) -> list[tuple[str, MergeState]]:
    runtime_merge_dir = repo_root / KITTIFY_DIR / "runtime" / "merge"
    if not runtime_merge_dir.exists():
        return []

    matches: list[tuple[str, MergeState]] = []
    for candidate in sorted(runtime_merge_dir.iterdir()):
        if not candidate.is_dir():
            continue
        # A corrupt state.json for ONE mission must not abort resolving
        # ANOTHER mission's merge state (#2899 pre-PR squad) -- this scan
        # enumerates every mission's runtime dir, unlike a single explicit
        # ``load_state(repo_root, mission_id)`` call, which stays
        # fail-closed. Mirrors the two scan-all loops in ``merge/state.py``
        # (``load_state``'s own no-``mission_id`` scan and the
        # ``pending_coord_reconcile`` enumeration generator) that already
        # skip a sibling's unreadable state rather than propagating.
        try:
            state = load_state(repo_root, candidate.name)
        except MergeStateReadError:
            continue
        if state is not None and state.mission_slug == mission_slug:
            matches.append((candidate.name, state))
    return matches


def _load_merge_state_for_mission(
    repo_root: Path,
    mission_slug: str | None,
) -> MergeState | None:
    """Load merge state by modern key, legacy key, then stored mission_slug."""
    entry = _load_merge_state_entry_for_mission(repo_root, mission_slug)
    if entry is None:
        return None
    _key, state = entry
    return state


def _load_merge_state_entry_for_mission(
    repo_root: Path,
    mission_slug: str | None,
) -> tuple[str | None, MergeState] | None:
    """Load merge state plus the runtime key used to find it."""
    if not mission_slug:
        state = load_state(repo_root)
        return (None, state) if state is not None else None

    # NOTE (#2899): this candidate-key loop deliberately has NO
    # `except MergeStateReadError: continue` guard, unlike the scan-all loops in
    # `_iter_merge_states_for_slug` (below) and `merge/state.py`. Those scan
    # OTHER missions' state and must skip a sibling's corruption; here
    # `_merge_state_key_candidates` yields only THIS mission's own variant keys
    # (canonical mission_id + slug), so a corrupt candidate IS the target
    # mission's own state — fail-closed (let it raise) is correct. Do NOT
    # "harmonize" this into skip-on-corrupt; that would re-introduce the exact
    # fail-open bug WP07 closed.
    for key in _merge_state_key_candidates(repo_root, mission_slug):
        state = load_state(repo_root, key)
        if state is not None:
            return key, state

    for key, state in _iter_merge_states_for_slug(repo_root, mission_slug):
        return key, state
    return None


def _load_or_create_merge_state(
    *,
    main_repo: Path,
    mission_slug: str,
    canonical_id: str,
    target_branch: str,
    wp_order: list[str],
    push_requested: bool,
    skip_lanes: bool = False,
) -> tuple[MergeState, bool]:
    """Load canonical/legacy merge state, migrating legacy state to canonical.

    FOLD-F2 (terminus-safety-invariant-01M2XFT7, T021/FR-012): ``skip_lanes``
    is persisted only on a FRESH state (this run's own choice becomes the
    durable record for a genuinely-lanes.json-absent mission). A loaded
    (existing) state's own persisted value is never overwritten here --
    that survives resume exactly as recorded on the run that created it.
    """
    canonical_state = load_state(main_repo, canonical_id)
    if canonical_state is not None:
        return canonical_state, True

    entry = _load_merge_state_entry_for_mission(main_repo, mission_slug)
    if entry is not None:
        source_key, state = entry
        if state.mission_id != canonical_id:
            state.mission_id = canonical_id
            state.mission_slug = mission_slug
            save_state(state, main_repo)
            if source_key is not None and source_key != canonical_id:
                clear_state(main_repo, source_key)
        return state, True

    state = MergeState(
        mission_id=canonical_id,
        mission_slug=mission_slug,
        target_branch=target_branch,
        wp_order=wp_order,
        push_requested=push_requested,
        skip_lanes=skip_lanes,
    )
    save_state(state, main_repo)
    return state, False


def _clear_merge_state_for_mission(repo_root: Path, mission_slug: str | None) -> bool:
    """Clear every state file that could belong to *mission_slug*."""
    if not mission_slug:
        return bool(clear_state(repo_root))

    cleared = False
    seen: set[str] = set()
    for key in _merge_state_key_candidates(repo_root, mission_slug):
        seen.add(key)
        cleared = clear_state(repo_root, key) or cleared

    for key, _state in _iter_merge_states_for_slug(repo_root, mission_slug):
        if key in seen:
            continue
        cleared = clear_state(repo_root, key) or cleared
    return cleared


def _cleanup_merge_workspaces_for_state(
    repo_root: Path,
    *,
    mission_slug: str | None,
    state_entry: tuple[str | None, MergeState] | None,
) -> None:
    """Clean every runtime workspace key that could belong to a merge state."""
    cleanup_keys: list[str] = []
    if state_entry is not None:
        source_key, state = state_entry
        cleanup_keys.append(state.mission_id)
        if source_key:
            cleanup_keys.append(source_key)
        cleanup_keys.append(state.mission_slug)
    if mission_slug:
        cleanup_keys.extend(_merge_state_key_candidates(repo_root, mission_slug))
        cleanup_keys.append(mission_slug)

    for key in dict.fromkeys(key for key in cleanup_keys if key):
        cleanup_merge_workspace(key, repo_root)


def _resolve_target_branch(
    repo_root: Path,
    mission_slug: str | None,
    explicit_target: str | None,
) -> tuple[str, str | None]:
    """Resolve target branch and its provenance.

    Delegates to the shared :func:`resolve_merge_target_branch` so this command
    and ``orchestrator-api merge-mission`` resolve the target identically (reading
    the PRIMARY-checkout meta, never silently falling back to main when the
    mission declares a target_branch).
    """
    from specify_cli.core.paths import resolve_merge_target_branch

    resolved: tuple[str, str | None] = resolve_merge_target_branch(
        repo_root, mission_slug, explicit_target
    )
    return resolved


__all__ = [
    "_extract_mission_slug",
    "_resolve_mission_slug",
    "_iter_merge_states_for_slug",
    "_load_merge_state_for_mission",
    "_load_merge_state_entry_for_mission",
    "_load_or_create_merge_state",
    "_clear_merge_state_for_mission",
    "_cleanup_merge_workspaces_for_state",
    "_resolve_target_branch",
]
