"""Render the ``Project authority paths:`` block (FR-003).

The Project authority paths section is the resolver's structured pointer to
the directories on disk that carry the canonical sources of truth a coding
agent must consult for terminology and architectural intent. It is rendered
between ``Policy Summary:`` and ``Action-Critical Charter Sections (...)``
in the bootstrap text returned by
:func:`charter.activation.context.build_charter_context`.

Design notes
------------

* **Default authority paths** are hard-coded here so every project gets the
  same convention without having to declare them in the charter
  (``docs/context/`` for terminology canon, ``docs/adr/3.x/`` for
  architectural intent — the canonical homes after the Common Docs structural
  fold).  Each default carries a project-agnostic "When you ..., ..."
  conditional.
* **Charter-declared paths** come from
  :attr:`charter.activation.schemas.GovernanceCharterConfig.authority_paths` and are
  appended in declaration order, deduped against the defaults.  Their
  conditional defaults to a generic "consult when you change content
  under this directory" copy; a future mission may parameterise this.
* **Existence-gated rendering**: a path is rendered only when the
  corresponding directory exists under *repo_root*.  This protects the
  resolver from emitting broken pointers when an entry references a
  non-existent path (the section header itself is suppressed when no path
  qualifies).
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.schemas import GovernanceCharterConfig

__all__ = [
    "AUTHORITY_PATHS_HEADER",
    "DEFAULT_AUTHORITY_PATHS",
    "DEFAULT_CHARTER_DECLARED_WHEN_CLAUSE",
    "render_authority_paths",
]


AUTHORITY_PATHS_HEADER: str = "Project authority paths:"
"""The literal section header anchored by the ATDD self-sufficiency test."""


_TERMINOLOGY_WHEN: str = (
    "canonical terminology — when you encounter a domain term in the "
    "diff, grep this directory"
)
_ADR_WHEN: str = (
    "architectural intent — when you change a structural boundary, "
    "read the relevant ADR"
)


DEFAULT_AUTHORITY_PATHS: dict[str, str] = {
    "docs/context/": _TERMINOLOGY_WHEN,
    "docs/adr/3.x/": _ADR_WHEN,
}
"""Mapping of default authority directory to its when-doing copy.

Each home is rendered with a trailing slash so callers that grep for
``docs/context/`` (the ATDD assertion form) match unambiguously.

**Mission B (C-003 / NFR-005):** the doc-tree fold relocated the terminology
canon to ``docs/context/`` and the architectural-intent ADRs to
``docs/adr/3.x/``.  The WP01 dual-read staged both the pre-fold homes and the
new homes while the move was in flight; now that the tree has landed
(WP03/WP06) the legacy branches are dropped — only the canonical new homes
remain.  Rendering stays existence-gated, so a home surfaces only when its
directory is present.
"""


DEFAULT_CHARTER_DECLARED_WHEN_CLAUSE: str = (
    "consult when you change content under this directory"
)
"""Generic conditional for charter-declared (non-default) authority paths."""


def _normalize_path(raw: str) -> str:
    """Return *raw* with a single trailing slash so dedup is consistent."""

    cleaned = raw.strip()
    if not cleaned:
        return ""
    if cleaned.endswith("/"):
        return cleaned
    return f"{cleaned}/"


def _directory_exists(repo_root: Path, relative_path: str) -> bool:
    """Return True when *relative_path* resolves to an existing directory.

    The lookup is intentionally permissive: a missing path returns False
    without raising, so callers can iterate over a candidate set without
    catching :class:`OSError`.
    """

    if not relative_path:
        return False
    candidate = repo_root / relative_path
    try:
        return candidate.is_dir()
    except OSError:
        return False


def render_authority_paths(
    repo_root: Path,
    charter_config: GovernanceCharterConfig,
) -> str:
    """Render the ``Project authority paths:`` section.

    Parameters
    ----------
    repo_root:
        Repository root whose layout determines which authority paths
        actually exist on disk.  Only existing directories are emitted —
        missing defaults are silently skipped (no broken pointers).
    charter_config:
        The charter-resolved doctrine selection.  Its
        :attr:`authority_paths` list contributes additional pointers
        beyond the built-in defaults; entries that duplicate a default
        path (e.g. ``docs/context/``) are deduplicated.

    Returns
    -------
    str
        A newline-delimited block beginning with
        :data:`AUTHORITY_PATHS_HEADER`, or the empty string when no path
        qualifies (caller can skip emitting the header).
    """

    lines: list[str] = []
    seen: set[str] = set()

    for default_path, when_clause in DEFAULT_AUTHORITY_PATHS.items():
        if not _directory_exists(repo_root, default_path):
            continue
        normalised = _normalize_path(default_path)
        if normalised in seen:
            continue
        seen.add(normalised)
        lines.append(f"  - {normalised}    ({when_clause})")

    for declared in charter_config.authority_paths:
        normalised = _normalize_path(declared)
        if not normalised or normalised in seen:
            continue
        if not _directory_exists(repo_root, normalised):
            continue
        seen.add(normalised)
        lines.append(
            f"  - {normalised}    ({DEFAULT_CHARTER_DECLARED_WHEN_CLAUSE})"
        )

    if not lines:
        return ""

    return "\n".join([AUTHORITY_PATHS_HEADER, *lines])
