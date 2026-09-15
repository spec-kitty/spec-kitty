"""Bounded jittered retry for the lifecycle/decision moment stream (#4311).

Robert's 2026-09-14 ruling (planning#2269): "I need decisions in real time
AND as a permanent record." These tests pin the real-time half — the
lifecycle fan-out path (decision points riding
``fire_lifecycle_saas_fanout`` → ``zeitgeist_bridge``) retries the
relay-wake failure class (503, offer timeout, unreachable) with jitter for
a bounded window covering a relay wake (~20 s), then gives up with a
visible stderr diagnostic — with no queue, no spool, no journal.

Three layers:

* pure unit tests over :func:`_offer_with_bounded_retry`'s loop mechanics
  and :func:`_is_retryable_offer`'s truth table (fake clock/sleep/jitter
  seams — no real waiting);
* the issue's required tests 3 and 4 through the REAL production chain
  (``emit_decision_opened`` → fan-out → bridge → client) with the relay
  doubled: a waking relay (503, then 200) still receives the decision
  event; a relay that stays down gives up within the bound, reports it
  loudly, and the local commit stays intact;
* the fan-out runner's handler-declared bound (``adapters``), without
  which a one-shot CLI process would exit before the retry window closed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.decisions.emit import emit_decision_opened
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.status import adapters
from specify_cli.status.zeitgeist_bridge import (
    RETRY_GIVEUP_NOTICE,
    _is_retryable_offer,
    _offer_with_bounded_retry,
    lifecycle_retry_window_s,
)
from specify_cli.zeitgeist_client import resolution as resolution_module
from specify_cli.zeitgeist_client import transport as transport_module
from specify_cli.zeitgeist_client.credentials import StoredCredential
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "issue-4311-retry-mission"
MISSION_ID = "01KI4311RETRYMISSION000000"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _offer_result(outcome: str, *, status_code: int | None = None):
    return transport_module.OfferResult(
        outcome=transport_module.OfferOutcome(outcome),
        request_id="req-1",
        elapsed_s=0.01,
        status_code=status_code,
    )


class _ScriptedClient:
    """A ``ZeitgeistClient`` double whose ``offer`` answers a scripted list.

    The last scripted outcome repeats forever; every offer records the op.
    """

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.offer_calls: list[str] = []

    def offer(self, op: str, args: Any) -> Any:
        self.offer_calls.append(op)
        index = min(len(self.offer_calls) - 1, len(self.outcomes) - 1)
        return self.outcomes[index]

    def presence(self, activity: str, path: str | None = None) -> Any:
        return _offer_result("sent")

    def focus_start(self, mission_slug: str, wp_id: str | None = None) -> Any:
        return _offer_result("sent")


class _FakeClock:
    """A monotonic clock double advanced only by the recorded sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _RecordingSleep:
    def __init__(self, clock: _FakeClock) -> None:
        self.clock = clock
        self.slept: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.clock.now += seconds


def _fixed_jitter(value: float, lo: float, hi: float) -> float:
    return value  # deterministic: the un-jittered backoff schedule


# ---------------------------------------------------------------------------
# Loop mechanics (pure unit — no real waiting)
# ---------------------------------------------------------------------------


