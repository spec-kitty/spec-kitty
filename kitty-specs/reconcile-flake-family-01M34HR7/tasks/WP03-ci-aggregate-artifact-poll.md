---
work_package_id: WP03
title: ci-aggregate.yml artefact-visibility polling (wait_for_artifacts.py)
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- NFR-001
- NFR-003
- C-002
- C-008
planning_base_branch: fix/reconcile-flake-family-4882
merge_target_branch: fix/reconcile-flake-family-4882
branch_strategy: Planning artifacts for this mission were generated on fix/reconcile-flake-family-4882. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/reconcile-flake-family-4882 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reconcile-flake-family-01M34HR7
base_commit: 8aadd9488ed78df3c609982c05a1b09ece5f3e6f
created_at: '2026-09-22T16:37:08.986836+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
history: []
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/wait_for_artifacts.py
- tests/ci/test_wait_for_artifacts.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/wait_for_artifacts.py
- .github/workflows/ci-aggregate.yml
- tests/ci/test_wait_for_artifacts.py
role: implementer
tags: []
tracker_refs: []
---

# WP03: ci-aggregate.yml artefact-visibility polling (wait_for_artifacts.py)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add a new bounded polling step to `.github/workflows/ci-aggregate.yml`'s `collect` job, ahead
of its existing `actions/download-artifact` steps, that re-checks GitHub Actions artefact
visibility for the triggering run's SELECTED (must-be-fresh) shard names before falling
through to the existing download-and-reconcile steps — implemented as a new
`scripts/ci/wait_for_artifacts.py` script (with its own unit tests), using WP01's
`retry_with_backoff` primitive. **`scripts/ci/reconcile_shards.py` is NOT modified by this
WP** — it remains the single, unmodified, fail-closed terminus for completeness decisions.

## Context

**Prerequisite**: WP01's `scripts/ci/reconcile_retry.py::retry_with_backoff` must already
exist with the signature documented in WP01's prompt file. Import it; do not hand-roll a
second retry loop.

Read `kitty-specs/reconcile-flake-family-01M34HR7/plan.md` in full before starting,
especially "User Story 3 — `ci-aggregate.yml` artefact-visibility polling (FR-005/006)" (the
exact sequencing change, the new step's `env:` block requirement, and the rationale for
polling only the SELECTED shard set), "Retry Budget Rationale (NFR-001)" (proposed 8
attempts, backoff 5s → 10s → 20s → 30s cap, ≈155s total), and "Safety Invariants — explicit
preservation statement" (invariant (b)). Also read spec.md's User Story 3 in full (its
acceptance scenarios are the authoritative behavior contract), FR-005, FR-006, NFR-003(3),
C-002, C-008.

**This WP fixes a previously-identified plan defect — do not regress it.** An earlier plan
review round (`kitty-specs/reconcile-flake-family-01M34HR7/reviews/plan.ruling.md`,
finding PLAN-FRESH2-001, severity 4, ACCEPTED) found that an earlier plan draft omitted
`GH_TOKEN` from the new step's `env:` block, which would make the step raise `KeyError` on
its first API call and fail the `collect` job on every PR — worse than the flake being
fixed. The current plan.md text (already corrected) is binding: **the new step's `env:`
block MUST declare all four variables** — `GH_TOKEN`, `SOURCE_RUN_ID`, `SOURCE_RUN_ATTEMPT`,
`SOURCE_REPOSITORY` — because the reused `GitHub.request()` boundary (see below) reads
`token = os.environ["GH_TOKEN"]` as a bare subscript with no fallback. Do not drop `GH_TOKEN`
from the new step's `env:` block for any reason.

**Current `.github/workflows/ci-aggregate.yml` `collect` job step order, verified in this
checkout** (read the live file yourself — exact line numbers will drift once you edit it):

