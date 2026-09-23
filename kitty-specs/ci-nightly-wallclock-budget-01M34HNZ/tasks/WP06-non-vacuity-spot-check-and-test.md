---
work_package_id: WP06
title: Non-Vacuity Spot-Check + Mandatory Committed Test (Phase 2c/2d)
dependencies:
- WP05
requirement_refs:
- FR-008
- NFR-003
- C-005
planning_base_branch: issue-4865-ci-nightly-wallclock-budget
merge_target_branch: issue-4865-ci-nightly-wallclock-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4865-ci-nightly-wallclock-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4865-ci-nightly-wallclock-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-nightly-wallclock-budget-01M34HNZ
base_commit: e864b4563a21c6635a8bd81b542011034fe90b7c
created_at: '2026-09-22T19:45:21.027740+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
- T033
phase: Phase 2 - Recapture & Re-Derive
history:
- at: '2026-09-22T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_charter_shard_skew_sensitivity.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_charter_shard_skew_sensitivity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Non-Vacuity Spot-Check + Mandatory Committed Test

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: (unset — select per `spec-kitty agent profile list` if not pre-assigned)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*None yet.*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This WP closes the mission's central charter obligation — Standing Order #5, "a gate-unmask
cannot self-validate." `test_inter_shard_skew_within_twenty_percent`'s aggregate pass condition
(`checked_multi_shard >= 1` across all 21 registry modules) already passes today regardless of
whether `charter` specifically became non-vacuous — so this WP proves it DID, two ways:

1. **A documented ad-hoc spot-check** (not committed): skew at `charter`'s derived `shard_count`
   (WP05) vs. skew at a pre-declared, collision-free, deliberately-wrong `shard_count`.
2. **A durable, CI-re-runnable committed test** —
   `tests/architectural/test_charter_shard_skew_sensitivity.py` (NEW) — which plan.md elevates
   from spec.md's "optional" framing (SC-006) to a MANDATORY plan-level requirement
   (PLAN-VERIFY-002), because an uncommitted ad-hoc snippet alone cannot meet Standing Order #5's
   bar.

Success = FR-008/NFR-003: the new test passes, asserting a real, non-zero,
`shard_count`-sensitive skew for `charter` — proving the gate CAN now fail for this module if a
future `shard_count` change is wrong.

## Context & Constraints

- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/spec.md` — FR-008, NFR-003, SC-006, User Story
  2's AC2, "The vacuous-gate finding" section.
- `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/plan.md` — "Red-first / revert discipline"
  section's `#4864 registry re-derivation` subsection (the FULL mandatory-elevation reasoning and
  the pre-declared wrong-`shard_count` rule, stated below verbatim), "Spec-phase review findings
  already resolved" (why this elevation is a plan-level decision, not a spec edit), Phasing §
  Phase 2 steps 2c-2d.
- **`tests/architectural/test_module_shard_registry.py` stays READ ONLY** — this WP imports
  `_lpt_bin_pack`/`_skew_of` from it, never edits it.
- **The PRE-DECLARED, collision-free, deliberately-wrong `shard_count` rule** (stated in plan.md
  BEFORE any real skew number was known — do NOT adjust this rule post-hoc to produce a
  convenient result):
  - For every `derived_shard_count >= 3`: use `max(2, derived_shard_count // 2)`.
  - For `derived_shard_count == 2`: use `derived_shard_count * 2` instead — this is the ONE case
    where the plain `// 2` form silently degenerates to a no-op (`max(2, 2 // 2) = max(2, 1) = 2`,
    IDENTICAL to `derived_shard_count` itself, which would compare `charter`'s skew at
    `shard_count=2` against itself — proving nothing while appearing to validate the gate).
  - This rule additionally excludes `shard_count == 1` (at `shard_count == 1`, `_lpt_bin_pack`
    places every duration into a single bin, so `_skew_of`'s `(max(bins) - min(bins)) / max(bins)`
    formula always returns exactly `0.0` for ANY data — a degenerate choice) and excludes any
    value within 1 of `len(module_test_durations["charter"])` (near-degenerate — each bin would
    hold ~1 test).

