"""``spec-kitty charter status`` command body (WP06 per-subcommand split).

Pure command surface: collection logic lives in
:mod:`specify_cli.cli.commands.charter._status_collectors`. Tests historically
reach for the ``_collect_*`` symbols via ``from specify_cli.cli.commands.charter
import _collect_charter_sync_status`` etc., so the package ``__init__`` re-exports
them.
"""
from __future__ import annotations

import json
from typing import Any

import typer
from rich.table import Table

from charter.activation.evidence.orchestrator import ConfigShapeError
from specify_cli.task_utils import TaskCliError

from specify_cli.cli.commands.charter._app import (
    CHARTER_YAML_FILENAME,
    charter_app,
    console,
)
from specify_cli.cli.commands.charter._common import _emit_error
from specify_cli.cli.commands.charter._status_collectors import (
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


@charter_app.command()
def status(  # noqa: C901
    json_output: bool = typer.Option(False, "--json", help="Output JSON"),
    provenance: bool = typer.Option(
        False,
        "--provenance",
        help="Include per-artifact provenance details.",
    ),
) -> None:
    """Display charter sync status plus synthesis/operator state."""
    try:
        repo_root = _charter_pkg.find_repo_root()
        charter_dir = repo_root / ".kittify" / "charter"
        # consolidate-charter-bundle (#2773): gate on the authoritative
        # charter.yaml, not the retired metadata.yaml (which the fold migration
        # deletes) — else the bundle-compat check silently no-ops on v2 bundles.
        if (charter_dir / CHARTER_YAML_FILENAME).exists():
            _charter_pkg._assert_bundle_compatible(charter_dir)
        from specify_cli.charter_runtime.freshness import compute_freshness

        payload: dict[str, Any] = {
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
        }

        if json_output:
            print(json.dumps(payload, indent=2))
            return

        sync_status = payload["charter_sync"]
        console.print("[bold]Charter sync[/bold]")
        if sync_status["available"]:
            console.print(f"Charter: {sync_status['charter_path']}")
            if sync_status["status"] == "stale":
                console.print(
                    "Status: [yellow]STALE[/yellow] (modified since last sync)"
                )
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
            table = Table(show_header=True, header_style="bold")
            table.add_column("File", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Size", justify="right")

            for file_info in sync_status["files"]:
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
        else:
            console.print(
                f"[yellow]Unavailable[/yellow]: {sync_status['error']}"
            )

        synthesis = payload["synthesis"]
        manifest = synthesis["manifest"]
        generated_inputs = synthesis["generated_inputs"]
        evidence = synthesis["evidence"]
        provenance_status = synthesis["provenance"]

        state_styles = {
            "promoted": "green",
            "ready_for_validation": "yellow",
            "needs_attention": "red",
            "not_started": "blue",
        }
        state = synthesis["generation_state"]
        state_style = state_styles.get(state, "white")

        console.print("\n[bold]Synthesis[/bold]")
        console.print(
            f"Generation state: [{state_style}]{state.upper()}[/{state_style}]"
        )
        console.print(
            "Generated inputs: "
            f"{generated_inputs['counts']['directive']} directive, "
            f"{generated_inputs['counts']['tactic']} tactic, "
            f"{generated_inputs['counts']['styleguide']} styleguide "
            f"under {generated_inputs['path']}"
        )

        manifest_state_style = {
            "valid": "green",
            "missing": "blue",
            "partial": "yellow",
            "invalid": "red",
        }.get(manifest["state"], "white")
        console.print(
            f"Manifest: [{manifest_state_style}]{manifest['state'].upper()}[/{manifest_state_style}] "
            f"({manifest['path']})"
        )
        if manifest["exists"]:
            if manifest["run_id"] and manifest["adapter_id"] and manifest["adapter_version"]:
                console.print(
                    f"  Run: {manifest['run_id']}  Adapter: {manifest['adapter_id']} v{manifest['adapter_version']}"
                )
            console.print(
                f"  Artifacts: {manifest['artifact_count']} "
                f"(live doctrine files: {manifest['live_artifact_count']})"
            )
        if manifest["error"]:
            console.print(f"  [red]Error:[/red] {manifest['error']}")
        if manifest["missing_provenance_paths"]:
            console.print("  Missing provenance paths:")
            for path in manifest["missing_provenance_paths"]:
                console.print(f"    [red]-[/red] {path}")

        if evidence["code"] is not None:
            code = evidence["code"]
            console.print(
                "Evidence: "
                f"stack={code['stack_id']} "
                f"(lang={code['primary_language']}, "
                f"frameworks={len(code['frameworks'])}, "
                f"test_frameworks={len(code['test_frameworks'])})"
            )
        else:
            console.print("Evidence: code signals unavailable")
        console.print(
            f"  Configured URLs: {evidence['configured_url_count']}  "
            f"Corpus snapshot: {evidence['corpus_snapshot_id'] or '(none)'}"
        )
        if evidence["warnings"]:
            for warning in evidence["warnings"]:
                console.print(f"  [yellow]Warning:[/yellow] {warning}")

        console.print(
            "Provenance: "
            f"{provenance_status['parsed_count']} visible sidecar(s)"
        )
        if provenance_status["manifest_artifact_count"]:
            console.print(
                "  Manifest coverage: "
                f"{provenance_status['manifest_artifact_count'] - provenance_status['missing_for_manifest_count']}/"
                f"{provenance_status['manifest_artifact_count']}"
            )
        if provenance_status["corpus_snapshot_ids"]:
            console.print(
                "  Corpus snapshots: "
                + ", ".join(provenance_status["corpus_snapshot_ids"])
            )
        if provenance_status["warnings"]:
            for warning in provenance_status["warnings"]:
                console.print(f"  [yellow]Warning:[/yellow] {warning}")

        if provenance and provenance_status["entries"]:
            console.print("\nProvenance entries:")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Kind", style="cyan")
            table.add_column("Slug", style="cyan")
            table.add_column("Artifact URN", style="magenta")
            table.add_column("Adapter")
            table.add_column("Corpus")
            table.add_column("Evidence Hash")

            for entry in provenance_status["entries"]:
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

        # WP07 FR-002 — Organisation Layer section (human-readable output only).
        # JSON output was already emitted above; this block renders the console view.
        org_layer = payload["org_layer"]
        org_packs = org_layer.get("packs", [])
        console.print("\n[bold]Organisation Layer[/bold]")
        console.print("  [dim]built-in[/dim]: [green]present[/green]")
        if org_packs:
            for pack in org_packs:
                pack_name = pack.get("name", "unknown")
                source_ref = pack.get("source_ref", "")
                node_count = pack.get("node_count", 0)
                edge_count = pack.get("edge_count", 0)
                fetched = pack.get("fetched", True)
                if fetched:
                    console.print(
                        f"  [green]org:{pack_name}[/green]: "
                        f"[dim]{source_ref}[/dim] "
                        f"({node_count} nodes, {edge_count} edges)"
                    )
                else:
                    console.print(
                        f"  [red]org:{pack_name}[/red]: [red]MISSING[/red] — {source_ref}"
                    )
            if org_layer.get("collision_warnings"):
                for cw in org_layer["collision_warnings"]:
                    console.print(
                        f"  [yellow]collision[/yellow]: {cw.get('kind')} "
                        f"target={cw.get('target_id')} "
                        f"resolution={cw.get('resolution')}"
                    )
        else:
            console.print("  org: [dim](no packs configured)[/dim]")
        if org_layer.get("errors"):
            for err in org_layer["errors"]:
                console.print(f"  [red]Error:[/red] {err}")

        # WP02 FR-005 — Freshness section (human-readable output only).
        freshness = payload["freshness"]
        console.print("\n[bold]Freshness[/bold]")
        _freshness_style = {
            "fresh": "green",
            "stale": "yellow",
            "missing": "blue",
            "built_in_only": "cyan",
            "invalid": "red",
        }
        for layer_label, layer_key in (
            ("Charter source ", "charter_source"),
            ("Synced bundle  ", "synced_bundle"),
            ("Synthesized DRG", "synthesized_drg"),
        ):
            sub = freshness[layer_key]
            state = sub["state"]
            colour = _freshness_style.get(state, "white")
            line = (
                f"  {layer_label}: [{colour}]{state.upper()}[/{colour}]"
            )
            if sub.get("last_change"):
                line += f"  [dim]last_change={sub['last_change']}[/dim]"
            console.print(line)
            if sub.get("detail"):
                console.print(f"    [dim]{sub['detail']}[/dim]")
            if sub.get("remediation"):
                console.print(f"    [dim]Run: {sub['remediation']}[/dim]")

    except (TaskCliError, ConfigShapeError) as e:
        # ConfigShapeError (a corrupt/non-mapping .kittify/config.yaml, ledger
        # SK-16) is a controlled, expected diagnostic -- treated the same as
        # TaskCliError, not routed through the generic "Unexpected error"
        # branch below.
        _emit_error(console, json_output=json_output, message=str(e))
        raise typer.Exit(code=1) from e
    except Exception as e:
        _emit_error(console, json_output=json_output, message=str(e), unexpected=True)
        raise typer.Exit(code=1) from e
