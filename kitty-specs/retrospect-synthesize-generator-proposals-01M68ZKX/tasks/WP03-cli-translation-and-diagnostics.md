---
work_package_id: WP03
title: synthesize plans them, and says what it could not plan
dependencies:
- WP01
- WP02
requirement_refs:
- FR-002
- FR-004
- FR-005
- FR-006
- FR-007
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
- C-003
planning_base_branch: issue-6385-retrospect-synthesize-generator-proposals
merge_target_branch: issue-6385-retrospect-synthesize-generator-proposals
branch_strategy: Planning artifacts for this mission were generated on issue-6385-retrospect-synthesize-generator-proposals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6385-retrospect-synthesize-generator-proposals unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retrospect-synthesize-generator-proposals-01M68ZKX
base_commit: 088fc38a4ffa64b1b96d66fc211e7b57a3aa200c
created_at: '2026-10-31T13:43:03.809446+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 3 - CLI surface
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent_retrospect.py
- src/specify_cli/cli/commands/retrospect.py
- tests/cli/test_agent_retrospect_synthesize.py
- tests/cli/commands/test_retrospect.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6385'
---

# Work Package Prompt: WP03 – synthesize plans them, and says what it could not plan

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro` · **Role**: `implementer`

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement
```

---

## Context

This is the WP that closes issue #6385 for an operator. Two behaviours change and one does not:

1. `agent retrospect synthesize` on a generator-shape record **plans and applies** the proposals
   WP02 translated, exactly like nested-schema proposals.
2. A generator-shape record that plans nothing — or that carries proposals it cannot translate —
   **says so**, by name, in both the JSON envelope and the Rich output. Today it prints
   `planned: [] applied: [] conflicts: []` and exits 0 with no explanation.
3. `retrospect create`'s `next_step` stops telling the operator to "review proposals" on a record
   that has none.

Exit codes do not change: a valid dry-run stays exit 0 (FR-007, C-003, and the table in
`docs/api/retrospective-schema.md`).

Read first:

- `src/specify_cli/cli/commands/agent_retrospect.py` — `synthesize_cmd`, the
  `except (YAMLParseError, SchemaError)` generator-shape fallback, `_build_json_envelope`,
  `_refuse_proposal_ids_on_generator_record`, `_create_empty_retrospective_record`.
- `src/specify_cli/cli/commands/retrospect.py` — `create_cmd`'s `counts` / `next_step` block.
- `src/specify_cli/retrospective/generator_proposals.py` (WP02).
- `tests/cli/test_agent_retrospect_synthesize.py` — `_write_generator_retrospective()` and the two
  tests that pin today's empty batch (`test_generator_record_dryrun_exit0`,
  `test_generator_record_apply_exit0`).

## Objectives

**Translation wiring (T002).** On the generator-shape fallback path, replace
`all_proposals = []` with the translated proposals. `apply_proposals` is called unchanged: same
parameters, same dry-run default, same conflict/staleness semantics. `_fabricated_empty` keeps
`all_proposals = []` (that record genuinely has none).

**Diagnostics (T003).** One helper builds a dict from the translation plus the `SynthesisResult`
and feeds both the JSON envelope and the Rich renderer:

```json
"diagnostics": {
  "record_schema": "generator",
  "findings": {"helped": 0, "not_helpful": 19, "gaps": 2, "proposals": 0},
  "proposals_translated": 0,
  "proposals_planned": 0,
  "untranslatable": [{"proposal_id": "p-001", "reason": "no structured payload …"}],
  "next_action": "…"
}
```

- Top level, sibling to `status`/`outcome` — not inside `result` (that dict is
  `SynthesisResult.model_dump()`, owned by `charter_pack_synthesizer`, which this Mission must not
  touch).
- Emitted **only** when the generator-shape fallback ran, so nested-schema envelopes are unchanged.
- Rich prints a `[yellow]Warning:[/yellow]` block when anything is untranslatable **or** nothing was
  planned; it must name the finding counts and the next step.
- A `ran_no_findings` record (including `--fabricate-empty`) is described as an empty record, not as
  a broken conversion.

**`--proposal-id` truth (T004).** Statuses become: `accepted` (selectable), `pending` (refused, with
the remedy), `unsupported_generator_proposal` (untranslatable, with WP02's reason),
`unknown` (not in the record). `_refuse_proposal_ids_on_generator_record` must stop claiming that
proposal application is entirely unsupported.

**`create` next step (T005).** When the persisted record has zero proposals and at least one
finding, say that synthesize cannot plan proposals from a generated record yet, name #3947, and say
a proposal needs a `payload` block. Rendered in the panel and in the JSON `next_step`. A record with
proposals keeps today's text.

**Round-trip conformance (T006).** One end-to-end test, as the issue asks: `retrospect create` on a
fixture mission with findings → `synthesize` → the run is either non-empty or explicitly diagnosed.
This also guards the #1239/#3533 reader disagreement (a created record must never be reported as a
Pydantic schema failure).

## Subtasks

- **T001** — Write the three red CLI tests first and prove they fail on the unfixed code. Capture
  the failure output for the PR body.
- **T002** — Wire the translation into `synthesize_cmd`.
- **T003** — Add the diagnostics helper, the envelope block and the Rich warning.
- **T004** — Update the `--proposal-id` refusal statuses and message.
- **T005** — Make `create`'s next step honest; pin the unchanged text for a proposal-bearing record.
- **T006** — Add the round-trip conformance test.
- **T007** — `uv run pytest tests/cli/test_agent_retrospect_synthesize.py tests/cli/commands/test_retrospect.py -q`,
  `ruff`, `mypy`.

## Hard rules

- **Never change an exit code.** No new non-zero path for a valid record. The empty batch is a
  diagnostic, not a failure.
- **Do not delete today's payload-free coverage.** The existing generator fixtures pin that a record
  with no proposals still plans nothing; keep a payload-free fixture test and flip only the
  payload-bearing one.
- Do not change `charter_pack_synthesizer` (NFR-002) or `retrospective/generator.py` (C-001).
- `--json` must not print extra prose to stdout; the envelope carries the diagnostics.
- Do not weaken or skip any existing test to get the suite green.

## Test strategy

- Real CLI through `typer.testing.CliRunner` against the agent app (that is how the file already
  works), and for the round-trip an actual `retrospect create` on a fixture mission.
- Positive control: the translatable proposal in the same fixture must reach `planned`, so the
  "untranslatable is named" assertion cannot pass on a record where nothing translates.
- `--apply` test asserts the written file (e.g. the glossary term), not just a non-empty
  `applied` list.

## Definition of Done

- The three reproductions are green and were red before the fix.
- Nested-schema envelope keys unchanged (explicit assertion).
- Exit-code table still true: valid dry-run exits 0, including an empty batch.
- Targeted suites, `ruff`, `mypy` clean.

## Branch strategy

Same planning branch and merge target as WP01/WP02; execution worktrees come from `lanes.json`.

## Reviewer guidance

- Does the diagnostics block appear only for generator-shape records?
- Can an operator with 19 findings and 0 proposals still see a bare empty batch? They must not.
- Are the exit codes untouched?
- Is `--proposal-id` still narrowing-only rather than a new approval power?
