"""Charter authoring commands: ``fetch``, ``new`` and ``validate``.

* ``spec-kitty charter fetch [--pack <name>] [--dry-run]`` — fetch one or all
  configured org charter packs into their local snapshot directories.
* ``spec-kitty charter new <kind> <id> [--pack <path>]`` — scaffold a stub
  project-layer (or pack-layer) artifact YAML pre-filled with the canonical
  schema's required fields (FR-016).
* ``spec-kitty charter validate <path>`` — validate a single project-layer
  artifact file or an artifact tree against the artifact schemas (FR-017).

The handlers are registered by :mod:`specify_cli.cli.commands.charter._app`
(mission charter-pack-cutover-01M491G6, FR-006; moved out of the retired
``doctrine`` command module with their bodies unchanged).
"""

from __future__ import annotations

from pathlib import Path

import typer
from charter.activation.kind_vocabulary import PROJECT_KIND_DIRS
from charter.activation.language_scope import (
    RESERVED_LANGUAGE_TOKENS,
    SENTINEL_LANGUAGE_TOKENS,
    UNKNOWN_LANGUAGE,
)
from charter.drg import ArtifactKind, slug_for
from kernel.charter_pack_paths import PROJECT_PACK_ROOT_POSIX, project_pack_root
from specify_cli.cli.console import console

__all__ = ["fetch", "new", "validate"]


# ----------------------------------------------------------------------
# fetch
# ----------------------------------------------------------------------
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
    """Fetch org Charter Pack(s) from their configured remote sources."""
    from charter.drg import load_pack_registry
    from specify_cli.core.paths import locate_project_root
    from specify_cli.charter_packs.snapshot import fetch_pack

    repo_root = locate_project_root()
    if repo_root is None:
        console.print("[red]Could not locate spec-kitty project root.[/red] Run from inside a project containing .kittify/.")
        raise typer.Exit(1)

    registry = load_pack_registry(repo_root)
    if not registry.packs:
        console.print("[red]No org charter packs configured.[/red]")
        console.print("Add an entry to the [bold]charter_packs.org.packs[/bold] list in .kittify/config.yaml.")
        raise typer.Exit(1)

    target_packs = list(registry.packs)
    if pack_name is not None:
        target_packs = [p for p in registry.packs if p.name == pack_name]
        if not target_packs:
            names = ", ".join(registry.names()) or "(none)"
            console.print(f"[red]Pack '{pack_name}' not found.[/red] Configured packs: {names}")
            raise typer.Exit(1)

    if dry_run:
        from charter.drg import OrgPackEnvVarUnsetError

        for pack in target_packs:
            origin = pack.url or str(pack.local_path)
            try:
                target = pack.local_path_root(repo_root)
            except OrgPackEnvVarUnsetError as exc:
                console.print(f"Would fetch pack '[bold]{pack.name}[/bold]' from {origin} — [red]cannot resolve target: {exc}[/red]")
                continue
            console.print(f"Would fetch pack '[bold]{pack.name}[/bold]' from {origin} into {target}")
        return

    any_failed = False
    for pack in target_packs:
        result = fetch_pack(pack, repo_root)
        if result.ok:
            suffix = " (unchanged)" if result.unchanged else ""
            console.print(f"[green]Pack '{pack.name}': {result.artifacts_written} artifacts{suffix}[/green]")
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
# new — scaffold a stub artifact (FR-016 / WP09 T048)
# ----------------------------------------------------------------------

