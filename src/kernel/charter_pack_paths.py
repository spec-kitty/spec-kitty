"""The project charter pack root and the pack-relative paths (FR-016, C-007).

This module is the one place that names the project pack root
(``.kittify/charter-packs/``) and the paths inside a charter pack
(``drg/fragment.yaml``, ``org-charter.yaml``, ``presets/``, ``graph.yaml``).
Every reader and writer of the project layer resolves its paths through it;
no other module spells these literals.

The project layer is **one flat pack** at ``.kittify/charter-packs/``.

Layer rule: ``kernel`` imports nothing upward (no ``charter``, ``glossary``,
``runtime`` or ``specify_cli``), so every layer can use this module.

There is no legacy read fallback (FR-011): ``spec-kitty upgrade`` moves the
retired pre-cutover project directory here, and the CLI-root
``LEGACY_CHARTER_STATE`` gate refuses a project that still has it.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "DRG_DIRNAME",
    "DRG_FRAGMENT",
    "KITTIFY_DIRNAME",
    "ORG_CHARTER_FILENAME",
    "PRESETS_DIRNAME",
    "PROJECT_GRAPH_FILENAME",
    "PROJECT_PACK_DIRNAME",
    "PROJECT_PACK_ROOT",
    "PROJECT_PACK_ROOT_POSIX",
    "pack_drg_fragment",
    "pack_org_charter",
    "pack_presets_dir",
    "project_pack_path",
    "project_pack_root",
]

#: The per-project Spec Kitty state directory at the repository root.
KITTIFY_DIRNAME = ".kittify"

#: The project charter pack directory under ``.kittify/``.
PROJECT_PACK_DIRNAME = "charter-packs"

#: The project pack root, relative to the repository root.
PROJECT_PACK_ROOT = Path(KITTIFY_DIRNAME, PROJECT_PACK_DIRNAME)

#: :data:`PROJECT_PACK_ROOT` in POSIX form, for prefix checks, manifests and globs.
PROJECT_PACK_ROOT_POSIX = PROJECT_PACK_ROOT.as_posix()

#: The DRG directory inside a charter pack.
DRG_DIRNAME = "drg"

#: The DRG fragment of a charter pack, relative to the pack root.
DRG_FRAGMENT = Path(DRG_DIRNAME, "fragment.yaml")

#: The org charter descriptor of a charter pack, relative to the pack root.
ORG_CHARTER_FILENAME = "org-charter.yaml"

#: The presets directory inside a charter pack.
PRESETS_DIRNAME = "presets"

#: The project pack's DRG overlay graph, relative to the project pack root.
PROJECT_GRAPH_FILENAME = "graph.yaml"


def project_pack_root(repo_root: Path) -> Path:
    """Return the project pack root ``<repo_root>/.kittify/charter-packs``."""
    return repo_root / PROJECT_PACK_ROOT


def project_pack_path(repo_root: Path, *parts: str) -> Path:
    """Return ``<project pack root>/<parts...>`` for *repo_root*."""
    return project_pack_root(repo_root).joinpath(*parts)


def pack_drg_fragment(pack_root: Path) -> Path:
    """Return the DRG fragment path of the charter pack at *pack_root*."""
    return pack_root / DRG_FRAGMENT


def pack_org_charter(pack_root: Path) -> Path:
    """Return the org charter descriptor path of the charter pack at *pack_root*."""
    return pack_root / ORG_CHARTER_FILENAME


def pack_presets_dir(pack_root: Path) -> Path:
    """Return the presets directory of the charter pack at *pack_root*."""
    return pack_root / PRESETS_DIRNAME
