"""The Zeitgeist moment handler at the status fan-out seam (E3, Priivacy-ai/spec-kitty#8).

One fire-and-forget ``event.publish`` per status moment, replacing the sync
package's import-time registration as the default occupant of the
``status/adapters.py`` fan-out slots. The design page
(``ephemeral-team-status.html``, CLI column) pins the shape: build the volatile
event via ``spec_kitty_events``, resolve credentials for ``(team, repo)``, then
``ZeitgeistClient.offer("event.publish", ...)`` inside the client's own 750 ms
budget — no retry, no queue, no daemon. ``emit.py`` is untouched; the handlers
are registered into the existing slots by
:func:`specify_cli.status.adapters.ensure_zeitgeist_moment_handlers`.

Three slots, one broadcast core:

* ``fire_saas_fanout`` (WP lane transitions) → ``WPStatusChanged``;
* ``fire_lifecycle_saas_fanout`` (mission lifecycle and decision logs) → the
  volatile subset of those logs' event types
  (:data:`spec_kitty_events.zeitgeist_attrs.VOLATILE_EVENT_TYPES`): mission
  created, the specify/plan/tasks Started and Completed phases, and decision
  points. A local-only field the canonical payload does not declare (a Started
  phase's ``artifact_path``) is projected away here, at the wire boundary, by
  the lifecycle module's own SaaS projection; the persisted event keeps it
  (#4214).
* ``fire_resolved_binding_fanout`` → nothing yet: ``WPResolvedBindingChanged``
  is not part of the volatile vocabulary
  (:data:`spec_kitty_events.zeitgeist_attrs.VOLATILE_EVENT_TYPES`), and
  inventing attrs for it here would put vocabulary where the design says it
  cannot live ("The vocabulary … lives only in spec-kitty-events"). The slot
  is wired anyway, so the moment spec-kitty-events ships a codec for it the
  relay carries binding changes with no further seam work.

Beside every moment this bridge also refreshes the actor's ≤90 s live state
(#186): one ``presence.publish`` frame per broadcast, plus one
``focus.start`` naming ``<mission>.<WP>`` when the moment carries a WP.
The moment stream alone cannot power the live panel — zeitgeist's own
dispatch treats ``event.publish`` as "activity ABOUT a session, never
liveness OF one", publishing one extends nothing's ttl — so without these
frames Team Kitty's presence/focus sections stay empty and GOAL.md's MVP
test ("presence shows the member on that repo/WP") fails. Presence rides
the same stored ``presence``-kind credential the moment used (the kind
grants ``presence.publish``); focus needs the separate ``focus``-kind lease
(:func:`specify_cli.zeitgeist_client.resolution.resolve_focus_capability`)
and stays silent when that mint is unavailable — a focus gap must never
cost a moment.

Who is on a mission-level moment: the relay attests the actor from the
capability credential (the frame's ``actor.user``), and the payload's own
optional ``actor`` rides alongside as an attr when the producer set one —
``emit_mission_created_local`` resolves git ``user.email`` → ``"cli"`` at
emit time (#75), so ``MissionCreated`` carries its WHO. This bridge never
fabricates an actor either way.

Every failure is environmental and every one of them resolves to a logged drop:
the moment is simply lost — by design (design page, "How long anything lives").
Nothing here ever raises into the fan-out, so canonical local persistence is
untouched regardless of relay, credential, or codec state.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from collections.abc import Mapping

from kernel.clock import datetime, now_utc, parse_iso
from pydantic import BaseModel, ValidationError

from spec_kitty_events.models import Event
from spec_kitty_events.status import StatusTransitionPayload
from spec_kitty_events.zeitgeist_attrs import (
    PAYLOAD_MODEL_BY_EVENT_TYPE,
    VOLATILE_EVENT_TYPES,
    ZeitgeistAttrsError,
    to_zeitgeist_attrs,
    zeitgeist_ref_for,
)

from .migrate_lifecycle_envelope import _generate_node_id  # noqa: PLC2701 -- same-package reuse, not a public API

if TYPE_CHECKING:
    from specify_cli.zeitgeist_client.credentials import StoredCredential
    from specify_cli.zeitgeist_client.repo_identity import Deadline
    from specify_cli.zeitgeist_client.transport import OfferResult
    from specify_cli.zeitgeist_client.resolution import FocusLease

logger = logging.getLogger(__name__)

#: What presents itself to the relay in ``ClientConfig.harness``.
_HARNESS_ID = "spec-kitty-cli"

#: The op this handler offers, and the only one it needs a grant for: the
#: capability mint rides the ``presence`` kind, which zeitgeist grants both
#: ``presence.publish`` and ``event.publish`` (zeitgeist ``managed_auth.py``).
_EVENT_PUBLISH_OP = "event.publish"

#: The presence activity this bridge reports. A status transition IS a
#: command (managed_presence.schema.json's enum: ``file_edit`` | ``command``
#: | ``focus``); there is no file edit to name.
_PRESENCE_ACTIVITY: Literal["file_edit", "command"] = "command"

#: ``managed_control.schema.json`` FocusArgs.focus_ref, verbatim: ident-shaped
#: (no ``/``), 64 chars max. A ``<mission>.<WP>`` ref outside this grammar —
#: a long kebab-case mission slug is the realistic case — is a guaranteed
#: 422, so it is filtered here before any attempt instead of being sent to be
#: rejected. (transport.py's docstring cites a wider bound from zeitgeist#38;
#: the canonical schema this programme deploys still enforces 64.)
_FOCUS_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}")


def saas_moment_handler(**kwargs: Any) -> None:
    """Broadcast one WP lane transition as a ``WPStatusChanged`` moment."""
    try:
        _broadcast_status_transition(kwargs)
    except Exception:
        logger.warning(
            "Zeitgeist moment handler failed; canonical status log unaffected",
            exc_info=True,
        )


def lifecycle_moment_handler(**kwargs: Any) -> None:
    """Broadcast one volatile mission-lifecycle moment from the local log envelope."""
    try:
        _broadcast_lifecycle_envelope(kwargs)
    except Exception:
        logger.warning(
            "Zeitgeist lifecycle moment handler failed; canonical lifecycle log unaffected",
            exc_info=True,
        )


def resolved_binding_moment_handler(**kwargs: Any) -> None:
    """Slot wiring for ``WPResolvedBindingChanged`` — no broadcast until a codec exists."""
    logger.debug(
        "Zeitgeist: WPResolvedBindingChanged (wp_id=%s) is not a volatile-family moment; nothing broadcast",
        kwargs.get("wp_id"),
    )


def _broadcast_status_transition(kwargs: Mapping[str, Any]) -> None:
    """Build the ``WPStatusChanged`` payload/envelope pair and offer it once.

    ``metadata`` is duck-typed (the CORE ``WPStatusChangeMetadata`` params
    object) rather than imported, so this module stays decoupled from the
    producer's params type.
    """
    metadata = kwargs.get("metadata")
    mission_slug = kwargs.get("mission_slug")
    evidence = _normalise_evidence(getattr(metadata, "evidence", None))

    # Validated through the model's own schema (like the lifecycle path below):
    # a transition whose fan-out kwargs cannot form a payload is a dropped
    # moment with a logged reason, never a raised error into the seam.
    try:
        payload = StatusTransitionPayload.model_validate(
            {
                "mission_slug": mission_slug,
                "wp_id": kwargs.get("wp_id"),
                "from_lane": kwargs.get("from_lane"),
                "to_lane": kwargs.get("to_lane"),
                "actor": kwargs.get("actor"),
                "force": bool(getattr(metadata, "force", False)),
                "reason": getattr(metadata, "reason", None),
                "execution_mode": getattr(metadata, "execution_mode", None),
                "review_ref": getattr(metadata, "review_ref", None),
                "evidence": evidence,
            }
        )
    except ValidationError as exc:
        logger.warning("Zeitgeist moment WPStatusChanged not broadcast: %s", exc)
        return

    event_id = str(getattr(metadata, "causation_id", None) or uuid.uuid4())
    envelope = Event(
        event_id=event_id,
        event_type="WPStatusChanged",
        aggregate_id=str(mission_slug or kwargs.get("wp_id") or "work-package"),
        payload=payload.model_dump(mode="json"),
        timestamp=_parse_stamp(getattr(metadata, "occurred_at", None)),
        **_envelope_bookkeeping(mission_key=mission_slug or kwargs.get("wp_id"), event_id=event_id),
    )
    # Both fan-out call sites (emit.py, coordination/outbound.py) already hold
    # the emitting checkout root and now pass it through; a caller that omits
    # it (older wiring, direct test calls) falls back to the process working
    # directory, mirroring the lifecycle slot below.
    wp_id = kwargs.get("wp_id")
    focus_wp = (str(mission_slug), str(wp_id)) if mission_slug and wp_id else None
    repo_root = kwargs.get("repo_root")
    cwd = repo_root if isinstance(repo_root, Path) else Path.cwd()
    _broadcast_moment(payload, envelope, cwd=cwd, focus_wp=focus_wp)


def _broadcast_lifecycle_envelope(kwargs: Mapping[str, Any]) -> None:
    """Build the volatile moment carried by one local lifecycle-log envelope.

    Non-volatile lifecycle types (``WPCreated``, ``ProjectInitialized``) are
    logged and skipped: they are not part of the ephemeral vocabulary, and
    fabricating attrs for them is exactly what the design forbids. A volatile
    payload is first projected to its canonical wire shape (a Started phase's
    local-only ``artifact_path`` is dropped, #4214); any other field the
    canonical model does not declare still fails strict validation and drops
    the moment.
    """
    envelope_dict = kwargs.get("envelope")
    if not isinstance(envelope_dict, Mapping):
        return
    event_type = envelope_dict.get("event_type")
    if event_type not in VOLATILE_EVENT_TYPES:
        logger.debug(
            "Zeitgeist: lifecycle event %r is not a volatile-family moment; nothing broadcast",
            event_type,
        )
        return

    # A discriminated-union event type (DecisionPointOpened, DecisionPointResolved)
    # maps to a tuple of variant models rather than one class -- mirrors
    # zeitgeist_attrs._payload_types()'s own normalisation, since that helper
    # is private to the codec module and not exported for reuse here.
    models = PAYLOAD_MODEL_BY_EVENT_TYPE[event_type]
    candidates = models if isinstance(models, tuple) else (models,)
    wire_payload = _wire_lifecycle_payload(str(event_type), envelope_dict.get("payload"))
    payload: BaseModel | None = None
    last_exc: ValidationError | None = None
    for candidate in candidates:
        try:
            payload = candidate.model_validate(wire_payload)
            break
        except ValidationError as exc:
            last_exc = exc
    if payload is None:
        logger.warning("Zeitgeist moment %s not broadcast: %s", event_type, last_exc)
        return

    event_id = str(envelope_dict.get("event_id") or uuid.uuid4())
    aggregate_id = str(envelope_dict.get("aggregate_id") or getattr(payload, "mission_slug", None) or event_type)
    envelope = Event(
        event_id=event_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=payload.model_dump(mode="json"),
        timestamp=_parse_stamp(envelope_dict.get("timestamp")),
        schema_version=str(envelope_dict.get("schema_version") or "3.0.0"),
        **_envelope_bookkeeping(
            mission_key=aggregate_id,
            event_id=event_id,
            project_uuid=envelope_dict.get("project_uuid"),
        ),
    )
    # The append site passes the log path: the mission dir names the checkout
    # the moment was produced in, which beats the process working directory.
    log_path = kwargs.get("log_path")
    _broadcast_moment(payload, envelope, cwd=log_path.parent if isinstance(log_path, Path) else Path.cwd())


def _wire_lifecycle_payload(event_type: str, payload: Any) -> dict[str, Any]:
    """Project a persisted lifecycle payload to its canonical wire shape (#4214).

    Delegates to the lifecycle module's SaaS projection, the one authority on
    which local-only fields leave a lifecycle payload, so the persisted event
    and every local consumer keep them.
    """
    # Local import: the status package imports this bridge while it initialises.
    from .lifecycle_events import _canonical_lifecycle_payload_for_saas  # noqa: PLC0415, PLC2701 -- same-package canonical projection

    projected: dict[str, Any] = _canonical_lifecycle_payload_for_saas(event_type, dict(payload or {}))
    return projected


def _normalise_evidence(evidence: Any) -> Any:
    """Make a local done-evidence bundle validate against the canonical model.

    The local journal treats ``repos`` as optional and omits empty
    (``DoneEvidence.to_dict``), while ``spec_kitty_events.DoneEvidence``
    requires at least one entry — and its transition validator requires
    evidence to be *present* for approved/done lanes, so a review-only done
    transition would otherwise die in payload validation and never reach the
    relay. When repos are missing, fill them with this checkout's identity the
    way ``sync/emitter.py``'s emitter always has (its own fallback is the
    literal "local"/"unknown" triple when git cannot answer). Nothing here
    reaches the wire: evidence is in ``UNBROADCAST_FIELDS``, so attrs never
    carry it; this exists purely so review-only done moments broadcast.
    """
    if not isinstance(evidence, Mapping) or not evidence:
        return evidence
    if evidence.get("repos"):
        return evidence
    return {
        **evidence,
        "repos": [{"repo": "local", "branch": "unknown", "commit": "unknown"}],
    }


def _first_non_printable_attr(attrs: Mapping[str, str]) -> tuple[str, list[str]] | None:
    """Find the first attr value a control-character guard would reject — the
    codec's encode-side guard today, and every consumer's decode always.

    ``to_zeitgeist_attrs`` (spec-kitty-events, pinned 9.1.6) already rejects
    non-printable characters on *encode* — its own
    ``_reject_control_characters`` guard over emitted attrs, using the same
    ``str.isprintable()`` predicate as here — and ``_broadcast_moment`` calls
    it first, inside the try. So on the current pin a non-printable attr is
    caught there as a ``ZeitgeistAttrsControlCharacterError`` and this bridge's
    own pre-check never runs; it is kept as belt-and-braces so a future pin
    that drops the codec's encode-side guard cannot silently reopen the gap.
    Only if such a pin ships does this bridge's message (naming the offending
    key and codepoints) take over from the codec's.
    The check earns its place because free-text decision prose
    (``question``/``options`` on open, ``final_answer``/``rationale`` on
    resolve) is what would carry control characters — a pasted ANSI escape
    sequence is routine — that every consumer's decode would reject. Using the
    same ``str.isprintable()`` predicate turns that otherwise-silent
    decode-side drop into a producer-side warning.
    """
    for key, value in attrs.items():
        bad = sorted({f"U+{ord(ch):04X}" for ch in value if not ch.isprintable()})
        if bad:
            return key, bad
    return None


def _broadcast_moment(
    payload: BaseModel,
    envelope: Event,
    *,
    cwd: Path,
    focus_wp: tuple[str, str] | None = None,
) -> None:
    """Project one volatile payload onto bounded attrs and offer it exactly once.

    Order matters: the codec runs first and credential resolution second, so an
    over-bound payload or an unresolvable credential costs zero network
    attempts — the relay's request log stays empty unless a well-formed moment
    has somewhere to go. When the broadcast carries a WP identity, ``focus_wp``
    is its ``(mission_slug, wp_id)`` pair, naming the focus frame that rides
    along (:func:`_refresh_liveness`).
    """
    event_type = envelope.event_type
    try:
        # The offer attrs are exactly what the codec returns: the wire
        # vocabulary has a single owner (spec_kitty_events.zeitgeist_attrs),
        # so what stays local — ``reason``/``evidence`` prose, unencodable
        # shapes — is decided there and only there.
        attrs = to_zeitgeist_attrs(payload, envelope)
        ref = zeitgeist_ref_for(event_type, payload)
    except ZeitgeistAttrsError as exc:
        logger.warning("Zeitgeist moment %s not broadcast: %s", event_type, exc)
        return

    non_printable = _first_non_printable_attr(attrs)
    if non_printable is not None:
        key, bad_chars = non_printable
        logger.warning(
            "Zeitgeist moment %s not broadcast: attr %r contains non-printable "
            "characters %s (every consumer's from_zeitgeist_attrs decode would "
            "reject this; dropped producer-side instead)",
            event_type,
            key,
            bad_chars,
        )
        return

    # One Git deadline for this whole broadcast: credential resolution,
    # presence's canonical identity, and the focus capability lookup below
    # each used to open their OWN fresh 2.0s `repo_identity.Deadline`,
    # stacking three independent budgets under the fan-out seam's 10s bound
    # (Priivacy-ai/spec-kitty#203). Sharing one here bounds all of this
    # broadcast's Git work to one budget, the same reasoning
    # `repo_identity.identity()`'s own docstring gives for not deriving
    # repo/branch/commit separately.
    from specify_cli.zeitgeist_client import repo_identity  # noqa: PLC0415

    deadline = repo_identity.Deadline()

    credential = _resolve_credentials(cwd, deadline=deadline)
    if credential is None or not credential.session_ref:
        # Not admitted anywhere / nothing configured / Team Kitty unreachable:
        # the MVP's "a repo no team admitted produces nothing anywhere".
        logger.debug("Zeitgeist moment %s not broadcast: no relay credentials", event_type)
        return

    # EventArgs requires session_id on every event frame (the relay derives the
    # actor's opaque session_ref from it); kind/attrs are required too, ref is
    # optional and omitted when the family declares no aggregate field.
    offer_args: dict[str, Any] = {"session_id": credential.session_ref, "kind": event_type, "attrs": attrs}
    if ref:
        offer_args["ref"] = ref
    _offer_and_log(credential, event_type, offer_args)

    # The moment is out; refresh this actor's live presence/focus state under
    # the same credential (no-op when nothing was resolvable above), sharing
    # the same Git deadline this broadcast already opened.
    _refresh_liveness(credential, cwd=cwd, focus_wp=focus_wp, deadline=deadline)


def _log_offer_outcome(label: str, result: OfferResult) -> None:
    """One line per offer attempt, sent or dropped.

    THROTTLED (#180): the relay answered 429 on the single attempt. The
    human-facing signal — the one-line "relay throttled; moment dropped"
    stderr notice — has already been emitted by the client itself; logging
    it again at warning level would print the loss twice, so this stays a
    debug-level structured record.

    rejected / dropped_budget / dropped_unreachable / refused_local: one
    attempt was made (or refused before any socket) and there is no retry,
    no queue — the frame is lost by design (design page, "How long anything
    lives"), so say so once.
    """
    from specify_cli.zeitgeist_client.transport import OfferOutcome  # noqa: PLC0415

    if result.outcome is OfferOutcome.SENT:
        logger.debug("Zeitgeist %s offered (%s) in %.0f ms", label, result.request_id, result.elapsed_s * 1000)
    elif result.outcome is OfferOutcome.THROTTLED:
        logger.debug("Zeitgeist %s throttled (%s) in %.0f ms; dropped", label, result.request_id, result.elapsed_s * 1000)
    else:
        logger.warning("Zeitgeist %s dropped (%s) after %.0f ms; no retry by design", label, result.outcome.value, result.elapsed_s * 1000)


def _offer_and_log(credential: StoredCredential, event_type: str, offer_args: Mapping[str, Any]) -> None:
    """One bounded offer through the typed client, with the outcome logged.

    Imported here, not at module level: the resolution/transport chains pull
    httpx and the urllib machinery, none of which the status package should
    pay for at import time (every CLI start imports this package).
    """
    from specify_cli.zeitgeist_client.transport import ClientConfig, ZeitgeistClient  # noqa: PLC0415

    if not credential.session_ref:
        return
    client = ZeitgeistClient(
        ClientConfig(
            relay_url=credential.relay_url,
            token=credential.token,
            harness=_HARNESS_ID,
            session_id=credential.session_ref,
            agent_id=None,
            # ``repo``/``branch`` feed only the presence/focus ops this handler
            # never sends; filling them would cost a git probe per transition
            # for values no event.publish arg reads.
            repo="",
            branch="",
            capability_credential=credential.capability_credential,
        )
    )
    _log_offer_outcome(f"moment {event_type}", client.offer(_EVENT_PUBLISH_OP, dict(offer_args)))


def _refresh_liveness(
    credential: StoredCredential,
    *,
    cwd: Path,
    focus_wp: tuple[str, str] | None,
    deadline: Deadline,
) -> None:
    """Refresh the actor's ≤90 s live state beside a broadcast moment (#186).

    The moment alone cannot power Team Kitty's live panel — zeitgeist treats
    ``event.publish`` as activity *about* a session that extends nothing's
    ttl — so GOAL.md's "presence shows the member on that repo/WP" needs this
    bridge to also publish liveness frames under the same credential:

    * always one ``presence.publish`` (kind ``command``, git-truth repo and
      branch via ``ClientConfig.for_repository`` — the Z6-C sanctioned
      constructor, so presence cannot be bound to a spoofed checkout);
    * when the broadcast carries a WP identity, one ``focus.start`` naming
      ``mission.wp``. Focus ops need the separate ``focus``-kind
      capability lease (:func:`specify_cli.zeitgeist_client.resolution.
      resolve_focus_capability`); when that mint is unavailable or denied the
      frame is skipped at debug level — a focus gap must never cost a moment,
      and neither failure may write a negative answer over the shared store
      entry.

    ``deadline`` is the ``repo_identity.Deadline`` this broadcast already
    opened for credential resolution — threaded through here and into the
    focus lookup below so this whole broadcast shares one Git budget
    (Priivacy-ai/spec-kitty#203) rather than each stage opening its own.

    Same fire-and-forget discipline as the moment: drop-no-retry per frame,
    every failure logged and swallowed here so the fan-out slot stays
    non-raising regardless of git, relay, or credential state.
    """
    try:
        _refresh_liveness_bounded(credential, cwd=cwd, focus_wp=focus_wp, deadline=deadline)
    except Exception:
        logger.warning("Zeitgeist presence/focus refresh failed; canonical status log unaffected", exc_info=True)


def _refresh_liveness_bounded(
    credential: StoredCredential,
    *,
    cwd: Path,
    focus_wp: tuple[str, str] | None,
    deadline: Deadline,
) -> None:
    """The network half of :func:`_refresh_liveness` — imports + git + offers."""
    from specify_cli.zeitgeist_client import repo_identity  # noqa: PLC0415
    from specify_cli.zeitgeist_client.transport import ClientConfig, ZeitgeistClient  # noqa: PLC0415

    if not credential.session_ref:
        return
    try:
        config = ClientConfig.for_repository(
            str(cwd),
            relay_url=credential.relay_url,
            token=credential.token,
            harness=_HARNESS_ID,
            session_id=credential.session_ref,
            agent_id=None,
            capability_credential=credential.capability_credential,
            deadline=deadline,
        )
    except repo_identity.RepoIdentityError as exc:
        logger.debug("Zeitgeist presence not published: no canonical checkout identity (%s)", exc)
        return

    _log_offer_outcome("presence", ZeitgeistClient(config).presence(_PRESENCE_ACTIVITY))

    if focus_wp is None:
        return
    mission_slug, wp_id = focus_wp
    composed = f"{mission_slug}.{wp_id}"
    if not _FOCUS_REF_RE.fullmatch(composed):
        # Zero-attempt discipline, same as the sanitizer gate: a ref outside
        # FocusArgs' grammar is a guaranteed 422; skipping beats sending a
        # frame built to be rejected. Presence above already went out.
        logger.debug("Zeitgeist focus ref %r does not fit the relay's focus_ref grammar; focus frame skipped", composed)
        return

    capability = _resolve_focus_capability(cwd, deadline=deadline)
    if capability is None:
        logger.debug("Zeitgeist focus frame %s not published: no focus-kind capability", composed)
        return

    # Focus uses its own capability and issuer-owned session reference.
    focus_config = replace(config, capability_credential=capability.capability_credential, session_id=capability.session_ref)
    _log_offer_outcome(f"focus.start {composed}", ZeitgeistClient(focus_config).focus_start(mission_slug, wp_id))


def _resolve_focus_capability(cwd: Path, *, deadline: Deadline) -> FocusLease | None:
    """The checkout's focus capability and raw session ID, or ``None``.

    ``deadline`` shares this broadcast's one Git budget
    (Priivacy-ai/spec-kitty#203) instead of letting this lookup open its
    own fresh one. Imported here for the same reason as every other
    transport-chain import: resolution pulls httpx, which the status package
    must not pay for at import time.
    """
    from specify_cli.zeitgeist_client.resolution import resolve_focus_lease  # noqa: PLC0415

    return resolve_focus_lease(cwd, deadline=deadline)


def _resolve_credentials(cwd: Path, *, deadline: Deadline) -> StoredCredential | None:
    """Credentials for this checkout's team relay, or ``None`` to stay silent.

    Delegates entirely to E3's resolver (#9): cached store answer, else one
    admission pre-flight + capability mint against Team Kitty, else a stored
    negative answer. Every way it can fail resolves to ``None`` plus its own
    debug log — none of them raise here. ``deadline`` shares this
    broadcast's one Git budget (Priivacy-ai/spec-kitty#203) rather than
    opening a fresh one here.
    """
    from specify_cli.zeitgeist_client.resolution import resolve_credentials  # noqa: PLC0415

    return resolve_credentials(cwd, deadline=deadline)


def _parse_stamp(raw: Any) -> datetime:
    """Producer occurrence time as a datetime, falling back to now.

    A missing/unparseable stamp must not drop the moment: the envelope's
    ``timestamp`` becomes the ``occurred_at`` attr, and a stamp we cannot read
    is replaced by the emission clock rather than losing the broadcast (Rule
    R-T-01 preserves *real* producer stamps end-to-end; this only covers their
    absence).
    """
    if isinstance(raw, str) and raw.strip():
        try:
            return parse_iso(raw)
        except (ValueError, TypeError):
            logger.debug("Zeitgeist: unparseable occurrence stamp %r; using emission clock", raw)
    return now_utc()


def _envelope_bookkeeping(*, mission_key: Any, event_id: str, project_uuid: Any = None) -> dict[str, Any]:
    """Synthesize the strict envelope's causal keys that moments do not carry.

    The attrs codec reads exactly ``event_id``/``timestamp``/``event_type`` off
    the envelope; the strict ``Event`` model still requires the causal keys, so
    they are synthesized deterministically and never reach the wire:

    * ``node_id`` — the repo-standard machine identity (hostname:user hash);
    * ``lamport_clock`` — ``0``, the "no causal order recorded" sentinel the
      local lifecycle journal already uses;
    * ``project_uuid``/``build_id`` — the real project UUID when the lifecycle
      log recorded one, else a deterministic UUID5 of the mission key, with
      ``build_id`` derived from it exactly as
      :func:`specify_cli.identity.project.derive_build_id` does elsewhere;
    * ``correlation_id`` — the moment's own ``event_id`` (the repo's standard
      root-event convention); ``causation_id`` stays ``None``.
    """
    from specify_cli.identity.project import derive_build_id  # noqa: PLC0415

    node_id = _generate_node_id()
    resolved_uuid = _coerce_uuid(project_uuid) or uuid.uuid5(uuid.NAMESPACE_URL, f"urn:spec-kitty:mission:{mission_key}")
    return {
        "node_id": node_id,
        "lamport_clock": 0,
        "project_uuid": resolved_uuid,
        "build_id": derive_build_id(resolved_uuid, node_id),
        "correlation_id": event_id,
        "causation_id": None,
    }


def _coerce_uuid(raw: Any) -> uuid.UUID | None:
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return uuid.UUID(raw)
        except ValueError:
            logger.debug("Zeitgeist: unparseable project_uuid %r; synthesizing", raw)
    return None


__all__ = [
    "lifecycle_moment_handler",
    "resolved_binding_moment_handler",
    "saas_moment_handler",
]
