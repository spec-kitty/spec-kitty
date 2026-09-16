# Mission Comparison Matrix

Side-by-side comparison of the 4 built-in Spec Kitty missions.

## Overview

| | software-dev | research | plan | documentation |
|---|---|---|---|---|
| **Domain** | software | research | planning | documentation |
| **Steps** | 7 (DAG) | 6 (DAG) | 4 (linear) | 7 (DAG; 6 workflow phases) |
| **Has WP iteration** | Yes (implement, review) | No | No | No |
| **Has loops** | No | No (gathering is iterative; the DAG is linear) | No | No |
| **Default** | Yes | No | No | No |

## Required Artifacts

| Artifact | software-dev | research | plan | documentation |
|---|:---:|:---:|:---:|:---:|
| `spec.md` | Required | Required | Required | Required |
| `plan.md` | Required | Required | Required | Required |
| `tasks.md` | Required | Required | Required | Required |
| `findings.md` | — | Required | — | — |
| `gap-analysis.md` | — | — | — | Required |
| `data-model.md` | Optional | — | — | — |
| `quickstart.md` | Optional | — | — | Optional |

## Step Sequences

### software-dev
```
discovery → specify → plan → tasks → implement → review → accept
```

### research
```
scoping → methodology → gathering → synthesis → output → accept
```
Note: source gathering is iterative — sources are registered as found until
the evidence base is sufficient for synthesis.

### plan
```
specify → research → plan → review
```

### documentation
```
discover → audit → design → generate → validate → publish → accept
```

## Gating by Mission

The mission-DSL v1 guard expressions were retired with the DSL runtime
(dead-port-disposition-01M1TZVN). Gating now lives on two shared surfaces for
every mission type: step progression via the `mission-runtime.yaml` DAG
(`depends_on`), and WP lane transitions via the status model (transition
matrix, review gates, dependency gating). What differs per mission type is
the artifact expectation checked at acceptance:

### software-dev

`spec.md`, `plan.md`, `tasks.md` required; review must be approved before
acceptance; validation checks `git_clean`, `all_tests_pass`,
`kanban_complete`, `no_clarification_markers`.

### research

`spec.md`, `plan.md`, `tasks.md`, `findings.md` required; at least 3 sources
documented before synthesis; publication approved at acceptance.

### plan

`goals.md`, `plan.md` required (optional `research.md`); plan approval gates
acceptance.

### documentation

Validation checks run during acceptance: `all_divio_types_valid`,
`no_conflicting_generators`, `templates_populated`, `gap_analysis_complete`.

## Agent Context

| Mission | Personality |
|---|---|
| software-dev | TDD practices, library-first architecture, tests before code |
| research | Research integrity, methodological rigor, evidence documentation |
| plan | (No explicit agent context) |
| documentation | (No explicit agent context) |

## Recommended Tools

| Mission | Required | Recommended |
|---|---|---|
| software-dev | filesystem, git | code-search, test-runner, docker |
| research | filesystem, git | web-search, pdf-reader, citation-manager, arxiv-search |
| plan | (not specified) | (not specified) |
| documentation | (not specified) | (not specified) |

## When to Choose Each Mission

| Scenario | Mission |
|---|---|
| Build a new feature with code changes | software-dev |
| Fix a bug or refactor existing code | software-dev |
| Evaluate technology options before deciding | research |
| Conduct a literature review or competitive analysis | research |
| Plan a project roadmap or architecture | plan |
| Design a system without implementing it yet | plan |
| Write tutorials, API docs, or how-to guides | documentation |
| Fill gaps in existing documentation | documentation |
| Document a specific feature or component | documentation |
