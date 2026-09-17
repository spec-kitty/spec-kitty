"""Z1-T1 §4 matrix: transport.ZeitgeistClient — offer()/focus_*()/presence().

Covers N1, N2 (forbidden-field zero-attempt), N3, N4, N5, N6
(750ms/drop-no-retry, one-offer-after-append), N12 (focus_end cannot claim
"revoked"), N15 (one active focus at a time), N16 (DND pauses focus only),
N17 (no fabricated client-side expiry), N18 (focus_ref derivation), and R1
(race: concurrent focus_heartbeat calls do not corrupt state).

``watch()``/``status()``/credential checkout are explicitly NOT covered here
— see docs/plans/zeitgeist-client-wp01-remaining.md for what remains
(validator.py schema checks, mcp_stdio.py, the CLI adapter, harness-asset
staging, credentials.py's network canary flow).
"""

from __future__ import annotations

import socket
import threading
import time
from unittest.mock import patch

import pytest

from kernel.clock import now_epoch, now_utc
from specify_cli.zeitgeist_client import budget, transport

from .conftest import mint_capability_token

# See tests/zeitgeist_client/test_grammar.py's pytestmark comment. This file
# uses real loopback sockets/threads (the Team Kitty double) but no
# subprocess and no git — the "fast" tier's actual disqualifier.
pytestmark = pytest.mark.fast


