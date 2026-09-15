"""``spec-kitty doctrine`` command group.

Surface area:

* ``spec-kitty doctrine fetch [--pack <name>] [--dry-run]`` — fetch one or
  all configured org doctrine packs into their local snapshot directories.
* ``spec-kitty doctrine regenerate-graph [--check] [--json]`` — deterministically
  regenerate the shipped DRG from the built-in doctrine tree as per-kind
  ``packs/built-in/*.graph.yaml`` fragments (FR-009 / WP09; sharded per mission
  #2680 WP05). ``--check`` compares without writing and exits non-zero when the
  committed graph source is stale.
* ``spec-kitty doctrine pack validate <pack-path> [--json]`` — validate a
  doctrine pack against the artifact / DRG / org-charter contracts.
* ``spec-kitty doctrine pack assemble <out> <inputs...> [--force]
  [--conflicts-out FILE] [--json]`` — assemble multiple input packs into a
  single distributable output pack.
* ``spec-kitty doctrine new <kind> <id> [--pack <path>]`` — scaffold a stub
  project-layer (or pack-layer) artifact YAML pre-filled with the canonical
  schema's required fields (FR-016).
* ``spec-kitty doctrine validate <path>`` — validate a single project-layer
  artifact file or a doctrine tree against the artifact schemas (FR-017).
* ``spec-kitty doctrine org init <path> [--force] [--template …]
  [--org-name …] [--local-path …] [--branch …]`` — scaffold a minimal org
  doctrine pack, or render a full tree from a local/git template for operators
  creating their own doctrine (FR-006 / WP08 + template render).
* ``spec-kitty doctrine org validate <path>`` — validate an org doctrine pack
  using the WP06 loader and schema checks; exits non-zero on errors (FR-006 /
  WP08).
* ``spec-kitty doctrine mission-type list [--json]`` — list all mission types
  visible in the doctrine layer (built-in + org + project) regardless of
  activation state (FR-013 / WP13).

Both ``pack validate`` and ``pack assemble`` are implemented by WP06; their
heavy lifting lives in :mod:`specify_cli.doctrine.pack_validator` and
:mod:`specify_cli.doctrine.pack_assembler` so this module only handles
argument parsing and exit-code mapping. ``new`` and ``validate`` are owned
by WP09 (Mission B) and reuse the same schema registry from
:mod:`specify_cli.doctrine.pack_validator`.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from charter.drg import ArtifactKind
from charter.activation.kind_vocabulary import PROJECT_KIND_DIRS
from specify_cli.cli.commands._doctrine_asset import asset_app
from specify_cli.cli.console import console
from rich.table import Table

__all__ = ["app"]

_JSON_OPTION_HELP = "Emit machine-readable JSON instead of rich text."

#: CR-02 (mission ``charter-code-topology-01M152G1`` S4): the deprecation
#: notice printed once per invocation of the ``spec-kitty doctrine`` group
#: (any subcommand). Unlike the CR-01/CR-03/CR-04/CR-07 config/URN-reader
#: shims -- which warn-once *per process* because a hot read path may call
#: the same function many times in one invocation -- a CLI group's own
#: ``@app.callback()`` fires at most once per process by construction (typer
#: invokes it a single time before dispatching to exactly one subcommand),
#: so no additional de-dup gate is needed here.
_DEPRECATION_NOTICE = (
    "`spec-kitty doctrine` is deprecated; use `spec-kitty charter` instead "
    "(mission charter-code-topology-01M152G1, CR-02). This command still "
    "works and delegates to the same implementation. "
    "The following commands remain under `spec-kitty doctrine`: "
    "regenerate-graph, pack validate, pack assemble, asset, and mission-type list "
    "(all visible types; charter mission-type list shows activated types)."
)


app = typer.Typer(
    name="doctrine",
    help="[DEPRECATED — use `spec-kitty charter`] Manage org-layer doctrine packs (fetch, validate, assemble).",
    no_args_is_help=True,
)


@app.callback()
def _deprecation_warning() -> None:
    """CR-02: emit a one-shot stderr deprecation notice, then delegate.

    Typer/Click always runs a Typer app's own ``@app.callback()`` before
    dispatching to whichever subcommand the operator invoked, so this fires
    for every ``spec-kitty doctrine <anything>`` invocation -- the "callback
    that emits a one-shot stderr deprecation then delegates" CR-02 asks for.
    Prints (not raises): the legacy group must keep working exactly as
    before, it only gains a warning banner.
    """
    typer.secho(_DEPRECATION_NOTICE, fg=typer.colors.YELLOW, err=True)

pack_app = typer.Typer(
    name="pack",
    help="Validate or assemble doctrine packs.",
    no_args_is_help=True,
)
app.add_typer(pack_app, name="pack")

org_app = typer.Typer(
    name="org",
    help="Manage org-layer doctrine pack authoring (init, validate).",
    no_args_is_help=True,
)
app.add_typer(org_app, name="org")

mission_type_app = typer.Typer(
    name="mission-type",
    help="Mission type commands.",
    no_args_is_help=True,
)
app.add_typer(mission_type_app, name="mission-type")

# WP05 — asset operator surface. Read-only ``asset list`` / ``asset path``
# commands resolve shipped and overlay doctrine assets through
# ``DoctrineService.assets`` (no install — C-002). ``asset_app`` is imported at
# the top of the module; registered here at the WP03 anchor.
app.add_typer(asset_app, name="asset")


# ----------------------------------------------------------------------
# fetch
# ----------------------------------------------------------------------
@app.command(name="fetch")
def fetch(
    pack_name: str | None = typer.Option(
        None,
        "--pack",
        help="Fetch only the named pack (default: fetch all configured packs).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be fetched without contacting any remote.",
    ),
) -> None:
    """Fetch org doctrine pack(s) from their configured remote sources."""
    from charter.drg import load_pack_registry
    from specify_cli.core.paths import locate_project_root
    from specify_cli.doctrine.snapshot import fetch_pack

    repo_root = locate_project_root()
    if repo_root is None:
        console.print(
            "[red]Could not locate spec-kitty project root.[/red] "
            "Run from inside a project containing .kittify/."
        )
        raise typer.Exit(1)

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        console.print("[red]No org doctrine packs configured.[/red]")
        console.print(
            "Add a [bold]doctrine.org.packs[/bold] block to "
            ".kittify/config.yaml. See the contract at "
            "kitty-specs/layered-doctrine-org-layer-*/contracts/config-schema.yaml."
        )
        raise typer.Exit(1)

    target_packs = list(registry.packs)
    if pack_name is not None:
        target_packs = [p for p in registry.packs if p.name == pack_name]
        if not target_packs:
            names = ", ".join(registry.names()) or "(none)"
            console.print(
                f"[red]Pack '{pack_name}' not found.[/red] "
                f"Configured packs: {names}"
            )
            raise typer.Exit(1)

    if dry_run:
        from charter.drg import OrgPackEnvVarUnsetError

        for pack in target_packs:
            origin = pack.url or str(pack.local_path)
            try:
                target = pack.local_path_root(repo_root)
            except OrgPackEnvVarUnsetError as exc:
                console.print(
                    f"Would fetch pack '[bold]{pack.name}[/bold]' from {origin} "
                    f"— [red]cannot resolve target: {exc}[/red]"
                )
                continue
            console.print(
                f"Would fetch pack '[bold]{pack.name}[/bold]' from {origin} "
                f"into {target}"
            )
        return

    any_failed = False
    for pack in target_packs:
        result = fetch_pack(pack, repo_root)
        if result.ok:
            suffix = " (unchanged)" if result.unchanged else ""
            console.print(
                f"[green]Pack '{pack.name}': {result.artifacts_written} "
                f"artifacts{suffix}[/green]"
            )
            if result.pack_version:
                console.print(f"  Version: {result.pack_version}")
        else:
            console.print(f"[red]Pack '{pack.name}' failed:[/red]")
            for err in result.errors:
                console.print(f"  {err}")
            any_failed = True

    if any_failed:
        raise typer.Exit(1)


# ----------------------------------------------------------------------
# regenerate-graph — deterministic DRG regeneration (FR-009 / WP09 T026)
# ----------------------------------------------------------------------
def _doctrine_root() -> Path:
    """Return the built-in pack root that owns the shipped DRG graph source.

    Post-flatten (relocate-builtin-doctrine-packs, WP03) the built-in artifact
    content and the sharded ``*.graph.yaml`` fragments live in
    ``packs/built-in/`` — no longer under ``src/charter/offering/<kind>/built-in``. This
    root is both the extractor's artifact input *and* the fragment write-target /
    freshness read source; the extractor resolves ``missions/`` (which did NOT
    move) internally.

    Routes through :func:`charter.offering.pack_paths.built_in_root` (C1.6), the single
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
    ``src/doctrine`` this module loads from) resolves identically either way.
    """
    from charter.pack_paths import built_in_root

    root: Path = built_in_root()
    return root


@app.command(name="regenerate-graph")
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
    from specify_cli.doctrine.builtin_manifest import (
        builtin_manifest_is_fresh,
        generate_builtin_manifest,
    )

    doctrine_root = _doctrine_root()

    if check:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            generated_dir = Path(tmp)
            try:
                write_reference_graph_with_overlay(doctrine_root, generated_dir / "graph.yaml")
            except DRGValidationError as exc:
                _emit_regen_result(
                    status="invalid",
                    path=doctrine_root,
                    json_output=json_output,
                    detail="; ".join(exc.errors),
                )
                raise typer.Exit(1) from exc
            # Freshness covers BOTH the DRG fragments and the generated
            # pack-manifest.yaml — either drifting registers as stale.
            fresh = _read_graph_source(generated_dir) == _read_graph_source(
                doctrine_root
            ) and builtin_manifest_is_fresh(doctrine_root)
        _emit_regen_result(
            status="fresh" if fresh else "stale",
            path=doctrine_root,
            json_output=json_output,
        )
        raise typer.Exit(0 if fresh else 1)

    try:
        write_reference_graph_with_overlay(doctrine_root, doctrine_root / "graph.yaml")
    except DRGValidationError as exc:
        _emit_regen_result(
            status="invalid",
            path=doctrine_root,
            json_output=json_output,
            detail="; ".join(exc.errors),
        )
        raise typer.Exit(1) from exc

    # Regenerate the built-in pack manifest in the same deterministic pass so
    # the shipped DRG fragments and the constituent inventory never drift apart.
    generate_builtin_manifest(doctrine_root)

    _emit_regen_result(status="written", path=doctrine_root, json_output=json_output)
    raise typer.Exit(0)


def _read_graph_source(doctrine_dir: Path) -> dict[str, str]:
    """Return ``{filename: text}`` for the DRG graph source under *doctrine_dir*.

    Layout-agnostic (mirrors ``load_graph_or_dir``): the ``graph.yaml`` monolith
    when present, otherwise the ``*.graph.yaml`` fragments. Freshness is a
    per-file byte-identity comparison over this mapping (DD-11), so a fragment
    added, removed, or drifted between the temp regeneration and the committed
    source all register as stale.
    """
    single = doctrine_dir / "graph.yaml"
    files = (
        [single]
        if single.is_file()
        else sorted(doctrine_dir.glob("*.graph.yaml"))
    )
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
        console.print(
            f"[red]DRG graph is stale:[/red] {path}\n"
            "Run [bold]spec-kitty doctrine regenerate-graph[/bold] and commit the result."
        )
    elif status == "invalid":
        console.print(
            f"[red]DRG graph failed validation:[/red] {detail or '(no detail)'}"
        )


# ----------------------------------------------------------------------
# pack validate
# ----------------------------------------------------------------------
@pack_app.command(name="validate")
def pack_validate(
    pack_path: Path = typer.Argument(
        ...,
        help="Path to the doctrine pack directory to validate.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=_JSON_OPTION_HELP,
    ),
) -> None:
    """Validate a doctrine pack against schema and DRG constraints.

    Exits 0 when the pack passes validation (advisories do not affect the
    exit code) and 1 when at least one error is reported.
    """
    from specify_cli.doctrine.pack_validator import (
        render_validation_result,
        validate_pack,
    )

    result = validate_pack(pack_path)
    render_validation_result(result, json_output=json_output)
    raise typer.Exit(0 if result.ok else 1)


# ----------------------------------------------------------------------
# pack assemble
# ----------------------------------------------------------------------
@pack_app.command(name="assemble")
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
        help=(
            "Resolve artifact-id conflicts by last-pack-wins and drop "
            "duplicate DRG edges silently."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=_JSON_OPTION_HELP,
    ),
) -> None:
    """Assemble multiple doctrine packs into a single distributable.

    Exits 0 on success and 1 when conflicts block the merge or when the
    assembled output fails validation.
    """
    from specify_cli.doctrine.pack_assembler import (
        assemble_pack,
        render_assembly_result,
    )

    result = assemble_pack(
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


# ----------------------------------------------------------------------
# new — scaffold a stub artifact (FR-016 / WP09 T048)
# ----------------------------------------------------------------------

#: Per-kind stub bodies (T016).  Each value is a ``str.format``-ready YAML
#: template whose ``{artifact_id}`` placeholder the scaffolder substitutes; the
#: rendered stub is the *minimum* payload that passes the corresponding Pydantic
#: schema in ``src/charter/offering/*/models.py`` (or ``AssetManifest``).  The scaffolder
#: validates the rendered stub against the schema before writing — a future
#: schema tightening surfaces at the next ``doctrine new`` rather than silently
#: scaffolding an invalid file.
#:
#: This is a ``dict[ArtifactKind, str]`` (not an eight-arm ``if``-chain) so the
#: kind projection is a table the kind-mapping totality guard can see. It is a
#: deliberately **partial** table — ``template`` (empty glob, unscaffoldable),
#: ``glossary_pack`` and ``anti_pattern`` (hand-authored) carry no stub — read
#: only through the membership gate in :func:`new`, so it is carried as an
#: allow-listed ``.get``/membership partial in the guard's
#: ``_EXEMPT_GET_PARTIALS`` with that reason. The set of keys is exactly the
#: kinds ``doctrine new`` supports.
_STUB_TEMPLATES: dict[ArtifactKind, str] = {
    # Directive: id must match [A-Z][A-Z0-9_-]*; intent + title required.
    ArtifactKind.DIRECTIVE: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "title: TODO short title\n"
        "intent: TODO why this directive exists\n"
        "enforcement: advisory\n"
    ),
    # Tactic: needs at least one step.
    ArtifactKind.TACTIC: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "name: TODO short name\n"
        "purpose: TODO when to apply this tactic\n"
        "steps:\n"
        "  - title: TODO first step\n"
        "    description: TODO what the step does\n"
    ),
    # Styleguide: needs at least one principle (min_length=1).
    ArtifactKind.STYLEGUIDE: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "title: TODO short title\n"
        "scope: code\n"
        "principles:\n"
        "  - TODO first principle\n"
        "applies_to_languages: []\n"
    ),
    # Toolguide: guide_path must match ^src/charter/offering/.+\.md$.
    ArtifactKind.TOOLGUIDE: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "tool: TODO tool name\n"
        "title: TODO short title\n"
        "guide_path: src/charter/offering/toolguides/{artifact_id}.md\n"
        "summary: TODO one-line summary\n"
    ),
    ArtifactKind.PARADIGM: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "name: TODO short name\n"
        "summary: TODO one-line summary of the paradigm\n"
    ),
    # Procedure: name + purpose + entry/exit + min 1 step.
    ArtifactKind.PROCEDURE: (
        'schema_version: "1.0"\n'
        "id: {artifact_id}\n"
        "name: TODO short name\n"
        "purpose: TODO why this procedure exists\n"
        "entry_condition: TODO when to enter\n"
        "exit_condition: TODO when complete\n"
        "steps:\n"
        "  - title: TODO first step\n"
    ),
    # AgentProfile uses hyphenated YAML aliases (profile-id, schema-version,
    # specialization → {primary-focus, ...}). The model requires roles
    # (min_length=1), purpose, and a Specialization with primary-focus.
    ArtifactKind.AGENT_PROFILE: (
        'schema-version: "1.0"\n'
        "profile-id: {artifact_id}\n"
        "name: TODO agent display name\n"
        "roles: [implementer]\n"
        "purpose: TODO one-line purpose statement\n"
        "specialization:\n"
        "  primary-focus: TODO primary focus area\n"
    ),
    ArtifactKind.MISSION_STEP_CONTRACT: (
        "id: {artifact_id}\n"
        'schema_version: "1.0"\n'
        "action: TODO action verb\n"
        "mission: TODO mission slug\n"
        "steps:\n"
        "  - id: step-1\n"
        "    description: TODO step description\n"
    ),
    # Asset: loose-contract sidecar manifest (AssetManifest, extra=forbid) —
    # required id/mime/path, optional title, and NO schema_version field.
    ArtifactKind.ASSET: (
        "id: {artifact_id}\n"
        "mime: text/plain\n"
        "path: TODO-relative-path-under-assets.txt\n"
        "title: TODO asset display name\n"
    ),
}


def _artifact_filename(kind: ArtifactKind, artifact_id: str) -> str:
    """Return the canonical filename for a doctrine artifact."""
    glob_pattern = kind.glob_pattern
    if not glob_pattern.startswith("*"):
        raise ValueError(f"Unsupported artifact kind: {kind.value}")
    return f"{artifact_id}{glob_pattern.removeprefix('*')}"


def _stub_template(kind: ArtifactKind, artifact_id: str) -> str:
    """Return the canonical YAML stub for ``kind`` populated with ``artifact_id``."""
    return _STUB_TEMPLATES[kind].format(artifact_id=artifact_id)


def _resolve_scaffoldable_kind(raw_kind: str) -> ArtifactKind:
    """Resolve an operator kind token to a scaffoldable :class:`ArtifactKind`.

    The set of scaffoldable kinds is exactly ``_STUB_TEMPLATES``' keys —
    ``template``/``glossary_pack``/``anti_pattern`` are not hand-scaffolded.
    Exits 2 (with the valid-kinds list) for an unknown or unscaffoldable token.
    """
    normalized = raw_kind.strip().lower()
    try:
        kind: ArtifactKind | None = ArtifactKind(normalized)
    except ValueError:
        kind = None
    if kind is None or kind not in _STUB_TEMPLATES:
        valid = ", ".join(sorted(member.value for member in _STUB_TEMPLATES))
        console.print(
            f"[red]Unknown artifact kind '{raw_kind}'.[/red] "
            f"Expected one of: {valid}."
        )
        raise typer.Exit(2)
    return kind


def _resolve_scaffold_root(
    repo_root: Path | None,
    pack: Path | None,
) -> Path:
    """Return the doctrine root that scaffolded files should land under.

    Project-layer scaffolding (no ``--pack``) writes under
    ``<repo_root>/.kittify/doctrine/``. Pack-mode scaffolding writes to the
    user-supplied pack root verbatim.
    """
    if pack is not None:
        return pack
    if repo_root is None:
        raise typer.BadParameter(
            "Could not locate spec-kitty project root. Run from inside a project "
            "containing .kittify/ or pass --pack to target an explicit pack directory."
        )
    return repo_root / ".kittify" / "doctrine"


@app.command(name="new")
def new(
    kind: str = typer.Argument(
        ...,
        help=(
            "Artifact kind (singular): one of "
            + ", ".join(sorted(member.value for member in _STUB_TEMPLATES))
            + "."
        ),
    ),
    artifact_id: str = typer.Argument(
        ...,
        metavar="ID",
        help="Artifact identifier (kebab-case for most kinds; SCREAMING_SNAKE for directives).",
    ),
    pack: Path | None = typer.Option(
        None,
        "--pack",
        help=(
            "Scaffold inside a doctrine pack directory instead of the project layer. "
            "When omitted, the stub lands under .kittify/doctrine/."
        ),
    ),
) -> None:
    """Scaffold a stub doctrine artifact YAML (FR-016).

    The scaffolder pre-fills the canonical schema's required fields with
    ``TODO …`` placeholders so the file passes ``doctrine validate`` on
    first emit.  Refuses to overwrite an existing file.
    """
    artifact_kind = _resolve_scaffoldable_kind(kind)
    plural = artifact_kind.plural

    from specify_cli.core.paths import locate_project_root

    repo_root = locate_project_root()
    try:
        doctrine_root = _resolve_scaffold_root(repo_root, pack)
    except typer.BadParameter as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    # Pack mode uses the plural pack-layout directory; project mode uses the
    # single canonical project-tier authority — the same map DoctrineService's
    # resolver reads (charter.offering.artifact_kinds.PROJECT_KIND_DIRS, re-exported
    # here via the charter.activation.kind_vocabulary facade per the runtime -> charter
    # -> doctrine boundary), so the stub lands exactly where the loader will
    # look for it.
    target_dir_name = (
        plural if pack is not None else PROJECT_KIND_DIRS[artifact_kind]
    )
    target_dir = doctrine_root / target_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / _artifact_filename(artifact_kind, artifact_id)

    if target_path.exists():
        console.print(
            f"[red]Refusing to overwrite existing file:[/red] {target_path}"
        )
        raise typer.Exit(1)

    stub_text = _stub_template(artifact_kind, artifact_id)

    # Sanity-check the stub against the schema before writing so a future
    # schema tightening can't silently regress the scaffolder.  The
    # registry in pack_validator is the canonical source of truth.
    from ruamel.yaml import YAML

    from specify_cli.doctrine.pack_validator import _artifact_schema_registry

    schema_cls = _artifact_schema_registry()[plural][1]
    parsed = YAML(typ="safe").load(stub_text)
    try:
        schema_cls.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001 — surface to operator verbatim
        console.print(
            f"[red]Internal error:[/red] stub for kind '{artifact_kind.value}' failed "
            f"schema validation: {exc}"
        )
        raise typer.Exit(1) from exc

    target_path.write_text(stub_text, encoding="utf-8")
    console.print(
        f"[green]Created stub artifact:[/green] {target_path}\n"
        f"Run [bold]spec-kitty doctrine validate {target_path}[/bold] to confirm."
    )


# ----------------------------------------------------------------------
# validate — project-layer artifact / tree validation (FR-017 / WP09 T049)
# ----------------------------------------------------------------------

#: Map filename suffix → ``(plural_dir_name, kind_singular)`` for the
#: ``validate`` command to detect a single file's artifact kind without
#: requiring the operator to pass it explicitly.  Mirrors the suffixes
#: declared in :func:`_artifact_schema_registry`.
_SUFFIX_TO_KIND: dict[str, tuple[str, str]] = {
    ".directive.yaml": ("directives", "directive"),
    ".tactic.yaml": ("tactics", "tactic"),
    ".styleguide.yaml": ("styleguides", "styleguide"),
    ".toolguide.yaml": ("toolguides", "toolguide"),
    ".paradigm.yaml": ("paradigms", "paradigm"),
    ".procedure.yaml": ("procedures", "procedure"),
    ".agent.yaml": ("agent_profiles", "agent_profile"),
    ".step-contract.yaml": ("mission_step_contracts", "mission_step_contract"),
    ".asset.yaml": ("assets", "asset"),
}


def _detect_artifact_kind(path: Path) -> tuple[str, str] | None:
    """Return ``(plural, singular)`` for *path* based on its filename suffix."""
    name = path.name.lower()
    for suffix, kinds in _SUFFIX_TO_KIND.items():
        if name.endswith(suffix):
            return kinds
    return None


#: Sentinel strings that authors mistakenly put in ``applies_to_languages``
#: to mean "applies to all languages".  These are NOT valid language tokens;
#: omitting the field entirely is the correct way to express always-applicable.
_APPLIES_TO_LANGUAGES_SENTINELS: frozenset[str] = frozenset({"any", "all"})


def _check_applies_to_languages(data: dict[str, object]) -> str | None:
    """Return an error message if ``applies_to_languages`` contains a sentinel.

    Checks the raw YAML dict (before Pydantic) so the guard fires regardless
    of artifact kind and gives authors an actionable message instead of a
    generic schema error.
    """
    raw = data.get("applies_to_languages")
    if not isinstance(raw, list):
        return None
    bad = [
        str(token)
        for token in raw
        if isinstance(token, str)
        and token.strip().lower() in _APPLIES_TO_LANGUAGES_SENTINELS
    ]
    if not bad:
        return None
    quoted = ", ".join(f"'{t}'" for t in bad)
    return (
        f"`any`/`all` are not language tokens — "
        f"omit `applies_to_languages` to mean always-applicable "
        f"(found: {quoted})"
    )


def _validate_single_artifact(
    path: Path,
) -> tuple[bool, str | None]:
    """Validate a single artifact YAML file.

    Returns ``(ok, error_message)``.  ``error_message`` is ``None`` on
    success and a human-readable string on failure.
    """
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    from specify_cli.doctrine.pack_validator import _artifact_schema_registry

    detected = _detect_artifact_kind(path)
    if detected is None:
        return False, (
            f"unrecognised artifact filename suffix (expected one of "
            f"{', '.join(sorted(_SUFFIX_TO_KIND))})"
        )
    plural, _singular = detected
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (YAMLError, OSError) as exc:
        return False, f"YAML parse error: {exc}"
    if data is None:
        return False, "empty YAML document"
    if not isinstance(data, dict):
        return False, "expected a YAML mapping at top level"
    lang_err = _check_applies_to_languages(data)
    if lang_err is not None:
        return False, lang_err
    schema_cls = _artifact_schema_registry()[plural][1]
    try:
        schema_cls.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — schema errors → operator text
        return False, f"schema validation failed: {exc}"
    return True, None


@app.command(name="validate")
def validate(
    path: Path = typer.Argument(
        ...,
        help=(
            "Artifact YAML file or a directory containing project-layer "
            "doctrine artifacts (recurses into per-kind subdirectories)."
        ),
    ),
) -> None:
    """Validate project-layer doctrine artifacts against their schemas (FR-017).

    When *path* is a single file, validates that file.  When *path* is a
    directory, walks the tree for ``*.yaml`` files whose filename suffix
    matches a canonical artifact kind and validates each one.

    Exit code: ``0`` if every artifact validates; ``1`` if any artifact
    fails.  A per-file error report is printed for failures.
    """
    if not path.exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(2)

    targets: list[Path] = (
        [path]
        if path.is_file()
        else sorted(p for p in path.rglob("*.yaml") if _detect_artifact_kind(p))
    )

    if not targets:
        console.print(
            f"[yellow]No doctrine artifact files found under {path}.[/yellow]"
        )
        raise typer.Exit(0)

    failures: list[tuple[Path, str]] = []
    for target in targets:
        ok, err = _validate_single_artifact(target)
        if ok:
            console.print(f"[green]OK[/green] {target}")
        else:
            failures.append((target, err or "(no error message)"))
            console.print(f"[red]FAIL[/red] {target}: {err}")

    if failures:
        console.print(
            f"\n[red]{len(failures)} of {len(targets)} artifact(s) failed validation.[/red]"
        )
        raise typer.Exit(1)
    console.print(
        f"\n[green]{len(targets)} artifact(s) passed validation.[/green]"
    )
    raise typer.Exit(0)


# ----------------------------------------------------------------------
# org init — scaffold a minimal org doctrine pack skeleton (FR-006 / WP08)
# ----------------------------------------------------------------------

#: Minimal ``org-charter.yaml`` body.  All fields are optional in
#: :class:`specify_cli.doctrine.org_charter.OrgCharterPolicy`; the stub
#: carries the schema_version sentinel and a TODO org_name as a
#: quickstart hint.
_ORG_CHARTER_STUB = """\
schema_version: "1"
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

