"""The Zeitgeist moment handler at the status/adapters seam (#8).

Pins the three contracts the issue names:

1. **Handler registered → one moment + its liveness frames.** Registering the
   moment handlers puts exactly one handler in each fan-out slot, and one
   status moment produces one ``event.publish`` offer carrying the volatile
   attrs plus (#186) the presence/focus frames that give the relay's live
   panel its liveness state.
2. **No credentials → no network call.** An unresolvable credential ends the
   broadcast before any client exists, let alone a socket.
3. **Budget exceeded → dropped and logged.** A ``dropped_budget`` outcome is
   logged once and never retried, queued, or raised.

Plus the drop paths around them: unencodable payloads cost zero attempts, and
non-volatile lifecycle types are skipped outright. All tests drive the seam
through the same boundaries production does — the ``adapters.fire_*`` functions,
E3's ``resolve_credentials``, and the typed ``ZeitgeistClient`` — with only the
network itself faked (and checkout identity pinned so no test ever shells out
to git).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest

from kernel.clock import UTC, datetime as _dt

from specify_cli.decisions.emit import emit_decision_opened, emit_decision_resolved
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.status import adapters
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.lifecycle_events import emit_mission_created_local
from specify_cli.status.models import Lane, TransitionRequest
from specify_cli.status import zeitgeist_bridge as bridge
from specify_cli.status.wp_status_metadata import WPStatusChangeMetadata
from specify_cli.zeitgeist_client import resolution as resolution_module
from specify_cli.zeitgeist_client import transport as transport_module
from specify_cli.zeitgeist_client.credentials import StoredCredential
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_RESOLVED
from tests.status.conftest import seed_wp_to_planned as _seed_planned

pytestmark = pytest.mark.fast

_EVENT_ID = "01JME2E2E2E2E2E2E2E2E2E2E2"


@pytest.fixture(autouse=True)
def _zeitgeist_only_registry() -> None:
    """Run every test with the Zeitgeist handlers as the sole wiring.

    Isolates these tests from the sync package's own fan-out handlers and from
    whatever a previous test left registered; restored afterwards so the
    next test sees the production wiring again.
    """
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()
    yield
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()


def _credential() -> StoredCredential:
    return StoredCredential(
        relay_url="http://127.0.0.1:9",
        token="relay-token",
        token_issued_at="2026-08-25T00:00:00+00:00",
        token_kind="presence",
        session_ref="presence-lease",
        capability_credential="capability-jwt",
    )


@dataclass
class OfferRecorder:
    """Stands in for ``ZeitgeistClient``, recording offers instead of POSTing.

    ``install`` also pins ``ClientConfig.for_repository`` to a fixed identity,
    so the #186 liveness frames exercise the same code path as production
    (a config built from "git truth") without any test ever shelling out to
    git or depending on the host checkout's branch.
    """

    outcome: str = "sent"
    offers: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    configs: list[Any] = field(default_factory=list)
    clients_built: int = 0

    def summaries(self) -> list[tuple[str, str | None]]:
        """(op, event-kind) per offer — the whole "the right frames" contract.

        Only the moment and presence frames carry a ``kind``; focus args name
        their ref instead, so they report ``None``.
        """
        return [(op, args.get("kind")) for op, args in self.offers]

    def moment_offers(self) -> list[tuple[str, dict[str, Any]]]:
        return [(op, args) for op, args in self.offers if op == "event.publish"]

    def install(self, monkeypatch: pytest.MonkeyPatch) -> OfferRecorder:
        recorder = self

        class FakeZeitgeistClient:
            def __init__(self, config: Any) -> None:
                recorder.clients_built += 1
                recorder.configs.append(config)
                self._config = config

            def offer(self, op: str, args: Any) -> Any:
                recorder.offers.append((op, dict(args)))
                return transport_module.OfferResult(
                    outcome=transport_module.OfferOutcome(recorder.outcome),
                    request_id="req-1",
                    elapsed_s=0.01,
                )

            def presence(self, activity: str, path: str | None = None) -> Any:
                config = self._config
                args: dict[str, Any] = {"session_id": config.session_id}
                if config.repo:
                    args["repo"] = config.repo
                if config.branch:
                    args["branch"] = config.branch
                args["kind"] = activity
                if path is not None:
                    args["path"] = path
                return self.offer("presence.publish", args)

            def focus_start(self, mission_slug: str, wp_id: str | None = None) -> Any:
                config = self._config
                focus_ref = mission_slug if wp_id is None else f"{mission_slug}.{wp_id}"
                return self.offer(
                    "focus.start",
                    {
                        "session_id": config.session_id,
                        **({"repo": config.repo} if config.repo else {}),
                        **({"branch": config.branch} if config.branch else {}),
                        "focus_ref": focus_ref,
                        "ttl_s": transport_module.FOCUS_TTL_S,
                    },
                )

        def fake_for_repository(cls: type, cwd: str, **kwargs: Any) -> Any:
            return transport_module.ClientConfig(
                relay_url=kwargs["relay_url"],
                token=kwargs["token"],
                harness=kwargs["harness"],
                session_id=kwargs["session_id"],
                agent_id=kwargs.get("agent_id"),
                repo="demo-repo",
                branch="main",
                capability_credential=kwargs.get("capability_credential"),
            )

        monkeypatch.setattr(transport_module, "ZeitgeistClient", FakeZeitgeistClient)
        monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(fake_for_repository))
        return recorder


@pytest.fixture
def resolved_credential(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Resolve every credential request to a stored relay credential."""
    seen: list[Path] = []

    def fake_resolve(cwd: Path, **kwargs: Any) -> StoredCredential:
        seen.append(cwd)
        return _credential()

    monkeypatch.setattr(resolution_module, "resolve_credentials", fake_resolve)
    return seen


@pytest.fixture(autouse=True)
def no_focus_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default every test to "no focus-kind lease available".

    Focus emission is opt-in per test via :func:`focus_capability`: the
    default here keeps each test's expected frame sequence to moment +
    presence and guarantees no test ever touches the real resolution path
    (which would read the ambient credential store).
    """
    monkeypatch.setattr(resolution_module, "resolve_focus_lease", lambda *a, **k: None)


@pytest.fixture
def focus_capability(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Resolve every focus-capability request to a minted ``focus`` JWT,
    recording the cwd each request came from."""
    seen: list[str] = []

    def fake_resolve(cwd: Path, **kwargs: Any) -> resolution_module.FocusLease | None:
        seen.append(str(cwd))
        return resolution_module.FocusLease("focus-jwt", "focus-lease")

    monkeypatch.setattr(resolution_module, "resolve_focus_lease", fake_resolve)
    return seen


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_ensure_registers_exactly_one_zeitgeist_handler_per_slot() -> None:
    adapters.reset_handlers()
    try:
        adapters.ensure_zeitgeist_moment_handlers()
        adapters.ensure_zeitgeist_moment_handlers()  # idempotent
        assert [h.__qualname__ for h in adapters._saas_handlers] == ["saas_moment_handler"]
        assert [h.__qualname__ for h in adapters._lifecycle_saas_handlers] == ["lifecycle_moment_handler"]
        assert [h.__qualname__ for h in adapters._resolved_binding_handlers] == ["resolved_binding_moment_handler"]
    finally:
        adapters.ensure_zeitgeist_moment_handlers()


