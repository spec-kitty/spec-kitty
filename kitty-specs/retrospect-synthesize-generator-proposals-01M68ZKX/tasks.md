# Work Packages: synthesize consumes generator-shape proposals (#6385)

**Inputs**: Design documents from `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (D1–D6)
**Issue**: spec-kitty/spec-kitty#6385 — application/reporting half only; generation stays in #3947 (C-001)

**Tests**: Required — this is a defect fix. The reproductions run red through the pre-existing CLI
entry points (`spec-kitty agent retrospect synthesize`, `spec-kitty retrospect create`) before the
fix exists (DIRECTIVE_034, ATDD-First Discipline).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently deliverable and testable; the chain is WP01 → WP02 → WP03 → WP04.

**Prompt Files**: Each work package references a matching prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`, `docs/`

---

## Work Package WP01: A generator-shape proposal can say what it applies (Priority: P1) 🎯 MVP

**Goal**: `GenProposal` carries an optional `payload` mapping, validated by the existing nested
`ProposalPayload` union, and it survives a read/write round trip without perturbing any record that
does not use it.
**Independent Test**: Write a generator-shape `retrospective.yaml` whose proposal carries a valid
`add_glossary_term` payload; `read_gen_record()` returns it intact and `write_gen_record()` of a
payload-free record reproduces the input bytes exactly.
**Prompt**: `tasks/WP01-proposal-payload-seam.md`
**Requirement Refs**: FR-001, NFR-001, NFR-003, C-002

### Included Subtasks

T001 Write the red-first round-trip test in `tests/retrospective/test_generator_proposal_payload.py` and prove it fails on the unfixed reader/writer (the `payload` key is rejected by `_PROPOSAL_KEYS` today)
T002 Add the optional `payload` field to `GenProposal` and validate it against `ProposalPayload` (single authority, no second schema)
T003 Teach `reader._PROPOSAL_KEYS` / `_proposal()` and `writer._gen_record_to_dict` / `_dict_to_gen_record` to carry it, emitting the key only when present
T004 Add the failure tests: unknown payload `kind`, missing required payload field, non-mapping `payload` — each raises a named `SchemaError`, never a traceback
T005 Run the targeted retrospective suites, `ruff` and `mypy` on the touched module

### Implementation Notes

- `_PROPOSAL_KEYS` is an allow-list; today a `payload` key makes `read_gen_record` raise. Add the
  key there, not a bypass.
- Emit `payload` in the serialized mapping **only when it is not None** — a record without payloads
  must serialise byte-identically (NFR-001). Pin that with a byte comparison, not a dict comparison.
- Validate with `pydantic.TypeAdapter(ProposalPayload)` and convert a `ValidationError` into the
  module's `SchemaError` with the first error line, so `synthesize`'s existing malformed-record path
  keeps working.
- Do **not** touch `generator.py` (C-001) — `create` keeps emitting `proposals: []`.

### Parallel Opportunities

- T002 and T004 are separable (model + validation tests), but both touch `schema.py`; serialise them.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A permissive `dict` field would let a bad payload through to apply time → validate at read time.
- YAML round-trip drift (`ruamel` reflow) → assert byte identity on a payload-free fixture.

---

## Work Package WP02: Translation from generator shape to typed proposals (Priority: P1)

**Goal**: A pure function turns every translatable generator-shape proposal into the typed
`Proposal` `apply_proposals` already applies, and returns every untranslatable one with a named
reason.
**Independent Test**: Unit-test the module directly: a payload-bearing proposal becomes a typed
`Proposal` with a deterministic ULID id, `accepted` state when `auto_applicable`, and only real
event-id ULIDs in provenance; a payload-free one, a kind disagreement, an invalid payload and an id
collision each come back untranslatable with their distinct reason.
**Prompt**: `tasks/WP02-generator-proposal-translation.md`
**Requirement Refs**: FR-002, FR-003, FR-004, NFR-002, NFR-003, C-002

### Included Subtasks

T001 Write the failing translation tests in `tests/retrospective/test_generator_proposals.py` (T1–T6 rule table from `plan.md`)
T002 Implement `translate_generator_proposals()` with the `UntranslatableProposal` / `GeneratorProposalTranslation` result types
T003 Implement the deterministic ULID id derivation plus the collision refusal, and the evidence-ULID mining
T004 Prove determinism: two calls on the same record yield identical ids and identical ordering
T005 Run the new test module, `ruff` and `mypy`

