"""Z4-C: parsing and local, honest-reported-live application of F3's managed
``LiveFrame`` wire shape (``m1-contract-drafts/`` ``managed_live.schema.json``
— ``$id: urn:zeitgeist:schema:managed_live:1``).

This module is pure logic: no sockets, no relay knowledge. The network half
(one SSE connection per team-bound subscription) lives in ``filtered_stream``,
which calls ``parse_live_frame`` on every ``data:`` line and feeds the result
into one ``StreamState`` per subscription.

Known, honestly-recorded scope reduction (same category Z1-T1's own
``transport.py`` docstring already recorded for the control-envelope path):
``parse_live_frame`` checks exactly the wire-shape fields this module reads
in order to apply a frame safely — required top-level keys, the
``schema_version`` major (rejecting any wire version this module was not
written against), the ``frame.type`` discriminator, and the handful of typed
fields ``StreamState`` consumes. It is NOT a general JSON-Schema validator
run against the bundled ``managed_live.schema.json`` document with a pinned
digest (that is ``validator.py``, still not landed per
``docs/plans/zeitgeist-client-wp01-remaining.md`` item 1 — F1-T1/F3-T1 landed
as *producer candidates in their own repos*, not yet imported/pinned here).
A frame this module cannot make sense of is dropped, never crashes the watch
loop and never raises — the same "fail closed, stay silent" posture
``sanitizer.assert_clean`` uses on the outbound side.

Reported-live honesty, not reconstruction:

* ``epoch`` changing between two frames (the relay restarted — F3's own
  N16 contract: a fresh process mints a fresh epoch and resets ``seq``) and
  an explicit ``signal.kind in {"gap", "epoch"}`` frame both mean the same
  thing to this module: local state is no longer known to be accurate, so it
  is cleared outright. Z4-C's node criterion is "no missed-event
  reconstruction" — there is no attempt to patch, diff, or partially trust
  what came before; the client is simply, honestly ignorant of the window it
  could not see, until fresh frames rebuild a view.
* ``signal.kind == "revoked"`` is scoped: only the named ``session_ref``'s
  presence/focus entries are removed, matching the relay's own
  ``session_revoke`` scoping (F3 N30).
* An ``event`` frame (E1's status moment, Priivacy-ai/spec-kitty#10) is
  accepted — before #10 it was silently dropped by the ``frame.type``
  discriminator, so a watch could never show the moment the demo path turns
  on — but it is the one frame type that leaves no trace in ``StreamState``
  (see ``_apply_event``): it is delivered live to watchers, never retained.
* A ``focus`` frame with ``state == "ended"`` is dropped immediately, never
  retained — "no durable queue for closed signals" is this module's own
  reading of that criterion: a closed signal is consumed and gone, not kept
  around for a later reader.
* ``ttl_s`` is always clamped to ``MAX_TTL_S`` (90, F1/F3's own ceiling —
  see ``transport.FOCUS_TTL_S``, the same constant, owned there because Z1
  is the write side; re-declared here rather than imported so this read-side
  module stays independent of ``transport``'s network stack, checked against
  it by ``test_live_frame.py``). This clamp is defense in depth: "<=90s
  clear" must hold even if a hostile or buggy relay sends a larger value —
  including a non-finite one: JSON's ``Infinity``/``-Infinity``/``NaN``
  tokens survive ``json.loads`` (the parser ``filtered_stream._accept_line``
  uses) unrejected by default, so ``_clamp_ttl`` treats any non-finite
  ``ttl_s`` the same as an absent one rather than let ``int()`` raise on it.
* ``session_ref``/``user`` (ident-shaped: a short opaque token, matching
  ``managed.ManagedRegistry.session_ref()``'s own 12-hex shape upstream) are
  routed through the shared Z1/zeitgeist identity grammar (``grammar``,
  itself a ported copy of ``zeitgeist/editor.py:146-192``) before reaching a
  ``PresenceView``/``FocusView`` or being used as this state's internal
  dict key. A relay is untrusted input exactly like the ``editor`` rumor
  feed upstream sanitizes at render time: a well-formed identifier passes
  through unchanged, a prose-shaped one (the same "IGNORE PRIOR
  INSTRUCTIONS ..." class ``grammar.py`` documents) is replaced with
  grammar's stable, non-reversible ``unknown-<digest>`` label rather than
  ever reaching a caller unfiltered — WIRE-M2-04, HIC-M2-DISPOSITIONS item 2.
* ``repo``/``focus_ref`` (ref-shaped: ``repo`` genuinely can carry ``/``;
  ``focus_ref`` is actually ident-shaped on the real wire —
  ``managed_control.schema.json``'s ``FocusArgs.focus_ref`` shares the ident
  CHARACTER class (no ``/``) with ``session_ref``/``user`` above, and
  FIX-M2-10 corrected ``transport.py``'s own construction from
  ``f"{mission_slug}/{wp_id}"`` to ``f"{mission_slug}.{wp_id}"`` to match —
  this read side needs no change of its own, since REF_RE is a strict
  superset of what an ident-shaped value needs) route through the SAME
  grammar as #135's ``EventSample.ref`` reader. #138 widened that grammar's
  ref-kind bound to 240 chars / ``MAX_SEGMENTS["ref"]`` 10 — 240 was
  ``EventSample.ref``'s own bound (``managed_live.schema.json``) from the
  start; ``repo``'s own bound is narrower (``FocusSample.repo``, 120,
  enforced at write time — a POST that violates it 422s before the value is
  ever broadcast, ``transport.py``), so sharing one grammar across all
  three is still a convenience for ``repo``, not a claim that 240/10 is
  what ``repo`` itself permits (controller-qa, #138 fix round). ``focus_ref``
  no longer has this gap: at #138 time its own bound
  (``FocusSample.focus_ref``/``FocusArgs.focus_ref``) was still the
  narrower ident one (64), so the two real mission slugs over 64 chars
  could not ride ``focus_ref`` at all once a ``.WP<nn>`` suffix was
  appended — filed as zeitgeist#38. zeitgeist#38 (relay #39) has since
  landed and widened both schemas' ``focus_ref`` to the same
  ``{0,239}``/``maxLength`` 240 envelope as ``EventSample.ref``, so the
  shared grammar's bound is no longer wider than ``focus_ref``'s own real
  bound — only ``repo`` still has the gap described above. Recorded
  consequence of sharing the grammar (now only for ``repo``), not hidden:
  the canonical prose fixture fits inside the real-slug envelope, so the
  shape defense no longer binds at ref positions — they enforce charset +
  length (+ grammar's ≥11-segment prose floor) only. This does not reopen
  the ``branch`` decision below (post-widening, full ref-kind routing would
  pass the same fixture anyway); callers treat the rendered form as
  untrusted display text exactly like ``branch``/``path``, while the dict
  keys here stay charset-gated.
* ``branch`` is deliberately NOT routed through grammar (rework cycle 3,
  Renata MAJOR — this replaces an earlier candidate's ``branch``-only
  carve-out). ``grammar.ident()``'s ``REF_RE`` shape check pairs a
  char-class-plus-length test with a segment-count cap
  (``grammar.MAX_SEGMENTS["ref"]``, 6 at the time of that review); the
  earlier candidate tried
  dropping only the segment-count half for ``branch``, to avoid
  mis-rejecting this program's own multi-segment sandbox branches
  (``bead/<ID>/<actor>/<n>``, e.g. ``bead/WIRE-M2-04/python-pedro/1``, 7
  segments). Review found the char-class-only half is not a working
  defense on its own: the same "IGNORE-PRIOR-INSTRUCTIONS-..." fixture
  ``grammar.py`` and ``zeitgeist/editor.py:157-165`` cite as PROOF that
  character validity alone cannot separate a real identifier from prose
  fullmatches ``REF_RE`` under 64 chars with no whitespace, so it would
  have passed the carve-out unmodified into MCP-adapter-facing output
  (``subscription.py``) — a weakened check that looked like the same
  defense as ``repo``/``focus_ref`` without actually providing it.
  Upstream's own resolution of the identical tension
  (``zeitgeist/editor.py:166-169``: "a branch name legitimately reads like
  prose ... so no shape rule can separate them") is not a weaker pattern
  either — it is to run ``branch`` through the exact same, FULL
  segment-capped ``_ident(..., _REF_RE)`` as ``repo`` wherever it renders
  it at all (``zeitgeist/editor.py:300``), and to leave it out entirely of
  the templates where a hostile value would otherwise reach a reader
  unvetted. This module cannot take upstream's first option: this
  program's own real branches are NOT short enough to survive the segment
  cap (7 segments is the *normal* case here, not an edge case), so full
  grammar routing would misclassify every real branch as hostile. With
  neither upstream option available and the partial check demonstrated not
  to work, ``branch`` is instead folded into the un-sanitized group below,
  same as ``path``: it already reaches the identical MCP-adapter-facing
  serialization (``subscription.py``'s ``_serialize_snapshot``) as
  un-sanitized ``path`` does today, it is never used as a lookup key (only
  ``session_ref``/``focus_ref`` are), and this way the module claims no
  defense for ``branch`` it does not actually provide.
* ``path``/``kind``/``branch``/``state`` are NOT identity fields in this
  sense (a file path or a branch name legitimately looks like prose;
  ``state`` is already closed-enum gated against ``_FOCUS_STATES``) and are
  left as plain, un-sanitized strings, matching upstream's own separate
  ``_safe_path`` treatment for paths (not ported here — same documented
  scope reduction as this module's own not-yet-landed ``validator.py``).
  A caller reading ``branch``/``path`` from a ``PresenceView``/``FocusView``
  must treat it as untrusted display text, never as a value safe to
  interpret, execute, or forward as an instruction.
"""