def test_session_id_matches_the_relay_schema_pattern() -> None:
    # managed_control.schema.json EventArgs.session_id:
    # [A-Za-z0-9][A-Za-z0-9._:-]{0,127}
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", _credential().session_ref)


# ---------------------------------------------------------------------------
# The wire contract: what the real client would put on the socket
# ---------------------------------------------------------------------------

# Vendored verbatim from EXPERIMENTAL-zeitgeist's managed_control.schema.json
# at commit 644628c2f00a4fd35612a6001b00fe5f758b1045 (#312: a hand-rolled
# mirror of this file can drift from the relay's real contract without the
# test noticing — see the class of bug in zeitgeist#83). The digest below
# forces a deliberate re-check whenever the vendored copy is refreshed: if
# someone edits or re-vendors the fixture without updating
# _ZEITGEIST_SCHEMA_DIGEST, this test fails loudly instead of silently
# validating against a stale or hand-edited document.
_ZEITGEIST_SCHEMA_FIXTURE = Path(__file__).parent / "fixtures" / "zeitgeist" / "managed_control.schema.json"
_ZEITGEIST_SCHEMA_DIGEST = "5c5cb2e5b4d0ad1a16b7d91aa654f045b47b1b4293a672bc3d9a6855b656b612"


def _load_control_envelope_schema() -> dict[str, Any]:
    raw = _ZEITGEIST_SCHEMA_FIXTURE.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()  # noqa: TID251 -- file-integrity check, not a charter hash
    assert digest == _ZEITGEIST_SCHEMA_DIGEST, (
        f"{_ZEITGEIST_SCHEMA_FIXTURE} does not match the pinned digest "
        f"(got {digest}) -- re-vendor deliberately from a pinned "
        "EXPERIMENTAL-zeitgeist commit and update _ZEITGEIST_SCHEMA_DIGEST"
    )
    return cast(dict[str, Any], json.loads(raw))


def _assert_event_args(args: dict[str, Any]) -> None:
    """Validate *args* against the REAL ``EventArgs`` contract, loaded from the
    vendored relay schema -- not a hand-rolled mirror of it (#312)."""
    event_args_schema = _load_control_envelope_schema()["$defs"]["EventArgs"]
    jsonschema.validate(instance=args, schema=event_args_schema, cls=jsonschema.Draft202012Validator)

    # `maxUtf8Bytes` is a zeitgeist-specific bound (`capabilities._check_bounds`)
    # that the standard JSON Schema vocabulary does not know how to enforce, so
    # jsonschema.validate() above silently skips it. Apply it here, reading the
    # bound itself from the vendored schema rather than restating the number.
    ref_bound = event_args_schema["properties"]["ref"].get("maxUtf8Bytes")
    if ref_bound is not None and "ref" in args:
        assert len(args["ref"].encode()) <= ref_bound
    attrs_value_bound = event_args_schema["properties"]["attrs"]["additionalProperties"].get("maxUtf8Bytes")
    if attrs_value_bound is not None:
        for key, value in args["attrs"].items():
            assert len(value.encode()) <= attrs_value_bound, key


def _pin_checkout_identity(monkeypatch: pytest.MonkeyPatch, *, capability: str) -> None:
    """Pin ``for_repository`` so the real-client wire test never shells to git."""

    def fake_for_repository(cls: type, cwd: str, **kwargs: Any) -> Any:
        return transport_module.ClientConfig(
            relay_url=kwargs["relay_url"],
            token=kwargs["token"],
            harness=kwargs["harness"],
            session_id=kwargs["session_id"],
            agent_id=kwargs.get("agent_id"),
            repo="demo-repo",
            branch="main",
            capability_credential=capability,
        )

    monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(fake_for_repository))


def test_wire_envelopes_satisfy_the_relay_schema(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    focus_capability: list[str],
) -> None:
    """Drive the REAL ZeitgeistClient with a stubbed HTTP layer and validate every
    outgoing envelope — moment, presence, focus — against the relay's own
    schema contracts.

    The faked-client tests above prove orchestration; this one proves the wire.
    It fails if offer_args ever omits session_id again (the relay answers 422 to
    an envelope missing it — every frame silently rejected).
    """
    captured: list[Any] = []

    class _FakeResponse:
        status = 202

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_open_bounded(req: Any, timeout: float) -> _FakeResponse:
        captured.append(req)
        return _FakeResponse()

    monkeypatch.setattr(transport_module.budget, "open_bounded", fake_open_bounded)
    _pin_checkout_identity(monkeypatch, capability="capability-jwt")

    _fire_transition()

    # One transition → three envelopes: the moment first, then liveness.
    assert [json.loads(req.data.decode())["op"] for req in captured] == [
        "event.publish",
        "presence.publish",
        "focus.start",
    ]

    moment_req = captured[0]
    body = json.loads(moment_req.data.decode())
    assert body["schema_version"] == "1.0.0"
    _assert_event_args(body["args"])
    args = body["args"]
    assert args["kind"] == "WPStatusChanged"
    assert args["ref"] == "demo-mission"
    assert args["attrs"]["wp_id"] == "WP01"
    assert moment_req.get_header("Authorization") == "Bearer relay-token"
    assert moment_req.get_header("X-zeitgeist-capability") == "capability-jwt"

    # PresencePublish (managed_presence.schema.json): session_id required,
    # additionalProperties false, kind in its closed enum. The presence frame
    # rides the stored presence-kind credential, same as the moment.
    presence_args = json.loads(captured[1].data.decode())["args"]
    assert set(presence_args) <= {"session_id", "repo", "branch", "kind", "path", "host", "harness", "agent_id", "ts"}
    assert presence_args["kind"] == "command"
    assert presence_args["repo"] == "demo-repo"
    assert presence_args["branch"] == "main"

    # FocusArgs (managed_control.schema.json): required [session_id, repo,
    # focus_ref, ttl_s], ident-grammar ref, ttl within the ≤90s bound — and
    # the FOCUS lease on the capability gate, not the presence one.
    focus_body = json.loads(captured[2].data.decode())
    focus_args = focus_body["args"]
    assert set(focus_args) == {"session_id", "repo", "branch", "focus_ref", "ttl_s"}
    assert focus_args["focus_ref"] == "demo-mission.WP01"
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}", focus_args["focus_ref"])
    assert focus_args["ttl_s"] == 90
    assert captured[2].get_header("X-zeitgeist-capability") == "focus-jwt"


