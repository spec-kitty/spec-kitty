"""Doctrine/profile health *render* helpers for ``spec-kitty doctor doctrine``.

Pure extraction (mission ``tooling-stability-guard-coherence-01KTRC04`` WP08,
issue #1623 / DIRECTIVE_013 / adversarial finding I-10): the doctrine- and
profile-health *rendering* helpers that grew on ``doctor.py`` during mission
``org-doctrine-profile-integrity-activation-closure-01KT1TV1`` belong beside the
single-source health model in :mod:`._doctrine_health`.  These helpers turn a
:class:`._doctrine_health.DoctrineHealthReport` (plus the registry pack entries
and selection block assembled by ``doctor.py``'s collectors) into operator
output — human Rich console lines and the ``--json`` payload.

This is a **pure move**: the bodies are verbatim relocations of the helpers that
previously lived in ``doctor.py`` (only the module docstring and the imports
differ).  The data *collectors* (``_collect_profile_health``,
``_attach_pack_health``, ``_build_pack_entries``, ``_collect_org_layer_data``,
``_collect_doctrine_collisions``, ``_build_selection_block``) and the
``doctrine`` command itself stay in ``doctor.py``; only the render-only surface
moved here.

The module-level :data:`console` is the shared singleton: ``doctor.py`` imports
it from here so the whole ``doctor`` command surface and these renderers write
through one :class:`rich.console.Console` instance.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rich.console import Console

from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.cli.console import console

if TYPE_CHECKING:
    from pathlib import Path

    from charter.drg import OrgDRGConflict, OrgDRGConflictError

    from ._doctrine_health import DoctrineHealthReport

__all__ = [
    "console",
    "_SELECTION_KIND_PLURALS",
    "_render_pack_invalid_profiles",
    "_render_doctrine_pack",
    "_emit_doctrine_human",
    "_emit_doctrine_json",
    "_emit_doctrine_no_packs",
    "_render_org_layer_section",
    "_render_selection_block_lines",
]

#: Shared Rich console singleton for the ``doctor`` command surface.  ``doctor.py``
#: re-imports this name so both modules emit through the same instance.

#: Artifact-kind plurals surfaced by ``doctor doctrine`` in the Selections
#: section: the selection-overlayable kinds (a ``selected_<plural>`` charter
#: field that org-required lists union into). Ordering is the operator-facing
#: reading order from the WP09 plan (directives first, agent_profiles last so
#: the audit ends on the "who can drive" surface), so it is spelled as
#: ``ArtifactKind`` members rather than derived; its membership is pinned to
#: ``SELECTION_OVERLAYABLE_KIND_FIELDS`` by
#: ``tests/cli/test_doctor_doctrine_selections_snapshot.py`` (#5538).
_SELECTION_KIND_PLURALS: tuple[str, ...] = tuple(
    kind.plural
    for kind in (
        ArtifactKind.DIRECTIVE,
        ArtifactKind.TACTIC,
        ArtifactKind.PARADIGM,
        ArtifactKind.STYLEGUIDE,
        ArtifactKind.TOOLGUIDE,
        ArtifactKind.PROCEDURE,
        ArtifactKind.MISSION_STEP_CONTRACT,
        ArtifactKind.AGENT_PROFILE,
    )
)


def _render_pack_invalid_profiles(pack_health: object) -> None:
    """Render per-layer invalid-profile diagnostics for a pack (FR-008/009)."""
    if not isinstance(pack_health, dict):
        return
    invalid = pack_health.get("invalid_profiles") or []
    if not (isinstance(invalid, list) and invalid):
        return
    console.print(f"  [yellow]invalid profiles:[/yellow] {len(invalid)} skipped")
    for entry in invalid:
        if not isinstance(entry, dict):
            continue
        layer = entry.get("layer", "?")
        path = entry.get("path", "?")
        error = entry.get("error_summary", "")
        # Render dynamic values without Rich markup so a path/error containing
        # square brackets is never mis-parsed as a style tag.
        console.print(
            f"    • ({layer}) {path}: {error}",
            markup=False,
        )


def _render_doctrine_pack(pack_entry: dict[str, object], pack_index: int) -> None:
    """Render one pack entry to the Rich console (human output for ``doctor doctrine``).

    FR-010: the pack header is colored from derived profile health
    (``pack_health.healthy``), not from snapshot presence.  A snapshot that is
    present but whose agent profiles failed to load renders *degraded* (yellow),
    and the per-layer invalid profiles are listed.
    """
    name = pack_entry.get("name") or f"pack#{pack_index}"
    local_path = pack_entry.get("local_path")
    if not pack_entry.get("snapshot_present"):
        console.print(
            f"[yellow]Pack:[/yellow] {name}  (snapshot missing at {local_path})"
        )
        return

    version = pack_entry.get("pack_version", "unknown")
    is_git = pack_entry.get("is_git_pack", False)
    counts = pack_entry.get("artifact_counts") or {}
    summary_parts = [f"git {version}" if is_git else f"v{version}"]
    if isinstance(counts, dict):
        for artifact_type, count in counts.items():
            summary_parts.append(f"{count} {artifact_type}")

    # FR-010: derive the header color from profile health, never snapshot
    # presence.  ``pack_health`` is the report's PackHealth.to_dict() for the
    # matching layer (attached by the report builder), or ``None`` if no
    # agent-profile surface was discovered for this pack.
    pack_health = pack_entry.get("pack_health")
    # WP01: default to degraded, not green. A present pack with no/partial
    # ``pack_health`` must render degraded (loud-over-hidden) rather than
    # silently green — only an explicit ``healthy: true`` greens the header.
    healthy = False
    if isinstance(pack_health, dict):
        healthy = bool(pack_health.get("healthy", False))
    color = "green" if healthy else "yellow"
    status_suffix = "" if healthy else "  [yellow](degraded)[/yellow]"
    console.print(
        f"[{color}]Pack:[/{color}] {name}  ({', '.join(summary_parts)}){status_suffix}"
    )
    _render_pack_invalid_profiles(pack_health)
    _render_org_charter_line(pack_entry.get("org_charter"))


def _render_org_charter_line(charter: object) -> None:
    """Render the per-pack ``org-charter.yaml`` status line."""
    if not (isinstance(charter, dict) and charter.get("present")):
        console.print("  org-charter.yaml: [dim]not present[/dim]")
        return
    if not charter.get("module_available", True):
        console.print("  org-charter.yaml: present (policy module not yet shipped)")
        return
    counts_msg = (
        f"{charter.get('interview_defaults_count', 0)} interview defaults, "
        f"{charter.get('required_directives_count', 0)} required directives, "
        f"{charter.get('governance_policies_count', 0)} governance policies"
    )
    console.print(f"  org-charter.yaml: {counts_msg}")


def _emit_doctrine_human(
    pack_entries: list[dict[str, object]],
    collision_summaries: list[dict[str, object]],
    selection_block: dict[str, list[dict[str, str]]],
    repo_root: Path,
) -> None:
    """Render the human-readable ``doctor doctrine`` report.

    The report is the single source: pack health was attached to
    ``pack_entries`` by :func:`_attach_pack_health`, and the org-DRG section is
    re-rendered from the same data path.  No parallel assembly (R-011-C).
    """
    console.print(
        f"\n[bold]Org Doctrine[/bold] — {len(pack_entries)} pack(s) configured\n"
    )
    for idx, entry in enumerate(pack_entries):
        _render_doctrine_pack(entry, idx)

    if collision_summaries:
        console.print(
            f"\n[bold]Collisions[/bold] — {len(collision_summaries)} override(s) detected\n"
        )
        for collision in collision_summaries:
            console.print(
                f"  • [yellow]{collision['kind']}[/yellow] "
                f"{collision['item_id']}: "
                f"{collision['higher_layer']} shadowed {collision['lower_layer']} "
                f"({collision['replaced']} replaced, {collision['inherited']} inherited)"
            )
    else:
        console.print(
            "\n[dim]Collisions:[/dim] none — every artifact resolves from a single layer."
        )

    # WP07 T037 (FR-007): surface org-layer DRG state in human-readable output.
    _render_org_layer_section(repo_root, console)

    # FR-018 / WP09 T050: render the Selections section verbatim so the
    # snapshot test in tests/cli/test_doctor_doctrine_selections_snapshot.py
    # can pin the operator-facing format byte-for-byte.
    console.print()
    for line in _render_selection_block_lines(selection_block):
        console.print(line)
    console.print()


def _emit_doctrine_json(
    report: DoctrineHealthReport,
    *,
    org_configured: bool,
    pack_entries: list[dict[str, object]],
    collision_summaries: list[dict[str, object]],
    selection_block: dict[str, list[dict[str, str]]],
) -> None:
    """Emit the ``doctor doctrine --json`` payload as a passthrough of the report.

    ``profile_health`` is a verbatim ``report.to_dict()`` so the invalid-profile
    fields (layer/path/profile_id/error_summary) and the derived ``healthy``
    flag are a single source of truth shared with the human surface (FR-010).
    """
    report_dict = report.to_dict()
    payload: dict[str, object] = {
        "org_configured": org_configured,
        "packs": pack_entries,
        "selections": selection_block,
        # WP07 FR-007: always include org_drg key so callers can rely on it.
        "org_drg": report_dict["org_drg"],
        # WP08 FR-008/009/010: derived profile health + invalid-profile diagnostics.
        "profile_health": report_dict,
    }
    if org_configured:
        payload["collisions"] = collision_summaries
    console.print_json(json.dumps(payload, indent=2, default=str))


def _emit_doctrine_no_packs(
    report: DoctrineHealthReport,
    selection_block: dict[str, list[dict[str, str]]],
    *,
    json_output: bool,
) -> None:
    """Emit the ``doctor doctrine`` output when no org packs are configured.

    A project with built-in + project-only doctrine still has selections (and
    profile health) to audit, so both are emitted before the command exits.
    """
    if json_output:
        _emit_doctrine_json(
            report,
            org_configured=False,
            pack_entries=[],
            collision_summaries=[],
            selection_block=selection_block,
        )
        return
    console.print("[yellow]No org doctrine configured.[/yellow]")
    console.print(
        "Add a 'charter_packs.org' block to .kittify/config.yaml to register a pack."
    )
    console.print()
    for line in _render_selection_block_lines(selection_block):
        console.print(line)


#: Verbosity cap for the org-layer findings lists, per the WP07 risk table
#: (risk 4). Applied to collisions and to dangling endpoints alike so one
#: misconfigured pack cannot bury the rest of the ``doctor doctrine`` report.
_ORG_FINDINGS_SHOWN = 3


def _render_dangling_org_endpoints(console: Console, dangling: list[str]) -> None:
    """Render org edge endpoints that name no node in the merged graph.

    Companion to the collision block: a distinct check gets a distinct verdict
    line, so ``collisions: none`` keeps meaning "no collisions" rather than
    quietly standing in for "org layer is fine".
    """
    if not dangling:
        console.print("  dangling endpoints: none")
        return
    console.print(
        f"  [red]dangling endpoints:[/red] {len(dangling)} org edge endpoint(s) "
        "name no node in any merged layer"
    )
    for message in dangling[:_ORG_FINDINGS_SHOWN]:
        console.print(f"    [red]•[/red] {message}")
    if len(dangling) > _ORG_FINDINGS_SHOWN:
        console.print(
            f"    … and {len(dangling) - _ORG_FINDINGS_SHOWN} more "
            "(run spec-kitty doctor doctrine --json for the full list)"
        )


def _render_org_layer_section(repo_root: Path, console: Console) -> None:
    """Surface organisation-tier DRG state in ``doctor doctrine`` (FR-007).

    Lists each configured pack with its fetched/missing status, node/edge
    counts, any collision warnings from ``merge_three_layers``, and any org
    edge endpoint that binds to nothing.

    Diagnostic commands are READ-ONLY and must never crash on operator
    misconfiguration.  All exceptions are caught and rendered as findings
    so ``doctor doctrine`` always returns a usable report.
    """
    from charter.drg import (
        OrgDRGConflictError,
        OrgPackMissingError,
        load_built_in_graph,
        validate_dangling_references,
    )
    from charter.activation.drg_activation import (
        load_org_drg,
        merge_three_layers,
    )

    console.print("\n[bold]Organisation Layer[/bold] (WP07 / FR-007)")

    try:
        fragments = load_org_drg(repo_root)
    except OrgPackMissingError as exc:
        console.print(f"  [red]org pack missing:[/red] {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red]org-DRG load error:[/red] {exc}")
        return

    if not fragments:
        console.print("  (no organisation packs configured)")
        return

    for frag in fragments:
        node_count = len(frag.nodes)
        edge_count = len(frag.edges)
        console.print(
            f"  - [green]{frag.pack_name}[/green] "
            f"[{frag.source_kind}: {frag.source_ref}] "
            f"✓ loaded ({node_count} nodes, {edge_count} edges)"
        )

    # Merge with the built-in layer to surface collision warnings AND graph
    # completeness. Both findings lists are truncated per the WP07 risk table
    # (risk 4: verbosity mitigation). The merge is the only statement in the
    # try — see ``_collect_org_layer_data`` for why the completeness check no
    # longer shares a handler with it.
    merged = None
    try:
        built_in = load_built_in_graph()
        merged = merge_three_layers(
            built_in=built_in, org_fragments=fragments, project=None
        )
        console.print("  collisions: none")
    except OrgDRGConflictError as exc:
        _render_org_conflicts(console, exc)
    except Exception as exc:  # noqa: BLE001 — doctor must not crash
        # Widened from "collision check skipped": the block now also owns the
        # completeness check, and naming only one of the two checks it skipped
        # would understate what the operator is missing.
        console.print(f"  [yellow]org-layer merge checks skipped:[/yellow] {exc}")

    if merged is None:
        # "Not checked" and "checked, found nothing" are different answers, and
        # only one of them is true here. Printing ``dangling endpoints: none``
        # would assert a result the command never computed — the merge refused
        # to assemble a graph, so there was nothing to walk.
        console.print(
            "  [yellow]dangling endpoints: not checked[/yellow] "
            "(no merged graph — see the merge findings above)"
        )
        return

    try:
        # Same merge, same inputs, same predicate as ``_collect_org_layer_data``
        # — the real shipped built-in against every configured pack, i.e. the
        # COMPLETE graph, which is when ``validate_dangling_references`` may
        # escalate (see its docstring; ``charter lint`` merges against an
        # intentionally EMPTY built-in and must not). That collector documents
        # itself as a mirror of *this* function, so wiring the check into one and
        # not the other left the two halves of one command disagreeing:
        # ``--json`` reported the dangling endpoint under ``org_drg.errors``
        # while this section printed the pack ``✓ loaded`` and nothing else.
        _render_dangling_org_endpoints(console, validate_dangling_references(merged))
    except Exception as exc:  # noqa: BLE001 — doctor must not crash
        console.print(f"  [yellow]dangling endpoints: not checked[/yellow] ({exc})")


def _render_org_conflicts(console: Console, exc: OrgDRGConflictError) -> None:
    """Render a refused merge, separating refusals from resolved precedence.

    ``merge_three_layers`` raises with every conflict it found. Rendering them
    as one undifferentiated "override(s)" list told the operator that a pack
    the merge REFUSED was in the same category as a permitted built-in
    override — the human half of the defect where a hard failure reached only
    the advisory channel. The partition comes from ``OrgDRGConflictError`` so
    this renderer and the two JSON collectors cannot disagree about severity.
    """
    fatal = exc.hard_failures
    advisory = exc.advisory_conflicts

    if fatal:
        console.print(
            f"  [red]org-DRG REFUSED:[/red] {len(fatal)} fatal conflict(s) — "
            "the merged graph could not be assembled"
        )
        _render_conflict_bullets(console, fatal, style="red")
    if advisory:
        console.print(f"  collisions: {len(advisory)} built-in invariant override(s)")
        _render_conflict_bullets(console, advisory, style="yellow")
    elif not fatal:  # pragma: no cover — the merge only raises when one exists
        console.print("  collisions: none")


def _render_conflict_bullets(
    console: Console, conflicts: list[OrgDRGConflict], *, style: str
) -> None:
    """Print up to :data:`_ORG_FINDINGS_SHOWN` conflicts, then a truncation note."""
    for conflict in conflicts[:_ORG_FINDINGS_SHOWN]:
        console.print(
            f"    [{style}]•[/{style}] {conflict.kind} "
            f"target={conflict.target_id} "
            f"resolution={conflict.resolution_applied}"
        )
    if len(conflicts) > _ORG_FINDINGS_SHOWN:
        console.print(
            f"    … and {len(conflicts) - _ORG_FINDINGS_SHOWN} more "
            "(run charter lint for details)"
        )


#: Closing line of the Selections block: where the active charter is listed.
_ACTIVE_CHARTER_POINTER = "Active charter (activated artifacts): spec-kitty charter list"


def _render_selection_block_lines(
    selections: dict[str, list[dict[str, str]]],
) -> list[str]:
    """Render the Selections block as a list of pinned-format lines.

    The exact layout is pinned by the snapshot test
    ``tests/cli/test_doctor_doctrine_selections_snapshot.py``.  Every
    change to spacing, punctuation, or per-kind ordering MUST update the
    snapshot fixture in the same commit.
    """
    lines: list[str] = ["Selections (active globally-selected artifacts):"]
    for kind in _SELECTION_KIND_PLURALS:
        entries = selections.get(kind, [])
        if not entries:
            lines.append(f"  {kind}: (none)")
            continue
        lines.append(f"  {kind}:")
        for entry in entries:
            lines.append(f"    - {entry['id']:<24}(source: {entry['source']})")
    # Selections are not activations (#4836): point at the activation view so
    # an operator checking an activation does not stop at "(none)".
    lines.append(_ACTIVE_CHARTER_POINTER)
    return lines
