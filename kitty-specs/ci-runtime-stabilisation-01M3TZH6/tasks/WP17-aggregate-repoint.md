---
work_package_id: WP17
title: CI Aggregate re-points to the matched run
dependencies:
- WP16
requirement_refs:
- FR-011
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-runtime-stabilisation-01M3TZH6
base_commit: 7b0992d2fcd1ff07c4abaae600812548510a4108
created_at: '2026-10-01T09:28:17.463023+00:00'
subtasks:
- T069
- T070
- T071
phase: Phase 7 - Skip-if-green
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-aggregate.yml
- tests/ci/test_aggregate_attempts.py
- tests/architectural/test_coverage_artefact_contract.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP17 – CI Aggregate re-points to the matched run

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

When CI Modules is a **skip run** (WP18), its empty matrix reaches `reconcile_shards.py` with
`selected=[]`. The result is `complete=true, coverage=false`, so `diff-cover` is skipped and
`aggregate-gate` stays green (R3 §0.2). That is a silent coverage drop. This WP closes it before
any workflow can produce a skip run (D-30 sequencing: helper → **Aggregate re-point** → wiring).

Done means:

1. `ci-aggregate.yml` `collect` has a new step, `id: effective-source`, immediately after
   checkout. It runs `python3 scripts/ci/green_match.py effective-source` (WP16) for the
   triggering CI Modules run attempt.
2. Every source-run reference inside `collect` reads `steps.effective-source.outputs.run-id` /
   `run-attempt` instead of `github.event.workflow_run.id || inputs.source_run_id` (and the
   attempt twin). This covers four `env:` blocks and two `run-id:` inputs.
3. Step names, step ids and env var **names** are unchanged. `SOURCE_RUN_ID`,
   `SOURCE_RUN_ATTEMPT` and `SOURCE_REPOSITORY` stay as they are, because
   `tests/ci/test_aggregate_attempts.py` executes these step bodies and
   `scripts/ci/wait_for_artifacts.py:178-180` reads the env names.
4. `run-name` (line 53) and `concurrency` (lines 78–80) are byte-unchanged. Fleet Verdict binds
   the aggregate by the **skip** run's display title (`scripts/ci/fleet_verdict.py:275-291`).
5. An unverifiable green-match marker **fails `collect`** with "re-run CI Modules to execute",
   never an empty-selection green. A source without a marker behaves byte-identically to today.
6. The step-execution test proves both the re-point and the failure, offline, over the fake-`gh`
   harness.

Acceptance anchors: FR-011 ("coverage aggregation reusing the matched run's coverage
artifacts"), spec scenario 4, D-15, D-16. Live verification of this half is a post-merge
follow-up, recorded by WP18: `workflow_run` executes `main`'s copy of this file.

## Context & Constraints

Read, in order:

- `research.md`: the decision log D-15, D-16, D-30, then R3 §0.2–§0.3, §1.4 and §1.7.
- `contracts/green-match.md`, section "Workflow integration", the CI Aggregate bullet.
- WP16's `scripts/ci/green_match.py` (`effective-source` CLI and output keys `run-id`,
  `run-attempt`, `repointed`, `matched-run-url`). Read its tests first; they are the interface.

Live anchors in `.github/workflows/ci-aggregate.yml` (675 lines), verified 2026-10-01. The line
numbers drifted about 120 lines from research R3 §1.4, so anchor by step name and id:

