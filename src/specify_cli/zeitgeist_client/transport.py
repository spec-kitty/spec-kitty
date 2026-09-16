"""The one typed client service (Z1.md §3.2 item 8).

``ZeitgeistClient.offer()`` implements "one-offer-after-append,
750ms/drop-no-retry, forbidden-field zero-attempt" exactly: (1) build the
request_id; (2) ``sanitizer.assert_clean(args)`` — any forbidden key raises
before any network attempt, yielding ``REFUSED_LOCAL``, ``elapsed_s=0.0``;
(3) exactly one HTTP POST, to ``<relay_url>/managed/control`` (F3's real
presence/focus/session op dispatcher — ``zeitgeist/managed.py`` — never the
baseline ``/events`` Beacon route, which has no ``op`` dispatch at all and
structurally cannot process a ``ControlEnvelope``), under a 750ms TOTAL
wall-clock deadline (``budget.run_with_deadline``); (4) whatever happens —
2xx, non-2xx, timeout, connection refused — ``offer()`` returns; it never
retries and never queues. This is binding, not incidental:
``decisions/HIC-EPHEMERAL-TEAM-STATUS-2026-08-25.md`` (decision C) and
``design/ephemeral-team-status.html`` both pin "no retry" / "≤750 ms" — "a
relay outage or a 750 ms CLI timeout loses the moment by design."

Refinement, not an exception (#180): a ``429`` from the relay is not an
ordinary rejection — zeitgeist's managed-control rate limiter answers a
throttled credential with ``429`` + ``Retry-After: <s>`` + a JSON detail
(zeitgeist#44). ``offer()`` still makes exactly one attempt — no pause, no
second POST — but classifies a 429 as :attr:`OfferOutcome.THROTTLED` instead
of folding it into a bare ``REJECTED``, and prints the one-line stderr notice
:data:`THROTTLE_NOTICE` — the signal a bare ``REJECTED`` never gave — so end
to end a throttled moment is lost loudly, not silently, while still being
lost on the first answer exactly like every other non-2xx status.

FIX-M2-10: two gates a real relay enforces on this route, both of which
``offer()`` must satisfy — confirmed against the live ``zeitgeist`` source
(``zeitgeist/auth.py``'s ``AuthenticationMiddleware`` — every route but
``/health``, ``/managed/control`` included — plus ``zeitgeist/managed.py``'s
own ``_extract_identity``), not against this module's own double:

1. ``Authorization: Bearer <token>`` — the outer, unconditional
   ``AuthenticationMiddleware`` gate every route sits behind.
2. ``X-Zeitgeist-Capability: <token>`` — ``managed.py``'s own capability
   check, verified by ``managed_auth.py`` against a *different* secret
   (``ZEITGEIST_CAPABILITY_KEY``) than the shared ``ZEITGEIST_TOKEN``
   ``AuthenticationMiddleware`` checks.

FIX-M2-15 (supersedes the FIX-M2-10 paragraph this replaces): a real
SaaS-provisioned per-team relay (``apps.live_capability.
provisioning_docker.DockerProvisioningDriver.provision`` —
``ZEITGEIST_TOKEN``/``ZEITGEIST_CAPABILITY_KEY`` minted as two
INDEPENDENT, unrelated secrets) makes both gates checking the SAME value
the exception, not the rule — DQA-M2-05's own real-container walkthrough
reproduced, by hand, that the pre-fix "one credential, two headers" model
below gets a genuine ``401``/``403`` against exactly that recipe (a
capability JWT presented as ``Authorization`` fails the outer gate; the
shared token presented as ``X-Zeitgeist-Capability`` fails
``managed_auth.py``'s HMAC check). ``ClientConfig`` therefore carries TWO
independent credential fields: ``token`` (``Authorization: Bearer
<token>`` — the deployment's shared bearer, Z1.md §3.2 item 7's original
field, unrenamed so every existing caller/config keeps working) and the
new ``capability_credential`` (``X-Zeitgeist-Capability: <capability_
credential>`` — a per-actor capability JWT, e.g. one
``apps.live_capability.relay_auth.mint_relay_token`` signed). Precedence:
when ``capability_credential`` is configured (non-``None``), each header
carries its OWN value; when it is ``None`` (the default — every config
written before this fix, and every self-hosted single-secret deployment
that still hands out one value for both gates), ``offer()`` falls back to
``token`` for BOTH headers, exactly this module's original FIX-M2-10
behaviour, unchanged. ``credentials.py``'s ``StoredCredential`` gained the
identically-named, identically-optional ``capability_credential`` field
this same fallback is threaded through from (see that module's own
docstring); ``spec-kitty-saas``'s member-facing credential-issuance
endpoint (``apps.live_capability.views.mint_cli_credential``, FIX-M2-15)
is what now hands a real team member the ``relay_url``/``relay_token``/
``capability_credential`` triple this checkout shape is built to receive.
Z1's own not-yet-built ``checkout`` flow (item 5,
``docs/plans/zeitgeist-client-wp01-remaining.md``) is expected to persist
whatever it receives through exactly this fallback-aware field, never a
second credential store.

Known scope reduction vs. the full Z1.md §3.2 item 8 contract (recorded
honestly, not silently): step 3 of the draft ("validator.validate
('managed_control', envelope)") is NOT implemented in this pass —
``validator.py`` and the bundled F1/F3 schema copies do not exist yet (F1-T1/
F3-T1 have not landed as producer candidates in their own repos to pin
digests against, per Z1.md §3.5's "cannot freeze before both exist"). offer()
currently performs only the sanitizer gate before its one network attempt.
``watch()``/``status()`` are not implemented (``NotImplementedError``) — see
``docs/plans/zeitgeist-client-wp01-remaining.md`` for the full remaining list.

``focus_start``/``_heartbeat``/`_pause``/`_end`` build ``focus_ref``
themselves (Z1.md §3.2 item 8, F1's normative derivation clause):
``focus_ref = mission_slug if wp_id is None else f"{mission_slug}.{wp_id}"``.

FIX-M2-10: the separator is ``.``, not the ``/`` F1's draft clause used —
confirmed against the live source, ``managed_control.schema.json``'s
``FocusArgs.focus_ref`` (and ``managed_live.schema.json``'s egress copy) is
ident-shaped in CHARACTER CLASS only (``[A-Za-z0-9][A-Za-z0-9._@+-]``: no
``/``, ``re.fullmatch`` enforced by ``capabilities.py``'s hand-rolled
validator — never a partial/substring match), not the ref-shaped
(``/``-permitting) grammar this module's own docstring and
``live_frame.py``'s read-side comment both assumed. The length bound is NOT
the ident one: zeitgeist#38 widened it from 64 to 240 (pattern quantifier
``{0,63}`` → ``{0,239}``, ``maxLength`` 64 → 240, class unchanged) once
real ``mission_slug.WPxx`` refs outgrew the ident envelope — this module
already sends the full ``f"{mission_slug}.{wp_id}"``, so nothing here
clamps, and neither field may be re-tightened to 64 to agree with a
pre-#38 comment. A ``/``-joined
``focus_ref`` therefore failed real schema validation (422) on every single
``focus.start``/``.heartbeat``/``.pause``/``.end`` call whenever a caller
passed ``wp_id`` — invisible to this module's own test double (which never
schema-validated ``args``) and only surfaced against a real container.
``focus_ref`` is opaque everywhere it is consumed (a dict key server- and
client-side, never split back into its parts — confirmed by grep across
both repos), so the join character itself carries no meaning beyond
producing a value the real schema accepts; ``.`` was chosen over the
schema's other permitted separators (``_``/``@``/``+``/bare ``-``) because
it reads cleanly against spec-kitty's own kebab-case mission slugs
(``034-feature-status-model.WP01``, not
``034-feature-status-model-WP01``). ``live_frame.py``'s read side is
unaffected: it already routes ``focus_ref`` through the strictly WIDER
``grammar.REF_RE`` (permits ``/`` in addition to everything ident-shaped
allows), so every ident-shaped value this fix now sends still parses
unchanged.
``focus_end``'s ``reason`` is deliberately restricted to ``user``/``timeout``
at both the type boundary and a runtime guard — ``revoked`` is a
server-originated ``LiveFrame.signal`` outcome the client can only observe,
never claim (Z1.md decision 6, N12).

``ClientConfig.for_repository`` (Z6-C) is an additive, stricter constructor:
it derives ``repo``/``branch`` from ``repo_identity.identity()`` — the
checkout's actual git truth — instead of accepting them as a bare caller
claim, so presence bound through it cannot be spoofed to a different
project. The plain ``ClientConfig(...)`` constructor is unchanged; Z1.md
decision 7 ("caller fields are claims only") still governs it.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import threading
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from kernel.clock import datetime, now_utc

from . import budget, repo_identity, sanitizer

# ≤90s current-focus bound (O1-C's operability drills exercise this
# denominator; Z1 owns the constant, Z1.md §1 "downstream criteria").
FOCUS_TTL_S = 90

# F3's real presence/focus/session op dispatcher (zeitgeist/managed.py),
# never the baseline Beacon route (`/events`) — see the module docstring.
_MANAGED_CONTROL_PATH = "/managed/control"

# `managed_control.schema.json`'s own `properties.schema_version.pattern`
# ("1.x.y") and top-level `"version"` (zeitgeist/zeitgeist/schemas/
# managed_control.schema.json) — a literal, not an import: zeitgeist is a
# separate, git-ignored sibling repo with no package dependency in either
# direction (same reason spec-kitty-saas's `relay.py` re-derives its own
# `_SCHEMA_VERSION` literal rather than importing one). Bump only in
# lockstep with a real, coordinated envelope-shape change on zeitgeist's
# side.
_SCHEMA_VERSION = "1.0.0"

# The status zeitgeist's managed-control rate limiter answers with (`429` +
# `Retry-After: <s>` + JSON detail, zeitgeist#44). No retry is made on it —
# decisions/HIC-EPHEMERAL-TEAM-STATUS-2026-08-25.md forbids one — it is only
# classified distinctly from an ordinary REJECTED so the loss is loud.
_THROTTLED_STATUS = 429

# managed_control.schema.json's ControlEnvelope.request_id pattern — the
# grammar a caller-supplied stable id (#4269) must satisfy before any
# network attempt is made.
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}")

# The one-line stderr notice emitted when the single attempt comes back
# throttled (#180: "lost silently" → lost loudly).
THROTTLE_NOTICE = "relay throttled; moment dropped"

_FocusPauseReason = Literal["user", "dnd"]
_FocusEndReason = Literal["user", "timeout"]
_PresenceActivity = Literal["file_edit", "command"]

_VALID_PAUSE_REASONS = frozenset({"user", "dnd"})
_VALID_END_REASONS = frozenset({"user", "timeout"})
_VALID_PRESENCE_ACTIVITIES = frozenset({"file_edit", "command"})


@dataclass(frozen=True)
class ClientConfig:
    relay_url: str  # local/Docker-hosted only; written only by the checkout() canary-offer flow and E3 credential resolution (mint)
    token: str
    harness: str
    session_id: str
    agent_id: str | None
    repo: str
    branch: str
    # FIX-M2-15: the X-Zeitgeist-Capability credential, independent of
    # `token` (Authorization) -- see the module docstring's FIX-M2-15 note.
    # `None` (the default) means "no second credential configured": offer()
    # falls back to `token` for BOTH headers, exactly the original
    # FIX-M2-10 single-credential behaviour -- every config/call site that
    # predates this field keeps working unchanged.
    capability_credential: str | None = None

    @classmethod
    def for_repository(
        cls,
        cwd: str,
        *,
        relay_url: str,
        token: str,
        harness: str,
        session_id: str,
        agent_id: str | None = None,
        capability_credential: str | None = None,
        budget_s: float = repo_identity.GIT_BUDGET_S,
        deadline: repo_identity.Deadline | None = None,
    ) -> ClientConfig:
        """The sanctioned, non-spoofable constructor (Z6-C): ``repo``/
        ``branch`` come from ``repo_identity.identity(cwd)`` — the checkout's
        actual git truth — rather than from a caller-supplied claim. Raises
        ``repo_identity.RepoIdentityError`` (``AmbiguousRepositoryIdentity``/
        ``UnverifiedRepositoryIdentity``) instead of constructing a
        ``ClientConfig`` whose ``.repo`` could be spoofed to a different
        project.

        The bare dataclass constructor above is unaffected: Z1.md decision 7
        ("caller fields are claims only") still governs direct
        ``ClientConfig(...)`` construction (existing callers, tests). This is
        an additive, stricter alternative for a caller (the not-yet-built CLI
        adapter) that needs presence bound to the checkout's canonical
        identity rather than a claim it merely trusts.

        Pass ``deadline`` to share a caller's already-open Git budget (e.g.
        the same one credential resolution and a focus-capability lookup are
        using in the same handler invocation) instead of allocating a fresh
        ``budget_s`` here — see ``repo_identity.identity``'s own ``deadline``
        parameter (Priivacy-ai/spec-kitty#203).
        """
        ident = repo_identity.identity(cwd, budget=budget_s, deadline=deadline)
        return cls(
            relay_url=relay_url,
            token=token,
            harness=harness,
            session_id=session_id,
            agent_id=agent_id,
            repo=ident.repo,
            branch=ident.branch,
            capability_credential=capability_credential,
        )


class OfferOutcome(StrEnum):
    SENT = "sent"  # relay accepted (2xx)
    REJECTED = "rejected"  # relay returned a non-throttle 4xx/5xx
    THROTTLED = "throttled"  # relay answered 429 on the one attempt (#180)
    DROPPED_BUDGET = "dropped_budget"  # 750ms elapsed before a response
    DROPPED_UNREACHABLE = "dropped_unreachable"  # connect/DNS failure
    REFUSED_LOCAL = "refused_local"  # sanitizer rejected before any socket call


@dataclass(frozen=True)
class OfferResult:
    outcome: OfferOutcome
    request_id: str  # ControlEnvelope.request_id (idempotency key)
    elapsed_s: float  # 0.0 for REFUSED_LOCAL — no network attempt was made
    status_code: int | None = None  # HTTP response status; None when no response arrived
    response_detail: str | None = None  # bounded, credential-redacted relay detail


_RESPONSE_READ_BYTES = 8192
_RESPONSE_DETAIL_CHARS = 512
_SENSITIVE_RESPONSE_VALUE = re.compile(r'(?i)("(?:authorization|token|credential|bearer)"\s*:\s*")[^"]*(")')
_BEARER_VALUE = re.compile(r"(?i)(\bbearer\s+)[^\s,;\"']+")


def _safe_response_detail(body: bytes, *, secrets_to_redact: tuple[str, ...]) -> str | None:
    """Extract one bounded diagnostic without retaining client credentials."""
    if not body:
        return None
    raw = body[:_RESPONSE_READ_BYTES]
    text = raw.decode("utf-8", errors="replace")
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        detail = text
    else:
        if isinstance(decoded, dict):
            decoded = next(
                (decoded[key] for key in ("detail", "error", "message") if key in decoded),
                decoded,
            )
        detail = decoded if isinstance(decoded, str) else json.dumps(decoded, ensure_ascii=False, separators=(",", ":"))

    for secret in sorted((value for value in secrets_to_redact if value), key=len, reverse=True):
        detail = detail.replace(secret, "[redacted]")
    detail = _SENSITIVE_RESPONSE_VALUE.sub(r"\1[redacted]\2", detail)
    detail = _BEARER_VALUE.sub(r"\1[redacted]", detail)
    detail = " ".join(detail.split())
    if not detail:
        return None
    if len(detail) > _RESPONSE_DETAIL_CHARS:
        return detail[: _RESPONSE_DETAIL_CHARS - 1] + "…"
    return detail


def _classify_network_error(exc: BaseException) -> OfferOutcome:
    reason: BaseException = exc
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason if isinstance(exc.reason, BaseException) else exc
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return OfferOutcome.DROPPED_BUDGET
    return OfferOutcome.DROPPED_UNREACHABLE


class ZeitgeistClient:
    """The single typed client. Owns no team/identity/permission logic — see
    module docstring and Z1.md decision 7: caller fields are claims only."""

    def __init__(self, config: ClientConfig):
        self._config = config
        self._focus_ref: str | None = None
        self._focus_started_at: datetime | None = None
        self._lock = threading.Lock()

    # -- read-only lease state (O1-C's operability report reads this) ---

    def focus_lease(self) -> tuple[str | None, datetime | None]:
        """The current ``focus_ref`` and when it started, if any — Z1's own
        in-process state, read-only and payload-free (no relay_url/token
        accompanies it). ``(None, None)`` whenever no focus is active."""
        with self._lock:
            return self._focus_ref, self._focus_started_at

    # -- the primitive ------------------------------------------------

    def offer(self, op: str, args: Mapping[str, Any], *, request_id: str | None = None) -> OfferResult:
        # A caller-supplied request_id is #4269's stable-contribution-id
        # primitive: the relay's replay cache dedupes on (scope, request_id),
        # so a bounded retry that re-offers the SAME id is idempotent
        # server-side (a replayed id returns the original 202 and never
        # re-executes). The id must satisfy the envelope's own grammar —
        # validated here, before any network attempt, so a malformed one is
        # a local refusal rather than a relay 422. None keeps the original
        # per-call uuid4: every pre-#4269 caller keeps its exact behavior.
        if request_id is None:
            request_id = str(uuid.uuid4())
        elif not _REQUEST_ID_RE.fullmatch(request_id):
            raise ValueError("request_id must match [A-Za-z0-9][A-Za-z0-9._@+-]{0,63} (the relay ControlEnvelope's own grammar)")

        try:
            sanitizer.assert_clean(args)
        except sanitizer.ForbiddenFieldError:
            return OfferResult(outcome=OfferOutcome.REFUSED_LOCAL, request_id=request_id, elapsed_s=0.0)

        envelope = {
            "schema_version": _SCHEMA_VERSION,
            "op": op,
            "request_id": request_id,
            "args": dict(args),
        }
        body = json.dumps(envelope).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            # Two independent gates, each with its OWN credential — see the
            # module docstring's FIX-M2-15 note. `capability_credential`
            # falls back to `token` when unset, so a single-credential
            # config still presents the same value to both gates.
            "Authorization": f"Bearer {self._config.token}",
            "X-Zeitgeist-Capability": self._config.capability_credential or self._config.token,
        }
        url = self._config.relay_url.rstrip("/") + _MANAGED_CONTROL_PATH

        def _post() -> tuple[int, bytes]:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with budget.open_bounded(req, timeout=budget.OFFER_BUDGET_S) as resp:
                    return int(resp.status), resp.read(_RESPONSE_READ_BYTES + 1)
            except urllib.error.HTTPError as exc:
                return exc.code, exc.read(_RESPONSE_READ_BYTES + 1)

        outcome = budget.run_with_deadline(_post, deadline_s=budget.OFFER_BUDGET_S)
        elapsed_s = outcome.elapsed_s
        if not outcome.completed:
            drop: OfferOutcome | None = OfferOutcome.DROPPED_BUDGET
            status = 0
            response_body = b""
        elif outcome.error is not None:
            drop = _classify_network_error(outcome.error)
            status = 0
            response_body = b""
        else:
            assert outcome.result is not None  # completed without error ⇒ a result
            drop = None
            status, response_body = outcome.result

        if drop is not None:
            return OfferResult(outcome=drop, request_id=request_id, elapsed_s=elapsed_s)
        response_detail = _safe_response_detail(
            response_body,
            secrets_to_redact=(
                self._config.token,
                self._config.capability_credential or self._config.token,
            ),
        )
        if status == _THROTTLED_STATUS:
            print(THROTTLE_NOTICE, file=sys.stderr)
            return OfferResult(
                outcome=OfferOutcome.THROTTLED,
                request_id=request_id,
                elapsed_s=elapsed_s,
                status_code=status,
                response_detail=response_detail,
            )
        result_outcome = OfferOutcome.SENT if 200 <= status < 300 else OfferOutcome.REJECTED
        return OfferResult(
            outcome=result_outcome,
            request_id=request_id,
            elapsed_s=elapsed_s,
            status_code=status,
            response_detail=response_detail,
        )

    # -- current-focus lifecycle (opt-in) ------------------------------

    def _claim_args(self, **extra: Any) -> dict[str, Any]:
        args: dict[str, Any] = {"session_id": self._config.session_id}
        # Claims ride only when git actually answered them (#186 wiring made
        # this path live): managed_control.schema.json's FocusArgs and
        # managed_presence.schema.json's PresencePublish both pattern
        # repo/branch with a >=1-char head, so an EMPTY-string claim present
        # as a key is a guaranteed 422 on every op -- not an omission. A
        # detached HEAD (or a spent git budget) yields branch "" from
        # repo_identity.branch_name; the honest wire shape for "no branch to
        # claim" is the key's absence.
        if self._config.repo:
            args["repo"] = self._config.repo
        if self._config.branch:
            args["branch"] = self._config.branch
        args.update(extra)
        return args

    def focus_start(self, mission_slug: str, wp_id: str | None = None) -> OfferResult:
        with self._lock:
            if self._focus_ref is not None:
                return OfferResult(
                    outcome=OfferOutcome.REFUSED_LOCAL,
                    request_id=str(uuid.uuid4()),
                    elapsed_s=0.0,
                )
            # FIX-M2-10: "." not "/" — see the module docstring's FIX-M2-10
            # note. managed_control.schema.json's FocusArgs.focus_ref is
            # ident-shaped (no "/" in its character class); a "/"-joined
            # value fails real schema validation (422) on every focus op.
            focus_ref = mission_slug if wp_id is None else f"{mission_slug}.{wp_id}"
            self._focus_ref = focus_ref
            self._focus_started_at = now_utc()
        return self.offer("focus.start", self._claim_args(focus_ref=focus_ref, ttl_s=FOCUS_TTL_S))

    def focus_heartbeat(self) -> OfferResult:
        focus_ref = self._focus_ref
        if focus_ref is None:
            return OfferResult(outcome=OfferOutcome.REFUSED_LOCAL, request_id=str(uuid.uuid4()), elapsed_s=0.0)
        # FIX-M2-10: FocusArgs (managed_control.schema.json) REQUIRES ttl_s
        # on every non-end focus op, not just focus.start — a heartbeat with
        # no ttl_s is both schema-invalid (422) and functionally inert:
        # managed.py's focus_op() computes the refreshed
        # expires_at = received_at + args["ttl_s"] for start/heartbeat/pause
        # alike, so omitting it also silently failed to renew the server-
        # side TTL a heartbeat exists to renew.
        return self.offer("focus.heartbeat", self._claim_args(focus_ref=focus_ref, ttl_s=FOCUS_TTL_S))

    def focus_pause(self, reason: _FocusPauseReason = "user") -> OfferResult:
        if reason not in _VALID_PAUSE_REASONS:
            raise ValueError(f"focus_pause reason must be one of {sorted(_VALID_PAUSE_REASONS)!r}, got {reason!r}")
        focus_ref = self._focus_ref
        if focus_ref is None:
            return OfferResult(outcome=OfferOutcome.REFUSED_LOCAL, request_id=str(uuid.uuid4()), elapsed_s=0.0)
        # FIX-M2-10: FocusArgs has no `pause_reason` property at all
        # (additionalProperties: false) — zeitgeist's own focus_op() never
        # reads a pause reason either (op == "focus.pause" only ever sets
        # state="paused", uninspected by why). `reason` therefore stays a
        # LOCAL, client-side-only distinction (validated above, never
        # dropped from the method's own contract) — it was never a wire
        # field to omit correctly; sending it as one was the bug (422,
        # unknown key). ttl_s IS required here, same reasoning as
        # focus_heartbeat above.
        return self.offer("focus.pause", self._claim_args(focus_ref=focus_ref, ttl_s=FOCUS_TTL_S))

    def focus_end(self, reason: _FocusEndReason = "user") -> OfferResult:
        # Runtime guard, not just a type hint: "revoked" is a server-originated
        # LiveFrame.signal outcome (F1's rev-2 fix) — the client must be
        # structurally incapable of claiming it, including via an MCP/JSON
        # caller that bypasses static typing (Z1.md decision 6, N12).
        if reason not in _VALID_END_REASONS:
            raise ValueError(
                f"focus_end reason must be one of {sorted(_VALID_END_REASONS)!r}, got {reason!r} "
                "— 'revoked' is a server-originated outcome the client can only observe "
                "via watch(), never claim"
            )
        with self._lock:
            focus_ref = self._focus_ref
            self._focus_ref = None
            self._focus_started_at = None
        if focus_ref is None:
            return OfferResult(outcome=OfferOutcome.REFUSED_LOCAL, request_id=str(uuid.uuid4()), elapsed_s=0.0)
        # FIX-M2-10: FocusEndArgs.required includes ttl_s too (schema
        # symmetry with FocusArgs) even though managed.py's own focus.end
        # handling never reads it (the entry is simply popped) — still
        # required to pass schema validation before dispatch.
        return self.offer(
            "focus.end",
            self._claim_args(focus_ref=focus_ref, ttl_s=FOCUS_TTL_S, ended_reason=reason),
        )

    # -- presence (independent of focus/DND state, Z1.md decision 9) ---

    def presence(self, activity: _PresenceActivity, path: str | None = None) -> OfferResult:
        if activity not in _VALID_PRESENCE_ACTIVITIES:
            raise ValueError(f"presence activity must be one of {sorted(_VALID_PRESENCE_ACTIVITIES)!r}, got {activity!r}")
        # FIX-M2-10: PresencePublish's wire field is `kind` (managed_
        # presence.schema.json — additionalProperties: false, no `activity`
        # property at all; managed.py's publish_presence() reads
        # `args["kind"]`, never `args["activity"]`) — `activity` is this
        # method's own PARAMETER name (public API, unchanged), not the wire
        # key it must be sent under.
        args = self._claim_args(kind=activity)
        if path is not None:
            args["path"] = path
        return self.offer("presence.publish", args)

    # -- not yet implemented in this pass -------------------------------

    def status(self) -> None:
        raise NotImplementedError("ZeitgeistClient.status() is not implemented in this pass — see docs/plans/zeitgeist-client-wp01-remaining.md")

    def watch(self, *, idle_timeout_s: float | None = None) -> None:
        raise NotImplementedError("ZeitgeistClient.watch() is not implemented in this pass — see docs/plans/zeitgeist-client-wp01-remaining.md")
