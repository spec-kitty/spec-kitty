"""Reference-block distribution + resolution (WP13, FR-013/FR-014, SC-006).

The resolver's ``Reference Docs:`` block names doctrine documents an agent may
want to fetch beyond what is inlined verbatim. Every emitted pointer must
OPEN -- resolve to a real on-disk doctrine document -- so a caller that greps
the block for a live path never chases a dead one.

:func:`_select_reference_pointers` is the pipeline entry point: action-scope
filter (:func:`_filter_references_for_action`) -> per-kind round-robin
distribution (:func:`_distribute_references_across_kinds`) -> resolve each
candidate against the on-disk offering catalog
(:func:`_reference_source_index` / :func:`_resolve_reference_source`),
keeping only pointers that resolve.

Design notes
------------

* The retired ``filtered_references[:10]`` window was order-rigged: the
  catalog leads with ``user_profile`` + 8 ``paradigm`` + ``DIRECTIVE_001``
  (indices 0-9), so a naive head cap was exhausted before the first
  ``tactic`` (index 34) was ever reached. Distribution across kinds makes
  every kind reachable; the emitted slice is capped at a stated limit so the
  block stays bounded.
* ``_REFERENCE_SOURCE_INDEX_CACHE`` is a process-wide cache of the
  ``kind -> {key -> source path}`` index, keyed by resolved offering root, so
  the filesystem walk that builds it runs once per interpreter rather than on
  every :func:`charter.activation.context.build_charter_context` call. The cache lives
  here (not in ``charter.activation.context``) because it is populated and read only by
  :func:`_reference_source_index`.
* ``_REFERENCE_POINTER_LIMIT`` / ``_REFERENCE_POINTER_FLOOR`` are re-exported
  from :mod:`charter.activation.context` (a thin re-export, mirroring the delivery-table
  sibling's shim) because ``tests/charter/test_reference_block.py`` imports
  them from there. :func:`_select_reference_pointers` is this module's only
  other cross-module surface -- its single internal caller lives in
  ``charter.activation.context``'s bootstrap-text rendering path; the remaining helpers
  (``_filter_references_for_action``, ``_reference_source_index``,
  ``_resolve_reference_source``, ``_distribute_references_across_kinds``,
  ``_action_offset``) have zero external consumers and stay module-private.
"""

from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml.error import YAMLError

from charter.bundle import CHARTER_YAML
from charter.offering.artifact_kinds import ArtifactKind

# ``_REFERENCE_POINTER_FLOOR`` / ``_REFERENCE_POINTER_LIMIT`` de-exported after
# the context.py re-export shim retirement (doctrine-built-in-seam-consolidation
# WP06): no external ``src/`` importer remains. Both stay module-internal
# constants used below.
__all__ = [
    "_load_references",
    "_select_reference_pointers",
]


_REFERENCE_POINTER_LIMIT = 12

# SC-006 non-vacuity floor: the stated minimum number of resolvable pointers
# the block must emit per software-dev action. Without a floor, "every emitted
# pointer resolves" would pass vacuously over an emitted set of zero. Held well
# below ``_REFERENCE_POINTER_LIMIT`` so it stays robust to catalog drift while
# still forbidding an empty block.
_REFERENCE_POINTER_FLOOR = 6

# Reference ``kind`` -> source subdirectory under the offering root.
# ``user_profile`` / ``template_set`` are project-generated (no offering
# source), so they carry no entry and are dropped when a pointer is resolved.
#: Curated membership (the reference kinds that have an offering source dir) is
#: named via :class:`ArtifactKind` members; the singular→plural mapping is
#: derived from the authority so it can never drift from the enum (issue #5409).
_REFERENCE_KIND_DIRS: dict[str, str] = {
    kind.value: kind.plural
    for kind in (
        ArtifactKind.TACTIC,
        ArtifactKind.DIRECTIVE,
        ArtifactKind.PARADIGM,
        ArtifactKind.PROCEDURE,
        ArtifactKind.STYLEGUIDE,
        ArtifactKind.TOOLGUIDE,
        ArtifactKind.AGENT_PROFILE,
    )
}

# Process-wide cache of the ``kind -> {key -> source path}`` index, keyed by
# resolved offering root so the filesystem walk runs once per interpreter.
_REFERENCE_SOURCE_INDEX_CACHE: dict[Path, dict[str, dict[str, Path]]] = {}


def _filter_references_for_action(references: list[dict[str, str]], action: str) -> list[dict[str, str]]:
    """Filter references for a specific action.

    Non-local_support references are always included.
    For local_support references:
      - If the summary contains "(action: XXX)", include only if XXX matches the requested action.
      - If no "(action: ...)" appears in the summary, include (global).
    """
    filtered: list[dict[str, str]] = []
    for ref in references:
        kind = ref.get("kind", "")
        if kind != "local_support":
            filtered.append(ref)
            continue

        # local_support: check summary for action scope
        summary = ref.get("summary", ref.get("title", ""))
        action_match = re.search(r"\(action:\s*(\w+)\)", summary)
        if action_match:
            ref_action = action_match.group(1).strip().lower()
            if ref_action == action.lower():
                filtered.append(ref)
        else:
            # No action scope in summary → include globally
            filtered.append(ref)

    return filtered


