# Implementation Plan: Pre-review gate scope recovery

**Branch**: `issue-6865-pre-review-gate-scope-recovery` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/spec.md`

**Note**: This plan was produced by the `/spec-kitty.plan` step for an autonomous
delivery run whose user input is issue #6865 and the operator brief. The
engineering-alignment answers are recorded below instead of being asked
interactively.

## Summary

The pre-review regression gate cannot run in this repository: its chosen scope
*is* the whole declared command (`DeclaredCommandScopeSource.file_to_scope`
returns `()` by design), so the 300 s scoped default bounds a whole-suite run and
every `for_review` move is refused at the timeout; and the recovery the gate
advertises (`pre_review_test_scope` in the WP frontmatter) makes the WP
unreadable because `WPMetadata` forbids the key.

The plan closes all three legs of the issue:

1. **The recovery parses.** `WPMetadata` declares `pre_review_test_scope` — the
   field the gate already consumes — so the WP stays readable to the
   subtask-roster guard and the pinned scope reaches the head run.
2. **The budget matches the chosen scope.** The review budget gains a
   whole-command shape: a source with no per-file narrowing resolves the
   whole-command default (1,200 s) when the project declares no
   `review.test_timeout_seconds`; a narrowing source keeps the 300 s scoped
   default; a declared budget always wins. One number is resolved per
   transition, so capture, the baseline-receipt match and the head run cannot
   disagree.
3. **The refusal is actionable.** The timeout and oversize reasons name the
   scope shape the gate chose, the declared command that ran, the policy
   metadata that classifies scopes, and the recovery for that shape.

## Technical Context

**Language/Version**: Python 3.11+ (repository targets 3.11–3.13)
**Primary Dependencies**: pydantic v2 (`WPMetadata`), typer/rich (CLI), pytest 8
**Storage**: YAML config (`.kittify/config.yaml`), JSON baseline receipts
(`kitty-specs/<mission>/tasks/<wp>/baseline-tests.json`)
**Testing**: pytest, fast marker tier; targeted suites only
(`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: Linux/macOS/Windows CLI (POSIX shell for configured commands)
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: no measurable cost added to a transition; the shape probe
reuses the already-built scope-source selection once per transition
**Constraints**: no new configuration key; one budget authority; no resurrected
census derivation; no gate weakened
**Scale/Scope**: four production modules, three docs pages, one changelog
fragment, ~5 focused test additions

## Engineering Alignment (recorded answers to the planning interrogation)

| Question | Answer |
|---|---|
| What is the observable contract change? | `WPMetadata` accepts one documented optional field, and the review budget's default becomes shape-dependent. No CLI flag, no config key, no outcome vocabulary changes. |
| Which single authority owns the budget? | `review/test_timeout.py::resolve_review_test_timeout`, extended with a `whole_command` selector. Nothing else reads `review.test_timeout_seconds`. |
| How is the scope shape derived? | From the resolved `ScopeSource` capability predicate `exposes_scope_breakdown` — never from file names, timings, or a second config surface. |
| Why not re-derive test targets? | The census derivation is retired by design (`scopesource-gate-followup-01KY6S9P` FR-001); a heuristic `src/**` → `tests/**` namer would be an improvised second authority (C-001). |
| What keeps the baseline valid? | A single resolved number per transition. Capture, the receipt match and every head leg read the same memoised value, so a shape-triggered mismatch cannot silently degrade the gate to `UNVERIFIED_BASELINE`. |
| What is the whole-command default and why? | 1,200 s. Measured `make test-fast` = 215.31 s of pytest (2026-11-02) and this repository's CI bounds a whole per-PR lane at 20 minutes; 1,200 s is the same order with ≥5× headroom over the measured run and well below the 86,400 s ceiling. |
| Failure behaviour if the run still exceeds the budget? | Unchanged: `TIMED_OUT` is terminal and refuses the transition; the new reason text explains the shape and the recovery. |
| What is explicitly deferred? | Scoping the **baseline capture** leg to a pinned WP scope. Capture stays a whole-declared-command reference run; its own follow-up issue carries the receipt-comparability decision. |

## Charter Check

