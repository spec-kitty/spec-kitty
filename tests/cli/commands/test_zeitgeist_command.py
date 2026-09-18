"""Z7-C: ``spec-kitty zeitgeist`` — the thin CLI adapter over
``subscription.py``'s shared team-scoped surface.

Covers: ``status``/``watch`` call subscription.py (not a second
implementation), no ``--relay-url``/``--token`` option exists on either
command (no runtime URL/credential), the ``NotCheckedOut``/network-fault
error paths exit non-zero without a stack trace, ``--json`` emits plain
JSON via the canonical console seam, the hidden ``mcp-serve`` command is
registered but not listed in ``--help``, and one true end-to-end run
against a real loopback double proves the whole CLI-to-relay wire-up
(not just the mocked unit path).
"""

from __future__ import annotations

import json
import urllib.error

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.zeitgeist import app
from specify_cli.zeitgeist_client import subscription

pytestmark = pytest.mark.fast

runner = CliRunner()


# --- no runtime URL/credential option on either command ---------------------


def test_status_command_has_no_relay_url_or_credential_option() -> None:
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    for forbidden in ("--relay-url", "--token", "--credential", "--runtime-url"):
        assert forbidden not in result.stdout


def test_watch_command_has_no_relay_url_or_credential_option() -> None:
    result = runner.invoke(app, ["watch", "--help"])
    assert result.exit_code == 0
    for forbidden in ("--relay-url", "--token", "--credential", "--runtime-url"):
        assert forbidden not in result.stdout


# --- mcp-serve is registered but hidden --------------------------------------


def test_mcp_serve_is_hidden_from_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "mcp-serve" not in result.stdout


def test_mcp_serve_dispatches_to_mcp_stdio_run_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.zeitgeist_client import mcp_stdio

    calls: list[bool] = []

    async def _fake_run_stdio() -> None:
        calls.append(True)

    monkeypatch.setattr(mcp_stdio, "run_stdio", _fake_run_stdio)
    result = runner.invoke(app, ["mcp-serve"])
    assert result.exit_code == 0
    assert calls == [True]


# --- status: mocked-unit paths -----------------------------------------------


def test_status_json_emits_the_subscription_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_result = {"repo": "spec-kitty", "epoch": "e1", "presence": [], "focus": [], "reset_count": 0, "last_reset_reason": None}
    monkeypatch.setattr(subscription, "status", lambda repo, *, timeout_s=2.0, filter_own=True: fake_result)

    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == fake_result


def test_status_not_checked_out_exits_nonzero_with_a_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(repo: str, *, timeout_s: float = 2.0, filter_own: bool = True) -> dict[str, object]:
        raise subscription.NotCheckedOut(repo)

    monkeypatch.setattr(subscription, "status", _raise)
    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty"])
    assert result.exit_code == 1
    assert "github.com/acme/spec-kitty" in result.stdout
    assert "checked out" in result.stdout.lower() or "checkout" in result.stdout.lower()


def test_status_bare_repo_name_is_rejected_with_the_accepted_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """#137: after #132 nothing is stored under a bare NAME, so accepting
    one could only ever serve an abandoned pre-#132 bearer. The command
    names the accepted form instead of failing with a confusing
    not-checked-out."""

    def _boom(repo: str, *, timeout_s: float = 2.0, filter_own: bool = True) -> dict[str, object]:  # pragma: no cover - must never run
        raise AssertionError("subscription.status must never be reached with an unusable key")

    monkeypatch.setattr(subscription, "status", _boom)
    result = runner.invoke(app, ["status", "widget"])
    assert result.exit_code == 1
    assert "host/owner/repo" in result.stdout
    assert "github.com/acme/widget" in result.stdout


def test_status_connection_fault_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(repo: str, *, timeout_s: float = 2.0, filter_own: bool = True) -> dict[str, object]:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(subscription, "status", _raise)
    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty"])
    assert result.exit_code == 1
    assert "connection refused" in result.stdout


