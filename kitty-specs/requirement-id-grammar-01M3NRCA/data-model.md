# Data Model: Requirement-ID grammar

## RequirementId (value object, frozen)

| Field | Type | Rule |
|---|---|---|
| `kind` | `Literal["FR","NFR","C","SC"]` | Stored uppercase. Input kind is case-insensitive. |
| `digits` | `str` | `\d+`, kept verbatim. Width is significant (`C-1` ≠ `C-001`). |
| `suffix` | `str \| None` | A single ASCII letter, stored lowercase. Spec scanning accepts only lowercase. Ref matching (`canonical()`) accepts either case. |
| `mission` | `str \| None` | The qualifier slug, `[a-z0-9][a-z0-9-]*` with an optional `-[0-9A-Z]{8}` mid8 tail (exactly 8 characters). Never resolved against real missions. |

- **Canonical string:** `f"{kind}-{digits}{suffix or ''}"`. A qualified ID renders as `f"{mission}#{canonical}"`.
- **Equality and hashing:** on the canonical tuple `(kind, digits, suffix, mission)`.
- **Properties:** `is_foreign = mission is not None`, `is_functional = kind == "FR"`, `is_success_criterion = kind == "SC"`.
- **Invariant:** every pattern that recognises an ID is generated from one core string in `grammar.py` (C-001). Patterns compile under `kernel._safe_re`: no lookbehind, no backreferences (C-005). The only product-code exceptions are the entries of the C-001 allowlist: 2 frozen divergences (`missions/_substantive.py`, `retrospective/generator.py`) plus 1 transitional entry (`runtime_bridge_cores.py`) at WP01, baseline 3; WP04 removes the transitional entry and lowers the baseline to 2, so at head the allowlist holds the 2 frozen entries (HiC ruling, Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`). `consolidation/retention.py` is a migrated consumer, not an exception.
- **Token boundary:** a token must not be preceded or followed by an ASCII word character (`[A-Za-z0-9_]`, i.e. ASCII `\b` semantics); the single lowercase suffix letter is part of the token and must itself not be followed by a word character. A trailing `-word` (`FR-008-mandated`) makes the token malformed in a declared position and not an ID in prose. Implemented RE2-safe as `\b` at both ends (ASCII semantics; `group(0)` is the bare token) plus an in-code check after the match that rejects a following `-<letter or digit>` compound (no lookbehind, no consumed group). Negative controls: `IC-01` is not `C-01`; `XFR-001`; `FR-00N` is not `FR-00`; `FR-008-mandated`; `C-1-2`; `x_FR-001`; `FR-001_`; `FR-0011x` is `FR-0011x`, never a truncation. See `contracts/grammar.md`.

## Grammar API (`specify_cli.requirement_mapping.grammar`)

| Function | Returns | Used by |
|---|---|---|
| `parse(token) -> RequirementId \| None` | Strict full-match on the token (qualifier optional; suffix case-tolerant) | map-requirements input; WP ref classification; consolidation retention constraint-row check (unqualified `kind == "C"`) |
| `canonical(token) -> str \| None` | The canonical string, or `None` if malformed | map-requirements add and dedup |
| `find_all(text, *, spec_scan: bool) -> list[RequirementId]` | Every ID token, with the qualifier consumed; spec scanning is lowercase-suffix-only | declared-ID scan, bare-prose, lint, tasks.md fallback |
| `tokenize_refs(value) -> list[str]` | Raw items from a list, or split from a scalar string on `[,\s]+` | WP frontmatter readers, `wp_metadata` |
| `DECLARED_SHAPE_PATTERNS` | 4 compiled patterns (table, heading, bullet or numbered, bold lead) | `_declared_ids`, lint |
| `MALFORMED_DECLARED_LEAD` | A case-sensitive, uppercase-kind-only pattern for a kind-prefixed token in a declared position (`FR`/`NFR`/`SC`/`C`, then `-` or `_`, then a digit or uppercase letter). `- C-style strings`, `\| C-suite \|` and `- c-001 lowercase` never match | lint (FR-013) |
| `classify(raw, declared) -> RefVerdict` | `Accepted(RequirementId)` or `Rejected(raw, reason)` | finalize, map-requirements, runtime (via injection) |
| `MALFORMED`, `UNKNOWN_SPEC_ID`, `FOREIGN_QUALIFIED` | The three reason strings | every consumer that names a reason (no literal duplication) |
| `FAILING_REASONS: frozenset` | `{MALFORMED, UNKNOWN_SPEC_ID}` | all three gates |
| `RULE_TEXT` | The grammar rule string `<kind>-<digits>[<lowercase letter>]` | map-requirements hint, setup-plan lint `rule` |
| `blank_html_comments(text) -> str` | `text` with every `<!-- … -->` span (an unterminated one runs to end of text) replaced by spaces, newlines kept, so line count and positions are preserved | `_declared_ids`, lint |

## RefVerdict

`reason ∈ {"malformed", "unknown_spec_id", "foreign_qualified"}`. Exactly one reason per rejected ref.

| Case | Verdict |
|---|---|
| Does not parse | `malformed` |
| Parses, has a qualifier | `foreign_qualified` (never fails) |
| Parses, unqualified, not in the declared set (compared by canonical form) | `unknown_spec_id` (fails; this applies to SC too) |
| Parses, unqualified, declared | Accepted. An FR counts toward the coverage gate; an SC counts toward the informational SC coverage; NFR and C are accepted with no coverage duty. |

**Per-WP rule (FR-019):** a WP's accepted refs always count, whatever its rejected siblings are. The WP fails validation if any rejected ref's reason is in `FAILING_REASONS`. A WP whose only accepted refs are SC counts as having refs (SC-only is not missing). A WP with **no accepted ref** is *missing* and fails, even when it carries `foreign_qualified` citations: `foreign_qualified` itself never fails, and the failure comes from the missing-refs rule (Decision Moment `01M3NYFZ1P6QBD2DX4DVDA323W`).

## Declared-ID set

Parsed from `spec.md`:
- It consists of the first ID on each line that matches a declared shape, with struck-through and bold wrappers tolerated.
- HTML comments are skipped: the scan runs on `blank_html_comments(text)`, so a declaration inside a comment is not declared.
- It is grouped as `functional` / `non_functional` / `constraint` / `success_criteria`.
- The existing keys `all` and `functional` of `parse_requirement_ids_from_spec_md` are kept. `all` now includes SC and suffixed IDs (the runtime's "unknown" test depends on it).

## SpecLintResult (setup-plan)

- `errors: list[{token, line, rule}]`: malformed kind-prefixed tokens in declared positions. Non-empty means refusal.
- `warnings: list[{token, line, message}]`: unqualified, well-formed, undeclared tokens in prose. Qualified citations are never warned about.

## State and lifecycle

There is no new persisted state. WP frontmatter `requirement_refs` is only appended to (by map-requirements) and never rewritten (by finalize). The `wps.yaml` schema is unchanged (C-003).
