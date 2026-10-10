"""spec-kitty charter list — show activated charter artifacts per kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from specify_cli.cli.console import CliConsole
from specify_cli.cli.console import console
from rich.table import Table

from charter.activation.evidence.orchestrator import ConfigShapeError
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import CHARTER_KIND_TOKENS
from charter.activation.pack_manager import AvailableArtifact, ActiveCharterManager
from charter.resolution import ResolutionTier
from charter.template_catalog import TemplateRef, TierRoot, discover_templates
from kernel.errors import KittyInternalConsistencyError

from specify_cli.cli.commands.charter._common import _emit_error
from charter.activation.layer_roots import resolve_layer_roots, resolve_pack_chain

__all__ = ["charter_list_app"]

# The layer-aware table is intentionally rendered at a generous fixed width so
# artifact IDs never word-wrap. Module-level (not per-call) so it registers with
# CliConsole and the test set_all_plain seam reaches it (#2632) — a per-call
# instance would be born after the colour-neutralising fixture and leak ANSI.
_wide_console = CliConsole(width=200)

charter_list_app = typer.Typer(
    name="list",
    help="List activated charter artifacts by kind.",
    no_args_is_help=False,
    invoke_without_command=True,
)

#: Display order for the charter kinds. Derived from the canonical charter kind
#: universe (:data:`charter.offering.artifact_kinds.CHARTER_KIND_TOKENS`, WP01) so this
#: surface never re-declares the kind set (R-009 / CC-4). The ``template`` kind
#: (FR-025) is *not* in ``CHARTER_KIND_TOKENS`` — it is resolved specially
#: (mission-qualified IDs, WP18) and appended to the ``--all`` listing below.
_KIND_ORDER: list[str] = list(CHARTER_KIND_TOKENS)

#: Pseudo-kind label for the template row in the ``--all`` listing. Templates
#: are not a charter activation kind (no ``config.yaml`` activation list); they
#: are surfaced here as an availability-only row (FR-025).
_TEMPLATE_KIND = "template"


def _template_tier_roots(repo_root: Path, layer_roots: dict[str, Path]) -> list[TierRoot]:
    """Build template-discovery tier roots (C-008) in precedence order.

    Templates live mission-scoped under ``<missions_root>/<mission>/templates``
    and ``.../command-templates`` (WP18). The package missions root ships with
    the ``doctrine`` package. The project layer (when present) carries its own
    missions tree under ``<project pack root>/missions``; the org
    layer (when present) carries a *flat* missions tree under
    ``<org_root>/missions`` — no ``doctrine/`` subdir (FR-006, matching what
    the resolver actually reads, WP03).

    Roots are returned override → package so :func:`discover_templates`
    deduplicates same ``<mission>/<name>`` IDs to the highest-precedence tier.
    """
    from charter.missions import MissionTemplateRepository  # noqa: PLC0415

    tier_roots: list[TierRoot] = []

    # Project (override-tier) missions, if a project pack exists. The project
    # layer root is the project pack root itself (``.kittify/charter-packs/``).
    project_root = layer_roots.get("project")
    if project_root is not None:
        missions = project_root / "missions"
        if missions.is_dir():
            tier_roots.append(
                TierRoot(
                    tier=ResolutionTier.OVERRIDE,
                    missions_root=missions,
                    project_dir=repo_root,
                )
            )

    # Org missions from EVERY configured, existing org Charter Pack (one ORG tier
    # root per chain pack; last-declared wins). Flat layout (``<root>/missions``,
    # no ``doctrine/`` subdir) and ``ResolutionTier.ORG`` match what the resolver
    # reads (WP03) — see FR-006/DEC-009.
    for org_root in resolve_pack_chain(repo_root, strict=False):
        missions = org_root / "missions"
        if missions.is_dir():
            tier_roots.append(
                TierRoot(
                    tier=ResolutionTier.ORG,
                    missions_root=missions,
                )
            )

    # Built-in (package-default-tier) missions: always present.
    tier_roots.append(
        TierRoot(
            tier=ResolutionTier.PACKAGE_DEFAULT,
            missions_root=MissionTemplateRepository.default_missions_root(),
        )
    )

    return tier_roots


def _available_over_chain(
    manager: ActiveCharterManager,
    ctx: ProjectContext,
    kind: str,
    layer_roots: dict[str, Path],
    org_chain: list[Path],
) -> list[AvailableArtifact]:
    """Availability across the FULL org-pack chain (``layer_roots["org"]`` is pack 1 only).

    Scans once with the supplied roots, then once per remaining chain pack as the
    ``org`` root, adding only the org-layer entries (built-in/project are already
    covered). Duplicates are dropped, preserving first-seen order.
    """
    # NOTE: this per-pack traversal is now partly obsoleted by the ``org_root_chain=``
    # parameter added to ``list_available_detailed`` / ``_scan_layer_dirs`` (#6006).
    # Unifying it onto that central scanner is tracked in #6012.
    entries = list(manager.list_available_detailed(ctx, kind, layer_roots=layer_roots))
    seen = {(e.artifact_id, e.layer) for e in entries}
    first_org = layer_roots.get("org")
    for org_root in org_chain:
        if org_root == first_org:
            continue
        scanned = manager.list_available_detailed(ctx, kind, layer_roots={**layer_roots, "org": org_root})
        for entry in scanned:
            key = (entry.artifact_id, entry.layer)
            if entry.layer == "org" and key not in seen:
                seen.add(key)
                entries.append(entry)
    return entries


def _render_available(entries: list[AvailableArtifact], activated: frozenset[str]) -> str:
    """Render available-but-not-activated artifacts annotated by source layer.

    Each entry is shown as ``<id> [<layer>]``. Artifacts already activated are
    dropped (an activated ID is no longer "available but not activated"). The
    output is sorted by ``(id, layer)`` for determinism.
    """
    not_activated = sorted(
        ((e.artifact_id, e.layer) for e in entries if e.artifact_id not in activated),
        key=lambda pair: (pair[0], pair[1]),
    )
    if not not_activated:
        return "[dim]—[/dim]"
    return ", ".join(f"{aid} [dim]({layer})[/dim]" for aid, layer in not_activated)


def _render_templates(refs: list[TemplateRef]) -> str:
    """Render discovered templates with mission-qualified IDs and source tier."""
    if not refs:
        return "[dim]—[/dim]"
    return ", ".join(
        f"{ref.template_id} [dim]({ref.tier.value})[/dim]" for ref in refs
    )


@charter_list_app.callback()
def list_cmd(
    show_available: bool = typer.Option(
        False,
        "--show-available",
        help="Also show available-but-not-activated artifacts.",
    ),
    all_layers: bool = typer.Option(
        False,
        "--all",
        help=(
            "Show every available artifact per kind across the built-in, org, "
            "and project layers (annotated by source layer), including the "
            "template kind. Supersedes --show-available."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "Output JSON. Every kind row always carries an 'available' key "
            "and the payload always carries a top-level 'templates' key — "
            "both are null unless requested (available: null without "
            "--show-available/--all; templates: null without --all) rather "
            "than absent, so callers can rely on key presence and branch on "
            "the value instead of on which flags were passed."
        ),
    ),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """List activated charter artifacts for each charter kind.

    With ``--all`` the listing additionally surfaces every *available* artifact
    across the built-in, org, and project layers — each annotated by its source
    layer — and appends the mission-scoped ``template`` kind (FR-025). Org and
    project doctrine roots are resolved here (in ``specify_cli``) and passed to
    the lower layers as data (C-008).

    ``--json`` emits the same rows the human table shows, reusing the exact
    same ``ActiveCharterManager`` / ``discover_templates`` calls rather than
    re-deriving anything. Errors reuse the shared ``_emit_error`` envelope
    (``{"result": "error", "success": false, "error": message}``).

    Key presence is unconditional (OP-CONTRACT-003): each row in
    ``payload["kinds"]`` always carries an ``available`` key, and
    ``payload`` always carries a top-level ``templates`` key. Both are
    ``null`` — never absent — when the corresponding flag wasn't passed
    (``available`` needs ``--show-available``/``--all``; ``templates`` needs
    ``--all``), mirroring the existing ``activated: null`` "not applicable"
    convention used for the all-built-ins state.
    """
    # --all implies and supersedes --show-available (it is a richer, layer-aware
    # availability view).
    if all_layers:
        show_available = True

    try:
        ctx = ProjectContext.from_repo(repo_root)
        manager = ActiveCharterManager()
        activated_map = manager.list_activated(ctx)

        # Resolve org/project roots once when we need the layer-aware view (C-008).
        layer_roots = resolve_layer_roots(repo_root) if all_layers else None
        org_chain = resolve_pack_chain(repo_root, strict=False) if all_layers else []

        table = Table(title="Charter Activation State", show_lines=True)
        table.add_column("Kind", style="bold cyan", no_wrap=True)
        table.add_column("Activated", style="white")
        if show_available:
            header = "Available (all layers)" if all_layers else "Available (not activated)"
            table.add_column(header, style="dim")

        # ``--json`` rows mirror the table rows exactly, built from the same
        # manager calls in the same loop -- serialization, not re-derivation.
        json_rows: list[dict[str, Any]] = []

        for kind in _KIND_ORDER:
            value = activated_map.get(kind)
            if value is None:
                activated_str = "[dim](All built-ins — no explicit activation)[/dim]"
            elif len(value) == 0:
                activated_str = "[yellow](Nothing activated — explicit restriction)[/yellow]"
            else:
                activated_str = ", ".join(sorted(value))

            json_row: dict[str, Any] = {
                "kind": kind,
                "activated": sorted(value) if value is not None else None,
                # OP-CONTRACT-003: always present, not conditionally absent --
                # null (not merely unset) when --show-available/--all wasn't
                # passed, so callers can rely on key presence.
                "available": None,
            }

            if show_available:
                activated_set = value or frozenset()
                if all_layers:
                    # CL-006/NFR-002 (post-fix verification sweep, mission
                    # up-mission-type-seam-01KZY1JB): for the ``mission-type``
                    # kind, ``list_available_detailed`` reaches
                    # ``scan_mission_types_dir`` directly (PR-CONTRACT-002) and
                    # loud-fails BY DESIGN on a malformed/unreadable YAML file
                    # anywhere in the built-in/org/project ``mission_types/``
                    # layers -- same underlying primitive as the other CLI
                    # surfaces this mission's grep found, a different direct
                    # caller. A bare ``except ValueError`` also catches
                    # ``pydantic.ValidationError`` (this scan's other documented
                    # ``Raises`` type, see its docstring) since it subclasses
                    # ``ValueError`` in the pinned pydantic version.
                    try:
                        entries = _available_over_chain(
                            manager, ctx, kind, layer_roots or {}, org_chain
                        )
                    except ValueError as exc:
                        _emit_error(console, json_output=json_output, message=str(exc))
                        raise typer.Exit(1) from exc
                    available_str = _render_available(entries, activated_set)
                    not_activated_entries = sorted(
                        (
                            (e.artifact_id, e.layer)
                            for e in entries
                            if e.artifact_id not in activated_set
                        ),
                        key=lambda pair: (pair[0], pair[1]),
                    )
                    json_row["available"] = [
                        {"artifact_id": aid, "layer": layer}
                        for aid, layer in not_activated_entries
                    ]
                else:
                    available = manager.list_available(ctx, kind)
                    not_activated = sorted(available - activated_set) if available else []
                    available_str = (
                        ", ".join(not_activated) if not_activated else "[dim]—[/dim]"
                    )
                    json_row["available"] = not_activated
                table.add_row(kind, activated_str, available_str)
            else:
                table.add_row(kind, activated_str)

            json_rows.append(json_row)

        # OP-CONTRACT-003: "templates" is always present, not conditionally
        # absent -- null (not merely unset) without --all, so callers can rely
        # on key presence.
        payload: dict[str, Any] = {
            "result": "success",
            "kinds": json_rows,
            "templates": None,
        }

        # FR-025: the template kind is mission-scoped and has no activation list, so
        # it only appears in the layer-aware (--all) availability view.
        if all_layers:
            tier_roots = _template_tier_roots(repo_root, layer_roots or {})
            template_refs = discover_templates(tier_roots=tier_roots)
            table.add_row(
                _TEMPLATE_KIND,
                "[dim](mission-scoped — not separately activated)[/dim]",
                _render_templates(template_refs),
            )
            payload["templates"] = [
                {
                    "template_id": ref.template_id,
                    "mission": ref.mission,
                    "name": ref.name,
                    "tier": ref.tier.value,
                }
                for ref in template_refs
            ]

        if json_output:
            print(json.dumps(payload, indent=2))
            return

        # The layer-aware view is intentionally wide (IDs + per-layer tags); render
        # it at a generous fixed width so artifact IDs are never word-wrapped into
        # unreadable fragments on narrow / non-tty terminals.
        if all_layers:
            _wide_console.print(table)
        else:
            console.print(table)
    except (ConfigShapeError, ValueError) as exc:
        # ValueError: pack_manager._load_config / _activation_list_or_error
        # (non-mapping or malformed .kittify/config.yaml) and
        # list_available_detailed's mission-type ValueError (already
        # guarded above for --all, but list_available's plain
        # --show-available path reaches the same primitive unguarded).
        # ConfigShapeError: kept for symmetry with the other guarded
        # charter surfaces (status/synthesize/resynthesize) even though
        # this command's own call chain does not currently raise it.
        _emit_error(console, json_output=json_output, message=str(exc))
        raise typer.Exit(1) from exc
    except KittyInternalConsistencyError as exc:
        # ActiveCharterConfigError (ProjectContext.from_repo ->
        # PackContext.from_config -> pack_context._load_config) on a
        # non-mapping .kittify/config.yaml or a dangling charter:
        # pointer. str(exc) is just the opaque code
        # (ACTIVE_CHARTER_CONFIG_INVALID); surface .body too, matching
        # the established pattern (synthesize.py's KittyInternalConsistencyError
        # handler).
        detail = f"{exc.code}: {exc.body}" if exc.body else exc.code
        _emit_error(console, json_output=json_output, message=detail)
        raise typer.Exit(1) from exc
