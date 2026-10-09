# Mission Specification: Every Mission-file writer takes the lock, and the runtime never cuts a log it cannot prove is its own

**Mission Branch**: `issue-5883-mission-writer-followups`
**Created**: 2026-10-08
**Status**: Draft (amended after the post-spec squad, 2026-10-08)
**Input**: Operator brief (2026-10-08): follow-ups to PR #5890 (Mission `concurrent-mission-writers-01M4BT23`), issues #5883, #5884 and #5885, starting from that PR's branch. A research squad confirmed all three are still real on that branch and on `main`. A post-spec squad (architecture and review lenses) and a glossary audit widened the scope; every widening below is an operator ruling recorded as a Decision Moment.

## Purpose

PR #5890 gave Mission files one write lock and one verified rollback, and an architectural gate that keeps unlocked read-modify-writes and blind truncates out. Its scout left three things open, and the follow-up squads found how wide each one is.

1. **Unlocked Mission-file writers.** Many writers still read `meta.json`, a work-package file or a matrix and write it back without the Mission lock, so a concurrent locked write is silently erased. The gate covers only two write targets, never `meta.json` or frontmatter, and documents three shapes it does not catch.
2. **The runtime's unverified rollback.** The runtime writes a terminal completion, then cuts its run log (`run.events.jsonl`) back to an earlier size and overwrites `state.json` when the retrospective gate refuses. Two `spec-kitty next` processes on one Mission can reach it.
3. **Planning-flow friction.** Generated commits and several CLI errors say "feature" where the domain object is a Mission. `implement` refuses on an analyze step that neither the tasks prompts nor `spec-kitty next` ever offers. And `next` reads its step order from a template copy under `src/specify_cli/missions` while the canonical copy in `packs/built-in/missions` is marked deprecated, so the two have drifted apart.

The glossary also lacks "topic branch" and contradicts itself on "Mission" and "Mission Run".

This Mission closes all of it so that parallel agents never lose a write, the planning flow offers every step it will enforce, and the canonical template and glossary are the ones in force.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Two writers to one `meta.json` both land (Priority: P1)

Agent A runs `spec-kitty implement WP01`, which records the Mission's VCS lock in `meta.json` under the Mission lock. At the same moment agent B binds a tracker ticket to the Mission. B could equally be `finalize-tasks` recording the target branch, `accept` restamping acceptance fields, a Mission being reopened or discarded, a documentation-mission state update, or consolidation updating its baseline or mission number.

