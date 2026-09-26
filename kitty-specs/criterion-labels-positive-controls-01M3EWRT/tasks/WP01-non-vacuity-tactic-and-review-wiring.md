---
work_package_id: WP01
title: Canonical non-vacuity tactic, DRG wiring, review prompt
dependencies: []
requirement_refs:
- C-001
- C-002
- C-005
- C-006
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-002
- NFR-003
planning_base_branch: claude/research-squad-remediation-mission-fvdk93
merge_target_branch: claude/research-squad-remediation-mission-fvdk93
branch_strategy: Planning artifacts for this mission were generated on claude/research-squad-remediation-mission-fvdk93. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/research-squad-remediation-mission-fvdk93 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-criterion-labels-positive-controls-01M3EWRT
base_commit: cb9d9f51595cab9e231d64d65c8e0238ee3d43f7
created_at: '2026-09-26T13:14:40.524337+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Doctrine
history:
- at: '2026-09-26T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: packs/built-in/tactics/testing/
create_intent:
- packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml
- tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml
- packs/built-in/tactics/testing/acceptance-test-first.tactic.yaml
- packs/built-in/tactics/testing/atdd-adversarial-acceptance.tactic.yaml
- packs/built-in/missions/software-dev/actions/review/index.yaml
- packs/built-in/missions/mission-steps/software-dev/review/prompt.md
- packs/built-in/*.graph.yaml
- packs/built-in/pack-manifest.yaml
- tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
- tests/doctrine/drg/test_reachability.py
- tests/doctrine/missions/test_action_indexes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Canonical non-vacuity tactic, DRG wiring, review prompt

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to
its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

- One new built-in tactic `acceptance-criteria-non-vacuity` is the **single canonical definition** (spec C-006) of:
  the delivery labels `[build]` / `[ratchet]` / `[folded]`, the *no-op passable?* mark, and the three review rules
  (same-fixture positive control; half-by-half proof of compound fixes; production-path non-vacuity). (FR-005)
- The regenerated DRG has a **direct `scope` edge** `action:software-dev/review → tactic:acceptance-criteria-non-vacuity`,
  present at `resolve_context(..., depth=1)`. (FR-006)
- The built-in review prompt carries a `### 4b. Criterion Non-Vacuity Check` naming the id and the fetch command,
  and the named id resolves through `spec-kitty charter context --include tactic:<id>`. (FR-007)
- `acceptance-test-first` and `atdd-adversarial-acceptance` reference the new tactic from the step where acceptance /
  refusal assertions are written, **without copying its content**. (FR-008)

## Context & Constraints

- Read: `kitty-specs/criterion-labels-positive-controls-01M3EWRT/{spec.md,plan.md,research.md,research/*.md}`.
- Pack tier: `packs/built-in` (C-001). Labels are guidance only — no gate (C-002).
- Tactic schema: `src/charter/offering/schemas/tactic.schema.yaml` (`additionalProperties: false`) — only `id`,
  `schema_version`, `name`, `purpose`, `steps[{title, description, examples, references}]`, `failure_modes`,
  `references`, `notes`, `applies_to_languages`. Check the schema file itself before writing.
- Model the wiring test on `tests/doctrine/test_supply_chain_security_layer.py` (direct scope edge + depth-1/2 stability).
- Model the prompt section on the supply-chain §3a in `packs/built-in/missions/mission-steps/software-dev/review/prompt.md` (~line 175).
- Do **not** edit `.kittify/overrides/**` (WP03 owns that) or generated agent copies.
- Terminology: "Mission", never "feature", in all new prose.

## Branch Strategy

- **Planning base branch**: `claude/research-squad-remediation-mission-fvdk93`
- **Merge target branch**: `claude/research-squad-remediation-mission-fvdk93`
- Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP01 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first wiring test

- **Purpose**: the acceptance contract for FR-005..FR-008, written first; it must fail before T002.
- **File**: `tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py` (new). Markers like the supply-chain test
  (`fast`, `doctrine`, `corpus`).
- **Tests**:
  1. Tactic loads and validates against the schema (use the same loader/validator `tests/doctrine/test_artifact_compliance.py` uses).
  2. Tactic content carries each rule — assert on distinctive, semantically-load-bearing phrases (e.g. "same fixture",
     "half", "production"), and that `notes` define all three labels plus the no-op mark.
  3. Direct `SCOPE` edge from `action:software-dev/review` and presence in `resolve_context` at depth 1 and 2.
     **Positive control on the same graph fixture**: assert an unrelated action (e.g. `action:software-dev/specify`)
     does **not** have a direct scope edge to it — proves the edge check is not vacuously true.
  4. Render the **built-in** review prompt (`render_command_template(<packs/built-in/.../review/prompt.md>, "sh",
     "claude", "$ARGUMENTS", "md")` — see `tests/specify_cli/regression/test_twelve_agent_parity.py` for the call shape)
     and assert it names `acceptance-criteria-non-vacuity` **and** the fetch command; then assert the named id resolves
     via the charter context include path (call the same function `spec-kitty charter context --include tactic:<id>`
     uses, or invoke the CLI through `typer.testing.CliRunner`). Resolution-by-id is what makes this non-vacuous.
  5. Sibling references: both sibling tactics have a step-level `references` entry with `id: acceptance-criteria-non-vacuity`,
     and neither contains the rule text itself (guard against duplication, C-006).
- **Validation**: run it; record the RED output in the Activity Log.

### Subtask T002 – Author the tactic

- **File**: `packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml`.
- **Shape** (adapt wording, keep schema-valid):
  - `name`: "Acceptance Criteria Non-Vacuity"; `purpose`: prove each acceptance criterion and its test could fail — a
    criterion a no-op satisfies, or a probe that cannot see what it asserts absent, proves nothing.
  - `steps`:
    1. *Label every criterion* — `[build]` / `[ratchet]` / `[folded]` (folded names the satisfying item).
    2. *Ask "no-op passable?"* — `yes` ⇒ reword, or name a positive control.
    3. *Pair refusal/absence assertions with a positive control on the same fixture* — the control proves the probe
       can observe the thing (example: a parser test asserting a mis-placed id is not declared also asserts a correctly
       placed id in the same text is declared).
    4. *Prove compound fixes half by half* — revert each independent part in turn; a test must go red each time
       (references `mutation-testing-workflow`).
    5. *Exercise the production path* — non-vacuity tests call the production entry point, not only a helper.
  - `failure_modes`: blind probe; half-fix still green; helper-only non-vacuity; label placed in the requirement-id cell
    (silently undeclares the requirement).
  - `notes`: the canonical legend (the only place the labels are defined).
  - `references`: `architectural-gate-non-vacuity` (gate-level sibling), `mutation-testing-workflow`,
    `delete-the-assertion-not-the-test`, `acceptance-test-first`.

### Subtask T003 – Sibling step references [P]

- `acceptance-test-first`: on step "Define acceptance behavior first" add a step `references` entry to the new tactic
  (`when:` "Label the criterion and confirm a no-op cannot pass it").
- `atdd-adversarial-acceptance`: on step "Convert to acceptance scenarios" add one sentence + a step reference
  (`when:` "Pair each refusal / state-unchanged assertion with a same-fixture positive control"). No rule text copies.

### Subtask T004 – Review action scope

- Add `acceptance-criteria-non-vacuity` to `tactics:` in `packs/built-in/missions/software-dev/actions/review/index.yaml`.
- If `tests/doctrine/missions/test_action_indexes.py` pins the raw list, extend it.

### Subtask T005 – Review prompt §4b [P]

- After §4a (anti-pattern checklist) and before "Bulk Edit Compliance", add `### 4b. Criterion Non-Vacuity Check`:
  load via `spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity`; three PASS / FAIL / N/A
  items (same-fixture positive control; half-by-half for compound fixes; production path, not helper-only); plus
  "every FR row marked no-op passable `yes` names a control that exists in the diff".
- Keep outside the SPDD REASONS markers (`tests/architectural/test_lifted_reviews.py` byte-checks those).

### Subtask T006 – Regenerate and adjudicate

- `spec-kitty doctrine regenerate-graph`, then `spec-kitty doctrine regenerate-graph --check`.
- `git diff packs/built-in/action.graph.yaml`: the calibrator derives review edges from implement's until review reaches
  ~80%; an explicit entry may drop one derived edge. If an existing review edge disappeared, record it in the Activity
  Log and re-pin `tests/doctrine/drg/test_reachability.py` only for that intended move.

## Test Strategy

```bash
source .venv/bin/activate
pytest tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py -q
pytest tests/doctrine tests/charter -q -n auto --dist loadfile
pytest tests/architectural/test_doctrine_regenerate_graph_roundtrip.py tests/architectural/test_pack_manifest_no_author_edit.py tests/architectural/test_lifted_reviews.py tests/architectural/test_no_legacy_terminology.py -q
ruff check tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py && ruff format --check tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
mypy tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
```

## Definition of Done

- T001 test red before T002, green after; all commands above green; regen `--check` fresh.
- No rule text outside the new tactic (siblings/prompt only point to it).

## Risks & Mitigations

- Calibrator drift → T006 adjudication. Schema rejection → read the schema first.
- Prompt-render test reading the override → render the built-in path explicitly.

## Review Guidance

- Apply the new tactic to this WP itself: does each test have a same-fixture positive control? Would deleting the
  tactic, the scope entry, or the prompt section each turn a test red (half-by-half)?

## Activity Log
