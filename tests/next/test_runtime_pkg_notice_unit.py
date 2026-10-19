"""Unit tests for the FR-020 stale-runtime deprecation notice.

Per FR-020 of mission ``shared-package-boundary-cutover-01KQ22DS``, the
CLI emits a single one-time notice on stderr if the retired
``spec-kitty-runtime`` PyPI package is still installed in the operator's
environment. The notice points at the migration runbook.

These tests verify the gating logic without exercising the live
``next_step`` command path.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.next import _runtime_pkg_notice as notice_mod

pytestmark = pytest.mark.fast


def test_notice_suppressed_by_env(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE=1 silences the notice."""
    monkeypatch.setenv("SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE", "1")
    with patch.object(notice_mod, "_runtime_package_installed", return_value=True):
        assert notice_mod.maybe_emit_runtime_pkg_notice() is False
    captured = capsys.readouterr()
    assert "spec-kitty-runtime" not in captured.err


def test_notice_skipped_when_runtime_not_installed(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When spec-kitty-runtime is absent, no notice is emitted."""
    monkeypatch.delenv("SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE", raising=False)
    with patch.object(notice_mod, "_runtime_package_installed", return_value=False):
        assert notice_mod.maybe_emit_runtime_pkg_notice() is False
    captured = capsys.readouterr()
    assert captured.err == ""


def test_runtime_package_missing_distribution_returns_false() -> None:
    """PackageNotFoundError is the normal post-cutover target state."""
    from importlib import metadata

    with patch.object(metadata, "distribution", side_effect=metadata.PackageNotFoundError):
        assert notice_mod._runtime_package_installed() is False


def test_notice_emitted_on_first_invocation(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First invocation with the package installed emits the notice."""
    monkeypatch.delenv("SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE", raising=False)
    marker_path = tmp_path / "marker"
    with patch.object(notice_mod, "_runtime_package_installed", return_value=True), \
         patch.object(notice_mod, "_marker_path", return_value=marker_path):
        emitted = notice_mod.maybe_emit_runtime_pkg_notice()

    assert emitted is True
    captured = capsys.readouterr()
    assert "spec-kitty-runtime" in captured.err
    assert "pip uninstall" in captured.err
    assert "shared-package-boundary-cutover-01KQ22DS" in captured.err
    assert marker_path.exists()


def test_notice_silent_on_repeat_invocation(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marker file present -> notice is not re-emitted."""
    monkeypatch.delenv("SPEC_KITTY_SUPPRESS_RUNTIME_NOTICE", raising=False)
    marker_path = tmp_path / "marker"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.touch()  # pre-existing marker == previous invocation already emitted

    with patch.object(notice_mod, "_runtime_package_installed", return_value=True), \
         patch.object(notice_mod, "_marker_path", return_value=marker_path):
        emitted = notice_mod.maybe_emit_runtime_pkg_notice()

    assert emitted is False
    captured = capsys.readouterr()
    assert captured.err == ""


def test_runtime_package_not_imported() -> None:
    """The detection MUST NOT import spec_kitty_runtime.

    This is the key FR-020 invariant: detection uses importlib.metadata
    which inspects the installed-distribution metadata without executing
    the package's code. Importing spec_kitty_runtime would re-create the
    dependency this mission retires (FR-002 / C-001).
    """
    import sys

    leaked_before = [k for k in sys.modules if "spec_kitty_runtime" in k]
    notice_mod._runtime_package_installed()
    leaked_after = [k for k in sys.modules if "spec_kitty_runtime" in k]
    assert leaked_after == leaked_before, (
        f"spec_kitty_runtime was imported by the detection: "
        f"new modules = {set(leaked_after) - set(leaked_before)}"
    )


def test_marker_path_uses_xdg_state_home_when_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """XDG_STATE_HOME is honored for marker placement."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    p = notice_mod._marker_path()
    assert p == tmp_path / "spec-kitty" / ".spec-kitty-runtime-cutover-notice-shown"


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"XDG_STATE_HOME": "state", "XDG_CACHE_HOME": "xdg", "LOCALAPPDATA": "lad"}, "state"),
        ({"XDG_CACHE_HOME": "xdg", "LOCALAPPDATA": "lad"}, "home/.cache"),
        ({}, "home/.cache"),
    ],
)
def test_marker_path_pinned_per_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, env: dict[str, str], expected: str
) -> None:
    """#6481: moving onto ``kernel.user_dirs.user_state_dir`` changed no location."""
    from tests.kernel.user_dirs_pins import fake_platform

    fake_platform(monkeypatch, tmp_path, platform, env)
    assert notice_mod._marker_path() == tmp_path / expected / "spec-kitty" / ".spec-kitty-runtime-cutover-notice-shown"
