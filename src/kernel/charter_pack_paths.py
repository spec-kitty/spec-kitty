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

from kernel.paths import to_posix

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
    "repo_relative_posix",
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


def repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Return *path* as a repo-relative POSIX string.

    A repo-relative path handed to a consumer (the JSON envelope, a manifest, a
    log line) is a POSIX string, so it reads the same on every operating system;
    a :class:`Path` stays the OS-native access path. ``str(Path.relative_to(...))``
    does not honour that split — on Windows it renders ``\\`` (#6277) — so every
    site that reports a repo-relative path renders it through this helper.

    Both arguments are :class:`Path` objects by design: an already-rendered
    string cannot be normalised safely, and a relative string would silently
    double its own prefix. The separator swap itself is
    :func:`kernel.paths.to_posix`'s job — the single normalisation seam — so
    this helper only decides *what* is reported, never *how* it is spelled.
    """
    return to_posix(path.relative_to(repo_root))


def pack_drg_fragment(pack_root: Path) -> Path:
    """Return the DRG fragment path of the charter pack at *pack_root*."""
    return pack_root / DRG_FRAGMENT


def pack_org_charter(pack_root: Path) -> Path:
    """Return the org charter descriptor path of the charter pack at *pack_root*."""
    return pack_root / ORG_CHARTER_FILENAME


def pack_presets_dir(pack_root: Path) -> Path:
    """Return the presets directory of the charter pack at *pack_root*."""
    return pack_root / PRESETS_DIRNAME
