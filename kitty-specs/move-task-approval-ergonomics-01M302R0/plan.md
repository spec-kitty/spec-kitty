# Implementation Plan: move-task / approval-gate ergonomics

**Branch**: `fix/move-task-approval-ergonomics` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/move-task-approval-ergonomics-01M302R0/spec.md`

## Summary

Fix GitHub issue #3469's still-real ergonomic defects in the WP lifecycle-transition + issue-matrix
approval surface. The core work is a **single-source reference-classification seam**: extend the
issue-reference discovery surface so every discovered `#NNNN` carries a *gating classification*
(implementation-target = gating, context-only / PR-or-commit = non-gating), computed as an aggregate
over all occurrences and defaulting to **gating** (fail-safe). All three sites that today
independently compute "referenced-but-missing" (the approval blocker, `merge_gates`, `status/doctor`)
consume that one classification. Alongside, add an additive, terminal, non-gating `not-applicable`
verdict to `IssueMatrixVerdict` + the `issue-verdict` CLI + the approval-blocker terminal-verdict
logic, recorded in a lightweight ADR that also supersedes the never-implemented WP09 `not_applicable`
intent. Plus lighter ergonomics: `move-task` `--actor`/`--reason` aliases, documented evidence-token
rule, early approval-gating warning at specify/plan/tasks/analyze, inert-checkbox guidance, and the
stale `--assignee` docstring fix.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), rich (console), ruamel.yaml (frontmatter), pytest, mypy --strict
**Storage**: JSON governance artifact `issue-matrix.json` (existing; schema extended additively — no new store, no migration); event-sourced `status.events.jsonl` (untouched)
**Testing**: pytest, targeted surfaces — `tests/specify_cli/cli/commands/` (move-task, issue-verdict, review/_issue_matrix, tasks_parsing_validation), `tests/tasks/` (issue_reference_discovery, issue_matrix), `tests/policy/` (merge_gates), `tests/status/` (doctor). ATDD red-first per NFR-005.
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows 10+)
**Project Type**: single (CLI/library monorepo, `src/specify_cli/`)
**Performance Goals**: reference classification adds < 200ms to the finalize/gate path for ≤ 20 refs; CLI ops < 2s (NFR-003)
**Constraints**: additive enum only (backward-compatible, no migration — NFR-001/C-003); no re-read of `tasks.md` checkboxes (C-001/#2816); do not re-fix #4330 (C-002); single-source gating across all consumers (FR-012/NFR-006); terminology canon, no `--feature` (C-004)
**Scale/Scope**: typical mission cites ≤ 20 issues; the audit artifact must stay honest at any citation count

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Charter (`.kittify/charter/charter.md`) governs. Relevant gates for this mission:

- **Single canonical authority** (DIRECTIVE_044) — ✅ the whole design *is* unification: one shared
  gating classifier consumed by all three "referenced-but-missing" sites, replacing three forked
  computations. No second authority introduced; the ADR absorbs the stale WP09 `not_applicable`
  intent rather than creating a parallel one.
- **ATDD-first / red-first** (C-011, DIRECTIVE_041) — ✅ each defect lands an issue-pinned
  `@pytest.mark.regression` repro RED on the planning base, GREEN on the fix (NFR-005).
- **Terminology canon** — ✅ no `--feature`; new `--actor`/`--reason` aliases use canonical
  vocabulary; `--mission` remains the mission selector.
- **Architectural gate discipline** (DIRECTIVE_043) — the single-source classifier is itself a
  by-construction close of the "gating decided in N places" defect class; the cross-site consistency
  test (NFR-006) is the non-vacuous guard.
- **Decision documentation** — ✅ the verdict-vocabulary contract change gets an ADR in
  `docs/adr/3.x/` (FR-010).
- **Backward compatibility** — ✅ additive StrEnum; existing `issue-matrix.json` validates unchanged
  (verified by the post-spec review against `IssueMatrixVerdict(value)` parsing).

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/move-task-approval-ergonomics-01M302R0/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (verdict-vocabulary + classification contract)
├── spec.md              # /spec-kitty.specify output
├── tracer-*.md          # mission tracer files
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/
├── tasks/
│   ├── issue_reference_discovery.py   # discover_issue_references — EXTEND: attach classification
│   └── issue_matrix.py                # detect_issue_references, scaffold — EXTEND: classify + aggregate over occurrences; default non-gating scaffolding
├── cli/commands/
│   ├── review/_issue_matrix.py        # IssueMatrixVerdict (~L50) — ADD not-applicable; evidence-token rule (~L348)
│   └── agent/
│       ├── issue_verdict.py           # --verdict help (~L297) — ADD not-applicable + evidence-token doc
│       ├── tasks.py                   # move-task flags (~L662-691) — ADD --actor/--reason aliases; fix --assignee help (~L675)
│       ├── tasks_parsing_validation.py# approval blocker (~L283-302) — consume shared classifier; not-applicable non-gating + terminal
│       └── tasks_shared.py            # subtask completion (~L501-572) — UNTOUCHED (#2816); docs only
├── policy/
│   └── merge_gates.py                 # _evaluate_issue_matrix_completeness_gate (~L359) — consume shared classifier
└── status/
    └── doctor.py                      # issue-matrix completeness (~L389) — consume shared classifier

packs/built-in/missions/mission-steps/software-dev/{specify,plan,tasks}/prompt.md   # early-warning note (FR-007)
packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md                  # early-warning note (FR-007)

docs/adr/3.x/2026-09-20-N-issue-matrix-not-applicable-verdict.md   # NEW ADR (FR-010)
docs/changelog/CHANGELOG.md                                        # [Unreleased] entry

tests/
├── tasks/                    # classification + aggregate + default-gating unit tests
├── specify_cli/cli/commands/ # move-task aliases, issue-verdict help, approval-blocker gating, not-applicable terminal
├── policy/                   # merge_gates cross-site consistency
└── status/                   # doctor cross-site consistency
```

**Structure Decision**: single-project CLI. The load-bearing new surface is a **classification
field on the discovered reference** owned by the discovery module (`tasks/issue_reference_discovery.py`
+ `tasks/issue_matrix.py`), consumed read-only by the three gating sites. This keeps one authority for
"is this reference gating?" and makes the cross-site consistency test (NFR-006) meaningful.

## Complexity Tracking

*No Constitution Check violations — section intentionally empty.*

## Parallel Work Analysis

### Dependency Graph

```
WP01  Classification seam (foundation)
      tasks/issue_reference_discovery.py + issue_matrix.py:
      per-reference gating classification, aggregate-over-occurrences,
      default-gating fail-safe. Shared function + IssueReference field.
        │
        ├────────────────► WP02  Verdict contract + ADR
        │                        IssueMatrixVerdict += not-applicable (terminal, non-gating);
        │                        issue-verdict CLI + help; approval-blocker terminal-verdict logic;
        │                        ADR (supersedes WP09 intent). [depends WP01 for the row model]
        │                          │
        │                          └────► WP03  Cross-site adoption + gate ergonomics
        │                                       merge_gates + status/doctor consume the shared
        │                                       classifier (NFR-006); early-warning note (FR-007);
        │                                       evidence-token doc (FR-006). [depends WP01+WP02]
        │
   (parallel lane, no issue-matrix coupling)
WP04  move-task CLI ergonomics + docs
      --actor/--reason aliases (FR-005), --assignee docstring (FR-009),
      inert-checkbox guidance (FR-008). Independent from day one.
        │
        └────────────────────────────────────────────────────►  WP05  Docs/CHANGELOG/ADR-finalize
                                                                       + cross-WP ATDD sweep. [depends all]
```

### Work Distribution

- **Sequential spine**: WP01 → WP02 → WP03 (each consumes the prior's contract).
- **Parallel stream**: WP04 (move-task CLI ergonomics + docs) shares no files with the issue-matrix
  seam and runs concurrently with the spine from day one.
- **Final**: WP05 consolidates docs/CHANGELOG, finalizes the ADR, and runs the cross-WP ATDD sweep.
- **Ownership (no-overlap guard)**: WP01 owns `tasks/`; WP02 owns `review/_issue_matrix.py` +
  `issue_verdict.py` + the approval-blocker verdict logic + the ADR; WP03 owns `merge_gates.py` +
  `doctor.py` + the mission-step prompts; WP04 owns `tasks.py` (move-task flag surface) + subtask
  docs. The only shared file risk is `tasks_parsing_validation.py` (WP02 verdict logic vs WP03
  classifier consumption) — sequence WP02 before WP03 to serialize it.

### Coordination Points

- **Contract handoff**: WP01 publishes the classification contract (`contracts/`) that WP02/WP03
  consume. WP02 publishes the verdict-vocabulary contract.
- **Integration test**: NFR-006 cross-site consistency test (a reference non-gating at `approved` is
  non-gating at merge and in doctor) is the integration proof; it lands with WP03 and exercises all
  three consumers against the one classifier.
- **Lanes**: two lanes (spine + WP04) is the natural topology; the mission was created with `coord`
  topology so lane state is coordinated.
