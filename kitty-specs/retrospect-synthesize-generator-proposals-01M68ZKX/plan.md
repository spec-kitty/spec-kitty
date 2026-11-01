# Implementation Plan: synthesize consumes generator-shape proposals

**Branch**: `issue-6385-retrospect-synthesize-generator-proposals` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/spec.md`
**Input**: Mission specification from `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/spec.md`
**Research**: `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/research.md`

## Summary

`spec-kitty retrospect create` writes the **generator-shape** record
(`GenRetrospectiveRecord` dataclass, `reader.read_gen_record`), while
`spec-kitty agent retrospect synthesize` can only apply the **nested** Pydantic `Proposal`
(kind + discriminated `payload`). On the generator-shape fallback path the command sets
`all_proposals = []` before calling `apply_proposals`, warns only when the record happens to carry
proposals, and reports `planned: [] applied: [] conflicts: []` as a normal exit-0 dry-run. So a
created record can never plan anything, and an operator cannot tell "nothing to plan" from
"nothing happened".

Per the issue's batch-14 triage, generation (deciding which payload kind a finding maps to, and
emitting proposals from `_build_findings`) belongs to #3947 and is **out of scope**. This Mission
delivers the application + reporting half in three parts:

1. **A structured payload seam.** A generator-shape proposal may carry an optional `payload`
   mapping, validated against the *existing* `ProposalPayload` discriminated union. No second
   payload schema.
2. **Translation.** A new pure module maps each translatable generator-shape proposal to the
   typed `Proposal` `apply_proposals` already consumes (deterministic ULID id derived from the
   source mission, state from `auto_applicable`, evidence limited to real event-id ULIDs), and
   returns every untranslatable proposal with a named reason. `synthesize` then plans and applies
   them exactly like nested-schema proposals — same apply path, no new writer.
3. **Honest reporting.** A `diagnostics` block in the JSON envelope plus a Rich warning that,
   whenever a generator-shape record plans nothing (or anything is untranslatable), states the
   record shape, the finding counts, the translated/planned counts, each untranslatable id with
   its reason, and the next step. `retrospect create`'s own `next_step` stops promising a
   synthesis it cannot feed. Exit codes are unchanged (documented dry-run contract, C-003).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `typer`, `rich`, `pydantic` v2 (`TypeAdapter`, `ValidationError`), `ruamel.yaml`; existing modules `specify_cli.retrospective.{schema,reader,writer,generator}` and `specify_cli.charter_pack_synthesizer.apply_proposals` (read-only consumer)
**Storage**: `kitty-specs/<slug>/retrospective.yaml` (YAML on disk; no database)
**Testing**: pytest — CLI-level `typer.testing.CliRunner` runs of the real `agent retrospect synthesize` / `retrospect create` entry points, plus unit tests for the pure translation function
**Target Platform**: Linux/macOS CLI (no OS-specific code)
**Project Type**: single project (Python CLI)
**Performance Goals**: no measurable change; translation is O(proposals) over one record in memory
**Constraints**: byte-identical YAML for records without `payload` (NFR-001); no new apply path (NFR-002); fail closed on any payload problem (NFR-003); exit codes and existing envelope keys unchanged (C-003)
**Scale/Scope**: 2 modules edited (`retrospective/schema.py`, `retrospective/reader.py`, `retrospective/writer.py` — three, all small), 1 new module (`retrospective/generator_proposals.py` ≈ 150 lines), 2 CLI modules (`cli/commands/agent_retrospect.py`, `cli/commands/retrospect.py`), 1 contract JSON, ~250 lines of tests, docs + changelog

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | The payload is validated by the one `ProposalPayload` union; the typed `Proposal` is the one proposal type; `apply_proposals` stays the one application seam. `GenProposal` gains no parallel classifier. |
| Architectural alignment | PASS | All changes stay in `specify_cli.retrospective` + its CLI commands; `charter_pack_synthesizer` is imported, never modified. |
| ATDD-first / DIRECTIVE_034 | PASS | Three red tests drive the real `synthesize`/`create` CLI before the fix exists (payload proposal not planned; empty batch silent; `create` next step misleading). |
| Terminology canon (Mission vs feature) | PASS | Uses "generator-shape record", "nested/typed proposal", "payload", "translation", "diagnostic" — the vocabulary already in `reader.py`/`agent_retrospect.py`. |
| DIRECTIVE_024 Locality of Change | PASS | Edits the exact modules that already own each half; no opportunistic refactor of `_build_findings` or `apply_proposals`. |
| DIRECTIVE_041 (test only real behaviour) | PASS | Tests assert observable CLI/envelope outcomes and a written glossary file; the id-derivation test asserts stability across two runs, not an internal shape. |
| Acceptance-Criteria Non-Vacuity | PASS | FR-005/FR-007 are pinned on one fixture (diagnostics present *and* exit 0); every "untranslatable" assertion ships a translatable proposal in the same fixture (SC-003 positive control). |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites only: `tests/cli/`, `tests/retrospective/`, the touched-module unit tests. |
| Pre-existing Failure Reporting Rule | PASS | Pre-existing reds (#6801, #6816, #5927; #6798 closed) are cited in the PR, never papered over. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery decisions D1-D6)
├── spec.md              # Mission specification
├── tasks.md             # Phase 2 output
└── tasks/WP*.md         # Per-work-package prompts
```

