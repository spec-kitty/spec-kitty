"""Bootstrap user-global canonical doctrine skills."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from specify_cli.runtime.bootstrap import _get_cli_version
from specify_cli.runtime.asset_preparation import AssetPreparation, _GlobalAssetPreparation
from specify_cli.runtime.home import get_kittify_home
from specify_cli.core.config import AGENT_SKILL_CONFIG
from specify_cli.skills.command_renderer import ensure_skill_frontmatter
from specify_cli.skills.paths import get_primary_global_skill_root, iter_installable_agents
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES
from specify_cli.template import get_local_repo_root
from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment

logger = logging.getLogger(__name__)

_VERSION_FILENAME = "agent-skills.lock"
_LOCK_FILENAME = ".agent-skills.lock"


@dataclass(frozen=True, init=False)
class GlobalSkillSelection:
    """Immutable caller-resolved sources and agents, not a registry or replay token.

    Snapshot only CanonicalSkill's name/directory/SKILL.md identity. Its mutable
    auxiliary file lists are not retained: assessment observes the complete tree.
    Construction performs no filesystem reads; source validity is checked during
    preparation. Empty sources or agents mean no selected skill work.
    """

    _sources: tuple[tuple[str, Path, Path], ...]
    agent_keys: tuple[str, ...]

    def __init__(self, *, skills: Sequence[CanonicalSkill], agent_keys: Sequence[str]) -> None:
        sources: dict[str, tuple[str, Path, Path]] = {}
        for skill in skills:
            name = skill.name
            if not name or name in {".", ".."} or any(part in name for part in ("/", "\\", ":")):
                raise ValueError(f"Unconfined selected skill name: {name!r}")
            directory, markdown = skill.skill_dir.absolute(), skill.skill_md.absolute()
            if markdown != directory / "SKILL.md":
                raise ValueError(f"Selected SKILL.md differs from its source tree: {name}")
            source = (name, directory, markdown)
            if name in sources and sources[name] != source:
                raise ValueError(f"Conflicting selected canonical skill: {name}")
            sources[name] = source
        agents = tuple(dict.fromkeys(agent_keys))
        if any(agent not in AGENT_SKILL_CONFIG for agent in agents):
            raise ValueError("Unknown selected skill agent")
        object.__setattr__(self, "_sources", tuple(sorted(sources.values())))
        object.__setattr__(self, "agent_keys", agents)


def _discover_registry() -> SkillRegistry | None:
    """Resolve the canonical bundled skill registry."""
    try:
        registry = SkillRegistry.from_package()
        if registry.discover_skills():
            return registry
    except ModuleNotFoundError:
        logger.debug("Package skill registry unavailable", exc_info=True)

    local_repo = get_local_repo_root()
    if local_repo is not None:
        registry = SkillRegistry.from_local_repo(local_repo)
        if registry.discover_skills():
            return registry

    return None


def _unique_global_roots(agent_keys: tuple[str, ...] | None = None) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()

    for agent_key in iter_installable_agents() if agent_keys is None else agent_keys:
        root = get_primary_global_skill_root(agent_key)
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append(root)

    return roots


def _retired_skill_cleanup_needed() -> bool:
    for root in _unique_global_roots():
        for skill_name in RETIRED_CANONICAL_SKILL_NAMES:
            dest = root / skill_name
            if dest.exists() or dest.is_symlink():
                return True
    return False


def _prepare_skill_tree(
    prepared: AssetPreparation,
    source: Path,
    destination: Path,
    skill_name: str,
    *,
    normalize_frontmatter: bool = True,
) -> None:
    state = prepared.observe(source, members=True)
    if state.kind != "directory":
        raise ValueError(f"Required skill directory unavailable: {source}")
    # #4017 rescope: ``destination`` is this owner's OWN managed tree, never
    # a source read -- see the identical rationale on the top-level
    # ``destination_root`` probe in ``assess_global_agent_skills``. Without
    # this tag, this RECURSIVE call would re-walk and un-upgrade (role
    # tagging only ever upgrades to "source_read", never back) the SAME
    # ancestors that call already correctly tagged.
    if prepared.observe(destination, role="destination_probe").kind not in {"directory", "absent"}:
        prepared.preserve(destination, "Unproven canonical skill path replacement")
        return
    # Package directory modes are not portable through every installer.
    prepared.asset(destination, None, 0o755)
    for child in sorted(source.iterdir()):
        child_state = prepared.observe(child)
        target = destination / child.name
        if child_state.kind == "directory":
            _prepare_skill_tree(prepared, child, target, skill_name, normalize_frontmatter=False)
        elif child_state.kind == "file":
            data = prepared.source(child)
            if child.name == "SKILL.md" and normalize_frontmatter:
                data = ensure_skill_frontmatter(data.decode("utf-8"), skill_name).encode("utf-8")
            prepared.asset(target, data, (child_state.mode or 0o644) & ~0o222)
        else:
            raise ValueError(f"Unsupported canonical skill source: {child}")


def _observe_registry_catalog(prepared: AssetPreparation, skills: list[CanonicalSkill]) -> None:
    """Retain catalog membership, including directories not yet valid skills."""
    catalog_roots = {skill.skill_dir.parent for skill in skills}
    if len(catalog_roots) != 1:
        raise ValueError("Canonical skill registry must have one source root")
    catalog_root = next(iter(catalog_roots))
    if prepared.observe(catalog_root, members=True).kind != "directory":
        raise ValueError("Canonical skill catalog is not a regular directory")
    discovered = set()
    for child in sorted(catalog_root.iterdir()):
        state = prepared.observe(child, members=True)
        if state.kind == "symlink":
            raise ValueError(f"Unproven canonical skill source link: {child}")
        if state.kind == "directory" and prepared.observe(child / "SKILL.md").kind == "file":
            discovered.add(child.name)
    if discovered != {skill.name for skill in skills}:
        raise ValueError("Canonical skill catalog changed during discovery")


def _load_registry_skills(prepared: AssetPreparation) -> list[CanonicalSkill]:
    registry = _discover_registry()
    if registry is None:
        raise ValueError("Required canonical skill registry unavailable")
    skills: list[CanonicalSkill] = registry.discover_skills()
    if not skills:
        raise ValueError("Required canonical skill registry is empty")
    _observe_registry_catalog(prepared, skills)
    return skills


def assess_global_agent_skills(
    *,
    consent: ApplyConsent = ApplyConsent(),
    selection: GlobalSkillSelection | None = None,
    _batch: _GlobalAssetPreparation | None = None,
) -> OwnerAssessment:
    """Prepare complete global skill trees without writes or marker shortcuts.

    Global callers, including project installers, must delegate this exact
    assessment once; project copy/manifest/backup policy stays in the installer.
    None uses the package catalog and all agents. An explicit selection keeps
    caller sources/agents and never stamps or retires unrelated global skills.
    """
    from specify_cli.runtime.asset_preparation import build_serialized, global_asset_root, incomplete

    home = get_kittify_home()
    agents = (
        tuple(iter_installable_agents())
        if selection is None
        else tuple(agent for agent in selection.agent_keys if get_primary_global_skill_root(agent) is not None)
    )
    roots = tuple(_unique_global_roots(agents))
    root = global_asset_root("global_skills", (home, *roots))

    def _build() -> tuple[AssetPreparation, OwnerAssessment]:
        prepared = AssetPreparation("global_skills", root, home / "cache", _LOCK_FILENAME, consent)
        skills = (
            _load_registry_skills(prepared)
            if selection is None
            else [CanonicalSkill(name, directory, markdown) for name, directory, markdown in selection._sources]
        )
        for destination_root in roots:
            # #4017 rescope: this owner's OWN managed destination root, never
            # a source read. Observing it (and its ancestors, incl. a parent
            # like ``~/.agents`` auto-created by a LATER ``parents()`` call)
            # without this tag defaults to "source_read" (``observe()``'s
            # default role) -- role-tagging only ever UPGRADES to
            # "source_read" and never downgrades back, so an untagged probe
            # here permanently poisons this whole tree's role, making a
            # concurrent peer's legitimate destination materialization look
            # like unretractable source drift instead of tolerable benign
            # drift (FR-002/C-002).
            state = prepared.observe(destination_root, members=True, role="destination_probe")
            if state.kind not in {"directory", "absent"}:
                prepared.preserve(destination_root, "Unproven global skill root replacement")
                continue
            canonical = {skill.name for skill in skills}
            for skill in skills:
                prepared.source(skill.skill_md)
                _prepare_skill_tree(prepared, skill.skill_dir, destination_root / skill.name, skill.name)
                prepared.prune_missing(destination_root / skill.name)
            if state.kind == "directory":
                for existing in destination_root.iterdir():
                    if existing.name not in canonical:
                        if selection is None and existing.name in RETIRED_CANONICAL_SKILL_NAMES:
                            prepared.retire(existing)
                        else:
                            prepared.preserve(existing, "Unproven custom skill; preserve content and links")
        assessment = prepared.finish(home / "cache" / _VERSION_FILENAME if selection is None else None, _get_cli_version())
        effects = []
        for effect in assessment.effects:
            logical = tuple(
                agent
                for agent in agents
                if (agent_root := get_primary_global_skill_root(agent)) is not None
                and (agent_root == effect.destination or agent_root in effect.destination.parents)
            )
            effects.append(replace(effect, logical_owners=logical or agents))
        assessment = replace(assessment, effects=tuple(effects))
        return prepared, assessment

    try:
        # #4017 rescope: escalate ONLY the local build (never `_batch.include()`,
        # called once below on the stabilized result) so an escalated rebuild
        # can never replay stale partial mutations into a shared, cross-owner
        # batch.
        prepared, assessment = build_serialized(_build, logger=logger)
        if _batch is not None:
            _batch.include(prepared, assessment.effects)
        return assessment
    except (OSError, ValueError, UnicodeError) as exc:
        return incomplete("global_skills", root, exc)


def ensure_global_agent_skills() -> None:
    """Repair actual canonical skill health and retain unchanged assets.

    Mirrors ``bootstrap.ensure_runtime()``'s re-assess-under-lock (#4017
    WP03) via the shared ``asset_preparation.apply_with_reassess`` helper
    (#4174 landing-pass) -- see its docstring for the full mechanism.
    """
    from specify_cli.runtime.asset_preparation import apply_with_reassess, assess_global_assets

    def _rebuild() -> OwnerAssessment:
        return assess_global_assets(runtime=False, commands=False)

    assessment = _rebuild()
    if not assessment.complete:
        raise RuntimeError("; ".join(d.message for d in assessment.diagnostics))
    if not assessment.effects:
        return
    result = apply_with_reassess(
        assessment,
        _rebuild,
        ApplyConsent(automatic=True),
        converged_log_message="global agent skills already materialized by a concurrent peer; nothing applied.",
        logger=logger,
    )
    if result.outcome not in {"applied", "skipped"}:
        raise RuntimeError("; ".join(d.message for d in result.diagnostics))
