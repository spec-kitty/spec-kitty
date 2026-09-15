"""Architectural gate: no project data leaves the machine from an unlisted file.

Issue Priivacy-ai/spec-kitty#3030 (P0 confidentiality). On 2026-07-27, 1,322
events belonging to five never-opted-in projects were delivered alongside 7,811
from the intended one. This mission then found and closed egress paths **one at
a time, five separate times**, each by a different review; a dedicated sink-first
enumeration (``kitty-specs/journal-project-consent-3030-01KYKWQS/egress-inventory.md``,
E1-E19) found three more. The operator's decision was to stop enumerating and
build a boundary.

Why a *sink* scan and not a name scan
-------------------------------------
The prior guard, ``tests/sync/test_no_queue_drain_constructed_3030.py``, keys on
two literal function names (``RETIRED_DRAIN_NAMES``). It was probed and **missed**
a new queue-backed sender of the shape ``queue.drain_queue(...)`` followed by
``urllib.request.urlopen(...)`` — the names differ, so the guard is blind. This
gate keys on the **sink**, which such a path cannot avoid having, and is
allowlisted **by file**, so a *new* sender in a file nobody has reasoned about is
a red build rather than a discovery six reviews later.

The inventory's structural finding is the reason a file-keyed allowlist works
here: two independent universes feed the *same* HTTP sink
(``delivery/dispatcher.py`` gated in SQL, ``sync/history_import/upload.py``
ungated), so ``DeliveryReceiver.deliver`` is itself treated as a sink. That makes
the two callers distinguishable even though the ``requests.post`` they share is
one line in one file.

Shape (modelled on ``tests/architectural/test_auth_transport_singleton.py``)
---------------------------------------------------------------------------
1. AST-scan every ``.py`` under ``src/`` for the sink vocabulary below.
2. Permit a sink only in a file carrying an explicit :data:`_EGRESS_ALLOWLIST`
   entry, each annotated with the **consent seam** that covers it (or a
   member of a closed vocabulary of non-consent reasons).
3. Permit, separately and loudly, the files on :data:`_KNOWN_UNGATED` — the
   currently-open work-list. See "The work-list, and why it is red" below.
4. Meta-tests: no stale allowlist entry; the annotated seam must still exist;
   and a negative control proving the scanner and the whole collection path
   actually bite.

The sink vocabulary
-------------------
* ``requests.post`` / ``.patch`` / ``.request`` and the same verbs on any HTTP
  client object (``httpx``, ``AuthenticatedClient``, ...). Matched on the
  *method name*, not the receiver's type, because the receiver is usually a
  parameter whose type is invisible to AST. ``.put`` is matched only when the
  call also carries a URL or a request-body keyword — see limit 6 below.
* ``urllib.request.urlopen(...)`` / a bare ``urlopen(...)``. **Every** call
  counts, loopback or not: whether a URL is loopback is a runtime property of a
  variable, so deciding it statically would hand a new sender the exact evasion
  (build the URL in a local) that this gate exists to remove. Loopback control
  endpoints are therefore allowlisted explicitly, with ``LOOPBACK_CONTROL``.
* ``.send_event(...)`` and ``<ws-ish>.send(...)`` — the WebSocket senders.
* ``.deliver(...)`` — ``DeliveryReceiver.deliver``, the shared transmit facade
  one call above ``requests.post`` (the "no chokepoint" finding above).
* **Any call carrying both ``headers=`` and a body** (``data``/``json``/
  ``content``/``files``), whatever the callee is named. This is the
  callee-agnostic rule, and it is the one that sees a transport **injected as a
  parameter** — ``poster(url, data=..., headers=...)`` is a bare ``Name`` call
  that no method-name rule can match. Request/response *value* constructors
  (``urllib.request.Request``) are excluded: they build a value, they do not
  transmit, and the ``urlopen`` that follows is already matched.

The work-list, and why it is empty
----------------------------------
:data:`_KNOWN_UNGATED` is how an egress path with **no** consent answer is
recorded while it is being fixed. It is deliberately not a ``skip`` and not a
strict-xfail: ``test_known_ungated_egress_paths_are_closed`` asserts the set is
**empty**, so a recorded path is a **red build** naming the file, its
requirement and the seam it must call. This mission's single worst documented
failure shape is a mechanism that reports success for having done nothing, and a
suppression that prints like a pass is exactly that shape.

It is empty today. It was authored holding E1
(``sync/history_import/upload.py``, FR-028), E2 (``tracker/saas_client.py``,
FR-029) and E3 (``saas_client/client.py``, FR-030) — the three ungated
sink-bearing files the enumeration found — and all three were closed by their
own work packages while this gate was being written. Each is now allowlisted
against the seam that closed it, and each seam is re-checked on every run by
``test_seam_allowances_name_a_live_seam``: if a fix is reverted, the allowance
stops being true and this module reds rather than staying quietly exempt.

Both sets are size-ratcheted in ``tests/architectural/_baselines.yaml``, where
growth **fails** ``test_ratchet_baselines.py`` — a different test in a different
file — and shrinkage only warns. ``known_ungated_files`` is pinned at **0**, so
recording a new open path costs a visible YAML diff with a written
justification; the intended response to a new finding is to close the path, not
to register it.

What this gate does not judge
-----------------------------
An allowance asserts that a named seam **exists**, not that it is *correct*. The
gate can tell you a consent call was deleted; it cannot tell you the call
resolves the right project or fails closed. That is a reviewer's job, and on this
mission it is where the real defects lived — FR-025's ``is False``, FR-031's
undetermined-reads-as-consent, FR-027's field-level shape faults. This gate
closes the *structural* hole (a sender nobody reasoned about) and nothing more.

Completeness limits — inherited from the enumeration, stated rather than implied
--------------------------------------------------------------------------------
A claim that names its gaps is the only defensible kind. This gate sees a sink
that is written as a call to one of the names above, in a file under ``src/``.
It does **not** see:

1. **``getattr``-by-string reaching a sender.** ``src/`` contains 433
   string-literal ``getattr`` calls; a string literal is not a reference, so an
   attribute reached by name is invisible to AST scanning. The same blind spot
   already made two egress paths look live that are dead (FR-032,
   ``token_manager._ws_client``), and it cuts both ways.
2. **Empty callback registries — and one exists.** E17,
   ``status/adapters.py::fire_resolved_binding_fanout``, has a firing site and
   **zero registered handlers**. *A sink that does not exist yet cannot be found
   by scanning for sinks.* This is the hard limit of sink-first enumeration and
   the strongest argument for this gate over any one-off audit: the gate is what
   reds on the day the handler is written.
3. **Dynamic import, entry-point plugins, ``exec``.** Not audited; a sender
   reached that way is still a sink *in some file*, so it reds only if that file
   is unlisted — which is the point, but reachability is not what is checked.
4. **``subprocess`` invoked through a variable command name.** E19
   (``git push origin <branch>``, ``merge/executor.py`` /
   ``orchestrator_api/commands.py``) is out of boundary by design — the project's
   own commits to the project's own ``origin``, opt-in, not the spec-kitty SaaS —
   and is deliberately not modelled here. A transmitting subprocess built from a
   variable command name would also be missed.
5. **At-rest pooling.** Writes into ``~/.spec-kitty/`` are not egress and are not
   scanned; the inventory scopes that to C-006.
6. **A bare ``.put(x)``.** ``put`` collides with ``queue.put`` / ``mailbox.put``,
   which are not egress — found by this module's own no-false-positive control,
   not reasoned about in advance. It is therefore matched only when the call
   carries an HTTP signal (a ``json``/``data``/``content``/``headers``/
   ``params``/``files``/``auth``/``cookies`` keyword, or a first argument that is
   a URL literal, an f-string, or a variable named ``url``/``uri``/
   ``endpoint``/...). ``client.put(some_var)`` with no keywords is consequently
   **missed**. ``timeout`` is excluded from the keyword set on purpose —
   ``queue.put(item, timeout=1)`` has one. ``post``/``patch``/``request`` carry
   no such collision in ``src/`` and are matched unconditionally.
7. **A file may hold more than one sink, and an allowance covers them all.** E20
   is the recorded case: the egress inventory traced the import path *backwards*
   from ``requests.post`` and named one sink, but ``run_server_preflight`` POSTs
   the same envelope stream earlier in the same function, so a gate placed where
   the inventory pointed would have leaked every envelope while looking closed.
   Tracing a sink backwards to its callers is not the same as tracing a path
   forwards through every request it makes. This gate keys on files, so it
   cannot tell you a *second* sink in an already-allowlisted file is ungated —
   the seam annotation is per file, not per call. Adding a sink to a listed file
   is therefore the cheapest way to evade this gate, and only review catches it.
8. **The all-positional / no-``headers=`` transport call.** ``poster(url, body,
   hdrs)`` — every argument positional, no ``headers=`` or body keyword present
   at all — evades both the method-name rules (the callee is a bare ``Name``,
   not ``.post``/``.patch``/``.request``) and ``_transmits_a_body`` (`:295-306`),
   which requires ``headers`` **and** a body keyword to be present before it
   will call a bare-``Name`` callee a sink. `#3113`: the guard's own bite-test
   (`test_scanner_detects_each_sink_shape`) exercised only the kwargs form of
   the injected-transport shape, so it would have certified a scanner that was
   blind to this one — a negative control that only tests the shape you
   thought of is not a negative control (see ``TestGuardBites`` below for the
   generalisation this produced). A structural tightening was measured before
   being ruled out: the callee is a bare ``ast.Name`` whose ``id`` resolves to
   a parameter of the *enclosing* ``FunctionDef`` — transport injected as a
   parameter, decidable with no author-chosen word (C-006 forbids any
   tightening that needs one, including ``_URL_ARG_NAMES``). Measured across
   the whole of ``src/`` **before** any matcher edit
   (``TestFR015StructuralTighteningMeasurement`` below is the reproducible,
   re-runnable form of that measurement), it produces a **non-zero**
   false-positive count: reproducible false hits include calls to
   ``resolve_workspace_for_wp``, ``locate_work_package``,
   ``behind_commits_touch_only_planning_artifacts`` and ``get_wp_lane`` —
   each a dependency-injected work-package/lane lookup function called through
   a same-named ``Callable``-typed parameter, not a transport. Per FR-015's
   acceptance criteria a non-zero count is itself the outcome: **the matcher is
   left alone.** What catches this shape is review, and the file-keyed
   allowlist if the sink lands in a file nobody has reasoned about.
   ``test_scanner_detects_each_sink_shape`` carries both of `#3113`'s
   positional cases pinned as ``pytest.xfail(..., strict=True)``, naming this
   limit.

Spec: FR-002, FR-003, FR-019, FR-025-FR-032, C-003. `#3113` (FR-013, FR-014,
FR-015) adds limit 8 above; cross-referenced one-directionally against
``kitty-specs/journal-project-consent-3030-01KYKWQS/egress-inventory.md``,
which belongs to a closed mission and is not edited by this change (C-010).
"""

