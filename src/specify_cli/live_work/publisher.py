"""Live Work publisher — observations onto the existing relay path (#4268).

Projects each canonical :class:`~live_work.models.Observation` onto the
relay's content-agnostic ``event.publish`` wire — ``session_id``,
``kind`` = the shared contract's exact ``work.<kind>.v1`` payload ID,
``ref`` = the aggregate identity (``mission/<id>`` when mission-bound,
``repo/<slug>`` otherwise, mirroring the contract's
``work_aggregate_id``), and ``attrs`` = bounded string metadata — then
makes exactly one offer through the existing typed client
(:meth:`specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer`),
the same transport the status moment bridge uses. No new transport, no
queue, no retry: the bounded wake-up retry is #4311's shared mechanism,
and when it lands its window wraps this call site rather than a second
loop appearing here.

Posture copied deliberately from ``status/zeitgeist_bridge.py``: every
failure is environmental and resolves to a logged drop — the frame is
lost by design (now-view, 2026-09-14 re-scope), the harness invocation
that produced it is never affected, and a repo no team admitted produces
nothing anywhere (unresolvable credentials = zero network attempts).

Defense in depth: before any offer the projected args pass
:func:`specify_cli.zeitgeist_client.sanitizer.assert_clean` against the
work-frame forbidden-key set (raw output, contents, env, secrets, and
caller-side identity-spoof fields — the server derives the principal from
the credential, never from an attr).
"""

from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Iterable

from .codec import validate_typed
from .kinds import payload_id
from .models import ActorBinding, FileDetail, Observation, TestRunDetail, ToolDetail
from .redaction import MAX_SUMMARY_CHARS

__all__ = [
    "MAX_ATTRS",
    "MAX_OBSERVATIONS_PER_INVOCATION",
    "PublishReport",
    "project_args",
    "publish_observation",
    "publish_observations",
]


logger = logging.getLogger(__name__)

MAX_ATTRS = 16
"""The relay's EventArgs attrs bound (maxProperties)."""

MAX_OBSERVATIONS_PER_INVOCATION = 4
"""One hook invocation publishes at most this many frames inside its budget
(4s hook budget: ~2s credential resolution + bounded offers, #4311's retry
window applies later at this same call site)."""

_HARNESS_ID = "spec-kitty-cli"
_EVENT_PUBLISH_OP = "event.publish"
_UNKNOWN = "unknown"


