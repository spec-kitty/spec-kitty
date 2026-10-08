"""Activation-stanza renderer (WP05 body).

This module is the WP05-owned implementation surface for FR-007 (trigger
stanza wiring).  WP04 places the call site in
:func:`charter.activation.context._render_bootstrap_text` so the activation hook is
exercised end-to-end as soon as WP05 fills in :func:`render_activation_stanza`.

Render contract
---------------
For each :class:`charter.activation.activations.ActivationEntry` whose
``activation_context`` matches the runtime ``(mission_type, action)``
pair (per :func:`charter.activation.activations.resolve_for_context`), the renderer
emits a two-line *fetch + when-doing* stanza pinned by the
prompt-governance contract::

    Run: spec-kitty charter context --include <kind>:<artifact_id>
    When you are about to <verb-clause>, run this command and apply the returned rule.

Verb-clause synthesis (per WP05 T022 wildcard handling):

* declared ``mission_type`` is absent / ``generic`` / ``any``
  -> qualifier omitted ("When you are about to <action>, ...")
* declared ``mission_type`` is concrete
  -> qualifier appended ("When you are about to <action> in a
  <mission_type> mission, ...")
* declared ``action`` is absent / ``generic`` / ``any``
  -> the runtime action label is used ("When you are about to implement, ...")
* declared ``action`` is concrete
  -> the declared action label is used, with underscores expanded into
  natural prose for the four fine-grained tokens (``write_comment``
  -> "write a code comment", ``write_docstring`` -> "write a docstring",
  ``rename_identifier`` -> "rename an identifier", ``add_dependency``
  -> "add a dependency").  Other tokens fall through verbatim.

The rendered block is prefixed by a ``Selected activations:`` header so
it parses as a discrete section of the bootstrap context.  An empty
match-set produces ``""`` (no header emitted) per WP05 acceptance
criteria.

Concatenation policy
--------------------
Multiple matched entries are rendered in the input order returned by
:func:`charter.activation.activations.resolve_for_context` (which preserves
declaration order across the three charter sources — see
data-model.md §4 "Merge semantics across the three sources").  This is
the documented "concatenate" policy from
``contracts/activation-registry.md`` -> "Failure Modes".

Layer rule
----------
``src/charter/`` MUST NOT import from ``specify_cli`` (C-001, hard
ratchet pinned by ``tests/architectural/test_layer_rules.py``).  This
module stays self-contained accordingly; the
:class:`charter.offering.service.CharterOfferingService` instance is passed in by the
caller rather than constructed here.
"""

from __future__ import annotations

from charter.activation.activations import (
    ALLOWED_ACTIONS,
    ActivationEntry,
    normalize_artifact_kind,
    resolve_for_context,
)
from charter.activation.context_renderers.fetch_stanza import (
    fetch_stanza_lines,
    format_selector,
)
from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR,
    CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL,
)


__all__ = ["render_activation_stanza"]


_ACTIVATION_HEADER = "Selected activations:"


#: Wildcard tokens that suppress a slot qualifier in the rendered prose.
#: Mirrors the wildcard set in :mod:`charter.activation.activations` (kept local to
#: avoid leaking the private ``_ACTION_WILDCARDS`` constant — the runtime
#: contract is byte-equality of the rendered output, not symbol identity).
_WILDCARD_TOKENS: frozenset[str] = frozenset({"generic", "any"})


#: Operator-friendly prose for the four fine-grained sub-action tokens
#: that live in ``REGISTERED_TRIGGERS`` but not ``ALLOWED_ACTIONS``.  The
#: ATDD test ``test_case_1_styleguide_render_includes_trigger_stanza`` pins
#: the canonical conditional plus the phrase "write a code comment", so the
#: ``write_comment`` mapping in particular MUST resolve to that phrase.
_FINE_GRAINED_ACTION_PROSE: dict[str, str] = {
    "write_comment": "write a code comment",
    "write_docstring": "write a docstring",
    "rename_identifier": "rename an identifier",
    "add_dependency": "add a dependency",
}


#: Operator-facing prose for mission/action tokens whose raw token is not
#: grammatical after ``are about to``.
_ACTION_PROSE: dict[str, str] = {
    "tasks": "work on tasks",
    "charter.interview": "conduct a charter interview",
    "charter.generate": "generate a charter",
    "charter.context": "load charter context",
}


