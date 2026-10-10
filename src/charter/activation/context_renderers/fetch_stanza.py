"""Canonical fetch + when-doing stanza formatter (WP05 T020).

This helper centralises the wire format used by every renderer that
emits the *verbatim-OR-fetch* pair pinned by the prompt-governance
ATDD contract:

* line 1 — ``Run: spec-kitty charter context --include <selector>``
* line 2 — ``When you <verb-clause>, run this command and apply the
  returned rule.``

The pair is matched by the ATDD helpers ``_FETCH_CMD_RE`` and
``_WHEN_DOING_RE`` in
``tests/specify_cli/next/test_wp_prompt_governance_contract.py``.  Drift
on either half is a contract violation — keep the strings here in sync
with the contract document
``kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md``
(section 2 "Verbatim-OR-fetch stanza") if either ever needs to change.

The shared formatter is used by:

* WP03 profile-cited directive / tactic rendering (over-budget per-entry
  substitution),
* WP04 action-critical section rendering (missing-section fall-through),
* WP05 token-budget substitution (longest-body swap).
"""

from __future__ import annotations

import re

from charter.offering.artifact_kinds import ArtifactKind

__all__ = [
    "DEFAULT_WHEN_CLAUSE",
    "fetch_stanza",
    "fetch_stanza_lines",
    "format_selector",
    "render_fetch_stanza",
]


DEFAULT_WHEN_CLAUSE: str = "are about to apply a code change"
"""Fallback when-doing clause when no domain-specific copy is available.

The clause matches the ``_WHEN_DOING_RE`` regex (anchor: ``are about
to``) so it always satisfies the prompt-governance contract — see
``tests/specify_cli/next/test_wp_prompt_governance_contract.py``.
"""


# ``_WHEN_DOING_RE`` (tests/specify_cli/next/test_wp_prompt_governance_contract.py:221)
# is a CLOSED 6-verb set: "when you (are about to|need to|encounter|introduce|
# rename|review)". Authored `when` clauses (packs/built-in/agent_profile.graph.yaml)
# are frequently gerund phrases ("designing or reviewing ...") or full sentences
# (STATED_DEFAULT_WHEN) that read as ungrammatical -- or silently break the
# contract -- once spliced verbatim into "When you <clause>, ...". The helpers
# below normalize an arbitrary clause into a form headed by one of the six
# lead-ins WITHOUT widening the regex (#3082 / NFR-003).
_LEAD_IN_ALTERNATION = r"(?:are\s+about\s+to|need\s+to|encounter|introduce|rename|review)"
_LEAD_IN_RE = re.compile(rf"^{_LEAD_IN_ALTERNATION}\b", re.IGNORECASE)
_LEADING_WHEN_RE = re.compile(r"^when\s+", re.IGNORECASE)
_GERUND_LEAD_RE = re.compile(r"^[A-Za-z]+ing\b")


def _normalize_when_clause(clause: str) -> str:
    """Map an authored ``when`` clause into the closed ``_WHEN_DOING_RE`` set.

    Rules, in order:

    1. Already headed by one of the six lead-ins (``are about to``, ``need
       to``, ``encounter``, ``introduce``, ``rename``, ``review``) — pass
       through byte-unchanged (no regression on the good path).
    2. A redundant leading ``when `` conjunction (authored e.g. ``when
       assessing whether tests meet the quality gate ...``) is stripped
       before the remaining rules apply, so the emitted line never doubles
       into ``When you when ...``.
    3. A leading gerund (``designing or reviewing ...``) cannot be
       re-inflected into a verb reliably (English morphology is irregular),
       so it re-anchors to the safe default :data:`DEFAULT_WHEN_CLAUSE`.
    4. Anything else — typically a full clause/sentence such as
       :data:`~charter.activation.progressive_disclosure.STATED_DEFAULT_WHEN` — has its
       trailing period stripped (so the stanza's own terminator is not
       doubled) and is re-anchored with the ``need to`` lead-in.
    """
    stripped = clause.strip()
    if not stripped:
        return DEFAULT_WHEN_CLAUSE
    candidate = _LEADING_WHEN_RE.sub("", stripped, count=1)
    if _LEAD_IN_RE.match(candidate):
        return candidate
    if _GERUND_LEAD_RE.match(candidate):
        return DEFAULT_WHEN_CLAUSE
    without_period = candidate[:-1] if candidate.endswith(".") else candidate
    if not without_period:
        return DEFAULT_WHEN_CLAUSE
    anchored = without_period[0].lower() + without_period[1:]
    return f"need to {anchored}"