**Why this priority**: the unlocked writer reads `meta.json`, the locked write lands, then the unlocked writer puts its stale copy back. One field silently disappears and both commands exit 0 (#5883).

**Independent Test**: for each writer, pause it after its read on its own thread, let a locked writer on another thread finish, then resume. Both fields are present. The test enters through the writer's real CLI caller.

**Acceptance Scenarios**:

1. **Given** writer B has read `meta.json` and is paused, **When** writer A writes another field under the Mission lock and B resumes, **Then** `meta.json` contains both fields.
2. **Given** a writer is called from a command that already holds the Mission lock on the same thread, **When** it runs, **Then** it does not deadlock, does not take a second, different lock, and still writes.
3. **Given** a Mission whose primary directory name differs from its coordination key (slug without the mid8 suffix), **When** a writer takes the Mission lock, **Then** it takes the same lock as the status transaction does for that Mission.

### User Story 2 - Concurrent work-package frontmatter writers keep each other's changes (Priority: P1)

Two agents map requirement refs onto the same work package (`agent tasks map-requirements`, union mode). Or one agent runs `finalize-tasks` while another adds a history note, or a status transition mirrors a lane into frontmatter.

**Why this priority**: each writer reads the frontmatter, holds it in memory (finalize runs all its ownership checks in between) and writes the whole file back, erasing the other writer's change (#5883).

**Independent Test**: pause the first writer after its read, let the second finish on another thread, then resume. Both changes are present.

**Acceptance Scenarios**:

1. **Given** two `map-requirements` runs add different refs to one work package, **When** they overlap, **Then** both refs are in the frontmatter.
2. **Given** `finalize-tasks` has read the work-package frontmatter and is paused, **When** `add-history` adds a note and finalize resumes, **Then** the note survives finalize's write.

### User Story 3 - Matrix writers never overwrite each other (Priority: P2)

`finalize-tasks` scaffolds the issue matrix while another agent records an issue verdict. Or two agents in different worktrees record acceptance and issue verdicts on one Mission.

**Why this priority**: the scaffold checks that the file is missing and then writes the whole map, so a verdict recorded in between is overwritten. The two locked matrix helpers resolve their lock from a different root than the Mission lock, which gives no mutual exclusion across worktrees (#5883).

**Independent Test**: pause the first writer at its window, let the second finish on another thread (from a second worktree for the helper case), then resume. Both rows are present.

**Acceptance Scenarios**:

1. **Given** the scaffold saw no matrix and is paused, **When** a verdict creates the matrix and the scaffold resumes, **Then** the matrix still holds the verdict row.
2. **Given** two verdict writers on one Mission from two worktrees, **When** they overlap, **Then** both verdicts are recorded.

### User Story 4 - The gate closes the writer class by construction (Priority: P1)

A contributor adds any of these:
- a `meta.json` or frontmatter write outside the Mission lock;
- a callable passed into the lock block that is stored and run after the lock is released;
- a lock keyed on a subscript such as `meta["mission_slug"]`;
- a whole-file rewrite of a status or run log through `open(..., "w")`, `write_text` or `write_bytes`.

**Why this priority**: the gate is how the defect class stays closed, and each of these shapes is a way back in (#5883).

**Independent Test**: one synthetic offender per shape goes red, and one near-miss per rule (the same call on a non-Mission path) stays green. Each rule's self-mutation proof shows that removing the rule turns its offender green. The real source tree passes with an empty allowlist.

**Acceptance Scenarios**:

1. **Given** a synthetic module with each offending shape, **When** the gate scans it, **Then** each shape is reported with its rule.
2. **Given** a near-miss (for example `write_text` on a config file, or a lock keyed on a known Mission-directory-name expression), **When** the gate scans it, **Then** it is not reported.
3. **Given** the real source tree, **When** the gate scans it, **Then** it passes with no allowlist entries beyond the primitive's own sites. Every real site the extended rules newly see has been fixed, routed through the primitive, or excluded by a structural rule stated in the gate (for example the git merge driver writing its output path), never by a named allowlist entry.

### User Story 5 - A refused terminal step leaves the run log and state exactly as other writers left them (Priority: P1)

The retrospective policy blocks completion, a `spec-kitty next` call reaches the terminal step, and the retrospective gate refuses. Meanwhile another `spec-kitty next` on the same Mission appends to the same run directory, or the run log shrinks.

**Why this priority**: a shrunk log is padded with NUL bytes, another writer's rows are cut, and another writer's state is overwritten (#5884).

**Independent Test**: drive one fixture twice. With the gate refusing and the run directory mutated inside the gate, nothing is appended and nothing foreign is lost. With the gate passing on the same fixture, the completion row is appended.

**Acceptance Scenarios**:

1. **Given** the gate refuses completion, **When** the call returns, **Then** no completion row was appended, `state.json` was not rewritten, and the decision reads as a retrospective-gate refusal (not a generic engine error).
2. **Given** another writer appended a row or replaced `state.json` while the gate ran, **When** the gate refuses, **Then** that row and that state are still there.
3. **Given** the run log shrank while the gate ran, **When** the gate refuses, **Then** the log contains no NUL bytes.
4. **Given** the engine's cached plan is missing or stale, **When** the terminal step is reached, **Then** the gate still runs before completion is written.
5. **Given** the gate passes on the same fixture, **When** the call returns, **Then** the run completes and the completion row is appended exactly as before.
6. **Given** a run that is already terminal, **When** it is polled again, **Then** the gate is not re-run. This is an accepted behaviour change: the gate runs once, when the step completes.

### User Story 6 - Operator-facing text says "mission" (Priority: P3)

An operator runs specify, plan, finalize-tasks or a documentation-mission planning step and reads the commit subjects, or hits a "canonical status not found", acceptance, plan-validation, validate-tasks or validate-encoding error.

**Why this priority**: the Terminology Canon forbids "feature" for a Mission in operator-facing text (#5885).

**Independent Test**: run `finalize-tasks` through the CLI and read the subject. Trigger each error and read it. A source scan fails on any "for feature" in a commit-message builder or CLI error string.

**Acceptance Scenarios**:

1. **Given** any planning commit builder, **When** it builds a subject, **Then** the subject reads "… for mission `<slug>`".
2. **Given** a Mission finalized before this change, **When** finalize-tasks runs again, **Then** its legacy "Add tasks for feature `<slug>`" commit is still treated as finalize bookkeeping. On the same history, a commit with any other subject still counts as drift.
3. **Given** any of the listed CLI errors, **When** it is shown, **Then** it says "mission".

### User Story 7 - `spec-kitty next` offers the analyze step before implement (Priority: P2)

An operator finishes `/spec-kitty.tasks` on a software-dev Mission and runs `spec-kitty next`, or reads the tasks prompts' handoff.

**Why this priority**: today the prompts and `next` go straight to implement, and implement then refuses with `analysis_report_required`. A later edit to a planning artifact makes the report stale and implement refuses again (#5885).

**Independent Test**: on one fixture Mission with finalized tasks, run `spec-kitty next --json` three times: with no analysis report, with a stale one, and with a current one.

**Acceptance Scenarios**:

1. **Given** the software-dev tasks and tasks-finalize prompts, **When** an agent reads their report and next-step sections, **Then** both name `/spec-kitty.analyze` as the required step before implement, and say that editing the spec, plan, tasks or charter afterwards makes the report stale.
2. **Given** finalized tasks and no analysis report, **When** the operator runs `spec-kitty next --json`, **Then** it issues the analyze step, not implement.
3. **Given** the analyze step was issued but the report is missing or stale, **When** the agent reports `--result success`, **Then** the step does not complete. The JSON names the reason code and the stale inputs.
4. **Given** a current report on the same fixture, **When** the agent reports `--result success` for analyze, **Then** `next` issues implement.
5. **Given** a software-dev run that started before this change, **When** `next` runs after the upgrade, **Then** it is not blocked by template drift.

### User Story 8 - The template `next` reads is the canonical one (Priority: P2)

A maintainer edits the software-dev runtime template in `packs/built-in/missions` and expects `spec-kitty next` to follow it.

**Why this priority**: `next` reads its step order from a copy under `src/specify_cli/missions` while the `packs/` copy carries a "deprecated, do not extend" banner. The two have drifted, and an edit to the canonical pack does nothing (single canonical authority).

**Independent Test**: change the software-dev pack template's step order in a fixture (or add the analyze step) and observe that `next` follows it. No second runtime template copy is read.

**Acceptance Scenarios**:

1. **Given** the built-in templates, **When** `next` resolves the runtime template for each built-in Mission type, **Then** it resolves the one under `packs/built-in/missions` and plans each type exactly as before (apart from the new software-dev analyze step).
2. **Given** the old `src/specify_cli/missions/*/mission-runtime.yaml` copies, **When** the Mission lands, **Then** they are removed (or reduced to something that is not read as a template), and the pack copy no longer says it is deprecated.

### User Story 9 - The glossary defines the terms we use (Priority: P3)

A contributor or agent looks up "topic branch", "Mission" or "Mission Run" in the glossary or in IDE hover.

**Why this priority**: "topic branch" is used across CLAUDE.md, the charter and the guides but defined nowhere. The YAML glossary gives "Mission" the Mission Type meaning. "Mission Run" names a key the runtime does not use. "feature branch" competes with topic branch as a canonical term.

**Independent Test**: read each term on every glossary surface. The existing parity and freshness tests pass, and the generated IDE glossary is current.

**Acceptance Scenarios**:

1. **Given** the canonical glossary pages, the YAML seed, the built-in glossary pack and the generated IDE glossaries, **When** a reader looks up topic branch, Mission or Mission Run, **Then** each surface carries the same definition, with "Do NOT use when" guards.
2. **Given** "feature branch", **When** a reader looks it up, **Then** it is an alias of topic branch. The wire value `feature-branch` is unchanged.
3. **Given** the related glossary inconsistencies the audit found, **When** the Mission lands, **Then** they are fixed:
   - the stale historical Feature entry;
   - the self-contradicting Lane Consolidation entry;
   - the 7-lane Lane list (the state machine has 9 lanes);
   - the out-of-date conventions schema;
   - the contextive slug table;
   - the "work package … inside a mission run" contradiction;
   - the stale generated orchestration glossary.

### Edge Cases

- A writer is reached from a subprocess or git hook while the parent holds the lock. It waits up to the bounded timeout and fails with the existing `STATUS_LOCK_HELD` diagnostic rather than hanging.
- A writer is called with the lock already held on the same thread. The lock key is resolved before the lock is entered and passed down, never resolved inside the lock.
- An offline migration rewrites `meta.json`. It writes under the Mission lock like every other writer; no migration is exempt.
- The run directory or `run.events.jsonl` vanishes while the gate runs. Nothing is created or padded.
- The analysis report goes stale after implement was already issued. `next` cannot step back. The existing implement-time refusal stays as the backstop and names `/spec-kitty.analyze`.
- A non-software-dev Mission type gets no analyze step and no analyze guard.
- Org or project template overrides still win over the built-in pack, in the same tier order as today.

## Domain Language *(optional)*

| Canonical term | Meaning | Avoid |
|----------------|---------|-------|
| Mission lock | The per-Mission lock door `mission_write_lock`, keyed on the canonical Mission directory name | "status lock" for non-status writers, slug-keyed locks |
| Mission file | Any file under a Mission's directory (`meta.json`, work-package files, matrices, status log) | — |
| Run log | `run.events.jsonl` in a runtime run directory; not a Mission file | "event log" (that is the status log) |
| Mission Run | One runtime execution of a Mission's step loop, keyed by `run_id` | "mission session" |
| Topic branch | A short-lived branch carrying one change to a pull request | "feature branch" (alias), "PR branch" |
| Analysis report | The recorded `/spec-kitty.analyze` result that implement and `next` check for currency | — |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `meta.json` setters write under the Mission lock | As an agent, I want every `mission_metadata` read-modify-write and accept's direct restamp writes to read and write inside one Mission-lock hold, so that a concurrent locked write is never erased. The setters are `set_target_branch`, `set_origin_ticket`, `record_discard`, `set_documentation_state`, `record_acceptance`, `clear_merge_metadata` and `flatten_coordination_metadata`. Setters with no production caller (`set_change_mode`, `clear_coordination_metadata`) are removed. The lock key is resolved before the lock is entered, matches the status transaction's key for the same Mission, and nests safely inside `ensure_vcs_locked` and the acceptance verdict guard. | High | Open | [build] | no — per-writer overlap test fails against today's unlocked setters |
| FR-002 | `map-requirements` frontmatter writes under the Mission lock | As an agent, I want `agent tasks map-requirements` to read the existing refs and write the work-package frontmatter inside one Mission-lock hold, so that two overlapping runs keep both refs. | High | Open | [build] | no — overlap test through the CLI fails today |
| FR-003 | `finalize-tasks` frontmatter flush does not erase concurrent writes | As an agent, I want `finalize-tasks` to re-read and write each work package's frontmatter under the Mission lock, so that a history note or ref added while finalize ran survives. Finalize's write-scope restore must not put back stale bytes over a concurrent write. | High | Open | [build] | no — overlap test through the CLI fails today |
| FR-004 | Issue-matrix scaffold checks and writes under the Mission lock | As an agent, I want the issue-matrix scaffold's existence check and write inside one Mission-lock hold, so that a verdict recorded in between is never overwritten. | Medium | Open | [build] | no — overlap test fails today |
| FR-005 | Matrix helpers lock through the Mission lock door | As an agent, I want the acceptance-matrix re-read helper, the acceptance verdict guard and the issue-verdict helper to lock through `mission_write_lock`, so that writers in two worktrees of one Mission exclude each other. | Medium | Open | [build] | no — two-worktree overlap test fails today |
| FR-006 | Gate Rule 2 refuses a callable run after the lock is released | As a maintainer, I want the read/sink rule to accept a callable passed into a lock block only when its parameter is only ever called (never stored, returned or assigned), so that deferred execution after release is caught. | Medium | Open | [build] | no — synthetic offender goes red; self-mutation proof |
| FR-007 | Gate Rule 3 accepts only known Mission-directory-name keys | As a maintainer, I want the lock-key rule to accept only key expressions known to be a Mission directory name, and to check `mission_write_lock`'s first argument as well, so that a subscript or call key such as `meta["mission_slug"]` is caught. | Medium | Open | [build] | no — synthetic offender goes red; near-miss stays green |
| FR-008 | Gate Rule 1 catches whole-file rewrites of status and run logs | As a maintainer, I want the truncate rule to also flag `open(..., "w")`, `write_text` and `write_bytes` whose target is a status or run log, and to scan `src/runtime` with the run-log and run-state names, so that a blind rewrite cannot come back under another name. The matching rule is stated precisely in the gate. Every newly seen real site is dispositioned: the consolidation bookkeeping projection's unlocked status-log rewrite is fixed under the status lock; the lane auto-rebase's create-if-missing becomes an exclusive create; the git merge driver's output write is excluded by a structural rule. | High | Open | [build] | no — synthetic offenders and today's runtime truncate go red; near-miss stays green |
| FR-009 | Runtime terminal gate runs before completion is written | As an operator, I want the retrospective gate on the legacy `next` path to run as the engine's abort-only completion hook and to refuse with a typed retrospective-gate refusal, so that a refused completion appends nothing, rewrites no state and reads as a gate refusal. A run that is already terminal is not re-gated on a later poll. | High | Open | [build] | no — NUL-pad, foreign-row and foreign-state repros fail today; same-fixture pass case appends |
| FR-010 | Runtime speculative rollback is removed | As a maintainer, I want the speculative capture, the rollback of the run log and `state.json`, and the buffering emitter that exists only for that rollback removed, so that no runtime code truncates a run log or restores state it cannot prove is its own. | High | Open | [build] | no — red proof: the deterministic foreign-append reproduction (a row another writer appends between the speculative capture and the rollback is cut today) fails on the pre-fix code |
| FR-011 | The stale-plan fallback never skips the gate | As an operator, I want the path that runs when no plan is cached or the plan is stale to carry the same completion hook, so that the gate runs before completion on every path. | High | Open | [build] | no — stale-plan repro shows completion written without the gate today |
| FR-012 | Operator-facing text says "mission" | As an operator, I want two kinds of text to say "mission": the five planning commit builders (tasks finalize, spec/plan setup, gap analysis, generator config, Mission creation), and the CLI errors that say "for feature" (canonical status not found, acceptance state and event-log errors, plan validation, validate-tasks, validate-encoding). | Low | Open | [build] | no — `finalize-tasks` CLI subject and error-text assertions fail today |
| FR-013 | Finalize drift check accepts the legacy subject | As an operator, I want the finalize drift check to accept both "Add tasks for mission" and the legacy "Add tasks for feature" subject, so that Missions finalized earlier raise no false drift warning. | Low | Open | [build] | no — paired: a legacy-subject fixture passes and a foreign-subject fixture on the same history still drifts |
| FR-014 | Source scan keeps "for feature" out of operator text | As a maintainer, I want a test that fails if a commit-message argument or CLI error string under `src/specify_cli` says "for feature", whatever the string construction (f-string, concatenation, `.format`), so that the wording cannot regress. The hosted-only strings stay out of scope. | Low | Open | [build] | no — fails on today's sites |
| FR-015 | Tasks prompts name the analyze step and its staleness rule | As an operator, I want the report and next-step sections of the software-dev tasks and tasks-finalize prompts to name `/spec-kitty.analyze` as required before implement, and to say editing the spec, plan, tasks or charter afterwards makes the report stale. | Medium | Open | [build] | no — section-scoped content test fails today |
| FR-016 | `next` issues an analyze step between tasks and implement | As an operator, I want the software-dev step order to go tasks → analyze → implement. The analyze step completes only while the analysis report is current; otherwise it refuses with a named reason code and the stale inputs. `next` then never hands out implement without a current report. The currency check reaches the runtime without adding an import to the frozen runtime→specify_cli ledger, and it is computed only when the analyze step is checked or when the finalized-board shortcut would hand out implement. | Medium | Open | [build] | no — `next --json` issues implement today with no report |
| FR-017 | In-flight software-dev runs survive the template change | As an operator, I want a software-dev run that started before this change to keep advancing after the upgrade instead of blocking on template drift, so that adding the analyze step strands no Mission. | Medium | Open | [build] | no — a run started on the old template blocks with "Template changed during active run" today |
| FR-018 | `next` reads the canonical pack templates | As a maintainer, I want the runtime to resolve built-in runtime templates from `packs/built-in/missions` for every built-in Mission type, keeping the same tier order for overrides. The `src/specify_cli/missions` runtime-template copies are retired, the two copies are reconciled into the pack, and the misleading deprecation banner on the pack copy is removed. | Medium | Open | [build] | no — a fixture edit to the pack template is ignored by `next` today |
| FR-019 | Gate Rule 4 keeps `meta.json` and frontmatter writes inside the lock | As a maintainer, I want a gate rule that fails when a `meta.json` or work-package frontmatter write sits outside a Mission-lock region and does not go through a locked helper, with an empty allowlist, so that the writer class is closed by construction. | High | Open | [build] | no — synthetic offender goes red; self-mutation proof; near-miss stays green |
| FR-020 | Every remaining `meta.json` and frontmatter writer takes the lock | As an agent, I want every other read-modify-write of `meta.json` or work-package frontmatter to run under the Mission lock so that FR-019 passes on the real tree. That covers the documentation-mission state writers, the finalize branch-contract recovery, the consolidation teardown, baseline and mission-number writers, the mission loader, the mission-state migration and the status lane mirror. | High | Open | [build] | no — FR-019 is red on today's tree; representative overlap tests per family fail today |
| FR-021 | The glossary defines topic branch, Mission and Mission Run consistently | As a contributor, I want the canonical glossary pages, the YAML seed, the built-in glossary pack and the generated IDE glossaries to carry the same entries for topic branch (new), Mission and Mission Run (rewritten), with "feature branch" as an alias of topic branch, and the related inconsistencies the audit found fixed. | Low | Open | [build] | no — topic branch is absent and the Mission definitions disagree today |
| FR-022 | The built-in software-dev Mission prompts and step definitions are cleaned up | As an operator, I want the shipped software-dev mission-step prompts and step definitions to describe what the CLI actually does, so that an agent following them never hits a refusal the prompt did not mention or follows an instruction the CLI contradicts. This covers: the tasks prompt de-duplicated (one outline, one sizing section, no reference to a template it does not define, no post-finalize frontmatter edits); tasks-outline, tasks-packages and tasks-finalize no longer claiming `next` advances to their sub-step; the analyze prompt stating the staleness rule and full command forms; the accept prompt resolving the repository root checkout correctly from a worktree; the implement prompt no longer pointing at a retired path and naming the analysis-report gate; the `step.yaml` dependency chain, `expected-artifacts.yaml`, the step contracts, the READMEs and the governance profile matching the current step set; "feature" wording, repo-local provenance tokens and the legacy profile-load alias removed. The provenance ratchet baseline shrinks accordingly. | Medium | Open | [build] | no — section-scoped prompt tests and the ratchet fail on today's files (operator ruling 2026-10-08, plan Engineering Alignment) |
| FR-023 | The pack's Mission config matches the config the CLI runs today | As an operator, I want each built-in Mission type's `packs/built-in/missions/<type>/mission.yaml` and `mission-runtime.yaml` to carry the same content as the `src/specify_cli/missions/<type>` copies that `spec-kitty` reads today, so that switching `next` to the pack (FR-018) and the charter readers of the pack copy see the configuration that actually runs. "What runs today" is decided per type by what actually resolves. For `mission.yaml`, the CLI pins built-ins to the src copy, so the pack copy is made equal to it: the unread `task_types` blocks and the documentation `deliverables: docs/output/` are dropped, and wording-only fixes ("feature" to "mission") land in both copies. For `mission-runtime.yaml`, software-dev and plan resolve to src today, so their pack copies take the src content (no extra `agent-profile` keys, and the loadable plan shape). Documentation and research already resolve from the user-global copy of the pack, so their pack runtime files are already what runs and stay byte-unchanged. The software-dev analyze step (FR-016) is the only intended difference in step order. A parity test fails if a pack `mission.yaml` differs from its src copy while both exist. | High | Open | [build] | no — a parity test over the four types fails on today's files (operator ruling 2026-10-08) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Overlap tests are deterministic and cross-thread | Every new concurrency test runs its two writers on distinct threads or processes (the lock is re-entrant per thread), uses injected pause points rather than sleeps, and passes 5 of 5 repeated runs with no flake. | Reliability | High | Open |
| NFR-002 | Lock waits stay bounded | Every newly locked writer uses the existing bounded wait (`BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`, 10 s today) and fails with `STATUS_LOCK_HELD`. Existing unbounded waiters (for example `ensure_vcs_locked`) are unchanged. No new unbounded wait is added. | Reliability | High | Open |
| NFR-003 | The uncontended path stays cheap | A newly locked writer adds exactly one lock acquisition and no git or other subprocess call on the uncontended path, asserted by counting subprocess calls in a test. | Performance | Medium | Open |
| NFR-004 | Gate stays empty-allowlist | The mission-write discipline gate ends the Mission with zero allowlist entries beyond the primitive's own sites. Each new or extended rule has a synthetic offender, a near-miss negative and a self-mutation proof. | Maintainability | High | Open |
| NFR-005 | New code quality | New and changed code passes `ruff check`, `ruff format --check` and `mypy` with zero new issues and no new suppressions. Every touched function stays at complexity 15 or below. | Maintainability | High | Open |
| NFR-006 | Template switch is behaviour-preserving | For each built-in Mission type, the planned step sequence from the pack template equals today's sequence from the `src` copy, apart from the software-dev analyze step. This is asserted per type. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Layer ledger does not grow | The frozen runtime→specify_cli outbound ledger does not grow (it shrinks from 23 to 22 when the two bare imports go); no new `specify_cli` import from `src/runtime` is added. Behaviour the runtime needs from `specify_cli` (the analysis-currency check) is injected by the `specify_cli` caller. | Technical | High | Open |
| C-002 | One lock door | Mission-file writers outside the status pipeline lock through `mission_write_lock`, keyed via `mission_write_lock_dir`. No second lock mechanism is introduced. | Technical | High | Open |
| C-003 | Edit sources, not copies | Prompt changes go to `packs/built-in/missions/mission-steps/software-dev/...`; generated agent copies are not edited. New prompt text carries no work-package ids, issue numbers, requirement ids, `src/specify_cli` paths or concrete Mission slugs; placeholder paths such as `kitty-specs/<mission>/...` are allowed (provenance ratchet; its baseline diff may only lower counts). | Technical | High | Open |
| C-004 | The pack is the canonical runtime template | The analyze step is added to the software-dev runtime template in `packs/built-in/missions`, which becomes the template `next` reads (FR-018). No runtime template is left under `src/specify_cli/missions` for `next` to read. | Technical | High | Open |
| C-005 | Stacked on PR #5890 | The work starts from and builds on the PR #5890 branch. It changes that PR's behaviour only where a requirement here says so. | Business | High | Open |
| C-006 | Red-first | Each FR with "no" in No-op passable gets a reproduction shown failing against the pre-fix code before the fix lands (ADR 2026-07-17-1). Compound FRs (FR-001, FR-008, FR-020) are proven part by part. | Technical | High | Open |
| C-007 | Out of scope | Out of scope: `review/prompt_metadata.write_frontmatter` (a per-invocation temporary file, not a Mission file); git `index.lock` collisions between two committers; serialising two concurrent runtime commits; hosted-only (Team Kitty) "feature" strings. The commitlint rule keeps accepting both "feature" and "mission" subjects for history. | Business | Medium | Open |
| C-008 | Only the runtime step-order template moves | Each built-in type's `mission.yaml`, its `templates/` and the Python modules under `src/specify_cli/missions` stay where they are (their retirement is #2652's later slices). Only the four `mission-runtime.yaml` copies are retired from `src`. Until #2652 retires the src `mission.yaml` copies, the pack and src copies are kept equal (FR-023). | Technical | High | Open |

### Key Entities

- **Mission lock**: the per-Mission lock, re-entrant per thread and keyed on the canonical Mission directory name. Held for every read-modify-write of a Mission file.
- **Run directory**: the runtime's per-Mission run state (`state.json`, `run.events.jsonl`). It is shared by every `spec-kitty next` on that Mission in one repository.
- **Runtime template**: the per-Mission-type step order `next` plans against. After this Mission there is one canonical copy per type, in the built-in pack.
- **Analysis report**: the recorded analyze result. It is current only while the hashed planning inputs (spec, plan, tasks, charter and related material) are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every overlap scenario of User Stories 1–3, both writers' changes are present afterwards in 5 of 5 runs, against 0 of 5 before the fix. — [build] · no-op passable: no
- **SC-002**: A refused terminal step leaves 0 NUL bytes in the run log, removes 0 foreign rows and overwrites 0 foreign states across the three repro scenarios. A passing step on the same fixture still records its completion. — [build] · no-op passable: no
- **SC-003**: The mission-write discipline gate reports each of its new offender shapes and none of its near-misses. On the real tree it finds 0 offenders with 0 allowlist entries. — [build] · no-op passable: no
- **SC-004**: 0 planning commit builders and 0 CLI error strings in scope say "for feature". — [build] · no-op passable: no
- **SC-005**: Measured through `spec-kitty next --json` on one software-dev fixture with finalized tasks, `next` issues implement 0 times while the analysis report is missing or stale, and issues it once the report is current. — [build] · no-op passable: no
- **SC-006**: Every built-in Mission type plans from exactly 1 runtime template, the one in the built-in pack. — [build] · no-op passable: no
- **SC-007**: All 3 glossary terms appear with identical definitions on all 4 glossary surfaces. The generated IDE glossary check passes. — [build] · no-op passable: no
- **SC-008**: After the cleanup, a scripted walk of the software-dev step prompts (specify → … → accept) finds 0 instructions that a CLI command refuses and 0 references to a non-existent path, command or template; the provenance ratchet counts for the touched prompts are lower than today. — [build] · no-op passable: no
- **SC-009**: For every built-in Mission type, the pack `mission.yaml` equals the src copy byte for byte. The pack `mission-runtime.yaml` loads, and it plans the same step sequence with the same dispatch route per step as today's src copy, apart from the software-dev analyze step. — [build] · no-op passable: no

## Assumptions

- Two `spec-kitty next` processes on one Mission are an expected case (the start race is already handled), so the run directory has more than one writer in practice.
- The bulk-edit guardrail does not apply. The "for feature" change touches an enumerated set of commit builders and error strings, listed in FR-012 and kept closed by FR-014's scan; it is not a codebase-wide rename.
- The analyze step's prompt (`software-dev/analyze`) already exists. The Mission wires it into the step order and gives it a guard; the prompt itself is only corrected under FR-022 (staleness rule, recovery recipe, full command forms), not rewritten from scratch.
- The comment that the built-in pack catalog "is not behaviourally equivalent yet" refers to the drift between the two template copies. FR-018 reconciles them, and NFR-006 proves the switch preserves each type's plan.

## Dependencies

Context only. Each item below is a dependency or related item, not work owed by this Mission.

- PR #5890 (`issue-5819-concurrent-mission-writers`) supplies `mission_write_lock`, `mission_write_lock_dir`, `locked_rewrite_text` and the gate this Mission extends.
- See also: #5854 (unserialised runtime commits), #5515 and #5443 (git index collisions), #5389 (run start race).
