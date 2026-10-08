"""Charter offering template discovery + DRG addressing (#1333, FR-033/034).

Templates are the one :class:`~charter.offering.artifact_kinds.ArtifactKind` that is
resolved *specially*: they live in mission-scoped tier directories
(``<missions_root>/<mission>/templates/`` and ``.../command-templates/``),
carry no dedicated extension/glob (``ArtifactKind.TEMPLATE`` has an empty
glob), and have no frontmatter ``id:`` field. Their identity therefore derives
purely from the existing **tier + mission + filename** layout — no
template-file frontmatter churn (plan §8, contract C4.5).

This module adds three things on top of the existing 6-tier
:mod:`charter.offering.resolver` chain:

1. :func:`discover_templates` — a discovery surface that enumerates templates
   across tiers/missions, annotating each with its source tier. Same-named
   templates in two different missions become two **distinct** refs (mission
   qualifies identity). Tier roots are supplied **as data** (C-008): the
   caller resolves and passes them; this module never reaches into
   ``.kittify`` or ``~/.kittify`` itself.

2. :func:`template_node` / :func:`template_nodes` — mint
   :class:`~charter.offering.drg.models.DRGNode` records of kind
   :attr:`~charter.offering.drg.models.NodeKind.TEMPLATE` with mission-qualified URNs
   ``template:<mission>/<name>`` so templates are addressable in the
   (layer-merged, WP03) DRG. Nodes are emitted as *data* the merge /
   aggregation layer can include; this module does not import ``charter`` or
   ``specify_cli`` (layer rule, zero upward dependency).

3. :func:`resolve_template_by_id` — maps a ``<mission>/<name>`` template ID
   back through :func:`charter.offering.resolver.resolve_template`, honouring the full
   6-tier precedence (override > legacy > org > global-mission > global > package).
   This is what WP17's ``charter context --include template:<id>`` calls; WP16's
   ``charter list --all`` consumes :func:`discover_templates`.

Layering
--------
``charter.offering`` is zero-dependency upward: this module imports only from
``charter.offering`` and ``kernel``. It MUST NOT import ``charter`` or ``specify_cli``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from charter.offering.drg.models import DRGNode, NodeKind
from charter.offering.resolver import ResolutionResult, ResolutionTier, resolve_template

__all__ = [
    "TemplateRef",
    "TierRoot",
    "discover_templates",
    "template_id_for",
    "template_node",
    "template_nodes",
    "template_urn",
    "resolve_template_by_id",
]

#: Per-mission template subdirectories scanned by discovery. Both ``templates``
#: (content templates, e.g. ``spec-template.md``) and ``command-templates``
#: (slash-command bodies, e.g. ``implement.md``) live mission-scoped.
_TEMPLATE_SUBDIRS: tuple[str, ...] = ("templates", "command-templates")

#: Files that exist in template directories but are not themselves templates.
_NON_TEMPLATE_FILES: frozenset[str] = frozenset({"README.md"})


@dataclass(frozen=True)
class TierRoot:
    """A resolution-tier root supplied to discovery **as data** (C-008).

    The caller is responsible for resolving these paths (the offering
    never reaches into ``.kittify`` / ``~/.kittify`` on its own). Each root
    points at a *missions root* — a directory whose immediate children are
    per-mission directories, each of which may contain ``templates/`` and
    ``command-templates/`` subdirectories.

    Attributes:
        tier: The resolution tier this root represents (used for annotation
            and for ordering when the same template appears in multiple tiers).
        missions_root: Directory containing per-mission template trees.
        project_dir: Optional project root (the directory containing
            ``.kittify/``). When supplied on any root, it lets
            :func:`resolve_template_by_id` delegate to the live
            :func:`charter.offering.resolver.resolve_template` 6-tier chain.
    """

    tier: ResolutionTier
    missions_root: Path
    project_dir: Path | None = None


@dataclass(frozen=True)
class TemplateRef:
    """A single discovered template, mission-qualified.

    Attributes:
        template_id: Mission-qualified identity ``"<mission>/<name>"``
            (e.g. ``"software-dev/spec-template.md"``). This is the stable
            handle ``charter list``/``context`` use; the leading ``<mission>``
            segment disambiguates same-named templates across missions.
        mission: Mission name (e.g. ``"software-dev"``).
        name: Template filename, including extension where present
            (e.g. ``"spec-template.md"``).
        tier: Source resolution tier (override > … > package).
        path: Absolute path to the template file on disk.
    """

    template_id: str
    mission: str
    name: str
    tier: ResolutionTier
    path: Path


def template_id_for(mission: str, name: str) -> str:
    """Return the mission-qualified template ID ``"<mission>/<name>"``."""
    return f"{mission}/{name}"


def template_urn(template_id: str) -> str:
    """Return the DRG URN for a template ID: ``template:<mission>/<name>``."""
    return f"{NodeKind.TEMPLATE.value}:{template_id}"


def _iter_mission_dirs(missions_root: Path) -> list[tuple[str, Path]]:
    """Yield ``(mission_name, mission_dir)`` pairs under *missions_root*.

    Robust to a missing or non-directory root (returns an empty list) so the
    caller can pass tier roots that may not exist on a given machine
    (e.g. ``~/.kittify`` before ``spec-kitty migrate``).
    """
    if not missions_root.is_dir():
        return []
    return sorted(
        (child.name, child)
        for child in missions_root.iterdir()
        if child.is_dir()
    )


def _iter_template_files(mission_dir: Path) -> list[Path]:
    """Return template files under a mission directory's template subdirs.

    Walks both ``templates/`` and ``command-templates/``. Does **not** assume a
    flat ``built-in/*.<suffix>`` layout or a dedicated extension — templates
    have an empty glob (``ArtifactKind.TEMPLATE``), so every regular file is a
    candidate. ``README.md`` and other non-template files are filtered out.
    Nested directories (e.g. ``documentation/templates/divio/``) are walked
    recursively so deeply-nested templates are still discovered.
    """
    files: list[Path] = []
    for subdir in _TEMPLATE_SUBDIRS:
        tpl_dir = mission_dir / subdir
        if not tpl_dir.is_dir():
            continue
        for path in sorted(tpl_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name in _NON_TEMPLATE_FILES:
                continue
            files.append(path)
    return files


def discover_templates(*, tier_roots: list[TierRoot]) -> list[TemplateRef]:
    """Enumerate templates across the supplied tier roots.

    Each :class:`TierRoot` is walked for per-mission ``templates/`` and
    ``command-templates/`` directories; every regular file found becomes a
    :class:`TemplateRef` annotated with its source tier. The same template
    *name* under two different missions yields two distinct refs (mission
    qualifies identity). The same ``<mission>/<name>`` appearing in multiple
    tiers is **deduplicated to the highest-precedence tier** (the first tier in
    ``tier_roots`` order wins), mirroring how :func:`charter.offering.resolver` would
    resolve it.

    Args:
        tier_roots: Tier roots in precedence order (override first, package
            last). Supplied as data by the caller (C-008).

    Returns:
        List of :class:`TemplateRef`, sorted by ``(template_id, tier)`` for
        deterministic output.
    """
    seen: dict[str, TemplateRef] = {}
    for root in tier_roots:
        for mission, mission_dir in _iter_mission_dirs(root.missions_root):
            for path in _iter_template_files(mission_dir):
                name = path.name
                tid = template_id_for(mission, name)
                if tid in seen:
                    # Higher-precedence tier already won (tier_roots is ordered).
                    continue
                seen[tid] = TemplateRef(
                    template_id=tid,
                    mission=mission,
                    name=name,
                    tier=root.tier,
                    path=path,
                )
    return sorted(seen.values(), key=lambda r: (r.template_id, r.tier.value))


def template_node(ref: TemplateRef) -> DRGNode:
    """Mint a DRG node for a discovered template.

    The node carries kind :attr:`NodeKind.TEMPLATE` and a mission-qualified URN
    ``template:<mission>/<name>``. Cross-mission same-named templates therefore
    mint **distinct** nodes. The node is returned as data for the WP03 merge /
    aggregation layer to include; this function performs no merge itself.

    Args:
        ref: A template reference from :func:`discover_templates`.

    Returns:
        A :class:`DRGNode` with a validated ``template:`` URN.
    """
    return DRGNode(
        urn=template_urn(ref.template_id),
        kind=NodeKind.TEMPLATE,
        label=ref.template_id,
    )


def template_nodes(refs: list[TemplateRef]) -> list[DRGNode]:
    """Mint DRG nodes for many discovered templates (see :func:`template_node`)."""
    return [template_node(ref) for ref in refs]


def resolve_template_by_id(
    template_id: str,
    *,
    tier_roots: list[TierRoot],
) -> ResolutionResult:
    """Resolve a ``<mission>/<name>`` template ID through the 6-tier chain.

    Splits *template_id* into ``mission`` and ``name`` and delegates to
    :func:`charter.offering.resolver.resolve_template`, so the existing 6-tier
    precedence (override > legacy > org > global-mission > global > package) is
    honoured rather than re-implemented. This is the resolution surface WP17's
    ``charter context --include template:<id>`` calls.

    The project root (the directory containing ``.kittify/``) is taken from the
    first :class:`TierRoot` that carries a ``project_dir``. When no tier root
    supplies one, resolution still works for the global/package tiers because
    :func:`resolve_template` skips the project-scoped override/legacy tiers
    when their files are absent; a synthetic, non-existent project dir is used
    so those tiers are simply skipped.

    Args:
        template_id: Mission-qualified template ID ``"<mission>/<name>"``.
        tier_roots: Tier roots supplied as data (C-008); used to locate the
            project root for the override/legacy tiers.

    Returns:
        The :class:`ResolutionResult` for the highest-precedence template.

    Raises:
        ValueError: If *template_id* is not of the form ``<mission>/<name>``.
        FileNotFoundError: If the template is not found at any tier.
    """
    if "/" not in template_id:
        raise ValueError(
            f"template_id {template_id!r} is not of the form '<mission>/<name>'"
        )
    mission, name = template_id.split("/", 1)
    if not mission or not name:
        raise ValueError(
            f"template_id {template_id!r} is not of the form '<mission>/<name>'"
        )

    project_dir = next(
        (root.project_dir for root in tier_roots if root.project_dir is not None),
        None,
    )
    if project_dir is None:
        # No project root supplied: the override/legacy tiers (which live under
        # ``<project_dir>/.kittify``) are simply skipped because their files
        # will not exist under a non-existent path. Global + package tiers
        # still resolve normally.
        project_dir = Path("/nonexistent-spec-kitty-project")

    return resolve_template(name, project_dir, mission)
