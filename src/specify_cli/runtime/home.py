"""Global runtime home directory and package asset discovery.

Thin compatibility surface over the canonical kernel path authority
(:mod:`kernel.paths`). ``get_package_asset_root`` is now a **delegate** to
:func:`kernel.paths.get_package_asset_root` -- the single resolution body
(FR-005/FR-006, DR-1) -- so this module no longer carries a second resolver,
its own ``SPEC_KITTY_TEMPLATE_ROOT`` normalisation, or the retired
``specify_cli/missions`` importlib and ``dev_root`` fallbacks (fail-closed,
DR-2). ``get_kittify_home`` keeps its ``specify_cli.paths`` Windows delegation,
which is specific to this layer (the unified ``%LOCALAPPDATA%\\spec-kitty``
runtime root) and is not part of the kernel floor.
"""

from __future__ import annotations

import os
from pathlib import Path

import kernel.paths
from kernel.paths import is_windows


def get_kittify_home() -> Path:
    """Return the path to the user-global runtime directory.

    On Windows this resolves to the unified ``%LOCALAPPDATA%\\spec-kitty\\``
    root (via ``specify_cli.paths.get_runtime_root()``) so that every consumer
    in ``specify_cli`` sees the same Windows runtime root per Q3=C of the
    Windows Compatibility Hardening mission.  POSIX behavior is unchanged
    (returns ``~/.kittify`` for back-compat with existing installs).

    The ``SPEC_KITTY_HOME`` environment variable always wins regardless of
    platform.
    """
    if env_home := os.environ.get("SPEC_KITTY_HOME"):
        return Path(env_home)

    if is_windows():
        from specify_cli.paths import get_runtime_root  # noqa: PLC0415

        return get_runtime_root().base

    return Path.home() / ".kittify"


def get_package_asset_root() -> Path:
    """Return the package's bundled mission assets via the kernel authority.

    Thin delegate to :func:`kernel.paths.get_package_asset_root` -- the ONE
    canonical resolution body (FR-005/FR-006, DR-1). Kept as a re-export shim so
    existing ``from specify_cli.runtime.home import get_package_asset_root``
    importers resolve the single authority; the legacy ``specify_cli/missions``
    importlib probe and the ``dev_root`` fallback are intentionally gone
    (fail-closed, DR-2). ``SPEC_KITTY_PACKS_ROOT`` / ``SPEC_KITTY_TEMPLATE_ROOT``
    precedence and the fail-closed contract all live in the kernel door.
    """
    return kernel.paths.get_package_asset_root()


__all__ = ["get_kittify_home", "get_package_asset_root"]
