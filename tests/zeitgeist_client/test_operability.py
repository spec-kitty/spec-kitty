"""O1-C: ``operability.py`` — payload-free client operability signals and
local failure drills (program-graph handle O1-C, "Spec Kitty client
operability").

Covers the seven named signals (offer/drop/latency/revoke/lease/MCP/repair),
the two hard-bound denominators (750ms offer budget, 90s focus-lease TTL),
the "no sensitive fields" guarantee (reused directly against
``sanitizer``'s own forbidden-key sets — the same gate the rest of the
client already trusts), and the three local drills (timeout/rotation/
rollback) named by O1-C's own node criterion. None of this touches a real
network or a real controlling terminal: the timeout drill uses a loopback
connection-refused target (same technique as ``test_transport.py``'s
``closed_port_url()``), and the rollback drill never reaches
``outbox_approval``'s human-gesture seam because it deliberately drills the
fail-closed guard that runs BEFORE that seam.
"""

from __future__ import annotations

import dataclasses
import socket
from pathlib import Path

import pytest

from kernel.clock import now_utc, timedelta
from specify_cli.zeitgeist_client import (
    budget,
    credentials,
    operability,
    outbox_approval,
    sanitizer,
    transport,
)
from specify_cli.zeitgeist_client.live_frame import TeamSnapshot

pytestmark = pytest.mark.fast


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


def closed_port_url() -> str:
    """A ``127.0.0.1`` URL with nothing listening — mirrors
    ``test_transport.py``'s own local helper (deliberately not imported
    cross-module, see that file's docstring for why)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


class FakeTTY:
    """A scripted stand-in for the controlling terminal — local copy of
    ``test_outbox_approval.py``'s own helper (deliberately not imported
    cross-module, matching that file's own precedent)."""

    def __init__(self, response: str) -> None:
        self.response = response

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass

    def readline(self) -> str:
        return self.response + "\n"

    def close(self) -> None:
        pass


def _config(url: str, **overrides: object) -> transport.ClientConfig:
    base: dict[str, object] = {
        "relay_url": url,
        "token": "test-token",
        "harness": "claude-code",
        "session_id": "sess-1",
        "agent_id": "agent-1",
        "repo": "github.com/acme/spec-kitty",
        "branch": "main",
    }
    base.update(overrides)
    return transport.ClientConfig(**base)  # type: ignore[arg-type]


# --- offer / drop / latency signals -----------------------------------------