class TestOfferWithBoundedRetry:
    def test_waking_relay_503_then_sent_is_delivered_on_the_retry(self, capsys: pytest.CaptureFixture) -> None:
        client = _ScriptedClient([_offer_result("rejected", status_code=503), _offer_result("sent")])
        clock = _FakeClock()
        sleep = _RecordingSleep(clock)

        _offer_with_bounded_retry(
            client,
            DECISION_POINT_OPENED,
            {"session_id": "s", "kind": DECISION_POINT_OPENED},
            window_s=25.0,
            sleep=sleep,
            clock=clock,
            jitter=_fixed_jitter,
        )

        assert client.offer_calls == ["event.publish", "event.publish"]
        assert sleep.slept == [0.5]  # base backoff, un-jittered
        # No give-up notice: the moment was delivered.
        assert RETRY_GIVEUP_NOTICE.split(":")[0] not in capsys.readouterr().err

    def test_relay_that_stays_down_gives_up_within_the_bound(self, capsys: pytest.CaptureFixture) -> None:
        client = _ScriptedClient([_offer_result("rejected", status_code=503)])
        clock = _FakeClock()
        sleep = _RecordingSleep(clock)

        _offer_with_bounded_retry(
            client,
            DECISION_POINT_OPENED,
            {"session_id": "s", "kind": DECISION_POINT_OPENED},
            window_s=25.0,
            sleep=sleep,
            clock=clock,
            jitter=_fixed_jitter,
        )

        # Backoff doubles off the 0.5s base, capped at 4s, and the whole
        # schedule never sleeps past the window.
        assert sleep.slept == [0.5, 1.0, 2.0, 4.0, 4.0, 4.0, 4.0, 4.0, 1.5]
        assert sum(sleep.slept) == pytest.approx(25.0)
        err = capsys.readouterr().err
        assert "not delivered" in err
        assert "relay did not recover within 25s" in err
        assert "no queue, no spool" in err
        # Every attempt was the moment op, nothing else.
        assert client.offer_calls and set(client.offer_calls) == {"event.publish"}

    def test_non_retryable_rejection_is_final_on_the_first_attempt(self) -> None:
        client = _ScriptedClient([_offer_result("rejected", status_code=404)])
        clock = _FakeClock()
        sleep = _RecordingSleep(clock)

        _offer_with_bounded_retry(
            client,
            DECISION_POINT_OPENED,
            {},
            window_s=25.0,
            sleep=sleep,
            clock=clock,
            jitter=_fixed_jitter,
        )

        assert client.offer_calls == ["event.publish"]
        assert sleep.slept == []

    def test_zero_window_is_a_single_attempt(self, capsys: pytest.CaptureFixture) -> None:
        client = _ScriptedClient([_offer_result("dropped_unreachable")])
        clock = _FakeClock()
        sleep = _RecordingSleep(clock)

        _offer_with_bounded_retry(
            client,
            DECISION_POINT_OPENED,
            {},
            window_s=0.0,
            sleep=sleep,
            clock=clock,
            jitter=_fixed_jitter,
        )

        assert client.offer_calls == ["event.publish"]
        assert sleep.slept == []
        assert "not delivered" in capsys.readouterr().err

    def test_jitter_is_applied_to_each_backoff_delay(self) -> None:
        client = _ScriptedClient([_offer_result("rejected", status_code=503)])
        clock = _FakeClock()
        sleep = _RecordingSleep(clock)
        jitters: list[float] = []

        def _recording_jitter(value: float, lo: float, hi: float) -> float:
            jitters.append((value, lo, hi))
            return value * 1.5  # the top of the ±50% band

        _offer_with_bounded_retry(
            client,
            DECISION_POINT_OPENED,
            {},
            window_s=3.0,
            sleep=sleep,
            clock=clock,
            jitter=_recording_jitter,
        )

        # Each delay was drawn from the ±50% band around the schedule.
        assert jitters == [(0.5, 0.5, 1.5), (1.0, 0.5, 1.5), (2.0, 0.5, 1.5)]
        assert sleep.slept == [0.75, 1.5, 0.75]  # last one clamped to remaining


class TestIsRetryableOffer:
    @pytest.mark.parametrize(
        ("outcome", "status_code", "expected"),
        [
            ("rejected", 503, True),  # the relay-wake status
            ("rejected", 404, False),  # a genuine rejection
            ("rejected", 429, False),  # throttle is its own contract
            ("dropped_budget", None, True),  # 750ms timeout against a waking relay
            ("dropped_unreachable", None, True),  # connect refused while booting
            ("refused_local", None, False),  # never any socket
            ("sent", None, False),
        ],
    )
    def test_truth_table(self, outcome: str, status_code: int | None, expected: bool) -> None:
        assert _is_retryable_offer(_offer_result(outcome, status_code=status_code)) is expected


