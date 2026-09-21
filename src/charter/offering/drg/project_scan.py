"""Project-tier ``agent_profile`` DRG-node walk (M6 / #3038).

Reusable filesystem walk that turns hand-authored project-tier agent profiles
under ``<project_root>/.kittify/doctrine/agent_profiles/`` into
``agent_profile:<profile-id>`` :class:`~charter.offering.drg.models.DRGNode` objects, so
they can be composed into the project overlay ``graph.yaml`` the charter cascade
reads. The composing caller
(:func:`charter.activation.synthesizer.project_drg.emit_project_layer`) applies the
additive-only / overlay-dedupe guards; this module only discovers and builds the
nodes.

Home rationale (KD-1 / C-001): the walk lives under ``charter.offering.drg`` — below
``charter`` in the dependency hierarchy (``kernel <- doctrine <- charter <-
specify_cli``) — so ``charter`` composes *down* into it and never imports
``specify_cli``. It mirrors the built-in discovery walk
(:func:`charter.offering.drg.migration.extractor._discover_built_in_nodes_in_dir`):
recursive ``*.agent.yaml`` glob, id-key ``profile-id``, ``urn =
artifact_to_urn("agent_profile", id)``, ``kind = NodeKind.AGENT_PROFILE`` — but
**fails loud** (INV-6 / NFR-002) on an unparseable file or a missing
``profile-id`` instead of silently skipping, because a project overlay node that
silently vanishes is a governance-invisible defect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.artifact_kinds import DIRECT_WRITE_KINDS, ArtifactKind, PROJECT_KIND_DIRS
from charter.offering.drg.migration.id_normalizer import artifact_to_urn
from charter.offering.drg.models import DRGEdge, DRGNode, NodeKind, Relation, is_valid_urn

# ``MalformedProjectProfileError`` is intentionally NOT exported here: it is a
# fail-loud exception meant to *propagate* (never caught inside src/), so adding
# it to ``__all__`` would trip the symbol-level dead-code gate
# (tests/architectural/test_no_dead_symbols.py). It stays a public, importable
# name on the module — tests import it directly by name.
__all__ = [
    "walk_project_agent_profile_nodes",
    "scan_project_artifacts",
    "project_reference_edges",
]

#: Provenance marker stamped on every walked node (data-model.md §"Project
#: agent_profile node"). Distinguishes project-overlay nodes from built-in /
#: org-layer nodes at merge time.
_PROJECT_PROVENANCE = "project"

#: The two accepted spellings of the profile id-key. ``profile-id`` is canonical
#: (matches the built-in walk and the authored ``*.agent.yaml`` schema);
#: ``profile_id`` is tolerated for parity with
#: :class:`charter.offering.agent_profiles.repository.AgentProfileRepository`, which
#: accepts both.
_ID_KEYS = ("profile-id", "profile_id")

_AGENT_PROFILE_KIND = ArtifactKind.AGENT_PROFILE
_AGENT_PROFILE_GLOB = _AGENT_PROFILE_KIND.glob_pattern  # "*.agent.yaml"


class MalformedProjectProfileError(ValueError):
    """A project-tier ``agent_profile`` file is unparseable or lacks a profile-id.

    Carries the offending file path so the operator can find and fix it
    (NFR-002: fail loud, name the file — never a silent skip).
    """


def _profiles_dir(project_root: Path) -> Path:
    return project_root / ".kittify" / "doctrine" / "agent_profiles"


def _load_profile_mapping(path: Path) -> dict[str, Any]:
    """Parse one ``*.agent.yaml`` into a mapping, failing loud on any defect."""
    yaml = YAML(typ="safe")
    try:
        data: Any = yaml.load(path)
    except (YAMLError, OSError) as exc:
        raise MalformedProjectProfileError(f"Project agent_profile file {path} could not be parsed: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedProjectProfileError(f"Project agent_profile file {path} does not contain a YAML mapping")
    return data


def _profile_id(data: dict[str, Any], path: Path) -> str:
    for key in _ID_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            _require_urn_safe_id(value, path)
            return value
    raise MalformedProjectProfileError(f"Project agent_profile file {path} is missing a non-empty 'profile-id' field")


def _require_urn_safe_id(profile_id: str, path: Path) -> None:
    """Fail loud (naming *path*) when *profile_id* is not URN-safe.

    The composed ``agent_profile:<profile-id>`` URN must match the DRG URN
    grammar; an id carrying a space, an embedded ``:``, or a non-ASCII
    character would otherwise reach :class:`DRGNode` and raise a raw pydantic
    ``ValidationError`` that does **not** name the offending file — breaking the
    NFR-002 "fail loud, name the file" contract for exactly the malformed values
    the walk is meant to catch.
    """
    if not is_valid_urn(artifact_to_urn(_AGENT_PROFILE_KIND.value, profile_id)):
        raise MalformedProjectProfileError(
            f"Project agent_profile file {path} has a URN-unsafe 'profile-id' "
            f"{profile_id!r}: it must form a valid 'agent_profile:<id>' URN "
            f"(lowercase/underscore-prefixed, no spaces or non-ASCII)."
        )


def _label(data: dict[str, Any]) -> str | None:
    name = data.get("name")
    return name if isinstance(name, str) and name else None


def walk_project_agent_profile_nodes(project_root: Path) -> list[DRGNode]:
    """Return one ``agent_profile`` :class:`DRGNode` per authored project profile.

    Enumerates ``<project_root>/.kittify/doctrine/agent_profiles/**/*.agent.yaml``
    (recursive, sorted for deterministic order — NFR-002) and builds a node for
    each with ``urn = agent_profile:<profile-id>``, ``kind =
    NodeKind.AGENT_PROFILE``, ``label = <name|None>`` and ``provenance =
    "project"``.

    Returns an empty list when the profiles directory does not exist (a project
    with no authored profiles is not an error). Two authored files declaring the
    **same** ``profile-id`` fail loud (naming both) rather than one silently
    winning — a dropped overlay node is the governance-invisible defect this
    walk exists to prevent. Cross-overlay dedupe against answer-driven targets
    and additive-only collision checks against built-in nodes remain the
    composing caller's responsibility.

    Raises:
        MalformedProjectProfileError: If any profile file fails to parse, is not
            a YAML mapping, lacks a non-empty ``profile-id``, carries a
            URN-unsafe ``profile-id``, or collides with another authored file on
            the same ``profile-id`` (INV-6 / NFR-002 — fail loud, name the file).
    """
    directory = _profiles_dir(project_root)
    if not directory.is_dir():
        return []

    nodes: list[DRGNode] = []
    seen_ids: dict[str, Path] = {}
    for path in sorted(directory.rglob(_AGENT_PROFILE_GLOB)):
        data = _load_profile_mapping(path)
        profile_id = _profile_id(data, path)
        if profile_id in seen_ids:
            raise MalformedProjectProfileError(
                f"Duplicate project agent_profile 'profile-id' {profile_id!r}: "
                f"declared by both {seen_ids[profile_id]} and {path}. Each "
                f"authored profile must carry a distinct profile-id so no "
                f"overlay node is silently dropped."
            )
        seen_ids[profile_id] = path
        nodes.append(
            DRGNode(
                urn=artifact_to_urn(_AGENT_PROFILE_KIND.value, profile_id),
                kind=NodeKind.AGENT_PROFILE,
                label=_label(data),
                provenance=_PROJECT_PROVENANCE,
            )
        )
    return nodes


@dataclass(frozen=True)
class ProjectArtifact:
    """An authored artifact and its validated identity; content remains user-owned."""

    path: Path
    node: DRGNode
    body: dict[str, Any]


def scan_project_artifacts(
    project_root: Path,
    *,
    paths: frozenset[Path] | None = None,
) -> tuple[ProjectArtifact, ...]:
    """Validate the five supported direct-write kinds in their canonical directories."""
    from charter.offering.agent_profiles.profile import AgentProfile
    from charter.offering.directives.models import Directive
    from charter.offering.procedures.models import Procedure
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic

    # ``schemas`` is paired positionally with the canonical DIRECT_WRITE_KINDS
    # tuple (directive → Directive, …); the ordering must stay aligned.
    schemas = (Directive, Tactic, Styleguide, Procedure, AgentProfile)
    kinds = DIRECT_WRITE_KINDS
    artifacts: list[ProjectArtifact] = []
    seen: dict[str, Path] = {}
    for kind_name, schema in zip(kinds, schemas, strict=True):
        kind = ArtifactKind(kind_name)
        directory = project_root / ".kittify" / "doctrine" / PROJECT_KIND_DIRS[kind]
        for path in sorted(directory.rglob(kind.glob_pattern)):
            if paths is not None and path not in paths:
                continue
            try:
                path.resolve().relative_to((project_root / ".kittify/doctrine").resolve())
                data = YAML(typ="safe").load(path)
                model = schema.model_validate(data)
                body = model.model_dump(mode="json", by_alias=True)
                identifier = str(body["profile-id"] if kind_name == "agent_profile" else body["id"])
                node = DRGNode(
                    urn=artifact_to_urn(kind_name, identifier), kind=NodeKind(kind_name), label=body.get("name") or body.get("title"), provenance="project"
                )
            except (ValueError, OSError, YAMLError, KeyError) as exc:
                raise ValueError(f"Invalid project {kind_name} artifact {path}: {exc}") from exc
            if node.urn in seen:
                raise ValueError(f"Duplicate project artifact {node.urn}: {seen[node.urn]} and {path}")
            seen[node.urn] = path
            artifacts.append(ProjectArtifact(path, node, body))
    return tuple(artifacts)


def project_reference_edges(
    artifacts: tuple[ProjectArtifact, ...],
    available_nodes: list[DRGNode],
) -> tuple[list[DRGEdge], tuple[str, ...]]:
    """Project authored profile references, reporting unresolved targets without phantom nodes."""
    from charter.offering.drg.migration.extractor import _project_profile_reference_edges

    universe = {node.urn: node for node in available_nodes}
    edges: dict[tuple[str, str, Relation], DRGEdge] = {}
    warnings: list[str] = []
    for artifact in artifacts:
        if artifact.node.kind is not NodeKind.AGENT_PROFILE:
            continue
        candidates: list[DRGEdge] = []
        _project_profile_reference_edges(artifact.body, artifact.node.urn, dict(universe), candidates.append)
        for entry in (artifact.body.get("collaboration") or {}).get("operating-procedures", []):
            candidates.append(DRGEdge(source=artifact.node.urn, target=artifact_to_urn("procedure", entry), relation=Relation.REQUIRES))
        for edge in candidates:
            if edge.target not in universe:
                warnings.append(
                    f"{artifact.node.urn} references unresolved {edge.target}; author or install that artifact, then repeat charter activate --cascade all."
                )
                continue
            edges[(edge.source, edge.target, edge.relation)] = edge.model_copy(update={"provenance": "project"})
    return list(edges.values()), tuple(sorted(set(warnings)))
