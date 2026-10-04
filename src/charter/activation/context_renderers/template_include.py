"""``--include`` template/directive/tactic/generic-artifact renderers (WP05, #2532).

Relocated verbatim from ``charter.activation.context`` (T024, single-owner extraction so
that shared, WP-contended file does not grow). These six renderers back the
``build_charter_context_include`` orchestrator (which stays in ``context.py``):
each one resolves and formats a single ``--include <kind>:<id>`` selector.

* :func:`_render_template_include` — ``template:<mission>/<name>`` (WP18/FR-034).
* :func:`_render_directive_include` / :func:`_render_tactic_include` — take the
  narrow ``directives``/``tactics`` repository directly (not the whole
  service), matching the WP04 typing pass.
* :func:`_render_generic_artifact_include` — the best-effort ``artifact:<id>``
  probe that fans out across every bare-probeable kind.
* :func:`_render_doctrine_artifact_include` — the shared renderer for the
  remaining (non-directive/tactic) doctrine artifact kinds.

``_default_missions_root`` is a private helper consumed only by
:func:`_render_template_include` in this module and stays un-exported.

charter-sync-sonar-remediation-01KZPPZW WP02 (Sonar S3776) additionally
relocated ``build_charter_context_include``'s per-selector-kind dispatch
bodies here — ``_render_section_include_selector``, ``_resolve_include_kind``,
``_render_agent_profile_include_selector``,
``_render_catalog_kind_include_selector`` — for the same reason as the
original six: keeping the WP-contended orchestrator's own cognitive
complexity (and ``context.py``'s independently-enforced 600-line ceiling)
under their respective gates. The orchestrator itself (branch *selection*)
stays in ``context.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from charter.activation._doctrine_paths import resolve_project_root
from charter.bundle import CHARTER_MD
from charter.activation.context_json import _bundle_root_for_json
from charter.activation.context_renderers.artifact_bodies import (
    _format_full_artifact_payload_body,
    _format_inline_agent_profile_body,
    _format_inline_directive_body,
    _format_inline_paradigm_body,
    _format_inline_procedure_body,
    _format_inline_skill_body,
    _format_inline_step_contract_body,
    _format_inline_styleguide_body,
    _format_inline_tactic_body,
    _format_inline_toolguide_body,
)
from charter.activation.context_renderers.section_bodies import render_critical_section_include
from charter.offering.drg.migration.id_normalizer import normalize_directive_id

if TYPE_CHECKING:
    import charter.offering.service as _doctrine_service_module
    from charter.offering.artifact_kinds import ArtifactKind

    from charter.repository_protocol import ArtifactRepository

__all__ = [
    "_render_agent_profile_include_selector",
    "_render_catalog_kind_include_selector",
    "_render_doctrine_artifact_include",
    "_render_generic_artifact_include",
    "_render_section_include_selector",
    "_render_template_include",
    "_resolve_include_kind",
]


def _render_template_include(
    repo_root: Path,
    identifier: str,
    selector: str,
) -> str:
    """Render a ``template:<mission>/<name>`` selector via WP18 (FR-034).

    Resolves the mission-qualified template ID through the doctrine
    6-tier chain (:func:`charter.offering.template_catalog.resolve_template_by_id`)
    and renders the resolved template file's content. The project root
    (the directory containing ``.kittify/``) is supplied as data so the
    project-scoped override/legacy tiers participate in resolution.

    Fails closed on malformed pack configuration: a
    :class:`charter.activation.pack_context.CharterPackConfigError` raised while
    resolving the project root is re-raised rather than swallowed, matching
    WP12's fail-closed contract for the context entry point.
    """
    from charter.offering.resolver import ResolutionTier
    from charter.offering.template_catalog import TierRoot, resolve_template_by_id

    project_root = resolve_project_root(repo_root)

    tier_roots = [
        TierRoot(
            tier=ResolutionTier.PACKAGE_DEFAULT,
            missions_root=_default_missions_root(),
            project_dir=project_root,
        )
    ]
    try:
        result = resolve_template_by_id(identifier, tier_roots=tier_roots)
    except FileNotFoundError as exc:
        raise ValueError(f"No template found for selector '{selector}'.") from exc
    except ValueError as exc:
        raise ValueError(f"Malformed template selector '{selector}': {exc}") from exc

    try:
        content = result.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Template for selector '{selector}' could not be read: {exc}") from exc

    return "\n".join(
        [
            f"Template {identifier} (tier: {result.tier.value}):",
            content.rstrip("\n"),
        ]
    )


def _default_missions_root() -> Path:
    """Return the doctrine-bundled missions root (PACKAGE_DEFAULT tier)."""
    from charter.offering.missions import MissionTemplateRepository

    return MissionTemplateRepository.default_missions_root()


def _render_directive_include(directives: ArtifactRepository[Any], identifier: str, selector: str) -> str:
    """Render a directive selector for ``--include``.

    Takes the ``directives`` repository directly (not the whole service) —
    that is the only attribute this renderer needs (WP04 typing pass).

    Normalize before repository lookup because the activation service exposes a
    mapping-shaped repository whose ``get`` performs exact-key lookup. This keeps
    slug, numeric, and canonical selector forms at parity (#3816).
    """

    directive_id = normalize_directive_id(identifier)
    directive = directives.get(directive_id)
    if directive is None:
        raise ValueError(f"No directive found for selector '{selector}'.")
    directive_id = getattr(directive, "id", directive_id)
    title = getattr(directive, "title", directive_id)
    return "\n".join(
        [
            f"Directive {directive_id}: {title}",
            *_format_inline_directive_body(directive),
            *_format_full_artifact_payload_body(directive),
        ]
    )


def _render_tactic_include(tactics: ArtifactRepository[Any], identifier: str, selector: str) -> str:
    """Render a tactic selector for ``--include``.

    Takes the ``tactics`` repository directly (not the whole service) — that
    is the only attribute this renderer needs (WP04 typing pass).
    """

    tactic = tactics.get(identifier)
    if tactic is None:
        raise ValueError(f"No tactic found for selector '{selector}'.")
    name = getattr(tactic, "name", identifier)
    return "\n".join(
        [
            f"Tactic {identifier}: {name}",
            *_format_inline_tactic_body(tactic),
            *_format_full_artifact_payload_body(tactic),
        ]
    )


def _render_generic_artifact_include(service: _doctrine_service_module.DoctrineService, identifier: str) -> str:
    """Resolve a best-effort ``artifact:<id>`` selector emitted by activations."""

    from charter.offering.artifact_kinds import _NON_AUGMENTATION_ELIGIBLE_KINDS, ArtifactKind

    # Derive the candidate kinds from the canonical ArtifactKind set rather
    # than re-declaring a parallel tuple (R-009 / CC-4). Members of the
    # canonical ``_NON_AUGMENTATION_ELIGIBLE_KINDS`` set are excluded: both
    # ``TEMPLATE`` (mission-qualified ``<mission>/<name>`` IDs) and ``ASSET``
    # (loose-contract kind, FR-005/FR-011) are not addressable by a bare
    # ``artifact:<id>`` probe. This is the single canonical exclusion set
    # (WP06) — no private single-member ``is not TEMPLATE`` check may be
    # re-declared here or elsewhere in the charter cascade.
    matches: list[tuple[str, str]] = []
    for candidate_kind in (member.value for member in ArtifactKind if member not in _NON_AUGMENTATION_ELIGIBLE_KINDS):
        selector = f"{candidate_kind}:{identifier}"
        try:
            rendered: str | None
            if candidate_kind == "directive":
                rendered = _render_directive_include(service.directives, identifier, selector)
            elif candidate_kind == "tactic":
                rendered = _render_tactic_include(service.tactics, identifier, selector)
            else:
                rendered = _render_doctrine_artifact_include(service, candidate_kind, identifier)
        except ValueError:
            continue
        if rendered is not None:
            matches.append((candidate_kind, rendered))

    if not matches:
        raise ValueError(f"No artifact found for selector 'artifact:{identifier}'.")
    if len(matches) > 1:
        kinds = ", ".join(kind for kind, _text in matches)
        raise ValueError(f"Ambiguous artifact selector 'artifact:{identifier}' matched kinds: {kinds}.")
    return matches[0][1]


def _format_inline_glossary_pack_body(pack: object) -> list[str]:
    """Render a glossary pack's description + term list for ``--include`` (FR-006).

    Defensive ``getattr`` access keeps the renderer decoupled from the concrete
    :class:`~doctrine.glossary_packs.models.GlossaryPack` shape and total across
    optional fields.
    """
    lines: list[str] = []
    description = getattr(pack, "description", None)
    if description:
        lines.append(f"  {description}")
    for term in getattr(pack, "terms", None) or []:
        surface = getattr(term, "surface", "")
        definition = getattr(term, "definition", "")
        lines.append(f"  - {surface}: {definition}")
    return lines


def _render_doctrine_artifact_include(
    service: object,
    kind: str,
    identifier: str,
) -> str | None:
    """Render non-directive/tactic doctrine artifacts addressed by ``--include``."""
    from charter.offering.artifact_kinds import CHARTER_ACTIVATABLE_KINDS

    renderers = {
        "glossary_pack": (
            "glossary_packs",
            "Glossary pack",
            "id",
            _format_inline_glossary_pack_body,
        ),
        "paradigm": (
            "paradigms",
            "Paradigm",
            "name",
            _format_inline_paradigm_body,
        ),
        "styleguide": (
            "styleguides",
            "Styleguide",
            "title",
            _format_inline_styleguide_body,
        ),
        "toolguide": (
            "toolguides",
            "Toolguide",
            "title",
            _format_inline_toolguide_body,
        ),
        "procedure": (
            "procedures",
            "Procedure",
            "name",
            _format_inline_procedure_body,
        ),
        "agent_profile": (
            "agent_profiles",
            "Agent profile",
            "name",
            _format_inline_agent_profile_body,
        ),
        "mission_step_contract": (
            "mission_step_contracts",
            "Mission step contract",
            "action",
            _format_inline_step_contract_body,
        ),
        "skill": (
            "skills",
            "Skill",
            "title",
            _format_inline_skill_body,
        ),
    }
    renderer = renderers.get(kind)
    if renderer is None:
        # FR-006 / SC-003: a charter-activatable kind with no dedicated inline
        # renderer (notably ``anti_pattern``, which ships no standalone artifact
        # files — its nodes live inside graph fragments) is still a RECOGNISED
        # selector kind: resolve it to the standard not-found rather than
        # returning ``None``, which the caller turns into the "Unsupported
        # --include selector kind" error. Recognition is derived from the single
        # charter-activatable kind authority so a future kind cannot silently
        # become "unsupported". Non-activatable kinds (``template``, ``asset``)
        # still return ``None`` -> unsupported.
        if kind in {member.value for member in CHARTER_ACTIVATABLE_KINDS}:
            raise ValueError(f"No {kind} found for selector '{kind}:{identifier}'.")
        return None

    repo_attr, label, title_attr, body_formatter = renderer
    repo = getattr(service, repo_attr, None)
    artifact = repo.get(identifier) if repo is not None else None
    if artifact is None:
        raise ValueError(f"No {kind} found for selector '{kind}:{identifier}'.")
    title = getattr(artifact, title_attr, identifier)
    return "\n".join(
        [
            f"{label} {identifier}: {title}",
            *body_formatter(artifact),
            *_format_full_artifact_payload_body(artifact),
        ]
    )


def _render_section_include_selector(
    repo_root: Path,
    selector: str,
    identifier: str,
    action: str | None,
) -> str:
    """Render the ``section:<id>`` selector — a charter.md heading lookup."""
    canonical_root = _bundle_root_for_json(repo_root)
    charter_path = canonical_root / CHARTER_MD
    if not charter_path.exists():
        raise ValueError("No charter.md found for section selector.")
    charter_content = charter_path.read_text(encoding="utf-8")
    section = render_critical_section_include(
        charter_content,
        identifier,
        action=action.strip().lower() if action else None,
    )
    if section is None:
        raise ValueError(f"No charter section found for selector '{selector}'.")
    return str(section)


def _resolve_include_kind(kind: str, selector: str) -> ArtifactKind:
    """Resolve *kind* to its canonical :class:`~charter.offering.artifact_kinds.ArtifactKind`.

    Raises ``ValueError`` (not the raw doctrine exception) when the
    operator-facing ``mission-type`` token is used — mission types are not
    addressable governance artifacts.
    """
    from charter.offering.artifact_kinds import ArtifactKind, MissionTypeNotAnArtifactKind

    try:
        return ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind as exc:
        raise ValueError(
            f"--include does not support the 'mission-type' selector (selector {selector!r}); mission types are not addressable governance artifacts."
        ) from exc


def _render_agent_profile_include_selector(
    # object (not DoctrineService): the caller forwards either the plain or the
    # activation-aware service (charter.activation.resolver.DoctrineService, an unrelated
    # class), and this only forwards it to _render_doctrine_artifact_include(service: object).
    gated_service: object,
    canonical_kind: str,
    identifier: str,
    selector: str,
) -> str:
    """Render an ``agent-profile:<id>`` selector via the activation-aware service.

    Takes the already-built *gated_service* (not ``repo_root``/``org_roots``)
    so the caller — ``charter.activation.context.build_charter_context_include`` — stays
    the sole call site of
    :func:`charter.activation.doctrine_service_builder._build_activation_aware_doctrine_service`.
    That preserves the existing ``context_module._build_activation_aware_doctrine_service``
    monkeypatch seam several tests rely on
    (e.g. ``tests/charter/test_context_include_activation.py``).
    """
    # For a kind with a registered renderer (agent_profile has one),
    # _render_doctrine_artifact_include renders the activated profile or
    # raises ("No agent_profile found ...") for a gated/missing one — it
    # never returns None here, so a direct return is sufficient (no dead
    # fall-through branch to guard).
    artifact_result = _render_doctrine_artifact_include(gated_service, canonical_kind, identifier)
    if artifact_result is None:
        raise ValueError(f"No {canonical_kind} found for selector '{selector}'.")
    return artifact_result


def _render_catalog_kind_include_selector(
    service: _doctrine_service_module.DoctrineService,
    canonical_kind: str,
    identifier: str,
    selector: str,
) -> str | None:
    """Render a directive/tactic/generic-artifact selector on the unwrapped service.

    Takes the already-built *service* (not ``repo_root``/``org_roots``) so the
    caller stays the sole call site of
    :func:`charter.activation.doctrine_service_builder._build_doctrine_service` — see
    :func:`_render_agent_profile_include_selector` for why that matters.

    Returns ``None`` when *canonical_kind* has no registered include renderer
    (the caller raises the "unsupported kind" error using the original,
    pre-resolution *kind* token for a user-facing message).
    """
    from charter.offering.artifact_kinds import ArtifactKind

    if canonical_kind == ArtifactKind.DIRECTIVE.value:
        return _render_directive_include(service.directives, identifier, selector)
    if canonical_kind == ArtifactKind.TACTIC.value:
        return _render_tactic_include(service.tactics, identifier, selector)
    return _render_doctrine_artifact_include(service, canonical_kind, identifier)
