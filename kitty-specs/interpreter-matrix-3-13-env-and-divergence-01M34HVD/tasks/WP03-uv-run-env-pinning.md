---
work_package_id: WP03
title: Pin interpreter/extras on the uv run step (FR-001), ATDD-first
dependencies: []
requirement_refs:
- FR-001
- NFR-002
- C-004
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- tests/ci/test_interpreter_matrix_env_pinning.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- tests/ci/test_interpreter_matrix_env_pinning.py
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Pin interpreter/extras on the uv run step (FR-001), ATDD-first

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select
the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make the `interpreter-matrix` job's `uv run` step in
`.github/workflows/ci-nightly.yml` actually use the interpreter/extras the
preceding `uv sync` step resolved, instead of silently re-syncing to
`.python-version`'s 3.11.15 with default (non-`test`) extras — this is the
entire root cause of issue #4866 (7 consecutive nights of false-red
`ModuleNotFoundError` collection errors for `pytestarch`/`respx`/
`pytest_benchmark`).

## Context

**This is the mission's core fix and its most CI-safety-net-free change** —
see "Verification" below. It is a small, precise, single-line-class flag
addition, but C-004 (charter ATDD-first, binding) requires a genuine
failing-first test for it, committed **before** the implementation commit —
unlike WP02, this WP's ATDD pinning IS a new test file.

**Exact target** (verified live in this checkout; re-verify line numbers
against your own checkout before editing):
- `.github/workflows/ci-nightly.yml:205` — the `uv sync` step:
  `run: uv sync --frozen --all-extras --python "${{ matrix.python-version }}"`
  (already correct — do NOT touch this line).
- `.github/workflows/ci-nightly.yml:212` — the `uv run` step, inside a
  multi-line `run: |` block:
  `uv run --frozen pytest -m "fast or unit" -q --junitxml="out/reports/xunit-nightly-interpreter-${{ matrix.python-version }}.xml"`
  — **this line is missing `--python "${{ matrix.python-version }}"
  --all-extras`**. This is the fix target.

**Fix shape (FR-001 acceptance criterion)**: add `--python "${{
matrix.python-version }}" --all-extras` to this `uv run` invocation. The
readiness report also considered `--no-sync` as an alternative (trusting the
prior sync rather than re-stating flags), but the explicit-flags form is
preferred: it fails loudly (a mismatched flag value would be visibly wrong in
the command itself) rather than silently trusting a possibly-stale prior
sync — matching NFR-002 and the mission's anti-silent-success stance (see
spec.md's Reflexivity section: this entire issue IS a silent-success
failure, `uv run` silently rebuilding the environment).

**Must not begin until WP01's baseline capture is complete.** This is an
**ordering constraint, not a data dependency**: nothing in this WP consumes
an artifact WP01 produces — the requirement is that the 3.11 baseline be
captured before any change lands, so pre-existing reds are not
misattributed to this mission. Per SK-25, that ordering is enforced by the
orchestrator's **dispatch sequencing** (do not dispatch WP03 until WP01 is
`approved`/`done`) and by this prose, not by a `dependencies:` edge in
`wps.yaml` — this WP's frontmatter carries `dependencies: []`. It has no
ordering requirement relative to WP02/WP04 among themselves. Per plan.md's
IC-03 "naturally lands before IC-07" note, it should also land on the
mission branch well before WP07 (final verification) dispatches the real
job.

**`--base` note**: because this ordering requirement is not encoded as a
`dependencies:` edge, `lanes.json`'s `lane-b` (which holds WP03) correctly
carries `depends_on_lanes: []`, and `worktree_allocator.py`'s
`_guard_base_honorable` "dependency_lane" safety guard has nothing to
enforce here — it is not a gap, since there is no data dependency for it to
guard. The ordering requirement is still real, though, so confirm WP01 has
already landed on the mission branch before implementing this WP; an
explicit `--base` is not recommended since there is no tooling check behind
it for this WP. See `tracer-tooling-friction.md`'s SK-25 entry for the full
correction.

**Write-scope note**: this WP is the sole owner of
`.github/workflows/ci-nightly.yml` in this mission's `wps.yaml`. WP04 (the
venv-corruption spike) does *not* list this file in its own `owned_files` —
if WP04's fallback branch needs to add a `UV_PROJECT_ENVIRONMENT` env key to
the same `interpreter-matrix` job, that lands as a small, explicitly
authorized out-of-map edit on WP04's side (see WP04's own prompt for the
rationale) rather than a second WP claiming this file. If you are
implementing WP03 and WP04 concurrently in separate worktrees, coordinate
so your edits (a `run:` string change here, a possible `env:` key addition
there) do not silently clobber each other at lane-merge time — they touch
different, non-overlapping parts of the same job block, so an ordinary git
merge should reconcile them cleanly, but confirm this at PR-prep if both
land.