#: Per-kind stub bodies (T016).  Each value is a ``str.format``-ready YAML
#: template whose ``{artifact_id}`` placeholder the scaffolder substitutes; the
#: rendered stub is the *minimum* payload that passes the corresponding Pydantic
#: schema in ``src/charter/offering/*/models.py`` (or ``AssetManifest``).  The scaffolder
#: validates the rendered stub against the schema before writing — a future
#: schema tightening surfaces at the next ``charter new`` rather than silently
#: scaffolding an invalid file.
#:
#: This is a ``dict[ArtifactKind, str]`` (not an eight-arm ``if``-chain) so the
#: kind projection is a table the kind-mapping totality guard can see. It is a
#: deliberately **partial** table — ``template`` (empty glob, unscaffoldable),
#: ``glossary_pack`` and ``anti_pattern`` (hand-authored) carry no stub — read
#: only through the membership gate in :func:`new`, so it is carried as an
#: allow-listed ``.get``/membership partial in the guard's
#: ``_EXEMPT_GET_PARTIALS`` with that reason. The set of keys is exactly the
#: kinds ``charter new`` supports.
_STUB_TEMPLATES: dict[ArtifactKind, str] = {
    # Directive: id must match [A-Z][A-Z0-9_-]*; intent + title required.
    ArtifactKind.DIRECTIVE: ('schema_version: "1.0"\nid: {artifact_id}\ntitle: TODO short title\nintent: TODO why this directive exists\nenforcement: advisory\n'),
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
        'schema_version: "1.0"\nid: {artifact_id}\ntitle: TODO short title\nscope: code\nprinciples:\n  - TODO first principle\napplies_to_languages: []\n'
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
    ArtifactKind.PARADIGM: ('schema_version: "1.0"\nid: {artifact_id}\nname: TODO short name\nsummary: TODO one-line summary of the paradigm\n'),
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
    ArtifactKind.ASSET: ("id: {artifact_id}\nmime: text/plain\npath: TODO-relative-path-under-assets.txt\ntitle: TODO asset display name\n"),
}


def _artifact_filename(kind: ArtifactKind, artifact_id: str) -> str:
    """Return the canonical filename for a doctrine artifact.

    The stem is derived via :func:`slug_for` (WP01) -- the same single
    producer-side authority the registration engine uses -- so a SCREAMING
    directive id such as ``LOVE_THY_ENEMY`` scaffolds as
    ``love-thy-enemy.directive.yaml`` while the authored ``id:`` inside the
    stub body stays ``LOVE_THY_ENEMY``. Non-directive kinds are unaffected
    (``slug_for`` is verbatim + ``quote`` for them).
    """
    glob_pattern = kind.glob_pattern
    if not glob_pattern.startswith("*"):
        raise ValueError(f"Unsupported artifact kind: {kind.value}")
    slug = slug_for(kind.value, artifact_id)
    return f"{slug}{glob_pattern.removeprefix('*')}"


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
        console.print(f"[red]Unknown artifact kind '{raw_kind}'.[/red] Expected one of: {valid}.")
        raise typer.Exit(2)
    return kind


def _resolve_scaffold_root(
    repo_root: Path | None,
    pack: Path | None,
) -> Path:
    """Return the doctrine root that scaffolded files should land under.

    Project-layer scaffolding (no ``--pack``) writes under
    ``<repo_root>/.kittify/charter-packs/`` (the project charter pack root).
    Pack-mode scaffolding writes to the
    user-supplied pack root verbatim.
    """
    if pack is not None:
        return pack
    if repo_root is None:
        raise typer.BadParameter(
            "Could not locate spec-kitty project root. Run from inside a project containing .kittify/ or pass --pack to target an explicit pack directory."
        )
    return project_pack_root(repo_root)


#: ``charter new`` KIND help: the scaffoldable kinds are exactly ``_STUB_TEMPLATES``' keys.
_NEW_KIND_HELP = "Artifact kind (singular): one of " + ", ".join(sorted(k.value for k in _STUB_TEMPLATES)) + "."


def new(
    kind: str = typer.Argument(
        ...,
        help=_NEW_KIND_HELP,
    ),
    artifact_id: str = typer.Argument(
        ...,
        metavar="ID",
        help="Artifact identifier (kebab-case for most kinds; SCREAMING_SNAKE for directives).",
    ),
    pack: Path | None = typer.Option(
        None,
        "--pack",
        help=(f"Scaffold inside a Charter Pack directory instead of the project layer. When omitted, the stub lands under {PROJECT_PACK_ROOT_POSIX}/."),
    ),
) -> None:
    """Scaffold a stub doctrine artifact YAML (FR-016).

    The scaffolder pre-fills the canonical schema's required fields with
    ``TODO …`` placeholders so the file passes ``charter validate`` on
    first emit.  Refuses to overwrite an existing file.
    """
    artifact_kind = _resolve_scaffoldable_kind(kind)
    plural = artifact_kind.plural

    from specify_cli.core.paths import locate_project_root

    repo_root = locate_project_root()
    try:
        pack_root = _resolve_scaffold_root(repo_root, pack)
    except typer.BadParameter as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    # Pack mode uses the plural pack-layout directory; project mode uses the
    # single canonical project-tier authority — the same map ActiveCharterService's
    # resolver reads (charter.offering.artifact_kinds.PROJECT_KIND_DIRS, re-exported
    # here via the charter.activation.kind_vocabulary facade per the runtime -> charter
    # -> doctrine boundary), so the stub lands exactly where the loader will
    # look for it.
    target_dir_name = plural if pack is not None else PROJECT_KIND_DIRS[artifact_kind]
    target_dir = pack_root / target_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / _artifact_filename(artifact_kind, artifact_id)

    if target_path.exists():
        console.print(f"[red]Refusing to overwrite existing file:[/red] {target_path}")
        raise typer.Exit(1)

    stub_text = _stub_template(artifact_kind, artifact_id)

    # Sanity-check the stub against the schema before writing so a future
    # schema tightening can't silently regress the scaffolder.  The
    # registry in pack_validator is the canonical source of truth.
    from ruamel.yaml import YAML

    from charter.packs import artifact_schema_registry

    schema_cls = artifact_schema_registry()[plural][1]
    parsed = YAML(typ="safe").load(stub_text)
    try:
        schema_cls.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001 — surface to operator verbatim
        console.print(f"[red]Internal error:[/red] stub for kind '{artifact_kind.value}' failed schema validation: {exc}")
        raise typer.Exit(1) from exc

    target_path.write_text(stub_text, encoding="utf-8")
    console.print(f"[green]Created stub artifact:[/green] {target_path}\nRun [bold]spec-kitty charter validate {target_path}[/bold] to confirm.")


