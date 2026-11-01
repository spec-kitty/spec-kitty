---
work_package_id: WP01
title: A generator-shape proposal can say what it applies
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- NFR-003
- C-002
planning_base_branch: issue-6385-retrospect-synthesize-generator-proposals
merge_target_branch: issue-6385-retrospect-synthesize-generator-proposals
branch_strategy: Planning artifacts for this mission were generated on issue-6385-retrospect-synthesize-generator-proposals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6385-retrospect-synthesize-generator-proposals unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retrospect-synthesize-generator-proposals-01M68ZKX
base_commit: 557fa97d5cd9f9e66ed3cea55501c3420fad197e
created_at: '2026-10-31T12:47:38.413449+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Record shape
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/retrospective/
create_intent:
- tests/retrospective/test_generator_proposal_payload.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/retrospective/schema.py
- src/specify_cli/retrospective/reader.py
- src/specify_cli/retrospective/writer.py
- tests/retrospective/test_generator_proposal_payload.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6385'
---

# Work Package Prompt: WP01 – A generator-shape proposal can say what it applies

## ⚡ Do This First: Load Agent Profile

Load the profile named in the frontmatter before reading anything else:

- **Profile**: `python-pedro`
- **Role**: `implementer`

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement
```

Behave according to the profile's guidance for the rest of this prompt.

---

## Context

`spec-kitty retrospect create` writes a **generator-shape** record (`GenRetrospectiveRecord`, a
dataclass in `src/specify_cli/retrospective/schema.py`). `spec-kitty agent retrospect synthesize`
can only apply the **nested** Pydantic `Proposal`, which carries a discriminated `payload`
(`ProposalPayload` union, same module). The generator shape has no field to say *what* a proposal
would apply, so `synthesize` can never plan one — the other half of issue #6385.

This WP adds that field and nothing else. It is the seam WP02's translation consumes.

Read first:

- `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/spec.md` — FR-001, NFR-001, NFR-003, C-002.
- `kitty-specs/retrospect-synthesize-generator-proposals-01M68ZKX/research.md` — D3 (why a structured
  field, not verb parsing), D5 (the exact modules).
- `src/specify_cli/retrospective/schema.py` — `GenProposal` (the dataclass), `ProposalPayload`
  (the discriminated union, the single payload authority), `validate_record`.
- `src/specify_cli/retrospective/reader.py` — `_PROPOSAL_KEYS` (an allow-list: today a `payload`
  key makes `read_gen_record` raise) and `_gen_record_from_mapping._proposal()`.
- `src/specify_cli/retrospective/writer.py` — `_gen_record_to_dict` / `_dict_to_gen_record`.

## Objectives

1. `GenProposal` gains an **optional** `payload: dict[str, Any] | None = None`.
2. A payload is validated against the existing `ProposalPayload` union — `TypeAdapter(ProposalPayload)`
   — so there is one payload schema, never two (C-002).
3. Read and write round-trip the field. A record **without** payloads serialises byte-identically to
   today (NFR-001).
4. A bad payload raises the module's `SchemaError` naming the problem; it never escapes as a raw
   `ValidationError` traceback (NFR-003).

## Subtasks

- **T001** — Write the red-first test mirroring the issue's own reproduction: a generator-shape
  `retrospective.yaml` whose single proposal carries a valid `add_glossary_term` payload. Assert
  `read_gen_record()` returns it. Prove it fails on the unfixed code (the allow-list rejects the
  key). Keep the failing output for the PR.
- **T002** — Add the field to `GenProposal`; validate a present payload with
  `TypeAdapter(ProposalPayload)` inside the read path so the error names the offending key.
- **T003** — Add `payload` to `_PROPOSAL_KEYS`; parse it in `_proposal()`; emit it in
  `_gen_record_to_dict` **only when not None**; accept it in `_dict_to_gen_record`.
- **T004** — Failure tests: unknown `payload.kind`, missing required payload field (e.g. a
  `synthesize_directive` without `body_hash`), non-mapping `payload`. Each must raise `SchemaError`
  with a message naming the proposal id or the key.
- **T005** — Run `uv run pytest tests/retrospective/ -q`, `uv run ruff check src/specify_cli/retrospective`,
  `uv run mypy src/specify_cli/retrospective`.

## Hard rules

- **Do not touch `generator.py`.** `create` keeps emitting `proposals: []`; generating payloads from
  findings is #3947 (C-001). A reviewer will check this.
- **Do not weaken `validate_record`.** No new invariant is required, but do not relax an existing one.
- **Byte identity is the test, not dict equality**: write a payload-free record through
  `write_gen_record()` and compare bytes with the fixture.
- No new dependency; `pydantic` v2 is already in use.

## Test strategy

- One new module `tests/retrospective/test_generator_proposal_payload.py`.
- Positive control on the same fixture family: a payload-bearing record round-trips *and* a
  payload-free record is byte-identical — so the round-trip assertion cannot pass vacuously.
- Exercise the production path (`read_gen_record` / `write_gen_record`), not the helper alone.

## Definition of Done

- `uv run pytest tests/retrospective/test_generator_proposal_payload.py -q` green, red-first proof
  captured.
- `uv run pytest tests/retrospective/ -q` green (no regression in reader/writer/generator tests).
- `ruff` and `mypy` clean on the touched module.
- Commit message references `#6385`.

## Branch strategy

Planning branch and merge target are both `issue-6385-retrospect-synthesize-generator-proposals`.
Execution worktrees are allocated per computed lane from `lanes.json`; do not hand-build a
workspace path.

## Reviewer guidance

- Is the payload validated by the *existing* union, or did the implementer add a parallel schema?
- Does the writer emit the key only when present, and is byte identity asserted?
- Is `generator.py` untouched?
