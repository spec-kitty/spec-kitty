# Data Model: plan artifact-vocabulary reconciliation

No new persisted entities. The change edits one pack manifest's keys/paths + comments and two
descriptive mission.yaml copies.

## expected-artifacts.yaml (plan family) — before → after
| step key (before) | artifact (before) | step key (after) | artifact (after) |
|-------------------|-------------------|------------------|------------------|
| goals             | goals.md          | **specify**      | **spec.md**      |
| research          | research.md       | research         | research.md      |
| structure         | [] (none)         | structure (drop/keep harmless) | [] |
| draft             | plan.md           | **plan**         | plan.md          |
| review            | [] (gate)         | review           | [] (gate)        |
| done              | [] (terminal)     | done (drop/keep harmless) | []      |

- `_presence_filenames_for('plan')`: `{goals.md,research.md,plan.md}` → `{spec.md,research.md,plan.md}`.
- `required_artifacts_for('specify','plan')`: `[]` → `{spec.md}`; `('plan','plan')`: `[]` → `{plan.md}`.
- Schema unchanged (`extra="forbid"`, `schema_version`, `manifest_version` preserved).

## Invariant (target)
For every built-in mission type: the manifest `required_by_step` keys ⊆ the runtime step-contract
action ids, and each action's guard-checked artifact ∈ `_presence_filenames_for(type)`.

## Guard (unchanged)
`_evaluate_plan_guards`: specify→spec.md, research→research.md, plan→plan.md, review→[]. Not edited.
