"""Lease identity must survive the real mint/store/producer path (#4217)."""

from pathlib import Path

import httpx
import pytest

from specify_cli.zeitgeist_client import credentials, resolution

pytestmark = pytest.mark.fast


def test_gateway_preserves_issued_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "relay_url": "http://relay",
                "relay_token": "test-bearer",
                "capability_credential": "test-capability",
                "expires_at": "2099-01-01T00:00:00Z",
                "session_ref": "issued-lease-a",
                "logical_session_id": "agent-a",
            },
        )

    gateway = resolution.SaasCapabilityGateway("http://saas", "test-auth", _http=httpx.Client(transport=httpx.MockTransport(respond)))
    minted = gateway.mint_capability(repo_slug="acme/widget")
    assert minted.session_ref == "issued-lease-a"


def test_cached_credentials_are_isolated_between_agents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")
    credentials.store(repo="github.com/acme/widget", relay_url="http://relay", token="a", token_kind="presence")
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-b")
    assert credentials.load(repo="github.com/acme/widget") is None
    credentials.store(repo="github.com/acme/widget", relay_url="http://relay", token="b", token_kind="presence")
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")
    assert credentials.load(repo="github.com/acme/widget").token == "a"


@pytest.mark.parametrize("override", ["", "../other", "agent/child", "é", "a" * 129])
def test_invalid_logical_identity_is_refused(override: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.zeitgeist_client.session_identity import logical_session_id

    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", override)
    with pytest.raises(ValueError, match="ASCII identifier"):
        logical_session_id()


def test_harness_threads_are_distinct_and_default_is_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.zeitgeist_client import session_identity

    monkeypatch.delenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-a")
    first = session_identity.logical_session_id()
    assert first == session_identity.logical_session_id()
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-b")
    assert session_identity.logical_session_id() != first
    monkeypatch.delenv("CODEX_THREAD_ID")
    # The unidentified fallback is a stable default, NOT per-process (#4217
    # squad MAJOR): a per-process value partitioned the credential store so a
    # credential stored by one command could never be loaded by the next.
    fallback = session_identity.logical_session_id()
    assert fallback == session_identity.logical_session_id()
    monkeypatch.setattr(session_identity.os, "getpid", lambda: -1)
    assert session_identity.logical_session_id() == fallback


_WRITE_CREDENTIAL = (
    "from specify_cli.zeitgeist_client import credentials\n"
    "credentials.store(repo='github.com/test/identity-probe', relay_url='http://localhost', "
    "token='fixture-only', token_kind='presence')\n"
)
_READ_CREDENTIAL = (
    "import json\n"
    "from specify_cli.zeitgeist_client import credentials\n"
    "print(json.dumps({'found': credentials.load(repo='github.com/test/identity-probe') is not None}))\n"
)


@pytest.mark.parametrize(
    "writer_env,reader_env,expected_cache_hit",
    [
        ({}, {}, True),  # default: separate command/reader processes share one logical session
        ({"SPEC_KITTY_ZEITGEIST_SESSION_ID": "agent-a"}, {"SPEC_KITTY_ZEITGEIST_SESSION_ID": "agent-a"}, True),
        ({"SPEC_KITTY_ZEITGEIST_SESSION_ID": "agent-a"}, {"SPEC_KITTY_ZEITGEIST_SESSION_ID": "agent-b"}, False),
        ({"CODEX_THREAD_ID": "thread-a"}, {"CODEX_THREAD_ID": "thread-a"}, True),
        ({"CODEX_THREAD_ID": "thread-a"}, {"CODEX_THREAD_ID": "thread-b"}, False),
    ],
    ids=[
        "default-separate-command-and-reader",
        "explicit-same-agent",
        "explicit-distinct-agents",
        "same-codex-thread",
        "distinct-codex-threads",
    ],
)
def test_cross_process_identity_partitions_the_credential_store(
    writer_env: dict[str, str], reader_env: dict[str, str], expected_cache_hit: bool, tmp_path: Path
) -> None:
    """The #4217 acceptance probe, verbatim semantics: what one process stores
    is exactly what a second process (same machine, same SPEC_KITTY_HOME)
    can load — unless the two are deliberately distinct logical agents."""
    import json
    import os
    import subprocess
    import sys

    env = dict(os.environ, SPEC_KITTY_HOME=str(tmp_path), SPEC_KITTY_ENABLE_SAAS_SYNC="0")
    for key in ("CODEX_THREAD_ID", "SPEC_KITTY_ZEITGEIST_SESSION_ID"):
        env.pop(key, None)
    subprocess.run([sys.executable, "-c", _WRITE_CREDENTIAL], env=env | writer_env, check=True)
    observed = json.loads(subprocess.check_output([sys.executable, "-c", _READ_CREDENTIAL], env=env | reader_env))["found"]
    assert observed is expected_cache_hit


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_ref", None),
        ("session_ref", ""),
        ("session_ref", []),
        ("session_ref", "invalid/session"),
        ("logical_session_id", None),
        ("logical_session_id", "other-agent"),
    ],
)
def test_legacy_or_mismatched_mint_is_refused(field: str, value: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")
    body = {
        "relay_url": "http://relay",
        "relay_token": "test-bearer",
        "expires_at": "2099-01-01T00:00:00Z",
        "session_ref": "issued-a",
        "logical_session_id": "agent-a",
    }
    body[field] = value
    gateway = resolution.SaasCapabilityGateway(
        "http://saas", "test-auth", _http=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    )
    with pytest.raises(resolution.GatewayError):
        gateway.mint_capability(repo_slug="acme/widget")


def test_lease_refs_round_trip_and_remint_independently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    key = "github.com/acme/widget"
    common = {"repo": key, "relay_url": "http://relay", "token": "test-bearer", "token_kind": "presence"}
    credentials.store(**common, session_ref="presence-old")
    credentials.store_focus_capability(repo=key, capability_credential="focus-token", session_ref="focus-old")
    credentials.store(**common, session_ref="presence-new")
    stored = credentials.load(repo=key)
    assert stored is not None
    assert (stored.session_ref, stored.focus_session_ref) == ("presence-new", "focus-old")
    credentials.store_focus_capability(repo=key, capability_credential="focus-new-token", session_ref="focus-new")
    stored = credentials.load(repo=key)
    assert stored is not None
    assert (stored.session_ref, stored.focus_session_ref) == ("presence-new", "focus-new")
    credentials.store_focus_capability(repo=key, capability_credential="unbound-token")
    assert credentials.load(repo=key).focus_session_ref is None


def test_old_shared_cache_is_not_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    old = tmp_path / "zeitgeist-credentials"
    old.write_text('["github.com/acme/widget"]\nrelay_url="http://relay"\ntoken="old"\ntoken_kind="presence"\ntoken_issued_at="2026-01-01"\n')
    assert credentials.load(repo="github.com/acme/widget") is None
    assert old.exists()


@pytest.mark.parametrize("case", ["unavailable", "no-host", "missing", "unbound", "racing", "matched"])
def test_focus_resolution_keeps_authority_and_identity_paired(case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.setattr(resolution, "resolve_focus_capability", lambda *args, **kwargs: None if case == "unavailable" else "minted-focus")
    monkeypatch.setattr(resolution.repo_identity, "origin_url", lambda *args: "/local" if case == "no-host" else "https://github.com/acme/widget")
    if case not in ("unavailable", "no-host", "missing"):
        key = "github.com/acme/widget"
        credentials.store(repo=key, relay_url="http://relay", token="test-bearer", token_kind="presence", session_ref="presence-ref")
        credentials.store_focus_capability(
            repo=key, capability_credential="other-focus" if case == "racing" else "minted-focus", session_ref=None if case == "unbound" else "focus-ref"
        )
    lease = resolution.resolve_focus_lease(tmp_path)
    if case == "matched":
        assert lease == resolution.FocusLease("minted-focus", "focus-ref")
    else:
        assert lease is None


def test_uncached_read_does_not_leave_process_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    assert credentials.load(repo="github.com/acme/widget") is None
    assert credentials.load_negative(repo="github.com/acme/widget") is None
    assert not (tmp_path / "zeitgeist-sessions").exists()


@pytest.mark.parametrize("session_ref", [None, ""])
@pytest.mark.parametrize("operation", ["moment", "liveness"])
def test_unbound_lease_never_constructs_a_publisher(session_ref: str | None, operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A usable bearer alone cannot identify the session SaaS must revoke."""
    from specify_cli.status import zeitgeist_bridge
    from specify_cli.zeitgeist_client import transport
    from specify_cli.zeitgeist_client.repo_identity import Deadline

    credential = credentials.StoredCredential(
        relay_url="http://relay",
        token="test-bearer",
        token_kind="presence",
        token_issued_at="2026-09-14T00:00:00Z",
        session_ref=session_ref,
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unbound lease attempted publisher construction")

    monkeypatch.setattr(transport, "ZeitgeistClient", forbidden)
    monkeypatch.setattr(transport.ClientConfig, "for_repository", forbidden)
    if operation == "moment":
        zeitgeist_bridge._offer_and_log(credential, "MissionCreated", {"kind": "MissionCreated"})
    else:
        zeitgeist_bridge._refresh_liveness_bounded(credential, cwd=tmp_path, focus_wp=("mission", "WP01"), deadline=Deadline())