#: Mapping of the charter-activatable (plural) ``ActiveCharterService`` property
#: names to the corresponding ``service.<property>`` attribute name.  Used
#: by :func:`_infer_kind` to scan the service when an operator omits
#: ``artifact_kind``.
#:
#: Derived from the single charter-activatable kind authority (FR-004): the
#: property name equals the plural for every kind. The prior hand-copied literal
#: had drifted two kinds behind (missing ``glossary_packs`` and
#: ``anti_patterns``), blinding kind inference for those kinds (#2981). Deriving
#: it restores ``glossary_packs`` inference (a real ``service.glossary_packs``
#: repo); ``anti_patterns`` is inert here — :func:`_infer_kind` reads it via
#: ``getattr(service, prop, None)`` and there is no ``service.anti_patterns``
#: repo, so it simply never matches.
_KIND_TO_PROPERTY: dict[str, str] = {
    plural: plural for plural in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.values()
}


def render_activation_stanza(
    entries: list[ActivationEntry],
    service: object,
    *,
    mission_type: str,
    action: str,
) -> str:
    """Render activation-registry entries matching the runtime context.

    Parameters
    ----------
    entries:
        The merged activation list (project + org + profile sources, per
        WP08 — WP05 ships the renderer that consumes the merged list
        regardless of how many sources contributed).
    service:
        A :class:`charter.offering.service.CharterOfferingService` (or compatible) used
        to disambiguate the ``artifact_kind`` when an entry omits it.
        May be ``None`` -- in which case kind inference is skipped and
        entries without a declared ``artifact_kind`` are rendered with
        their best-guess plural kind from the entry alone (which may
        fail gracefully and surface a generic ``artifact:`` selector).
    mission_type:
        The active mission type (e.g. ``"software-dev"``).
    action:
        The active mission action (e.g. ``"implement"``).

    Returns
    -------
    str
        A newline-joined block headed by ``Selected activations:`` with
        one fetch + when-doing stanza per matching entry, or ``""`` when
        no entries match.
    """

    if not entries:
        return ""

    matched = resolve_for_context(
        list(entries),
        mission_type=mission_type,
        action=action,
    )
    if not matched:
        return ""

    lines: list[str] = [_ACTIVATION_HEADER]
    for entry in matched:
        stanza_lines = _render_entry(entry, service, action=action)
        # Add a leading blank line between header and the first stanza,
        # and between consecutive stanzas, so the block renders as
        # discrete two-line groups inside the larger bootstrap text.
        if len(lines) > 1:
            lines.append("")
        lines.extend(stanza_lines)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-entry rendering helpers
# ---------------------------------------------------------------------------


def _render_entry(
    entry: ActivationEntry,
    service: object,
    *,
    action: str,
) -> list[str]:
    """Render one :class:`ActivationEntry` as a fetch + when-doing stanza.

    The two-line output is generated by
    :func:`charter.activation.context_renderers.fetch_stanza.fetch_stanza_lines` so
    the wire format stays byte-identical to every other fetch stanza in
    the bootstrap context (matched by the ATDD ``_FETCH_CMD_RE`` /
    ``_WHEN_DOING_RE`` regexes).

    The runtime ``mission_type`` is intentionally NOT a parameter here:
    the rendered qualifier reads off the entry's *declared* mission_type
    (per the wildcard rules in the module docstring), not off the
    runtime context.  Filtering by runtime mission_type already happened
    in :func:`charter.activation.activations.resolve_for_context`.
    """
    kind_plural = entry.artifact_kind or _infer_kind(entry.artifact_id, service)
    kind_singular = _singular_kind(kind_plural) if kind_plural else "artifact"
    selector = format_selector(kind_singular, entry.artifact_id)
    when_clause = _render_when_clause(entry, action=action)
    return fetch_stanza_lines(selector, when_clause)


def _render_when_clause(
    entry: ActivationEntry,
    *,
    action: str,
) -> str:
    """Synthesise the canonical when-doing verb phrase for *entry*.

    See module docstring for the full wildcard / fine-grained rules.
    The returned string is passed verbatim to
    :func:`fetch_stanza_lines`, which prepends ``"When you "`` and
    appends the trailing clause ``", run this command and apply the
    returned rule."`` — so this function returns ONLY the verb-clause
    body (``"are about to write a code comment"``,
    ``"are about to implement in a software-dev mission"``, etc.).
    """
    declared_mt = entry.activation_context.get("mission_type")
    declared_action = entry.activation_context.get("action")

    # Action label: fine-grained tokens get prose-mapped; ALLOWED_ACTIONS
    # verbs are used verbatim; wildcards fall back to the runtime
    # action.
    action_label = (
        _action_label_for(action)
        if declared_action is None or declared_action in _WILDCARD_TOKENS
        else _action_label_for(declared_action)
    )

    # Mission-type qualifier: dropped on wildcard / absent.
    qualifier = (
        ""
        if declared_mt in (None, *_WILDCARD_TOKENS)
        else f" in a {declared_mt} mission"
    )

    return f"are about to {action_label}{qualifier}"


