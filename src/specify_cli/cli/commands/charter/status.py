"""``spec-kitty charter status`` command body (WP06 per-subcommand split).

Pure command surface: collection logic lives in
:mod:`specify_cli.cli.commands.charter._status_collectors`. Tests historically
reach for the ``_collect_*`` symbols via ``from specify_cli.cli.commands.charter
import _collect_charter_sync_status`` etc., so the package ``__init__`` re-exports
them.

Errors (#6557, operator decision 01M5ZCANVH16B2ANT1BJ115S8R): an unsound
``charter.yaml`` is refused by the shared soundness gate before the bundle
check, and every error renders through :func:`render_coded_error` --
``Error (<CODE>): <message>`` in text mode, the canonical
``{"ok": false, "error": {"code", "message"}}`` envelope under ``--json``.
"""
from __future__ import annotations

import json
from typing import Any

import typer
from rich.table import Table

from charter.activation.evidence.orchestrator import ConfigShapeError
from kernel.errors import KittyInternalConsistencyError
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import (
    CHARTER_YAML_FILENAME,
    charter_app,
    console,
)
from specify_cli.cli.commands.charter._charter_yaml_gate import assert_charter_yaml_sound
from specify_cli.cli.commands.charter._coded_errors import render_coded_error
from specify_cli.cli.commands.charter._status_collectors import (
    _collect_activation_status,
    _collect_governance_reference_status,
    _collect_org_layer_status,
)

# Test-patch shim: ``find_repo_root``, ``_assert_bundle_compatible``,
# ``_collect_charter_sync_status``, and ``_collect_synthesis_status`` are looked
# up on the package module at call time so legacy
# ``patch("specify_cli.cli.commands.charter.X", ...)`` test fixtures keep
# working after the WP06 split.
import specify_cli.cli.commands.charter as _charter_pkg

__all__ = ["status"]

#: ``.kittify/config.yaml`` is not a mapping (ledger SK-16).
CHARTER_CONFIG_SHAPE_INVALID = "CHARTER_CONFIG_SHAPE_INVALID"
#: Repository or task resolution failed (``TaskCliError``).
CHARTER_STATUS_FAILED = "CHARTER_STATUS_FAILED"
#: An exception no handler anticipated; the only path that says "Unexpected".
INTERNAL_ERROR = "INTERNAL_ERROR"

_WARNING_LINE = "  [yellow]Warning:[/yellow] {}"


def _status_error(exc: Exception) -> tuple[str, str]:
    """The ``(code, message)`` pair ``charter status`` renders for *exc* (contracts/cli-json.md)."""
    if isinstance(exc, KittyInternalConsistencyError):
        return exc.code, exc.body or exc.code
    if isinstance(exc, ConfigShapeError):
        return CHARTER_CONFIG_SHAPE_INVALID, str(exc)
    if isinstance(exc, TaskCliError):
        return CHARTER_STATUS_FAILED, str(exc)
    return INTERNAL_ERROR, f"Unexpected error: {exc}"


