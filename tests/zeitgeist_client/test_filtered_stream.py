"""Z4-C §network layer: ``filtered_stream.FilteredStream`` over F3's
``GET /managed/stream`` — one SSE connection per team-bound subscription.

Covers: the capability credential is the ONLY selector sent (forbidden-field
denial by construction — there is no team/deployment/repo parameter to leak
one through), composable non-aggregating subscriptions, watch() updating
local state as check()/current_focus() read it back with no network call of
their own, and the network fault/race/security matrix around that loop.

``live_frame``'s own parsing/state-machine matrix (gap/epoch/revoke/<=90s
clear) is covered in ``test_live_frame.py`` and is not re-derived here —
these tests exercise the wire/loop mechanics that sit on top of it.
"""

from __future__ import annotations

from kernel.clock import now_epoch

import inspect
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from specify_cli.zeitgeist_client import filtered_stream, sanitizer

from .conftest import mint_capability_token

pytestmark = pytest.mark.fast


def closed_port_url() -> str:
    """A ``127.0.0.1`` URL with nothing listening (connection-refused
    target). Local helper, not imported cross-module — same reasoning as
    ``test_transport.py``'s own copy: pytest.ini deliberately keeps ``.``
    off ``pythonpath``, so ``tests`` is not importable as a package."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


def _config(url: str, credential: str = "cred-team-a") -> filtered_stream.TeamStreamConfig:
    return filtered_stream.TeamStreamConfig(relay_url=url, capability_credential=credential)


def _frame(*, seq: int, frame: dict[str, object], epoch: str = "epoch-1") -> dict[str, object]:
    return {"schema_version": "1.0.0", "epoch": epoch, "seq": seq, "emitted_at": now_epoch(), "frame": frame}


def _presence(session_ref: str = "a" * 12) -> dict[str, object]:
    return {"type": "presence", "presence": {"actor": {"session_ref": session_ref}, "observed_at": now_epoch(), "ttl_s": 30}}


def _focus(focus_ref: str = "mission-x", state: str = "active", session_ref: str = "b" * 12) -> dict[str, object]:
    return {"type": "focus", "focus": {"actor": {"session_ref": session_ref}, "focus_ref": focus_ref, "state": state, "ttl_s": 90}}


def _signal(kind: str, **extra: object) -> dict[str, object]:
    signal: dict[str, object] = {"kind": kind}
    signal.update(extra)
    return {"type": "signal", "signal": signal}


def _drain(gen: object, n: int, timeout_s: float = 5.0) -> list[object]:
    """Pull exactly ``n`` items from a watch() generator, bounded — never an
    unbounded ``list(gen)`` against a stream that never signals EOF."""
    out: list[object] = []
    deadline = time.monotonic() + timeout_s
    it = iter(gen)  # type: ignore[call-overload]
    while len(out) < n:
        if time.monotonic() > deadline:
            raise TimeoutError(f"only drained {len(out)}/{n} frames before the {timeout_s}s bound")
        out.append(next(it))
    return out


# --- selector is the credential, structurally, nothing else -----------------


def test_watch_sends_the_capability_credential_header_and_nothing_else_identifying(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url, credential="team-a-cred"))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    _drain(gen, 1)
    gen.close()

    assert managed_stream_double.received_headers
    sent = managed_stream_double.received_headers[0]
    assert sent.get("X-Zeitgeist-Capability") == "team-a-cred"


def test_watch_sends_authorization_bearer_header_too(managed_stream_double) -> None:
    """FIX-M2-13: ``GET /managed/stream`` sits behind the SAME outer
    ``AuthenticationMiddleware`` (``Authorization: Bearer <token>``, every
    route but ``/health``) as ``POST /managed/control`` — the pre-fix
    request carried only ``X-Zeitgeist-Capability`` and was always 401'd by
    a real relay regardless of that header's validity. FIX-M2-15: when
    ``relay_token`` is unset (this test's config), both headers still fall
    back to the SAME stored credential — the single-credential shape every
    config built before FIX-M2-15 has."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url, credential="team-a-cred"))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    _drain(gen, 1)
    gen.close()

    sent = managed_stream_double.received_headers[0]
    assert sent.get("Authorization") == "Bearer team-a-cred"
    assert sent.get("X-Zeitgeist-Capability") == "team-a-cred"


def test_watch_sends_two_independent_credentials_when_relay_token_is_configured(managed_stream_double) -> None:
    """FIX-M2-15: a SaaS-provisioned per-team relay mints ``relay_token``
    (the deployment's shared bearer) and ``capability_credential`` (a
    per-actor JWT) as two INDEPENDENT secrets — each header must carry its
    OWN configured value, never one value doing double duty."""
    stream = filtered_stream.FilteredStream(
        filtered_stream.TeamStreamConfig(
            relay_url=managed_stream_double.url,
            relay_token="team-shared-token",
            capability_credential="actor-capability-jwt",
        )
    )
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    _drain(gen, 1)
    gen.close()

    sent = managed_stream_double.received_headers[0]
    assert sent.get("Authorization") == "Bearer team-shared-token"
    assert sent.get("X-Zeitgeist-Capability") == "actor-capability-jwt"


def test_team_stream_config_has_no_team_deployment_or_repo_field() -> None:
    """Forbidden-field denial by construction: there is structurally no
    field a caller could use to smuggle a client-supplied team filter — the
    credential IS the selector. Every one of these names is a member of
    ``sanitizer.FORBIDDEN_CONTROL_KEYS``."""
    field_names = set(filtered_stream.TeamStreamConfig.__dataclass_fields__)
    assert field_names == {"relay_url", "capability_credential", "relay_token", "own_sessions"}
    assert field_names.isdisjoint(sanitizer.FORBIDDEN_CONTROL_KEYS)


def test_public_surface_has_no_team_selector_parameter() -> None:
    """Same guarantee, checked across the whole public surface: no method
    of ``FilteredStream`` accepts a parameter named like a forbidden
    control key, so there is no way to pass one even by a future mistake."""
    for name in ("__init__", "watch", "check", "current_focus"):
        sig = inspect.signature(getattr(filtered_stream.FilteredStream, name))
        params = set(sig.parameters) - {"self"}
        assert params.isdisjoint(sanitizer.FORBIDDEN_CONTROL_KEYS), f"{name} accepts a forbidden-key-named parameter"


# --- watch() updates state; check()/current_focus() read it back locally ----


def test_check_reflects_frames_observed_by_a_running_watch(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    assert stream.check().presence == ()  # nothing observed yet: honestly empty, not an error

    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="a" * 12)))
    _drain(gen, 1)

    snap = stream.check()
    assert len(snap.presence) == 1
    assert snap.presence[0].session_ref == "a" * 12
    gen.close()


