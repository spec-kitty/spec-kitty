"""ActionRouter: deterministic request → (profile_id, action) mapping.

ADR-3 (Option A): pure function over canonical role verbs and profile domain keywords.
No I/O, no network, no LLM call at any point.

See: kitty-specs/profile-invocation-runtime-audit-trail-01KPQRX2/adr-3-deterministic-action-router.md
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from charter.profiles import DEFAULT_ROLE_CAPABILITIES, Role

from specify_cli.invocation.errors import RouterAmbiguityError
from specify_cli.invocation.registry import ProfileRegistry

# ---------------------------------------------------------------------------
# Stop-words stripped during token normalization (ADR-3 §"Token normalization")
# ---------------------------------------------------------------------------

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "can",
        "please",
        "kindly",
        "some",
        "for",
        "me",
        "us",
        "our",
        "my",
        "to",
        "and",
        "or",
        "in",
        "on",
        "at",
        "of",
        "with",
        "by",
    }
)

# ---------------------------------------------------------------------------
# CANONICAL_VERB_MAP: request token → (canonical_action, Role)
# Authoritative table per ADR-3 §"CANONICAL_VERB_MAP"
# ---------------------------------------------------------------------------

CANONICAL_VERB_MAP: dict[str, tuple[str, Role]] = {
    # IMPLEMENTER
    "implement": ("implement", Role.IMPLEMENTER),
    "build": ("implement", Role.IMPLEMENTER),
    "code": ("implement", Role.IMPLEMENTER),
    "develop": ("implement", Role.IMPLEMENTER),
    "create": ("implement", Role.IMPLEMENTER),
    "write": ("implement", Role.IMPLEMENTER),
    "generate": ("implement", Role.IMPLEMENTER),
    "produce": ("implement", Role.IMPLEMENTER),
    "output": ("implement", Role.IMPLEMENTER),
    "refine": ("implement", Role.IMPLEMENTER),
    "improve": ("implement", Role.IMPLEMENTER),
    "fix": ("implement", Role.IMPLEMENTER),
    "patch": ("implement", Role.IMPLEMENTER),
    "repair": ("implement", Role.IMPLEMENTER),
    "debug": ("implement", Role.IMPLEMENTER),
    # REVIEWER
    "review": ("review", Role.REVIEWER),
    "check": ("review", Role.REVIEWER),
    "inspect": ("review", Role.REVIEWER),
    "evaluate": ("review", Role.REVIEWER),
    "audit": ("review", Role.REVIEWER),
    "assess": ("review", Role.REVIEWER),
    # PLANNER
    "plan": ("plan", Role.PLANNER),
    "decompose": ("plan", Role.PLANNER),
    "break": ("plan", Role.PLANNER),
    "outline": ("plan", Role.PLANNER),
    "schedule": ("plan", Role.PLANNER),
    "prioritize": ("plan", Role.PLANNER),
    "triage": ("plan", Role.PLANNER),
    "rank": ("plan", Role.PLANNER),
    "order": ("plan", Role.PLANNER),
    # ARCHITECT
    "specify": ("specify", Role.ARCHITECT),
    "spec": ("specify", Role.ARCHITECT),
    "define": ("specify", Role.ARCHITECT),
    "requirements": ("specify", Role.ARCHITECT),
    "scope": ("specify", Role.ARCHITECT),
    # DESIGNER
    "design": ("design", Role.DESIGNER),
    "mockup": ("design", Role.DESIGNER),
    "prototype": ("design", Role.DESIGNER),
    "wireframe": ("design", Role.DESIGNER),
    # RESEARCHER
    "analyze": ("analyze", Role.RESEARCHER),
    "investigate": ("analyze", Role.RESEARCHER),
    "research": ("analyze", Role.RESEARCHER),
    "explore": ("analyze", Role.RESEARCHER),
    "study": ("analyze", Role.RESEARCHER),
    "summarize": ("analyze", Role.RESEARCHER),
    "synthesize": ("analyze", Role.RESEARCHER),
    "compile": ("analyze", Role.RESEARCHER),
    "report": ("analyze", Role.RESEARCHER),
    # CURATOR
    "curate": ("curate", Role.CURATOR),
    "classify": ("curate", Role.CURATOR),
    "organize": ("curate", Role.CURATOR),
    "tag": ("curate", Role.CURATOR),
    "validate": ("curate", Role.CURATOR),
    "verify": ("curate", Role.CURATOR),
    # MANAGER
    "coordinate": ("coordinate", Role.MANAGER),
    "manage": ("coordinate", Role.MANAGER),
    "delegate": ("coordinate", Role.MANAGER),
    "monitor": ("coordinate", Role.MANAGER),
    "track": ("coordinate", Role.MANAGER),
}


# ---------------------------------------------------------------------------
# RouterDecision: frozen result returned on successful routing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouterDecision:
    """Resolved routing result — immutable, serializable."""

    profile_id: str
    action: str
    # "generic_fallback" (WP02/#3064): pinned by
    # specify_cli.invocation.empty_charter.resolve_generic_fallback when the
    # project charter is wholly empty -- never produced by ActionRouter.route()
    # itself (that seam pre-empts the router entirely at the executor branch).
    confidence: Literal["exact", "canonical_verb", "domain_keyword", "generic_fallback"]
    match_reason: str
    # WP2/#3840 (FR-005): every non-winning candidate the router considered,
    # each {"profile_id", "action", "confidence", "match_reason"}. Always a
    # list, never None -- no default, so every construction site must supply
    # it explicitly (mypy --strict enforces this at every production site).
    alternatives: list[dict[str, str]]


# ---------------------------------------------------------------------------
# ActionRouterPlugin: no-op Protocol stub (ADR-3 §"Future Extension Point")
# Reserved for future hybrid routing; not called in v1.
# ---------------------------------------------------------------------------


class ActionRouterPlugin:
    """No-op Protocol stub — reserved for future hybrid routing extension.

    A future release will implement this Protocol to add an LLM fallback
    path that activates only on ROUTER_NO_MATCH.  Not called in v1.
    """


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _normalize_tokens(text: str) -> list[str]:
    """Lowercase, split on whitespace/punctuation, drop stop-words."""
    raw = re.split(r"[\s\W]+", text.lower())
    return [t for t in raw if t and t not in STOP_WORDS]


# ---------------------------------------------------------------------------
# DOCUMENTATION_DOMAIN_ALIASES: request noun → the profile keyword it stands for
# ---------------------------------------------------------------------------
# #6970: a documentation-maintenance request ("mark ADR-0068 Accepted and
# regenerate the ADR index") matched nothing. No shipped profile declares `adr`,
# `changelog`, `readme`, `docstring`, `guide`, `handbook` or `tutorial` as a
# domain keyword, and the one profile that DOES own the documentation domain
# (`curator-carla`: `documentation`, `knowledge base`, `glossary`, `doctrine`, …)
# never saw its own keyword either. ADR-3 names expanding the vocabulary table as
# the sanctioned remedy for a coverage gap (this issue is exactly the
# "real invocation event data" ADR-3 said would drive that expansion), so the
# expansion lives here, in the router, not in the fetched profile pack.
#
# The mapping is  canonical profile keyword -> request-side aliases .  A request
# token in an alias set contributes the canonical keyword to the request's domain
# term set, so a profile that declares the canonical keyword matches through the
# ordinary domain_keyword path.
#
# Deliberate exclusions:
#   * bare `index` is NOT an alias: "index the invoice table" also means a
#     database/binary index, and misrouting that to a documentation curator is
#     worse than refusing it. "ADR index" / "documentation index" already carry
#     an unambiguous noun.
#   * maintenance verbs (`mark`, `regenerate`, `refresh`, `publish`) are NOT in
#     CANONICAL_VERB_MAP: a verb maps to a ROLE, and "regenerate" says nothing
#     about who should own the work. Domain nouns discriminate here; verbs do not.
#
# Tier position (#6970 FR-011): aliases are the LAST signal tier, consulted only
# when the request has no literal single-token and no literal phrase keyword
# match, so no request that routes today can move to a different profile.
DOCUMENTATION_DOMAIN_ALIASES: dict[str, frozenset[str]] = {
    "documentation": frozenset(
        {
            "adr",
            "adrs",
            "changelog",
            "changelogs",
            "doc",
            "docs",
            "documentation",
            "docstring",
            "docstrings",
            "guide",
            "guides",
            "handbook",
            "readme",
            "readmes",
            "tutorial",
            "tutorials",
        }
    ),
}

#: How many nearest profiles a ``ROUTER_NO_MATCH`` refusal may name (#6970 FR-004,
#: NFR-002). Bounded so the message stays readable for a catalog of any size.
_NEAREST_PROFILE_LIMIT = 3

#: How many distinct role-defining keywords a profile must share with a request
#: before a ``ROUTER_NO_MATCH`` refusal may name it (#7697). One shared word is
#: incidental: ``actions`` and ``minutes`` in a CI request made the meeting-minutes
#: profile the printed ``--profile`` remedy.
_NEAREST_MIN_KEYWORD_HITS = 2

#: The built-in general-purpose profile. A route that lands on it, or a
#: canonical-verb tie, is decided by domain-keyword hits when one profile leads
#: them (#7697, operator ruling 2026-11-18). ``empty_charter`` re-exports it.
GENERIC_PROFILE_ID = "generic-agent"


# ---------------------------------------------------------------------------
# Profile vocabulary helpers (pure)
# ---------------------------------------------------------------------------


def _profile_keywords(profile: object) -> list[str]:
    """The declared routing vocabulary of one profile.

    ``specialization_context.domain_keywords`` is the documented source; the
    profile-level ``collaboration.canonical_verbs`` are folded in as additional
    signals (pre-existing behaviour, unchanged by #6970).
    """
    sc = getattr(profile, "specialization_context", None)
    keywords: list[str] = list(sc.domain_keywords) if sc and sc.domain_keywords else []
    collab = getattr(profile, "collaboration", None)
    collab_verbs: list[str] = list(collab.canonical_verbs) if collab and collab.canonical_verbs else []
    for verb in collab_verbs:
        if verb not in keywords:
            keywords.append(verb)
    return keywords


def _keyword_tokens(keyword: str) -> tuple[str, ...]:
    """Normalize one declared keyword with the same splitter used on the request."""
    return tuple(_normalize_tokens(keyword))


def _is_single_token_match(keyword_tokens: tuple[str, ...], token_set: frozenset[str]) -> bool:
    """Tier 2: today's exact-token rule (byte-identical to pre-#6970 behaviour)."""
    return len(keyword_tokens) == 1 and keyword_tokens[0] in token_set


def _is_phrase_match(keyword_tokens: tuple[str, ...], tokens: list[str]) -> bool:
    """Tier 3: the keyword's own tokens appear as a contiguous run (#6970 FR-003).

    Before #6970 a keyword was compared by exact token equality, so any declared
    keyword containing a space (``knowledge base``, ``bug fix``) or a hyphen
    (``transcribe-notes``, ``detect-drift``) could never match — a dead signal.
    """
    size = len(keyword_tokens)
    if size < 2 or size > len(tokens):
        return False
    return any(tuple(tokens[index : index + size]) == keyword_tokens for index in range(len(tokens) - size + 1))


def _is_alias_match(keyword_tokens: tuple[str, ...], token_set: frozenset[str]) -> bool:
    """Tier 4: a documentation-artifact noun stands for the canonical keyword."""
    if len(keyword_tokens) != 1:
        return False
    aliases = DOCUMENTATION_DOMAIN_ALIASES.get(keyword_tokens[0])
    if not aliases:
        return False
    return bool(aliases & token_set)


def _default_action_for_role(role: object) -> str:
    """The action a keyword-tier match reports for a profile of *role*."""
    caps = DEFAULT_ROLE_CAPABILITIES.get(role) if isinstance(role, Role) else None
    if caps and caps.canonical_verbs:
        return str(caps.canonical_verbs[0])
    return "review"


def _collect_keyword_matches(
    profiles: list[object],
    matches_keyword: Callable[[tuple[str, ...]], bool],
) -> list[tuple[str, str, str]]:
    """One keyword pass: ``(profile_id, action, keyword)`` for every matching profile.

    *matches_keyword* is the tier predicate over a keyword's tokens, which is what
    makes the tier ladder in :func:`_keyword_tier_matches` explicit: the caller
    decides which tier runs, never this helper.

    The first matching keyword per profile wins, preserving the pre-#6970
    "first declared keyword" semantics inside a tier.
    """
    matches: list[tuple[str, str, str]] = []
    for profile in profiles:
        action = _default_action_for_role(getattr(profile, "role", None))
        for keyword in _profile_keywords(profile):
            keyword_tokens = _keyword_tokens(keyword)
            if not keyword_tokens or not matches_keyword(keyword_tokens):
                continue
            matches.append((str(getattr(profile, "profile_id", "")), action, keyword))
            break
    return matches


def _role_keywords(profile: object) -> list[str]:
    """The role-defining vocabulary of one profile: its declared domain keywords.

    Canonical verbs are left out on purpose (#7697): they name actions, not the
    role, and a hyphenated verb splits into homonyms (``attribute-actions`` gives
    ``actions``, ``transcribe-minutes`` gives ``minutes``).
    """
    sc = getattr(profile, "specialization_context", None)
    return list(sc.domain_keywords) if sc and sc.domain_keywords else []


def _nearest_profiles(profiles: list[object], tokens: list[str]) -> list[tuple[object, str, list[str]]]:
    """Rank the profiles a refusal could have named (#6970 FR-004, #7697).

    A profile qualifies only when at least ``_NEAREST_MIN_KEYWORD_HITS`` distinct
    role-defining keywords (see :func:`_role_keywords`) share a normalized token
    with the request. The order is total — keyword hits desc, shared tokens desc,
    ``routing_priority`` desc, ``profile_id`` asc — so two identical calls return
    identical candidates for any catalog order (NFR-001).

    A profile below the threshold is never listed: the refusal must not invent a
    closest match that does not exist (FR-005), and an incidental one-word overlap
    is not a match (#7697).
    """
    token_set = set(tokens)
    scored: list[tuple[int, int, int, str, object, list[str]]] = []
    for profile in profiles:
        hits = 0
        shared_tokens: set[str] = set()
        for keyword in _role_keywords(profile):
            overlap = token_set.intersection(_keyword_tokens(keyword))
            if overlap:
                hits += 1
                shared_tokens.update(overlap)
        if hits < _NEAREST_MIN_KEYWORD_HITS:
            continue
        priority = getattr(profile, "routing_priority", 0)
        shared = sorted(shared_tokens)
        scored.append((hits, len(shared), priority if isinstance(priority, int) else 0, str(getattr(profile, "profile_id", "")), profile, shared))
    scored.sort(key=lambda entry: (-entry[0], -entry[1], -entry[2], entry[3]))
    return [(profile, _default_action_for_role(getattr(profile, "role", None)), shared) for _, _, _, _, profile, shared in scored[:_NEAREST_PROFILE_LIMIT]]


def _domain_keyword_hits(profile: object, tokens: list[str], token_set: frozenset[str]) -> list[str]:
    """The declared domain keywords of *profile* the request contains whole (#7697).

    A hit is a literal single token or a contiguous phrase (tiers 2 and 3). The
    documentation aliases (tier 4) and the folded canonical verbs never count:
    they name what to do, not whose domain the work is in.
    """
    hits: list[str] = []
    for keyword in _role_keywords(profile):
        keyword_tokens = _keyword_tokens(keyword)
        if keyword_tokens and (_is_single_token_match(keyword_tokens, token_set) or _is_phrase_match(keyword_tokens, tokens)):
            hits.append(keyword)
    return hits


def _domain_keyword_leader(pool: list[object], tokens: list[str]) -> tuple[object, list[str]] | None:
    """The one profile in *pool* with the most domain-keyword hits, if it is unique.

    ``None`` when no profile has a hit, or when two or more share the top count:
    the router never invents a winner (#6970 FR-006).
    """
    token_set = frozenset(tokens)
    scored = [(profile, hits) for profile in pool if (hits := _domain_keyword_hits(profile, tokens, token_set))]
    if not scored:
        return None
    best = max(len(hits) for _, hits in scored)
    leaders = [entry for entry in scored if len(entry[1]) == best]
    return leaders[0] if len(leaders) == 1 else None


def _public_candidate(candidate: dict[str, str]) -> dict[str, str]:
    """A candidate as it is reported in ``alternatives``."""
    return {
        "profile_id": candidate["profile_id"],
        "action": candidate["action"],
        "confidence": candidate["_confidence"],
        "match_reason": candidate["match_reason"],
    }


def _quoted_hits(hits: list[str]) -> str:
    return ", ".join(f"'{hit}'" for hit in hits)


def _quote_request(request_text: str) -> str:
    """Quote a request for a copy-pasteable suggestion command.

    Double quotes match the existing suggestion wording; embedded double quotes
    are neutralized so the rendered ``--profile`` command stays runnable (#6970).
    """
    return '"' + request_text.replace('"', "'") + '"'


def _keyword_tier_matches(profiles: list[object], tokens: list[str]) -> list[tuple[str, str, str]]:
    """The keyword ladder: single token (today's rule) → phrase → docs alias.

    A later tier runs only when the earlier one produced no match (#6970 FR-011), so
    the new signals can only ever turn a refusal into a route — never move a route
    that already exists.
    """
    token_set = frozenset(tokens)
    tiers: tuple[Callable[[tuple[str, ...]], bool], ...] = (
        lambda keyword_tokens: _is_single_token_match(keyword_tokens, token_set),
        lambda keyword_tokens: _is_phrase_match(keyword_tokens, tokens),
        lambda keyword_tokens: _is_alias_match(keyword_tokens, token_set),
    )
    for tier in tiers:
        matches = _collect_keyword_matches(profiles, tier)
        if matches:
            return matches
    return []


def _no_match_suggestion(request_text: str, nearest: list[tuple[object, str, list[str]]]) -> str:
    """The ``ROUTER_NO_MATCH`` remedy, naming the candidates when there are any.

    #6970 FR-004/FR-005: the reported session saw only ``ROUTER_NO_MATCH`` and had to
    guess a profile id. The suggestion now carries a runnable ``--profile`` command
    naming a real candidate; when no profile clears the #7697 keyword threshold it
    says there is no close match and points at ``profiles list`` instead of
    inventing an id.
    """
    quoted = _quote_request(request_text)
    if nearest:
        listed = ", ".join(f"{getattr(profile, 'profile_id', '')} ({action})" for profile, action, _ in nearest)
        first_profile_id = getattr(nearest[0][0], "profile_id", "")
        return (
            f"No profile matched. Closest: {listed}. "
            f"Retry with 'spec-kitty dispatch {quoted} --profile {first_profile_id}', "
            "or run 'spec-kitty profiles list' for the full catalog."
        )
    return (
        "No profile matched and there is no close match: no profile shares "
        f"{_NEAREST_MIN_KEYWORD_HITS} or more of its role keywords with this request. "
        "Run 'spec-kitty profiles list' to choose one, then retry with "
        f"'spec-kitty dispatch {quoted} --profile <id>'."
    )


def _ambiguous_suggestion(request_text: str, tied: list[dict[str, str]]) -> str:
    """The ``ROUTER_AMBIGUOUS`` remedy: the tied ids and a ``--profile`` command per id.

    #6970 FR-006: a genuine tie stays a refusal (the router never invents a winner),
    but the caller must be able to resolve it in one step, so every tied id gets its
    own runnable command. The command list is capped at three so a large tie stays
    readable; the remaining ids are still named in the list that opens the sentence.

    *tied* is expected in ``profile_id`` order (the raise site sorts it), so the
    suggestion is identical for any catalog order.
    """
    quoted = _quote_request(request_text)
    listed = ", ".join(f"{candidate['profile_id']} ({candidate['action']})" for candidate in tied)
    commands = " or ".join(f"'spec-kitty dispatch {quoted} --profile {candidate['profile_id']}'" for candidate in tied[:3])
    remainder = f" (and {len(tied) - 3} more in the list above)" if len(tied) > 3 else ""
    return f"Multiple profiles matched: {listed}. Retry with {commands}{remainder}, or run 'spec-kitty profiles list' for the full catalog."


# ---------------------------------------------------------------------------
# ActionRouter
# ---------------------------------------------------------------------------


class ActionRouter:
    """Deterministic request → (profile_id, action) router.

    Pure function: no I/O, no network, no LLM call.  All routing decisions
    are based on CANONICAL_VERB_MAP tokens and profile domain keywords.

    Routing precedence (ADR-3), extended by #6970 with the signal-tier ladder:
      1. Explicit profile_hint → exact match
      2. Canonical verb match → canonical_verb confidence
      3. Literal single-token domain keyword → domain_keyword confidence
      4. Literal phrase keyword / canonical verb → domain_keyword confidence
         (#6970: previously dead signals)
      5. Documentation-artifact noun → domain_keyword confidence (#6970)
      6. Zero or ambiguous matches → RouterAmbiguityError naming the candidates

    Tiers 3-5 are a LADDER, not one pool: a later tier is consulted only when the
    earlier one produced no candidate, so the new signals are strictly additive and
    a request that routed before this change cannot move to another profile.
    """

    def __init__(
        self,
        registry: ProfileRegistry,
        router_plugin: ActionRouterPlugin | None = None,  # noqa: ARG002
    ) -> None:
        self._registry = registry
        # router_plugin reserved for future hybrid extension; not used in v1

    def route(
        self,
        request_text: str,
        profile_hint: str | None = None,
    ) -> RouterDecision:
        """Route *request_text* to a (profile_id, action) pair.

        Args:
            request_text: Natural-language request from the caller.
            profile_hint: Optional profile identifier to bypass routing.

        Returns:
            RouterDecision with profile_id, action, confidence, match_reason.

        Raises:
            RouterAmbiguityError: On no-match or ambiguous match.
        """
        profiles = self._registry.list_all()
        if not profiles:
            # #4114: an empty catalog means the activation gate admitted
            # nothing (built-ins always ship, so a bare project never lands
            # here) — the remedy is activation, not synthesis.
            raise RouterAmbiguityError(
                request_text,
                "ROUTER_NO_MATCH",
                [],
                "No profiles available. Run 'spec-kitty charter activate "
                "agent-profile <id>' to activate one, or 'spec-kitty profiles "
                "list --all' to see the catalog.",
            )

        # ------------------------------------------------------------------
        # Level 1: Explicit profile hint → exact confidence
        # ------------------------------------------------------------------
        if profile_hint is not None:
            from specify_cli.invocation.errors import ProfileNotFoundError  # noqa: PLC0415

            try:
                profile = self._registry.resolve(profile_hint)
            except ProfileNotFoundError as exc:
                raise RouterAmbiguityError(
                    request_text,
                    "PROFILE_NOT_FOUND",
                    [],
                    str(exc),
                ) from exc
            action = self._derive_action_from_tokens(request_text, profile.role)
            return RouterDecision(
                profile_id=profile.profile_id,
                action=action,
                confidence="exact",
                match_reason=f"explicit profile_hint '{profile_hint}'",
                # WP2/#3840: the router never computes candidates on the
                # explicit-hint path (Edge Case / Acceptance Scenario 2).
                alternatives=[],
            )

        tokens = _normalize_tokens(request_text)

        # ------------------------------------------------------------------
        # Level 2: Canonical verb match
        # ------------------------------------------------------------------
        # Map each matched token to its role; first occurrence per role wins.
        verb_matches: dict[Role, tuple[str, str]] = {}  # role → (action, token)
        for token in tokens:
            entry = CANONICAL_VERB_MAP.get(token)
            if entry is not None:
                action, role = entry
                if role not in verb_matches:
                    verb_matches[role] = (action, token)

        # ------------------------------------------------------------------
        # Level 3-5: domain keyword match (per-profile), as a TIER LADDER
        # ------------------------------------------------------------------
        # Check specialization_context.domain_keywords (NOT specialization.domain_keywords),
        # with collaboration.canonical_verbs folded in as additional signals (#6970
        # extracted that fold into _profile_keywords so the refusal ranking reads the
        # same vocabulary).
        #
        # #6970 FR-011: the passes run in order and a later pass is consulted ONLY when
        # the earlier one produced no match. That is what keeps the new signals
        # additive — every request that routed before this change resolves in the
        # first (single-token) pass, byte-identically to the pre-#6970 matcher.
        keyword_matches = _keyword_tier_matches(profiles, tokens)

        # ------------------------------------------------------------------
        # Aggregate candidates
        # ------------------------------------------------------------------
        candidates: list[dict[str, str]] = []

        # Verb-matched roles → expand to profiles with that role
        for role, (action, token) in verb_matches.items():
            role_profiles = [p for p in profiles if getattr(p, "role", None) == role]
            for p in role_profiles:
                candidates.append(
                    {
                        "profile_id": p.profile_id,
                        "action": action,
                        "match_reason": f"token '{token}' matched {getattr(role, 'value', str(role))} canonical verb",
                        "_confidence": "canonical_verb",
                    }
                )

        # Keyword-matched profiles (only add if not already in candidates)
        existing_ids = {c["profile_id"] for c in candidates}
        for profile_id, action, kw in keyword_matches:
            if profile_id not in existing_ids:
                candidates.append(
                    {
                        "profile_id": profile_id,
                        "action": action,
                        "match_reason": f"domain keyword '{kw}' matched",
                        "_confidence": "domain_keyword",
                    }
                )
                existing_ids.add(profile_id)

        if not candidates:
            nearest = _nearest_profiles(profiles, tokens)
            raise RouterAmbiguityError(
                request_text,
                "ROUTER_NO_MATCH",
                [
                    {
                        "profile_id": str(getattr(profile, "profile_id", "")),
                        "action": action,
                        "match_reason": ("partial overlap on " + ", ".join(f"'{token}'" for token in shared)),
                        "confidence": "partial",
                    }
                    for profile, action, shared in nearest
                ],
                _no_match_suggestion(request_text, nearest),
            )

        # #7697 (operator ruling 2026-11-18): domain keywords decide a
        # canonical-verb tie, and outrank a route that landed on the generic
        # profile, when exactly one profile leads the domain-keyword hits.
        try:
            decision = self._select_candidate(request_text, candidates)
        except RouterAmbiguityError as err:
            broken = self._break_verb_tie(err, candidates, tokens)
            if broken is None:
                raise
            return broken
        return self._prefer_domain_specialist(decision, candidates, profiles, tokens)

    def _select_candidate(self, request_text: str, candidates: list[dict[str, str]]) -> RouterDecision:
        """Pick one candidate by tier, then ``routing_priority`` (WP3/#3840)."""
        # ------------------------------------------------------------------
        # WP3/#3840 (FR-006, SK-08 rerank -- narrowed by operator ruling on
        # top of the original WP03 commit): partition candidates into the
        # canonical-verb tier and the domain-keyword tier BEFORE any
        # priority-based selection. A canonical-verb candidate always beats
        # a domain-keyword candidate, regardless of routing_priority --
        # routing_priority only continues to break ties WITHIN the
        # canonical-verb tier (unchanged from today). This is the
        # competition case SK-08 actually reported
        # (SPEC-KITTY-LEDGER.md:2727): a lone/weak domain-keyword candidate
        # outranking the request's own canonical-verb match.
        #
        # When the verb tier is EMPTY there is no verb-vs-keyword
        # competition to resolve -- the request's tokens carried no
        # canonical verb at all. That no-competition case is out of SK-08's
        # reported scope: it falls back to the pre-existing (pre-WP03)
        # selection pool of every candidate, which -- since the verb tier is
        # empty -- is exactly the keyword tier. A unique keyword-tier
        # candidate still auto-selects there, and routing_priority still
        # breaks ties among multiple keyword-tier candidates, exactly as
        # before this fix. A real shipped profile depends on this:
        # `chart` is a diagram-daisy domain-keyword-tier signal (folded from
        # collaboration.canonical_verbs), unique across the shipped set,
        # with no competing canonical-verb candidate -- see
        # test_writing_comms_routing.py::test_diagram_as_code_still_routes_to_diagram_daisy.
        # ------------------------------------------------------------------
        verb_tier = [c for c in candidates if c["_confidence"] == "canonical_verb"]

        def _priority(candidate: dict[str, str]) -> int:
            p = self._registry.get(candidate["profile_id"])
            return getattr(p, "routing_priority", 0) if p is not None else 0

        # Selection pool: the verb tier when it is non-empty (cross-tier
        # competition always resolves in the verb tier's favor); otherwise
        # the full candidate list, which is exactly the keyword tier when
        # the verb tier is empty (candidates only ever carry
        # "canonical_verb" or "domain_keyword" confidence -- the two tiers
        # partition `candidates` completely).
        selection_pool = verb_tier if verb_tier else candidates

        if len(selection_pool) == 1:
            c = selection_pool[0]
            return RouterDecision(
                profile_id=c["profile_id"],
                action=c["action"],
                confidence=c["_confidence"],  # type: ignore[arg-type]
                match_reason=c["match_reason"],
                # WP2/#3840 (FR-005, SC-003) + WP3/#3840 (FR-006): every
                # non-winning candidate from the FULL candidates list --
                # verb-tier and keyword-tier losers alike.
                alternatives=[
                    {
                        "profile_id": other["profile_id"],
                        "action": other["action"],
                        "confidence": other["_confidence"],
                        "match_reason": other["match_reason"],
                    }
                    for other in candidates
                    if other is not c
                ],
            )

        # ------------------------------------------------------------------
        # Tiebreaker: routing_priority (higher wins) -- WITHIN the selection
        # pool only. When the verb tier is non-empty this is WITHIN the
        # canonical-verb tier ONLY (FR-006), unchanged from today's
        # intra-tier behavior; a domain-keyword candidate never enters this
        # comparison regardless of its routing_priority. When the verb tier
        # is empty this is within the keyword tier, exactly as it was
        # before WP03 (no competition to resolve, so the pre-existing
        # priority-based selection applies unchanged).
        # ------------------------------------------------------------------
        sorted_pool = sorted(selection_pool, key=_priority, reverse=True)
        top_priority = _priority(sorted_pool[0])
        top_candidates = [c for c in sorted_pool if _priority(c) == top_priority]

        if len(top_candidates) == 1:
            c = top_candidates[0]
            return RouterDecision(
                profile_id=c["profile_id"],
                action=c["action"],
                confidence=c["_confidence"],  # type: ignore[arg-type]
                match_reason=c["match_reason"] + " (selected by routing_priority)",
                # WP2/#3840 (FR-005, SC-003): every non-winning candidate from
                # the FULL `candidates` list, not just `top_candidates` -- a
                # candidate that lost the priority tiebreaker before ever
                # reaching `top_candidates` is still a real alternative the
                # router considered.
                alternatives=[
                    {
                        "profile_id": other["profile_id"],
                        "action": other["action"],
                        "confidence": other["_confidence"],
                        "match_reason": other["match_reason"],
                    }
                    for other in candidates
                    if other is not c
                ],
            )

        # Still ambiguous after the tiebreaker: genuinely tied at the top
        # priority within the selection pool -- either two-or-more tied
        # canonical-verb candidates (unchanged from today), or two-or-more
        # tied keyword-tier candidates when the verb tier is empty
        # (unchanged from pre-WP03: this is a real tie, not merely "zero
        # verb-tier candidates present").
        raise RouterAmbiguityError(
            request_text,
            "ROUTER_AMBIGUOUS",
            [
                {
                    "profile_id": c["profile_id"],
                    "action": c["action"],
                    "match_reason": c["match_reason"],
                    # FR-009: sourced from the same _confidence value computed
                    # above during the verb/keyword match passes -- so
                    # build_ambiguous_dry_run_payload can build `alternatives`
                    # from err.candidates without a schema mismatch.
                    "confidence": c["_confidence"],
                }
                for c in sorted(top_candidates, key=lambda candidate: candidate["profile_id"])
            ],
            _ambiguous_suggestion(request_text, sorted(top_candidates, key=lambda candidate: candidate["profile_id"])),
        )

    def _break_verb_tie(
        self,
        err: RouterAmbiguityError,
        candidates: list[dict[str, str]],
        tokens: list[str],
    ) -> RouterDecision | None:
        """Resolve a canonical-verb tie by domain-keyword hits (#7697).

        Only a ``ROUTER_AMBIGUOUS`` refusal inside the canonical-verb tier is
        considered. The pool is the whole verb tier, not only the top-priority
        ties: a lower-priority profile whose domain the request names is a better
        owner than five equally ranked generalists. ``None`` keeps the refusal.
        """
        if err.error_code != "ROUTER_AMBIGUOUS":
            return None
        verb_tier = [c for c in candidates if c["_confidence"] == "canonical_verb"]
        by_id = {c["profile_id"]: c for c in verb_tier}
        pool = [profile for profile_id in by_id if (profile := self._registry.get(profile_id)) is not None]
        leader = _domain_keyword_leader(pool, tokens)
        if leader is None:
            return None
        profile, hits = leader
        winner = by_id[str(getattr(profile, "profile_id", ""))]
        return RouterDecision(
            profile_id=winner["profile_id"],
            action=winner["action"],
            confidence="canonical_verb",
            match_reason=f"{winner['match_reason']}; tie broken by domain keyword {_quoted_hits(hits)}",
            alternatives=[_public_candidate(other) for other in candidates if other is not winner],
        )

    def _prefer_domain_specialist(
        self,
        decision: RouterDecision,
        candidates: list[dict[str, str]],
        profiles: list[object],
        tokens: list[str],
    ) -> RouterDecision:
        """Hand a route that landed on the generic profile to the domain owner (#7697).

        The generic profile declares no domain; its folded verbs (``update``,
        ``fix``) say what to do, not whose work it is. When exactly one other
        profile leads the request's domain-keyword hits, it takes the route.
        """
        if decision.profile_id != GENERIC_PROFILE_ID:
            return decision
        pool = [profile for profile in profiles if getattr(profile, "profile_id", "") != GENERIC_PROFILE_ID]
        leader = _domain_keyword_leader(pool, tokens)
        if leader is None:
            return decision
        profile, hits = leader
        profile_id = str(getattr(profile, "profile_id", ""))
        action = decision.action if decision.confidence == "canonical_verb" else _default_action_for_role(getattr(profile, "role", None))
        generic = {
            "profile_id": decision.profile_id,
            "action": decision.action,
            "confidence": decision.confidence,
            "match_reason": decision.match_reason,
        }
        others = [_public_candidate(c) for c in candidates if c["profile_id"] not in (profile_id, GENERIC_PROFILE_ID)]
        return RouterDecision(
            profile_id=profile_id,
            action=action,
            confidence="domain_keyword",
            match_reason=f"domain keyword {_quoted_hits(hits)} matched; outranks the generic profile '{GENERIC_PROFILE_ID}'",
            alternatives=[generic, *others],
        )

    def _derive_action_from_tokens(self, request_text: str, role: object) -> str:
        """Derive canonical action from request tokens, falling back to role default."""
        tokens = _normalize_tokens(request_text)
        for token in tokens:
            entry = CANONICAL_VERB_MAP.get(token)
            if entry is not None:
                action, _ = entry
                return action
        caps = DEFAULT_ROLE_CAPABILITIES.get(role) if isinstance(role, Role) else None
        if caps and caps.canonical_verbs:
            # str() re-types the upstream Any (follow_imports=skip) as str.
            return str(caps.canonical_verbs[0])
        return "review"
