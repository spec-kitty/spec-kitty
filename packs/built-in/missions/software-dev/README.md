# Software Development Mission

The primary mission type for structured software delivery. It runs an eight-step
workflow from discovery through review to acceptance.

## Runtime step order

```
discovery → specify → plan → tasks → analyze → implement → review → accept
                                                  ↑           |
                                                  └───────────┘ (rework)
```

Each transition is guarded — an artifact-presence check (for example
`artifact_exists("spec.md")`), a work-package status check, or, for `analyze`,
an analysis-currency check. `implement` and `review` iterate per work package;
a rejected review sends the work package back to `implement`.

`analyze` is the required analysis gate between `tasks` and `implement`: it
records a cross-artifact analysis report, and `implement` refuses to claim a
work package until a current analysis report exists. `analyze` stays off the
action sequence (it has no action index), so a run frozen before the step was
added keeps its recorded order.

## Steps

| Step | Purpose |
|------|---------|
| `discovery` | Research technologies and best practices |
| `specify` | Define user scenarios and acceptance criteria |
| `plan` | Design the technical architecture |
| `tasks` | Break work into finalized, dependency-ordered work packages |
| `analyze` | Cross-artifact consistency analysis, recorded as a current analysis report |
| `implement` | Execute a work package |
| `review` | Review and validate a work package |
| `accept` | Validate mission completeness before consolidation |

Agent profiles are selected per work package (in the WP prompt frontmatter),
not fixed per runtime step.

## Contents

- `mission.yaml` — State machine with guards and transitions
- `mission-runtime.yaml` — Runtime step DAG with step ordering
- `templates/` — Content scaffolds (spec, plan, tasks, task-prompt templates)

The step prompts live under `mission-steps/software-dev/<step>/prompt.md`.