## Branch Strategy

- **Strategy**: `single_branch`.
- **Planning base branch**: `issue-4865-ci-nightly-wallclock-budget`
- **Merge target branch**: `issue-4865-ci-nightly-wallclock-budget`

> Populated automatically by `spec-kitty agent mission tasks`. Do NOT change manually.

## Subtasks & Detailed Guidance

### Subtask T028 – Run the documented ad-hoc spot-check

- **Purpose**: SC-006's illustrative, human-readable proof, supplementary to T029's committed
  test.
- **Steps**:
  1. Import `_lpt_bin_pack`/`_skew_of` from `test_module_shard_registry.py` and the recaptured
     `module_test_durations["charter"]` from `.github/ci-shard-timings.json` (WP04's output).
  2. Compute skew at `charter`'s genuinely LPT-derived `shard_count` (WP05's T024 value). Expect
     `<=20%` (passing).
  3. Compute skew at the deliberately-wrong `shard_count` per the pre-declared rule above (using
     WP05's derived `shard_count` as `derived_shard_count` in the rule). Expect `>0%`, plausibly
     `>20%`.
  4. Record BOTH commands and BOTH numeric outputs verbatim — this is the artifact WP07 pulls into
     the PR description under a "Non-vacuity spot-check" heading.
- **Files**: None committed (an ad-hoc script/REPL session is fine — do not add it to the repo).
- **Parallel?**: No — depends on WP05's derived `shard_count`.

### Subtask T029 – Write the mandatory committed non-vacuity test

- **Purpose**: FR-008/NFR-003/PLAN-VERIFY-002 — the standing order's evidence of record: durable,
  independently re-executable by CI on every future PR touching the `charter` row.
- **Steps**:
  1. Create `tests/architectural/test_charter_shard_skew_sensitivity.py` (does not exist before
     this WP).
  2. Import `_lpt_bin_pack`/`_skew_of` from `test_module_shard_registry.py` (that file stays
     read-only) plus the recaptured `module_test_durations["charter"]`.
  3. Write a test asserting `charter`'s own recomputed skew AT ITS DERIVED `shard_count` (WP05's
     value) is non-zero and ABOVE A CONCRETE FLOOR — start from `>1%`, then tighten it once T028's
     real recaptured number is known (do not leave a floor looser than the real measured value
     would justify).
  4. Keep this test narrowly scoped — it is a sibling module to `test_module_shard_registry.py`,
     not a replacement or extension of it.
- **Files**: `tests/architectural/test_charter_shard_skew_sensitivity.py` (NEW)
- **Parallel?**: No — depends on T028's real numbers to calibrate the floor.

### Subtask T030 – `ruff format --check` on the new file

- **Purpose**: Formatting gate enforced repo-wide.
- **Steps**: `uv run ruff format --check tests/architectural/test_charter_shard_skew_sensitivity.py`
  — fix with `uv run ruff format tests/architectural/test_charter_shard_skew_sensitivity.py` if it
  flags anything, then re-check.
- **Files**: `tests/architectural/test_charter_shard_skew_sensitivity.py`
- **Parallel?**: No — depends on T029.

### Subtask T031 – Run the new test, confirm GREEN

- **Purpose**: The genuine pytest-observable RED-then-GREEN story for this WP.
- **Steps**: `uv run --frozen pytest tests/architectural/test_charter_shard_skew_sensitivity.py
  -q` — confirm it passes against the real recaptured data.
- **Files**: None (verification only).
- **Parallel?**: No — depends on T029/T030.

### Subtask T032 – Confirm the existing gate still passes

- **Purpose**: Close the loop that WP05's registry edit did not regress the gate's own aggregate
  pass condition.
- **Steps**: `uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q` —
  confirm it passes post-recapture. Note explicitly in your Activity Log that this test's own
  aggregate `checked_multi_shard >= 1` condition passing is NOT, by itself, proof `charter`
  specifically became non-vacuous — that is what T028/T029/T031 prove.
