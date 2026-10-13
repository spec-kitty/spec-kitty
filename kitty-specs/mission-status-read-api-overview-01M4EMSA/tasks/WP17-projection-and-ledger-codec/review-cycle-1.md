---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T15:17:06Z'
reviewer_agent: reviewer-renata
wp_id: WP17
---

# WP17 review cycle 1: returned for one redaction fix and two parity cases (reviewer-renata)

The full evidence is in wp17-review-verdict.md (orchestrator scratchpad, plus the reviewer's material in scratchpad/rv/). Everything else passed: per-class JaCoCo, 55 hand ledgers and 799 generated lines against the oracle, the annotation end to end, and 0 live divergences across 959 unique ledgers.

The orchestrator ruled R1 under bounded autonomy. Option (b) of the reviewer's fork would knowingly ship an AC-9g redaction hole, so (a) is the only remedy that satisfies the spec.

| id | severity | file | problem | remedy |
|---|---|---|---|---|
| R1 | medium | domain/projection/LeakClasses.java (`compile`, around line 33) | `Pattern.UNICODE_CHARACTER_CLASS` is not Python's `re` semantics. Java `\w` also matches Mn/Mc/Me, Pc and Join_Control, and Java `\s` omits U+001C to U+001F. Measured: `é/home/x` (with a COMBINING ACUTE, U+0301, before the slash), `a<U+200D>/home/x` and `x<U+203F>/home/x` are redacted to `[path]` by Python but served unredacted by Java, and `humanLeak` misses them too. `x<U+0301>user@localhost` keeps the address in Java. This is an AC-9g redaction hole. | In `compile`, translate the pattern source so that `\w` becomes Python's class, `[\p{L}\p{N}_]` (check Python's exact `str` `\w` definition: `str.isalnum()` or `_`, and match it), `\W` becomes its complement, and `\s`/`\S` become Python's whitespace set (`str.isspace()`: include U+001C to U+001F, U+0085 and the Unicode Zs/Zl/Zp spaces). Mind character-class contexts (`[\w-]`) and escaped backslashes. Keep `compile` as the single place. Add probes run through the REAL Python patterns versus Java for U+0301, U+200D, U+203F and U+001C to U+001F before a host path and before an email, with expected values from running Python. Add a revert row: going back to the plain flag turns them red. |
| R2 | low | LedgerLineOracleParityTest (`DIVERGENCES`, `OracleCases`) | Unlisted divergence. A truthy non-text `feature_slug` or `mission_slug` (int, float, bool, list, object), or a slug over 255 characters, makes Python's partition path raise, so `materialize_snapshot` fails, while the codec serves the line. The live count is 0. | Add it to `DIVERGENCES` with its reason, plus one oracle case per type (expected verdicts from running the oracle). No production change. |
| R3 | low | LedgerLineOracleParityTest | Lone CR and raw U+0085 or U+2028 inside a string make `materialize_snapshot` fail in Python (its two readers frame lines differently), while Java serves the line. No parity case pins this. The live count is 0. | Add parity cases for a lone CR, U+0085 and U+2028, with `DIVERGENCES` reasons. No production change. |

Note for later, not this round: F4. WP06 maps every `MalformedReason` to `ledger_unparseable` and never serves the enum name. Report planning-side DD text for R1 to R3 (the next free id is DD-86), including the correction that WP07's manifest `patternDivergences` entry wrongly says the flag alone is sufficient. Do NOT edit the manifest: it belongs to WP07, and I route that separately.
