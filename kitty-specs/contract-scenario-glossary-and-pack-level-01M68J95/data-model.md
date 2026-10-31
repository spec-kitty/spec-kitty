# Data Model — Contract Scenario glossary entry and the Pack Level wording

This mission has no runtime data. Its "entities" are the two documentation shapes it
edits, recorded here so the entry's structure and invariants are explicit before the
prose is written.

## Entity: Glossary entry

A glossary term in `docs/context/`. Authored as a `### Term` heading followed by a
two-column markdown table. Delimited from its neighbours by a `---` rule.

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `heading` | `### <Term>` | yes | The canonical surface; the page's other entries link to it by anchor |
| `Definition` | one table cell | yes | One concept, functional not compositional, readable without a follow-up question (`styleguide:kitty-glossary-writing`) |
| `Context` | `Governance` \| `Mission` \| … | yes | The glossary context page's own domain |
| `Status` | `candidate` \| `canonical` \| `deprecated` \| `superseded` | yes | New terms enter as `candidate`; the Human-in-Charge (HiC) promotes to `canonical` |
| `Applicable to` | version scope, e.g. `` `4.x` `` | yes | Matches the neighbouring entry on the same page |
| `Do NOT use when` | prose | optional | Disambiguation guard; names the neighbouring terms that own the other senses |
| `Related terms` | links or prose | optional | In-page anchors (`#term`) or cross-page relative links (`./page.md#term`) |
| `Note` | prose | optional | Anything the rows above do not carry |

Source of truth: `docs/context/glossary-conventions.md`, "Term Entry Schema".

## Entity: Contract Scenario (the term being added)

| Attribute | Value |
| --- | --- |
| Surface | `Contract Scenario` |
| Sense | the Gherkin behavior half of the charter contract |
| Where it lives | `contracts/charter/scenarios/` in `spec-kitty/spec-kitty-charter` (today `action_context.feature`, `errors.feature`, `packs.feature`) |
| What it does | names pack files, calls one operation of `contracts/charter/openapi.yaml`, states the answer |
| Tags | `@contract` — runs in `verifyAll`; `@provisional` — behaviour the conformance corpus has yet to decide |
| Distinguish from | the acceptance scenarios under `tests/scenarios/charter/`; the conformance corpus as a whole; BDD the practice |
| Context | Governance (charter contract) |
| Status | `candidate` — the styleguide's entry rule: a new term enters as candidate, the HiC promotes |
| Applicable to | `4.x` (matches the Charter Pack entry it sits beside) |

## Entity: Pack Level (the term being corrected)

Invariants the edit must preserve:

1. The entry still declares that a Charter Pack's level is declared by `pack_level` in
   its `pack.yaml`, one of `built-in`, `org` or `project`, in ascending precedence.
2. It still cites [ADR 2026-10-11-2](../../adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md).
3. It still names `kernel.pack_tiers` as the one authority for the three level names —
   the module name is not renamed.
4. It still carries `PACK_LEVEL_MISMATCH` (refusal), `PACK_LEVEL_MISSING` (non-blocking
   diagnostic during the deprecation window, refusal afterwards — #6403's shipped
   wording), and the `built-in` single-spelling fold.
5. In prose, a pack's level is a **level**, never a **tier**. "Tier" survives only
   inside the module name `kernel.pack_tiers` (an inline code span).

The same claim restated in the **Charter Pack** entry (`docs/context/charter.md`) carries
invariants 1–5 minus the entry-local error codes.

## Entity: Guard test

| Attribute | Value |
| --- | --- |
| Path | `tests/docs/test_context_glossary_contract_scenario_and_pack_level.py` |
| Fixtures | the two markdown files, read once; an entry-slicer helper that takes a `### Term` heading and returns the body up to the next `---` or `###` |
| Positive controls | the Pack Level entry contains `kernel.pack_tiers`; the Contract Scenario entry contains all four required rows; the slicer is proven to return a non-empty body for at least two known entries on each page |
| Negative probes | zero `tier`/`tiers` outside inline code spans in Pack Level and Charter Pack; the Contract Scenario entry is present and is not a bare heading |
| Failure messages | each assertion names the file, the entry and the offending word or missing row |

## State transitions

None. A glossary entry has a status lifecycle
(`candidate → canonical → deprecated/superseded`) but this mission moves no entry's
status: the new term enters as `candidate`, as the styleguide requires, and the
promotion is the HiC's call.

## Externally visible events

None. No CLI, contract or event surface changes.