```
checkout
→ Prepare exact source registry and diff       (writes out/aggregate/source/, incl. ci-module-registry.yml via scripts/ci/aggregate_source.py; env: GH_TOKEN + 3 SOURCE_* vars)
→ Upload exact source data
→ Resolve run mode                              (id: resolve-mode)
→ Select reports from executions retained by the source attempt   (id: select-current; env: GH_TOKEN + 3 SOURCE_* vars)
→ Download the triggering run's shard artefacts  (id: download-current; if: steps.select-current.outputs.has-artifacts == 'true'; continue-on-error: true)
→ Find the most-recent successful "CI Modules" run   (id: last-success; if: github.event_name != 'workflow_dispatch')
→ Download the fallback run's shard artefacts    (id: download-previous; if: steps.last-success.outputs.run-id != ''; continue-on-error: true)
→ Download the triggering run's selected-module set   (id: download-selected-modules; if: github.event_name != 'workflow_dispatch'; continue-on-error: true; downloads artifact name "selected-modules" to out/aggregate/selected/)
→ Install PyYAML
→ Reconcile shard artefacts by basename          (id: reconcile; runs: python3 scripts/ci/reconcile_shards.py — DO NOT MODIFY THIS STEP OR THE SCRIPT IT CALLS)
→ Upload reconciled coverage set
```

**Required new step order** (plan.md, binding): move "Download the triggering run's
selected-module set" to immediately after "Select reports from executions retained by the
source attempt", then insert the new "Wait for selected shard artefact visibility" step
between it and "Download the triggering run's shard artefacts":

```
checkout
→ Prepare exact source registry and diff        (unchanged)
→ Upload exact source data                       (unchanged)
→ Resolve run mode                                (unchanged)
→ Select reports from executions retained by the source attempt   (unchanged: select-current)
→ Download the triggering run's selected-module set     (MOVED earlier)
→ Wait for selected shard artefact visibility            (NEW — this WP, FR-005)
→ Download the triggering run's shard artefacts          (unchanged: download-current)
→ Find the most-recent successful "CI Modules" run       (unchanged: last-success)
→ Download the fallback run's shard artefacts             (unchanged: download-previous)
→ Install PyYAML                                            (unchanged)
→ Reconcile shard artefacts by basename                    (unchanged: reconcile — NOT MODIFIED)
→ Upload reconciled coverage set                            (unchanged)
```

**Why the reorder, not just an insert (do not skip this)**: the poller needs to know which
shards are SELECTED (must-be-fresh) before it starts polling, per `reconcile_shards.py`'s own
`reconcile()` predicate (`must_be_fresh = selected is not None and shard.module in
selected`). That selection data comes from `out/aggregate/selected/selected-modules.json`,
which only exists once "Download the triggering run's selected-module set" has run — hence
it must move ahead of the new polling step. Polling the FULL registry instead (skipping the
reorder) would waste the poller's entire budget on every ordinary diff-scoped PR, since most
modules are usually unselected and their artefacts are never produced at all by design
(`ci-aggregate.yml`'s own header comment: "an UNSELECTED (unchanged) module's leaf is
SKIPPED, not run").

**New step's exact `env:` block** (copy the pattern from the "Prepare exact source registry
and diff" step at the top of the job, which already declares all four variables):
```yaml
      - name: Wait for selected shard artefact visibility
        id: wait-for-artifacts
        if: github.event_name != 'workflow_dispatch'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SOURCE_RUN_ID: ${{ github.event.workflow_run.id || inputs.source_run_id }}
          SOURCE_RUN_ATTEMPT: ${{ github.event.workflow_run.run_attempt || inputs.source_run_attempt }}
          SOURCE_REPOSITORY: ${{ github.repository }}
        shell: bash
        run: |
          set -euo pipefail
          python3 scripts/ci/wait_for_artifacts.py
```
(Adjust the exact CLI invocation/args to whatever your `wait_for_artifacts.py` CLI edge
actually expects — see T012 — but the `env:` block's four variables are fixed by the
Context above and must not be reduced to three.) Gate this step's execution the same way
`download-selected-modules` is gated (`if: github.event_name != 'workflow_dispatch'`) since
manual `workflow_dispatch` replay has no selection scoping to poll against — read the
existing `download-selected-modules` step's own `if:` condition and mirror it.

**`scripts/ci/wait_for_artifacts.py`'s exact shape** (plan.md, mirroring
`source_eligibility.py`/`select_source_artifacts.py` — a pure decision core + thin CLI edge):

1. Read the already-written `out/aggregate/source/ci-module-registry.yml` via
   `reconcile_shards.parse_registry(registry_path)` (imported, not re-derived) — default
   path is `reconcile_shards.DEFAULT_REGISTRY_PATH`, verify this constant in the live file
   and reuse it rather than hardcoding the path string again.
2. Read the already-downloaded `out/aggregate/selected/selected-modules.json` via
   `reconcile_shards.read_selected_modules(selected_path)` (imported) — default path is
   `reconcile_shards.DEFAULT_SELECTED_PATH`.
