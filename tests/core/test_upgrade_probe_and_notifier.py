"""Behavior tests for the WP09 upgrade probe + notifier.

Per the WP09 contract (`contracts/upgrade-probe-and-notifier.md`) and the
``function-over-form-testing`` tactic, these tests:

- Mock the network boundary via ``respx`` (httpx-native).
- Assert on observable behavior (returned channel, emitted message
  substring, return value of ``maybe_emit_upgrade_notice``), never on
  internal call counts.
- Inject time via the ``now`` parameter rather than ``freezegun`` (the
  notifier exposes ``now`` precisely so tests stay simple).
- Use ``monkeypatch`` for env-var manipulation so leakage to other tests
  is impossible.
"""

from __future__ import annotations

import time
from kernel.clock import datetime, timedelta, UTC
from io import StringIO
from pathlib import Path

import httpx
import pytest
import respx
from rich.console import Console

from specify_cli.core.upgrade_notifier import (
    OPT_OUT_ENV_VAR,
    TTL_SUCCESS_SECONDS,
    TTL_UNKNOWN_SECONDS,
    maybe_emit_upgrade_notice,
)
from specify_cli.core.upgrade_probe import (
    PYPI_JSON_URL,
    UpgradeChannel,
    UpgradeProbeResult,
    probe_pypi,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_pypi_payload(latest: str, releases: list[str]) -> dict:
    """Build a minimal PyPI JSON metadata payload."""
    return {
        "info": {"version": latest},
        "releases": {v: [{"yanked": False}] for v in releases},
    }


def _capture_console() -> tuple[Console, StringIO]:
    """Return a Rich Console that writes into a StringIO for assertion."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=200)
    return console, buf


# ---------------------------------------------------------------------------
# probe_pypi: channel classification
# ---------------------------------------------------------------------------


class TestProbeChannelClassification:
    """The channel matrix from contracts/upgrade-probe-and-notifier.md."""

    @respx.mock
    def test_already_current_when_installed_equals_latest(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.1.0", "3.2.0"])))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.ALREADY_CURRENT
        assert result.latest_pypi_version == "3.2.0"
        assert result.error is None

    @respx.mock
    def test_ahead_of_pypi_when_installed_greater_than_latest(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0"])))

        result = probe_pypi("3.2.0rc7")

        assert result.channel == UpgradeChannel.AHEAD_OF_PYPI
        assert result.latest_pypi_version == "3.1.0"

    @respx.mock
    def test_no_upgrade_path_when_installed_not_in_releases(self) -> None:
        # Installed version "0.0.0-dev" is NOT a published release.
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.1.0", "3.2.0"])))

        result = probe_pypi("0.0.1.dev0")

        assert result.channel == UpgradeChannel.NO_UPGRADE_PATH
        assert result.latest_pypi_version == "3.2.0"

    @respx.mock
    def test_upgrade_available_when_installed_is_older_published_release(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.1", ["3.2.0", "3.2.1"])))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UPGRADE_AVAILABLE
        assert result.latest_pypi_version == "3.2.1"

    @respx.mock
    def test_unknown_on_http_500(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(500))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN
        assert result.error is not None
        assert result.latest_pypi_version is None

    @respx.mock
    def test_unknown_on_http_404(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(404))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN
        assert result.error is not None

    @respx.mock
    def test_unknown_on_connection_error(self) -> None:
        respx.get(PYPI_JSON_URL).mock(side_effect=httpx.ConnectError("boom"))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN
        assert result.error is not None
        assert "ConnectError" in result.error or "boom" in result.error

    @respx.mock
    def test_unknown_on_timeout(self) -> None:
        respx.get(PYPI_JSON_URL).mock(side_effect=httpx.TimeoutException("slow"))

        result = probe_pypi("3.2.0", timeout_s=0.1)

        assert result.channel == UpgradeChannel.UNKNOWN
        assert result.error is not None

    @respx.mock
    def test_unknown_on_malformed_json_payload(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, text="not-json"))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN

    @respx.mock
    def test_unknown_on_missing_info_version(self) -> None:
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json={"info": {}, "releases": {}}))

        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN

    @respx.mock
    def test_probe_never_raises_on_unexpected_exception(self) -> None:
        respx.get(PYPI_JSON_URL).mock(side_effect=RuntimeError("totally unexpected"))

        # Must not raise.
        result = probe_pypi("3.2.0")

        assert result.channel == UpgradeChannel.UNKNOWN


# ---------------------------------------------------------------------------
# maybe_emit_upgrade_notice: opt-out
# ---------------------------------------------------------------------------


class TestOptOut:
    def test_opt_out_returns_false_and_emits_no_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv(OPT_OUT_ENV_VAR, "1")
        cache_path = tmp_path / "upgrade-check.json"
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)

        assert emitted is False
        assert buf.getvalue() == ""
        # Cache must not be touched when opt-out is set.
        assert not cache_path.exists()

    def test_opt_out_truthy_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        cache_path = tmp_path / "upgrade-check.json"
        for value in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv(OPT_OUT_ENV_VAR, value)
            console, buf = _capture_console()
            assert maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path) is False
            assert buf.getvalue() == ""

    def test_opt_out_falsy_values_do_not_disable(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Empty/0/false values must NOT disable the check."""
        cache_path = tmp_path / "upgrade-check.json"
        monkeypatch.setenv(OPT_OUT_ENV_VAR, "0")
        # With "0", the function should proceed to probe. We don't care about
        # the result here (no respx mock), only that it doesn't short-circuit
        # on the opt-out check. The probe will return UNKNOWN; no notice is
        # emitted for UNKNOWN; the function returns False but for a different
        # reason. We can detect that the cache was written.
        console, _ = _capture_console()
        maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)
        # The cache should be touched (UNKNOWN result persisted) — proves the
        # function did NOT short-circuit on opt-out.
        assert cache_path.exists()