# The selector kinds the ``charter context --include`` surface accepts: the
# charter-activatable kind singulars plus the non-kind ``section`` selector.
# Derived from the single :class:`ArtifactKind` authority
# (:attr:`~charter.offering.artifact_kinds.ArtifactKind.activatable`) rather than
# hand-listed so it cannot drift from the enum; ``section`` is not a kind, so it
# is unioned in explicitly. This set is behaviorally inert — ``format_selector``'s
# valid and invalid branches are identical — so keying it on ``activatable`` (the
# honest "kinds ``charter context --include`` accepts" set) rather than the
# retired ``core`` set (#5824) carries no behavior change.
_VALID_SELECTOR_KINDS: frozenset[str] = frozenset(k.value for k in ArtifactKind if k.activatable) | {"section"}


def format_selector(kind: str, identifier: str) -> str:
    """Return the canonical ``<kind>:<identifier>`` selector.

    ``kind`` is normalised to lowercase and validated against the set of
    selector kinds the ``spec-kitty charter context --include`` surface
    accepts (for example, ``directive``, ``tactic``, ``styleguide``, and
    ``section``).  An unknown kind is permitted (returned as-is) so callers can
    extend the vocabulary without code changes here, but the canonical kinds
    are guaranteed to round-trip through the validator unchanged.
    """

    cleaned_kind = (kind or "").strip().lower()
    cleaned_id = (identifier or "").strip()
    if not cleaned_kind or not cleaned_id:
        return ""
    if cleaned_kind not in _VALID_SELECTOR_KINDS:
        # Permissive on unknown kinds — keep callers extensible.
        return f"{cleaned_kind}:{cleaned_id}"
    return f"{cleaned_kind}:{cleaned_id}"


def fetch_stanza(
    selector: str,
    when_doing_clause: str,
    *,
    indent: str = "",
) -> str:
    """Return the two-line fetch + when-doing stanza for *selector*.

    Parameters
    ----------
    selector:
        The canonical ``<kind>:<identifier>`` selector (see
        :func:`format_selector`).  Used verbatim in the rendered
        ``--include`` argument.
    when_doing_clause:
        The verb-phrase that completes the ``When you <clause>, ...``
        sentence.  When empty, falls back to :data:`DEFAULT_WHEN_CLAUSE`
        so the ATDD ``_WHEN_DOING_RE`` regex always matches.
    indent:
        Optional leading indentation applied to both lines.  The default
        of an empty string keeps the stanza top-level; callers nesting
        the stanza inside a list-item block typically pass ``"  "`` or
        ``"    "``.

    Returns
    -------
    str
        Newline-joined two-line stanza.
    """

    clause = (when_doing_clause or "").strip() or DEFAULT_WHEN_CLAUSE
    return "\n".join(fetch_stanza_lines(selector, clause, indent=indent))


def fetch_stanza_lines(
    selector: str,
    when_doing_clause: str,
    *,
    indent: str = "",
) -> list[str]:
    """List-form variant of :func:`fetch_stanza` for line-oriented callers.

    The list is always exactly two strings; callers that build the
    rendered payload as a ``list[str]`` (most of ``context.py``) extend
    their working list with this result instead of splitting the joined
    string.
    """

    clause = (when_doing_clause or "").strip() or DEFAULT_WHEN_CLAUSE
    clause = _normalize_when_clause(clause)
    return [
        f"{indent}Run: spec-kitty charter context --include {selector}",
        f"{indent}When you {clause}, run this command and apply the returned rule.",
    ]


def render_fetch_stanza(
    *,
    selector: str,
    when_clause: str,
) -> list[str]:
    """Render the canonical fetch + when-doing stanza for a single entry.

    Public renderer form folded from ``charter.activation.context._render_fetch_stanza``
    (WP01/#3082 T003): a thin wrapper around :func:`fetch_stanza_lines` with
    the four-space indent every profile-section renderer (WP03 profile-cited,
    WP04 section bodies, WP05 budget substitution) already expects, so every
    caller emits identical bytes.
    """
    return list(fetch_stanza_lines(selector, when_clause, indent="    "))
