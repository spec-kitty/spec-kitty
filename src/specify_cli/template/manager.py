"""Template discovery and copy helpers."""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from importlib.resources.abc import Traversable
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

from kernel.clock import now_utc_compact_stamp
from rich.console import Console

console = Console()


class TemplateCopyResult(NamedTuple):
    """Outcome of a full base-template copy (FR-001(a)/#4931 re-arm fix).

    ``command_templates_dir`` is the path both copy functions have always
    returned (``.kittify/templates/command-templates``), unchanged.

    ``templates_created`` is True only when THIS invocation's copy step
    actually populated/refreshed ``.kittify/templates/`` -- i.e. the
    templates SOURCE existed and the backup+copy branch ran. It is False
    when the source was absent (partial checkout, or a future relocation of
    the templates source) and the templates branch was skipped entirely: no
    backup, no copytree, nothing touched.

    Callers MUST use this field -- never assume unconditionally-True -- to
    decide whether a pre-existing operator ``.kittify/templates/`` was
    created by this run. Getting this wrong re-arms the #4931 P0: a
    provenance-unaware caller "proves" an untouched operator tree
    run-created and a downstream cleanup guard silently deletes it, no
    backup, exit 0.
    """

    command_templates_dir: Path
    templates_created: bool


#: Prefix for the persistent, operator-reported backup directories this
#: module creates (FR-006/D6). Deliberately distinct from
#: ``template_render/pipeline.py``'s transactional ``.bak-{nonce}`` swap
#: (removed on success) -- see C-006. Never removed automatically; the
#: operator owns cleanup.
_BACKUP_DIR_PREFIX = ".backup-"


def _resource_exists(resource: Traversable) -> bool:
    return resource.is_file() or resource.is_dir()


def _utc_backup_timestamp() -> str:
    """Return the current UTC timestamp in a filesystem-safe, sortable form.

    A separate seam (rather than inlining the clock read at the call site)
    so tests can force a same-second collision deterministically. Routes
    through the canonical ``kernel.clock`` door (FR-012) rather than a raw
    ``datetime.now`` read; the compact stamp is byte-identical
    (``%Y%m%dT%H%M%SZ``).
    """
    return now_utc_compact_stamp()


def _allocate_backup_dir(parent: Path) -> Path:
    """Allocate a fresh backup directory under ``parent``, collision-safe.

    Two re-inits within the same wall-clock second must not collide: a
    numeric suffix is appended and retried until an as-yet-unclaimed
    directory name is found and atomically created (``mkdir(exist_ok=False)``
    -- no TOCTOU window between the existence check and the create).
    """
    parent.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_backup_timestamp()
    suffix = 0
    while True:
        name = f"{_BACKUP_DIR_PREFIX}{timestamp}" if suffix == 0 else f"{_BACKUP_DIR_PREFIX}{timestamp}-{suffix}"
        candidate = parent / name
        try:
            candidate.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            suffix += 1
            continue
        return candidate


def back_up_operator_subtrees(
    source_root: Path,
    subtree_names: Sequence[str],
    *,
    backup_parent: Path | None = None,
) -> Path | None:
    """Move existing operator-authored subtrees out of harm's way before scaffolding.

    The single canonical "back up operator-authored content, then proceed"
    helper (FR-006/D6). For each name in ``subtree_names`` that exists
    directly under ``source_root`` (e.g. ``.kittify/missions``,
    ``.kittify/memory``), the whole subtree is moved -- not copied -- into a
    freshly allocated, timestamped, collision-safe ``.backup-<UTC-ts>/``
    directory, so the original destructive removal step downstream finds
    nothing left to delete. Returns the backup directory's path (reported to
    the operator) when anything was preserved, else ``None``.

    ``backup_parent`` controls where the backup directory itself is created;
    it defaults to ``source_root`` (``.kittify/.backup-<ts>/``). A caller
    about to delete ``source_root``'s own ancestor wholesale must pass a
    location that survives that deletion.
    """
    existing = [name for name in subtree_names if (source_root / name).exists()]
    if not existing:
        return None
    parent = backup_parent if backup_parent is not None else source_root
    backup_dir = _allocate_backup_dir(parent)
    for name in existing:
        shutil.move(str(source_root / name), str(backup_dir / name))
    console.print(f"[yellow]Preserved existing operator-authored content ({', '.join(existing)}) before scaffolding -> {backup_dir}[/yellow]")
    return backup_dir


