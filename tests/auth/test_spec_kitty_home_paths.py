"""SPEC_KITTY_HOME rerouting for the auth state surface (mission
spec-kitty-home-isolation, WP03 / T014).

Covers FR-002 (encrypted session store), FR-003 (refresh lock), and NFR-005
(no auth material outside the resolved runtime root). Each call site now
resolves through :func:`specify_cli.paths.get_runtime_root`:

- ``file_fallback.default_store_dir()`` → ``<runtime-root>/auth``
- ``token_manager._refresh_lock_path()`` → ``<runtime-root>/auth/refresh.lock``
- ``WindowsFileStorage()`` default → ``<runtime-root>/auth``

With ``SPEC_KITTY_HOME`` set, all three land under it on every platform; with it
unset on POSIX they fall back to ``~/.spec-kitty/auth``. The Windows default is
normalized to the runtime root (decision DM-01KW1KDHVGWZ0QERDMV1CRJ15S) instead
of the previously hardcoded ``~/.spec-kitty/auth``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.auth import token_manager as tm_module
from specify_cli.auth.secure_storage.file_fallback import default_store_dir
from specify_cli.auth.secure_storage.windows_storage import WindowsFileStorage
from specify_cli.paths import get_runtime_root

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# default_store_dir() — FR-002 (encrypted session store)
# ---------------------------------------------------------------------------


def test_default_store_dir_honors_spec_kitty_home(monkeypatch, tmp_path: Path):
    """With SPEC_KITTY_HOME set, the store dir lands under it verbatim/auth."""
    home = tmp_path / "sk-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    assert default_store_dir() == home / "auth"


def test_default_store_dir_posix_default_when_env_unset(monkeypatch, tmp_path: Path):
    """With SPEC_KITTY_HOME unset on POSIX, it stays ``~/.spec-kitty/auth``."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert default_store_dir() == tmp_path / ".spec-kitty" / "auth"


def test_default_store_dir_is_under_runtime_root_nfr005(monkeypatch, tmp_path: Path):
    """NFR-005: no auth material is written outside the resolved runtime root."""
    home = tmp_path / "sk-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    store = default_store_dir()
    assert store.is_relative_to(home)


# ---------------------------------------------------------------------------
# _refresh_lock_path() — FR-003 (refresh lock)
# ---------------------------------------------------------------------------


def test_refresh_lock_honors_spec_kitty_home_posix(monkeypatch, tmp_path: Path):
    """POSIX branch: lock resolves under SPEC_KITTY_HOME when set."""
    home = tmp_path / "sk-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setattr(sys, "platform", "linux")
    assert tm_module._refresh_lock_path() == home / "auth" / "refresh.lock"


def test_refresh_lock_posix_default_when_env_unset(monkeypatch, tmp_path: Path):
    """POSIX branch: env unset ⇒ ``~/.spec-kitty/auth/refresh.lock``."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert (
        tm_module._refresh_lock_path()
        == tmp_path / ".spec-kitty" / "auth" / "refresh.lock"
    )


def test_refresh_lock_windows_branch_honors_spec_kitty_home(
    monkeypatch, tmp_path: Path
):
    """Windows branch (``kernel.paths.is_windows()`` forced True): lock resolves under the env root.

    Setting SPEC_KITTY_HOME makes get_runtime_root() env-driven regardless of
    platform, so the win32 branch lands beside the platform session file under
    the resolved root. ``_refresh_lock_path`` routes its OS check through the
    canonical ``kernel.paths.is_windows`` seam (cross-os-primitive-unification,
    WP03/T012) rather than an inline ``sys.platform`` comparison, so the
    branch is forced via that seam -- faking ``sys.platform`` alone no longer
    has any effect on it.
    """
    home = tmp_path / "sk-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
    assert tm_module._refresh_lock_path() == home / "auth" / "refresh.lock"


# ---------------------------------------------------------------------------
# WindowsFileStorage default — FR-002 + Windows normalization (D4)
# ---------------------------------------------------------------------------


def test_windows_storage_default_honors_spec_kitty_home(monkeypatch, tmp_path: Path):
    """WindowsFileStorage default store resolves under SPEC_KITTY_HOME."""
    home = tmp_path / "sk-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.setattr(sys, "platform", "win32")
    assert WindowsFileStorage().store_path == home / "auth"


def test_windows_storage_default_uses_runtime_root_not_home(
    monkeypatch, tmp_path: Path
):
    """Normalization (DM-01KW1KDHVGWZ0QERDMV1CRJ15S): the win32 default is the
    runtime root's ``auth`` dir, not the previously hardcoded ``~/.spec-kitty``.
    """
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    assert WindowsFileStorage().store_path == get_runtime_root().auth_dir
