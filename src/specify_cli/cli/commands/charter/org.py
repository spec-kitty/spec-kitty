"""``spec-kitty charter org`` — org pack authoring and project registration.

* ``spec-kitty charter org init <path> [--force] [--template …]
  [--org-name …] [--local-path …] [--branch …]`` — scaffold a minimal org
  pack, or render a full tree from a local/git template.
* ``spec-kitty charter org validate <path>`` — validate an org pack (schema,
  DRG and preset checks); exits non-zero on errors.
* ``spec-kitty charter org add <name> --local-path <dir> [--url <url>]
  [--ref <ref>] [--source-type …] [--subdir <dir>] [--force] [--json]`` —
  register the pack with this project (#6267): validates it exactly as
  ``org validate`` does, then writes one ``charter_packs.org.packs[]`` entry
  through the registry's own write seam, so nothing hand-edits
  ``.kittify/config.yaml``.
* ``spec-kitty charter org remove <name> [--json]`` — retire a registration.
  Config only: the pack directory is never deleted.

``org_app`` is registered under ``charter`` by
:mod:`specify_cli.cli.commands.charter._app` (mission
charter-pack-cutover-01M491G6, FR-006).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import typer
from kernel.charter_pack_paths import (
    DRG_FRAGMENT,
    ORG_CHARTER_FILENAME,
    pack_drg_fragment,
    pack_org_charter,
)
from specify_cli.cli.commands.charter._coded_errors import render_coded_error
from specify_cli.cli.console import console

if TYPE_CHECKING:  # pragma: no cover - typing only; keeps --help free of the registry stack
    from pydantic import ValidationError

    from charter.offering.drg.org_pack_config import OrgPackConfig, PackRegistry

__all__ = ["org_app"]

org_app = typer.Typer(
    name="org",
    help="Manage org Charter Pack authoring (init, validate) and registration (add, remove).",
    no_args_is_help=True,
)

#: Coded refusals for ``org add`` / ``org remove`` (#6267); rendered by the
#: shared :func:`render_coded_error` so text and ``--json`` agree.
ORG_PACK_INVALID = "ORG_PACK_INVALID"
ORG_PACK_EXISTS = "ORG_PACK_EXISTS"
ORG_PACK_NOT_FOUND = "ORG_PACK_NOT_FOUND"
ORG_PACK_UNREADABLE = "ORG_PACK_UNREADABLE"

#: ``OrgPackConfig.source_type``'s accepted values (C-001: the model's own set).
_SOURCE_TYPES = ("git", "https", "artifactory", "api")
#: Names the offering resolves by tier; an org pack may not shadow them.
_RESERVED_PACK_NAMES = ("built-in", "project")


def _refuse(
    code: str,
    message: str,
    *,
    json_output: bool,
    details: list[str] | None = None,
    payload: dict[str, object] | None = None,
) -> NoReturn:
    """Render a coded refusal and exit 1 (nothing has been written at any call site)."""
    render_coded_error(code, message, details=details, payload=payload, json_output=json_output)
    raise typer.Exit(1)


def _project_root(json_output: bool) -> Path:
    """Resolve the project root, refusing outside a spec-kitty project."""
    from specify_cli.core.paths import locate_project_root

    repo_root = locate_project_root()
    if repo_root is None:
        _refuse(
            ORG_PACK_INVALID,
            "could not locate a spec-kitty project root; run this from inside a project containing .kittify/",
            json_output=json_output,
        )
    return repo_root


def _validation_details(result: object) -> list[str]:
    """Flatten a ``ValidationResult``'s errors into one-line refusal details."""
    errors = getattr(result, "errors", ())
    return [f"{issue.file}: {issue.message}" for issue in errors]


