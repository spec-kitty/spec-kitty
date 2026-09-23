# Mission Specification: interpreter-matrix 3.13 leg: env resolution and real 3.13 divergence

**Mission Branch**: `issue-4866-interpreter-matrix-3-13`
**Created**: 2026-09-22
**Status**: Draft
**Input**: GitHub issue [#4866](https://github.com/spec-kitty/spec-kitty/issues/4866) — "ci(nightly): interpreter-matrix 3.13 leg perma-red on stale 3.11 venv missing test extra — nightly gate untrustworthy"

## Summary

The nightly `interpreter-matrix` job in `.github/workflows/ci-nightly.yml`
(`interpreter-matrix`, lines ~174–241) has reported red for **7 consecutive
nights** (2026-09-16 through 2026-09-22; last green 2026-09-15), with 13
collection errors (`ModuleNotFoundError` for `pytestarch`, `respx`,
`pytest_benchmark`) while every ordinary module shard stays green. The red is
**not caused by a real 3.13 defect** — it is caused by the workflow's own `uv
run` step silently discarding the preceding `uv sync --python 3.13
--all-extras` and re-syncing against `.python-version` (pinned to `3.11.15`)
with default extras only, on every single invocation. The job has therefore
never actually exercised FR-021 interpreter-divergence coverage: it reports a
confident, specific-looking red about the wrong interpreter and the wrong
dependency set, every night, which desensitizes the nightly gate as a whole —
a genuinely new regression on 3.13 would be indistinguishable from this noise.

This mission fixes the environment-pinning defect, and — per an explicit
operator scope decision (see Clarifications) — also fixes the confirmed real
3.13 stdlib divergence uncovered once the leg is made to actually run on
3.13, and root-causes a second, independently discovered environment hazard
(a shared `.venv` that can be silently rebuilt mid-run under parallel
workers). It does **not** claim the nightly leg will report green when this
mission closes; see Success Criteria for why, and Edge Cases (c) for the
disposition of any residual red.

## User Scenarios & Testing *(mandatory)*

This is a CI/test-infrastructure bug fix mission, not a user-facing product
feature. There is no end-user story in the ordinary sense; the "user" is the
**maintainer/operator who relies on the nightly interpreter-matrix leg as a
trustworthy signal** that spec-kitty's own test suite behaves the same way
on Python 3.13 as it does on the officially supported 3.11/3.12 floor. The
"journeys" below are the maintainer's, framed the same way a product user
story would be so priority and independent testability still apply.

### User Story 1 - The nightly leg actually tests what it claims to test (Priority: P1)

As the Spec Kitty maintainer relying on `ci-nightly.yml`, I want the
`interpreter-matrix` job's `pytest` invocation to actually run on the
Python 3.13 interpreter with the `test` extra installed, so that a red night
means "something is wrong with spec-kitty on 3.13" rather than "the workflow
silently synced back to 3.11 with no test dependencies."

**Why this priority**: This is the entire thesis of #4866 and the issue's
stated P1 severity. Every other requirement in this mission is downstream of
this one being true — none of the divergence findings below could have been
observed without it.

**Independent Test**: Dispatch `ci-nightly.yml` manually
(`gh workflow run ci-nightly.yml --ref issue-4866-interpreter-matrix-3-13`)
and inspect the `interpreter-matrix` job's log for the `pytest` invocation
line: it must show the 3.13 interpreter's site-packages path and zero
`ModuleNotFoundError` for `pytestarch`/`respx`/`pytest_benchmark`. This is
testable independently of User Stories 2 and 3 — the flags fix stands alone
as a complete, mergeable change even if no further divergence work happened.

**Acceptance Scenarios**:

1. **Given** the `interpreter-matrix` job's sync step has already run `uv
   sync --frozen --all-extras --python 3.13`, **When** the subsequent `uv
   run` step executes `pytest`, **Then** the interpreter/extras selected by
   that sync are the ones actually used to run `pytest` — not silently
   re-resolved to `.python-version`'s 3.11.15 with default (non-`test`)
   extras.
2. **Given** a local reproduction of the exact `uv sync` + `uv run` step
   pair as written in `ci-nightly.yml`, **When** run with `uv 0.11.28` (the
   version `setup-uv@v10.0.1` currently installs), **Then** the reproduction
   shows the run step using Python 3.13 with `iniconfig`-class test-extra
   packages importable — matching the local repro captured in the readiness
   report, not the "3.11 interpreter, `ModuleNotFoundError`" signature.

---

### User Story 2 - The leg is honest about genuine 3.13 divergence it already found (Priority: P1)

As the maintainer, I want the 4 confirmed `dir_fd`-related kernel test
failures — caused by Python 3.13's `shutil.rmtree` legitimately changing its
implementation to use `os.open(..., dir_fd=...)` — fixed at the test-double
level, so that the leg's first genuine run on 3.13 does not immediately
report a false negative caused by a stale test double rather than by
spec-kitty's own product behavior.

**Why this priority**: operator decision Q1=B (see Clarifications). This is
a Standing-Order-4 "stale test double" case, not a product defect: 3.13
changed, the test double didn't. Landing the flags fix alone (User Story 1)
without this would hand the operator a newly-red nightly leg the very next
night, with the specific defect already diagnosed and cheap to fix.

**Independent Test**: With the flags fix from User Story 1 already in place
(or a temporary manual invocation on 3.13 without it, for isolated
verification before the flags fix lands), run
`.venv/bin/python -m pytest tests/kernel/test_lock_parity.py
tests/kernel/test_no_follow.py tests/specify_cli/core/test_no_follow.py -v`
under Python 3.13: 3 tests in `test_lock_parity.py` currently ERROR, and the
non-parametrized `test_read_rejects_symlink_planted_before_open` test in
each of the two separate `test_no_follow.py` copies currently ERRORs (via
its shared teardown), and this work package shows they pass after the fix.

**Acceptance Scenarios**:

1. **Given** a Python 3.13 interpreter, **When**
   `tests/kernel/test_lock_parity.py::test_naive_second_open_of_a_held_lock_raises_under_simulation`
   (and its two sibling tests in the same file) run to teardown, **Then**
   `_WindowsMandatoryLockSimulator.wrap_open`'s `_open` shim accepts and
   passes through 3.13's `dir_fd` keyword argument instead of raising
   `TypeError: ... got an unexpected keyword argument 'dir_fd'`.
2. **Given** a Python 3.13 interpreter, **When**
   `tests/kernel/test_no_follow.py::test_read_rejects_symlink_planted_before_open`
   and `tests/specify_cli/core/test_no_follow.py::test_read_rejects_symlink_planted_before_open`
   run to teardown, **Then** the `plant_symlink` monkeypatch shim accepts and
   passes through the `dir_fd` keyword argument the same way, and pytest's own
   `tmp_path` teardown (which invokes `shutil.rmtree` while the monkeypatch is
   still active) completes without error.
3. **Given** the same fix, **When** run on Python 3.11 and 3.12 (the CI floor
   `module-tests.yml` actually exercises), **Then** the shims' behavior is
   unchanged for those interpreters — the fix widens what the shim accepts,
   it does not narrow or alter existing-interpreter behavior.

---

### User Story 3 - A mid-run shared-venv corruption hazard is root-caused, not just noted (Priority: P1)

As the maintainer, I want the mission to identify (or make a bounded,
documented attempt to identify) which test or fixture causes the shared
`.venv` to be silently rebuilt from Python 3.13 back to 3.11 mid-suite under
`-n auto` parallel execution, so that the 3.13 divergence figure the mission
reports is measured against a *stable* environment rather than one that
changes interpreter underneath a running worker — and so CI, which also uses
one shared default `.venv`, is not carrying the same latent hazard
unaddressed.

**Why this priority**: operator decision Q2=B (see Clarifications) —
explicitly in scope, not filed as a separate issue. This is the largest
unknown and the largest schedule risk in the mission (see Edge Case (a));
its priority reflects operator instruction, not confidence that it is cheap.

**Independent Test**: Reproduce the corruption independently of the flags
fix and the kernel fix — run the exact `fast or unit` selector with
`-n auto` against a hand-built, `UV_PROJECT_ENVIRONMENT`-isolated 3.13
`.venv` (mirroring the readiness report's own reproduction), and watch for
a `multiprocessing`-spawn child reporting Python 3.11 while its parent
worker reports 3.13 — the exact signature already captured in the readiness
report from `tests/upgrade/test_migration_robustness.py::test_concurrent_upgrade_handled`.
Success is either (a) a named culprit call site with a fix and a regression
test proving the venv no longer moves mid-run, or (b) a documented, timeboxed
"could not isolate within budget" outcome with the interim mitigation applied
(see Edge Case (a)).

**Acceptance Scenarios**:

1. **Given** the `fast or unit` selector run with `-n auto` against a 3.13
   `.venv`, **When** any nested nightly-suite test or fixture shells out to
   `uv` without pinning `--python`/`--all-extras` (or `--no-sync`), **Then**
   that call site is identified and fixed (pinned or `--no-sync`'d) so it
   cannot retarget the shared `.venv` regardless of which worker or ordering
   triggers it.
2. **Given** the fix from (1), **When** the same `fast or unit` / `-n auto`
   run is repeated end-to-end, **Then** no worker's subprocess output shows
   an interpreter version mismatch against the venv the run started with
   (spot-checked via the same `multiprocessing.spawn` traceback signature
   that first surfaced the hazard, plus a new regression test asserting the
   `.venv`'s interpreter identity is unchanged before/after the suite run).
3. **Given** the timebox in Edge Case (a) is exhausted without isolating a
   culprit, **When** the mission closes, **Then** the fallback mitigation
   and its rationale are recorded in the spec/plan, a lightweight regression
   check asserts the pinned per-interpreter `UV_PROJECT_ENVIRONMENT` venv's
   interpreter identity and installed-extras set is unchanged before/after a
   `fast or unit` / `-n auto` run (an analogous but not identical assertion
   to Acceptance Scenario 2's named-culprit-branch check — scoped to the
   pinned fallback venv rather than a fixed call site, and broader, since it
   also covers the installed-extras set, which Scenario 2 does not require),
   and a follow-up issue is filed
   with the reproduction steps and evidence already gathered — the mission
   does not silently drop the finding.

---

### User Story 4 - Re-measurement replaces the distrusted baseline before any further scoping decision (Priority: P2)

As the maintainer, I want the mission to re-run the `fast or unit` selector
on 3.13 **after** the venv-corruption fix (or its documented fallback) lands,
rather than continuing to plan or report against the original "429
failing/erroring only on 3.13" figure, so that any residual-red disposition
decision (Edge Case (c)) is made against real data, not data known to be
contaminated by a second, independent defect.

**Why this priority**: directly required by the tension between facts 3 and
5 in the issue brief — the 429 figure is explicitly distrusted and will
shrink once User Story 3's fix lands. This is sequenced after User Stories 1
and 3 for exactly that reason.

**Independent Test**: Compare the re-measured 3.13 `fast or unit` failure
count and failure-ID set against both the original distrusted 429-only-on-3.13
figure and the 3.11 baseline (21 failed). The re-measurement is itself the
independent, falsifiable artifact — its counts and IDs are recorded in the
mission's PR body / tests-run evidence, not asserted from memory.

**Acceptance Scenarios**:

1. **Given** the venv-corruption fix (or documented fallback) from User
   Story 3 has landed, **When** the `fast or unit` selector is re-run on a
   freshly synced 3.13 `.venv` with `-n auto`, **Then** the resulting
   failure/error set is recorded (count, and the specific test IDs new
   relative to the 3.11 baseline) and superscedes the 429 figure for all
   subsequent scoping decisions in this mission.
2. **Given** the re-measurement, **When** its failure set is compared to the
   4 confirmed `dir_fd` kernel failures already fixed by User Story 2,
   **Then** the spec/PR states plainly whether the re-measured residual
   (beyond those 4) is zero, small-and-fixable-in-scope, or large-and-out-of-scope
   — driving the Edge Case (c) disposition with real numbers instead of the
   429 placeholder.

---

### Edge Cases

The spec author resolves each of the following explicitly rather than
leaving it to plan/tasks time, per the readiness report's identified
tensions.

**(a) Q2-B (root-causing the venv corruption) is an unbounded investigation — what is the timebox, and what happens if it fails?**

The culprit test/fixture causing the mid-run 3.13→3.11 `.venv` rebuild under
`-n auto` is **not yet identified** as of spec authoring. This is the single
largest schedule risk in the mission (explicitly called out here, not
buried in a WP). Resolution:

- **Approach**: treat it as a bounded investigation spike, not open-ended
  debugging. Search for `uv` subprocess invocations anywhere under `tests/`
  and `src/` that could run during a `fast or unit` collection (`grep -rn
  "uv sync\|uv run\|subprocess.*uv " tests/ src/`), cross-referenced against
  which test modules are collected under the `fast or unit` marker set and
  which exercise spec-kitty's own bootstrap/upgrade/skill-installer tooling
  (the readiness report's own suspicion: "plausibly something in the
  upgrade/skill-installer families that legitimately shells out to `uv`
  while testing spec-kitty's own bootstrap tooling"). Reproduce with `-n
  auto` first (parallel is required to trigger it — the readiness report's
  repro was itself accidental, under `-n auto`), narrowing via `-k` subsets
  by suspect subsystem rather than re-running the full ~35k-item selector
  repeatedly (SK-99 timeout discipline; see tracer-tooling-friction.md).
- **Timebox**: the investigation gets **one bounded work package**, sized
  and time-boxed at plan/tasks time (not open-ended across the mission).
  This spec does not fix a wall-clock number (that belongs to the plan),
  but states the shape: a fixed, small number of `-k`-scoped reproduction
  attempts against named suspect subsystems, not an unbounded full-suite
  bisection loop.
- **Fallback if the timebox is exhausted without isolating a culprit**: fall
  back toward the readiness report's original recommendation (Q2 option A)
  for the *unresolved remainder* only — apply an interim mitigation
  (documented, not silent) such as pinning the CI/local `.venv` used by the
  nightly leg to a per-interpreter `UV_PROJECT_ENVIRONMENT` path so a
  same-run nested `uv` call cannot retarget the leg's own working venv even
  if the culprit is never found, **and** file a follow-up issue carrying the
  reproduction evidence already gathered (the `multiprocessing.spawn`
  traceback signature, the suspect-subsystem list, what was ruled out). The
  mission does not claim root-cause success it did not achieve, and does not
  silently drop the finding either (User Story 3, Acceptance Scenario 3).
- **If the named call site is under `src/` (product code) rather than
  `tests/`**: treat it the same as a timebox-exhausted finding — do not fix
  product code in this mission (that would silently absorb a product-code
  change into a mission C-001 scopes as workflow-file-plus-test-doubles, and
  would risk expanding into #3189's broader above-3.12 burn-down, which
  C-002 forbids). Instead, apply the UV_PROJECT_ENVIRONMENT interim
  mitigation at the test-harness level and file the product-code call site
  as a follow-up issue with the evidence gathered, cross-linked from this
  mission's PR.

**(b) Fixing the venv corruption changes the 3.13 failure count — the mission re-measures rather than planning against 429.**

Resolved via User Story 4 above: the 429-only-on-3.13 figure is explicitly
**not** a planning baseline for scoping decisions; it is the *raw, distrusted*
starting observation. The mission re-measures after User Story 3's fix (or
documented fallback) lands, and that re-measurement — not 429 — is what
Edge Case (c)'s disposition decision is made against.

**On the charter's full-suite-run exemption**: the charter's Testing
Requirements (`.kittify/charter/charter.md`, "Testing Requirements" section)
reserve `pytest tests/` full-suite runs for post-merge mission-level
validation, explicit cross-cutting changes, and release-candidate
verification — not ordinary scoped WP validation. A re-measurement of the
`fast or unit` selector on 3.13 after the venv-corruption fix is judged to
be a legitimate instance of the "explicit cross-cutting change" exemption:
the venv-corruption fix, by construction, changes how the *shared test
environment itself* behaves during a broad parallel run, which is exactly
the class of shared-infrastructure change the exemption contemplates — a
narrow, single-module-scoped test cannot validate that the environment no
longer moves under a wide, parallel run. This exemption is stated here
explicitly, per the readiness/operator brief's instruction not to assume
it's obviously fine without saying so. It licenses the `fast or unit`
selector specifically (the same selector `ci-nightly.yml`'s own job uses,
~35k items, not `pytest tests/` unfiltered), not an unscoped full-repo
run — the interpreter-matrix job itself only ever runs `-m "fast or unit"`.

**(c) Scope is bounded to the 4 confirmed `dir_fd` failures — what happens if the leg is still red after all three fixes land, from OTHER genuine 3.13 divergence not scoped into this mission?**

Q1=B scopes the kernel-fix work item to exactly the 4 confirmed `dir_fd`
failures identified by direct reproduction (User Story 2). It does **not**
commit this mission to fixing every 3.13 divergence the re-measurement in
User Story 4 might reveal. Disposition, chosen and justified here rather
than left open:

- **Chosen disposition: file the residue against #3189, and accept the leg
  reporting an honest red in the interim if residue exists.** #3189
  ("no pytest job runs above Python 3.12 … interpreter-divergence defects
  invisible to the gate", open, P2) is explicitly the deferred, broader
  above-3.12 divergence burn-down; the `interpreter-matrix` job's own inline
  comment already says so ("Deliberately scoped to the nightly lane, NOT the
  full above-3.12 suite burn-down (#3189 is a deferred follow-up, not
  claimed here)"). Any residual divergence beyond the 4 confirmed `dir_fd`
  failures is, by the workflow's own existing design intent, #3189's scope,
  not #4866's. This mission files the re-measured residual failure IDs
  (User Story 4) as a comment/update on #3189 (or a new issue cross-linked
  to it, if #3189's own scope doesn't cleanly absorb the specific findings)
  rather than expanding this mission's blast radius to chase them.
- **Why not "declare the leg green regardless"**: that would be exactly the
  green-washing Standing Order 9 forbids — claiming trustworthiness the
  evidence does not support. Why not "keep fixing until green, however
  long that takes": that silently absorbs #3189's entire deferred scope
  into a P1 CI-hygiene mission, which is scope creep the readiness report
  and the operator's own Q1 framing explicitly reject.
- **This directly interacts with the charter's red-main standing order
  (§9)**: an honestly red `interpreter-matrix` leg — red because real,
  currently out-of-scope 3.13 divergence exists and is tracked (#3189) — is
  **acceptable, correct doctrine** under this charter. A green leg achieved
  by silently narrowing what it tests, or by declaring residual divergence
  "not a big deal" without evidence, would not be. Success Criteria below
  are written to reflect this: they do not claim the leg turns green.

**(d) Verification has no CI safety net — the spec must not claim otherwise.**

`.github/workflows/ci-nightly.yml` triggers on `schedule` and
`workflow_dispatch` only (confirmed by direct inspection of the workflow's
`on:` block) — **never** `pull_request` or `push`. A PR that edits this
workflow file receives **zero** automatic CI signal from the very workflow
it changes; no status check on the PR will exercise the `interpreter-matrix`
job. Verification is therefore necessarily:

1. **Local reproduction** of the exact `uv sync` + `uv run` step pair,
   mirroring the workflow's own commands byte-for-byte, on a real Python
   3.13 interpreter (as already done for the readiness probe).
2. **A manual dispatch** of the real workflow against the mission branch —
   `gh workflow run ci-nightly.yml --ref issue-4866-interpreter-matrix-3-13`
   — inspected via `gh run watch` / `gh run view --log`, which the
   maintainer landing workflow permits.

No requirement or acceptance scenario in this spec claims or implies that a
normal PR check will validate this change; every acceptance scenario above
names the exact local command or manual dispatch that constitutes its
verification instead.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Pin interpreter/extras on the `uv run` step, not only the `uv sync` step | As the maintainer, I want the `interpreter-matrix` job's `pytest` invocation to run under 3.13 with the `test` extra installed, so that a red result reflects a real 3.13 defect. | High | Open |
| FR-002 | Fix the 4 confirmed `dir_fd` kernel test-double failures | As the maintainer, I want `_WindowsMandatoryLockSimulator.wrap_open` and the `plant_symlink` teardown-adjacent shims to accept 3.13's `dir_fd` keyword, so a stale test double doesn't masquerade as a product regression. | High | Open |
| FR-003 | Root-cause (or timebox-and-fallback) the shared-`.venv` mid-run corruption under `-n auto` | As the maintainer, I want to know which call site rebuilds the shared venv mid-suite, or have a documented, evidenced fallback if it can't be isolated in the timebox, so the 3.13 failure count is measured against a stable environment and CI's own shared `.venv` isn't carrying the same latent hazard. | High | Open |
| FR-004 | Re-measure the 3.13 `fast or unit` selector after the venv-corruption fix lands, before finalizing any further divergence scope | As the maintainer, I want the mission's scoping decisions made against fresh, uncontaminated measurement data, not the original distrusted 429 figure. | High | Open |
| FR-005 | Discharge the Pre-existing Failure Reporting Rule obligation for currently-observed reds | As the maintainer, I want the charter's pre-existing-failure reporting obligation satisfied for the 21 pre-existing 3.11 failures and any residual 3.13 reds this mission does not fix, so later agents don't have to re-derive whether those failures were ever formally reported. | Medium | Open |
| FR-006 | Explicit disposition of any leg-still-red residue after all three in-scope fixes land | As the maintainer, I want a stated, justified answer for what happens if the leg is still red from genuine, out-of-scope 3.13 divergence after this mission closes, so the mission doesn't silently imply an unconditional green claim it can't support. | High | Open |

**Acceptance criteria per FR** (falsifiable, tied to a concrete check):

- **FR-001**: `.github/workflows/ci-nightly.yml`'s `interpreter-matrix` job's
  `uv run` step (currently `uv run --frozen pytest -m "fast or unit" -q
  --junitxml=...`) carries `--python "${{ matrix.python-version }}"
  --all-extras` (or `--no-sync`, with the tradeoffs documented in the
  readiness report — a silent "using incompatible environment" warning
  every invocation vs. trusting a possibly-stale prior sync — favoring the
  explicit-flags form since it fails loudly rather than silently trusting
  staleness, matching the mission's anti-silent-success stance in the
  Reflexivity section below). Checked by: (1) a diff of the workflow file
  showing the flag addition; (2) a local repro of the exact command pair
  showing 3.13 site-packages and no `ModuleNotFoundError`; (3) a manual
  `workflow_dispatch` run of the real job showing the same.
- **FR-002**: `tests/kernel/test_lock_parity.py`'s
  `_WindowsMandatoryLockSimulator.wrap_open`, and both
  `tests/kernel/test_no_follow.py`'s and
  `tests/specify_cli/core/test_no_follow.py`'s
  `test_read_rejects_symlink_planted_before_open`'s `plant_symlink` shim,
  accept `**kwargs` (or an explicit `dir_fd: int | None = None` parameter)
  and pass it through to the wrapped/real `os.open` call. Checked by:
  `.venv/bin/python -m pytest tests/kernel/test_lock_parity.py
  tests/kernel/test_no_follow.py tests/specify_cli/core/test_no_follow.py -v`
  on a 3.13 interpreter showing 0 errors (currently 5 errors: 3 in
  `test_lock_parity.py`, and 1 each in the two separate, non-parametrized
  `test_no_follow.py` copies — `tests/kernel/test_no_follow.py` and
  `tests/specify_cli/core/test_no_follow.py`), and the same command on 3.11
  showing no change in outcome.
- **FR-003**: either (a) a named, fixed call site with a regression test
  proving the shared `.venv`'s interpreter identity does not change across
  a `fast or unit` / `-n auto` run, or (b) the documented fallback mitigation
  from Edge Case (a) applied, plus a follow-up issue filed with the
  gathered evidence — and, in both cases, a lightweight regression check:
  for (a), a deterministic, targeted assertion on the identified call site
  itself (e.g. a unit/integration test asserting that specific subprocess
  invocation now passes `--python`/`--all-extras` or `--no-sync`) is the
  primary revert-sensitive check, with a full `fast or unit` / `-n auto`
  reproduction kept only as corroborating, not sole, evidence; for (b), a
  test or CI step asserting the pinned per-interpreter
  `UV_PROJECT_ENVIRONMENT` venv's interpreter identity and installed-extras
  set is unchanged before/after a `fast or unit` / `-n auto` run — an
  analogous but not identical check to (a)'s targeted call-site assertion
  (broader, since it also covers installed extras, and a dynamic
  before/after comparison rather than a static per-call-site assertion),
  applied against the pinned venv rather than a fixed call site. This (b)
  check lands as a lightweight step added alongside the fallback's own
  `ci-nightly.yml` / `UV_PROJECT_ENVIRONMENT`-pinning change, or, if that
  is not a natural fit, as a small standalone test added to
  `tests/upgrade/test_migration_robustness.py` — the module already hosting
  the hazard's own original reproduction, `test_concurrent_upgrade_handled`
  — the WP records the exact file/test name it used. Checked by:
  for (a), the targeted call-site assertion
  passing plus a repeat of the exact reproduction that first surfaced the
  hazard (the `multiprocessing.spawn`-child-reports-3.11 signature from
  `tests/upgrade/test_migration_robustness.py::test_concurrent_upgrade_handled`)
  no longer occurring; for (b), the pinned-venv regression check passing
  plus confirmation the fallback mitigation is in place and the follow-up
  issue exists.
- **FR-004**: a recorded re-measurement (command, exact pass/fail/error
  counts, and the failure-ID diff against the 3.11 baseline) exists in the
  mission's PR body / tests-run evidence, explicitly superseding the 429
  figure. Checked by: presence of that recorded evidence in the PR, and
  that FR-006's disposition cites the re-measured numbers, not 429.
- **FR-005**: either (a) a fresh GitHub issue is opened reporting the 21
  pre-existing 3.11 `fast or unit` failures (command run, failure summary,
  and why they're believed pre-existing — i.e., also fail on `main` at the
  merge-base, per the charter's stale-venv/baseline-red gotcha
  classification) if no such currently-open issue already covers them, or
  (b) the spec states explicitly why #3284 (closed) plus #4866 (this
  mission's own issue) together already discharge the obligation, with the
  reasoning made explicit rather than asserted. This mission adopts **(a)**:
  #3284 is **closed**, so it cannot be the open report the charter's rule
  requires ("before treating those failures as accepted baseline context");
  #4866 itself reports the *environment* defect, not the 21 pre-existing
  3.11 `fast or unit` failures as their own tracked item. A fresh issue
  reporting the current 21 pre-existing 3.11 failures (with the exact
  command and failure list from the readiness report's baseline run) is
  opened as part of this mission's implementation, and any residual 3.13
  reds surviving after FR-002/FR-003/FR-004 are folded into that same issue
  or cross-linked to #3189 per FR-006, not left unreported. Checked by: the
  issue exists, is linked from the mission's PR, and names the command run
  plus the failure list.
- **FR-006**: the mission's spec/plan/PR states, in writing, one of three
  dispositions for any residual red after FR-001/002/003 land — and this
  spec commits to the answer given in Edge Case (c): file the residue
  against #3189 (already the charter-sanctioned home for above-3.12
  divergence the interpreter-matrix job doesn't claim), and let the leg
  report an honest red if residue exists, rather than claiming or implying
  an unconditional green. Checked by: the disposition statement is present
  in this spec (Edge Case (c)) and echoed in the mission's closing PR body;
  the PR body does not claim "nightly turns green" unless the FR-004
  re-measurement, after FR-002/FR-003, in fact shows zero residual beyond
  what's already fixed.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded verification runtime | Every `fast or unit` / `-n auto` verification run in this mission's plan/tasks/implementation carries an explicit, bounded timeout in the command invocation itself (not relying on the shell's default), sized comfortably above the ~411s (3.13) / ~485s (3.11) baseline observed in the readiness report, and is run in the foreground rather than backgrounded, per SK-99 (Claude subagents auto-background at 120s and strand on their own long-running commands). | Reliability | High | Open |
| NFR-002 | No new silent-success path | The `uv run` step fix and any venv-corruption fix must fail loudly (non-zero exit, or a change visible in job output) if the interpreter/extras pinning is ever wrong again — not silently re-sync to an unexpected interpreter the way the current defect does. | Reliability | High | Open |
| NFR-003 | Cross-interpreter neutrality of the kernel-shim fix | The `dir_fd`-accepting shim fix (FR-002) must not alter observed behavior on Python 3.11/3.12 (the CI floor), only widen what it accepts for 3.13+. | Compatibility | Medium | Open |

**Checked by (NFR-002)**: unlike NFR-001/NFR-003 (which are process constraints
checked by inspection of the mission's own commands and diffs), NFR-002 gets
its own falsifiable check, since its "fail loudly" guarantee spans both the
FR-001 flags fix and whichever FR-003 mitigation is chosen: a negative-path
check that temporarily removes/breaks a flag (or the `UV_PROJECT_ENVIRONMENT`
pin) and confirms the job/test run now fails loudly — non-zero exit or an
explicit, visible warning — rather than silently succeeding against the
wrong interpreter/extras.

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Blast radius limited to workflow file + kernel test doubles/fixtures | This mission touches `.github/workflows/ci-nightly.yml` (the `interpreter-matrix` job) and the kernel test-double/fixture files named in FR-002 (`tests/kernel/test_lock_parity.py`, `tests/kernel/test_no_follow.py`, `tests/specify_cli/core/test_no_follow.py`), plus whatever call site FR-003's investigation names (scope unknown until found; if found, expected to be a test/fixture shelling out to `uv`, not product code). If FR-003's (b) fallback branch is taken instead, its own regression check (FR-003 AC) is likewise in-radius: either a step added alongside the `ci-nightly.yml` fallback change itself, or a small standalone test added to `tests/upgrade/test_migration_robustness.py` (the module already hosting the hazard's own original reproduction, `test_concurrent_upgrade_handled`). No other source, product, or migration code is expected to change. | Technical | High | Open |
| C-002 | Does not expand into #3189's scope | This mission does not add interpreter versions beyond 3.13 to the matrix, does not widen the suite selector beyond `fast or unit`, and does not attempt to fix 3.13 divergence beyond the 4 confirmed `dir_fd` failures — any further divergence found is filed against #3189 per Edge Case (c), not fixed here. | Technical | High | Open |
| C-003 | No CI safety net for the workflow-file diff | `ci-nightly.yml` triggers on `schedule`/`workflow_dispatch` only; verification is local reproduction plus manual `workflow_dispatch`, never an automatic PR check on the changed workflow itself (Edge Case (d)). | Technical | High | Open |
| C-004 | ATDD-first applies, including to the workflow-YAML fix | Per charter C-011, the flags fix (FR-001) needs a failing-first test committed before the implementation commit: a test that parses `.github/workflows/ci-nightly.yml`'s YAML and asserts the `interpreter-matrix` job's `uv run` step (the one invoking `pytest -m "fast or unit"`) carries `--python` and `--all-extras` (or `--no-sync`) — the test must assert the flags on that step's own `run:` string specifically, not the job's or file's full YAML text: the preceding `uv sync` step (line ~205) already carries `--python`/`--all-extras`, so a whole-text match would be vacuously green even before the fix lands. This test must be shown RED against the current file (which lacks those flags on the `uv run` step) and GREEN after the fix. The kernel `dir_fd` fix (FR-002) similarly needs a failing-first test: the existing `test_naive_second_open_of_a_held_lock_raises_under_simulation` and the two `test_read_rejects_symlink_planted_before_open` copies (non-parametrized, one each in `tests/kernel/test_no_follow.py` and `tests/specify_cli/core/test_no_follow.py`) already fail RED on 3.13 today (that failure *is* the pinning test, no new test file is required — the WP records their current-3.13 RED, then their post-fix GREEN, on the WP's `planning_base_branch` vs. final commit, per C-011). C-011's "committed as a separate commit ... BEFORE any implementation commit" clause is read narrowly here as inapplicable to a *new, separate* test-file commit: FR-002's implementation commit DOES edit test-support files — per C-001, the same `tests/kernel/test_lock_parity.py` and both `test_no_follow.py` copies, widening the `_WindowsMandatoryLockSimulator.wrap_open` `_open` shim and the `plant_symlink` shim to accept `dir_fd` — but it does not add or modify a *test assertion*: the pre-existing test functions and their expected behavior are unchanged, only the inline shim helper's signature widens to accept a kwarg the OS now passes. The ATDD pinning is therefore the pre-existing tests' own current RED state on 3.13, not a new test file, so there is no new, separate test-file commit to sequence before the implementation commit — only C-011's red-on-base/green-on-final verification obligation (checked at WP review) applies to this WP. | Process | High | Open |

### Key Entities

Not applicable in the conventional data-model sense — this mission modifies a
CI workflow definition (YAML) and Python test fixtures/doubles, not a
persistent domain entity. The closest analogue:

- **`interpreter-matrix` job** (`.github/workflows/ci-nightly.yml`): the CI
  job definition whose `uv sync` / `uv run` step pair is the primary fix
  target.
- **`_WindowsMandatoryLockSimulator`** (`tests/kernel/test_lock_parity.py`):
  the test double whose `wrap_open` shim needs to accept `dir_fd`.
- **`plant_symlink` shim** (`tests/kernel/test_no_follow.py`,
  `tests/specify_cli/core/test_no_follow.py`): the monkeypatch helper with
  the same `dir_fd` gap.

## Reflexivity

This mission runs inside spec-kitty's own tooling, driven in part by the
same nightly CI infrastructure it modifies. No mid-flight mission depends on
`ci-nightly.yml`'s current (broken) behavior in a way this change could
disrupt: the fix only makes the `interpreter-matrix` leg's report *accurate*
(right interpreter, right extras), it does not change what any other job or
consumer of the nightly workflow observes about jobs other than
`interpreter-matrix` itself, and no job fails, blocks, or branches on
`interpreter-matrix`'s result — the only reader is `ci-nightly.yml`'s own
`nightly-summary` job, which echoes the result for operator visibility under
`if: always()` and does not gate on it (it is a human/operator-facing
signal, not a merge gate — `ci-nightly.yml` is not in any PR's
required-checks path). The irony is explicit and worth naming: this
very issue is itself a silent-success failure — `uv run` silently rebuilt
the environment to the wrong interpreter/extras, and the nightly job
reported a confident, specific-looking red about entirely the wrong thing.
NFR-002 exists specifically so this mission's own fix does not introduce a
new instance of the same failure mode (e.g., a workflow that silently skips
extras/python pinning under some untested condition, or a venv-corruption
fix that silently masks rather than surfaces a future re-occurrence).

## Canonical Sources

This mission does not touch canonical templates, agent profiles, or mission
type definitions under `packs/built-in/` — verified against this checkout
(`packs/built-in/agent_profiles/`, `packs/built-in/missions/mission-steps/`
exist and are unrelated to this mission's blast radius). It is a CI
workflow + kernel test-fixture fix; no canonical-sources concern applies.

## Clarifications

Recorded verbatim (paraphrase kept minimal) so a later reviewer or
`sk-review` audit can see exactly what was decided and why, per the
operator's explicit instruction that these be persisted into the spec
itself, not just referenced.

**Q1 (Scope of this mission once the leg genuinely runs on 3.13) — decided: option B.**
> "Fix the flags AND the 4 confirmed kernel `dir_fd` failures in the same
> mission."

The readiness probe's own recommendation was the narrower option A (flags
only; file the kernel `dir_fd` failures and venv-corruption finding
separately). The operator explicitly chose B over that recommendation,
accepting the tradeoff the probe named for B: it ships a fix outside the
issue's literal stated scope ("stale 3.11 venv missing test extra"), in
exchange for not handing the operator a newly-red nightly leg with an
already-diagnosed, cheap fix left undone.

**Q2 (Handling of the shared-venv-corruption finding) — decided: option B.**
> "Treat it as in-scope for #4866."

The readiness probe recommended the narrower option A (file a new issue,
scoped to "some test shells out to `uv` without pinning
interpreter/extras... the mission finds and pins whichever call(s) are
responsible, or documents why it's sandbox-only"). The operator explicitly
overrode that recommendation: this mission must root-cause and fix the
mid-run corruption (or apply the documented, evidenced fallback from Edge
Case (a) if the timebox is exhausted), not merely file it as a separate
issue and move on.

## Success Criteria *(mandatory)*

Success is framed around **trustworthiness of the nightly signal**, not an
unconditional "the leg turns green" claim — the evidence in hand does not
support that claim yet (Edge Case (c)), and claiming it anyway would be the
green-washing Standing Order 9 forbids.

### Measurable Outcomes

- **SC-001**: A manual `workflow_dispatch` of `ci-nightly.yml` on the
  mission branch shows the `interpreter-matrix` job's `pytest` invocation
  running under Python 3.13 with the `test` extra installed — zero
  `ModuleNotFoundError` for `pytestarch`, `respx`, or `pytest_benchmark`.
  (Was: 13 such collection errors every night for 7 consecutive nights.)
- **SC-002**: The 4 confirmed `dir_fd`-related kernel test failures
  (`test_lock_parity.py` ×3, and the non-parametrized
  `test_read_rejects_symlink_planted_before_open` symlink-planting test in
  each of the two separate `test_no_follow.py` copies) pass on Python 3.13,
  with no behavior change on 3.11/3.12. (Was: 5 ERRORs — 3 + 2 across the two
  `test_no_follow` copies — with a `TypeError: ... unexpected keyword
  argument 'dir_fd'` signature.)

  > **Mission-closing correction (filed post-implementation, does not
  > change SC-002's outcome):** this spec (User Story 2, FR-002, and
  > SC-002 above) describes the confirmed set as "**4** confirmed `dir_fd`
  > failures." The actual, fuller set both WP02 (the fix) and WP05 (the
  > re-measurement) worked and verified against is **5 IDs**:
  > `tests/kernel/test_lock_parity.py::test_naive_second_open_of_a_held_lock_raises_under_simulation`,
  > `tests/kernel/test_lock_parity.py::test_sync_primitive_never_reopens_the_resource_while_held`,
  > `tests/kernel/test_lock_parity.py::test_async_primitive_never_reopens_the_resource_while_held`
  > (3 in `test_lock_parity.py`), plus one
  > `test_read_rejects_symlink_planted_before_open` in each of the two
  > separate `test_no_follow.py` copies
  > (`tests/kernel/test_no_follow.py` and
  > `tests/specify_cli/core/test_no_follow.py`) — 5 total, not 4. This
  > spec's own SC-002 parenthetical elsewhere on this line already says
  > "Was: 5 ERRORs" — the "5" and "4" figures coexisted in this document
  > without being reconciled. WP05's re-measurement evidence
  > (`evidence-remeasurement-3.13.md`) explicitly checked the fuller 5-ID
  > set and confirmed none of the 5 appear in the post-fix failure set.
  > The original "4" text above is left as written, not silently edited,
  > per the mission's append-only correction convention (see `plan.md`'s
  > "Tasks-phase amendment" notes for precedent).

- **SC-003**: The shared-`.venv` mid-run interpreter identity is stable
  across a full `fast or unit` / `-n auto` run — either proven via a
  regression test after a named fix, or the documented fallback mitigation
  from Edge Case (a) is in place with a follow-up issue filed and evidenced.
  (Was: an unquantified, undocumented hazard, discovered by accident.)
- **SC-004**: The 3.13 `fast or unit` failure count is re-measured after
  SC-003's fix/fallback lands, and that re-measured count (not the original
  429) is what any remaining-scope decision is made against, recorded with
  exact command + counts in the mission's PR.
- **SC-005**: Any residual 3.13-only failure beyond the 4 fixed in SC-002 is
  explicitly disposed of — filed against #3189 with the re-measured
  evidence — rather than left unaddressed and unremarked. The
  `interpreter-matrix` leg may legitimately still report red at mission
  close if genuine, out-of-scope divergence remains; that red is honest
  signal, not mission failure, provided SC-005's disposition has happened.
- **SC-006**: A fresh GitHub issue reports the 21 pre-existing 3.11 `fast or
  unit` failures per the charter's Pre-existing Failure Reporting Rule (FR-005),
  discharging the obligation this mission's own investigation triggered.
