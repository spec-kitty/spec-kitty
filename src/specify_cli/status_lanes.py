"""Shared status-lane constants without importing status orchestration."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

CANONICAL_LANES: tuple[str, ...] = (
    "planned",
    "claimed",
    "in_progress",
    "for_review",
    "in_review",
    "approved",
    "done",
    "blocked",
    "canceled",
)

LANE_ALIASES: dict[str, str] = {
    "doing": "in_progress",
    # NOTE: "in_review" is NO LONGER an alias — it is a first-class lane (FR-012a)
}

TERMINAL_LANES: frozenset[str] = frozenset({"done", "canceled"})

#: Lanes that are an acceptable mission ending *unconditionally* — approved and
#: done are always a valid ending regardless of provenance. ``canceled`` is a
#: TERMINAL lane (see :data:`TERMINAL_LANES`) but is deliberately NOT here:
#: acceptability, terminality, and provenance are three separable decisions
#: (post-spec squad F2). ``canceled`` is acceptable only with operator-authored
#: provenance, decided in :func:`is_acceptable_ending`.
_UNCONDITIONALLY_ACCEPTABLE_LANES: frozenset[str] = frozenset({"approved", "done"})

#: The ``reason_source`` discriminator value that marks a canceled event's
#: reason as operator-authored (as opposed to the CLI's auto-synthesized
#: default). Projected onto the reduced snapshot by
#: ``specify_cli.status.reducer`` (FR-001 / C-002).
OPERATOR_REASON_SOURCE = "operator"


def is_acceptable_ending(lane: str, *, has_provenance: bool) -> bool:
    """Return whether ``lane`` is an acceptable mission ending.

    The single acceptable-ending authority (FR-005), consumed by ``accept``,
    ``merge``, and the dependency-readiness gate. Terminality
    (``{done, canceled}``), acceptability (``{approved, done}``), and provenance
    are three separable decisions (post-spec squad F2): this predicate must NOT
    be confused with a terminal-lane check.

    Truth table (contract ``acceptable-ending-predicate.md``):

    * ``approved`` / ``done`` → ``True`` (``has_provenance`` ignored).
    * ``canceled`` → ``True`` iff ``has_provenance`` (operator-authored).
    * every other lane → ``False``.

    Pure: no I/O. Provenance is resolved by the caller from the reduced
    snapshot via :func:`has_operator_provenance` (C-002). References the
    canonical :data:`TERMINAL_LANES` set only to classify ``canceled``.
    """
    if lane in _UNCONDITIONALLY_ACCEPTABLE_LANES:
        return True
    # ``done`` already returned above, so the only remaining TERMINAL lane is
    # ``canceled`` — the sole lane whose acceptability turns on provenance.
    if lane in TERMINAL_LANES:
        return has_provenance
    return False


def has_operator_provenance(wp_snapshot: Mapping[str, Any] | None) -> bool:
    """Return whether a reduced WP snapshot carries operator-authored cancellation provenance.

    The single shared reader of WP01's ``reason_source`` snapshot slot (paula:
    avoid a 3-site ``reason_source == "operator"`` whack-a-field). ``accept``
    (WP02), ``merge`` (WP03), and the dependency gate (WP04) all read provenance
    through this one accessor rather than inlining the slot name.

    Returns ``False`` for a ``None`` snapshot, a snapshot with no
    ``reason_source`` key (a legacy snapshot, or any non-canceled WP — the slot
    is only ever projected onto a canceled snapshot, NFR-002), and a synthetic
    cancellation. Returns ``True`` only when ``reason_source`` is exactly
    ``operator``. Pure: no I/O.
    """
    if wp_snapshot is None:
        return False
    return wp_snapshot.get("reason_source") == OPERATOR_REASON_SOURCE


def mission_terminal_acceptability(
    work_packages: Mapping[str, Mapping[str, Any]],
    *,
    expected_wp_ids: Collection[str] | None = None,
) -> tuple[bool, list[str]]:
    """Return whether every WP in ``work_packages`` has reached an acceptable ending.

    The single mission-level, provenance-aware readiness aggregate (FR-009,
    contract ``C-SHARED-AUTHORITY``), consumed by ``merge`` and ``mission
    close`` so neither re-inlines its own acceptable-ending loop (C-001).
    ``accept``'s lane-bucket views (``gates_core``/``summary_core``) are
    deliberately provenance-blind and are NOT rerouted onto this aggregate —
    see the WP01 scope note in ``terminus-safety-invariant-01M2XFT7``.

    ``work_packages`` is a mapping of WP id to a reduced snapshot dict in the
    shape ``StatusSnapshot.work_packages`` already uses (at least a ``lane``
    key, and — for a ``canceled`` WP — the optional ``reason_source``
    provenance slot). For each WP the per-lane authority
    :func:`is_acceptable_ending` is consulted with provenance resolved via
    :func:`has_operator_provenance`; the acceptable-ending rule is never
    re-derived here.

    ``expected_wp_ids``, when given, is the full set of WP ids the mission
    DECLARES (e.g. ``run.all_wp_ids``). Any id in ``expected_wp_ids`` that is
    ABSENT from ``work_packages`` (no status event on the read surface at
    all) is folded into ``missing`` too — never silently dropped. A gate
    meant to be fail-CLOSED cannot fail-open on a WP the reducer has no
    record of; a missing snapshot entry is strictly less evidence of
    readiness than an ``in_progress`` one, so it must refuse, not pass. This
    is the SINGLE shared home for that absent-WP fail-closed rule (previously
    duplicated in ``merge.executor._assert_mission_terminal_ready`` and
    re-inlined, undocumented, by ``policy.merge_gates``'s evidence gate).
    Default ``None`` preserves the exact prior behavior (only WPs actually
    present in ``work_packages`` are considered).

    Returns ``(True, [])`` when every WP is at an acceptable ending —
    including the vacuous case of no WPs at all, and the boundary case where
    every WP is a provenance-cancelled ``canceled``. Otherwise returns
    ``(False, missing)`` where ``missing`` is the sorted list of WP ids not
    yet at an acceptable ending. Pure: no I/O.
    """
    missing = [
        wp_id
        for wp_id, snapshot in work_packages.items()
        if not is_acceptable_ending(
            str(snapshot.get("lane", "")),
            has_provenance=has_operator_provenance(snapshot),
        )
    ]
    if expected_wp_ids is not None:
        missing.extend(wp_id for wp_id in expected_wp_ids if wp_id not in work_packages)
    missing = sorted(set(missing))
    return (not missing, missing)