| Anchor | Line | Current source-run reference |
|---|---|---|
| `run-name:` | 53 | `github.event.workflow_run.id \|\| inputs.source_run_id` (**keep**) |
| `concurrency.group` | 79 | `workflow_run.head_branch \|\| github.ref` (**keep**) |
| `collect` job, `permissions: {contents: read, actions: read}` | 91–95 | already has `actions: read` |
| `collect` job `if:` | 97–101 | reads `workflow_run.conclusion` (job-level, **keep**) |
| checkout | 109 | — |
| step "Prepare exact source registry and diff …" | 111–123 | `env.SOURCE_RUN_ID/ATTEMPT` at 114–115 |
| step `select-current` | 148–161 | `env` at 152–153 |
| step `download-selected-modules` | 163–172 | `with.run-id` at 172 |
| step `wait-for-artifacts` | 185–200 | `env` at 194–195 |
| step `download-current` | 202–212 | `with.run-id` at 212 |
| step `last-success` | 214–243 | `TRIGGER_JSON: toJSON(github.event.workflow_run)`: provenance of the trigger, **keep** |
| step `download-previous` | 245–255 | `run-id: steps.last-success.outputs.run-id` (**keep**) |
| `sonar-pr` job | 431+ | reads `github.event.workflow_run.*` for the PR condition (**keep**; re-upload on skip runs accepted, D-16) |

Facts that make the re-point sound:

- `source_eligibility.py:129-130` returns `NotAMainSource` for `event == pull_request`, so a
  skip run can never become a backfill source. `last-success` stays bound to the trigger.
- `prepare_source` (`aggregate_source.py:71-79`) validates that `run.id`/`run_attempt` equal the
  `--run-id`/`--attempt` it is given. After the re-point, the Prepare step fetches **and**
  validates the matched attempt consistently.
- Both runs are CI Modules runs and carry an immutable `referenced_workflows` merge reference,
  including a zero-selection run. Run `36823737462` was verified live.
- The harness in `tests/ci/test_aggregate_attempts.py`:
  - `collect()` (lines 84–161) builds a fake `gh` whose response is keyed on the exact
    `repos/...` endpoint string (lines 104–109). Pages print newline-joined.
  - It runs the steps by **name prefix** (`"Prepare exact source"`, line 124) and by **id**
    (`select-current`, `download-current`, `reconcile`).
  - It sets `SOURCE_RUN_ID=42` / `SOURCE_RUN_ATTEMPT=2` directly in the process env
    (lines 117–118). It does **not** evaluate step `env:` expressions, so existing rows are
    unaffected by the re-point. Your extension must thread the effective-source outputs through
    explicitly, to model the expression honestly.

Constraints:

- No new workflow file (17/20) and no new job: `aggregate-gate`'s `needs` set-equality assertion
  must not move.
- Reuse the pinned action SHAs already in the file.
- The `gh api` calls must stay inside the trusted checkout. Do not check out PR code.
- `tests/architectural/test_coverage_artefact_contract.py:754` pins header prose
  (`fallback`/`collision`). **Append** to the header comment; never rewrite it.
- Use "Mission", never "feature". Never write bare "routing".

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T069 – Red-first: execute the step bodies with a green-match marker fixture

- **Purpose**: Prove, offline, that the shipped `collect` steps aggregate the matched run when
  the source carries a marker, and fail closed when it cannot be verified (R3 §1.8.3).
