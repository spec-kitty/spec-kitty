# Data Model: dispatch routing vocabulary and refusal candidates

Mission: `dispatch-router-docs-coverage-01M6BTTX` · Issue #6970

This mission changes no persisted data. The entities below are the in-memory concepts the
router reasons about; they are documented because the refusal payload and the ordering
rules are observable behaviour that tests pin.

## Entity: Routing request (normalized form)

| Attribute | Type | Notes |
| --- | --- | --- |
| `request_text` | `str` | The verbatim request the caller passed to `spec-kitty dispatch`. Unchanged in the payload. |
| `tokens` | `tuple[str, ...]` | `_normalize_tokens(request_text)`: lowercased, split on `r"[\s\W]+"`, stop-words dropped. The single normalization used by every tier and by the refusal ranking. |

Invariant: `tokens` is deterministic for a given `request_text` and is the only form any
matcher may inspect — no matcher lowercases or re-splits on its own.

## Entity: Canonical verb mapping (existing, unchanged)

`CANONICAL_VERB_MAP: dict[str, tuple[str, Role]]` — a request token → `(action, role)`.
Unchanged by this mission. Its precedence over domain signals is preserved (FR-010).

## Entity: Domain vocabulary term (new)

A documentation-artifact noun family folded onto the canonical profile keyword
`documentation`.

| Attribute | Type | Notes |
| --- | --- | --- |
| `canonical_keyword` | `str` | The profile-declared keyword the family stands for: `"documentation"`. |
| `aliases` | `frozenset[str]` | `doc`, `docs`, `documentation`, `docstring`, `readme`, `adr`, `changelog`, `guide`, `handbook`, `tutorial` — normalized request tokens that mean the same domain. |
| `excluded` | — | `index` deliberately not an alias: it also names a database/binary index (FR-002). A phrase such as "ADR index" routes through `adr`. |

Rules:

- An alias contributes the canonical keyword to the request's *domain term set*; the
  profile keyword then matches by the normal keyword rule.
- If a profile declares a keyword that is itself an alias member, no behaviour changes
  (the term set contains what it already contained).
- The docs family never enters the verb tier, so a request with a canonical verb still
  routes on the verb (FR-010).

## Entity: Keyword match (rewritten rule)

A declared keyword or canonical verb matches a request when the keyword's own normalized
token sequence appears as a **contiguous** run inside the request's token sequence.

| Case | Keyword tokens | Request tokens | Match |
| --- | --- | --- | --- |
| single word | `("documentation",)` | `("refresh","documentation","page")` | yes |
| phrase | `("knowledge","base")` | `("refresh","the","knowledge","base","article")` | yes |
| phrase, one word only | `("knowledge","base")` | `("share","knowledge")` | no |
| hyphenated verb | `("transcribe","notes")` | `("transcribe","notes","for","standup")` | yes |
| order matters | `("base","knowledge")` | `("knowledge","base")` | no |

Invariants:

- A keyword that normalizes to zero tokens can never match (it declares no signal).
- Matching is order-sensitive and contiguity-sensitive, so a phrase is a phrase, not a
  bag of words.

## Entity: Signal tiers (the ordering rule that keeps today's routes)

The router evaluates signal sources in order and stops at the first tier that yields a
candidate set. This is the rule that makes the new vocabulary additive (FR-011):