### Implementation Notes

- The function is pure: no I/O, no repo access, no clock. `actor` is passed in.
- `Proposal.rationale` is capped at 2,000 characters; truncate, never raise, and say so in the
  docstring.
- `ProposalProvenance.source_mission_id` must be a ULID; a generator record whose `mission_id` is
  not a ULID cannot be translated — return it untranslatable rather than guessing.
- Only ULIDs mined from the referenced evidence `range` values are carried; when none resolve,
  pass an empty list (no staleness claim), never a synthesized event id.
- Keep `flag_not_helpful` in mind: `apply_proposals` auto-includes it, so a `pending`
  `flag_not_helpful` translated proposal is still applied — do not special-case it here.

### Parallel Opportunities

- T003 (id derivation) and T002 (mapping) can be written together but land as one commit.

### Dependencies

- Depends on WP01 (the record must carry a `payload` to translate).

### Risks & Mitigations

- Invented ids that collide across a record → collision is refused, and the derivation is tested for
  distinctness on a multi-proposal fixture.
- A translated proposal that `apply_proposals` rejects as stale → evidence is limited to real ULIDs,
  and an empty evidence list is a legal "no claim" shape.

---

## Work Package WP03: synthesize plans them, and says what it could not plan (Priority: P1)

**Goal**: `agent retrospect synthesize` plans and applies translated proposals from a
generator-shape record, and a generator-shape record that plans nothing produces a named
diagnostic instead of a silent empty batch. `retrospect create` stops promising a synthesis it
cannot feed.
**Independent Test**: Three real-CLI reproductions — (a) a payload-bearing generator record yields
`planned ≥ 1` and `--apply` writes the target; (b) a findings-bearing, proposal-free record carries
`diagnostics` naming the shape and counts at exit 0 and prints a warning; (c) `create` on such a
record says synthesize cannot plan from it and names #3947.
**Prompt**: `tasks/WP03-cli-translation-and-diagnostics.md`
**Requirement Refs**: FR-002, FR-004, FR-005, FR-006, FR-007, SC-001, SC-002, SC-003, SC-004, SC-005, C-003

### Included Subtasks

T001 Write the red-first CLI tests in `tests/cli/test_agent_retrospect_synthesize.py` (payload proposal planned/applied; empty batch diagnosed; untranslatable named) and prove all three fail today
T002 Wire the translation into `synthesize_cmd`: typed proposals feed `apply_proposals` exactly as nested-schema proposals do
T003 Add the top-level `diagnostics` block to the JSON envelope and the matching Rich warning, from one shared helper
T004 Keep `--proposal-id` truthful: `accepted`/`pending`/untranslatable/unknown statuses with the remedy named
T005 Make `retrospect create`'s `next_step` honest for a findings-bearing, proposal-free record (panel and JSON), and pin the unchanged text for a record that carries proposals
T006 Add the round-trip conformance test (`create` on a fixture mission with findings → `synthesize`) that also guards the #1239/#3533 reader class
T007 Run the targeted CLI suites, `ruff` and `mypy`

### Implementation Notes

- Do not change exit codes: a valid dry-run stays exit 0 (FR-007, C-003), even when the batch is
  empty. The signal is the diagnostic.
- Existing tests assert `apply_mock.call_args.kwargs["proposals"] == []` on the generator fixture;
  those assertions must flip for a payload-bearing fixture and stay for a payload-free one. Do not
  delete the payload-free coverage.
- `result` inside the envelope is `SynthesisResult.model_dump()`; the diagnostics block goes next to
  `status`/`outcome`, not inside `result` (NFR-002: `charter_pack_synthesizer` is untouched).
- The Rich and JSON surfaces read one helper so they cannot disagree.
- `--fabricate-empty` records have `ran_no_findings` and no proposals: the diagnostic must describe
  them accurately, not as a broken conversion.

### Parallel Opportunities

- T002/T003 and T005 touch different command modules and can be worked in parallel by two agents.

### Dependencies

- Depends on WP01 and WP02.

### Risks & Mitigations

- Envelope drift for nested-schema records → a test pins the nested envelope's keys unchanged.
- Diagnostics noise on a genuinely empty record → distinct wording for `ran_no_findings`.

---

## Work Package WP04: Contract, docs and changelog (Priority: P2)