from __future__ import annotations

import ast
import warnings
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# Sink vocabulary
# ---------------------------------------------------------------------------


class SinkKind(StrEnum):
    """The transmit primitives this gate recognises."""

    HTTP_VERB = "http-verb"
    URLOPEN = "urlopen"
    SEND_EVENT = "send-event"
    WEBSOCKET_SEND = "websocket-send"
    RECEIVER_DELIVER = "receiver-deliver"
    TRANSPORT_CALL = "transport-call"


#: HTTP methods that transmit a body or an arbitrary request. Measured against
#: ``src/``: ``post``/``patch``/``request`` produce zero non-transport matches,
#: so they are matched unconditionally.
_HTTP_VERBS: frozenset[str] = frozenset({"post", "patch", "request"})

#: ``put`` is the one verb that collides with a common non-network API
#: (``queue.put``, ``mailbox.put``), so it is matched only when the call also
#: carries an HTTP signal. See ``_looks_like_http_call`` and limit 6 in the
#: module docstring for the residual hole this leaves.
_AMBIGUOUS_HTTP_VERBS: frozenset[str] = frozenset({"put"})

#: Keyword arguments that mean "this call carries a request body/headers".
#: ``timeout`` is deliberately absent — ``queue.put(item, timeout=1)`` has one.
_HTTP_KWARGS: frozenset[str] = frozenset({"json", "data", "content", "headers", "params", "files", "auth", "cookies"})

#: Argument names that mean the first positional is a URL.
_URL_ARG_NAMES: frozenset[str] = frozenset({"url", "uri", "endpoint", "href", "base_url", "full_url", "request_url", "target_url"})

#: Body-carrying keywords. A call taking one of these **and** ``headers`` is an
#: HTTP request whatever its callee is named — which is how an *injected*
#: transport is caught. ``sync/history_import/upload.py::run_server_preflight``
#: POSTs the full envelope stream through a ``poster(...)`` parameter, a bare
#: ``Name`` call that no method-name rule can see; it was found only because
#: FR-028's implementer traced the path *forwards*. See limit 7.
_REQUEST_BODY_KWARGS: frozenset[str] = frozenset({"json", "data", "content", "files"})

#: Callees that build a request/response *value* rather than transmitting one.
#: ``urllib.request.Request(url, data=..., headers=...)`` is HTTP-shaped but sends
#: nothing — the ``urlopen`` that follows is the sink, and it is already matched.
_VALUE_CONSTRUCTORS: frozenset[str] = frozenset({"Request", "Response"})

#: Receiver names that make a bare ``.send(...)`` a websocket frame rather than
#: a queue put. Kept narrow on purpose: ``.send`` is too common a name to match
#: unconditionally, and every live websocket sender in ``src/`` binds one of
#: these (``self.ws.send`` in ``sync/client.py``).
_WEBSOCKET_RECEIVERS: frozenset[str] = frozenset({"ws", "_ws", "websocket", "_websocket", "ws_client", "_ws_client", "conn", "socket"})

#: What an unlisted file must do, per sink kind. This is the actionable half of
#: the failure message: "route it through X" beats "you are not allowed".
_SEAM_GUIDANCE: dict[SinkKind, str] = {
    SinkKind.RECEIVER_DELIVER: (
        "resolve consent from the batch's own project_uuid before calling "
        "DeliveryReceiver.deliver — delivery/selection.py::select_consented "
        "already computes exactly that value (E9)"
    ),
    SinkKind.SEND_EVENT: (
        "gate on the event's own project_uuid behind an authenticated client lookup "
        "that fails closed (issue #5 retired the per-project consent chain; "
        "invocation/propagator.py::_get_saas_client returning None must mean no "
        "send, no log, no fallback path)"
    ),
    SinkKind.WEBSOCKET_SEND: (
        "the hosted-sync websocket retired with the transport (issue #5); a new "
        "websocket sender must gate on the frame's own project_uuid and refuse "
        "when it cannot be proven, never read 'could not determine' as consent "
        "(FR-003)"
    ),
    SinkKind.HTTP_VERB: (
        "resolve the payload's own project_uuid and refuse unless its egress answer "
        "is affirmative — never a checkout/cwd/repo-slug proxy for that "
        "project_uuid (FR-019), and never read 'could not determine' as consent "
        "(FR-003); hosted requests ride the operator's authenticated session "
        "(tracker_egress_verdict at HOSTED_SERVICE is the pinned seam)"
    ),
    SinkKind.URLOPEN: (
        "if this is a loopback control endpoint, allowlist it as LOOPBACK_CONTROL; "
        "otherwise resolve the payload's own project_uuid and refuse unless its "
        "egress answer is affirmative before the call"
    ),
    SinkKind.TRANSPORT_CALL: (
        "this transmits a body through an injected/aliased transport, so the "
        "method name hides nothing — resolve the payload's own project_uuid and "
        "refuse unless its egress answer is affirmative BEFORE the call. E20 is "
        "the precedent: the import path had two sinks and gating only the visible "
        "one would have leaked every envelope while looking closed"
    ),
}


@dataclass(frozen=True)
class SinkSite:
    """One transmit call, located by file + line + kind (never by line alone)."""

    relpath: str
    lineno: int
    kind: SinkKind
    snippet: str


