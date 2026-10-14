---
work_package_id: WP02
title: Wire resilience into the three module-test shards and pin it
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
- FR-005
- NFR-003
- C-001
- C-002
- C-004
- C-005
planning_base_branch: issue-6191-ci-uv-sync-resilience
merge_target_branch: issue-6191-ci-uv-sync-resilience
branch_strategy: Planning artifacts for this mission were generated on issue-6191-ci-uv-sync-resilience. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6191-ci-uv-sync-resilience unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
history: []
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/ci-router.yml
create_intent:
- tests/ci/test_uv_sync_resilience.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- tests/ci/test_uv_sync_resilience.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Wire resilience into the three module-test shards and pin it

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make the three CI Router module-test shards resilient to a transient install
download failure by (a) enabling the uv cache on their `setup-uv` step and
(b) routing their `uv sync --frozen --all-extras` through the WP01 helper. Add one
focused `tests/ci/` wiring test that reds if either resilience mechanism is removed.

## Context

Depends on **WP01** (the helper `scripts/ci/uv_sync_retry.py` must exist first).
The three shards are the only jobs sharing the `setup-uv` → `uv sync --frozen
--all-extras` → `pytest` module-test-shard pattern (grounding note §1):

- `tests-docs` (`tests (docs)`) — the issue's subject.
- `tests-e2e` (`tests (e2e)`).
- `tests-corpus-blocking` (`tests (corpus-blocking)`).

Critical grounding facts (grounding note §3):

- **No existing wiring test inspects these three shards' `uv sync`/`setup-uv`
  steps**, so adding `enable-cache: true` and the retry invocation needs **zero**
  re-pointing of existing tests.
- The one active guard on any new/edited `run:` block is
  `tests/ci/test_workflow_run_shell_syntax.py` (`bash -n` + no doubled trailing
  backslashes) — write valid bash with single `\` continuations.
- Do NOT touch the architectural battery jobs' `uv sync` (their step shape is
  pinned by `test_ci_module_wiring.py` / `test_ci_workflow_prestep_shape.py` via a
  `run_contains="uv sync"` finder) — keep this change inline and scoped (C-005).
- Do NOT change `router-gate.needs` or the routing-authority guards (C-001);
  do NOT touch `uv.lock`/`pyproject.toml`/pytest selection (C-002); add no new
  ratchet gate (C-004).

### Subtask T004: Failing-first wiring test (ATDD red)

**Purpose**: Pin the resilience so it cannot silently regress (FR-005), RED before
the workflow edit (ATDD-first), committed as this WP's first commit.

**Steps**:
1. Create `tests/ci/test_uv_sync_resilience.py`.
2. Parse `.github/workflows/ci-router.yml` with `yaml.safe_load` (follow the raw
   parse used by sibling tests; resolve the repo root the way `tests/ci` already
   does — e.g. via the module's `Path(__file__)` parents or an existing helper).
3. For each of `tests-docs`, `tests-e2e`, `tests-corpus-blocking`, assert:
   - its `setup-uv` step (the step whose `uses` starts with
     `astral-sh/setup-uv@`) has `with.enable-cache` equal to `true`; **and**
   - some `run:` step in the job routes the install through the helper — i.e. the
     run text contains both `scripts/ci/uv_sync_retry.py` and `uv sync`.
4. Add a focused negative-control assertion proving the test is non-vacuous: build
   an in-memory copy of one shard job with the cache input and the helper
   invocation stripped and assert the same predicate FAILS on it (so a future
   regression would red). Keep it a pure in-memory check (no file write).

**Files**: `tests/ci/test_uv_sync_resilience.py` (new, ~70 lines).
**Validation**: Before T005 the test is RED (the workflow lacks `enable-cache` and
the helper routing). Capture that RED as the first commit.

### Subtask T005: Wire cache + retry into the three shards (green)

**Purpose**: Make T004 green by hardening exactly the three shards.

**Steps**:
1. In `.github/workflows/ci-router.yml`, for `tests-docs`, `tests-e2e`, and
   `tests-corpus-blocking`, add to each `astral-sh/setup-uv` step's `with:` block:
   ```yaml
       enable-cache: true
   ```
   (keep the existing `python-version: '3.12'`; keep the pinned action SHA).
2. In each of the three shards' install line, replace
   `uv sync --frozen --all-extras` with
   `python3 scripts/ci/uv_sync_retry.py uv sync --frozen --all-extras`.
   Keep the subsequent `uv run --frozen pytest …` line(s) byte-identical. The
   default `bash -eo pipefail` shell means a non-zero retry-helper exit fails the
   step before pytest runs (preserving the honest red; FR-003).
3. Do not add a step-level `if:`, `continue-on-error`, or any `|| true` / `set +e`
   / `exit 0` soft-fail idiom. Do not split pytest into a separate step unless
   necessary (smallest-viable-diff; keep the corpus-blocking `run:` step present
   for `test_workflow_run_shell_syntax.py` non-vacuity).
4. Leave every other `uv sync` job (architectural battery, `tests-contract-tools`,
   `mission-state-audit`, shift-left/fast gates) untouched (C-005).

**Files**: `.github/workflows/ci-router.yml` (edit 3 jobs; ~9 changed lines).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_uv_sync_resilience.py -q`
is GREEN.