No `data-model.md` / `quickstart.md` / `contracts/`: the record shape is already specified by
`kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json`,
which gains the optional `payload` property in WP01. A new data model for a record field would
duplicate that contract.

### Source Code (repository root)

```
src/specify_cli/
├── retrospective/
│   ├── schema.py                    # GenProposal: + optional payload (WP01)
│   ├── reader.py                    # _PROPOSAL_KEYS + _proposal() parse (WP01)
│   ├── writer.py                    # round trip, payload only when present (WP01)
│   └── generator_proposals.py       # NEW: translation (WP02)
└── cli/commands/
    ├── agent_retrospect.py          # translate + diagnostics + --proposal-id truth (WP03)
    └── retrospect.py                # create next_step honesty (WP03)

kitty-specs/retrospective-default-policy-01KS049J/contracts/
└── retrospective-record.schema.json # optional proposal.payload (WP01)

tests/
├── cli/test_agent_retrospect_synthesize.py   # translation + diagnostics CLI tests (WP03)
├── cli/commands/test_retrospect.py           # create next_step tests (WP03)
└── retrospective/test_generator_proposals.py # NEW: translation unit tests (WP02)

docs/
├── api/retrospective-schema.md               # generator-record limitation + payload seam (WP04)
├── guides/how-to/governance/use-retrospective-learning.md  # the create -> synthesize loop (WP04)
└── changelog/CHANGELOG.md                    # [Unreleased] entry (WP04)
```

**Structure Decision**: single project; the CLI commands are thin bindings over the retrospective
package, which is where the record schema, reader and writer already live.

## Implementation Concern Map

- **IC-01 Record shape**: `GenProposal` and its reader/writer must carry an optional `payload`
  without perturbing any existing record's bytes. Owner: WP01.
- **IC-02 Translation purity**: mapping a generator-shape proposal to a typed `Proposal` (or a
  named reason it cannot) must be provably deterministic and side-effect free. Owner: WP02.
- **IC-03 CLI truthfulness**: `synthesize` must plan translated proposals and say exactly what it
  could not plan; `create` must not promise a synthesis it cannot feed. Owner: WP03.