def _attr_tail(node: ast.expr) -> str | None:
    """Last name segment of ``a``/``a.b``/``self.a.b``; ``None`` for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _looks_like_http_call(node: ast.Call) -> bool:
    """True when *node* carries a URL or a request-body keyword.

    Used to disambiguate ``client.put(url, json=...)`` from ``queue.put(item)``
    without keying on the receiver's *name* — name-keying is the failure mode
    this whole gate exists to replace.
    """
    if any(kw.arg in _HTTP_KWARGS for kw in node.keywords if kw.arg is not None):
        return True
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.JoinedStr):  # f"{base}/api/..."
        return True
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return "://" in first.value or first.value.startswith("/")
    tail = _attr_tail(first)
    return tail is not None and tail.lower().lstrip("_") in _URL_ARG_NAMES


def _transmits_a_body(node: ast.Call) -> bool:
    """True when *node* carries both headers and a request body.

    Callee-agnostic on purpose. This is the rule that sees a transport passed in
    as a parameter (``poster(url, data=..., headers=...)``) or reached through an
    alias, neither of which any method-name rule can match.
    """
    tail = _attr_tail(node.func)
    if tail in _VALUE_CONSTRUCTORS:
        return False
    kwargs = {kw.arg for kw in node.keywords if kw.arg is not None}
    return "headers" in kwargs and bool(kwargs & _REQUEST_BODY_KWARGS)


def _classify(node: ast.Call) -> SinkKind | None:
    """Return the :class:`SinkKind` of *node*, or ``None`` when it is not a sink."""
    func = node.func
    if isinstance(func, ast.Name):
        # A bare ``urlopen(...)`` after ``from urllib.request import urlopen``.
        if func.id == "urlopen":
            return SinkKind.URLOPEN
        return SinkKind.TRANSPORT_CALL if _transmits_a_body(node) else None
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in _HTTP_VERBS:
        return SinkKind.HTTP_VERB
    if func.attr in _AMBIGUOUS_HTTP_VERBS and _looks_like_http_call(node):
        return SinkKind.HTTP_VERB
    if func.attr == "urlopen":
        return SinkKind.URLOPEN
    if func.attr == "send_event":
        return SinkKind.SEND_EVENT
    if func.attr == "deliver":
        return SinkKind.RECEIVER_DELIVER
    if func.attr == "send" and _attr_tail(func.value) in _WEBSOCKET_RECEIVERS:
        return SinkKind.WEBSOCKET_SEND
    return SinkKind.TRANSPORT_CALL if _transmits_a_body(node) else None


def _find_sinks(path: Path, root: Path) -> list[SinkSite]:
    """Every sink call in *path*, with ``relpath`` taken relative to *root*."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a louder problem than this rule
        return []

    relpath = path.relative_to(root).as_posix()
    sites: list[SinkSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _classify(node)
        if kind is None:
            continue
        try:
            snippet = ast.unparse(node.func)
        except Exception:  # pragma: no cover - older interpreters
            snippet = "<unparse-unavailable>"
        sites.append(SinkSite(relpath=relpath, lineno=node.lineno, kind=kind, snippet=snippet))
    return sites


def _scan(root: Path) -> list[SinkSite]:
    """Every sink call under *root*, excluding ``__pycache__``."""
    sites: list[SinkSite] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sites.extend(_find_sinks(path, root))
    return sites


# ---------------------------------------------------------------------------
# The allowlist
# ---------------------------------------------------------------------------


class AllowanceKind(StrEnum):
    """Closed vocabulary of reasons a file may hold a sink.

    Closed on purpose: without it, "no seam needed" becomes the escape hatch
    that turns the allowlist back into a name list.
    """

    #: A named consent seam resolves the data's **own** project_uuid.
    SEAM = "seam"
    #: The payload carries no project data at all (auth, doctrine fetch, probes).
    NOT_PROJECT_DATA = "not-project-data"
    #: A localhost control/health endpoint; nothing crosses the machine boundary.
    LOOPBACK_CONTROL = "loopback-control"
    #: A per-project transport whose every caller is separately allowlisted.
    TRANSPORT_ONLY = "transport-only"
    #: No production caller; non-reachability pinned by a named companion guard.
    UNREACHABLE = "unreachable"


@dataclass(frozen=True)
class Allowance:
    """Why one file is permitted to hold a sink."""

    kind: AllowanceKind
    inventory_id: str
    note: str
    #: For ``SEAM``: the symbol that must still exist, and the module holding it
    #: (relative to ``src/``). The seam frequently lives in the *caller*, not the
    #: sink file — E9's selection is in ``delivery/selection.py`` while the
    #: ``requests.post`` is in ``delivery/receivers.py``.
    seam_symbol: str | None = None
    seam_module: str | None = None
    #: For ``UNREACHABLE``: the test that pins the absence of a caller.
    pinned_by: str | None = None


#: Files permitted to hold a transmit primitive, keyed by path relative to
#: ``src/``. Inventory ids refer to
#: ``kitty-specs/journal-project-consent-3030-01KYKWQS/egress-inventory.md``.
_EGRESS_ALLOWLIST: dict[str, Allowance] = {
    # -- Gated by a named consent seam on the data's own project_uuid ---------
    # Issue-5-delete-sync-transport (2026-08-25): every sync/* and delivery/*
    # row below this marker's predecessors gated or transported the deleted
    # hosted-sync pipeline (E1/E7/E8/E9/E10/E13); those files were deleted with
    # their transport and their allowances died with them. The surviving
    # hosted-egress paths gate on authentication + team admission instead.
    "specify_cli/tracker/saas_client.py": Allowance(
        kind=AllowanceKind.SEAM,
        inventory_id="E2",
        note=(
            "FR-029. _request refuses via tracker_egress_verdict before the call. "
            "This is the path reached non-interactively during mission creation "
            "(core/mission_creation.py -> tracker/origin_consumer.py -> "
            "bind_mission_origin), which needed no operator action to fire. "
            "#3108 swapped the seam from project_egress_refusal to "
            "tracker_egress_verdict(root, destination=HOSTED_SERVICE), which joins "
            "the same hosted-sync consent chain (Channel 1) with the project's own "
            "committed tracker.egress key (Channel 2) as a narrowing conjunct. The "
            "exemption is strictly safer than before: Channel 1 still decides, and a "
            "tracker.egress grant is a no-op here because this transport reaches "
            "spec-kitty's own hosted service. Per FR-016 the Channel-1 refusal text "
            "stays byte-identical to what #3030 shipped."
        ),
        seam_symbol="tracker_egress_verdict",
        seam_module="specify_cli/tracker/saas_client.py",
    ),
    "specify_cli/saas_client/client.py": Allowance(
        kind=AllowanceKind.SEAM,
        inventory_id="E3",
        note=(
            "Re-anchored at issue-5-delete-sync-transport: FR-030's per-project "
            "_refuse_unless_project_consents retired with the hosted-sync consent "
            "chain, and _exchange now gates on _authenticated_authority_for_token "
            "*before the URL is used* — the bearer-token authority check "
            "(authenticated account + Private Teamspace + one Collaborative "
            "Teamspace) that team-side admission enforcement now rides. Four of "
            "five endpoints still put mission_id ('ULID or slug', and a slug is a "
            "client engagement name) in the request path, so a body-only gate would "
            "have missed every one; the authority check sits at that same chokepoint."
        ),
        seam_symbol="_authenticated_authority_for_token",
        seam_module="specify_cli/saas_client/client.py",
    ),
    "specify_cli/invocation/propagator.py": Allowance(
        kind=AllowanceKind.SEAM,
        inventory_id="E6",
        note=(
            "Re-anchored at issue-5-delete-sync-transport: FR-025's "
            "resolve_egress_consent adapter retired with the per-project consent "
            "ledger it consulted. The three send_event sites sit behind the auth "
            "lookup — resolve() returns before any send when _get_saas_client finds "
            "no connected client — so an unauthenticated checkout sends nothing; "
            "the envelope itself stays policy-gated by projection_resolution "
            "(include_request_text / include_evidence_ref)."
        ),
        seam_symbol="_get_saas_client",
        seam_module="specify_cli/invocation/propagator.py",
    ),
    # NOTE: E15 (specify_cli/sync/batch.py, kind=UNREACHABLE) was REMOVED by #3167.
    # The allowance existed because the queue-backed drain was ungated but had no
    # production caller. #3167 deleted the drain instead of gating it, so the module
    # now holds zero transmit primitives and no allowance is owed -- an inert row
    # here is exactly the quiet drift that mission was opened to close. Do not
    # re-add it: `sync/batch.py` must not regain a `requests.*` or
    # `request_with_stdlib_fallback_sync` call, which
    # `tests/architectural/test_batch_drain_retired_3167.py` now enforces.
    # -- Not project egress (E18), verified individually rather than assumed --
    "specify_cli/auth/transport.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="The centralized auth transport (FR-030 of the auth-boundary ADR); token traffic.",
    ),
    "specify_cli/auth/http/transport.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="Auth-internal transport with the stdlib fallback; token traffic.",
    ),
    "specify_cli/auth/flows/authorization_code.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="OAuth authorization-code exchange; carries no project data.",
    ),
    "specify_cli/auth/flows/device_code.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="OAuth device-code flow; carries no project data.",
    ),
    "specify_cli/auth/flows/client_credentials.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note=(
            "OAuth client_credentials machine login (#3277); exchanges the "
            "ServicePrincipal credential pair for a session. Same E18 class "
            "as the other auth flows — credential traffic, no project data."
        ),
    ),
    "specify_cli/auth/flows/refresh.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="OAuth token refresh; carries no project data.",
    ),
    "specify_cli/auth/flows/revoke.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="OAuth token revocation; carries no project data.",
    ),
    "specify_cli/auth/websocket/token_provisioning.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="Provisions a websocket token; carries no project data.",
    ),
    "specify_cli/tracker/saas_readiness.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note=(
            "Server reachability probe; sends no payload. Re-homed verbatim from "
            "`saas/readiness.py` when issue #5 deleted the sync transport — same "
            "HEAD-only urllib probe, new address."
        ),
    ),
    "specify_cli/doctrine/sources/api_source.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18",
        note="Fetches doctrine content inbound; the request carries no project data.",
    ),
    "specify_cli/doctrine/sources/https_source.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E18-#217",
        note=(
            "Inbound doctrine fetch. The Artifactory AQL query identifies the "
            "configured public pack item (repo/path/name) and returns metadata; "
            "it carries no project data."
        ),
    ),
    # -- Credential traffic, not project egress (E3, Priivacy-ai/spec-kitty#9) --
    "specify_cli/zeitgeist_client/resolution.py": Allowance(
        kind=AllowanceKind.NOT_PROJECT_DATA,
        inventory_id="E3-#9",
        note=(
            "The capability mint: POST /api/v1/live/capability/cli/ with "
            "{'repo_slug', 'kind'} and nothing else — a credential exchange that "
            "*receives* the relay token, in the same class as the auth flows above. "
            "No journal row, no envelope, no project_uuid: repo_slug is the hosted "
            "owner/repo key the admission GET one call earlier already carries, and "
            "the gate here is team membership over Bearer auth (SaasCapabilityGateway), "
            "not FR-019's per-project consent — presence broadcast must neither queue "
            "nor consult hosted-sync consent (design page ephemeral-team-status)."
        ),
    ),
    # specify_cli/dashboard/handlers/api.py RETIRED (E4 re-homing, planning epic #4):
    # its only transmit primitive was the /api/sync/trigger proxy urlopen; the
    # route was deleted rather than gated, so the file holds no sink and is off
    # the allowlist entirely.
    "specify_cli/dashboard/lifecycle.py": Allowance(
        kind=AllowanceKind.LOOPBACK_CONTROL,
        inventory_id="E18",
        note="Localhost dashboard health probe and shutdown/control endpoints.",
    ),
    # specify_cli/dashboard/server.py (#4125, fix round 2): the detached-spawn
    # readiness probe GETs the child's /api/health on 127.0.0.1 to verify the
    # listener serves this project's identity (project_path + token) — the
    # same loopback contract lifecycle.py's row above covers, on the spawn
    # side of the same boundary. Sends no payload beyond the GET itself.
    "specify_cli/dashboard/server.py": Allowance(
        kind=AllowanceKind.LOOPBACK_CONTROL,
        inventory_id="E18",
        note="Localhost detached-child readiness probe: GET /api/health on 127.0.0.1 to verify the listener's project identity (#4125).",
    ),
}

#: Ratcheted in ``_baselines.yaml`` as
#: ``test_egress_consent_boundary.egress_allowlist_files``. Growth fails
#: ``test_ratchet_baselines.py``, so silencing this gate by adding a file
#: requires an edit in a second file with a justification comment.
_EGRESS_ALLOWLIST_FILES: frozenset[str] = frozenset(_EGRESS_ALLOWLIST)


# ---------------------------------------------------------------------------
# The work-list: how an egress path with no consent answer gets recorded
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UngatedPath:
    """A sink-bearing file with no consent gate, and the requirement closing it."""

    inventory_id: str
    requirement: str
    seam_required: str
    note: str


#: Egress paths with no consent answer at all, recorded while they are fixed.
#:
#: **This set is asserted EMPTY** by ``test_known_ungated_egress_paths_are_closed``,
#: so an entry here is a red build naming the file, the requirement that closes it
#: and the seam it must call — never a skip, never a strict-xfail, because a
#: suppression that prints like a pass is this mission's worst documented failure
#: shape. Its size is pinned at 0 in ``_baselines.yaml``
#: (``test_egress_consent_boundary.known_ungated_files``), so recording a new one
#: also reds ``test_ratchet_baselines.py`` until a written justification is added
#: there. The intended response to a new finding is to close the path.
#:
#: Authored holding E1/E2/E3 (FR-028/029/030); all three landed while this gate was
#: being written and are now allowlisted above against the seam that closed each.
#:
#: NOT recorded here, deliberately: FR-031, the fail-open enqueue gate in
#: ``sync/body_upload.py``. That file holds no transmit primitive — it enqueues, and
#: E10's per-task seam gates the actual send — so this gate has nothing to red on
#: there, and an entry it could never clear by its own evidence would be a standing
#: false accusation rather than a work-list. FR-031 is a gate defect with its own pins.
_KNOWN_UNGATED: dict[str, UngatedPath] = {}

