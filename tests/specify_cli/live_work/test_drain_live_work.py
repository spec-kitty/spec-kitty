"""ATDD contract: drain gates live-work publish/authored,
the retrospective live-work frame, and the ``live-work hook`` CLI command.

Under drain-off, ``publish_observations`` must drop every observation with
reason ``"drain off"`` (not "no relay credentials") without ever calling
``resolution.resolve_credentials``; ``authored.send``/``.reply`` must raise
``AuthoredMessageError`` with code ``drain_off`` (distinct from
``not_admitted``); the bounded-retry loop must never sleep or retry a
refusal (C-005); the retrospective fan-out and the hook CLI command must
skip cleanly.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from specify_cli.live_work import authored, publisher
from specify_cli.live_work.bindings import RepositoryBinding, ResolvedBindings
from specify_cli.live_work.kinds import WorkEmissionKind, payload_id
from specify_cli.live_work.models import (
    ActorBinding,
    Observation,
    Provenance,
    SessionBinding,
    ToolDetail,
    ToolOutcome,
    ToolState,
)
from specify_cli.zeitgeist_client import resolution

pytestmark = pytest.mark.fast

_MOMENT_KILL_SWITCHES = (
    "SPEC_KITTY_NO_MOMENT_HANDLERS",
    "SPEC_KITTY_SYNC_DISABLE",
    "SPEC_KITTY_SYNC_MINIMAL_IMPORT",
)


@pytest.fixture
def moment_handlers_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the ambient moment-handler kill switches.

    ``moment_handlers_disabled_reason()`` returns early *before* the drain
    gate, so with any of these set a drain-off test passes even when the
    drain gate is deleted (vacuous). Drain-gate tests must reach the gate.
    """
    for name in _MOMENT_KILL_SWITCHES:
        monkeypatch.delenv(name, raising=False)


