# Mission Specification: synthesize consumes generator-shape proposals

**Mission Branch**: `retrospect-synthesize-generator-proposals-01M68ZKX`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6385 — `retrospect create` never emits proposals, and `agent retrospect synthesize` cannot apply generator-shape proposals, so `create` → `synthesize` is a no-op"

## Problem

`spec-kitty retrospect create` writes a **generator-shape** record (`GenRetrospectiveRecord`, the
dataclass schema in `specify_cli/retrospective/schema.py`), while
`spec-kitty agent retrospect synthesize` applies only the **nested** Pydantic `Proposal` shape
(`kind` + typed `payload`). The two halves of the documented
`retrospect create` → `agent retrospect synthesize` loop therefore never meet:

1. **`create` emits an empty `proposals` list, always.** `_build_findings` in
   `specify_cli/retrospective/generator.py` starts `proposals: list[GenProposal] = []`, never
   appends to it, and `_classify_risk` — the helper that would classify one — has no caller.
2. **`synthesize` cannot plan a generator-shape proposal even when one exists.** On the
   generator-shape fallback path the command sets `all_proposals = []` unconditionally
   (`specify_cli/cli/commands/agent_retrospect.py`), prints a single warning only when the record
   happens to carry proposals, and then reports `planned: [] applied: [] conflicts: []` as a
   normal, successful exit-0 dry-run. A record with 19 `not_helpful` findings and 2 `gaps`
   produces no warning at all: there was nothing to warn about, because the proposals list was
   empty.

The two gaps stack, and either one alone empties the loop, so a batch that plans nothing looks
exactly like a batch that had nothing to plan. The operator gets a green run that changed nothing
and no statement of why.

Per the batch-14 triage on the issue, this Mission owns the **application and reporting** half.
Deciding which payload kind each finding maps to, and emitting payloads from `_build_findings`, is
the generation half and stays with #3947 (already linked from the issue); the seam this Mission
builds is what #3947 fills.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A typed generator-shape proposal is planned and applied (Priority: P1)

An operator (or a future generator) writes a proposal into a `retrospect create`-shape record with
a structured `payload` block. `synthesize` recognises it, translates it into the typed proposal
`synthesize` already knows how to apply, and plans it — and with `--apply`, applies it to
project-local state.

**Why this priority**: This is the missing half of the loop. Without it no generator-shape record
can ever reach `planned`, whatever `create` writes, so #3947 alone could not close the issue.

**Independent Test**: Write a generator-shape record whose `proposals` entry carries an
`add_glossary_term` payload (and an `auto_applicable: true`), run the real
`spec-kitty agent retrospect synthesize --mission <slug>` dry-run and read `planned` from the JSON
envelope; then run `--apply` and read the glossary file it wrote.

**Acceptance Scenarios**:

1. **Given** a generator-shape record with one proposal carrying a valid typed `payload`, **When**
   the operator runs `synthesize` (dry-run), **Then** `planned` contains that proposal and the
   envelope reports `translated: 1`.
2. **Given** the same record, **When** the operator runs `synthesize --apply`, **Then** the
   payload's target is written to project-local state and `applied` is non-empty.
3. **Given** a generator-shape proposal whose `payload.kind` disagrees with the verb in
   `suggested_action`, **When** the operator runs `synthesize`, **Then** nothing is planned for it
   and the run names the id and the disagreement as the reason.

---

### User Story 2 - A generator-shape record that plans nothing says so (Priority: P1)

An operator runs `synthesize` on the record a real `retrospect create` wrote: findings, no
proposals. The run states the record shape, the finding counts, and that nothing was planned or
planned-and-skipped, and it points at the remedy — instead of a bare `planned: [] applied: []`
that reads like success.

**Why this priority**: This is the issue's own minimum bar ("a created record with findings should
not end in a silent, successful-looking empty batch"). It is what tells the operator the loop is
not wired for their record yet, rather than letting them believe synthesis ran.

**Independent Test**: Write a generator-shape record with `not_helpful`/`gaps` findings and no
proposals, run the real `synthesize` with `--json`, and assert the envelope carries a named
diagnostic block and the Rich surface carries a warning; then write a record with no findings at
all and assert the diagnostic distinguishes that case from the findings-bearing one.

**Acceptance Scenarios**:

1. **Given** a generator-shape record with findings and zero proposals, **When** the operator runs
   `synthesize`, **Then** the envelope and the Rich output both state that the record is
   generator-shape, how many findings it carries, that zero proposals could be planned, and what
   to do next.