3. Compute the must-be-fresh `RegistryShard` set using the **exact same predicate**
   `reconcile_shards.reconcile()` applies later in the same job — its named
   `must_be_fresh` variable: `selected is not None and shard.module in selected` (read
   `reconcile()`'s own docstring/body in `scripts/ci/reconcile_shards.py` to confirm this
   is still accurate before you copy it — do not invent a second definition of
   "must-be-fresh"). This is the boolean that decides whether a shard MUST show up as
   fresh versus is backfill-eligible from `previous_available`; it is distinct from the
   separate "is this shard required-if-absent at all" check in `reconcile()`'s own `elif`
   chain (`elif selected is None or shard.module in selected: missing.append(shard)`),
   which additionally treats `selected is None` (full/legacy mode) as "every shard
   required" — do not conflate the two.
4. For each must-be-fresh shard, compute its expected GitHub Actions **artifact name** using
   the exact same naming convention `scripts/ci/select_source_artifacts.py` already defines
   and matches: `ARTIFACT = re.compile(r"module-tests-([A-Za-z0-9._-]+)-shard-([1-9][0-9]*)-of-([1-9][0-9]*)-attempt-([1-9][0-9]*)-reports")`
   — i.e. `module-tests-{module}-shard-{shard_index}-of-{shard_count}-attempt-{attempt}-reports`.
   Import/reuse this regex (or the module-name-construction logic it implies) rather than
   reimplementing a second copy that could drift. `attempt` should accept any value
   `<= SOURCE_RUN_ATTEMPT` (matching `select_source_artifacts.py`'s own carried-forward-attempt
   tolerance — read that file's `select_artifacts()` function to see exactly how it handles
   this, and mirror the same tolerance here).
5. Poll `GET actions/runs/{SOURCE_RUN_ID}/artifacts` (paginated) via the `GitHub`/`GitHubCLI`
   request/`pages()` boundary already defined in `scripts/ci/fleet_verdict.py` (import it —
   this becomes its third consumer, after `fleet_verdict.py` itself and `fleet_main.py`).
   `GitHub.request()` reads `os.environ["GH_TOKEN"]` as a bare subscript
   (`scripts/ci/fleet_verdict.py`, `class GitHub.request`) — this is exactly why the `env:`
   block above must declare `GH_TOKEN`. Use `.pages("actions/runs/{run_id}/artifacts",
   field="artifacts")` (verify the exact response shape / field name against GitHub's REST
   API for "List workflow run artifacts" — the `field` parameter is `pages()`'s existing
   mechanism for unwrapping a paginated list from a named key in the response object).
6. Wrap the poll in `retry_with_backoff(attempt, max_attempts=8, backoff_seconds=...)` with
   `attempt()` returning the found artifact-name set once every expected name is present, or
   `None` otherwise. Wire the 8-attempt / 5s→10s→20s→30s(cap) budget from plan.md's Retry
   Budget Rationale as an explicit named constant, the same way WP02 pins its own numbers.
7. **On budget exhaustion, exit 0 regardless** — never raise, never set a failing exit code.
   Print a diagnostic naming which expected shard artifacts were still not visible (same
   `print`/`::error::`/`::warning::` conventions as the sibling scripts). The workflow then
   falls through unconditionally to the existing `actions/download-artifact` steps, which
   download whatever is actually available; `reconcile_shards.py::main()` applies its own
   unchanged, already-tested fail-closed guard against whatever that turns out to be (FR-006).
