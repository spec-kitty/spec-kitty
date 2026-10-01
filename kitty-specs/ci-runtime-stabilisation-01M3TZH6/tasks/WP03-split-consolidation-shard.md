---
work_package_id: WP03
title: Split the consolidation module shard
dependencies:
- WP02
requirement_refs:
- FR-012
- NFR-006
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 1 - Foundations
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/ci-module-registry.yml
- .github/ci-shard-timings.json
- tests/architectural/test_module_length_agreement.py
- .github/workflows/ci-charter-shard-recapture.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Split the consolidation module shard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

FR-012 (partial #5086): the consolidation module row stops setting the longest pipelines. It is
split into **two** shards balanced by **re-captured** timings, so `module-tests.yml`'s positional
pairing weights it by measured time instead of the uniform fallback.

Done means:

1. `.github/ci-module-registry.yml` consolidation row: `shard_count: 2`, with a reasoning comment
   in the style of the charter precedent (run-id, collected/passed/skipped counts, summed
   seconds, CI evidence, LPT-2 projection).
2. `.github/ci-shard-timings.json`: consolidation's `module_test_durations`,
   `module_test_count`, `module_duration_seconds` and `module_capture_provenance` replaced
   together by `scripts/ci/capture_shard_timings.py --module consolidation --write`; list length
   equals the consumer's live collection (**1617** today); provenance `selection` is
   `"not performance and not stress"` (the WP01 alignment).
3. `tests/architectural/test_module_length_agreement.py`: `"consolidation"` removed from
   `_MISMATCH_ALLOWLIST` and `_BASELINE_ALLOWLIST_COUNT` lowered **20 → 18** in the same commit.
4. `test_inter_shard_skew_within_twenty_percent` green at `shard_count=2`.
5. The predicted per-shard load (sum of each LPT bin) is recorded in the registry comment and the
   Activity Log. NFR-006 (p90 ≤ 15 min per shard over ≥ 3 CI runs; the two shards' durations within 25%) is measured later on the Mission PR's CI
   and recorded in the Mission evidence file by the orchestrator — not a local claim.

This copies commit `d460f55d91` ("ci(registry): split charter into 7 per-PR shards and recapture
its durations (#5378)"): registry + timings only, only the target module's entries change.

## Context & Constraints

- Read first: `research.md` D-18 (superseded on the count by **D-31**), D-21, D-31, R3 §3
  (3.1-3.6); `plan.md` IC-11; `data-model.md` "Module shard row" (20 → 18, D-31).
- Depends on WP02 (and transitively WP01): the capture now selects with
  `MODULE_SELECTION_MARKER_EXPR` and `test_module_length_agreement.py` imports it. Consolidation
  has no `stress` tests, so both expressions collect 1617 — but the recorded `selection` field
  must show the aligned expression.
- C-009: the capture runs the consolidation **module** suite serially (its own `test_dirs`).
  That is a module suite, not `tests/architectural` and not the whole repo — the same mechanism
  the charter precedent used. Do not use `ci-charter-shard-recapture.yml`: it is charter-only,
  gated to `refs/heads/main`, and publishes with a PAT (R3 §3.2).
- Lane discipline: `uv run --frozen …`; never `git stash`. Terminology: Mission.

### Current-state anchors (verified 2026-10-01)

| What | Where / value |
|---|---|
| Consolidation row | `.github/ci-module-registry.yml:13-36`; `shard_count: 1` at **line 27**; `test_dirs: [tests/consolidation, tests/specify_cli/consolidation, tests/terminus]` |
| Charter precedent comment | same file, lines 161-204 (`shard_count=5` … `shard_count=7` reasoning) |
| Committed timings | `module_test_durations.consolidation`: **782** entries, `module_duration_seconds.consolidation = 73.408`; provenance run-id `wp02-durations-20260918T185654Z`, `selection: "not performance"`, test_dirs without `tests/terminus` (captured as `merge`, before #3080 and #5001) |
| Live collection | `pytest tests/consolidation tests/specify_cli/consolidation tests/terminus -m "not performance and not stress" --collect-only -q` → **1617** (identical under `-m "not performance"`) |
| Allowlist | `tests/architectural/test_module_length_agreement.py:120-143` `_MISMATCH_ALLOWLIST` — **19 entries**; consolidation entry at **line 121** (`committed=782 collected=804 …`) |
| Baseline | `_BASELINE_ALLOWLIST_COUNT = 20` at **line 151** |
| Ratchets | `test_allowlist_does_not_exceed_baseline` (:402, `len <= baseline`); `test_allowlisted_modules_still_genuinely_mismatch` (:420, hard-fails if an allowlisted module agrees — its message says "lower _BASELINE_ALLOWLIST_COUNT to match"); `test_non_allowlisted_modules_agree_with_live_collection` (:352, warn by default, hard fail under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`) |
| Skew gate | `tests/architectural/test_module_shard_registry.py::test_inter_shard_skew_within_twenty_percent` (:269), LPT over committed durations at the row's `shard_count`, ≤ 20 % |
| CI evidence | last 7 green consolidation runs 15.5-26.2 min serial; xunit sum ≈ 788 s; heaviest single test 39.3 s (R3 §3, D-21) |
| Stale prose elsewhere | `.github/workflows/ci-charter-shard-recapture.yml:26` and `:41` say `agent` is "the only other non-allowlisted module" — false once consolidation leaves the allowlist |

What adjusts automatically (verify, do not edit): coverage artefact basenames come from
`(module, shard, of)` (`tests/architectural/test_coverage_artefact_contract.py:135`);
`scripts/ci/reconcile_shards.py` and `scripts/ci/wait_for_artifacts.py` read registry shards; the
nightly `full-module-matrix` expands the registry; `module-tests.yml` `timeout-minutes: 58` is
unchanged. No test pins a `consolidation … 1-of-1` artefact name (grep verified).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first: strict length agreement fails for consolidation (782 vs 1617)

- **Purpose**: Make the existing gate demand the fix before the data exists — an honest
  red→green through a gate that already exists, with no new pin (R3 §3.5).
- **Steps**:
  1. In `test_module_length_agreement.py`, delete the `"consolidation": …` entry (line 121) and
     change `_BASELINE_ALLOWLIST_COUNT = 20` to `18` (19 entries − 1). Do not edit the module
     docstring (lines 1-93): `tests/release/pinning_rule_inventory.json` anchors its line 63, and
     its "20 rows" wording is a dated historical record ("measured 2026-09-22").
  2. Run:
     ```bash
     SPEC_KITTY_STRICT_SHARD_TIMINGS=1 uv run --frozen pytest \
       tests/architectural/test_module_length_agreement.py \
       -k "non_allowlisted_modules_agree or does_not_exceed_baseline" -q
     ```
     Expect `test_non_allowlisted_modules_agree_with_live_collection` **red**, with
     `('consolidation', 782, 1617)` in the mismatch list. The session fixture collects every
     registry module, so this takes minutes; it is one gate file, not a heavy suite.
  2a. **Pin the split itself** (the recapture alone must not turn this WP green): add
     `test_consolidation_registry_row_is_split` (`@pytest.mark.fast`, registry read only — no
     collection, so it runs in the always-fast path) next to the charter precedent
     `test_charter_is_not_allowlisted_and_agrees`. It asserts `"consolidation" not in
     _MISMATCH_ALLOWLIST` **and** the `consolidation` row of `_load_registry()["modules"]` has
     `shard_count >= 2`, with a message citing #5510 FR-012. It is red on the planning base
     (`shard_count: 1`) and stays red after T011's recapture; only T012's registry edit greens it.
     The strict length-agreement red above is env-gated (`SPEC_KITTY_STRICT_SHARD_TIMINGS=1`;
     per PR drift is only a warning since #5189), so this unconditional pin is what makes the
     FR-012 deliverable fail closed.
  3. If the red message also lists `charter` or `agent` (drift on main since their last
     recapture), that is pre-existing and **not yours**: confirm it on the planning base, note it
     in the Activity Log and the PR, and do not recapture those modules here.
  4. Commit this red state (message cites #5510 FR-012 and "red-first").
- **Files**: `tests/architectural/test_module_length_agreement.py`.
- **Parallel?**: No — first commit.
- **Notes**: `_BASELINE_ALLOWLIST_COUNT` must equal `len(_MISMATCH_ALLOWLIST)` after the change
  (shrink-only discipline in the comment at :145-150). 18, not 19.
  **Pre-existing Failure Reporting Rule (charter, binding):** such a red needs a GitHub issue — cite the existing one or open one (command, failure summary, why it is pre-existing) — before you continue past it.

### Subtask T011 – Recapture consolidation timings locally

- **Purpose**: Produce the measured, consumer-aligned list (1617 entries) the positional pairing
  needs.
- **Steps**:
  1. Rebase onto the latest planning base first; `tests/terminus` gains tests often, and a capture
     taken before a rebase goes stale immediately.
  2. Confirm the live count right before capturing:
     ```bash
     uv run --frozen python -m pytest tests/consolidation tests/specify_cli/consolidation tests/terminus \
       -m "not performance and not stress" --collect-only -q | grep -c "::"
     ```
  3. Capture (serial, the registry's own `test_dirs` via `resolve_test_dirs`):
     ```bash
     uv run --frozen python scripts/ci/capture_shard_timings.py --module consolidation \
       --run-id landing-5510-consolidation-split --write
     ```
     It runs ~1617 tests serially (CI xunit sum ≈ 788 s; locally usually less). It exits 1 if any
     captured test fails; the data is still complete (every reported test is recorded) but a
     failing consolidation test on the base is a signal: investigate and record it before
     committing.
  4. Inspect the diff: only consolidation's four entries may change
     (`git diff --stat .github/ci-shard-timings.json` plus a JSON diff of the other modules: none).
     Provenance must show `unique_tests_measured == <count from step 2>`,
     `selection == "not performance and not stress"`, the three `test_dirs`, `exit_code: 0`.
  5. Re-run the T010 command: `non_allowlisted…` is now green for consolidation; and
     `test_allowlisted_modules_still_genuinely_mismatch` (run the full file once) stays green.
- **Files**: `.github/ci-shard-timings.json` (written by the producer — never hand-edited).
- **Parallel?**: After T010.
- **Notes**: If the count moved between step 2 and the capture, recapture. The JSON is written
  with `indent=2` plus a trailing newline by the producer; do not reformat it.

### Subtask T012 – Registry `shard_count: 2` with the reasoning comment; prose companion

- **Purpose**: The split itself, documented where the next maintainer looks (the charter style).
- **Steps**:
  1. `.github/ci-module-registry.yml` line 27: `shard_count: 2`. Above it, replace
     `# … shard_count re-measured in T010.` with a comment block recording:
     - `shard_count=2 (#5510 FR-012, partial #5086)`;
     - run-id `landing-5510-consolidation-split`, collected / passed / skipped counts and the
       summed seconds from the capture's stderr line and provenance;
     - CI evidence: recent green runs 15.5-26.2 min serial, xunit sum ≈ 788 s (D-21);
     - the LPT-2 projection from T013 (per-bin seconds and skew);
     - the consequence (R3 §3.3): consolidation is no longer allow-listed, so the scheduled
       `strict-shard-timings-check` hard-fails on future consolidation count drift; per PR it is
       a `ShardTimingsDriftWarning` plus the WP02 loud selector warning; recapture with the
       command above. Follow-up: generalise the scheduled recapture beyond charter (child of
       #5086).
  2. `.github/workflows/ci-charter-shard-recapture.yml` lines 26 and 41: "`agent`, the only other
     non-allowlisted module" → "`agent` and `consolidation`, the other non-allowlisted modules"
     (and "(today, only `agent`)" → "(today, `agent` or `consolidation`)"). This WP owns the file
     (it is in `owned_files`; WP01's stale-prose fix merged before you), so this is an ordinary
     comment-only edit — no out-of-map rationale needed.
  3. Run `uv run --frozen pytest tests/ci/test_recapture_charter_shard_timings.py -q` (workflow
     shape tests must not depend on the comment).
- **Files**: `.github/ci-module-registry.yml` (+ the companion comment edit).
- **Parallel?**: After T011 (needs the capture numbers).
- **Notes**: Keep the change set as tight as `d460f55d91`: no other registry row, no other
  timings module.

### Subtask T013 – Verify the balanced split prediction and record it

- **Purpose**: Show the split balances on the committed data (≤ 20 % skew) and give the NFR-006
  measurement a prediction to compare against.
- **Steps**:
  1. Compute the two LPT bins over the committed list with the shared selector:
     ```bash
     uv run --frozen python - <<'EOF'
     import json
     from scripts.ci.shard_select import lpt_loads
     d = json.load(open(".github/ci-shard-timings.json"))["module_test_durations"]["consolidation"]
     loads = lpt_loads(d, 2)
     print(len(d), round(sum(d), 1), [round(x, 1) for x in loads], f"skew={(max(loads)-min(loads))/max(loads):.2%}")
     EOF
     ```
  2. Expect skew ≈ 0 % (the heaviest single test, ~39 s on CI, cannot unbalance two bins of
     several hundred seconds). Record the line in the registry comment (T012) and the Activity
     Log. Translate to CI wall-clock with the ratio R3 used: CI xunit ≈ 788 s total → ≈ 394 s of
     tests per shard plus ~3 min setup/coverage ≈ 10 min per shard expected, against the NFR-006
     bound p90 ≤ 15 min per shard, shards within 25% of each other.
  3. Run `uv run --frozen pytest tests/architectural/test_module_shard_registry.py -q` —
     `test_inter_shard_skew_within_twenty_percent` must be green, and it now checks
     consolidation as a multi-shard module.
  4. Leave a note in the Activity Log naming the CI jobs to measure for NFR-006:
     `module-tests (consolidation shard 1/2)` and `(… 2/2)`, ≥ 3 runs, p90 ≤ 15 min per shard and shard balance within 25%, run IDs
     recorded in the Mission evidence file (C-011).
- **Files**: none beyond T012's comment.
- **Parallel?**: With T012.
- **Notes**: 3 shards were rejected (R3 §3.6): unnecessary for the measured weight and more
  runner start-up overhead.

## Test Strategy

```bash
SPEC_KITTY_STRICT_SHARD_TIMINGS=1 uv run --frozen pytest tests/architectural/test_module_length_agreement.py -q
uv run --frozen pytest tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_coverage_artefact_contract.py tests/architectural/test_module_tests_matrix.py -q
uv run --frozen pytest tests/ci/test_ci_module_wiring.py tests/ci/test_wait_for_artifacts.py \
  tests/ci/test_reconcile_shards.py tests/ci/test_recapture_charter_shard_timings.py tests/ci/test_shard_select.py -q
make test-fast
uv run --frozen ruff check tests/architectural/test_module_length_agreement.py
uv run --frozen ruff format --check .
python3 -c "import json,yaml; json.load(open('.github/ci-shard-timings.json')); yaml.safe_load(open('.github/ci-module-registry.yml'))"
```

- In strict mode, a red for `charter`/`agent` that is also red on the planning base is
  pre-existing (classify per CLAUDE.md "baseline-red gotcha"); a red for `consolidation` is yours.
- WP02's characterization test (`tests/ci/test_shard_select.py`) reads every registry row at its
  `shard_count`; it must stay green with consolidation at 2.

## Risks & Mitigations

- **Count drift before merge** (new `tests/terminus` repros on main): recapture after the final
  rebase; reviewer re-runs the collect-only count and compares to `module_test_count.consolidation`.
- **Strict scheduled check reds on future drift** (R3 §3.3): accepted and documented; per-PR stays
  a warning; follow-up under #5086.
- **A failing consolidation test during capture**: the producer records it anyway (exit 1); treat
  it as a base-red classification task, not as noise.
- **Wrong baseline number**: 18, verified by counting the dict after the edit
  (`len(_MISMATCH_ALLOWLIST) == _BASELINE_ALLOWLIST_COUNT`).

## Review Guidance

- **Red on planning base, green on WP tip**: at the T010 commit, the strict command lists
  `('consolidation', 782, 1617)`; at the tip it does not. `test_consolidation_registry_row_is_split`
  is red at the T010 commit **and** after the T011 recapture commit, green only from T012.
- `git show --stat` of the WP: registry, timings, `test_module_length_agreement.py` and the
  comment-only `ci-charter-shard-recapture.yml` edit only; the timings diff touches consolidation's four entries only.
- Provenance: run-id `landing-5510-consolidation-split`, aligned `selection`, `exit_code: 0`,
  `unique_tests_measured` equal to the live count at review time (re-run the collect-only).
- `_BASELINE_ALLOWLIST_COUNT == 18 == len(_MISMATCH_ALLOWLIST)`.
- Registry comment carries the evidence and the LPT projection; skew gate green.
- FR-012 acceptance (two balanced shards, recaptured timings, checked length). NFR-006 is
  measured on CI later — the review does not accept a local claim for it.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
