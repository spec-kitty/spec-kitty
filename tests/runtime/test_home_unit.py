"""Compatibility-surface tests for :mod:`specify_cli.runtime.home`.

Kernel path semantics live in ``tests/kernel/test_paths.py``. This suite keeps
only behavior unique to the historical runtime-home import surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime.home import get_kittify_home, get_package_asset_root


pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestGetKittifyHomeUnix:
    """Unix (macOS/Linux) default path resolution."""

    def test_unix_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: False)
        assert get_kittify_home() == Path.home() / ".kittify"

    def test_returns_path_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: False)
        assert isinstance(get_kittify_home(), Path)

    def test_returns_absolute_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: False)
        assert get_kittify_home().is_absolute()


class TestGetKittifyHomeWindows:
    """Windows keeps a distinct runtime-root compatibility contract."""

    @pytest.mark.windows_ci
    def test_windows_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import platformdirs

        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: True)
        monkeypatch.setattr(
            platformdirs,
            "user_data_dir",
            lambda *_args, **_kwargs: r"C:\Users\test\AppData\Local\kittify",
        )
        assert get_kittify_home() == Path(r"C:\Users\test\AppData\Local\kittify")


class TestSpecKittyHomeEnvOverride:
    """``SPEC_KITTY_HOME`` overrides the platform default."""

    def test_env_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        custom_path = str(tmp_path / "custom-kittify")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom_path)
        assert get_kittify_home() == Path(custom_path)

    def test_env_override_on_windows(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        custom_path = str(tmp_path / "custom-kittify")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom_path)
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: True)
        assert get_kittify_home() == Path(custom_path)

    def test_env_override_returns_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
        assert isinstance(get_kittify_home(), Path)

    def test_empty_env_var_uses_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_HOME", "")
        monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: False)
        assert get_kittify_home() == Path.home() / ".kittify"


def test_package_asset_root_compatibility_surface_delegates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The public legacy import delegates to the kernel authority by identity."""
    expected = tmp_path / "sentinel-missions"
    monkeypatch.setattr(
        "specify_cli.runtime.home.kernel.paths.get_package_asset_root",
        lambda: expected,
    )

    assert get_package_asset_root() is expected
