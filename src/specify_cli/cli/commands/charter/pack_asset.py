"""``spec-kitty charter pack asset`` — the operator surface over ASSET resolution.

WP05 (``doctrine-delivery-reachability``). Two read-only commands let an
operator see and resolve shipped/overlay charter pack assets, reading exclusively
through :class:`charter.offering.service.CharterOfferingService` ``.assets`` (the WP04
:class:`~charter.offering.assets.repository.AssetRepository`):

* ``asset list [--json]`` — every resolvable asset with its source tier.
* ``asset path <asset-id> [--json]`` — a resolvable filesystem path; an unknown
  id exits non-zero with the id named (contract A-7).

**C-002 — resolution and explicit invocation only.** Nothing here writes into a
consumer repository; there is no auto-install path. Assets are resolved from
package data (the built-in tier) plus the project/org overlays when the command
runs inside a project.

The subapp is registered under ``spec-kitty charter pack`` by
:mod:`specify_cli.cli.commands.charter._app` (mission
charter-pack-cutover-01M491G6, FR-006; moved from ``_doctrine_asset.py``).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import typer
from rich.table import Table

from specify_cli.cli.console import console

if TYPE_CHECKING:
    from pathlib import Path

    from charter.assets import AssetRepository

__all__ = ["asset_app"]

_JSON_OPTION_HELP = "Emit machine-readable JSON instead of rich text."

#: Marker recorded in the ``path`` column when a manifest resolves but its blob
#: escapes the anchoring root (NFR-006 containment refusal); never a real path.
_UNRESOLVABLE = "<unresolvable: path escapes root>"

asset_app = typer.Typer(
    name="asset",
    help="Resolve shipped and overlay charter pack assets (no install — C-002).",
    no_args_is_help=True,
)


def _build_asset_repository() -> AssetRepository:
    """Construct the three-tier asset repository for the current context.

    Built-in assets self-resolve via the shared ``built_in_dir(kind)`` seam
    (packaged data — editable checkout, installed wheel, or an
    ``importlib.resources`` sibling; no built-in-root parameter needed here),
    so the command works from a clean installation with no repository
    present. When invoked inside a project, the project pack root
    (``.kittify/charter-packs/``) layer and configured org packs are layered on top (more specific tiers
    win).

    WP03 (charter-sole-door-bypass-closure-01KZ3WAA, FR-002/T012): the raw
    inner service is always routed through the sanctioned
    ``charter.activation.resolver.ActiveCharterService`` wrapper (normal, activation-aware
    construction — a real ``PackContext`` when *repo_root* is available) so
    no code outside ``charter.activation.resolver``/the unified builder constructs
    ``charter.offering.service.CharterOfferingService`` directly (NFR-001). ``.assets`` is a
    non-charter-activatable kind (``ArtifactKind.ASSET`` is excluded via
    ``_NON_AUGMENTATION_ELIGIBLE_KINDS``), so it has no gated property on the
    wrapper and falls through ``__getattr__`` to the raw
    ``AssetRepository`` unfiltered either way -- this migration closes the
    construction site, it does not add new filtering for assets. The
    pre-existing ``repo_root is None`` clean-install branch (no project
    overlay, no org packs) is unchanged.
    """
    from charter.offering.service import CharterOfferingService
    from charter.activation.resolver import ActiveCharterService
    from charter.activation.pack_context import PackContext
    from specify_cli.core.paths import locate_project_root

    project_root: Path | None = None
    org_roots: list[Path] = []
    pack_context: PackContext | None = None
    repo_root = locate_project_root()
    if repo_root is not None:
        from charter.activation._project_root_candidates import resolve_project_root
        from charter.activation.layer_roots import resolve_pack_chain

        project_root = resolve_project_root(repo_root)
        org_roots = resolve_pack_chain(repo_root, strict=False)
        pack_context = PackContext.from_config(repo_root)

    inner = CharterOfferingService(project_root=project_root, org_roots=org_roots)
    service = ActiveCharterService(inner, pack_context=pack_context)
    # ``.assets`` delegates through the wrapper's ``__getattr__`` (typed
    # ``-> Any``, since it forwards arbitrary attribute names), so mypy
    # cannot infer the concrete return type on its own; the cast documents
    # what is actually true (``.assets`` is not one of the nine gated
    # properties, see this function's docstring).
    return cast("AssetRepository", service.assets)


def _resolved_path_str(repo: AssetRepository, asset_id: str) -> str:
    """Return the resolved blob path as a string, or the unresolvable marker.

    ``asset list`` iterates every loaded manifest, including ones whose
    anchoring can miss even though the manifest itself resolved cleanly out of
    :meth:`AssetRepository.list_all` — e.g. an org-tier manifest whose source
    isn't under any *currently* configured org dir, or a project-provenance
    manifest with no project dir. ``resolve_path`` raises
    :class:`AssetNotFoundError` for that anchoring miss (from ``_anchor_for``),
    distinct from the containment refusal :class:`AssetPathEscapeError` raised
    for a ``..``/symlink escape. Both render as the same unresolvable marker
    rather than one of them crashing the whole ``list`` command with an
    uncaught traceback.
    """
    from charter.assets import AssetNotFoundError, AssetPathEscapeError

    try:
        return str(repo.resolve_path(asset_id))
    except (AssetPathEscapeError, AssetNotFoundError):
        return _UNRESOLVABLE


@asset_app.command("list")
def asset_list(
    json_output: bool = typer.Option(False, "--json", help=_JSON_OPTION_HELP),
) -> None:
    """List all resolvable charter pack assets and their source tiers."""
    repo = _build_asset_repository()
    rows = [
        {
            "id": manifest.id,
            "tier": repo.get_provenance(manifest.id) or "unknown",
            "path": _resolved_path_str(repo, manifest.id),
        }
        for manifest in repo.list_all()
    ]

    if json_output:
        console.print_json(json.dumps(rows))
        return

    if not rows:
        console.print("[yellow]No charter pack assets found.[/yellow]")
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("TIER", style="green")
    table.add_column("PATH")
    for row in rows:
        table.add_row(row["id"], row["tier"], row["path"])
    console.print(table)
    raise typer.Exit(0)


@asset_app.command("path")
def asset_path(
    asset_id: str = typer.Argument(
        ...,
        metavar="ASSET_ID",
        help="Identifier of the asset to resolve (see `charter pack asset list`).",
    ),
    json_output: bool = typer.Option(False, "--json", help=_JSON_OPTION_HELP),
) -> None:
    """Resolve an asset identifier to a filesystem path (fail-closed on miss).

    Exits ``0`` and prints the path on success. An unknown id or a containment
    refusal exits non-zero with the offending id named (A-7 / NFR-006).
    """
    from charter.assets import (
        AssetNotFoundError,
        AssetPathEscapeError,
    )

    repo = _build_asset_repository()
    try:
        resolved = repo.resolve_path(asset_id)
    except AssetNotFoundError as exc:
        _emit_path_error(asset_id, f"Unknown asset id: {asset_id}", json_output)
        raise typer.Exit(1) from exc
    except AssetPathEscapeError as exc:
        _emit_path_error(asset_id, str(exc), json_output)
        raise typer.Exit(1) from exc

    if json_output:
        console.print_json(
            json.dumps(
                {
                    "id": asset_id,
                    "tier": repo.get_provenance(asset_id) or "unknown",
                    "path": str(resolved),
                }
            )
        )
    else:
        # ``soft_wrap`` keeps the path on one line so it stays copy-pasteable
        # and machine-consumable regardless of terminal width.
        console.print(str(resolved), soft_wrap=True)
    raise typer.Exit(0)


def _emit_path_error(asset_id: str, message: str, json_output: bool) -> None:
    """Render a ``path`` failure as JSON or rich text (id always named)."""
    if json_output:
        console.print_json(json.dumps({"id": asset_id, "error": message}))
    else:
        console.print(f"[red]{message}[/red]")
