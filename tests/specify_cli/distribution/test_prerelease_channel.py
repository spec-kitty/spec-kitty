"""Tests for the rc release-channel consumer slice (T025, C-CHN-1).

Covers:
- ``core.channel.prerelease_enabled`` — the single-read env accessor (T021).
- ``distribution.simple_index._highest_version`` — the shared "highest
  version, prerelease-gated" primitive (T022).
- ``compat.provider.PyPIProvider.get_latest`` — the JSON-API channel gate
  (T022).

The **default-off** behaviour proven here (``SPEC_KITTY_PRERELEASE`` unset,
a newer rc present on the index, latest stays stable) is the regression-
critical guarantee this WP exists to protect (C-CHN-1): stable users must
never be nagged onto a release candidate.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from specify_cli.compat.provider import LatestVersionResult, PyPIProvider
from specify_cli.core.channel import prerelease_enabled
from specify_cli.distribution.simple_index import _highest_version

pytestmark = pytest.mark.fast

_PYPI_URL = "https://pypi.org/pypi/spec-kitty-cli/json"


# ---------------------------------------------------------------------------
# core.channel.prerelease_enabled (T021)
# ---------------------------------------------------------------------------


class TestPrereleaseEnabled:
    def test_default_off_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPEC_KITTY_PRERELEASE", raising=False)
        assert prerelease_enabled() is False

    @pytest.mark.parametrize("falsy", ["", "0", "false", "no", "off", "garbage"])
    def test_off_for_non_truthy_tokens(self, monkeypatch: pytest.MonkeyPatch, falsy: str) -> None:
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", falsy)
        assert prerelease_enabled() is False

    @pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "y", "on"])
    def test_on_for_truthy_tokens(self, monkeypatch: pytest.MonkeyPatch, truthy: str) -> None:
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", truthy)
        assert prerelease_enabled() is True

    def test_whitespace_is_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_PRERELEASE", "  1  ")
        assert prerelease_enabled() is True


# ---------------------------------------------------------------------------
# simple_index._highest_version include_prerelease gate (T022)
# ---------------------------------------------------------------------------


class TestHighestVersionChannelGate:
    def test_default_excludes_prerelease(self) -> None:
        """Byte-for-byte the pre-WP05 behaviour: stable wins over a newer rc."""
        assert _highest_version(["1.9.0", "2.0.0rc1"]) == "1.9.0"

    def test_default_kwarg_matches_positional_call(self) -> None:
        """Old call sites (no kwarg at all) keep working identically."""
        assert _highest_version(["1.9.0", "2.0.0rc1"]) == _highest_version(
            ["1.9.0", "2.0.0rc1"], include_prerelease=False
        )

    def test_include_prerelease_true_surfaces_the_rc(self) -> None:
        assert _highest_version(["1.9.0", "2.0.0rc1"], include_prerelease=True) == "2.0.0rc1"

    def test_include_prerelease_true_still_prefers_a_genuinely_newer_stable(self) -> None:
        """PEP 440 ordering: a final release outranks its own rc."""
        assert (
            _highest_version(["2.0.0rc1", "2.0.0"], include_prerelease=True) == "2.0.0"
        )

    def test_no_stable_falls_back_to_highest_prerelease_either_way(self) -> None:
        assert _highest_version(["2.0.0rc1", "2.0.0rc2"]) == "2.0.0rc2"
        assert _highest_version(["2.0.0rc1", "2.0.0rc2"], include_prerelease=True) == "2.0.0rc2"


# ---------------------------------------------------------------------------
# PyPIProvider.get_latest channel gate (T022, C-CHN-1 core guarantee)
# ---------------------------------------------------------------------------


def _pypi_payload_with_releases(stable: str, releases: list[str]) -> bytes:
    return json.dumps({"info": {"version": stable}, "releases": {v: [{"yanked": False}] for v in releases}}).encode()


class TestPyPIProviderChannelGate:
    @pytest.mark.parametrize(
        ("newer_files", "expected"),
        [
            ([{"yanked": True}, {"yanked": True}], "4.0.0rc3"),
            ([], "4.0.0rc3"),
            ([{"yanked": True}, {"yanked": False}], "4.2.0a1"),
        ],
    )
    @respx.mock
    def test_prerelease_requires_a_live_file(self, newer_files: list[dict[str, bool]], expected: str) -> None:
        from specify_cli.core.upgrade_probe import probe_pypi

        payload = {
            "info": {"version": "3.2.7"},
            "releases": {
                "3.2.7": [{"yanked": False}],
                "4.0.0rc3": [{"yanked": False}],
                "4.2.0a1": newer_files,
            },
        }
        respx.get(_PYPI_URL).mock(return_value=httpx.Response(200, json=payload))
        assert PyPIProvider().get_latest("spec-kitty-cli", prerelease=True).version == expected
        assert probe_pypi("3.2.7", prerelease=True).latest_pypi_version == expected

    @respx.mock
    def test_default_off_returns_stable_even_with_newer_rc_on_index(self) -> None:
        """C-CHN-1: the regression-critical stable-user guarantee.

        A newer rc (2.0.0rc1) is published on the index alongside the stable
        1.9.0. Without opting in, ``get_latest`` must report the stable
        version — no rc advisory to a default-configuration user.
        """
        respx.get(_PYPI_URL).mock(
            return_value=httpx.Response(200, content=_pypi_payload_with_releases("1.9.0", ["1.9.0", "2.0.0rc1"]))
        )
        result = PyPIProvider().get_latest("spec-kitty-cli")
        assert result == LatestVersionResult(version="1.9.0", source="pypi", error=None)

    @respx.mock
    def test_default_off_is_byte_identical_to_explicit_prerelease_false(self) -> None:
        respx.get(_PYPI_URL).mock(
            return_value=httpx.Response(200, content=_pypi_payload_with_releases("1.9.0", ["1.9.0", "2.0.0rc1"]))
        )
        default_call = PyPIProvider().get_latest("spec-kitty-cli")

        respx.get(_PYPI_URL).mock(
            return_value=httpx.Response(200, content=_pypi_payload_with_releases("1.9.0", ["1.9.0", "2.0.0rc1"]))
        )
        explicit_call = PyPIProvider().get_latest("spec-kitty-cli", prerelease=False)

        assert default_call == explicit_call

    @respx.mock
    def test_opted_in_surfaces_the_newest_prerelease(self) -> None:
        respx.get(_PYPI_URL).mock(
            return_value=httpx.Response(200, content=_pypi_payload_with_releases("1.9.0", ["1.9.0", "2.0.0rc1"]))
        )
        result = PyPIProvider().get_latest("spec-kitty-cli", prerelease=True)
        assert result == LatestVersionResult(version="2.0.0rc1", source="pypi", error=None)

    @respx.mock
    def test_opted_in_without_releases_key_falls_back_to_stable(self) -> None:
        """Malformed/absent ``releases`` must never crash the opted-in path."""
        respx.get(_PYPI_URL).mock(return_value=httpx.Response(200, content=json.dumps({"info": {"version": "1.9.0"}}).encode()))
        result = PyPIProvider().get_latest("spec-kitty-cli", prerelease=True)
        assert result == LatestVersionResult(version="1.9.0", source="pypi", error=None)

    @respx.mock
    def test_opted_in_still_prefers_a_genuinely_newer_stable_over_an_old_rc(self) -> None:
        respx.get(_PYPI_URL).mock(
            return_value=httpx.Response(
                200,
                content=_pypi_payload_with_releases("2.1.0", ["1.9.0", "2.0.0rc1", "2.1.0"]),
            )
        )
        result = PyPIProvider().get_latest("spec-kitty-cli", prerelease=True)
        assert result.version == "2.1.0"
