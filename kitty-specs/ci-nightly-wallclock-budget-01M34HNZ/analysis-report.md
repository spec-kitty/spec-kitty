---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: ci-nightly-wallclock-budget-01M34HNZ
mission_id: 01M34HNZB9SSK2G0P35T1PEEJT
generated_at: '2026-09-22T15:38:19.741241+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md
    sha256: f333b029d3a743711cb423f5cc3cbc7d7970f25d7641cfe951236b5802d2f7a8
  plan.md:
    path: kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md
    sha256: 45e8e11534e186ba3b9c684f0b8fb259a295e3fea9c9a4667acf666a451bacff
  tasks.md:
    path: kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/tasks.md
    sha256: a86edee2262b9e991d4856064034f1a162f48d86de359d66a625a34ae48652a3
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: ready
issue_counts:
  low: 0
  critical: 0
  high: 0
  medium: 0
  info: 0
findings: []
---

## Specification Analysis Report — ci-nightly-wallclock-budget-01M34HNZ

Cross-artifact consistency analysis over spec.md, plan.md, tasks.md, and all 7 WP prompt files
(WP01-WP07), against `.kittify/charter/charter.md`. Two minor cross-artifact drift findings were
identified during this pass and were fixed directly (analyze-then-fix, per this mission's dispatch
instructions), so this report is findings-free:

1. **Fixed** — `tracer-design-decisions.md`'s "Decision (plan phase...): size the three new
   timeouts from real pulled run data" entry cited a stale, superseded provisional `stress` budget
   of "60 minutes". The committed `plan.md`/`tasks.md`/WP02/WP03 all use a two-stage design instead
   (Stage A `timeout-minutes: 90`, measurement-only; Stage B unconditionally re-derived from a real
   completed dispatch duration, with a `90 -> 150 -> 300` widen-retry ladder). `60` does not appear
   anywhere in the committed plan/tasks/WP text. Fixed by appending a dated correction entry to the
   tracer file (preserving the historical record rather than rewriting it) that states the
   authoritative Stage A value is 90, per plan.md.
2. **Fixed** — WP05 (`tasks/WP05-rederive-charter-shard-count.md`) was the only code-change WP
   (of WP01-06) missing a dedicated, labeled "Red-first / revert discipline" section — WP01, WP02,
   WP03, WP04, and WP06 all have one, and the RED/GREEN falsification content for WP05's own claim
   (T024's derivation trace must be independently reproducible) existed but was folded into "Test
   Strategy" only, under a different heading. This is directly relevant to the dispatch's explicit
   instruction to verify red-first is concrete for both YAML-only WPs (WP02 and WP05). Fixed by
   adding an explicit "Red-first / revert discipline (concrete, for this WP)" section to WP05,
   stating its RED/GREEN condition, and leaving a cross-reference in place of the duplicated text
   in "Test Strategy".

No other findings surfaced across the detection passes below.

### Detection passes run

- **Duplication**: none found. The widen-retry ladder (90 -> 150 -> 300), the ~1.5x-headroom
  timeout-sizing method, and the pre-declared wrong-`shard_count` rule are each stated once
  authoritatively (plan.md) and consistently cross-referenced (never re-derived) by every WP that
  uses them (WP02/WP03; WP06).
- **Ambiguity**: none found. Every FR/NFR/C is stated with concrete, measurable language; User
  Story 1 and User Story 2 each carry an explicit "How each AC fails (falsifiability)"
  subsection in spec.md.
- **Underspecification**: none found. The mission's own real-evidence-gathering (pulled run
  `35683539593`'s step timestamps via `gh run view --json jobs`) replaces what would otherwise be
  unspecified timeout values; the ~110-minute recapture cost and the up-to-~650-minute worst-case
  cumulative wall-clock are both explicitly sized and accepted, not hand-waved.
- **Charter alignment**: PASS against Standing Order #2 (campsite-clean precedes functional change
  — WP01's Commit A precedes WP02's Commit B), #3 (mission tracer files seeded and appended — all
  three tracer files present, and this pass's own corrections are recorded in them), #4/ATDD-First
  Discipline C-011 (WP06's committed `test_charter_shard_skew_sensitivity.py` is a genuine
  RED-before/GREEN-after story; WP02/WP03's live-topology claims are explicitly, correctly
  reasoned as falling outside pytest's reach and use the already-cited red baseline run instead),
  #5 (the mission's entire P2 half exists to close a vacuous-gate defect per this order's own
  "a gate-unmask cannot self-validate" language — see the WP04->WP05->WP06 finding below), and the
  Pre-existing Failure Reporting Rule (encoded as explicit conditional subtasks in WP01/T002,
  WP03/T016, WP04/T022).