def _build_payload(*, provenance: bool) -> dict[str, Any]:
    repo_root = _charter_pkg.find_repo_root()
    # #6557: refuse an unsound charter.yaml (unparseable, non-mapping, empty)
    # with ACTIVE_CHARTER_CONFIG_INVALID BEFORE the bundle check, so a
    # list-rooted file never reaches the bundle-schema "run upgrade" message.
    assert_charter_yaml_sound(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    # consolidate-charter-bundle (#2773): gate on the authoritative
    # charter.yaml, not the retired metadata.yaml (which the fold migration
    # deletes) — else the bundle-compat check silently no-ops on v2 bundles.
    if (charter_dir / CHARTER_YAML_FILENAME).exists():
        _charter_pkg._assert_bundle_compatible(charter_dir)
    from specify_cli.charter_runtime.freshness import compute_freshness

    return {
        "result": "success",
        "charter_sync": _charter_pkg._collect_charter_sync_status(repo_root),
        "synthesis": _charter_pkg._collect_synthesis_status(
            repo_root,
            include_provenance=provenance,
        ),
        # WP07 FR-002: org-layer state (built-in + org packs + project).
        # Always present in JSON output; packs list is empty when no org
        # packs are configured (NFR-001 — no spurious empty section).
        "org_layer": _collect_org_layer_status(repo_root),
        "governance_references": _collect_governance_reference_status(repo_root),
        # WP02 FR-005: freshness sub-payload (charter -> bundle -> DRG).
        "freshness": compute_freshness(repo_root).to_dict(),
        # #6526 (local slice): activation state; JSON only, never rendered
        # in text mode (FR-011).
        "activation": _collect_activation_status(repo_root),
    }


def status(
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    provenance: bool = typer.Option(
        False,
        "--provenance",
        help="Include per-artifact provenance details.",
    ),
) -> None:
    """Display charter sync status plus synthesis/operator state."""
    try:
        payload = _build_payload(provenance=provenance)
        if json_output:
            print(json.dumps(payload, indent=2))
            return
        _render_text(payload, provenance=provenance)
    except Exception as e:
        code, message = _status_error(e)
        render_coded_error(code, message, json_output=json_output)
        raise typer.Exit(code=1) from e


# Registered by call rather than decorator so ``status`` keeps its signature
# under ``mypy --strict`` (``untyped-decorator``), as ``activate``/``deactivate`` do.
charter_app.command("status")(status)


# --------------------------------------------------------------------------- #
# Text rendering (human-readable output only; JSON was emitted above)
# --------------------------------------------------------------------------- #


def _render_text(payload: dict[str, Any], *, provenance: bool) -> None:
    _render_charter_sync(payload)
    _render_synthesis(payload["synthesis"], provenance=provenance)
    _render_org_layer(payload["org_layer"])
    _render_freshness(payload["freshness"])


def _render_charter_sync(payload: dict[str, Any]) -> None:
    sync_status = payload["charter_sync"]
    console.print("[bold]Charter sync[/bold]")
    if not sync_status["available"]:
        console.print(f"[yellow]Unavailable[/yellow]: {sync_status['error']}")
        return
    console.print(f"Charter: {sync_status['charter_path']}")
    if sync_status["status"] == "stale":
        console.print("Status: [yellow]STALE[/yellow] (modified since last sync)")
        if sync_status["stored_hash"]:
            console.print(f"Expected hash: {sync_status['stored_hash']}")
        console.print(f"Current hash:  {sync_status['current_hash']}")
        # Reuse the freshness computer's recommendation (single source);
        # it is None when no command can clear the state.
        remediation = payload["freshness"]["charter_source"]["remediation"]
        if remediation:
            console.print(f"\n[dim]Run: {remediation}[/dim]")
    else:
        console.print("Status: [green]SYNCED[/green]")
        if sync_status["last_sync"]:
            console.print(f"Last sync: {sync_status['last_sync']}")
        console.print(f"Hash: {sync_status['current_hash']}")

    console.print(f"Library docs: {sync_status['library_docs']}")
    governance_references = payload["governance_references"]
    if governance_references["warnings"]:
        console.print("\n[yellow]Governance reference warnings[/yellow]")
        for warning in governance_references["warnings"]:
            console.print(f"  - {warning}")
    console.print("\nExtracted files:")
    _render_extracted_files(sync_status["files"])


def _render_extracted_files(files: list[dict[str, Any]]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("File", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Size", justify="right")

    for file_info in files:
        name = str(file_info["name"])
        exists = bool(file_info["exists"])
        size_kb = float(file_info["size_kb"])

        if exists:
            status_icon = "[green]Y[/green]"
            size_str = f"{size_kb:.1f} KB"
        else:
            status_icon = "[red]N[/red]"
            size_str = "[dim]-[/dim]"

        table.add_row(name, status_icon, size_str)

    console.print(table)


_GENERATION_STATE_STYLES = {
    "promoted": "green",
    "ready_for_validation": "yellow",
    "needs_attention": "red",
    "not_started": "blue",
}
_MANIFEST_STATE_STYLES = {
    "valid": "green",
    "missing": "blue",
    "partial": "yellow",
    "invalid": "red",
}


def _render_synthesis(synthesis: dict[str, Any], *, provenance: bool) -> None:
    generated_inputs = synthesis["generated_inputs"]
    state = synthesis["generation_state"]
    state_style = _GENERATION_STATE_STYLES.get(state, "white")

    console.print("\n[bold]Synthesis[/bold]")
    console.print(f"Generation state: [{state_style}]{state.upper()}[/{state_style}]")
    console.print(
        "Generated inputs: "
        f"{generated_inputs['counts']['directive']} directive, "
        f"{generated_inputs['counts']['tactic']} tactic, "
        f"{generated_inputs['counts']['styleguide']} styleguide "
        f"under {generated_inputs['path']}"
    )
    _render_manifest(synthesis["manifest"])
    _render_evidence(synthesis["evidence"])
    _render_provenance_summary(synthesis["provenance"])
    if provenance and synthesis["provenance"]["entries"]:
        _render_provenance_entries(synthesis["provenance"]["entries"])


def _render_manifest(manifest: dict[str, Any]) -> None:
    manifest_state_style = _MANIFEST_STATE_STYLES.get(manifest["state"], "white")
    console.print(f"Manifest: [{manifest_state_style}]{manifest['state'].upper()}[/{manifest_state_style}] ({manifest['path']})")
    if manifest["exists"]:
        if manifest["run_id"] and manifest["adapter_id"] and manifest["adapter_version"]:
            console.print(f"  Run: {manifest['run_id']}  Adapter: {manifest['adapter_id']} v{manifest['adapter_version']}")
        console.print(f"  Artifacts: {manifest['artifact_count']} (live doctrine files: {manifest['live_artifact_count']})")
    if manifest["error"]:
        console.print(f"  [red]Error:[/red] {manifest['error']}")
    if manifest["missing_provenance_paths"]:
        console.print("  Missing provenance paths:")
        for path in manifest["missing_provenance_paths"]:
            console.print(f"    [red]-[/red] {path}")


def _render_evidence(evidence: dict[str, Any]) -> None:
    if evidence["code"] is not None:
        code = evidence["code"]
        console.print(
            "Evidence: "
            f"stack={code['stack_id']} "
            f"(lang={'+'.join(code['languages']) if len(code.get('languages', ())) > 1 else code['primary_language']}, "
            f"frameworks={len(code['frameworks'])}, "
            f"test_frameworks={len(code['test_frameworks'])})"
        )
    else:
        console.print("Evidence: code signals unavailable")
    console.print(f"  Configured URLs: {evidence['configured_url_count']}  Corpus snapshot: {evidence['corpus_snapshot_id'] or '(none)'}")
    for warning in evidence["warnings"]:
        console.print(_WARNING_LINE.format(warning))


def _render_provenance_summary(provenance_status: dict[str, Any]) -> None:
    console.print(f"Provenance: {provenance_status['parsed_count']} visible sidecar(s)")
    if provenance_status["manifest_artifact_count"]:
        console.print(
            "  Manifest coverage: "
            f"{provenance_status['manifest_artifact_count'] - provenance_status['missing_for_manifest_count']}/"
            f"{provenance_status['manifest_artifact_count']}"
        )
    if provenance_status["corpus_snapshot_ids"]:
        console.print("  Corpus snapshots: " + ", ".join(provenance_status["corpus_snapshot_ids"]))
    for warning in provenance_status["warnings"]:
        console.print(_WARNING_LINE.format(warning))


def _render_provenance_entries(entries: list[dict[str, Any]]) -> None:
    console.print("\nProvenance entries:")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Kind", style="cyan")
    table.add_column("Slug", style="cyan")
    table.add_column("Artifact URN", style="magenta")
    table.add_column("Adapter")
    table.add_column("Corpus")
    table.add_column("Evidence Hash")

    for entry in entries:
        evidence_hash = entry["evidence_bundle_hash"] or ""
        table.add_row(
            str(entry["kind"]),
            str(entry["slug"]),
            str(entry["artifact_urn"]),
            f"{entry['adapter_id']} v{entry['adapter_version']}",
            str(entry["corpus_snapshot_id"] or "-"),
            evidence_hash[:12] if evidence_hash else "-",
        )

    console.print(table)


def _render_org_pack(pack: dict[str, Any]) -> None:
    pack_name = pack.get("name", "unknown")
    source_ref = pack.get("source_ref", "")
    if pack.get("fetched", True):
        console.print(
            f"  [green]org:{pack_name}[/green]: [dim]{source_ref}[/dim] ({pack.get('node_count', 0)} nodes, {pack.get('edge_count', 0)} edges)"
        )
    else:
        console.print(f"  [red]org:{pack_name}[/red]: [red]MISSING[/red] — {source_ref}")


def _render_org_layer(org_layer: dict[str, Any]) -> None:
    """WP07 FR-002 — Organisation Layer section."""
    org_packs = org_layer.get("packs", [])
    console.print("\n[bold]Organisation Layer[/bold]")
    console.print("  [dim]built-in[/dim]: [green]present[/green]")
    if org_packs:
        for pack in org_packs:
            _render_org_pack(pack)
        for cw in org_layer.get("collision_warnings") or ():
            console.print(f"  [yellow]collision[/yellow]: {cw.get('kind')} target={cw.get('target_id')} resolution={cw.get('resolution')}")
    else:
        console.print("  org: [dim](no packs configured)[/dim]")
    for err in org_layer.get("errors") or ():
        console.print(f"  [red]Error:[/red] {err}")


_FRESHNESS_STYLES = {
    "fresh": "green",
    "stale": "yellow",
    "missing": "blue",
    "built_in_only": "cyan",
    "invalid": "red",
}
_FRESHNESS_LAYERS = (
    ("Charter source ", "charter_source"),
    ("Synced bundle  ", "synced_bundle"),
    ("Synthesized DRG", "synthesized_drg"),
)


def _render_freshness(freshness: dict[str, Any]) -> None:
    """WP02 FR-005 — Freshness section."""
    console.print("\n[bold]Freshness[/bold]")
    for layer_label, layer_key in _FRESHNESS_LAYERS:
        sub = freshness[layer_key]
        state = sub["state"]
        colour = _FRESHNESS_STYLES.get(state, "white")
        line = f"  {layer_label}: [{colour}]{state.upper()}[/{colour}]"
        if sub.get("last_change"):
            line += f"  [dim]last_change={sub['last_change']}[/dim]"
        console.print(line)
        if sub.get("detail"):
            console.print(f"    [dim]{sub['detail']}[/dim]")
        if sub.get("remediation"):
            console.print(f"    [dim]Run: {sub['remediation']}[/dim]")