def test_current_focus_reflects_focus_frames(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_focus(focus_ref="mission-y")))
    _drain(gen, 1)

    focus = stream.current_focus()
    assert len(focus) == 1
    assert focus[0].focus_ref == "mission-y"
    gen.close()


def test_watch_yields_each_accepted_frame(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    managed_stream_double.push_frame(_frame(seq=2, frame=_focus()))
    frames = _drain(gen, 2)
    assert [f.frame_type for f in frames] == ["presence", "focus"]  # type: ignore[attr-defined]
    gen.close()


# --- no missed-event reconstruction: gap/epoch clear, revoke is scoped ------


def test_gap_signal_clears_check_snapshot(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    _drain(gen, 1)
    assert stream.check().presence

    managed_stream_double.push_frame(_frame(seq=2, frame=_signal("gap", from_seq=2, to_seq=4)))
    _drain(gen, 1)
    snap = stream.check()
    assert snap.presence == ()
    assert snap.last_reset_reason == "gap"
    gen.close()


def test_revoked_signal_removes_only_the_named_session(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="c" * 12)))
    managed_stream_double.push_frame(_frame(seq=2, frame=_presence(session_ref="d" * 12)))
    _drain(gen, 2)
    managed_stream_double.push_frame(_frame(seq=3, frame=_signal("revoked", session_ref="d" * 12)))
    _drain(gen, 1)

    refs = {p.session_ref for p in stream.check().presence}
    assert refs == {"c" * 12}
    gen.close()


# --- composability: two subscriptions never implicitly aggregate ------------


def test_two_subscriptions_never_share_state(managed_stream_double) -> None:
    stream_a = filtered_stream.FilteredStream(_config(managed_stream_double.url, credential="team-a"))
    stream_b = filtered_stream.FilteredStream(_config(managed_stream_double.url, credential="team-b"))

    gen_a = stream_a.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence(session_ref="a" * 12)))
    _drain(gen_a, 1)

    # stream_b never called watch(): its own state is untouched by stream_a's
    # traffic on the same double — there is no shared registry to leak through.
    assert stream_a.check().presence
    assert stream_b.check().presence == ()
    gen_a.close()


def test_module_offers_no_multi_subscription_aggregate_helper() -> None:
    """ "no implicit multi-team aggregate": the module must not offer a
    function/method whose job is to merge several FilteredStream states."""
    banned_substrings = ("aggregate", "merge", "union", "combine_all")
    public_names = [n for n in dir(filtered_stream) if not n.startswith("_")]
    offenders = [n for n in public_names if any(b in n.lower() for b in banned_substrings)]
    assert offenders == []


# --- request URL construction -------------------------------------------------


@pytest.mark.parametrize("own_sessions,filter_own", [(None, "false"), ("issuer-a", "true")])
def test_watch_merges_filterown_into_a_relay_url_query_string(monkeypatch: pytest.MonkeyPatch, own_sessions: str | None, filter_own: str) -> None:
    """Finding #10 (PR #4224, issue #4549): ``filterOwn`` merges into a
    relay_url's existing query string instead of blindly appending ``?…``
    (which would silently discard it) — the same urlencode construction
    ``history.py`` already uses."""
    from types import SimpleNamespace

    observed: dict[str, str] = {}

    class _Response:
        headers = {"X-Zeitgeist-Filter-Own": filter_own}

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def readline(self) -> bytes:
            return b""

    def _open(request: urllib.request.Request, **_kwargs: object) -> _Response:
        observed["url"] = request.full_url
        return _Response()

    monkeypatch.setattr(filtered_stream.budget.NoRedirects, "build", lambda: SimpleNamespace(open=_open))
    config = filtered_stream.TeamStreamConfig("http://relay/base/?ticket=x", "inner", "outer", own_sessions)
    assert list(filtered_stream.FilteredStream(config).watch()) == []
    assert observed["url"] == f"http://relay/base/managed/stream?ticket=x&filterOwn={filter_own}"