def copy_specify_base_from_local(repo_root: Path, project_path: Path) -> TemplateCopyResult:
    """Copy the embedded .kittify assets from a local repository checkout."""
    specify_root = project_path / ".kittify"
    specify_root.mkdir(parents=True, exist_ok=True)
    templates_created = False

    # Copy from .kittify/memory/ for consistency with other .kittify paths
    memory_src = repo_root / ".kittify" / "memory"
    if memory_src.exists():
        memory_dest = specify_root / "memory"
        # FR-006: preserve any operator-authored memory/ instead of an
        # unconditional rmtree -- back it up first (#4759).
        back_up_operator_subtrees(specify_root, ["memory"])
        shutil.copytree(memory_src, memory_dest)

    # Copy from src/charter/offering/templates/ (doctrine artifacts, relocated
    # by mission charter-code-topology-01M152G1).
    # Mission content templates live under packs/built-in/missions/<mission>/templates
    # (mission doctrine-consumer-surface-missions-extraction-01KZ6G6H, FR-005,
    # relocated the missions data subdirectories out of src/charter/offering/missions).
    templates_src = repo_root / "src" / "charter" / "offering" / "templates"
    if templates_src.exists():
        templates_dest = specify_root / "templates"
        # FR-001(b)/#4931: preserve any operator-authored templates/ instead
        # of an unconditional rmtree -- back it up first, mirroring the
        # memory/ precedent above (:107, #4759).
        back_up_operator_subtrees(specify_root, ["templates"])
        shutil.copytree(templates_src, templates_dest)
        templates_created = True
        agents_template = templates_src / "AGENTS.md"
        if agents_template.exists():
            shutil.copy2(agents_template, specify_root / "AGENTS.md")

    # HIGH SEVERITY finding (R-12): before FR-005, this used
    # `repo_root / "src" / "charter" / "offering" / "missions"` — a directory that still
    # exists post-relocation (only the .py logic modules remain there) and
    # would silently `.exists() == True` with zero mission data inside,
    # producing a broken `.kittify/missions/` scaffold with no error signal.
    missions_src = repo_root / "packs" / "built-in" / "missions"
    if missions_src.exists():
        missions_dest = specify_root / "missions"
        # FR-006: preserve any operator-authored custom missions instead of
        # an unconditional rmtree -- back them up first (#4759).
        back_up_operator_subtrees(specify_root, ["missions"])
        shutil.copytree(missions_src, missions_dest)

    # NOTE: Templates are copied temporarily for agent command generation
    # They will be cleaned up after all commands are generated (see init.py)
    return TemplateCopyResult(
        command_templates_dir=specify_root / "templates" / "command-templates",
        templates_created=templates_created,
    )


def copy_package_tree(resource: Traversable, dest: Path, *, preserve_existing: bool = False) -> None:
    """Recursively copy an importlib.resources directory tree.

    ``preserve_existing`` (FR-006/D6) guards this function's own removal
    step: when True and ``dest`` already holds content, it is preserved
    (moved into a timestamped ``.kittify/.backup-<ts>/`` directory via
    :func:`back_up_operator_subtrees`) instead of being deleted outright.
    Regenerable-scaffold callers (e.g. ``templates/``) pass the default
    ``False`` and keep the prior replace-in-place behavior -- deliberately
    not preserved (#4759).
    """
    if dest.exists():
        if preserve_existing:
            back_up_operator_subtrees(dest.parent, [dest.name])
        else:
            shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for child in resource.iterdir():
        target = dest / child.name
        if child.is_dir():
            copy_package_tree(child, target)
        else:
            with child.open("rb") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)


