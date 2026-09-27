"""ATDD contract: drain gates the SaaS capability gateway and
the three ``resolve_*`` pre-cache checks.

``SaasCapabilityGateway.check_repo_admission``/``.mint_capability`` must raise
``DrainDisabled`` before any ``self._http`` call when drain is off (F-2), while
the constructor and its ``_http=`` test seam stay ungated. ``resolve_credentials``,
``resolve_focus_capability`` and ``resolve_focus_lease`` must return ``None``
before any cache/credential-store read when drain is off, logging a literal
``drain-off`` debug reason (US1-AS2: an already-cached credential is not used
either).

Without ``drain_off`` (root autouse fixture: drain on), the same calls behave
exactly as they do on ``main`` today — a green baseline regression guard.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from kernel.clock import now_utc, timedelta

from specify_cli.core.hosted_posture import DrainDisabled
from specify_cli.zeitgeist_client import credentials, resolution
from specify_cli.zeitgeist_client.resolution import SaasCapabilityGateway

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]

BASE = "http://teamkitty.test"


def _iso_in(seconds: float) -> str:
    return (now_utc() + timedelta(seconds=seconds)).isoformat()


def _refusing_http() -> httpx.Client:
    """An httpx.Client that fails the test the instant it is asked to send
    a request — the strongest available assertion that no network call
    happens under drain-off."""

    def _blow_up(request: httpx.Request) -> httpx.Response:  # pragma: no cover - only runs on failure
        raise AssertionError(f"unexpected HTTP call under drain-off: {request.method} {request.url}")

    return httpx.Client(transport=httpx.MockTransport(_blow_up))


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


@pytest.fixture()
def clone(tmp_path: Path) -> Path:
    """A checkout whose origin claims to be github.com/acme/widget."""
    bare = tmp_path / "gh" / "acme" / "widget.git"
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
    dest = tmp_path / "work" / "acme" / "widget"
    dest.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/acme/widget.git"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=dest, check=True, capture_output=True)
    (dest / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=dest, check=True, capture_output=True)
    return dest


# ---------------------------------------------------------------------------
# SaasCapabilityGateway — constructor stays ungated, gated methods refuse
# ---------------------------------------------------------------------------


class TestGatewayDrainGate:
    def test_construction_succeeds_under_drain_off(self, drain_off: None) -> None:
        """F-2: the ``_http=`` test seam and object construction are never
        gated — only the two network-making methods are."""
        gateway = SaasCapabilityGateway(BASE, "test-token", _http=_refusing_http())
        assert isinstance(gateway, SaasCapabilityGateway)

    def test_check_repo_admission_raises_and_makes_no_http_call(self, drain_off: None) -> None:
        gateway = SaasCapabilityGateway(BASE, "test-token", _http=_refusing_http())
        with pytest.raises(DrainDisabled):
            gateway.check_repo_admission(repo_slug="acme/widget", host="github.com")

    def test_mint_capability_raises_and_makes_no_http_call(self, drain_off: None) -> None:
        gateway = SaasCapabilityGateway(BASE, "test-token", _http=_refusing_http())
        with pytest.raises(DrainDisabled):
            gateway.mint_capability(repo_slug="acme/widget")

    def test_check_repo_admission_unaffected_under_drain_on(self) -> None:
        """Baseline regression guard: without ``drain_off`` (root fixture
        pins drain on), the gate is a no-op and the real request path runs."""

        def _respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"admitted": False, "reason": "no_match"})

        gateway = SaasCapabilityGateway(BASE, "test-token", _http=httpx.Client(transport=httpx.MockTransport(_respond)))
        answer = gateway.check_repo_admission(repo_slug="acme/widget", host="github.com")
        assert answer.admitted is False


# ---------------------------------------------------------------------------
# resolve_credentials / resolve_focus_capability / resolve_focus_lease
# ---------------------------------------------------------------------------


class TestResolveCredentialsDrainGate:
    def test_returns_none_and_never_reads_the_cache(self, state_root: Path, clone: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        cached_answer = Mock(name="cached_answer")
        monkeypatch.setattr(resolution, "cached_answer", cached_answer)
        assert resolution.resolve_credentials(clone) is None
        cached_answer.assert_not_called()

    def test_logs_a_drain_off_debug_reason(self, state_root: Path, clone: Path, drain_off: None, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="specify_cli.zeitgeist_client.resolution")
        resolution.resolve_credentials(clone)
        assert any("drain-off" in record.message for record in caplog.records)

    def test_an_already_cached_credential_is_not_used_when_drain_is_off(self, state_root: Path, clone: Path, drain_off: None) -> None:
        """US1-AS2: developer was previously logged in and holds a cached
        relay credential; drain is off; the cached credential is not used
        and nothing is sent."""
        credentials.store(
            repo="github.com/acme/widget",
            relay_url="http://relay",
            token="bearer",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host="github.com",
            repo_slug="acme/widget",
            team="demo",
        )
        assert resolution.resolve_credentials(clone) is None

    def test_unaffected_under_drain_on(self, state_root: Path, clone: Path) -> None:
        """Baseline regression guard: an already-cached credential still
        answers offline exactly as on ``main`` today."""
        credentials.store(
            repo="github.com/acme/widget",
            relay_url="http://relay",
            token="bearer",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host="github.com",
            repo_slug="acme/widget",
            team="demo",
        )
        stored = resolution.resolve_credentials(clone)
        assert stored is not None
        assert stored.relay_url == "http://relay"


class TestResolveFocusCapabilityDrainGate:
    def test_returns_none_and_never_reads_the_credential_store(self, state_root: Path, clone: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        load = Mock(name="credentials.load")
        monkeypatch.setattr(credentials, "load", load)
        assert resolution.resolve_focus_capability(clone) is None
        load.assert_not_called()

    def test_logs_a_drain_off_debug_reason(self, state_root: Path, clone: Path, drain_off: None, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="specify_cli.zeitgeist_client.resolution")
        resolution.resolve_focus_capability(clone)
        assert any("drain-off" in record.message for record in caplog.records)


class TestResolveFocusLeaseDrainGate:
    def test_returns_none_when_drain_is_off(self, state_root: Path, clone: Path, drain_off: None) -> None:
        assert resolution.resolve_focus_lease(clone) is None


# ---------------------------------------------------------------------------
# A3: drain posture is scoped to the ACTING repo, never the process cwd.
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
def test_resolve_credentials_drain_posture_uses_the_acting_repo_not_process_cwd(
    tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``resolve_credentials(cwd=...)`` must scope its drain-posture read to
    the repo it is resolving FOR, never to the process's own
    ``os.getcwd()``. Two repos get opposite ``hosted.drain`` values, the
    process cwd sits inside the OFF one, and only the drain-OFF repo's own
    call may log the ``drain-off`` reason."""
    from specify_cli.core.hosted_posture import set_personal_drain, set_repo_drain

    set_personal_drain(True)  # personal scope on for both repos

    def _make_repo(name: str, *, drain_on: bool) -> Path:
        repo = tmp_path / name
        (repo / ".kittify").mkdir(parents=True)
        set_repo_drain(repo, drain_on)
        return repo

    repo_on = _make_repo("repo_on", drain_on=True)
    repo_off = _make_repo("repo_off", drain_on=False)

    monkeypatch.chdir(repo_off)  # the PROCESS sits inside the drain-OFF repo

    caplog.set_level(logging.DEBUG, logger="specify_cli.zeitgeist_client.resolution")

    caplog.clear()
    # repo_on has no git origin, so past the drain gate this fails on
    # identity resolution instead -- but the gate itself must not fire.
    assert resolution.resolve_credentials(repo_on) is None
    assert not any("drain-off" in record.message for record in caplog.records), (
        "the acting repo (repo_on) has drain ON; the gate must not fire just because the PROCESS cwd (repo_off) has drain off"
    )

    caplog.clear()
    assert resolution.resolve_credentials(repo_off) is None
    assert any("drain-off" in record.message for record in caplog.records), "the acting repo (repo_off) has drain OFF; the gate must fire for it"