def _reference_source_index(offering_root: Path) -> dict[str, dict[str, Path]]:
    """Build (and cache) a ``kind -> {lookup key -> source path}`` index.

    Each artifact file contributes its stem (the filename before the first
    dot, e.g. ``acceptance-test-first``) and, for numerically-prefixed
    directives (``001-...``), a ``DIRECTIVE_001`` alias so the catalog id form
    resolves.
    """
    cached = _REFERENCE_SOURCE_INDEX_CACHE.get(offering_root)
    if cached is not None:
        return cached

    index: dict[str, dict[str, Path]] = {}
    for kind, subdir in _REFERENCE_KIND_DIRS.items():
        base = offering_root / subdir
        kind_index: dict[str, Path] = {}
        if base.is_dir():
            for path in sorted(base.rglob("*.yaml")):
                stem = path.name.split(".", 1)[0]
                kind_index.setdefault(stem, path)
                numeric = re.match(r"^(\d+)-", stem)
                if numeric:
                    kind_index.setdefault(f"DIRECTIVE_{numeric.group(1)}", path)
        index[kind] = kind_index

    _REFERENCE_SOURCE_INDEX_CACHE[offering_root] = index
    return index


def _resolve_reference_source(ref: dict[str, str], index: dict[str, dict[str, Path]]) -> Path | None:
    """Resolve *ref* to an existing offering-source path, or ``None``.

    Tries the catalog artifact id (the part after ``KIND:``) first, then the
    slug carried by the ``_LIBRARY/<kind>-<slug>.md`` local path. Returns
    ``None`` when the reference names no resolvable document (e.g. the
    project-generated ``user_profile`` / ``template_set`` entries).
    """
    kind_index = index.get(ref.get("kind", ""))
    if not kind_index:
        return None

    artifact_id = ref.get("id", "").split(":", 1)[-1]
    resolved = kind_index.get(artifact_id)
    if resolved is not None:
        return resolved

    slug = Path(ref.get("local_path", "")).stem
    prefix = f"{ref.get('kind', '')}-"
    if slug.startswith(prefix):
        slug = slug[len(prefix) :]
    return kind_index.get(slug)


def _action_offset(action: str) -> int:
    """Deterministic, salt-free ordinal seed derived from *action*.

    Used to rotate each kind's window so the emitted slice VARIES by action
    (FR-014 / SC-006 cross-action variation) rather than always leading with
    the same fixed head. Deterministic across processes (no ``hash()`` salt).
    """
    return sum((position + 1) * ord(char) for position, char in enumerate(action))


def _distribute_references_across_kinds(references: list[dict[str, str]], action: str) -> list[dict[str, str]]:
    """Interleave *references* across their kinds (round-robin).

    Groups by ``kind`` (preserving first-seen kind order), rotates each kind's
    members by an action-seeded offset, then emits one member per kind per
    round. The result surfaces later kinds early instead of exhausting the
    first kind in a fixed order (FR-013), and varies by *action* (FR-014).
    """
    by_kind: dict[str, list[dict[str, str]]] = {}
    for ref in references:
        by_kind.setdefault(ref.get("kind", ""), []).append(ref)

    offset = _action_offset(action)
    rotated: dict[str, list[dict[str, str]]] = {}
    for kind, members in by_kind.items():
        start = offset % len(members) if members else 0
        rotated[kind] = members[start:] + members[:start]

    ordered: list[dict[str, str]] = []
    round_index = 0
    added = True
    while added:
        added = False
        for members in rotated.values():
            if round_index < len(members):
                ordered.append(members[round_index])
                added = True
        round_index += 1
    return ordered


def _select_reference_pointers(
    references: list[dict[str, str]],
    action: str,
    offering_root: Path,
    *,
    limit: int = _REFERENCE_POINTER_LIMIT,
) -> list[tuple[dict[str, str], Path]]:
    """Return up to *limit* ``(reference, resolved source path)`` pairs.

    The pipeline is: action-scope filter -> per-kind distribution -> resolve
    each candidate to an existing doctrine document, keeping only pointers that
    OPEN (FR-013 / F-1). Distribution runs before the cap, so the emitted slice
    still spreads across kinds; unresolvable entries (``user_profile`` /
    ``template_set``) are skipped rather than emitted as dead pointers.
    """
    filtered = _filter_references_for_action(references, action)
    distributed = _distribute_references_across_kinds(filtered, action)
    index = _reference_source_index(offering_root)

    selected: list[tuple[dict[str, str], Path]] = []
    for ref in distributed:
        resolved = _resolve_reference_source(ref, index)
        if resolved is None:
            continue
        selected.append((ref, resolved))
        if len(selected) >= limit:
            break
    return selected


def _load_references(canonical_root: Path) -> list[dict[str, str]]:
    """Load the doctrine reference catalog from charter.yaml's ``catalog.references``.

    consolidate-charter-bundle (#2773): the retired ``references.yaml`` body is now
    the DERIVED ``catalog`` projection inside the authoritative ``charter.yaml``
    (``charter.activation.schemas.CharterCatalog`` — item shape mirrors the old file verbatim).
    Reading it here keeps the injected "Reference Docs" bootstrap block sourced from
    the authoritative charter, not the file the fold migration deletes. Returns
    ``[]`` when charter.yaml or its ``catalog`` section is absent.
    """
    # Same-layer, lazy import: avoids an import cycle with ``charter.activation.charter_yaml_io``.
    from charter.activation.charter_yaml_io import load_charter_yaml  # noqa: PLC0415

    charter_yaml_path = canonical_root / CHARTER_YAML
    if not charter_yaml_path.exists():
        return []

    try:
        document = load_charter_yaml(charter_yaml_path)
    except (YAMLError, UnicodeDecodeError, OSError):
        return []

    catalog = document.get("catalog") if isinstance(document, dict) else None
    raw_references = catalog.get("references") if isinstance(catalog, dict) else []
    if not isinstance(raw_references, list):
        return []

    refs: list[dict[str, str]] = []
    for item in raw_references:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "local_path": str(item.get("local_path", "")),
                "kind": str(item.get("kind", "")),
                "summary": str(item.get("summary", "")),
            }
        )
    return refs