class PublishReport:
    """The honest per-invocation outcome — what was sent, dropped, and why."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.dropped: list[tuple[str, str]] = []

    def as_dict(self) -> dict[str, object]:
        return {"sent": self.sent, "dropped": [{"kind": k, "reason": r} for k, r in self.dropped]}


def project_args(observation: Observation) -> dict[str, object]:
    """Project one observation onto the relay's ``event.publish`` args.

    Pure and total: no network, no clock. Attrs are bounded string values
    (≤240 chars, ≤16 keys) and never carry raw output, contents, env
    values, or identity claims.
    """
    attrs: dict[str, str] = _identity_attrs(observation)
    attrs.update(_action_attrs(observation.action))
    attrs.update(_coverage_and_text_attrs(observation))
    for key, value in (observation.extensions or {}).items():
        if len(attrs) >= MAX_ATTRS:
            break
        attrs[key] = str(value)[:MAX_SUMMARY_CHARS]

    # Hard bounds, enforced here as well as at the relay: never more than
    # 16 attrs, never a value over 240 chars, never a non-string value.
    bounded = {k: v[:MAX_SUMMARY_CHARS] for k, v in list(attrs.items())[:MAX_ATTRS]}

    args: dict[str, object] = {
        "session_id": observation.session.session_id[:128],
        "kind": payload_id(observation.kind),
        "attrs": bounded,
    }
    ref = f"mission/{observation.mission.mission_id}" if observation.mission is not None else f"repo/{observation.repository.slug}"
    args["ref"] = ref[:240]
    return args


def _identity_attrs(observation: Observation) -> dict[str, str]:
    """The identity/context attrs: actor harness, repository, mission,
    activity lineage, delegation counterpart, occurrence time, and the
    honest provenance limitation — never a principal claim."""
    attrs: dict[str, str] = {}
    actor = observation.actor
    attrs["harness"] = (actor.harness if isinstance(actor, ActorBinding) else _UNKNOWN)[:64]
    attrs["repo"] = observation.repository.slug[:MAX_SUMMARY_CHARS]
    if observation.repository.branch:
        # "branch" is fine as a value; it is deliberately not an attr key
        # (the presence family's forbidden set bans the key, and git-truth
        # branch is metadata, not identity).
        attrs["x-branch"] = observation.repository.branch[:MAX_SUMMARY_CHARS]
    if observation.mission is not None:
        attrs["mission"] = observation.mission.mission_id[:120]
    if observation.activity is not None:
        attrs["activity"] = observation.activity.activity_id[:128]
        if observation.activity.parent_activity_id:
            attrs["parent"] = observation.activity.parent_activity_id[:128]
    if observation.session.parent_session_id:
        attrs["delegated_from"] = observation.session.parent_session_id[:128]
    if observation.counterpart:
        attrs["counterpart"] = observation.counterpart[:128]
    attrs["occurred_at"] = observation.occurred_at[:40]
    if observation.provenance.limitation:
        attrs["limitation"] = observation.provenance.limitation[:MAX_SUMMARY_CHARS]
    return attrs


def _action_attrs(action: object) -> dict[str, str]:
    """The per-action-kind attrs (tool / file / test), bounded strings only."""
    attrs: dict[str, str] = {}
    if isinstance(action, ToolDetail):
        attrs["tool"] = action.tool[:64]
        attrs["state"] = action.state.value
        if action.outcome is not None:
            attrs["outcome"] = action.outcome.value
        if action.duration_ms is not None:
            attrs["duration_ms"] = str(action.duration_ms)
    elif isinstance(action, FileDetail):
        attrs["op"] = action.operation.value
        attrs["path"] = action.path[:MAX_SUMMARY_CHARS]
        if action.destination_path:
            attrs["dest"] = action.destination_path[:MAX_SUMMARY_CHARS]
        attrs["bytes_added"] = str(action.bytes_added)
        attrs["bytes_removed"] = str(action.bytes_removed)
        if action.coalesced_edits > 1:
            attrs["edits"] = str(action.coalesced_edits)
            if action.coalesced_window_s is not None:
                attrs["window_s"] = str(action.coalesced_window_s)
        if action.attribution != "exact":
            attrs["attribution"] = action.attribution
    elif isinstance(action, TestRunDetail):
        attrs["selector"] = action.selector[:MAX_SUMMARY_CHARS]
        attrs["state"] = action.state.value
        if action.outcome is not None:
            attrs["outcome"] = action.outcome.value
        if action.passed is not None:
            attrs["passed"] = str(action.passed)
            attrs["failed"] = str(action.failed)
            attrs["skipped"] = str(action.skipped)
    return attrs


def _coverage_and_text_attrs(observation: Observation) -> dict[str, str]:
    """Coverage-gap and bounded inline-text attrs."""
    attrs: dict[str, str] = {}
    if observation.coverage is not None:
        attrs["area"] = observation.coverage.area[:64]
        if observation.coverage.reason:
            attrs["reason"] = observation.coverage.reason[:MAX_SUMMARY_CHARS]
    if observation.text:
        # Bounded honest inline text (failure/skip lifecycle kinds). The
        # key is x-namespaced: "text" is a forbidden key on the live wire's
        # presence family and stays one.
        attrs["x-text"] = observation.text[:MAX_SUMMARY_CHARS]
    return attrs


def _work_frame_forbidden_keys() -> frozenset[str]:
    """The work-frame forbidden-key set, asserted before any offer.

    Mirrors the shared WorkObservation contract's privacy set (raw output,
    file contents, environment values, secrets) and the identity rule
    (the principal is server-derived; caller attrs never claim it) — the
    CLI-side set until the events 10.x ``FORBIDDEN_WORK_KEYS`` ships with
    the post-launch repin (planning#2000), at which point the codec gate
    swaps to the upstream owner.
    """
    return frozenset(
        {
            "contents",
            "stdout",
            "stderr",
            "output",
            "command_text",
            "env",
            "environment",
            "user",
            "user_id",
            "email",
            "actor",
            "team",
            "team_id",
            "token",
            "authorization",
            "bearer",
            "password",
            "secret",
            "url",
            "text",
        }
    )


def publish_observations(observations: Iterable[Observation], *, cwd: Path, report: PublishReport | None = None) -> PublishReport:
    """Publish every observation through the existing relay path.

    Credentials resolve once per invocation; each observation makes at most
    one bounded offer; everything environmental resolves to a recorded
    drop. Never raises into the caller (a hook process must exit 0).
    """
    report = report if report is not None else PublishReport()
    pending = list(observations)[:MAX_OBSERVATIONS_PER_INVOCATION]
    overflow = list(observations)[MAX_OBSERVATIONS_PER_INVOCATION:]
    for observation in overflow:
        report.dropped.append((payload_id(observation.kind), "invocation frame budget exceeded"))
        logger.debug("live-work frame dropped: invocation budget exceeded")

    from specify_cli.zeitgeist_client import repo_identity, resolution  # noqa: PLC0415
    from specify_cli.zeitgeist_client.credentials import StoredCredential  # noqa: PLC0415

    deadline = repo_identity.Deadline()
    try:
        credential: StoredCredential | None = resolution.resolve_credentials(cwd, deadline=deadline)
    except Exception as exc:  # environmental: no relay, no team, no network
        for observation in pending:
            report.dropped.append((payload_id(observation.kind), f"credential resolution failed: {exc}"))
        return report
    if credential is None:
        for observation in pending:
            report.dropped.append((payload_id(observation.kind), "no relay credentials (repo not admitted)"))
        logger.debug("live-work frames not published: no relay credentials")
        return report

    from specify_cli.zeitgeist_client.transport import (  # noqa: PLC0415
        ClientConfig,
        OfferOutcome,
        ZeitgeistClient,
    )

    client = ZeitgeistClient(
        ClientConfig(
            relay_url=credential.relay_url,
            token=credential.token,
            harness=_HARNESS_ID,
            session_id=pending[0].session.session_id if pending else _UNKNOWN,
            agent_id=None,
            repo="",
            branch="",
            capability_credential=credential.capability_credential,
        )
    )
    for observation in pending:
        kind_id = payload_id(observation.kind)
        # The capability-gated typed codec: when the installed events
        # package carries the shared WorkObservation contract, every frame
        # is validated by the shared models here; until then the gate is a
        # visible matrix row and this is a no-op.
        codec_error = validate_typed(observation)
        if codec_error is not None:
            report.dropped.append((kind_id, codec_error))
            logger.warning("live-work frame %s not published: %s", kind_id, codec_error)
            continue
        try:
            args = project_args(observation)
            _assert_clean_args(args)
        except Exception as exc:
            report.dropped.append((kind_id, f"projection/redaction refused: {exc}"))
            logger.warning("live-work frame %s not published: %s", kind_id, exc)
            continue
        try:
            result = client.offer(_EVENT_PUBLISH_OP, args)
        except Exception as exc:  # environmental: never fail the harness
            report.dropped.append((kind_id, f"offer failed: {exc}"))
            logger.warning("live-work frame %s dropped: %s", kind_id, exc)
            continue
        if result.outcome is OfferOutcome.SENT:
            report.sent.append(f"{kind_id}:{result.request_id}")
            logger.debug("live-work frame %s offered (%s)", kind_id, result.request_id)
        else:
            report.dropped.append((kind_id, f"offer outcome {result.outcome.value}"))
            logger.warning(
                "live-work frame %s dropped (%s); no retry by design (#4311 owns the shared wake-up window)",
                kind_id,
                result.outcome.value,
            )
    return report


def publish_observation(observation: Observation, *, cwd: Path) -> PublishReport:
    """Publish one observation — see :func:`publish_observations`."""
    return publish_observations([observation], cwd=cwd)


def _assert_clean_args(args: dict[str, object]) -> None:
    """Assert the projected args carry no forbidden key, anywhere inside."""
    from specify_cli.zeitgeist_client.sanitizer import assert_clean  # noqa: PLC0415

    assert_clean(args, forbidden=_work_frame_forbidden_keys())
