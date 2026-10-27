"""spec-kitty charter list — show activated charter artifacts per kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from specify_cli.cli.console import CliConsole
from specify_cli.cli.console import console
from rich.table import Table

from charter.activation.api import (
    ActiveCharterConfigError,
    IdentityIndex,
    RequiredOmission,
    RequiringPack,
    load_activation_ledger,
    read_org_required_provenance,
    required_not_in_force,
)
from charter.activation.evidence.orchestrator import ConfigShapeError
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import CHARTER_KIND_TOKENS
from charter.activation.pack_manager import AvailableArtifact, ActiveCharterManager
from charter.drg import ArtifactKind
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

#: An empty table cell.
_EMPTY_CELL = "[dim]—[/dim]"


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


def _deactivated_by_kind(repo_root: Path) -> dict[str, list[str]]:
    """Per operator kind token, the ledger's deny-list (``ActivationLedger.deny_for``, R12).

    ``mission-type`` is not an artifact kind and has no deny-list, so it has no entry.
    """
    ledger = load_activation_ledger(repo_root)
    deactivated: dict[str, list[str]] = {}
    for kind in _KIND_ORDER:
        try:
            artifact_kind = ArtifactKind.from_operator_token(kind)
        except ValueError:  # ``mission-type``
            continue
        deactivated[kind] = sorted(ledger.deny_for(artifact_kind))
    return deactivated


#: How the table marks an org-required id an explicit allow list leaves out (FR-023).
_REQUIRED_NOT_IN_FORCE = "required (not in force: explicit allow list omits it)"


def _required_not_in_force_by_kind(repo_root: Path) -> dict[str, list[RequiredOmission]]:
    """Per operator kind token, the org-required ids an explicit allow list omits (FR-023, R12).

    Read leniently (``strict=False``): a listing never fails because an org
    pack's required floor is unreadable; ``doctor charter-packs`` reports that.
    """
    by_kind: dict[str, list[RequiredOmission]] = {}
    for omission in required_not_in_force(repo_root, strict=False):
        by_kind.setdefault(omission.kind.operator_token, []).append(omission)
    return by_kind


def _required_not_in_force_json(by_kind: dict[str, list[RequiredOmission]]) -> dict[str, Any]:
    """The additive ``--json`` key ``required_not_in_force: {<plural>: [{id, packs}]}``; ``{}`` when nothing is omitted."""
    if not by_kind:
        return {}
    return {
        "required_not_in_force": {
            items[0].kind.plural: [{"id": item.artifact_id, "packs": list(item.pack_names)} for item in items] for items in by_kind.values()
        }
    }


def _with_required_not_in_force(activated_str: str, omissions: list[RequiredOmission], identity: _KindIdentity) -> str:
    """Append the FR-023 marker for each omitted required id to a kind's Activated cell."""
    marks = [f"[yellow]{identity.label(item.artifact_id)} — {_REQUIRED_NOT_IN_FORCE}; required by {item.describe_packs()}[/yellow]" for item in omissions]
    return "\n".join([activated_str, *marks]) if marks else activated_str


#: How the table marks an org-required id an absent allow list leaves in force (#6417).
_REQUIRED_IN_FORCE = "in force: required by"

#: One kind's org-required floor in force: ``[(stem, requiring packs)]``.
_InForce = list[tuple[str, tuple[RequiringPack, ...]]]


def _provided_stems(manager: ActiveCharterManager, ctx: ProjectContext, kind: str) -> frozenset[str]:
    """The stems of *kind* the built-in, project and every org layer provide (the ``--all`` scan)."""
    entries = _available_over_chain(manager, ctx, kind, resolve_layer_roots(ctx.repo_root), resolve_pack_chain(ctx.repo_root, strict=False))
    return frozenset(entry.artifact_id for entry in entries)


def _required_in_force_by_kind(
    manager: ActiveCharterManager, ctx: ProjectContext, activated_map: dict[str, Any]
) -> tuple[dict[str, _InForce], list[str]]:
    """Per operator kind token, the org-required ids in force because the kind's allow list is absent (#6417).

    An absent ``activated_<kind>`` key leaves the org packs' required floor in force,
    and no deny-list can remove a required id. Only a floor id some layer provides is
    listed: an id no layer provides is not claimed in force (``doctor charter-packs``
    reports it). A present list is :func:`_required_not_in_force_by_kind`'s concern.

    The floor is read strictly so an unreadable org pack is never shown as "nothing
    required": that kind lands in the second element (its tokens) and the listing
    carries a hint to run ``doctor charter-packs``; the listing itself never fails.
    """
    by_kind: dict[str, _InForce] = {}
    unreadable: list[str] = []
    for kind in _KIND_ORDER:
        if activated_map.get(kind) is not None:
            continue
        try:
            artifact_kind = ArtifactKind.from_operator_token(kind)
        except ValueError:  # ``mission-type``
            continue
        if not artifact_kind.org_requirable:
            continue
        try:
            floor = read_org_required_provenance(ctx.repo_root, artifact_kind, strict=True)
        except ActiveCharterConfigError:
            unreadable.append(kind)
            continue
        provided = _provided_stems(manager, ctx, kind) if floor else frozenset()
        in_force = [(stem, packs) for stem, packs in floor.items() if stem in provided]
        if in_force:
            by_kind[kind] = in_force
    return by_kind, unreadable


