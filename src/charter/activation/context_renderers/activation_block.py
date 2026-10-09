"""Activation-registry rendering (WP05, #2532; originally WP04 T023 / FR-007).

Relocated verbatim from ``charter.activation.context``: the org∪project activation-entry
union (:func:`_load_governance_activations`, :func:`_read_org_activations`,
:func:`_union_activations`) plus the call-site wrapper
(:func:`_render_activation_block`) that ``bootstrap_text.py``'s
``_render_bootstrap_text`` calls.

Only :func:`_render_activation_block` has an external caller
(``bootstrap_text.py``, cross-module); the other three are consumed solely by
that function within this module and stay private, matching the
``reference_pointers.py`` precedent.

Cycle note: :func:`_read_org_activations` needs
``charter.activation.context._iter_org_charter_docs`` — that helper is part of the
org-pack-discovery cluster, which stays in ``charter.activation.context`` until a later
WP relocates it. A function-local import breaks the load-time cycle a
top-level import would create (``charter.activation.context`` imports this module for
its re-export shim), mirroring the existing lazy-import precedent already
used throughout ``charter.activation.context``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from charter.activation.activations import ActivationEntry, _activation_identity_key

if TYPE_CHECKING:
    from pathlib import Path

    from charter.activation.schemas import GovernanceCharterConfig

__all__ = [
    "_render_activation_block",
]


_LOGGER = logging.getLogger(__name__)


def _load_governance_activations(repo_root: Path) -> list[ActivationEntry]:
    """Best-effort load of ``GovernanceConfig.activations`` for *repo_root*.

    The activation registry is a top-level governance field (per
    :mod:`charter.activation.activations`).  We isolate the load here so the call
    site in :func:`_render_bootstrap_text` stays small and a parse failure
    collapses to an empty list (mirrors :func:`_load_governance_charter_config`'s
    resilience pattern). A retired shape is not a parse failure and is never
    dropped in silence (#3732, FR-011): a retired pack field
    (``RetiredPackFieldError``) or the retired ``governance.doctrine`` key
    (``ActiveCharterConfigError``) propagates, naming its remedy.
    """
    from charter.activation.pack_context import ActiveCharterConfigError
    from charter.activation.sync import load_governance_config
    from charter.offering.packs.retired_fields import RetiredPackFieldError

    try:
        governance = load_governance_config(repo_root)
    except (RetiredPackFieldError, ActiveCharterConfigError):
        raise
    except Exception:  # noqa: BLE001 — best-effort governance load
        return []
    return list(governance.activations)


def _read_org_activations(repo_root: Path) -> list[ActivationEntry]:
    """Union every org pack's ``activations:`` entries (FR-001/002/004).

    Mirrors :func:`_read_org_required_selections`'s union/order shape
    (first-seen across packs in config order, via the shared
    :func:`_iter_org_charter_docs` reader) but deliberately does NOT
    mirror its silent-skip error handling (C-002 override): a
    structurally malformed entry in a *present* pack's ``activations:``
    list RAISES via ``ActivationEntry.model_validate`` (FR-004), naming
    the offending pack so the operator can locate it (SC-003). A pack
    whose ``org-charter.yaml`` is missing or unreadable is skipped by
    :func:`_iter_org_charter_docs` upstream — that is a different,
    non-raising failure class (the pack was never a parseable document
    to begin with).

    Deduplication across packs (and against the project-local list) is
    NOT performed here — :func:`_union_activations` owns identity-key
    dedup for the merged project+org list (SC-002).
    """
    from charter.activation.context import _iter_org_charter_docs  # noqa: PLC0415 — breaks a load-time cycle (see module docstring)

    entries: list[ActivationEntry] = []
    for name, raw in _iter_org_charter_docs(repo_root):
        value = raw.get("activations")
        if not isinstance(value, list):
            continue
        for item in value:
            try:
                entries.append(ActivationEntry.model_validate(item))
            except ValidationError as exc:
                raise ValueError(
                    f"org pack `{name}` declares a malformed activations entry "
                    f"{item!r}: {exc}"
                ) from exc
    return entries


def _union_activations(
    project_activations: list[ActivationEntry],
    org_activations: list[ActivationEntry],
) -> list[ActivationEntry]:
    """Union *project_activations* and *org_activations*, deduped by identity.

    Mirrors :func:`_read_org_required_selections`'s union/order
    semantics: first-seen wins on the shared 4-tuple identity key
    (:func:`charter.activation.activations._activation_identity_key`), project
    entries are processed first so project first-seen order is
    preserved, and org entries are appended in their own first-seen
    order for anything not already present (SC-002). This is NOT
    ``_fold_policies``'s extends-chain last-wins semantics.
    """
    seen: set[tuple[str, str, str, str]] = set()
    merged: list[ActivationEntry] = []
    for entry in (*project_activations, *org_activations):
        key = _activation_identity_key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    return merged


def _render_activation_block(
    _charter_config: GovernanceCharterConfig | None,
    repo_root: Path | None,
    service: object,
    *,
    mission_type: str,
    action: str,
) -> str:
    """Call the WP05 activation-stanza renderer with the runtime context.

    WP04 owns the wire; WP05 owns the body.  This helper centralises the
    boilerplate (governance load + safe-call) so the call site in
    :func:`_render_bootstrap_text` is a single line.

    ``_charter_config`` is accepted (and always passed positionally by
    every caller — see ``bootstrap_text.py`` and the test seams below) but
    not read here: the WP05 stanza renderer draws its selection state from
    *service*/*mission_type*/*action* instead. Kept in the signature to
    match the call-site shape shared with the sibling
    :func:`_render_selection_block` wire.

    WP01 (#2365) adds the org∪project resolve-time union: the org read
    (:func:`_read_org_activations`) is a SEPARATE call from the project
    load, not folded inside :func:`_load_governance_activations` (that
    function has its own best-effort ``except: return []`` which would
    swallow the FR-004 validation raise). Both calls — and the union —
    happen BEFORE the ``if not activations`` short-circuit below (so an
    org-only match still renders, SC-001) and before the ``try`` around
    the renderer call (so the FR-004 raise escapes to
    :func:`build_charter_context` instead of being caught by the
    defensive ``except Exception`` a few lines down).

    Returns ``""`` when the activation list is empty, when the WP05
    renderer is still a stub, or when any error is raised by the
    renderer (defensive — the prompt build hot path must not crash).
    """
    if repo_root is None:
        return ""
    project_activations = _load_governance_activations(repo_root)
    org_activations = _read_org_activations(repo_root)
    activations = _union_activations(project_activations, org_activations)
    if not activations:
        return ""

    from charter.activation._activation_render import render_activation_stanza

    try:
        return str(render_activation_stanza(
            activations,
            service,
            mission_type=mission_type,
            action=action,
        ))
    except Exception:  # noqa: BLE001 — defensive: never crash the prompt build
        _LOGGER.warning(
            "Activation stanza renderer raised; surface omitted for action %s.",
            action,
        )
        return ""
