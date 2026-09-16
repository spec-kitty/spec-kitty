"""#4269's authored-message service — send/reply/read/inbox over doubles.

The publish path is exercised against a protocol-shaped inline double (POST
``/managed/control`` for ``event.publish``, GET ``/managed/events`` for the
recent ring) rather than the real relay: the suite's subject is the authored
service's own discipline — typed refusals, the stable contribution id, the
three-way outcome, bounded retrieval, addressing and receipts — not the relay
transport, which ``tests/zeitgeist_client/`` already pins against its own
protocol-faithful doubles.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.live_work import authored
from specify_cli.live_work.bindings import RepositoryBinding, ResolvedBindings
from specify_cli.zeitgeist_client import credentials

pytestmark = pytest.mark.fast

_STORE_KEY = "github.com/acme/widget"
_EPOCH = "epoch-1"
_QUESTION_WIRE_KIND = "work.narrative.question_asked.v1"
_MESSAGE_WIRE_KIND = "work.message.peer_sent.v1"


class _RelayDouble:
    """Inline relay double: a publish route and a recent-ring route.

    Records every POST envelope verbatim so a test can assert exactly what
    reached the wire (args shape, stable request_id, retry count); serves a
    configurable ring for the read surfaces. Status/detail are configurable
    per-test to exercise the outcome vocabulary."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.post_status = 202
        self.post_detail: str | None = None
        self.events: list[dict[str, Any]] = []
        self.filter_own_ack = "true"
        double = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

            def _send(self, status: int, payload: dict[str, Any], extra: dict[str, str] | None = None) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for key, value in (extra or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0") or "0")
                envelope = json.loads(self.rfile.read(length) or b"{}")
                double.posts.append(envelope)
                if double.post_status == 202:
                    self._send(202, {"request_id": envelope.get("request_id"), "received_at": 1.0})
                else:
                    self._send(double.post_status, {"detail": double.post_detail or "refused"}, {"Retry-After": "1"} if double.post_status == 429 else None)

            def do_GET(self) -> None:  # noqa: N802
                events = double.events
                self._send(
                    200,
                    {"schema_version": "1.0", "epoch": _EPOCH, "seq": len(events), "events": events},
                    {"X-Zeitgeist-Filter-Own": double.filter_own_ack},
                )

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def applied_op_count(self, op: str) -> int:
        return sum(1 for post in self.posts if post.get("op") == op and self.post_status == 202)


def _event_frame(
    seq: int,
    *,
    kind: str = _QUESTION_WIRE_KIND,
    attrs: dict[str, str] | None = None,
    session_ref: str = "sess-peer",
) -> dict[str, Any]:
    """One ring entry shaped exactly as ``parse_live_frame`` accepts."""
    return {
        "schema_version": "1.0",
        "epoch": _EPOCH,
        "seq": seq,
        "emitted_at": float(seq),
        "frame": {
            "type": "event",
            "event": {
                "kind": kind,
                "ref": "repo/acme/widget",
                "attrs": attrs or {},
                "actor": {"session_ref": session_ref, "user": "peer@example"},
                "observed_at": float(seq),
            },
        },
    }


def _authored_ring_entry(
    seq: int,
    message_id: str,
    *,
    kind: str = _QUESTION_WIRE_KIND,
    thread: str | None = None,
    audience: str = "team",
    reply_to: str | None = None,
    text: str = "which tag ships?",
) -> dict[str, Any]:
    attrs = {"event_id": message_id, "x-thread": thread or message_id, "x-audience": audience, "x-text": text}
    if reply_to is not None:
        attrs["x-reply-to"] = reply_to
    return _event_frame(seq, kind=kind, attrs=attrs)


@pytest.fixture()
def relay() -> _RelayDouble:
    double = _RelayDouble()
    try:
        yield double
    finally:
        double.stop()


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "spec-kitty-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(root))
    return root


@pytest.fixture()
def publish_env(relay: _RelayDouble, monkeypatch: pytest.MonkeyPatch) -> _RelayDouble:
    """Fake the publish path's environment down to the credential seam —
    the same surface the MCP suite patches (an admitted credential, a
    repository binding, this checkout's store key); the real SaaS gateway is
    not this suite's subject."""
    from specify_cli.zeitgeist_client import resolution

    monkeypatch.setattr(
        "specify_cli.zeitgeist_client.resolution.resolve_credentials",
        lambda cwd, deadline=None, force=False: SimpleNamespace(relay_url=relay.url, token="team-token", capability_credential=None, session_ref="sess-author"),
    )
    monkeypatch.setattr(
        "specify_cli.live_work.bindings.resolve_bindings",
        lambda cwd: ResolvedBindings(repository=RepositoryBinding(slug="acme/widget"), mission=None, repo_root=Path(cwd)),
    )
    monkeypatch.setattr(resolution, "store_key_for_checkout", lambda cwd: _STORE_KEY)
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")
    return relay


# --- send ---------------------------------------------------------------------


def test_send_publishes_one_frame_and_reports_accepted(publish_env: _RelayDouble, tmp_path: Path) -> None:
    result = authored.send("question", "which tag ships?", cwd=tmp_path, audience="team")
    assert result.outcome is authored.SendOutcome.ACCEPTED
    assert result.kind == "question"
    assert result.audience == "team"
    assert result.thread == result.message_id  # a new conversation's root is the message's own id
    assert result.truncated is False
    payload = result.as_dict()
    assert payload["delivery_scope"] == authored.DELIVERY_SCOPE_NOTE
    assert authored.DELIVERY_SCOPE_NOTE.startswith("live relay ring only")
    assert publish_env.applied_op_count("event.publish") == 1
    envelope = publish_env.posts[0]
    assert envelope["request_id"] == result.message_id  # the stable contribution id is the envelope's own id
    args = envelope["args"]
    assert set(args) == {"session_id", "kind", "ref", "attrs"}
    assert args["kind"] == _QUESTION_WIRE_KIND
    assert args["session_id"] == "agent-a"
    assert args["attrs"]["x-text"] == "which tag ships?"
    assert args["attrs"]["event_id"] == result.message_id
    assert args["attrs"]["x-thread"] == result.thread
    assert args["attrs"]["x-audience"] == "team"


def test_send_refuses_unsupported_kind_before_any_network(publish_env: _RelayDouble, tmp_path: Path) -> None:
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.send("finding", "no contract kind for this", cwd=tmp_path)
    assert caught.value.code == "unsupported_kind"
    assert publish_env.posts == []  # zero-attempt: the refusal precedes any socket call


def test_send_refuses_oversize_body_and_honors_explicit_truncation(publish_env: _RelayDouble, tmp_path: Path) -> None:
    body = "x" * (authored.MAX_BODY_CHARS + 60)
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.send("progress", body, cwd=tmp_path)
    assert caught.value.code == "oversize_body"
    assert publish_env.posts == []
    result = authored.send("progress", body, cwd=tmp_path, allow_truncate=True)
    assert result.outcome is authored.SendOutcome.ACCEPTED
    assert result.truncated is True
    assert publish_env.posts[-1]["args"]["attrs"]["x-text"] == "x" * authored.MAX_BODY_CHARS


def test_send_refuses_secret_bodies_without_echoing_them(publish_env: _RelayDouble, tmp_path: Path) -> None:
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.send("handoff", "take this: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig", cwd=tmp_path)
    assert caught.value.code == "unsafe_body"
    assert "Bearer" not in str(caught.value)  # the category is reported, never the content
    assert publish_env.posts == []


def test_send_audience_is_team_or_one_addressed_peer(publish_env: _RelayDouble, tmp_path: Path) -> None:
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.send("intent", "ship it", cwd=tmp_path, audience="everyone")
    assert caught.value.code == "invalid_audience"
    peer = authored.send("question", "ready?", cwd=tmp_path, audience="peer:agent-b")
    assert peer.audience == "peer:agent-b"
    assert publish_env.posts[-1]["args"]["attrs"]["x-audience"] == "peer:agent-b"


def test_send_fails_after_bounded_retry_when_the_relay_is_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dead_port = _RelayDouble()
    dead_url = dead_port.url
    dead_port.stop()  # the port is now closed: every attempt is a transport drop
    monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_SESSION_ID", "agent-a")
    monkeypatch.setattr(
        "specify_cli.zeitgeist_client.resolution.resolve_credentials",
        lambda cwd, deadline=None, force=False: SimpleNamespace(relay_url=dead_url, token="t", capability_credential=None, session_ref="s"),
    )
    monkeypatch.setattr(
        "specify_cli.live_work.bindings.resolve_bindings",
        lambda cwd: ResolvedBindings(repository=RepositoryBinding(slug="acme/widget"), mission=None, repo_root=Path(cwd)),
    )
    result = authored.send("blocker", "relay is down", cwd=tmp_path)
    assert result.outcome is authored.SendOutcome.FAILED
    assert result.reason is not None and "dropped_unreachable" in result.reason


def test_send_reports_offered_when_the_relay_throttles_without_confirming(publish_env: _RelayDouble, tmp_path: Path) -> None:
    publish_env.post_status = 429
    result = authored.send("progress", "still going", cwd=tmp_path)
    assert result.outcome is authored.SendOutcome.OFFERED
    assert publish_env.applied_op_count("event.publish") == 0
    assert result.reason is not None and "idempotent" in result.reason
    assert len(publish_env.posts) == authored.MAX_SEND_ATTEMPTS  # bounded: every retry re-offered the same id
    assert {post["request_id"] for post in publish_env.posts} == {result.message_id}


def test_send_maps_a_definitive_relay_refusal_to_failed_without_retrying(publish_env: _RelayDouble, tmp_path: Path) -> None:
    publish_env.post_status = 403
    publish_env.post_detail = "capability does not grant op event.publish"
    result = authored.send("intent", "ship it", cwd=tmp_path, audience="peer:agent-b")
    assert result.outcome is authored.SendOutcome.FAILED
    assert result.reason is not None and "capability does not grant op event.publish" in result.reason
    assert len(publish_env.posts) == 1  # a definitive refusal is never retried


# --- reply --------------------------------------------------------------------


def test_reply_inherits_thread_and_audience_from_the_parent(publish_env: _RelayDouble, tmp_path: Path, state_root: Path) -> None:
    parent_id = "01M2KT865QSS8S5FPSY3S7PX02"
    publish_env.events = [_authored_ring_entry(1, parent_id, kind=_MESSAGE_WIRE_KIND, thread="thread-root", audience="peer:agent-a")]
    credentials.store(repo=_STORE_KEY, relay_url=publish_env.url, token="t", token_kind="shared_team", session_ref="sess-author")
    result = authored.reply(parent_id, "the stable 4.x tag", cwd=tmp_path)
    assert result.outcome is authored.SendOutcome.ACCEPTED
    assert result.kind == "message"
    assert result.thread == "thread-root"
    assert result.audience == "peer:agent-a"  # inherited, never broadened to team scope
    assert result.reply_to == parent_id
    assert publish_env.posts[-1]["args"]["kind"] == _MESSAGE_WIRE_KIND
    assert publish_env.posts[-1]["args"]["attrs"]["x-reply-to"] == parent_id


def test_reply_refuses_an_audience_the_parent_does_not_have(publish_env: _RelayDouble, tmp_path: Path, state_root: Path) -> None:
    parent_id = "01M2KT865QSS8S5FPSY3S7PX02"
    publish_env.events = [_authored_ring_entry(1, parent_id, audience="peer:agent-a")]
    credentials.store(repo=_STORE_KEY, relay_url=publish_env.url, token="t", token_kind="shared_team", session_ref="sess-author")
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.reply(parent_id, "broadening attempt", cwd=tmp_path, audience="team")
    assert caught.value.code == "invalid_audience"
    assert publish_env.posts == []


def test_reply_refuses_a_parent_outside_the_recent_window(publish_env: _RelayDouble, tmp_path: Path, state_root: Path) -> None:
    credentials.store(repo=_STORE_KEY, relay_url=publish_env.url, token="t", token_kind="shared_team", session_ref="sess-author")
    with pytest.raises(authored.AuthoredMessageError) as caught:
        authored.reply("01AAAAAAAAAAAAAAAAAAAAAAAA", "too old", cwd=tmp_path)
    assert caught.value.code == "unknown_parent"
    assert publish_env.posts == []


# --- read_conversation ----------------------------------------------------------


def test_read_conversation_projects_authored_frames_with_framed_bodies(relay: _RelayDouble, state_root: Path) -> None:
    relay.events = [
        _authored_ring_entry(1, "01M2KT865QSS8S5FPSY3S7PX01", thread="thread-root"),
        _authored_ring_entry(2, "01M2KT865QSS8S5FPSY3S7PX02", kind=_MESSAGE_WIRE_KIND, thread="thread-root", audience="peer:agent-b"),
        _event_frame(3, kind="WPStatusChanged", attrs={"mission_slug": "m"}),  # a status moment, not authored vocabulary
    ]
    credentials.store(repo=_STORE_KEY, relay_url=relay.url, token="t", token_kind="shared_team", session_ref="sess-author")
    result = authored.read_conversation(_STORE_KEY)
    assert [message["kind"] for message in result["messages"]] == ["question", "message"]
    assert result["withheld"] == {"not_authored": 1, "thread": 0, "budget": 0}
    first = result["messages"][0]
    assert first["message_id"] == "01M2KT865QSS8S5FPSY3S7PX01"
    assert first["thread"] == "thread-root"
    assert first["audience"] == "team"
    assert first["actor"] == {"session_ref": "sess-peer", "user": "peer@example"}
    assert first["untrusted_text"].startswith("[zeitgeist moment ")
    assert "x-text=which tag ships?" in first["untrusted_text"]
    assert "[end of zeitgeist moment" in first["untrusted_text"]
    threaded = authored.read_conversation(_STORE_KEY, thread="thread-root")
    assert len(threaded["messages"]) == 2
    other = authored.read_conversation(_STORE_KEY, thread="01M2KT865QSS8S5FPSY3S7PX02")
    assert other["messages"] == []  # a message's own id is its thread only when it started the thread
    assert other["withheld"]["thread"] == 2


def test_read_conversation_reports_the_ring_budget_honestly(relay: _RelayDouble, state_root: Path) -> None:
    relay.events = [_authored_ring_entry(seq, f"01M2KT865QSS8S5FPSY3S7P{seq:02d}") for seq in range(1, 4)]
    credentials.store(repo=_STORE_KEY, relay_url=relay.url, token="t", token_kind="shared_team", session_ref="sess-author")
    result = authored.read_conversation(_STORE_KEY, max_messages=2)
    assert len(result["messages"]) == 2
    assert result["withheld"]["budget"] == 1
    assert result["coverage"]["source"] == "relay_retained_history"


def test_read_conversation_is_bounded_per_message_count(state_root: Path) -> None:
    with pytest.raises(ValueError, match="max_messages"):
        authored.read_conversation(_STORE_KEY, max_messages=0)


# --- inbox -----------------------------------------------------------------------


def test_inbox_surfaces_only_messages_addressed_to_this_consumer(relay: _RelayDouble, state_root: Path) -> None:
    relay.events = [
        _authored_ring_entry(1, "01M2KT865QSS8S5FPSY3S7PX01", audience="team"),
        _authored_ring_entry(2, "01M2KT865QSS8S5FPSY3S7PX02", audience="peer:agent-a"),
        _authored_ring_entry(3, "01M2KT865QSS8S5FPSY3S7PX03", audience="peer:agent-b"),
    ]
    credentials.store(repo=_STORE_KEY, relay_url=relay.url, token="t", token_kind="shared_team", session_ref="sess-author")
    result = authored.inbox(_STORE_KEY, consumer="agent-a")
    assert [message["message_id"] for message in result["messages"]] == ["01M2KT865QSS8S5FPSY3S7PX01", "01M2KT865QSS8S5FPSY3S7PX02"]
    assert result["withheld"]["unaddressed"] == 1
    assert result["catch_up"] == {"operation": "inbox", "within_retention_only": True}
    receipt = result["receipt"]
    assert receipt is not None

    authored.acknowledge_inbox(_STORE_KEY, receipt, consumer="agent-a")
    again = authored.inbox(_STORE_KEY, consumer="agent-a")
    assert again["messages"] == []  # acknowledged identities stop repeating
    assert again["withheld"]["duplicates"] == 2
    replayed = authored.inbox(_STORE_KEY, consumer="agent-a", replay=True)
    assert len(replayed["messages"]) == 2  # replay deliberately retrieves acknowledged messages


def test_inbox_raises_the_shared_disabled_signal_when_moments_are_off(relay: _RelayDouble, state_root: Path) -> None:
    from specify_cli.zeitgeist_client import moments

    config = state_root / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[moments]\nagents = "off"\n', encoding="utf-8")
    credentials.store(repo=_STORE_KEY, relay_url=relay.url, token="t", token_kind="shared_team", session_ref="sess-author")
    with pytest.raises(moments.MomentsDisabled):
        authored.inbox(_STORE_KEY, consumer="agent-a")


def test_send_honors_the_same_explicit_opt_out(relay: _RelayDouble, state_root: Path, tmp_path: Path) -> None:
    from specify_cli.zeitgeist_client import moments

    config = state_root / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[moments]\nagents = "off"\n', encoding="utf-8")
    with pytest.raises(moments.MomentsDisabled):
        authored.send("question", "quiet?", cwd=tmp_path)
    assert relay.posts == []
