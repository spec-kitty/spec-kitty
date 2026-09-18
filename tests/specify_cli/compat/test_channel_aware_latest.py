"""Tests for the rc release-channel opt-in path (T025, C-CHN-2).

Covers:
- ``core.upgrade_probe.probe_pypi`` — channel-aware classification so an
  installed rc build stops reading ``AHEAD_OF_PYPI`` when opted in, while
  the default (unset) path is unchanged (T022).
- ``compat.planner._resolve_latest_version`` / ``_cache_version_key`` — the
  single channel read threaded to the provider call, and folded into the
  nag-cache key so a channel toggle forces a fresh probe (T023).
- ``compat.upgrade_hint.build_upgrade_hint`` — the pinned ``==<rc>`` install
  command (no ``--pre``) that ``_agent_check_payload`` already threads
  ``target_version`` into (T023).

Each test that proves the opt-in behaviour has a sibling proving the
default-off path is unaffected — the C-CHN-1 guarantee is the load-bearing
one; C-CHN-2 must never come at its expense.
"""

from __future__ import annotations

from dataclasses import dataclass
from kernel.clock import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat.cache import NagCache
from specify_cli.compat.planner import Invocation, _cache_version_key, _resolve_latest_version, plan
from specify_cli.compat.provider import FakeLatestVersionProvider, LatestVersionResult
from specify_cli.compat.upgrade_hint import build_upgrade_hint
from specify_cli.core.upgrade_probe import PYPI_JSON_URL, UpgradeChannel, probe_pypi

pytestmark = pytest.mark.fast

_NOW = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


def _make_pypi_payload(latest: str, releases: list[str]) -> dict[str, Any]:
    return {"info": {"version": latest}, "releases": {v: [{"yanked": False}] for v in releases}}


# ---------------------------------------------------------------------------
# probe_pypi channel awareness (T022)
# ---------------------------------------------------------------------------


class TestProbePypiChannelAware:
    @respx.mock
    def test_default_off_ahead_of_pypi_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression guard: the pre-WP05 AHEAD_OF_PYPI scenario is untouched.

        Installed 3.2.0rc7 is newer than the stable 3.1.0, and NOT itself
        published (releases only contains 3.0.0/3.1.0) — with the channel
        unset this must still classify AHEAD_OF_PYPI, exactly as before T022.
        """
        monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0"])))

        result = probe_pypi("3.2.0rc7")

        assert result.channel == UpgradeChannel.AHEAD_OF_PYPI
        assert result.latest_pypi_version == "3.1.0"

    @respx.mock
    def test_explicit_prerelease_false_matches_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0"])))
        default_result = probe_pypi("3.2.0rc7")

        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0"])))
        explicit_result = probe_pypi("3.2.0rc7", prerelease=False)

        assert default_result.channel == explicit_result.channel
        assert default_result.latest_pypi_version == explicit_result.latest_pypi_version

    @respx.mock
    def test_opted_in_rc_build_stops_reading_ahead_of_pypi(self) -> None:
        """C-CHN-2: an installed rc that IS the newest published release
        reclassifies as ALREADY_CURRENT once its own channel is consulted.
        """
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0", "3.2.0rc7"])))

        result = probe_pypi("3.2.0rc7", prerelease=True)

        assert result.channel != UpgradeChannel.AHEAD_OF_PYPI
        assert result.channel == UpgradeChannel.ALREADY_CURRENT
        assert result.latest_pypi_version == "3.2.0rc7"

    @respx.mock
    def test_prerelease_none_resolves_via_channel_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``prerelease=None`` (the production default) reads core.channel."""
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "1")
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0", "3.2.0rc7"])))

        result = probe_pypi("3.2.0rc7")

        assert result.latest_pypi_version == "3.2.0rc7"


# ---------------------------------------------------------------------------
# planner._cache_version_key (T023)
# ---------------------------------------------------------------------------


class TestCacheVersionKey:
    def test_stable_channel_key_is_unchanged(self) -> None:
        assert _cache_version_key("2.0.11", prerelease=False) == "2.0.11"

    def test_prerelease_channel_key_differs_from_stable(self) -> None:
        stable_key = _cache_version_key("2.0.11", prerelease=False)
        rc_key = _cache_version_key("2.0.11", prerelease=True)
        assert rc_key != stable_key

    def test_prerelease_channel_key_is_deterministic(self) -> None:
        first = _cache_version_key("2.0.11", prerelease=True)
        second = _cache_version_key("2.0.11", prerelease=True)
        assert first == second


# ---------------------------------------------------------------------------
# planner._resolve_latest_version threads prerelease to the provider (T022/T023)
# ---------------------------------------------------------------------------


@dataclass
class _RecordingProvider:
    """Records the ``prerelease`` kwarg it was called with (T022 threading proof)."""

    version: str = "9.9.9"
    calls: list[bool] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:
        assert self.calls is not None
        self.calls.append(prerelease)
        return LatestVersionResult(version=self.version, source="pypi", error=None)