def _pack_names(packs: tuple[RequiringPack, ...]) -> list[str]:
    return list(dict.fromkeys(pack.pack for pack in packs))


def _required_in_force_json(by_kind: dict[str, _InForce], unreadable: list[str]) -> dict[str, Any]:
    """The additive ``--json`` keys: ``required_in_force: {<plural>: [{id, packs}]}`` and ``required_floor_unreadable: [<plural>]``.

    Each key is present only when non-empty, so a project without either keeps its payload unchanged.
    """
    payload: dict[str, Any] = {}
    if by_kind:
        payload["required_in_force"] = {
            ArtifactKind.from_operator_token(kind).plural: [{"id": stem, "packs": _pack_names(packs)} for stem, packs in items]
            for kind, items in by_kind.items()
        }
    if unreadable:
        payload["required_floor_unreadable"] = [ArtifactKind.from_operator_token(kind).plural for kind in unreadable]
    return payload


#: The hint under a kind whose org required floor could not be read (#6417).
_FLOOR_UNREADABLE = "[dim]org required floor unreadable — run `spec-kitty doctor charter-packs`[/dim]"


def _with_required_in_force(activated_str: str, in_force: _InForce, identity: _KindIdentity, *, unreadable: bool = False) -> str:
    """Append one line per org-required id an absent allow list leaves in force to a kind's Activated cell.

    An *unreadable* floor adds the doctor hint instead of silently reading as "nothing required".
    """
    marks = [f"[green]{identity.label(stem)} — {_REQUIRED_IN_FORCE} {', '.join(pack.describe() for pack in packs)}[/green]" for stem, packs in in_force]
    if unreadable:
        marks.append(_FLOOR_UNREADABLE)
    return "\n".join([activated_str, *marks]) if marks else activated_str


#: What an absent allow key leaves in force, by ``ArtifactKind.effective_when_absent``.
_ABSENT_KEY_CELLS = {
    "all": "[dim](All built-ins — no explicit activation)[/dim]",
    "required": "[dim](Org-required only — no explicit activation)[/dim]",
}


def _absent_key_cell(kind: str) -> str:
    """The Activated cell of a kind whose allow key is absent: all built-ins, or only the org-required ids."""
    try:
        return _ABSENT_KEY_CELLS[ArtifactKind.from_operator_token(kind).effective_when_absent]
    except ValueError:  # ``mission-type`` is not an artifact kind
        return _ABSENT_KEY_CELLS["all"]


class _KindIdentity:
    """Stem <-> declared-id view of one kind, so ``stem (declared_id)`` and activation agree (FR-007).

    A config activation list may spell an artifact by its file stem or its
    declared id; the ``AvailableArtifact`` rows carry the stem. ``mission-type``
    is not an artifact kind, so it has no index and every lookup is the identity.
    """

    def __init__(self, index: IdentityIndex, kind: str) -> None:
        try:
            self._kind: ArtifactKind | None = ArtifactKind.from_operator_token(kind)
        except ValueError:  # ``mission-type`` is not an addressable artifact kind
            self._kind = None
        self._index = index

    def declared_id(self, stem: str, layer: str | None = None) -> str | None:
        """Declared id of *stem* (or of a declared-id token); ``None`` when unknown.

        With *layer* the id comes from that layer's own file, so a shadowed row never
        borrows the id of a higher layer that reuses its stem; a layer without such a
        file falls back to the cross-layer lookup.
        """
        if self._kind is None:
            return None
        if layer is not None:
            own: str | None = self._index.declared_id_in_layer(self._kind, stem, layer)
            if own is not None:
                return own
        declared: str | None = self._index.declared_id(self._kind, stem)
        return declared

    def is_activated(self, stem: str, activated: frozenset[str], layer: str | None = None) -> bool:
        """Whether *stem* is activated under either of its spellings."""
        declared = self.declared_id(stem, layer)
        return stem in activated or (declared is not None and declared in activated)

    def label(self, token: str, layer: str | None = None) -> str:
        """``stem (declared_id)`` when a token's stem and declared id differ, else the token."""
        declared = self.declared_id(token, layer)
        stem = (self._index.stem(self._kind, token) if self._kind is not None else None) or token
        return f"{stem} ({declared})" if declared is not None and declared != stem else stem


def _deactivated_cells(identity: _KindIdentity, tokens: list[str] | None, *, show: bool) -> list[str]:
    """The Deactivated column cell of one row (none when the column is hidden)."""
    if not show:
        return []
    return [", ".join(identity.label(token) for token in tokens or []) or _EMPTY_CELL]


