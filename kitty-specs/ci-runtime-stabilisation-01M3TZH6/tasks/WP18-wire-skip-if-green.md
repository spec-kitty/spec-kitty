---
work_package_id: WP18
title: Wire skip-if-green into router, modules and packs
dependencies:
- WP12
- WP17
requirement_refs:
- FR-011
- SC-005
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
subtasks:
- T072
- T073
- T074
- T075
- T076
phase: Phase 7 - Skip-if-green
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_skip_if_green_wiring.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/packs.yml
- .github/workflows/ci-modules.yml
- tests/ci/test_skip_if_green_wiring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP18 – Wire skip-if-green into router, modules and packs

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

On a `pull_request` `ready_for_review` event whose tested key `(workflow, PR, head SHA, merge-commit
first parent)` already has a successful run of the same workflow, the three selection jobs
suppress their path-filter step. Every path-gated job then skips, and the required gates still
post success. This is the last of the three skip-if-green steps (D-30): helper (WP16), then
Aggregate re-point (WP17), then **this wiring**. Wiring before the re-point would silently drop
diff-cover, which is why this WP depends on WP17.

Done means:

1. Router `changes`, Packs `changes` and CI Modules `generate-matrix` each run a first step,
   `id: green`, immediately after checkout. The step runs
   `python3 scripts/ci/green_match.py decide --workflow <own file>` and carries
   `continue-on-error: true`, so a crashed helper means "run normally".
2. Each of these three jobs has job-level `permissions: {contents: read, actions: read}`. A
   job-level block replaces the workflow-level grant, so `contents` is restated, following the
   `ci-modules.yml` `summarize` precedent at lines 415–425.
3. On skip:
   - every step whose outputs feed the job's `outputs:` is skipped by
     `if: steps.green.outputs.skip != 'true'`;
   - the one exception is the ci-modules `build` step, which instead forces an empty selection
     from a `GREEN_SKIP` env var and still publishes `selected-modules.json = []`.
4. Every run with a non-empty `steps.green.outputs.marker` uploads that artifact:
   - executing `pull_request` runs upload `ci-tested-key-pr<N>-base-<sha>`;
   - skip runs upload `ci-green-match-run-<id>-attempt-<n>`;
   - non-PR and unbound runs upload nothing.
5. **No job `if:`, no `needs:` and no `changes.outputs` expression changes.** No new job, no new
   filter group, no new workflow file. `pull_request.types` still lists `ready_for_review`.
6. Golden lane tests, fork-guard tests, router-gate `needs` tests, the gate-selection authority
   and transcription guards all stay green **unchanged**.
7. The DoD records that **live verification of the CI Aggregate half is a post-merge follow-up**
   (see T076).

Acceptance anchors: FR-011, SC-005 ("an already-green commit marked ready for review consumes no
expensive CI jobs"), spec scenarios 4–5, the Edge Cases (in-progress, re-run/dispatch, moved
base), C-003 (no third CI path routing authority), D-15, D-16, D-30.

## Context & Constraints

Read, in order:

- `research.md`: the decision log D-15, D-16, D-30, then R3 §1.1, §1.2 (why the fold lives on a
  **step**: `scripts/ci/gate_selection.py:52` `_GROUP_REF` would mis-parse any
  `needs.changes.outputs.skip` in a job `if:` as a CI path routing group), §1.7 and §1.8.
- `contracts/green-match.md` and `contracts/router-two-authority-amendment.md` A4 (event-level
  suppression is not a third authority).
- The WP16 helper `scripts/ci/green_match.py` (`decide` CLI, outputs `skip`, `reason`, `marker`,
  `matched-run-id`, `matched-run-attempt`, `matched-run-url`; marker JSON written to
  `--marker-dir`) and the WP17 `ci-aggregate.yml` re-point.

Live anchors. Anchor by **job and step id**, never by line. WP07, WP08, WP09, WP10 and WP12
rewrite parts of `ci-router.yml` and `packs.yml` before this WP, so the line numbers below are
the 2026-10-01 base, for orientation only.