8. Also exit 0 (with an appropriate diagnostic, not necessarily the same one) if there are NO
   must-be-fresh shards to wait for at all (e.g. an ordinary diff-scoped PR that selected
   zero modules, or `selected is None` in a shape this WP does not otherwise special-case —
   confirm against `reconcile()`'s own handling) — the poller should not spin needlessly when
   there is nothing to wait for.

**`reconcile_shards.py::main()` is provably unreachable-to-regress from this WP**: because
`wait_for_artifacts.py` never touches exit code semantics that flow into `reconcile()` or
`main()`, and `reconcile_shards.py` is not part of this WP's `owned_files`, spec.md's US3
Acceptance Scenario 2 (exhausted-budget still fails closed) is satisfied by construction —
your job is to prove it with a composing test (T014), not to touch the guard itself.

**Charter C-011 (ATDD-First Discipline)** binds this WP: it introduces new functional code,
so a red-first commit must precede implementation. Because `wait_for_artifacts.py` does not
exist before this mission, "red-first through the pre-existing entry point" cannot apply
literally — plan.md's own resolution (see "Red-First Application Across All NFR-003 Test
Surfaces") is: write the new recovery/terminal tests FIRST against a stub, single-attempt
(no-loop) version of the polling function, confirm they fail the way a single, unretried poll
attempt fails today (a transiently-missing artifact is treated as permanently missing — i.e.
the stub returns "missing" immediately with no retry), THEN add `retry_with_backoff` wiring
and confirm the same tests pass.

## Subtask T011: Red-first — stub single-attempt version + failing tests

**Purpose**: Establish the red-first anchor per plan.md's stub-based resolution (there is no
pre-fix entry point to run red against literally).

**Steps**:
1. Create `tests/ci/test_wait_for_artifacts.py` (new file). Study `tests/ci/test_fleet_verdict.py`'s
   `class API`/`class GitHub`-mocking conventions and mirror them for a mocked GitHub Actions
   artifacts-API client (a fake implementing the same `request`/`pages` interface as
   `GitHub`/`GitHubCLI`, returning a controllable, evolving list of artifact names across
   calls).
2. Create a minimal, single-attempt (no retry loop) STUB version of the polling function in
   `scripts/ci/wait_for_artifacts.py` — e.g. a `_poll_once(...)` that checks artifact
   visibility exactly once and returns found/not-found, with no `retry_with_backoff` wiring
   yet.
3. Write a test: a mocked client that reports a must-be-fresh shard's artifact absent on the
   first poll but present on a hypothetical second poll (simulate this however is natural,
   e.g. a call-count-based fake). Against the STUB (single-attempt) version, this test must
   FAIL — the stub only polls once, so it never sees the artifact appear. This is the
   red-first anchor for the recovery path.
4. Write a second test: a mocked client that reports the artifact present by the 8th poll
   within the eventual real budget, but the STUB naturally fails this immediately too (only
   one poll).
5. Commit `tests/ci/test_wait_for_artifacts.py` plus the minimal single-attempt stub as the
   red-first commit, confirmed failing.

**Files**: `tests/ci/test_wait_for_artifacts.py` (new), `scripts/ci/wait_for_artifacts.py`
(new, stub-only single-attempt version for this subtask).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_wait_for_artifacts.py -q` shows RED
against the single-attempt stub, for the stated reason (transient-becomes-permanent).

## Subtask T012: Implement the full `wait_for_artifacts.py` decision core + CLI edge

**Purpose**: Make T011's tests pass by adding the real polling logic (registry/selection
reads, artifact-name computation, `retry_with_backoff` wiring, terminal behavior).

**Steps**:
1. Implement the full module per the "exact shape" walkthrough in Context above: import
   `reconcile_shards.parse_registry`/`read_selected_modules` and their default path
   constants; import/reuse `select_source_artifacts.py`'s artifact-naming regex/logic; import
   `fleet_verdict.GitHub`/`GitHubCLI` for the request/`pages()` boundary; import WP01's
   `retry_with_backoff`.
2. Structure the module as a pure decision core (e.g. a function that takes the registry
   shards, selected set, and a `pages`-like callable, and returns found/missing) plus a thin
   CLI `main()` edge that resolves environment variables (`GH_TOKEN` implicitly via `GitHub`,
   `SOURCE_RUN_ID`, `SOURCE_RUN_ATTEMPT`, `SOURCE_REPOSITORY`) and calls the decision core —
   mirroring `source_eligibility.py`/`select_source_artifacts.py`'s existing split so the
   decision logic is directly unit-testable without a real subprocess or network call.
3. Wire `retry_with_backoff(attempt, max_attempts=8, backoff_seconds=<5,10,20,30-cap>,
   sleep=time.sleep)` around the poll, with the real default `sleep=time.sleep` in
   production code (tests must inject a fake `sleep`, per WP01's contract).
4. Implement the exhausted-budget and no-must-be-fresh-shards terminal paths: exit 0, print
   diagnostic, never raise.
5. Run T011's tests against this real implementation and confirm they now pass (RED → GREEN).

**Files**: `scripts/ci/wait_for_artifacts.py` (completed, ~80–120 lines per plan.md's
estimate).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_wait_for_artifacts.py -q` — green.

