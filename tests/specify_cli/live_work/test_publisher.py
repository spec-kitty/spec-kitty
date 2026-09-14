"""Publisher — wire projection bounds and the one-offer posture.

Fake only the socket: credential resolution is monkeypatched to a stored
credential and the typed client to a recording stub, mirroring the posture
of ``tests/status/test_zeitgeist_moment_handler.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from specify_cli.zeitgeist_client.transport import OfferOutcome

from specify_cli.live_work.kinds import WorkEmissionKind, payload_id
from specify_cli.live_work.models import (
    ActivityBinding,
    ActorBinding,
    MissionBinding,
    Observation,
    Provenance,
    RepositoryBinding,
    SessionBinding,
    TestRunDetail,
    ToolDetail,
    ToolOutcome,
    ToolState,
    UnknownActor,
)
from specify_cli.live_work.publisher import (
    MAX_ATTRS,
    MAX_OBSERVATIONS_PER_INVOCATION,
    project_args,
    publish_observations,
)

pytestmark = pytest.mark.fast


def _observation(**overrides) -> Observation:
    base = {
        "kind": WorkEmissionKind.TOOL_INVOKED,
        "session": SessionBinding(session_id="sess-1"),
        "actor": ActorBinding(harness="claude"),
        "repository": RepositoryBinding(slug="acme/repo", branch=None),
        "provenance": Provenance(source="harness_hook", capability="live-work.test"),
        "activity": ActivityBinding(activity_id="act-1"),
        "action": ToolDetail(tool="Bash", state=ToolState.RESULT, outcome=ToolOutcome.SUCCESS),
        "occurred_at": "2026-09-14T12:00:00+00:00",
    }
    base.update(overrides)
    return Observation(**base)


def test_projection_uses_the_shared_payload_ids() -> None:
    args = project_args(_observation())
    assert args["kind"] == payload_id(WorkEmissionKind.TOOL_INVOKED)
    assert args["kind"] == "work.action.tool_invoked.v1"
    assert args["session_id"] == "sess-1"


def test_projection_bounds_match_the_relay_schema() -> None:
    observation = _observation(
        mission=MissionBinding(mission_id="01J" + "23456789ABCDEFGHJKMNPQRST"[:23]),
        extensions={f"x-k{i}": "v" for i in range(20)},
    )
    args = project_args(observation)
    attrs = args["attrs"]
    assert len(attrs) <= MAX_ATTRS
    assert all(isinstance(v, str) for v in attrs.values())
    assert all(len(v) <= 240 for v in attrs.values())
    assert all(len(k) <= 64 for k in attrs)


def test_projection_aggregate_ref_mirrors_work_aggregate_id() -> None:
    mission_id = "01J" + "23456789ABCDEFGHJKMNPQRST"[:23]
    mission_bound = project_args(_observation(mission=MissionBinding(mission_id=mission_id)))
    assert mission_bound["ref"] == f"mission/{mission_id}"
    repo_bound = project_args(_observation())
    assert repo_bound["ref"] == "repo/acme/repo"


def test_projection_forbidden_keys_never_appear_at_any_depth() -> None:
    from specify_cli.live_work.publisher import _work_frame_forbidden_keys

    observation = _observation(
        kind=WorkEmissionKind.TEST_EXECUTED,
        action=TestRunDetail(
            selector="pytest::tests/a.py",
            state=ToolState.RESULT,
            passed=3,
            failed=0,
            skipped=1,
            outcome=ToolOutcome.SUCCESS,
        ),
        extensions={"x-summary": "pytest -q", "x-branch": "main"},
    )
    args = project_args(observation)
    dumped = json.dumps(args)
    for forbidden in _work_frame_forbidden_keys():
        assert f'"{forbidden}"' not in dumped, forbidden


def test_lifecycle_text_rides_x_namespaced_and_bounded() -> None:
    observation = _observation(
        kind=WorkEmissionKind.RETROSPECTIVE_FAILED,
        action=None,
        text="retrospective failed: " + "x" * 1970,  # under the model's 2000-char inline bound
    )
    args = project_args(observation)
    assert args["attrs"]["x-text"] == ("retrospective failed: " + "x" * 1970)[:240]
    assert "text" not in args["attrs"]


def test_unknown_actor_publishes_as_unknown_harness() -> None:
    args = project_args(_observation(actor=UnknownActor()))
    assert args["attrs"]["harness"] == "unknown"


# ── the offer path (socket faked) ────────────────────────────────────────────


@dataclass
class _FakeCredential:
    relay_url = "https://relay.example"
    token = "t"
    capability_credential = "c"


@dataclass
class _OfferResult:
    outcome: object
    request_id: str = "req-1"
    elapsed_s: float = 0.01


@dataclass
class _FakeClient:
    offers: list[tuple[str, dict]] = field(default_factory=list)
    outcome: object = OfferOutcome.SENT

    def offer(self, op: str, args: dict) -> _OfferResult:
        self.offers.append((op, args))
        return _OfferResult(outcome=self.outcome)


def _patch_publish(monkeypatch, *, credential=_FakeCredential(), client=None):
    fake_client = client or _FakeClient()
    monkeypatch.setattr(
        "specify_cli.zeitgeist_client.resolution.resolve_credentials",
        lambda cwd, deadline: credential,
    )
    import specify_cli.zeitgeist_client.transport as transport

    monkeypatch.setattr(transport, "ZeitgeistClient", lambda config: fake_client)
    return fake_client


def test_one_offer_per_observation_through_the_existing_client(monkeypatch, tmp_path: Path) -> None:
    fake_client = _patch_publish(monkeypatch)
    report = publish_observations([_observation(), _observation()], cwd=tmp_path)
    assert len(fake_client.offers) == 2
    assert all(op == "event.publish" for op, _ in fake_client.offers)
    assert len(report.sent) == 2
    assert report.dropped == []


def test_no_credentials_means_zero_network_attempts(monkeypatch, tmp_path: Path) -> None:
    fake_client = _patch_publish(monkeypatch, credential=None)
    report = publish_observations([_observation()], cwd=tmp_path)
    assert fake_client is not None
    assert fake_client.offers == []
    assert report.dropped and "credentials" in report.dropped[0][1]


def test_rejected_offer_is_a_recorded_drop_never_a_raise(monkeypatch, tmp_path: Path) -> None:
    fake_client = _patch_publish(monkeypatch, client=_FakeClient(outcome=OfferOutcome.REJECTED))
    report = publish_observations([_observation()], cwd=tmp_path)
    assert fake_client.offers  # the offer WAS made; the relay refused it
    assert report.sent == []
    assert report.dropped[0][0] == "work.action.tool_invoked.v1"


def test_invocation_frame_budget_is_honest(monkeypatch, tmp_path: Path) -> None:
    fake_client = _patch_publish(monkeypatch)
    many = [_observation(session=SessionBinding(session_id=f"s{i}")) for i in range(10)]
    report = publish_observations(many, cwd=tmp_path)
    assert len(fake_client.offers) == MAX_OBSERVATIONS_PER_INVOCATION
    assert len(report.dropped) == 10 - MAX_OBSERVATIONS_PER_INVOCATION
    assert all("budget" in reason for _, reason in report.dropped)


def test_offer_exception_never_raises_into_the_harness(monkeypatch, tmp_path: Path) -> None:
    class _ExplodingClient:
        def offer(self, op: str, args: dict) -> None:
            msg = "socket exploded"
            raise OSError(msg)

    monkeypatch.setattr(
        "specify_cli.zeitgeist_client.resolution.resolve_credentials",
        lambda cwd, deadline: _FakeCredential(),
    )
    import specify_cli.zeitgeist_client.transport as transport

    monkeypatch.setattr(transport, "ZeitgeistClient", lambda config: _ExplodingClient())
    report = publish_observations([_observation()], cwd=tmp_path)
    assert report.sent == []
    assert "offer failed" in report.dropped[0][1]