@pytest.mark.parametrize(
    "gate_var",
    [
        "SPEC_KITTY_NO_MOMENT_HANDLERS",
        "SPEC_KITTY_SYNC_DISABLE",
        "SPEC_KITTY_SYNC_MINIMAL_IMPORT",
    ],
)
def test_import_tail_honours_the_moment_handler_gate(gate_var: str) -> None:
    """The moment-handler import gate (#3980) means 'register no transport at
    import': ``SPEC_KITTY_NO_MOMENT_HANDLERS`` is its own name, the
    ``SPEC_KITTY_SYNC_DISABLE`` kill switch folds in, and the deprecated
    ``SPEC_KITTY_SYNC_MINIMAL_IMPORT`` alias is still honored."""
    script = "from specify_cli.status import adapters\nprint(len([h for h in adapters._saas_handlers if h.__module__.endswith('zeitgeist_bridge')]))\n"
    gated_env = dict(os.environ)
    gated_env[gate_var] = "1"
    ungated_env = {k: v for k, v in os.environ.items() if k not in ("SPEC_KITTY_NO_MOMENT_HANDLERS", "SPEC_KITTY_SYNC_DISABLE", "SPEC_KITTY_SYNC_MINIMAL_IMPORT")}

    gated = subprocess.run([sys.executable, "-c", script], env=gated_env, text=True, capture_output=True, timeout=120)
    ungated = subprocess.run([sys.executable, "-c", script], env=ungated_env, text=True, capture_output=True, timeout=120)

    assert gated.returncode == 0, gated.stderr
    assert gated.stdout.strip() == "0"
    assert ungated.returncode == 0, ungated.stderr
    assert ungated.stdout.strip() == "1"


