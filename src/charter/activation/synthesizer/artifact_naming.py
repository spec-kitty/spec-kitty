"""Helpers for artifact filenames and project-pack subdirectories.

These helpers intentionally avoid regex backtracking so they remain safe when
fed arbitrary artifact IDs from external inputs or persisted manifests.
"""

from __future__ import annotations

__all__ = [
    "artifact_filename",
    "pack_kind_subdir",
]



def extract_directive_number(artifact_id: str | None) -> str:
    """Return the numeric directive segment from an artifact ID.

    Valid directive IDs contain an uppercase prefix followed by ``_`` and one or
    more digits, for example ``PROJECT_001``. When no such segment is present,
    the safe fallback is ``"000"``.
    """
    if not artifact_id:
        return "000"

    length = len(artifact_id)
    index = 0
    while index < length:
        start = index
        while index < length and artifact_id[index].isupper():
            index += 1
        if index == start or index >= length or artifact_id[index] != "_":
            index = start + 1
            continue

        digits_start = index + 1
        digits_end = digits_start
        while digits_end < length and artifact_id[digits_end].isdigit():
            digits_end += 1
        if digits_end > digits_start:
            return artifact_id[digits_start:digits_end].zfill(3)

        index = digits_start

    return "000"


def artifact_filename(kind: str, slug: str, artifact_id: str | None = None) -> str:
    """Return the repository-glob-matching filename for an artifact."""
    if kind == "directive":
        return f"{extract_directive_number(artifact_id)}-{slug}.directive.yaml"
    if kind == "tactic":
        return f"{slug}.tactic.yaml"
    if kind == "styleguide":
        return f"{slug}.styleguide.yaml"
    raise ValueError(f"Unknown artifact kind: {kind!r}")


def pack_kind_subdir(kind: str) -> str:
    """Return the project-pack subdirectory name for a given artifact kind.

    Returns singular names that match the ``.gitignore`` whitelist entries
    (``directive/``, ``tactic/``, ``styleguide/``).  Plural names
    (``directives/``, etc.) were previously returned but are NOT whitelisted,
    making synthesized artifacts ungit-trackable.
    """
    return {
        "directive": "directive",
        "tactic": "tactic",
        "styleguide": "styleguide",
    }[kind]
