# Contract: requirement-ID grammar (single authority)

- **Home:** `src/specify_cli/requirement_mapping/grammar.py`. No other product module may compile a requirement-ID pattern, change an ID's case, or tokenise `requirement_refs`. This is enforced by `tests/architectural/test_requirement_id_grammar_single_source.py`.
- **Allowlist** (shrink-only; the gate asserts that the entry count equals the recorded baseline, two-sided):
  - **Frozen** (2 entries, HiC ruling Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`, superseding `01M3P07HV88QNVVKP3E2W28VB6`): `src/specify_cli/missions/_substantive.py`, `src/specify_cli/retrospective/generator.py`. Each entry names its follow-up ticket.
  - **Transitional ratchet**: WP01 lands the allowlist with **3 entries and `baseline: 3`**: the 2 frozen entries plus 1 transitional entry for `src/runtime/next/runtime_bridge_cores.py` (`_REQUIREMENT_REF_PATTERN`, marked `transitional: "WP04 removes"`). WP04 deletes that pattern, removes the transitional entry and lowers the baseline to 2 in the same edit. At the mission head the allowlist holds exactly the 2 frozen entries with `baseline: 2`.
  - **Migrated, not allowlisted**: `src/specify_cli/consolidation/retention.py`. WP01 replaces `_CONSTRAINT_ROW_ID` with a grammar check: a table's first cell counts as a retention constraint row when `parse(cell)` yields an unqualified ID with `kind == "C"` (kind input case-insensitive). `C-001`, `c-001` and `C-007a` count; `other-mission#C-001`, `C-S1` and `IC-01` do not. After WP01 the file holds no requirement-ID literal.

```
id         := [qualifier "#"] kind "-" digits [suffix]
kind       := "FR" | "NFR" | "C" | "SC"            ; input case-insensitive, canonical uppercase
digits     := DIGIT+                                ; verbatim; width significant
suffix     := LOWER_LETTER                          ; spec scan: lowercase only
                                                    ; ref matching: either case → lowercase
qualifier  := slug                                  ; foreign citation; never resolved
slug       := [a-z0-9] [a-z0-9-]* ["-" 8[0-9A-Z]]   ; optional mid8 tail: exactly 8 characters
```

- **Core pattern:** `(?:FR|NFR|SC|C)-\d+(?-i:[a-z])?` (the kind alternation is case-insensitive; the suffix class is case-sensitive). RE2-safe.
- **Token boundary** (applies to `find_all` and to the declared-shape scan):
  - A token must not be preceded or followed by an ASCII word character (`[A-Za-z0-9_]`, ASCII `\b` semantics; compile with `re.ASCII` if the stdlib fallback is active). The single lowercase suffix letter is part of the token, and it must itself not be followed by a word character.
  - A trailing `-word` (a hyphen followed by a letter or digit, e.g. `FR-008-mandated`, `C-007-mission`) makes the token malformed in a declared position and not an ID at all in prose.
  - Implementation (analysis F9 ruling): RE2 supports `\b`, so the pattern uses `\b` at both ends of the (optionally qualified) core. No consumed group, no lookbehind, no lookahead. `group(0)` is exactly the token. `find_all` then applies an in-code check on the text right after each match: a following `-<letter>` compound (`FR-008-mandated`) makes it not-an-ID in prose, and malformed in declared positions. Verify `\b` behaviour under `kernel._safe_re` in a unit test.
  - `_REF_FIND_PATTERN` (the legacy-compat alias) is generated from the core as `\b(?:FR|NFR|C)-\d+\b`: unqualified, unsuffixed, with no compound check. It is kept ONLY because the frozen `test_bare_prose_false_negative_sample.py` reimplements the legacy scan with `finditer`/`group(0)`, so its figures must not move. Production code never uses it; production uses `find_all`.
  - Negative controls: `IC-01` never yields `C-01`; `XFR-001` yields nothing; `FR-00N` never yields `FR-00`; `FR-008-mandated` yields nothing; `FR-0011x` yields `FR-0011x` whole, never a truncated `FR-0011` or `FR-001`.
- **Declared positions:** the lead token of a markdown table's first cell, of a heading, of a `-`/`*`/`N.` list item, or of a `**bold**` paragraph lead. Wrappers `**` and `~~` are tolerated. HTML comments are skipped (blanked by `blank_html_comments`, positions preserved). Only the first ID on a line is a declaration.
- **Malformed declared lead (`MALFORMED_DECLARED_LEAD`, FR-013):** detection is **uppercase-kind only** and case-sensitive: a lead token in a declared position that starts with `FR`, `NFR`, `SC` or `C`, followed by `-` or `_`, then a digit or an uppercase letter, and that does not full-match the core. It runs spec-wide over declared positions (not only inside requirement sections). Negative controls on declared-position lines, none of which may error: `- C-style strings`, `| C-suite |`, `- c-001 lowercase`. **Lead-token capture charset (analysis B6):** the captured lead is `[A-Za-z0-9_.-]+`, and it ends at the first other character (`'`, `/`, whitespace, a non-ASCII dash `–`, an ellipsis `…`, `)`, …). So `- **FR-009's** …`, `| FR-001/FR-002 |`, `| FR-002–FR-006 |` and `- **SC-001…004**` capture a well-formed ID and do not error. The known corpus refusal set stays exactly 4 specs.
- **Verdicts:** `malformed` fails; `unknown_spec_id` fails; `foreign_qualified` never fails. Valid refs on the same WP always count.
- **Not in the grammar:** implementation-concern IDs (`IC-##`), hyphen-qualified compounds (`C-007-mission`, `FR-008-mandated`), and dotted numbers (`FR-001.1`).