def _read_registry(repo_root: Path, *, json_output: bool) -> PackRegistry:
    """Read the org-pack registry strictly, refusing a config it could not parse."""
    from charter.drg import load_pack_registry

    try:
        return load_pack_registry(repo_root, strict=True)
    except ValueError as exc:
        _refuse(
            ORG_PACK_UNREADABLE,
            f"the org pack registry in {repo_root / '.kittify' / 'config.yaml'} cannot be read, so it will not be rewritten: {exc}",
            json_output=json_output,
        )


# ----------------------------------------------------------------------
# org init — scaffold a minimal org Charter Pack skeleton (FR-006 / WP08)
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
# Org Charter Pack

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
        help="Destination directory for the scaffold or rendered charter pack tree.",
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
        help="Path to the org Charter Pack directory to validate.",
    ),
) -> None:
    """Validate an org Charter Pack using schema and DRG checks (FR-006).

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


# ----------------------------------------------------------------------
# org add — register an org Charter Pack with this project (#6267)
# ----------------------------------------------------------------------


@org_app.command(name="add")
def org_add(
    name: str = typer.Argument(..., help="Name to register the pack under."),
    local_path: str = typer.Option(
        ...,
        "--local-path",
        help=(
            "Pack root: relative to the project root, absolute, ~-prefixed, or a ${VAR} template "
            "(tokens are never expanded or frozen; redundant ./ and trailing separators are normalised). "
            "May be absent when --url is given."
        ),
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        help="Remote source URL. Registers the pack for `charter fetch` instead of requiring a local pack.",
    ),
    ref: str | None = typer.Option(None, "--ref", help="Git ref to fetch (requires --url)."),
    source_type: str | None = typer.Option(
        None,
        "--source-type",
        help="Remote source type: git|https|artifactory|api (requires --url; defaults to git).",
    ),
    subdir: str | None = typer.Option(
        None,
        "--subdir",
        help="Subdirectory of the pack root that holds the doctrine artifacts.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace an existing registration of the same name (declaration order is kept).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Register an org Charter Pack with this project (#6267).

    Validates the pack exactly as ``spec-kitty charter org validate`` does, then
    writes one ``charter_packs.org.packs[]`` entry through the registry's own
    write seam -- the operator never hand-edits ``.kittify/config.yaml``.

    Every refusal exits 1 and leaves the config byte-identical. With ``--url``
    the pack root may be absent: it is then registered for
    ``spec-kitty charter fetch`` rather than validated. Nothing here touches the
    network.
    """
    from charter.drg import register_org_pack

    pack = _add_entry(
        name=name,
        local_path=local_path,
        url=url,
        ref=ref,
        source_type=source_type,
        subdir=subdir,
        json_output=json_output,
    )

    repo_root = _project_root(json_output)
    config_path = repo_root / ".kittify" / "config.yaml"
    registry = _read_registry(repo_root, json_output=json_output)
    existing = registry.get(pack.name)
    if existing is not None and not force:
        _refuse(
            ORG_PACK_EXISTS,
            f"org pack {pack.name!r} is already registered in {config_path}",
            json_output=json_output,
            details=["Pass --force to replace it, or run `spec-kitty charter org remove` first."],
            payload={"pack": pack.name, "config": str(config_path)},
        )

    validated = _checked_pack_root(pack, repo_root=repo_root, local_path=local_path, json_output=json_output)

    # -- the write --------------------------------------------------------
    try:
        replaced = register_org_pack(repo_root, pack, replace=existing is not None)
    except (ValueError, OSError) as exc:
        # A strict-read or write failure inside the seam is still a refusal, not
        # a traceback (NFR-004); the seam's own atomic write leaves the file as
        # it found it.
        _refuse(
            ORG_PACK_UNREADABLE,
            f"could not register org pack {pack.name!r} in {config_path}: {exc}",
            json_output=json_output,
            payload={"pack": pack.name, "config": str(config_path)},
        )
    payload = {
        "pack": _pack_payload(pack),
        "config": str(config_path),
        "replaced": replaced,
        "validated": validated,
        # add never fetches; the key exists so callers need no special case.
        "fetched": False,
    }
    if json_output:
        console.emit_json(payload)
        return
    verb = "Replaced" if replaced else "Registered"
    console.print(f"[green]{verb} org pack '{pack.name}'[/green] in {config_path}")
    console.print(f"  local_path: {local_path}")
    if not validated:
        console.print(f"Run [bold]spec-kitty charter fetch {pack.name}[/bold] to materialize it into that directory.")
    else:
        console.print(f"Run [bold]spec-kitty charter pack list[/bold] to confirm, or [bold]spec-kitty charter org remove {pack.name}[/bold] to retire it.")