### Subtask T006: Guard-suite + targeted validation

**Purpose**: Prove no pre-existing CI wiring guard regressed and the bash is valid
(NFR-003).

**Steps**:
1. `.venv/bin/python -m pytest tests/ci -q` (the owning dir for CI wiring).
2. Run the specific workflow-shape guards named in grounding §3 that could be
   implicated: `tests/ci/test_workflow_run_shell_syntax.py`,
   `tests/ci/test_ci_module_wiring.py`, `tests/ci/test_ci_workflow_prestep_shape.py`,
   and `tests/architectural/test_no_duplicate_suite_execution.py`
   (specific files only — never a bare `tests/architectural/` sweep, per
   `NO_FULL_HEAVY_SUITES_IN_MISSION`).
3. Confirm `git diff` touches no `uv.lock`, `pyproject.toml`, `router-gate.needs`,
   or any pytest selection (C-001/C-002).

**Files**: none beyond T004/T005.
**Validation**: all targeted suites GREEN; diff scope confirmed.

## Definition of Done

- All three shards set `enable-cache: true` on `setup-uv` and route `uv sync`
  through `scripts/ci/uv_sync_retry.py`.
- `tests/ci/test_uv_sync_resilience.py` was RED before the workflow edit, is GREEN
  after, and its negative control proves removing the resilience reds it (FR-005).
- `tests/ci/` plus the named workflow-shape guards are GREEN; no guard was loosened
  (NFR-003).
- No change to `uv.lock`, `pyproject.toml`, `router-gate.needs`, pytest selection,
  or any out-of-scope `uv sync` job (C-001/C-002/C-005); no new ratchet gate (C-004).
- Each subtask recorded via `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- **Bash validity**: the edited `run:` block must pass `bash -n` — single `\`
  continuations, no doubled backslashes.
- **Accidental scope creep**: resist hardening the architectural battery or other
  `uv sync` jobs — it widens blast radius against their step-shape tests (C-005).
- **PYTHONPATH**: the helper is invoked by path (`python3 scripts/ci/…`), not
  `-m`, so no PYTHONPATH is needed in the shard.

## Reviewer Guidance

- Confirm only `tests-docs`/`tests-e2e`/`tests-corpus-blocking` changed, and only
  their `setup-uv` `with:` + install line.
- Confirm `router-gate.needs` (workflow lines ~1256–1275) is byte-identical.
- Confirm the wiring test's negative control actually fails on a stripped job
  (non-vacuous) and that removing `enable-cache` OR the helper routing reds it.
- Confirm no soft-fail idiom was introduced that would mask a real install failure.

Implement with:
`spec-kitty agent action implement WP02 --agent claude --mission ci-uv-sync-resilience-01M4VDBW`
