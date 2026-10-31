"""``pack_fetch.default_cache_root`` location pin (#6488): no git, unlike ``test_pack_fetch``."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.packs.pack_fetch import default_cache_root
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        # The pre-#6488 helper applied the XDG rule on every platform, Windows included.
        ("linux", {"XDG_CACHE_HOME": "xdg", "LOCALAPPDATA": "lad"}, ("xdg", "spec-kitty")),
        ("linux", {}, ("home", ".cache", "spec-kitty")),
        ("darwin", {"XDG_CACHE_HOME": "xdg"}, ("xdg", "spec-kitty")),
        ("darwin", {}, ("home", "Library", "Caches", "spec-kitty")),
        # platformdirs gives Windows no XDG branch: %LOCALAPPDATA% wins and the cache
        # directory carries the opinionated ``Cache`` level.
        ("windows", {"LOCALAPPDATA": "lad", "XDG_CACHE_HOME": "ignored"}, ("lad", "spec-kitty", "Cache")),
        ("windows", {"LOCALAPPDATA": "lad"}, ("lad", "spec-kitty", "Cache")),
    ],
)
def test_default_cache_root_pinned_per_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    env: dict[str, str],
    expected: tuple[str, ...],
) -> None:
    """#6488: one authority, so ``open-packs`` sits under the platform's cache directory."""
    fake_platform(monkeypatch, tmp_path, platform, env)
    assert default_cache_root() == tmp_path.joinpath(*expected, "open-packs")