> Scaffolded by `spec-kitty doctrine org init`.

## Contents

- `org-charter.yaml` — organisation-level governance policy
- `drg/fragment.yaml` — DRG extension fragment declaring org-tier nodes
- Additional artifact subdirectories (e.g. `directives/`, `tactics/`) may
  be added alongside the `org-charter.yaml`.

## Validation

```bash
spec-kitty doctrine org validate .
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
        help=(
            "Local template directory or git URL (HTTPS/SSH; optional #branch). "
            "When omitted, scaffolds the minimal three-file pack."
        ),
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

    Without ``--template``, creates three files under *pack-path*::

        org-charter.yaml   — governance policy stub
        drg/fragment.yaml  — DRG extension stub (with pydantic_model: frontmatter)
        README.md          — authoring quickstart

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
    """Write the legacy three-file org pack skeleton."""
    if pack_path.exists() and not force:
        console.print(
            f"[red]Target directory already exists:[/red] {pack_path}\n"
            "Pass [bold]--force[/bold] to overwrite."
        )
        raise typer.Exit(1)

    pack_path.mkdir(parents=True, exist_ok=True)
    (pack_path / "drg").mkdir(parents=True, exist_ok=True)

    (pack_path / "org-charter.yaml").write_text(_ORG_CHARTER_STUB, encoding="utf-8")
    (pack_path / "drg" / "fragment.yaml").write_text(_DRG_FRAGMENT_STUB, encoding="utf-8")
    (pack_path / "README.md").write_text(_ORG_PACK_README_STUB, encoding="utf-8")

    console.print(f"[green]Org pack scaffolded at:[/green] {pack_path}")
    console.print("  org-charter.yaml")
    console.print("  drg/fragment.yaml")
    console.print("  README.md")
    console.print(
        f"\nRun [bold]spec-kitty doctrine org validate {pack_path}[/bold] to confirm."
    )


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
    from specify_cli.doctrine.template_render import RenderRequest
    from specify_cli.doctrine.template_render.pipeline import render_org_pack

    if not org_name:
        console.print(
            "[red]ORG_NAME is required when --template is set[/red] "
            "(org_name.required)."
        )
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
    console.print(
        "  Full template tree written (minus .templateignore); "
        "ORG_NAME / LOCAL_PATH tokens substituted."
    )
    console.print(
        f"\nRun [bold]spec-kitty doctrine org validate {pack_path}/pack[/bold] "
        "or your template's quality-check if applicable."
    )


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

    Calls the WP06 :func:`specify_cli.doctrine.pack_validator.validate_pack`
    loader.  Prints per-file findings with file paths.  Exits non-zero when
    at least one error is found.

    Org fragments use id and plural kind (for example, directives) for nodes.
    Validation uses the runtime loader, which supplies pack provenance fields.
    """
    from specify_cli.doctrine.pack_validator import (
        render_validation_result,
        validate_pack,
    )

    # Written explicitly (not relying on validate_pack's own default) so a
    # future default change cannot silently alter org_validate's behaviour
    # without a visible diff here. No carve-out: org_init's scaffold never
    # produces the drg-root-graph-missing shape, so this call was never
    # protected by a carve-out in the first place (operator ruling #2,
    # reviews/plan.ruling.md).
    result = validate_pack(pack_path, check_drg_root=True)

    render_validation_result(result, json_output=False)
    raise typer.Exit(0 if result.ok else 1)


# ----------------------------------------------------------------------
# mission-type list — enumerate all doctrine-layer mission types (FR-013)
# ----------------------------------------------------------------------

#: Dataclass-free record type for a mission-type row.
class _MissionTypeRow:
    """Lightweight row value object for mission-type list output."""

    __slots__ = ("id", "source_layer", "display_name")

    def __init__(self, id: str, source_layer: str, display_name: str) -> None:  # noqa: A002
        self.id = id
        self.source_layer = source_layer
        self.display_name = display_name


@mission_type_app.command("list")
def mission_type_list(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
) -> None:
    """List all mission types in the doctrine layer (FR-013).

    Enumerates built-in, org, and project mission types regardless of
    activation state.  The DRG resolution chain applies: built-in →
    org → project.  An org type with the same id shadows the built-in
    type; a project type shadows the org type.

    Use ``spec-kitty charter mission-type list`` to see only types that
    are currently activated for this project.
    """
    # FR-008 (WP07/T018): the full layered roster (built-in -> org ->
    # project, full per-id replacement) IS the built-in -> org -> project
    # shadow chain this docstring already promises -- reach it directly
    # instead of the built-in-only collector, so an id merely *registered*
    # (not activated) in an org/project layer still appears here with its
    # real layer, matching this command's own contract (activation-scoped
    # listing is `charter mission-type list`'s job, not this one's).
    from specify_cli.cli.commands.charter.mission_type import (  # noqa: PLC0415
        resolve_layered_roster,
        resolve_mission_type_source_layer,
    )

    repo_root = Path.cwd()

    # CL-006/NFR-002 (post-fix verification sweep, mission
    # up-mission-type-seam-01KZY1JB): sibling of the same unguarded call in
    # ``charter mission-type list`` -- ``resolve_layered_roster`` loud-fails
    # BY DESIGN (WP03, PR-CONTRACT-002) on a malformed/unreadable YAML file
    # anywhere in the built-in/org/project ``mission_types/`` layers. A bare
    # ``except ValueError`` also catches ``pydantic.ValidationError`` (this
    # resolver's other documented ``Raises`` type) since it subclasses
    # ``ValueError`` in the pinned pydantic version.
    try:
        roster = resolve_layered_roster(repo_root)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    rows: list[_MissionTypeRow] = [
        _MissionTypeRow(
            id=mt_id,
            source_layer=resolve_mission_type_source_layer(mt_id, repo_root),
            display_name=mission_type.display_name,
        )
        for mt_id, mission_type in roster.items()
    ]

    # Sort: built-in first (already the case), then by id within each layer.
    rows.sort(key=lambda r: (r.source_layer != "built-in", r.id))

    if json_output:
        data = [
            {"id": r.id, "source_layer": r.source_layer, "display_name": r.display_name}
            for r in rows
        ]
        console.print_json(json.dumps(data))
        return

    if not rows:
        console.print("[yellow]No mission types found.[/yellow]")
        raise typer.Exit(0)

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("SOURCE", style="green")
    table.add_column("DISPLAY NAME")

    for row in rows:
        table.add_row(row.id, row.source_layer, row.display_name)

    console.print(table)
    raise typer.Exit(0)