| Order | Tier | Notes |
| --- | --- | --- |
| 1 | canonical verb (`CANONICAL_VERB_MAP`) | unchanged (#3840: verb tier beats every keyword) |
| 2 | **literal single-token** keyword / canonical verb | today's exact-token behaviour, byte-identical |
| 3 | **literal phrase** keyword / canonical verb (new) | multi-token declared signals, previously dead |
| 4 | **documentation vocabulary** alias (new) | aliases fold onto the canonical keyword `documentation` |
| 5 | refusal (`NO_MATCH` / `AMBIGUOUS`) | unchanged selection rules within a tier |

Consequences to preserve in tests:

- `"release notes for the sprint"` still routes to `planner-priti`: tier 2 fires on the
  literal single-token `sprint` before `comms-cleo`'s phrase `release-notes` can compete.
- `"the guide for the spike"` still routes to `researcher-robbie`: tier 2 fires on `spike`
  before the docs alias for `guide` is consulted.
- A request with no tier-2 signal but a docs noun ("mark ADR-0068 Accepted and regenerate
  the ADR index") falls through to tier 4 and routes to the documentation profile.
- Within tiers 3 and 4 the existing `routing_priority` tiebreak and the existing
  `ROUTER_AMBIGUOUS` behaviour apply unchanged.

## Entity: Router decision (existing, unchanged)

| Attribute | Type | Notes |
| --- | --- | --- |
| `profile_id` | `str` | Resolved profile. |
| `action` | `str` | Canonical action (`implement`, `review`, `curate`, …). |
| `confidence` | `Literal["exact","canonical_verb","domain_keyword","generic_fallback"]` | Unchanged literal set (C-002). The docs route reports `domain_keyword`. |
| `match_reason` | `str` | Human sentence naming the token/keyword that matched. |
| `alternatives` | `list[dict[str,str]]` | Non-winning candidates considered; unchanged. |

## Entity: Refusal candidate (new use of an existing field)

`RouterAmbiguityError.candidates` — `list[dict[str, str]]`.

| Attribute | Type | Notes |
| --- | --- | --- |
| `profile_id` | `str` | An id from the catalog; never invented. |
| `action` | `str` | What the router would have stored as the action for that profile. |
| `match_reason` | `str` | For `NO_MATCH`, states the overlap is *partial* and names the shared token(s); for `AMBIGUOUS`, unchanged wording. |
| `confidence` | `str` | Existing open-ended string. For nearest-profile entries: `"partial"`. |

Rules:

- **AMBIGUOUS**: exactly the tied top-priority candidates (unchanged selection), ordered
  by `profile_id` ascending so the message is stable.
- **NO_MATCH**: the profiles with the strongest *partial* overlap, where overlap is the
  count of normalized tokens shared between the request and that profile's declared
  keyword tokens + canonical verb tokens; ordered by overlap desc, `routing_priority`
  desc, `profile_id` asc; capped at **three**. Zero overlap ⇒ empty list.
- Suggestion text:
  - non-empty candidates →
    `No profile matched. Closest: <id> (<action>), …. Retry with 'spec-kitty dispatch "<request>" --profile <id>', or run 'spec-kitty profiles list'.`
  - empty candidates →
    `No profile matched. Run 'spec-kitty profiles list' to choose one, then retry with 'spec-kitty dispatch "<request>" --profile <id>'.`
  - empty catalog → the existing #4114 activation suggestion, unchanged.
- **AMBIGUOUS** suggestion →
  `Multiple profiles matched: <id> (<action>), …. Retry with 'spec-kitty dispatch "<request>" --profile <id>' (one of the ids above), or run 'spec-kitty profiles list'.`

## Entity: Routing error payload (existing, additive)

`{"error": "routing_failed", "error_code": str, "message": str, "candidates": list, "suggestion": str}`

Invariants: the five keys and their types are unchanged (FR-008); `candidates` carries the
entries above; `message` is `"<error_code>: <suggestion>"` as today.

## State transitions

```
request ─▶ normalize ─▶ profile_hint? ──yes──▶ exact decision (unchanged)
                            │no
                            ▼
             verb tier non-empty? ──yes──▶ decide within verb tier (priority)
                            │no                    │tie ⇒ AMBIGUOUS(tied)
                            ▼                       ▼
   tier 2: literal single-token keyword non-empty? ──yes──▶ decide (priority; tie ⇒ AMBIGUOUS)
                            │no
                            ▼
   tier 3: literal phrase keyword/verb non-empty? ──yes──▶ decide (priority; tie ⇒ AMBIGUOUS)
                            │no
                            ▼
   tier 4: documentation vocabulary non-empty? ──yes──▶ decide (priority; tie ⇒ AMBIGUOUS)
                            │no
                            ▼
             NO_MATCH (nearest ≤3, suggestion with the --profile remedy)
```

No other transition changes: `generic_fallback` still pre-empts the router for an empty
charter, and `--profile` still bypasses every tier.