#: See :data:`_EGRESS_ALLOWLIST_FILES` — same ratchet, different key.
_KNOWN_UNGATED_FILES: frozenset[str] = frozenset(_KNOWN_UNGATED)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _collect_offenders(
    root: Path,
    allowed: frozenset[str],
    known_ungated: frozenset[str],
) -> list[SinkSite]:
    """Sink sites under *root* in a file that is neither allowlisted nor known-ungated.

    Parameterised over *root* and both permission sets so the negative control
    exercises **this** function — the one the boundary test calls — rather than
    only the leaf matcher. A guard whose collection path has never been observed
    to fail is decoration.
    """
    permitted = allowed | known_ungated
    return [site for site in _scan(root) if site.relpath not in permitted]


def _worklist_schema_violations(entries: dict[str, UngatedPath]) -> list[str]:
    """Ways a work-list entry stops being actionable, and so becomes an exemption."""
    problems: list[str] = []
    for relpath, entry in sorted(entries.items()):
        if not entry.requirement.startswith("FR-"):
            problems.append(f"{relpath}: requirement {entry.requirement!r} does not name an FR — nobody can tell when it clears")
        if not entry.seam_required.strip():
            problems.append(f"{relpath}: names no seam it has to call, so nobody can clear it")
        if not entry.note.strip():
            problems.append(f"{relpath}: carries no description of the path")
    return problems


def _worklist_failure_text(entries: dict[str, UngatedPath]) -> str:
    """The red-build report for an open egress path."""
    listed = "\n".join(
        f"  {relpath}  [{entry.inventory_id}] closed by {entry.requirement}\n      seam required: {entry.seam_required}\n      {entry.note}"
        for relpath, entry in sorted(entries.items())
    )
    return (
        f"#3030: {len(entries)} egress path(s) still ship project data with no "
        f"per-project consent answer:\n{listed}\n\n"
        "This failure is the work-list. Close each path at its sink, then move the "
        "file to _EGRESS_ALLOWLIST with the seam that now covers it and shrink "
        "test_egress_consent_boundary.known_ungated_files in "
        "tests/architectural/_baselines.yaml."
    )


def _format(sites: list[SinkSite]) -> str:
    return "\n".join(f"  {site.relpath}:{site.lineno}  [{site.kind.value}] {site.snippet}(...)\n      -> {_SEAM_GUIDANCE[site.kind]}" for site in sites)


# ---------------------------------------------------------------------------
# The boundary
# ---------------------------------------------------------------------------


class TestEgressConsentBoundary:
    """#3030: project data may only leave the machine from a reasoned-about file."""

    def test_no_unlisted_file_holds_an_egress_sink(self) -> None:
        """A new sender in an unlisted file fails the build."""
        offenders = _collect_offenders(_SRC, _EGRESS_ALLOWLIST_FILES, _KNOWN_UNGATED_FILES)
        if offenders:
            files = sorted({site.relpath for site in offenders})
            pytest.fail(
                "#3030 egress boundary violation: transmit primitive(s) in "
                f"{len(files)} file(s) with no recorded consent seam "
                f"({len(offenders)} site(s)):\n"
                f"{_format(offenders)}\n\n"
                "Every path that causes project data to leave the machine must reach "
                "its consent answer through the data's OWN project_uuid — never through "
                "cwd, a checkout, a repo slug or a machine-global arming flag (FR-019), "
                "and an inability to determine consent is never consent (FR-003).\n"
                "If this sink genuinely carries no project data, add an entry to "
                "_EGRESS_ALLOWLIST in this file naming the reason, and record the "
                "growth in tests/architectural/_baselines.yaml with a justification.\n"
                "Inventory: kitty-specs/journal-project-consent-3030-01KYKWQS/"
                "egress-inventory.md"
            )

    def test_known_ungated_egress_paths_are_closed(self) -> None:
        """The work-list must be empty. An entry here is a red build, not a skip.

        Empty today. It held E1/E2/E3 (FR-028/029/030) while this gate was being
        authored; those landed and moved to ``_EGRESS_ALLOWLIST``. The failure
        text this would print is exercised by
        ``TestGuardBites::test_recording_an_open_path_reds_with_its_requirement``,
        so the reporting path stays proven while the set is empty — an assertion
        over an empty collection is a pass for having done nothing, which is the
        shape this whole module exists to avoid.
        """
        if _KNOWN_UNGATED:
            pytest.fail(_worklist_failure_text(_KNOWN_UNGATED))


class TestAllowlistIntegrity:
    """Meta-tests: the allowlist must not rot into a second RETIRED_DRAIN_NAMES."""

    def test_allowlisted_files_exist(self) -> None:
        """No stale entry may silently permit a path that has moved or been deleted."""
        missing = sorted(relpath for relpath in _EGRESS_ALLOWLIST_FILES | _KNOWN_UNGATED_FILES if not (_SRC / relpath).is_file())
        assert not missing, (
            "Stale egress-boundary entries — these files no longer exist, so their "
            f"allowance permits nothing and hides nothing: {missing}. Remove them and "
            "shrink the matching baseline in tests/architectural/_baselines.yaml."
        )

    def test_every_listed_file_still_holds_a_sink(self) -> None:
        """An entry that no longer guards anything must be deleted, not kept.

        This is the half that stops the allowlist rotting: an entry whose sink was
        refactored away keeps a file permanently exempt, which is how a name-shaped
        guard becomes blind without anyone editing it.
        """
        sink_files = {site.relpath for site in _scan(_SRC)}
        inert = sorted((_EGRESS_ALLOWLIST_FILES | _KNOWN_UNGATED_FILES) - sink_files)
        assert not inert, (
            "Egress-boundary entries that no longer hold any transmit primitive: "
            f"{inert}. The exemption now covers nothing while still exempting the "
            "file from every future sink added to it — delete the entry."
        )

    def test_seam_allowances_name_a_live_seam(self) -> None:
        """A ``SEAM`` allowance is only as good as the symbol it names.

        The annotation is load-bearing, not a comment: if the consent call is
        refactored out of the seam module, the allowance stops being true and this
        reds — rather than the file staying quietly exempt.
        """
        broken: list[str] = []
        for relpath, allowance in sorted(_EGRESS_ALLOWLIST.items()):
            if allowance.kind is not AllowanceKind.SEAM:
                continue
            assert allowance.seam_symbol and allowance.seam_module, f"{relpath}: a SEAM allowance must name both seam_symbol and seam_module."
            seam_path = _SRC / allowance.seam_module
            if not seam_path.is_file():
                broken.append(f"{relpath}: seam module {allowance.seam_module} is missing")
                continue
            if allowance.seam_symbol not in seam_path.read_text(encoding="utf-8"):
                broken.append(f"{relpath}: seam {allowance.seam_symbol} is gone from {allowance.seam_module} ({allowance.inventory_id})")
        assert not broken, (
            "Egress allowances whose named consent seam no longer exists:\n  "
            + "\n  ".join(broken)
            + "\nThe file is still permitted to transmit while the thing that made "
            "that safe has been removed. Restore the seam or re-classify the entry."
        )

    def test_non_seam_allowances_declare_a_closed_reason(self) -> None:
        """Every non-``SEAM`` allowance must carry a real reason and its evidence."""
        for relpath, allowance in sorted(_EGRESS_ALLOWLIST.items()):
            assert allowance.note.strip(), f"{relpath}: allowance carries no rationale."
            assert allowance.inventory_id.strip(), f"{relpath}: allowance names no inventory id."
            if allowance.kind is AllowanceKind.UNREACHABLE:
                assert allowance.pinned_by, (
                    f"{relpath}: an UNREACHABLE allowance rests on 'no caller exists', "
                    "which is a claim about the whole tree — it must name the test that "
                    "pins it, or it is an assertion nothing re-checks."
                )
                assert (_REPO_ROOT / allowance.pinned_by).is_file(), f"{relpath}: pinned_by {allowance.pinned_by} does not exist."

    def test_allowlist_and_worklist_are_disjoint(self) -> None:
        """A file cannot be both gated and known-ungated."""
        overlap = sorted(_EGRESS_ALLOWLIST_FILES & _KNOWN_UNGATED_FILES)
        assert not overlap, (
            f"{overlap} appear in both _EGRESS_ALLOWLIST and _KNOWN_UNGATED. The "
            "work-list entry would then be unfalsifiable — clearing it would change "
            "nothing, because the allowlist already permits the file."
        )

    def test_every_worklist_entry_names_its_requirement_and_seam(self) -> None:
        """The work-list must stay actionable, or it becomes a permanent exemption.

        Vacuous while the set is empty, which is why
        ``TestGuardBites::test_worklist_schema_check_rejects_an_unclearable_entry``
        exercises the same validator against a malformed entry.
        """
        problems = _worklist_schema_violations(_KNOWN_UNGATED)
        assert not problems, "Work-list entries that cannot be cleared:\n  " + "\n  ".join(problems)


