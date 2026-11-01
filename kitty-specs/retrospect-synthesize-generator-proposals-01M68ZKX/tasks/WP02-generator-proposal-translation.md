---
work_package_id: WP02
title: Translation from generator shape to typed proposals
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- NFR-002
- NFR-003
- C-002
planning_base_branch: issue-6385-retrospect-synthesize-generator-proposals
merge_target_branch: issue-6385-retrospect-synthesize-generator-proposals
branch_strategy: Planning artifacts for this mission were generated on issue-6385-retrospect-synthesize-generator-proposals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6385-retrospect-synthesize-generator-proposals unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retrospect-synthesize-generator-proposals-01M68ZKX
base_commit: 83b0474355ed5b99cd21d5691f3d89565d378cc4
created_at: '2026-10-31T13:12:52.405023+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 2 - Translation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/retrospective/
create_intent:
- src/specify_cli/retrospective/generator_proposals.py
- tests/retrospective/test_generator_proposals.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/retrospective/generator_proposals.py
- tests/retrospective/test_generator_proposals.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6385'
---

# Work Package Prompt: WP02 – Translation from generator shape to typed proposals

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro` · **Role**: `implementer`

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement
```

---

## Context

WP01 gave `GenProposal` an optional `payload`. This WP turns a payload-bearing generator-shape
proposal into the typed `Proposal` that `apply_proposals` already knows how to plan and apply
(`src/specify_cli/charter_pack_synthesizer/apply.py`), and returns every proposal it cannot
translate with a named reason — nothing is ever silently dropped.

The design decisions are already made in
`kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/plan.md` under
"Translation contract". Implement them; do not redesign them, and do not add verb parsing of
`suggested_action` (the issue calls that fragile).

Read first:

- `src/specify_cli/retrospective/schema.py` — `Proposal`, `ProposalPayload`, `ProposalState`,
  `ProposalProvenance`, `ActorRef`, `ProposalId` (ULID pattern), `GenProposal`,
  `GenRetrospectiveRecord`, `GenEvidenceRef`.
- `src/specify_cli/charter_pack_synthesizer/apply.py` — `apply_proposals` (what it needs from a
  `Proposal`: `id`, `kind`, `payload`, `state.status`, `provenance.source_evidence_event_ids`).
- `src/specify_cli/retrospective/reader.py` — `read_gen_record`, `_gen_record_from_mapping`.

## Objectives

Create `src/specify_cli/retrospective/generator_proposals.py` exporting:

```python
@dataclass(frozen=True)
class UntranslatableProposal:
    proposal_id: str
    reason: str

@dataclass(frozen=True)
class GeneratorProposalTranslation:
    proposals: list[Proposal]
    untranslatable: list[UntranslatableProposal]
    translated_ids: dict[str, str]   # generator id -> typed proposal id

def translate_generator_proposals(
    record: GenRetrospectiveRecord, *, actor: ActorRef
) -> GeneratorProposalTranslation: ...
```

Rules (each one is a test):

| Rule | Input | Outcome |
|---|---|---|
| T1 | no `payload` | untranslatable, reason names the missing structured payload and points at #3947 |
| T2 | `payload` fails `ProposalPayload` validation | untranslatable, reason carries the first validation error line |
| T3 | `payload.kind` disagrees with the typed verb of `suggested_action` (when that verb is one of the nine kinds) | untranslatable, names both |
| T4 | valid payload | typed `Proposal`: `kind = payload.kind`, `rationale = summary` truncated to 2,000 chars, `state` = `accepted` iff `auto_applicable` else `pending`, provenance = record `mission_id` + evidence event-id ULIDs + `authored_by = actor` |
| T5 | two proposals derive the same typed id | the later one is untranslatable, "id collision with <generator id>"; never merged |
| T6 | no resolvable evidence ULIDs | `source_evidence_event_ids = []` (no staleness claim); never invent an event id from a finding id |

**Id derivation** (`ProposalId` must match the ULID pattern; `GenProposal.id` is `p-001`): take the
record's `mission_id` and replace its last three characters with the first three characters of the
Crockford-base32 encoding of `sha256(gen_proposal_id)`. Deterministic, stable across runs, distinct
per generator id, and never fabricated from the clock.

A record whose `mission_id` is not a ULID cannot produce legal proposal ids: return every proposal
untranslatable with that reason instead of guessing.

## Subtasks

- **T001** — Write `tests/retrospective/test_generator_proposals.py` first, covering T1–T6 plus the
  determinism case; run it red.
- **T002** — Implement the mapping and the two result types.
- **T003** — Implement the id derivation, the collision refusal and the evidence-ULID mining. Mine
  only from evidence refs the proposal itself cites, and only values that match the ULID pattern
  (`range` may hold `first..last`).
- **T004** — Determinism test: two calls on the same record yield identical ids, identical ordering
  and equal `translated_ids`.
- **T005** — `uv run pytest tests/retrospective/test_generator_proposals.py -q`, `ruff`, `mypy`.

## Hard rules

- The function is **pure**: no filesystem, no repo root, no clock, no logging side effects.
- **No new apply path** (NFR-002): the output type is the existing `Proposal`; do not modify
  `charter_pack_synthesizer`.
- `flag_not_helpful` needs no special case here — `apply_proposals` auto-includes it regardless of
  state.
- Fail closed: any surprise in the payload becomes an `UntranslatableProposal`, never an exception.

## Test strategy

- Unit tests on the pure function, with a fixture builder that writes a `GenRetrospectiveRecord`
  directly (no CLI). CLI-level behaviour is WP03's.
- Positive control: every untranslatable case ships with a translatable proposal in the same
  record, so "untranslatable" cannot pass because the probe is blind.
- Assert observable outcomes (ids, kinds, states, reasons), not internal call shapes.

## Definition of Done

- New module + tests green; red-first output captured.
- Two runs produce identical ids (determinism test).
- `ruff` and `mypy` clean.

## Branch strategy

Same planning branch and merge target as WP01; execution worktrees come from `lanes.json`.

## Reviewer guidance

- Is the payload validated by the existing union rather than a re-implementation?
- Could a translated id collide, or change between runs?
- Is any event id invented? An empty evidence list is legal; a fabricated ULID is not.
- Was `generator.py` or `charter_pack_synthesizer` touched? Neither may be.
