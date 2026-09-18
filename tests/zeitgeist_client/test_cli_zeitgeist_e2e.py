"""Z7-C: one true end-to-end run of ``spec-kitty zeitgeist status`` — CLI
invocation through ``subscription.py`` through ``FilteredStream`` to a real
loopback SSE double. The unit-level CLI paths (help text, error handling,
``--json`` framing) are covered with mocked ``subscription`` calls in
``tests/cli/commands/test_zeitgeist_command.py``; this file is the one place
that proves the whole wire-up actually works end to end, not just each
layer in isolation.
"""

from __future__ import annotations

from kernel.clock import now_epoch

import json
import socket
import threading
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.zeitgeist import app
from specify_cli.zeitgeist_client import credentials
from tests._perf_helpers import assert_timing_budget

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


def _frame(*, seq: int, frame: dict[str, object], epoch: str = "epoch-1") -> dict[str, object]:
    return {"schema_version": "1.0.0", "epoch": epoch, "seq": seq, "emitted_at": now_epoch(), "frame": frame}


def _presence(session_ref: str = "a" * 12) -> dict[str, object]:
    return {"type": "presence", "presence": {"actor": {"session_ref": session_ref}, "observed_at": now_epoch(), "ttl_s": 30}}


def test_status_end_to_end_over_a_real_loopback_double(state_root: Path, managed_stream_double) -> None:
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="a" * 12)))
    managed_stream_double.close_stream()

    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty", "--timeout", "2.0", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["repo"] == "github.com/acme/spec-kitty"
    assert payload["presence"][0]["session_ref"] == "a" * 12
    assert managed_stream_double.received_headers[0].get("X-Zeitgeist-Capability") == "team-a-cred"


def test_status_end_to_end_answers_a_quiet_repo_from_the_relay_snapshot(state_root: Path, managed_stream_double) -> None:
    """#4215 end to end: nothing is ever published on this relay, yet the CLI
    reports the teammate the relay has on record, says where that came from,
    and dates the observation."""
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    managed_stream_double.snapshot_document = {
        "schema_version": "1.0.0",
        "epoch": "epoch-1",
        "seq": 4,
        "cursor": "epoch-1:4",
        "observed_at": now_epoch(),
        "presence": [
            {
                "observed_at": now_epoch() - 40,
                "ttl_s": 60,
                "expires_in_s": 20.0,
                "actor": {"session_ref": "d" * 12, "user": "alice"},
                "path": "src/app.py",
            }
        ],
        "focus": [],
        "events": [],
        "coverage": {"history_basis": "empty", "retained_frames": 0, "returned_frames": 0, "follow": False},
    }

    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty", "--timeout", "2.0"])

    assert result.exit_code == 0
    assert "d" * 12 in result.stdout
    assert "the relay's own record of who is live now" in result.stdout
    assert "observed 40s ago" in result.stdout


def test_status_end_to_end_dates_entries_skew_free_from_the_document_anchor(state_root: Path, managed_stream_double) -> None:
    """#4335 (folded here): the relay's clock is an HOUR ahead of this
    machine's. Entry age is derived from the document's own ``observed_at``
    anchor (both timestamps on the relay's clock) plus only the
    locally-measured time since fetch — so the entry the relay observed 40
    seconds before its anchor still prints ``observed 40s ago``. The legacy
    local-clock subtraction would read ``now - (relay_clock - 40)`` as
    strongly negative and clamp it to a lying ``observed 0s ago``."""
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    relay_ahead_by_s = 3600.0
    anchor = now_epoch() + relay_ahead_by_s
    managed_stream_double.snapshot_document = {
        "schema_version": "1.0.0",
        "epoch": "epoch-1",
        "seq": 4,
        "cursor": "epoch-1:4",
        "observed_at": anchor,
        "presence": [
            {
                "observed_at": anchor - 40,
                "ttl_s": 60,
                "expires_in_s": 20.0,
                "actor": {"session_ref": "d" * 12, "user": "alice"},
                "path": "src/app.py",
            }
        ],
        "focus": [],
        "events": [],
        "coverage": {"history_basis": "empty", "retained_frames": 0, "returned_frames": 0, "follow": False},
    }

    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty", "--timeout", "2.0"])

    assert result.exit_code == 0
    assert "observed 40s ago" in result.stdout
    assert "observed 0s ago" not in result.stdout