## Subtask T013: Re-sequence `ci-aggregate.yml` and add the new step

**Purpose**: Wire the new script into the real workflow, in the required step order, with
the required `env:` block.

**Steps**:
1. Move the "Download the triggering run's selected-module set" step (`id:
   download-selected-modules`) to immediately after "Select reports from executions retained
   by the source attempt" (`id: select-current`) — a real reordering of existing YAML, not a
   copy. Preserve its existing `if:`/`continue-on-error:`/`with:` content unchanged; only its
   position in the step list moves.
2. Insert the new "Wait for selected shard artefact visibility" step (per the exact `env:`
   block shown in Context above — all four variables, `GH_TOKEN` included) immediately after
   the moved step and immediately before "Download the triggering run's shard artefacts"
   (`id: download-current`).
3. Re-verify, by reading the live file after your edit, that no later step in the job
   implicitly depended on `download-selected-modules` running AFTER `download-previous` (the
   plan's own review found none, but re-confirm against the live file, not the plan's
   summary — plan.md's own "Deviations" item 2 asks the implement phase to re-verify this).
4. Confirm the new step's `if:` condition matches (or is deliberately and explainably
   different from) the moved step's own `if: github.event_name != 'workflow_dispatch'`
   condition — both should skip together on manual replay, since replay has no selection
   scoping to poll against.

**Files**: `.github/workflows/ci-aggregate.yml` (modified — step reorder + new step).

**Validation**: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-aggregate.yml'))"`
(or equivalent) confirms the file still parses as valid YAML. Manually re-read the full
`collect` job step list top-to-bottom and confirm it matches the "Required new step order"
list in Context exactly.

## Subtask T014: Composing test — `reconcile_shards.py::main()` still fails closed

**Purpose**: Prove invariant (b) (FR-006/C-002) end-to-end without a real workflow run: when
the poller exhausts its budget, `reconcile_shards.py::main()`, invoked against whatever
directory state results, still exits non-zero and still prints its `::error::` annotation.

**Steps**:
1. In `tests/ci/test_wait_for_artifacts.py`, add an integration-style unit test that:
   constructs a scenario where the poller exhausts its budget for a must-be-fresh shard,
   constructs the resulting on-disk directory state that `actions/download-artifact` would
   have produced in that circumstance (the shard genuinely absent from
   `out/aggregate/current/`), and then invokes `reconcile_shards.py::main()` (or its
   `reconcile()` core function directly, whichever gives a more direct, deterministic
   assertion) against that constructed state.
2. Assert `main()`/`reconcile()` reports incomplete (`complete=False`, the missing shard
   present in `missing`) and — if invoking the real CLI `main()` — that it exits non-zero and
   the `::error::ci-aggregate: ... refusing to silently treat this run as complete ...`
   annotation (or its current exact text — read it from the live `reconcile_shards.py` file)
   is printed.
3. Re-run `tests/ci/test_reconcile_shards.py` UNMODIFIED (per SC-003's baseline — this WP
   does not touch that file or the module it tests) and confirm it still passes in full,
   proving this WP made zero behavioral change to `reconcile_shards.py`.

**Files**: `tests/ci/test_wait_for_artifacts.py` (adds the composing test).

**Validation**: New composing test passes; `.venv/bin/python -m pytest
tests/ci/test_reconcile_shards.py -q` unchanged and green (baseline re-run).

## Subtask T015: Gate verification and untouched-file proof

**Purpose**: Confirm this WP's diff is gate-clean and that `reconcile_shards.py` is
genuinely untouched.

**Steps**:
1. Run `git diff --stat -- scripts/ci/reconcile_shards.py` (or equivalent) against this WP's
   base and confirm zero lines changed — `reconcile_shards.py` must not appear in this WP's
   diff at all, per Key Entities item 3 in spec.md.
