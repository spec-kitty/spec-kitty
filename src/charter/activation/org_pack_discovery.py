"""Org-pack discovery + charter-level doctrine selection (WP06 T029, #2532).

Relocated verbatim from ``charter.activation.context`` (single-owner, no-net-growth for
that file). Covers configured org-pack path enumeration, the shared raw
``org-charter.yaml`` reader, the ``required_<kind>`` union, and the
charter-level :class:`~charter.activation.schemas.DoctrineSelectionConfig` resolver that
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
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.schemas import DoctrineSelectionConfig
from charter.offering.artifact_kinds import SELECTION_OVERLAYABLE_KIND_FIELDS

__all__ = [
    # `_enumerate_org_pack_paths` retired from __all__ (#3520 chain fold): its
    # only cross-module callers (the executor + action-bundle first-match loops)
    # were deleted when the DRG became chain-aware; it stays a module-internal
    # (still used by the helpers below).
    "_iter_org_charter_docs",
    "_load_doctrine_selection",
    "_missing_pack_diagnostic",
    "_read_org_required_selections",
]


_LOGGER = logging.getLogger(__name__)


#: Artifact-kind suffixes for which an org pack may declare a
#: ``required_<kind>`` list (mirrors
#: :data:`specify_cli.doctrine.org_charter.REQUIRED_KIND_FIELDS`).  Kept
#: as a local constant inside the charter layer so we can do the
#: cross-pack union without importing ``specify_cli`` (preserves the
#: kernel <- doctrine <- charter <- specify_cli dependency direction).
#:
#: Derived from the :attr:`ArtifactKind.selection_overlayable` fact: the kinds
#: whose org ``required_<kind>`` list unions into a ``selected_<kind>`` field of
#: ``DoctrineSelectionConfig``. This is deliberately a strict subset of the
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
        "  - Doctrine pack(s) referenced in .kittify/config.yaml do NOT exist on disk:",
    ]
    for name, local_path in missing:
        lines.append(f"    - pack `{name}`: local_path `{local_path}` does not exist")
    lines.append("  - Run `spec-kitty doctrine fetch --pack <name>` to populate the pack, or remove the entry from .kittify/config.yaml.")
    return "\n".join(lines)


def _iter_org_charter_docs(repo_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(pack_name, raw_dict)`` for every pack's parsed ``org-charter.yaml``.

    Single shared raw-rescan reader (FR-006) consumed by BOTH
    :func:`_read_org_required_selections` (``required_<kind>``, the
    established precedent) and :func:`_read_org_activations`
    (``activations:``, WP01) so the fix does not leave a third
    hand-rolled rescan copy — the exact duplication class that caused
    #2365.

    Packs whose ``org-charter.yaml`` is absent, unreadable, or does not
    parse to a YAML mapping are silently skipped here — the loud
    diagnostic for a missing *pack directory* is produced by
    :func:`_missing_pack_diagnostic` upstream. This reader only decides
    "can I hand the caller a parsed document"; whether individual
    entries within that document are then valid is each caller's own
    concern (e.g. :func:`_read_org_activations` raises on a malformed
    ``activations:`` entry per FR-004 — a different failure class than
    "the YAML file itself didn't parse").
    """
    yaml = YAML(typ="safe")
    docs: list[tuple[str, dict[str, Any]]] = []
    for name, pack_path in _enumerate_org_pack_paths(repo_root):
        charter_path = pack_path / "org-charter.yaml"
        if not charter_path.exists():
            continue
        try:
            raw = yaml.load(charter_path.read_text(encoding="utf-8"))
        except (OSError, YAMLError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        docs.append((name, raw))
    return docs


def _read_org_required_selections(repo_root: Path) -> dict[str, list[str]]:
    """Union every org pack's ``required_<kind>`` across packs.

    Reads each configured pack's parsed ``org-charter.yaml`` (via the
    shared :func:`_iter_org_charter_docs` reader) and returns a
    ``{kind: [ids...]}`` map covering the 8 kinds listed in
    :data:`_REQUIRED_KIND_FIELDS`.  Union preserves first-seen order
    across packs (declaration-order precedence, matching the merge
    semantics of :func:`specify_cli.doctrine.org_charter.load_org_charter_policies`).
    """
    out: dict[str, list[str]] = {kind: [] for kind in _REQUIRED_KIND_FIELDS}
    for _name, raw in _iter_org_charter_docs(repo_root):
        for kind in _REQUIRED_KIND_FIELDS:
            value = raw.get(f"required_{kind}")
            if not isinstance(value, list):
                continue
            for item in value:
                token = str(item).strip()
                if token and token not in out[kind]:
                    out[kind].append(token)
    return out


def _load_doctrine_selection(repo_root: Path) -> DoctrineSelectionConfig:
    """Return the charter's :class:`DoctrineSelectionConfig` for *repo_root*.

    Best-effort lookup: any failure (missing governance.yaml, parse
    error, unexpected exception) collapses to a default-constructed
    :class:`DoctrineSelectionConfig`.  This keeps the resolver hot path
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

    from charter.activation.sync import load_governance_config

    try:
        governance = load_governance_config(repo_root)
        selection = governance.charter
    except Exception:  # noqa: BLE001 — best-effort governance load
        selection = DoctrineSelectionConfig()

    org_required = _read_org_required_selections(repo_root)
    if not any(org_required.values()):
        return selection

    # Merge per-kind, preserving project-selected order and appending new
    # org-required ids.  Pydantic models default to mutable list fields
    # so in-place ``extend`` is fine; we still rebuild the model via
    # ``model_copy`` to keep the original instance immutable for callers
    # that hold a reference.
    updates: dict[str, list[str]] = {}
    for kind in _REQUIRED_KIND_FIELDS:
        field_name = f"selected_{kind}"
        current = list(getattr(selection, field_name, []) or [])
        additions = [token for token in org_required[kind] if token not in current]
        if additions:
            updates[field_name] = current + additions
    if not updates:
        return selection
    return selection.model_copy(update=updates)