def test_status_end_to_end_says_a_quiet_listen_is_not_proof_nobody_is_working(state_root: Path, managed_stream_double) -> None:
    """The honesty half of the same acceptance criterion: on a relay with no
    snapshot route, an empty result is reported as "nothing was published",
    never as an empty team."""
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    managed_stream_double.close_stream()

    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty", "--timeout", "1.0"])

    assert result.exit_code == 0
    assert "not the same as nobody working" in result.stdout
    assert "snapshot_route_unavailable" in result.stdout


def test_watch_end_to_end_over_a_real_loopback_double(state_root: Path, managed_stream_double) -> None:
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="b" * 12)))
    managed_stream_double.close_stream()

    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--timeout", "2.0", "--json"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    frame = json.loads(lines[0])
    assert frame["frame_type"] == "presence"
    assert frame["payload"]["actor"]["session_ref"] == "b" * 12
    assert json.loads(lines[1])["type"] == "watch_summary"


def test_watch_quiet_repo_returns_one_json_summary_within_timeout(state_root: Path, managed_stream_double) -> None:
    """Functional half of the #4015 split; the wall-clock window now lives in
    ``test_watch_quiet_repo_summary_arrives_within_window`` (nightly-only)."""
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=managed_stream_double.url,
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    result = runner.invoke(
        app,
        ["watch", "github.com/acme/spec-kitty", "--timeout", "0.25", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "watch_summary"
    assert payload["frames"] == 0
    assert payload["reason"] == "timeout"


@pytest.mark.performance
def test_watch_quiet_repo_summary_arrives_within_window(state_root: Path, managed_stream_double) -> None:
    """Split from ``test_watch_quiet_repo_returns_one_json_summary_within_timeout``
    (#4015); budget preserved (nightly)."""
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=managed_stream_double.url,
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    started = time.monotonic()
    runner.invoke(
        app,
        ["watch", "github.com/acme/spec-kitty", "--timeout", "0.25", "--json"],
    )
    elapsed = time.monotonic() - started

    assert 0.20 <= elapsed < 0.75


def test_watch_connection_that_never_establishes_http_fails_within_timeout(
    state_root: Path,
) -> None:
    """Functional half of the #4015 split; the wall-clock ceiling now lives in
    ``test_watch_connection_that_never_establishes_fails_within_window``
    (nightly-only)."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    stop = threading.Event()

    def _accept_without_reply() -> None:
        connection, _ = listener.accept()
        try:
            stop.wait(2)
        finally:
            connection.close()

    server = threading.Thread(target=_accept_without_reply, daemon=True)
    server.start()
    port = listener.getsockname()[1]
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=f"http://127.0.0.1:{port}",
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    try:
        result = runner.invoke(
            app,
            ["watch", "github.com/acme/spec-kitty", "--timeout", "0.25", "--json"],
        )
    finally:
        stop.set()
        listener.close()
        server.join(timeout=1)

    assert result.exit_code == 1
    assert "could not reach the relay" in result.stdout
    assert "timed out" in result.stdout


@pytest.mark.performance
def test_watch_connection_that_never_establishes_fails_within_window(
    state_root: Path,
) -> None:
    """Split from ``test_watch_connection_that_never_establishes_http_fails_within_timeout``
    (#4015); budget preserved (nightly)."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    stop = threading.Event()

    def _accept_without_reply() -> None:
        connection, _ = listener.accept()
        try:
            stop.wait(2)
        finally:
            connection.close()

    server = threading.Thread(target=_accept_without_reply, daemon=True)
    server.start()
    port = listener.getsockname()[1]
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=f"http://127.0.0.1:{port}",
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    started = time.monotonic()
    try:
        runner.invoke(
            app,
            ["watch", "github.com/acme/spec-kitty", "--timeout", "0.25", "--json"],
        )
    finally:
        stop.set()
        listener.close()
        server.join(timeout=1)
    elapsed = time.monotonic() - started

    assert_timing_budget(elapsed, 0.75, name="watch_connection_never_establishes")


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (404, "unknown host"),
        (401, "authentication required"),
        (422, "unknown_op at op"),
    ],
)
def test_operability_report_distinguishes_relay_rejections(state_root: Path, team_kitty_double, status: int, detail: str) -> None:
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=team_kitty_double.url,
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    team_kitty_double.configure(status=status, body={"detail": detail})

    result = runner.invoke(app, ["operability", "report", "github.com/acme/spec-kitty"])

    assert result.exit_code == 0
    assert f"outcome=rejected ({status}: {detail})" in result.stdout


def test_operability_report_uses_a_supported_presence_canary(state_root: Path, team_kitty_double) -> None:
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=team_kitty_double.url,
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )

    result = runner.invoke(app, ["operability", "report", "github.com/acme/spec-kitty"])

    assert result.exit_code == 0
    assert "outcome=sent (200" in result.stdout
    assert team_kitty_double.requests[-1].body["op"] == "presence.publish"


