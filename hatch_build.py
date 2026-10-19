"""Hatch build hook: ship the pinned ``packs/built-in`` tree, verified (#6451, FR-007..FR-009).

``packs/built-in`` is fetched from spec-kitty-open-packs at the commit recorded in
``packs/built-in.source.yaml``; it is not (eventually) tracked here. This hook runs
before every wheel and sdist build and decides what to do with the tree:

* **Git checkout** (a ``.git`` entry at the project root): a missing or stale tree is
  fetched and placed through ``charter.offering.packs.pack_fetch`` (offline when
  ``SPEC_KITTY_PACK_OFFLINE`` is set), then re-verified.
* **Unpacked sdist** (no ``.git``): verify only. This path never fetches (C-003), so a
  wheel builds from an sdist with no network and no git.

A tree whose clean-tree digest differs from the pin fails the build with the stable
``PACK_*`` code. For the wheel the verified tree is then force-included at
``packs/built-in`` (the site-packages sibling of ``charter`` the kernel sibling walk
expects, C-001); ``packs/internal`` is never referenced here (C-002).

The hook runs in a build environment where the project is not installed, so it puts
``src/`` on ``sys.path`` and imports only the pin/fetch modules, whose third-party
requirements are listed in ``[build-system].requires``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

__all__ = ["BuiltInPackBuildHook", "ensure_built_in_tree"]

# Literals on purpose: this hook runs before ``src/`` is on ``sys.path`` (see
# ``_import_pack_modules``), so it cannot use ``pack_pin.pin_filename``.
PIN_RELPATH = "packs/built-in.source.yaml"
PACK_RELPATH = "packs/built-in"
OFFLINE_ENV = "SPEC_KITTY_PACK_OFFLINE"
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_STALE_FMT = "{tree} is missing or does not match the digest pinned in {pin}; {remedy}"


def _offline_requested() -> bool:
    return os.environ.get(OFFLINE_ENV, "").strip().lower() in _TRUTHY


def _is_git_checkout(root: Path) -> bool:
    # ``.git`` is a directory in a clone and a file in a linked worktree.
    return (root / ".git").exists()


def _import_pack_modules(root: Path) -> tuple[Any, Any]:
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from charter.offering.packs import pack_fetch, pack_pin

    return pack_pin, pack_fetch


def ensure_built_in_tree(root: Path, *, offline: bool | None = None) -> Path:
    """Make sure ``<root>/packs/built-in`` matches its pin and return it.

    Raises ``PackSyncError`` (code ``PACK_TREE_STALE`` for a tree that is missing or
    differs in an sdist, or the fetch error code in a checkout) when it cannot.
    """
    pack_pin, pack_fetch = _import_pack_modules(root)
    pin = pack_pin.load_pack_pin(root / PIN_RELPATH)
    dest = root / PACK_RELPATH
    if pack_fetch.check_pack(pin, dest) is pack_fetch.PackTreeStatus.OK:
        return dest
    if not _is_git_checkout(root):
        raise pack_fetch.PackSyncError(
            pack_fetch.PACK_TREE_STALE,
            _STALE_FMT.format(
                tree=PACK_RELPATH,
                pin=PIN_RELPATH,
                remedy="an sdist build verifies only and never fetches; rebuild from a git checkout after `make sync-packs`",
            ),
        )
    effective_offline = _offline_requested() if offline is None else offline
    cached = pack_fetch.fetch_to_cache(pin, offline=effective_offline)
    pack_fetch.place_pack(cached, dest, pin)
    return dest


class BuiltInPackBuildHook(BuildHookInterface[Any]):
    PLUGIN_NAME = "custom"

    def initialize(self, _version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        ensure_built_in_tree(root)
        if self.target_name == "wheel":
            build_data.setdefault("force_include", {})[str(root / PACK_RELPATH)] = PACK_RELPATH