class TestCompletenessLimitsDocstring:
    """Meta-test: FR-013 (`#3113`). The docstring's numbered gap list must stay honest."""

    def test_limit_8_positional_transport_call_is_documented(self) -> None:
        """A future trim of limit 8 must red here, not go unnoticed.

        Before this change the list ran 1-7 (getattr-by-string; empty callback
        registries; dynamic import/``exec``; variable-command ``subprocess``;
        at-rest pooling; bare ``.put(x)``; multi-sink-per-file). `#3113` adds
        exactly one entry: the all-positional / no-``headers=`` transport call.
        """
        doc = __doc__ or ""
        assert "8. **The all-positional / no-``headers=`` transport call.**" in doc, (
            "Module docstring's 'Completeness limits' list no longer states limit 8 "
            "(the all-positional / no-headers= transport call, #3113/FR-013). This "
            "entry documents a real blind spot in _transmits_a_body: update this "
            "assertion to match new wording, do not delete it."
        )
        assert "resolve_workspace_for_wp" in doc and "get_wp_lane" in doc, (
            "Limit 8 must keep naming the reproducible FR-015 false-positive "
            "functions, or the recorded reason the matcher was left alone silently "
            "disappears from the one place a future reader would look."
        )


class TestGuardBites:
    """Negative controls. A guard never observed to fail is decoration.

    Three plugins on this mission rotted into exactly that and reported false
    confidence in both directions, so these controls exercise the real collection
    path and assert the failure text, not just a boolean.

    `#3113`'s generalisation: a negative control that only tests the shape you
    thought of is not a negative control. ``test_scanner_detects_each_sink_shape``
    exercised the injected-transport shape only in its kwargs form
    (``poster(url, data=body, headers=hdrs, ...)``); an all-positional call of
    the identical shape (``poster(url, body, hdrs)``) evaded both the
    method-name rule and ``_transmits_a_body`` while the bite-test reported
    "not blind." Every rule in the sink vocabulary should carry a bite-test
    case per **shape** it claims to cover, not one per rule.
    """

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            pytest.param(
                "import requests\ndef go(p):\n    requests.post('https://x', json=p)\n",
                SinkKind.HTTP_VERB,
                id="requests-post",
            ),
            pytest.param(
                "def go(client, p):\n    return client.put('https://x', json=p)\n",
                SinkKind.HTTP_VERB,
                id="client-put-literal-url",
            ),
            pytest.param(
                "def go(client, url, p):\n    return client.put(url, data=p)\n",
                SinkKind.HTTP_VERB,
                id="client-put-url-variable",
            ),
            pytest.param(
                "def go(client, m, u):\n    return client.request(m, u)\n",
                SinkKind.HTTP_VERB,
                id="client-request",
            ),
            pytest.param(
                "import urllib.request\ndef go(r):\n    urllib.request.urlopen(r)\n",
                SinkKind.URLOPEN,
                id="urllib-urlopen",
            ),
            pytest.param(
                "from urllib.request import urlopen\ndef go(r):\n    urlopen(r)\n",
                SinkKind.URLOPEN,
                id="bare-urlopen",
            ),
            pytest.param(
                "async def go(c, e):\n    await c.send_event(e)\n",
                SinkKind.SEND_EVENT,
                id="send-event",
            ),
            pytest.param(
                "async def go(self, e):\n    await self.ws.send(e)\n",
                SinkKind.WEBSOCKET_SEND,
                id="ws-send",
            ),
            pytest.param(
                "def go(receiver, batch):\n    return receiver.deliver(batch)\n",
                SinkKind.RECEIVER_DELIVER,
                id="receiver-deliver",
            ),
            pytest.param(
                "def go(poster, url, body, hdrs):\n    return poster(url, data=body, headers=hdrs, timeout=5.0)\n",
                SinkKind.TRANSPORT_CALL,
                id="injected-transport-parameter",
            ),
            pytest.param(
                "def go(self, url, body, hdrs):\n    return self._send(url, json=body, headers=hdrs)\n",
                SinkKind.TRANSPORT_CALL,
                id="aliased-transport-method",
            ),
            pytest.param(
                "def go(poster, url, body, hdrs):\n    return poster(url, body, hdrs)\n",
                SinkKind.TRANSPORT_CALL,
                id="injected-transport-positional-url-name",
                marks=pytest.mark.xfail(
                    reason=(
                        "#3113 case (A): all-positional injected transport whose first "
                        "argument name IS in _URL_ARG_NAMES. _transmits_a_body requires "
                        "headers= AND a body keyword (:295-306), so an all-positional call "
                        "is invisible regardless of argument names. This is limit 8 in the "
                        "module docstring's completeness-limits list. FR-015 measured the "
                        "structural tightening (bare-Name callee resolving to an enclosing "
                        "FunctionDef parameter) BEFORE any matcher edit and found a "
                        "non-zero false-positive count over src/ (resolve_workspace_for_wp, "
                        "locate_work_package, behind_commits_touch_only_planning_artifacts, "
                        "get_wp_lane), so per FR-015's acceptance criteria the matcher is "
                        "left alone and this case is pinned red rather than fixed. Red-first "
                        "quoted: 'AssertionError: scanner went blind to transport-call / "
                        "assert []'."
                    ),
                    strict=True,
                ),
            ),
            pytest.param(
                "def relay(post, u, payload, meta):\n    return post(u, payload, meta)\n",
                SinkKind.TRANSPORT_CALL,
                id="injected-transport-positional-non-url-name",
                marks=pytest.mark.xfail(
                    reason=(
                        "#3113 case (B) -- THE ADOPTION GATE: all-positional injected "
                        "transport whose argument names (post, u, payload, meta) are "
                        "OUTSIDE _URL_ARG_NAMES. A matcher that passed (A) above but failed "
                        "this case would still be blind in exactly the way #3113 is about, "
                        "because _attr_tail returns node.id verbatim for a bare Name "
                        "(:266-272) -- (A) alone would certify a blind matcher. Same "
                        "limit-8 gap as (A); same FR-015 non-adoption decision (non-zero "
                        "false positives over src/, measured before any matcher edit). "
                        "Red-first quoted: 'AssertionError: scanner went blind to "
                        "transport-call / assert []'."
                    ),
                    strict=True,
                ),
            ),
        ],
    )
    def test_scanner_detects_each_sink_shape(self, tmp_path: Path, source: str, expected: SinkKind) -> None:
        """Every shape in the vocabulary is detected, so none can go blind unnoticed."""
        module = tmp_path / "sender.py"
        module.write_text(source, encoding="utf-8")
        sites = _find_sinks(module, tmp_path)
        assert sites, f"scanner went blind to {expected.value}"
        assert sites[0].kind is expected

    def test_positional_transport_strict_xfail_landmines_disposition_still_pending(
        self,
    ) -> None:
        """WP06 (T028/T030, FR-015 fix-before-wiring): re-validate the two #3113
        strict-xfail landmines on the current tree.

        Re-validated in isolation: both ``injected-transport-positional-*``
        parametrized cases still report ``XFAIL`` (not ``XPASS``) -- FR-015's
        own non-adoption decision (a structural tightening that measured
        non-zero false positives over ``src/``) still holds, so the gap is
        still genuinely open. This guard pins that disposition: it fails if
        either case's marker is dropped, stops being ``strict=True``, or loses
        its ``#3113`` tracking reference without the underlying gap actually
        closing (``strict=True`` on the parametrized test itself already
        catches an unexpected XPASS).
        """
        marks = getattr(type(self).test_scanner_detects_each_sink_shape, "pytestmark", [])
        parametrize_marks = [m for m in marks if m.name == "parametrize"]
        assert len(parametrize_marks) == 1
        params = parametrize_marks[0].args[1]
        xfail_params = {p.id: [m for m in p.marks if m.name == "xfail"][0] for p in params if any(m.name == "xfail" for m in p.marks)}
        assert set(xfail_params) == {
            "injected-transport-positional-url-name",
            "injected-transport-positional-non-url-name",
        }
        for case_id, xfail_mark in xfail_params.items():
            assert xfail_mark.kwargs.get("strict") is True, case_id
            assert "#3113" in xfail_mark.kwargs.get("reason", ""), case_id

    def test_unlisted_sender_is_reported_with_its_seam(self, tmp_path: Path) -> None:
        """The whole collection path reds on a synthetic un-allowlisted sender."""
        pkg = tmp_path / "specify_cli" / "widen"
        pkg.mkdir(parents=True)
        (pkg / "exfil.py").write_text(
            "import requests\ndef ship(rows):\n    requests.post('https://saas.example/api/ingest', json=rows)\n",
            encoding="utf-8",
        )
        offenders = _collect_offenders(tmp_path, _EGRESS_ALLOWLIST_FILES, _KNOWN_UNGATED_FILES)
        assert [site.relpath for site in offenders] == ["specify_cli/widen/exfil.py"]
        assert offenders[0].lineno == 3
        assert "project_uuid" in _format(offenders)

    def test_the_shape_the_name_keyed_guard_missed_is_caught(self, tmp_path: Path) -> None:
        """``drain_queue(...)`` then ``urlopen(...)`` — probed to evade RETIRED_DRAIN_NAMES.

        ``tests/sync/test_no_queue_drain_constructed_3030.py`` keys on two literal
        names, so a queue-backed sender under any third name is invisible to it.
        Keying on the sink catches this because the shape cannot avoid having one.
        """
        pkg = tmp_path / "specify_cli" / "sync"
        pkg.mkdir(parents=True)
        (pkg / "resend.py").write_text(
            "import urllib.request\n"
            "def flush(queue, url):\n"
            "    for row in queue.drain_queue(limit=100):\n"
            "        req = urllib.request.Request(url, data=row)\n"
            "        urllib.request.urlopen(req)\n",
            encoding="utf-8",
        )
        offenders = _collect_offenders(tmp_path, _EGRESS_ALLOWLIST_FILES, _KNOWN_UNGATED_FILES)
        assert [(s.relpath, s.kind) for s in offenders] == [("specify_cli/sync/resend.py", SinkKind.URLOPEN)]

    def test_allowlisting_the_same_sender_clears_it(self, tmp_path: Path) -> None:
        """Positive control: the guard is discriminating, not unconditionally red.

        Without this, an always-red collector would satisfy every control above
        while telling us nothing about the allowlist mechanism.
        """
        pkg = tmp_path / "specify_cli" / "widen"
        pkg.mkdir(parents=True)
        (pkg / "exfil.py").write_text(
            "import requests\ndef ship(rows):\n    requests.post('https://x', json=rows)\n",
            encoding="utf-8",
        )
        cleared = _collect_offenders(
            tmp_path,
            _EGRESS_ALLOWLIST_FILES | {"specify_cli/widen/exfil.py"},
            _KNOWN_UNGATED_FILES,
        )
        assert cleared == []

    def test_the_e20_preflight_shape_is_caught(self, tmp_path: Path) -> None:
        """A second sink reached through an injected transport is not invisible.

        E20: ``run_server_preflight`` POSTs the full envelope stream through a
        ``poster(...)`` parameter, earlier in the same function as the delivery
        call the inventory named. A method-name rule cannot see a bare ``Name``
        call, so gating where the inventory pointed would have left the leak.
        """
        pkg = tmp_path / "specify_cli" / "sync" / "history_import"
        pkg.mkdir(parents=True)
        (pkg / "preflight.py").write_text(
            "import gzip, json\n"
            "def preflight(envelopes, *, url, token, poster):\n"
            "    body = gzip.compress(json.dumps({'events': list(envelopes)}).encode())\n"
            "    return poster(url, data=body, headers={'Authorization': token}, timeout=30)\n",
            encoding="utf-8",
        )
        offenders = _collect_offenders(tmp_path, _EGRESS_ALLOWLIST_FILES, _KNOWN_UNGATED_FILES)
        assert [(s.relpath, s.kind) for s in offenders] == [("specify_cli/sync/history_import/preflight.py", SinkKind.TRANSPORT_CALL)]
        assert "project_uuid" in _format(offenders)

    def test_request_value_constructors_are_not_sinks(self, tmp_path: Path) -> None:
        """``Request(url, data=..., headers=...)`` builds a value; it transmits nothing.

        Without this the callee-agnostic rule would flag every stdlib request
        construction, and the noise is what gets a gate weakened.
        """
        module = tmp_path / "build.py"
        module.write_text(
            "import urllib.request\ndef build(url, body, hdrs):\n    return urllib.request.Request(url, data=body, headers=hdrs)\n",
            encoding="utf-8",
        )
        assert _find_sinks(module, tmp_path) == []

    def test_recording_an_open_path_reds_with_its_requirement(self) -> None:
        """The work-list's reporting path stays proven while the set is empty.

        ``test_known_ungated_egress_paths_are_closed`` currently asserts over an
        empty dict, which passes for having done nothing. This exercises the text
        it would print, so a future entry cannot fail silently or unhelpfully.
        """
        entry = UngatedPath(
            inventory_id="E-synthetic",
            requirement="FR-999",
            seam_required="specify_cli.sync.consent, on the data's own project_uuid",
            note="Synthetic control; not a real path.",
        )
        text = _worklist_failure_text({"specify_cli/widen/exfil.py": entry})
        assert "specify_cli/widen/exfil.py" in text
        assert "FR-999" in text
        assert "seam required:" in text

    def test_worklist_schema_check_rejects_an_unclearable_entry(self) -> None:
        """An entry with no requirement or no seam is an exemption, not a work-list.

        Named, not counted. ``bad`` is defective in all three ways at once, so a
        count of three passes just as happily when one check fires three times and
        the other two are dead — which is how a schema guard quietly stops guarding
        two of the three ways an entry becomes unclearable.
        """
        bad = UngatedPath(inventory_id="E-x", requirement="soon", seam_required="  ", note="")
        problems = _worklist_schema_violations({"specify_cli/widen/exfil.py": bad})
        assert problems == [
            "specify_cli/widen/exfil.py: requirement 'soon' does not name an FR — nobody can tell when it clears",
            "specify_cli/widen/exfil.py: names no seam it has to call, so nobody can clear it",
            "specify_cli/widen/exfil.py: carries no description of the path",
        ]
        assert _worklist_schema_violations({}) == []

    def test_non_sink_code_is_not_flagged(self, tmp_path: Path) -> None:
        """No false positives on ordinary code, or the gate gets weakened to shut it up.

        This control earned its place: on its first run it caught ``mailbox.put``
        matching the ``.put`` verb, which would have made an unrelated queue write
        red the boundary — and the natural remedy for a spurious red is to weaken
        the gate. The scanner was narrowed instead (limit 6).
        """
        module = tmp_path / "quiet.py"
        module.write_text(
            "def go(mailbox, queue, parser, item):\n"
            "    mailbox.put(item)\n"
            "    queue.put(item, block=False, timeout=1)\n"
            "    parser.parse(item)\n"
            "    parser.send(item)\n"
            "    return item.post_id\n",
            encoding="utf-8",
        )
        assert _find_sinks(module, tmp_path) == []