def test_review_only_done_transition_still_broadcasts(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """A done moment whose evidence carries no repos must not die in payload
    validation: local journals treat repos as optional, the canonical model
    requires one — normalised exactly as the sync emitter always did."""
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(
        to_lane="done",
        metadata=_transition_metadata(evidence={"review": {"reviewer": "rob", "verdict": "approved", "reference": "pr-1"}}),
    )

    # The review-only done transition still broadcasts its moment (plus the
    # #186 presence frame; focus stays off via the autouse fixture).
    assert [op for op, _args in recorder.moment_offers()] == ["event.publish"]
    _op, args = recorder.offers[0]
    assert args["kind"] == "WPStatusChanged"
    assert args["attrs"]["to_lane"] == "done"
    assert "evidence" not in args["attrs"]  # unbroadcast, whatever its shape


# ---------------------------------------------------------------------------
# Slot 1: WP lane transitions -> WPStatusChanged
# ---------------------------------------------------------------------------


def _transition_metadata(**overrides: Any) -> WPStatusChangeMetadata:
    fields: dict[str, Any] = {
        "causation_id": _EVENT_ID,
        "force": False,
        "execution_mode": "worktree",
        "occurred_at": "2026-08-25T09:00:00+00:00",
    }
    fields.update(overrides)
    return WPStatusChangeMetadata(**fields)


def _fire_transition(**overrides: Any) -> None:
    kwargs: dict[str, Any] = {
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "claimed",
        "actor": "robert",
        "mission_slug": "demo-mission",
        "mission_id": None,
        "metadata": _transition_metadata(),
        "ensure_daemon": False,
    }
    kwargs.update(overrides)
    adapters.fire_saas_fanout(**kwargs)


def test_transition_broadcasts_one_moment_plus_its_liveness_frames(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition()

    # One moment, then its liveness frames (#186): presence always, focus for
    # a WP-carrying broadcast — but only when the focus lease resolves (the
    # autouse fixture keeps it off here).
    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    assert args["ref"] == "demo-mission"
    attrs = args["attrs"]
    assert attrs["event_id"] == _EVENT_ID
    assert attrs["occurred_at"] == "2026-08-25T09:00:00+00:00"
    assert attrs["mission_slug"] == "demo-mission"
    assert attrs["wp_id"] == "WP01"
    assert attrs["from_lane"] == "planned"
    assert attrs["to_lane"] == "claimed"
    assert attrs["actor"] == "robert"
    # HIC amendment 2026-08-26 (planning decisions/HIC-EPHEMERAL-TEAM-STATUS):
    # ``force`` is an enumeration about the transition, so it rides; the
    # free-text ``reason`` stays local (UNBROADCAST_FIELDS). Identifiers and
    # transition facts ride; prose never does.
    assert attrs["force"] == "false"
    assert "reason" not in attrs


def test_one_broadcast_shares_one_git_deadline_across_credentials_presence_and_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Priivacy-ai/spec-kitty#203: credential resolution, presence identity
    (via ``ClientConfig.for_repository``), and the focus capability lookup
    each used to open their OWN fresh ``repo_identity.Deadline`` — three
    independent 2.0s budgets stacking under the fan-out seam's 10s bound.
    One status-transition broadcast must thread exactly ONE ``Deadline``
    through all three calls."""
    seen_deadlines: list[Any] = []

    def fake_resolve_credentials(cwd: Path, **kwargs: Any) -> StoredCredential:
        seen_deadlines.append(kwargs.get("deadline"))
        return _credential()

    def fake_for_repository(cls: type, cwd: str, **kwargs: Any) -> Any:
        seen_deadlines.append(kwargs.get("deadline"))
        return transport_module.ClientConfig(
            relay_url=kwargs["relay_url"],
            token=kwargs["token"],
            harness=kwargs["harness"],
            session_id=kwargs["session_id"],
            agent_id=kwargs.get("agent_id"),
            repo="demo-repo",
            branch="main",
            capability_credential=kwargs.get("capability_credential"),
        )

    def fake_resolve_focus_capability(cwd: Path, **kwargs: Any) -> resolution_module.FocusLease | None:
        seen_deadlines.append(kwargs.get("deadline"))
        return resolution_module.FocusLease("focus-jwt", "focus-lease")

    class _FakeZeitgeistClient:
        def __init__(self, config: Any) -> None:
            self._config = config

        def offer(self, op: str, args: Any) -> Any:
            return transport_module.OfferResult(outcome=transport_module.OfferOutcome("sent"), request_id="req-1", elapsed_s=0.0)

        def presence(self, activity: str, path: str | None = None) -> Any:
            return self.offer("presence.publish", {})

        def focus_start(self, mission_slug: str, wp_id: str | None = None) -> Any:
            return self.offer("focus.start", {})

    monkeypatch.setattr(resolution_module, "resolve_credentials", fake_resolve_credentials)
    monkeypatch.setattr(resolution_module, "resolve_focus_lease", fake_resolve_focus_capability)
    monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(fake_for_repository))
    monkeypatch.setattr(transport_module, "ZeitgeistClient", _FakeZeitgeistClient)

    _fire_transition()

    assert len(seen_deadlines) == 3, "expected one deadline observed at each of the three call sites"
    assert all(d is not None for d in seen_deadlines), "every call must receive a deadline, not fall back to None"
    assert seen_deadlines[0] is seen_deadlines[1] is seen_deadlines[2], (
        "resolve_credentials, for_repository, and resolve_focus_capability each got their own Deadline instead of sharing the one this broadcast opened"
    )


def test_forced_rollback_transition_broadcasts_force_true(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """A forced backward transition carries ``force="true"`` on the wire.

    The amendment moves ``force`` onto the relay with every other transition
    fact — only its reason text stays local. Re-introducing a bridge-side
    strip of ``force`` fails this test: the codec's attrs go out unfiltered.
    """
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(
        from_lane="approved",
        to_lane="planned",
        metadata=_transition_metadata(force=True, reason="found a defect after approval"),
    )

    _op, args = recorder.moment_offers()[0]
    assert args["kind"] == "WPStatusChanged"
    assert args["attrs"]["force"] == "true"
    assert "reason" not in args["attrs"]


def test_reason_and_evidence_never_reach_the_wire(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """The rule that survives the amendment: prose and evidence stay local.

    Both fields are dropped by spec-kitty-events' ``UNBROADCAST_FIELDS``, which
    is now the single owner of the wire vocabulary — this bridge adds no
    filtering of its own, so removing either field there turns this red
    immediately (the keys would reappear in the offered attrs).
    """
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(metadata=_transition_metadata(force=True, reason="found a defect after approval"))
    _fire_transition(
        to_lane="done",
        metadata=_transition_metadata(
            force=False,
            reason="closing out",
            evidence={
                "repos": [{"repo": "demo", "branch": "main", "commit": "abc1234"}],
                "review": {"reviewer": "rob", "verdict": "approved", "reference": "pr-1"},
            },
        ),
    )

    moments = recorder.moment_offers()
    assert [op for op, _args in moments] == ["event.publish", "event.publish"]
    for _op, args in moments:
        leaked = sorted(key for key in args["attrs"] if key.split(".")[0] in {"reason", "evidence"})
        assert leaked == []


def test_structured_actor_rides_as_its_single_label(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(actor={"role": "implementer", "profile": "rob", "tool": "claude", "model": None})

    _op, args = recorder.offers[0]
    assert args["attrs"]["actor"] == "rob"


def test_client_config_carries_the_stored_relay_credential(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition()

    config = recorder.configs[0]
    assert config.relay_url == "http://127.0.0.1:9"
    assert config.token == "relay-token"
    assert config.capability_credential == "capability-jwt"


def test_first_non_printable_attr_finds_the_offending_key_and_codepoint() -> None:
    assert bridge._first_non_printable_attr({"summary": "Which auth? \x1b[31mRED"}) == (
        "summary",
        ["U+001B"],
    )


def test_first_non_printable_attr_is_none_for_ordinary_prose() -> None:
    assert bridge._first_non_printable_attr({"summary": "Which auth? session, oauth2"}) is None


def test_unencodable_payload_drops_before_any_attempt(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path], caplog: pytest.LogCaptureFixture) -> None:
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(wp_id="WP01" + "x" * 300)  # over the 240-byte attr bound

    assert recorder.offers == []
    assert recorder.clients_built == 0
    assert resolved_credential == []  # codec failure costs zero lookups too
    assert "not broadcast" in caplog.text


def test_malformed_payload_is_logged_and_dropped(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path], caplog: pytest.LogCaptureFixture) -> None:
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(actor=None)  # StatusTransitionPayload.actor is required

    assert recorder.offers == []
    assert "WPStatusChanged not broadcast" in caplog.text


def test_handler_never_raises_even_when_resolution_explodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    OfferRecorder().install(monkeypatch)

    def exploding_resolve(cwd: Path, **kwargs: Any) -> StoredCredential:
        raise RuntimeError("boom")

    monkeypatch.setattr(resolution_module, "resolve_credentials", exploding_resolve)

    _fire_transition()  # must not raise into the fan-out


# ---------------------------------------------------------------------------
# No credentials / not-a-moment -> nothing leaves the process
# ---------------------------------------------------------------------------


def test_no_credentials_means_no_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = OfferRecorder().install(monkeypatch)
    monkeypatch.setattr(resolution_module, "resolve_credentials", lambda *a, **k: None)

    _fire_transition()

    assert recorder.clients_built == 0
    assert recorder.offers == []


def test_non_volatile_lifecycle_types_broadcast_nothing(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path], caplog: pytest.LogCaptureFixture) -> None:
    recorder = OfferRecorder().install(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=bridge.__name__)

    adapters.fire_lifecycle_saas_fanout(
        envelope={"event_type": "WPCreated", "payload": {"mission_slug": "demo-mission", "wp_id": "WP01"}},
        log_path=None,
    )

    assert recorder.offers == []
    assert resolved_credential == []  # not even a credential lookup
    # Pin the early return itself, not a side effect it shares with validation
    # failures and swallowed exceptions: the guard's own debug line is the only
    # observable that distinguishes it (mutation-check: deleting the
    # `event_type not in VOLATILE_EVENT_TYPES` return turns this red via KeyError).
    assert "not a volatile-family moment" in caplog.text


def test_resolved_binding_slot_is_wired_but_broadcasts_nothing_yet(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    recorder = OfferRecorder().install(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=bridge.__name__)

    adapters.fire_resolved_binding_fanout(
        wp_id="WP01",
        mission_slug="demo-mission",
        actor="robert",
        causation_id=_EVENT_ID,
        occurred_at="2026-08-25T09:00:00+00:00",
        role="implementer",
        agent_profile=None,
        agent_profile_version=None,
        model="claude",
        provider=None,
    )

    assert recorder.offers == []
    assert "not a volatile-family moment" in caplog.text


# ---------------------------------------------------------------------------
# Liveness frames (#186): presence beside every moment, focus beside a WP
# ---------------------------------------------------------------------------


def test_focus_frame_names_mission_dot_wp_when_the_lease_resolves(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    focus_capability: list[str],
) -> None:
    """E2E-MVP 1.2: a WP transition puts ``<mission>.<WP>`` on the live panel.

    The focus frame is a separate offer on a separate lease: zeitgeist grants
    the focus.* ops only to the ``focus`` credential kind, so its client
    config must carry the focus JWT on the capability gate while the moment
    and presence frames ride the stored presence-kind one.
    """
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition()

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
        ("focus.start", None),
    ]
    _op, args = recorder.offers[2]
    assert args["focus_ref"] == "demo-mission.WP01"
    assert args["ttl_s"] == transport_module.FOCUS_TTL_S
    assert focus_capability == [str(Path.cwd())]
    # Lease split across the two capability gates.
    assert [config.capability_credential for config in recorder.configs] == [
        "capability-jwt",
        "capability-jwt",
        "focus-jwt",
    ]


def test_presence_rides_the_stored_presence_kind_lease(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
) -> None:
    """``presence.publish`` needs no second mint: the presence kind grants it
    alongside ``event.publish``, so the presence frame reuses the stored
    credential exactly as the moment did."""
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition()

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.offers[1]
    assert args["kind"] == "command"
    assert args["repo"] == "demo-repo"
    assert args["branch"] == "main"
    assert recorder.configs[0].capability_credential == recorder.configs[1].capability_credential == "capability-jwt"


def test_unresolvable_focus_lease_skips_only_focus(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing/denied focus mint costs the focus frame alone — never the
    moment, never presence, and never a raised error into the fan-out."""
    recorder = OfferRecorder().install(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=bridge.__name__)

    _fire_transition()

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    assert "no focus-kind capability" in caplog.text


def test_overlong_focus_ref_is_filtered_before_any_attempt(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """managed_control.schema.json caps focus_ref at 64 ident chars; a longer
    ``<mission>.<WP>`` is a guaranteed 422, so it is filtered locally — the
    resolver is never even asked, let alone the relay."""
    recorder = OfferRecorder().install(monkeypatch)

    def must_not_be_asked(cwd: Any, **kwargs: Any) -> str | None:
        raise AssertionError("focus resolver consulted for a ref that cannot go out")

    monkeypatch.setattr(resolution_module, "resolve_focus_lease", must_not_be_asked)
    caplog.set_level(logging.DEBUG, logger=bridge.__name__)

    _fire_transition(mission_slug="m" * 70)

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    assert "does not fit the relay's focus_ref grammar" in caplog.text


def test_unidentifiable_checkout_drops_liveness_but_not_the_moment(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
) -> None:
    """Presence/focus are bound to git truth (Z6-C); where git cannot answer,
    liveness goes silent while the moment still goes out."""
    from specify_cli.zeitgeist_client import repo_identity

    def raising_for_repository(cls: type, cwd: str, **kwargs: Any) -> Any:
        raise repo_identity.RepoIdentityError("no canonical identity")

    recorder = OfferRecorder().install(monkeypatch)
    monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(raising_for_repository))

    _fire_transition()

    assert recorder.moment_offers() != []
    assert [op for op, _args in recorder.offers if op != "event.publish"] == []


def test_liveness_failure_never_raises_into_the_fanout(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fan-out slot stays non-raising whatever liveness does — canonical
    persistence and the moment broadcast are unaffected."""

    def exploding_identity(cls: type, cwd: str, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    recorder = OfferRecorder().install(monkeypatch)
    monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(exploding_identity))
    caplog.set_level(logging.WARNING, logger=bridge.__name__)

    _fire_transition()  # must not raise

    assert recorder.moment_offers() != []
    assert "presence/focus refresh failed" in caplog.text


def test_mission_creation_publishes_no_focus_even_with_a_lease(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
    focus_capability: list[str],
) -> None:
    """Mission creation refreshes presence only: there is no WP to name, so
    no focus frame exists even when a focus lease is in hand."""
    recorder = OfferRecorder().install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=_EVENT_ID,
        mission_number=1,
        mission_type="software-dev",
        target_branch="main",
        wp_count=2,
        friendly_name="Demo",
        purpose_tldr="tldr",
        purpose_context="context",
    )

    assert recorder.summaries() == [
        ("event.publish", "MissionCreated"),
        ("presence.publish", "command"),
    ]
    assert focus_capability == []  # never consulted without a WP


# ---------------------------------------------------------------------------
# Budget / rejection outcomes: one attempt per moment, logged, no retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome",
    ["dropped_budget", "rejected", "dropped_unreachable"],
)
def test_non_sent_outcome_is_dropped_and_logged_once(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
    outcome: str,
) -> None:
    recorder = OfferRecorder(outcome=outcome).install(monkeypatch)
    caplog.set_level(logging.WARNING, logger=bridge.__name__)

    _fire_transition()
    _fire_transition()

    # One attempt per frame, neither retried nor queued; every drop names the
    # outcome and the no-retry contract, content-exact.
    assert (
        recorder.summaries()
        == [
            ("event.publish", "WPStatusChanged"),
            ("presence.publish", "command"),
        ]
        * 2
    )
    moment_drop = f"Zeitgeist moment WPStatusChanged dropped ({outcome}) after 10 ms; no retry by design"
    presence_drop = f"Zeitgeist presence dropped ({outcome}) after 10 ms; no retry by design"
    assert [m for m in caplog.messages if "dropped" in m] == [moment_drop, presence_drop] * 2


def test_budget_drop_does_not_block_canonical_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The fan-out contract: a hanging/expired relay never touches local truth."""
    recorder = OfferRecorder(outcome="dropped_budget").install(monkeypatch)
    monkeypatch.setattr(resolution_module, "resolve_credentials", lambda *a, **k: _credential())
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    _seed_planned(feature_dir, "WP01")

    event = emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="demo-mission",
            wp_id="WP01",
            to_lane="claimed",
            actor="robert",
        )
    )

    assert event.to_lane is Lane.CLAIMED
    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]


