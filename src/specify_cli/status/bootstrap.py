"""Bootstrap canonical status state for work packages in a feature.

Scans WP files in a feature directory, checks the canonical event log
for existing state, and emits initial ``planned`` events for any WP
that lacks one.  After seeding, materializes ``status.json`` so the
snapshot is immediately consistent.

This module uses the transactional status-transition pipeline; it does
not reimplement event emission or validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from specify_cli.core.commit_guard import GuardCapability
from specify_cli.frontmatter import FrontmatterError
from specify_cli.status.models import TransitionRequest
from specify_cli.status.reducer import materialize
from specify_cli.status.wp_metadata import read_wp_frontmatter

if TYPE_CHECKING:
    from specify_cli.core.owned_mission import OwnedMission

logger = logging.getLogger(__name__)

# Possible detail values stored in BootstrapResult.wp_details
_INITIALIZED = "initialized"
_ALREADY_EXISTS = "already_exists"
_WOULD_SEED = "would_seed"
_SKIPPED_MALFORMED = "skipped_malformed"


@dataclass
class BootstrapResult:
    """Outcome of a bootstrap operation."""

    total_wps: int = 0
    already_initialized: int = 0
    newly_seeded: int = 0
    skipped: int = 0
    wp_details: dict[str, str] = field(default_factory=dict)


def _collect_wp_ids(tasks_dir: Path, result: BootstrapResult) -> list[str]:
    """Return valid WP IDs discovered in ``tasks_dir`` and record skips."""
    wp_ids: list[str] = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            meta, _body = read_wp_frontmatter(wp_file)
        except (FrontmatterError, ValidationError):
            logger.warning("Skipping %s: malformed frontmatter", wp_file.name)
            result.skipped += 1
            result.wp_details[wp_file.stem] = _SKIPPED_MALFORMED
            continue

        wp_id = meta.work_package_id
        if not wp_id:
            logger.warning(
                "Skipping %s: missing or invalid work_package_id",
                wp_file.name,
            )
            result.skipped += 1
            result.wp_details[wp_file.stem] = _SKIPPED_MALFORMED
            continue

        wp_ids.append(wp_id)
    return wp_ids


def _classify_wp_ids(
    wp_ids: list[str],
    initialized_wp_ids: set[str],
    result: BootstrapResult,
) -> list[str]:
    """Update ``result`` counts/details and return WPs that still need seeding."""
    wps_to_seed: list[str] = []
    for wp_id in wp_ids:
        if wp_id in initialized_wp_ids:
            result.already_initialized += 1
            result.wp_details[wp_id] = _ALREADY_EXISTS
            continue
        wps_to_seed.append(wp_id)
    return wps_to_seed


def bootstrap_canonical_state(
    feature_dir: Path,
    mission_slug: str,
    *,
    dry_run: bool = False,
    capability: GuardCapability = GuardCapability.STANDARD,
    repo_root: Path | None = None,
    effective_root: Path | None = None,
    owned_mission: OwnedMission | None = None,
) -> BootstrapResult:
    """Ensure every WP in a feature has canonical status state.

    Scans ``feature_dir/tasks/`` for ``WP*.md`` files, reads each
    file's frontmatter to extract ``work_package_id``, then checks
    the canonical event log for existing events.  Uninitialized WPs
    receive a ``planned`` event via the transactional status emitter.

    After all events are emitted (unless *dry_run*), calls
    :func:`materialize` to write a fresh ``status.json``.

    Args:
        feature_dir: Path to the kitty-specs feature directory.
        mission_slug: Feature identifier (e.g. ``"060-feature-name"``).
        dry_run: If ``True``, report what would happen without mutating
            any files.
        capability: Asserted-at-the-surface authorization for the seed
            commit (FR-008). Defaults to ``GuardCapability.STANDARD``: the
            transactional seed commit lands on the (unprotected) coordination
            branch, so no protected-flow capability is required, and a
            protected destination is refused. Test fixtures that seed on a
            protected branch may pass ``GuardCapability.TEST_MODE``.

    Returns:
        A :class:`BootstrapResult` with counts and per-WP detail strings.
    """
    # Lazy import breaks an import cycle: ``status/__init__`` imports this module
    # (bootstrap), and ``coordination.status_transition`` imports back into the
    # status package via ``coordination.transaction``. Importing the transactional
    # helpers at call time (rather than module load) lets ``status/__init__``
    # finish initializing before the coordination package is touched.
    from specify_cli.coordination.status_transition import (
        emit_status_transition_transactional,
        read_events_transactional,
    )

    result = BootstrapResult()

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return result

    wp_ids = _collect_wp_ids(tasks_dir, result)
    if not wp_ids:
        return result

    result.total_wps = len(wp_ids)

    # Read existing events from the same branch/worktree targeted by the
    # transactional writer, so coordination-branch missions do not reseed.
    existing_events = read_events_transactional(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        **({"repo_root": repo_root, "effective_root": effective_root} if effective_root is not None else {}),
    )
    initialized_wp_ids: set[str] = {e.wp_id for e in existing_events}

    wps_to_seed = _classify_wp_ids(wp_ids, initialized_wp_ids, result)

    if dry_run:
        for wp_id in wps_to_seed:
            result.wp_details[wp_id] = _WOULD_SEED
        result.newly_seeded = len(wps_to_seed)
        return result

    # Emit planned events for uninitialized WPs
    for wp_id in wps_to_seed:
        # T030: genesis -> planned is a real allowed edge post-WP01 FSM refactor,
        # so force=True is no longer needed and the event no longer records "force": true
        # on every canonical bootstrap seed.
        emit_status_transition_transactional(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                to_lane="planned",
                actor="finalize-tasks",
                reason="canonical bootstrap",
                repo_root=repo_root,
                effective_root=effective_root,
                # #3866: thread the caller's validated value object so the
                # per-WP identity derivation does not re-run
                # ``resolve_owned_mission`` for every seeded WP.
                owned_mission=owned_mission,
            ),
            capability=capability,
        )
        result.newly_seeded += 1
        result.wp_details[wp_id] = _INITIALIZED

    # Materialize snapshot after all events are emitted.
    # The transactional emitter materializes per event, but
    # we call it once more to guarantee the final snapshot is coherent
    # across all newly seeded WPs.
    if wps_to_seed:
        materialize(feature_dir)

    return result
