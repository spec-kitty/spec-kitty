"""Cross-resolver contract: kernel and specify_cli agree on the runtime root.

``kernel.paths.get_runtime_state_root()`` and
``specify_cli.paths.windows_paths.get_runtime_root().base`` each claim (in
their own docstrings) to resolve to *exactly* the same directory. Before this
test existed the two diverged on one branch: only the ``specify_cli`` side
wrapped its Windows ``platformdirs.user_data_dir`` call in a
``try/except Exception`` fallback to ``Path.home() / ".spec-kitty"`` --
``kernel.paths`` let the exception propagate. This module pins parity across
every resolution branch, including that platformdirs-failure edge, so the two
resolvers can never silently drift apart again.

No test here touches the real ``HOME`` -- every branch is driven through
``monkeypatch``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import kernel.paths as kernel_paths
from specify_cli.paths import windows_paths


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_parity_with_spec_kitty_home_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both resolvers use ``SPEC_KITTY_HOME`` verbatim, on every platform."""
    env_home = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(env_home))

    kernel_result = kernel_paths.get_runtime_state_root()
    cli_result = windows_paths.get_runtime_root().base

    assert kernel_result == env_home
    assert cli_result == env_home
    assert kernel_result == cli_result


def test_parity_on_posix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both resolvers fall back to ``~/.spec-kitty`` on a non-Windows platform."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: "linux")

    kernel_result = kernel_paths.get_runtime_state_root()
    cli_result = windows_paths.get_runtime_root().base

    assert kernel_result == fake_home / ".spec-kitty"
    assert cli_result == fake_home / ".spec-kitty"
    assert kernel_result == cli_result


def test_parity_on_windows_nominal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both resolvers use the same platformdirs base when it resolves cleanly."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    fake_local_appdata = tmp_path / "LocalAppData" / "spec-kitty"
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: "win32")
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *_args, **_kwargs: str(fake_local_appdata),
    )

    kernel_result = kernel_paths.get_runtime_state_root()
    cli_result = windows_paths.get_runtime_root().base

    assert kernel_result == fake_local_appdata
    assert cli_result == fake_local_appdata
    assert kernel_result == cli_result


def test_parity_on_windows_platformdirs_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Both resolvers fall back to ``~/.spec-kitty`` identically when
    ``platformdirs.user_data_dir`` raises (e.g. a constrained/simulated
    Windows runtime with no ctypes/registry access) -- the divergence this
    contract test was written to close.
    """
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: "win32")

    def _raise(*_args: object, **_kwargs: object) -> str:
        raise ImportError("ctypes HRESULT unavailable")

    monkeypatch.setattr("platformdirs.user_data_dir", _raise)

    kernel_result = kernel_paths.get_runtime_state_root()
    cli_result = windows_paths.get_runtime_root().base

    assert kernel_result == fake_home / ".spec-kitty"
    assert cli_result == fake_home / ".spec-kitty"
    assert kernel_result == cli_result
