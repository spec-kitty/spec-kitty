"""The project charter pack root and the pack-relative paths (FR-016, C-007).

This module is the one place that names the project pack root
(``.kittify/charter-packs/``) and the paths inside a charter pack
(``drg/fragment.yaml``, ``org-charter.yaml``, ``presets/``, ``graph.yaml``).
Every reader and writer of the project layer resolves its paths through it;
no other module spells these literals.

The project layer is **one flat pack** at ``.kittify/charter-packs/``.

Layer rule: ``kernel`` imports nothing upward (no ``charter``, ``glossary``,
``runtime`` or ``specify_cli``), so every layer can use this module.

Temporary legacy read fallback (FR-011): ``LEGACY_PROJECT_PACK_DIRNAME``,
:class:`LegacyDoctrineRootWarning` and :func:`resolve_project_pack_read_root`
keep a project that still has the retired ``.kittify/doctrine/`` tree readable
until the migration has moved it. They exist only until WP14 of mission
``charter-pack-cutover-01M491G6`` deletes them; nothing else may depend on the
legacy name.
"""

from __future__ import annotations

import functools
import warnings
from pathlib import Path

__all__ = [
    "DRG_DIRNAME",
    "DRG_FRAGMENT",
    "KITTIFY_DIRNAME",
    "LEGACY_PROJECT_PACK_DIRNAME",
    "ORG_CHARTER_FILENAME",
    "PRESETS_DIRNAME",
    "PROJECT_GRAPH_FILENAME",
    "PROJECT_PACK_DIRNAME",
    "PROJECT_PACK_ROOT",
    "PROJECT_PACK_ROOT_POSIX",
    "LegacyDoctrineRootWarning",
    "pack_drg_fragment",
    "pack_org_charter",
    "pack_presets_dir",
    "project_pack_path",
    "project_pack_root",
    "resolve_project_pack_read_root",
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

#: TEMPORARY (FR-011, deleted by WP14): the retired project layer directory
#: under ``.kittify/``. Only :func:`resolve_project_pack_read_root` and the
#: write sites WP03 flips may use it.
LEGACY_PROJECT_PACK_DIRNAME = "doctrine"


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


class LegacyDoctrineRootWarning(UserWarning):
    """TEMPORARY (FR-011, deleted by WP14).

    Emitted once per process when a project is read from the retired
    ``.kittify/doctrine/`` root because ``.kittify/charter-packs/`` does not
    exist yet.
    """


@functools.lru_cache(maxsize=1)
def _warn_legacy_project_pack_root_once() -> None:
    """TEMPORARY (FR-011, deleted by WP14): emit the legacy-root warning once per process.

    Gated by ``lru_cache`` rather than the ``warnings`` module's own de-dup
    filter: a caller running under a stricter ``filterwarnings`` configuration
    could otherwise turn a *repeated* warning into a hard failure. Tests reset
    this gate via ``_warn_legacy_project_pack_root_once.cache_clear()``.
    """
    warnings.warn(
        f"'{KITTIFY_DIRNAME}/{LEGACY_PROJECT_PACK_DIRNAME}/' is the retired "
        "project charter pack root; reading it because "
        f"'{PROJECT_PACK_ROOT_POSIX}/' does not exist yet. "
        "A migration moves this data to the project charter pack root.",
        LegacyDoctrineRootWarning,
        stacklevel=3,
    )


def resolve_project_pack_read_root(repo_root: Path, *, quiet: bool = False) -> Path:
    """TEMPORARY (FR-011, deleted by WP14): return the project pack root to read from.

    The project pack root ``<repo_root>/.kittify/charter-packs`` wins whenever
    it is a directory, even alongside a still-present legacy tree.

    Falls back to the retired ``<repo_root>/.kittify/doctrine`` when only that
    is a directory, warning once per process unless *quiet*.

    When neither exists, returns the project pack root: there is nothing to
    read and nothing to warn about.
    """
    canonical = project_pack_root(repo_root)
    if canonical.is_dir():
        return canonical

    legacy = repo_root / KITTIFY_DIRNAME / LEGACY_PROJECT_PACK_DIRNAME
    if legacy.is_dir():
        if not quiet:
            _warn_legacy_project_pack_root_once()
        return legacy

    return canonical