def test_offer_signal_from_sent_result_reports_the_750ms_denominator(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.OfferSignal.from_result(result)
    assert signal.outcome == "sent"
    assert signal.budget_s == budget.OFFER_BUDGET_S
    assert signal.within_budget is True


def test_offer_signal_reports_dropped_budget_outcome_honestly(team_kitty_double):
    team_kitty_double.configure(delay_s=2.0)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.OfferSignal.from_result(result)
    assert signal.outcome == "dropped_budget"
    assert signal.budget_s == budget.OFFER_BUDGET_S


def test_drop_signal_true_for_every_dropped_outcome(team_kitty_double):
    team_kitty_double.configure(delay_s=2.0)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.DropSignal.from_result(result)
    assert signal.dropped is True
    assert signal.reason == "dropped_budget"


def test_drop_signal_false_for_sent(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.DropSignal.from_result(result)
    assert signal.dropped is False
    assert signal.reason is None


def test_drop_signal_true_for_connection_refused():
    client = transport.ZeitgeistClient(_config(closed_port_url()))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.DropSignal.from_result(result)
    assert signal.dropped is True
    assert signal.reason == "dropped_unreachable"


# --- lease signal: honest <=90s current-focus reporting ---------------------


def test_lease_signal_inactive_when_no_focus_started(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    signal = operability.lease_signal(client)
    assert signal.active is False
    assert signal.ttl_s == transport.FOCUS_TTL_S
    assert signal.remaining_s is None


def test_lease_signal_active_reports_remaining_within_the_90s_denominator(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    signal = operability.lease_signal(client)
    assert signal.active is True
    assert signal.ttl_s == 90
    assert signal.remaining_s is not None
    assert 0.0 < signal.remaining_s <= 90.0


def test_lease_signal_remaining_clamps_to_zero_past_the_ttl(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    far_future = now_utc() + timedelta(seconds=1000)
    signal = operability.lease_signal(client, at=far_future)
    assert signal.remaining_s == 0.0


def test_lease_signal_remaining_clamps_to_ttl_when_at_predates_lease_start(team_kitty_double):
    """Renata HIGH-adjacent LOW finding: a backward clock adjustment (or an
    `at` earlier than the lease's own started_at) must never report
    remaining_s ABOVE the ttl_s denominator it is measured against."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    _focus_ref, started_at = client.focus_lease()
    assert started_at is not None
    before_start = started_at - timedelta(seconds=1000)

    signal = operability.lease_signal(client, at=before_start)

    assert signal.remaining_s == float(transport.FOCUS_TTL_S)


def test_lease_signal_inactive_after_focus_end(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    client.focus_end(reason="user")
    signal = operability.lease_signal(client)
    assert signal.active is False
    assert signal.remaining_s is None


# --- revoke signal: outbox counts, never content ----------------------------


def test_revoke_signal_reports_zero_when_nothing_pending(state_root: Path):
    signal = operability.revoke_signal("github.com/acme/spec-kitty")
    assert signal.repo == "github.com/acme/spec-kitty"
    assert signal.revocable_count == 0


def test_revoke_signal_model_reachable_is_always_false(state_root: Path):
    signal = operability.revoke_signal("github.com/acme/spec-kitty")
    assert signal.model_reachable is False


def test_revoke_signal_counts_only_approved_items_as_revocable(state_root: Path, monkeypatch: pytest.MonkeyPatch):
    approved = outbox_approval.submit(repo="github.com/acme/spec-kitty", audience="team-a", content="approve me")
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: FakeTTY(approved.item_id[:8]))
    outbox_approval.approve(approved.item_id, actor="robert")
    outbox_approval.submit(repo="github.com/acme/spec-kitty", audience="team-a", content="still pending")

    signal = operability.revoke_signal("github.com/acme/spec-kitty")
    assert signal.revocable_count == 1


# --- MCP signal: exactly the subscription two-tool surface -------------------


def test_mcp_signal_reports_reachable_and_the_exact_read_tool_surface():
    signal = operability.mcp_signal()
    assert signal.reachable is True
    assert signal.tool_names == ("zeitgeist_activity", "zeitgeist_status", "zeitgeist_watch")


def test_mcp_signal_reports_unreachable_when_agent_moments_are_off(moments_config: Path):
    """PR #201 MAJOR: operability is an operator diagnostic, so a developer's
    agent-moment off switch must not make the report command traceback."""
    moments_config.write_text('[moments]\nagents = "off"\n')
    signal = operability.mcp_signal()
    assert signal == operability.McpSignal(reachable=False, tool_names=())


def test_mcp_signal_never_names_an_outbox_tool():
    signal = operability.mcp_signal()
    for name in signal.tool_names:
        assert "outbox" not in name
        assert "approve" not in name
        assert "reject" not in name
        assert "revoke" not in name


# --- repair signal: honest stale-vs-observed reporting -----------------------


def test_repair_signal_reports_stale_when_no_snapshot_supplied():
    signal = operability.repair_signal(None)
    assert signal.observed is False
    assert signal.reset_count == 0
    assert signal.last_reset_reason is None


def test_repair_signal_reports_reset_count_and_reason_from_a_snapshot():
    snapshot = TeamSnapshot(epoch="e2", presence=(), focus=(), reset_count=3, last_reset_reason="gap")
    signal = operability.repair_signal(snapshot)
    assert signal.observed is True
    assert signal.reset_count == 3
    assert signal.last_reset_reason == "gap"


# --- collect_report(): the combined, payload-free snapshot -------------------


def test_collect_report_offline_reports_honest_staleness(state_root: Path):
    report = operability.collect_report(repo="github.com/acme/spec-kitty")
    assert report.repo == "github.com/acme/spec-kitty"
    assert report.credential_checked_out is False
    assert report.offer is None
    assert report.drop is None
    assert report.lease.active is False
    assert report.repair.observed is False


def test_collect_report_with_a_live_client_probes_offer(state_root: Path, team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    report = operability.collect_report(repo="github.com/acme/spec-kitty", client=client)
    assert report.offer is not None
    assert report.offer.outcome == "sent"
    assert report.drop is not None
    assert report.drop.dropped is False
    probes = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "presence.publish"]
    assert len(probes) == 1
    assert probes[0].body["args"]["kind"] == "command"


def test_collect_report_reflects_stored_checkout(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://127.0.0.1:9", token="tok", token_kind="shared_team")
    report = operability.collect_report(repo="github.com/acme/spec-kitty")
    assert report.credential_checked_out is True


def test_collect_report_never_carries_a_forbidden_sensitive_field(state_root: Path, team_kitty_double):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url=team_kitty_double.url, token="secret-token", token_kind="shared_team")
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    snapshot = TeamSnapshot(epoch="e1", presence=(), focus=(), reset_count=1, last_reset_reason="epoch")
    report = operability.collect_report(repo="github.com/acme/spec-kitty", client=client, snapshot=snapshot)

    payload = dataclasses.asdict(report)
    sanitizer.assert_clean(payload, forbidden=sanitizer.FORBIDDEN_CONTROL_KEYS)
    sanitizer.assert_clean(payload, forbidden=sanitizer.FORBIDDEN_OBSERVATION_KEYS)
    assert "secret-token" not in repr(payload)


# --- timeout drill: relay unreachable ----------------------------------------


def test_timeout_drill_against_an_unreachable_relay_passes_within_the_750ms_denominator():
    result = operability.timeout_drill(closed_port_url())
    assert result.outcome == "pass"
    assert result.drop.dropped is True
    assert result.offer.elapsed_s <= result.offer.budget_s + 0.5  # loopback refuse — near-instant, generous CI margin
    assert result.offer.budget_s == budget.OFFER_BUDGET_S


def test_timeout_drill_default_target_is_unreachable():
    result = operability.timeout_drill()
    assert result.outcome == "pass"


# --- rotation drill: auth expiry ---------------------------------------------


def test_rotation_drill_reports_not_checked_out_when_nothing_stored(state_root: Path):
    result = operability.rotation_drill("github.com/acme/spec-kitty")
    assert result.outcome == "pass"
    assert result.checked_out is False
    assert result.age_s is None
    assert result.rotation_due is False
    assert result.rotation_window_s == operability.ROTATION_WINDOW_S


def test_rotation_drill_reports_age_and_rotation_due_flag_honestly(state_root: Path, monkeypatch: pytest.MonkeyPatch):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://127.0.0.1:9", token="tok", token_kind="shared_team")
    stale = credentials.load(repo="github.com/acme/spec-kitty")
    assert stale is not None
    stale_issued = dataclasses.replace(stale, token_issued_at=(now_utc() - timedelta(seconds=operability.ROTATION_WINDOW_S + 60)).isoformat())
    monkeypatch.setattr(credentials, "load", lambda *, repo: stale_issued)

    result = operability.rotation_drill("github.com/acme/spec-kitty")
    assert result.checked_out is True
    assert result.rotation_due is True
    assert result.age_s is not None
    assert result.age_s >= operability.ROTATION_WINDOW_S


def test_rotation_drill_reports_rotation_not_due_for_a_fresh_credential(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://127.0.0.1:9", token="tok", token_kind="shared_team")
    result = operability.rotation_drill("github.com/acme/spec-kitty")
    assert result.rotation_due is False


# --- rollback drill: revoke fails closed before any human gesture -----------


def test_rollback_drill_blocks_revoke_of_a_never_approved_item(state_root: Path, monkeypatch: pytest.MonkeyPatch):
    def _boom():
        raise AssertionError("rollback_drill must never open the controlling terminal")

    monkeypatch.setattr(outbox_approval, "_controlling_tty", _boom)
    result = operability.rollback_drill(repo="github.com/acme/spec-kitty")
    assert result.outcome == "pass"
    assert result.blocked_reason == "not_yet_approved"
    assert outbox_approval.show(result.item_id).status == "pending"


def test_rollback_drill_is_content_addressed_and_idempotent(state_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(outbox_approval, "_controlling_tty", lambda: (_ for _ in ()).throw(AssertionError("no tty")))
    first = operability.rollback_drill(repo="github.com/acme/spec-kitty")
    second = operability.rollback_drill(repo="github.com/acme/spec-kitty")
    assert first.item_id == second.item_id
    assert outbox_approval.status_counts(repo="github.com/acme/spec-kitty")["pending"] == 1


def test_rollback_drill_rerun_after_its_own_ttl_lapses_still_passes(state_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Renata HIGH finding: `rollback_drill` is content-addressed, so a
    second call for the same repo made AFTER `_ROLLBACK_DRILL_TTL_S` has
    lapsed resubmits/returns the SAME item_id, now already swept to
    "expired" by outbox_approval.submit()'s own sweep. revoke() on that row
    raises outbox_approval.Expired (not InvalidTransition) -- this must be
    caught and reported as an honest "pass" (fail-closed either way), never
    left to propagate as an unhandled exception. Reproduces the exact
    "run the drill again a bit later" usage pattern that crashed."""

    def _boom():
        raise AssertionError("rollback_drill must never open the controlling terminal")

    monkeypatch.setattr(outbox_approval, "_controlling_tty", _boom)

    first = operability.rollback_drill(repo="github.com/acme/spec-kitty")
    assert first.outcome == "pass"
    assert first.blocked_reason == "not_yet_approved"

    # Advance past the drill's own 1.0s TTL so the SAME content-addressed
    # item_id is now expired, not merely pending.
    past_ttl = now_utc() + timedelta(seconds=operability._ROLLBACK_DRILL_TTL_S + 1)
    monkeypatch.setattr(outbox_approval, "_now", lambda: past_ttl)

    second = operability.rollback_drill(repo="github.com/acme/spec-kitty")

    assert second.item_id == first.item_id
    assert second.outcome == "pass"
    assert second.blocked_reason == "expired_before_disposition"
    assert outbox_approval.show(second.item_id).status == "expired"


def test_drop_signal_true_for_throttled(team_kitty_double):
    """#180: a 429 on the single attempt is a lost frame — the drop signal
    names it, while an ordinary REJECTED keeps reading as the relay's answer
    rather than a loss."""
    team_kitty_double.configure(status=429)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    signal = operability.DropSignal.from_result(result)
    assert signal.dropped is True
    assert signal.reason == "throttled"


def test_offer_signal_reports_throttled_outcome_honestly(team_kitty_double):
    team_kitty_double.configure(status=429)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "command"})
    assert operability.OfferSignal.from_result(result).outcome == "throttled"
