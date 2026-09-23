---
work_package_id: WP02
title: Fix the 4 confirmed dir_fd kernel test-double failures (FR-002)
dependencies: []
requirement_refs:
- FR-002
- NFR-003
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-interpreter-matrix-3-13-env-and-divergence-01M34HVD
base_commit: 203059f87d08885e3701a32f51aaa38282e772e7
created_at: '2026-09-22T17:59:38.584983+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history: []
agent_profile: python-pedro
authoritative_surface: tests/kernel/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/kernel/test_lock_parity.py
- tests/kernel/test_no_follow.py
- tests/specify_cli/core/test_no_follow.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Fix the 4 confirmed dir_fd kernel test-double failures (FR-002)

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

Widen the two kernel/core test-double shims — `_WindowsMandatoryLockSimulator
.wrap_open`'s inner `_open` function (`tests/kernel/test_lock_parity.py`), and
the `plant_symlink` monkeypatch shim duplicated in
`tests/kernel/test_no_follow.py` and `tests/specify_cli/core/test_no_follow.py`
— to accept and pass through the `dir_fd` keyword argument that Python 3.13's
`shutil.rmtree` now legitimately passes to `os.open`, so these test doubles
stop masquerading as a product regression on 3.13.

## Context

**Standing Order 4 classification (binding on this WP)**: this is a **stale
test double**, not a product defect. Python 3.13's `shutil.rmtree`
legitimately changed its implementation to call `os.open(..., dir_fd=...)`;
the test doubles below were written before that change and don't model the
new kwarg, so they raise `TypeError: ... got an unexpected keyword argument
'dir_fd'` when 3.13's `rmtree` (invoked by pytest's own `tmp_path` teardown,
or directly by the simulator's own test) calls through them. Fix at the
shim level — **never** by relaxing the underlying assertion or narrowing
what the test verifies.

**Exact shim locations** (verified live in this checkout; re-verify against
your own checkout before editing, since line numbers drift):
- `tests/kernel/test_lock_parity.py:197` — `class
  _WindowsMandatoryLockSimulator:`; `:213` — `def wrap_open(self, real_open:
  Callable[..., int]) -> Callable[..., int]:`; `:214` — `def _open(path: str,
  flags: int, mode: int = 0o777) -> int:` — this inner function's signature
  is the fix target.
- `tests/kernel/test_no_follow.py:75` — `def plant_symlink(candidate: str |
  Path, flags: int, mode: int = 0o777) -> int:` inside
  `test_read_rejects_symlink_planted_before_open` (starts at `:66`).
- `tests/specify_cli/core/test_no_follow.py:65` — the same `plant_symlink`
  shim, independently duplicated in this second copy of
  `test_read_rejects_symlink_planted_before_open` (starts at `:56`).

**ATDD note (spec C-004, binding — read carefully, this WP's red-first shape
is NOT a new test file)**: per spec C-004, the ATDD pinning for this WP **is
the pre-existing tests' own current RED state on 3.13** — there is no new
test file to write and no new commit to sequence before an implementation
commit. Subtask T001 below (running the pre-fix command and recording the
current ERROR IDs) **is** the red-first evidence; `planning_base_branch`
already carries this RED state. The only commit this WP needs is the fix
commit itself. The reviewer's job (see "Reviewer Guidance") is to re-run the
exact same command on the WP's base commit (still RED) and on the WP's final
commit (GREEN) — do not skip T001 thinking it's optional scaffolding; it is
the load-bearing red-first evidence this WP's entire ATDD compliance rests
on.

**This WP does not touch any `src/` file.** Per plan.md's "Kernel coverage
floor" section, this fix widens two existing helper *signatures* only — zero
new lines land under `src/kernel/**`. The `ci-aggregate.yml` diff-cover ≥90%
gate scores changed critical-path lines under `src/` only, so this WP's diff
cannot fail that gate by construction (there is no changed `src/` line for it
to score).

**Must not begin until WP01's baseline capture is complete.** This is an
**ordering constraint, not a data dependency**: nothing in this WP consumes
an artifact WP01 produces — the requirement is that the 3.11 baseline be
captured before any change lands, so pre-existing reds are not
misattributed to this mission. Per SK-25, that ordering is enforced by the
orchestrator's **dispatch sequencing** (do not dispatch WP02 until WP01 is
`approved`/`done`) and by this prose, not by a `dependencies:` edge in
`wps.yaml` — this WP's frontmatter carries `dependencies: []`. It has no
ordering requirement relative to WP03/WP04 among themselves and can run in
parallel with them once WP01 has landed.

