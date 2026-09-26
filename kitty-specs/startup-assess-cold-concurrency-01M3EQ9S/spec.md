# Mission Specification: Concurrency-safe cold startup asset assessment

**Mission Branch**: `issue-3998-startup-assess-cold-concurrency`
**Created**: 2026-09-26
**Status**: Draft (post-spec squad folded)
**Input**: GitHub issue #3998 (P1, milestone 4.0.0 release scope). The pre-spec grounding squad reproduced it on main `a862d471a9`, and the operator confirmed the Intent Summary.

## Context

Every Spec Kitty command that runs startup asset preparation prepares its global assets before it runs. Three owners each prepare one family into the per-user Spec Kitty home: the runtime (mission templates and doctrine), the global slash commands, and the global skills. (`next`, `session-start` and the live-work hook skip startup preparation entirely.)

The failure is on a **cold home**, meaning a home the assets have never been written to (a fresh CI runner, a new machine, an orchestrator starting several agents at once). If several commands start together there, one becomes the installer. The others read the half-written home while that peer is still writing it.

That read is a **torn read**: one preparation pass sees the same path in two different states. On an unlocked pass it is evidence of a peer mid-write, not a failure. Today the unlocked pass retries three times back-to-back and never waits for the writer. It loses the race under load, and the command the user or agent actually ran crashes with a traceback (`RuntimeError: Asset changed during preparation: …/runtime_bootstrap-assets.json`).

Observed on main: 5/32 processes crashed on a fresh shared home (N=32), and 1/16 with 4 CPUs (N=16). A warm home never fails.

The original shape in #3998 was "Global asset input changed" at the slash-commands recheck. PR #4174's re-assess-under-lock seam already closed it for same-version peers. The residual this mission fixes is the torn read on the **unlocked assessment**, which happens *before* that seam is reached. The same pattern exists in all three owners.

## Domain Language

