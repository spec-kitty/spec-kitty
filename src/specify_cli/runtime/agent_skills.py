"""Bootstrap user-global canonical doctrine skills."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from specify_cli.runtime.bootstrap import _get_cli_version
from specify_cli.runtime.asset_preparation import AssetPreparation, PredecessorProof, RetireProof, _GlobalAssetPreparation
from specify_cli.runtime.home import get_kittify_home
from specify_cli.core.config import AGENT_SKILL_CONFIG
from specify_cli.skills.catalog import resolve_builtin_skill_catalog
from specify_cli.skills.historical_renders import is_historical_render
from specify_cli.skills.skill_frontmatter import SKILL_FILENAME, is_shared_root, project_skill_bytes
from specify_cli.skills.paths import get_primary_global_skill_root, get_project_skill_root_for_global_root, iter_installable_agents
from specify_cli.skills.registry import CanonicalSkill, SkillRegistry
from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES
from specify_cli.tool_surface.operations import ApplyConsent, Disposition, FileState, OwnerAssessment

logger = logging.getLogger(__name__)

_VERSION_FILENAME = "agent-skills.lock"
_LOCK_FILENAME = ".agent-skills.lock"
_KEPT_STATES = frozenset({"preserve", "consent_required"})

KeptKind = Literal["stale_canonical", "edited_retired"]


@dataclass(frozen=True)
class KeptSkillFile:
    """A global skill file the sync left in place because it could not prove Spec Kitty wrote it.

    ``stale_canonical``: a file in a skill Spec Kitty ships today, so the skill stays out of
    date there. ``edited_retired``: a file in a skill Spec Kitty retired, kept because its
    bytes match no render that ever shipped. A user's own skill is neither and is not listed.
    """

    path: Path
    kind: KeptKind
    reason: str


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
    """Resolve the canonical bundled skill registry.

    Built-in only, by design: this feeds the user-global skill roots, and pack
    skills are project-root only (ADR 2026-09-27-1).
    """
    return resolve_builtin_skill_catalog()


def global_skill_names() -> frozenset[str]:
    """Names of the skills Spec Kitty ships into the user-global roots (built-in only; empty when unavailable)."""
    registry = _discover_registry()
    return frozenset(skill.name for skill in registry.discover_skills()) if registry is not None else frozenset()


def _skill_effect_owners(destination: Path, agents: tuple[str, ...]) -> tuple[str, ...]:
    """The selected agents whose global skill root holds *destination*; every selected agent for a shared file."""
    owners = tuple(
        agent
        for agent in agents
        if (agent_root := get_primary_global_skill_root(agent)) is not None and (agent_root == destination or agent_root in destination.parents)
    )
    return owners or agents


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


def _is_shared_global_root(destination_root: Path) -> bool:
    """Whether a global root (``~/.agents/skills``, ``~/.claude/skills``...) takes the spec projection.

    A root an agent resolves away from the home mirror (``$CLAUDE_CONFIG_DIR/skills``,
    #7701) is judged by that agent's project root, so it keeps its native projection.
    """
    project_root = get_project_skill_root_for_global_root(destination_root)
    if project_root is not None:
        return bool(is_shared_root(project_root))
    try:
        return bool(is_shared_root(destination_root.relative_to(Path.home()).as_posix()))
    except ValueError:
        return True


def _prepare_skill_tree(
    prepared: AssetPreparation,
    source: Path,
    destination: Path,
    skill_name: str,
    *,
    shared: bool = True,
    normalize_frontmatter: bool = True,
    prefix: str = "",
) -> None:
    """Stage *source* into *destination*; ``SKILL.md`` is projected for a shared or native root (A-M2).

    A destination file whose bytes are a render an earlier release shipped for the same
    ``<skill>/<path>`` is Spec Kitty's own output and is refreshed (#7700); any other
    existing content is preserved by :meth:`AssetPreparation.asset`.
    """
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
            _prepare_skill_tree(prepared, child, target, skill_name, shared=shared, normalize_frontmatter=False, prefix=f"{prefix}{child.name}/")
        elif child_state.kind == "file":
            data = prepared.source(child)
            if child.name == SKILL_FILENAME and normalize_frontmatter:
                data = project_skill_bytes(data, shared=shared, skill_name=skill_name)
            proof = _shipped_render_proof(skill_name, f"{prefix}{child.name}")
            prepared.asset(target, data, (child_state.mode or 0o644) & ~0o222, canonical_predecessor=proof)
        else:
            raise ValueError(f"Unsupported canonical skill source: {child}")


def _shipped_render_proof(skill_name: str, relative: str) -> PredecessorProof:
    """Proof, judged on ``asset()``'s own observation, that a destination holds a render shipped for ``<skill_name>/<relative>``."""

    def proven(before: FileState) -> bool:
        return before.kind == "file" and bool(is_historical_render(skill_name, relative, before.sha256))

    return proven


def _retired_render_proof(skill_dir: Path) -> RetireProof:
    """Byte proof for a retired skill directory: each file must be a render shipped at its own path."""

    def proven(path: Path, sha256: str | None) -> bool:
        return bool(is_historical_render(skill_dir.name, path.relative_to(skill_dir).as_posix(), sha256))

    return proven


def _classify_kept(
    dispositions: Sequence[Disposition],
    root: Path,
    skill_roots: Sequence[Path],
    canonical: frozenset[str] | set[str],
) -> tuple[KeptSkillFile, ...]:
    """Kept files of canonical and retired skills, innermost path only; custom skills are not listed."""
    found: dict[Path, KeptSkillFile] = {}
    for disposition in dispositions:
        if disposition.state not in _KEPT_STATES or disposition.path is None:
            continue
        path = root / disposition.path
        skill = _skill_of(path, skill_roots)
        if skill in canonical:
            found[path] = KeptSkillFile(path, "stale_canonical", disposition.reason)
        elif skill in RETIRED_CANONICAL_SKILL_NAMES:
            found[path] = KeptSkillFile(path, "edited_retired", disposition.reason)
    innermost = [item for path, item in found.items() if not any(other != path and path in other.parents for other in found)]
    return tuple(sorted(innermost, key=lambda item: item.path))


def _skill_of(path: Path, skill_roots: Sequence[Path]) -> str | None:
    for skill_root in skill_roots:
        if skill_root in path.parents:
            return path.relative_to(skill_root).parts[0]
    return None


def kept_global_skill_files(
    assessment: OwnerAssessment,
    *,
    canonical: frozenset[str] | set[str] | None = None,
    skill_roots: Sequence[Path] | None = None,
) -> tuple[KeptSkillFile, ...]:
    """Classify the files a global skill assessment keeps (#7700, #5983): one rule for every reporter.

    Reads the assessment's ``preserve`` / ``consent_required`` dispositions; a file of a skill
    Spec Kitty ships today is ``stale_canonical``, one of a retired skill ``edited_retired``.
    *canonical* and *skill_roots* default to the package catalog and every agent's global root,
    which is what an unselected assessment used; pass the assessment's own when it had a selection.
    """
    if canonical is None:
        canonical = global_skill_names()
    roots = _unique_global_roots() if skill_roots is None else list(skill_roots)
    return _classify_kept(assessment.dispositions, assessment.root.path, roots, canonical)


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
        prepared = AssetPreparation("global_skills", root, home / "cache", _LOCK_FILENAME, consent, known_roots=roots)
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
            shared = _is_shared_global_root(destination_root)
            for skill in skills:
                prepared.source(skill.skill_md)
                _prepare_skill_tree(prepared, skill.skill_dir, destination_root / skill.name, skill.name, shared=shared)
                prepared.prune_missing(destination_root / skill.name)
            if state.kind == "directory":
                for existing in destination_root.iterdir():
                    if existing.name not in canonical:
                        if selection is None and existing.name in RETIRED_CANONICAL_SKILL_NAMES:
                            prepared.retire(existing, proven=_retired_render_proof(existing))
                        else:
                            prepared.preserve(existing, "Unproven custom skill; preserve content and links")
        # #7700 (b): never stamp the skills current while a canonical skill file stays stale.
        stale = any(item.kind == "stale_canonical" for item in _classify_kept(prepared.dispositions, prepared.root.path, roots, {skill.name for skill in skills}))
        stamp = home / "cache" / _VERSION_FILENAME if selection is None and not stale else None
        assessment = prepared.finish(stamp, _get_cli_version())
        if agents:
            # With no agent selected (an upgrade whose agents have no user-global skill root),
            # the effects keep the owner itself as logical owner, as agent_commands does: an
            # empty owner tuple is not a valid effect. The one write then is the inventory's
            # one-time move to the #7722 layout, which keeps every record.
            effects = tuple(replace(effect, logical_owners=_skill_effect_owners(effect.destination, agents)) for effect in assessment.effects)
            assessment = replace(assessment, effects=effects)
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
    from specify_cli.runtime.asset_preparation import apply_with_reassess, assess_global_assets, startup_asset_error

    def _rebuild() -> OwnerAssessment:
        return assess_global_assets(runtime=False, commands=False)

    assessment = _rebuild()
    if not assessment.complete:
        raise startup_asset_error(assessment.owner_key, assessment.diagnostics)
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
        raise startup_asset_error(result.owner_key, result.diagnostics)
