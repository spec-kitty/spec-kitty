---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: migration-actor-cli-spoofing-01M66YYX
mission_id: 01M66YYX43K243WESFE0QRZ1MJ
generated_at: '2026-10-30T17:56:06.841862+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/migration-actor-cli-spoofing-01M66YYX/spec.md
    sha256: a9e626e78c76254647159cc7a5e55d618937a42f6b22f9101dfa54977e4a5980
  plan.md:
    path: kitty-specs/migration-actor-cli-spoofing-01M66YYX/plan.md
    sha256: 75367de17d1b706e5742e079ec714980fa004338caf0f11d0cc09754fc90dc2e
  tasks.md:
    path: kitty-specs/migration-actor-cli-spoofing-01M66YYX/tasks.md
    sha256: 6abc0e726146d6d5703d178d80a9f72ae169c337c4908721433710e018762a01
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  critical: 0
  medium: 2
  low: 4
  info: 0
findings:
- id: F1
  severity: medium
  category: inconsistency
  summary: spec FR-009 says ONE matrix test file; plan and tasks split the matrix across three modules (WP01 plus two WP02 modules).
- id: F2
  severity: medium
  category: coverage
  summary: "NFR-004 (quality gates: ruff/format/mypy, no new suppressions, complexity <= 15) is not in any work package's requirement_refs."
- id: F3
  severity: low
  category: underspecification
  summary: WP01 subtask T005 names tests/specify_cli/cli/commands/agent/test_status_emit.py, which does not exist; the owning module is tests/status/test_agent_status_emit_cli.py.
- id: F4
  severity: low
  category: inconsistency
  summary: plan.md Scale/Scope says 5 source files; the ownership map names 8 source files.
- id: F5
  severity: low
  category: ambiguity
  summary: spec Edge Cases does not say whether the refusal trims whitespace (a leading space defeats the prefix); data-model invariant 1 does, the spec row only implies it.
- id: F6
  severity: low
  category: duplication
  summary: research D-3 and data-model.md both tabulate the surface-by-surface recording shapes; deliberate (decision record vs design), but the two must stay in sync.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency | MEDIUM | spec.md FR-009; tasks.md WP01/WP02 | FR-009 asks for "one matrix test file that drives each refused surface"; the WP split puts the emit arms in `tests/status/test_caller_seed_refusal_6754.py` and the orchestrator-api / implement arms in two WP02 modules, because a WP must be green when it is approved and WP02's surfaces do not exist at WP01 time. | Reword FR-009 as "one matrix per surface family, same matrix spec, driven through real entry points" so the requirement matches the executable plan. No behaviour change. |
