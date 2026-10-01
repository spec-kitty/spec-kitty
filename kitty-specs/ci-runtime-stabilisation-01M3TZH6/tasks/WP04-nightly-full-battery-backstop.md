---
work_package_id: WP04
title: Nightly full-battery backstop
dependencies: []
requirement_refs:
- FR-001
- SC-003
- C-001
- FR-002
planning_base_branch: issue-5510-ci-runtime-stabilisation
merge_target_branch: issue-5510-ci-runtime-stabilisation
branch_strategy: Planning artifacts for this mission were generated on issue-5510-ci-runtime-stabilisation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5510-ci-runtime-stabilisation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-runtime-stabilisation-01M3TZH6
base_commit: af3835c061b70b593dea46f98b26fdda168f977c
created_at: '2026-10-01T08:56:35.825886+00:00'
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 2 - Honest safety net
history:
- at: '2026-10-01T07:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_nightly_architectural_backstop.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-nightly.yml
- tests/ci/test_nightly_exit_code_honesty.py
- tests/ci/test_nightly_architectural_backstop.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Nightly full-battery backstop

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

Make "a green nightly means the full architectural battery ran" true. Today the nightly runs
664 of 3,561 battery tests (18.6%), only through `interpreter-matrix-shard-3`'s
`-m "fast or unit"` selection on Python 3.13. ADR 2026-09-26-1 and the by-design closure of
#5302 both assume a full nightly backstop that does not exist.

This WP adds one job, `architectural-backstop`, to `.github/workflows/ci-nightly.yml`. It
runs the **plain per-PR battery base command**, with no partition plugin, on four workers.

Done means:

- **FR-001**: the backstop's parsed selection (paths, deselects, marker) equals the per-PR
  battery base read from `ci-router.yml`. It carries no `--battery-part` and no
  `-p scripts.ci.battery_partition_plugin`. It is in `nightly-summary.needs` with an echo line.
  **FR-001's set-equality is jointly evidenced**: this WP proves **command parity** (backstop
  selection == per-PR base, statically); WP06's partition proof proves **fast ∪ S1 ∪ S2 = base**.
  Neither alone establishes "the nightly runs everything the per-PR battery can run" — do not
  claim the full FR-001 equality from this WP's tests.
- **SC-003**: once WP06 proves fast ∪ S1 ∪ S2 = base, the nightly runs 100% of what the
  per-PR fast job and both legs can run.
- **C-001**: no per-PR selection changes in this WP. The nightly only gains coverage.
- A red backstop fails the nightly run conclusion, which `scripts/ci/release_nightly_gate.py`
  reads. It also escalates under the suite key `architectural`, gated on `refs/heads/main`,
  and the terminal fail-loud step does not exempt exit 5 (it is a directory lane).
- The red-first test file `tests/ci/test_nightly_architectural_backstop.py` is red on the
  planning base and green on the WP tip.

## Context & Constraints