- **Coverage gaps**: none. See the Requirements Coverage table and manual SC- check below — every
  FR/NFR/C/SC id maps to at least one WP, and no WP subtask lacks a traceable requirement.
- **Inconsistency**: the two items above (both fixed). No other inconsistency found between spec.md,
  plan.md, tasks.md, and the 7 WP files — cross-checked timeout values, job names, gate lists, the
  four operator rulings, and the PLAN-VERIFY-002 elevation, all below.
- **Terminology canon**: clean. Grepped spec.md/plan.md/tasks.md for `feature`/`Feature` as a
  product-domain term (as opposed to legitimate technical uses like `feature_dir`,
  `feature specification`, `--feature`-as-forbidden-flag documentation, or `feature/component`
  scaffolding vocabulary already present in CLAUDE.md's own Documentation Mission Patterns section)
  — no canon violation found. "Mission" is used consistently throughout.

### FR/NFR/SC/C requirement coverage

Full counts: **10 FRs** (FR-001–FR-010), **6 NFRs** (NFR-001–NFR-006), **7 Constraints**
(C-001–C-007), **8 Success Criteria** (SC-001–SC-008) — 31 requirement ids total, all traced.

**Known tooling gap accounted for explicitly**: `_parse_requirement_refs_from_tasks_md`
(`src/runtime/next/runtime_bridge_cores.py:93`, confirmed by direct inspection:
`_REQUIREMENT_REF_PATTERN = re.compile(r"\b(?:FR|NFR|C)-\d+\b", re.IGNORECASE)`) never matches an
`SC-` id — any automated coverage signal from `finalize-tasks`/this tool is structurally blind to
every `SC-` requirement. This mission's own `tracer-tooling-friction.md` (2026-09-22 entry) already
documents this defect precisely and its mitigation (an accompanying machine-recognized FR/NFR/C
anchor alongside every `SC-` citation). This analysis pass performed its own **manual** SC-
coverage check, independent of any tool signal, by reading tasks.md's own prose "Requirement Refs"
lines and the Requirements Coverage Summary table, plus each WP's Objectives/Success-Criteria text:

| SC id | Traces to | Manually confirmed via |
|---|---|---|
| SC-001 (three independent job entries) | WP03, WP07 | WP03 T013/T014 dispatch+capture; WP07 T034/T035 consolidation |
| SC-002 (stress conclusion never `cancelled`) | WP03, WP07 | WP03 T014/T017 Stage B; WP07 consolidation |
| SC-003 (`nightly-summary` needs: lists all three) | WP02, WP07 | WP02 T008; WP07 T036 |
| SC-004 (guard-test file modified, still passes) | WP02, WP07 | WP02 T009-T011; WP07 T038 commit-history check |
| SC-005 (`module_capture_provenance["charter"]` populated) | WP04, WP07 | WP04 T021; WP07 T035 |
| SC-006 (non-vacuous skew, spot-check + committed test) | WP06, WP07 | WP06 T028 (spot-check) + T029-T033 (committed test); WP07 T035/T036 |
| SC-007 (`shard_count` traceably derived) | WP05, WP07 | WP05 T024/T025; WP07 T035 |
| SC-008 (no pre-existing failure silently absorbed) | WP01, WP03 (T016), WP04 (T022), WP07 | WP01 T002 (conditional issue-filing); WP03 T016 and WP04 T022 also carry the same conditional Pre-existing Failure Reporting Rule obligation (not listed in tasks.md's summary table row for SC-008, which names only WP01/WP07 — a minor completeness gap in the summary table's own listing, not a coverage gap in the mission's actual enforcement, since the rule is genuinely threaded through all three WPs and consolidated by WP07) |

No `SC-` id is orphaned; every one traces to a concrete, implementing WP plus WP07's
evidence-consolidation. (Note: SC-008's coverage-table row listing only WP01/WP07, while WP03/WP04
also carry live conditional enforcement of the same rule, was considered as a possible finding but
judged not worth a fix-pass entry — the table is a summary, not the sole source of truth, and the
per-WP subtasks (T016, T022) are themselves unambiguous and already correctly cross-referenced to
WP01's mechanism ("apply the charter's Pre-existing Failure Reporting Rule"). Recorded here for
transparency rather than silently omitted.)

### Falsifiable acceptance criteria

Every FR/NFR/C/SC id has a falsifiable, concrete failure condition. FR-001–FR-010 for User Story 1
are covered by spec.md's explicit "How each AC fails (falsifiability)" subsection (AC1-AC4);
FR-006–FR-009 for User Story 2 by the equivalent subsection under User Story 2. NFRs and
Constraints each state their own concrete failure condition inline (e.g. NFR-002: stress's timeout
"must be sufficient... based on the wall-clock actually observed... not assumed"; C-001: "Enforced
by `tests/architectural/test_performance_marker_guard.py`"). SC-001–SC-008 are each stated as
precise, binary, directly-observable outcomes (a job conclusion, a populated record, a specific
`needs:` list) whose failure condition is the direct negation of the stated success condition — no
vague or unfalsifiable success criterion was found.

### Committed CI gate set — consistency across plan.md and WP prompts

plan.md's "Gate set" section (ruff format --check enforced repo-wide but out of `.github/*.yml`'s
domain; SonarCloud `sonar-pr` reported-not-required per C-007; diff-cover ≥90% structurally
inapplicable to the YAML/JSON files in this diff per C-006; commitlint; markdown lint;
`test_inter_shard_skew_within_twenty_percent`; `test_performance_marker_guard.py`'s two
trigger-detection tests as the real C-001/FR-005 enforcement mechanism) is consistently restated,
never contradicted, in every WP that touches a gated surface: WP02/WP06 both correctly scope
`ruff format --check` to the Python files they touch; WP04/WP05 correctly note no `ruff` gate
applies to their YAML/JSON-only edits; WP07 restates C-006/C-007 verbatim per its own T036. No
drift found.

### Red-first concreteness for the YAML-only WPs (WP02, WP05)

- **WP02** (job-split YAML): has an explicit "Red-first / revert discipline" section. Concrete: a
  pytest RED is structurally impossible for the live-topology claim; the already-cited run
  `35683539593`'s single blended, `cancelled` verdict IS the red baseline (no fresh
  revert-and-redispatch needed); WP03's post-split dispatch is the green. What IS pytest-observable
  (no `pull_request` trigger introduced) is stated separately and correctly.
- **WP05** (registry-row YAML): **was missing** this dedicated section (finding #2 above, now
  fixed). Its RED/GREEN condition — a reviewer's independent re-run of T024's recorded derivation
  trace against WP04's recaptured data reproducing a different smallest-skew-under-20% value would
  be RED; reproducing the identical value is GREEN — is a genuinely different (and genuinely
  concrete) falsification mechanism from WP02's, correctly distinguished from WP06's separate
  non-vacuity-test claim. Now stated in its own labeled section, consistent with sibling WPs.

### The four operator rulings — consistency check

All four verified present and mutually consistent across spec.md, plan.md, and every WP that
touches them; none is re-litigated or contradicted anywhere:

- **(a) YES.** #4865 is fixed by splitting into three jobs, never by raising the timeout cap.
  spec.md's "Binding operator decisions" #1 states the rejection explicitly ("Raising the single
  job's cap... was explicitly considered and rejected as a half-fix"); plan.md's Summary and
  tracer-design-decisions.md's first entry restate it identically; WP02's Context & Constraints
  states "Operator decision, binding, do not re-litigate: split into three jobs, never raise the
  single job's timeout."
- **(b) YES.** #4864's `charter` shard timings are recaptured via
  `scripts/ci/capture_shard_timings.py --module charter --write`; the manual heuristic from commit
  `349b73fc0` is explicitly rejected as a precedent. spec.md C-002/Clarifications, plan.md Summary
  + Seam/layering + Gate set, WP04's C-002 binding constraint, and WP05's AC3/context (citing the
  rejected heuristic by commit hash) all state this identically, using the same "explicitly
  rejected as a precedent" language throughout.
- **(c) YES.** Recapturing the other 13 stale registry modules is explicitly out of scope; per the
  charter's "no follow-up issues" standing order, no new GitHub issue is opened for that gap —
  spec.md's C-003/"Scope boundary (binding)" section, plan.md's Campsite-clean and Constitution
  Check sections, and WP04's Context & Constraints and Implementation Notes all state this
  identically. **Verified as actually ledgered, not just stated as intent**: read
  `tracer-design-decisions.md`'s "Decision: scope is `charter` only" entry directly — it records
  "the boundary is instead recorded in the spec's Clarifications section for the orchestrator to
  fold, escalate, or ledger at mission exit," matching C-003 exactly.
- **(d) YES.** WP07's T039 (re-checking PR #4886's collision status immediately before push) is
  detect-and-escalate only. Read T039's own subtask text directly: "This subtask is READ-ONLY,"
  "Do not attempt to reopen WP05, run `move-task --force`, or trigger any re-invocation of WP05's
  own work; WP07's role ends at detection and escalation." This is restated identically in WP07's
  Risks & Mitigations, Review Guidance, and in tasks.md's "Dependency & Execution Summary"
  two-checkpoint design section (WP05's T026 is the only WP permitted to edit the registry row
  mid-mission; WP07's T039 is read-only and terminal).

### The WP04→WP05→WP06 non-vacuity proof chain

**Confirmed real and committed, not an ad-hoc spot-check alone.** spec.md's own SC-006 language
frames the narrow `charter`-specific unit test as optional ("Optionally, a narrow
`charter`-specific unit test... would be a stronger, re-runnable alternative proof, but is not
required"). plan.md explicitly and deliberately elevates this: searching plan.md for
"PLAN-VERIFY-002" and "MANDATORY, not optional" confirms the "Red-first / revert discipline"
section's `#4864 registry re-derivation` subsection states "This plan deliberately elevates that
optional spec item to a MANDATORY plan-level requirement — a reasoned strengthening this plan
makes, not a spec correction" and the Constitution Check section restates: "the MANDATORY
committed, re-runnable `tests/architectural/test_charter_shard_skew_sensitivity.py`... is the
concrete, durable, independently re-executable non-vacuity proof this standing order requires; the
ad-hoc SC-006 spot-check snippet is retained only as a supplementary, human-readable illustration
in the PR description, not the standing order's evidence of record." WP06's own frontmatter
declares `create_intent: [tests/architectural/test_charter_shard_skew_sensitivity.py]` and
`owned_files: [tests/architectural/test_charter_shard_skew_sensitivity.py]`, and its subtasks
(T029 write, T030 format-check, T031 run-and-confirm-GREEN, T033 commit as `test(ci):`) deliver a
genuinely NEW, committed, CI-re-runnable pytest file — not merely an uncommitted spot-check. The
chain WP04 (recapture real per-test durations) -> WP05 (re-derive `shard_count` from that real
data via the existing LPT method) -> WP06 (commit a test asserting non-zero, `shard_count`-sensitive
skew at that derived value) is causally ordered and each step consumes the prior step's real,
recorded output (WP05 explicitly depends on WP04; WP06 explicitly depends on WP05). This
genuinely, mechanically delivers a committed re-runnable proof, satisfying spec.md's stronger,
plan-elevated bar — not merely an ad-hoc uncommitted spot-check (the spot-check, T028, is retained
only as a supplementary illustration for the PR description, exactly as plan.md specifies).

### Metrics

- Total Functional Requirements: 10 (FR-001–FR-010), 100% covered
- Total Non-Functional Requirements: 6 (NFR-001–NFR-006), 100% covered
- Total Constraints: 7 (C-001–C-007), 100% covered
- Total Success Criteria: 8 (SC-001–SC-008), 100% covered (manually verified; tool-blind to `SC-`
  prefix, see "Known tooling gap" above)
- Total Work Packages: 7 (WP01–WP07)
- Total Subtasks: 39 (T001–T039, including T039 out of numeric sequence per tasks.md's own
  documented WP07 subtask ordering)
- Duplication Count: 0
- Ambiguity Count: 0
- Underspecification Count: 0
- Critical Issues Count: 0
- High Issues Count: 0
- Medium Issues Count: 0
- Low Issues Count: 0 (2 low-severity drift items found and fixed in this same pass; see above)

### Next Actions

The mission is **READY for implementation**. No HIGH or CRITICAL findings. The two LOW-severity
drift items found during this pass (stale tracer-file timeout value; WP05's missing
"Red-first / revert discipline" section heading) were fixed directly in this same pass, so this
report is findings-free at the point of recording.