from __future__ import annotations

from kernel.clock import now_epoch

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeGuard

from . import grammar

FrameType = Literal["presence", "focus", "signal", "event"]

# "event" (Priivacy-ai/spec-kitty#10) is the E1 status-moment frame the
# relay emits for one fire-and-forget ``event.publish`` — activity ABOUT a
# session, never liveness OF one. Accepting it here is what lets
# ``filtered_stream.watch()`` deliver it at all; see ``_apply_event`` for why
# it is deliberately the one frame type that leaves no trace in state.
_FRAME_TYPES: frozenset[str] = frozenset({"presence", "focus", "signal", "event"})
_SIGNAL_KINDS: frozenset[str] = frozenset({"gap", "epoch", "revoked", "heartbeat"})
_FOCUS_STATES: frozenset[str] = frozenset({"active", "paused", "ended"})

# managed_live.schema.json FocusSample.ttl_s / managed_presence.schema.json
# PresenceSample.ttl_s: both declare "maximum": 90. Cross-checked against
# transport.FOCUS_TTL_S by test_live_frame.py rather than imported (see
# module docstring).
MAX_TTL_S = 90


@dataclass(frozen=True)
class LiveFrame:
    """One parsed, shape-valid ``LiveFrame`` envelope. ``payload`` is the
    ``frame[frame_type]`` sub-object, exactly as received — ``StreamState``
    reads individual fields defensively, so this stays a plain mapping
    rather than a second, type-specific dataclass layer."""

    schema_version: str
    epoch: str
    seq: int
    emitted_at: float
    frame_type: FrameType
    payload: Mapping[str, Any]


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_live_frame(raw: object) -> LiveFrame | None:
    """Return a :class:`LiveFrame` for a shape-valid envelope, else ``None``.

    Never raises: this is the read-side "forbidden/malformed input" gate —
    anything this module was not written to understand is refused, exactly
    as ``sanitizer.assert_clean`` refuses an outbound document, except the
    read side cannot signal the sender, so it drops and moves on.
    """
    if not isinstance(raw, dict):
        return None

    schema_version = raw.get("schema_version")
    epoch = raw.get("epoch")
    seq = raw.get("seq")
    emitted_at = raw.get("emitted_at")
    frame = raw.get("frame")

    if not isinstance(schema_version, str) or not schema_version.startswith("1."):
        return None  # version-skew rejection: only the 1.x major is understood
    if not isinstance(epoch, str) or not epoch:
        return None
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        return None
    if not _is_number(emitted_at):
        return None
    if not isinstance(frame, dict):
        return None

    frame_type = frame.get("type")
    if frame_type not in _FRAME_TYPES:
        return None
    payload = frame.get(frame_type)
    if not isinstance(payload, dict):
        return None

    return LiveFrame(
        schema_version=schema_version,
        epoch=epoch,
        seq=seq,
        emitted_at=float(emitted_at),
        frame_type=frame_type,
        payload=payload,
    )