class _LegacyProvider:
    """A provider double predating T022 — no ``prerelease`` parameter at all.

    Regression guard: ``_resolve_latest_version`` must not raise TypeError
    against providers outside this WP's ownership that haven't adopted the
    new keyword (see ``planner._call_provider_get_latest``).
    """

    def __init__(self, version: str) -> None:
        self._version = version
        self.call_count = 0

    def get_latest(self, package: str) -> LatestVersionResult:
        self.call_count += 1
        return LatestVersionResult(version=self._version, source="pypi", error=None)


@dataclass
class _Profile:
    package_name: str = "spec-kitty-cli"


class TestResolveLatestVersionThreadsChannel:
    def _call(self, *, provider: Any, prerelease: bool, tmp_path: Path) -> tuple[str | None, str, Any]:
        cache = NagCache(tmp_path / "upgrade-nag.json")
        return _resolve_latest_version(
            cache_data_fresh=False,
            cache_record=None,
            preference_record=None,
            latest_version_provider=provider,
            profile=_Profile(),
            nag_cache=cache,
            installed_version="2.0.11",
            now=_NOW,
            prerelease=prerelease,
        )

    def test_prerelease_true_is_threaded_to_the_provider(self, tmp_path: Path) -> None:
        provider = _RecordingProvider()
        self._call(provider=provider, prerelease=True, tmp_path=tmp_path)
        assert provider.calls == [True]

    def test_prerelease_false_is_threaded_to_the_provider(self, tmp_path: Path) -> None:
        provider = _RecordingProvider()
        self._call(provider=provider, prerelease=False, tmp_path=tmp_path)
        assert provider.calls == [False]

    def test_legacy_provider_without_prerelease_kwarg_does_not_raise(self, tmp_path: Path) -> None:
        provider = _LegacyProvider(version="9.9.9")
        latest_version, source, _fetched_at = self._call(provider=provider, prerelease=True, tmp_path=tmp_path)
        assert provider.call_count == 1
        assert latest_version == "9.9.9"
        assert source == "pypi"


# ---------------------------------------------------------------------------
# Full-stack plan() channel awareness (C-CHN-1 default-off + C-CHN-2 opt-in)
# ---------------------------------------------------------------------------


def _invocation() -> Invocation:
    return Invocation(
        command_path=("status",),
        raw_args=(),
        is_help=False,
        is_version=False,
        flag_no_nag=False,
        env_ci=False,
        stdout_is_tty=True,
    )


class TestPlanChannelAwareEndToEnd:
    def test_default_off_never_surfaces_the_rc(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """C-CHN-1 at the full plan() level: unset channel, rc on the index → stable latest."""
        monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
        provider = FakeLatestVersionProvider(version="1.9.0", prerelease_version="2.0.0rc1")

        result = plan(
            _invocation(),
            latest_version_provider=provider,
            nag_cache=NagCache(tmp_path / "upgrade-nag.json"),
            now=_NOW,
        )

        assert result.cli_status.latest_version == "1.9.0"

    def test_opted_in_surfaces_the_rc(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """C-CHN-2 at the full plan() level: opted in → the rc is surfaced."""
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "1")
        provider = FakeLatestVersionProvider(version="1.9.0", prerelease_version="2.0.0rc1")

        result = plan(
            _invocation(),
            latest_version_provider=provider,
            nag_cache=NagCache(tmp_path / "upgrade-nag.json"),
            now=_NOW,
        )

        assert result.cli_status.latest_version == "2.0.0rc1"

    def test_toggling_the_channel_forces_a_fresh_probe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T023: switching SPEC_KITTY_PRERELEASE re-probes instead of trusting
        a cache record written under the other channel."""
        cache = NagCache(tmp_path / "upgrade-nag.json")
        provider = FakeLatestVersionProvider(version="1.9.0", prerelease_version="2.0.0rc1")

        monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
        stable_result = plan(_invocation(), latest_version_provider=provider, nag_cache=cache, now=_NOW)
        assert stable_result.cli_status.latest_version == "1.9.0"

        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "1")
        rc_result = plan(_invocation(), latest_version_provider=provider, nag_cache=cache, now=_NOW)
        assert rc_result.cli_status.latest_version == "2.0.0rc1"


# ---------------------------------------------------------------------------
# Pinned rc install command (T023) — no --pre, ==<rc> pin
# ---------------------------------------------------------------------------


class TestPinnedRcInstallCommand:
    def test_uv_tool_pins_the_rc_target_version(self) -> None:
        hint = build_upgrade_hint(InstallMethod.UV_TOOL, target_version="1.2.3rc1")
        assert hint.command is not None
        assert "spec-kitty-cli==1.2.3rc1" in hint.command

    def test_pinned_command_never_contains_pre_flag(self) -> None:
        hint = build_upgrade_hint(InstallMethod.UV_TOOL, target_version="1.2.3rc1")
        assert hint.command is not None
        assert "--pre" not in hint.command