# --- spec-kitty#137: no repo argument derives the key from the checkout -----


def _checkout_with_origin(bare: Path, dest: Path, origin: str) -> Path:
    """A minimal checkout whose origin claims ``origin`` (same shape as
    test_resolution.py's helper; fixtures are not shared across top-level
    test directories)."""
    import subprocess

    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "set-url", "origin", origin], cwd=dest, check=True, capture_output=True)
    return dest


def test_status_with_no_repo_argument_reads_the_checkout_own_credential(
    state_root: Path, managed_stream_double, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #137 acceptance probe, end to end: the bridge auto-mints under
    ``github.com/acme/widget`` (resolution.store_key of the checkout's
    origin); ``status`` run inside that checkout with NO repo argument must
    find exactly that entry — and a stale pre-#132 bare-name entry in the
    same store file must be neither matched nor served."""
    checkout = _checkout_with_origin(
        tmp_path / "server" / "acme" / "widget.git",
        tmp_path / "work" / "acme" / "widget",
        "https://github.com/acme/widget.git",
    )
    credentials.store(
        repo="github.com/acme/widget", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    # A leftover live-shaped bearer from before #132, still on disk.
    with credentials.credentials_path().open("a") as fh:
        fh.write('\n["widget"]\nrelay_url = "http://stale.invalid"\ntoken = "stale-bearer"\n')
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="c" * 12)))
    managed_stream_double.close_stream()

    monkeypatch.chdir(checkout)
    result = runner.invoke(app, ["status", "--timeout", "2.0", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["repo"] == "github.com/acme/widget"
    assert payload["presence"][0]["session_ref"] == "c" * 12
    assert managed_stream_double.received_headers[0].get("X-Zeitgeist-Capability") == "team-a-cred"


def _event(session_ref: str = "c" * 12) -> dict[str, object]:
    return {
        "type": "event",
        "event": {
            "observed_at": now_epoch(),
            "kind": "mission.status.changed",
            "actor": {"session_ref": session_ref, "user": "lynn"},
            "ref": "034-demo/WP01",
            "attrs": {"wp_id": "WP01", "to_lane": "for_review"},
        },
    }


def test_watch_end_to_end_delivers_a_status_moment_event_frame(state_root: Path, managed_stream_double) -> None:
    """The demo path's step 1: a teammate moves a WP, and `spec-kitty
    zeitgeist watch` shows it within a second. Before #10 the client dropped
    the relay's `event` frame unread, so the moment never reached Bob."""
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url=managed_stream_double.url,
        token="team-a-cred",
        session_ref="issuer-reader",
        token_kind="shared_team",
    )
    managed_stream_double.push_frame(_frame(seq=1, frame=_event()))
    managed_stream_double.close_stream()

    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--timeout", "2.0", "--json"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2  # one pushed moment plus the terminal summary
    frame = json.loads(lines[0])
    assert frame["frame_type"] == "event"
    assert frame["payload"]["kind"] == "mission.status.changed"
    assert frame["payload"]["attrs"] == {"wp_id": "WP01", "to_lane": "for_review"}
    assert json.loads(lines[1])["type"] == "watch_summary"


# --- spec-kitty#4215: seeded watch and person/project activity, end to end ---


def _seed_document(events: list[dict[str, object]]) -> dict[str, object]:
    seq = max((int(e["seq"]) for e in events), default=0)
    return {
        "schema_version": "1.0.0",
        "epoch": "epoch-1",
        "seq": seq,
        "cursor": f"epoch-1:{seq}",
        "observed_at": now_epoch(),
        "presence": [],
        "focus": [],
        "events": events,
        "coverage": {
            "history_basis": "retained" if events else "empty",
            "retained_frames": len(events),
            "returned_frames": len(events),
            "follow": True,
        },
    }


def test_watch_seed_end_to_end_over_a_real_loopback_follow_double(state_root: Path, managed_stream_double) -> None:
    """#4215 end to end: `watch --seed` replays the relay's retained history
    first (the follow=1 preface), then continues live, deduplicating the
    overlap the relay's reserve-before-snapshot order can produce — one CLI
    invocation, one connection, no lost startup window."""
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    retained = _frame(seq=1, frame=_presence(session_ref="a" * 12))
    managed_stream_double.snapshot_document = _seed_document([retained])
    # The same (epoch, seq) arrives live after the preface: overlap to drop.
    managed_stream_double.push_frame(retained)
    managed_stream_double.push_frame(_frame(seq=2, frame=_presence(session_ref="c" * 12)))
    managed_stream_double.close_stream()

    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--timeout", "2.0", "--seed", "120", "--json"])

    assert result.exit_code == 0, result.stdout
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    frames = [json.loads(line) for line in lines[:-1]]
    summary = json.loads(lines[-1])
    assert [f["seq"] for f in frames] == [1, 2]  # history, then the NEW live frame; the overlap copy is deduplicated
    assert summary["type"] == "watch_summary"
    assert summary["seed"]["coverage"]["history_basis"] == "retained"
    assert any(p.startswith("/managed/snapshot?") and "follow=1" in p for p in managed_stream_double.requested_paths)


def test_watch_seed_reports_a_relay_without_the_route_honestly(state_root: Path, managed_stream_double) -> None:
    """A requested seed against a snapshot-less relay is a clean, named
    error — never a silent fall-back that looks like a future-only watch."""
    credentials.store(
        repo="github.com/acme/spec-kitty", relay_url=managed_stream_double.url, token="team-a-cred", session_ref="issuer-reader", token_kind="shared_team"
    )
    # snapshot_document unset + snapshot_status 404 is the double's default.

    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--timeout", "1.0", "--seed", "60", "--json"])

    assert result.exit_code == 1
    # Named for what actually happened (squad pass on #4716): the relay WAS
    # reached — what is missing is the follow route, not connectivity.
    assert "serves no snapshot/follow route" in result.stdout
    assert "could not reach the relay" not in result.stdout


@pytest.fixture()
def events_relay(monkeypatch: pytest.MonkeyPatch) -> object:
    """A loopback double for ``GET /managed/events`` (the retained-history
    route `activity` reads) — file-local, mirroring test_history.py's own
    fixture for the same reason that file keeps its copy: pytest.ini keeps
    ``.`` off pythonpath, so fixtures are not shared across directories."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from types import SimpleNamespace

    from specify_cli.zeitgeist_client import history

    state = SimpleNamespace(body={"schema_version": "1.0", "epoch": "epoch-1", "seq": 3, "events": []}, requests=[])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.requests.append(self.path)
            body = json.dumps(state.body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            # The real relay confirms own-session filtering when asked.
            self.send_header("X-Zeitgeist-Filter-Own", "true" if "filterOwn=true" in self.path else "false")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        history.credentials,
        "load",
        lambda **kwargs: SimpleNamespace(
            relay_url=f"http://127.0.0.1:{server.server_port}",
            token="outer",
            capability_credential="inner",
            session_ref="issuer-reader",
            # Admission metadata AgentDelivery scopes receipts by (stable
            # across renewal); the raw read never uses the token values.
            team="acme",
            host="github.com",
            repo_slug="acme/spec-kitty",
            focus_session_ref=None,
            focus_capability_credential=None,
        ),
    )
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _history_frame(seq: int, frame: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "1.0.0", "epoch": "epoch-1", "seq": seq, "emitted_at": now_epoch(), "frame": frame}


def _focus_payload(focus_ref: str, user: str) -> dict[str, object]:
    return {"type": "focus", "focus": {"actor": {"user": user, "session_ref": "b" * 12}, "focus_ref": focus_ref, "state": "active"}}


def test_activity_person_and_project_end_to_end_over_a_real_events_double(state_root: Path, events_relay) -> None:
    """#4215 end to end: the CLI's `--person`/`--project` selectors run
    against a real /managed/events response — the whole path (command →
    agent_activity → history.read_history → HTTP) with nothing mocked, and
    the selector's matched/withheld counts in the --json result."""
    events_relay.body["events"] = [
        _history_frame(1, _focus_payload("034-demo.WP01", "alice")),
        _history_frame(2, _focus_payload("034-demo.WP02", "bob")),
        _history_frame(3, _focus_payload("035-other", "alice")),
    ]

    result = runner.invoke(
        app,
        ["activity", "github.com/acme/spec-kitty", "--person", "alice", "--project", "034-demo", "--json", "--raw"],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert [f["seq"] for f in payload["frames"]] == [1]
    assert payload["frames"][0]["payload"]["focus_ref"] == "034-demo.WP01"
    assert payload["selector"] == {
        "person": "alice",
        "project": "034-demo",
        "matched_frames": 1,
        "withheld_frames": 2,
    }
    # The read went to the real retained-history route, unfiltered by the relay.
    assert events_relay.requests[0].startswith("/managed/events?")
    assert "filterOwn=false" in events_relay.requests[0]