# --- repo omitted: derived from the current checkout (#137) ------------------


def test_status_with_no_repo_argument_uses_the_checkout_derived_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The #137 acceptance path: running inside the checkout reads THAT
    checkout's auto-minted ``host/owner/repo`` entry, instead of reporting
    not-checked-out for a credential the bridge minted a minute ago."""
    seen: list[str] = []

    def _fake_status(repo: str, *, timeout_s: float = 2.0, filter_own: bool = True) -> dict[str, object]:
        seen.append(repo)
        return {"repo": repo, "epoch": "e1", "presence": [], "focus": [], "reset_count": 0, "last_reset_reason": None}

    monkeypatch.setattr(subscription, "status", _fake_status)
    monkeypatch.setattr("specify_cli.zeitgeist_client.resolution.store_key_for_checkout", lambda cwd: "github.com/acme/widget")
    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["repo"] == "github.com/acme/widget"
    assert seen == ["github.com/acme/widget"]


def test_status_with_no_repo_argument_and_no_checkout_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.zeitgeist_client.resolution.store_key_for_checkout", lambda cwd: None)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "host/owner/repo" in result.stdout


# --- watch: mocked-unit paths -------------------------------------------------
#
# (squad pass on #4716, recorded) These fakes mirror `subscription.watch`'s
# signature (seed_window_s included) but prove only the CLI's plumbing —
# flag parsing, exit codes, output framing. Real coverage of the seeded
# watch's behaviour lives in tests/zeitgeist_client/test_cli_zeitgeist_e2e.py
# (follow route, preface, dedup) and tests/zeitgeist_client/test_mcp_stdio.py
# (schema), never here.


def test_watch_json_emits_one_json_line_per_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [
        {"schema_version": "1.0.0", "epoch": "e1", "seq": 1, "emitted_at": 1.0, "frame_type": "presence", "payload": {}},
        {"schema_version": "1.0.0", "epoch": "e1", "seq": 2, "emitted_at": 2.0, "frame_type": "focus", "payload": {}},
    ]

    def _fake_watch(repo: str, *, timeout_s: float = 5.0, max_frames: int = 500, seed_window_s: float | None = None):
        yield from frames

    monkeypatch.setattr(subscription, "watch", _fake_watch)
    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--raw", "--json"])
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    payloads = [json.loads(line) for line in lines]
    assert payloads[:-1] == frames
    assert payloads[-1]["type"] == "watch_summary"
    assert payloads[-1]["frames"] == 2


def test_watch_not_checked_out_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(repo: str, *, timeout_s: float = 5.0, max_frames: int = 500, seed_window_s: float | None = None):
        raise subscription.NotCheckedOut(repo)
        yield  # pragma: no cover - never reached, makes this a generator function

    monkeypatch.setattr(subscription, "watch", _raise)
    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--raw"])
    assert result.exit_code == 1
    assert "github.com/acme/spec-kitty" in result.stdout


# The true end-to-end run (CLI -> subscription.py -> FilteredStream -> a real
# loopback SSE double) lives in
# tests/zeitgeist_client/test_cli_zeitgeist_e2e.py — it needs the
# managed_stream_double fixture, which that directory's conftest.py owns
# (pytest.ini deliberately keeps `.` off pythonpath, so fixtures are not
# shared across top-level test directories; see test_filtered_stream.py's
# own local-helper-duplication precedent for the same constraint).


# --- #10: the human-readable watch branch renders events through the frame ---


def test_watch_end_reason_covers_the_three_ways_a_watch_stops() -> None:
    """(squad pass on #4716) The summary's ``reason`` decision, extracted to
    keep the command inside the complexity ceiling — pinned directly so the
    extraction has its own coverage: cap, whole-call timeout (with the
    summary rounding's 50ms grace), or the relay closing the stream."""
    from specify_cli.cli.commands.zeitgeist import _watch_end_reason

    assert _watch_end_reason(count=10, max_frames=10, elapsed_s=0.1, effective_timeout=2.0) == "max_frames"
    assert _watch_end_reason(count=3, max_frames=10, elapsed_s=2.0, effective_timeout=2.0) == "timeout"
    # Inside the 50ms grace window the watch reads as closed, not timed out.
    assert _watch_end_reason(count=3, max_frames=10, elapsed_s=1.9, effective_timeout=2.0) == "stream_closed"


def test_watch_human_branch_frames_event_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """An event's attrs are another client's prose: the terminal rendering goes
    through subscription.render_event's nonce-framed untrusted block, never
    printed as this tool's own trusted output."""
    import re

    def _fake_watch(repo: str, *, timeout_s: float = 5.0, max_frames: int = 500, seed_window_s: float | None = None):
        yield {
            "schema_version": "1.0.0",
            "epoch": "epoch-1",
            "seq": 4,
            "emitted_at": 1.0,
            "frame_type": "event",
            "payload": {
                "observed_at": 1.0,
                "kind": "mission.status.changed",
                "actor": {"session_ref": "c" * 12},
                "attrs": {"to_lane": "for_review"},
            },
        }

    monkeypatch.setattr(subscription, "watch", _fake_watch)
    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--raw"])
    assert result.exit_code == 0
    assert "[zeitgeist moment " in result.stdout
    assert re.search(r"\[end of zeitgeist moment [0-9a-f]{8}\]", result.stdout)
    assert "to_lane=for_review" in result.stdout  # readable, but inside the block


def test_watch_json_keeps_the_raw_payload_for_event_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    """--json is the data channel: lossless frames for scripts, exactly as for
    presence/focus. Framing is a property of the renderer, not of the data."""
    import json as json_module

    payload = {"observed_at": 1.0, "kind": "mission.status.changed", "attrs": {"to_lane": "for_review"}}

    def _fake_watch(repo: str, *, timeout_s: float = 5.0, max_frames: int = 500, seed_window_s: float | None = None):
        yield {"schema_version": "1.0.0", "epoch": "e", "seq": 4, "emitted_at": 1.0, "frame_type": "event", "payload": payload}

    monkeypatch.setattr(subscription, "watch", _fake_watch)
    result = runner.invoke(app, ["watch", "github.com/acme/spec-kitty", "--raw", "--json"])
    assert result.exit_code == 0
    lines = [json_module.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert lines[0]["frame_type"] == "event"
    assert lines[0]["payload"]["attrs"] == {"to_lane": "for_review"}
    assert lines[1]["type"] == "watch_summary"


@pytest.mark.parametrize("flags,expected", [([], True), (["--raw"], False)])
def test_status_requests_own_filter_by_default_and_raw_opt_out(monkeypatch, flags, expected):
    def status(repo, *, timeout_s, filter_own):
        assert filter_own is expected
        return {"repo": repo}

    monkeypatch.setattr(subscription, "status", status)
    result = runner.invoke(app, ["status", "github.com/acme/widget", "--json", *flags])
    assert result.exit_code == 0, result.stdout


def test_status_own_filter_contract_fault_is_not_a_connection_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding #1 (PR #4224, issue #4549): ``status`` maps the own-filter
    contract's explicit ``ValueError`` failures (no cached publisher
    identity; a relay that will not confirm filtering) to their own handler,
    exactly like ``watch``/``activity`` — never to "could not reach the
    relay"."""
    message = "Zeitgeist relay did not confirm own filtering; upgrade the relay or explicitly request a raw feed"

    def _raise(repo: str, *, timeout_s: float = 2.0, filter_own: bool = True) -> dict[str, object]:
        raise ValueError(message)

    monkeypatch.setattr(subscription, "status", _raise)
    result = runner.invoke(app, ["status", "github.com/acme/spec-kitty"])
    assert result.exit_code == 1
    assert message in result.stdout
    assert "could not reach the relay" not in result.stdout
