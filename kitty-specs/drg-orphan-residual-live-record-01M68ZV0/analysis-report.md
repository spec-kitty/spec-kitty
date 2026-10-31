---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: drg-orphan-residual-live-record-01M68ZV0
mission_id: 01M68ZV0YVQ02CMX6QYD38QKGE
generated_at: '2026-10-31T12:46:41.466094+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/drg-orphan-residual-live-record-01M68ZV0/spec.md
    sha256: b4f14934609ae6b26bdd0a369b1b4ee530ac55251fab5da730899e2075fe8a76
  plan.md:
    path: kitty-specs/drg-orphan-residual-live-record-01M68ZV0/plan.md
    sha256: c33173d89f8bb0148b69cae4cd8a337b8569e554841259d637637a98dfcc656e
  tasks.md:
    path: kitty-specs/drg-orphan-residual-live-record-01M68ZV0/tasks.md
    sha256: efa261b6c96b016b39caaee1f7d67a3e761776ab9be4bc8882994a8996b6b2f1
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  medium: 1
  high: 0
  low: 1
  info: 0
findings:
- id: F1
  severity: medium
  category: duplication
  summary: The record's 25 URNs and the pure-view _SHIPPED_ORPHANS pin both list membership; the plan states the differing frames but tasks.md does not make the frame distinction an explicit reviewer checkpoint.
- id: E1
  severity: low
  category: coverage
  summary: SC-004 (docs gates + touched module green) is covered by T007 only; no task names the markdownlint invocation explicitly enough to be reproducible.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Duplication | MEDIUM | spec.md (Key Entities), plan.md (Approach 1-2), tasks.md T002/T003 | Two membership lists now exist: the live record (shipped frame, 25) and `_SHIPPED_ORPHANS` (pure-extractor frame, 25 by coincidence of the one overlay/resolver difference). The plan explains why the frames differ; the WP prompt should say it too, or a future curator will "fix" one against the other. | Add one sentence to the WP prompt: the record is the *shipped* frame and is bound to `load_built_in_graph()`; `_SHIPPED_ORPHANS` stays the *pure* frame; they are related by `_ORPHANS_RESOLVED_BY_OVERLAY`. |
| E1 | Coverage | LOW | spec.md SC-004, tasks.md T007 | The docs gate command is named, but the markdown lint invocation is given as "or the repo's markdown gate", which is not a reproducible command. | Name the repo's actual markdown gate (the CI step that lints `docs/`) in the WP prompt's T007. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 live-record | yes | T003 | shipped-frame record in an existing, inventory-registered page |
| FR-002 enumerate-measured-set | yes | T003 | delimited block, 25 URNs, grouped dispositions |
| FR-003 retarget-gate-instructions | yes | T004 | constant unchanged at 25 |
| FR-004 membership-guard | yes | T002, T005 | red-first, then both-direction proof |
| FR-005 ceiling-ledger-rationale | yes | T003 | 21 -> 25 with #6379/#6432 and #6513 |
| NFR-001 guard-cost | yes | T001, T002 | one reuse of the module's graph load |
| NFR-002 deterministic-offline | yes | T002 | doc read + set compare, no network/clock |
| NFR-003 docs-gates-green | yes | T007 | `check_docs_freshness --ci`, lint on touched docs |
| C-001 ceiling-unchanged | yes | T004, T007 | assertion still `<=`, constant still 25 |
| C-002 frozen-archive-untouched | yes | T007 | `test_archive_root_byte_identical.py` |
| C-003 no-gate-weakened | yes | T002, T005, T007 | guard is additive; no skip/xfail |
| C-004 out-of-scope-reds-cited | yes | (spec only) | #6798/#6801/#6816/#5927 cited as context; issue matrix rows carry `not-applicable` |

**Charter Alignment Issues:** none. No `src/` change, no doctrine-pack edit, no new dependency; the
change is a docs truth-up plus one additive guard, which is the smallest viable diff for the issue's
own remedy clause (`change-apply-smallest-viable-diff`, DIRECTIVE_024).

**Unmapped Tasks:** none. T001-T007 all map to FR/NFR/C rows above.

**Metrics:**

- Total Requirements: 8 (5 FR + 3 NFR) plus 4 constraints
- Total Tasks: 7
- Coverage %: 100
- Ambiguity Count: 1 (E1 — the markdown-lint command is not named precisely)
- Duplication Count: 1 (F1 — two membership lists in two frames)
- Critical Issues Count: 0