def closed_port_url() -> str:
    """A ``127.0.0.1`` URL with nothing listening (N5's connection-refused
    target). Local helper (not imported cross-module) to avoid depending on
    ``tests`` being on ``sys.path`` as an importable package — pytest.ini
    intentionally keeps ``.`` off ``pythonpath`` (see that file's own
    docstring)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


def _config(double_url: str, **overrides: object) -> transport.ClientConfig:
    base: dict[str, object] = {
        "relay_url": double_url,
        "token": "test-token",
        "harness": "claude-code",
        "session_id": "sess-1",
        "agent_id": "agent-1",
        "repo": "spec-kitty",
        "branch": "main",
    }
    base.update(overrides)
    return transport.ClientConfig(**base)  # type: ignore[arg-type]


# --- N1 / N2: forbidden-field zero-attempt --------------------------------


def test_n1_offer_with_forbidden_field_makes_zero_network_attempts(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit", "detail": "x"})
    assert result.outcome == transport.OfferOutcome.REFUSED_LOCAL
    assert result.elapsed_s == 0.0
    assert team_kitty_double.requests == []
    assert team_kitty_double.connection_count == 0


def test_n2_offer_with_nested_forbidden_field_makes_zero_network_attempts(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit", "meta": {"team_id": "t-1"}})
    assert result.outcome == transport.OfferOutcome.REFUSED_LOCAL
    assert team_kitty_double.connection_count == 0


# --- N3 / N4 / N5: 750ms/drop-no-retry -------------------------------------


def test_n3_slow_double_drops_at_budget_with_exactly_one_attempt(team_kitty_double):
    """Functional half of the #4015 split; the wall-clock window now lives in
    ``test_n3_slow_double_drops_within_the_offer_budget_window`` (nightly-only)."""
    team_kitty_double.configure(delay_s=2.0)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit"})

    assert result.outcome == transport.OfferOutcome.DROPPED_BUDGET
    assert team_kitty_double.connection_count == 1
    assert len(team_kitty_double.requests) == 1


@pytest.mark.performance
def test_n3_slow_double_drops_within_the_offer_budget_window(team_kitty_double):
    """Split from ``test_n3_slow_double_drops_at_budget_with_exactly_one_attempt``
    (#4015); budget preserved (nightly).

    Generous bound vs. the draft's +/-50ms: http.server + urllib overhead on
    a loaded CI box makes a razor-thin window flaky without changing the
    underlying behaviour under test (a hard total bound, not a per-op one).
    """
    team_kitty_double.configure(delay_s=2.0)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    start = time.monotonic()
    client.offer("presence.publish", {"activity": "file_edit"})
    wall = time.monotonic() - start

    assert budget.OFFER_BUDGET_S <= wall < 1.5


@pytest.mark.timing
def test_n4_double_rejects_immediately(team_kitty_double):
    team_kitty_double.configure(status=503)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit"})
    assert result.outcome == transport.OfferOutcome.REJECTED
    assert team_kitty_double.connection_count == 1


def test_n5_connection_refused_is_dropped_unreachable():
    client = transport.ZeitgeistClient(_config(closed_port_url()))
    result = client.offer("presence.publish", {"activity": "file_edit"})
    assert result.outcome == transport.OfferOutcome.DROPPED_UNREACHABLE


# --- N6: one-offer-after-append, no batching -------------------------------


def test_n6_two_sequential_heartbeats_produce_two_distinct_requests(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    r1 = client.focus_heartbeat()
    r2 = client.focus_heartbeat()

    assert r1.request_id != r2.request_id
    posts = [r for r in team_kitty_double.requests if r.method == "POST"]
    heartbeat_ids = {r.body["request_id"] for r in posts if r.body and r.body.get("op") == "focus.heartbeat"}
    assert len(heartbeat_ids) == 2


# --- N12: focus_end cannot claim "revoked" ---------------------------------


def test_n12_focus_end_rejects_revoked_reason(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    with pytest.raises(ValueError, match="revoked"):
        client.focus_end(reason="revoked")  # type: ignore[arg-type]


def test_n12_focus_end_accepts_user_and_timeout(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    result = client.focus_end(reason="user")
    assert result.outcome in (transport.OfferOutcome.SENT, transport.OfferOutcome.REJECTED)

    client.focus_start("mission-y")
    result = client.focus_end(reason="timeout")
    assert result.outcome in (transport.OfferOutcome.SENT, transport.OfferOutcome.REJECTED)


# --- N15: one active focus at a time, client-enforced -----------------------


def test_n15_second_focus_start_without_end_is_refused_local(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    first = client.focus_start("mission-x")
    assert first.outcome != transport.OfferOutcome.REFUSED_LOCAL

    second = client.focus_start("mission-y")
    assert second.outcome == transport.OfferOutcome.REFUSED_LOCAL
    # no second focus.start POST reached the double
    starts = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "focus.start"]
    assert len(starts) == 1


def test_n15_focus_start_after_end_is_allowed(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    client.focus_end(reason="user")
    second = client.focus_start("mission-y")
    assert second.outcome != transport.OfferOutcome.REFUSED_LOCAL


# --- N16: DND pauses focus reporting only, not presence ---------------------


def test_n16_dnd_pause_does_not_block_presence(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    pause_result = client.focus_pause(reason="dnd")
    assert pause_result.outcome != transport.OfferOutcome.REFUSED_LOCAL

    presence_result = client.presence(activity="file_edit", path="src/foo.py")
    assert presence_result.outcome != transport.OfferOutcome.REFUSED_LOCAL
    presence_posts = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "presence.publish"]
    assert len(presence_posts) == 1


# --- N17: no fabricated client-side expiry ----------------------------------


def test_n17_no_offer_fires_on_a_bare_timer(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    with patch.object(client, "offer", wraps=client.offer) as spy:
        client.focus_start("mission-x")
        assert spy.call_count == 1
        # no heartbeat/timer fires on its own while nothing else calls offer()
        time.sleep(0.3)
        assert spy.call_count == 1


def test_n17_focus_start_creates_no_background_timer_thread():
    before = threading.active_count()
    client = transport.ZeitgeistClient(_config(closed_port_url()))
    client.focus_start("mission-x")
    # allow any (incorrect) fire-and-forget thread to have started
    time.sleep(0.1)
    after = threading.active_count()
    assert after <= before + 1  # at most the daemon worker thread run_with_deadline spawns per offer, already finished/settling


# --- N18: focus_ref derivation ----------------------------------------------


def test_n18_focus_ref_with_wp_id(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x", wp_id="WP03")
    starts = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "focus.start"]
    assert starts[0].body["args"]["focus_ref"] == "mission-x.WP03"


def test_n18_focus_ref_without_wp_id(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    starts = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "focus.start"]
    assert starts[0].body["args"]["focus_ref"] == "mission-x"


# --- empty claims are omitted, never sent as "" ------------------------------
#
# Both wire schemas (FocusArgs / PresencePublish) pattern repo/branch with a
# >=1-char head, so an EMPTY-string claim present as a key is a guaranteed
# 422 on every op. A detached HEAD (or a spent git budget) yields branch ""
# from repo_identity.branch_name — since #186 wired presence/focus into the
# status seam that shape is reachable in production, and the honest wire
# form for "no branch to claim" is the key's absence.


def test_empty_branch_is_omitted_from_claim_args_not_sent_as_empty(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url, branch=""))
    result = client.focus_start("mission-x", wp_id="WP03")

    assert result.outcome == transport.OfferOutcome.SENT
    start = [r for r in team_kitty_double.requests if r.body.get("op") == "focus.start"][-1]
    assert "branch" not in start.body["args"]
    assert start.body["args"]["repo"] == "spec-kitty"


def test_empty_repo_and_branch_are_both_omitted_from_presence_args(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url, repo="", branch=""))
    result = client.presence("command")

    assert result.outcome == transport.OfferOutcome.SENT
    post = [r for r in team_kitty_double.requests if r.body.get("op") == "presence.publish"][-1]
    assert "repo" not in post.body["args"]
    assert "branch" not in post.body["args"]
    assert post.body["args"]["kind"] == "command"
    assert post.body["args"]["session_id"] == "sess-1"


# --- R1: race — concurrent focus_heartbeat calls ----------------------------


@pytest.mark.stress
def test_r1_concurrent_heartbeats_produce_independent_request_ids(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")

    results: list[transport.OfferResult] = []
    lock = threading.Lock()

    def _call() -> None:
        r = client.focus_heartbeat()
        with lock:
            results.append(r)

    threads = [threading.Thread(target=_call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(results) == 2
    assert results[0].request_id != results[1].request_id
    heartbeat_posts = [r for r in team_kitty_double.requests if r.body and r.body.get("op") == "focus.heartbeat"]
    assert len(heartbeat_posts) == 2
    assert len({r.body["request_id"] for r in heartbeat_posts}) == 2


# --- O1-C: focus_lease() — read-only lease state for the operability report -


def test_focus_lease_is_none_before_any_focus_start(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    focus_ref, started_at = client.focus_lease()
    assert focus_ref is None
    assert started_at is None


def test_focus_lease_reports_ref_and_start_time_after_focus_start(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    before = now_utc()
    client.focus_start("mission-x", wp_id="WP03")
    after = now_utc()
    focus_ref, started_at = client.focus_lease()
    assert focus_ref == "mission-x.WP03"
    assert started_at is not None
    assert before <= started_at <= after


def test_focus_lease_clears_after_focus_end(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    client.focus_end(reason="user")
    focus_ref, started_at = client.focus_lease()
    assert focus_ref is None
    assert started_at is None


def test_focus_lease_unchanged_by_heartbeat(team_kitty_double):
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.focus_start("mission-x")
    _, started_at_before = client.focus_lease()
    client.focus_heartbeat()
    _, started_at_after = client.focus_lease()
    assert started_at_before == started_at_after


# --- FIX-M2-10: offer() targets /managed/control with the required ---------
# --- headers/envelope, not /events -----------------------------------------


def test_offer_posts_to_managed_control_not_events(team_kitty_double):
    """The wire-shape defect itself: before this fix, offer() posted to
    ``<relay_url>/events`` — server.py's baseline Beacon route, which has no
    ``op`` dispatch at all and structurally cannot process a
    ``ControlEnvelope``. A real relay's managed op dispatcher lives at
    ``/managed/control`` (``zeitgeist/managed.py``) instead."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.presence("file_edit", path="src/foo.py")
    assert len(team_kitty_double.requests) == 1
    assert team_kitty_double.requests[0].path == "/managed/control"


def test_offer_body_includes_schema_version(team_kitty_double):
    """``managed_control.schema.json``'s ``ControlEnvelope`` requires
    ``schema_version`` (``additionalProperties: false``, ``required``) —
    the pre-fix envelope omitted it entirely."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.presence("file_edit")
    body = team_kitty_double.requests[0].body
    assert body["schema_version"] == "1.0.0"
    assert set(body.keys()) == {"schema_version", "op", "request_id", "args"}


def test_offer_sends_authorization_and_capability_headers(team_kitty_double):
    """Both gates a real relay enforces on this route: the outer
    ``AuthenticationMiddleware`` (``Authorization: Bearer <token>``, every
    route but ``/health``) and ``managed.py``'s own capability check
    (``X-Zeitgeist-Capability``) — the pre-fix request carried neither the
    right path nor the second header at all."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url, token="secret-token-1"))
    client.presence("file_edit")
    headers = team_kitty_double.requests[0].headers
    assert headers["Authorization"] == "Bearer secret-token-1"
    assert headers["X-Zeitgeist-Capability"] == "secret-token-1"


def test_offer_capability_credential_falls_back_to_token_when_unset(team_kitty_double):
    """FIX-M2-15: every config built before this fix (``capability_
    credential`` left at its default, ``None``) must keep sending the SAME
    value to both headers — no behaviour change for a single-credential
    deployment."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url, token="only-one-value"))
    client.presence("file_edit")
    headers = team_kitty_double.requests[0].headers
    assert headers["Authorization"] == "Bearer only-one-value"
    assert headers["X-Zeitgeist-Capability"] == "only-one-value"


def test_offer_sends_two_distinct_configured_credentials(team_kitty_double):
    """FIX-M2-15: when ``capability_credential`` IS configured, it — not
    ``token`` — is what reaches ``X-Zeitgeist-Capability``; ``token`` alone
    still reaches ``Authorization``."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url, token="team-shared-token", capability_credential="actor-capability-jwt"))
    client.presence("file_edit")
    headers = team_kitty_double.requests[0].headers
    assert headers["Authorization"] == "Bearer team-shared-token"
    assert headers["X-Zeitgeist-Capability"] == "actor-capability-jwt"


def test_offer_targets_managed_control_for_every_op(team_kitty_double):
    """Every offer()-driven op — presence AND every focus op AND the
    (client-unreachable-in-practice, but still wire-shape-identical)
    session.revoke path — goes through the SAME corrected target/headers,
    not just the op the original DQA-M2-02 probe happened to check first."""
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.presence("file_edit")
    client.focus_start("mission-x")
    client.focus_heartbeat()
    client.focus_pause(reason="user")
    client.focus_end(reason="user")
    assert len(team_kitty_double.requests) == 5
    for req in team_kitty_double.requests:
        assert req.path == "/managed/control"
        assert req.headers["X-Zeitgeist-Capability"] == "test-token"
        assert req.body["schema_version"] == "1.0.0"


# --- FIX-M2-10: real acceptance/rejection against a PROTOCOL-FAITHFUL ------
# --- double (managed_control_double, tests/zeitgeist_client/conftest.py) ---
#
# Unlike the recording-only team_kitty_double above, this double actually
# enforces AuthenticationMiddleware's Bearer gate, managed_auth.py's
# X-Zeitgeist-Capability HMAC verification (kind-scoped), and
# managed_control.schema.json's schema_version requirement — a request that
# reaches SENT here would be genuinely ACCEPTED (202) by a real relay, and
# one that is REJECTED here for the wrong reason (401/403/422) would be
# genuinely rejected by one too. This is what "verified against the live
# zeitgeist source, not the double" (FIX-M2-10 acceptance criterion 1) means
# for a test that cannot itself run a real zeitgeist container.


def _kinded_client(double, *, kind: str, session_id: str = "sess-1") -> transport.ZeitgeistClient:
    """Build a client whose ``token`` both matches ``double``'s configured
    ``shared_token`` (the Authorization gate) AND is a real, ``kind``-scoped
    capability token signed with ``double``'s own already-configured
    ``capability_key`` (the X-Zeitgeist-Capability gate) — the "one
    credential, two headers" model ``offer()``'s module docstring
    documents."""
    now = now_epoch()
    token = mint_capability_token(
        double.capability_key,
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind=kind,
        iat=now,
        exp=now + 300,
    )
    double.set_shared_token(token)
    return transport.ZeitgeistClient(
        transport.ClientConfig(
            relay_url=double.url,
            token=token,
            harness="claude-code",
            session_id=session_id,
            agent_id="agent-1",
            repo="spec-kitty",
            branch="main",
        )
    )


def test_offer_accepted_with_two_genuinely_independent_secrets(managed_control_double):
    """FIX-M2-15's own regression pin: ``_kinded_client`` above (and every
    FIX-M2-10 test built on it) only ever proved acceptance by setting the
    double's ``shared_token`` EQUAL to the minted capability JWT — not the
    genuinely two-unrelated-secrets shape a real SaaS-provisioned per-team
    relay actually uses (``ZEITGEIST_TOKEN``/``ZEITGEIST_CAPABILITY_KEY``
    minted independently, ``apps.live_capability.provisioning_docker.
    DockerProvisioningDriver.provision``) — exactly what DQA-M2-05
    reproduced failing (401/403) against by hand. This test leaves the
    double's default, already-different ``shared_token``/
    ``capability_key`` untouched and configures ``token``/
    ``capability_credential`` to match each independently."""
    assert managed_control_double.shared_token != managed_control_double.capability_key
    now = now_epoch()
    capability_jwt = mint_capability_token(
        managed_control_double.capability_key,
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind="presence",
        iat=now,
        exp=now + 300,
    )
    client = transport.ZeitgeistClient(
        transport.ClientConfig(
            relay_url=managed_control_double.url,
            token=managed_control_double.shared_token,
            capability_credential=capability_jwt,
            harness="claude-code",
            session_id="sess-1",
            agent_id="agent-1",
            repo="spec-kitty",
            branch="main",
        )
    )
    result = client.presence("file_edit")
    assert result.outcome == transport.OfferOutcome.SENT
    assert managed_control_double.applied_op_count("presence.publish") == 1
    sent_headers = managed_control_double.last_request_headers()
    assert sent_headers.get("Authorization") == f"Bearer {managed_control_double.shared_token}"
    assert sent_headers.get("X-Zeitgeist-Capability") == capability_jwt


def test_offer_presence_publish_accepted_by_protocol_faithful_double(managed_control_double):
    client = _kinded_client(managed_control_double, kind="presence")
    result = client.presence("file_edit", path="src/foo.py")
    assert result.outcome == transport.OfferOutcome.SENT
    assert managed_control_double.applied_op_count("presence.publish") == 1


def test_offer_focus_lifecycle_accepted_by_protocol_faithful_double(managed_control_double):
    client = _kinded_client(managed_control_double, kind="focus")
    assert client.focus_start("mission-x").outcome == transport.OfferOutcome.SENT
    assert client.focus_heartbeat().outcome == transport.OfferOutcome.SENT
    assert client.focus_pause(reason="user").outcome == transport.OfferOutcome.SENT
    assert client.focus_end(reason="user").outcome == transport.OfferOutcome.SENT
    assert managed_control_double.applied_op_count("focus.start") == 1
    assert managed_control_double.applied_op_count("focus.end") == 1


def test_offer_focus_op_without_prior_start_is_rejected_by_protocol_faithful_double(managed_control_double):
    """``managed.py``'s ``FocusNotStarted`` (404): the double's own
    faithfulness to "focus.heartbeat/pause require a prior focus.start for
    this key", not something offer() itself enforces server-side."""
    client = _kinded_client(managed_control_double, kind="focus")
    result = client.focus_heartbeat()
    # ZeitgeistClient.focus_heartbeat() refuses locally when the client has
    # no in-process focus_ref of its own — reach the wire directly via
    # offer() to exercise the relay's own guard instead.
    assert result.outcome == transport.OfferOutcome.REFUSED_LOCAL
    wire_result = client.offer(
        "focus.heartbeat",
        {"session_id": "sess-1", "repo": "spec-kitty", "focus_ref": "never-started", "ttl_s": 90},
    )
    assert wire_result.outcome == transport.OfferOutcome.REJECTED
    assert managed_control_double.applied_op_count("focus.heartbeat") == 0


def test_offer_rejected_when_capability_token_kind_does_not_grant_op(managed_control_double):
    """A ``presence``-kind capability token can never drive a ``focus.*``
    op — ``managed_auth._KIND_CAPS``'s own closed mapping, reproduced by
    the double."""
    client = _kinded_client(managed_control_double, kind="presence")
    result = client.focus_start("mission-x")
    assert result.outcome == transport.OfferOutcome.REJECTED
    assert managed_control_double.applied_op_count("focus.start") == 0


def test_offer_event_publish_accepted_by_presence_kind_capability(managed_control_double):
    """spec-kitty#30: ``managed_auth._KIND_CAPS["presence"]`` grants both
    ``presence.publish`` and ``event.publish`` on the real relay — the CLI's
    fire-and-forget status moment rides the same lease presence already
    holds. The double's ``_KIND_CAPS_DOUBLE``/``_ALL_MANAGED_OPS`` must stay
    in parity with that closed mapping."""
    client = _kinded_client(managed_control_double, kind="presence")
    result = client.offer(
        "event.publish",
        {"session_id": "sess-1", "kind": "WPStatusChanged", "attrs": {"to_lane": "doing"}},
    )
    assert result.outcome == transport.OfferOutcome.SENT
    assert managed_control_double.applied_op_count("event.publish") == 1


def test_offer_event_publish_rejected_when_capability_token_kind_does_not_grant_op(managed_control_double):
    """The inverse of the acceptance case above: a ``focus``-kind token
    never grants ``event.publish``.

    #352: ``OfferOutcome.REJECTED`` collapses both a 422 (unknown op) and a
    403 (known op, wrong kind) — asserting only the outcome can't tell those
    apart, so this couldn't distinguish "op not in _ALL_MANAGED_OPS" (not
    this PR's change) from "op known but kind doesn't grant it" (the actual
    behavior under test). Pin the double's raw status too so a future
    accidental drop of ``event.publish`` from ``_ALL_MANAGED_OPS`` fails
    this test loudly (422) instead of silently passing for the wrong
    reason. The payload pins the specific 403 detail as well.
    """
    client = _kinded_client(managed_control_double, kind="focus")
    result = client.offer(
        "event.publish",
        {"session_id": "sess-1", "kind": "WPStatusChanged", "attrs": {"to_lane": "doing"}},
    )
    assert result.outcome == transport.OfferOutcome.REJECTED
    assert managed_control_double.applied_op_count("event.publish") == 0
    assert managed_control_double.last_response_status() == (
        403,
        {"detail": "capability does not grant op event.publish"},
    )


def test_offer_rejected_when_authorization_bearer_is_wrong(managed_control_double):
    """``AuthenticationMiddleware``'s outer gate, checked before
    ``managed.py`` ever inspects ``X-Zeitgeist-Capability`` — a client
    presenting a token the relay's shared secret does not recognize is
    REJECTED (401) regardless of whether the capability signature is
    otherwise valid."""
    now = now_epoch()
    valid_capability_token = mint_capability_token(
        "cap-key",
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind="presence",
        iat=now,
        exp=now + 300,
    )
    managed_control_double.set_shared_token("a-completely-different-shared-secret")
    client = transport.ZeitgeistClient(
        transport.ClientConfig(
            relay_url=managed_control_double.url,
            token=valid_capability_token,
            harness="claude-code",
            session_id="sess-1",
            agent_id="agent-1",
            repo="spec-kitty",
            branch="main",
        )
    )
    result = client.presence("file_edit")
    assert result.outcome == transport.OfferOutcome.REJECTED
    assert managed_control_double.applied_op_count("presence.publish") == 0


# --- #180: 429 is a throttle, not a rejection -------------------------------
#
# zeitgeist#44's managed-control rate limiter answers a throttled credential
# with 429 (+ Retry-After + a JSON detail this client never reads). offer()
# still makes exactly one attempt — decisions/HIC-EPHEMERAL-TEAM-STATUS-
# 2026-08-25.md (decision C) and design/ephemeral-team-status.html both pin
# "no retry" / "≤750 ms" as binding, not incidental — but a 429 is now
# reported as THROTTLED (with the one-line stderr notice) instead of being
# folded into REJECTED where it vanished silently.


def test_429_is_reported_as_throttled_with_no_second_attempt(team_kitty_double):
    team_kitty_double.configure(status=429)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit"})

    assert result.outcome == transport.OfferOutcome.THROTTLED
    # Exactly one attempt — no retry, per the binding "no retry" decision.
    assert len(team_kitty_double.requests) == 1


def test_non_throttle_status_makes_no_second_attempt(team_kitty_double):
    """Every status keeps the original one-attempt contract (N4's 503, here
    401) — 429 is classified differently, not treated specially in attempt
    count."""
    team_kitty_double.configure(status=401)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    result = client.offer("presence.publish", {"activity": "file_edit"})

    assert result.outcome == transport.OfferOutcome.REJECTED
    assert len(team_kitty_double.requests) == 1


@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (404, "unknown host"),
        (401, "authentication required"),
        (422, "unknown_op at op"),
    ],
)
def test_rejected_offer_retains_distinguishable_bounded_diagnostic(team_kitty_double, status: int, detail: str):
    team_kitty_double.configure(status=status, body={"detail": detail})
    result = transport.ZeitgeistClient(_config(team_kitty_double.url)).offer("presence.publish", {"activity": "file_edit"})

    assert result.outcome == transport.OfferOutcome.REJECTED
    assert result.status_code == status
    assert result.response_detail == detail