# ---------------------------------------------------------------------------
# Credential-resolution cwd selection
# ---------------------------------------------------------------------------


def test_lifecycle_slot_resolves_credentials_from_the_log_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resolved_credential: list[Path]) -> None:
    OfferRecorder().install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    adapters.fire_lifecycle_saas_fanout(
        envelope={
            "event_type": "MissionClosed",
            "payload": {"mission_slug": "demo-mission", "mission_number": 1, "mission_type": "software-dev"},
        },
        log_path=feature_dir / "status.events.jsonl",
    )

    assert resolved_credential == [feature_dir]


def test_transition_slot_resolves_credentials_from_repo_root_when_given(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resolved_credential: list[Path]) -> None:
    """Mirrors the lifecycle slot: a caller-supplied checkout root wins over cwd (#125)."""
    OfferRecorder().install(monkeypatch)
    repo_root = tmp_path / "some-other-checkout"

    _fire_transition(repo_root=repo_root)

    assert resolved_credential == [repo_root]


def test_transition_slot_falls_back_to_cwd_when_no_repo_root_given(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """A caller that omits ``repo_root`` (older wiring, direct calls) keeps the old behaviour."""
    OfferRecorder().install(monkeypatch)

    _fire_transition()

    assert resolved_credential == [Path.cwd()]


# ---------------------------------------------------------------------------
# End-to-end through the producers (real emit path, faked network only)
# ---------------------------------------------------------------------------


def test_lane_transition_via_emit_status_transition_offers_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    recorder = OfferRecorder().install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    _seed_planned(feature_dir, "WP01")

    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="demo-mission",
            wp_id="WP01",
            to_lane="claimed",
            actor="robert",
        )
    )

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    assert args["attrs"]["actor"] == "robert"