# ---------------------------------------------------------------------------
# maybe_emit_upgrade_notice: notice content per channel
# ---------------------------------------------------------------------------


class TestNoticeContent:
    @respx.mock
    def test_already_current_emits_latest_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=tmp_path / "c.json")

        assert emitted is True
        assert "3.2.0" in buf.getvalue()
        assert "latest supported" in buf.getvalue()

    @respx.mock
    def test_ahead_of_pypi_emits_ahead_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.1.0", ["3.0.0", "3.1.0"])))
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0rc7", console=console, cache_path=tmp_path / "c.json")

        assert emitted is True
        out = buf.getvalue()
        assert "3.2.0rc7" in out
        assert "ahead" in out.lower()
        assert "3.1.0" in out

    @respx.mock
    def test_no_upgrade_path_emits_non_pypi_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("0.0.1.dev0", console=console, cache_path=tmp_path / "c.json")

        assert emitted is True
        out = buf.getvalue()
        assert "non-PyPI" in out or "no PyPI upgrade path" in out.lower()

    @respx.mock
    def test_unknown_emits_no_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(500))
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=tmp_path / "c.json")

        assert emitted is False
        assert buf.getvalue() == ""

    @respx.mock
    def test_upgrade_available_emits_no_no_upgrade_notice(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.1", ["3.2.0", "3.2.1"])))
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=tmp_path / "c.json")

        assert emitted is False
        assert buf.getvalue() == ""


# ---------------------------------------------------------------------------
# maybe_emit_upgrade_notice: cache behavior
# ---------------------------------------------------------------------------