def copy_specify_base_from_package(project_path: Path) -> TemplateCopyResult:
    """Copy the packaged .kittify assets that ship with the CLI."""
    specify_data_root = files("specify_cli")
    specify_root = project_path / ".kittify"
    specify_root.mkdir(parents=True, exist_ok=True)
    templates_created = False

    memory_resource = specify_data_root.joinpath("memory")
    if _resource_exists(memory_resource):
        # FR-006: preserve, never unconditionally rmtree, operator-authored
        # memory/ (#4759).
        copy_package_tree(memory_resource, specify_root / "memory", preserve_existing=True)

    try:
        doctrine_data_root = files("charter.offering")
    except (ModuleNotFoundError, TypeError):
        doctrine_data_root = specify_data_root

    templates_resource_candidates = [
        doctrine_data_root.joinpath("templates"),
        specify_data_root.joinpath("templates"),  # Legacy fallback
    ]
    for templates_resource in templates_resource_candidates:
        if _resource_exists(templates_resource):
            templates_dest = specify_root / "templates"
            # FR-001(b)/#4931: this is the pip-installed default `init` path
            # -- preserve, never unconditionally rmtree, operator-authored
            # templates/, mirroring the memory/ precedent above (:179).
            copy_package_tree(templates_resource, templates_dest, preserve_existing=True)
            templates_created = True
            agents_template = templates_resource.joinpath("AGENTS.md")
            if _resource_exists(agents_template):
                with agents_template.open("rb") as src, open(specify_root / "AGENTS.md", "wb") as dst:
                    shutil.copyfileobj(src, dst)
            break

    # HIGH SEVERITY finding (R-13) — the single default `spec-kitty init` code
    # path (no `--local` flag). Before FR-005, the first candidate was
    # `doctrine_data_root.joinpath("missions")` — a resource-package-relative
    # join that resolved to `src/charter/offering/missions`. Mission
    # doctrine-consumer-surface-missions-extraction-01KZ6G6H relocated the
    # missions data to `packs/built-in/missions`, which ships as a
    # site-packages-level *sibling* of the `doctrine` package (hatch
    # force-include), not a resource nested inside it -- so no
    # `files("charter.offering").joinpath(...)`-shaped join can reach it at all.
    # `MissionTemplateRepository.default_missions_root()` (FR-004) is the one
    # promoted authority that resolves it correctly in both an editable
    # checkout and an installed wheel; the returned `pathlib.Path` satisfies
    # the same duck-typed `Traversable` interface (`is_dir`/`iterdir`/`open`)
    # `copy_package_tree` and `_resource_exists` already consume, so it slots
    # into the existing candidate-list shape unchanged.
    missions_resource_candidates: list[Traversable] = []
    try:
        from charter.missions import (  # noqa: PLC0415
            MissionsRootNotFound,
            MissionTemplateRepository,
        )

        missions_resource_candidates.append(MissionTemplateRepository.default_missions_root())
    except MissionsRootNotFound:
        pass
    missions_resource_candidates.extend(
        [
            specify_data_root.joinpath("missions"),  # Legacy fallback
            specify_data_root.joinpath(".kittify", "missions"),  # Legacy fallback
            specify_data_root.joinpath("template_data", "missions"),  # Legacy fallback
        ]
    )
    for missions_resource in missions_resource_candidates:
        if _resource_exists(missions_resource):
            # FR-006: preserve, never unconditionally rmtree, operator-authored
            # custom missions (#4759).
            copy_package_tree(missions_resource, specify_root / "missions", preserve_existing=True)
            break

    return TemplateCopyResult(
        command_templates_dir=specify_root / "templates" / "command-templates",
        templates_created=templates_created,
    )


def get_local_repo_root(override_path: str | None = None) -> Path | None:
    """Return repository root when running from a local checkout, else None.

    Args:
        override_path: Optional override path (e.g., from --template-root flag)

    Returns:
        Path to repository root containing doctrine templates and missions, or None
    """

    def _is_template_root(path: Path) -> bool:
        # The second conjunct checks packs/built-in/missions (mission
        # doctrine-consumer-surface-missions-extraction-01KZ6G6H, FR-005,
        # relocated the missions data out of src/charter/offering/missions -- that
        # directory still exists post-relocation, .py-only, so checking it
        # here would silently accept a checkout whose missions data has
        # actually moved elsewhere, with no error signal).
        return (path / "src" / "charter" / "offering" / "templates" / "AGENTS.md").is_file() and (path / "packs" / "built-in" / "missions").is_dir()

    # Check override path first (from --template-root flag)
    if override_path:
        override = Path(override_path).expanduser().resolve()
        if _is_template_root(override):
            return override
        # Legacy fallback for old template structure
        if (override / ".kittify" / "templates" / "command-templates").exists():
            return override
        console.print(
            f"[yellow]--template-root {override} is not a Spec Kitty checkout/template root; using packaged templates.[/yellow]"  # noqa: E501
        )

    # Check environment variable
    env_root = os.environ.get("SPEC_KITTY_TEMPLATE_ROOT")
    if env_root:
        root_path = Path(env_root).expanduser().resolve()
        if _is_template_root(root_path):
            return root_path
        # Legacy fallback for old template structure
        if (root_path / ".kittify" / "templates" / "command-templates").exists():
            return root_path
        console.print(
            f"[yellow]SPEC_KITTY_TEMPLATE_ROOT {root_path} is not a Spec Kitty checkout/template root; using packaged templates.[/yellow]"  # noqa: E501
        )

    # Check package location
    candidate = Path(__file__).resolve().parents[3]
    if _is_template_root(candidate):
        return candidate
    # Legacy fallback for old template structure
    if (candidate / ".kittify" / "templates" / "command-templates").exists():
        return candidate
    return None


__all__ = [
    "TemplateCopyResult",
    "back_up_operator_subtrees",
    "copy_package_tree",
    "copy_specify_base_from_local",
    "copy_specify_base_from_package",
    "get_local_repo_root",
]