*GATE: must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Charter rule | Status |
|---|---|
| Single canonical authority (DIRECTIVE_044) | **Pass** — one budget resolver, one WP model, one scope-source selection; the fix extends each owner rather than adding a parallel reader. |
| Architectural alignment (DIRECTIVE_001) | **Pass** — the change stays inside `review/`, `status/wp_metadata.py` and the existing gate seam in `cli/commands/agent/`; no new module boundary. |
| ATDD-first (C-011) | **Pass** — a failing test through the pre-existing entry points (`authored_subtask_roster`, the move-task CLI, the rendered verdict) precedes each fix. |
| Terminology adherence | **Pass** — Mission, work package, lane, review budget, scope shape; no "feature". |
| Test integrity (DIRECTIVE_041) | **Pass** — each new test guards a standing invariant (readable WP model, comparable budget, actionable refusal); no test asserts implementation trivia. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | **Pass** — targeted suites only; CI owns the aggregate. |
| Pre-existing Failure Reporting Rule | **Pass** — any pre-existing red is reported, never masked. |

No violations, so **Complexity Tracking** stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 findings
├── reasons-canvas.md    # SPDD canvas
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── pre-review-gate-scope-contract.md
├── traces/              # tracer files (approach, design-decisions, tooling-friction)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── status/wp_metadata.py                     # + pre_review_test_scope field
├── review/test_timeout.py                    # + whole-command default + selector
├── review/pre_review_gate.py                 # shape-aware refusal reasons
└── cli/commands/agent/tasks_move_task_gates.py  # shape probe at the budget seam

tests/
├── specify_cli/status/test_wp_metadata.py        # model + roster-read proof
├── review/test_review_budget_scope_shape.py      # NEW: budget shape resolution
├── review/test_pre_review_gate_scope_diagnostics.py  # NEW: refusal content
└── specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py
                                                  # existing harness: pinned-scope move

docs/
├── development/how-to/review-gates.md
├── configuration/review-test-budget.md
├── api/configuration.md
└── changelog/unreleased/<pr>.fixed.md
```

**Structure Decision**: single-package layout, as the repository already uses.
The change touches four production modules, adds two focused test modules and
extends one existing test harness; it adds no package, no dependency and no
configuration key.

## Complexity Tracking

*No charter violations; nothing to justify.*

## Implementation Concern Map

### IC-01 — WP model accepts the gate-consumed scope key

- **Purpose**: make the documented per-WP `pre_review_test_scope` readable so the
  strict WP model and the subtask-roster guard stop refusing the WP.
- **Relevant requirements**: FR-001, FR-002, SC-001
- **Affected surfaces**: `src/specify_cli/status/wp_metadata.py`,
  `src/specify_cli/core/subtask_rows.py` (read-only consumer)
- **Sequencing/depends-on**: none
- **Risks**: the model must stay `extra="forbid"` for genuine typos; the field is
  additive and must not alter `model_dump` for WPs that omit it.

### IC-02 — Budget matches the scope shape

- **Purpose**: bound a whole-declared-command run with the whole-command budget
  while keeping one resolved number per transition.
- **Relevant requirements**: FR-004, FR-005, FR-008, C-003, SC-002
- **Affected surfaces**: `src/specify_cli/review/test_timeout.py`,
  `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`
- **Sequencing/depends-on**: none
- **Risks**: the receipt-budget identity (`test_timeout_seconds`) must match
  across capture and head legs; an invalid declaration must still raise; the
  shape probe must not run for a skipped gate.

### IC-03 — Actionable refusals

- **Purpose**: name the scope shape, the executed command, the policy metadata
  owner and the recovery in the timeout and oversize refusals.
- **Relevant requirements**: FR-006, FR-007, FR-009, NFR-002
- **Affected surfaces**: `src/specify_cli/review/pre_review_gate.py`, the console
  renderer in `tasks_move_task_gates.py`
- **Sequencing/depends-on**: IC-02 (the shape predicate is shared)
- **Risks**: existing rendering assertions in the observability test encode the
  old wording; they are updated as part of the change, with the paired
  whole-command/bounded assertions proving the two shapes are distinguishable.

### IC-04 — Docs, changelog and the operator path

- **Purpose**: document the field, the shape-dependent budget and the recovery so
  the next operator does not rediscover this issue.
- **Relevant requirements**: FR-006 (operator-facing half), SC-003
- **Affected surfaces**: `docs/development/how-to/review-gates.md`,
  `docs/configuration/review-test-budget.md`, `docs/api/configuration.md`,
  `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-01, IC-02, IC-03
- **Risks**: docs freshness check must stay at errors=0; the changelog is a
  per-PR fragment, never an edit to `CHANGELOG.md`.
