"""Retained reads use the existing managed-events wire contract."""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from specify_cli.zeitgeist_client import history


def frame(seq=1):
    return {"schema_version": "1.0", "epoch": "epoch-1", "seq": seq, "emitted_at": 1.0, "frame": {"type": "event", "event": {"kind": "decision"}}}


@pytest.fixture
def relay(monkeypatch):
    state = SimpleNamespace(body={"schema_version": "1.0", "epoch": "epoch-1", "seq": 1, "events": [frame()]}, requests=[])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state.requests.append((self.path, dict(self.headers)))
            body = state.body if isinstance(state.body, bytes) else json.dumps(state.body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            if getattr(state, "own_ack", None) is not None:
                self.send_header("X-Zeitgeist-Filter-Own", state.own_ack)
            self.end_headers()
            if getattr(state, "drip", False):
                for offset in range(0, len(body), 8):
                    self.wfile.write(body[offset : offset + 8])
                    self.wfile.flush()
                    time.sleep(0.05)
            else:
                self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        history.credentials,
        "load",
        lambda **kwargs: SimpleNamespace(relay_url=f"http://127.0.0.1:{server.server_port}", token="outer", capability_credential="inner"),
    )
    yield state
    server.shutdown()
    server.server_close()
    thread.join()


def test_history_reads_scope_and_preserves_coverage(relay):
    relay.body.update(reset=True, gap={"from_seq": 1, "to_seq": 2})
    result = history.read_history("github.com/acme/repo", since="old:0", window_s=60)
    path, headers = relay.requests[0]
    assert urlsplit(path).path == "/managed/events"
    assert parse_qs(urlsplit(path).query) == {"since": ["old:0"], "window_s": ["60"], "filterOwn": ["false"]}
    assert headers["Authorization"] == "Bearer outer"
    assert headers["X-Zeitgeist-Capability"] == "inner"
    assert result["frames"][0]["frame_type"] == "event"
    assert result["coverage"]["reset"] is True
    assert result["coverage"]["gap"] == {"from_seq": 1, "to_seq": 2}
    assert result["coverage"]["retention_s"] is None
    assert result["coverage"]["complete"] is False


def test_history_bounds_frames_and_continues_at_returned_cursor(relay, monkeypatch):
    monkeypatch.setattr(history, "MAX_HISTORY_FRAMES", 2)
    relay.body.update(seq=90, events=[frame(i) for i in range(1, 5)])
    result = history.read_history("github.com/acme/repo")
    assert len(result["frames"]) == 2
    assert result["coverage"]["truncated"] is True
    assert result["coverage"]["continuation"] == "epoch-1:2"
    assert result["coverage"]["withheld_count"] == 2


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        [],
        {},
        {"schema_version": "1.0", "epoch": "epoch-1", "seq": True, "events": []},
        {"schema_version": "1.0", "epoch": "epoch-1", "seq": 2, "events": [frame(2), frame(1)]},
        {"schema_version": "1.0", "epoch": "epoch-1", "seq": 1, "events": [{}]},
        {"schema_version": "1.0", "epoch": "epoch-1", "seq": 1, "events": [], "gap": {"from_seq": 2, "to_seq": 1}},
    ],
)
def test_malformed_history_is_explicit(relay, body):
    relay.body = body
    with pytest.raises(history.HistoryProtocolError):
        history.read_history("github.com/acme/repo")


def test_response_byte_limit(relay, monkeypatch):
    monkeypatch.setattr(history, "MAX_HISTORY_BYTES", 20)
    with pytest.raises(history.HistoryProtocolError, match="byte limit"):
        history.read_history("github.com/acme/repo")


@pytest.mark.parametrize("kwargs", [{"window_s": -1}, {"timeout_s": float("nan")}, {"since": "invalid"}])
def test_invalid_requests_do_not_connect(relay, kwargs):
    with pytest.raises(ValueError):
        history.read_history("github.com/acme/repo", **kwargs)
    assert not relay.requests


def test_missing_credentials_never_connect(relay, monkeypatch):
    monkeypatch.setattr(history.credentials, "load", lambda **kwargs: None)
    with pytest.raises(history.subscription.NotCheckedOut):
        history.read_history("github.com/acme/repo")
    assert not relay.requests


def test_empty_retained_result_makes_no_completeness_claim(relay):
    relay.body.update(seq=0, events=[])
    result = history.read_history("github.com/acme/repo", window_s=0)
    assert result["frames"] == []
    assert result["coverage"]["complete"] is False
    assert result["coverage"]["continuation"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"epoch": "wrong"},
        {"seq": 2},
        {"emitted_at": float("inf")},
    ],
)
def test_inconsistent_frames_fail_without_partial_results(relay, change):
    relay.body["events"][0].update(change)
    with pytest.raises(history.HistoryProtocolError):
        history.read_history("github.com/acme/repo")


def test_slow_drip_cannot_extend_whole_call_deadline(relay):
    relay.drip = True
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="whole-call deadline"):
        history.read_history("github.com/acme/repo", timeout_s=0.2)
    assert time.monotonic() - started < 1.5


def test_exhausted_reader_slots_are_reported_without_connecting(relay, monkeypatch):
    import threading

    monkeypatch.setattr(history, "_READ_SLOTS", threading.BoundedSemaphore(0))
    with pytest.raises(history.HistoryProtocolError, match="busy"):
        history.read_history("github.com/acme/repo")
    assert relay.requests == []


def test_agent_history_requests_issuer_identity_and_requires_ack(relay, monkeypatch):
    from specify_cli.zeitgeist_client import credentials

    old_load = credentials.load
    stored = old_load(repo="github.com/acme/repo")
    stored.session_ref = "issuer-a"
    stored.focus_session_ref = "issuer-focus"
    monkeypatch.setattr(credentials, "load", lambda **kwargs: stored)
    with pytest.raises(ValueError, match="confirm"):
        history.read_history("github.com/acme/repo", filter_own=True)
    path, headers = relay.requests[-1]
    assert parse_qs(urlsplit(path).query)["filterOwn"] == ["true"]
    assert headers["X-Zeitgeist-Own-Sessions"] == "issuer-a,issuer-focus"
    relay.own_ack = "true"
    result = history.read_history("github.com/acme/repo", filter_own=True)
    assert len(result["frames"]) == 1


@pytest.mark.parametrize("value", ["true", 1, None])
def test_history_rejects_non_boolean_own_filter(value):
    with pytest.raises(ValueError, match="boolean"):
        history.read_history("github.com/acme/repo", filter_own=value)
