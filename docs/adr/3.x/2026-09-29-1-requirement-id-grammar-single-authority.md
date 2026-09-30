---
title: 'ADR: one requirement-ID grammar, one authority'
description: 'Accepted: every requirement-ID surface reads FR/NFR/C/SC IDs through one shared grammar module, replacing six divergent parsers.'
status: Accepted
date: '2026-09-29'
updated: '2026-09-30'
---

**Status:** Accepted

**Date:** 2026-09-29

**Deciders:** Stijn Dejongh (owner), via the operator rulings recorded in
`kitty-specs/requirement-id-grammar-01M3NRCA/decisions/`.

**Technical Story:** [#2991](https://github.com/spec-kitty/spec-kitty/issues/2991)
(the erasure defect), [#3519](https://github.com/spec-kitty/spec-kitty/issues/3519)
part 2 (the invisible letter-suffixed requirement), and
[#2066](https://github.com/spec-kitty/spec-kitty/issues/2066) (the undiagnosed
coverage failure) — Mission `requirement-id-grammar-01M3NRCA`.

---

## Context and Problem Statement

Before this Mission, a requirement ID — `FR-###`, `NFR-###`, `C-###`, `SC-###`, each with
an optional letter suffix and an optional `<mission-slug>#` qualifier — had no single
authority. `spec.md`'s SC-006 measured six separate definitions, four of them in scope for
this Mission's consumers; the other two were deferred out of this Mission's scope as frozen
divergences (orchestrator auto-mode scope deferral, Decision Moment
`01M3P07HV88QNVVKP3E2W28VB6`) and have since been migrated onto the grammar by
[#5387](https://github.com/spec-kitty/spec-kitty/issues/5387) and
[#5388](https://github.com/spec-kitty/spec-kitty/issues/5388) (see the amendment below). Each definition tokenised, canonicalised, or matched IDs on
its own regular expression, and they disagreed on kind coverage, digit width, suffix
handling, and qualifier syntax.

That drift produced three concrete defects:

- **#2991 (erasure):** a real `finalize-tasks` run could respell or drop an authored
  `requirement_refs` list — the WP's own citation of its requirements disappeared without a
  trace.
- **#3519 part 2 (invisible letter-suffixed requirement):** a declared, unmapped suffixed FR
  (`FR-006a`) did not fail `finalize-tasks --validate-only`'s coverage gate, because the
  runtime's own pattern had no suffix support — a requirement could go completely unmapped
  and unreported.
- **#2066 (undiagnosed coverage failure):** the failure JSON carried no parsed spec-ID set,
  so an operator debugging a rejected mapping could not see what the tool believed the spec
  declared.

A fourth, structural risk (research R8): once refs are kept on disk rather than
respelled away, an **all-or-nothing** rule — where one bad ref on a WP unmaps every valid
ref on that same WP — would silently discard coverage for correctly-cited requirements the
moment any other ref on the WP was malformed or foreign.

## Decision Drivers

- **Single canonical authority** (`DIRECTIVE_044`): one requirement-ID grammar, not six.
- **"No authored ref disappears without a trace"** (spec Intent Summary): a rejected ref is
  reported, never silently dropped or respelled.
- **Layering unchanged** (C-002): the grammar must be reachable from `specify_cli` and from
  the `runtime`/`mission_runtime` layers without inverting the enforced
  `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` chain.
- **RE2-safe patterns** (C-005): no catastrophic-backtracking construct anywhere in the
  grammar.
- **Upstream contract closed** (R7): the orchestrator-api `upstream_contract.json` schema is
  not reopened by this Mission.

## Considered Options

1. **Grammar in `kernel`.** Rejected (R2): `kernel`'s own README admits only cross-package
   infrastructure, and the runtime/`specify_cli` cores could not import a requirement-ID
   grammar from there without inventing a new dependency direction anyway.
2. **A mirror constant plus a parity test in each core.** Rejected (R3): this keeps a second
   authority per consumer and trades "one shared module" for "N modules kept in sync by a
   test", exactly the shape that produced the six-definition drift in the first place.
3. **Integer `number` digits field instead of a `digits: str`.** Rejected (R4): an integer
   collapses `C-1` and `C-001` into the same value, losing the declared spelling's
   significant width.
4. **Hyphen-joined qualifier (`slug-FR-001`).** Rejected (R4/R5): collides with an ordinary
   prose compound such as `FR-###-mandated`, which must remain a non-match.
5. **Path-style qualifier (`<slug>/ID`).** Rejected (R5): collides with real file paths
   appearing in spec/plan prose.
6. **A check inside `spec-commit`.** Rejected (R6): `spec-commit` is a transport step: gating
   there would block a legitimate work-in-progress commit that has not yet reached a valid
   grammar state.
7. **A new orchestrator-api error code for the setup-plan requirement-ID gate.** Rejected
   (R7): would reopen `upstream_contract.json`'s schema before this Mission's other
   consumers had landed; the existing `PLAN_SETUP_FAILED` envelope with `data.reason` covers
   it additively instead (see "Setup-plan gate and orchestrator-api parity" below).

**Chosen option:** a single shared grammar module,
`src/specify_cli/requirement_mapping/grammar.py`, injected by required argument into every
consumer, with a verdict table (FR-019) replacing the all-or-nothing rule.

## Decision Outcome

### Grammar home

The grammar lives at `src/specify_cli/requirement_mapping/grammar.py`;
`requirement_mapping` became a package (`__init__.py`, `grammar.py`, `lint.py`) with no
import-path change for existing callers of the package's re-exported names
(`src/specify_cli/requirement_mapping/__init__.py:15-48`). Every requirement-ID-aware
surface — the planning hand-off, `map-requirements`, `finalize-tasks` (including its
tasks.md fallback reader), the runtime readiness check, and the merge-cleanup retention
reader's constraint-row check (`src/specify_cli/consolidation/retention.py:10,70`) — reads
IDs through this module and this module alone; the boundary is enforced by
`tests/architectural/test_requirement_id_grammar_single_source.py`.

### `RequirementId` shape

`RequirementId(kind, digits: str, suffix: str | None, mission: str | None)`
(`grammar.py:123-135`, frozen dataclass). Canonical form is `KIND-digits[suffix]`, kind
uppercase, digits verbatim (width significant — `C-1` and `C-001` are distinct), suffix
lowercase; the qualified form (`__str__`) renders `mission#canonical`
(`grammar.py:137-140` `canonical` property, `:154-158` `__str__`).

### One core pattern

Every pattern in the module is generated from one core kind alternation,
`_KIND_ALT = "FR|NFR|SC|C"` (`grammar.py:74`), matched case-insensitively
(`_KIND_DIGITS`, `grammar.py:87`); kinds are `FR`, `NFR`, `C`, `SC`. Declared-shape scanning
(`spec_scan=True`) accepts only a lowercase suffix; ref-item matching
(`spec_scan=False`) is case-tolerant on the suffix (`find_all`, `grammar.py:247-275`;
Decision Moment `01M3NRCVW5VPE1DC9J6G5F3RBC`: accept the letter suffix, lowercase
canonical). The
C-001 architectural gate's floor test asserts the one detectable site IS this named
constant (`grammar.py:66-74`).

### Dotted IDs are dropped, not truncated

A token immediately followed by a token-boundary `-<alphanumeric>` or `.<alphanumeric>`
is not an ID at all: `is_compound_tail` (`grammar.py:202-222`, backed by
`_COMPOUND_TAIL`, `grammar.py:198`) rejects the whole match. A dotted sub-requirement
id — `FR-002.3`, `### FR-001.1 Title`, `**FR-004.1** x` — is therefore DROPPED entirely
by both `find_all` and the declared-shape scan, not silently truncated to the
well-formed prefix (`FR-002`/`FR-001`/`FR-004`, folded from the earlier
truncate-to-parent behaviour): truncation would let a spec-scan/declared-id consumer
accept a token the setup-plan lint refuses as malformed (it reads the same
`.`-inclusive lead charset via `MALFORMED_DECLARED_LEAD`, `grammar.py:330-337`),
disagreeing about what the document declares. A sentence-final period is not a dotted
tail: `.` followed by whitespace or end-of-string (`see FR-001.`) leaves nothing
alphanumeric for the check to match, so it still yields `FR-001`. Verified directly
against this Mission's tip: `grammar.find_all("FR-002.3", spec_scan=False)`,
`grammar.find_all("### FR-001.1 Title", spec_scan=False)` and
`grammar.find_all("**FR-004.1** x", spec_scan=False)` each return `[]`, while
`grammar.find_all("see FR-001.", spec_scan=False)` returns `FR-001`.

### Qualified citation

`<mission-slug>#<ID>` (`_QUALIFIED_KIND_DIGITS`, `grammar.py:96`; finder in `find_all`,
`grammar.py:247-275`): never declared, never required, never flagged by the bare-prose
scan, never warned about at setup-plan, reported `foreign_qualified` when present in a
work package's refs, and the qualifier itself is never resolved against anything local
(Decision Moment `01M3NRD1N2PFH7MX82PH2D93PV`: include the qualified foreign-citation
syntax). The bare-prose candidate helper `_unqualified_unsuffixed_ids` excludes any
qualified match (`src/specify_cli/requirement_mapping/__init__.py:165-177`, C-009),
consumed by the public `find_bare_prose_requirement_ids` (`:270`), and the setup-plan lint
(`src/specify_cli/requirement_mapping/lint.py`) never treats a qualified citation as an
undeclared local ID.

### Verdict table (FR-019)

`classify(raw, declared)` (`grammar.py:381-392`) applies, in order: does not parse ->
`malformed`; has a qualifier -> `foreign_qualified` (never fails); not in `declared` by
canonical form -> `unknown_spec_id`; otherwise `Accepted` (Decision Moment
`01M3NSKBMEKR60XKRJSYQC41G3`: malformed and unknown fail, foreign_qualified never
fails, a rejected ref never un-maps the WP's valid refs).

| Reason | Fails the gate? | Example (placeholder) |
| --- | --- | --- |
| `malformed` | yes | a token that does not full-match the grammar (e.g. an underscore where a hyphen is required) |
| `unknown_spec_id` | yes (every kind, `SC` included) | `FR-###` not present in the spec's declared-ID set |
| `foreign_qualified` | never | `<mission-slug>#FR-###` |

`FAILING_REASONS = {malformed, unknown_spec_id}` (`grammar.py:358`) is the shared set every
consumer classifies against — a `foreign_qualified` rejection is never counted as failing
anywhere. A rejected ref never un-maps a valid sibling: every consumer classifies **per
ref**, not per WP.

- `src/specify_cli/cli/commands/agent/mission_finalize.py:1180-1197` (`_classify_one_wp`)
  and `:1201-1243` (`_classify_wp_requirement_refs`) — a WP is "missing" only when it has NO
  accepted ref: a WP whose only refs are `foreign_qualified` is missing too (Decision
  Moment `01M3NYFZ1P6QBD2DX4DVDA323W`), cited at `:1214`.
- `src/specify_cli/cli/commands/agent/tasks_map_requirements.py:538-564`
  (`_mr_classify_wp_refs`) and `src/specify_cli/cli/commands/agent/tasks_mapping_core.py:214-234`
  (`_classify_new_ref_offenders`).
- `src/runtime/next/runtime_bridge_cores.py:343-366` (`_classify_wp_refs`) — returns
  `(accepted, rejected)`; `rejected` is populated only for `FAILING_REASONS` members, so a
  `foreign_qualified` ref is dropped from the rejected list entirely while an accepted
  sibling on the same WP survives regardless. The same missing-WP rule (Decision Moment
  `01M3NYFZ1P6QBD2DX4DVDA323W`) is cited at `:376`.

### Authored refs are never rewritten

Decision Moment `01M3NSKHE8T6TBKNFPSJ6BRD2G`: `finalize-tasks` never rewrites an existing
item; `map-requirements` writes added refs in canonical form, keeps existing items
byte-identical, and dedups by canonical form. `finalize-tasks`'s bootstrap never rewrites
an authored `requirement_refs` list, whatever
the resolved/classified value looks like; its only write is a narrow populate-when-empty
one for the legacy tasks.md-fallback case
(`src/specify_cli/cli/commands/agent/mission_finalize.py:1554-1619`, guard at
`:1615-1618`). `map-requirements` is append-only: existing items are kept byte-identical
and in place, new refs are merged in canonical form, and duplicates are dropped by
canonical-form dedup (`src/specify_cli/cli/commands/agent/tasks_mapping_core.py:125`
`_dedup_key`, `:136` `_merge_refs`, `:237-273` `plan_mapping`).

### `map-requirements` input tokenisation and stale-ref reporting

Both `--refs` (a space/comma-separated scalar) and `--batch` (a JSON `{WP_ID: [refs]}`
object) are tokenised through the shared `grammar.tokenize_refs` before classification —
`_mr_build_new_mappings` (`src/specify_cli/cli/commands/agent/tasks_map_requirements.py:239-270`),
`--batch` at `:259`, `--refs` at `:269` — so neither input path re-splits or re-cases a
ref on its own. The pre-write gate (`_mr_gate_offenders`, `:430-475`) and the post-write
stale gate (`_mr_stale_gate`, `:584-641`) both classify through the same grammar verdict
table: a `foreign_qualified` ref is reported only in `stale_ref_reasons` (informational),
never in `stale_refs`, whose `--replace to correct` hint would otherwise invite deleting a
valid cross-mission citation, and a WP whose only stale refs are `foreign_qualified` never
sets the gate (`:609-618`). The unknown-ID refusal (`_mr_gate_offenders`, `:459-475`) now
carries `parsed_spec_ids` alongside `unknown_refs` (`:461,466`), the same additive
diagnostic `finalize-tasks` carries — an operator debugging a rejected `map-requirements`
call sees the same "what does the tool believe the spec declares" answer #2066 asked for.

### SC tracked, not gating

`success_criteria_coverage` is informational: an unreferenced declared SC never fails a run
(`src/specify_cli/cli/commands/agent/mission_finalize.py:1275-1300`,
`_build_success_criteria_coverage`; Decision Moment `01M3NRCRYFBC1QNN62EFGXDVBY`: SC status
in the requirement graph is tracked, not gating). The prior "SC … dropped, not traced"
advisory warning is retired — `find_discarded_sc_refs` no longer exists anywhere in `src/`.

### Diagnostics: `parsed_spec_ids` and `rejected_requirement_refs`

`finalize-tasks` reports both, additively, on the failure payload AND on the
`--validate-only`/real-run success payload alike
(`src/specify_cli/cli/commands/agent/mission_finalize.py:1303-1328`, `_build_requirement_diagnostics`,
spread into success JSON at `:2122` and `:3068`).

### Setup-plan gate and orchestrator-api parity

`setup-plan` refuses (exit 1) a spec.md that declares a malformed requirement ID
(Decision Moment `01M3NRCYSGDJ3VDW6KJ2DVBWZF`: block malformed declared ids, warn only on
prose citations): `_evaluate_requirement_id_gate`
(`src/specify_cli/cli/commands/agent/mission_setup_plan.py:526-559`) returns
`error_code: SPEC_REQUIREMENT_IDS_INVALID` and `invalid_requirement_ids` (`:549,551`),
via `SetupPlanLocalOutcome(payload, 1, "error")` (`:559`). Prose suspects (unqualified,
unsuffixed FR/NFR/C tokens outside a declared position) are reported separately as
`requirement_id_warnings`, non-blocking (`:996-1062`, `_build_setup_plan_result`). HTML
comments are blanked, position-preserving, before either scan sees the text
(`src/specify_cli/requirement_mapping/lint.py:190`, `grammar.blank_html_comments`).

`orchestrator-api`'s `plan` verb keeps its envelope in contract rather than leaking a newly
unregistered delegate code (Decision Moment `01M3NSKEGC7QNXA1G3711AP77X`: the envelope
keeps `PLAN_SETUP_FAILED`, the real reason travels in `data`, and the direct setup-plan JSON
still uses the typed `SPEC_REQUIREMENT_IDS_INVALID` code): `_plan_contract_error`
(`src/specify_cli/orchestrator_api/commands.py:497-516`) degrades an unregistered code (for
example `SPEC_REQUIREMENT_IDS_INVALID`) to the already-registered `PLAN_SETUP_FAILED`, with
the real code preserved as `data.reason` (`:516`); a registered code passes through
unchanged. The shared `_classify_delegate_error` helper and
`src/specify_cli/core/upstream_contract.json` are unchanged by this Mission —
`git diff 0ec391f39c..HEAD -- src/specify_cli/core/upstream_contract.json` is empty
(`0ec391f39c` is the Mission's last planning commit).

### Runtime injection

The runtime cores take the grammar by **required** dependency injection, never a local
fallback pattern: `RequirementGrammarLike(Protocol)`
(`src/runtime/next/runtime_bridge_cores.py:298-317`) declares only the members the cores
call, satisfied structurally by the real `specify_cli.requirement_mapping.grammar` module;
`RequirementMappingFacts.grammar: RequirementGrammarLike` (`:327-340`) has no default. The
supplier call site passes the real module in: `_cores.RequirementMappingFacts(...,
grammar=grammar, ...)` (`src/runtime/next/runtime_bridge.py:1105-1111`).

### C-001 gate and frozen divergences

The single-source architectural gate
(`tests/architectural/test_requirement_id_grammar_single_source.py`) AST-scans `src/` for a
second requirement-ID kind-alternation literal, against a shrink-only allowlist
(`tests/architectural/requirement_id_pattern_allowlist.yaml`) whose `baseline` is checked
two-sided against the file's own entry count. At this Mission's tip, `baseline: 2`, exactly
the two frozen divergences below; an earlier transitional third entry
(`runtime_bridge_cores.py`'s own local pattern) was removed by WP04 once the cores took the
grammar as an injected, required argument, lowering the baseline from 3 to 2 in that same
edit.

- `src/specify_cli/missions/_substantive.py`, constant `_FR_TABLE_ROW` — the setup-plan
  substantive-spec gate's own functional-requirement table-row pattern, a cheap structural
  heuristic independent of the grammar's full ID space (SC, suffixes, qualifiers). Follow-up ticket: [#5387](https://github.com/spec-kitty/spec-kitty/issues/5387).
- `src/specify_cli/retrospective/generator.py`, constant `_FR_REF_RE` — the retrospective
  generator's narrower, retrospective-specific FR-only scan (3+ digit FRs, no NFR/C/SC, no
  suffix or qualifier), predating this Mission. Follow-up ticket: [#5388](https://github.com/spec-kitty/spec-kitty/issues/5388).

**Provenance correction (2026-09-30).** An earlier revision of this ADR attributed both
frozen divergences to a HiC ruling. That was wrong. They came from a scope deferral the
orchestrator made in auto mode (Decision Moment `01M3P07HV88QNVVKP3E2W28VB6`: "outside
every issue's scope and locality forbids migrating it in-mission"). The only HiC ruling
(Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`) decided one thing: migrate
`consolidation/retention.py` in-mission rather than freeze it. No human ruled that the two
remaining patterns must stay separate by design.

`src/specify_cli/consolidation/retention.py` is **not** a divergence: WP01 migrated its
constraint-row check onto `grammar.parse` in this Mission
(`consolidation/retention.py:10,70`), per that HiC ruling.

**Amendment 2026-09-30 (#5387, #5388): both divergences drained, `baseline: 0`.**

- The setup-plan substantive-spec gate (`missions/_substantive.py`) now counts a
  functional-requirement row only when its lead is a local FR id in a grammar-declared shape
  (`grammar.DECLARED_TABLE_ROW` / `grammar.DECLARED_LIST_ITEM`, both named out of
  `DECLARED_SHAPE_PATTERNS`), with HTML comments blanked as the declared-id scan does. A
  spec whose FRs are all letter-suffixed (`FR-006a`) or wider than three digits (`FR-1001`)
  is no longer judged "not substantive".
- The retrospective generator (`retrospective/generator.py`) takes this spec's FRs from
  `parse_requirement_ids_from_spec_md(...)["functional"]` and judges every WP-file citation
  with `grammar.classify` against that set. A prose citation of another mission's FR is no
  longer reported as an uncovered requirement, a suffixed FR is no longer invisible, and a
  foreign-qualified citation (`other-mission#FR-001`) no longer covers a local FR.

### Known residuals

Six accepted, honestly-recorded low residuals (WP01 review; see
`traces/design-decisions.md:23-24` for the original acceptance of the first four, and the
pre-PR review fold for the last two) remain live at this Mission's tip:

- **The C-001 literal gate cannot see a runtime-joined alternation.** The architectural
  gate (`tests/architectural/test_requirement_id_grammar_single_source.py`) walks only
  `ast.Constant` string nodes, including `JoinedStr` f-string parts, EXCEPT docstrings
  (`:23-24`); it never visits a `Call` node, so a kind alternation assembled at runtime
  (for example via `"|".join([...])`) is invisible to it (`:281` gates on
  `isinstance(node, ast.Constant)`). The grammar's own core literal is a detectable
  constant asserted by name, so copying the idiom is caught; deliberate obfuscation of a
  second authority stays a review concern, not a gate one.
- **A truncated slug parses as foreign with the wrong slug, never as local.** A qualifier
  missing its own token boundary — `foo/bar#FR-001` — captures only the trailing `bar` as
  the mission slug (`_SLUG`, `grammar.py:83`; `_QUALIFIED_KIND_DIGITS`, `:96`), so
  `grammar.find_all("foo/bar#FR-001", spec_scan=False)` returns a `foreign` id with
  `mission="bar"` — never a local `FR-001`. Verified directly against this Mission's tip.
- **`issue #FR-003` is dropped entirely.** A `#` immediately preceding a kind-digits token
  with no valid slug before it (the qualifier attempt backs off to zero-width) is treated
  as a leaked/truncated qualifier and the whole match is discarded, not read as local
  `FR-003` (`_has_invalid_qualifier_prefix`, `grammar.py:225`, checked against
  `_INVALID_QUALIFIER_LEAD`, `:199`). Verified directly:
  `grammar.find_all("issue #FR-003", spec_scan=False)` returns `[]`.
- **An ID declared only inside an HTML comment is no longer declared.** `_declared_ids`
  blanks every `<!-- ... -->` span, position-preserving, before scanning for declared
  shapes (`src/specify_cli/requirement_mapping/__init__.py:125,147`, calling
  `grammar.blank_html_comments`, `grammar.py:352`). This is an intended behaviour change
  from the pre-Mission scanner, pinned by tests; WP08's corpus scan reports affected
  specs. Listed here and under `#### Negative` below, not silently absorbed into the
  general "re-finalizing may newly fail" bullet.
- **An unterminated `<!--` blanks the rest of the spec.** `blank_html_comments` has no
  terminated/unterminated distinction for scanning purposes: `_HTML_COMMENT_UNTERMINATED`
  (`grammar.py:345`) blanks from an un-closed `<!--` to end-of-text, so a spec.md with a
  stray, never-closed `<!--` loses every declared ID and every prose token after it to
  both the declared-ID scan and the lint, silently. By design (mirrors an HTML renderer's
  own unterminated-comment behaviour); the corpus has zero hits for this shape.
- **A fenced code block is not honoured.** Neither `_declared_ids` nor
  `lint_spec_requirement_ids` special-case a markdown code fence (` ``` `): a requirement-ID
  token inside a fenced example block is scanned exactly like prose or a declaration, the
  same as every other span of text. By design (the grammar has no markdown-structure
  awareness beyond HTML comments); the corpus has zero hits for this shape.

### Supersession

This ADR supersedes the policy recorded by commit `f11791683a`
(`docs/changelog/CHANGELOG.md:1616`): `finalize-tasks` previously warned, advisory-only,
when an `SC-###` ref was discarded by the pre-Mission `(?:FR|NFR|C)`-only scanner, while
stating explicitly that "`SC` is **not** admitted as a first-class ref (the graph is
unchanged)". Under this Mission's single grammar, `SC` **is** a first-class kind: it
participates in the same verdict table as every other kind (an undeclared `SC` ref fails as
`unknown_spec_id`, exactly like an undeclared `FR`), its coverage is tracked
(`success_criteria_coverage`, informational, never gating), and the discard-specific
advisory warning is retired as redundant with the general verdict table. No prior ADR
records the superseded policy (`grep -rln -i 'success.criteri' docs/adr/` returns three
unrelated hits, none of which document this discard rule), so no other ADR needs a
"Superseded by" note.

### Consequences

#### Positive

- One place to read, and one place to fix, requirement-ID recognition; the six-definition
  drift SC-006 measured cannot recur silently.
- No authored ref disappears without a trace (#2991 closed): a rejected ref is always
  reported, with its reason, never respelled or dropped.
- A previously invisible unmapped suffixed requirement now fails coverage loudly (#3519
  part 2 closed).
- A rejected ref never discards a valid sibling's coverage (research R8's structural risk
  closed) — the shared FR-019 verdict table is per-ref everywhere.

#### Negative

- Re-finalizing an existing Mission may newly fail on a previously-silent suffixed FR or a
  malformed/undeclared ref that the old, looser scanners let through (intended; WP08's
  corpus scan lists the affected Missions).
- The four known specs identified in NFR-001(b) are refused on re-plan under the new
  setup-plan gate until their declared IDs are corrected.
- Dossier parity hashes change for any WP whose refs were previously silently erased by the
  pre-Mission bug (the hash now reflects the preserved, authored refs).
- The byte-contract fixture (NFR-002) flips to the new additive JSON keys.
- An ID declared only inside an HTML comment no longer counts as declared (see "Known
  residuals" above) — an intended, tested behaviour change from the pre-Mission scanner.
- `requirement_refs_parsed` (both the failure and success payloads,
  `src/specify_cli/cli/commands/agent/mission_finalize.py:1355,3033`) changed meaning: it
  now lists every WP's authored raw tokens verbatim (case preserved, including malformed
  and foreign ones) via the raw reader `read_all_wp_raw_requirement_refs`
  (`src/specify_cli/requirement_mapping/__init__.py:541-559`, wired in at
  `mission_finalize.py:1068`), not the pre-Mission normalised/accepted-only subset. A
  consumer that read this key as "the accepted refs" must instead classify each token
  itself (or read `rejected_requirement_refs`/`unknown_requirement_refs` alongside it).
- `unknown_requirement_refs` now includes every ref whose rejection reason is in
  `FAILING_REASONS` (`malformed` as well as `unknown_spec_id`), not `unknown_spec_id`
  alone (`_classify_wp_requirement_refs`,
  `src/specify_cli/cli/commands/agent/mission_finalize.py:1201-1243`, `:1236-1238`) — a
  malformed ref that previously surfaced only via a separate error path now shows up in
  this key too.

#### Neutral

- `requirement_mapping` becoming a package is an internal reorganisation only; every
  existing import path is preserved via re-export.

### Confirmation

- The C-001 architectural gate (`tests/architectural/test_requirement_id_grammar_single_source.py`)
  stays green with an empty allow-list (`baseline: 0`) since the 2026-09-30 amendment.
- The cross-command parity test (`tests/specify_cli/test_requirement_reason_parity.py`, WP06
  T038) proves `finalize-tasks`, `map-requirements` and the runtime readiness check agree on
  both the pass/fail verdict and the per-ref reason, through production entry points only.
- The per-surface tests WP02 (finalize), WP03 (map-requirements), WP04 (runtime), and WP05
  (setup-plan/orchestrator-api) each added in their own lanes.

## Links

- [`2026-06-06-1-plan-concerns-to-work-package-traceability.md`](2026-06-06-1-plan-concerns-to-work-package-traceability.md)
  — implementation-concern IDs (`IC-##`) stay a separate, plan-level grammar (C-004); this
  Mission's grammar never recognises an `IC` kind (`grep -rn '"IC"' src/specify_cli/requirement_mapping/`
  and `grep -rn 'IC-' src/specify_cli/requirement_mapping/` both return no matches).
- [`2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`](2026-07-17-1-red-main-is-honest-ci-is-release-authority.md)
  — the red-first repro discipline (NFR-005) this Mission's WP02-WP06 each followed.