class TestWindowKnob:
    def test_default_covers_a_relay_wake(self) -> None:
        assert lifecycle_retry_window_s() == 25.0

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", "30")
        assert lifecycle_retry_window_s() == 30.0

    def test_zero_disables_the_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", "0")
        assert lifecycle_retry_window_s() == 0.0

    @pytest.mark.parametrize("bad", ["not-a-number", "-5", "inf", "nan", "  "])
    def test_invalid_values_fall_back_to_the_default(self, monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", bad)
        assert lifecycle_retry_window_s() == 25.0


# ---------------------------------------------------------------------------
# The production chain, relay doubled (the issue's required tests 3 and 4)
# ---------------------------------------------------------------------------


class _DirectMissionDirSeam:
    """Pins ``decisions.emit``'s mission-dir resolution to a flat path, so
    the chain under test targets the fan-out contract, not topology lookup
    (same pattern as ``test_zeitgeist_decision_moment_docker_local.py``)."""

    def __init__(self, repo_root: Path, mission_slug: str) -> None:
        self._repo_root = repo_root
        self._mission_slug = mission_slug

    def read_dir(self, kind: object) -> Path:
        return self._repo_root / "kitty-specs" / self._mission_slug


def _make_entry() -> IndexEntry:
    from kernel.clock import UTC, datetime

    return IndexEntry(
        decision_id="01KI4311AAAAAAAAAAAAAAAAAA",
        origin_flow=OriginFlow.CHARTER,
        step_id="charter.q1",
        input_key="auth_strategy",
        question="Which auth strategy?",
        options=("session", "oauth2"),
        status=DecisionStatus.OPEN,
        created_at=datetime(2026, 9, 14, 10, 0, 0, tzinfo=UTC),
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
    )


def _credential() -> StoredCredential:
    return StoredCredential(
        relay_url="http://127.0.0.1:9",
        token="relay-token",
        token_issued_at="2026-08-25T00:00:00+00:00",
        token_kind="presence",
        capability_credential="capability-jwt",
    )


@pytest.fixture(autouse=True)
def _zeitgeist_handlers_only():
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()
    yield
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()


@pytest.fixture(autouse=True)
def _direct_mission_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.decisions.emit.placement_seam", _DirectMissionDirSeam)


@pytest.fixture(autouse=True)
def _no_focus_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolution_module, "resolve_focus_capability", lambda *a, **k: None)


def _install_relay_double(monkeypatch: pytest.MonkeyPatch, moment_outcomes: list[Any]) -> _RelayDouble:
    """Double the relay: scripted ``event.publish`` outcomes per client
    instance, resolved credentials, and a pinned checkout identity (the
    ``OfferRecorder`` pattern from ``test_zeitgeist_moment_handler.py`` —
    no network, no git in the liveness frames).

    ``moment_outcomes`` is consumed per client instance: the bridge builds
    one client for the moment (all its retries hit the same instance) and
    a separate one for the liveness frames; the last scripted outcome
    repeats forever. The returned double records every offer across every
    instance, tagged by op.
    """
    double = _RelayDouble(moment_outcomes)
    double.install(monkeypatch)
    return double


class _RelayDouble:
    def __init__(self, moment_outcomes: list[Any]) -> None:
        self.moment_outcomes = moment_outcomes
        self.moment_offers: list[str] = []  # one entry per event.publish attempt
        self.other_offers: list[str] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        double = self

        class FakeZeitgeistClient:
            def __init__(self, config: Any) -> None:
                self._config = config
                self._moment_calls = 0

            def offer(self, op: str, args: Any) -> Any:
                if op != "event.publish":
                    double.other_offers.append(op)
                    return _offer_result("sent")
                double.moment_offers.append(op)
                self._moment_calls += 1
                outcome = double.moment_outcomes[min(self._moment_calls - 1, len(double.moment_outcomes) - 1)]
                return outcome

            def presence(self, activity: str, path: str | None = None) -> Any:
                return self.offer("presence.publish", {})

            def focus_start(self, mission_slug: str, wp_id: str | None = None) -> Any:
                return self.offer("focus.start", {})

        monkeypatch.setattr(transport_module, "ZeitgeistClient", FakeZeitgeistClient)

        def fake_resolve_credentials(cwd: Path, **kwargs: object) -> StoredCredential:
            return _credential()

        monkeypatch.setattr(resolution_module, "resolve_credentials", fake_resolve_credentials)

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

        monkeypatch.setattr(transport_module.ClientConfig, "for_repository", classmethod(fake_for_repository))


