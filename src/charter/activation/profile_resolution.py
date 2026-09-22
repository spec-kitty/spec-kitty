"""Agent-profile resolution + module-global caches (WP06 T030, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file) — the **LAST** cluster of the ``context.py`` decomposition
(research.md Decision 7, extraction step 13). Covers the process-wide
cached built-in-only :class:`~charter.offering.agent_profiles.AgentProfileRepository`,
the per-repo charter-activation-aware profile map, the ``repo_root``-aware
resolver that picks between the two, and the FR-009 test hook
:func:`_reset_agent_profile_cache`.

FR-009 single-source cache (verified safe): ``charter.activation.context`` re-exports
:data:`_DEFAULT_AGENT_PROFILE_REPO`, :data:`_ACTIVATION_AWARE_PROFILE_MAPS`,
and :func:`_reset_agent_profile_cache` by reference — the mutable dict and
the reset function are the SAME objects whether reached via
``charter.activation.context`` or ``charter.activation.profile_resolution``, so there is no
dual-cache trap.

Cycle note: several existing tests patch ``charter.activation.context._default_agent_profile_repository``
/ ``charter.activation.context._build_activation_aware_doctrine_service`` and then
exercise this module's resolvers indirectly (via ``build_charter_context`` or
a direct call to ``_load_agent_profile``/``_activation_aware_profile_map``
re-exported from ``charter.activation.context``). Because the calling functions here now
live in a *different* module than the patched attribute, both cross-references
resolve the callee via a function-local ``from charter.activation.context import ...``
(mirroring the existing lazy-import precedent in
``context_renderers/compact_governance.py``) so ``charter.activation.context`` stays the
single test-patchable seam for both symbols, regardless of which module
physically defines them.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from charter.offering.agent_profiles import AgentProfile, AgentProfileRepository

# ``_reset_agent_profile_cache`` is intentionally *not* exported: after the
# context.py re-export shim retirement (doctrine-built-in-seam-consolidation WP06)
# its only ``src/`` importer (the shim) was removed — the remaining callers are
# tests (which import it by name) — so keeping it in ``__all__`` would trip the
# symbol-level dead-code gate. It stays a module-level name
# (``profile_resolution._reset_agent_profile_cache``); re-export it once a real
# ``src/`` consumer imports it.
__all__ = [
    "_ACTIVATION_AWARE_PROFILE_MAPS",
    "_activation_aware_profile_map",
    "_default_agent_profile_repository",
    "_existing_org_roots",
    "_load_agent_profile",
    "_normalize_directive_id",
]


_LOGGER = logging.getLogger(__name__)


# Shared, repository-cached store. ``AgentProfileRepository()`` reads YAML
# at construction; we cache the default instance so per-call cost in the
# resolver is a dict lookup (NFR-002 budget).
_DEFAULT_AGENT_PROFILE_REPO: AgentProfileRepository | None = None
# Per-repo cache of the **charter-activation-aware** profile map (org + project
# + built-in, gated by ``activated_agent_profiles``). Used whenever a repository
# root is available, including projects with no org packs. Keyed by ``repo_root``.
_ACTIVATION_AWARE_PROFILE_MAPS: dict[Path, dict[str, AgentProfile]] = {}


def _default_agent_profile_repository() -> AgentProfileRepository:
    """Return a process-wide cached **built-in-only** :class:`AgentProfileRepository`.

    The repository is constructed lazily and reused for callers without a
    repository root. Callers with a root use the activation-aware service so
    project profiles and activation restrictions apply even without org packs.
    """
    global _DEFAULT_AGENT_PROFILE_REPO
    if _DEFAULT_AGENT_PROFILE_REPO is None:
        _DEFAULT_AGENT_PROFILE_REPO = AgentProfileRepository()
    return _DEFAULT_AGENT_PROFILE_REPO


def _reset_agent_profile_cache() -> None:
    """Clear the cached profile stores (test hook)."""
    global _DEFAULT_AGENT_PROFILE_REPO
    _DEFAULT_AGENT_PROFILE_REPO = None
    _ACTIVATION_AWARE_PROFILE_MAPS.clear()


def _existing_org_roots(repo_root: Path) -> list[Path]:
    """Return on-disk org-pack roots declared in ``.kittify/config.yaml``.

    Best-effort: a missing/corrupt config yields an empty org-root list;
    project-aware resolution still runs. Imports stay charter→doctrine
    (never charter→specify_cli) so the layer rule holds.
    """
    try:
        from charter.offering.drg.org_pack_config import resolve_org_roots  # noqa: PLC0415
    except ImportError:
        return []
    try:
        return [root for root in resolve_org_roots(repo_root) if root.exists()]
    except Exception:  # noqa: BLE001 — context rendering stays best-effort
        return []


def _profiles_dict_from_service(service: object) -> dict[str, AgentProfile]:
    """Return the activation-aware service's pre-gated ``{id: profile}`` map.

    Single builder contract (R5): every activation-service builder now ALWAYS
    wraps, so ``service.agent_profiles`` is the wrapper's already-gated ``dict``.
    The empty fallback defends against a service that exposes no mapping.
    """
    attr = getattr(service, "agent_profiles", None)
    return dict(attr) if isinstance(attr, dict) else {}


def _resolve_composed(repository: AgentProfileRepository, profile_id: str) -> AgentProfile | None:
    """Resolve *profile_id* with its ``specializes_from`` lineage composed.

    Dispatch-capsule / governance-context parity with ``profiles show`` and the
    runtime bridge (#4917): those surfaces read the ungated
    :meth:`AgentProfileRepository.resolve_profile`, which unions a profile's
    ``directive-references`` / ``tactic-references`` (and the other list
    sections) up its ``specializes_from`` ancestor chain. The capsule funnel
    previously returned the raw, un-composed record via
    :meth:`AgentProfileRepository.get`, so a leaf profile that
    ``specializes_from`` a base citing directives/tactics only on the base
    rendered those sections in ``profiles show`` but dropped them from the
    capsule. Composing here closes that gap.

    Lineage is composed *below the activation grain* (the pinned
    ``resolver.py`` ``agent_profile_repository`` semantics): the traversal may
    cross into a de-activated ancestor, matching ``profiles show``. Activation
    gating on the leaf id is applied by the caller
    (:func:`_activation_aware_profile_map` / :func:`_resolve_agent_profile_record`),
    not here.

    Returns ``None`` only when the profile genuinely does not exist. On a broken
    lineage (missing parent / cycle) the raw record is returned so the
    prompt-build hot path never collapses.
    """
    raw = repository.get(profile_id)
    if raw is None:
        return None
    # Compose lineage when the store supports it; otherwise fall back to the raw
    # record. A real ``AgentProfileRepository`` always does, so production always
    # composes; the guard keeps the best-effort funnel tolerant of lightweight
    # ``get``-only profile stubs (the funnel never collapses the prompt).
    resolve = getattr(repository, "resolve_profile", None)
    if resolve is None:
        return raw
    try:
        return resolve(profile_id)
    except (KeyError, ValueError):
        _LOGGER.warning(
            "Lineage composition failed for profile '%s'; rendering the raw record without inherited sections.",
            profile_id,
        )
        return raw


def _activation_aware_profile_map(repo_root: Path, org_roots: list[Path]) -> dict[str, AgentProfile]:
    """Return (and cache) the activation-gated, lineage-composed profile map.

    Reuses :func:`~charter.activation.doctrine_service_builder._build_activation_aware_doctrine_service`
    (the FR-016 precedent) so the ``activated_agent_profiles`` three-state
    gate is honoured — never re-implemented — and threads the discovered org
    roots in as **data** (no ``specify_cli`` import, preserving the layer
    rule).

    Compose-then-filter (#4917): the wrapper's ``agent_profiles`` dict is the
    already-gated **leaf** set, and each entry is then composed through the
    ungated :attr:`agent_profile_repository` so the dispatch capsule renders the
    same ``specializes_from`` lineage that ``profiles show`` does. The gate
    still applies to the leaf id; lineage may cross into a de-activated
    ancestor (:func:`_resolve_composed`).
    """
    cached = _ACTIVATION_AWARE_PROFILE_MAPS.get(repo_root)
    if cached is not None:
        return cached
    from charter.activation.context import _build_activation_aware_doctrine_service  # noqa: PLC0415

    service = _build_activation_aware_doctrine_service(repo_root, org_roots=org_roots)
    gated = _profiles_dict_from_service(service)
    repository = getattr(service, "agent_profile_repository", None)
    profile_map: dict[str, AgentProfile] = {}
    for profile_id, raw in gated.items():
        composed = _resolve_composed(repository, profile_id) if repository is not None else None
        profile_map[profile_id] = composed if composed is not None else raw
    _ACTIVATION_AWARE_PROFILE_MAPS[repo_root] = profile_map
    return profile_map


def _resolve_agent_profile_record(profile_id: str, repo_root: Path | None) -> AgentProfile | None:
    """Resolve project, org, and built-in profiles through charter activation.

    Only callers without a repository root use the built-in-only bootstrap
    repository. Project profiles must resolve even with no organization packs.

    Every path composes ``specializes_from`` lineage via
    :func:`_resolve_composed` (#4917) so the dispatch capsule renders the same
    profile-cited sections ``profiles show`` does; the activation gate still
    applies to the leaf id.
    """
    from charter.activation.context import _default_agent_profile_repository  # noqa: PLC0415

    if repo_root is None:
        return _resolve_composed(_default_agent_profile_repository(), profile_id)
    org_roots = _existing_org_roots(repo_root)
    return _activation_aware_profile_map(repo_root, org_roots).get(profile_id)


def _load_agent_profile(profile_id: str, repo_root: Path | None = None) -> AgentProfile | None:
    """Resolve *profile_id* via the doctrine layer. Returns ``None`` on miss.

    Errors are intentionally swallowed: this helper is on the prompt-build
    hot path and must never raise into the resolver. A diagnostic is logged
    at WARNING level so operators can audit unknown profile IDs without the
    prompt collapsing.
    """
    try:
        record = _resolve_agent_profile_record(profile_id, repo_root)
    except Exception:  # noqa: BLE001 — best-effort lookup
        _LOGGER.warning(
            "Profile '%s' lookup failed; profile-cited sections will be omitted.",
            profile_id,
        )
        return None
    if record is None:
        _LOGGER.warning(
            "Profile '%s' not found; profile-cited sections omitted.",
            profile_id,
        )
    return record


def _normalize_directive_id(raw: str) -> str:
    """Normalise a directive slug like '024-locality-of-change' -> 'DIRECTIVE_024'.

    If the raw value already looks like DIRECTIVE_NNN, return as-is.

    Kept in lock-step with ``charter.offering.drg.migration.id_normalizer.normalize_directive_id``
    (a separate copy for a documented import-cycle reason): the fallback folds
    hyphens to underscores so slug-named hub directives
    (``use-c4-model-techniques`` -> ``USE_C4_MODEL_TECHNIQUES``) resolve to their
    canonical node id rather than a dangling hyphenated form (#3009).
    """
    if re.match(r"^DIRECTIVE_\d+$", raw):
        return raw
    match = re.match(r"^(\d+)", raw)
    if match:
        number = match.group(1).zfill(3)
        return f"DIRECTIVE_{number}"
    return raw.upper().replace("-", "_")
