# Mission Specification: Acceptance-matrix atomic read-modify-write (lost-update fix)

**Mission Branch**: `fix/acceptance-matrix-atomic-rmw`
**Created**: 2026-09-21
**Status**: Draft (hardened after post-spec adversarial squad)
**Input**: Operator mission brief "Mission B — Acceptance-matrix atomic RMW (P0: #4858)" plus the code-grounding report `grounding-4858.md`, both prepared on baseline `upstream/main @ 32cfc272ee`.

## Intent Summary *(confirmed via operator brief)*

Discovery was supplied in full by the operator's mission brief and a same-baseline code-grounding report, and the operator directed autonomous execution; this section records the confirmed scenario and assumptions in lieu of an interactive interview.

- **Primary actor**: an automation agent (or CI job) that records acceptance verdicts for a mission by running `spec-kitty agent mission acceptance-verdict` — once per acceptance criterion or negative invariant.
- **Trigger**: two such verdict invocations run concurrently for **different** entries (e.g. two distinct negative invariants) against the same mission's acceptance matrix.
- **Desired outcome**: every committed verdict row survives, and the mission's overall verdict is honest — it stays `fail` whenever any committed row failed.
- **Invariant that must always hold**: a verdict write may only change the single row it owns (its criterion id or invariant id); it must never overwrite, drop, or resurrect any other row from a stale snapshot.
- **Canonical domain terms**: *acceptance matrix*, *acceptance criterion*, *negative invariant*, *entry_id*, *overall verdict*, *flat layout* vs *coordination (coord) layout*.

**Assumptions**
- The reproduction is driven deterministically (a serialized read1 → run2 → finish1 interleaving), not with real threads, so the regression guard is not stress-flaky.
- The existing per-mission status lock keyed on the git common dir is the correct coordination primitive (it spans the primary checkout and coordination worktrees); no new lock primitive is introduced. (Validated by the post-spec architecture lens against `status/locking.py::feature_status_lock_path`.)
- Behaviour of a single (non-concurrent) verdict invocation is unchanged, including idempotent re-run (FR-012 no-op) semantics already covered by the suite.

## Scope Boundaries *(explicit, per post-spec architecture lens)*

- **In scope**: serializing two concurrent `acceptance-verdict` invocations against each other (verdict-vs-verdict), on both flat and coordination layouts, for both the negative-invariant and acceptance-criterion modes.
- **Deliberately NOT in scope**: serializing a verdict write against the other matrix writers — finalize scaffolding, the accept-gate residual sweep, `gates_core` evaluation, post-consolidation. Those are temporally separated from verdict recording (finalize precedes verdicts; accept follows them) and are not the #4858 root. This fix does **not** claim to close the general matrix RMW race; it closes the verdict-pair lost-update. Routing the shared low-level writer through the atomic door does, however, give *every* writer torn-free file writes as a side benefit.
- **Referenced, not folded**: #2482 (P2, same file, restage-clobber — a different mechanism) stays a note (C-005). No parent epic; do not file under #3347/#4792.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent negative-invariant verdicts never lose a committed row (Priority: P1)

Two acceptance-verdict invocations run at overlapping times for two **different** negative invariants of the same mission's matrix. The invocation that *read* the matrix first (A) happens to *finish* last. Today, A writes back the whole matrix from the snapshot it read before its own slow check ran, silently erasing the row B committed in the meantime — and because the overall verdict is recomputed from whatever rows remain, a mission with a committed failing invariant can flip from `fail` to `pass`. Both invocations still exit `0`.

**Why this priority**: This is the P0 data-loss defect. A silently dropped failing row lets a broken mission be accepted; there is no MVP without fixing it.

