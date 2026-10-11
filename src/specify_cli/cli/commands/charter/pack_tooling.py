"""Charter pack tooling: ``validate``, ``assemble`` and ``regenerate-graph``.

* ``spec-kitty charter pack validate <pack-path> [--json]`` — validate a pack
  against the artifact / DRG / org-charter / preset contracts.
* ``spec-kitty charter pack assemble <out> <inputs...> [--force]
  [--conflicts-out FILE] [--json]`` — assemble multiple input packs into a
  single distributable output pack.
* ``spec-kitty charter pack regenerate-graph [--check] [--json]`` —
  deterministically regenerate the shipped DRG as per-kind
  ``packs/built-in/*.graph.yaml`` fragments plus the built-in pack manifest.
  ``--check`` compares without writing and exits 1 when the committed source
  is stale.

The heavy lifting lives in :mod:`charter.packs`; this module only parses
arguments and maps exit codes. The handlers are registered on
``charter_pack_app`` by :mod:`specify_cli.cli.commands.charter._app`
(mission charter-pack-cutover-01M491G6, FR-006).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from specify_cli.cli.console import console

__all__ = ["pack_assemble", "pack_validate", "regenerate_graph"]

_JSON_OPTION_HELP = "Emit machine-readable JSON instead of rich text."


# ----------------------------------------------------------------------
# regenerate-graph — deterministic DRG regeneration (FR-009 / WP09 T026)
# ----------------------------------------------------------------------
def _built_in_pack_root() -> Path:
    """Return the built-in pack root that owns the shipped DRG graph source.

    Post-flatten (relocate-builtin-doctrine-packs, WP03) the built-in artifact
    content and the sharded ``*.graph.yaml`` fragments live in
    ``packs/built-in/`` — no longer under ``src/charter/offering/<kind>/built-in``. This
    root is both the extractor's artifact input *and* the fragment write-target /
    freshness read source; the extractor resolves ``missions/`` (which did NOT
    move) internally.

    Routes through :func:`charter.pack_paths.built_in_root` (the charter facade over
    :mod:`charter.offering.pack_paths`, C1.6), the single
    root-resolution authority every root-needing reader must use instead of
    scattering bare ``resolve_pack_root("built-in")`` calls or a hand-rolled
    walk. This retires the CWD ancestor-walk this function previously
    reimplemented (mission ``doctrine-built-in-seam-consolidation-01KYW3TX``
    WP03 — an INTENTIONAL, called-out NFR-001 behaviour delta, not a
    regression): an operator standing in a checkout different from the
    installed/editable module now resolves through the packaged seam (env
    override → editable-checkout ancestor walk from the *module's* location →
    installed wheel sibling → fail-closed) rather than a CWD-rooted walk. The
    normal in-checkout case (operator invoking from inside the repo whose
    ``packs/built-in`` this module loads from) resolves identically either way.
    """
    from charter.pack_paths import built_in_root

    root: Path = built_in_root()
    return root


def _require_built_in_level(pack_root: Path) -> None:
    """Refuse (exit 1) unless *pack_root* carries a ``pack.yaml`` declaring ``pack_level: built-in``.

    The generators are built-in-shaped (sharded ``*.graph.yaml`` fragments plus
    the built-in manifest); pointed at a project or org pack they would
    overwrite its ``graph.yaml`` or write a wrong manifest.
    """
    from charter.packs import load_pack_descriptor
    from kernel.pack_tiers import BUILT_IN
    from ruamel.yaml.error import YAMLError

    descriptor_path = pack_root / "pack.yaml"
    try:
        level = load_pack_descriptor(descriptor_path).pack_level
    except (ValueError, OSError, YAMLError) as exc:  # ValidationError and retired-field errors are ValueErrors
        console.print(f"[red]--pack-root {pack_root} needs a valid pack.yaml declaring pack_level: {BUILT_IN}:[/red] {exc}")
        raise typer.Exit(1) from exc
    if level != BUILT_IN:
        console.print(f"[red]--pack-root only supports built-in-level packs;[/red] {descriptor_path} declares pack_level: {level}")
        raise typer.Exit(1)


def regenerate_graph(
    check: bool = typer.Option(
        False,
        "--check",
        help=(
            "Do not write; regenerate into a temp directory and compare the "
            "per-kind graph fragments against the committed packs/built-in source. "
            "Exit 1 when stale (operator-runnable freshness gate). Exit 0 when "
            "fresh."
        ),
    ),
    pack_root: Annotated[
        Path | None,
        typer.Option(
            "--pack-root",
            help=(
                "Regenerate the DRG fragments and pack manifest for the BUILT-IN-level "
                "pack at this root instead of the shipped built-in pack (e.g. a vendored "
                "copy). The root must carry a pack.yaml declaring pack_level: built-in; "
                "org and project packs are refused. Applies to both the write path and "
                "--check. Defaults to the built-in pack root, leaving the no-flag "
                "behaviour byte-identical."
            ),
        ),
    ] = None,
    json_output: bool = typer.Option(
        False,
        "--json",
        help=_JSON_OPTION_HELP,
    ),
) -> None:
    """Regenerate the shipped DRG graph source deterministically (FR-009).

    Composes the DRG extractor + calibrator into per-populated-node-kind
    ``packs/built-in/*.graph.yaml`` fragments (sharded per mission #2680 WP05;
    relocated from ``src/charter/offering/`` by the pack flatten),
    retiring the legacy ``graph.yaml`` monolith in the same write. Running twice
    on unchanged inputs yields byte-identical fragments. With ``--check`` the
    command never writes: it regenerates into a temp directory and compares the
    fragment set against the committed source, exiting non-zero when stale — the
    operator-facing twin of the freshness gate.

    Both the write path and ``--check`` merge in the enumerable hand-authored
    overlay (:mod:`charter.offering.drg.migration.hand_authored_overlay`) — the
    ``in_tension_with``/``reconciles_tension``/``rejects`` edges and
    ``anti_pattern`` nodes hand-authored directly in the graph fragments
    (mission doctrine-tension-edges-01KY1WPC). The extractor has no
    frontmatter mechanism that could ever mint these, so a bare pure
    regeneration would (a) silently drop them from the committed source on
    write, and (b) always report "stale" under ``--check`` even when nothing
    is actually stale.
    """
    from charter.offering.drg.migration.hand_authored_overlay import (
        write_reference_graph_with_overlay,
    )
    from charter.drg import DRGValidationError
    from charter.packs import builtin_manifest_is_fresh, generate_builtin_manifest

    # FR-013: default (no --pack-root) resolves to the built-in root, keeping the
    # no-flag behaviour byte-identical; an explicit root targets a vendored /
    # out-of-core built-in-level pack for both the write path and --check.
    if pack_root is None:
        resolved_root = _built_in_pack_root()
    else:
        _require_built_in_level(pack_root)
        resolved_root = pack_root

    if check:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            generated_dir = Path(tmp)
            try:
                write_reference_graph_with_overlay(resolved_root, generated_dir / "graph.yaml")
            except DRGValidationError as exc:
                _emit_regen_result(
                    status="invalid",
                    path=resolved_root,
                    json_output=json_output,
                    detail="; ".join(exc.errors),
                )
                raise typer.Exit(1) from exc
            # Freshness covers BOTH the DRG fragments and the generated
            # pack-manifest.yaml — either drifting registers as stale.
            fresh = _read_graph_source(generated_dir) == _read_graph_source(resolved_root) and builtin_manifest_is_fresh(resolved_root)
        _emit_regen_result(
            status="fresh" if fresh else "stale",
            path=resolved_root,
            json_output=json_output,
        )
        raise typer.Exit(0 if fresh else 1)

    try:
        write_reference_graph_with_overlay(resolved_root, resolved_root / "graph.yaml")
    except DRGValidationError as exc:
        _emit_regen_result(
            status="invalid",
            path=resolved_root,
            json_output=json_output,
            detail="; ".join(exc.errors),
        )
        raise typer.Exit(1) from exc

    # Regenerate the built-in pack manifest in the same deterministic pass so
    # the shipped DRG fragments and the constituent inventory never drift apart.
    generate_builtin_manifest(resolved_root)

    _emit_regen_result(status="written", path=resolved_root, json_output=json_output)
    raise typer.Exit(0)


def _read_graph_source(pack_dir: Path) -> dict[str, str]:
    """Return ``{filename: text}`` for the DRG graph source under *pack_dir*.

    Layout-agnostic (mirrors ``load_graph_or_dir``): the ``graph.yaml`` monolith
    when present, otherwise the ``*.graph.yaml`` fragments. Freshness is a
    per-file byte-identity comparison over this mapping (DD-11), so a fragment
    added, removed, or drifted between the temp regeneration and the committed
    source all register as stale.
    """
    single = pack_dir / "graph.yaml"
    files = [single] if single.is_file() else sorted(pack_dir.glob("*.graph.yaml"))
    return {p.name: p.read_text(encoding="utf-8") for p in files}


def _emit_regen_result(
    *,
    status: str,
    path: Path,
    json_output: bool,
    detail: str | None = None,
) -> None:
    """Render the regenerate-graph outcome as JSON or rich text."""
    if json_output:
        payload: dict[str, object] = {"status": status, "path": str(path)}
        if detail is not None:
            payload["detail"] = detail
        console.print_json(json.dumps(payload))
        return

    if status == "written":
        console.print(f"[green]Regenerated DRG graph:[/green] {path}")
    elif status == "fresh":
        console.print(f"[green]DRG graph is fresh:[/green] {path}")
    elif status == "stale":
        console.print(f"[red]DRG graph is stale:[/red] {path}\nRun [bold]spec-kitty charter pack regenerate-graph[/bold] and commit the result.")
    elif status == "invalid":
        console.print(f"[red]DRG graph failed validation:[/red] {detail or '(no detail)'}")


# ----------------------------------------------------------------------
# pack validate
# ----------------------------------------------------------------------
def pack_validate(
    pack_path: Path = typer.Argument(
        ...,
        help="Path to the Charter Pack directory to validate.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=_JSON_OPTION_HELP,
    ),
) -> None:
    """Validate a Charter Pack against schema and DRG constraints.

    Exits 0 when the pack passes validation (advisories do not affect the
    exit code) and 1 when at least one error is reported.
    """
    from charter.packs import render_validation_result, validate_pack_with_org_charter

    result = validate_pack_with_org_charter(pack_path)
    render_validation_result(result, json_output=json_output)
    raise typer.Exit(0 if result.ok else 1)


# ----------------------------------------------------------------------
# pack assemble
# ----------------------------------------------------------------------
def pack_assemble(
    output_path: Path = typer.Argument(
        ...,
        help="Output directory for the assembled distributable pack.",
    ),
    input_packs: list[Path] = typer.Argument(
        ...,
        help="One or more input pack directories to assemble.",
    ),
    conflicts_out: Path | None = typer.Option(
        None,
        "--conflicts-out",
        help="Write the conflict report to this path (JSON).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=("Resolve artifact-id conflicts by last-pack-wins and drop duplicate DRG edges silently."),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=_JSON_OPTION_HELP,
    ),
) -> None:
    """Assemble multiple Charter Packs into a single distributable.

    Exits 0 on success and 1 when conflicts block the merge or when the
    assembled output fails validation.
    """
    from charter.packs import assemble_pack_with_org_charter, render_assembly_result

    result = assemble_pack_with_org_charter(
        input_packs=list(input_packs),
        output_dir=output_path,
        force=force,
        conflicts_out=conflicts_out,
    )
    render_assembly_result(
        result,
        output_dir=output_path,
        input_packs=list(input_packs),
        json_output=json_output,
    )
    raise typer.Exit(0 if result.ok else 1)