**`--base` note**: because this ordering requirement is not encoded as a
`dependencies:` edge, `lanes.json`'s `lane-a` (which holds WP02) correctly
carries `depends_on_lanes: []`, and `worktree_allocator.py`'s
`_guard_base_honorable` "dependency_lane" safety guard has nothing to
enforce here — it is not a gap, since there is no data dependency for it to
guard. The ordering requirement is still real, though, so confirm WP01 has
already landed on the mission branch before implementing this WP; an
explicit `--base` is not recommended since there is no tooling check behind
it for this WP. See `tracer-tooling-friction.md`'s SK-25 entry for the full
correction.

## Subtask T001: Capture pre-fix RED on 3.13 (the ATDD evidence)

**Purpose**: Record the exact currently-ERRORing test IDs on a real Python
3.13 interpreter, **before** any shim-signature change — this run is this
WP's red-first ATDD evidence per spec C-004.

**Steps**:
1. Confirm you are on a Python 3.13 interpreter / synced `.venv`
   (`.venv/bin/python --version`; `uv sync --frozen --all-extras --python
   3.13` first if needed).
2. Run:
   ```bash
   .venv/bin/python -m pytest tests/kernel/test_lock_parity.py \
     tests/kernel/test_no_follow.py \
     tests/specify_cli/core/test_no_follow.py -v
   ```
3. Record the exact ERRORing test node IDs. Spec.md expects **5 total**: 3 in
   `test_lock_parity.py` (including
   `test_naive_second_open_of_a_held_lock_raises_under_simulation` and its
   two sibling tests in the same file — enumerate them from this run's own
   output, do not guess the other two names in advance), and one
   non-parametrized `test_read_rejects_symlink_planted_before_open` in each
   of the two separate `test_no_follow.py` copies. If your real run's count
   or IDs differ, record what you actually observed.

**Files**: none modified — this is the pre-fix baseline capture.

**Validation**: The exact ERROR-ing node IDs are recorded verbatim (you will
cite them again in T005/T006 and in your WP completion report).

## Subtask T002: Widen `_WindowsMandatoryLockSimulator.wrap_open`'s shim

**Purpose**: Fix the `test_lock_parity.py` shim.

**Steps**:
1. In `tests/kernel/test_lock_parity.py`, change the inner `_open` function's
   signature (currently `def _open(path: str, flags: int, mode: int =
   0o777) -> int:`) to accept `dir_fd` and pass it through to the wrapped
   `real_open` call — either an explicit `dir_fd: int | None = None`
   parameter (matching FR-002's acceptance criterion's preferred shape) or
   `**kwargs`, whichever keeps the function's existing type-narrowness best;
   `dir_fd: int | None = None` is preferred since it keeps the signature
   self-documenting and passes `mypy --strict` cleanly.
2. Ensure the `real_open(...)` call inside `_open` forwards `dir_fd` when the
   wrapped call site passes it — the shim's entire purpose is to intercept
   then delegate, so the delegation must carry the new kwarg through, not
   just silently accept and drop it (dropping it would make the shim's
   *simulation* wrong even though it stops the `TypeError`).

**Files**: `tests/kernel/test_lock_parity.py` (~5-10 line change).

**Validation**: covered by T005 (post-fix GREEN run).

## Subtask T003: Widen `plant_symlink` in `tests/kernel/test_no_follow.py`

**Purpose**: Fix the first `plant_symlink` shim copy.

**Steps**:
1. In `tests/kernel/test_no_follow.py:75`, widen `plant_symlink`'s signature
   the same way as T002 (`dir_fd: int | None = None`, forwarded to whatever
   the shim delegates to internally).

**Files**: `tests/kernel/test_no_follow.py` (~5 line change).

**Validation**: covered by T005.

## Subtask T004: Widen `plant_symlink` in `tests/specify_cli/core/test_no_follow.py`

