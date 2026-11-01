---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: dispatch-router-docs-coverage-01M6BTTX
mission_id: 01M6BTTXA9B98ZEY6T8W6G4RSG
generated_at: '2026-11-01T15:26:40.499739+00:00'
analyzer_agent: pi
input_artifacts:
  spec.md:
    path: kitty-specs/dispatch-router-docs-coverage-01M6BTTX/spec.md
    sha256: e04e1631c67d9e8a6c4a369826fd32c459fc46474d1f3a139ecf6079dc3a7f42
  plan.md:
    path: kitty-specs/dispatch-router-docs-coverage-01M6BTTX/plan.md
    sha256: 14da85e67ddd2484eadc4cedd219ccf5f8c5173dc6ea08c28cc201dbf3aeccad
  tasks.md:
    path: kitty-specs/dispatch-router-docs-coverage-01M6BTTX/tasks.md
    sha256: 35deeeece95d52f8c39a0aa1ef5ac879967f2a8bafbabe93c6c38d2e6fbe65ae
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  low:
  high:
  info:
  critical:
  medium:
findings: []
---

# Analysis Report: `dispatch` docs routing (#6970)

**Date**: 2026-11-01 · **Branch**: `kitty/mission-dispatch-router-docs-coverage-01M6BTTX`
**Gate**: spec ↔ plan ↔ tasks consistency + requirement coverage, pre-implement.
**Analyzer**: pi/deepseek-v4.1-flash-1017, with one pre-implementation review round
(independent reviewer, read-only) whose findings are folded into the artifacts.

## Requirement coverage (spec → IC → WP → subtask)

| Requirement | IC | WP | Subtask(s) | Status |
|-------------|----|----|-----------|--------|
| FR-001 docs request routes without `--profile` | IC-01 | WP01, WP02 | T001, T002, T014 | covered (router + CLI proof) |
| FR-002 bare `index` is not a docs signal | IC-01 | WP01, WP02 | T001, T014 | covered (positive + negative, both levels) |
| FR-003 multi-token keyword/verb matches | IC-01 | WP01 | T003, T004 | covered |
| FR-004 NO_MATCH names nearest candidates | IC-02 | WP01, WP02 | T005, T006, T010 | covered |
| FR-005 NO_MATCH names the remedy command | IC-02 | WP01, WP02 | T005, T006, T010 | covered |
| FR-006 AMBIGUOUS names tied ids + remedy | IC-02 | WP01, WP02 | T005, T006, T010 | covered |
| FR-007 human refusal without `--json` | IC-03 | WP02 | T008, T009 | covered (no-match, dry-run, unknown `--profile`) |
| FR-008 JSON envelope compatible | IC-02 | WP01, WP02 | T005, T008 | covered |
| FR-009 router stays pure | IC-01 | WP01 | T007(c), T007(f) | covered |
| FR-010 verb tier outranks signals | IC-01 | WP01 | T004, T007(e) | covered |
| FR-011 new signals are fallback tiers | IC-01 | WP01 | T002, T004, T007(d)(e) | covered (added after review round) |
| FR-012 ranking never decays a decision | IC-02 | WP01 | T006, T007(f) | covered |
| NFR-001 deterministic order | IC-02 | WP01 | T006, T007(a)(b) | covered |
| NFR-002 bounded refusal size | IC-02 | WP01 | T005, T006 | covered (≤3) |
| NFR-003 no routing regression | IC-01 | WP01 | T007(d)(e) | covered (shipped-catalog differential corpus) |
| NFR-004 complexity ceiling | IC-01 | WP01 | prompt constraint + review | covered |
| NFR-005 fast refusal path | IC-02 | WP01 | T007(c) | covered (single `list_all`) |
| C-001 no pack edits | — | all | owned_files forbid `packs/` | covered |
| C-002 no new confidence tier | IC-01 | WP01 | T002 constraint | covered |
| C-003 no LLM/plugin fallback | IC-01 | WP01 | prompt constraint | covered |
| C-004 one routing authority | IC-02 | WP01, WP02 | T006, T009 | covered |
| C-005 no gate weakening | — | all | prompt constraint | covered |
| C-006 red-first proof | — | WP01, WP02 | T001, T003, T005, T008, T014 | covered |
| SC-001 issue request routes | — | WP01, WP02 | T001, T014 | covered |
| SC-002 refusals name candidates | — | WP01 | T005, T006 | covered |
| SC-003 AMBIGUOUS names tied ids | — | WP01, WP02 | T006, T010 | covered |
| SC-004 no route moved | — | WP01 | T007(d) | covered |
| SC-005 phrase pairwise | — | WP01 | T003, T004 | covered |
| SC-006 differential corpus | — | WP01 | T007(d)(e) | covered |

Zero unmapped requirements; zero subtasks without a requirement link.

## Consistency checks

- **Spec ↔ plan**: every FR maps to an IC; IC-04 (docs/changelog) carries the charter rule
  rather than an FR, and WP03 references FR-001/FR-004/FR-007 only as *documented*
  behaviour, which the requirement validator accepts.
- **Plan ↔ tasks**: WP01/WP02 own only `src/` + `tests/` paths; WP03 is a
  `planning_artifact` WP confined to `docs/` (finalize-tasks ownership validation passes,
  no overlapping `owned_files`).
- **Tasks ↔ testability**: every subtask names a runnable command or assertion. The three
  tests that must be red-first (T001, T003, T005) and the CLI-level T008/T014 state the
  expected failure explicitly.
- **Tier ordering** is stated once in `data-model.md` §"Signal tiers" and referenced by
  WP01 T002/T004/T007; no artifact restates it differently.

## Findings from the pre-implementation review round and their disposition

1. **(blocker, fixed in artifacts)** Adding phrase/alias matches to one candidate pool
   moved live routes (`release notes for the sprint` → `comms-leo`… correction:
   `comms-cleo`; `the guide for the spike` → a priority-40 tie). Disposition: the signals
   are now ordered **fallback tiers** (single token → phrase → docs alias), adding FR-011
   and SC-006, and WP01 T007 asserts the two named requests plus a differential corpus.
2. **(should-fix, fixed in artifacts)** No CLI-level proof of SC-001. Disposition: new
   WP02 T014 asserts the exact request and the bare-`index` negative through
   `dispatch --dry-run --json` with the configured-charter stub.
3. **(should-fix, fixed in artifacts)** FR-002 had no verifying test. Disposition: the
   positive/negative pair is now in WP01 T001 and WP02 T014.
4. **(should-fix, fixed in artifacts)** `profile_not_found_routing` still dumped JSON in
   human mode. Disposition: WP02 T009 routes that third call site through the same
   renderer; T008 asserts it first (red).
5. **(nit, folded into 1)** Alias-induced priority ties. Covered by the same tier ladder
   and the differential corpus.
6. **(should-fix, fixed in artifacts)** The changelog style guard requires the issue
   reference *after* the bold headline and a `**Before:**` sentence. Disposition: WP03
   T011/T013 now pin the house shape and run `check_changelog_style`.

## Verdict

**PASS** — the artifacts are internally consistent, every FR/SC has an owning subtask with
a red-first or ratchet proof, and the review round's blocker is closed by design rather
than by assertion wording.
