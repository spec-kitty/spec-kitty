"""``pack_fetch.default_cache_root`` location pin (#6481): no git, unlike ``test_pack_fetch``."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.packs.pack_fetch import default_cache_root
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("platform", ["linux", "darwin", "windows"])
@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"XDG_CACHE_HOME": "xdg", "LOCALAPPDATA": "lad"}, "xdg"),
        ({"LOCALAPPDATA": "lad", "XDG_STATE_HOME": "state"}, "home/.cache"),
    ],
)
def test_default_cache_root_pinned_per_platform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str, env: dict[str, str], expected: str) -> None:
    """#6481: the XDG rule on every platform, Windows included; ``LOCALAPPDATA`` is never read."""
    fake_platform(monkeypatch, tmp_path, platform, env)
    assert default_cache_root() == tmp_path / expected / "spec-kitty" / "open-packs"