| F2 | Coverage | MEDIUM | spec.md NFR-004; tasks.md requirement_refs | NFR-004 is a standing quality gate rather than work an implementer schedules: every WP prompt already carries the ruff/format/mypy commands and the review guidance checks complexity ≤ 15 and no new suppressions. It has no `requirement_refs` entry, so the coverage table shows it unmapped. | Accept as CI- and review-enforced (do not add a WP), or add NFR-004 to WP01's refs if the reviewer wants it tracked. Reviewer's call; no implementation gap. |
| F3 | Underspecification | LOW | tasks/WP01-refusal-authority-and-emit-surface.md T005 | The prompt names a module that does not exist and tells the implementer to "pick the module that owns `agent status emit`". | Replace the path with `tests/status/test_agent_status_emit_cli.py` (verified to exist on the base). |
| F4 | Inconsistency | LOW | plan.md "Scale/Scope" | Says "5 source files"; the ownership map and tasks name 8 (`models.py`, `actor.py`, `status/__init__.py`, `agent/status.py`, `tasks_move_task_hops.py`, `tasks.py`, `orchestrator_api/wp_lifecycle.py`, `implement.py`). | Correct the count to 8 in plan.md. |
| F5 | Ambiguity | LOW | spec.md Edge Cases | The row for `" migration:x"` says it "is left alone" without stating the rule (the classifier and the refusal are both the exact, case-sensitive prefix with no trimming). `data-model.md` invariant 1 states it; the spec row should too. | Add "the guard is the exact prefix, never a trimmed one" to the edge case. |
| F6 | Duplication | LOW | research.md D-3; data-model.md | Both tabulate which surface records an identity verbatim and which parses it strictly. Intentional: research records the grounding decision, data-model records the design. | Keep both; the reviewer should confirm they agree after implementation (they describe the same 8 surfaces). |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 one-refusal-authority | yes | T002 | WP01 |
| FR-002 emit-refused | yes | T001, T003 | WP01 |
| FR-003 orchestrator-api-refused | yes | T006, T007 | WP02 |
| FR-004 implement-refused | yes | T008, T009 | WP02 |
| FR-005 fail-closed-builder | yes | T004 | WP01 |
| FR-006 recorded-seeds-keep-status | yes | T004, T005 | WP01 |
| FR-007 explicit-agent-unchanged | yes | T001, T005 | WP01 |
| FR-008 migration-writers-unchanged | yes | T005 | WP01 |
| FR-009 matrix-pinned | yes | T001, T006, T008 | WP01 + WP02 (see F1) |
| FR-010 no-silent-rewrite | yes | T003, T004 | WP01 (asserted by the byte-identical-log arm) |
| FR-011 docs-and-changelog | yes | T011, T012, T013 | WP03 |
| NFR-001 no-partial-state | yes | T007, T009 | WP02 |
| NFR-002 no-extra-io | yes | T003, T004 | WP01 (predicate only, no I/O) |
| NFR-003 coverage | yes | (all) | measured by the diff-cover gate in CI |
| NFR-004 quality-gates | no | — | see F2 (standing gate, CI + review enforced) |
| NFR-005 one-predicate-n-call-sites | yes | T002, T010 | WP01 + WP02's review guidance |
| C-001 no-events-contract-change | yes | — | binding constraint on every task; no task may touch `spec_kitty_events` |
| C-002 no-new-append-path | yes | T007, T009 | the refusal removes write paths only |
| C-003 reader-side-untouched | yes | T002, T005 | WP01 review guidance diffs `status/` for reader edits |
| C-004 system-writers-out-of-scope | yes | — | scope boundary, enforced by the ownership map |
| C-005 compatibility-stated | yes | T013 | WP03 |
| SC-001 zero-refused-writes | yes | T006, T008 | WP02 |
| SC-002 allowed-forms-unchanged | yes | T005 | WP01 |
| SC-003 migration-writers-unchanged | yes | T005 | WP01 |
| SC-004 rule-in-one-place | yes | T002 | WP01 |

**Charter Alignment Issues:** none. Single canonical authority (one predicate, six call sites), architectural alignment (no events-package or frozen-path change), ATDD-first (T001/T006/T008 are red-first and committed alone), locality of change (8 source files, no refactor), no new append path, terminology canon (`Mission`), and `NO_FULL_HEAVY_SUITES_IN_MISSION` (every WP prompt names the targeted suites and forbids the full sweeps).

**Unmapped Tasks:** none. Every subtask belongs to exactly one work package, and the three work packages have disjoint `owned_files`.

**Interface and dependency notes:**

- WP02 depends on WP01 for the refusal predicate; WP03 depends on both because it documents the final behaviour. The dependency graph is acyclic and `lanes.json` computed 3 lanes (`lane-a`, `lane-b`, `lane-planning`) with no collapse.
- The only cross-surface ordering risk is the guard placement inside `implement` (before `detect_context`) and inside the four orchestrator-api verbs (before `_resolve_start_workspace`); both are stated in the WP02 prompt with the reason (NFR-001).

**Verdict:** ready. No high or critical findings; the two medium findings are a wording mismatch between spec and plan (F1) and one standing quality gate tracked outside the requirement table (F2).
