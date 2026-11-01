"""The test-side reader of the pinned service extras fails closed (#6915, FR-008).

A test that reads a pinned extra must fail, naming the code and the remedy, when the
extra was never fetched: a skip would let a missing ``make sync-services`` pass as green.
The positive control reads the real cache that ``make sync-services`` (or the CI action)
filled, so the same reader is shown to work when the asset is there.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.pinned_service_assets import (
    conformance_fixtures_root,
    contract_bundle_dir,
    contract_tools_dir,
    pinned_extra,
    service_cache_root,
)

pytestmark = [pytest.mark.contract, pytest.mark.fast]


def test_an_unfetched_extra_fails_with_the_code_and_the_remedy(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception) as failed:
        pinned_extra("fixtures", cache_root=tmp_path / "empty-cache")

    message = str(failed.value)
    assert "SERVICE_BINARY_MISSING" in message
    assert "make sync-services" in message


def test_the_fetched_extras_are_read_from_the_real_cache() -> None:
    assert (conformance_fixtures_root() / "conformance" / "manifest.json").is_file()
    assert (contract_bundle_dir("mission-status") / "openapi.yaml").is_file()
    assert (contract_tools_dir() / "contract_resolver.py").is_file()


def test_the_cache_follows_xdg_cache_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert service_cache_root() == tmp_path / "spec-kitty" / "services"


def test_without_xdg_the_cache_is_under_the_real_home_not_the_test_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("SPEC_KITTY_REAL_HOME_FOR_TESTS", str(tmp_path / "real"))
    monkeypatch.setenv("HOME", str(tmp_path / "isolated"))

    assert service_cache_root() == tmp_path / "real" / ".cache" / "spec-kitty" / "services"