**Goal**: The generator-record contract, the reference, the how-to and the changelog state the seam
and the still-open generation half.
**Independent Test**: `docs/api/retrospective-schema.md` documents the `payload` seam, the
`diagnostics` block and the unchanged exit codes; the how-to says what `create` → `synthesize` can
and cannot do today; `CHANGELOG.md` has one `[Unreleased]` entry with `(#6385)`; the contract JSON
carries the optional `payload`; `check_docs_freshness --ci` reports errors=0.
**Prompt**: `tasks/WP04-docs-contract-changelog.md`
**Requirement Refs**: FR-006, SC-004, C-001

### Included Subtasks

T001 Add the optional `payload` property to the generator proposal in `kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json`
T002 Document the generator-shape record, the `payload` seam, the `diagnostics` block and the unchanged exit codes in `docs/api/retrospective-schema.md`
T003 Update the create → synthesize loop section of `docs/guides/how-to/governance/use-retrospective-learning.md`
T004 Add the `[Unreleased]` changelog entry (impact-first lead, `(#6385)`, before/after, under 1,200 characters)
T005 Verify docs freshness (`check_docs_freshness --ci`, errors=0) and `tests/architectural/test_no_legacy_terminology.py`

### Implementation Notes

- Root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the file, never replace
  the symlink.
- Say plainly that `create` writes `proposals: []` today and that generating payloads is #3947 —
  the issue's own acceptable resolution includes the docs saying so.
- Shared machine state: do not rebuild the whole `docs/api/cli-commands.md` reference.

### Parallel Opportunities

- T002 and T003 are separate pages; T004 can be drafted alongside.

### Dependencies

- Depends on WP01, WP02, WP03 (the docs must describe shipped behaviour).

### Risks & Mitigations

- Docs index drift → `check_docs_freshness --ci` and the terminology test are the gate.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02 → WP03 → WP04.
- **Parallelization**: none across WPs (each builds on the previous); within a WP, the marked subtasks.
- **MVP Scope**: WP01 + WP02 + WP03 (WP04 documents the shipped change).

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02, WP03 |
| FR-003 | WP02 |
| FR-004 | WP02, WP03 |
| FR-005 | WP03 |
| FR-006 | WP03, WP04 |
| FR-007 | WP03 |
| NFR-001 | WP01 |
| NFR-002 | WP02, WP03 |
| NFR-003 | WP01, WP02 |
| C-001 | WP04 |
| C-002 | WP01, WP02 |
| C-003 | WP03 |
| SC-001 | WP03 |
| SC-002 | WP03 |
| SC-003 | WP03 |
| SC-004 | WP03, WP04 |
| SC-005 | WP03 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first payload round-trip test | WP01 | P1 | No |
| T002 | `GenProposal.payload` + union validation | WP01 | P1 | No |
| T003 | Reader/writer carry the payload, only when present | WP01 | P1 | No |
| T004 | Named failures for bad payloads | WP01 | P1 | Yes |
| T005 | Targeted suites, ruff, mypy | WP01 | P1 | No |
| T001 | Failing translation tests (T1–T6) | WP02 | P1 | No |
| T002 | `translate_generator_proposals()` | WP02 | P1 | No |
| T003 | Deterministic id derivation, collision, evidence mining | WP02 | P1 | No |
| T004 | Determinism test | WP02 | P1 | Yes |
| T005 | Module tests, ruff, mypy | WP02 | P1 | No |
| T001 | Red-first CLI reproductions (planned / diagnosed / named) | WP03 | P1 | No |
| T002 | Wire translation into `synthesize_cmd` | WP03 | P1 | Yes |
| T003 | `diagnostics` block + Rich warning from one helper | WP03 | P1 | Yes |
| T004 | Truthful `--proposal-id` statuses | WP03 | P1 | No |
| T005 | Honest `create` next step | WP03 | P2 | Yes |
| T006 | Round-trip conformance test | WP03 | P1 | No |
| T007 | Targeted CLI suites, ruff, mypy | WP03 | P1 | No |
| T001 | Contract JSON `payload` property | WP04 | P2 | Yes |
| T002 | Schema reference: generator shape + diagnostics + exit codes | WP04 | P2 | Yes |
| T003 | How-to: the create → synthesize loop | WP04 | P2 | Yes |
| T004 | Changelog `[Unreleased]` entry | WP04 | P2 | Yes |
| T005 | Docs freshness + terminology checks | WP04 | P2 | No |