def _add_entry(
    *,
    name: str,
    local_path: str,
    url: str | None,
    ref: str | None,
    source_type: str | None,
    subdir: str | None,
    json_output: bool,
) -> OrgPackConfig:
    """Every cheap ``org add`` refusal, then the ``OrgPackConfig`` to write.

    All checks here happen before any filesystem write, so a refusal cannot
    leave the config touched.
    """
    from typing import cast

    from pydantic import ValidationError

    from charter.offering.drg.org_pack_config import OrgPackConfig, SourceType

    if not name or not name.strip():
        _refuse(ORG_PACK_INVALID, "a pack name is required (it cannot be blank or whitespace only)", json_output=json_output)
    if name != name.strip():
        _refuse(ORG_PACK_INVALID, f"pack name {name!r} has leading or trailing whitespace", json_output=json_output)
    if name in _RESERVED_PACK_NAMES:
        _refuse(
            ORG_PACK_INVALID,
            f"pack name {name!r} is reserved (the {', '.join(_RESERVED_PACK_NAMES)} tiers are not org packs)",
            json_output=json_output,
        )
    if not local_path.strip():
        _refuse(ORG_PACK_INVALID, "--local-path is required and cannot be blank", json_output=json_output)
    if url is None and (ref is not None or source_type is not None):
        missing = "--ref" if ref is not None else "--source-type"
        _refuse(ORG_PACK_INVALID, f"{missing} requires --url (a local pack has no remote ref or source type)", json_output=json_output)
    if source_type is not None and source_type not in _SOURCE_TYPES:
        _refuse(
            ORG_PACK_INVALID,
            f"--source-type {source_type!r} is not one of: {', '.join(_SOURCE_TYPES)}",
            json_output=json_output,
        )

    # `_SOURCE_TYPES` above proves membership, so the cast adds no new claim;
    # it just says the checked value is the model's own literal union.
    resolved_source_type = source_type if source_type is not None else ("git" if url is not None else None)

    try:
        return OrgPackConfig(
            name=name,
            local_path=Path(local_path),
            subdir=subdir,
            source_type=cast("SourceType", resolved_source_type) if resolved_source_type is not None else None,
            url=url,
            ref=ref,
        )
    except ValidationError as exc:
        _refuse(ORG_PACK_INVALID, f"invalid org pack entry: {_pydantic_message(exc)}", json_output=json_output)