- **Read first**: `kitty-specs/ci-runtime-stabilisation-01M3TZH6/research.md`. Read decision
  log rows D-04, D-05, D-26, D-32 and D-34 first, then R1 §2 ("FR-001 — Nightly full-battery
  backstop") for detail. Also read `spec.md` (US1, FR-001, SC-003), `plan.md` IC-04,
  `contracts/battery-partition.md` ("Nightly" bullet) and `.kittify/charter/charter.md`.
- **D-26**: the backstop is **not** a registry key. Do not touch `.github/ci-module-registry.yml`.
  This keeps WP04 independent of the registry/selector chain (WP01→WP05).
- **D-04**: the backstop must not depend on the partition machinery. If the plugin or
  selector ever dropped a file, a plugin-free base run still executes it. Equality with the
  three per-PR parts is proven statically by WP06, not here.
- **D-32**: the nightly is currently red on `main` (P0s #5418/#5505/#5506/#5507). Judge the
  backstop on **its own job conclusion**, not on the run conclusion.
- **PR #5521 has merged (D-32 → D-37)**: #5521 (#5517) is on base `bc826fcbcb`. It rewrote
  `scripts/ci/nightly_escalation.py` so every filed or bumped escalation issue is triaged —
  native type `Bug` (`BUG_ISSUE_TYPE`), labels `ESCALATION_LABELS = ("priority:P0", "from:ci")`,
  milestone `MILESTONE_TITLE = "4.0.0 release scope"` (resolved by title at run time), and a
  sub-issue link under `PARENT_ISSUE_NUMBER = 5106` — via `triage_issue()`, called from
  `run_escalation()` after create/bump. Each triage step degrades to a `::warning title=Nightly
  escalation triage::` annotation, never a failure. **The CLI is unchanged**: `main()`
  (`nightly_escalation.py:404-415`) still takes `--suite-key` (required, free-form — there is
  no suite-key registry or allow-list to extend), `--conclusion {success,failure}`, `--repo`,
  `--run-url` and `--ref` (default `$GITHUB_REF`). So the T016 escalation step needs **no new
  flag and no new permission** beyond the job-level `issues: write` every escalating nightly job
  already declares; the `architectural` key is registered simply by using it. Never edit
  `nightly_escalation.py` or `tests/ci/test_nightly_escalation.py` here.
- **C-009**: never run `tests/architectural` as a whole locally, and never `make test-full`.
  A `--collect-only` of the battery base is allowed (collection, not a run).
- **Workflow ceiling**: 17/20 workflow files. Add a job, never a workflow file.
- **Terminology**: say "Mission", never "feature". Never write bare "routing"; say "CI path
  routing" or "gate selection".

### Current-state anchors (verified 2026-10-01 on `issue-5510-ci-runtime-stabilisation`)

| Surface | Anchor | Today |
|---|---|---|
| Per-PR battery base | `ci-router.yml` job `architectural-heavy` (≈:555-606) | `uv run --frozen pytest tests/architectural -q -m "not performance and not stress and not timing" -n auto --dist loadfile` plus 4 `--deselect` (`test_no_legacy_terminology.py`, `test_layer_rules.py`, `test_pyproject_shape.py`, `test_archive_root_byte_identical.py`); `python-version: '3.12'`; `fetch-depth: 0` |
| Nightly architectural coverage | `ci-nightly.yml` job `interpreter-matrix-shard-3` (≈:546) | Python 3.13, `-m "fast or unit"` subset only |
| Directory-lane pattern | `ci-nightly.yml` jobs `integration-next` (≈:912) and `specify-cli-out-of-matrix` (≈:1015) | fork-guard `if:`; `permissions: {contents: read, issues: write}`; run step `if: always()` + `set +e` + `X_EXIT` → `$GITHUB_ENV`; upload-artifact `043fb46…# v7.0.1`; escalation step `if: always() && github.ref == 'refs/heads/main'`; terminal fail-loud on `${X_EXIT:-1} -ne 0` |
| Summary | `ci-nightly.yml` job `nightly-summary` (≈:1094) | `needs: [performance, e2e, stress, interpreter-matrix-shard-1..6, integration-next, specify-cli-out-of-matrix, full-module-matrix]`, one `echo` per need |
| Exit-code pins | `tests/ci/test_nightly_exit_code_honesty.py:66-69` `_DIRECTORY_LANES` | `{"integration-next": "INTEGRATION_EXIT", "specify-cli-out-of-matrix": "SPECIFY_CLI_OOM_EXIT"}` |
| Timeout headroom rule | `tests/ci/test_nightly_timeout_headroom.py:51` `_is_nightly_target`; `_cap_violations(text, is_target)` | targets interpreter shards plus `specify-cli-out-of-matrix` only. The predicate is a parameter. |
| Escalation gate pin | `tests/ci/test_nightly_escalation.py` `_escalation_steps` (≈:513), `_ungated_escalation_steps` (≈:523), `test_every_nightly_escalation_step_is_gated_on_the_mainline_ref` (≈:543), mutation control `test_ungated_escalation_step_is_caught_by_the_gate_check` (≈:552) — post-#5521 line numbers | every escalation step needs `github.ref == 'refs/heads/main'`, `--ref "$GITHUB_REF"` and a space before the `--run-url` value |
| Escalation triage (#5521) | `scripts/ci/nightly_escalation.py` `triage_issue` / `_TRIAGE_STEPS`; pinned by `test_triage_policy_constants_match_the_hand_triage_convention` (≈:575) | applies to every suite key, including the new `architectural`; nothing to wire per key |
| Summary-aggregation pin | `tests/ci/test_nightly_exit_code_honesty.py:292` `test_every_escalating_nightly_job_is_aggregated_by_nightly_summary` | every job with an escalation step is in `nightly-summary.needs` |
| Fork guard | `tests/ci/test_fork_guard.py` | every self-starting job in a scheduled workflow puts the canonical fork guard first in its `if:` |
| Release gate | `scripts/ci/release_nightly_gate.py:105` | gates on the **run conclusion** of `ci-nightly.yml` for the release SHA (`conclusion == "success"`) |
| Gate model | `tests/architectural/_gate_coverage.py` `WORKFLOW_FILES` includes `ci-nightly.yml`; `parse_workflow` (≈:823) | the backstop is parsed into a `Gate` automatically; `python -m pytest` and `uv run --frozen` prefixes are stripped |

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T014 – Red-first: backstop-shape test

- **Purpose**: pin FR-001 before writing YAML. The test fails today because no
  `architectural-backstop` job exists, and the only nightly architectural selection is
  `fast or unit`.
- **Steps**:
  1. Create `tests/ci/test_nightly_architectural_backstop.py` with `pytestmark = pytest.mark.fast`.
     It runs in the `ci` module row.
  2. Write **one production check function**,
     `backstop_violations(nightly_jobs: dict, router_gates: list[Gate], nightly_gates: list[Gate]) -> list[str]`.
     The live test and every mutation test call this same function (Standing Order #5:
     a mutation that never reaches the production check proves nothing). It returns one
     message per broken property:
     - exactly one `Gate` with `job == "architectural-backstop"` in `gc.parse_workflow(ci-nightly.yml)`;
     - the router battery family is every `ci-router.yml` gate whose `paths == ["tests/architectural"]`.
       Today that is `architectural-heavy` alone; after WP12 it is `architectural-fast` plus
       both legs. Every family member must share one `(set(ignores), marker_expr)`, and the
       backstop must equal it, with `paths == ["tests/architectural"]`. Drift in either
       workflow is reported.
     - the backstop's raw run text contains neither `--battery-part` nor `battery_partition_plugin`;
     - the run text carries the literal `-n 4` and `--dist loadfile`, and no `-q` (FR-002 evidence);
     - the job is in `nightly-summary.needs`, and the summary run text echoes
       `needs.architectural-backstop.result`;
     - an escalation step invokes `nightly_escalation.py --suite-key architectural`;
     - neither the job nor any of its steps is `continue-on-error: true`;
     - the checkout step has `fetch-depth: 0`, and `setup-uv` pins `python-version: '3.12'`
       (the per-PR battery interpreter; see Notes).
  3. Live test: `test_live_nightly_backstop_has_no_violations` asserts `backstop_violations(...) == []`.
     Load jobs with `_gate_coverage.load_spliced_workflow`, the canonical loader (not a raw
     `yaml.safe_load`; see LAND-PAT-003 in `test_nightly_exit_code_honesty.py`).
  4. Mutation tests run on in-memory copies of the live jobs dict or on a tmp copy of the YAML.
     Each one asserts the specific message appears:
     - drop the job from `nightly-summary.needs`;
     - swap the marker for `"fast or unit"`;
     - append `--battery-part 1/2` to the command;
     - replace `-n 4` with `-n auto`;
     - remove one `--deselect`.
  5. Timeout headroom: import `_cap_violations` from `tests.ci.test_nightly_timeout_headroom`.
     Assert `_cap_violations(text, lambda key: key == "architectural-backstop") == []`. This
     applies the #5378 rule without editing that unowned file (alternative below).
  6. Run it and confirm it is **red**. Record the failing assertion in the Activity Log.
- **Files**: `tests/ci/test_nightly_architectural_backstop.py` (new).
- **Parallel?**: No. It is the first commit (ATDD red-first, charter ATDD-First Discipline).
- **Notes**:
  - Do not mention the pinning-inventory subjects (the literals `ci-quality.yml`,
    `sonarcloud`, `make test-fast`) in this file. A mention adds a row to
    `tests/release/pinning_rule_inventory.json` and forces a regeneration.
  - Alternative to step 5: add the key to `_is_nightly_target`. That file is not owned, so
    prefer the import. If you must edit it, record the out-of-map rationale in the Activity Log.
  - Python 3.12: the router battery pins `python-version: '3.12'`, while the nightly
    `setup-uv` steps default to `.python-version` (3.11.15). The backstop claims "the same
    set the per-PR legs run", and version-conditional skips make the set interpreter-dependent,
    so pin 3.12. Interpreter diversity remains the interpreter shards' job (D-14, #5250).

### Subtask T015 – Add the `architectural-backstop` job

- **Purpose**: the job itself (FR-001), built on the `specify-cli-out-of-matrix` /
  `integration-next` directory-lane pattern.
- **Steps**:
  1. Insert the job immediately before the `nightly-summary` comment block in `ci-nightly.yml`.
     Shape (adapt step names to house style; keep every pinned SHA identical to the
     neighbouring jobs):
     ```yaml
       architectural-backstop:
         if: (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')
         name: Architectural battery backstop (nightly-only, #5510)
         runs-on: ubuntu-24.04
         # headroom (#5378): max-suite>=25:09 runs=<census run id of the 25:09 max> formula=ceil((max+0:30)*1.5)
         timeout-minutes: 40
         permissions:
           contents: read
           issues: write
         steps:
           - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
             with:
               fetch-depth: 0
           - name: Install uv
             uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
             with:
               python-version: '3.12'
           - name: Sync dev environment
             shell: bash
             run: uv sync --frozen --all-extras
           - name: Run the full architectural battery base (no partition, run-all-regardless)
             if: always()
             shell: bash
             run: |
               set +e
               uv run --frozen python -m pytest tests/architectural \
                 -m "not performance and not stress and not timing" \
                 -n 4 --dist loadfile \
                 --deselect tests/architectural/test_no_legacy_terminology.py \
                 --deselect tests/architectural/test_layer_rules.py \
                 --deselect tests/architectural/test_pyproject_shape.py \
                 --deselect tests/architectural/test_archive_root_byte_identical.py \
                 --junitxml=out/reports/xunit-nightly-architectural.xml
               code=$?
               echo "ARCH_BACKSTOP_EXIT=$code" >> "$GITHUB_ENV"
               echo "::notice::architectural backstop exit=$code (full base, no partition; fail-loud below)"
     ```
     Then add three steps: upload `out/reports/` as `ci-nightly-architectural-backstop-reports`
     (`if: always()`, the same upload-artifact SHA); the escalation step (T016); and the
     terminal fail-loud step (`${ARCH_BACKSTOP_EXIT:-1} -ne 0` → `::error::` + `exit 1`, with
     **no** `-ne 5` exemption).
  2. Copy the deselect list **byte-for-byte from the live router battery command**. Do not
     retype it from this prompt. If WP07/WP08 changed the router before you rebase,
     T014's family check tells you.
  3. Timeout: `ceil((25:09 + 0:30) × 1.5) = 39` ⇒ 40 satisfies the rule. 25:09 is the
     census worst battery job at `-n 2` (spec Context). Cite real run ids in the comment if
     the census evidence names them; otherwise write `runs=census-2026-09-30`. Re-base the
     number after the first measured backstop runs (D-04).
  4. Write a job comment block above the job saying why it exists (FR-001, #5510, #3265 fold,
     ADR 2026-09-26-1), why it is plugin-free (D-04), that it is not a registry key (D-26), and
     that its junit is the battery per-file timings refresh source (D-29/D-36: WP14 seeds from census logs; junit capture via WP05's `--from-junit` mode is the refresh path).
- **Files**: `.github/workflows/ci-nightly.yml`.
- **Parallel?**: No (T014 first).
- **Notes**:
  - `python -m pytest` matches the router's future `-p` form and is parsed by `_gate_coverage`.
  - Drop `-q` so xdist prints `created: 4/4 workers` and `4 workers [N items]` (D-05; xdist
    suppresses `report_line` only at `verbose < 0`).
  - `if: always()` on the run step keeps `mode=pr` diagnostic dispatches from short-circuiting
    it (house pattern, #4212).
  - The job is a root job with no `needs:`, so `test_fork_guard.py` requires the canonical
    guard as the first `&&` conjunct. Use the exact string the neighbouring jobs use.

### Subtask T016 – Wire summary, escalation and exit-code honesty pins

- **Purpose**: make the backstop's red visible. It feeds the summary, the escalation
  issue and the run conclusion the release gate reads.
- **Steps**:
  1. Add `architectural-backstop` to `nightly-summary.needs`, after `specify-cli-out-of-matrix`.
     Add `echo "architectural-backstop: ${{ needs.architectural-backstop.result }}"` to the
     summary run step.
  2. Add the escalation step (copy the `specify-cli-out-of-matrix` step and change only the key and var):
     ```yaml
           - name: Escalate architectural backstop red -> deduped P0 (fail-closed)
             if: always() && github.ref == 'refs/heads/main'
             shell: bash
             env:
               GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
             run: |
               if [ "${ARCH_BACKSTOP_EXIT:-1}" -ne 0 ]; then conclusion=failure; else conclusion=success; fi
               python3 scripts/ci/nightly_escalation.py --suite-key architectural --conclusion "$conclusion" --ref "$GITHUB_REF" --run-url "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
     ```
  3. In `tests/ci/test_nightly_exit_code_honesty.py`, extend `_DIRECTORY_LANES` with
     `"architectural-backstop": "ARCH_BACKSTOP_EXIT"` and update its comment (#5510 adds the
     backstop). That one entry automatically applies the "unset exit never defaults to 0",
     the "defaults to the `:-1` sentinel" and the "directory lane never exempts exit 5" checks.
  4. Confirm `test_every_escalating_nightly_job_is_aggregated_by_nightly_summary` and
     `test_nightly_escalation.py::test_every_nightly_escalation_step_is_gated_on_the_mainline_ref`
     pass unchanged. The new step must satisfy their production checks.
- **Files**: `.github/workflows/ci-nightly.yml`, `tests/ci/test_nightly_exit_code_honesty.py`.
- **Parallel?**: No.
- **Notes**:
  - `architectural` is a new escalation suite key. Grep `--suite-key` in `ci-nightly.yml`
    to confirm it is unused. Escalation dedups per key, so a backstop red and an interpreter
    shard red on the same test open two P0s, by design (the LAND-ARCH-001 precedent).
  - No `continue-on-error` anywhere in the job. Otherwise the run conclusion stays green
    and the release gate never sees the red.

### Subtask T017 – Verify the release nightly gate needs no wiring; document it

- **Purpose**: US1 AS-2 says the release nightly gate sees a backstop failure. Prove that
  this holds by construction, then write it down.
- **Steps**:
  1. Read `scripts/ci/release_nightly_gate.py` around `_is_success` (≈:105). It keys on the
     `ci-nightly.yml` **run conclusion** for the release SHA. A failing non-`continue-on-error`
     job makes the run conclusion `failure`, so the release blocks. No script change is needed.
  2. Add one sentence to the backstop job comment block naming this mechanism, so a later
     reader does not add redundant wiring.
  3. Node-level sanity check (collection only, allowed under C-009): run the base command
     with `--collect-only -q` and record the selected-test count in the Activity Log. That
     count is the FR-001 reference which WP06/WP12 evidence later compares to
     fast + S1 + S2:
     ```bash
     uv run --frozen python -m pytest tests/architectural \
       -m "not performance and not stress and not timing" \
       --deselect tests/architectural/test_no_legacy_terminology.py \
       --deselect tests/architectural/test_layer_rules.py \
       --deselect tests/architectural/test_pyproject_shape.py \
       --deselect tests/architectural/test_archive_root_byte_identical.py \
       --collect-only -q | tail -3
     ```
  4. After the branch is pushed under the mission's push authorization (never to `main`),
     the orchestrator dispatches `gh workflow run ci-nightly.yml --ref issue-5510-ci-runtime-stabilisation`.
     Record that run id, the backstop job conclusion and its duration (C-011). Judge the
     **job** conclusion (D-32), because the run conclusion is red for unrelated P0s.
- **Files**: `.github/workflows/ci-nightly.yml` (comment only).
- **Parallel?**: Yes, alongside T016 once T015 exists.
- **Notes**: do not edit `release_nightly_gate.py`. It is correct as is.

## Test Strategy

Red-first: T014's file is red on the planning base and green on the WP tip.

Local validation (C-009: targeted files only, never `tests/architectural` as a whole):

```bash
make test-fast
uv run --frozen pytest tests/ci/test_nightly_architectural_backstop.py \
  tests/ci/test_nightly_exit_code_honesty.py tests/ci/test_nightly_timeout_headroom.py \
  tests/ci/test_nightly_escalation.py tests/ci/test_fork_guard.py \
  tests/ci/test_release_nightly_gate.py tests/ci/test_interpreter_matrix_env_pinning.py -q
# Architectural gates that parse ci-nightly.yml (specific files only):
uv run --frozen pytest tests/architectural/test_interpreter_shard_coverage.py::test_nightly_summary_needs_includes_every_roster_shard \
  tests/architectural/test_module_shard_registry.py tests/architectural/test_marker_job_completeness.py \
  tests/architectural/test_gate_coverage_runner_prefix.py tests/architectural/test_dual_mode_contract.py -q
uv run --frozen ruff check tests/ci/test_nightly_architectural_backstop.py tests/ci/test_nightly_exit_code_honesty.py
uv run --frozen ruff format --check tests/ci/test_nightly_architectural_backstop.py tests/ci/test_nightly_exit_code_honesty.py
uv run --frozen mypy tests/ci/test_nightly_architectural_backstop.py
python3 scripts/ci/derive_pinning_inventory.py --check   # green on the base (D-37); must stay green
```

Record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run*.

## Risks & Mitigations

- **40-min timeout too tight at `-n 4`**: estimated 14–17 min (R1 §2), so the margin is
  large. Re-base the headroom comment after the first measured runs.
- **Deselect drift between router and nightly**: T014's family-equality check reports it,
  in both directions.
- **Pinning inventory**: green on base `bc826fcbcb` (#5523 fixed by `e3794ded2d`, CLOSED; D-37). This WP does not edit inventory-scanned rule lines, so
  `--check` must stay green and nothing is regenerated here. A red on your tip is **yours**
  (most likely a subject literal in new text — see T014's note); fix the text rather than
  regenerating.
- **#5521 already merged** (D-37): it did not touch `ci-nightly.yml` and kept the CLI, so the
  T016 step is the verbatim copy of the `specify-cli-out-of-matrix` step (`ci-nightly.yml`
  ≈:1068-1075) with only the key and exit variable changed. A backstop red now also files a
  triaged issue (type Bug, `from:ci`, milestone, parent #5106) — expected, no wiring.
- **Main nightly red for unrelated P0s (D-32)**: evidence cites the backstop job conclusion only.

## Review Guidance

- Check out the planning base, run `tests/ci/test_nightly_architectural_backstop.py`, and
  confirm it is **red** (no job). On the WP tip it is green.
- Diff the backstop command against the live `architectural-heavy` command: same paths,
  marker and four deselects; `-n 4`; no `-q`; no plugin; no `--battery-part`.
- Confirm `nightly-summary.needs` and the echo line, the escalation key `architectural`
  with the main-ref gate, the `:-1` sentinel, no exit-5 exemption, no `continue-on-error`,
  `fetch-depth: 0`, the 3.12 pin, and the headroom comment directly above `timeout-minutes`.
- Confirm `.github/ci-module-registry.yml` and `release_nightly_gate.py` are untouched (D-26, T017).
- Confirm the mutation tests call the same `backstop_violations` function as the live test.
- If typed test sources changed, confirm the implementer ran mypy as well as pytest and
  that its diagnostics passed.
- Confirm the WP claims only command parity for FR-001; the partition half is WP06's proof.
- **Definition of Done**: FR-001 / SC-003 wiring is statically proven (command-parity half;
  the fast ∪ S1 ∪ S2 = base half is WP06's); the exit-code honesty,
  escalation, fork-guard and headroom pins are green; the collect-only reference count is
  recorded; the dispatched nightly run id and the backstop job conclusion are recorded (C-011).

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
- 2026-10-01T09:08:37Z – claude – shell_pid=1510448 – WP04 implemented. Red-first: 677ebbc246 test file red on base (9 failed/2 passed: no architectural-backstop job). Green on tip: tests/ci/test_nightly_architectural_backstop.py + exit-code honesty, headroom, escalation, fork-guard, release-gate, env-pinning = 270 passed. Arch gates (interpreter_shard_coverage needs-test, module_shard_registry, marker_job_completeness, gate_coverage_runner_prefix, dual_mode_contract) 60 passed; out_of_matrix_evidence/suite_jobs_gate_blocking/performance_marker_guard/no_duplicate_suite_execution/workflow_coherence/ci_router_transcription_guards/ci_module_wiring/release_ci_ownership green; shard coverage + module_length 36 passed after uv sync --all-extras (initial 13 collection errors were a stale fresh-worktree venv, not the change). tests/ci+tests/release fast tier 869 passed. ruff check/format/mypy clean; pinning inventory --check exit 0. FR-001 collect-only reference count of battery base: 3394/3602 tests collected (208 deselected). Live nightly run is an orchestrator closeout measurement (C-011): no workflow dispatched by this agent; run id and backstop job conclusion/duration to be recorded by the orchestrator. Only command parity claimed; fast+S1+S2=base is WP06. T017: release_nightly_gate.py reads ci-nightly run conclusion; no wiring needed, documented in job comment. Untouched: ci-module-registry.yml, release_nightly_gate.py, nightly_escalation.py.