- **Files**: None (verification only).
- **Parallel?**: No.

### Subtask T033 – Commit the new test

- **Purpose**: Land the mandatory non-vacuity proof.
- **Steps**: Stage `tests/architectural/test_charter_shard_skew_sensitivity.py` only. Commit with
  a message like `test(ci): add charter shard skew non-vacuity test`.
- **Files**: `tests/architectural/test_charter_shard_skew_sensitivity.py`
- **Parallel?**: No.

## Red-first / revert discipline (concrete, for this WP)

**RED before this WP**: `tests/architectural/test_charter_shard_skew_sensitivity.py` does not
exist before T029 — there is no test to run, and if a version of it existed against the
PRE-recapture data it would assert nothing meaningful (the near-uniform ~0.098s-mean durations
make every `shard_count` from 1 to 4211 report ~0% skew, so a non-vacuity assertion against that
data would either be vacuously true or would never have been written honestly). **GREEN after**:
T031's run asserts a real, non-zero, `shard_count`-sensitive skew against WP04's recaptured data.
Unlike WP02/WP03's live-topology claims (where a pytest RED is structurally impossible), THIS
WP's central claim IS genuinely pytest-observable — this is the real RED-then-GREEN story the
charter's ATDD-First Discipline (C-011) and Standing Order #4 require, made concrete rather than
hand-waved.

## Test Strategy

- `uv run --frozen pytest tests/architectural/test_charter_shard_skew_sensitivity.py -q` —
  mandatory, T031.
- `uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q` — mandatory,
  T032, confirming no regression to the existing gate.
- `uv run ruff format --check tests/architectural/test_charter_shard_skew_sensitivity.py` —
  mandatory, T030.

## Risks & Mitigations

- **Risk**: the concrete floor (`>1%`) in T029's assertion is calibrated blind, before the real
  number is known, and turns out too tight (flaky) or too loose (weak proof). **Mitigation**: T028
  runs FIRST specifically so T029's floor is set against the real recaptured skew, not a guess.
- **Risk**: adjusting the pre-declared wrong-`shard_count` rule after seeing an inconvenient
  result. **Mitigation**: the rule is stated verbatim above, sourced directly from plan.md, which
  states it was fixed BEFORE implementation saw any skew numbers — do not deviate from it.

## Review Guidance

- Confirm the new test file did not exist before this WP (git history / `create_intent`
  confirms this).
- Confirm the test asserts against WP05's genuinely derived `shard_count`, not a hardcoded
  literal that happens to match it today (a future re-derivation should not silently desync the
  test from the registry row — consider whether the test should import the registry's YAML row
  directly, or accept the derived value as a documented constant with a comment explaining the
  linkage, and pick the more maintainable of the two, stating the choice in the Activity Log).
- Confirm the spot-check's two numbers (T028) are recorded somewhere retrievable for WP07 — not
  only in this WP's private scratch session.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-22T14:15:00Z – system – Prompt created.

- 2026-09-22T19:07:50Z – claude (Wrangler Wendy) – **RULING RECEIVED**: operator Decision Moment
  `DM-01M3584PY5A6F79DWX1QFDHW87` (see `kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/decisions/`)
  withdraws the premise this WP's prompt was written on — WP05's committed claim that the
  WP04 recapture made the skew gate "genuinely `shard_count`-sensitive" for `charter`. Independent
  re-measurement (the gate's own `_lpt_bin_pack`/`_skew_of`) found skew stays ~0% across the whole
  practical `shard_count` range (2–40ish) both before AND after the recapture, and that the
  pre-recapture data crossed the 20% ceiling EARLIER (k=52) and read WORSE (39.4% at k=67) than
  post (19.9% at k=67) — the k>=68 crossing is a structural bin-packing artifact (largest single
  test exceeding one ideal bin), not detection of genuine imbalance. FR-008/NFR-003/SC-006 are
  recorded as **not satisfied**. T028's ad-hoc spot-check (skew at derived vs. deliberately-wrong
  `shard_count`) and T029's originally-specified committed test
  (`tests/architectural/test_charter_shard_skew_sensitivity.py`, asserting non-zero
  `shard_count`-sensitive skew) are **superseded** — writing either would assert a property that
  predates this mission, i.e. a vacuous test about a vacuous gate. Per the ruling, this WP is
  repointed toward the REAL defect behind #4864: `module-tests.yml` pairs committed durations to
  collected node ids positionally and silently falls back to uniform weights on a length mismatch;
  no existing gate notices because the skew guard only re-reads the same committed list.

