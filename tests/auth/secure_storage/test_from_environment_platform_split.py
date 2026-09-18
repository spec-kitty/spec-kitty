"""Unit tests for the file-only ``SecureStorage.from_environment()`` dispatch."""

from __future__ import annotations

import importlib
import sys


import pytest

pytestmark = [pytest.mark.integration]

def _snapshot_modules(*prefixes: str) -> dict[str, object]:
    """Return a copy of sys.modules for all keys matching any prefix."""
    return {k: v for k, v in sys.modules.items() if any(k.startswith(p) for p in prefixes)}


def _restore_modules(snapshot: dict[str, object], *prefixes: str) -> None:
    """Remove newly-added modules and restore the snapshotted state."""
    for key in list(sys.modules):
        if any(key.startswith(p) for p in prefixes):
            del sys.modules[key]
    sys.modules.update(snapshot)


_SPEC_KITTY_AUTH_STORAGE = "specify_cli.auth.secure_storage"


def test_from_environment_windows_returns_windows_file_storage(monkeypatch):
    """On win32, from_environment() returns the Windows file-storage alias only.

    Routed through the canonical ``kernel.paths.is_windows`` seam
    (cross-os-primitive-unification-01M2T1CM WP01) rather than faking
    ``sys.platform`` -- ``from_environment`` does a deferred
    ``from kernel.paths import is_windows`` at call time, so patching the
    module attribute here is honoured without ever touching ``os.name``
    (C-003: faking ``os.name`` flips ``pathlib`` to ``WindowsPath`` and
    crashes pytest).
    """
    prefixes = (_SPEC_KITTY_AUTH_STORAGE,)
    snapshot = _snapshot_modules(*prefixes)

    monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
    for name in list(sys.modules):
        if name.startswith(_SPEC_KITTY_AUTH_STORAGE):
            del sys.modules[name]

    import specify_cli.auth.secure_storage.abstract as abstract_mod

    importlib.reload(abstract_mod)

    try:
        storage = abstract_mod.SecureStorage.from_environment()

        from specify_cli.auth.secure_storage.windows_storage import WindowsFileStorage

        assert isinstance(storage, WindowsFileStorage), (
            f"Expected WindowsFileStorage on win32, got {type(storage).__name__}"
        )
        # WP03 / DM-01KW1KDHVGWZ0QERDMV1CRJ15S: the Windows store is no longer
        # hardcoded to ``~/.spec-kitty/auth``; it now resolves through the
        # unified runtime root (platformdirs base on real Windows,
        # ``$SPEC_KITTY_HOME`` when set). Assert against get_runtime_root() so
        # the test reflects the normalization rather than a coincidental path.
        from specify_cli.paths import get_runtime_root

        assert storage.store_path == get_runtime_root().auth_dir
        assert "specify_cli.auth.secure_storage.keychain" not in sys.modules, (
            "keychain module must never be imported in the file-only storage model"
        )
    finally:
        _restore_modules(snapshot, *prefixes)


def test_from_environment_posix_returns_encrypted_file_storage(monkeypatch):
    """On linux, from_environment() returns the encrypted file backend.

    Routed through the ``kernel.paths.is_windows`` seam -- see the docstring
    on the sibling Windows test above for why this patches the seam instead
    of ``sys.platform``.
    """
    prefixes = (_SPEC_KITTY_AUTH_STORAGE,)
    snapshot = _snapshot_modules(*prefixes)

    monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
    for name in list(sys.modules):
        if name.startswith(_SPEC_KITTY_AUTH_STORAGE):
            del sys.modules[name]

    import specify_cli.auth.secure_storage.abstract as abstract_mod

    importlib.reload(abstract_mod)

    try:
        storage = abstract_mod.SecureStorage.from_environment()

        from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage

        assert isinstance(storage, FileFallbackStorage), (
            f"Expected FileFallbackStorage on linux, got {type(storage).__name__}"
        )
        assert "specify_cli.auth.secure_storage.keychain" not in sys.modules, (
            "keychain module must never be imported in the file-only storage model"
        )
    finally:
        _restore_modules(snapshot, *prefixes)
