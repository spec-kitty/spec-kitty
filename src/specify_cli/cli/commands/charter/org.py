"""``spec-kitty charter org`` — org pack authoring (``init``, ``validate``).

* ``spec-kitty charter org init <path> [--force] [--template …]
  [--org-name …] [--local-path …] [--branch …]`` — scaffold a minimal org
  pack, or render a full tree from a local/git template.
* ``spec-kitty charter org validate <path>`` — validate an org pack (schema,
  DRG and preset checks); exits non-zero on errors.

``org_app`` is registered under ``charter`` by
:mod:`specify_cli.cli.commands.charter._app` (mission
charter-pack-cutover-01M491G6, FR-006).
"""

from __future__ import annotations

from pathlib import Path

import typer
from kernel.charter_pack_paths import (
    DRG_FRAGMENT,
    ORG_CHARTER_FILENAME,
    pack_drg_fragment,
    pack_org_charter,
)
from specify_cli.cli.console import console

__all__ = ["org_app"]

org_app = typer.Typer(
    name="org",
    help="Manage org-layer doctrine pack authoring (init, validate).",
    no_args_is_help=True,
)


# ----------------------------------------------------------------------
# org init — scaffold a minimal org doctrine pack skeleton (FR-006 / WP08)
# ----------------------------------------------------------------------

#: Minimal ``org-charter.yaml`` body.  All fields are optional in
#: :class:`charter.activation.org_charter.OrgCharterPolicy`; the stub
#: carries the schema_version sentinel and a TODO org_name as a
#: quickstart hint.
_ORG_CHARTER_STUB = """\
schema_version: "2"
org_name: TODO replace with your organisation name
required_directives: []
required_tactics: []
required_paradigms: []
required_styleguides: []
required_toolguides: []
required_procedures: []
required_agent_profiles: []
required_mission_step_contracts: []
governance_policies: []
activations: []
"""

#: Minimal ``drg/fragment.yaml`` stub.  Carries ``# pydantic_model:`` and
#: ``# expect: valid`` frontmatter so the FR-140 contract round-trip gate
#: exercises it automatically.  The ``source_ref`` placeholder is
#: intentionally ``TODO`` — operators replace it with the pack's real path.
_DRG_FRAGMENT_STUB = """\
# pydantic_model: charter.drg.OrgDRGFragment
# expect: valid
pack_name: TODO replace with your pack name
source_kind: local_path
source_ref: .
layer_index: 1
provenance_marker: org
nodes: []
edges: []
"""

#: Minimal ``README.md`` stub.
_ORG_PACK_README_STUB = """\
# Org Doctrine Pack

> Scaffolded by `spec-kitty charter org init`.

## Contents

- `org-charter.yaml` — organisation-level governance policy
- `drg/fragment.yaml` — DRG extension fragment declaring org-tier nodes
- `presets/` — activation presets (`spec-kitty charter activate --preset <name>`)
- Additional artifact subdirectories (e.g. `directives/`, `tactics/`) may
  be added alongside the `org-charter.yaml`.

## Validation

```bash
spec-kitty charter org validate .
```
"""


@org_app.command(name="init")
def org_init(
    pack_path: Path = typer.Argument(
        ...,
        help="Destination directory for the scaffold or rendered doctrine tree.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing pack directory.",
    ),
    template: str | None = typer.Option(
        None,
        "--template",
        help=("Local template directory or git URL (HTTPS/SSH; optional #branch). When omitted, scaffolds the minimal four-file pack."),
    ),
    org_name: str | None = typer.Option(
        None,
        "--org-name",
        help="Validated org/pack identity for {{ORG_NAME}} (required with --template).",
    ),
    local_path: str | None = typer.Option(
        None,
        "--local-path",
        help="Value for {{LOCAL_PATH}} (default: pack). Distinct from PACK_PATH.",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Git ref when --template is a git URL (may also be encoded in TEMPLATE).",
    ),
) -> None:
    """Scaffold a minimal org pack or render from a template.

    Without ``--template``, creates four files under *pack-path*::

        org-charter.yaml     — governance policy stub
        drg/fragment.yaml    — DRG extension stub (with pydantic_model: frontmatter)
        presets/starter.yaml — example activation preset
        README.md            — authoring quickstart

    With ``--template``, copies the full template tree (minus ``.templateignore``),
    substitutes ``{{ORG_NAME}}`` / ``{{LOCAL_PATH}}``, and writes under *pack-path*.

    Refuses to overwrite an existing directory unless ``--force`` is passed.
    """
    if template is not None:
        _run_template_render(
            pack_path=pack_path,
            template=template,
            org_name=org_name,
            local_path=local_path,
            branch=branch,
            force=force,
        )
        return
    _run_minimal_scaffold(pack_path, force=force)