**Purpose**: Fix the second, independently-duplicated `plant_symlink` shim
copy — do not assume fixing one file also fixes the other; they are separate
functions in separate files (per spec.md's own "two separate `test_no_follow.py`
copies" framing).

**Steps**:
1. In `tests/specify_cli/core/test_no_follow.py:65`, apply the identical
   widening as T003.

**Files**: `tests/specify_cli/core/test_no_follow.py` (~5 line change).

**Validation**: covered by T005.

## Subtask T005: Confirm GREEN on 3.13

**Purpose**: Prove the fix works — this is the ATDD green-after evidence
paired with T001's red-before evidence.

**Steps**:
1. Re-run the exact same command as T001:
   ```bash
   .venv/bin/python -m pytest tests/kernel/test_lock_parity.py \
     tests/kernel/test_no_follow.py \
     tests/specify_cli/core/test_no_follow.py -v
   ```
2. Confirm 0 errors — specifically confirm the exact node IDs recorded in
   T001 now pass, not just that the overall exit code is 0 (a marker
   mismatch or collection change could produce a misleading "0 errors" for
   the wrong reason).

**Files**: none (verification only).

**Validation**: 0 errors, and the specific T001 node IDs are confirmed
passing by name.

## Subtask T006: Confirm NFR-003 (no 3.11/3.12 behavior change)

**Purpose**: Prove the shim widening only *widens* what's accepted — it must
not change observed behavior on the CI floor interpreters.

**Steps**:
1. On a Python 3.11 interpreter (re-sync if needed:
   `uv sync --frozen --all-extras --python 3.11`), run the exact same
   command as T001/T005 **before** your fix is present (e.g. against the
   WP's base commit / `git stash` your changes temporarily) and record the
   outcome.
2. Run the same command again on 3.11 **after** your fix (unstash /
   checkout your changes). Confirm the counts and outcomes are **identical**
   before and after — no new failures, no newly-passing tests that were
   previously failing for an unrelated reason, no changed skip/xfail count.
3. If a 3.12 interpreter is readily available in your environment, repeat
   the same before/after comparison on 3.12; if not, state explicitly in
   your completion report that only 3.11 was directly verified and 3.12 is
   inferred to behave identically by the same code-path reasoning (the
   `dir_fd` parameter is additive and optional; 3.11/3.12's `shutil.rmtree`
   never passes it, so the new parameter's default is exercised
   identically to the pre-fix implicit absence).

**Files**: none (verification only).

**Validation**: 3.11 before/after outcomes are identical, recorded
explicitly (not asserted from confidence alone).

## Definition of Done

- [ ] T001: pre-fix RED captured on 3.13, exact ERROR node IDs recorded
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: `_WindowsMandatoryLockSimulator.wrap_open`'s `_open` shim
      accepts and forwards `dir_fd`
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: `tests/kernel/test_no_follow.py`'s `plant_symlink` shim accepts
      and forwards `dir_fd`
      (`spec-kitty agent tasks mark-status T003 --status done`).
- [ ] T004: `tests/specify_cli/core/test_no_follow.py`'s `plant_symlink`
      shim accepts and forwards `dir_fd`
      (`spec-kitty agent tasks mark-status T004 --status done`).
- [ ] T005: post-fix GREEN confirmed on 3.13 for the exact T001 node IDs
      (`spec-kitty agent tasks mark-status T005 --status done`).
- [ ] T006: NFR-003 cross-interpreter neutrality confirmed via explicit
      3.11 before/after comparison
      (`spec-kitty agent tasks mark-status T006 --status done`).
- [ ] `ruff check` and `ruff format --check` pass on the three touched files
      (blocking gate — `ci-quality.yml`'s `lint` job runs these directly).
- [ ] `mypy --strict` run locally as discipline (not a CI safety net — no
      live workflow invokes mypy in this checkout).

## Risks

- **Low.** Per plan.md's Charter Check: the fix widens existing shim
  signatures to accept an additional optional kwarg; it does not narrow or
  remove any existing behavior. The concrete guard against a behavior
  regression is T006's explicit before/after 3.11 comparison — do not skip
  it or treat it as obviously safe without running it.
- **Do not accidentally "fix" the underlying product behavior.** There is no
  `src/` change in this WP. If you find yourself wanting to touch
  `src/kernel/` or any other `src/` path to make this pass, stop — that is
  out of this WP's and this mission's C-001 blast radius; the correct fix is
  always at the test-double level for this specific defect.

## Reviewer Guidance

- Confirm T001's captured node IDs are re-run on the WP's `planning_base_branch`
  and independently confirmed RED there, and re-run on the WP's final commit
  and confirmed GREEN — this is the concrete red→green verification C-011
  requires, substituting for a new-test-file commit per spec C-004's explicit
  narrow reading.
- Confirm the diff touches only the three named test files, and only their
  shim signatures — no `src/` file, no change to the actual test assertions
  (`assert ...` lines) themselves, only the inline shim helper widening.
- Confirm T006's 3.11 before/after comparison was actually run (ask for the
  two outcome summaries), not asserted from "the change is obviously
  additive."
- Confirm `ruff check .` / `ruff format --check .` pass on the touched files
  (this IS a blocking CI gate, unlike `mypy`/`make lint`/`make typecheck`).

Implementation command: `spec-kitty agent action implement WP02 --agent claude`