2. Re-run `tests/ci/test_reconcile_retry.py` (WP01's own tests) unmodified to confirm this WP
   did not regress the shared primitive.
3. Run `.venv/bin/python -m pytest tests/ci/test_wait_for_artifacts.py -q` standalone —
   green, fast (injected `sleep`, no real waiting).
4. Run `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` scoped at
   minimum to `scripts/ci/wait_for_artifacts.py` and `tests/ci/test_wait_for_artifacts.py`.
5. Run `uv run --frozen ruff check --select TID251 .` and confirm nothing new is flagged.
6. Note in your completion notes: this WP additionally triggers the `.github/workflows/**`
   surface (per `.github/ci-module-registry.yml`'s `ci` module row `roots:` including that
   path) — the same `ci-modules.yml` `ci` shard gate WP01/WP02 trigger also covers this WP's
   workflow-YAML change; there is no separate workflow-lint gate to run beyond the YAML
   parse check in T013.

**Files**: none new — verification only.

**Validation**: `pytest`, `ruff check`, `ruff format --check` all green; `git diff` proves
`reconcile_shards.py` untouched.

## Definition of Done

- `scripts/ci/wait_for_artifacts.py` exists: reads the registry/selection via
  `reconcile_shards.parse_registry`/`read_selected_modules` (imported, not re-derived),
  computes must-be-fresh shard artifact names via `select_source_artifacts.py`'s existing
  naming convention (imported/reused), polls via `fleet_verdict.py`'s `GitHub`/`GitHubCLI`
  boundary wrapped in WP01's `retry_with_backoff` (8 attempts, 5s→10s→20s→30s-cap backoff),
  and always exits 0 (never raises, never sets a failing exit code) regardless of outcome.
- `.github/workflows/ci-aggregate.yml`'s `collect` job step order matches the "Required new
  step order" list above exactly; the new step's `env:` block declares all four variables
  (`GH_TOKEN`, `SOURCE_RUN_ID`, `SOURCE_RUN_ATTEMPT`, `SOURCE_REPOSITORY`) — this is a
  previously-identified, operator-accepted finding (plan.ruling.md PLAN-FRESH2-001) and must
  not regress.
- `scripts/ci/reconcile_shards.py` is provably unchanged (zero diff) — it gains a new
  *importer* only.
- `tests/ci/test_wait_for_artifacts.py` covers: recovery-within-budget (artifact absent then
  present), exhausted-budget termination (never raises, exit 0, diagnostic printed), and a
  composing test proving `reconcile_shards.py::main()` still fails closed when the poller's
  budget is exhausted and a shard is genuinely still absent.
- Git history shows a red-first commit (new tests + a single-attempt stub, failing the way a
  transient artifact-visibility gap fails today) preceding the full `retry_with_backoff`
  implementation commit, per charter C-011.
- `tests/ci/test_wait_for_artifacts.py` and `tests/ci/test_reconcile_shards.py` (baseline,
  unmodified) both pass; `ruff check .` / `ruff format --check .` clean for this WP's three
  files (C-005); no new TID251 findings.
- No new third-party dependency added (NFR-002/C-004).

## Risks

- **GH_TOKEN omission risk (already once identified and accepted as a finding)**: dropping
  `GH_TOKEN` from the new step's `env:` block silently produces a step that raises `KeyError`
  on every real run, invisible to NFR-003's mocked unit tests (which never exercise a real
  workflow `env:` block). Triple-check the YAML before considering this WP done.
- **Full-registry-polling regression risk**: polling the entire registry instead of only the
  SELECTED set would silently reintroduce a multi-minute latency tax on every diff-scoped PR
  and make "budget exhausted" logs meaningless for on-call triage. Verify your `must-be-fresh`
  predicate matches `reconcile()`'s own, not a broader one.
- **Artifact-naming drift risk**: reimplementing the artifact-name regex independently
  instead of importing `select_source_artifacts.py`'s existing one risks silent drift between
  the two if either is ever changed later. Import, don't duplicate.
- **Reorder side-effect risk**: moving `download-selected-modules` earlier could interact
  with something later in the job that this plan's reading did not catch. Re-verify against
  the live file yourself (T013 step 3), not just this prompt's summary.

## Reviewer Guidance

Verify the new step's `env:` block literally contains all four variables including
`GH_TOKEN` — this is the exact defect a prior review round already caught once. Verify
`reconcile_shards.py` has zero diff. Verify the red-first stub-based test failure is genuine
(run the stub version yourself, confirm it fails the stated way) rather than trusting the
PR description. Verify the must-be-fresh predicate in `wait_for_artifacts.py` matches
`reconcile()`'s own predicate exactly, side by side. Verify the composing test in T014
actually exercises `reconcile_shards.py`'s real fail-closed path, not a mocked stand-in for
it.

Run: `spec-kitty agent action implement WP03 --agent claude`