- **Steps**:
  1. Extend the `collect()` helper in `tests/ci/test_aggregate_attempts.py` without changing its
     existing call signature. Add keyword-only `source_run_id: int = 42`, `extra_api: dict | None = None`
     and `artifacts_by_run: dict[int, list] | None = None`. Then:
     - if a step with `id == "effective-source"` exists, run its `run:` body first with env
       `TRIGGER_RUN_ID`, `TRIGGER_RUN_ATTEMPT` and `SOURCE_REPOSITORY` (match the env names you
       choose in T070), `GH_TOKEN=dummy`, and `GITHUB_OUTPUT` set to a separate file;
     - parse that output and set `SOURCE_RUN_ID`/`SOURCE_RUN_ATTEMPT` for every later step from
       `run-id`/`run-attempt`, which models the re-pointed `${{ steps.effective-source.outputs.* }}`
       expressions;
     - if the step exits non-zero, return its `CompletedProcess`, because `collect` stops there.
  2. The fake API needs these extra keys. Use the WP16 endpoint strings verbatim; read them
     from `green_match.py`:
     - `repos/spec-kitty/spec-kitty/actions/runs/<id>/attempts/<n>` for the skip run (id 41,
       attempt 1);
     - `repos/spec-kitty/spec-kitty/actions/runs/41/artifacts?per_page=100`, holding
       `selected-modules` and `ci-green-match-run-42-attempt-2`;
     - `repos/spec-kitty/spec-kitty/git/commits/<merge>` for each merge SHA, with parents
       read from the real fixture repo (`source_fixture` builds a genuine merge commit). For the
       skip run, create a second merge commit with **the same parents** but a different message.
       That gives a different SHA with the same tested identity, and proves the comparison is on
       `(pr, head, base)`.
  3. New tests:
     - `test_green_match_source_is_repointed_to_the_matched_run`: the source is skip run 41 and
       the marker names 42/2. Expect `resolved 2/2` and `out/aggregate/source/source.json`
       `run_id == 42`.
     - `test_unverifiable_green_match_fails_collect`, parametrised over: `missing-run`,
       `matched-failed`, `different-head`, `different-workflow`, `different-tested-base`,
       `two-markers`. Expect a non-zero exit, `re-run CI Modules to execute` in the output, and
       no `out/aggregate/source/source.json`.
     - `test_marker_from_an_earlier_attempt_does_not_repoint`. The skip marker's `created_at`
       is before the requested attempt's `run_started_at` (WP16 row A4). Expect a normal,
       non-re-pointed collect of run 41's own evidence.
     - `test_dispatch_replay_of_a_skip_run_repoints` (A3, `event="workflow_dispatch"`).
     - `test_no_marker_source_is_byte_identical_to_today` (A2). The existing
       `test_partial_rerun_collects_carried_forward_shard_and_latest_replacement` rows must pass
       through the effective-source step with `repointed=false`.
  4. Run and record red: `uv run --frozen pytest tests/ci/test_aggregate_attempts.py -q`. The
     new tests fail because no `effective-source` step exists. Commit the red tests first.
- **Files**: `tests/ci/test_aggregate_attempts.py`.
- **Parallel?**: No.
- **Notes**:
  - Keep `pytestmark = pytest.mark.fast` (the file's precedent; it already spawns subprocesses).
  - Keep the fake-`gh` script generic: it must still answer `--paginate` calls with
    newline-joined pages. The WP16 `GhTransport` parses concatenated JSON.
  - Do not touch `tests/ci/test_aggregate_source.py`. WP16 owns it, and `source_fixture` is
    imported unchanged.

### Subtask T070 – Add the step and re-point every source-run reference in `collect`

- **Purpose**: Make T069 green with the smallest workflow diff.
- **Steps**:
  1. Insert this step right after the checkout at line 109:
     ```yaml
     - name: Resolve the effective source run (skip-if-green re-point; mission ci-runtime-stabilisation FR-011)
       id: effective-source
       env:
         GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
         TRIGGER_RUN_ID: ${{ github.event.workflow_run.id || inputs.source_run_id }}
         TRIGGER_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt || inputs.source_run_attempt }}
         SOURCE_REPOSITORY: ${{ github.repository }}
       shell: bash
       run: |
         set -euo pipefail
         [[ "$TRIGGER_RUN_ID" =~ ^[1-9][0-9]*$ && "$TRIGGER_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]]
         python3 scripts/ci/green_match.py effective-source --transport gh \
           --repository "$SOURCE_REPOSITORY" --run-id "$TRIGGER_RUN_ID" --attempt "$TRIGGER_RUN_ATTEMPT" >> "$GITHUB_OUTPUT"
     ```
     Match the exact CLI flags WP16 shipped. If WP16 did not ship `--transport`, drop it.
  2. Replace the value, and only the value, in:
     - Prepare: `SOURCE_RUN_ID` and `SOURCE_RUN_ATTEMPT` (114–115);
     - `select-current` (152–153);
     - `wait-for-artifacts` (194–195);
     - `download-selected-modules` `run-id` (172);
     - `download-current` `run-id` (212).

     The new values are `${{ steps.effective-source.outputs.run-id }}` and
     `${{ steps.effective-source.outputs.run-attempt }}`.
  3. Leave `run-name`, `concurrency`, the job `if:`, `last-success` (`TRIGGER_JSON`),
     `download-previous`, `diff-cover`, `sonar-pr` and `aggregate-gate` unchanged.
  4. Append a header paragraph after line 50, titled "SKIP-IF-GREEN RE-POINT (mission
     ci-runtime-stabilisation, FR-011)". It should say:
     - a CI Modules skip run carries `ci-green-match-run-<id>-attempt-<n>`;
     - `effective-source` re-verifies head, workflow, event, success and tested identity, then
       aggregates the matched attempt;
     - an unverifiable marker fails `collect`;
     - `run-name` deliberately stays on the skip run for Fleet Verdict.
  5. Run `uv run --frozen pytest tests/ci/test_aggregate_attempts.py -q`. Everything is green,
     including every pre-existing row.