def _clamp_ttl(value: object) -> int:
    if not _is_number(value):
        return MAX_TTL_S
    # A hostile or buggy relay can send JSON's `Infinity`/`NaN`/`-Infinity`
    # tokens — Python's own ``json.loads`` (used by
    # ``filtered_stream._accept_line``) accepts them by default, and
    # ``int()`` on a non-finite float raises (OverflowError for +/-inf,
    # ValueError for nan). Treat any non-finite value the same as "absent":
    # clamp to the ceiling rather than let it propagate out of
    # ``StreamState.apply``/``FilteredStream.watch()`` and end the whole
    # subscription generator over one bad field in one frame.
    if isinstance(value, float) and not math.isfinite(value):
        return MAX_TTL_S
    return max(1, min(int(value), MAX_TTL_S))


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _grammar_ident(value: object, pattern: re.Pattern[str] = grammar.IDENT_RE) -> str | None:
    """``_optional_str`` composed with the shared Z1/zeitgeist identity
    grammar (``grammar.ident``): a non-str value is dropped exactly as
    ``_optional_str`` already drops it; a well-typed but prose-shaped value
    is replaced with grammar's stable ``unknown-<digest>`` label rather than
    reaching a View unfiltered — the same rendering-time sanitization
    ``zeitgeist/editor.py`` applies before a caller-supplied identity is
    ever displayed (see the module docstring and ``grammar.py`` itself)."""
    return grammar.ident(value, pattern=pattern) if isinstance(value, str) else None