# --- fault / compatibility ----------------------------------------------------


def test_connection_refused_raises_on_first_next(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(closed_port_url()))
    gen = stream.watch()
    with pytest.raises(urllib.error.URLError):
        next(gen)


def test_non_2xx_status_raises_http_error(managed_stream_double) -> None:
    managed_stream_double.response_status = 403
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    with pytest.raises(urllib.error.HTTPError):
        next(gen)


def test_malformed_data_line_is_dropped_not_fatal(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_raw(b"data: not-json-at-all\n\n")
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)  # the malformed line is skipped; the real frame after it still arrives
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()


def test_unknown_frame_shape_is_dropped_not_fatal(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame({"schema_version": "2.0.0", "epoch": "e", "seq": 1, "emitted_at": 1.0, "frame": {}})
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()


def test_server_closing_the_stream_ends_watch_cleanly(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    _drain(gen, 1)
    managed_stream_double.close_stream()
    # No further frame arrives; the generator returns (StopIteration), it
    # does not raise.
    with pytest.raises(StopIteration):
        next(gen)


@pytest.mark.performance
def test_idle_timeout_stops_watch_without_raising(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch(idle_timeout_s=0.3)
    start = time.monotonic()
    with pytest.raises(StopIteration):
        next(gen)  # double never sends anything: idle timeout fires
    assert time.monotonic() - start < 3.0


@pytest.mark.performance
def test_timeout_is_a_hard_whole_call_bound_despite_sse_heartbeats(
    managed_stream_double,
) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch(idle_timeout_s=0.25)
    stop = threading.Event()

    def _heartbeat() -> None:
        while not stop.wait(0.02):
            managed_stream_double.push_raw(b": keepalive\n\n")

    sender = threading.Thread(target=_heartbeat, daemon=True)
    sender.start()
    started = time.monotonic()
    try:
        with pytest.raises(StopIteration):
            next(gen)
    finally:
        stop.set()
        sender.join(timeout=1)

    elapsed = time.monotonic() - started
    assert 0.20 <= elapsed < 0.75


# --- race: check() from another thread while watch() is applying frames -----


def test_concurrent_check_during_active_watch_does_not_raise(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()

    errors: list[BaseException] = []
    stop = threading.Event()

    def _read_repeatedly() -> None:
        try:
            while not stop.is_set():
                stream.check()
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion below
            errors.append(exc)

    reader = threading.Thread(target=_read_repeatedly, daemon=True)
    reader.start()
    for n in range(1, 21):
        managed_stream_double.push_frame(_frame(seq=n, frame=_presence(session_ref=f"{n:012d}".replace("0", "a"))))
    _drain(gen, 20)
    stop.set()
    reader.join(timeout=5)
    assert not reader.is_alive()
    assert errors == []
    gen.close()


# --- security: a hostile double cannot crash the loop ------------------------


def test_binary_garbage_chunk_between_valid_frames_is_dropped(managed_stream_double) -> None:
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_raw(b"\xff\xfe\x00garbage not even sse\n\n")
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()


def test_non_finite_ttl_over_sse_is_clamped_not_fatal_to_the_watch_loop(managed_stream_double) -> None:
    """A hostile/buggy relay can send JSON's ``Infinity``/``NaN`` tokens as
    ``ttl_s`` inside an otherwise well-formed presence frame — Python's own
    ``json.loads`` (used by ``FilteredStream._accept_line``) accepts them by
    default. Verified over a real loopback SSE connection: this must not
    raise out of ``next()`` and end the subscription for one bad field in
    one frame; the frame after it must still arrive."""
    hostile = {
        "type": "presence",
        "presence": {"actor": {"session_ref": "a" * 12}, "observed_at": now_epoch(), "ttl_s": float("inf")},
    }
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=hostile))
    managed_stream_double.push_frame(_frame(seq=2, frame=_presence(session_ref="b" * 12)))
    frames = _drain(gen, 2)  # neither call raises; both frames arrive
    assert [f.frame_type for f in frames] == ["presence", "presence"]  # type: ignore[attr-defined]
    refs = {p.session_ref for p in stream.check().presence}
    assert refs == {"a" * 12, "b" * 12}
    gen.close()


def test_oversized_nested_payload_is_still_shape_checked_not_trusted_blindly(managed_stream_double) -> None:
    presence_payload = {
        "actor": {"session_ref": "a" * 12},
        "observed_at": now_epoch(),
        "ttl_s": 30,
        "extra": {"nested": ["x"] * 500},
    }
    hostile = _frame(seq=1, frame={"type": "presence", "presence": presence_payload})
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    managed_stream_double.push_frame(hostile)
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]  # extra keys are ignored, not rejected outright, not crashed on
    gen.close()


# --- FIX-M2-13: real acceptance/rejection against a PROTOCOL-FAITHFUL ------
# --- double (managed_stream_auth_double, tests/zeitgeist_client/conftest.py)
#
# Unlike managed_stream_double above (records anything, gates nothing), this
# double actually enforces AuthenticationMiddleware's outer Bearer gate AND
# managed.py's own X-Zeitgeist-Capability HMAC verification, in the same
# 401-missing/403-invalid split _extract_identity() itself codes. A watch()
# call that reaches a frame here would genuinely reach one against a real
# relay, and one that is denied here for the wrong reason would be genuinely
# denied by one too — this is what "verified against the live zeitgeist
# source, not the double" (acceptance criterion 1) means for a test that
# cannot itself run a real zeitgeist container; the real-container contract
# test (contract_test_harness.py, evidence dir) covers criterion 2.


def _authed_config(double, *, kind: str = "presence") -> filtered_stream.TeamStreamConfig:
    """Mint a real, ``kind``-scoped capability token signed with ``double``'s
    own ``capability_key``, then configure the double's ``shared_token`` to
    equal that SAME minted token — the "one credential, two headers" model
    ``FilteredStream.watch()``'s FIX-M2-13 fix (and ``transport.py``'s
    identical FIX-M2-10 one) both rely on: a deployment that wants both
    gates satisfied by one stored value configures ``ZEITGEIST_TOKEN`` to
    literally equal the signed capability token (see ``filtered_stream.py``'s
    module docstring, and ``test_transport.py``'s identical ``_kinded_client``
    precedent)."""
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
    return filtered_stream.TeamStreamConfig(relay_url=double.url, capability_credential=token)


def test_watch_receives_real_frames_with_two_genuinely_independent_secrets(managed_stream_auth_double) -> None:
    """FIX-M2-15's own regression pin, distinct from ``_authed_config``'s
    existing precedent above: that helper (and every FIX-M2-13 test built
    on it) only ever proved acceptance by setting the double's
    ``shared_token`` EQUAL to the minted capability JWT — the exact
    "one credential doing double duty" shape a real SaaS-provisioned
    per-team relay does NOT use (``ZEITGEIST_TOKEN``/
    ``ZEITGEIST_CAPABILITY_KEY`` are minted as two unrelated random
    secrets, ``apps.live_capability.provisioning_docker.
    DockerProvisioningDriver.provision``). This test leaves the double's
    default, already-DIFFERENT ``shared_token``/``capability_key`` pair
    untouched and configures ``relay_token``/``capability_credential`` to
    match each independently — the genuinely two-secret shape DQA-M2-05
    reproduced failing against, now proven accepted."""
    assert managed_stream_auth_double.shared_token != managed_stream_auth_double.capability_key
    now = now_epoch()
    capability_jwt = mint_capability_token(
        managed_stream_auth_double.capability_key,
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind="presence",
        iat=now,
        exp=now + 300,
    )
    stream = filtered_stream.FilteredStream(
        filtered_stream.TeamStreamConfig(
            relay_url=managed_stream_auth_double.url,
            relay_token=managed_stream_auth_double.shared_token,
            capability_credential=capability_jwt,
        )
    )
    gen = stream.watch()
    managed_stream_auth_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()

    sent = managed_stream_auth_double.received_headers[0]
    assert sent.get("Authorization") == f"Bearer {managed_stream_auth_double.shared_token}"
    assert sent.get("X-Zeitgeist-Capability") == capability_jwt
    assert managed_stream_auth_double.denied_statuses == []


def test_watch_receives_real_frames_when_both_headers_are_valid(managed_stream_auth_double) -> None:
    stream = filtered_stream.FilteredStream(_authed_config(managed_stream_auth_double))
    gen = stream.watch()
    managed_stream_auth_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()

    sent = managed_stream_auth_double.received_headers[0]
    assert sent.get("Authorization", "").startswith("Bearer ")
    assert sent.get("X-Zeitgeist-Capability")
    assert managed_stream_auth_double.denied_statuses == []  # never denied


def test_watch_accepts_any_capability_kind_unlike_managed_control(managed_stream_auth_double) -> None:
    """``/managed/stream``'s own ``_extract_identity(request)`` call passes
    no ``needs_op`` — unlike ``POST /managed/control``'s per-op kind check —
    so an ``operator``-kind capability (which grants no control op at all)
    still admits a stream connection."""
    stream = filtered_stream.FilteredStream(_authed_config(managed_stream_auth_double, kind="operator"))
    gen = stream.watch()
    managed_stream_auth_double.push_frame(_frame(seq=1, frame=_presence()))
    frames = _drain(gen, 1)
    assert frames[0].frame_type == "presence"  # type: ignore[attr-defined]
    gen.close()


def test_watch_raises_401_when_authorization_bearer_is_wrong(managed_stream_auth_double) -> None:
    """``AuthenticationMiddleware``'s outer gate, checked before
    ``managed.py`` ever inspects ``X-Zeitgeist-Capability`` — a client
    presenting a credential the relay's shared secret does not recognize is
    401'd regardless of whether the capability signature is otherwise
    valid. This double's ``authorized()`` mismatch reproduces exactly what
    the pre-fix code (no ``Authorization`` header at all) always hit against
    a real relay."""
    now = now_epoch()
    valid_capability_token = mint_capability_token(
        managed_stream_auth_double.capability_key,
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind="presence",
        iat=now,
        exp=now + 300,
    )
    managed_stream_auth_double.set_shared_token("a-completely-different-shared-secret")
    stream = filtered_stream.FilteredStream(
        filtered_stream.TeamStreamConfig(relay_url=managed_stream_auth_double.url, capability_credential=valid_capability_token)
    )
    gen = stream.watch()
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        next(gen)
    assert exc_info.value.code == 401
    assert managed_stream_auth_double.denied_statuses == [401]


def test_watch_raises_403_when_capability_signature_is_wrong(managed_stream_auth_double) -> None:
    """The Authorization gate alone is not enough: a credential that passes
    ``AuthenticationMiddleware``'s literal-match check but is not a validly
    HMAC-signed capability token is denied by ``managed.py``'s own gate —
    ``_extract_identity``'s "malformed" reason maps to 403, not 401 (only a
    completely absent capability header maps to 401 — see the raw-request
    test below)."""
    bogus_credential = "not-a-real-capability-token"
    managed_stream_auth_double.set_shared_token(bogus_credential)  # passes the Authorization gate...
    stream = filtered_stream.FilteredStream(filtered_stream.TeamStreamConfig(relay_url=managed_stream_auth_double.url, capability_credential=bogus_credential))
    gen = stream.watch()
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        next(gen)  # ...but fails managed_auth's HMAC verification
    assert exc_info.value.code == 403
    assert managed_stream_auth_double.denied_statuses == [403]


def test_raw_request_without_authorization_header_is_401_by_the_double(managed_stream_auth_double) -> None:
    """Direct proof of "with and without Authorization -> frames vs 401",
    independent of ``FilteredStream``: a bare GET carrying ONLY
    ``X-Zeitgeist-Capability`` — this module's exact pre-fix wire shape — is
    401'd by this protocol-faithful double, exactly as a real relay's
    ``AuthenticationMiddleware`` would 401 it before ``managed.py`` ever
    ran."""
    now = now_epoch()
    token = mint_capability_token(
        managed_stream_auth_double.capability_key,
        sub="probe",
        team="acme",
        deployment="d1",
        repo="spec-kitty",
        kind="presence",
        iat=now,
        exp=now + 300,
    )
    req = urllib.request.Request(
        managed_stream_auth_double.url + "/managed/stream",
        headers={"X-Zeitgeist-Capability": token},  # no Authorization header at all
        method="GET",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401
    assert managed_stream_auth_double.denied_statuses == [401]


def test_raw_request_with_authorization_but_no_capability_header_is_401_by_the_double(managed_stream_auth_double) -> None:
    """``_extract_identity``'s "missing" reason (no ``X-Zeitgeist-Capability``
    header at all) maps to 401, distinct from the "malformed"/"signature"
    reasons above which map to 403."""
    managed_stream_auth_double.set_shared_token("some-shared-secret")
    req = urllib.request.Request(
        managed_stream_auth_double.url + "/managed/stream",
        headers={"Authorization": "Bearer some-shared-secret"},  # no X-Zeitgeist-Capability at all
        method="GET",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    assert exc_info.value.code == 401
    assert managed_stream_auth_double.denied_statuses == [401]


# --- #10: `event` frames ride the same stream -------------------------------


def _event(session_ref: str = "c" * 12, attrs: dict[str, object] | None = None) -> dict[str, object]:
    event: dict[str, object] = {
        "observed_at": now_epoch(),
        "kind": "mission.status.changed",
        "actor": {"session_ref": session_ref},
    }
    if attrs is not None:
        event["attrs"] = attrs
    return {"type": "event", "event": event}


def test_watch_yields_event_frames_and_state_stays_clean(managed_stream_double) -> None:
    """Before #10 the relay's status-moment frame was dropped unread by the
    client's own type discriminator — a watch could never show the moment the
    demo path turns on. It must be delivered, and (matching the relay's own
    retention posture) it must leave no presence/focus trace behind."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    managed_stream_double.push_frame(_frame(seq=2, frame=_event(attrs={"to_lane": "for_review"})))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0), 2)
    assert [f.frame_type for f in frames if f is not None] == ["presence", "event"]  # type: ignore[attr-defined]
    event = frames[1]
    assert event is not None and getattr(event, "payload", {}).get("kind") == "mission.status.changed"

    snap = stream.check()
    assert [pr.session_ref for pr in snap.presence] == ["a" * 12]  # the broadcast touched nothing else
    assert snap.focus == ()
    assert snap.reset_count == 0


# --- #190: frame_filter, the one client-side membership rule -----------------


def test_frame_filter_drops_rejected_frames_before_delivery_and_state(managed_stream_double) -> None:
    """A rejected frame leaves no trace at all: it is never yielded and never
    reaches StreamState — "this subscription does not carry that", not a
    frame the caller must remember to ignore."""
    stream = filtered_stream.FilteredStream(
        _config(managed_stream_double.url),
        frame_filter=lambda frame: frame.frame_type != "focus",
    )
    gen = stream.watch()
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    managed_stream_double.push_frame(_frame(seq=2, frame=_focus(focus_ref="mission-z")))
    managed_stream_double.close_stream()

    frames = _drain(gen, 1)
    assert [f.frame_type for f in frames if f is not None] == ["presence"]  # type: ignore[attr-defined]

    snap = stream.check()
    assert [pr.session_ref for pr in snap.presence] == ["a" * 12]
    assert snap.focus == ()  # the filtered focus frame never mutated state


def test_frame_filter_receives_each_parsed_live_frame(managed_stream_double) -> None:
    """The predicate sees the same shape-valid object delivery would: a
    :class:`LiveFrame`, not raw wire bytes."""
    seen: list[filtered_stream.LiveFrame] = []

    def record(frame: filtered_stream.LiveFrame) -> bool:
        seen.append(frame)
        return True  # admit everything; this test only inspects what arrived

    stream = filtered_stream.FilteredStream(
        _config(managed_stream_double.url),
        frame_filter=record,
    )
    managed_stream_double.push_frame(_frame(seq=1, frame=_event(attrs={"to_lane": "doing"})))
    managed_stream_double.close_stream()
    _drain(stream.watch(idle_timeout_s=2.0), 1)

    # Exactly one predicate call, for exactly the one delivered frame —
    # asserted by content, not by a len()==n golden count.
    assert [f.frame_type for f in seen] == ["event"]
    assert isinstance(seen[0], filtered_stream.LiveFrame)
    assert seen[0].frame_type == "event"
    assert seen[0].payload["kind"] == "mission.status.changed"


def test_no_frame_filter_admits_every_shape_valid_frame(managed_stream_double) -> None:
    """``frame_filter=None`` (every subscription built before #190) keeps
    today's behaviour exactly: nothing is dropped client-side."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    gen = stream.watch()
    for seq, payload in ((1, _presence()), (2, _focus()), (3, _event())):
        managed_stream_double.push_frame(_frame(seq=seq, frame=payload))
    managed_stream_double.close_stream()

    frames = _drain(gen, 3)
    assert [f.frame_type for f in frames if f is not None] == ["presence", "focus", "event"]  # type: ignore[attr-defined]
    gen.close()


def test_frame_filter_is_keyword_only_and_defaults_to_none() -> None:
    """Every constructor call site that predates #190 keeps compiling
    unchanged — the filter is an opt-in keyword, never a positional arg a
    caller could accidentally shift into."""
    sig = inspect.signature(filtered_stream.FilteredStream.__init__)
    param = sig.parameters["frame_filter"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is None


# --- spec-kitty#4215 / zeitgeist#296: follow=1, the race-safe seeded watch ---


def _snapshot_doc(
    *,
    events: list[dict[str, object]] | None = None,
    presence: list[dict[str, object]] | None = None,
    focus: list[dict[str, object]] | None = None,
    history_basis: str = "retained",
) -> dict[str, object]:
    """One SnapshotDocument shaped like managed_snapshot.schema.json: the
    registries' unexpired entries plus the ring's retained history and the
    coverage metadata that makes an empty result honest."""
    events = events if events is not None else []
    seq = max((int(e["seq"]) for e in events), default=0)  # type: ignore[arg-type]
    return {
        "schema_version": "1.0.0",
        "epoch": "epoch-1",
        "seq": seq,
        "cursor": f"epoch-1:{seq}",
        "observed_at": now_epoch(),
        "presence": presence if presence is not None else [],
        "focus": focus if focus is not None else [],
        "events": events,
        "coverage": {
            "history_basis": history_basis,
            "retained_frames": len(events),
            "returned_frames": len(events),
            "follow": True,
        },
    }


def test_seeded_watch_uses_the_follow_route_and_yields_history_first(managed_stream_double) -> None:
    """`seed_window_s` switches the connection to `/managed/snapshot?follow=1`:
    the preface's retained history is yielded before any live frame, so a
    frame published just before the call is never lost to the future-only
    hole the plain stream leaves."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_document = _snapshot_doc(events=[_frame(seq=1, frame=_presence(session_ref="a" * 12)), _frame(seq=2, frame=_focus())])
    managed_stream_double.push_frame(_frame(seq=3, frame=_focus(focus_ref="mission-live")))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=120), 3)
    assert [f.seq for f in frames if f is not None] == [1, 2, 3]  # type: ignore[attr-defined]
    assert managed_stream_double.requested_paths
    path = managed_stream_double.requested_paths[0]
    assert path.startswith("/managed/snapshot?")
    assert "follow=1" in path
    assert "window_s=120" in path
    assert stream.seed_coverage() is not None


def test_seeded_watch_dedups_live_overlap_by_epoch_and_seq(managed_stream_double) -> None:
    """The relay's contract delivers a frame that lands in BOTH the preface
    history and the live queue twice — the consumer deduplicates on
    `(epoch, seq)`, never by a seq range."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    overlap_frame = _frame(seq=2, frame=_focus(focus_ref="mission-overlap"))
    managed_stream_double.snapshot_document = _snapshot_doc(events=[_frame(seq=1, frame=_presence()), overlap_frame])
    # The same (epoch, seq) arrives live after the preface — overlap, not news.
    managed_stream_double.push_frame(overlap_frame)
    managed_stream_double.push_frame(_frame(seq=3, frame=_focus(focus_ref="mission-new")))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 3)
    assert [f.seq for f in frames if f is not None] == [1, 2, 3]  # type: ignore[attr-defined]


def test_seeded_watch_dedups_a_precut_signal_and_never_wipes_the_seeded_state(managed_stream_double) -> None:
    """(squad pass on #4716) The follow contract delivers a pre-cut gap
    signal in BOTH the history and the live queue. The history copy is
    skipped (the coverage/gap metadata already carries that news), but its
    ``(epoch, seq)`` still joins the overlap set — otherwise the live copy
    escapes dedup, is state-applied, and wipes the just-seeded registries:
    exactly the regression ``_seed_history``'s docstring rules out, and it
    would be yielded as fresh news that predates the replay."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_document = _snapshot_doc(
        events=[
            _frame(seq=1, frame=_presence(session_ref="b" * 12)),
            _frame(seq=2, frame=_signal("gap", from_seq=2, to_seq=4)),
        ],
        presence=[
            {
                "observed_at": now_epoch() - 5,
                "ttl_s": 90,
                "expires_in_s": 85.0,
                "actor": {"session_ref": "d" * 12, "user": "alice"},
            }
        ],
    )
    # The SAME (epoch, seq) gap signal arrives live after the preface — the
    # relay's reserve-before-snapshot overlap, not news.
    managed_stream_double.push_frame(_frame(seq=2, frame=_signal("gap", from_seq=2, to_seq=4)))
    managed_stream_double.push_frame(_frame(seq=3, frame=_focus(focus_ref="mission-new")))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 2)
    assert [f.seq for f in frames if f is not None] == [1, 3]  # type: ignore[attr-defined] — the signal is never yielded
    snapshot = stream.check()
    refs = {p.session_ref for p in snapshot.presence}
    assert "d" * 12 in refs  # the registry seed survived the duplicated signal
    assert "b" * 12 not in refs  # history frames still never touch state


def test_seeded_watch_never_state_applies_an_overlap_frame(managed_stream_double) -> None:
    """(squad pass on #4716) An overlap frame is dropped WHOLE — before
    ``StreamState``, not just before the yield: a pre-cut focus frame
    regressing the seeded registries is the same defect as a pre-cut signal
    wiping them, one notch gentler."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    overlap_frame = _frame(seq=2, frame=_focus(focus_ref="mission-overlap"))
    managed_stream_double.snapshot_document = _snapshot_doc(
        events=[_frame(seq=1, frame=_presence()), overlap_frame],
        focus=[
            {
                "observed_at": now_epoch() - 5,
                "ttl_s": 90,
                "expires_in_s": 85.0,
                "actor": {"session_ref": "d" * 12},
                "focus_ref": "mission-seeded",
                "state": "active",
            }
        ],
    )
    managed_stream_double.push_frame(overlap_frame)
    managed_stream_double.push_frame(_frame(seq=3, frame=_focus(focus_ref="mission-new")))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 3)
    # seq=2 is yielded ONCE, from the history — its live copy is the one
    # dropped, so the caller never sees it twice.
    assert [f.seq for f in frames if f is not None] == [1, 2, 3]  # type: ignore[attr-defined]
    focus_refs = {view.focus_ref for view in stream.check().focus}
    assert "mission-seeded" in focus_refs  # the registry seed, not the pre-cut replay
    assert "mission-overlap" not in focus_refs  # neither history copy nor live copy touched state
    assert "mission-new" in focus_refs  # the genuinely-new live frame did


def test_seeded_watch_preface_read_honours_the_whole_call_deadline(managed_stream_double) -> None:
    """(squad pass on #4716) A follow=1 response trickling only SSE
    comment/heartbeat lines keeps every individual ``readline`` inside the
    socket timeout — the preface loop must consult the watch deadline
    itself, or ``watch(idle_timeout_s=…)`` hangs indefinitely on a relay
    that never serves the snapshot. The elapse is LOUD (a named
    ``TimeoutError``): the caller asked for a seed, and "no seed, silently"
    is the degradation this path refuses everywhere else."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    # snapshot_body=b"" serves follow=1 as SSE whose first data line is
    # empty — a preface that never arrives, without a 404.
    managed_stream_double.snapshot_body = b""
    stop = threading.Event()

    def _trickle() -> None:
        # Heartbeats faster than the socket timeout: without the deadline
        # check, every readline succeeds and the loop never unblocks.
        while not stop.is_set():
            managed_stream_double.push_raw(b": ping\n\n")
            time.sleep(0.05)

    trickle = threading.Thread(target=_trickle, daemon=True)
    trickle.start()
    try:
        with pytest.raises(TimeoutError, match="follow preface"):
            _drain(stream.watch(idle_timeout_s=0.5, seed_window_s=60), 1, timeout_s=3.0)
    finally:
        stop.set()
        trickle.join(timeout=1)
        managed_stream_double.close_stream()


def test_seeded_watch_state_comes_from_the_preface_not_the_history(managed_stream_double) -> None:
    """The preface seeds state from the registries AT THE CUT — strictly
    newer than any history frame — so a pre-cut presence frame in the
    history is delivered but never allowed to regress the seeded view."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_document = _snapshot_doc(
        events=[_frame(seq=1, frame=_presence(session_ref="b" * 12))],
        presence=[
            {
                "observed_at": now_epoch() - 5,
                "ttl_s": 90,
                "expires_in_s": 85.0,
                "actor": {"session_ref": "d" * 12, "user": "alice"},
            }
        ],
    )
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 1)
    assert frames[0].payload["actor"]["session_ref"] == "b" * 12  # type: ignore[index]
    snapshot = stream.check()
    refs = {p.session_ref for p in snapshot.presence}
    assert "d" * 12 in refs  # the registry seed
    assert "b" * 12 not in refs  # the history frame never touched state


def test_seeded_watch_reports_the_preface_coverage(managed_stream_double) -> None:
    """`seed_coverage()` carries the preface's coverage metadata so a
    truncated backfill is visible to the caller, never silent."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_document = _snapshot_doc(events=[_frame(seq=1, frame=_presence())], history_basis="retained")
    managed_stream_double.close_stream()

    _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 1)
    coverage = stream.seed_coverage()
    assert coverage is not None
    assert coverage["history_basis"] == "retained"
    assert coverage["follow"] is True


def test_seeded_watch_raises_on_an_unusable_preface(managed_stream_double) -> None:
    """A preface that is not a usable SnapshotDocument is a hard ValueError —
    never a silently-skipped seed that leaves the caller believing it
    replayed history."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_body = b"not-a-snapshot"
    managed_stream_double.close_stream()

    with pytest.raises(ValueError):
        _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 1)


def test_seeded_watch_propagates_a_relay_without_the_snapshot_route(managed_stream_double) -> None:
    """A relay that serves no snapshot (older build / self_hosted profile)
    answers 404; the caller asked for a seed and gets an honest fault, never
    a silent fall-back to a future-only stream."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.snapshot_status = 404
    managed_stream_double.close_stream()

    with pytest.raises(urllib.error.HTTPError):
        _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=60), 1)


def test_seed_window_zero_is_future_only_and_negative_is_refused() -> None:
    """0 keeps today's `/managed/stream` behaviour; a negative or non-finite
    window is refused at the door rather than sent to the relay."""
    assert filtered_stream._validated_seed_window(None) is None
    assert filtered_stream._validated_seed_window(0.0) is None
    assert filtered_stream._validated_seed_window(90.0) == 90.0
    with pytest.raises(ValueError):
        filtered_stream._validated_seed_window(-1.0)
    with pytest.raises(ValueError):
        filtered_stream._validated_seed_window(float("nan"))


def test_watch_url_formats_every_representable_window_as_a_plain_decimal() -> None:
    """(squad pass on #4716) The relay's `_WINDOW_S_RE` grammar
    (`[0-9]{1,19}(?:\\.[0-9]{1,19})?`) has no exponent form: for
    `0 < seed < 1e-4`, `repr` emits `'1e-05'` and the relay answers 400.
    The sub-millisecond range is formatted fixed-decimal instead — and a
    window too small to express at microsecond granularity is refused
    loudly, never silently rounded to a future-only `window_s=0`."""
    stream = filtered_stream.FilteredStream(_config("http://relay.example"))

    url = stream._watch_url(1e-05)
    assert "window_s=0.00001" in url
    assert "e-05" not in url

    # The ranges every client already uses are byte-for-byte unchanged.
    assert "window_s=120" in stream._watch_url(120.0)
    assert "window_s=1.5" in stream._watch_url(1.5)

    with pytest.raises(ValueError, match="granularity"):
        stream._watch_url(5e-07)


def test_zero_seed_keeps_the_plain_stream_route(managed_stream_double) -> None:
    """The default call shape — no `seed_window_s` — is byte-for-byte
    today's future-only behaviour: `/managed/stream`, no preface read."""
    stream = filtered_stream.FilteredStream(_config(managed_stream_double.url))
    managed_stream_double.push_frame(_frame(seq=1, frame=_presence()))
    managed_stream_double.close_stream()

    frames = _drain(stream.watch(idle_timeout_s=2.0, seed_window_s=0.0), 1)
    assert [f.seq for f in frames if f is not None] == [1]  # type: ignore[attr-defined]
    assert managed_stream_double.requested_paths[0].startswith("/managed/stream?")
    assert stream.seed_coverage() is None