def test_offer_response_diagnostic_redacts_both_credentials(team_kitty_double):
    relay_token = "relay-secret-value"
    capability = "capability-secret-value"
    team_kitty_double.configure(
        status=401,
        body={"detail": (f'Authorization: Bearer {relay_token}; {{"credential":"{capability}"}}')},
    )
    result = transport.ZeitgeistClient(
        _config(
            team_kitty_double.url,
            token=relay_token,
            capability_credential=capability,
        )
    ).offer("presence.publish", {"activity": "file_edit"})

    assert result.response_detail is not None
    assert relay_token not in result.response_detail
    assert capability not in result.response_detail
    assert "[redacted]" in result.response_detail


def test_throttled_notice_is_one_stderr_line(team_kitty_double, capsys):
    team_kitty_double.configure(status=429)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.offer("presence.publish", {"activity": "file_edit"})

    err = capsys.readouterr().err
    assert transport.THROTTLE_NOTICE in err
    assert err.count(transport.THROTTLE_NOTICE) == 1

    team_kitty_double.configure(status=200)
    client = transport.ZeitgeistClient(_config(team_kitty_double.url))
    client.offer("presence.publish", {"activity": "file_edit"})
    assert capsys.readouterr().err.count(transport.THROTTLE_NOTICE) == 0
