"""The one skill-catalog seam (ADR 2026-09-27-1, plan decision 4).

Every install/assess/verify/repair caller obtains its skill catalog here, so the
retiring installer always sees the *whole* inventory it is allowed to manage:

* the shipped doctrine skills (``SkillRegistry.from_package()`` with the
  local-checkout fallback), and
* the charter-pack skills in force for the project, rendered into a staged root
  (``.kittify/runtime/pack-skills/<rendered-name>/SKILL.md``).

:class:`~specify_cli.skills.registry.CanonicalSkill` is path-based and
``snapshot_catalog`` refuses anything that is not a regular file below its own
root, so a pack skill (a YAML record plus a body) must be materialized as a real
skill directory before the installer can see it. Staging is therefore a *write*:
every refusal (preparation error, unknown wrapper target, name collision) is
decided in memory **before** the staging directory is touched, so a refused
resolution leaves the tree byte-identical.

Pack skills are tagged ``origin="pack"``; the installer projects them to project
skill roots only and never to a user-global root.
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from charter.activation.skill_preparation import PreparedSkill, SkillPreparationError, prepare_project_skill_activations
from charter.drg import resolve_existing_org_roots
from specify_cli.core.atomic import atomic_write
from specify_cli.core.paths import UnsafePathSegmentError, assert_safe_path_segment
from specify_cli.skills.manifest import ORIGIN_PACK
from specify_cli.skills.pack_skill_renderer import PackSkillRenderError, render_pack_skill
from specify_cli.skills.paths import SkillPathObservation
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry

logger = logging.getLogger(__name__)

__all__ = [
    "PackSkillCatalogError",
    "resolve_builtin_skill_catalog",
    "resolve_project_skill_catalog",
]

#: Staged root of rendered pack skills, relative to the project root.
_PACK_SKILL_STAGING = Path(".kittify") / "runtime" / "pack-skills"

#: Project-tier pack skills live here (``PROJECT_KIND_DIRS[ArtifactKind.SKILL]``).
_PROJECT_SKILLS_DIR = Path(".kittify") / "doctrine" / "skills"

_SKILL_FILENAME = "SKILL.md"

#: Lazily created process-wide root for read-only (``stage=False``) resolutions.
_READ_ONLY_ROOT: Path | None = None
_STAGED_FILE_MODE = 0o644


class PackSkillCatalogError(ValueError):
    """Pack skills cannot be resolved into the catalog; nothing was written."""


def resolve_builtin_skill_catalog(*, local_repo: Path | None = None, prefer_local: bool = False) -> SkillRegistry | None:
    """Return the shipped doctrine skill registry, or ``None`` when none is found.

    The installed package wins; a local checkout is the development fallback.
    ``prefer_local`` (with *local_repo*) reverses the order -- ``init`` from a
    local checkout installs that checkout's skills.
    """
    if prefer_local and local_repo is not None:
        return SkillRegistry.from_local_repo(local_repo)
    try:
        registry = SkillRegistry.from_package()
        if registry.discover_skills():
            return registry
    except Exception:
        logger.debug("Package skill registry unavailable", exc_info=True)
    return _local_checkout_catalog(local_repo)


def _local_checkout_catalog(local_repo: Path | None) -> SkillRegistry | None:
    from specify_cli.template import get_local_repo_root

    repo = local_repo if local_repo is not None else get_local_repo_root()
    if repo is None:
        return None
    registry = SkillRegistry.from_local_repo(repo)
    return registry if registry.discover_skills() else None


def resolve_project_skill_catalog(
    project_root: Path,
    *,
    builtin: SkillRegistry | None = None,
    local_repo: Path | None = None,
    prefer_local: bool = False,
    stage: bool = True,
) -> SkillRegistry:
    """Return the merged catalog (built-in plus staged pack skills) for *project_root*.

    When no shipped skills can be found the package registry is returned as-is
    (empty or missing, exactly what callers got before the seam existed); use
    ``discover_skills()`` to test for emptiness. *builtin* injects the shipped
    registry (tests, callers that already resolved one). Raises
    :class:`PackSkillCatalogError` -- before writing anything -- when the pack
    skills in force cannot be prepared or rendered, or when one renders under
    the name of a shipped skill.

    ``stage=False`` is the read-only mode (detect, assessment, dry-run, verify):
    the pack skills are rendered into a process-lifetime temporary directory
    outside the project, so the project tree is never written. Only install and
    apply paths stage under ``.kittify/runtime/pack-skills/``.
    """
    shipped = builtin or resolve_builtin_skill_catalog(local_repo=local_repo, prefer_local=prefer_local) or SkillRegistry.from_package()
    rendered = _render_active_pack_skills(project_root, shipped)
    staged = _stage(project_root, rendered) if stage else _stage_read_only(rendered)
    if staged is None:
        return shipped
    return _MergedSkillRegistry(shipped, staged, {item.prepared.rendered_name: item.prepared for item in rendered}, project_root)


@dataclass(frozen=True)
class _Rendered:
    """A prepared pack skill together with its rendered text."""

    prepared: PreparedSkill
    text: str


def _project_may_have_pack_skills(project_root: Path) -> bool:
    """Cheap prefilter: pack skills come from an org pack or the project tier only."""
    return (project_root / _PROJECT_SKILLS_DIR).is_dir() or bool(resolve_existing_org_roots(project_root))


def _render_active_pack_skills(project_root: Path, shipped: SkillRegistry) -> list[_Rendered]:
    """Prepare, render and collision-check the pack skills in force (no writes)."""
    if not _project_may_have_pack_skills(project_root):
        return []
    try:
        prepared = prepare_project_skill_activations(project_root)
        rendered = [_Rendered(item, render_pack_skill(item)) for item in prepared]
    except (SkillPreparationError, PackSkillRenderError) as exc:
        raise PackSkillCatalogError(str(exc)) from exc
    _refuse_unsafe_names(rendered)
    _refuse_builtin_collisions(rendered, shipped)
    return rendered


def _refuse_unsafe_names(rendered: list[_Rendered]) -> None:
    """Sink guard: no rendered name reaches a path join unless it is one safe segment."""
    for item in rendered:
        try:
            assert_safe_path_segment(item.prepared.rendered_name)
        except UnsafePathSegmentError as exc:
            raise PackSkillCatalogError(f"pack skill {item.prepared.id!r} would render as an unsafe directory name; {exc}") from exc


def _refuse_builtin_collisions(rendered: list[_Rendered], shipped: SkillRegistry) -> None:
    if not rendered:
        return
    shipped_names = {skill.name for skill in shipped.discover_skills()}
    for item in rendered:
        if item.prepared.rendered_name in shipped_names:
            raise PackSkillCatalogError(
                f"pack skill {item.prepared.id!r} renders as {item.prepared.rendered_name!r}, "
                "which is the name of a built-in skill; change its id or the pack's skill namespace"
            )


def _stage(project_root: Path, rendered: list[_Rendered]) -> SkillRegistry | None:
    """Materialize *rendered* under the staging root; remove what is no longer in force."""
    root = project_root / _PACK_SKILL_STAGING
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise PackSkillCatalogError(f"pack-skill staging root is not a regular directory: {root}")
    if not rendered:
        if root.is_dir() and any(root.iterdir()):
            shutil.rmtree(root)
        return None
    wanted = {item.prepared.rendered_name for item in rendered}
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.name not in wanted:
                _remove_node(child)
    for item in rendered:
        _write_staged(root / item.prepared.rendered_name / _SKILL_FILENAME, item.text)
    return SkillRegistry(root)


def _read_only_parent() -> Path:
    """The one per-process parent temp root (created, and its cleanup registered, once)."""
    global _READ_ONLY_ROOT
    if _READ_ONLY_ROOT is None or not _READ_ONLY_ROOT.is_dir():
        _READ_ONLY_ROOT = Path(tempfile.mkdtemp(prefix="spec-kitty-pack-skills-"))
        atexit.register(shutil.rmtree, _READ_ONLY_ROOT, ignore_errors=True)
    return _READ_ONLY_ROOT


def _rendered_set_key(rendered: list[_Rendered]) -> str:
    digest = hashlib.blake2b(digest_size=16)
    for item in sorted(rendered, key=lambda r: r.prepared.rendered_name):
        for part in (item.prepared.rendered_name, item.text):
            data = part.encode("utf-8")
            digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def _stage_read_only(rendered: list[_Rendered]) -> SkillRegistry | None:
    """Render into a content-addressed subdirectory of the process-wide temp root.

    The subdirectory is keyed by a hash of the rendered set and is reused
    untouched when it already exists, and never deleted during the process, so a
    registry (and the file identities recorded against it) from an earlier
    read-only resolution stays valid after later resolutions.
    """
    if not rendered:
        return None
    root = _read_only_parent() / _rendered_set_key(rendered)
    if not root.is_dir():
        building = root.with_name(f"{root.name}.building")
        shutil.rmtree(building, ignore_errors=True)
        for item in rendered:
            _write_staged(building / item.prepared.rendered_name / _SKILL_FILENAME, item.text)
        building.rename(root)
    return SkillRegistry(root)


def _remove_node(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _write_staged(path: Path, text: str) -> None:
    """Write *text* only when it differs, so a warm resolution is a no-op."""
    content = text.encode("utf-8")
    if path.parent.is_symlink():
        raise PackSkillCatalogError(f"pack-skill staging directory is a symlink: {path.parent}")
    if path.is_file() and not path.is_symlink() and path.read_bytes() == content:
        return
    if path.is_symlink() or path.is_dir():
        raise PackSkillCatalogError(f"pack-skill staging path is not a regular file: {path}")
    atomic_write(path, content, mkdir=True)
    path.chmod(_STAGED_FILE_MODE)


class _MergedSkillRegistry(SkillRegistry):
    """Built-in registry plus the staged pack registry, tagged by origin."""

    def __init__(
        self,
        shipped: SkillRegistry,
        staged: SkillRegistry,
        prepared_by_name: dict[str, PreparedSkill],
        project_root: Path,
    ) -> None:
        self._shipped = shipped
        self._staged = staged
        self._prepared = prepared_by_name
        self._project_root = project_root

    def _tag(self, skill: CanonicalSkill) -> CanonicalSkill:
        prepared = self._prepared[skill.name]
        return replace(skill, origin=ORIGIN_PACK, source_ref=_portable_ref(prepared.source_path, self._project_root), source_hash=prepared.source_hash)

    def discover_skills(self) -> list[CanonicalSkill]:
        return [*self._shipped.discover_skills(), *(self._tag(skill) for skill in self._staged.discover_skills())]

    def snapshot_catalog(self) -> tuple[tuple[CanonicalSkill, ...], tuple[SkillPathObservation, ...]]:
        shipped_skills, observations = self._shipped.snapshot_catalog()
        staged_skills, staged_observations = self._staged.snapshot_catalog()
        return (*shipped_skills, *(self._tag(skill) for skill in staged_skills)), (*observations, *staged_observations)


def _portable_ref(source: Path, project_root: Path) -> str:
    """Project-relative POSIX path when the source is inside the project, else absolute."""
    try:
        return source.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return source.as_posix()
