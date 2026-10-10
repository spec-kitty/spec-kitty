"""Prepare activated pack skills for projection (ADR 2026-09-27-1, FR-008).

:func:`_prepare_skill_activations` is the charter-side half of the projection
seam: it turns the *activated* pack skills (already filtered by the
default-in-force rule) into :class:`PreparedSkill` records that the
``specify_cli`` adapter renders into project skill roots. It is pure over its
inputs -- a skill source, the activated ids, the merged DRG and the two
namespaces -- so the adapter (and tests) can call it without a project layout.
Charter never imports ``specify_cli``: a wrapper skill's ``builtin:`` target is
carried through *unresolved* and validated by the adapter against its command
set.

Precedent: :func:`charter.activation.compiler.prepare_mission_type_activations`
(a charter-owned prepare step the adapter wraps).
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from kernel.content_digest import sha256_digest
from charter.drg import DRGGraph, Relation
from charter.offering.pack_skills.models import (
    BUILTIN_TARGET_PREFIX,
    CLI_TARGET_PREFIX,
    PackSkill,
    SkillExpansion,
    skill_namespace_violation,
)
from charter.offering.pack_skills.validation import RESERVED_PREFIXES, Tier, rendered_name

__all__ = [
    # Wrapper-target prefixes, re-exported so specify_cli reaches them through
    # charter rather than importing charter.offering directly.
    "BUILTIN_TARGET_PREFIX",
    "CLI_TARGET_PREFIX",
    "InForceSkills",
    "PreparedSkill",
    "SkillPreparationError",
    "establish_in_force_skill_ids",
    "pack_skills_matter",
    "prepare_project_skill_activations",
    "require_valid_skill_namespace",
]

#: Dotted ``.kittify/config.yaml`` path of the project-tier skill namespace.
_PROJECT_NAMESPACE_CONFIG_PATH = "charter_packs.project.skill_namespace"

_ORG_NAMESPACE_REMEDY = "set `skill_namespace` in the org pack's org-charter.yaml"
_PROJECT_NAMESPACE_REMEDY = f"set `{_PROJECT_NAMESPACE_CONFIG_PATH}` in .kittify/config.yaml"


class SkillPreparationError(ValueError):
    """Activated skills cannot be prepared (missing namespace or name collision)."""


def require_valid_skill_namespace(namespace: str, remedy: str) -> str:
    """Return *namespace* unchanged, or refuse it with *remedy* (never normalises)."""
    violation = skill_namespace_violation(namespace)
    if violation is not None:
        raise SkillPreparationError(f"{violation}; {remedy}")
    return namespace


class _SkillSource(Protocol):
    """The read-only slice of :class:`PackSkillRepository` preparation needs."""

    def get(self, item_id: str) -> PackSkill | None: ...

    def source_path(self, skill_id: str) -> Path | None: ...

    def provenance_of(self, skill_id: str) -> str | None: ...

    def body_text(self, skill_id: str) -> str | None: ...


@dataclass(frozen=True)
class PreparedSkill:
    """One activated skill, ready to render.

    ``body`` is set for prompt-form skills, ``expansion`` for wrapper-form ones
    (its ``builtin:`` target is *unresolved*). ``source_hash`` is the
    ``sha256:`` digest of the canonical record, sorted ``requires``, rendered
    name and body: a changed pack source or DRG edge changes it even when the
    rendered bytes would not.
    """

    id: str
    tier: Tier
    rendered_name: str
    form: str
    body: str | None
    expansion: SkillExpansion | None
    requires: tuple[str, ...]
    source_path: Path
    source_hash: str
    skill: PackSkill


def _prepare_skill_activations(
    source: _SkillSource,
    activated_ids: Iterable[str],
    *,
    graph: DRGGraph,
    org_namespace: str | None,
    project_namespace: str | None,
    load_problems: Sequence[str] = (),
) -> list[PreparedSkill]:
    """Prepare *activated_ids* for projection, sorted by id.

    Raises :class:`SkillPreparationError` -- before returning anything -- when
    an activated id is not loadable from any pack tier (*load_problems* carries
    what the loader reported, so the refusal says why), when an org/project
    skill has no namespace to render under, when its rendered name uses a
    prefix reserved for built-in skills, or when two skills render to the same
    name.
    """
    prepared = [_prepare_one(source, skill_id, graph, org_namespace, project_namespace, load_problems) for skill_id in sorted(set(activated_ids))]
    _refuse_duplicate_names(prepared)
    return prepared


def _prepare_one(
    source: _SkillSource,
    skill_id: str,
    graph: DRGGraph,
    org_namespace: str | None,
    project_namespace: str | None,
    load_problems: Sequence[str] = (),
) -> PreparedSkill:
    skill = source.get(skill_id)
    source_path = source.source_path(skill_id)
    if skill is None or source_path is None:
        reasons = f" (the loader reported: {'; '.join(load_problems)})" if load_problems else ""
        raise SkillPreparationError(f"activated skill {skill_id!r} is not available in any pack tier{reasons}")
    tier = _tier(source.provenance_of(skill_id), skill_id)
    name = _name_for(skill_id, tier, org_namespace, project_namespace)
    body = source.body_text(skill_id)
    requires = _requires(graph, skill_id)
    return PreparedSkill(
        id=skill_id,
        tier=tier,
        rendered_name=name,
        form=skill.form,
        body=body,
        expansion=skill.expands_to,
        requires=requires,
        source_path=source_path,
        source_hash=_source_hash(skill, body, requires, name),
        skill=skill,
    )


def _tier(provenance: str | None, skill_id: str) -> Tier:
    if provenance == "builtin":
        return "builtin"
    if provenance == "org":
        return "org"
    if provenance == "project":
        return "project"
    raise SkillPreparationError(f"activated skill {skill_id!r} has unknown provenance {provenance!r}")


def _name_for(skill_id: str, tier: Tier, org_namespace: str | None, project_namespace: str | None) -> str:
    """Rendered name: bare id for built-in, ``<namespace>-<id>`` otherwise."""
    if tier == "builtin":
        return skill_id
    namespace = org_namespace if tier == "org" else project_namespace
    if not namespace:
        remedy = _ORG_NAMESPACE_REMEDY if tier == "org" else _PROJECT_NAMESPACE_REMEDY
        raise SkillPreparationError(f"{tier}-tier skill {skill_id!r} has no skill namespace to render under; {remedy}")
    require_valid_skill_namespace(namespace, _ORG_NAMESPACE_REMEDY if tier == "org" else _PROJECT_NAMESPACE_REMEDY)
    name: str = rendered_name(skill_id, namespace)
    if name.startswith(RESERVED_PREFIXES):
        raise SkillPreparationError(f"{tier}-tier skill {skill_id!r} renders as {name!r}, a prefix reserved for built-in skills {list(RESERVED_PREFIXES)}")
    return name


def _requires(graph: DRGGraph, skill_id: str) -> tuple[str, ...]:
    urn = f"skill:{skill_id}"
    return tuple(sorted({edge.target for edge in graph.edges_from(urn, Relation.REQUIRES)}))


def _source_hash(skill: PackSkill, body: str | None, requires: tuple[str, ...], name: str) -> str:
    """``sha256:`` digest of every input the rendered ``SKILL.md`` depends on.

    Canonical JSON of the record, the sorted DRG ``requires`` (rendered as the
    context preamble), the rendered name (frontmatter) and the body bytes.
    """
    inputs = {"record": skill.model_dump(mode="json"), "requires": sorted(requires), "rendered_name": name}
    canonical = json.dumps(inputs, sort_keys=True).encode("utf-8")
    return sha256_digest(canonical + b"\0" + (body or "").encode("utf-8"))


def _refuse_duplicate_names(prepared: list[PreparedSkill]) -> None:
    owners: dict[str, str] = {}
    for item in prepared:
        previous = owners.setdefault(item.rendered_name, item.id)
        if previous != item.id:
            raise SkillPreparationError(f"skills {previous!r} and {item.id!r} both render as {item.rendered_name!r}; give one a different id or namespace")


# ---------------------------------------------------------------------------
# Project-level convenience (reads the same inputs the adapter would)
# ---------------------------------------------------------------------------


def _read_project_skill_namespace(repo_root: Path) -> str | None:
    """Return ``charter_packs.project.skill_namespace`` from ``.kittify/config.yaml``, if set."""
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.is_file():
        return None
    try:
        data: Any = YAML(typ="safe").load(config_path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise SkillPreparationError(f"cannot read {config_path}: {exc}") from exc
    node: Any = data
    for key in _PROJECT_NAMESPACE_CONFIG_PATH.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    if not isinstance(node, str) or not node.strip():
        return None
    return require_valid_skill_namespace(node.strip(), _PROJECT_NAMESPACE_REMEDY)


def pack_skills_matter(repo_root: Path, *, installed_pack_skills: bool = False) -> bool:
    """Whether *repo_root* shows evidence that pack skills matter to it.

    True when a pack skill is already installed (*installed_pack_skills*, the
    caller's manifest fact) or ``activated_skills`` is an explicit non-empty list.
    A project with neither takes nothing from a pack, so the health of its org packs
    must not change what any skill path does.

    This is the one condition every skill path classifies a failed resolution by:
    when the in-force set cannot be established, a project where pack skills matter
    is refused and any other behaves as a project with no org pack. It is total: a
    project whose activation config cannot be read cannot show that nothing is
    activated, so it counts as one where pack skills matter.
    """
    from charter.activation.pack_context import explicit_activated_skills

    if installed_pack_skills:
        return True
    try:
        return bool(explicit_activated_skills(repo_root))
    except Exception:
        # Total by design, deliberately broad: whatever stops the activation config from being read, nothing
        # proves that no skill is activated, so pack skills are taken to matter (a refusal, never a retirement).
        return True


@dataclass(frozen=True)
class InForceSkills:
    """The ids of the skills in force for a project (``ids is None``: every available skill)."""

    ids: frozenset[str] | None

    @property
    def is_empty(self) -> bool:
        return self.ids is not None and not self.ids


def establish_in_force_skill_ids(repo_root: Path, *, installed_pack_skills: bool = False) -> InForceSkills:
    """Stage 1: establish WHICH skills are in force for *repo_root*, from configuration alone.

    The in-force set is the project's explicit ``activated_skills`` list (exactly that list,
    ``[]`` meaning none: an established empty set) or, when the key is absent, the org packs'
    ``required_skills`` plus the built-in defaults (none at MVP) -- the ``PackContext`` rule.
    No DRG is loaded and no skill is read here.

    When pack skills matter (:func:`pack_skills_matter`: an installed copy or a non-empty
    explicit list) the set must be *established*: a configured pack registry that is invalid,
    a pack path that is not an existing directory, or (when the org packs decide) an
    unreadable or empty ``org-charter.yaml`` or a ``required_skills`` that is not a list,
    raises instead of reading as "nothing required" -- which would retire installed skills.
    Any other project keeps the lenient reading (what it cannot read requires nothing).
    A caller classifies every failure here by :func:`pack_skills_matter`.
    """
    from charter.activation.org_pack_discovery import require_org_skill_policy_readable
    from charter.activation.pack_context import PackContext, explicit_activated_skills

    explicit = explicit_activated_skills(repo_root)
    if explicit is not None and not explicit:
        return InForceSkills(frozenset())
    if installed_pack_skills or explicit:
        require_org_skill_policy_readable(repo_root, org_decides=explicit is None)
    return InForceSkills(PackContext.from_config(repo_root).activated_skills)


def prepare_project_skill_activations(repo_root: Path, *, installed_pack_skills: bool = False, in_force: InForceSkills | None = None) -> list[PreparedSkill]:
    """Stage 2: prepare the skills in force for *repo_root*, establishing the set first when not given.

    An empty in-force set returns ``[]`` without touching any DRG, so a broken org graph never
    blocks a project that uses no pack skill. For a non-empty set, everything here is a
    refusal (:class:`SkillPreparationError` or the loaders' own errors) whatever the manifest
    holds: a skill that is in force and cannot be rendered (no namespace, a DRG that does not
    load, a record that does not load, a sibling id conflict) is never silently skipped.

    Otherwise resolves the active charter service, the merged built-in + org-chain DRG and both
    namespaces, and delegates to :func:`_prepare_skill_activations`.
    """
    from charter.activation._drg_helpers import load_validated_graph
    from charter.activation.active_charter_service_builder import build_active_charter_service
    from charter.activation.drg_activation import load_org_drg
    from charter.activation.org_pack_discovery import read_org_skill_namespace
    from charter.activation.layer_roots import resolve_pack_chain

    established = in_force if in_force is not None else establish_in_force_skill_ids(repo_root, installed_pack_skills=installed_pack_skills)
    if established.is_empty:
        return []
    service = build_active_charter_service(repo_root)
    source, load_problems = _load_skill_source(service)
    graph = load_validated_graph(
        repo_root,
        org_roots=resolve_pack_chain(repo_root, strict=False),
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    return _prepare_skill_activations(
        source,
        service.skills if established.ids is None else established.ids,
        graph=graph,
        org_namespace=read_org_skill_namespace(repo_root),
        project_namespace=_read_project_skill_namespace(repo_root),
        load_problems=load_problems,
    )


def _load_skill_source(service: Any) -> tuple[Any, list[str]]:
    """Load the raw skill repository, returning it with the problems the loader warned about.

    The pack-skill loader reports a record it cannot load (an unknown key, a
    failing tier rule) only as a ``UserWarning``. Those warnings are re-emitted
    unchanged and also returned, so a refusal for an in-force skill that did
    not load can say why.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        source = service.raw_repository("skills")
    for item in caught:
        warnings.warn_explicit(item.message, item.category, item.filename, item.lineno)
    return source, [str(item.message) for item in caught if issubclass(item.category, UserWarning)]
