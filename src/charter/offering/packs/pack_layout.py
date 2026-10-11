"""The one pack-layout resolution seam (FR-009, WP02 T007).

:func:`resolve_pack_layout` is the single authority for *where a Charter Pack's
layout files live*: the active-charter file and the DRG source. It is
descriptor-first (an authored ``active_charter`` / ``pack_drg`` pointer wins)
with a per-level convention fallback that **delegates to the
``kernel.charter_pack_paths`` constants/helpers** — so no second filename
authority is introduced.

The returned ``drg_path`` is deliberately typed as "a path
``charter.offering.drg.loader.load_graph_or_dir`` accepts", i.e. a file OR a
directory: an org/project pack resolves to a single file
(``drg/fragment.yaml`` / ``graph.yaml``) while the built-in pack resolves to the
pack root itself, whose sharded ``*.graph.yaml`` fragments that loader reads as
a directory. One seam, no per-level branch at every call site.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.packs.pack_descriptor import PackDescriptor
from kernel.charter_pack_paths import PROJECT_GRAPH_FILENAME, pack_drg_fragment, pack_org_charter
from kernel.pack_tiers import ORG, PROJECT

__all__ = ["PackLayoutError", "resolve_pack_layout"]


class PackLayoutError(ValueError):
    """A descriptor layout pointer does not resolve to a path inside the pack root.

    Raised when ``active_charter`` / ``pack_drg`` is absolute or escapes the
    pack root (a ``..`` component or a symlink escape). ``validate_pack`` catches
    it and reports the finding at the offending path.
    """


def _resolve_pointer(pack_root: Path, pointer: str) -> Path:
    """Resolve an authored pack-relative pointer, rejecting any escape.

    Reuses the single canonical containment primitive
    (``charter.offering.drg.org_pack_config.resolve_relative_path_within_root``)
    rather than a second hand-rolled ``..``/absolute/symlink check — imported
    lazily to keep this module's import surface minimal (pack-layout resolution
    is not a hot path).
    """
    from charter.offering.drg.org_pack_config import (  # noqa: PLC0415 — lazy: single escape-detection authority, kept off this module's import surface
        OrgPackSubdirEscapeError,
        resolve_relative_path_within_root,
    )

    try:
        resolved: Path = resolve_relative_path_within_root(pack_root, pointer)
    except OrgPackSubdirEscapeError as exc:
        raise PackLayoutError(str(exc)) from exc
    return resolved


def resolve_pack_layout(pack_root: Path, descriptor: PackDescriptor) -> tuple[Path | None, Path]:
    """Resolve a pack's ``(active_charter_path, drg_path)`` (FR-009).

    Descriptor pointer first (validated inside *pack_root*); else the per-level
    convention via ``kernel.charter_pack_paths``:

    * ``active_charter_path`` — the ``active_charter`` pointer, else
      ``org-charter.yaml`` for an org pack and ``None`` for built-in/project.
    * ``drg_path`` — the ``pack_drg`` pointer, else ``drg/fragment.yaml`` (org),
      the pack root as the sharded ``*.graph.yaml`` directory (built-in), or
      ``graph.yaml`` (project).

    The convention is selected from ``descriptor.pack_level`` as given; this
    seam does not check it against the position the pack was configured at. A
    caller that knows the position (``validate_pack``) passes a descriptor whose
    level is that position, so the configured position — not an unchecked
    declaration — governs layout; the disagreement itself is reported by
    ``PACK_LEVEL_MISMATCH``.

    Raises:
        PackLayoutError: a pointer is absolute or escapes *pack_root*.
    """
    active_charter = (
        _resolve_pointer(pack_root, descriptor.active_charter) if descriptor.active_charter else _convention_active_charter(pack_root, descriptor.pack_level)
    )
    drg = _resolve_pointer(pack_root, descriptor.pack_drg) if descriptor.pack_drg else _convention_drg(pack_root, descriptor.pack_level)
    return active_charter, drg


def _convention_active_charter(pack_root: Path, level: str) -> Path | None:
    """Per-level active-charter convention: org ships one, built-in/project do not."""
    return pack_org_charter(pack_root) if level == ORG else None


def _convention_drg(pack_root: Path, level: str) -> Path:
    """Per-level DRG-source convention, as a path ``load_graph_or_dir`` accepts."""
    if level == ORG:
        return pack_drg_fragment(pack_root)
    if level == PROJECT:
        return pack_root / PROJECT_GRAPH_FILENAME
    # built-in: the sharded ``*.graph.yaml`` root directory.
    return pack_root
