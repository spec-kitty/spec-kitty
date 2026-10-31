"""One authority: every caller resolves under the same per-user directory (#6488).

The defect this guards against is not a wrong path, it is *disagreement*: each caller
carried its own copy of the rule and its own pin, so nothing compared them. On macOS the
upgrade, pack and service caches resolved to ``~/.cache/spec-kitty`` while the upgrade-nag
cache resolved to ``~/Library/Caches/spec-kitty``, and every per-caller test was green.

This test therefore asserts agreement, not a literal path: for one faked platform it
resolves **the production entry points themselves** and requires each answer to be exactly
the authority's directory plus that caller's own leaf. Revert any single caller to its
pre-#6488 composition and the corresponding case goes red, naming the caller.

Positive control: the same fixture also asserts the six answers are six distinct paths
under one tree, so a probe that always returned ``True`` (or a fixture where all six
trivially collapsed to one path) cannot pass.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path

import pytest

from kernel.user_dirs import user_cache_dir, user_config_dir, user_state_dir
from tests.kernel._user_dirs_pins import fake_platform

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: ``(caller label, module, attribute, kind, leaf segments)`` -- one row per production
#: resolver. An empty leaf means the resolver answers with the directory itself. The leaf
#: is the caller's own business; the base must come from the authority.
_CALLERS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("upgrade_notifier", "specify_cli.core.upgrade_notifier", "_default_cache_path", "cache", ("upgrade-check.json",)),
    ("compat.cache", "specify_cli.compat.cache", "_resolve_cache_dir", "cache", ()),
    ("pack_fetch", "charter.offering.packs.pack_fetch", "default_cache_root", "cache", ("open-packs",)),
    ("service_artifacts", "kernel.service_artifacts", "default_cache_root", "cache", ("services",)),
    ("runtime_pkg_notice", "runtime.next._runtime_pkg_notice", "_marker_path", "state", (".spec-kitty-runtime-cutover-notice-shown",)),
    ("compat.config", "specify_cli.compat.config", "_resolve_config_dir", "config", ()),
)

_AUTHORITY: dict[str, Callable[[], Path]] = {"cache": user_cache_dir, "state": user_state_dir, "config": user_config_dir}

_PLATFORMS = ("linux", "darwin", "windows")


def _call(module_name: str, attribute: str) -> Path:
    """Invoke one production resolver and normalise its return type to ``Path``."""
    resolver = getattr(import_module(module_name), attribute)
    return Path(resolver())


def _base_of(resolved: Path, leaf: tuple[str, ...]) -> Path:
    """The authority directory a resolved path sits under."""
    return resolved if not leaf else resolved.parents[len(leaf) - 1]


@pytest.mark.parametrize("platform", _PLATFORMS)
@pytest.mark.parametrize(("label", "module_name", "attribute", "kind", "leaf"), _CALLERS, ids=[c[0] for c in _CALLERS])
def test_caller_resolves_under_the_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    label: str,
    module_name: str,
    attribute: str,
    kind: str,
    leaf: tuple[str, ...],
) -> None:
    """Each caller == authority directory + its own leaf, on every platform."""
    fake_platform(monkeypatch, tmp_path, platform, {"LOCALAPPDATA": "lad", "XDG_CACHE_HOME": "xdg", "XDG_STATE_HOME": "xdg", "XDG_CONFIG_HOME": "xdg"})
    authority = _AUTHORITY[kind]()
    expected = authority if not leaf else authority.joinpath(*leaf)
    resolved = _call(module_name, attribute)
    assert resolved == expected, f"{label} ({kind}) left the single authority on {platform}: {resolved} is not under {authority}"


@pytest.mark.parametrize("platform", _PLATFORMS)
def test_all_callers_agree_on_one_tree_per_platform(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str) -> None:
    """The four cache callers share one directory; state and config agree where the OS says so."""
    fake_platform(monkeypatch, tmp_path, platform, {"LOCALAPPDATA": "lad"})
    cache_roots = {_base_of(_call(module, attr), leaf) for label, module, attr, kind, leaf in _CALLERS if kind == "cache"}
    assert len(cache_roots) == 1, f"cache callers disagree on {platform}: {sorted(map(str, cache_roots))}"
    assert cache_roots.pop() == user_cache_dir()
    marker = _call("runtime.next._runtime_pkg_notice", "_marker_path")
    assert marker.parent == user_state_dir()
    config_dir = Path(import_module("specify_cli.compat.config")._resolve_config_dir())
    assert config_dir == user_config_dir()


@pytest.mark.parametrize("platform", _PLATFORMS)
def test_the_six_leaves_are_distinct(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str) -> None:
    """Positive control: the probe sees six separate files, not one collapsed path."""
    fake_platform(monkeypatch, tmp_path, platform, {"LOCALAPPDATA": "lad"})
    resolved = {_call(module, attr) for label, module, attr, kind, leaf in _CALLERS}
    assert len(resolved) == len(_CALLERS), sorted(map(str, resolved))