2. **Given** a generator-shape record with findings and proposals that carry no `payload`, **When**
   the operator runs `synthesize`, **Then** every such proposal is named with its reason and none
   is silently dropped.
3. **Given** a generator-shape record with no findings and no proposals, **When** the operator runs
   `synthesize`, **Then** the diagnostic says the record has no findings (a genuinely empty record)
   rather than implying a broken conversion.
4. **Given** any successful `synthesize` dry-run, **When** it completes, **Then** the documented
   exit-code contract is unchanged (exit 0; the empty-batch signal is diagnostic, not an error
   code) — the change is what the operator is *told*, not a new failure mode for a valid record.

---

### User Story 3 - `retrospect create` stops promising a synthesis it cannot feed (Priority: P2)

An operator runs `retrospect create`, which prints the counts and a next step. When the record it
just wrote carries findings but no proposals, the next step says plainly that `synthesize` has
nothing to plan from a generated record yet and that grading findings into proposals is tracked
separately (#3947), instead of "run synthesize to review proposals".

**Why this priority**: The issue's alternative acceptable resolution is that "the docs and `create`
output say plainly that synthesize is not usable on created records yet". Leaving the misleading
prompt in place is the silent half of the defect.

**Independent Test**: Run the real `retrospect create` against a fixture mission whose recorded
findings are non-empty (or drive the reporting helper with a persisted record) and assert the
rendered next step and the JSON `next_step` field both name the limitation; then run it for a
record with proposals and assert the ordinary next step is unchanged.

**Acceptance Scenarios**:

1. **Given** a mission whose created record has findings and no proposals, **When** `retrospect
   create` completes, **Then** its next step states that synthesize cannot plan proposals from a
   generated record yet and names #3947.
2. **Given** a record that carries proposals, **When** `create` completes, **Then** the next step
   is the ordinary "run synthesize" text.

---

### Edge Cases

- A generator-shape record that also *parses* as the nested schema: `read_record` wins, the
  generator fallback never runs, and nothing in this Mission changes that path.
- A `payload` that fails the nested schema (missing `body_hash`, unsafe `artifact_id`, unknown
  `kind`): untranslatable, named with the validation detail, never applied and never a crash.
- Duplicate proposal ids across a generator-shape record: translated ids stay deterministic and
  distinct; a collision is refused rather than silently merged.
- `--proposal-id` against a generator-shape record: the refusal message must reflect the new
  reality — a translated proposal that is `pending` is refused as pending (with the remedy), and an
  id the record does not carry is refused as unknown. Untranslatable ids keep their own status.
- `--fabricate-empty` records: fabricated by this command with `proposals: []` and
  `ran_no_findings`; the new diagnostic must describe them accurately and must not claim a broken
  conversion.
- Evidence refs on a translator-produced proposal: an id must resolve to a real event id in the
  source mission's log, or be omitted; a bogus id must not be invented from a finding id.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Generator record carries a typed payload | As a generator or operator, I want a generator-shape proposal to carry an optional structured `payload` so that a proposal can express what it applies without free-text verb parsing. | High | Open | [build] | no |
| FR-002 | Translation to typed proposals | As an operator, I want `synthesize` to translate every translatable generator-shape proposal into the typed proposal it applies so that a created record can reach `planned`/`applied`. | High | Open | [build] | no |
| FR-003 | Deterministic translated ids | As an operator, I want a translated proposal's id to be stable across runs and derived from the record so that re-running synthesize never double-applies or renames a proposal. | High | Open | [build] | no |
| FR-004 | Untranslatable proposals are named | As an operator, I want every generator-shape proposal that cannot be translated named with its reason so that no proposal is silently dropped. | High | Open | [build] | no |
| FR-005 | Empty batch is not silent | As an operator, I want a generator-shape record that plans nothing to say so — shape, finding counts, zero planned, next step — in both the JSON envelope and the Rich output. | High | Open | [build] | no |
| FR-006 | `create` next step is honest | As an operator, I want `retrospect create` to stop pointing at a synthesis that cannot plan from a generated record with findings and no proposals. | Medium | Open | [build] | no |
| FR-007 | Exit-code contract unchanged | As a tool consumer, I want a valid dry-run to keep exiting 0 so that the documented exit-code table stays true and the honesty change is additive. | High | Open | [ratchet] | no — paired with FR-005 on the same fixture (both surfaces asserted on one record) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Record bytes unchanged for old records | A generator-shape record with no `payload` anywhere serialises to byte-identical YAML, so no existing `retrospective.yaml` is rewritten by a read/write round trip. | Reliability | High | Open |
| NFR-002 | No new apply path | Translation produces the same `Proposal` type `apply_proposals` already accepts; no new writer, no second application seam, no change to `charter_pack_synthesizer`. | Technical | High | Open |
| NFR-003 | Fail closed | An unparsable `payload`, an unsafe artifact id or a missing discriminator yields an untranslatable entry with a reason; no exception escapes as a traceback and no partial batch is applied. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Generation stays in #3947 | `_build_findings` keeps emitting no proposals from findings; this Mission only builds the seam that consumes them. | Business | High | Open |
| C-002 | Nested schema is the single authority | The payload block is validated by the existing `ProposalPayload` discriminated union; no second payload schema is introduced. | Technical | High | Open |
| C-003 | Documented surfaces only | The JSON envelope and exit codes stay additive; no existing key is renamed or removed, and `docs/api/retrospective-schema.md`'s exit-code table keeps holding. | Business | High | Open |

### Key Entities

- **Generator-shape record** (`GenRetrospectiveRecord`): the dataclass schema `retrospect create`
  writes to `kitty-specs/<slug>/retrospective.yaml`; free-text findings plus an optional `payload`
  on each proposal.
- **Nested record / typed proposal** (`Proposal`): the Pydantic schema `synthesize` applies; each
  proposal has a discriminated `payload`, a `state`, and provenance.
- **Translation**: the pure function that maps one generator-shape proposal to one typed proposal,
  or to a named reason it cannot.
- **Diagnostic**: the statement a `synthesize` run makes about what it could and could not plan —
  shape, counts, untranslatable ids, next step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's hand-authored case reaches `planned`: a generator-shape record whose
  proposal carries a valid typed payload yields `planned` ≥ 1 on the real CLI, and `--apply` writes
  the payload's target. — [build] · no-op passable: no
- **SC-002**: The issue's reported case is no longer silent: a created record with 19 `not_helpful`
  findings, 2 `gaps` and 0 proposals produces a diagnostic naming the record shape, both counts and
  zero planned, on the real CLI — 0 runs that print an unexplained empty batch. — [build] · no-op passable: no
- **SC-003**: Every untranslatable proposal in a fixture record appears by id and reason: 0 dropped
  proposals across the fixture set, with a positive control (the same fixture's translatable
  proposal) proving the probe can see a translated one. — [build] · no-op passable: no
- **SC-004**: `retrospect create`'s next step for a findings-bearing, proposal-free record names the
  limitation and #3947; a record with proposals keeps today's text — 0 misleading prompts on the
  first shape. — [build] · no-op passable: no
- **SC-005**: Round-trip conformance: `retrospect create` on a fixture mission with findings →
  `synthesize` → the run is either non-empty or explicitly diagnosed, asserted end to end on the
  real CLI, guarding the #1239/#3533 reader class as well. — [build] · no-op passable: no

## Out of Scope

- Emitting proposals from findings in the generator (`_build_findings`), i.e. deciding which payload
  kind a finding maps to — #3947, linked from the issue, coordinated by a comment on that issue.
- Verb-parsing `suggested_action` to invent a payload. The issue calls it fragile; the structured
  `payload` field is the safer option it names.
- Making `retrospect create` auto-accept or apply anything, and any change to
  `charter_pack_synthesizer`'s apply semantics.
- The `retrospect summary` surface and the #5512/#5479 `--proposal-id` commit routing, beyond the
  generator-record refusal message this Mission must keep accurate.

## Traceability

| Source | Requirement |
|--------|-------------|
| #6385 "Observed" 1 (create emits `proposals: []`) | FR-005, FR-006, SC-002, SC-004 |
| #6385 "Observed" 2 (hand-authored proposal, warning, empty batch) | FR-001, FR-002, FR-003, SC-001 |
| #6385 "Expected" (either working translation, or plain statement) | FR-002, FR-005, FR-006, SC-002, SC-004 |
| #6385 "Possible directions" (structured field is safer) | FR-001, C-002 |
| #6385 "round-trip conformance test" request | SC-005 |
| #6385 batch-14 triage (application/reporting here, generation in #3947) | C-001 |
| #1239 / #3533 (reader disagreement, already fixed) | SC-005 (regression guard) |
