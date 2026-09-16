"""CLI command group: spec-kitty profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from specify_cli.cli.console import console
from rich.table import Table

from specify_cli.task_utils import find_repo_root

if TYPE_CHECKING:
    from charter.profiles import AgentProfile, AgentProfileRepository

app = typer.Typer(name="profiles", help="Manage and list agent profiles.")
_KITTIFY_DIR = ".kittify"
_PROFILE_ID_LABEL = "Profile ID"
_EMPTY_VALUE = "[dim]—[/dim]"


def _activated_agent_profiles(repo_root: Path) -> frozenset[str] | None:
    """Return the three-state ``activated_agent_profiles`` set for ``repo_root``.

    ``None`` → key absent from config (all profiles available — NFR-001
    backward-compat). ``frozenset()`` → explicit empty (nothing activated).
    Non-empty frozenset → explicit set of activated IDs.
    """
    if not (repo_root / _KITTIFY_DIR / "config.yaml").exists():
        return None

    from charter.activation.pack_context import PackContext

    activated: frozenset[str] | None = PackContext.from_config(repo_root).activated_agent_profiles
    return activated


def _build_descriptor(p: AgentProfile, *, source_layer: str | None = None) -> dict[str, Any]:
    """Build the legacy descriptor row for a profile (schema preserved — NFR-001)."""
    from charter.profiles import DEFAULT_ROLE_CAPABILITIES, Role

    caps = DEFAULT_ROLE_CAPABILITIES.get(p.role) if isinstance(p.role, Role) else None
    canonical_verbs = list(caps.canonical_verbs) if caps else []
    # domain_keywords lives in specialization_context (SpecializationContext), NOT specialization
    sc = getattr(p, "specialization_context", None)
    domain_kws = list(sc.domain_keywords) if sc and sc.domain_keywords else []
    # collaboration.canonical_verbs also carries per-profile verbs
    collab = getattr(p, "collaboration", None)
    collab_verbs = list(collab.canonical_verbs) if collab and collab.canonical_verbs else []
    provenance = source_layer or getattr(p, "_source", None)
    if provenance == "project":
        source = "project_local"
    elif provenance == "org":
        source = "org"
    else:
        source = "built-in"
    return {
        "profile_id": p.profile_id,
        "identifier": p.profile_id,
        "name": p.name,  # AgentProfile.name (not friendly_name — that field does not exist)
        "role": str(p.role),
        "action_domains": sorted({*canonical_verbs, *collab_verbs, *domain_kws}),
        "source": source,
    }


def _profile_catalog(
    repo_root: Path,
) -> tuple[list[AgentProfile], dict[str, str | None], dict[str, AgentProfileRepository]]:
    """Return merged doctrine + legacy invocation profiles.

    ``.kittify/profiles`` remains the live invocation registry for ask/router
    flows, while ``.kittify/doctrine/agent_profiles`` is the charter doctrine
    surface. The profile CLI must not hide either source.
    """
    from charter.profiles import AgentProfileRepository

    legacy_dir = repo_root / _KITTIFY_DIR / "profiles"
    legacy_repo = AgentProfileRepository(
        project_dir=legacy_dir if legacy_dir.exists() else None
    )

    by_id: dict[str, AgentProfile] = {}
    provenance: dict[str, str | None] = {}
    owner: dict[str, AgentProfileRepository] = {}

    # Display surface (FR-008 audited): the profile CLI is the operator-facing
    # *catalog view*, NOT dispatch routing, so it reads the UNGATED built-in +
    # legacy-invocation catalog directly from ``legacy_repo``. ``--all`` /
    # ``--show-available`` annotate each row with its activated|available state,
    # which requires de-activated profiles to remain visible here. (The gated
    # routing catalog now lives in ``ProfileRegistry`` per R3 and must not be
    # used as this view's source, or de-activated rows would vanish.)
    for profile in legacy_repo.list_all():
        layer = legacy_repo.get_provenance(profile.profile_id)
        by_id[profile.profile_id] = profile
        provenance[profile.profile_id] = layer
        owner[profile.profile_id] = legacy_repo

    # Overlay charter doctrine project/org profiles that the legacy invocation
    # registry cannot see. The doctrine inner repository is read UNGATED so the
    # catalog view shows every layer; activation state is annotated separately.
    project_doctrine_profiles = repo_root / _KITTIFY_DIR / "doctrine" / "agent_profiles"
    from charter.drg import resolve_org_roots

    org_roots = [root for root in resolve_org_roots(repo_root) if root.exists()]
    if project_doctrine_profiles.exists() or org_roots:
        from specify_cli.doctrine_service_factory import (
            build_activation_aware_doctrine_service,
        )

        svc = build_activation_aware_doctrine_service(repo_root)
        doctrine_repo: AgentProfileRepository = svc.agent_profile_repository
        for profile in doctrine_repo.list_all():
            layer = doctrine_repo.get_provenance(profile.profile_id)
            if layer in {"project", "org"}:
                by_id[profile.profile_id] = profile
                provenance[profile.profile_id] = layer
                owner[profile.profile_id] = doctrine_repo

    return (
        sorted(by_id.values(), key=lambda p: p.profile_id),
        provenance,
        owner,
    )


@app.command("list")
def list_profiles(
    json_output: bool = typer.Option(False, "--json", help="Output JSON array."),
    show_all: bool = typer.Option(
        False,
        "--all",
        help=(
            "Show every profile across all source layers (annotated by source "
            "layer and activated|available state). Supersedes the activated-only "
            "default and --show-available."
        ),
    ),
    show_available: bool = typer.Option(
        False,
        "--show-available",
        help="Also show available-but-not-activated profiles (annotated by state).",
    ),
    mission: str | None = typer.Option(
        None,
        "--mission",
        hidden=True,
        help=(
            "Accepted and ignored: profiles are mission-agnostic. Lets agents "
            "pass --mission uniformly in multi-mission repos (#3953)."
        ),
    ),
) -> None:
    """List agent profiles (activated-only by default; --all for the full catalog)."""
    del mission  # mission-agnostic: accepted for CLI consistency only (#3953)
    # FR-008 / T031: This command does not open an InvocationRecord at baseline.
    # If a future version of `profiles list` opens an invocation, it should use:
    #   derive_mode("profiles.list")  -> ModeOfWork.QUERY
    # The mapping is reserved in _ENTRY_COMMAND_MODE (modes.py) for enforcement
    # consistency (QUERY mode disallows Tier 2 evidence promotion per FR-009).
    # TODO(future): wire derive_mode("profiles.list") when InvocationRecord is opened here.
    repo_root = find_repo_root()
    profiles, provenance, _owner = _profile_catalog(repo_root)

    if not profiles:
        if json_output:
            typer.echo("[]")
        else:
            console.print(
                "[yellow]No profiles found.[/yellow] "
                "Run 'spec-kitty charter synthesize' to create project-local profiles."
            )
        raise typer.Exit(0)

    # --all is the richer, layer-aware availability view; it implies --show-available.
    if show_all:
        show_available = True

    activated = _activated_agent_profiles(repo_root)

    # FR-011: default lists activated-only by *filtering* the existing rows.
    # When the catalog/state columns are not requested, preserve the legacy
    # descriptor schema and byte-identical output for unconfigured projects.
    if not show_available:
        if activated is not None:
            profiles = [p for p in profiles if p.profile_id in activated]
        descriptors = [
            _build_descriptor(p, source_layer=provenance.get(p.profile_id))
            for p in profiles
        ]
        _render_list(descriptors, json_output=json_output)
        return

    # FR-012: --all / --show-available — annotate every row by source + state.
    descriptors = []
    for p in profiles:
        d = _build_descriptor(p, source_layer=provenance.get(p.profile_id))
        is_activated = activated is None or p.profile_id in activated
        d["state"] = "activated" if is_activated else "available"
        descriptors.append(d)

    _render_list_annotated(descriptors, json_output=json_output)


def _render_list(descriptors: list[dict[str, Any]], *, json_output: bool) -> None:
    """Render the default (legacy-schema) list output — NFR-001 byte-identity."""
    if json_output:
        typer.echo(json.dumps(descriptors, indent=2))
        return
    table = Table(title="Agent Profiles")
    table.add_column(_PROFILE_ID_LABEL, no_wrap=True, overflow="fold")
    table.add_column("Friendly Name")
    table.add_column("Role")
    table.add_column("Source")
    for d in descriptors:
        table.add_row(str(d["profile_id"]), str(d["name"]), str(d["role"]), str(d["source"]))
    console.print(table)


def _render_list_annotated(descriptors: list[dict[str, Any]], *, json_output: bool) -> None:
    """Render the layer-aware list (adds a State column) for --all / --show-available."""
    if json_output:
        typer.echo(json.dumps(descriptors, indent=2))
        return
    table = Table(title="Agent Profiles")
    table.add_column(_PROFILE_ID_LABEL, no_wrap=True, overflow="fold")
    table.add_column("Friendly Name")
    table.add_column("Role")
    table.add_column("Source")
    table.add_column("State")
    for d in descriptors:
        state = str(d.get("state", "activated"))
        style = "green" if state == "activated" else "dim"
        table.add_row(
            str(d["profile_id"]),
            str(d["name"]),
            str(d["role"]),
            str(d["source"]),
            f"[{style}]{state}[/{style}]",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# profile show (FR-013/014/015)
# ---------------------------------------------------------------------------

#: Warning text emitted when resolution traverses non-activated ancestor
#: profiles (abstract base profiles). Schema mirrors data-model.md.
_LINEAGE_WARNING_PREFIX = "resolved via non-activated parent profile(s): "
_LINEAGE_WARNING_SUFFIX = (
    " — these act as abstract base profiles and are not directly selectable"
)


def _lineage_warning(non_activated_ancestors: list[str]) -> str:
    """Build the FR-015 lineage warning naming non-activated ancestors."""
    return (
        _LINEAGE_WARNING_PREFIX
        + ", ".join(non_activated_ancestors)
        + _LINEAGE_WARNING_SUFFIX
    )


def _profile_payload(profile: AgentProfile, *, source_layer: str | None, warnings: list[str]) -> dict[str, Any]:
    """Build the rendered/JSON payload for a resolved profile (sorted-key safe)."""
    spec = profile.specialization
    collab = profile.collaboration
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "role": str(profile.role),
        "initialization_declaration": profile.initialization_declaration,
        "specialization": {
            "primary_focus": spec.primary_focus,
            "secondary_awareness": spec.secondary_awareness,
            "avoidance_boundary": spec.avoidance_boundary,
            "success_definition": spec.success_definition,
        },
        "collaboration": {
            "handoff_to": list(collab.handoff_to),
            "handoff_from": list(collab.handoff_from),
            "works_with": list(collab.works_with),
            "canonical_verbs": list(collab.canonical_verbs),
        },
        "mode_defaults": [
            {"mode": m.mode, "description": m.description, "use_case": m.use_case}
            for m in profile.mode_defaults
        ],
        "directive_references": [
            {"code": r.code, "name": r.name, "rationale": r.rationale}
            for r in profile.directive_references
        ],
        "tactic_references": [
            {"id": r.id, "rationale": r.rationale} for r in profile.tactic_references
        ],
        "source_layer": source_layer,
        "warnings": warnings,
    }


def _resolve_with_lineage(
    repo: AgentProfileRepository,
    profile_id: str,
    activated: frozenset[str] | None,
) -> tuple[AgentProfile, list[str]]:
    """Resolve ``profile_id`` (composing lineage) and collect non-activated ancestors.

    FR-015 (Option A): resolution may traverse non-activated ``specializes_from``
    parents (abstract base profiles). Any traversed ancestor not in the activated
    set yields a user-facing warning; inheritance is never silently hidden.
    """
    resolved = repo.resolve_profile(profile_id)
    warnings: list[str] = []
    ancestors = repo.get_ancestors(profile_id)
    if ancestors and activated is not None:
        non_activated = [a for a in ancestors if a not in activated]
        if non_activated:
            warnings.append(_lineage_warning(non_activated))
    return resolved, warnings


@app.command("show")
@app.command("get", hidden=True)
def show_profile(
    profile_id: str = typer.Argument(..., help="Profile ID to show."),
    json_output: bool = typer.Option(False, "--json", help="Output JSON object."),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Bypass the activation gate for inspection (show non-activated profiles).",
    ),
    mission: str | None = typer.Option(
        None,
        "--mission",
        hidden=True,
        help=(
            "Accepted and ignored: profiles are mission-agnostic. Lets agents "
            "pass --mission uniformly in multi-mission repos (#3953)."
        ),
    ),
) -> None:
    """Show the full resolved definition of an agent profile (FR-013/014/015)."""
    del mission  # mission-agnostic: accepted for CLI consistency only (#3953)
    repo_root = find_repo_root()
    profiles, provenance, owner = _profile_catalog(repo_root)
    by_id = {p.profile_id: p for p in profiles}
    activated = _activated_agent_profiles(repo_root)
    activated_profiles = (
        by_id if activated is None else {k: v for k, v in by_id.items() if k in activated}
    )

    # FR-014: activation gate on the leaf id. --all bypasses for inspection.
    if profile_id not in activated_profiles and not show_all:
        candidates = sorted(activated_profiles.keys())
        _emit_not_activated(profile_id, candidates, json_output=json_output)
        raise typer.Exit(1)

    repo = owner.get(profile_id)
    if repo is None or repo.get(profile_id) is None:
        # Not loaded at all (even built-in) — surface as not-activated with the
        # activated candidate set (FR-014 schema).
        candidates = sorted(activated_profiles.keys())
        _emit_not_activated(profile_id, candidates, json_output=json_output)
        raise typer.Exit(1)

    resolved, warnings = _resolve_with_lineage(repo, profile_id, activated)
    source_layer = provenance.get(profile_id)

    payload = _profile_payload(resolved, source_layer=source_layer, warnings=warnings)

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_profile_human(payload)
        for warning in warnings:
            console.print(f"[yellow]warning: {warning}[/yellow]", style="yellow")


def _emit_not_activated(
    profile_id: str,
    activated_candidates: list[str],
    *,
    json_output: bool,
) -> None:
    """Emit the structured ``profile_not_activated`` error (data-model.md)."""
    error = {
        "error": "profile_not_activated",
        "profile_id": profile_id,
        "activated_candidates": activated_candidates,
    }
    if json_output:
        typer.echo(json.dumps(error, indent=2, sort_keys=True))
    else:
        console.print(
            f"[red]Error: profile '{profile_id}' is not activated.[/red]"
        )
        if activated_candidates:
            console.print(
                "Activated candidates: " + ", ".join(activated_candidates)
            )
        else:
            console.print("No agent profiles are currently activated.")
        console.print(
            "Use --all to inspect a non-activated profile, or activate it via "
            "'spec-kitty charter activate agent-profile <id>'."
        )


def _render_profile_human(payload: dict[str, Any]) -> None:
    """Render the resolved profile as a human-readable table."""
    table = Table(title=f"Agent Profile: {payload['profile_id']}", show_lines=True)
    table.add_column("Field", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row(_PROFILE_ID_LABEL, str(payload["profile_id"]))
    table.add_row("Name", str(payload["name"]))
    table.add_row("Role", str(payload["role"]))
    table.add_row("Source layer", str(payload["source_layer"]))
    table.add_row("Initialization", str(payload["initialization_declaration"]) or _EMPTY_VALUE)

    spec = payload["specialization"]
    table.add_row("Primary focus", spec["primary_focus"] or _EMPTY_VALUE)
    table.add_row("Secondary awareness", spec["secondary_awareness"] or _EMPTY_VALUE)
    table.add_row("Avoidance boundary", spec["avoidance_boundary"] or _EMPTY_VALUE)
    table.add_row("Success definition", spec["success_definition"] or _EMPTY_VALUE)

    collab = payload["collaboration"]
    table.add_row("Handoff to", ", ".join(collab["handoff_to"]) or _EMPTY_VALUE)
    table.add_row("Handoff from", ", ".join(collab["handoff_from"]) or _EMPTY_VALUE)
    table.add_row("Works with", ", ".join(collab["works_with"]) or _EMPTY_VALUE)
    table.add_row("Canonical verbs", ", ".join(collab["canonical_verbs"]) or _EMPTY_VALUE)

    modes = ", ".join(m["mode"] for m in payload["mode_defaults"])
    table.add_row("Mode defaults", modes or _EMPTY_VALUE)
    directives = ", ".join(r["code"] for r in payload["directive_references"])
    table.add_row("Directive refs", directives or _EMPTY_VALUE)
    tactics = ", ".join(r["id"] for r in payload["tactic_references"])
    table.add_row("Tactic refs", tactics or _EMPTY_VALUE)

    console.print(table)
