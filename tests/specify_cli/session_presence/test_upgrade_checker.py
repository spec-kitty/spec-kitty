"""T019 — Tests for UpgradeChecker TTL/cache/background behavior.

All tests use tmp_path and monkeypatch CACHE_PATH to avoid touching ~/.kittify/.
No network calls are made.
"""

from __future__ import annotations

import json
from kernel.clock import timedelta, now_utc_iso, now_utc
from pathlib import Path
from unittest.mock import patch

import pytest

import specify_cli.session_presence.upgrade_check as upgrade_check_module
from specify_cli.session_presence.upgrade_check import TTL_SECONDS, UpgradeChecker

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture
def patched_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch CACHE_PATH to a tmp_path location."""
    cache_file = tmp_path / "last-cli-check.json"
    monkeypatch.setattr(upgrade_check_module, "CACHE_PATH", cache_file)
    monkeypatch.delenv(upgrade_check_module.OPT_OUT_ENV_VAR, raising=False)
    monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
    # Also patch the attribute in the module namespace for class usage
    return cache_file


def _write_cache(path: Path, version: str, age_seconds: int = 0) -> None:
    """Write a cache file with the given version and age."""
    checked_at = (now_utc() - timedelta(seconds=age_seconds)).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"checked_at": checked_at, "latest_version": version}),
        encoding="utf-8",
    )


class TestGetAvailableVersion:
    def test_opt_out_returns_none_even_when_cache_exists(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SPEC_KITTY_NO_UPGRADE_CHECK disables cached upgrade notices."""
        _write_cache(patched_cache, "9.9.9", age_seconds=60)
        monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
        checker = UpgradeChecker()
        assert checker.get_available_version() is None

    def test_cache_miss_no_file_returns_none(self, patched_cache: Path) -> None:
        """Cache miss (no file): get_available_version() returns None."""
        checker = UpgradeChecker()
        assert checker.get_available_version() is None

    def test_cache_hit_within_ttl(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cache hit within TTL: returns cached version, check_in_background NOT called."""
        _write_cache(patched_cache, "3.3.0", age_seconds=60)  # fresh
        checker = UpgradeChecker()
        with patch.object(checker, "check_in_background") as mock_bg:
            result = checker.get_available_version()
        assert result == "3.3.0"
        mock_bg.assert_not_called()

    def test_cache_stale_returns_last_known(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stale cache remains available while a background refresh starts."""
        _write_cache(patched_cache, "3.2.0", age_seconds=TTL_SECONDS + 100)
        checker = UpgradeChecker()
        with patch.object(checker, "check_in_background") as mock_bg:
            result = checker.get_available_version()
        assert result == "3.2.0"
        mock_bg.assert_called_once_with()

    def test_prerelease_channel_does_not_reuse_stable_cache(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_cache(patched_cache, "3.2.7")  # Legacy caches have no channel marker.
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "1")
        assert UpgradeChecker().get_available_version() is None

    def test_cache_malformed_json_returns_none(self, patched_cache: Path) -> None:
        """Cache malformed JSON: returns None, no exception raised."""
        patched_cache.parent.mkdir(parents=True, exist_ok=True)
        patched_cache.write_text("NOT JSON {{{", encoding="utf-8")
        checker = UpgradeChecker()
        assert checker.get_available_version() is None

    def test_cache_missing_latest_version_key_returns_none(self, patched_cache: Path) -> None:
        """Cache JSON without latest_version key returns None."""
        patched_cache.parent.mkdir(parents=True, exist_ok=True)
        patched_cache.write_text(
            json.dumps({"checked_at": now_utc_iso()}),
            encoding="utf-8",
        )
        checker = UpgradeChecker()
        assert checker.get_available_version() is None

    def test_cache_malformed_timestamp_returns_none(self, patched_cache: Path) -> None:
        """Cache with malformed checked_at returns None."""
        patched_cache.parent.mkdir(parents=True, exist_ok=True)
        patched_cache.write_text(
            json.dumps({"checked_at": "not-a-date", "latest_version": "3.3.0"}),
            encoding="utf-8",
        )
        checker = UpgradeChecker()
        assert checker.get_available_version() is None


class TestCheckInBackground:
    def test_opt_out_does_not_spawn_subprocess(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SPEC_KITTY_NO_UPGRADE_CHECK disables background PyPI probes."""
        monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
        with patch("subprocess.Popen") as mock_popen:
            checker = UpgradeChecker()
            checker.check_in_background()
        mock_popen.assert_not_called()

    def test_subprocess_oserror_does_not_raise(self, patched_cache: Path) -> None:
        """check_in_background() with subprocess failure does not raise."""
        with patch("subprocess.Popen", side_effect=OSError("not found")):
            checker = UpgradeChecker()
            # Must not raise
            checker.check_in_background()

    def test_any_exception_does_not_raise(self, patched_cache: Path) -> None:
        """check_in_background() bare except catches any exception."""
        with patch("subprocess.Popen", side_effect=RuntimeError("unexpected")):
            checker = UpgradeChecker()
            result = checker.check_in_background()
        assert result is None

    def test_background_probe_spawns_refresh_cache_once(self, patched_cache: Path) -> None:
        """#4125: launched as a real module (`-m`), never `-c` codegen.

        A `-c` child has no `__main__.__file__`, which a transitive import
        reads during interpreter bootstrap on Windows and crashes on.
        """
        calls: list[list[str]] = []

        with patch("subprocess.Popen", side_effect=lambda argv, **_: calls.append(argv)):
            UpgradeChecker().check_in_background()

        assert calls
        argv = calls[0]
        assert argv[1] == "-m"
        assert argv[2] == "specify_cli.session_presence.upgrade_check"
        assert "-c" not in argv
        assert "uv pip index" not in " ".join(argv)

    def test_mkdir_failure_does_not_raise(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check_in_background() swallows mkdir failures."""
        with patch("subprocess.Popen", side_effect=PermissionError("no access")):
            checker = UpgradeChecker()
            checker.check_in_background()  # Must not raise


class TestRefreshCacheOnce:
    def test_refresh_queries_active_prerelease_channel(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.compat.provider import LatestVersionResult

        seen: list[bool] = []

        class RecordingProvider:
            def get_latest(self, package: str, *, prerelease: bool = False) -> LatestVersionResult:
                seen.append(prerelease)
                return LatestVersionResult("4.0.0rc3" if prerelease else "3.2.7", "pypi", None)

        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "1")
        monkeypatch.setattr(
            "specify_cli.distribution.upgrade_provider.resolve_upgrade_provider",
            lambda: RecordingProvider(),
        )
        upgrade_check_module.refresh_cache_once()

        data = json.loads(patched_cache.read_text(encoding="utf-8"))
        assert seen == [True]
        assert data["latest_version"] == "4.0.0rc3"
        assert data["prerelease"] is True
        assert UpgradeChecker().get_available_version() == "4.0.0rc3"

    def test_uses_resolved_provider_and_package_name(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.compat.provider import FakeLatestVersionProvider, LatestVersionResult

        calls: list[str] = []

        class RecordingProvider:
            def get_latest(self, package: str) -> LatestVersionResult:
                calls.append(package)
                return FakeLatestVersionProvider(version="8.8.8").get_latest(package)

        monkeypatch.setattr(
            "specify_cli.distribution.package_name.resolve_cli_package_name",
            lambda: "acme-spec-kitty-cli",
        )
        monkeypatch.setattr(
            "specify_cli.distribution.upgrade_provider.resolve_upgrade_provider",
            lambda: RecordingProvider(),
        )
        from specify_cli.distribution.package_name import clear_cli_package_name_cache
        from specify_cli.distribution.upgrade_provider import clear_upgrade_provider_cache

        clear_cli_package_name_cache()
        clear_upgrade_provider_cache()

        upgrade_check_module.refresh_cache_once()
        assert calls == ["acme-spec-kitty-cli"]
        data = json.loads(patched_cache.read_text(encoding="utf-8"))
        assert data["latest_version"] == "8.8.8"

    def test_stock_path_queries_default_package_via_provider(self, patched_cache: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.compat.provider import FakeLatestVersionProvider, LatestVersionResult
        from specify_cli.distribution.package_name import (
            DEFAULT_CLI_PACKAGE_NAME,
            clear_cli_package_name_cache,
        )
        from specify_cli.distribution.upgrade_provider import clear_upgrade_provider_cache

        clear_cli_package_name_cache()
        clear_upgrade_provider_cache()

        seen: list[str] = []

        class StockProvider:
            def get_latest(self, package: str) -> LatestVersionResult:
                seen.append(package)
                return FakeLatestVersionProvider(version="1.2.3").get_latest(package)

        monkeypatch.setattr(
            "specify_cli.distribution.package_name.entry_points",
            lambda group: [],
        )
        monkeypatch.setattr(
            "specify_cli.distribution.package_name.packages_distributions",
            lambda: {},
        )
        monkeypatch.setattr(
            "specify_cli.distribution.upgrade_provider.entry_points",
            lambda group: [],
        )
        # Force provider path without network: replace resolve_upgrade_provider
        monkeypatch.setattr(
            "specify_cli.distribution.upgrade_provider.resolve_upgrade_provider",
            lambda: StockProvider(),
        )
        clear_cli_package_name_cache()
        upgrade_check_module.refresh_cache_once()
        assert seen == [DEFAULT_CLI_PACKAGE_NAME]
