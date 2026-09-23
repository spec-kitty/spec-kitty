---
work_package_id: WP04
title: Root-cause or timebox-and-fallback the venv-corruption hazard (FR-003)
dependencies: []
requirement_refs:
- FR-003
- NFR-001
- NFR-002
- C-001
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history: []
agent_profile: debugger-debbie
authoritative_surface: tests/upgrade/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/upgrade/**
- tests/specify_cli/upgrade/**
- tests/specify_cli/skills/**
role: implementer
tags: []
tracker_refs: []
---

# WP04 — Root-cause or timebox-and-fallback the venv-corruption hazard (FR-003)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `debugger-debbie`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select
the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Identify — or make a bounded, documented attempt to identify — which test or
fixture causes the shared `.venv` to be silently rebuilt from Python 3.13
back to 3.11 mid-run under `-n auto` parallel execution, so the 3.13
divergence figure WP05 re-measures is measured against a *stable*
environment. This is **the mission's largest schedule risk** (plan.md names
it explicitly) — read this entire prompt, including the timebox and both
branches, before starting.

## Context — read completely before starting the spike

**Must not begin until WP01's baseline capture is complete.** This is an
**ordering constraint, not a data dependency**: nothing in this WP consumes
an artifact WP01 produces — the requirement is that the 3.11 baseline be
captured before any change lands, so pre-existing reds are not
misattributed to this mission. Per SK-25, that ordering is enforced by the
orchestrator's **dispatch sequencing** (do not dispatch WP04 until WP01 is
`approved`/`done`) and by this prose, not by a `dependencies:` edge in
`wps.yaml` — this WP's frontmatter carries `dependencies: []`. It has no
ordering requirement relative to WP02/WP03 among themselves and can run in
parallel with them once WP01 has landed. **WP05 does have a real data
dependency on this WP** (and, naturally, also on WP02) — WP05 consumes this
WP's fix/fallback outcome and cannot start until it has landed; that edge
is a genuine data dependency and remains declared in `wps.yaml`.

**`--base` note**: because this ordering requirement is not encoded as a
`dependencies:` edge, `lanes.json`'s `lane-c` (which holds WP04) correctly
carries `depends_on_lanes: []`, and `worktree_allocator.py`'s
`_guard_base_honorable` "dependency_lane" safety guard has nothing to
enforce here — it is not a gap, since there is no data dependency for it to
guard. The ordering requirement is still real, though, so confirm WP01 has
already landed on the mission branch before implementing this WP; an
explicit `--base` is not recommended since there is no tooling check behind
it for this WP. See `tracer-tooling-friction.md`'s SK-25 entry for the full
correction.

**The hazard, concretely**: under `-n auto` parallel `fast or unit` execution
against a 3.13 `.venv`, some `multiprocessing`-spawned child process reports
running under Python 3.11 while its parent worker reports 3.13 — the exact
signature the readiness report captured accidentally from
`tests/upgrade/test_migration_robustness.py::test_concurrent_upgrade_handled`.
The suspected cause is a nested test or fixture shelling out to `uv` without
pinning `--python`/`--all-extras` (or `--no-sync`), which can silently
re-target the *shared* `.venv` mid-run — the readiness report's own
suspicion is "plausibly something in the upgrade/skill-installer families
that legitimately shells out to `uv` while testing spec-kitty's own bootstrap
tooling," which is why this WP's `owned_files` are scoped to
`tests/upgrade/**`, `tests/specify_cli/upgrade/**`, and
`tests/specify_cli/skills/**` — the named suspect subsystems.

### The timebox (binding — do not exceed)

**3 hours of wall-clock investigation time, OR 5 `-n auto` reproduction
attempts against named suspect subsystems, whichever is reached first.**
Each `-n auto` reproduction of the `fast or unit` selector costs ~411s
(3.13) — 5 attempts is ~34 minutes of pure repro-run time, leaving ample
budget within 3 hours for the grep enumeration, cross-referencing, and
`-k`-subset narrowing steps below. **Track and record your elapsed time and
attempt count as you go** — do not discover you've blown the budget only in
retrospect.

### SK-99 discipline (binding on every command in this WP)

Every `-n auto` / `fast or unit` command you run in this WP MUST carry an
**explicit bounded timeout on the invocation itself** (not a shell default),
sized comfortably above ~411s (3.13, this mission's own measured baseline),
and MUST run in the **foreground**. Claude subagents auto-background any
command still running at 120s and then strand waiting for a completion
notification that never arrives — a plain, un-timed `-n auto` invocation in
this WP is exactly the shape that triggers this failure mode. Prefer
`-k`/path-scoped subsets over the full ~35k-item selector wherever the full
surface isn't actually needed for a specific narrowing step (T004) — reserve
the full selector for the initial reproduction (T003) and the final
regression confirmation.

### Exact investigation sequence

## Subtask T001: Enumerate candidate `uv` call sites

**Purpose**: Build the candidate list before attempting any reproduction.

**Steps**:
1. Run:
   ```bash
   grep -rn "uv sync\|uv run\|subprocess.*uv " tests/ src/
   ```
2. Record every hit — this is your candidate call-site list for T002's
   cross-referencing.

**Files**: none (investigation only).

**Validation**: A recorded, complete grep hit list.

## Subtask T002: Cross-reference against `fast or unit` collection

**Purpose**: Narrow the candidate list to modules that can actually run
during the reproduction, before spending a full `-n auto` attempt.

**Steps**:
1. Run (fast — collection-only, not a full run):
   ```bash
   .venv/bin/python -m pytest --collect-only -q -m "fast or unit"
   ```
2. Intersect T001's grep hits against this collection output — a candidate
   call site only matters if its containing module actually collects under
   the `fast or unit` marker set.
3. Record the narrowed candidate list, prioritizing the upgrade/skill-installer
   families the readiness report already suspects.

**Files**: none (investigation only).

**Validation**: A narrowed candidate list, prioritized by suspicion and by
actual `fast or unit` collection membership.

## Subtask T003: Reproduce with `-n auto` (attempt 1 of up to 5)

**Purpose**: Trigger the hazard — parallel execution is *required*; a serial
run will not reproduce it (the readiness report's own repro was itself
accidental, under `-n auto`).

**Steps**:
1. Build a hand-built, `UV_PROJECT_ENVIRONMENT`-isolated 3.13 `.venv`
   (mirroring the readiness report's own reproduction) so this reproduction
   doesn't corrupt your primary working `.venv` mid-investigation.
2. Run the full `fast or unit` selector with `-n auto` against that isolated
   venv, with an **explicit bounded timeout of at least 600s** (comfortably
   above the ~411s baseline), in the foreground:
   ```bash
   .venv/bin/python -m pytest -m "fast or unit" -q -n auto
   ```
3. Watch for the `multiprocessing.spawn`-child-reports-3.11 traceback
   signature. Record whether it reproduced on this attempt, and any partial
   evidence (which worker, which test module was running when it happened)
   even if it didn't cleanly reproduce.

**Files**: none (investigation only — this is attempt 1/5 of the timebox).

**Validation**: Either the hazard reproduced (proceed to T004's narrowing
with a concrete starting point) or it didn't (note this and proceed to T004
anyway, narrowing by suspicion rather than by a confirmed trigger).

## Subtask T004: Narrow via `-k` subsets by suspect subsystem

**Purpose**: Isolate a culprit without repeatedly re-running the full
~35k-item selector — this is what makes the remaining 4 timebox attempts
efficient rather than wasteful.

**Steps**:
1. Starting with the upgrade/skill-installer families (the readiness
   report's own first suspicion), run `-k`-scoped subsets with `-n auto`
   against the isolated venv, each with its own explicit bounded timeout
   (size proportionally to the subset — a `-k`-scoped run should be much
   faster than the full 411s baseline, but still bound it explicitly rather
   than assuming).
2. Continue narrowing across your remaining timebox budget (up to 4 more
   `-n auto` attempts, or until the 3-hour wall-clock limit, whichever
   first). Each attempt should narrow the candidate set further based on
   the previous attempt's outcome.
3. **The instant the timebox is exhausted (3 hours OR 5 total `-n auto`
   attempts including T003), stop investigating and proceed to T005's
   Branch B — do not "just try one more thing."** This is a hard boundary
   stated in plan.md and spec.md Edge Case (a); exceeding it defeats the
   entire purpose of bounding this spike.

**Files**: none (investigation only).

**Validation**: Either a named call site (exact file + line) with enough
confidence to fix it (proceed to T005 Branch A), or the timebox is exhausted
without isolation (proceed to T005 Branch B).

## Subtask T005: Land the fix (Branch A) or the fallback (Branch B)

**This subtask branches — do exactly one of the two branches below, not
both, based on T004's outcome.**

### Branch A — named call site found, and it is under `tests/`

**Steps**:
1. Fix the named call site: pin `--python`/`--all-extras` (or add
   `--no-sync`) to the offending `uv` invocation so it cannot retarget the
   shared `.venv` regardless of which worker or ordering triggers it.
2. Write a regression test/assertion proving this specific call site now
   carries the pinning flags — a deterministic, targeted assertion (e.g.
   parse the source file or the constructed subprocess command and assert
   the flags are present), analogous in spirit to WP03's YAML-parsing
   assertion but targeting this call site's Python source instead of a
   workflow YAML file.
3. Per this mission's ATDD discipline (plan.md's "ATDD-First" section,
   "FR-003's own regression check" — this assertion is *new* content, unlike
   WP02's pre-existing-RED pinning): write the assertion, confirm it RED
   against the not-yet-fixed call site, then land the fix and confirm GREEN,
   as two sequenced commits (test-first, then fix) where practical.
4. As corroborating (not sole) evidence, repeat T003's full `fast or unit` /
   `-n auto` reproduction once more and confirm the
   `multiprocessing.spawn`-reports-3.11 signature no longer occurs.

**Files**: the named call site's file (within `tests/upgrade/**`,
`tests/specify_cli/upgrade/**`, or `tests/specify_cli/skills/**` — already
covered by this WP's `owned_files`).

### Branch A-exception — named call site found, but it is under `src/`

Per spec Edge Case (a)'s explicit instruction: **treat this identically to a
timebox-exhausted finding.** Do NOT fix `src/` product code in this mission
— that would silently expand C-001's blast radius and risk absorbing
#3189's broader above-3.12 burn-down, which C-002 forbids. Proceed to
Branch B instead, and additionally file the `src/` call site itself as a
separate follow-up issue with the evidence gathered (in addition to Branch
B's own follow-up issue about the mitigation).

### Branch B — timebox exhausted, or the named call site is under `src/`

**Steps**:
1. Add a per-interpreter `UV_PROJECT_ENVIRONMENT` pin to
   `.github/workflows/ci-nightly.yml`'s `interpreter-matrix` job — as an
   `env:` key on the job or on the "Sync dev environment on this
   interpreter" step, scoped by `${{ matrix.python-version }}` (e.g.
   `UV_PROJECT_ENVIRONMENT: .venv-py${{ matrix.python-version }}` — record
   the exact key/value you choose). **This file is owned by WP03 in
   `wps.yaml`, not this WP** — this is a small, explicitly authorized
   out-of-map edit (the `tasks-finalize` prompt's own ownership rules permit
   "a small, well-justified out-of-map edit... acceptable when recorded with
   a one-line rationale"). Record that rationale in your commit message and
   WP completion report. If WP03 has already landed on the mission branch by
   the time you reach this step, rebase/merge cleanly on top of it rather
   than reverting its flags fix.
2. Add the FR-003(b) lightweight regression check as a **small standalone
   test in `tests/upgrade/test_migration_robustness.py`** — beside
   `test_concurrent_upgrade_handled`, the module that already hosts the
   hazard's own original reproduction. The check asserts the pinned
   per-interpreter `UV_PROJECT_ENVIRONMENT` venv's interpreter identity AND
   installed-extras set are unchanged before/after a `fast or unit` /
   `-n auto` run. This is inherently dynamic (a before/after comparison
   around a real run), which is why it belongs beside the test that first
   surfaced the hazard rather than as a static CI-YAML-only assertion.
   Write this assertion RED first (against the not-yet-pinned state), then
   GREEN after the pin lands, as two sequenced commits where practical —
   same ATDD discipline as Branch A.
3. File a follow-up GitHub issue carrying the reproduction evidence already
   gathered: the `multiprocessing.spawn`-child-reports-3.11 traceback
   signature, the suspect-subsystem list from T001/T002, what was ruled out
   in T003/T004, and (if applicable) the `src/` call site identified in the
   Branch A-exception path. Cross-link it from this mission's PR (record the
   issue number/URL for PR-prep, the same way WP01 does for its own issue).

**Files**: `.github/workflows/ci-nightly.yml` (small out-of-map edit, see
above), `tests/upgrade/test_migration_robustness.py` (new regression test —
already covered by this WP's `tests/upgrade/**` ownership).

## Subtask T006: Record evidence regardless of branch

**Purpose**: Ensure the investigation's findings are captured for WP05/WP06
and for the mission's tracer files, regardless of which branch was taken.

**Steps**:
1. Append a dated entry to
   `kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md`
   (via `spec-kitty agent tracer-append` if available, or a direct edit
   respecting the file's append-only convention) recording: which branch was
   taken, the elapsed time/attempt count against the timebox, the
   grep/collection candidate list, what was ruled out, and (Branch A) the
   named call site or (Branch B) the fallback pin's exact key/value and the
   follow-up issue number.
2. This evidence is what WP05/WP06 and PR-prep draw on — do not leave it
   only in your own working notes.

**Files**:
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/tracer-tooling-friction.md`
(append only — this path is under `kitty-specs/`, a planning surface; note
that this WP is `execution_mode: code_change` per its `tests/` ownership, so
per the "staged ownership rule," this specific append is a small,
well-justified out-of-map edit to a planning file, not a second competing
ownership claim — the mission's tracer-append convention already treats
tracer files as append targets for any WP, not a single WP's exclusive
`owned_files`).

## Definition of Done

- [ ] T001: `uv` call-site grep enumeration recorded
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: candidates cross-referenced against `fast or unit` collection
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: first `-n auto` reproduction attempt run with an explicit
      bounded foreground timeout, outcome recorded
      (`spec-kitty agent tasks mark-status T003 --status done`).
- [ ] T004: `-k`-scoped narrowing performed within the timebox (3h OR 5
      total `-n auto` attempts, whichever first)
      (`spec-kitty agent tasks mark-status T004 --status done`).
- [ ] T005: Branch A (named fix + regression test) OR Branch B (fallback
      pin + regression test + follow-up issue) landed, per T004's outcome
      (`spec-kitty agent tasks mark-status T005 --status done`).
- [ ] T006: evidence recorded in the mission's tracer files
      (`spec-kitty agent tasks mark-status T006 --status done`).
- [ ] Whichever branch: a regression test exists proving the venv's
      interpreter identity does not move (Branch A: targeted call-site
      assertion; Branch B: pinned-venv identity/extras before/after check).

## Risks

- **This is the mission's largest schedule risk** — plan.md says so
  explicitly. The timebox exists precisely so this risk cannot silently
  expand to consume the rest of the mission's schedule. Respect it.
- **Do not stack multiple simultaneous `-n auto` runs against other
  concurrently-running mission lanes.** Per plan.md's write-scopes section,
  issue #3283 (a related shared-venv-lock hazard) is closed/resolved, but
  the underlying shared-fixture contention pattern is mitigated, not proven
  structurally impossible to re-trigger under heavy concurrent load — avoid
  running this WP's reproduction attempts at the same wall-clock time as
  WP05's own `-n auto` re-measurement.
- **Do not fix `src/` product code in this mission** even if a `src/` call
  site is the clear culprit — see the Branch A-exception above.

## Reviewer Guidance

- Confirm the timebox was respected — ask for the elapsed time and attempt
  count, and check T006's recorded evidence for consistency with the T005
  branch actually taken.
- If Branch A: confirm the regression test is genuinely new content with its
  own RED-before/GREEN-after commits (unlike WP02, this is NOT a
  pre-existing-RED pinning case).
- If Branch B: confirm the `UV_PROJECT_ENVIRONMENT` out-of-map edit to
  `.github/workflows/ci-nightly.yml` is small, rationale-recorded, and
  doesn't silently conflict with WP03's flags fix in the same file/job block
  — check both diffs together if both WPs touched this file.
- Confirm the follow-up issue (Branch B) or `src/`-call-site issue (Branch
  A-exception) exists and carries real reproduction evidence, not a stub.
- Confirm no fix landed under `src/` regardless of what T004 found.

Implementation command: `spec-kitty agent action implement WP04 --agent claude`
