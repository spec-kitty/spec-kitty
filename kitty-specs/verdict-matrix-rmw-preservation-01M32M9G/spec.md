# Mission Specification: Verdict-matrix RMW preservation

**Mission Branch**: `fix/verdict-matrix-rmw-preservation`
**Created**: 2026-09-21
**Status**: Draft (hardened after post-spec adversarial squad on the #4858 half; #4868 half grounded)
**Input**: Operator mission brief "Mission B — Acceptance-matrix atomic RMW (P0: #4858)" + operator decision to FOLD #4868 (P1). Grounding: `research/grounding-4858.md`, `research/grounding-4868.md`.

## Intent Summary *(confirmed via operator brief + operator fold decision)*

This mission closes one defect class — **a verdict-recording command silently dropping
previously-committed rows from its coordination-resident matrix and exiting success** — across
both verdict matrices. Discovery was supplied by the operator brief and same-family code
grounding; the operator explicitly chose to fold #4868 into this mission.

- **Primary actor**: an automation agent (or CI job) recording verdicts for a mission via
  `spec-kitty agent mission acceptance-verdict` (acceptance criteria / negative invariants) or
  `spec-kitty agent issue-verdict` (issue verdicts).
- **Two triggers (two roots, one class)**:
  - **#4858 (P0, concurrency)**: two `acceptance-verdict` invocations run concurrently for
    **different** entries; the later finisher overwrites the whole acceptance matrix from a
    snapshot it read before its slow check ran.
  - **#4868 (P1, serial migration)**: an `issue-verdict` on a coordination mission with a
    legacy `issue-matrix.md` on its coord authoritative branch migrates the **wrong source
    directory** on the first JSON write, so existing issue verdicts vanish.
- **Unifying invariant that must always hold**: a verdict write must be based on the **true
  authoritative current matrix** (the surface actually read for this mission) and change **only
  the row it owns**; it must never overwrite from a stale (concurrency), partial, or
  wrong-source (migration) snapshot.
- **Canonical domain terms**: *acceptance matrix*, *issue matrix*, *acceptance criterion*,
  *negative invariant*, *issue verdict*, *entry_id*, *overall verdict*, *authoritative /
  coordination (coord) read surface*, *flat layout* vs *coordination layout*.

**Assumptions**
- #4858 reproduction is deterministic (serialized read1 → run2 → finish1, no real threads).
- #4868 reproduction is deterministic and serial (single writer), driven through the **real**
  write-seam (a faked write-seam would not materialize the coord copy and would mask the fix).
- The existing per-mission status lock keyed on the git common dir is the correct concurrency
  primitive (validated by the post-spec architecture lens); no new lock primitive is introduced.
- Single (non-concurrent, non-migrating) verdict behaviour is unchanged, incl. idempotent
  re-run (FR-012 no-op) for acceptance and the existing flat migration for issue.

## Scope Boundaries *(explicit)*

- **In scope**:
  - #4858: serialize concurrent `acceptance-verdict` invocations against each other
    (verdict-vs-verdict), on flat + coord, for both negative-invariant and criterion modes;
    route the shared acceptance writer through the atomic door.
  - #4868: make the `issue-verdict` first-JSON migration read the coord-aware authoritative
    surface and preserve existing rows before upserting the requested issue.
- **Deliberately NOT in scope**:
  - Serializing acceptance verdict writes against the other acceptance-matrix writers
    (finalize scaffold, accept residual sweep, `gates_core` evaluate, post-consolidation) —
    temporally separated from verdict recording (C-010).
  - Any concurrency work on the issue matrix (#4868 is a serial migration bug, not concurrency).
  - **Deferring the atomic-write door on the issue-matrix writer.** `write_issue_matrix` has the
    same full-object-overwrite shape as `write_acceptance_matrix`, but #4868 is a wrong-source
    *read*, not a torn *write*; routing the issue writer through the atomic door is a consciously
    deferred, separate hardening (not required for #4868 correctness) and is left out to keep the
    fix minimal. Noted so a reviewer sees the omission is deliberate.
  - #2482 (P2, acceptance-matrix restage-clobber, different mechanism) — referenced as a note,
    not folded (C-005). No parent epic (#3347/#4792) for #4858.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent negative-invariant acceptance verdicts never lose a committed row (#4858, Priority: P1)

Two acceptance-verdict invocations run at overlapping times for two **different** negative
invariants. The invocation that *read* the matrix first (A) *finishes* last, and today writes
back the whole matrix from its pre-check snapshot, erasing the row B committed meanwhile — so a
mission with a committed failing invariant can flip `fail`→`pass`. Both still exit `0`.

**Why this priority**: The P0 data-loss defect; no MVP without it.

**Independent Test (deterministic harness — test-craft contract)**: Force the interleaving with
**no real threads** by wrapping the single seam between A's read and A's write — in NI mode the
custom check `enforce_negative_invariants`, invoked after the `L440-441` read and before the
`L335` write. Patch the **command-module binding**
`specify_cli.cli.commands.agent.acceptance_verdict.enforce_negative_invariants` (the command
imports the symbol by name, so patching `specify_cli.acceptance.matrix.enforce_negative_invariants`
would NOT intercept the call — false green). The wrapper is **one-shot** (a `nonlocal` "driven"
flag): it drives B's full invocation once (B runs the real check and commits), then delegates to
the real check for A — otherwise B's own call to the same patched name recurses infinitely.

**Acceptance Scenarios**:

1. **(FR-004-bearing — the fail→pass flip)** **Given** two verdicts for distinct invariants where A reads first, **When** B fully completes and commits a **failing** row (`still_present`) and A then writes its **passing** row, **Then** — asserted by **re-reading the matrix from disk** (never an in-memory object) — B's failing row is present with evidence, A's row is recorded, and the disk-computed overall verdict is `fail`. RED on base (B's row absent, verdict `pass`).
2. **(mid-point provenance checkpoint)** **Given** the same interleaving, **When** B completes inside the wrapped seam and **before** A resumes, **Then** the on-disk matrix already contains B's row — proving the loss is A's stale-snapshot overwrite (#4858), not a B-side failure (#2482).
3. **(row survival, no-flip direction)** **Given** B commits a **passing** row and A commits a **failing** row, **When** both finish, **Then** both rows are present on disk and the overall verdict is `fail`.
4. **(lock is actually acquired — gates C-001/C-002 deterministically)** **Given** a verdict invocation, **When** it re-reads and writes, **Then** a spy on `specify_cli.status.locking.feature_status_lock` records acquisition with `lock_key == matrix_dir.name` and a resolved lock path under the git **common** dir. Required because the serialized harness alone cannot fail on a missing lock.
5. **(slow check outside the lock — gates NFR-002)** **Given** a verdict invocation, **When** its call order is observed, **Then** the slow custom check is invoked **before** the lock is acquired.
6. **(atomic write door — gates FR-009/C-003)** **Given** a verdict write, **When** the acceptance matrix is persisted, **Then** a spy asserts `write_acceptance_matrix` routes through `kernel.atomic.atomic_write` (not a bare `path.write_text`). Required because a single-thread harness cannot observe a torn read, so without this a `write_text`-preserving fix would satisfy every behavioural scenario while silently failing C-003.
7. **(re-read is INSIDE the lock — gates FR-003 against the killer mutant)** **Given** a verdict write, **When** its call order is observed, **Then** the strict order is `feature_status_lock.__enter__` → `read_acceptance_matrix` → write/commit → `feature_status_lock.__exit__` (the re-read AND the write both happen while the lock is held). Required because the serial harness cannot fail on a "re-read outside the lock" implementation (B always finishes before A's re-read in the serialized drive), yet that mutant re-opens the P0 under real concurrency.
8. **(fail CLOSED on lock timeout — gates C-012)** **Given** the status lock cannot be acquired within the bounded timeout, **When** the verdict command runs (harness patches `feature_status_lock` to raise the timeout — no threads), **Then** no matrix write occurs (`write_acceptance_matrix`/`atomic_write` is NOT called), the command exits non-zero with a structured error, and it never falls back to an unlocked write. Fail-open would resurrect the exact unlocked stale-snapshot write this mission removes.
9. **(the REPORTED verdict is honest — gates FR-016)** **Given** the concurrent interleaving of Scenario 1, **When** the command emits its result payload, **Then** the reported `overall_verdict` is computed from the re-read+spliced matrix and equals the disk-reloaded verdict (`fail`) — not the stale in-memory snapshot (which would still report `pass`). A calling agent trusting stdout must not be misled.

### User Story 2 - #4858 correctness holds on flat and coordination layouts (Priority: P1)

The concurrency fix must behave identically on flat and coord layouts. Coord is where a naive
per-checkout lock fails: writers may act through **different worktree roots** sharing one git
common dir.

**Independent Test**: Build a real coord mission via `_build_coord_mission_for_matrix` →
`(result, coord_root, coord_feature_dir)` (primary root vs coord worktree root, one `.git`
common dir). Prove the lock spans worktrees by **either** driving A with `repo_root=`primary and
B with `repo_root=coord_root`, **or** a focused lock-key-equality unit test that both roots
resolve the **same** lock-file path. Assert the coord matrix path is **distinct from** primary
(non-vacuous) so a silent degrade-to-primary cannot pass vacuously.

**Acceptance Scenarios**:

1. **Given** a coord mission whose acceptance-matrix path resolves to coord (asserted ≠ primary), **When** two concurrent verdicts for distinct invariants race across the two worktree roots (earlier-started finishing last, one failing), **Then** both rows survive and the overall verdict stays `fail`.
2. **Given** the primary root and the coord worktree root of the same mission, **When** each is passed to the lock helper, **Then** both resolve to the identical lock-file path under the shared common dir.

### User Story 3 - #4858 both acceptance verdict modes are protected (Priority: P2)

The guarantee must hold for criterion mode as well. Criterion mode has **no** slow-check seam
(`read → _resolve_criterion_update → write`), so its interleaving is forced at a **different**
seam — wrapping `_resolve_criterion_update` (or the write step) with the same one-shot drive.
Implementation note: `_resolve_criterion_update` and the `index_by_id`/unknown-criterion lookup
must run against the **freshly re-read** matrix inside the lock (not the pre-check snapshot), and
the negative-invariant splice must **replace-or-append the already-judged row** (a new small
helper) rather than reuse `_register_negative_invariant`, which synthesizes a fresh `pending` row
and would silently reset the judged result.

**Independent Test**: A concurrent-pair criterion-mode test mirroring US1 Scenario 1's
disk-reload row-survival + honest-verdict assertions at the criterion-mode seam.

**Acceptance Scenarios**:

1. **Given** two concurrent criterion-mode verdicts for distinct criteria where A reads first and finishes last (one failing), **When** both finish, **Then** both criterion rows survive on disk and the overall verdict stays `fail`.

### User Story 4 - Issue verdict on a coord legacy-Markdown mission preserves existing verdicts (#4868, Priority: P1)

On a coordination mission whose authoritative coord branch holds a valid legacy
`issue-matrix.md` (e.g. issue #A `fixed` with evidence, no JSON yet), recording a **different**
issue #B via `issue-verdict` today writes a canonical JSON containing only #B — the migration
read the primary `feature_dir` (empty) instead of the coord authoritative surface, so #A
vanishes from active state (its `.md` bytes remain but readers prefer the new JSON). Exit `0`.

**Why this priority**: Silent loss of recorded issue verdicts on the common coord topology; a
release-blocking-adjacent data-preservation failure the operator routed into this family.

**Independent Test (integration — must use the real write-seam)**: A faked `write_artifact`
writes only the primary path and would not materialize the coord JSON, masking the fix — so this
is an integration test with real git + real seam. Reuse `_build_coord_mission_for_matrix`; seed
a legacy `issue-matrix.md` on the coord surface (mkdir the lazily-materialized coord feature dir,
commit on the coord branch) with issue #A `fixed` + evidence; assert the canonical reader
(`load_issue_matrix` via `coord_read_dir_for`) sees #A **before** the call; run
`do_issue_verdict(issue="#B", ...)`; assert the committed coord `issue-matrix.json` (resolved via
`coord_read_dir_for`, never a hand-rolled `-coord` path) and `load_issue_matrix` return **both**
#A and #B. RED on base (only #B). The existing flat control
(`test_issue_verdict_command.py::TestMigrateOnWrite.test_legacy_markdown_mission_migrates_on_first_write`)
already passes and is cited, not rewritten, to prove the fix is coord-specific.

**Acceptance Scenarios**:

1. **Given** a coord mission with a legacy `issue-matrix.md` (#A `fixed` + evidence) on its authoritative surface and no JSON, **When** issue #B is recorded via the real `issue-verdict`, **Then** the command reports `ok` and `migrated is True`, and both #A and #B (with #A's evidence) are present in the committed coord `issue-matrix.json` and via the canonical reader.
2. **(write-staging guard — gates C-011/FR-012, mutation-tested)** **Given** the same call, **When** the migration runs, **Then** a spy asserts `migrate_issue_matrix_to_json` invokes `write_issue_matrix` with `feature_dir == `primary (never `read_dir`/coord). A bare "no untracked primary residue" assertion is INSUFFICIENT — the untouched main write in `do_issue_verdict` cleans primary residue whether the migration write targets primary (right) or coord (wrong), so the residue check passes for the wrong fix too. This scenario must be demonstrated RED against BOTH the base AND the `read_dir`-as-write-`feature_dir` mutant (per mutation-testing discipline), so it genuinely kills that mutant.
3. **(2nd-call idempotency)** **Given** the coord JSON now exists (post-migration), **When** a third issue #C is recorded, **Then** `migrated is False` (short-circuit), all of #A/#B/#C survive, and no primary residue remains.
4. **(control, already green)** **Given** the analogous flat mission, **When** #B is recorded, **Then** both issues are preserved (unchanged behaviour).

### User Story 5 - Single-invocation behaviour is preserved for both commands (Priority: P2)

A single acceptance verdict (record, unknown-criterion error, invalid-result error, idempotent
no-op re-run) and a single issue verdict / existing flat migration behave exactly as before.

**Independent Test**: Re-run the existing acceptance-verdict and issue-verdict command suites
unchanged and confirm green.

**Acceptance Scenarios**:

1. **Given** a matrix with one pending criterion, **When** a single verdict is recorded and re-run with the same inputs, **Then** the first run commits and the second is a no-op (no new commit).
2. **Given** a flat mission with a legacy issue `.md`, **When** an issue verdict is recorded, **Then** existing rows migrate and are preserved (existing behaviour, unchanged).

### Edge Cases

- **(#4858) Both invocations target the same acceptance entry id.** Last-writer-wins on that row is acceptable; no *other* row may be lost; must not deadlock or error.
- **(#4858) A row was added on disk between A's read and A's write.** Merged in (incidentally exercised — B's row is such a row).
- **(#4858) The invocation's own entry is absent from the re-read matrix.** Inserted, not dropped (a replace-only merge helper would fail US1).
- **(#4858) Corrupt / partial matrix file.** Prevented by the atomic-write door (tempfile+rename); a single-thread harness cannot itself observe a torn read.
- **(#4858) Lock timeout.** Acquisition uses a **bounded** timeout; on timeout the command fails closed (no write, non-zero exit, structured error) — never falls back to an unlocked write (C-012).
- **(#4858) Read surface vs commit surface must agree.** The re-read surface (`matrix_dir`) must equal the surface `commit_for_mission` resolves and writes. The coord worktree is materialized **before** the lock is acquired (C-013) so both racers and the commit path resolve the same coord surface; otherwise a first-ever-coord-write or pruned-worktree race could let the commit copy a stale primary-derived matrix over a sibling's coord row. **Precondition**: coord worktree materialized (normal post-`finalize-tasks` state).
- **(#4858) Criterion index recomputed from the re-read.** The criterion `index_by_id`/unknown-criterion check is recomputed from the freshly re-read matrix inside the lock, not the pre-check snapshot, so a concurrently-reshaped criteria list cannot cause a wrong-row splice or IndexError.
- **(#4868) No legacy `.md` and no JSON anywhere.** First write creates a JSON with only the recorded issue — correct (nothing to preserve).
- **(#4868) A coord JSON already exists.** The existing coord-aware JSON existence check short-circuits migration (already correct); the fix must not disturb it.
- **(#4868) Flat mission with legacy `.md`.** Must remain green (primary == authoritative there).
- **(#4868) Malformed legacy coord `.md`.** Behaviour changes with the fix: on base a malformed coord `.md` is silently ignored (migration reads empty primary) and the command wrongly succeeds with only the new issue; after the fix the migration reads the coord `.md` and validation may now raise. **Decision**: fail loudly — but the validation failure must be translated into a **structured `IssueVerdictError`/result** (the command's `except IssueVerdictError` contract), NOT surfaced as a raw traceback. A guard test pins the structured error so a later agent does not misread it as a regression.
- **(#4868) Unmaterialized coord worktree at read time.** If the legacy `.md` is on the coord *branch* but the worktree is not materialized, `read_dir` degrades to primary (empty) and prior verdicts would still be lost. **Precondition**: acceptance/issue verdicts run post-`finalize-tasks`, where the coord worktree is materialized (the normal state). The fix states this precondition explicitly; the happy-path test materializes the worktree, and this degradation path is called out so it is not silently assumed away.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Owned-row-only acceptance write | US1 — a verdict write changes only the entry it owns; a concurrent sibling's committed row is never overwritten. | High | Open |
| FR-002 | Acceptance merge onto current on-disk matrix | US1 — the owned row is spliced into the matrix as it currently exists on disk (not a pre-check snapshot); an owned row absent from the re-read is inserted. | High | Open |
| FR-003 | Serialized acceptance RMW critical section | US1 — re-read + single-row merge + write-commit run as one atomic critical section, with `matrix_dir` resolved once and reused as both re-read base and write target. | High | Open |
| FR-004 | Honest overall verdict under concurrency | US1 — the overall verdict stays `fail` whenever any committed row failed; concurrency can never flip fail→pass. | High | Open |
| FR-005 | #4858 correct on flat and coordination layouts | US2 — the guarantee holds identically; coord-worktree writers are serialized against primary-checkout writers via the shared common-dir lock. | High | Open |
| FR-006 | Coverage for both acceptance verdict modes | US3 — the guarantee applies to both negative-invariant and criterion modes, each independently exercised at its correct seam. | Medium | Open |
| FR-007 | Lock acquired with correct key and path | US1 — a deterministic assertion that the critical section acquires `feature_status_lock` with `lock_key == matrix_dir.name` and a lock path under the git common dir, so C-001/C-002 are gated by test, not review-only. | High | Open |
| FR-008 | Slow acceptance check runs outside the lock | US1 — the slow custom check is invoked before the lock is acquired (short critical section), verified by a call-order assertion. | Medium | Open |
| FR-009 | Atomic write at the shared acceptance writer | US1 — the shared `write_acceptance_matrix` writes via the atomic door (tempfile + rename), asserted by a call-spy (not review-only); no reader observes a torn file; benefits all callers. | High | Open |
| FR-010 | Issue-verdict migrates the authoritative read surface | US4 — the first-JSON migration reads the coord-aware authoritative `read_dir` (the surface actually read for this mission), not the primary `feature_dir` alone. | High | Open |
| FR-011 | Issue-verdict preserves existing verdicts on migration | US4 — recording one issue on a coord legacy-`.md` mission preserves every pre-existing verdict + evidence before upserting the requested issue. | High | Open |
| FR-012 | Issue-verdict write staging unchanged | US4 — the write still stages on the primary copy and routes through the write-seam (coord materialization + primary residue cleanup) unchanged; only the migration read source changes. | Medium | Open |
| FR-013 | Preserve single-invocation behaviour (both commands) | US5 — unchanged acceptance single-writer behaviour (record, unknown-criterion, invalid-result, idempotent no-op) and unchanged flat issue-migration behaviour. | High | Open |
| FR-014 | Failing regression guards committed before each fix | US1/US4 — a deterministic failing-first reproduction is committed before the implementation for BOTH roots; red-on-base → green-on-fix is verifiable per root. | High | Open |
| FR-015 | Fail closed on lock timeout | US1 — acquisition uses a bounded timeout; on timeout the command performs no write and exits non-zero with a structured error, never falling back to an unlocked write. | High | Open |
| FR-016 | Reported verdict is honest | US1 — the command's own reported `overall_verdict` is computed from the re-read+spliced matrix (the committed content), matching disk, so callers trusting stdout are not misled. | High | Open |
| FR-017 | Re-read and commit surface agree, materialized before lock | US1/US2 — the re-read surface equals the commit placement surface; the coord worktree is materialized before the lock is acquired so both racers and the commit path resolve the same coord surface (holds once the worktree is materialized — the normal post-`finalize-tasks` state). | High | Open |
| FR-018 | Structured error on malformed authoritative issue matrix | US4 — a malformed authoritative issue `.md` surfaces a structured `IssueVerdictError`/result (not a raw traceback) rather than silently dropping prior rows. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No row loss | Across all scenarios, 0 committed rows are lost and 0 fail→pass flips occur, measured by disk-reloaded assertions. | Reliability | High | Open |
| NFR-002 | Bounded acceptance critical section | Only re-read + merge + write + commit are serialized; the slow check runs outside the lock. Falsifiable via a call-order assertion (FR-008). | Performance | Medium | Open |
| NFR-003 | Deterministic, non-flaky regressions | Both repros use deterministic interleavings/serial drives (no real threads); the #4858 seam wrapper is one-shot and correctly bound; stable under parallel execution. | Reliability | High | Open |
| NFR-004 | Atomic acceptance write at the door the fix owns | A write through `write_acceptance_matrix` is never observable as torn. Scope is that door; the downstream coord copy (`shutil.copy2` in the frozen commit_router) is a pre-existing property out of scope. | Reliability | High | Open |
| NFR-005 | Backward-compatible signature change | Adding `read_dir=None` to `migrate_issue_matrix_to_json` is backward-compatible for its bulk caller (`_migrate_one_mission`); no caller passes positionally past `feature_dir`. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical locking primitive only | #4858 serialization uses the sanctioned kernel locking door; raw `fcntl`/`msvcrt`/`filelock` forbidden (`test_lock_primitive_ban.py`). | Technical | High | Open |
| C-002 | Common-dir-keyed lock across worktrees | The lock is keyed on the git common dir + mission directory name; one lock file coordinates primary + all coord worktrees. | Technical | High | Open |
| C-003 | Atomic write door | The acceptance matrix write routes through `kernel.atomic.atomic_write`; no bare full-file overwrite. | Technical | High | Open |
| C-004 | No new `--feature` CLI surface | No new `--feature`-named option; internal `feature_dir`/`feature_slug`/`read_dir` params are the tolerated exception. | Technical | High | Open |
| C-005 | #2482 not folded | #2482 (acceptance restage-clobber, different mechanism) stays a note. No parent epic (#3347/#4792) for #4858. | Business | Medium | Open |
| C-006 | ATDD red-first per root | A failing reproduction is committed as a distinct commit before implementation for EACH root (charter C-011 / Standing Order #4). | Technical | High | Open |
| C-007 | Dead-symbol discipline | `kernel.atomic.atomic_write` (a live symbol) is used; the deferred `write_if_changed` is NOT activated (confirmed absent), avoiding the C-007 dead-symbol trap. | Technical | Medium | Open |
| C-008 | No reintroduced retired subsystem tokens | Do not reintroduce retired `sync` tokens in prose/migration (`test_no_retired_subsystems.py`). | Technical | Low | Open |
| C-009 | Avoid `__init__.py` coupling | Keep changes out of `src/specify_cli/__init__.py` (avoids mandatory version-bump + CHANGELOG coupling) unless genuinely warranted. | Technical | Medium | Open |
| C-010 | #4858 lock scope is verdict-vs-verdict | The lock serializes concurrent acceptance verdict writers only; non-verdict acceptance-matrix writers remain unserialized (temporally separated). | Technical | Medium | Open |
| C-011 | #4868 write staging must not move to coord | The issue-verdict fix changes the migration READ source only; it must not pass `read_dir` as the write `feature_dir` (would break the write-seam residue-cleanup contract). Gated by a spy asserting the migration's `write_issue_matrix` receives `feature_dir == primary`, mutation-tested RED against the wrong-fix variant. | Technical | High | Open |
| C-012 | Fail closed on lock timeout | The #4858 lock uses a bounded timeout; on timeout the command never performs an unlocked fallback write (fail-open would re-introduce the P0). | Technical | High | Open |
| C-013 | Re-read surface == commit surface; materialize before lock | The re-read/splice surface must equal `commit_for_mission`'s placement surface; materialize the coord worktree before acquiring the lock so both concurrent racers and the commit path agree on the coord surface. | Technical | High | Open |

### Key Entities

- **Acceptance matrix / issue matrix**: per-mission JSON records of verdicts, whose read surface is resolved by the placement seam (primary or coordination). Each carries a computed overall verdict / verdict rows.
- **Entry / row**: a criterion, negative invariant, or issue verdict, identified by an **entry_id** with a result and evidence.
- **Verdict invocation**: one execution of a verdict-recording command owning exactly one entry_id for the duration of its write.
- **Authoritative read surface (`read_dir`)**: the coord-aware directory the matrix is actually read from for this mission; the write stages on primary and the seam materializes coord.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #4858 concurrent two-entry reproduction, 100% of committed rows survive on disk with evidence — 0 dropped rows — on flat and coord, for both acceptance modes.
- **SC-002**: The acceptance overall verdict never flips `fail`→`pass` under any concurrent scenario, asserted against the disk-reloaded matrix.
- **SC-003**: In the #4868 coord legacy-`.md` reproduction, recording one issue preserves 100% of pre-existing issue verdicts (both #A and #B present with evidence) in the committed coord JSON.
- **SC-004**: Each reproduction is RED on the mission's planning base and GREEN on the mission's final commit, deterministically across repeated/parallel runs.
- **SC-005**: The #4858 lock presence/correctness, the re-read-inside-lock ordering, the atomic-write door, and the fail-closed-on-timeout behaviour are each independently gated by spies/ordering assertions (a test fails if the lock is absent/mis-keyed, if the re-read happens outside the lock, if the write bypasses the atomic door, or if a timeout triggers a fallback write); the reported `overall_verdict` is asserted to equal disk; the #4868 write-staging contract is gated by a `feature_dir==primary` spy (mutation-tested); and the full targeted acceptance + issue test surface passes with no regressions.
