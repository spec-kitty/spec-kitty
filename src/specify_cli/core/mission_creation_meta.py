"""``meta.json`` assembly and the coordination-branch mint it triggers.

Moved from ``mission_creation.py`` (#5634); reshaped by the decision-core and seam
cleanups. ``mission_creation`` re-exports every name defined here. A call to a name
tests patch on ``mission_creation``, or to a function another ``mission_creation*``
module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mission_runtime import (
    MissionTopology,
)
from specify_cli.core.mission_creation_decisions import (
    meta_flag_patch,
)
from kernel.clock import now_utc_iso
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.core.mission_creation_errors import MissionCreationError
from specify_cli.core.mission_creation_identity import _Purpose


# coord-primary-partition-lock WP02 (T009 / S1192): the ``meta`` field names
# repeated across the metadata-assembly block below (default + event-emission
# reads) hoisted to named constants rather than restated as literals.
_META_KEY_MISSION_TYPE = "mission_type"


_META_KEY_CREATED_AT = "created_at"


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
    topology: MissionTopology,
    force_recreate_coordination_branch: bool,
    created_at: str | None = None,
) -> _MetaBuild:
    """Assemble ``meta.json`` and mint the coordination branch for it (not persisted).

    Sections 6, 6.5 and 6.6 of the pre-decomposition body (T051): the
    canonical machine-facing identity fields, the create-time retention
    opt-in (#3131 FR-009, field-absent-unless-True), the per-mission
    coordination branch mint (WP03 / issue #1348, #2218 -- ONLY for the
    coordination-bearing shapes), and the topology corroboration (FR-002 /
    #2069, #2218): the operator's explicit choice is stored verbatim and
    only CORROBORATED (never re-derived) against the minted coordination
    state.

    The orchestrator then runs the protected-target mint, which
    may set ``meta["mission_branch"]``, and persists the dict with
    :func:`_write_create_meta`. ``minted_mission_branch`` is therefore always
    ``None`` here; the orchestrator fills it in.

    ``created_at``: the injected creation stamp, or ``None`` to read the
    clock (:func:`kernel.clock.now_utc_iso`) here, exactly when the stamp was
    always taken. An existing ``meta.json`` value still wins (``setdefault``).
    """
    from specify_cli.core import mission_creation as _mc

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
    meta.setdefault(_META_KEY_CREATED_AT, created_at if created_at is not None else now_utc_iso())
    # #3131 FR-009 retention and #5100 FR-008 (WP08) override: written ONLY
    # when True, never a written ``false``; same keys, same insertion order.
    meta.update(
        meta_flag_patch(
            pr_bound=pr_bound,
            retain_branches=retain_branches,
            retain_worktrees=retain_worktrees,
            commit_to_target=commit_to_target,
        )
    )

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
            coordination_branch_pre_seed_tip = _mc._rev_parse_or_none(resolved_root, coordination_outcome.branch_name)

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

    return _MetaBuild(
        meta=meta,
        coordination_branch_created=coordination_branch_created_flag,
        coordination_branch_skipped_reason=coordination_branch_skipped_reason,
        coordination_branch_pre_seed_tip=coordination_branch_pre_seed_tip,
    )


def _write_create_meta(feature_dir: Path, meta: dict[str, Any], mission: str | None) -> None:
    """Persist ``meta.json`` (and the documentation mission's initial state).

    The tail of the former single-step ``_build_create_meta``, verbatim: the orchestrator
    calls it right after the protected-target mint, so the file carries the
    minted ``mission_branch`` exactly as before.

    The birth write of ``meta.json`` runs under the Mission write lock like every
    other ``meta.json`` writer (FR-001/FR-020), so a writer that races the create
    (a reopen, discard or tracker binding of the same slug) is serialised rather
    than silently overwritten. ``fallback_to_dir_name`` covers the window before a
    coordination key is readable; the nested ``set_documentation_state`` re-enters
    the same re-entrant lock on this thread.
    """
    from specify_cli.mission_metadata import set_documentation_state, write_meta
    from specify_cli.status import mission_write_lock

    with mission_write_lock(feature_dir, fallback_to_dir_name=True):
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
