"""Platform-aware runtime state path resolution for spec-kitty.

This module is a leaf — it must not import from specify_cli.auth,
specify_cli.tracker, or any kernel subpackage.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import platformdirs
from kernel.paths import ensure_runtime_state_root, to_posix


@dataclass(frozen=True)
class RuntimeRoot:
    """Immutable descriptor of the runtime state root for the current platform.

    Fields
    ------
    platform:
        The normalised platform string: "win32", "darwin", or "linux".
    base:
        Absolute path to the top-level runtime state directory.  Subdirs are
        derived properties so callers never construct paths by hand.

    Notes
    -----
    This dataclass is frozen so it can safely be cached at module or function
    level by callers.  It performs no I/O and creates no directories.
    """

    platform: Literal["win32", "darwin", "linux"]
    base: Path

    @property
    def auth_dir(self) -> Path:
        return self.base / "auth"

    @property
    def tracker_dir(self) -> Path:
        return self.base / "tracker"

    @property
    def sync_dir(self) -> Path:
        return self.base / "sync"

    @property
    def daemon_dir(self) -> Path:
        return self.base / "daemon"

    @property
    def cache_dir(self) -> Path:
        return self.base / "cache"


def get_runtime_root() -> RuntimeRoot:
    """Return the canonical runtime state root for the current platform.

    Resolution order (all platforms):

    1. ``SPEC_KITTY_HOME`` environment variable, when set to a non-empty value
       — used verbatim as ``base`` (so ``config.toml`` lands at
       ``$SPEC_KITTY_HOME/config.toml``; the env path is *not* suffixed with
       ``.spec-kitty``).
    2. On Windows: ``platformdirs.user_data_dir`` (non-roaming LocalAppData).
    3. On POSIX  : ``~/.spec-kitty``.

    An empty ``SPEC_KITTY_HOME`` is falsy and falls through to the platform
    default, matching ``kernel.paths.get_kittify_home`` (the asset-home helper).

    This function is **pure** — it performs no I/O and creates no directories.
    Directory creation is the caller's responsibility.
    """
    platform = _current_platform()
    if env_home := os.environ.get("SPEC_KITTY_HOME"):
        base = Path(env_home)
    elif platform == "win32":
        try:
            base = Path(platformdirs.user_data_dir("spec-kitty", appauthor=False, roaming=False))
        except Exception:
            # Keep import-time Windows simulations and constrained runtimes from
            # crashing before callers can patch or inspect the module.
            base = Path.home() / ".spec-kitty"
    else:
        base = Path.home() / ".spec-kitty"
    return RuntimeRoot(platform=platform, base=base)


def ensure_runtime_root() -> Path:
    """Create (or re-harden) the shared runtime-state root at ``0o700``.

    :func:`get_runtime_root` itself stays a **pure** resolver (pinned by
    ``tests/paths/test_runtime_root_spec_kitty_home.py`` T-RR-4/T005/
    NFR-002: "resolution creates no directories") and the kernel-floor
    mirror :func:`kernel.paths.get_runtime_state_root` carries the identical
    contract -- so the actual mkdir/chmod side effect cannot live inside
    either of those functions without breaking a test that binds this
    module's public contract. This sibling function is the single door any
    writer calls instead: co-located with :func:`get_runtime_root` in this
    module per mission ``local-write-safety-01M2ZPZD`` WP06 (#4812/#4760),
    which retires the hand-rolled ``chmod(0o700)`` ladder
    ``zeitgeist_client/credentials.py`` used to run on every credential
    write, and the equivalent implicit gap in ``tracker/credentials.py``
    (which never hardened the root at all, only relying on whichever writer
    happened to create it first) -- closing the FR-011 split-brain where two
    independent writers raced to be "the" owner of ``~/.spec-kitty``'s mode.

    Idempotent and safe to call on every write: an already-existing
    directory is re-chmod'd to ``0o700`` rather than trusted at whatever
    mode a pre-fix write left it (ambient umask, typically ``0o755``).

    The 0o700 mkdir/chmod itself is delegated to the single kernel-floor door
    :func:`kernel.paths.ensure_runtime_state_root` so this hardening lives in
    exactly one place, shared with the runtime-layer prompt-namespace writer
    (``runtime.next._tmp_namespace``) which cannot import ``specify_cli``. The
    kernel resolver ``get_runtime_state_root()`` and this module's
    ``get_runtime_root().base`` are pinned equal on every branch
    (``tests/kernel/test_runtime_root_resolver_parity.py``), so the hardened
    directory is exactly ``get_runtime_root().base``.
    """
    ensure_runtime_state_root()
    return get_runtime_root().base


def render_runtime_path(path: Path, *, for_user: bool = True) -> str:
    """Render a runtime-state path for user-facing output.

    On Windows: returns the real absolute path
    (e.g. ``C:\\Users\\alice\\AppData\\Local\\spec-kitty\\auth``).

    On POSIX: returns a tilde-compressed form (``~/...``) when the path is
    under ``$HOME`` and *for_user* is ``True``, otherwise returns the absolute
    path as a string.

    Parameters
    ----------
    path:
        The path to render.  May be relative or not yet exist on disk.
    for_user:
        When ``False`` always return the absolute path regardless of platform.
    """
    abs_path = Path(path).resolve(strict=False)
    if not for_user:
        return str(abs_path)
    if _current_platform() == "win32":
        return str(abs_path)
    # POSIX tilde compression
    try:
        home = Path.home().resolve(strict=False)
        rel = abs_path.relative_to(home)
        return "~/" + to_posix(rel)
    except ValueError:
        return str(abs_path)


def _current_platform() -> Literal["win32", "darwin", "linux"]:
    """Return the normalised platform string for the current runtime."""
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"