# ---------------------------------------------------------------------------
# FR-015 (`#3113`): the src/-wide false-positive measurement for the candidate
# tightening, taken BEFORE any matcher edit (binding order, WP10 T031/T032).
# ---------------------------------------------------------------------------
#
# The candidate predicate: the callee is a bare ``ast.Name`` whose ``id``
# resolves to a parameter of the *enclosing* ``FunctionDef``/``AsyncFunctionDef``
# (nearest enclosing only) — transport injected as a parameter, decidable with
# no author-chosen word. This is deliberately NOT wired into ``_classify`` /
# ``_find_sinks`` above: ``_classify(node: ast.Call)`` is reached from a flat
# ``ast.walk(tree)`` at ``_find_sinks`` and carries no enclosing-scope
# information, so adopting the predicate for real would be a scanner
# restructure (threading the enclosing function's parameter set through the
# walk), not a branch edit. That cost is paid only if this measurement returns
# zero false positives. It does not — see below — so the real matcher (above)
# is untouched, and this section exists solely to make the false-positive
# count reproducible rather than a recollection.


def _fr015_candidate_param_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Every positional/positional-only/keyword-only parameter name of *fn*.

    ``*args``/``**kwargs`` are deliberately excluded: neither resolves to a
    single named parameter holding one callable value.
    """
    args = fn.args
    names = {a.arg for a in args.posonlyargs} | {a.arg for a in args.args} | {a.arg for a in args.kwonlyargs}
    return frozenset(names)


def _find_fr015_candidates(path: Path, root: Path) -> list[SinkSite]:
    """Every call in *path* whose callee is a bare Name resolving to a
    parameter of its nearest-enclosing function (FR-015's candidate predicate).

    Measurement-only, as above: this walks with enclosing-function parameter
    tracking that ``_find_sinks`` does not do, specifically so the FR-015
    false-positive count is measurable without restructuring the real gate.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a louder problem than this rule
        return []

    relpath = path.relative_to(root).as_posix()
    sites: list[SinkSite] = []
    param_stack: list[frozenset[str]] = []

    class _EnclosingParamVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            param_stack.append(_fr015_candidate_param_names(node))
            self.generic_visit(node)
            param_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            param_stack.append(_fr015_candidate_param_names(node))
            self.generic_visit(node)
            param_stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if param_stack and isinstance(node.func, ast.Name) and node.func.id in param_stack[-1]:
                sites.append(SinkSite(relpath=relpath, lineno=node.lineno, kind=SinkKind.TRANSPORT_CALL, snippet=node.func.id))
            self.generic_visit(node)

    _EnclosingParamVisitor().visit(tree)
    return sites


def _scan_fr015_candidates(root: Path) -> list[SinkSite]:
    """Every FR-015 candidate site under *root*, excluding ``__pycache__``."""
    sites: list[SinkSite] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sites.extend(_find_fr015_candidates(path, root))
    return sites


class TestFR015StructuralTighteningMeasurement:
    """`#3113` / FR-015: measured BEFORE any matcher edit, per the WP's binding order.

    Reproducible command::

        PYTHONPATH=<worktree>/src pytest \\
            tests/architectural/test_egress_consent_boundary.py::TestFR015StructuralTighteningMeasurement -v

    Measured at this commit: 1198 ``.py`` files under ``src/`` scanned; the
    candidate predicate (see the module-level comment above) finds 203
    candidate call sites in 112 files. Of those, 195 sites in 106 files are
    "new offenders" — in a file neither in ``_EGRESS_ALLOWLIST_FILES`` nor
    ``_KNOWN_UNGATED_FILES`` — and among the new offenders at least 5 are
    confirmed, reproducible false positives: calls to
    ``resolve_workspace_for_wp`` (twice, in two different files),
    ``locate_work_package``, ``behind_commits_touch_only_planning_artifacts``
    and ``get_wp_lane``, each a dependency-injected work-package/lane lookup
    function reached through a same-named ``Callable``-typed parameter — not a
    transport. (This aggregate site/file total differs from an earlier
    planning-time figure of 211 sites / 13 files; the 5 named false positives
    reproduce identically under either count, so the FR-015 decision — decline
    — does not depend on reconciling the totals. See WP10's transition note
    for the fuller reconciliation.)

    Per FR-015's acceptance criteria a non-zero false-positive count is itself
    the outcome: **the matcher is left alone.** This test pins that
    measurement rather than only asserting it once: it fails loudly if the
    four named false positives stop reproducing (the measurement rotted) or if
    the false-positive count ever drops to zero (the signal that FR-015's
    scanner restructure is now funded and this decision should be revisited).
    """

    #: The four functions FR-015's planning-time measurement named. Each is a
    #: real function elsewhere in the tree, reached here through a same-named
    #: ``Callable``-typed parameter (a dependency-injection pattern) — not a
    #: transport of any kind.
    _KNOWN_FALSE_POSITIVE_CALLEES: frozenset[str] = frozenset(
        {
            "resolve_workspace_for_wp",
            "locate_work_package",
            "behind_commits_touch_only_planning_artifacts",
            "get_wp_lane",
        }
    )

    def test_candidate_tightening_yields_nonzero_false_positives_over_src(self) -> None:
        files_scanned = [p for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts]
        candidates = _scan_fr015_candidates(_SRC)
        candidate_files = {c.relpath for c in candidates}

        permitted = _EGRESS_ALLOWLIST_FILES | _KNOWN_UNGATED_FILES
        new_offenders = [c for c in candidates if c.relpath not in permitted]
        new_offender_files = {c.relpath for c in new_offenders}

        reproduced = {c.snippet for c in new_offenders if c.snippet in self._KNOWN_FALSE_POSITIVE_CALLEES}
        assert reproduced == self._KNOWN_FALSE_POSITIVE_CALLEES, (
            f"Expected all four named FR-015 false positives to reproduce; got {sorted(reproduced)} "
            f"of {sorted(self._KNOWN_FALSE_POSITIVE_CALLEES)}. Input: {len(files_scanned)} .py files "
            f"scanned, {len(candidates)} candidate sites in {len(candidate_files)} files, "
            f"{len(new_offenders)} new-offender sites in {len(new_offender_files)} files. If this set "
            "has changed, the FR-015 measurement needs re-running before the non-adoption decision "
            "can be trusted."
        )
        assert len(new_offenders) > 0, (
            f"FR-015 candidate tightening measured 0 new-offender sites over src/ "
            f"({len(files_scanned)} .py files scanned, {len(candidates)} candidate sites in "
            f"{len(candidate_files)} files). Per FR-015's acceptance criteria this is the ADOPT "
            "branch: the scanner restructure (threading enclosing-FunctionDef parameter sets "
            "through _find_sinks) is now funded, and this module's 'matcher left alone' decision "
            "(limit 8, TestGuardBites' two xfail cases) is stale — revisit WP10 T031/T032."
        )


# ---------------------------------------------------------------------------
# Per-project store mission: named sender and local-writer hand-off (WP01).
# Issue-5-delete-sync-transport: the delivery/ and sync/ roots died with their
# transport; the census below now covers the two surviving hosted senders.
# ---------------------------------------------------------------------------

_PROJECT_SENDER_ROOTS = (
    _SRC / "specify_cli" / "tracker",
    _SRC / "specify_cli" / "saas_client",
)


@dataclass(frozen=True, order=True)
class _ProjectSinkSite:
    relpath: str
    qualname: str
    kind: SinkKind
    callee: str
    lineno: int
    canonical_attempt: bool

    @property
    def key(self) -> str:
        return f"{self.relpath}::{self.qualname}::{self.kind.value}::{self.callee}"


@dataclass(frozen=True)
class _ContextBinding:
    version: int
    dependency_versions: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class _AttemptBinding:
    version: int
    context_name: str
    context_version: int
    body_dump: str | None
    body_dependency_versions: tuple[tuple[str, int], ...]


@dataclass
class _SinkFlowState:
    aliases: dict[str, ast.expr] = field(default_factory=dict)
    versions: Counter[str] = field(default_factory=Counter)
    contexts: dict[str, _ContextBinding] = field(default_factory=dict)
    attempts: dict[str, _AttemptBinding] = field(default_factory=dict)
    eligible: dict[str, int] = field(default_factory=dict)

    def branch(self) -> _SinkFlowState:
        return _SinkFlowState(
            self.aliases.copy(),
            self.versions.copy(),
            self.contexts.copy(),
            self.attempts.copy(),
            self.eligible.copy(),
        )


class _SinkFunctionAnalyzer:
    def __init__(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        relpath: str,
        qualname: str,
    ) -> None:
        self.node = node
        self.relpath = relpath
        self.qualname = qualname
        self.sites: list[_ProjectSinkSite] = []

    @staticmethod
    def _argument_names(call: ast.Call) -> set[str]:
        return {child.id for argument in (*call.args, *(kw.value for kw in call.keywords)) for child in ast.walk(argument) if isinstance(child, ast.Name)}

    @staticmethod
    def _dependency_versions(
        expression: ast.expr,
        state: _SinkFlowState,
    ) -> tuple[tuple[str, int], ...]:
        return tuple(sorted((name, state.versions[name]) for name in _SinkFunctionAnalyzer._names(expression)))

    @staticmethod
    def _names(expression: ast.AST) -> set[str]:
        return {child.id for child in ast.walk(expression) if isinstance(child, ast.Name)}

    @staticmethod
    def _delivery_body(call: ast.Call, context_name: str) -> ast.expr | None:
        for keyword in call.keywords:
            if keyword.arg in {"body", "event", "payload"}:
                return keyword.value
        for argument in call.args:
            if not (isinstance(argument, ast.Name) and argument.id == context_name):
                return argument
        return None

    @staticmethod
    def _resolve_alias(
        expression: ast.expr,
        state: _SinkFlowState,
    ) -> ast.expr:
        resolved = expression
        seen: set[str] = set()
        while isinstance(resolved, ast.Name) and resolved.id in state.aliases:
            if resolved.id in seen:
                break
            seen.add(resolved.id)
            resolved = state.aliases[resolved.id]
        return resolved

    def _apply_binding(
        self,
        item: ast.Assign | ast.AnnAssign,
        state: _SinkFlowState,
    ) -> None:
        # TODO(#3280): Resolve tuple and other non-name assignment targets; current alias evidence is name-target only.
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        value = item.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            name = target.id
            alias = self._resolve_alias(value, state) if isinstance(value, (ast.Name, ast.Attribute)) else None
            state.versions[name] += 1
            state.aliases.pop(name, None)
            state.contexts.pop(name, None)
            state.attempts.pop(name, None)
            state.eligible.pop(name, None)
            if alias is not None:
                state.aliases[name] = alias
            if not isinstance(value, ast.Call):
                continue
            tail = _attr_tail(value.func)
            if tail == "ProjectSyncContext" and (value.args or any(keyword.arg == "project_uuid" for keyword in value.keywords)):
                project = next(
                    (keyword.value for keyword in value.keywords if keyword.arg == "project_uuid"),
                    value.args[0] if value.args else value,
                )
                state.contexts[name] = _ContextBinding(
                    state.versions[name],
                    self._dependency_versions(project, state),
                )
            elif tail == "DeliveryAttempt":
                context = next(
                    (candidate for candidate in self._argument_names(value) if candidate in state.contexts),
                    None,
                )
                if context is None:
                    continue
                context_binding = state.contexts[context]
                if any(state.versions[dependency] != version for dependency, version in context_binding.dependency_versions):
                    continue
                body = self._delivery_body(value, context)
                state.attempts[name] = _AttemptBinding(
                    state.versions[name],
                    context,
                    context_binding.version,
                    ast.dump(body, include_attributes=False) if body else None,
                    self._dependency_versions(body, state) if body else (),
                )

    def _guarded_attempt(
        self,
        test: ast.expr,
        state: _SinkFlowState,
    ) -> tuple[str | None, bool]:
        inverted = isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
        candidate = test.operand if isinstance(test, ast.UnaryOp) and inverted else test
        if not isinstance(candidate, ast.Call) or _attr_tail(candidate.func) != "final_transport_eligible":
            return None, inverted
        attempt = next(
            (name for name in self._argument_names(candidate) if name in state.attempts and state.attempts[name].version == state.versions[name]),
            None,
        )
        return attempt, inverted

    @staticmethod
    def _transmitted_body(call: ast.Call) -> ast.expr | None:
        for keyword in call.keywords:
            if keyword.arg in {"json", "data", "content", "body", "payload", "event"}:
                return keyword.value
        return call.args[-1] if call.args else None

    def _coherent_attempt(
        self,
        call: ast.Call,
        state: _SinkFlowState,
    ) -> bool:
        body = self._transmitted_body(call)
        if body is None:
            return False
        body_dump = ast.dump(body, include_attributes=False)
        body_names = self._names(body)
        for name, eligible_version in state.eligible.items():
            attempt = state.attempts.get(name)
            if attempt is None or attempt.version != eligible_version:
                continue
            context = state.contexts.get(attempt.context_name)
            stable = (
                state.versions[name] == attempt.version
                and context is not None
                and context.version == attempt.context_version
                and all(
                    state.versions[dependency] == version
                    for dependency, version in (
                        *context.dependency_versions,
                        *attempt.body_dependency_versions,
                    )
                )
            )
            related = name in body_names or (attempt.body_dump is not None and attempt.body_dump == body_dump)
            if stable and related:
                return True
        return False

    def _inspect_call(self, call: ast.Call, state: _SinkFlowState) -> None:
        resolved = call
        callee = ast.unparse(call.func)
        if isinstance(call.func, ast.Name) and call.func.id in state.aliases:
            alias = self._resolve_alias(call.func, state)
            resolved = ast.Call(
                func=alias,
                args=call.args,
                keywords=call.keywords,
            )
            callee = ast.unparse(alias)
        kind = _classify(resolved)
        if kind is None:
            return
        self.sites.append(
            _ProjectSinkSite(
                self.relpath,
                self.qualname,
                kind,
                callee,
                call.lineno,
                self._coherent_attempt(call, state),
            )
        )

    def _inspect_block(
        self,
        statements: list[ast.stmt],
        state: _SinkFlowState,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.If):
                # TODO(#3280): Join post-branch alias states; this bounded pass only follows each branch independently.
                attempt, inverted = self._guarded_attempt(statement.test, state)
                terminal_guard = bool(statement.body) and isinstance(
                    statement.body[-1],
                    (ast.Return, ast.Raise),
                )
                if attempt and not inverted:
                    body_state = state.branch()
                    body_state.eligible[attempt] = body_state.versions[attempt]
                    self._inspect_block(statement.body, body_state)
                else:
                    self._inspect_block(statement.body, state.branch())
                self._inspect_block(statement.orelse, state.branch())
                if attempt and inverted and terminal_guard:
                    state.eligible[attempt] = state.versions[attempt]
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for call in (child for child in ast.walk(statement) if isinstance(child, ast.Call)):
                self._inspect_call(call, state)
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                self._apply_binding(statement, state)

    def run(self) -> list[_ProjectSinkSite]:
        self._inspect_block(self.node.body, _SinkFlowState())
        return self.sites


class _ProjectSinkVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, source_root: Path) -> None:
        self.path = path
        self.source_root = source_root
        self.classes: list[str] = []
        self.sites: list[_ProjectSinkSite] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.classes.append(node.name)
        self.generic_visit(node)
        self.classes.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join((*self.classes, node.name))
        analyzer = _SinkFunctionAnalyzer(
            node,
            self.path.relative_to(self.source_root).as_posix(),
            qualname,
        )
        self.sites.extend(analyzer.run())

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node)