## Subtask T001: Write the ATDD test file (RED-first, own commit)

**Purpose**: Pin the fix's contract with a failing-first test, per charter
C-011 and spec C-004.

**Steps**:
1. Create `tests/ci/test_interpreter_matrix_env_pinning.py`. Precedent for
   parsing GitHub Actions workflow YAML directly with `yaml.safe_load` in
   this repo: `scripts/ci/gate_selection.py` does this for `ci-router.yml`.
   Precedent for a `tests/ci/` test parsing a non-Python artifact by loading
   the file directly: `tests/ci/test_sonar_project_version.py`.
2. The test must, concretely:
   a. `yaml.safe_load()` the real `.github/workflows/ci-nightly.yml` (load
      the file from its actual repo-relative path — do not hardcode a copy
      of its content into the test).
   b. Walk to `workflow["jobs"]["interpreter-matrix"]["steps"]`, find the
      step whose `run:` string contains `pytest -m "fast or unit"` (this is
      the `uv run` step, distinct from the earlier `uv sync` step).
   c. Assert **that step's own `run:` string** — not the job's or file's
      full YAML text — contains both `--python` and `--all-extras` (or
      `--no-sync`, but this WP implements the explicit-flags form, so assert
      for `--python`/`--all-extras` specifically). This precision is
      load-bearing per C-004: the preceding `uv sync` step already carries
      `--python --all-extras`, so a whole-text match against the job or file
      would be vacuously green even before the fix lands — you must isolate
      the specific step's `run:` string.
3. `PyYAML` is already a project dependency (used by
   `scripts/ci/gate_selection.py`) — no new dependency needed.
4. Commit this test file **as its own commit**, before any implementation
   change to `ci-nightly.yml` — the commit message should make clear this is
   the ATDD red-first commit (e.g. `test(ci): pin interpreter-matrix uv run
   step's flags (RED, #4866)`).

**Files**: `tests/ci/test_interpreter_matrix_env_pinning.py` (new file,
~40-80 lines).

**Validation**: covered by T002.

## Subtask T002: Confirm RED

**Purpose**: Prove the test actually fails against the current (unfixed)
workflow file — this is the concrete RED evidence C-011 requires.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/ci/test_interpreter_matrix_env_pinning.py -v
   ```
2. Confirm it fails (RED) — the failure should be specifically because the
   `uv run` step's `run:` string lacks `--python`/`--all-extras`, not a
   collection error, import error, or an assertion about the wrong step.
   If it errors instead of failing an assertion (e.g. `KeyError` on
   `workflow["jobs"]["interpreter-matrix"]`), fix the test's own YAML-walking
   logic before proceeding — a collection/attribute error is not the RED
   this WP needs.

**Files**: none (verification only).

**Validation**: The test fails with a clear assertion message naming the
missing flags on the `uv run` step specifically.

## Subtask T003: Add the flags fix

**Purpose**: Turn the T001 test GREEN.

**Steps**:
1. In `.github/workflows/ci-nightly.yml`, edit the `uv run` step's `run:`
   string (line ~212). The current text (verify against your own checkout
   before editing, since line numbers drift):
   ```
   uv run --frozen pytest -m "fast or unit" -q --junitxml="out/reports/xunit-nightly-interpreter-${{ matrix.python-version }}.xml"
   ```
   `uv run`'s own CLI grammar is `uv run [OPTIONS] [COMMAND]...` — once the
   command word `pytest` appears, every subsequent token is passed through
   to `pytest`, not consumed by `uv run`. So the two new flags
   (`--python "${{ matrix.python-version }}" --all-extras`) MUST be inserted
   **between `uv run --frozen` and `pytest`**, not appended after the
   existing `pytest` arguments. The exact resulting `run:` string must be:
   ```
   uv run --frozen --python "${{ matrix.python-version }}" --all-extras pytest -m "fast or unit" -q --junitxml="out/reports/xunit-nightly-interpreter-${{ matrix.python-version }}.xml"
   ```
   Every other existing argument/path (`--frozen`, `pytest -m "fast or
   unit"`, `-q`, `--junitxml=...`) is preserved unchanged, in its original
   order, relative to `pytest` — only the two new flags are inserted, and
   only in the `uv run`-options position before the `pytest` command word.
2. Do not touch the `uv sync` step (line ~205) — it already carries the
   correct flags (in the correct position, since `uv sync` takes no
   subcommand word to trip over) and is not the defect.
3. Commit this as a separate commit from T001's test commit (e.g. `fix(ci):
   pin interpreter/extras on interpreter-matrix's uv run step (#4866)`).

**Files**: `.github/workflows/ci-nightly.yml` (1-line addition inside the
existing `run:` string).

**Validation**: covered by T004.

