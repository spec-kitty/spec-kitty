"""``SPEC_KITTY_HOME`` rerouting tests for tracker state (T017, FR-008 / WP04).

These exercise the WP04 reroute: tracker credentials and the tracker DB resolve
under ``get_runtime_root().base`` (honoring ``SPEC_KITTY_HOME``) while preserving
the POSIX *flat* suffixes — ``base/credentials`` and ``base/trackers`` — per
NFR-001 / research.md D3. The POSIX-flat vs Windows-nested divergence
(``_tracker_root()`` returns ``base`` on POSIX but ``base/tracker`` on Windows)
is intentional and is asserted here.

Every test pins both the platform and ``$HOME`` via monkeypatch, so the suite
is deterministic on every OS. Platform pinning patches TWO independent seams
(cross-os-primitive-unification WP04): ``sys.platform``, which still drives
``get_runtime_root()``'s own (out-of-scope-for-WP04) platform detection, and
``kernel.paths.is_windows``, the canonical FR-012 seam that
``credentials._tracker_root()`` itself was migrated onto -- patching only
``sys.platform`` would leave ``is_windows()`` (which reads ``os.name``, never
faked here since that would flip ``pathlib`` to ``WindowsPath``) still
reporting the REAL host platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.tracker import credentials
from specify_cli.tracker.store import build_tracker_scope, default_tracker_db_path


pytestmark = [pytest.mark.unit, pytest.mark.fast]


# Stable scope inputs (hoisted so the literals live in exactly one place).
_PROVIDER = "github"
_WORKSPACE = "acme/widgets"
_SERVER_URL = "https://example.test"
_USERNAME = "octocat"
_TEAM_SLUG = "rocket"


def _expected_scope() -> str:
    return build_tracker_scope(
        provider=_PROVIDER,
        workspace=_WORKSPACE,
        server_url=_SERVER_URL,
        username=_USERNAME,
        team_slug=_TEAM_SLUG,
    )


def _resolved_db_path() -> Path:
    return default_tracker_db_path(
        provider=_PROVIDER,
        workspace=_WORKSPACE,
        server_url=_SERVER_URL,
        username=_USERNAME,
        team_slug=_TEAM_SLUG,
    )


def _set_platform(monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    """Pin the platform seen by ``_tracker_root()`` and ``get_runtime_root()``.

    ``get_runtime_root()`` reads the global ``sys.platform`` directly (out of
    WP04's scope, untouched); ``credentials._tracker_root()`` was migrated
    onto the canonical ``kernel.paths.is_windows()`` seam and binds that name
    into its OWN module namespace at import time (``from kernel.paths import
    is_windows``), so patching ``kernel.paths.is_windows`` would not reach
    it -- patch ``credentials.is_windows`` directly instead. Both seams are
    pinned together so a single ``platform`` value governs both.
    """
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(credentials, "is_windows", lambda: platform == "win32")


def test_tracker_root_posix_flat_under_env_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """POSIX: ``_tracker_root()`` is the env base itself (flat); creds at base/credentials."""
    base = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))
    _set_platform(monkeypatch, "linux")

    assert credentials._tracker_root() == base
    assert credentials._credentials_path() == base / "credentials"


def test_tracker_root_windows_nested_under_env_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Windows: ``_tracker_root()`` keeps the nested ``base/tracker`` suffix."""
    base = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))
    _set_platform(monkeypatch, "win32")

    assert credentials._tracker_root() == base / "tracker"
    assert credentials._credentials_path() == base / "tracker" / "credentials"


def test_tracker_db_path_under_env_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The tracker DB resolves to ``base/trackers/<scope>.db`` under the env root."""
    base = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))
    _set_platform(monkeypatch, "linux")

    assert _resolved_db_path() == base / "trackers" / f"{_expected_scope()}.db"


def test_tracker_db_path_flat_on_windows_under_env_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The store has no platform branch: the DB stays ``base/trackers`` on Windows too."""
    base = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))
    _set_platform(monkeypatch, "win32")

    assert _resolved_db_path() == base / "trackers" / f"{_expected_scope()}.db"


def test_tracker_root_posix_default_when_env_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """POSIX, env unset: creds fall back to ``~/.spec-kitty/credentials`` (NFR-001)."""
    fake_home = tmp_path / "home"
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    _set_platform(monkeypatch, "linux")

    assert credentials._tracker_root() == fake_home / ".spec-kitty"
    assert credentials._credentials_path() == fake_home / ".spec-kitty" / "credentials"


def test_tracker_db_path_posix_default_when_env_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """POSIX, env unset: DB falls back to ``~/.spec-kitty/trackers/<scope>.db`` (NFR-001)."""
    fake_home = tmp_path / "home"
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    _set_platform(monkeypatch, "linux")

    assert _resolved_db_path() == fake_home / ".spec-kitty" / "trackers" / f"{_expected_scope()}.db"