def _observation(**overrides: object) -> Observation:
    base: dict[str, object] = {
        "kind": WorkEmissionKind.TOOL_INVOKED,
        "session": SessionBinding(session_id="sess-1"),
        "actor": ActorBinding(harness="claude"),
        "repository": RepositoryBinding(slug="acme/repo", branch=None),
        "provenance": Provenance(source="harness_hook", capability="live-work.test"),
        "action": ToolDetail(tool="Bash", state=ToolState.RESULT, outcome=ToolOutcome.SUCCESS),
        "occurred_at": "2026-09-14T12:00:00+00:00",
    }
    base.update(overrides)
    return Observation(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# publish_observations
# ---------------------------------------------------------------------------


class TestPublishObservationsDrainGate:
    def test_drops_every_observation_with_an_accurate_reason(self, drain_off: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        resolve_credentials = Mock(name="resolve_credentials")
        monkeypatch.setattr(resolution, "resolve_credentials", resolve_credentials)

        report = publisher.publish_observations([_observation()], cwd=tmp_path)

        resolve_credentials.assert_not_called()
        assert report.sent == []
        assert report.dropped == [(payload_id(WorkEmissionKind.TOOL_INVOKED), "drain off")]

    def test_unaffected_under_drain_on_still_resolves_credentials(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Baseline regression guard: without drain_off, resolution still runs
        (and reports its own honest "no relay credentials" drop)."""
        resolve_credentials = Mock(name="resolve_credentials", return_value=None)
        monkeypatch.setattr(resolution, "resolve_credentials", resolve_credentials)

        report = publisher.publish_observations([_observation()], cwd=tmp_path)

        resolve_credentials.assert_called_once()
        assert report.dropped == [(payload_id(WorkEmissionKind.TOOL_INVOKED), "no relay credentials (repo not admitted)")]


# ---------------------------------------------------------------------------
# authored.send / authored.reply
# ---------------------------------------------------------------------------


@pytest.fixture()
def authored_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "specify_cli.live_work.bindings.resolve_bindings",
        lambda cwd: ResolvedBindings(repository=RepositoryBinding(slug="acme/widget"), mission=None, repo_root=Path(cwd)),
    )
    monkeypatch.setattr(authored, "_require_moments_enabled", lambda: None)


class TestAuthoredSendDrainGate:
    def test_send_raises_drain_off_and_touches_no_network(self, drain_off: None, authored_bindings: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        resolve_credentials = Mock(name="resolve_credentials")
        monkeypatch.setattr(resolution, "resolve_credentials", resolve_credentials)
        offer = Mock(name="ZeitgeistClient.offer")
        monkeypatch.setattr("specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer", offer)

        with pytest.raises(authored.AuthoredMessageError) as excinfo:
            authored.send("message", "hello team", cwd=tmp_path)

        assert excinfo.value.code == "drain_off"
        assert excinfo.value.code != "not_admitted"
        resolve_credentials.assert_not_called()
        offer.assert_not_called()


class TestAuthoredReplyDrainGate:
    def test_reply_raises_drain_off_and_touches_no_network(self, drain_off: None, authored_bindings: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            authored,
            "_lookup_parent",
            lambda cwd, parent_id: {"audience": "team", "thread": parent_id},
        )
        resolve_credentials = Mock(name="resolve_credentials")
        monkeypatch.setattr(resolution, "resolve_credentials", resolve_credentials)
        offer = Mock(name="ZeitgeistClient.offer")
        monkeypatch.setattr("specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer", offer)

        with pytest.raises(authored.AuthoredMessageError) as excinfo:
            authored.reply("parent-1", "sure thing", cwd=tmp_path)

        assert excinfo.value.code == "drain_off"
        resolve_credentials.assert_not_called()
        offer.assert_not_called()


# ---------------------------------------------------------------------------
# _offer_with_bounded_retry — no retry, no sleep on a definitive refusal
# ---------------------------------------------------------------------------


class _FakeOfferClient:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome
        self.calls = 0

    def offer(self, op: str, args: dict[str, object], *, request_id: str) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(outcome=self._outcome, request_id=request_id, elapsed_s=0.0, response_detail=None)


class TestOfferWithBoundedRetryNonRetryableSet:
    def test_a_future_non_retryable_outcome_never_sleeps_or_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A stand-in outcome not in {SENT, THROTTLED, DROPPED_BUDGET,
        DROPPED_UNREACHABLE} must be definitive by construction (D3/C-005),
        exactly like WP02's future DRAIN_DISABLED, without this WP naming it."""
        stand_in_outcome = SimpleNamespace(value="drain_disabled")
        client = _FakeOfferClient(stand_in_outcome)

        def _blow_up(seconds: float) -> None:
            raise AssertionError(f"unexpected sleep({seconds}) on a definitive refusal")

        monkeypatch.setattr(authored.time, "sleep", _blow_up)

        outcome, reason = authored._offer_with_bounded_retry(client, {"kind": "work.message.team_sent.v1"}, "msg-1")  # type: ignore[arg-type]

        assert client.calls == 1
        assert outcome is authored.SendOutcome.FAILED
        assert reason is not None

    def test_throttled_retry_behaviour_is_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.zeitgeist_client.transport import OfferOutcome

        client = _FakeOfferClient(OfferOutcome.THROTTLED)
        sleeps: list[float] = []
        monkeypatch.setattr(authored.time, "sleep", lambda seconds: sleeps.append(seconds))

        outcome, reason = authored._offer_with_bounded_retry(client, {"kind": "work.message.team_sent.v1"}, "msg-1")  # type: ignore[arg-type]

        assert client.calls == authored.MAX_SEND_ATTEMPTS
        assert outcome is authored.SendOutcome.OFFERED
        assert reason is not None


# ---------------------------------------------------------------------------
# retrospective live-work fan-out
# ---------------------------------------------------------------------------


class TestRetrospectiveLiveWorkFanoutDrainGate:
    def test_skips_publish_observations_under_drain_off(
        self, drain_off: None, moment_handlers_enabled: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.retrospective import lifecycle_events

        monkeypatch.setattr(
            "specify_cli.live_work.bindings.resolve_bindings",
            lambda repo_root: ResolvedBindings(repository=RepositoryBinding(slug="acme/widget"), mission=None, repo_root=repo_root),
        )
        publish_observations = Mock(name="publish_observations")
        monkeypatch.setattr("specify_cli.live_work.publisher.publish_observations", publish_observations)

        lifecycle_events._fanout_live_work_retrospective("captured", repo_root=tmp_path, mission_id="m1", text="done")

        publish_observations.assert_not_called()

    def test_unaffected_under_drain_on_still_publishes(self, moment_handlers_enabled: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Baseline regression guard (root fixture: drain on).

        Hermetic against the dispatch environment's own kill switch: this
        test's subject is the drain gate, not the narrower
        moment_handlers_disabled_reason() check that already precedes it in
        `_fanout_live_work_retrospective` -- so the ambient
        SPEC_KITTY_NO_MOMENT_HANDLERS/SPEC_KITTY_SYNC_DISABLE/
        SPEC_KITTY_SYNC_MINIMAL_IMPORT env vars (set for every agent in this
        mission's dispatch environment) must not silence it before the drain
        check is ever reached (review cycle 1, Issue 1)."""
        from specify_cli.retrospective import lifecycle_events

        monkeypatch.setattr(
            "specify_cli.live_work.bindings.resolve_bindings",
            lambda repo_root: ResolvedBindings(repository=RepositoryBinding(slug="acme/widget"), mission=None, repo_root=repo_root),
        )
        publish_observations = Mock(name="publish_observations")
        monkeypatch.setattr("specify_cli.live_work.publisher.publish_observations", publish_observations)

        lifecycle_events._fanout_live_work_retrospective("captured", repo_root=tmp_path, mission_id="m1", text="done")

        publish_observations.assert_called_once()


# ---------------------------------------------------------------------------
# live-work hook CLI command
# ---------------------------------------------------------------------------


class TestLiveWorkHookDrainGate:
    def test_hook_exits_cleanly_without_resolving_an_adapter(self, drain_off: None, moment_handlers_enabled: None, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import live_work as live_work_cli

        get_adapter = Mock(name="get_adapter")
        monkeypatch.setattr("specify_cli.live_work.adapters.get_adapter", get_adapter)
        # A drain-off skip must happen before stdin is ever touched (no
        # wasted work, NFR-003) -- isatty()=True makes an unguarded call
        # return early on its own rather than raising under pytest's
        # captured stdin, so a false negative here can only be a passing
        # gate, never a stdin-capture artifact.
        monkeypatch.setattr(live_work_cli.sys.stdin, "isatty", lambda: True)

        live_work_cli._run_hook("claude", False)

        get_adapter.assert_not_called()