def _render_available(entries: list[AvailableArtifact], activated: frozenset[str], identity: _KindIdentity) -> str:
    """Render available-but-not-activated artifacts annotated by source layer.

    Each entry is shown as ``<id> [<layer>]``, or ``<stem> (<declared id>) [<layer>]``
    when the two differ. Artifacts already activated (under either spelling) are
    dropped (an activated ID is no longer "available but not activated"). The
    output is sorted by ``(id, layer)`` for determinism.
    """
    not_activated = sorted(
        ((e.artifact_id, e.layer) for e in entries if not identity.is_activated(e.artifact_id, activated, e.layer)),
        key=lambda pair: (pair[0], pair[1]),
    )
    if not not_activated:
        return _EMPTY_CELL
    return ", ".join(f"{identity.label(aid, layer)} [dim]({layer})[/dim]" for aid, layer in not_activated)


def _render_templates(refs: list[TemplateRef]) -> str:
    """Render discovered templates with mission-qualified IDs and source tier."""
    if not refs:
        return _EMPTY_CELL
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
        identity_index = IdentityIndex.build(repo_root)
        deactivated_map = _deactivated_by_kind(repo_root)
        required_omitted = _required_not_in_force_by_kind(repo_root)
        required_in_force, floor_unreadable = _required_in_force_by_kind(manager, ctx, activated_map)
        # The column appears only when something is deactivated, so a project
        # without a deny-list keeps its byte-identical table.
        show_deactivated = any(deactivated_map.values())

        # Resolve org/project roots once when we need the layer-aware view (C-008).
        layer_roots = resolve_layer_roots(repo_root) if all_layers else None
        org_chain = resolve_pack_chain(repo_root, strict=False) if all_layers else []

        table = Table(title="Charter Activation State", show_lines=True)
        table.add_column("Kind", style="bold cyan", no_wrap=True)
        table.add_column("Activated", style="white")
        if show_available:
            header = "Available (all layers)" if all_layers else "Available (not activated)"
            table.add_column(header, style="dim")
        if show_deactivated:
            table.add_column("Deactivated", style="yellow")

        # ``--json`` rows mirror the table rows exactly, built from the same
        # manager calls in the same loop -- serialization, not re-derivation.
        json_rows: list[dict[str, Any]] = []

        for kind in _KIND_ORDER:
            value = activated_map.get(kind)
            identity = _KindIdentity(identity_index, kind)
            if value is None:
                activated_str = _absent_key_cell(kind)
            elif len(value) == 0:
                activated_str = "[yellow](Nothing activated — explicit restriction)[/yellow]"
            else:
                activated_str = ", ".join(identity.label(token) for token in sorted(value))
            activated_str = _with_required_not_in_force(activated_str, required_omitted.get(kind, []), identity)
            activated_str = _with_required_in_force(activated_str, required_in_force.get(kind, []), identity, unreadable=kind in floor_unreadable)

            json_row: dict[str, Any] = {
                "kind": kind,
                "activated": sorted(value) if value is not None else None,
                # OP-CONTRACT-003: always present, not conditionally absent --
                # null (not merely unset) when --show-available/--all wasn't
                # passed, so callers can rely on key presence.
                "available": None,
                # Always present: the deny-list of the kind; null for mission-type.
                "deactivated": deactivated_map.get(kind),
            }
            deactivated_cells = _deactivated_cells(identity, deactivated_map.get(kind), show=show_deactivated)

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
                    available_str = _render_available(entries, activated_set, identity)
                    not_activated_entries = sorted(
                        (
                            (e.artifact_id, e.layer)
                            for e in entries
                            if not identity.is_activated(e.artifact_id, activated_set, e.layer)
                        ),
                        key=lambda pair: (pair[0], pair[1]),
                    )
                    # FR-007 / #6406: ``declared_id`` rides beside the stem-keyed ``artifact_id``.
                    json_row["available"] = [
                        {
                            "artifact_id": aid,
                            "layer": layer,
                            "declared_id": identity.declared_id(aid, layer) or aid,
                        }
                        for aid, layer in not_activated_entries
                    ]
                else:
                    available = manager.list_available(ctx, kind)
                    not_activated = sorted(s for s in available if not identity.is_activated(s, activated_set)) if available else []
                    available_str = (
                        ", ".join(identity.label(s) for s in not_activated) if not_activated else _EMPTY_CELL
                    )
                    json_row["available"] = not_activated
                table.add_row(kind, activated_str, available_str, *deactivated_cells)
            else:
                table.add_row(kind, activated_str, *deactivated_cells)

            json_rows.append(json_row)

        # OP-CONTRACT-003: "templates" is always present, not conditionally
        # absent -- null (not merely unset) without --all, so callers can rely
        # on key presence.
        payload: dict[str, Any] = {
            "result": "success",
            "kinds": json_rows,
            "templates": None,
        }
        # FR-023: additive, present only when an explicit allow list omits a required id.
        payload.update(_required_not_in_force_json(required_omitted))
        # #6417: additive, present only when an absent allow list leaves a required id in force.
        payload.update(_required_in_force_json(required_in_force, floor_unreadable))

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