## Subtask T004: Confirm GREEN

**Purpose**: Prove the fix works, paired with T002's RED evidence.

**Steps**:
1. Re-run:
   ```bash
   .venv/bin/python -m pytest tests/ci/test_interpreter_matrix_env_pinning.py -v
   ```
2. Confirm it now passes.

**Files**: none (verification only).

**Validation**: The test passes against the fixed workflow file.

## Subtask T005: Local reproduction of the exact command pair

**Purpose**: User Story 1 Acceptance Scenario 2 — prove the fix actually
behaves correctly when run for real, not just that the YAML now contains the
right substring (the YAML-parsing test in T001-T004 proves the *workflow
file's contract*; this subtask proves the *runtime behavior* the contract is
meant to guarantee).

**Steps**:
1. On a real Python 3.13 interpreter, run the exact `uv sync` + fixed `uv
   run` step pair, mirroring `ci-nightly.yml`'s own commands byte-for-byte
   (substitute a literal `3.13` for the `${{ matrix.python-version }}`
   GitHub Actions expression, since this is a local reproduction, not an
   Actions run):
   ```bash
   uv sync --frozen --all-extras --python 3.13
   uv run --frozen --python 3.13 --all-extras pytest -m "fast or unit" -q \
     --junitxml=out/reports/xunit-nightly-interpreter-3.13.xml
   ```
   Note the flag order: `--python 3.13 --all-extras` sit **between** `uv run
   --frozen` and `pytest` — once the `pytest` command word appears, `uv
   run` passes everything after it straight through to `pytest`, so flags
   placed after `pytest` would be parsed (and rejected) as pytest arguments,
   not consumed by `uv run`.
   Apply an explicit bounded timeout (≥600s, comfortably above the ~411s
   3.13 baseline per NFR-001/SK-99) and run in the foreground — do not let
   this strand past the 120s auto-background cliff.
2. Confirm the invocation shows Python 3.13's site-packages path in use and
   **zero** `ModuleNotFoundError` for `pytestarch`, `respx`, or
   `pytest_benchmark` — this is the exact "was: 13 such collection errors"
   signature from SC-001, now expected to be absent.
3. Record the outcome (pass/fail counts are informative but not this WP's
   concern — WP04/WP05 own the actual failure-count investigation; this
   subtask only needs to confirm the *environment* is now correct, i.e. no
   `ModuleNotFoundError` collection errors).

**Files**: none (verification only).

**Validation**: 3.13 site-packages confirmed in use; zero
`ModuleNotFoundError` for the three named test-extra packages.

## Definition of Done

- [ ] T001: ATDD test committed as its own commit, before any
      implementation change
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: RED confirmed against the current (unfixed) workflow file
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: flags fix landed, in a separate commit from T001
      (`spec-kitty agent tasks mark-status T003 --status done`).
- [ ] T004: GREEN confirmed against the fixed workflow file
      (`spec-kitty agent tasks mark-status T004 --status done`).
- [ ] T005: local repro of the real command pair on 3.13 shows correct
      interpreter/extras and zero `ModuleNotFoundError`
      (`spec-kitty agent tasks mark-status T005 --status done`).
- [ ] `ruff check` / `ruff format --check` pass on the new test file.
- [ ] `uv.lock` untouched (no new dependency — `PyYAML` is already
      available).

## Risks

- **Low** — a single-line-class flag addition. The only real risk is
  scoping the ATDD assertion too broadly (matching the whole job/file text
  instead of the specific `uv run` step's `run:` string), which would make
  the test vacuously green even before the fix — see T001 step 2c's
  explicit warning about this exact failure mode.
- **No CI safety net for this file** (C-003): `ci-nightly.yml` triggers on
  `schedule`/`workflow_dispatch` only. T005's local repro is this WP's own
  best verification; WP07's manual `workflow_dispatch` (operator-authorized)
  is the only check that exercises the real job end-to-end, and it is
  sequenced last in this mission, after every other WP has landed.

## Reviewer Guidance

- Confirm T001's commit predates T003's commit in the branch history (`git
  log --oneline`) — the ATDD test-first-then-fix ordering is load-bearing,
  not just a suggestion.
- Re-run T002's exact command against the WP's `planning_base_branch` and
  confirm RED there independently; re-run against the final commit and
  confirm GREEN.
- Confirm the test asserts against the **specific step's** `run:` string,
  not the whole job/file YAML text (open the test file and check the
  assertion target directly).
- Confirm the `uv sync` step (line ~205) was NOT modified — only the `uv
  run` step's flags changed.
- Confirm T005's local repro was actually performed (ask for the captured
  pytest output showing 3.13 site-packages / zero `ModuleNotFoundError`),
  not asserted from "the flags are obviously correct now."

Implementation command: `spec-kitty agent action implement WP03 --agent claude`