@dataclass(frozen=True)
class PresenceView:
    session_ref: str
    user: str | None
    repo: str | None
    branch: str | None
    path: str | None
    kind: str | None
    expires_at: float


@dataclass(frozen=True)
class FocusView:
    session_ref: str | None
    focus_ref: str
    state: str
    user: str | None
    repo: str | None
    branch: str | None
    expires_at: float


@dataclass(frozen=True)
class TeamSnapshot:
    """The honest, TTL-clamped, closed-signals-already-dropped view of one
    team-bound subscription's local state at read time. ``reset_count`` /
    ``last_reset_reason`` are the only trace a gap/epoch reset leaves —
    observability without ever retaining what was cleared."""

    epoch: str | None
    presence: tuple[PresenceView, ...]
    focus: tuple[FocusView, ...]
    reset_count: int
    last_reset_reason: str | None


class StreamState:
    """Volatile, in-process, per-subscription state. Nothing here is ever
    written to disk (Z4's own "no payload persisted" criterion) — construct
    a fresh instance per ``FilteredStream`` and let it go when the
    subscription does."""

    def __init__(self) -> None:
        self._epoch: str | None = None
        self._presence: dict[str, dict[str, Any]] = {}
        self._focus: dict[tuple[str | None, str], dict[str, Any]] = {}
        self._reset_count = 0
        self._last_reset_reason: str | None = None

    def _reset(self, reason: str) -> None:
        self._presence.clear()
        self._focus.clear()
        self._reset_count += 1
        self._last_reset_reason = reason

    def apply(self, live_frame_obj: LiveFrame) -> None:
        if self._epoch is not None and live_frame_obj.epoch != self._epoch:
            self._reset("epoch_change")
        self._epoch = live_frame_obj.epoch

        if live_frame_obj.frame_type == "signal":
            self._apply_signal(live_frame_obj)
        elif live_frame_obj.frame_type == "presence":
            self._apply_presence(live_frame_obj)
        elif live_frame_obj.frame_type == "event":
            self._apply_event(live_frame_obj)
        else:
            self._apply_focus(live_frame_obj)

    def _apply_signal(self, live_frame_obj: LiveFrame) -> None:
        kind = live_frame_obj.payload.get("kind")
        if kind not in _SIGNAL_KINDS:
            return  # unknown/future signal kind: ignored, not fatal
        if kind in ("gap", "epoch"):
            self._reset(kind)
            return
        if kind == "revoked":
            ref = live_frame_obj.payload.get("session_ref")
            if isinstance(ref, str) and ref:
                # Grammar-sanitized before matching: presence/focus keys are
                # stored under the sanitized form too (see _apply_presence /
                # _apply_focus), so a hostile-but-consistent session_ref still
                # revokes the record it named rather than silently no-op-ing.
                ref = grammar.ident(ref)
                self._presence.pop(ref, None)
                self._focus = {k: v for k, v in self._focus.items() if v.get("session_ref") != ref}
        # "heartbeat": liveness only, no state change.

    def _apply_presence(self, live_frame_obj: LiveFrame) -> None:
        payload = live_frame_obj.payload
        actor = payload.get("actor")
        if not isinstance(actor, dict):
            return
        ref = actor.get("session_ref")
        if not isinstance(ref, str) or not ref:
            return
        ref = grammar.ident(ref)  # ident-shaped: 12-hex session token, never a ref path
        observed_at = payload.get("observed_at")
        base_ts = float(observed_at) if _is_number(observed_at) else live_frame_obj.emitted_at
        self._presence[ref] = {
            "session_ref": ref,
            "user": _grammar_ident(actor.get("user")),
            "repo": _grammar_ident(payload.get("repo"), grammar.REF_RE),
            "branch": _optional_str(payload.get("branch")),  # prose-shaped, not identity: see module docstring
            "path": _optional_str(payload.get("path")),
            "kind": _optional_str(payload.get("kind")),
            "expires_at": base_ts + _clamp_ttl(payload.get("ttl_s")),
        }

    def _apply_event(self, live_frame_obj: LiveFrame) -> None:
        """An ``event`` frame is deliberately the one frame type that changes
        nothing here. The relay's own contract for ``event.publish``
        (``zeitgeist/managed.py``) is "an event is activity ABOUT a session,
        never liveness OF one — publishing one must not extend anything's
        ttl", and it keeps nothing beyond its replay cache; this read side
        holds to the same shape. A moment is delivered exactly once, live, to
        whoever is watching (``filtered_stream.watch()`` yields every accepted
        frame); a caller reading :meth:`snapshot` afterwards gets presence and
        focus — what is true NOW — never a history that would silently grow
        with every broadcast and outlive the 90s honesty ceiling everything
        else in this module obeys. Z4-C's own criteria say the same thing from
        the client side: no missed-event reconstruction, no payload persisted.
        """

    def _apply_focus(self, live_frame_obj: LiveFrame) -> None:
        payload = live_frame_obj.payload
        focus_ref = payload.get("focus_ref")
        if not isinstance(focus_ref, str) or not focus_ref:
            return
        focus_ref = grammar.ident(focus_ref, grammar.REF_RE)  # ref-shaped: mission_slug/wp_id
        state = payload.get("state")
        if state not in _FOCUS_STATES:
            return
        actor = payload.get("actor")
        session_ref = actor.get("session_ref") if isinstance(actor, dict) else None
        session_ref = grammar.ident(session_ref) if isinstance(session_ref, str) and session_ref else None
        key = (session_ref, focus_ref)
        if state == "ended":
            self._focus.pop(key, None)  # only this session's focus ends
            return
        self._focus[key] = {
            "focus_ref": focus_ref,
            "session_ref": session_ref,
            "state": state,
            "user": _grammar_ident(actor.get("user")) if isinstance(actor, dict) else None,
            "repo": _grammar_ident(payload.get("repo"), grammar.REF_RE),
            "branch": _optional_str(payload.get("branch")),  # prose-shaped, not identity: see module docstring
            "expires_at": live_frame_obj.emitted_at + _clamp_ttl(payload.get("ttl_s")),
        }

    def snapshot(self, *, now: float | None = None) -> TeamSnapshot:
        ts = now if now is not None else now_epoch()  # kernel.clock single door (M2 canonical integration)
        # Lazy eviction, purged in place (not merely filtered from the
        # output): an expired entry is not "closed" by any signal the relay
        # sent, so nothing else would ever remove it — <=90s clear must hold
        # on ordinary silence, not only on an explicit end/revoke.
        for ref in [k for k, v in self._presence.items() if v["expires_at"] <= ts]:
            del self._presence[ref]
        for focus_key in [k for k, v in self._focus.items() if v["expires_at"] <= ts]:
            del self._focus[focus_key]

        presence = tuple(
            PresenceView(
                session_ref=v["session_ref"],
                user=v["user"],
                repo=v["repo"],
                branch=v["branch"],
                path=v["path"],
                kind=v["kind"],
                expires_at=v["expires_at"],
            )
            for v in self._presence.values()
        )
        focus = tuple(
            FocusView(
                session_ref=v["session_ref"],
                focus_ref=v["focus_ref"],
                state=v["state"],
                user=v["user"],
                repo=v["repo"],
                branch=v["branch"],
                expires_at=v["expires_at"],
            )
            for v in self._focus.values()
        )
        return TeamSnapshot(
            epoch=self._epoch,
            presence=presence,
            focus=focus,
            reset_count=self._reset_count,
            last_reset_reason=self._last_reset_reason,
        )