| Canonical term | Meaning | Do not confuse with |
|---|---|---|
| **Torn read** | Within one preparation pass, the same path is observed in two different states ("Asset changed during preparation"). On a destination-role path it is evidence of a concurrent writer. | **Asset input drift** ("Global asset input changed"): a recorded observation no longer matches at recheck time. That is the reassess gate owned by #4885, and it is out of scope here. |
| **Observation role** | Whether an observed path was read as a packaged *source* or probed as this owner's managed *destination*. A path once read as a source stays source-role. | — |
| **Unlocked assessment** | The first preparation pass, taken without holding any lock (the lock-free warm-path fast check). | **Under-lock reassessment**: the rebuild performed while holding the serialization point (`apply_with_reassess`, #4174). |
| **Owner lock** | The per-owner lock file that serializes writers of one asset family. | **Cold-install sentinel**: serializes installers before any owner lock exists. **In-process held-lock set**: re-entrancy bookkeeping. **`.lock`-named stamps** (`version.lock`, freshness stamp): content files, not locks. |
| **Serialization point** | Exactly the lock set the existing locked recheck acquires for an owner: the cold-install sentinel when any of the owner's lock paths is absent, plus every owner lock path that exists, recorded in the in-process held-lock set. One authority, never a second, parallel lock choice. | "the lock" (ambiguous: always say owner lock, cold-install sentinel, or serialization point). |
| **Recheck** | The existing precondition check of an assessment against disk immediately before apply. The unlocked diagnostic is advisory; the check under the serialization point is authoritative. | The upgrade manifest's command-completion recheck (unrelated). |
| **Cold home** | A home that has never been written to, with no owner lock yet. | A **warm home**: already materialized. The fast path must stay lock-free there. |
| **Converge** | After waiting for the peer, the reassessment shows nothing left to do (or a consistent remainder the normal locked apply completes), and the command proceeds. | "Retry until green": re-racing the writer without waiting for it. |
| **Source drift** | A packaged *source* asset changed between observation and use, including a source-role torn read. Always refused. | A peer materializing canonical *destination* bytes, which is tolerated. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent commands on a fresh home all run (Priority: P1)

An orchestrator starts several agents on a freshly installed Spec Kitty. Each agent's first command that runs startup preparation (for example `implement`, `events --help`) hits the same cold home at the same moment. One becomes the installer. Every other command waits for the installer's write, confirms the home is consistent, and then runs the command it was asked to run.

**Why this priority**: This is the reported defect (#3998, P1, a 4.0.0 release-scope blocker). An intermittent crash of an arbitrary command on first use hits new machines, CI runners and multi-agent orchestration.

**Independent Test**: Through each owner's pre-existing startup entry point, inject a torn read at the file-observation level on every unlocked assessment, with the simulated peer finishing inside the real lock acquisition. Startup completes without raising. Run this for each of the three owners.

**Acceptance Scenarios**:

1. **Given** a cold home and a peer mid-write to the runtime assets, **When** a command starts and its unlocked assessment tears, **Then** the command acquires the serialization point, reassesses once under it, converges, and runs. No traceback, and the exit code is that of the actual command.
2. **Given** the same situation for the global slash-commands owner, **When** the command starts, **Then** it converges the same way.
3. **Given** the same situation for the global skills owner, **When** the command starts, **Then** it converges the same way.
4. **Given** 16 or 32 concurrent commands on a fresh isolated home (the #3998 reproducer), **When** they all start together, **Then** all exit 0 across repeated runs (recorded evidence).

---

### User Story 2 - Warm startup is unchanged (Priority: P1)

A developer runs commands on an already materialized home. Startup behaves exactly as it does today: one lock-free check, no lock taken, no extra preparation pass.

**Why this priority**: The warm path is every command's hot path. #4174 established it as lock-free with a single check, and the perf work (#4516) depends on not adding passes to it.

**Independent Test**: On a warm home, spy on the lock primitive and each owner's assessment during startup. Each owner makes exactly 1 assessment and 0 lock acquisitions.

**Acceptance Scenarios**:

1. **Given** a warm home, **When** a command starts, **Then** each owner performs exactly one unlocked assessment and acquires no lock.
2. **Given** a warm home and no concurrent peer, **When** a command starts, **Then** the torn-read escalation is never entered.

---

### User Story 3 - A genuine failure is reported, not hidden (Priority: P2)

When startup preparation truly cannot complete, the user gets a stable diagnostic naming the owner, the path and a next step, not a Rich traceback. Examples: a torn read that recurs while the serialization point is held, or source drift.

**Why this priority**: The #3998 "Expected" asks for a stable, actionable diagnostic when a run cannot proceed. Waiting must never mask a real fault.

**Independent Test**: Force a torn read that recurs under the serialization point. Startup exits 1 with the stable diagnostic in both text and `--json` modes, and no traceback frames are printed. Separately, force a source-role torn read and confirm it is refused without acquiring any lock.

**Acceptance Scenarios**:

1. **Given** a torn read that recurs while the serialization point is held, **When** a command starts, **Then** it exits 1 with a stable diagnostic naming the owner and path (one stderr line, or a JSON error object under `--json`), and no traceback.
2. **Given** a torn read on a source-role path (a packaged source asset changing mid-preparation), **When** a command starts, **Then** preparation refuses it immediately as source drift. There is no waiting and no escalation.
3. **Given** any preparation failure that is not a torn read (invalid inventory, missing package assets, unreadable file), **When** a command starts, **Then** it fails without waiting or retrying. The diagnostic content is the same as today, rendered through the existing CLI error-presentation hook (exit 1, no traceback).

### Edge Cases

- **The peer crashes mid-write and releases its lock with a partial tree.** The waiting command reassesses under the serialization point and sees a consistent, partially-materialized home. The reassessment plans the remaining effects, and the normal locked apply then completes the install.
- **Sentinel-to-owner-lock handoff.** A late process arrives after the installer created the owner lock file, so it serializes on the owner lock instead of the sentinel. The installer must hold that owner lock across its writes, so the late process cannot tear while holding its serialization point. The installer's apply already has a short create-then-lock window. It is benign, because writes are atomic and canonical, and it is recorded here but not changed.
- **Nested or re-entrant preparation (this process already holds the owner's locks).** A torn read there is terminal. It never blocks on itself.
- **Several owners cold at once.** Owners run one after another, and each releases its serialization point before the next starts. No new cross-owner ordering is introduced.
- **Callers of the owner assessment outside startup** (the skills installer, and the slash-commands tool-surface provider used by upgrade/doctor planning). Because the fix lives at the assessment layer, they also wait and reassess on an unlocked destination torn read. The skills installer's cross-family batch "observations disagree" conflict is a different signal and stays terminal (out of scope).
- **A peer running a different CLI version writes non-canonical bytes.** Out of scope. The existing under-lock precondition path still refuses it (noted, not changed).
- **Windows.** The escalation path must not read a held owner lock file's bytes (#4703).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Unlocked torn read escalates to serialized reassessment | As a CLI user on a cold shared home, I want a destination-role torn read on an owner's unlocked assessment to make that assessment acquire the owner's serialization point and rebuild once under it, so that my command waits for the concurrent writer and proceeds instead of crashing. | High | Open |
| FR-002 | One shared mechanism at the assessment layer | As a maintainer, I want the runtime, global slash-commands and global skills owners' assessments to adopt one shared escalation primitive that replaces the unlocked back-to-back retry. The serialization point must be a single extracted authority shared with the existing locked recheck, so the fix cannot drift between owners and no second lock authority exists. | High | Open |
| FR-003 | Torn read carries a typed identity end-to-end | As a maintainer, I want a torn read raised as a distinct exception type that carries the path, its observation role, and the owner's lock paths and anchor. When it is terminal, the owner assessment must show it under a distinct diagnostic code, not the generic "assets unavailable" code. Handling then routes on type and code rather than message text, and the identity survives to the startup entry points. | High | Open |
| FR-004 | Only an under-serialization torn read is terminal | As a CLI user, I want a torn read that recurs while the serialization point is held (including one already held re-entrantly by this process) to fail preparation, and a source-role torn read to be refused immediately, so that a genuine fault is never hidden behind waiting. | High | Open |
| FR-005 | Startup preparation failures render without traceback | As a CLI user whose startup asset preparation cannot complete, I want the startup entry points to raise an error that the existing CLI error-presentation hook renders: exit 1, one stderr line or a JSON error object under `--json`, naming the owner and a next step. The offending path appears in the error text; the JSON envelope `path` stays `null`, because diagnostics carry no structured path (the reviewed, accepted deviation). I get a stable actionable diagnostic instead of a traceback. The error stays catchable as the runtime error type existing callers catch. | Medium | Open |
| FR-006 | Deterministic red-first regression coverage | As a maintainer, I want a deterministic regression test per owner so the defect cannot silently return. It must drive the pre-existing startup entry point. It injects the torn read at the file-observation level, never by patching the assessment, the retry/escalation primitive or the new helper. The simulated peer finishes inside the real lock acquisition. It must be red on main with the exact `Asset changed during preparation` failure. | High | Open |
| FR-007 | Direct coverage of the escalation primitive | As a maintainer, I want direct unit tests for the escalation primitive covering six cases: a clean first pass (no lock); a destination torn read (one serialized rebuild); a torn read under serialization (terminal); a re-entrant held lock (terminal, never blocks); a source-role torn read (refused without locking); and an error that is not a torn read (propagates immediately). | Medium | Open |
| FR-008 | Operator signal when waiting | As an operator, I want one INFO message on the owner's logger when startup waits for a concurrent peer, following the existing operator-signal convention. It stays silent on stdout in `--json` mode and never contains the word "Error". Like the existing converged-no-op message, it is visible whenever INFO logging is enabled for that logger, and it is never mistaken for a failure. | Low | Open |
| FR-009 | Tracker closeout | As the operator, I want #3998 closed by this mission's PR, #4017 closed by the same PR with the nightly evidence that PR #4174 fixed it, and #4885 informed with a comment that the torn read is distinct from the reassess gate, so that the tracker reflects reality. | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fresh-home concurrency reliability (evidence) | Ivan's fresh-home reproducer (#3998 comment) yields 0 non-zero exits and 0 tracebacks at N=16 and N=32, 5 runs each, including one run pinned to 4 CPUs. The results are recorded as PR evidence, not a CI gate; SC-002's deterministic test is the gate. | Reliability | High | Open |
| NFR-002 | Warm path unchanged (spy-verified) | A fast-tier test spies on the lock primitive and each owner's assessment. On a warm home, each owner performs exactly 1 assessment and 0 lock acquisitions per startup. | Performance | High | Open |
| NFR-003 | Bounded wait, no busy-retry | On the torn-read path, each owner makes exactly 1 serialization acquisition for the escalation. It performs at most 1 additional assessment on the converge path, or at most 2 when effects remain and the normal locked apply runs. No unlocked back-to-back retry loop remains, and the wait is bounded by the same lock acquisition the existing locked apply already performs. | Reliability | Medium | Open |
| NFR-004 | Code quality gates | Every new or changed function has cyclomatic complexity ≤ 15. ruff, ruff format and mypy --strict report 0 issues on touched files. New branches reach ≥ 90% diff coverage. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Source drift always refused | Source drift detection is never relaxed. A source-role torn read is refused immediately, with no escalation. Only destination-side concurrency is tolerated. | Technical | High | Open |
| C-002 | Warm path stays lock-free | The lock-free single-check warm path (#4174) is preserved. The serialization point is entered only after an unlocked destination-role torn read. | Technical | High | Open |
| C-003 | No batch replay | Escalation happens inside the owner's local build, before any shared cross-owner batch inclusion. The batch is included exactly once, from the stabilized result. | Technical | High | Open |
| C-004 | Reassess gate is out of scope | The asset-input-drift reassess gate ("Global asset input changed") is neither removed nor narrowed. That decision belongs to #4885. | Business | High | Open |
| C-005 | No re-entrant deadlock | If this process already holds any serialization point (the in-process held-lock set is non-empty), a torn read is terminal instead of blocking. Serialization points never nest, because the cold-install sentinel is shared across owners and is non-reentrant. | Technical | High | Open |
| C-006 | Existing out-of-scope seams untouched | These are not changed: the managed-skills paired global+project composition (#4174 scoped out), the skills installer's cross-family batch conflict, agent install fan-out (#3048), config caching (#4516), the different-CLI-version peer precondition residual, and e2e lane placement (#4207). | Business | Medium | Open |
| C-007 | Red-first through the pre-existing entry point | The regression test drives each owner's pre-existing startup entry point and is committed red before the fix (ADR 2026-07-17-1). | Technical | High | Open |
| C-008 | One serialization authority | The escalation and the existing locked recheck acquire the serialization point through one shared code path. A test asserts that both select the identical lock set (sentinel key plus owner lock paths) for the same owner. | Technical | High | Open |
| C-009 | Windows lock-read safety | Owner lock files are observed without reading their bytes on the escalation path (#4703). The existing mandatory-lock read simulation covers this. | Technical | High | Open |
| C-010 | Reuse the CLI error-presentation seam | FR-005 reuses the existing guarded-read error base and the global presentation hook. No new renderer and no new exit-code convention. | Technical | Medium | Open |

### Key Entities

- **Owner assessment**: one owner's plan of effects for its asset family. It is either complete or incomplete with diagnostics.
- **Torn-read signal**: typed evidence that a path changed within one pass. It carries the path, the observation role and the owner's serialization identity (lock paths and anchor).
- **Serialization point**: see Domain Language. It is the one lock set shared with the locked recheck.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 crashes across 10 runs of concurrent commands started on a fresh shared home (5 at N=16, including one CPU-pinned run, and 5 at N=32), recorded as PR evidence. Today up to 5/32 crash per run.
- **SC-002**: The deterministic torn-read regression test fails on main for all 3 owners and passes after the fix.
- **SC-003**: Warm-home startup performs the same number of preparation passes (1 per owner) and lock acquisitions (0) as before the change.
- **SC-004**: When startup preparation genuinely cannot complete, the user sees a single stable error line (or JSON error object), exit 1, and 0 traceback frames.
- **SC-005**: #3998 and #4017 are closed by the mission PR, and #4885 carries a cross-reference comment.

## Assumptions

- Blocking on the serialization point ends when the installing peer finishes its write. This is the same assumption the existing locked apply path makes.
- One additional assessment pass under the serialization point is cheap compared with the peer's install.
- Owner assessments reached outside startup (upgrade/doctor planning, the skills installer) may now block briefly on a concurrent installer after a torn read. This is intended and will be recorded in the plan and module docs. It is not gated by a flag.
- A peer creating children never tears an ancestor directory's observation, because directory observations exclude mtime and compare identity by device/inode. So refusing source-role torn reads does not reintroduce crashes under legitimate concurrency. The plan verifies this with a test.
- The different-CLI-version peer residual (under-lock precondition refusal on non-canonical bytes) is rare and stays as-is. It is noted in the PR, not fixed.

## Out of Scope

- Removing or narrowing the "Global asset input changed" reassess gate (#4885, decision-shaped; comment only).
- The different-CLI-version peer residual on the under-lock precondition path.
- The skills installer's cross-family batch conflict, the managed-skills paired composition, agent install fan-out (#3048), config caching (#4516), and moving the e2e lane back to per-PR (#4207).
