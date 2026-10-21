"""Org-pack discovery + charter-level doctrine selection (WP06 T029, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file). Covers configured org-pack path enumeration, the shared raw
``org-charter.yaml`` reader, the ``required_<kind>`` union, and the
charter-level :class:`~charter.activation.schemas.GovernanceCharterConfig` resolver that
folds org-required selections into the project's own selection.

Cycle note: :func:`_iter_org_charter_docs` and
:func:`_read_org_required_selections` are already consumed by
``context_renderers/activation_block.py`` and
``context_renderers/selection_block.py`` via a function-local
``from charter.activation.context import ...`` (breaking the load-time cycle a
top-level import would create, since ``charter.activation.context`` imports this
module for its re-export shim). That precedent is unaffected by this
relocation — ``charter.activation.context`` continues to re-export both names.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.schemas import GovernanceCharterConfig
from charter.activation.skill_preparation import SkillPreparationError, require_valid_skill_namespace
from charter.offering.artifact_kinds import SELECTION_OVERLAYABLE_KIND_FIELDS, ArtifactKind
from kernel.charter_pack_paths import pack_org_charter

__all__ = [
    # `_enumerate_org_pack_paths` retired from __all__ (#3520 chain fold): its
    # only cross-module callers (the executor + action-bundle first-match loops)
    # were deleted when the DRG became chain-aware; it stays a module-internal
    # (still used by the helpers below).
    "RequiringPack",
    "_iter_org_charter_docs",
    "_load_governance_charter_config",
    "_missing_pack_diagnostic",
    "_read_org_required_selections",
    "last_non_empty_token",
    "read_org_required_ids",
    "read_org_required_provenance",
    "read_org_required_tokens",
    "read_org_skill_namespace",
    "require_org_skill_policy_readable",
    "union_required_tokens",
]


_LOGGER = logging.getLogger(__name__)


#: Artifact-kind suffixes for which an org pack may declare a
#: ``required_<kind>`` list (mirrors
#: :data:`charter.activation.org_charter.REQUIRED_KIND_FIELDS`).  Kept
#: as a local constant inside the charter layer so we can do the
#: cross-pack union without importing ``specify_cli`` (preserves the
#: kernel <- charter.offering <- charter <- specify_cli dependency direction).
#:
#: Derived from the :attr:`ArtifactKind.selection_overlayable` fact: the kinds
#: whose org ``required_<kind>`` list unions into a ``selected_<kind>`` field of
#: ``GovernanceCharterConfig``. This is deliberately a strict subset of the
#: org-requirable kinds (``glossary_pack`` and ``asset`` carry a
#: ``required_<kind>`` list but no ``selected_<kind>`` overlay). Declaration
#: order of :class:`ArtifactKind` is preserved.
_REQUIRED_KIND_FIELDS: tuple[str, ...] = SELECTION_OVERLAYABLE_KIND_FIELDS


def _enumerate_org_pack_paths(repo_root: Path) -> list[tuple[str, Path]]:
    """Return configured ``(pack_name, local_path)`` pairs.

    The shared parser lives in ``charter.offering.drg.org_pack_config`` so charter,
    DRG composition, and specify_cli registry paths consume one config
    contract.
    """
    try:
        from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415
    except ImportError:
        return []
    try:
        registry = load_pack_registry(repo_root)
    except Exception:  # noqa: BLE001 - context rendering stays best-effort
        _LOGGER.debug(
            "load_pack_registry raised while enumerating org pack paths for %s; treating as no configured packs.",
            repo_root,
            exc_info=True,
        )
        return []
    return [(pack.name, pack.effective_root(repo_root)) for pack in registry.packs]


def _enumerate_org_pack_paths_strict(repo_root: Path) -> list[tuple[str, Path]]:
    """Like :func:`_enumerate_org_pack_paths`, but a registry that cannot be established raises.

    The lenient sibling answers an invalid registry, an unset ``${VAR}`` in a pack path or a
    subdir escape with "no configured packs"; a caller that must not mistake "unknown" for
    "none" (skill preparation) reads through this one. Raises :class:`ValueError` (pydantic
    ``ValidationError`` included, :class:`~charter.offering.drg.org_pack_config.OrgPackEnvVarUnsetError`
    and ``OrgPackSubdirEscapeError`` too) with the cause in its message.
    """
    from charter.offering.drg.org_pack_config import load_pack_registry  # noqa: PLC0415

    return [(pack.name, pack.effective_root(repo_root)) for pack in load_pack_registry(repo_root, strict=True).packs]


def _missing_pack_diagnostic(repo_root: Path) -> str | None:
    """Return a human-readable diagnostic when an org pack is missing on disk.

    Per FR-015 (Mission B WP06), a consumer whose ``.kittify/config.yaml``
    references a pack whose ``local_path`` does not exist on disk MUST
    surface a loud diagnostic at context-resolution time.  Returns ``None``
    when every configured pack exists (or no packs are configured).

    The diagnostic is rendered into the bootstrap text by
    :func:`~charter.activation.context.build_charter_context` so the operator sees the
    error in the prompt body — exactly what
    ``test_case_2_consumer_without_fetched_pack_fails_loudly`` pins.
    """
    missing: list[tuple[str, Path]] = []
    for name, local_path in _enumerate_org_pack_paths(repo_root):
        if not local_path.exists():
            missing.append((name, local_path))
    if not missing:
        return None
    lines = [
        "Charter Context Error:",
        "  - Charter Pack(s) referenced in .kittify/config.yaml do NOT exist on disk:",
    ]
    for name, local_path in missing:
        lines.append(f"    - pack `{name}`: local_path `{local_path}` does not exist")
    lines.append("  - Run `spec-kitty charter fetch --pack <name>` to populate the pack, or remove the entry from .kittify/config.yaml.")
    return "\n".join(lines)


#: One ``org-charter.yaml`` document of the walk: ``(declared_pack, member_pack, raw)``.
OrgCharterDoc = tuple[str, str, dict[str, Any]]


def _strict_error(message: str) -> Exception:
    """The strict floor read's refusal (FR-013): the activation layer's configuration error."""
    from charter.activation.activation_ledger import ActiveCharterConfigError  # noqa: PLC0415 — keeps the import graph acyclic

    error: Exception = ActiveCharterConfigError(
        f"{message}\nThe org required floor cannot be read, so nothing was changed. Fix the org pack, or run `spec-kitty doctor charter-packs`."
    )
    return error


def _declared_org_packs(repo_root: Path, *, strict: bool) -> list[tuple[str, Path]]:
    if not strict:
        return _enumerate_org_pack_paths(repo_root)
    try:
        return _enumerate_org_pack_paths_strict(repo_root)
    except ValueError as exc:
        raise _strict_error(f"The org pack registry in .kittify/config.yaml cannot be read: {exc}") from exc


def _load_org_charter_doc(name: str, pack_path: Path, *, strict: bool) -> dict[str, Any] | None:
    """The parsed ``org-charter.yaml`` of one pack; ``None`` when it requires nothing (or, lenient, cannot be read)."""
    if strict and not pack_path.is_dir():
        raise _strict_error(f"org pack {name!r} is declared but its path is not an existing directory ({pack_path}); run `spec-kitty charter fetch --pack {name}`.")
    charter_path = pack_org_charter(pack_path)
    if not charter_path.exists():
        return None
    try:
        raw = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    except (OSError, YAMLError, ValueError) as exc:
        if strict:
            raise _strict_error(f"cannot read {charter_path} of org pack {name!r}: {exc}") from exc
        return None
    if not isinstance(raw, dict):
        if strict:
            raise _strict_error(f"{charter_path} of org pack {name!r} is not a YAML mapping.")
        return None
    return raw


def _chain_members(declared: str, docs: dict[str, dict[str, Any]], *, strict: bool) -> list[str]:
    """*declared* first, then its ``extends:`` bases nearest first, via the canonical resolver.

    Lenient: a cycle or a dangling base falls back to *declared* alone (today's flat read).
    """
    from charter.offering.packs.extends import ExtendsBaseNotFoundError, ExtendsCycleError, resolve_extends_order  # noqa: PLC0415 — lazy: keeps the offering packs subpackage off this module's load path (context renderers import it)

    edges = {name: (str(raw["extends"]) if raw.get("extends") else None) for name, raw in docs.items()}
    try:
        order = resolve_extends_order(declared, edges)
    except (ExtendsCycleError, ExtendsBaseNotFoundError) as exc:
        if strict:
            raise _strict_error(f"the extends: chain of org pack {declared!r} is invalid: {exc}") from exc
        return [declared]
    return list(reversed(order))


def _iter_org_charter_docs(repo_root: Path, *, strict: bool = False) -> list[OrgCharterDoc]:
    """Return ``(declared_pack, member_pack, raw)`` for every declared pack and its ``extends:`` chain.

    The single raw reader (FR-006, R3) behind the required floor, the
    ``required_<kind>`` overlay, the org activations and the skill namespace.
    Each declared pack yields itself first (``member == declared``), then the
    bases its ``extends:`` chain inherits, nearest first, resolved once through
    :func:`charter.offering.packs.extends.resolve_extends_order`. A reader that
    wants each pack once filters ``declared == member``.

    Lenient (default): a pack whose ``org-charter.yaml`` is absent, unreadable
    or not a mapping is skipped, and a bad ``extends:`` chain falls back to the
    declared pack alone (the loud diagnostic for a missing pack directory is
    :func:`_missing_pack_diagnostic`). Strict (FR-013): an unreadable registry,
    a declared pack that is not a directory, an unreadable or non-mapping
    ``org-charter.yaml`` and a cycling or dangling ``extends:`` raise
    :class:`~charter.activation.activation_ledger.ActiveCharterConfigError`; a
    pack without an ``org-charter.yaml`` requires nothing.
    """
    declared = _declared_org_packs(repo_root, strict=strict)
    docs: dict[str, dict[str, Any]] = {}
    for name, pack_path in declared:
        raw = _load_org_charter_doc(name, pack_path, strict=strict)
        if raw is not None:
            docs.setdefault(name, raw)
    out: list[OrgCharterDoc] = []
    for name, _path in declared:
        if name in docs:
            out.extend((name, member, docs[member]) for member in _chain_members(name, docs, strict=strict))
    return out


def _declared_docs(repo_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Each declared pack's own document once, declaration order (no ``extends:`` members)."""
    return [(declared, raw) for declared, member, raw in _iter_org_charter_docs(repo_root) if declared == member]


def union_required_tokens(into: list[str], items: Iterable[object]) -> None:
    """Union *items* into *into*: stripped, non-empty, first-seen order.

    THE merge rule for every ``required_<kind>`` field. The charter-layer
    readers below and ``charter.activation.org_charter`` (which folds parsed
    policies) both call it, so there is one owner of the semantics.
    """
    for item in items:
        token = str(item).strip()
        if token and token not in into:
            into.append(token)


def last_non_empty_token(current: str | None, candidate: object) -> str | None:
    """Last-non-empty-wins fold step for ``skill_namespace``.

    Used by :func:`read_org_skill_namespace` (charter layer) and by
    ``charter.activation.org_charter`` when it folds parsed policies. ``org_name``
    follows the same rule but is still open-coded in ``org_charter.py``.
    """
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return current


def _read_org_required_selections(repo_root: Path) -> dict[str, list[str]]:
    """Union every org pack's ``required_<kind>`` across packs and their ``extends:`` chains.

    Reads the shared :func:`_iter_org_charter_docs` walk (lenient) and returns a
    ``{kind: [ids...]}`` map covering the kinds listed in
    :data:`_REQUIRED_KIND_FIELDS`. Union preserves first-seen order. The overlay
    reads the same iterator as the required floor (D-18), so a requirement
    inherited through ``extends:`` is selected too.
    """
    out: dict[str, list[str]] = {kind: [] for kind in _REQUIRED_KIND_FIELDS}
    for _declared, _member, raw in _iter_org_charter_docs(repo_root):
        for kind in _REQUIRED_KIND_FIELDS:
            value = raw.get(f"required_{kind}")
            if isinstance(value, list):
                union_required_tokens(out[kind], value)
    return out


def read_org_required_ids(repo_root: Path, kind: ArtifactKind) -> list[str]:
    """Union every org pack's ``required_<plural>`` for one *kind*, first-seen order (lenient).

    Unlike :func:`_read_org_required_selections` this is not limited to the
    selection-overlayable kinds: it serves ``required_skills``, which has no
    ``selected_skills`` overlay. A malformed (non-list) value is skipped.
    """
    field = f"required_{kind.plural}"
    out: list[str] = []
    for _declared, _member, raw in _iter_org_charter_docs(repo_root):
        value = raw.get(field)
        if isinstance(value, list):
            union_required_tokens(out, value)
    return out


@dataclass(frozen=True)
class RequiringPack:
    """One org pack that requires an id (data-model.md §4).

    ``pack`` is the chain member whose own ``org-charter.yaml`` lists the id;
    ``via`` is the declared pack whose ``extends:`` chain inherits it
    (``None`` when ``pack`` is itself the declared pack).
    """

    pack: str
    via: str | None = None

    def describe(self) -> str:
        """``'base'`` or ``'base' (via 'overlay')``."""
        return f"{self.pack!r}" if self.via is None else f"{self.pack!r} (via {self.via!r})"


def _required_values(raw: dict[str, Any], field: str, member: str, *, strict: bool) -> list[str]:
    value = raw.get(field)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        if strict:
            raise _strict_error(f"`{field}` in the org-charter.yaml of org pack {member!r} must be a list of ids.")
        return []
    return [item.strip() for item in value if item.strip()]


def _stem_normaliser(repo_root: Path, kind: ArtifactKind) -> Callable[[list[str]], list[str]]:
    """Map raw ``required_<plural>`` ids to activation stems (the promotion path's normaliser)."""
    from charter.activation.layer_roots import resolve_layer_roots, resolve_pack_chain  # noqa: PLC0415 — lazy: only needed once a required id must be normalised
    from charter.activation.org_charter import _best_effort_offering_root, _normalize_required_ids  # noqa: PLC0415 — lazy: org_charter imports this module (cycle)

    offering_root = _best_effort_offering_root()
    org_roots = resolve_pack_chain(repo_root, strict=False)
    layer_roots = resolve_layer_roots(repo_root)

    def normalise(raw_ids: list[str]) -> list[str]:
        stems: list[str] = _normalize_required_ids(kind.plural, raw_ids, offering_root=offering_root, org_roots=org_roots, layer_roots=layer_roots, warnings=[])
        return stems

    return normalise


def _required_by_requirer(repo_root: Path, kind: ArtifactKind, *, strict: bool) -> list[tuple[RequiringPack, list[str]]]:
    """Each requiring pack with its raw ``required_<plural>`` ids, from the one iterator."""
    field = f"required_{kind.plural}"
    out: list[tuple[RequiringPack, list[str]]] = []
    for declared, member, raw in _iter_org_charter_docs(repo_root, strict=strict):
        ids = _required_values(raw, field, member, strict=strict)
        if ids:
            out.append((RequiringPack(member, None if member == declared else declared), ids))
    return out


def read_org_required_tokens(repo_root: Path, kind: ArtifactKind, *, strict: bool) -> list[str]:
    """The required floor of *kind* as the raw ids the packs list (any spelling), first-seen order.

    Same iterator and the same strict refusals as :func:`read_org_required_provenance`,
    without the stem normalisation: a reader that compares in identity space
    (``activation_ledger._effective_deny``) resolves each spelling itself, so the
    read path skips the costly normaliser (NFR-003).
    """
    out: list[str] = []
    for _requirer, ids in _required_by_requirer(repo_root, kind, strict=strict):
        union_required_tokens(out, ids)
    return out


def read_org_required_provenance(repo_root: Path, kind: ArtifactKind, *, strict: bool) -> dict[str, tuple[RequiringPack, ...]]:
    """The required floor of *kind* with provenance: stem -> the packs that require it (R3, FR-013).

    The union of ``required_<plural>`` over every declared org pack and each
    pack's ``extends:`` chain, read by :func:`_iter_org_charter_docs`. Ids are
    normalised to activation stems with the promotion path's normaliser.
    Precedence never decides membership (C-005). With *strict* an unreadable or
    malformed declared pack, a cycle or a dangling base raises
    :class:`~charter.activation.activation_ledger.ActiveCharterConfigError`;
    the answer is never silently widened.
    """
    raw_by_requirer = _required_by_requirer(repo_root, kind, strict=strict)
    if not raw_by_requirer:
        return {}
    normalise = _stem_normaliser(repo_root, kind)
    provenance: dict[str, list[RequiringPack]] = {}
    for requirer, ids in raw_by_requirer:
        for stem in dict.fromkeys(normalise(ids)):
            entries = provenance.setdefault(stem, [])
            if requirer not in entries:
                entries.append(requirer)
    return {stem: tuple(entries) for stem, entries in provenance.items()}


def read_org_skill_namespace(repo_root: Path) -> str | None:
    """Return the org ``skill_namespace`` (last non-empty value across packs wins).

    Folds with :func:`last_non_empty_token`, the same helper
    ``charter.activation.org_charter`` uses (single owner of the rule). Every
    value read is checked against the skill-namespace grammar; an invalid one
    raises :class:`~charter.activation.skill_preparation.SkillPreparationError`.
    """
    namespace: str | None = None
    for name, raw in _declared_docs(repo_root):
        namespace = last_non_empty_token(namespace, raw.get("skill_namespace"))
        if namespace is not None:
            require_valid_skill_namespace(namespace, f"fix `skill_namespace` in org pack {name!r}'s org-charter.yaml")
    return namespace


def require_org_skill_policy_readable(repo_root: Path, *, org_decides: bool) -> None:
    """Refuse a configured org pack whose skill policy cannot be established.

    Skill preparation's strict read: the lenient readers above treat "cannot read"
    as "nothing required", which would retire installed pack skills. The pack
    registry itself is read strictly (an invalid ``.kittify/config.yaml`` block, an
    unset ``${VAR}`` in a pack path or a subdir escape raises instead of reading as
    "no packs"). A configured pack whose path is not an existing directory is always
    refused (naming the remedy). When *org_decides* (the project has no
    ``activated_skills`` list, so the org packs' ``required_skills`` are the in-force
    set), an ``org-charter.yaml`` that is unreadable, empty, not a mapping, or carries
    a ``required_skills`` that is not a list of strings is refused too. A pack without
    an ``org-charter.yaml``, or one that is a mapping without ``required_skills``,
    requires nothing, which is a legitimate "no longer required".
    """
    yaml = YAML(typ="safe")
    for name, pack_path in _enumerate_org_pack_paths_strict(repo_root):
        if not pack_path.is_dir():
            raise SkillPreparationError(
                f"org pack {name!r} is configured but its path is not an existing directory ({pack_path}); "
                f"run `spec-kitty charter fetch --pack {name}`, or remove the pack from .kittify/config.yaml"
            )
        charter_path = pack_org_charter(pack_path)
        if org_decides and charter_path.exists():
            _require_readable_required_skills(yaml, name, charter_path)


def _require_readable_required_skills(yaml: YAML, pack_name: str, charter_path: Path) -> None:
    try:
        raw = yaml.load(charter_path.read_text(encoding="utf-8"))
    except (OSError, YAMLError, ValueError) as exc:
        raise SkillPreparationError(f"cannot read {charter_path} of org pack {pack_name!r}, so its required skills are unknown: {exc}") from exc
    if raw is None:
        # A zero-byte charter is never an authored state: the pack that supplied an installed skill
        # needed a namespace from it. "Required nothing" is an authored mapping that omits the key.
        raise SkillPreparationError(f"{charter_path} of org pack {pack_name!r} is empty, so its required skills are unknown")
    if not isinstance(raw, dict):
        raise SkillPreparationError(f"{charter_path} of org pack {pack_name!r} is not a YAML mapping, so its required skills are unknown")
    required = raw.get("required_skills")
    if required is not None and not (isinstance(required, list) and all(isinstance(item, str) for item in required)):
        raise SkillPreparationError(f"`required_skills` in {charter_path} of org pack {pack_name!r} must be a list of skill ids")


def _load_governance_charter_config(repo_root: Path) -> GovernanceCharterConfig:
    """Return the charter's :class:`GovernanceCharterConfig` for *repo_root*.

    Best-effort lookup: a failure (missing governance.yaml, parse error,
    unexpected exception) collapses to a default-constructed
    :class:`GovernanceCharterConfig`. A retired shape (``RetiredPackFieldError``,
    or the retired ``governance.doctrine`` key as ``ActiveCharterConfigError``)
    propagates instead, so its selections are never dropped in silence.  This keeps the resolver hot path
    resilient (NFR-005) so a malformed governance file never crashes
    prompt rendering — the authority-paths block will simply lack
    charter-declared entries.

    Mission B WP06: after loading the charter-level selection, this
    helper UNIONs every org pack's ``required_<kind>`` into the matching
    ``selected_<kind>`` field.  Org-required artifacts therefore reach
    the prompt without the operator having to mirror them in the
    project's own ``governance.yaml`` (FR-003 / FR-008).  The union is
    non-destructive: project-selected ids are preserved and org-required
    additions append in first-seen order across packs.
    """

    from charter.activation.pack_context import ActiveCharterConfigError
    from charter.activation.sync import load_governance_config
    from charter.offering.packs.retired_fields import RetiredPackFieldError

    try:
        governance = load_governance_config(repo_root)
        selection = governance.charter
    except (RetiredPackFieldError, ActiveCharterConfigError):
        # A retired shape is not a parse failure: never dropped in silence (#3732, FR-011).
        raise
    except Exception:  # noqa: BLE001 — best-effort governance load
        selection = GovernanceCharterConfig()

    from charter.activation.pack_context import load_denied  # noqa: PLC0415 — pack_context imports this module (cycle)

    org_required = _read_org_required_selections(repo_root)
    denied = dict(load_denied(repo_root))
    if not any(org_required.values()) and not denied:
        return selection

    # Sel(k) = (selected_k | R(k)) - D*(k) (US1.6): merge per kind, preserving
    # project-selected order and appending new org-required ids, then subtract
    # the effective deny (which never holds a required id). We rebuild the
    # model via ``model_copy`` to keep the original instance immutable for
    # callers that hold a reference.
    updates: dict[str, list[str]] = {}
    for kind in _REQUIRED_KIND_FIELDS:
        field_name = f"selected_{kind}"
        current = list(getattr(selection, field_name, []) or [])
        merged = current + [token for token in org_required[kind] if token not in current]
        deny = denied.get(kind)
        if deny:
            merged = [token for token in merged if deny.admits(token)]
        if merged != current:
            updates[field_name] = merged
    if not updates:
        return selection
    return selection.model_copy(update=updates)