def _layout_paths(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Every ``*.py`` under each *root* (a directory expands, a file passes through)."""
    paths: list[Path] = []
    for root in roots:
        paths.extend(root.rglob("*.py") if root.is_dir() else [root])
    return tuple(sorted(set(paths)))


def _scan_project_sinks(
    paths: tuple[Path, ...] | None = None,
    *,
    source_root: Path = _SRC,
) -> tuple[_ProjectSinkSite, ...]:
    if paths is None:
        roots = _PROJECT_SENDER_ROOTS if source_root == _SRC else (source_root,)
        paths = _layout_paths(roots)
    sites: list[_ProjectSinkSite] = []
    for path in sorted(paths):
        visitor = _ProjectSinkVisitor(path, source_root)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        sites.extend(visitor.sites)
    return tuple(sorted(sites))


_KNOWN_PROJECT_SINK_COUNTS: Counter[str] = Counter(
    line.strip()
    for line in """
specify_cli/saas_client/client.py::SaasClient._exchange::http-verb::self._http.post
specify_cli/tracker/saas_client.py::SaaSTrackerClient._request::http-verb::client.request
specify_cli/tracker/saas_client.py::SaaSTrackerClient._physical_request_with_retry::transport-call::self._request
specify_cli/tracker/saas_client.py::SaaSTrackerClient._physical_request_with_retry::transport-call::self._request
specify_cli/tracker/saas_client.py::SaaSTrackerClient._physical_request_with_retry::transport-call::self._request
specify_cli/tracker/saas_client.py::SaaSTrackerClient._request_with_retry::transport-call::self._physical_request_with_retry
specify_cli/tracker/saas_client.py::SaaSTrackerClient.bind_confirm::transport-call::self._request_with_retry
specify_cli/tracker/saas_client.py::SaaSTrackerClient.bind_mission_origin::transport-call::self._request_with_retry
specify_cli/tracker/saas_client.py::SaaSTrackerClient.push::transport-call::self._request_with_retry
specify_cli/tracker/saas_client.py::SaaSTrackerClient.run::transport-call::self._request_with_retry
specify_cli/tracker/saas_readiness.py::_probe_reachability::urlopen::urllib.request.urlopen
""".splitlines()
    if line.strip()
)

#: Empty since issue-5-delete-sync-transport: its single entry was the deleted
#: sync daemon's quiesce/restart handshake. A loopback control sink reappearing
#: under the surviving roots reds the growth assertion below instead.
_WP10_LOOPBACK_CONTROL_SINK_COUNTS: Counter[str] = Counter()


def _new_sender_violations(
    sites: tuple[_ProjectSinkSite, ...],
    baseline: Counter[str],
) -> tuple[_ProjectSinkSite, ...]:
    seen: Counter[str] = Counter()
    violations: list[_ProjectSinkSite] = []
    for site in sites:
        seen[site.key] += 1
        if seen[site.key] > baseline[site.key] and not site.canonical_attempt:
            violations.append(site)
    return tuple(violations)


def test_source_discovered_sender_census_is_counted_and_shrink_only() -> None:
    sites = _scan_project_sinks()
    loopback = Counter(site.key for site in sites if site.key in _WP10_LOOPBACK_CONTROL_SINK_COUNTS)
    assert loopback == _WP10_LOOPBACK_CONTROL_SINK_COUNTS
    observed = Counter(site.key for site in sites if site.key not in _WP10_LOOPBACK_CONTROL_SINK_COUNTS)
    growth = observed - _KNOWN_PROJECT_SINK_COUNTS
    assert not growth, "new project sender sites:\n" + "\n".join(f"{key} (+{count})" for key, count in sorted(growth.items()))
    shrink = _KNOWN_PROJECT_SINK_COUNTS - observed
    if shrink:
        warnings.warn(
            "project sender census shrank: " + ", ".join(f"{key} (-{count})" for key, count in sorted(shrink.items())),
            stacklevel=1,
        )


def test_hosted_sender_census_is_exact_per_symbol_not_per_file() -> None:
    """The surviving hosted senders are pinned per symbol: a NEW transmit call inside an already-
    allowlisted file cannot be seen by the file-keyed gate above, so this exact census is what
    reds on it."""
    observed = Counter(site.key for site in _scan_project_sinks() if site.key not in _WP10_LOOPBACK_CONTROL_SINK_COUNTS)
    assert observed == _KNOWN_PROJECT_SINK_COUNTS


_T034_DURABLE_ADAPTER_SINK_COUNTS: Counter[str] = Counter(
    {
        "specify_cli/saas_client/client.py::SaasClient._exchange::http-verb::self._http.post": 1,
        "specify_cli/tracker/saas_client.py::SaaSTrackerClient._physical_request_with_retry::transport-call::self._request": 3,
        "specify_cli/tracker/saas_client.py::SaaSTrackerClient._request_with_retry::transport-call::self._physical_request_with_retry": 1,
    }
)


def _t034_durable_adapter_sink_counts(
    sites: tuple[_ProjectSinkSite, ...],
) -> Counter[str]:
    return Counter(site.key for site in sites if site.key in _T034_DURABLE_ADAPTER_SINK_COUNTS)


def test_t034_durable_adapter_sender_census_is_exact() -> None:
    assert _t034_durable_adapter_sink_counts(_scan_project_sinks()) == _T034_DURABLE_ADAPTER_SINK_COUNTS


def test_t034_durable_adapter_sender_census_rejects_extra_retry_mutant(
    tmp_path: Path,
) -> None:
    tracker = tmp_path / "specify_cli" / "tracker" / "saas_client.py"
    tracker.parent.mkdir(parents=True)
    tracker.write_text(
        "class SaaSTrackerClient:\n"
        "    def _physical_request_with_retry(self, payload):\n"
        "        self._request('POST', '/one', json=payload, headers={})\n"
        "        self._request('POST', '/two', json=payload, headers={})\n"
        "        self._request('POST', '/three', json=payload, headers={})\n"
        "        self._request('POST', '/mutant', json=payload, headers={})\n",
        encoding="utf-8",
    )

    observed = _t034_durable_adapter_sink_counts(_scan_project_sinks((tracker,), source_root=tmp_path))

    assert observed - _T034_DURABLE_ADAPTER_SINK_COUNTS == Counter(
        {"specify_cli/tracker/saas_client.py::SaaSTrackerClient._physical_request_with_retry::transport-call::self._request": 1}
    )


def test_new_sender_mutants_flow_through_real_collectors(tmp_path: Path) -> None:
    """A previously-unseen sender and an aliased transport, written into a synthetic root, must
    reach the real growth collector. (The layout-writer half of this plumbing test retired with
    the layout-writer census it exercised -- issue #5 deleted that scanner's only subjects.)"""
    sync_root = tmp_path / "specify_cli" / "sync"
    source = sync_root / "previously_unseen_sender.py"
    alias_source = sync_root / "aliased_transport.py"
    clean = sync_root / "wrapped_sender.py"
    sync_root.mkdir(parents=True)
    source.write_text(
        "def bypass(client, payload):\n"
        "    context = ProjectSyncContext(payload['project_uuid'])\n"
        "    attempt = DeliveryAttempt(context, payload)\n"
        "    final_transport_eligible(attempt)\n"
        "    wire = client.post\n"
        "    wire('/events', json=payload)\n"
        "    wire = safe\n"
        "    wire(payload)\n"
        "def exact_reviewer_bypass(client, payload):\n"
        "    ProjectSyncContext(payload['project_uuid'])\n"
        "    DeliveryAttempt(payload)\n"
        "    final_transport_eligible(payload)\n"
        "    client.post('/events', json=payload)\n"
        "def audit_header_decoy(client, payload, foreign_payload):\n"
        "    context = ProjectSyncContext(payload['project_uuid'])\n"
        "    attempt = DeliveryAttempt(context, payload)\n"
        "    if final_transport_eligible(attempt):\n"
        "        client.post('/events', json=foreign_payload, headers={'X-Audit': str(attempt)})\n"
        "def rebound_project(client, payload, a, b):\n"
        "    project = a.uuid\n"
        "    context = ProjectSyncContext(project)\n"
        "    project = b.uuid\n"
        "    attempt = DeliveryAttempt(context, payload)\n"
        "    if final_transport_eligible(attempt):\n"
        "        client.post('/events', json=attempt)\n",
        encoding="utf-8",
    )
    alias_source.write_text(
        "import httpx as wire\ndef send(payload):\n    wire.post('/events', json=payload)\n",
        encoding="utf-8",
    )
    clean.write_text(
        "def send(client, payload):\n"
        "    context = ProjectSyncContext(payload['project_uuid'])\n"
        "    attempt = DeliveryAttempt(context, payload)\n"
        "    if final_transport_eligible(attempt):\n"
        "        client.post('/events', json=attempt)\n",
        encoding="utf-8",
    )
    sink_sites = _scan_project_sinks(source_root=tmp_path)
    violations = _new_sender_violations(sink_sites, Counter())
    assert {site.relpath for site in violations} == {
        "specify_cli/sync/aliased_transport.py",
        "specify_cli/sync/previously_unseen_sender.py",
    }
    assert all(not site.canonical_attempt for site in sink_sites if site.relpath == "specify_cli/sync/previously_unseen_sender.py")
    assert all(site.canonical_attempt for site in sink_sites if site.relpath == "specify_cli/sync/wrapped_sender.py")


def test_sender_aliases_resolve_transitively(tmp_path: Path) -> None:
    source = tmp_path / "specify_cli" / "sync" / "alias_chain.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def alias_chain(client, payload):\n    wire = client.post\n    send = wire\n    send('/events', json=payload)\n",
        encoding="utf-8",
    )
    sites = _scan_project_sinks(source_root=tmp_path)
    assert [(site.qualname, site.callee) for site in sites] == [("alias_chain", "client.post")]