- **IC-04 Documentation and contract surface**: the reference, the how-to and the changelog must
  state the seam and the still-open generation half (#3947). Owner: WP04.

## Phase 0: Outline & Research

Done in `research.md` (discovery + plan extension): D1 re-verifies every line the issue cites on
`dfe9efb0e8`; D2 records the triage scope split; D3 fixes the payload-over-verb-parsing decision
with its id/state/evidence rules; D4 fixes "loud, not failing"; D5 surveys the change surface; D6
names the test surfaces. Open questions D6.1 (envelope placement) and D6.2 (`--proposal-id`
semantics) are resolved in Phase 1 below.

**Phase 1 resolution of the open questions**

1. **Envelope placement**: a top-level `diagnostics` object on the JSON envelope, sibling to
   `status`/`outcome`/`result`. `result` is `SynthesisResult.model_dump()`, owned by
   `charter_pack_synthesizer`; adding keys there would change a model this Mission must not touch
   (NFR-002). Shape:
   ```json
   "diagnostics": {
     "record_schema": "generator",
     "findings": {"helped": 0, "not_helpful": 19, "gaps": 2, "proposals": 0},
     "proposals_translated": 0,
     "proposals_planned": 0,
     "untranslatable": [{"proposal_id": "p-001", "reason": "no structured payload"}],
     "next_action": "…"
   }
   ```
   The block is emitted for generator-shape records only, so nested-schema envelopes are
   byte-identical to today (C-003).
2. **`--proposal-id` semantics**: unchanged. An `accepted` translated proposal (record declares
   `auto_applicable: true`) can be selected; a `pending` translated proposal is refused as
   `pending` with the remedy named; an untranslatable id is refused with
   `unsupported_generator_proposal` plus its translation reason; an absent id is `unknown`. No new
   approval power is granted to the flag (the #5512/#5479 concern stays untouched).

## Phase 1: Design & Contracts

### Translation contract (`specify_cli/retrospective/generator_proposals.py`)

```python
@dataclass(frozen=True)
class UntranslatableProposal:
    proposal_id: str
    reason: str

@dataclass(frozen=True)
class GeneratorProposalTranslation:
    proposals: list[Proposal]              # typed, ready for apply_proposals
    untranslatable: list[UntranslatableProposal]
    translated_ids: dict[str, str]         # gen id -> typed proposal id (for --proposal-id truth)

def translate_generator_proposals(
    record: GenRetrospectiveRecord, *, actor: ActorRef
) -> GeneratorProposalTranslation: ...
```

Rules, each with a test:

| Rule | Input | Outcome |
|---|---|---|
| T1 | `payload` absent | untranslatable, `"no structured payload (add a payload block validated by the nested proposal schema; generating payloads from findings is #3947)"` |
| T2 | `payload` present but fails `ProposalPayload` validation | untranslatable, reason carries the first validation error line |
| T3 | `payload.kind` disagrees with the typed verb in `suggested_action` | untranslatable, names both |
| T4 | valid payload | typed `Proposal`: `id` derived (below), `kind = payload.kind`, `rationale = summary` (truncated to the 2000-char cap), `state` = `accepted` iff `auto_applicable` else `pending`, `provenance` = source mission id + evidence event-id ULIDs mined from the proposal's referenced evidence ranges + `authored_by = actor` |
| T5 | two proposals derive the same id | second is untranslatable, `"id collision with <gen id>"` (never merged) |
| T6 | no evidence ULIDs | `source_evidence_event_ids: []` (no staleness claim) — never a synthesized event id |

**Id derivation**: `ProposalId` is `^[0-9A-HJKMNP-TV-Z]{26}$` (ULID). Take the source
`mission_id` (a ULID) and replace its last three characters with the first three characters of
`base32(sha256(gen_proposal_id))` over the Crockford alphabet. Deterministic, stable across runs,
distinct per generator id (collision checked, T5), and lexicographically adjacent to the mission's
own timestamp so ids sort predictably.

### Envelope and Rich surface

- One helper builds the diagnostics dict from the translation + the `SynthesisResult`; both the
  JSON and the Rich renderer read it, so the two surfaces cannot disagree.
- Rich prints a `[yellow]Warning:[/yellow]` block when `untranslatable` is non-empty **or** nothing
  was planned on a generator-shape record, including the finding counts and the next step.
- `--json` prints nothing extra to stdout (the envelope carries it); the existing stderr warning
  for a *malformed* record is untouched.

### `create` next step

`create_cmd` computes `next_step` from the persisted record: if `proposals` is empty and any of
`helped`/`not_helpful`/`gaps` is non-empty, the next step says synthesize cannot plan proposals
from a generated record yet (generation tracked in #3947) and that a proposal needs a `payload`
block; otherwise today's text. Rendered in both the panel and the JSON `next_step`.

### Contract and docs

- `contracts/retrospective-record.schema.json`: `proposal` gains optional `payload` (object).
- `docs/api/retrospective-schema.md`: a "Generator-shape records" subsection stating that
  `create` writes `proposals: []` today, that a proposal is planned only when it carries a
  `payload`, and that generating payloads is #3947; plus the `diagnostics` block and the
  unchanged exit codes.
- `docs/guides/how-to/governance/use-retrospective-learning.md`: the loop section gains the same
  statement in operator terms.
- `docs/changelog/CHANGELOG.md`: one `[Unreleased]` entry under 1,200 characters.

## Risks

| Risk | Mitigation |
|---|---|
| Deriving a ULID id looks invented | It is deterministic, documented in the module docstring, and tested for stability; the alternative (rejecting generator proposals whose ids are not ULIDs) would leave the loop empty again. |
| A translated proposal applies with wrong risk semantics | `state` follows `auto_applicable` only; `--apply` is still required for any mutation; `flag_not_helpful` keeps today's auto-include rule. |
| Diagnostics bloat the envelope for nested records | The block is emitted only when the generator-shape fallback ran; a test pins the nested-schema envelope keys unchanged. |
| Scope creep into #3947 | C-001: `_build_findings` and `_classify_risk` are untouched; the only generator-adjacent change is a field on the record it writes. |