class TestDecisionEventRetryThroughTheFanout:
    def test_waking_relay_still_receives_the_decision_event(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture) -> None:
        """Required test 3: a relay that answers 503 while waking and 200 a
        moment later still receives the decision event — through the REAL
        emit → fan-out → bridge → client chain, retried within the window."""
        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", "5")
        relay = _install_relay_double(
            monkeypatch,
            [_offer_result("rejected", status_code=503), _offer_result("sent")],
        )
        (tmp_path / "kitty-specs" / MISSION_SLUG).mkdir(parents=True)

        emit_decision_opened(
            tmp_path,
            MISSION_SLUG,
            decision_id="01KI4311AAAAAAAAAAAAAAAAAA",
            entry=_make_entry(),
            actor="alice",
        )

        assert relay.moment_offers == ["event.publish", "event.publish"]
        # No give-up notice: the waking relay got the frame.
        assert "not delivered" not in capfd.readouterr().err
        # The canonical local event row exists regardless of relay state.
        events = (tmp_path / "kitty-specs" / MISSION_SLUG / "status.events.jsonl").read_text(encoding="utf-8")
        assert DECISION_POINT_OPENED in events

    def test_relay_that_stays_down_gives_up_within_the_bound_and_reports_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture
    ) -> None:
        """Required test 4 (relay half): a relay that never recovers gives up
        within the bound, says so visibly on stderr, and the local record is
        intact."""
        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", "1")
        relay = _install_relay_double(monkeypatch, [_offer_result("dropped_unreachable")])
        (tmp_path / "kitty-specs" / MISSION_SLUG).mkdir(parents=True)

        emit_decision_opened(
            tmp_path,
            MISSION_SLUG,
            decision_id="01KI4311AAAAAAAAAAAAAAAAAA",
            entry=_make_entry(),
            actor="alice",
        )

        # More than one attempt, bounded by the 1s window (base backoff 0.5s
        # fits exactly one retry; the give-up is within the bound by design).
        assert 2 <= len(relay.moment_offers) <= 3
        err = capfd.readouterr().err
        assert "not delivered" in err
        assert "relay did not recover within 1s" in err
        events = (tmp_path / "kitty-specs" / MISSION_SLUG / "status.events.jsonl").read_text(encoding="utf-8")
        assert DECISION_POINT_OPENED in events


# ---------------------------------------------------------------------------
# The fan-out runner's handler-declared bound (#4311 — without it the retry
# window cannot survive the default 10s join in a one-shot CLI process)
# ---------------------------------------------------------------------------