# ----------------------------------------------------------------------
# validate — project-layer artifact / tree validation (FR-017 / WP09 T049)
# ----------------------------------------------------------------------

#: Map filename suffix → ``(plural_dir_name, kind_singular)`` for the
#: ``validate`` command to detect a single file's artifact kind without
#: requiring the operator to pass it explicitly.  Mirrors the suffixes
#: declared in :func:`artifact_schema_registry`.
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


def _check_applies_to_languages(data: dict[str, object]) -> str | None:
    """Return an error message if ``applies_to_languages`` holds a non-language token.

    Checks the raw YAML dict (before Pydantic) so the guard fires regardless
    of artifact kind and gives authors an actionable message instead of a
    generic schema error.  Sentinels (``any``/``all``) and reserved tokens
    (``unknown``) get distinct messages; both sets come from ``scoping`` via the ``charter.activation.language_scope`` door.
    """
    raw = data.get("applies_to_languages")
    if not isinstance(raw, list):
        return None
    tokens = [str(t) for t in raw if isinstance(t, str)]
    reserved = [t for t in tokens if t.strip().lower() in RESERVED_LANGUAGE_TOKENS]
    if reserved:
        quoted = ", ".join(f"'{t}'" for t in reserved)
        return f"`{UNKNOWN_LANGUAGE}` is a reserved value set by Spec Kitty for unrecognised project languages; artifacts cannot target it (found: {quoted})"
    bad = [t for t in tokens if t.strip().lower() in SENTINEL_LANGUAGE_TOKENS]
    if not bad:
        return None
    quoted = ", ".join(f"'{t}'" for t in bad)
    return f"`any`/`all` are not language tokens — omit `applies_to_languages` to mean always-applicable (found: {quoted})"


def _validate_single_artifact(
    path: Path,
) -> tuple[bool, str | None]:
    """Validate a single artifact YAML file.

    Returns ``(ok, error_message)``.  ``error_message`` is ``None`` on
    success and a human-readable string on failure.
    """
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    from charter.packs import artifact_schema_registry

    detected = _detect_artifact_kind(path)
    if detected is None:
        return False, (f"unrecognised artifact filename suffix (expected one of {', '.join(sorted(_SUFFIX_TO_KIND))})")
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
    schema_cls = artifact_schema_registry()[plural][1]
    try:
        schema_cls.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — schema errors → operator text
        return False, f"schema validation failed: {exc}"
    return True, None


def validate(
    path: Path = typer.Argument(
        ...,
        help=("Artifact YAML file or a directory containing project-layer doctrine artifacts (recurses into per-kind subdirectories)."),
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

    targets: list[Path] = [path] if path.is_file() else sorted(p for p in path.rglob("*.yaml") if _detect_artifact_kind(p))

    if not targets:
        console.print(f"[yellow]No doctrine artifact files found under {path}.[/yellow]")
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
        console.print(f"\n[red]{len(failures)} of {len(targets)} artifact(s) failed validation.[/red]")
        raise typer.Exit(1)
    console.print(f"\n[green]{len(targets)} artifact(s) passed validation.[/green]")
    raise typer.Exit(0)
