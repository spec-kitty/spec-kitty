"""Unit tests for the file-only ``SecureStorage.from_environment()`` dispatch."""

from __future__ import annotations

import importlib
import sys

import pytest

pytestmark = [pytest.mark.integration]


def _purge_modules(monkeypatch: pytest.MonkeyPatch, *prefixes: str) -> None:
    """Force a fresh import for every loaded module matching a prefix.

    ``monkeypatch.delitem`` on a key already present in ``sys.modules``
    records the removed value and restores it when the fixture tears down, so
    a bare delitem per key already puts ``sys.modules`` back to its exact
    pre-test state once the test ends, regardless of what the import
    machinery wrote in between.

    The import machinery also rebinds the *parent* package's attribute
    (``pkg.sub = submodule``) on a fresh import; a plain ``sys.modules``
    purge/restore does not touch that attribute, so it keeps pointing at the
    stale, freshly-reimported submodule after the test even though
    ``sys.modules`` itself is clean again. Restore that too via
    ``monkeypatch.delattr`` before each purge.
    """
    for name in [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]:
        parent_name, _, child = name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None and hasattr(parent, child):
            monkeypatch.delattr(parent, child)
        monkeypatch.delitem(sys.modules, name)


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
    monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
    _purge_modules(monkeypatch, _SPEC_KITTY_AUTH_STORAGE)

    import specify_cli.auth.secure_storage.abstract as abstract_mod

    importlib.reload(abstract_mod)

    storage = abstract_mod.SecureStorage.from_environment()

    from specify_cli.auth.secure_storage.windows_storage import WindowsFileStorage

    assert isinstance(storage, WindowsFileStorage), f"Expected WindowsFileStorage on win32, got {type(storage).__name__}"
    # WP03 / DM-01KW1KDHVGWZ0QERDMV1CRJ15S: the Windows store is no longer
    # hardcoded to ``~/.spec-kitty/auth``; it now resolves through the
    # unified runtime root (platformdirs base on real Windows,
    # ``$SPEC_KITTY_HOME`` when set). Assert against get_runtime_root() so
    # the test reflects the normalization rather than a coincidental path.
    from specify_cli.paths import get_runtime_root

    assert storage.store_path == get_runtime_root().auth_dir
    assert "specify_cli.auth.secure_storage.keychain" not in sys.modules, "keychain module must never be imported in the file-only storage model"


def test_from_environment_posix_returns_encrypted_file_storage(monkeypatch):
    """On linux, from_environment() returns the encrypted file backend.

    Routed through the ``kernel.paths.is_windows`` seam -- see the docstring
    on the sibling Windows test above for why this patches the seam instead
    of ``sys.platform``.
    """
    monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
    _purge_modules(monkeypatch, _SPEC_KITTY_AUTH_STORAGE)

    import specify_cli.auth.secure_storage.abstract as abstract_mod

    importlib.reload(abstract_mod)

    storage = abstract_mod.SecureStorage.from_environment()

    from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage

    assert isinstance(storage, FileFallbackStorage), f"Expected FileFallbackStorage on linux, got {type(storage).__name__}"
    assert "specify_cli.auth.secure_storage.keychain" not in sys.modules, "keychain module must never be imported in the file-only storage model"