def test_mission_creation_via_local_emitter_offers_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=_EVENT_ID,
        mission_number=1,
        mission_type="software-dev",
        target_branch="main",
        wp_count=2,
        friendly_name="Demo",
        purpose_tldr="tldr",
        purpose_context="context",
    )

    assert recorder.summaries() == [
        ("event.publish", "MissionCreated"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    assert args["ref"] == "demo-mission"
    assert "friendly_name" not in args["attrs"]  # prose stays local
    assert args["attrs"]["mission_type"] == "software-dev"


def test_mission_created_moment_carries_the_payload_actor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """The WHO a mission-level moment renders with is the payload's ``actor``.

    The local emitter resolves it (#75); the bridge must project it verbatim —
    never fabricate one and never drop it.
    """
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    emit_mission_created_local(
        feature_dir,
        mission_slug="demo-mission",
        mission_id=_EVENT_ID,
        mission_number=1,
        mission_type="software-dev",
        target_branch="main",
        wp_count=2,
        friendly_name="Demo",
        purpose_tldr="tldr",
        purpose_context="context",
        actor="robert@example.com",
    )

    # Mission creation carries presence (E2E-MVP 1.1: "presence shows you on
    # EXPERIMENTAL-demo-repo") but no focus — there is no WP to name.
    assert recorder.summaries() == [
        ("event.publish", "MissionCreated"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    assert args["attrs"]["actor"] == "robert@example.com"


@pytest.mark.git_repo
def test_mission_creation_publishes_specify_started_after_local_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """#4214: a real mission creation publishes ``SpecifyStarted`` once, after ``MissionCreated``.

    The persisted event keeps its local ``artifact_path``; the wire projection
    drops it, and the moment keeps the persisted event's id, actor and time.
    """
    from specify_cli.core.mission_creation import create_mission_core
    from tests.core.test_mission_create_scaffold_rollback import _init_git_repo, _mission_summary

    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    _init_git_repo(tmp_path)

    result = create_mission_core(tmp_path, "specify-started", allow_worktree_context=True, **_mission_summary("specify-started"))

    assert [args["kind"] for _op, args in recorder.moment_offers()] == ["MissionCreated", "SpecifyStarted"]
    persisted = [json.loads(line) for line in (result.feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    local_started = [event for event in persisted if event["event_type"] == "SpecifyStarted"]
    assert len(local_started) == 1
    local = local_started[0]
    assert local["payload"]["artifact_path"], "the persisted event keeps its local artifact path"
    _op, args = recorder.moment_offers()[1]
    assert "artifact_path" not in args["attrs"]
    assert args["attrs"]["event_id"] == local["event_id"]
    assert args["attrs"]["actor"] == local["payload"]["actor"]
    # The codec renders timestamps canonically (``+00:00`` for ``Z``); the instant is what must survive.
    assert _dt.fromisoformat(args["attrs"]["at"]) == _dt.fromisoformat(local["payload"]["at"].replace("Z", "+00:00"))


@pytest.mark.parametrize("artifact_path", ["kitty-specs/demo-mission/artifact.md", None])
@pytest.mark.parametrize("event_type", ["SpecifyStarted", "PlanStarted", "TasksStarted"])
def test_started_phase_moments_project_off_the_local_artifact_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
    event_type: str,
    artifact_path: str | None,
) -> None:
    """#4214: every Started phase publishes, with or without local-only ``artifact_path``."""
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    envelope = emit_artifact_phase(
        feature_dir,
        event_type=event_type,
        mission_slug="demo-mission",
        mission_number=1,
        actor="robert@example.com",
        artifact_path=artifact_path,
    )

    assert envelope is not None
    assert envelope["payload"].get("artifact_path") == artifact_path, "the persisted payload is never projected"
    assert [args["kind"] for _op, args in recorder.moment_offers()] == [event_type]
    _op, args = recorder.moment_offers()[0]
    assert "artifact_path" not in args["attrs"]
    assert args["ref"] == "demo-mission"
    assert args["attrs"]["event_id"] == envelope["event_id"]
    assert args["attrs"]["actor"] == "robert@example.com"


def test_completed_phase_moment_keeps_its_artifact_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """Completed payloads declare ``artifact_path``; the Started projection must not touch them."""
    from specify_cli.status.lifecycle_events import emit_artifact_phase

    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"

    emit_artifact_phase(
        feature_dir,
        event_type="SpecifyCompleted",
        mission_slug="demo-mission",
        actor="cli",
        artifact_path="kitty-specs/demo-mission/spec.md",
    )

    _op, args = recorder.moment_offers()[0]
    assert args["kind"] == "SpecifyCompleted"
    assert args["attrs"]["artifact_path"] == "kitty-specs/demo-mission/spec.md"


def test_started_phase_with_an_unrelated_extra_field_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the local-only ``artifact_path`` is projected away; strict validation stays strict."""
    recorder = OfferRecorder().install(monkeypatch)
    payload = {
        "mission_slug": "demo-mission",
        "mission_number": 1,
        "actor": "cli",
        "at": "2026-09-13T22:00:00+00:00",
        "artifact_path": "kitty-specs/demo-mission/spec.md",
        "unexpected": "field",
    }

    with caplog.at_level(logging.WARNING):
        adapters.fire_lifecycle_saas_fanout(
            envelope={"event_type": "SpecifyStarted", "event_id": _EVENT_ID, "payload": payload},
            log_path=None,
        )

    assert recorder.offers == []
    assert resolved_credential == []
    assert "SpecifyStarted not broadcast" in caplog.text


def test_status_event_occurrence_time_is_preserved_in_the_attrs(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """Rule R-T-01: the moment carries the transition's own time, not emission time."""
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(metadata=_transition_metadata(occurred_at="2026-08-25T11:22:33+00:00"))

    _op, args = recorder.offers[0]
    assert args["attrs"]["occurred_at"] == "2026-08-25T11:22:33+00:00"


def test_throttled_outcome_is_recorded_at_debug_without_a_second_warning(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#180: a throttled moment is lost loudly, not silently — the client
    prints the one-line stderr notice itself (proven against the real
    ``offer()`` in ``tests/zeitgeist_client/test_transport.py``), so this
    bridge records only the structured detail, at debug level, instead of
    logging the loss a second time (the other drop outcomes keep their
    warning). The recorder throttles every offer it sees, so the moment's
    unconditional presence frame (#186) is throttled too — same discipline,
    same debug-only record, still no warning."""
    recorder = OfferRecorder(outcome="throttled").install(monkeypatch)
    caplog.set_level(logging.DEBUG, logger=bridge.__name__)

    _fire_transition()

    assert recorder.summaries() == [
        ("event.publish", "WPStatusChanged"),
        ("presence.publish", "command"),
    ]
    # Nothing at warning level or above — the loss was already noticed on
    # stderr by the client; only the structured debug record remains.
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert sum("throttled" in r.getMessage() for r in caplog.records) == 2


# ---------------------------------------------------------------------------
# DecisionPoint moments (#324): fan-out through the same lifecycle path
# ---------------------------------------------------------------------------


class _DirectMissionDirSeam:
    """Stub placement seam mirroring tests/specify_cli/decisions/test_emit.py.

    These tests target the fan-out projection, not mission/topology lookup.
    """

    def __init__(self, repo_root: Path, mission_slug: str) -> None:
        self._repo_root = repo_root
        self._mission_slug = mission_slug

    def read_dir(self, kind: object) -> Path:
        return self._repo_root / "kitty-specs" / self._mission_slug


@pytest.fixture(autouse=True)
def _direct_decision_mission_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.decisions.emit.placement_seam", _DirectMissionDirSeam)


def _decision_entry(
    decision_id: str,
    *,
    status: DecisionStatus = DecisionStatus.OPEN,
    question: str = "Which auth strategy?",
    options: tuple[str, ...] = ("session", "oauth2"),
    final_answer: str | None = None,
    rationale: str | None = None,
    resolved_at: Any = None,
    resolved_by: str | None = None,
    mission_slug: str = "demo-mission",
) -> IndexEntry:
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=OriginFlow.CHARTER,
        step_id="charter.q1",
        input_key="auth_strategy",
        question=question,
        options=options,
        status=status,
        final_answer=final_answer,
        rationale=rationale,
        created_at=_dt(2026, 4, 23, 10, 0, 0, tzinfo=UTC),
        resolved_at=resolved_at,
        resolved_by=resolved_by,
        mission_id="01KPWT8PNY8683QX3WBW6VXYM7",
        mission_slug=mission_slug,
    )


def test_decision_point_opened_via_local_emitter_offers_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """The exact same fan-out path WPStatusChanged/MissionCreated use: one
    local append, then one ``event.publish`` -- before any git push."""
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    entry = _decision_entry("01AAAAAAAAAAAAAAAAAAAAAAAA")

    emit_decision_opened(
        tmp_path,
        "demo-mission",
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        entry=entry,
        actor="robert",
    )

    assert recorder.summaries() == [
        ("event.publish", "DecisionPointOpened"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    _assert_event_args(args)
    assert args["kind"] == DECISION_POINT_OPENED
    assert args["ref"] == "01AAAAAAAAAAAAAAAAAAAAAAAA"  # decision_point_id
    assert args["attrs"]["actor_id"] == "robert"
    assert args["attrs"]["mission_slug"] == "demo-mission"
    # Bounded moment summary (#77): question + options, joined "; ".
    assert args["attrs"]["summary"] == "Which auth strategy?; session, oauth2"


def test_decision_prose_with_control_characters_is_dropped_not_broadcast(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pasted ANSI escape in decision prose (#415): on the pinned
    spec-kitty-events (9.1.6) the codec rejects non-printable characters on
    encode, so an over-bound moment is dropped before any offer — never
    reaching a consumer whose decode would also reject it. The bridge's own
    ``_first_non_printable_attr`` pre-check is belt-and-braces behind that."""
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    entry = _decision_entry(
        "01AAAAAAAAAAAAAAAAAAAAAAAA",
        question="Which auth? \x1b[31mRED\x1b[0m fallback",
    )

    emit_decision_opened(
        tmp_path,
        "demo-mission",
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        entry=entry,
        actor="robert",
    )

    assert recorder.offers == []
    assert "not broadcast" in caplog.text
    assert "U+001B" in caplog.text


def test_decision_point_resolved_via_local_emitter_carries_final_answer_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    entry = _decision_entry(
        "01AAAAAAAAAAAAAAAAAAAAAAAA",
        status=DecisionStatus.RESOLVED,
        final_answer="oauth2",
        rationale="better security",
        resolved_at=_dt(2026, 4, 23, 10, 5, 0, tzinfo=UTC),
        resolved_by="robert",
    )

    emit_decision_resolved(
        tmp_path,
        "demo-mission",
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        entry=entry,
        actor="robert",
    )

    assert recorder.summaries() == [
        ("event.publish", "DecisionPointResolved"),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    _assert_event_args(args)
    assert args["kind"] == DECISION_POINT_RESOLVED
    assert args["attrs"]["terminal_outcome"] == "resolved"
    assert args["attrs"]["resolved_by"] == "robert"
    assert args["attrs"]["summary"] == "oauth2; better security"


def test_decision_point_resolved_deferred_summary_uses_rationale_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """Deferred/canceled resolutions carry no ``final_answer``: the summary
    falls back to ``rationale`` alone rather than being omitted."""
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    entry = _decision_entry(
        "01AAAAAAAAAAAAAAAAAAAAAAAA",
        status=DecisionStatus.DEFERRED,
        rationale="revisit later",
        resolved_at=_dt(2026, 4, 23, 10, 5, 0, tzinfo=UTC),
        resolved_by="robert",
    )

    emit_decision_resolved(
        tmp_path,
        "demo-mission",
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        entry=entry,
        actor="robert",
    )

    _op, args = recorder.moment_offers()[0]
    assert args["attrs"]["terminal_outcome"] == "deferred"
    assert args["attrs"]["summary"] == "revisit later"


def test_decision_point_opened_summary_is_truncated_on_a_utf8_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_credential: list[Path],
) -> None:
    """An oversize summary is truncated to the 240-UTF-8-byte bound with a
    trailing "…" marker -- never raised, never splitting a multi-byte
    codepoint (#77's boundary-truncation contract)."""
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)
    # Multi-byte codepoints (2 bytes each in UTF-8): guarantees the cut lands
    # mid-string, not just at the tail, and never on a partial codepoint.
    entry = _decision_entry("01AAAAAAAAAAAAAAAAAAAAAAAA", question="é" * 130, options=())

    emit_decision_opened(
        tmp_path,
        "demo-mission",
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        entry=entry,
        actor="robert",
    )

    _op, args = recorder.moment_offers()[0]
    _assert_event_args(args)  # includes the <=240-byte attr-value bound
    summary = args["attrs"]["summary"]
    assert summary.endswith("…")
    assert len(summary.encode("utf-8")) <= 240
    # Every char before the marker survived intact -- no partial codepoint.
    assert summary[:-1] == "é" * (len(summary) - 1)


# ---------------------------------------------------------------------------
# Lifecycle beats (#324): Specify/Plan/Tasks x Started/Completed all fan out
# through the same shared path, unlocked by the events pin bump alone.
# ---------------------------------------------------------------------------

_LIFECYCLE_ARTIFACT_PAYLOADS: dict[str, dict[str, Any]] = {
    "SpecifyStarted": {"mission_slug": "demo-mission", "actor": "robert"},
    "SpecifyCompleted": {"mission_slug": "demo-mission", "actor": "robert", "artifact_path": "spec.md"},
    "PlanStarted": {"mission_slug": "demo-mission", "actor": "robert"},
    "PlanCompleted": {"mission_slug": "demo-mission", "actor": "robert", "artifact_path": "plan.md"},
    "TasksStarted": {"mission_slug": "demo-mission", "actor": "robert"},
    "TasksCompleted": {
        "mission_slug": "demo-mission",
        "actor": "robert",
        "artifact_path": "tasks.md",
        "wp_count": 3,
    },
}


@pytest.mark.parametrize("event_type", sorted(_LIFECYCLE_ARTIFACT_PAYLOADS))
def test_lifecycle_started_and_completed_events_broadcast_through_the_shared_path(
    monkeypatch: pytest.MonkeyPatch,
    resolved_credential: list[Path],
    event_type: str,
) -> None:
    """No duplicate lifecycle emitter is introduced: the six Specify/Plan/Tasks
    x Started/Completed beats reach the relay through the exact same
    ``fire_lifecycle_saas_fanout`` slot MissionCreated already uses -- the
    events#77 pin bump alone is what unlocked them (no new call site)."""
    recorder = OfferRecorder(outcome="sent").install(monkeypatch)

    adapters.fire_lifecycle_saas_fanout(
        envelope={
            "event_id": "01JME2E2E2E2E2E2E2E2E2E2E3",
            "event_type": event_type,
            "aggregate_id": "demo-mission",
            "timestamp": "2026-08-27T00:00:00+00:00",
            "payload": _LIFECYCLE_ARTIFACT_PAYLOADS[event_type],
        },
        log_path=None,
    )

    assert recorder.summaries() == [
        ("event.publish", event_type),
        ("presence.publish", "command"),
    ]
    _op, args = recorder.moment_offers()[0]
    _assert_event_args(args)
    assert args["attrs"]["mission_slug"] == "demo-mission"


# ---------------------------------------------------------------------------
# #4327: ``review_ref`` is pointer-only and rides the wire VERBATIM.
#
# The #3954 interim wire-side bound (``bridge._bound_wire_review_ref`` /
# ``bridge._looks_like_review_ref_pointer``) is deleted: every producer now
# writes a pointer or synthetic marker token into the slot (``move-task``
# never falls back to the operator's ``--note`` prose), so the codec's own
# 240-UTF-8-byte attr bound is the single authority again. The e2e regression
# coverage for the four transition families (approval/completion/rejection/
# direct-emission) lives in
# tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py.
# ---------------------------------------------------------------------------


def test_interim_review_ref_bound_helpers_are_gone() -> None:
    """#4327 architectural gate: the #3954 interim truncation helpers no longer
    exist on the bridge — the wire projection is verbatim, codec-authoritative."""
    assert not hasattr(bridge, "_bound_wire_review_ref")
    assert not hasattr(bridge, "_looks_like_review_ref_pointer")


@pytest.mark.regression
def test_short_review_ref_still_offers_exactly_once(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path]) -> None:
    """An ordinary pointer-shaped review_ref rides verbatim and still produces
    exactly one moment offer (single-hop)."""
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(metadata=_transition_metadata(review_ref="review:WP04"))

    moments = recorder.moment_offers()
    assert len(moments) == 1
    assert moments[0][1]["attrs"]["review_ref"] == "review:WP04"


@pytest.mark.regression
def test_over_bound_review_ref_rides_verbatim_and_fails_loud_at_the_codec(
    monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path], caplog: pytest.LogCaptureFixture
) -> None:
    """#4327 no-silent-drop gate: a review_ref over the codec's 240-UTF-8-byte
    bound rides the projection VERBATIM (never truncated, never collapsed) and
    the whole moment is then dropped LOUDLY — a logged WARNING naming
    ``review_ref`` — exactly as the codec's own bound dictates. With the
    producers pointer-only this is only reachable through an explicit
    free-text ``--review-ref``-style input, which the operator typed into the
    pointer slot themselves; the canonical local log keeps whatever was
    written."""
    recorder = OfferRecorder().install(monkeypatch)

    over_bound_prose = (
        "Reviewed the diff at src/specify_cli/status/zeitgeist_bridge.py and confirmed the fix behaves as "
        "expected across every hop of the transition, closing out the review with no outstanding concerns "
        "after a careful pass through the full acceptance matrix for this change."
    )
    assert len(over_bound_prose.encode("utf-8")) > 240

    _fire_transition(metadata=_transition_metadata(review_ref=over_bound_prose))

    assert recorder.moment_offers() == []
    assert "not broadcast" in caplog.text
    assert "review_ref" in caplog.text


@pytest.mark.regression
def test_over_bound_non_review_ref_attr_is_untouched(monkeypatch: pytest.MonkeyPatch, resolved_credential: list[Path], caplog: pytest.LogCaptureFixture) -> None:
    """Scope guard (ex-#3954 T8): an over-bound attr OTHER than ``review_ref``
    (here ``wp_id``) is not rescued by anything on the review_ref path. A
    normal-length pointer-shaped ``review_ref`` riding alongside it changes
    nothing: the codec's existing fail-closed behavior for every other attr
    is unchanged."""
    recorder = OfferRecorder().install(monkeypatch)

    _fire_transition(
        wp_id="WP01" + "x" * 300,  # over the 240-byte attr bound, unrelated to review_ref
        metadata=_transition_metadata(review_ref="review:WP04"),
    )

    assert recorder.offers == []
    assert recorder.clients_built == 0
    assert "not broadcast" in caplog.text