def _checked_pack_root(pack: OrgPackConfig, *, repo_root: Path, local_path: str, json_output: bool) -> bool:
    """Validate the pack at its effective root; return whether it was validated.

    An existing root is validated through the same door ``charter org validate``
    uses. Without ``--url`` a missing root is a refusal (nothing could ever
    materialize it); with ``--url`` it is fine and the caller prints the
    ``charter fetch`` follow-up.
    """
    from charter.drg import OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError

    try:
        pack_root = pack.effective_root(repo_root)
    except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError) as exc:
        # Both are bad *input* (an unset token, a subdir that escapes through a
        # symlink), so both are refusals rather than tracebacks (NFR-004).
        _refuse(ORG_PACK_INVALID, str(exc), json_output=json_output)
    if pack_root.is_file():
        _refuse(
            ORG_PACK_INVALID,
            f"--local-path {local_path!r} is a regular file, not a directory",
            json_output=json_output,
            payload={"pack": pack.name, "local_path": local_path},
        )
    if not pack_root.is_dir():
        if pack.url is not None:
            return False
        _refuse(
            ORG_PACK_INVALID,
            f"pack root {pack_root} does not exist",
            json_output=json_output,
            details=["Create the pack there, fix --local-path, or pass --url for a pack `charter fetch` should materialize."],
            payload={"pack": pack.name, "local_path": local_path},
        )

    from charter.packs import validate_pack_with_org_charter

    result = validate_pack_with_org_charter(pack_root, check_drg_root=True)
    if not result.ok:
        details = _validation_details(result)
        _refuse(
            ORG_PACK_INVALID,
            f"org pack {pack.name!r} failed validation; nothing was registered",
            json_output=json_output,
            details=details,
            payload={"pack": pack.name, "local_path": local_path, "errors": details},
        )
    return True


def _field_path(error: object) -> str:
    """Render a pydantic error's ``loc`` as a dotted field path."""
    loc = getattr(error, "loc", ())
    return ".".join(str(part) for part in loc) or "(entry)"


def _pydantic_message(exc: ValidationError) -> str:
    """One-line summary of a ``ValidationError`` (field path + message per error)."""
    errors = exc.errors()
    return "; ".join(f"{_field_path(err)}: {err['msg']}" for err in errors)


def _pack_payload(pack: OrgPackConfig) -> dict[str, object]:
    """The written entry as JSON-ready data (``OrgPackConfig``'s declared fields only)."""
    payload: dict[str, object] = {"name": pack.name, "local_path": str(pack.local_path)}
    for field in ("subdir", "source_type", "url", "ref"):
        value = getattr(pack, field)
        if value is not None:
            payload[field] = value
    return payload


# ----------------------------------------------------------------------
# org remove — retire a registration
# ----------------------------------------------------------------------


@org_app.command(name="remove")
def org_remove(
    name: str = typer.Argument(..., help="Name of the registered pack to retire."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Retire an org Charter Pack registration (#6267).

    Deletes exactly that ``charter_packs.org.packs[]`` entry; every other key,
    comment and pack in ``.kittify/config.yaml`` is left alone. The pack
    directory is never deleted -- the command prints where it stays (C-003).
    An unknown name exits 1 listing the configured names; the config is then
    byte-identical.
    """
    from charter.drg import unregister_org_pack

    repo_root = _project_root(json_output)
    config_path = repo_root / ".kittify" / "config.yaml"
    registry = _read_registry(repo_root, json_output=json_output)
    if registry.get(name) is None:
        configured = registry.names()
        _refuse(
            ORG_PACK_NOT_FOUND,
            f"org pack {name!r} is not registered in {config_path}",
            json_output=json_output,
            details=[f"Configured packs: {', '.join(configured) or '(none)'}"],
            payload={"pack": name, "config": str(config_path), "configured": list(configured)},
        )

    try:
        removed = unregister_org_pack(repo_root, name)
    except (ValueError, OSError) as exc:
        # Same refusal surface as add's write: a seam failure is not a traceback,
        # and the seam's atomic write leaves the config as it found it.
        _refuse(ORG_PACK_UNREADABLE, str(exc), json_output=json_output, payload={"pack": name, "config": str(config_path)})

    try:
        pack_root = str(removed.effective_root(repo_root))
    except ValueError:
        # An unset ${VAR}/~ token (or an escaping subdir) only means the printed
        # directory cannot be resolved; the raw stored value is what stays.
        pack_root = str(removed.local_path)
    payload = {"removed": removed.name, "config": str(config_path), "pack_root": pack_root}
    if json_output:
        console.emit_json(payload)
        return
    console.print(f"[green]Removed org pack '{removed.name}'[/green] from {config_path}")
    console.print(f"  The pack directory is left in place: {pack_root}")
