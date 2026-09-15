"""Subscriber identity consumes issuer refs, with explicit protocol acknowledgment."""

from types import SimpleNamespace
import pytest
from specify_cli.zeitgeist_client import own_filter


def test_both_issuer_sessions_are_forwarded_without_derivation():
    stored = SimpleNamespace(session_ref="issuer-a", focus_session_ref="issuer-focus")
    assert own_filter.identity_header(stored) == "issuer-a,issuer-focus"


@pytest.mark.parametrize("refs", [(None, None), (None, "focus-only"), ("bad,ref", None), ("", None)])
def test_unresolvable_identity_fails_loud(refs):
    with pytest.raises(ValueError, match="identity"):
        own_filter.identity_header(SimpleNamespace(session_ref=refs[0], focus_session_ref=refs[1]))


@pytest.mark.parametrize("ack", [None, "false", "TRUE"])
def test_old_or_unconfirmed_relay_fails_before_read(ack):
    with pytest.raises(ValueError, match="confirm"):
        own_filter.require_ack({"X-Zeitgeist-Filter-Own": ack})


def test_true_acknowledgment():
    own_filter.require_ack({"X-Zeitgeist-Filter-Own": "true"})


def test_agent_stream_reconnect_reads_current_cached_identity(monkeypatch):
    from specify_cli.zeitgeist_client import subscription

    stored = SimpleNamespace(relay_url="http://relay", token="outer", capability_credential="inner", session_ref="lease-one", focus_session_ref="focus-one")
    monkeypatch.setattr(subscription.credentials, "load", lambda **kw: stored)
    first = subscription.resolve_stream("github.com/acme/widget", filter_own=True)
    stored.session_ref = "lease-two"
    second = subscription.resolve_stream("github.com/acme/widget", filter_own=True)
    assert first._config.own_sessions == "lease-one,focus-one"
    assert second._config.own_sessions == "lease-two,focus-one"
    stored.session_ref = None
    stored.focus_session_ref = None
    assert subscription.resolve_stream("github.com/acme/widget", filter_own=False)._config.own_sessions is None
    with pytest.raises(ValueError, match="identity"):
        subscription.resolve_stream("github.com/acme/widget", filter_own=True)


@pytest.mark.parametrize("ack", [None, "false", "true"])
def test_wire_ack_is_checked_before_any_frame(monkeypatch, ack):
    from specify_cli.zeitgeist_client import filtered_stream

    observed = []

    class Response:
        headers = {"X-Zeitgeist-Filter-Own": ack}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def readline(self):
            observed.append("read")
            return b""

    def open_request(request, **kwargs):
        assert request.full_url == "http://relay/managed/stream?filterOwn=true"
        assert request.get_header("X-zeitgeist-own-sessions") == "issuer-a,issuer-focus"
        return Response()

    monkeypatch.setattr(filtered_stream.budget.NoRedirects, "build", lambda: SimpleNamespace(open=open_request))
    stream = filtered_stream.FilteredStream(filtered_stream.TeamStreamConfig("http://relay", "inner", "outer", "issuer-a,issuer-focus"))
    if ack == "true":
        assert list(stream.watch()) == []
        assert observed == ["read"]
    else:
        with pytest.raises(ValueError, match="confirm"):
            list(stream.watch())
        assert observed == []


def test_unbound_cached_focus_lease_fails_loud():
    stored = SimpleNamespace(session_ref="issuer-a", focus_session_ref=None, focus_capability_credential="focus-token")
    with pytest.raises(ValueError, match="focus publisher identity"):
        own_filter.identity_header(stored)