- **Files**: `.github/workflows/ci-aggregate.yml`.
- **Parallel?**: No.
- **Notes**:
  - `tests/ci/test_workflow_script_import_guard.py` now discovers `scripts/ci/green_match.py`
    as a workflow-invoked bare script. It is stdlib-only (WP16 T068), so the guard only asserts
    it exists. Run the guard.
  - The trusted checkout runs `main`'s `green_match.py` in production. Until this mission
    merges, nothing calls the step, which is why live proof is post-merge.

### Subtask T071 – Fail closed, no empty-selection green; pin the shape statically

- **Purpose**: Make the failure mode explicit and pin the wiring so a later edit cannot silently
  revert one reference (R3 §1.7, §1.8.2 aggregate half).
- **Steps**:
  1. Add the following to `tests/architectural/test_coverage_artefact_contract.py`, using the
     existing `_aggregate_yaml()`/`_aggregate_text()` helpers.
     - `test_ci_aggregate_collect_resolves_effective_source_first`: the first non-checkout step
       of `collect` has `id == "effective-source"`, and its `run` invokes
       `scripts/ci/green_match.py effective-source`.
     - `test_ci_aggregate_collect_reads_source_only_through_effective_source`:
       - for every `collect` step other than `effective-source`, no `env` value and no
         `with.run-id` contains `github.event.workflow_run.id` or `inputs.source_run_id`;
       - every `SOURCE_RUN_ID`/`SOURCE_RUN_ATTEMPT` env value and every `with.run-id` except
         `download-previous` contains `steps.effective-source.outputs.`.
     - `test_ci_aggregate_run_name_stays_bound_to_the_trigger`: assert the literal `run-name`
       string at line 53 is unchanged (Fleet Verdict binding, `fleet_verdict.py:285`).
  2. Re-run and keep green: `test_ci_aggregate_downloads_reports_glob_pattern` (line 155,
     satisfied by `download-previous`), `test_ci_aggregate_declares_workflow_dispatch_and_honors_mode`
     (168), `test_ci_aggregate_empty_selection_skips_coverage_consumers` (213),
     `test_ci_aggregate_all_actions_sha_pinned` (242) and
     `test_ci_aggregate_embeds_stale_fallback_and_collision_guard_language` (754).
  3. Confirm by reading `green_match.py` that every effective-source error path exits 1 before
     any later step runs. Because `collect` fails, `diff-cover` short-circuits in `pr` mode
     (its job `if:` requires `needs.collect.result == 'success'`), and `aggregate-gate` reports
     failure. The aggregate is never green with `coverage=false` for a skip run.
- **Files**: `tests/architectural/test_coverage_artefact_contract.py`.
- **Parallel?**: It can be written alongside T070.
- **Notes**:
  - `tests/ci/test_sonar_pr_analysis.py`, `tests/release/test_sonar_workflow.py`,
    `tests/ci/test_fleet_verdict.py`, `tests/ci/test_source_eligibility.py` and
    `tests/ci/test_wait_for_artifacts.py` read `ci-aggregate.yml`. Run them; they should stay
    green unchanged.
  - `tests/architectural/test_dual_mode_contract.py` and `test_suite_jobs_gate_blocking.py` also
    parse this file. Run those two specific files.