def _action_label_for(action_token: str) -> str:
    """Map *action_token* to its operator-facing prose label.

    The four fine-grained tokens (``write_comment``, ``write_docstring``,
    ``rename_identifier``, ``add_dependency``) get explicit natural-prose
    mappings -- the ATDD test pins ``"write a code comment"`` for
    ``write_comment``.  Mission-type / charter-loop verbs in
    ``ALLOWED_ACTIONS`` (``implement``, ``review``, etc.) are usually
    used verbatim; non-verb tokens are mapped to grammatical prose.
    Unknown tokens fall through verbatim.
    """
    if action_token in _FINE_GRAINED_ACTION_PROSE:
        return _FINE_GRAINED_ACTION_PROSE[action_token]
    if action_token in _ACTION_PROSE:
        return _ACTION_PROSE[action_token]
    if action_token in ALLOWED_ACTIONS:
        return action_token
    return action_token


def _singular_kind(plural_kind: str) -> str:
    """Return the singular form of *plural_kind* for the fetch selector.

    The ``--include <kind>:<id>`` surface uses singular tokens by
    convention (``directive:DIRECTIVE_010``, ``tactic:foo``,
    ``styleguide:caveman-comments``).  This helper inverts the
    plural-canonical kind back to the singular form expected by the
    selector.  Unknown plurals are returned unchanged so a future kind
    addition doesn't crash the renderer.

    Derived from the single charter-activatable kind authority
    (:data:`charter.offering.artifact_kinds.CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR`,
    FR-004) — no local plural↔singular kind dict.  The prior local literal had
    drifted two kinds behind (missing ``glossary_packs`` and ``anti_patterns``),
    so ``_singular_kind("glossary_packs")`` failed open and rendered the plural
    token verbatim (#2981); deriving it fixes that.
    """
    return CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR.get(plural_kind, plural_kind)


def _infer_kind(artifact_id: str, service: object) -> str | None:
    """Scan *service* for the (plural) kind owning *artifact_id*.

    Returns ``None`` when *service* is ``None`` or when no repository on
    the service exposes *artifact_id*.  Returns the plural kind name
    (``"styleguides"``) of the FIRST repository to claim the id; ties
    are rare in practice (artifact IDs are kind-scoped by convention)
    and an explicit ``artifact_kind`` is the documented escape hatch
    (``contracts/activation-registry.md`` -> "Failure Modes").

    The kind inference walks the 8 canonical
    :class:`charter.offering.service.CharterOfferingService` properties via
    :data:`_KIND_TO_PROPERTY`.  Each property is expected to expose a
    membership-test surface (``__contains__`` / ``get`` / iterable of
    ids) -- we try them in turn so we stay compatible with whatever
    shape the service repositories happen to use.
    """
    if service is None:
        return None
    for kind, prop in _KIND_TO_PROPERTY.items():
        repo = getattr(service, prop, None)
        if repo is None:
            continue
        if _repo_contains(repo, artifact_id):
            return kind
    return None


def _repo_contains(repo: object, artifact_id: str) -> bool:
    """Best-effort membership test against an offering repository.

    The offering repositories are not a uniform shape; this helper tries
    the three patterns commonly observed:

    * ``repo[artifact_id]`` raises ``KeyError`` on miss
    * ``repo.get(artifact_id)`` returns ``None`` on miss
    * ``artifact_id in repo`` for set-like surfaces

    Returns ``False`` on any exception so kind inference stays
    crash-free in the prompt-build hot path.
    """
    # Try get() first — most repositories expose it as the canonical
    # lookup-or-None surface.
    getter = getattr(repo, "get", None)
    if callable(getter):
        try:
            return getter(artifact_id) is not None
        except Exception:  # noqa: BLE001 — defensive: never crash the renderer
            pass

    # Fall back to __contains__ for set-like / list-like surfaces.
    try:
        return artifact_id in repo  # type: ignore[operator]
    except Exception:  # noqa: BLE001 — defensive: never crash the renderer
        return False


# Keep ``normalize_artifact_kind`` reachable for tests that want to
# validate the renderer's normalisation behaviour without depending on
# the activations module's private constants.
_normalize_artifact_kind = normalize_artifact_kind