**Independent Test (deterministic harness — test-craft contract)**: Drive the interleaving with **no real threads** by wrapping the single seam that sits between A's matrix read and A's write. In negative-invariant mode that seam is the custom check `enforce_negative_invariants`, invoked at `_run_negative_invariant_mode` **after** the `L440-441` read and **before** the `L335` write. The harness MUST patch the **command-module binding** `specify_cli.cli.commands.agent.acceptance_verdict.enforce_negative_invariants` (the command imports the symbol by name at module load, so patching `specify_cli.acceptance.matrix.enforce_negative_invariants` would NOT intercept the command's call and would produce a false green). The wrapper is **one-shot**: guarded by a `nonlocal` "already-driven" flag, it drives B's full invocation exactly once (B runs the real, un-wrapped check and commits), then delegates to the real check for A — otherwise B's own call to the same patched name recurses infinitely.

**Acceptance Scenarios**:

1. **(FR-004-bearing case — the fail→pass flip)** **Given** a matrix and two verdict invocations for distinct invariants where A reads the matrix, **When** B then fully completes and commits a **failing** invariant row (`still_present`) and A then completes and writes its **passing** invariant row, **Then** — asserted by **re-reading the matrix from disk** (`read_acceptance_matrix(matrix_dir)`, never an in-memory object) — B's failing row is present with its evidence, A's row is recorded, and the disk-computed overall verdict is `fail`. On the buggy base this scenario is RED because B's row is absent and the verdict is `pass`; it is the only scenario that exercises both the row-drop and the verdict flip.
2. **(mid-point provenance checkpoint)** **Given** the same interleaving, **When** B completes inside the wrapped seam and **before** A resumes, **Then** the on-disk matrix already contains B's row — proving the eventual loss is attributable to A's stale-snapshot overwrite (#4858), not to a B-side commit/routing failure (#2482).
3. **(row survival, no-flip direction)** **Given** the overlap where B commits a **passing** row and A commits a **failing** row, **When** both finish, **Then** both rows are present on disk and the overall verdict is `fail` (A's failing row is not lost).
4. **(lock is actually acquired — gates C-001/C-002 deterministically)** **Given** a single or concurrent verdict invocation, **When** it performs its re-read-and-write, **Then** a spy on `specify_cli.status.locking.feature_status_lock` records that it was acquired with `lock_key == matrix_dir.name`, and the resolved lock-file path lies under the git **common** dir. This assertion is required because the serialized no-threads harness alone cannot fail on a missing lock (B commits before A's section begins), so without it C-001/C-002 would be review-only.
5. **(slow check runs outside the lock — gates NFR-002)** **Given** a verdict invocation, **When** its call order is observed, **Then** the slow custom check is invoked **before** the lock is acquired (the held critical section is only re-read + merge + write + commit).

### User Story 2 - Correctness holds on both flat and coordination layouts (Priority: P1)

The defect and its fix must behave identically on a flat layout and a coordination layout. The coordination layout is where a naive per-checkout / per-cwd lock would fail: the two writers may act through **different worktree roots** that share one git common dir.

**Why this priority**: The brief and grounding confirm the bug reproduces on both layouts; a fix whose lock is keyed per-checkout would still corrupt the coord surface — the common multi-lane case.

**Independent Test**: Build a real coordination-topology mission via `_build_coord_mission_for_matrix`, which returns `(result, coord_root, coord_feature_dir)` — `result.feature_dir` is the primary checkout root and `coord_root` is the coord worktree root, two distinct paths sharing one `.git` common dir. Prove the lock spans worktrees by **either** (a) driving invocation A with `repo_root=`primary and invocation B with `repo_root=coord_root` (both resolving the same underlying matrix) and asserting the row-survival + honest-verdict outcomes, **or** (b) a focused lock-key-equality unit test asserting the two roots resolve the **same** lock-file path. The coord acceptance-matrix path must be asserted **distinct from** the primary path (non-vacuous), so a silent degrade-to-primary cannot pass the scenario vacuously.

**Acceptance Scenarios**:

1. **Given** a coordination-topology mission whose acceptance-matrix path resolves to the coordination surface (asserted distinct from primary), **When** two concurrent verdict invocations for distinct invariants race across the two worktree roots (earlier-started finishing last, one failing), **Then** both rows survive on disk and the overall verdict stays `fail`.
2. **Given** the primary checkout root and the coord worktree root of the same mission, **When** each is passed to the lock helper, **Then** both resolve to the identical lock-file path under the shared common dir (proves C-002 independent of the interleaving).

### User Story 3 - Both verdict modes are protected (Priority: P2)

The guarantee must hold for the acceptance-criterion mode as well as the negative-invariant mode. Criterion mode has **no** slow-check seam (its flow is read → `_resolve_criterion_update` → write, with nothing resembling `enforce_negative_invariants`), so its interleaving must be forced at a **different** seam — wrapping the in-module `_resolve_criterion_update` (or the `write_and_commit_acceptance_matrix` write step) with the same one-shot drive.

**Why this priority**: Grounding confirms criterion mode is structurally identical to invariant mode for this defect; FR-006 must be independently testable, not asserted-but-unexercised.

**Independent Test**: A concurrent-pair criterion-mode test (and ideally one mixed criterion+invariant pair) mirroring US1 Scenario 1's disk-reload row-survival + honest-verdict assertions, using the criterion-mode seam.

**Acceptance Scenarios**:

1. **Given** two concurrent criterion-mode verdicts for distinct criteria where A reads first and finishes last (one failing), **When** both finish, **Then** both criterion rows survive on disk and the overall verdict stays `fail`.

### User Story 4 - Single-invocation behaviour is preserved (Priority: P2)

An agent recording a single verdict, or re-running the same verdict, sees no change: the row is written, an unknown criterion still errors, an invalid result still errors, and an idempotent re-run remains a no-op that creates no new commit.

**Why this priority**: The fix must not regress the well-covered single-writer path.

**Independent Test**: Re-run the existing acceptance-verdict command suite unchanged and confirm green (record/persist, FR-012 idempotent no-op, unknown-criterion exit 1, invalid-result exit 2, coord landing with no stranded primary copy).

**Acceptance Scenarios**:

1. **Given** a matrix with one pending criterion, **When** a single verdict is recorded and the command is re-run with the same inputs, **Then** the first run commits and the second run is a no-op (no new commit, write reported unchanged).

### Edge Cases

- **Both invocations target the same entry id.** Last-writer-wins on that single row is acceptable; no *other* row may be lost and the flow must not deadlock or error. Covered by a focused smoke assertion (the single-thread harness with a reentrant lock must not hang).
- **A row was added on disk between A's read and A's write.** The write merges onto the current on-disk matrix, so the unseen row survives. (Incidentally exercised by US1: B's row is exactly such an unseen row.)
- **The invocation's own entry is absent from the re-read matrix.** The owned row is **inserted**, not dropped — a merge helper that only *replaces* an existing id would fail US1. (Incidentally exercised by US1: A's own row is absent from the disk snapshot it re-reads.)
- **Corrupt or partially written matrix file.** Prevented by construction: the write routes through the atomic door (tempfile + rename), so no reader observes a torn file at the write locus. A single-thread deterministic harness cannot itself observe a torn read; this is guaranteed by the atomic-write door (C-003), not by the concurrency test.
- **Lock contention / a slow sibling.** Acquisition uses the existing bounded-timeout status-lock semantics; the slow custom check runs outside the held lock so the critical section stays short.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Owned-row-only write | As an agent recording a verdict, I want my write to change only the entry I own so a concurrent sibling's committed row is never overwritten. | High | Open |
| FR-002 | Merge onto current on-disk matrix | As an agent recording a verdict, I want my row spliced into the matrix as it currently exists on disk (not a pre-check snapshot) so rows committed after I first read still survive; an owned row absent from the re-read is inserted. | High | Open |
| FR-003 | Serialized read-modify-write critical section | As the acceptance subsystem, I want the re-read, single-row merge, and write-commit to run as one atomic critical section, with `matrix_dir` resolved once and reused as both the re-read base and the write target so the merge base and staged bytes stay coherent. | High | Open |
| FR-004 | Honest overall verdict under concurrency | As a mission owner, I want the overall verdict to remain `fail` whenever any committed row failed so concurrency can never flip a mission from fail to pass. | High | Open |
| FR-005 | Correct on flat and coordination layouts | As a mission on either layout, I want the guarantee to hold identically so coordination-worktree writers are serialized against primary-checkout writers via the shared common-dir lock. | High | Open |
| FR-006 | Coverage for both verdict modes | As a maintainer, I want the guarantee to apply to both negative-invariant and acceptance-criterion modes, each with its own independently-exercised concurrency test at the correct seam. | Medium | Open |
| FR-007 | Preserve single-writer behaviour | As an agent, I want unchanged single-invocation behaviour (record, unknown-criterion error, invalid-result error, idempotent no-op re-run) so the fix introduces no regression. | High | Open |
| FR-008 | Failing regression guard committed before the fix | As a reviewer, I want a deterministic failing-first reproduction committed before the implementation so red-on-base → green-on-fix is verifiable. | High | Open |
| FR-009 | Lock is acquired with the correct key and path | As a reviewer, I want a deterministic assertion that the critical section acquires `feature_status_lock` with `lock_key == matrix_dir.name` and a lock-file path under the git common dir, so the presence and correctness of the lock (C-001/C-002) is gated by a test, not left review-only. | High | Open |
| FR-010 | Atomic write at the shared writer door | As the acceptance subsystem, I want the shared low-level `write_acceptance_matrix` to write via the atomic door (tempfile + rename) so no reader observes a torn file, benefiting every caller of that writer. | High | Open |
| FR-011 | Slow check runs outside the lock | As the acceptance subsystem, I want the slow custom check invoked before the lock is acquired so the held critical section stays short, verified by a call-order assertion. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No row loss under concurrency | Across the concurrent-verdict scenarios, 0 committed rows are lost and 0 fail→pass verdict flips occur, measured by disk-reloaded assertions in the deterministic regression harness. | Reliability | High | Open |
| NFR-002 | Bounded critical section | Only re-read + merge + write + commit are serialized; the slow custom check runs outside the held lock. Falsifiable via a call-order assertion (FR-011), not narrative. | Performance | Medium | Open |
| NFR-003 | Deterministic, non-flaky regression | The reproduction uses a deterministic serialized interleaving (no real threads/processes) with a one-shot, correctly-bound seam wrapper, so it is stable under parallel test execution. | Reliability | High | Open |
| NFR-004 | Atomic file write at the door the fix owns | A write through `write_acceptance_matrix` is never observable as a torn/partial file. Scope is the atomic-write door at that locus; the downstream coord-worktree copy (`shutil.copy2` inside the frozen commit_router) is a pre-existing property out of this mission's scope. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical locking primitive only | Serialization must use the sanctioned kernel locking door; raw `fcntl`/`msvcrt`/`filelock` are forbidden (`tests/architectural/test_lock_primitive_ban.py`). | Technical | High | Open |
| C-002 | Common-dir-keyed lock across worktrees | The lock must be keyed on the git common dir and the mission directory name, so one lock file coordinates the primary checkout and all coordination worktrees. | Technical | High | Open |
| C-003 | Atomic write door | The matrix file write must route through the sanctioned atomic-write primitive; a bare full-file overwrite is not permitted. | Technical | High | Open |
| C-004 | No new `--feature` CLI surface | No new `--feature`-named CLI option; internal `feature_dir`/`feature_slug` parameters are the tolerated exception. | Technical | High | Open |
| C-005 | Scope is #4858 only | Fix the concurrent lost-update root only; #2482 (same file, restage-clobber, different mechanism) is a note and not folded. No parent epic (#3347/#4792). | Business | Medium | Open |
| C-006 | ATDD red-first | A failing reproduction is committed as a distinct commit before any implementation commit (charter C-011 / Standing Order #4). | Technical | High | Open |
| C-007 | Dead-symbol discipline | If the deferred `write_if_changed` atomic extension point is activated, it must gain a real caller in the same change (`__all__` / `test_no_dead_symbols.py`, C-007); otherwise leave it untouched. The atomic-write door used here is `kernel.atomic.atomic_write`, already a live symbol. | Technical | Medium | Open |
| C-008 | No reintroduced retired subsystem tokens | Do not reintroduce retired `sync` tokens in migration/prose (`tests/architectural/test_no_retired_subsystems.py`). | Technical | Low | Open |
| C-009 | Avoid `__init__.py` coupling | Keep the change out of `src/specify_cli/__init__.py` to avoid the mandatory version-bump + CHANGELOG coupling, unless a bump is genuinely warranted. | Technical | Medium | Open |
| C-010 | Lock scope is verdict-vs-verdict | This fix serializes concurrent verdict writers only; non-verdict matrix writers (finalize scaffold, accept residual sweep, `gates_core` evaluate, post-consolidation) remain unserialized and are out of scope (temporally separated from verdict writes). | Technical | Medium | Open |

### Key Entities

- **Acceptance matrix**: the per-mission record of acceptance criteria and negative invariants and their verdicts, persisted as a JSON file whose location is resolved by the placement seam (primary or coordination surface). Carries a computed **overall verdict**.
- **Acceptance criterion / negative invariant**: individual rows, each identified by an **entry_id** (criterion id or invariant id) with a result and evidence.
- **Verdict invocation**: one execution of the acceptance-verdict command that owns exactly one entry_id for the duration of its write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the concurrent two-entry reproduction (earlier-started finishing last), 100% of committed rows survive on disk with their evidence — 0 dropped rows — on both flat and coordination layouts, for both verdict modes.
- **SC-002**: The overall verdict never flips from `fail` to `pass` under any concurrent scenario; it is `fail` whenever any committed row failed, asserted against the disk-reloaded matrix.
- **SC-003**: The reproduction is RED on the mission's planning base commit and GREEN on the mission's final commit, and passes deterministically across repeated and parallel runs.
- **SC-004**: The presence and correctness of the lock is independently gated — a test fails if the lock is absent or keyed off the common dir — and the full targeted acceptance test surface passes with no regressions.