class TestCache:
    @respx.mock
    def test_cache_is_persisted_after_successful_probe(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        cache_path = tmp_path / "c.json"
        console, _ = _capture_console()

        maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)

        assert cache_path.exists()
        import json

        data = json.loads(cache_path.read_text())
        assert data["channel"] == "already_current"
        assert data["installed_version"] == "3.2.0"
        assert data["ttl_seconds"] == TTL_SUCCESS_SECONDS

    @respx.mock
    def test_unknown_uses_short_ttl_in_cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(500))
        cache_path = tmp_path / "c.json"
        console, _ = _capture_console()

        maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)

        import json

        data = json.loads(cache_path.read_text())
        assert data["channel"] == "unknown"
        assert data["ttl_seconds"] == TTL_UNKNOWN_SECONDS

    @respx.mock
    def test_cache_fresh_within_ttl_suppresses_repeat_notice_for_already_current(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """AC #4: identical-channel-within-TTL suppression for ALREADY_CURRENT."""
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        cache_path = tmp_path / "c.json"
        t0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

        # First call: emits the notice.
        console1, buf1 = _capture_console()
        e1 = maybe_emit_upgrade_notice("3.2.0", console=console1, cache_path=cache_path, now=t0)
        assert e1 is True
        assert "3.2.0" in buf1.getvalue()

        # Second call within TTL: cache is fresh and previous was also
        # ALREADY_CURRENT → suppress.
        console2, buf2 = _capture_console()
        t1 = t0 + timedelta(hours=1)
        e2 = maybe_emit_upgrade_notice("3.2.0", console=console2, cache_path=cache_path, now=t1)
        assert e2 is False
        assert buf2.getvalue() == ""

    @respx.mock
    def test_cache_stale_after_ttl_re_probes_and_re_emits(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """After TTL expires, the cache is stale → re-probe + re-emit."""
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        cache_path = tmp_path / "c.json"
        t0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

        # Prime the cache.
        console1, _ = _capture_console()
        maybe_emit_upgrade_notice("3.2.0", console=console1, cache_path=cache_path, now=t0)

        # Advance past TTL: cache stale → re-probe → ALREADY_CURRENT again,
        # but the previous cache entry was NOT fresh, so the suppression
        # rule (which checks `cached_was_fresh`) does NOT apply → emit.
        t1 = t0 + timedelta(seconds=TTL_SUCCESS_SECONDS + 10)
        console2, buf2 = _capture_console()
        e2 = maybe_emit_upgrade_notice("3.2.0", console=console2, cache_path=cache_path, now=t1)
        assert e2 is True
        assert "3.2.0" in buf2.getvalue()

    @respx.mock
    def test_cache_invalidated_when_installed_version_changes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """If the user upgrades mid-cache-window, the cache is stale."""
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.1", ["3.2.0", "3.2.1"])))
        cache_path = tmp_path / "c.json"
        t0 = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)

        # First call as 3.2.0 (installed in releases but older than latest).
        # The no-upgrade notifier stays silent and caches the probe result;
        # the existing upgrade nag owns the actual upgrade-available message.
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.1", ["3.2.0", "3.2.1"])))
        console1, _ = _capture_console()
        maybe_emit_upgrade_notice("3.2.0", console=console1, cache_path=cache_path, now=t0)

        import json

        cached_v1 = json.loads(cache_path.read_text())["installed_version"]
        assert cached_v1 == "3.2.0"

        # Now user upgraded to 3.2.1 — within TTL window of the first call.
        t1 = t0 + timedelta(minutes=5)
        console2, buf2 = _capture_console()
        maybe_emit_upgrade_notice("3.2.1", console=console2, cache_path=cache_path, now=t1)

        cached_v2 = json.loads(cache_path.read_text())["installed_version"]
        # The cache must have been rebuilt with the new installed version.
        assert cached_v2 == "3.2.1"

    @respx.mock
    def test_corrupt_cache_file_is_treated_as_miss(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        cache_path = tmp_path / "c.json"
        cache_path.write_text("definitely-not-json{[")
        console, buf = _capture_console()

        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)

        # The corrupt cache is ignored; a fresh probe runs and emits.
        assert emitted is True
        assert "3.2.0" in buf.getvalue()


# ---------------------------------------------------------------------------
# maybe_emit_upgrade_notice: failure containment
# ---------------------------------------------------------------------------


class TestFailureContainment:
    def test_notifier_returns_cleanly_when_probe_explodes(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The notifier must never re-raise probe-layer exceptions."""
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)

        # Force the probe to raise by patching it. The notifier's outer
        # try/except must catch this.
        def boom(*args, **kwargs):
            raise RuntimeError("synthetic")

        monkeypatch.setattr("specify_cli.core.upgrade_notifier.probe_pypi", boom)

        console, buf = _capture_console()
        emitted = maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=tmp_path / "c.json")

        assert emitted is False
        assert buf.getvalue() == ""

    def test_probe_swallows_all_exceptions_to_unknown(self) -> None:
        """probe_pypi itself must not raise on any failure mode."""

        # Use a transport that raises a non-httpx exception (rare path).
        class ExplodingTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                raise RuntimeError("synthetic exception")

        result = probe_pypi("3.2.0", transport=ExplodingTransport())

        assert result.channel == UpgradeChannel.UNKNOWN
        assert result.error is not None


# ---------------------------------------------------------------------------
# maybe_emit_upgrade_notice: integration with should_check_version
# ---------------------------------------------------------------------------


class TestVersionCheckerIntegration:
    def test_maybe_emit_no_upgrade_notice_skips_for_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The helper must reuse should_check_version — init is skipped."""
        from specify_cli.core.version_checker import maybe_emit_no_upgrade_notice

        # Even if the probe would otherwise run, "init" is in the skip list,
        # so the helper must return False without touching the notifier.
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)

        # If the notifier WERE called, we'd see network attempts. We don't
        # mock respx here — if a real probe runs, the test machine's
        # network state would surface in this test (slow / unstable).
        # Instead we trust that an early-return on should_check_version
        # short-circuits before the import. The contract is: "init" skips.
        result = maybe_emit_no_upgrade_notice("init")
        assert result is False

    def test_maybe_emit_no_upgrade_notice_swallows_exceptions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the notifier raises somehow, the helper must still return False."""
        from specify_cli.core import version_checker

        def boom(*args, **kwargs):
            raise RuntimeError("synthetic")

        # Patch the lazy-imported notifier function to explode.
        import specify_cli.core.upgrade_notifier as un

        monkeypatch.setattr(un, "maybe_emit_upgrade_notice", boom)

        result = version_checker.maybe_emit_no_upgrade_notice("some-real-command")
        assert result is False


# ---------------------------------------------------------------------------
# Performance: cache-warm path under 100 ms (NFR-004)
# ---------------------------------------------------------------------------


@pytest.mark.performance
class TestPerformance:
    @respx.mock
    def test_cache_warm_path_under_100ms(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """NFR-004: cache-warm invocations must complete in <=100 ms (avg over 10)."""
        monkeypatch.delenv(OPT_OUT_ENV_VAR, raising=False)
        respx.get(PYPI_JSON_URL).mock(return_value=httpx.Response(200, json=_make_pypi_payload("3.2.0", ["3.2.0"])))
        cache_path = tmp_path / "c.json"

        # Warm the cache.
        console, _ = _capture_console()
        maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)
        assert cache_path.exists()

        # Measure 10 subsequent invocations.
        start = time.perf_counter()
        for _ in range(10):
            console, _ = _capture_console()
            maybe_emit_upgrade_notice("3.2.0", console=console, cache_path=cache_path)
        elapsed_per_call = (time.perf_counter() - start) / 10

        assert elapsed_per_call < 0.1, f"cache-warm path took {elapsed_per_call * 1000:.1f}ms — should be <100ms"


# ---------------------------------------------------------------------------
# Cache path resolution
# ---------------------------------------------------------------------------


class TestCachePath:
    def test_posix_path_honours_xdg_cache_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from specify_cli.core.upgrade_notifier import _default_cache_path

        if __import__("os").name == "nt":
            pytest.skip("POSIX-only test")

        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        path = _default_cache_path()
        assert path == tmp_path / "spec-kitty" / "upgrade-check.json"

    def test_posix_path_falls_back_to_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.core.upgrade_notifier import _default_cache_path

        if __import__("os").name == "nt":
            pytest.skip("POSIX-only test")

        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        path = _default_cache_path()
        assert path.name == "upgrade-check.json"
        assert "spec-kitty" in str(path)


# ---------------------------------------------------------------------------
# Probe result serialization round-trip (covers cache deserializer paths)
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip(self) -> None:
        from specify_cli.core.upgrade_notifier import (
            _deserialize_result,
            _serialize_result,
        )

        original = UpgradeProbeResult(
            installed_version="3.2.0",
            latest_pypi_version="3.2.0",
            channel=UpgradeChannel.ALREADY_CURRENT,
            probed_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
            error=None,
            releases=("3.1.0", "3.2.0"),
        )

        data = _serialize_result(original, TTL_SUCCESS_SECONDS)
        restored = _deserialize_result(data)

        assert restored is not None
        assert restored.installed_version == "3.2.0"
        assert restored.channel == UpgradeChannel.ALREADY_CURRENT
        assert restored.releases == ("3.1.0", "3.2.0")

    def test_deserialize_returns_none_on_missing_keys(self) -> None:
        from specify_cli.core.upgrade_notifier import _deserialize_result

        assert _deserialize_result({}) is None
        assert _deserialize_result({"installed_version": "3.2.0"}) is None