class TestFanoutHandlerDeclaredBound:
    def test_declared_bound_raises_the_join_above_the_configured_timeout(self) -> None:
        assert (
            adapters._handler_declared_bound_s(
                adapters._lifecycle_saas_handlers[0]
                if adapters._lifecycle_saas_handlers
                else __import__("specify_cli.status.zeitgeist_bridge", fromlist=["lifecycle_moment_handler"]).lifecycle_moment_handler,
            )
            >= 25.0
        )

    def test_missing_declaration_resolves_to_zero(self) -> None:
        def _bare_handler(**kwargs: object) -> None:  # noqa: ARG001
            return None

        assert adapters._handler_declared_bound_s(_bare_handler) == 0.0

    def test_malformed_declarations_resolve_to_zero_never_raise(self) -> None:
        def _negative(**kwargs: object) -> None:  # noqa: ARG001
            return None

        _negative.saas_fanout_bound_s = -3  # type: ignore[attr-defined]
        assert adapters._handler_declared_bound_s(_negative) == 0.0

        def _unparsable(**kwargs: object) -> None:  # noqa: ARG001
            return None

        _unparsable.saas_fanout_bound_s = "soon"  # type: ignore[attr-defined]
        assert adapters._handler_declared_bound_s(_unparsable) == 0.0

        def _broken_callable(**kwargs: object) -> None:  # noqa: ARG001
            return None

        _broken_callable.saas_fanout_bound_s = lambda: 1 / 0  # type: ignore[attr-defined]
        assert adapters._handler_declared_bound_s(_broken_callable) == 0.0

    def test_the_join_honors_a_declared_bound_above_the_configured_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A handler whose declared bound exceeds the configured fan-out
        timeout runs to completion instead of being cut at the configured
        join — the mechanism that keeps a legitimate retry window alive."""
        import time as _time

        monkeypatch.setenv("SPEC_KITTY_SAAS_FANOUT_TIMEOUT", "0.2")
        ran: list[float] = []

        def _slow_handler(**kwargs: object) -> None:  # noqa: ARG001
            _time.sleep(0.35)
            ran.append(_time.monotonic())

        _slow_handler.saas_fanout_bound_s = 1.0  # type: ignore[attr-defined]

        # Without the declared bound the 0.2s join would raise TimeoutError.
        adapters._run_fanout_handler_bounded(_slow_handler, {}, label="Lifecycle SaaS fan-out")
        assert ran  # the handler ran to completion

    def test_the_configured_timeout_still_binds_undeclared_handlers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time as _time

        monkeypatch.setenv("SPEC_KITTY_SAAS_FANOUT_TIMEOUT", "0.1")

        def _slow_handler(**kwargs: object) -> None:  # noqa: ARG001
            _time.sleep(0.3)

        with pytest.raises(TimeoutError):
            adapters._run_fanout_handler_bounded(_slow_handler, {}, label="Lifecycle SaaS fan-out")


# ---------------------------------------------------------------------------
# Required test 4, ledger half: the relay staying down never costs the
# permanent record — the decision is committed locally regardless.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
class TestRelayDownLocalCommitIntact:
    def test_relay_down_decision_still_committed_locally(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture) -> None:
        import sys

        sys.path.append("tests")
        from tests.specify_cli.write_side.topology_fixtures import build_primary

        from specify_cli.decisions.service import open_decision

        monkeypatch.setenv("SPEC_KITTY_ZEITGEIST_RETRY_WINDOW_S", "1")
        _install_relay_double(monkeypatch, [_offer_result("rejected", status_code=503)])

        top = build_primary(tmp_path)
        repo, slug = top.repo_root, top.mission_slug

        # Non-protected feature target (``main`` is protected by default —
        # see test_ledger_commit.py's _retarget_to_feature_branch).
        def _git(*args: str) -> str:
            return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout

        branch = "feature/decisions-retry"
        _git("checkout", "-q", "-b", branch)
        meta = repo / "kitty-specs" / slug / "meta.json"
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["target_branch"] = branch
        meta.write_text(json.dumps(data), encoding="utf-8")
        _git("add", "-A")
        _git("commit", "-q", "-m", "retarget")

        # Direct the emit seam at the real repo too (the autouse fixture
        # pins it to a flat path — rebuild it for this repo root).
        monkeypatch.setattr("specify_cli.decisions.emit.placement_seam", _DirectMissionDirSeam)

        resp = open_decision(
            repo,
            slug,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )

        # The live half gave up, loudly, within the bound.
        err = capfd.readouterr().err
        assert "not delivered" in err
        # The permanent half is intact: committed locally, tree clean.
        assert resp.ledger_commit is not None
        assert resp.ledger_commit.status == "committed"
        subjects = _git("log", "-3", "--pretty=%s")
        assert "record open of" in subjects
        status = _git("status", "--porcelain", "--", "kitty-specs")
        assert status == ""