def _run_minimal_scaffold(pack_path: Path, *, force: bool) -> None:
    """Write the minimal org pack skeleton (charter, fragment, example preset, README)."""
    from charter.packs import write_example_preset

    if pack_path.exists() and not force:
        console.print(f"[red]Target directory already exists:[/red] {pack_path}\nPass [bold]--force[/bold] to overwrite.")
        raise typer.Exit(1)

    pack_path.mkdir(parents=True, exist_ok=True)
    fragment_path = pack_drg_fragment(pack_path)
    fragment_path.parent.mkdir(parents=True, exist_ok=True)

    pack_org_charter(pack_path).write_text(_ORG_CHARTER_STUB, encoding="utf-8")
    fragment_path.write_text(_DRG_FRAGMENT_STUB, encoding="utf-8")
    preset_path = write_example_preset(pack_path)
    (pack_path / "README.md").write_text(_ORG_PACK_README_STUB, encoding="utf-8")

    console.print(f"[green]Org pack scaffolded at:[/green] {pack_path}")
    console.print(f"  {ORG_CHARTER_FILENAME}")
    console.print(f"  {DRG_FRAGMENT.as_posix()}")
    console.print(f"  {preset_path.relative_to(pack_path).as_posix()}")
    console.print("  README.md")
    console.print(f"\nRun [bold]spec-kitty charter org validate {pack_path}[/bold] to confirm.")


def _run_template_render(
    *,
    pack_path: Path,
    template: str,
    org_name: str | None,
    local_path: str | None,
    branch: str | None,
    force: bool,
) -> None:
    """Dispatch template render via ``template_render.pipeline``."""
    from specify_cli.charter_packs.template_render import RenderRequest
    from specify_cli.charter_packs.template_render.pipeline import render_org_pack

    if not org_name:
        console.print("[red]ORG_NAME is required when --template is set[/red] (org_name.required).")
        raise typer.Exit(1)

    err = render_org_pack(
        RenderRequest(
            pack_path=pack_path,
            template=template,
            org_name=org_name,
            local_path=local_path,
            branch=branch,
            force=force,
        )
    )
    if err is not None:
        console.print(f"[red]{err.message}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Org doctrine rendered at:[/green] {pack_path}")
    console.print("  Full template tree written (minus .templateignore); ORG_NAME / LOCAL_PATH tokens substituted.")
    console.print(f"\nRun [bold]spec-kitty charter org validate {pack_path}/pack[/bold] or your template's quality-check if applicable.")


# ----------------------------------------------------------------------
# org validate — validate an org pack against WP06 schema (FR-006 / WP08)
# ----------------------------------------------------------------------


@org_app.command(name="validate")
def org_validate(
    pack_path: Path = typer.Argument(
        ...,
        help="Path to the org doctrine pack directory to validate.",
    ),
) -> None:
    """Validate an org doctrine pack using schema and DRG checks (FR-006).

    Calls the WP06 :func:`charter.offering.packs.pack_validator.validate_pack`
    loader.  Prints per-file findings with file paths.  Exits non-zero when
    at least one error is found.

    Org fragments use id and plural kind (for example, directives) for nodes.
    Validation uses the runtime loader, which supplies pack provenance fields.
    """
    from charter.packs import render_validation_result, validate_pack_with_org_charter

    # Written explicitly (not relying on validate_pack's own default) so a
    # future default change cannot silently alter org_validate's behaviour
    # without a visible diff here. No carve-out: org_init's scaffold never
    # produces the drg-root-graph-missing shape, so this call was never
    # protected by a carve-out in the first place (operator ruling #2,
    # reviews/plan.ruling.md).
    result = validate_pack_with_org_charter(pack_path, check_drg_root=True)

    render_validation_result(result, json_output=False)
    raise typer.Exit(0 if result.ok else 1)