- `ci-router.yml`:
  - `on.pull_request.types: [opened, synchronize, reopened, ready_for_review]` (line 21);
  - workflow `permissions: contents: read` (41–42);
  - `changes` job (57), whose `outputs` all have the shape
    `(inputs.mode == 'full' || steps.unmatched.outputs.unmatched == 'true') && 'true' || steps.filter.outputs.<g>`,
    plus `unmatched: ${{ steps.unmatched.outputs.unmatched }}`;
  - steps: checkout (depth 1), dorny `id: filter`, and `id: unmatched` ("Compute fail-closed
    catch-all unmatched signal").

  On a PR, `inputs.mode` is `''`. With `filter` and `unmatched` skipped, every group output
  evaluates to `''`, so every `needs.changes.outputs.X == 'true'` gate is false.
- `ci-router.yml` `prose-scan` job (288). It does **not** need `changes`, and runs on every PR.
  `tests-docs` (665, `if: docs == 'true' || prose_only == 'true'`) can therefore still run on a
  prose-only skip run. The always-on lanes also still run: ruff, commit-msg, markdownlint,
  uv-lock, import-linter, regen-check, terminology, docs-lint, layer-rules, archive-freeze, and
  WP12's `architectural-fast`. See T076.
- `ci-router.yml` `router-gate`. It reads job conclusions through `scripts/ci/router_gate.py`,
  where `skipped` is non-blocking.
- `ci-modules.yml`:
  - `types` (49);
  - `generate-matrix` (89–320): checkout `fetch-depth: 0`, "Install PyYAML", `id: resolve-mode`,
    `id: changed-files` (with an `if:` on mode / selection-forced-full), `id: build` (a Python
    heredoc; changed-files outcome `skipped` is accepted), and the "Publish the selected-module
    set" upload;
  - `test` (331), gated on `has-selection`;
  - `modules-gate` (362), which blocks only on failure/cancelled;
  - the `workflow_call` trigger (52), used by the nightly. A called workflow sees the caller's
    event name, so `decide` returns Run (N1).
- `packs.yml`:
  - `types` (40);
  - `changes` (71–98): checkout, dorny `id: filter`, outputs
    `(inputs.mode == 'full' || github.event_name == 'push') && 'true' || steps.filter.outputs.<g>`.

  **After WP09/WP10** `changes` also computes `corpus` via `scripts/ci/corpus_select.py`, behind a
  pre-sync step. Guard that step too: the rule is "every step feeding `outputs:`".
- The pinned upload action is
  `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1`. Reuse exactly this
  pin.

Constraints:

- C-003: two CI path routing authorities only. Never put `green`/`skip` into a filter block, a
  job `if:`, or `changes.outputs`.
- C-004: the battery stays non-required.
- The workflow count stays 17/20.
- **Pinned-file lane discipline (D-25)**: this WP does not edit `_gate_coverage.py`,
  `_ci_integrity_oracle.py` or `test_no_duplicate_suite_execution.py`.
- Use "Mission", never "feature". Never write bare "routing": write "CI path routing",
  "selection-step suppression" or "gate selection".

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T072 – Red-first: workflow-shape tests for all three selection jobs

- **Purpose**: Pin the wiring structurally before editing YAML (R3 §1.8.2). The checks are
  derived by construction from each job's `outputs:`, so a future output-producing step cannot
  silently escape the guard.
- **Steps**:
  1. Create `tests/ci/test_skip_if_green_wiring.py` with `pytestmark = pytest.mark.fast`. Parse
     the workflows with `yaml.safe_load`. Use a parametrised table:
     `("ci-router.yml", "changes")`, `("packs.yml", "changes")`,
     `("ci-modules.yml", "generate-matrix")`.
  2. Write one test per assertion, each parametrised over the three rows:
     - `test_green_step_runs_first_after_checkout`: the first non-checkout step has `id == "green"`;
       its `run` contains `scripts/ci/green_match.py decide --workflow <own filename>`; it has
       `continue-on-error: true` and `env.GH_TOKEN`.
     - `test_selection_job_grants_actions_read`: the job `permissions == {"contents": "read", "actions": "read"}`.
     - `test_every_output_producing_step_is_suppressed_on_skip`:
       - collect `steps\.([\w-]+)\.outputs` ids from the job's `outputs:` values, transitively
         through step `env` references such as `ANY_SRC: ${{ steps.filter.outputs.any_src }}`;
       - every such id other than `green` must have `steps.green.outputs.skip != 'true'` in its
         `if:`;
       - the one allowed exception is ci-modules `build`, which must instead declare
         `env.GREEN_SKIP: ${{ steps.green.outputs.skip }}`;
       - every `dorny/paths-filter` step and `changed-files` is guarded regardless.
     - `test_marker_artifact_is_uploaded`: an upload step using the pinned upload-artifact SHA,
       with `if: steps.green.outputs.marker != ''`, `with.name: ${{ steps.green.outputs.marker }}`,
       `retention-days: 30` and `if-no-files-found: error`.
     - `test_no_job_condition_references_the_green_step`: across **all** jobs of the workflow, no
       job-level `if:`, no `needs` and no `outputs` value mentions `green` or `outputs.skip`.
       This pins the `_GROUP_REF` safety.
     - `test_ready_for_review_stays_a_trigger`: `ready_for_review` is in `on.pull_request.types`.
       Remember the PyYAML `on:` → `True` quirk; copy the helper in
       `test_coverage_artefact_contract.py:173-178`.
  2a. **Skip-context golden test** — `test_skip_context_turns_every_path_gated_job_off`: on a
     skip run the suppressed filter step leaves every selection-job output as the **empty
     string**. Reuse the existing GitHub `if:` evaluator — `_eval_gh_if` / `_GhIfEvaluator` in
     `tests/ci/test_ci_module_wiring.py:258-316` — by importing it (do not copy it; that file is
     not owned here). For each workflow, find every job whose `if:` references
     `needs.<selection job>.outputs.` (router: `architectural-heavy`, the corpus/e2e/docs and
     remaining code-scoped jobs; packs: the `built_in` / `internal` jobs), build a context with
     **every** `<selection job>.<output>` key = False (the evaluator's `== 'true'` / `!= 'true'`
     semantics treat `''` exactly like False), and assert each `if:` evaluates **False**. Derive
     the job set from the `if:` text, never a hand list, and assert it is non-empty per workflow.
     Two known edges — handle them explicitly, never by skipping a job:
     - router `prose-scan` is **not** suppressed by the green step (it computes `prose_only`
       itself; D-35 records "on a skip run the always-on lanes and `prose-scan` still run" as a
       residual), so evaluate with `prose-scan.prose_only` both False and True. Under False,
       every path-gated job is off. Under True, pin the residual **exactly**: the set of jobs
       that still evaluate True must equal `{"tests-docs"}` (its `if:` is
       `docs == 'true' || prose_only == 'true'`), with a comment citing D-35 — so any new leak
       reds the test instead of joining a silent allowlist. Mention this residual in the DoD;
     - ci-modules' downstream `if:` uses the hyphenated output `has-selection`, which the
       evaluator's `_COND_RE` (`[A-Za-z0-9_]+`) does not model (it asserts). Do not widen the
       regex here (not owned); assert that job's `if:` is exactly
       `${{ needs.generate-matrix.outputs.has-selection == 'true' }}` (false for `''`), or ask
       the orchestrator to have the regex widened by the file's owner.
  3. Add `test_suppression_checker_catches_an_unguarded_step`. Copy the router `changes` job
     dict, delete the `if:` from the `filter` step, and assert the checker helper reports
     `filter`. This is the positive control (Standing Order #5).
  4. Run it red: `uv run --frozen pytest tests/ci/test_skip_if_green_wiring.py -q`. Commit the
     red tests first.
- **Files**: `tests/ci/test_skip_if_green_wiring.py` (new).
- **Parallel?**: No.
- **Notes**:
  - Keep the checker a pure helper function with complexity ≤ 15.
  - Do not assert line numbers.
  - The ADR-prose pin suggested in R3 §4.6 is optional. Do **not** add it here: WP19 writes that
    ADR later, and a pin on prose that does not exist yet would be red until then.

### Subtask T073 – Router `changes` wiring

- **Purpose**: Suppress the router's path-to-group step on a green match without touching
  either CI path routing authority's content.
- **Steps**:
  1. Add to the `changes` job: `permissions: {contents: read, actions: read}`.
  2. After the checkout, insert:
     ```yaml
     - name: Skip-if-green on ready-for-review (selection-step suppression; FR-011)
       id: green
       continue-on-error: true
       env:
         GH_TOKEN: ${{ github.token }}
       run: python3 scripts/ci/green_match.py decide --workflow ci-router.yml --marker-dir "$RUNNER_TEMP/green-match"
     ```
  3. Add `if: steps.green.outputs.skip != 'true'` to the dorny `id: filter` step and the
     `id: unmatched` step. If a step already has an `if:`, AND the new condition into it.
  4. Add the marker upload step after `unmatched`:
     ```yaml
     - name: Upload the skip-if-green marker (tested key or matched run)
       if: steps.green.outputs.marker != ''
       uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
       with:
         name: ${{ steps.green.outputs.marker }}
         path: ${{ runner.temp }}/green-match/
         retention-days: 30
         if-no-files-found: error
     ```
  5. Append to the header comment (lines 1–16) one paragraph. It should say that skip-if-green
     is an **event-level selection-step suppression**, like the fork guard, and not a third
     authority, and that `gate_selection.py` deliberately does not model it. Cite
     `contracts/router-two-authority-amendment.md` A4.
  6. Run the router companions listed in the Test Strategy.
- **Files**: `.github/workflows/ci-router.yml`.
- **Parallel?**: It can be done in either order with T074 and T075; it is the same review unit.
- **Notes**:
  - The checkout is depth 1. The helper resolves the merge parents through the REST commits API,
    never `HEAD^1`, which avoids the shallow-graft problem.
  - `gate_selection._dorny_filters` (`scripts/ci/gate_selection.py:98-105`) finds the filter by
    `uses:`, so an added `if:` does not affect it.

### Subtask T074 – Packs `changes` wiring

- **Purpose**: The same suppression for Packs.
- **Steps**:
  1. Add the job permissions, the `green` step (`--workflow packs.yml`) and the marker upload,
     exactly as in T073.
  2. Guard the dorny `id: filter` step. Then guard **every other step whose outputs feed
     `changes.outputs`**, including the WP09 corpus-selection step and any install step that
     exists only to feed it. Guarding the install step is optional but saves time. The T072
     checker tells you whether you missed one.
  3. Check every output expression. The current shape reduces to `''` on a PR when the filter is
     skipped. If WP09 introduced a different fold for `corpus`, confirm it also reduces to `''`
     (or `'false'`) when its step is skipped, and record that in the Activity Log.
- **Files**: `.github/workflows/packs.yml`.
- **Parallel?**: See T073.
- **Notes**:
  - `tests/architectural/test_pycache_sweep.py` pins a Packs step against the on-disk YAML. Run it.
  - `packs gate` blocks only on failure/cancelled (`packs.yml` gate job), so all-skipped means
    success.

### Subtask T075 – CI Modules `generate-matrix` wiring

- **Purpose**: An empty module selection on skip, while still publishing `selected-modules` for
  Aggregate (WP17 re-points to the matched run).
- **Steps**:
  1. Add the job permissions, the `green` step (`--workflow ci-modules.yml`) and the marker
     upload, as in T073. Place `green` after checkout and **before** "Install PyYAML": the helper
     needs no packages.
  2. `changed-files`: extend its existing `if:` to
     `${{ steps.resolve-mode.outputs.mode != 'full' && steps.resolve-mode.outputs.selection-forced-full != 'true' && steps.green.outputs.skip != 'true' }}`.
  3. `build`: add `GREEN_SKIP: ${{ steps.green.outputs.skip }}` to `env`. In the heredoc, after
     `effective_selected` is computed, add:
     if `os.environ.get("GREEN_SKIP") == "true"`, then set `effective_selected = set()` and print
     `ci-modules: skip-if-green matched a prior green run -- empty selection` to stderr. The
     helper's `::notice::` already names the run. The `selected-modules` upload stays
     unconditional, so the artifact holds `[]`.
  4. **Re-run escape hatch check.** The documented way to force execution of a skip run is
     "Re-run all jobs" (attempt 2 means `decide` returns Run). That re-runs `generate-matrix`,
     which re-uploads `selected-modules` under the **same name** within the same run.
     - Read the upload-artifact README at the pinned SHA to confirm whether a same-name upload
       in a later attempt conflicts (the `overwrite` input exists from v4.2).
     - If it can conflict, add `overwrite: true` to the `selected-modules` upload and to all
       three marker uploads.
     - Record the finding and the citation in the Activity Log.
- **Files**: `.github/workflows/ci-modules.yml`.
- **Parallel?**: See T073.
- **Notes**:
  - The nightly `workflow_call` sees the caller's event, so `decide` returns Run with
    `marker=''` and nothing is uploaded.
  - `tests/ci/test_ci_module_wiring.py::test_reduced_paths_*` and the golden tests evaluate
    selection, not these steps. Run them anyway.

### Subtask T076 – Companions stay green unchanged; record residuals and the post-merge follow-up

- **Purpose**: Prove C-003 and the pinned invariants hold with **no** edits to their tests, and
  write down what this WP does not prove.
- **Steps**:
  1. Run, unchanged and green:
     - `tests/ci/test_ci_module_wiring.py`, whose golden lane tests evaluate job `if:`s
       against a modelled `changes` context;
     - `tests/ci/test_fork_guard.py`;
     - `tests/architectural/test_dual_mode_contract.py` (router-gate `needs` == all non-gate jobs);
     - `tests/architectural/test_gate_selection_authority.py`;
     - `tests/architectural/test_ci_quality_path_filters.py`;
     - `tests/architectural/test_ci_router_transcription_guards.py` (finds `unmatched` by id;
       an `if:` is harmless);
     - `tests/architectural/test_workflow_coherence.py`;
     - `tests/release/test_release_ci_ownership.py`.

     If any needs an edit, stop: that means a job `if:`/`needs:`/output changed, which this WP
     forbids.
  2. Run `tests/ci/test_workflow_script_import_guard.py`. `green_match.py` is now invoked in
     three more workflows; the guard asserts the path exists and that the script has no
     `scripts.*` import.
  3. Run `tests/architectural/test_no_duplicate_suite_execution.py`. Do not edit it: it parses
     `pull_request_types` via `_gate_coverage.py:1081,1369`, and trigger types are unchanged.
  4. Record these **residuals** in the Activity Log and the PR body, as decisions, not defects:
     - Always-on router lanes and `prose-scan` still execute on a skip run. They are cheap
       lint/static lanes plus WP12's `architectural-fast`, about 1–2 minutes. On a prose-only PR,
       `tests-docs` can still run because `prose-scan` is not suppressed. Suppressing it would
       need a fourth helper call in `prose-scan`; it was left out to keep the change minimal
       (SC-005 targets the *expensive* jobs).
     - Sonar's informational per-change upload repeats on a skip run (D-16, accepted).
     - `ci-quality.yml` also re-runs on `ready_for_review` and is out of scope (follow-up in
       research).
  5. Record the **post-merge follow-up** (D-16, R3 §1.8):
     - `ci-aggregate.yml` runs from `main` via `workflow_run`, so the re-point (WP17) cannot be
       observed on the mission PR.
     - While the mission PR is open, a CI Modules skip run feeds main's **old** aggregate,
       which goes green with `coverage=false`. That run is not FR-011 evidence.
     - Add a follow-up line to the Activity Log and hand it to the orchestrator for the
       tracker: "On the first post-merge PR that goes draft → ready on an already-green head,
       record the CI Aggregate run, confirm `effective-source` printed `repointed=true` and that
       `diff-cover` ran against the matched run's evidence, and cite the run IDs in the mission
       evidence file (C-011)."
  6. Mission-PR live check (C-011 evidence for the decide half). Open the mission PR as a draft,
     wait for green, mark it ready. Record for Router, Modules and Packs:
     - the skip run IDs;
     - their `::notice::` "matched run" lines;
     - the required-check success of `router gate` and `CI Modules gate`.
- **Files**: none beyond the owned set. The record goes in the Activity Log and the PR body.
- **Parallel?**: Last.

## Test Strategy

Red-first: commit T072's failing test file before editing any workflow.

```bash
uv run --frozen pytest tests/ci/test_skip_if_green_wiring.py tests/ci/test_green_match.py -q
uv run --frozen pytest tests/ci/test_ci_module_wiring.py tests/ci/test_fork_guard.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_aggregate_attempts.py -q
uv run --frozen pytest tests/architectural/test_dual_mode_contract.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_quality_path_filters.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_pycache_sweep.py -q
uv run --frozen pytest tests/release/test_release_ci_ownership.py -q
uv run --frozen ruff check tests/ci/test_skip_if_green_wiring.py && uv run --frozen ruff format --check tests/ci/test_skip_if_green_wiring.py
make test-fast
```

Pinning inventory: run `python3 scripts/ci/derive_pinning_inventory.py --check`. It is green on
base `bc826fcbcb` (the #3143 entry landed with `e3794ded2d`; #5523 closed, D-37; WP19
regenerates). Confirm your diff adds no delta.

Never run `pytest tests/architectural` as a directory, and never run `make test-full`. The PR's
own CI runs the battery, because WP07's `ci_config` group selects it for workflow edits.

## Risks & Mitigations

- **A missed output-producing step.** Some group output stays `'true'` on a skip run.
  Mitigation: T072 derives the step set from `outputs:` and has a positive control.
- **The helper crashes or the API errors.** Mitigation: the step has `continue-on-error: true`
  and the helper itself fails open. A missing output means the filter runs, which is the safe
  direction.
- **`_GROUP_REF` contamination.** Mitigation: the static test forbids any job-level reference to
  `green`/`skip`.
- **Re-run escape hatch blocked by an artifact name conflict.** Mitigation: the T075 step 4
  check plus `overwrite: true` if needed.
- **No new trust surface.** `pull_request` runs already execute PR-controlled workflow YAML; a
  PR could equally delete jobs. Aggregate's trusted re-verification (WP17) neutralises a forged
  marker *name*.

## Review Guidance

- Diff each workflow. Each should show only:
  - one permissions block;
  - one `green` step;
  - `if:` additions on output-producing steps;
  - one upload step;
  - (ci-modules only) the `GREEN_SKIP` fold;
  - one header paragraph.

  Reject any change to a job `if:`, `needs:`, `outputs:`, filter globs or triggers.
- Confirm the skip-context golden test imports the existing `_eval_gh_if` evaluator, derives
  the path-gated job set from the `if:` text, and pins the D-35 `prose_only` residual as the
  exact set `{"tests-docs"}` (no open-ended allowlist).
- Confirm the companion tests ran unchanged with recorded counts.
- Confirm the DoD records the post-merge Aggregate verification follow-up and the residuals
  (always-on lanes, `prose-scan`/`tests-docs`, Sonar re-upload).
- Confirm the live draft → ready evidence on the mission PR names the matched runs.

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