## Test Strategy

Red-first: commit T069's failing tests before T070.

```bash
uv run --frozen pytest tests/ci/test_aggregate_attempts.py tests/ci/test_aggregate_source.py tests/ci/test_green_match.py -q
uv run --frozen pytest tests/ci/test_workflow_script_import_guard.py tests/ci/test_sonar_pr_analysis.py tests/ci/test_fleet_verdict.py tests/ci/test_source_eligibility.py tests/ci/test_wait_for_artifacts.py tests/ci/test_fork_guard.py -q
uv run --frozen pytest tests/architectural/test_coverage_artefact_contract.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_suite_jobs_gate_blocking.py -q
uv run --frozen pytest tests/release/test_sonar_workflow.py tests/release/test_release_ci_ownership.py -q
uv run --frozen ruff check tests/ci/test_aggregate_attempts.py tests/architectural/test_coverage_artefact_contract.py
uv run --frozen ruff format --check tests/ci/test_aggregate_attempts.py tests/architectural/test_coverage_artefact_contract.py
make test-fast
```

Pinning inventory: `ci-aggregate.yml` is referenced by four inventory rules. Run
`python3 scripts/ci/derive_pinning_inventory.py --check`. It is green on base `bc826fcbcb`
(#5523 closed by `e3794ded2d`, D-37; WP19 regenerates last). Verify your diff adds no delta with
`--check` (or `--stdout` plus `diff` against the base when it is red). **Never regenerate the inventory in this
WP** (tasks.md Global rules). If your diff does add a delta (for example a shifted line in one of
the four `ci-aggregate.yml` rules), record the rule names and the cause in the Activity Log so
WP19's final regeneration can check them — do not commit `tests/release/pinning_rule_inventory.json`.

Never run `tests/architectural` as a directory, and never run `make test-full`.

## Risks & Mitigations

- **A reference is missed and still reads the trigger.** The aggregate then mixes the skip run's
  empty selection with the matched run's reports. Mitigation: T071's static test enumerates
  every `env`/`with.run-id`.
- **`run-name` is "fixed" to the matched run.** That breaks Fleet Verdict's binding. Mitigation:
  a literal pin.
- **The harness models the expression dishonestly.** Mitigation: thread the outputs from the
  executed step's real `$GITHUB_OUTPUT`, never hard-code 42.
- **The cancelled sibling aggregate.** A skip run's aggregate can cancel the still-running
  matched aggregate (same head-branch concurrency group). This is harmless: the survivor
  computes the same verdict (R3 §1.4). Do not change concurrency.
- **Cannot be proven on the mission PR.** `workflow_run` runs `main`'s file. While the mission
  PR is open, a CI Modules skip run feeds main's **old** aggregate, which goes green with
  `coverage=false`. That run is **not** FR-011 evidence (R3 §1.8 caveat). WP18 records the
  post-merge follow-up.

## Review Guidance

- Diff `ci-aggregate.yml`: one new step, one header paragraph, and six value substitutions.
  Nothing else.
- Confirm the step names and env names are unchanged, and that `TRIGGER_RUN_*` is used only
  inside `effective-source`.
- Confirm the A1 rows fail with the "re-run CI Modules to execute" text and that A2 is
  byte-identical.
- Confirm the implementer recorded that live verification is post-merge, and did not claim
  pre-merge live proof.

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

**Example (correct chronological order)**:

```
- 2026-01-12T10:00:00Z – system – Prompt created
- 2026-01-12T10:30:00Z – claude – Started implementation
- 2026-01-12T11:00:00Z – codex – Implementation complete, ready for review
- 2026-01-12T11:30:00Z – claude – Review passed, all tests passing  ← LATEST (at bottom)
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T07:30:00Z – system – Prompt generated via /spec-kitty.tasks

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

### Optional Phase Subdirectories

For large missions, organize prompts under `tasks/` to keep bundles grouped while maintaining lexical ordering.
