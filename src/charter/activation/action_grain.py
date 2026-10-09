"""Action-grain aggregation — the single canonical action-grain union module.

A mission type's *action grain* is the union, across every action a mission
type defines, of the doctrine artifacts scoped to that action (an
``ActionIndex`` per ``<mission_type>/actions/<action>/index.yaml``,
``src/charter/offering/missions/action_index.py``). Three consumers each need this
union:

* the resolver (``charter.activation.mission_type_profiles.resolve_mission_type_context``,
  WP03) — threads the real action grain into ``ResolvedGovernance.from_grains``
  instead of the placeholder ``_EMPTY_GRAIN``;
* the integrity gate (WP04) — asserts no artifact URN is declared in both the
  type grain and the action grain (FR-013);
* the reconciled test tier (WP05).

This module is the **single** home of that union logic (C-002) — no other
module re-implements the ``actions/*/index.yaml`` scan or the per-kind
concatenation.

Layer rule
----------
``src/charter/`` MUST NOT import ``specify_cli`` (C-001); importing from
``doctrine`` is the canonical dependency direction and is used here
(:mod:`charter.offering.missions.action_index`).

Circular-import guard
----------------------
``charter.activation.mission_type_profiles`` owns the canonical ``_GOVERNANCE_KINDS``
governance-kind list and will (WP03) import :func:`aggregate_action_grain`
back to thread the real action grain into its resolver. To avoid a
module-level import cycle, every reference this module makes to
``charter.activation.mission_type_profiles`` (or the sibling
``charter.activation.mission_type_profile_repository``) is a **lazy, function-local**
import — the same ``# noqa: PLC0415`` convention ``mission_type_profiles``
itself already uses for its own cycle-prone imports. Do not hoist these to
module level.

Scope cap
---------
Aggregation reads the **built-in** missions root only
(``builtin_missions_root()`` =
``src/charter/offering/missions``). No project/org action-index overlay exists today;
building a multi-root or field-merge engine here is explicitly out of scope
for this module.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.missions.action_index import ActionIndex, load_action_index

# ``aggregate_action_grain`` and ``scan_builtin_cross_grain_duplicates`` are
# exported: both now have a real ``src`` caller.  ``aggregate_action_grain``
# is the seam ``charter.activation.mission_type_profiles`` imports; ``scan_builtin_cross_grain_duplicates``
# is called from ``specify_cli.cli.commands._charter_pack_collect._run_cross_grain_check``
# (WP05, #2666), which wires the FR-013 built-in dup-scan into
# ``spec-kitty doctor charter-packs`` so the integrity gate is load-bearing outside
# pytest. ``action_index_to_mapping`` stays out of ``__all__`` — it is a pure
# internal adapter with no runtime caller (only exercised by its own tests) —
# so the symbol-level dead-code gate (``tests/architectural/test_no_dead_symbols.py``)
# does not flag it.
__all__ = [
    "aggregate_action_grain",
    "scan_builtin_cross_grain_duplicates",
]


def action_index_to_mapping(index: ActionIndex) -> dict[str, list[str]]:
    """Project an :class:`ActionIndex` onto the canonical governance-kind keys.

    Pure, no I/O. ``ActionIndex``'s seven doctrine-artifact fields
    (``directives`` / ``tactics`` / ``paradigms`` / ``styleguides`` /
    ``toolguides`` / ``procedures`` / ``agent_profiles``) map 1:1 onto
    ``charter.activation.mission_type_profiles._GOVERNANCE_KINDS`` by field name, so the
    keys (and their order) are read from that single source rather than
    re-declared here.

    Parameters
    ----------
    index:
        The loaded (or fallback-empty) action index.

    Returns
    -------
    dict[str, list[str]]
        One list per governance kind, each a fresh copy of the corresponding
        ``index`` field. An empty ``ActionIndex`` yields all-empty lists.
    """
    from charter.activation.mission_type_profiles import _GOVERNANCE_KINDS  # noqa: PLC0415 — lazy; avoids charter.activation.action_grain <-> charter.activation.mission_type_profiles import cycle (T004)

    return {kind: list(getattr(index, kind)) for kind in _GOVERNANCE_KINDS}


def aggregate_action_grain(built_in_dir: Path, mission_type: str) -> dict[str, list[str]]:
    """Union every action's grain for ``mission_type`` into one mapping per kind.

    Enumerates ``<built_in_dir>/<mission_type>/actions/*`` (sorted for
    deterministic ordering), loads each action's :class:`ActionIndex` via
    :func:`~charter.offering.missions.action_index.load_action_index`, and
    concatenates the per-action mappings (:func:`action_index_to_mapping`)
    for each governance kind.

    De-duplication is deliberately **not** performed here: this function only
    concatenates. The *cross-grain* collision (an URN in both the type grain
    and this action grain) is what ``ResolvedGovernance.from_grains`` /
    ``_merge_disjoint_grain`` detects and raises on (FR-013), so the raw
    (undeduped) lists must reach that caller intact. Note the asymmetry: a
    *cross-action* repeat (the same URN declared by two of this type's actions)
    is **not** a double declaration — ``_merge_disjoint_grain`` silently
    deduplicates it when unioning the two grains; only the type-vs-action
    overlap is an error. This function does not police cross-action repeats.

    A mission type with no ``actions/`` directory at all degrades to an
    empty-content mapping (every shipped type currently has an ``actions/``
    directory; this branch exists as a defensive fallback and is exercised
    by a synthetic fixture, not a real built-in type). A mission type whose
    action indexes are all *intentionally* empty (e.g. ``plan``) also
    resolves to an empty-content mapping — that is empty content, not a
    missing directory.

    Parameters
    ----------
    built_in_dir:
        The shipped missions root (``builtin_missions_root()``
        == ``src/charter/offering/missions``), **not** a project ``repo_root``.
    mission_type:
        The mission type key (e.g. ``"software-dev"``).

    Returns
    -------
    dict[str, list[str]]
        One list per governance kind, keyed by
        ``charter.activation.mission_type_profiles._GOVERNANCE_KINDS``, each the
        concatenation of every action's contribution (order: actions sorted
        by directory name, kinds in ``_GOVERNANCE_KINDS`` order).
    """
    from charter.activation.mission_type_profiles import _GOVERNANCE_KINDS  # noqa: PLC0415 — lazy; avoids charter.activation.action_grain <-> charter.activation.mission_type_profiles import cycle (T005)

    merged: dict[str, list[str]] = {kind: [] for kind in _GOVERNANCE_KINDS}

    actions_dir = built_in_dir / mission_type / "actions"
    if not actions_dir.is_dir():
        return merged

    action_names = sorted(p.name for p in actions_dir.iterdir() if p.is_dir())
    for action_name in action_names:
        index = load_action_index(built_in_dir, mission_type, action_name)
        mapping = action_index_to_mapping(index)
        for kind in _GOVERNANCE_KINDS:
            merged[kind].extend(mapping[kind])

    return merged


def scan_builtin_cross_grain_duplicates(built_in_dir: Path | None = None) -> list[str]:
    """Assert no cross-grain URN duplicate exists for any shipped mission type.

    IC-11 dup-scan: for every shipped mission type — enumerated from the
    doctrine ``mission_types/*.yaml`` source via
    :class:`~charter.offering.missions.mission_type_repository.MissionTypeRepository`,
    NOT a hardcoded roster, so a newly-shipped type is covered automatically —
    loads the type grain (``governance-profile.yaml`` ``selected_*``) and the
    action grain (:func:`aggregate_action_grain`) and unions them through
    ``ResolvedGovernance.from_grains`` — the same union the resolver uses —
    which raises :class:`~charter.activation.mission_type_profiles.CrossGrainDoubleDeclarationError`
    the moment one artifact URN appears in both grains (FR-013). This is the
    **single** dup-scan authority (C-002): WP04's integrity gate calls this
    function rather than re-implementing the union/collision check.

    Parameters
    ----------
    built_in_dir:
        The shipped missions root. Defaults to
        ``builtin_missions_root()``
        (``src/charter/offering/missions``).

    Returns
    -------
    list[str]
        The mission types that were scanned and confirmed disjoint — every
        shipped type on success (never a partial list, since a collision
        raises instead of being skipped).

    Raises
    ------
    charter.activation.mission_type_profiles.CrossGrainDoubleDeclarationError
        If any artifact URN is declared in both the type grain and the
        action grain for any shipped mission type.
    """
    # Lazy: avoids a charter.activation.action_grain <-> charter.activation.mission_type_profile_repository
    # import cycle (T006).
    from charter.activation.mission_type_profile_repository import (  # noqa: PLC0415
        builtin_missions_root,
    )
    # Lazy: avoids a charter.activation.action_grain <-> charter.activation.mission_type_profiles import
    # cycle (T006).
    from charter.activation.mission_type_profiles import (  # noqa: PLC0415
        ResolvedGovernance,
        _load_mission_type_profile,
        _profile_type_grain,
    )
    # Lazy: the doctrine mission_types/*.yaml roster (post-review hardening —
    # enumerate the derived source, not a hardcoded list, so a new type is
    # auto-covered).
    from charter.offering.missions.mission_type_repository import (  # noqa: PLC0415
        MissionTypeRepository,
    )

    # consume the promoted builtin_missions_root() — WP06 #2668
    root = built_in_dir if built_in_dir is not None else builtin_missions_root()

    # Enumerate the mission types from the doctrine ``mission_types/*.yaml`` source
    # (the same source the DRG generator reads), NOT a hardcoded roster — so a
    # newly-shipped mission type is automatically covered by this forward-looking
    # gate. ``MissionTypeRepository`` additionally fails loud on a malformed
    # mission-type YAML (id/stem mismatch or invalid schema).
    scanned: list[str] = []
    for mission_type in MissionTypeRepository(root / "mission_types").ids():
        profile = _load_mission_type_profile(mission_type)
        type_grain = _profile_type_grain(profile)
        action_grain = aggregate_action_grain(root, mission_type)
        ResolvedGovernance.from_grains(type_grain=type_grain, action_grain=action_grain)
        scanned.append(mission_type)

    return scanned
