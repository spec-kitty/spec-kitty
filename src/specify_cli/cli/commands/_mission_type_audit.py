"""Mission-type resolution health audit for ``doctor mission-type`` (FR-007,
FR-008, FR-009, NFR-004).

Combines the domain-layer classifier shape of
:mod:`specify_cli.status.identity_audit` (``IdentityState``,
``classify_mission``, ``audit_repo``, ``summarize``) with the CLI-glue/
report-builder shape of :mod:`specify_cli.cli.commands._identity_audit`
(``run_identity_audit``, ``_build_identity_json``, ``_compute_fail_on``) into
one sibling module — mission-type resolution logic already lives entirely in
``charter``/``doctrine`` and does not need a second domain-layer home (see
plan.md's Seam & Module Placement section).

Six-state classifier
---------------------
Every mission in ``kitty-specs/`` is classified into exactly one of the
FR-008 states, based on ``meta.json``'s ``mission_type`` (and legacy
``mission``) keys:

``resolved``
    ``mission_type`` is a present, non-blank string, is activated in the
    project charter, AND resolves through the project's layered mission-type
    roster (project > org > built-in) — the SAME
    :func:`~charter.missions.resolve_layered_mission_types` factory the
    runtime's ``_resolve_action_slot`` uses, NOT the built-in-only
    ``MissionTypeRepository.default()`` (which would misreport a
    legitimately-resolvable org- or project-pack custom type as
    ``activated-unresolvable``).

``activated-unresolvable``
    ``mission_type`` is a present, non-blank string and is activated in the
    project charter, but does not resolve in any layer of that roster. Mirrors
    the exact branch ``_resolve_action_slot`` hits when
    ``resolve_layered_mission_types(...).get(mission_type)`` is ``None`` — its
    ``raise UnknownMissionTypeError(...)`` — as the read-only classification
    twin of that raise.

``unknown``
    ``mission_type`` is a present, non-blank string but is not activated/
    registered anywhere.

``typeless``
    Either no ``mission_type`` key at all AND no legacy ``mission`` key
    holding a real string value, OR ``mission_type`` IS present but is
    blank (``""``), ``null``, or a non-string value. The key's own
    presence-with-a-value is what routes classification into this state —
    a present-but-empty ``mission_type`` value never falls through to check
    the legacy ``mission`` key (FR-008's closing sentence).

``legacy-key-only``
    No ``mission_type`` key at all, but the retired ``mission`` key holds a
    real string value.

``error``
    ``meta.json`` is unreadable or malformed for that mission directory
    (mirrors ``doctor identity``'s ``orphan``-on-unreadable-metadata
    posture).

Performance (NFR-004): the full audit over a typical ``kitty-specs/`` tree
must complete in under 2 seconds. ``existing_mission_types`` and the layered
mission-type roster (:func:`_resolve_layered_roster`) are each resolved ONCE
per audit run (in :func:`audit_mission_types`), not once per mission, to avoid
N redundant ``.kittify/config.yaml`` reads across the tree.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import typer
from rich.table import Table

from charter.activation.api import canonical_mission_type_key
from charter.activation.mission_type_profiles import existing_mission_types
from charter.missions import MissionTemplateRepository, resolve_layered_mission_types
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.core.utils import safe_is_dir

from ._doctor_shared import console

__all__ = ["run_mission_type_audit"]

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

MissionTypeStateLabel = Literal[
    "resolved",
    "activated-unresolvable",
    "unknown",
    "typeless",
    "legacy-key-only",
    "error",
]

#: All six FR-008 states, in report order — the single source of truth for
#: zero-filling summary counts (avoids repeating the state-name literals).
_ALL_STATES: tuple[MissionTypeStateLabel, ...] = (
    "resolved",
    "activated-unresolvable",
    "unknown",
    "typeless",
    "legacy-key-only",
    "error",
)


@dataclass
class MissionTypeState:
    """Audit result for a single mission directory.

    Attributes:
        path: Absolute path to the mission directory.
        slug: Directory name used as the mission slug.
        mission_type_raw: The raw ``mission_type`` string value as read from
            ``meta.json``, or ``None`` when the key is absent, blank, null,
            or a non-string value.
        resolved_key: The canonicalized mission-type key this mission
            resolves to (from either ``mission_type`` or the legacy
            ``mission`` key), or ``None`` when no key resolves.
        state: One of the six FR-008 states.
        error: Non-empty when ``meta.json`` could not be read / parsed.
    """

    path: Path
    slug: str
    mission_type_raw: str | None
    resolved_key: str | None
    state: MissionTypeStateLabel
    error: str | None = field(default=None)

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict."""
        return {
            "path": str(self.path),
            "slug": self.slug,
            "mission_type_raw": self.mission_type_raw,
            "resolved_key": self.resolved_key,
            "state": self.state,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _resolve_layered_roster(repo_root: Path) -> Mapping[str, object]:
    """Resolve the project's layered mission-type roster (project > org >
    built-in) — the SAME :func:`~charter.missions.resolve_layered_mission_types`
    factory the runtime's ``_resolve_action_slot`` uses.

    Using the built-in-only ``MissionTypeRepository.default()`` here would
    misreport a mission whose ``mission_type`` is a legitimately-resolvable
    org- or project-pack custom type as ``activated-unresolvable`` — it loads
    fine at runtime but is absent from the built-in bundle — a false positive
    that ``--fail-on activated-unresolvable`` would turn into a spurious CI
    failure. Resolved ONCE per audit run (NFR-004), not once per mission.
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — lazy; avoids circular

    pack_context = PackContext.from_config(repo_root)
    mission_types_dirs = (MissionTemplateRepository.default_missions_root() / "mission_types",)
    roster: Mapping[str, object] = resolve_layered_mission_types(
        mission_types_dirs, pack_context
    )
    return roster


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def _classify_present_key(
    raw_val: object, *, registered: list[str], roster: Mapping[str, object]
) -> tuple[str | None, MissionTypeStateLabel]:
    """Classify a mission whose ``meta.json`` HAS a ``mission_type`` key.

    A present-but-blank/null/non-string value classifies as ``typeless``
    without ever consulting the legacy ``mission`` key (FR-008).

    ``resolved`` vs ``activated-unresolvable`` keys off membership in the
    layered mission-type *roster* (project > org > built-in), NOT the
    built-in-only repository — mirroring the runtime's own
    ``resolve_layered_mission_types(...).get(mission_type) is None`` branch.
    """
    key = canonical_mission_type_key(raw_val) if isinstance(raw_val, str) else None
    if key is None:
        return None, "typeless"
    if key not in registered:
        return key, "unknown"
    if key in roster:
        return key, "resolved"
    return key, "activated-unresolvable"


def _classify_absent_key(raw_legacy: object) -> tuple[str | None, MissionTypeStateLabel]:
    """Classify a mission whose ``meta.json`` has NO ``mission_type`` key."""
    legacy_key = canonical_mission_type_key(raw_legacy) if isinstance(raw_legacy, str) else None
    if legacy_key is not None:
        return legacy_key, "legacy-key-only"
    return None, "typeless"


def classify_mission_type(
    feature_dir: Path, *, registered: list[str], roster: Mapping[str, object]
) -> MissionTypeState:
    """Classify a single mission directory into one of the six FR-008 states.

    Reads ``meta.json`` from *feature_dir* via the shared fail-closed reader,
    then runs it through the classification helpers. Per FR-008's Edge Case
    ("never silently skip it and never crash the whole audit run"), the ENTIRE
    body below — the ``meta.json`` read AND the classification helpers that
    consume it — runs under one broad-but-intentional ``except Exception``:
    any failure anywhere in this function classifies the mission as ``error``
    with the ``error`` field populated. It does **not** propagate an
    exception, so a bug in a single mission's classification can never abort
    the whole audit run (mirrors ``doctor identity``'s ``orphan`` posture).

    Args:
        feature_dir: Absolute path to a mission directory.
        registered: The project's activated mission-type IDs, computed ONCE
            per audit run by the caller (NFR-004).
        roster: The layered mission-type roster (project > org > built-in),
            resolved ONCE per audit run by the caller (NFR-004). Membership
            distinguishes ``resolved`` from ``activated-unresolvable``.

    Returns:
        A :class:`MissionTypeState` for the mission.
    """
    slug = feature_dir.name

    try:
        raw = load_meta_fail_closed(feature_dir) or {}
        if "mission_type" in raw:
            raw_val = raw["mission_type"]
            resolved_key, state = _classify_present_key(
                raw_val, registered=registered, roster=roster
            )
            mission_type_raw = raw_val if isinstance(raw_val, str) else None
        else:
            resolved_key, state = _classify_absent_key(raw.get("mission"))
            mission_type_raw = None
    except Exception as exc:
        # Intentional broad catch: FR-008 requires that ANY classification
        # failure for one mission report as `error` rather than crash the
        # whole audit run (see docstring above).
        return MissionTypeState(
            path=feature_dir,
            slug=slug,
            mission_type_raw=None,
            resolved_key=None,
            state="error",
            error=str(exc),
        )

    return MissionTypeState(
        path=feature_dir,
        slug=slug,
        mission_type_raw=mission_type_raw,
        resolved_key=resolved_key,
        state=state,
    )


# ---------------------------------------------------------------------------
# Repo-level audit
# ---------------------------------------------------------------------------


def audit_mission_types(repo_root: Path) -> list[MissionTypeState]:
    """Walk ``kitty-specs/`` and classify every mission directory.

    Mirrors :func:`specify_cli.status.identity_audit.audit_repo`'s walk
    shape exactly (same ``safe_is_dir``/``KITTY_SPECS_DIR`` pattern) —
    deliberately, not by omission. A raw walk (rather than routing through
    ``specify_cli.context.mission_resolver.FsMissionResolver.all_missions()``)
    is a **documented distinct corpus walk**
    (``tests/architectural/test_mission_resolver_walker_gate.py``'s
    ``_LEGACY_WALKER_ALLOWLIST``), the same anti-fold carve-out the port's own
    ADR (``docs/adr/3.x/2026-07-08-1-mission-resolver-port.md``, C-001) grants
    ``status/identity_audit.py``: ``FsMissionResolver.all_missions()``
    silently skips missions whose ``meta.json`` lacks ``mission_id`` (legacy,
    pre-083 missions), but the six-state FR-008 classifier must see EVERY
    mission directory — including id-less ones — to report ``typeless``/
    ``unknown``/``error`` states honestly. Routing this walk through the
    resolver would make the audit blind to exactly the missions it exists to
    audit, mirroring the resolver's own documented rationale for exempting
    ``identity_audit.py`` rather than folding it in.
    ``registered`` and the layered mission-type roster are each resolved ONCE
    before the loop (NFR-004) rather than per mission.

    Args:
        repo_root: Path to the repository root (contains ``kitty-specs/``).

    Returns:
        List of :class:`MissionTypeState` objects, one per mission directory.
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    states: list[MissionTypeState] = []
    try:
        if not safe_is_dir(specs_dir):
            return []
        entries = sorted(specs_dir.iterdir())
    except OSError:
        return []

    registered = existing_mission_types(repo_root)
    roster = _resolve_layered_roster(repo_root)

    for entry in entries:
        try:
            is_mission_dir = safe_is_dir(entry)
        except OSError:
            continue  # unstattable entry: same skip as "not a directory"
        if not is_mission_dir:
            continue  # skip README.md, templates, etc.
        states.append(classify_mission_type(entry, registered=registered, roster=roster))

    return states


# ---------------------------------------------------------------------------
# Summarise
# ---------------------------------------------------------------------------


def summarize_mission_types(states: list[MissionTypeState]) -> dict[str, object]:
    """Aggregate a list of :class:`MissionTypeState` objects into a summary dict.

    Returns a dict with ``counts``: ``{state: int}`` for all six states,
    zero-filled (mirrors :func:`specify_cli.status.identity_audit.summarize`).
    """
    counts: dict[str, int] = dict.fromkeys(_ALL_STATES, 0)
    for s in states:
        counts[s.state] += 1
    return {"counts": counts}


# ---------------------------------------------------------------------------
# CLI glue
# ---------------------------------------------------------------------------


def _scope_to_mission(
    all_states: list[MissionTypeState], mission: str
) -> list[MissionTypeState]:
    """Filter states to a single mission slug."""
    return [s for s in all_states if s.slug == mission]


def _compute_fail_on(
    fail_on: str | None, all_states: list[MissionTypeState]
) -> tuple[set[str], bool]:
    """Parse ``--fail-on`` states and determine whether the gate is triggered.

    Rejects any token that is not one of the six FR-008 state names via
    :class:`typer.BadParameter` (exit code 2), so a misspelled state — e.g.
    ``--fail-on unkown`` — fails loudly instead of silently matching nothing
    and exiting 0 (a vacuous-green CI gate).
    """
    if not fail_on:
        return set(), False
    fail_on_states = {s.strip() for s in fail_on.split(",") if s.strip()}
    unknown = sorted(fail_on_states - set(_ALL_STATES))
    if unknown:
        raise typer.BadParameter(
            f"unknown --fail-on state(s): {', '.join(unknown)}; "
            f"valid states are: {', '.join(_ALL_STATES)}"
        )
    fail_on_triggered = any(s.state in fail_on_states for s in all_states)
    return fail_on_states, fail_on_triggered


def _build_mission_type_json(
    all_states: list[MissionTypeState],
    summary: dict[str, object],
    fail_on_triggered: bool,
) -> dict[str, object]:
    """Build the ``--json`` report payload for ``doctor mission-type``."""
    return {
        "summary": summary["counts"],
        "missions": [s.to_dict() for s in all_states],
        "fail_on_triggered": fail_on_triggered,
    }


def _print_mission_type_summary_table(
    all_states: list[MissionTypeState], summary: dict[str, object]
) -> None:
    """Print the per-state count table (extracted to keep callers <=15 CC)."""
    counts_dict: dict[str, int] = summary["counts"]  # type: ignore[assignment]
    total = len(all_states)
    console.print(f"\n[bold]Mission Type Audit[/bold] — {total} mission(s)\n")

    summary_table = Table(box=None, padding=(0, 2), show_edge=False)
    summary_table.add_column("State", style="cyan", min_width=10)
    summary_table.add_column("Count", justify="right", min_width=6)
    _state_styles = {
        "resolved": "[green]",
        "activated-unresolvable": "[red]",
        "unknown": "[red]",
        "typeless": "[yellow]",
        "legacy-key-only": "[yellow]",
        "error": "[red]",
    }
    for state_name in _ALL_STATES:
        count = counts_dict.get(state_name, 0)
        styled = f"{_state_styles.get(state_name, '')}{state_name}[/]"
        summary_table.add_row(styled, str(count))
    console.print(summary_table)
    console.print()


def _print_mission_type_human(
    all_states: list[MissionTypeState],
    summary: dict[str, object],
    fail_on_states: set[str],
    fail_on_triggered: bool,
    fail_on: str | None,
) -> None:
    """Render the human-readable mission-type report to the console."""
    _print_mission_type_summary_table(all_states, summary)

    if fail_on_triggered:
        console.print(
            f"[bold red]FAIL:[/bold red] --fail-on {fail_on!r} triggered "
            f"(one or more missions in: {', '.join(sorted(fail_on_states))})"
        )


def run_mission_type_audit(
    repo_root: Path, json_output: bool, mission: str | None, fail_on: str | None
) -> None:
    """Entry point for ``doctor mission-type`` — mirrors ``run_identity_audit``'s
    exact exit-code contract.

    *repo_root* is resolved by the ``doctor.py`` command shell (which owns the
    patchable ``locate_project_root`` seam) and injected here, preserving the
    same monkeypatch contract as ``run_identity_audit``.
    """
    all_states = audit_mission_types(repo_root)

    if mission is not None:
        scoped = _scope_to_mission(all_states, mission)
        if not scoped:
            console.print(f"[red]Error:[/red] Mission not found: {mission!r}")
            raise typer.Exit(1)
        all_states = scoped

    summary = summarize_mission_types(all_states)
    fail_on_states, fail_on_triggered = _compute_fail_on(fail_on, all_states)

    if json_output:
        report = _build_mission_type_json(all_states, summary, fail_on_triggered)
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        sys.stdout.flush()
        raise typer.Exit(1 if fail_on_triggered else 0)

    _print_mission_type_human(all_states, summary, fail_on_states, fail_on_triggered, fail_on)
    raise typer.Exit(1 if fail_on_triggered else 0)
