"""Windows runtime-root consistency tests.

Tracker and kernel runtime state resolve through the shared runtime root: on
Windows it lives under the platformdirs LocalAppData base
(``%LOCALAPPDATA%\\spec-kitty``) and honors ``SPEC_KITTY_HOME`` when set.
"""
from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.windows_ci
def test_runtime_consumers_share_single_windows_root() -> None:
    """Tracker/kernel runtime state resolves under RuntimeRoot.base.

    (The sync/daemon and auth sections of this probe died with the sync
    transport, issue #5, and the hosted-surface removal, issue #6164.)
    """
    from specify_cli.paths import get_runtime_root

    root = get_runtime_root()
    assert root.platform == "win32", (
        f"This test must run on Windows; platform={root.platform}"
    )
    base_str = str(root.base).lower()

    # Tracker
    from specify_cli.tracker import credentials

    tracker_root = credentials._tracker_root()
    assert base_str in str(tracker_root).lower(), (
        f"Tracker root {tracker_root} is not under unified root {root.base}"
    )

    # kernel.paths — get_kittify_home() Windows branch uses the same
    # platformdirs call (app="spec-kitty", roaming=False) as get_runtime_root(),
    # so both must resolve to the same %LOCALAPPDATA%\spec-kitty base.
    from kernel import paths as kernel_paths

    kittify_home = kernel_paths.get_kittify_home()
    assert base_str in str(kittify_home).lower(), (
        f"kernel.paths.get_kittify_home() resolves to {kittify_home}, "
        f"outside the unified Windows root {root.base}"
    )


@pytest.mark.windows_ci
def test_runtime_root_platform_field_is_win32() -> None:
    """RuntimeRoot.platform is 'win32' when running on Windows."""
    from specify_cli.paths import get_runtime_root

    root = get_runtime_root()
    assert root.platform == "win32"


@pytest.mark.windows_ci
def test_runtime_root_base_is_absolute() -> None:
    """RuntimeRoot.base is an absolute path."""
    from specify_cli.paths import get_runtime_root

    root = get_runtime_root()
    assert root.base.is_absolute(), f"Expected absolute base path, got: {root.base}"


# ---------------------------------------------------------------------------
# SPEC_KITTY_HOME precedence flows into the unified runtime root (FR-011/FR-012).
# These run on every platform (no windows_ci gate) by pinning the platform-
# detection source, proving the env base is honored cross-platform and that the
# RuntimeRoot-derived directories inherit it. (Wiring the per-surface consumers
# — tracker — through this base is downstream WP02-WP05 work and is
# intentionally NOT asserted here.)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_spec_kitty_home_sets_runtime_base_on_all_platforms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str
) -> None:
    """A non-empty SPEC_KITTY_HOME is the unified base on every platform."""
    from specify_cli.paths import get_runtime_root, windows_paths

    base = tmp_path / "env-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(base))
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: platform)

    root = get_runtime_root()

    assert root.platform == platform
    assert root.base == base
    assert root.tracker_dir == base / "tracker"


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_empty_spec_kitty_home_falls_through_to_posix_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str
) -> None:
    """An empty SPEC_KITTY_HOME is falsy ⇒ POSIX ``~/.spec-kitty`` default."""
    from specify_cli.paths import get_runtime_root, windows_paths

    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: fake_home))
    monkeypatch.setattr(windows_paths, "_current_platform", lambda: platform)
    monkeypatch.setenv("SPEC_KITTY_HOME", "")

    assert get_runtime_root().base == fake_home / ".spec-kitty"