- 2026-09-22T19:30:00Z – claude (Wrangler Wendy) – **Honest 21-module measurement** (replaces
  T028's spot-check, which is no longer the right proof): ran the consumer's own
  `pytest <test_dirs> -m "not performance and not stress" --collect-only -q` against every
  `.github/ci-module-registry.yml` row's `test_dirs` (resolved via
  `scripts/ci/capture_shard_timings.resolve_test_dirs`, never reimplemented) and compared each
  count to `len(module_test_durations[module])` in `.github/ci-shard-timings.json`. Result: only
  `charter` (6156==6156, this mission's recaptured module) agrees. All other 20 modules mismatch
  (e.g. `status` 1702 committed vs 1758 collected — matches the number DM-01M3584PY5A6F79DWX1QFDHW87
  cites independently). Full table recorded in the WP06 report to the mission orchestrator.

- 2026-09-22T19:45:00Z – claude (Wrangler Wendy) – **T029 delivered differently**: created
  `tests/architectural/test_module_length_agreement.py` (NOT the originally-named
  `test_charter_shard_skew_sensitivity.py` — that name and assertion are what the ruling
  withdraws). Asserts committed/collected length agreement for every non-allowlisted module, with
  a frozen `_MISMATCH_ALLOWLIST` (Standing Order #2) covering the 20 known-mismatched modules,
  enforced shrink-only via a count ratchet (`_BASELINE_ALLOWLIST_COUNT = 20`,
  `test_allowlist_does_not_exceed_baseline`) plus a dead-entry check forcing removal once a module
  is recaptured (`test_allowlisted_modules_still_genuinely_mismatch`), plus a hard-coded guard that
  `charter` itself can never enter the allowlist (`test_charter_is_not_allowlisted_and_agrees`).
  Self-mutation tests (`test_mismatch_detection_fires_on_synthetic_length_disagreement` et al.)
  prove the comparison mechanism fires on a synthetic mismatch without a subprocess call
  (Standing Order #5). T030 (`ruff format --check`) and T031 (run new test, confirm GREEN — 8/8
  passed) both done. T032: `tests/architectural/test_module_shard_registry.py` re-run, 17/17
  still pass post-recapture — noted per the subtask's own instruction that this aggregate pass is
  NOT itself proof of non-vacuity (the length-agreement test above is). Mutation demonstration
  performed twice (perturbed `ci-shard-timings.json`'s `charter` duration count by one entry —
  RED on both `test_non_allowlisted_modules_agree_with_live_collection` and
  `test_charter_is_not_allowlisted_and_agrees`, then restored — GREEN; separately grew
  `_MISMATCH_ALLOWLIST` to 21 entries — RED on `test_allowlist_does_not_exceed_baseline`, then
  restored — GREEN); `git status --porcelain` confirmed clean after both restores. Full
  `tests/architectural/` battery (`-m "not performance and not stress and not timing" -n auto
  --dist loadfile`) run three times: without the new file (2805 passed/3 skipped/2 xfailed, 0
  failed) and with it twice (once showing one unrelated pre-existing xdist race between
  `test_charter_sole_door_resolver_imports.py` and `test_topology_inference_retired.py`'s
  `src/__t019_relay_negative_control__.py` scratch file — neither file touched by this WP's diff
  — non-reproducing on immediate re-run: 2813 passed/3 skipped/2 xfailed, 0 failed, matching
  2805+8 exactly). T033: committed as `bbb463ee2` on `issue-4865-ci-nightly-wallclock-budget` via
  `spec-kitty safe-commit`.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP06 --to
<status>` to change WP status.
