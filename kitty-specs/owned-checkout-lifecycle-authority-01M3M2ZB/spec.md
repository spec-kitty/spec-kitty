# Mission Specification: Owned-checkout lifecycle authority

**Mission Branch**: `claude/sleepy-hamilton-5lelee` (planning/base and merge target)
**Created**: 2026-09-28
**Status**: Draft (post-spec squad folded)
**Input**: Issues #3449, #5026, #4252, #4867, #5277. PR #5009 (@samuelgoff) is prior art. Operator-locked decisions and squad evidence are in `research/pre-spec-options-memo.md` and the Decision Moments under `decisions/`.

## Summary

**Bulk edit (DIRECTIVE_035).** This mission renames the owned-mission value object `OwnedMission` to `OwnedCheckout`, and moves it from the CLI application layer into the mission-runtime layer with canonical field names. It also replaces every bare `effective_root: Path` owned-root parameter with the validated fact. Per-category rules are in `occurrence_map.yaml`.

An operator can give a mission its own linked checkout, the **owned checkout**, with `--owned-checkout <path>` (ADR 2026-08-12-1). Mission creation already writes there. Most later lifecycle reads still resolve against the **repository root checkout**, so an owned mission cannot be taken from planning through review. Commands either fail, or report success while acting on repository-root state.

This mission makes the owned checkout the single authority for every lifecycle read of an owned mission:

- Ownership is established once, by one validator, per command.
- The result is handed on as a validated ownership fact.
- It is never re-derived from path shape, and it is never taken from whichever checkout happens to hold a copy of the mission.

### Terms (canonical; see `docs/context/execution.md` and `docs/context/orchestration.md`)

- **Repository root checkout**: the non-worktree checkout of the repository. This spec does not use "primary" or "primary checkout" as generic aliases. In quoted current-behaviour text, "primary" means this checkout.
- **Owned checkout**: a linked checkout that the canonical ownership validator has accepted as owning a given mission for this command. A glossary entry is added by this mission (FR-024).
- **Coordination worktree** / **lane worktree**: as in the glossary. Neither is ever an owned checkout.
- **Validated ownership fact**: the one proof, produced by the canonical validator, that checkout P owns mission M. It records P, the repository root checkout, the mission's stored topology and its target branch.

### Observed on `main` @ `af847be7` (real CLI, 2026-09-28)

| # | Command against an owned mission | Today | Issue |
|---|---|---|---|
| O1 | `agent tasks status --mission <slug\|mid8\|id>` | `MISSION_NOT_FOUND` for every handle; no `--owned-checkout` flag | #3449 |
| O2 | `agent mission setup-plan --mission <handle>` after an owned create and spec commit | `PLAN_CONTEXT_UNRESOLVED`; no flag | #3449, #4252 |
| O3 | `agent context resolve --action implement --wp-id WP01` | `WORK_PACKAGE_UNRESOLVED` naming repository-root paths | #5026 |
| O4 | O3 while the repository root checkout holds a stale copy of the mission | **exit 0**: the WP file comes from the repository root checkout and the workspace is a lane worktree there that doesn't exist | #5277 |
| O5 | `next --owned-checkout … --result success` at tasks→implement | uncaught `ValueError` traceback; the run state is left at `implement` | #5277 |
| O6 | `finalize-tasks --owned-checkout` for an owned checkout under `.worktrees/` | refused as a "coordination worktree" after a partial, uncommitted write (a status event is appended and a WP file is rewritten) | #5277 |
| O7 | `agent mission create --owned-checkout` | charter activation, mission-type context and the spec template are read from the repository root checkout | #5277 |
| O8 | `next --owned-checkout` for a coordination-topology mission | a `commondir` probe failure surfaces as `fatal: … commondir: Success` | #4867 |
| O9 | `next --owned-checkout` | validates only the ownership *claim*. It skips the canonical validator's branch and protection checks that every other owned command applies | #5277 |
| O10 | flagless `context resolve` from inside a linked checkout | adopts the current directory without the canonical validator | #5026 |

### Topology rule (decision `01M3M4GMJVYEGW80YJEA7CNWGF`)

The validator records the mission's stored topology in the validated fact. **Each command enforces its own allowed topologies:**

- `next` keeps accepting every topology it accepts today: `single_branch`, `lanes`, `coord` and `lanes_with_coord` (`NEXT_OWNED_TOPOLOGIES`), preserving current behaviour rather than newly narrowing it, as ADR 2026-08-12-1 allows today.
- The lifecycle commands of ADR 2026-09-03-1 (`agent tasks status`, `setup-plan`, `context resolve`, `finalize-tasks`, `move-task`, `mark-status`, `spec-commit`, `accept`) remain single_branch-only. Other topologies are refused with `OWNED_TOPOLOGY_UNSUPPORTED`.

## User Scenarios & Testing *(mandatory)*

The actor is an **operator or agent harness** that created mission M with `--owned-checkout P` in linked checkout P. The repository root checkout R may be on another branch or running another mission.

**Common fixture.** R is created with `spec-kitty init`, and P is a linked worktree of R. Handles are parametrised over slug, mid8 and mission id. "R unchanged" is defined by NFR-001, which is the single authority for what the **R snapshot** covers (working tree including ignored files and excluding exactly P's resolved subtree, `HEAD`, index, the shared lock root, and an isolated `SPEC_KITTY_HOME` minus the P-keyed prompt cache); this paragraph does not restate a narrower definition.

### User Story 1 - Plan an owned mission (Priority: P1)

After an owned create and a substantive spec commit, the operator checks status and sets up the plan, entirely in P.

**Why this priority**: an owned mission cannot pass specify today (#3449, #4252).

**Independent Test**: owned create, then spec commit, then `agent tasks status --owned-checkout P`, then `setup-plan --owned-checkout P`, with an R snapshot around each command.

**Acceptance Scenarios**:

1. **Given** M committed in P with WPs WP01–WP02 finalized, and R holding a stale copy of M whose WP set is WP01–WP05, **When** `agent tasks status --owned-checkout P --mission H` runs, **Then**:
   - it exits 0;
   - it lists exactly WP01–WP02;
   - its JSON carries the stale-copy warning field;
   - R is unchanged.
2. **Given** M with a substantive committed spec in P, **When** `agent mission setup-plan --owned-checkout P --mission H` runs, **Then** `plan.md` is created and committed on P's branch, and R is unchanged.
3. **Given** each invalid `--owned-checkout` value, **When** each of `agent tasks status`, `setup-plan` or `context resolve` runs with it, **Then** it exits non-zero with the listed code and writes nothing to P or R. The invalid values and codes are:
   - a missing path (`OWNERSHIP_BROKEN_POINTER`);
   - a plain directory inside a checkout, e.g. `R/docs` (`OWNERSHIP_NESTED`);
   - a directory outside any repository (`OWNERSHIP_BROKEN_POINTER`, the same code as a missing path);
   - R itself (`OWNED_CHECKOUT_IS_REPOSITORY_ROOT`);
   - a lane or coordination worktree (`OWNED_CHECKOUT_IS_MISSION_WORKTREE`);
   - a mismatched or detached branch (`OWNED_BRANCH_REFUSED`);
   - a protected target (`OWNED_BRANCH_REFUSED`);
   - a non-single_branch mission (`OWNED_TOPOLOGY_UNSUPPORTED`).

   Each case is paired with the valid P on the same fixture.

---

### User Story 2 - Resolve work-package context in an owned mission (Priority: P1)

**Why this priority**: implement and review prompts depend on WP context (#5026). O4 fails open.

**Independent Test**: after finalize in P, run `agent context resolve --owned-checkout P --action implement --wp-id WP01`, with and without a stale copy of M in R.

**Acceptance Scenarios**:

1. **Given** finalized tasks in P, **When** WP-level context is resolved with `--owned-checkout P`, **Then**:
   - `wp_file` and `workspace_path` are under P;
   - `resolution_kind` is `owned_checkout`;
   - `lane_id` is null.
2. **Given** WP09, which is absent from P but present in R's stale copy, **When** it is resolved, **Then** the result is `WORK_PACKAGE_UNRESOLVED` naming P's mission directory, and no path in the result is under R.
3. **Given** R holds a stale copy of M, **When** WP01 is resolved, **Then**:
   - every returned path is under P;
   - the JSON warning field `stale_repository_root_copy` names R's copy;
   - the same warning text is printed on stderr in human mode.

---

### User Story 3 - Drive an owned mission through implement and review with `next` (Priority: P1)

The supported owned path (decision `01M3M4GZHZVB3A248J266Y9WMX`) works like this:
- `next --owned-checkout P` issues the implement and review prompts, with the workspace set to P;
- lane transitions go through `agent tasks move-task --owned-checkout P`.

**Why this priority**: `next` is the canonical control loop. Today it crashes at tasks→implement (O5) and follows R's routing when R holds a stale copy.

**Independent Test**: from finalized tasks, run `next --result success`, then `move-task` WP01 through `claimed` and `in_progress` to `for_review`, then `next` again for the review prompt. Repeat with a stale copy of M in R. Take the R snapshot throughout.

**Acceptance Scenarios**:

1. **Given** finalized tasks in P, **When** `next --owned-checkout P --result success` runs, **Then** it returns `kind=step`, `action=implement`, `wp_id=WP01`, with the prompt's workspace equal to P. A following `next --owned-checkout P` query does **not** return the same unadvanced decision.
2. **Given** P's composition policy differs from R's (the fixture sets a distinguishing policy value in P), **When** `next` dispatches composition, **Then** P's policy value is observed in the dispatched step.
3. **Given** R holds a stale copy of M with a different lane map, **When** `next` resolves the task board for M, **Then** the workspace is P, never a lane worktree under R, and the stale-copy warning field is present.
4. **Given** WP01 was moved to `for_review` with `move-task --owned-checkout P`, and a sibling WP02 commit exists in P, **When** `next --owned-checkout P` builds WP01's review prompt, **Then**:
   - the review base is WP01's **claim commit**, defined below;
   - the review diff is the diff from the claim commit to `HEAD`, restricted to WP01's declared owned files;
   - the diff excludes WP02's files.
5. **Given** WP01 declares no owned files, **or** no claim commit is recorded for it, **When** its review prompt is built, **Then** `next` returns a `blocked` decision with the code `OWNED_REVIEW_BASE_UNAVAILABLE` and never emits an unscoped whole-checkout diff.
6. **Given** the `next --owned-checkout` call of AS-1, **When** the repository root checkout's current branch is changed between the ownership validation and the prompt build (simulated by a test hook), **Then** all reads use the validated fact from the start of the command and do not re-derive ownership.

**Claim commit** (definition): the commit on P's branch that recorded the WP's transition to `claimed`, identified by the commit hash that the status event log records for that transition. It is never identified by matching commit subjects.

---

### User Story 4 - Finalize tasks atomically in any owned location (Priority: P2)

**Why this priority**: owned checkouts under `.worktrees/` are common. A half-applied refusal corrupts the authoritative status log (O6).

**Independent Test**:
- place P at `R/.worktrees/<name>` and finalize;
- separately, place a coordination worktree at the same kind of path and read it as the repository root checkout;
- separately, force a finalize refusal after the first write step.

**Acceptance Scenarios**:

1. **Given** a valid owned single_branch P at `R/.worktrees/owned-a`, **When** `finalize-tasks --owned-checkout P` runs, **Then** it exits 0 and the new events are appended to P's status log.
2. **Given** the same `.worktrees/<name>` path shape registered as a real coordination worktree, **When** a read that claims the repository root checkout targets it, **Then** the existing refusal still fires.
3. **Given** a finalize that is refused for a reason other than location, **When** it returns, **Then** `git status --porcelain --ignored` in P is identical to before (no modified WP files, no new events file, no new `.kittify/derived/` content). The refusal originally chosen was a **lane dependency cycle** (plan research R-07). Since origin/main's #5100 an owned single_branch mission has exactly one repo-root `lane-planning` lane, so no lane cycle can be refused inside an owned checkout; the former lane-cycle fixture now finalizes to that single lane (the single-lane finalize test proves the guarantee), and the post-write refusals exercised are the stale-canceled, planning-pin-orphan and issue-matrix refusals. Dependency-graph cycles and invalid WP references are not used, because they are already refused before any write on the planning base. The same-fixture control is a successful finalize, which does append events and rewrite WP files.

---

### User Story 5 - Governance reads at creation follow the owned checkout (Priority: P2)

Mission creation with `--owned-checkout P` reads charter activation, mission-type context and the spec template from P, consistent with `next`. Charter authoring stays repository-root only.

**Acceptance Scenarios**:

1. **Given** P activates the mission type and R does not, **When** owned create runs, **Then** it succeeds.
2. **Given** P does not activate the mission type and R does, **When** owned create runs, **Then** it refuses with the existing inactive-charter error.
3. **Given** P's spec template carries the marker `OWNED-TEMPLATE-MARKER` and R's does not, **When** owned create runs, **Then** the scaffolded `spec.md` contains the marker.
4. **Given** any charter-authoring command is run against P, **Then** the existing repository-root-only authoring refusal (#4785) still applies.

The boundary with #4250: invoking `charter context` or charter authoring from P is #4250's scope and is not changed here.

---

### User Story 6 - Clear refusals where owned missions are not supported (Priority: P3)

**Acceptance Scenarios**:

1. **Given** `agent action implement WP01 --owned-checkout P` or `agent action review WP01 --owned-checkout P`, **When** it runs, **Then**:
   - it exits non-zero with `OWNED_ACTION_UNSUPPORTED`;
   - the guidance names `spec-kitty next --owned-checkout P` and `spec-kitty agent tasks move-task --owned-checkout P`;
   - no worktree or branch is created;
   - nothing is written to P or R.

---

### User Story 7 - Flagless commands inside an owned checkout (Priority: P2)

Decision `01M3M4GTA4ENB73A0HDS65WZ1P`: a flagless command run from **inside a linked checkout** adopts that checkout, but **only if the canonical validator accepts it**.

**Acceptance Scenarios**:

1. **Given** the working directory is inside a valid owned P for M, **When** flagless `agent context resolve --action tasks_outline --mission H` runs, **Then** it resolves from P exactly as with `--owned-checkout P`.
2. **Given** the working directory is inside a lane worktree or a coordination worktree, **When** a flagless command runs, **Then** its behaviour is unchanged from today. There is no adoption. This case is pinned by the existing lane and coordination tests.
3. **Given** the working directory is inside a linked checkout the validator rejects, for example a mismatched branch, **When** a flagless command runs, **Then** it does **not** adopt the checkout and resolves from the repository root checkout as today.
4. **Given** the working directory is the repository root checkout, **When** any flagless command runs, **Then** its behaviour is unchanged.
5. **Given** the working directory is inside a valid owned P, and the same selector resolves to a **different** mission id in P than in R, **When** a flagless command runs, **Then** it refuses with the existing mission-surface-conflict error. This preserves today's behaviour; the stale-copy warning applies only when the mission ids are the same.

### Edge Cases

- **Stale copy.** The same handle resolves in both P and R. P wins and the stale-copy warning is emitted (decision `01M3M2ZXH4CGY20X1PZEC18F54`).
- **Path aliases.** A symlinked or case-variant path for P is passed. Identity is decided on the canonical path.
- **Same slug in two owned checkouts.** Lookups and caches are isolated per checkout.
- **Adoption guard.** A flagless command is run inside a lane or coordination worktree. It is never adopted as owned (US7-AS2).
- **Coordination-topology owned `next`.** The coordination-workspace probe fails deterministically (a zero-byte `commondir`). `next` reports `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` and never a `commondir: Success` fatal.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One ownership validator | As a maintainer, I want the canonical owned-mission validator to be the only code that turns an ownership claim into a validated ownership fact, so that ownership has one authority. An architectural check fails if the ownership-claim primitive is called anywhere else outside that validator, and if any parameter or field anywhere in `src/` carries an owned root as a bare path. Named rule-based exemptions are defined in `contracts/architectural-gate.md` (the `OwnedCheckout` carrier's own fields, the CLI claim-input alias, the org-pack module sense of `effective_root`, and historical migrations); there is no site-level allowlist. The allowlist is empty (operator decision `01M3M65D…`: all bare owned-root parameters are converted in this mission — census in plan Scale/Scope — with no ratchet ledger). | High | Open | [build] | no — red on main: `next` calls the claim primitive directly (O9), and context resolution adopts cwd (O10) |
| FR-002 | `next` uses the validator | As an operator, I want `next --owned-checkout` to go through the canonical validator, including its branch and protection checks, so that it enforces the same ownership rules as every other owned command. | High | Open | [build] | no — red on main: `next --owned-checkout` with a protected target is accepted today |
| FR-003 | Validated once per command | As an operator, I want ownership validated exactly once per owned command invocation and the fact handed to every downstream read, so that reads are consistent and cheap (NFR-002). | High | Open | [build] | no — the check asserts exactly 1 validation through the CLI; 0 or ≥2 fails |
| FR-004 | Owned status listing | As an operator, I want `agent tasks status --owned-checkout` to list the owned mission's WPs by any handle (US1-AS1, #3449). | High | Open | [build] | no — red on main (MISSION_NOT_FOUND) |
| FR-005 | Owned plan setup | As an operator, I want `setup-plan --owned-checkout` to create and commit the plan in P (US1-AS2, #4252). | High | Open | [build] | no — red on main (PLAN_CONTEXT_UNRESOLVED) |
| FR-006 | Owned WP context | As an operator, I want `agent context resolve --owned-checkout` to resolve the WP file, workspace and metadata from P, returning `WORK_PACKAGE_UNRESOLVED` scoped to P when the WP is absent (US2-AS1/AS2, #5026). | High | Open | [build] | no — red on main (WORK_PACKAGE_UNRESOLVED naming R) |
| FR-007 | Stale copy never wins | As an operator, I want every owned read to resolve from P even when R holds a copy of M, with the warning field `stale_repository_root_copy` in JSON and on stderr. The owned reads are: `agent tasks status`, `setup-plan`, `context resolve`, `next` (including the task board) and `finalize-tasks` (US1-AS1, US2-AS3, US3-AS3). | High | Open | [build] | no — red on main (O4 exits 0 with R paths) |
| FR-008 | `next` crosses tasks→implement | As an operator, I want `next --owned-checkout --result success` on finalized tasks to return an implement step for WP01 with workspace P, and to advance, not wedge, the run (US3-AS1). | High | Open | [build] | no — red on main (traceback); wrapping the error into `blocked` fails the row |
| FR-009 | Owned runtime reads | As an operator, I want `next` to read from P for: composition policy, task-board resolution, WP action and prompt building, prompt governance, and the working directory of git history lookups (US3-AS2/AS3). | High | Open | [build] | no — red on main (R's policy and R lane routing are observed) |
| FR-010 | Owned review base | As a reviewer, I want an owned WP's review prompt to use the claim commit (US3 definition) and a diff restricted to the WP's owned files, and to return `blocked` with `OWNED_REVIEW_BASE_UNAVAILABLE` when there are no owned files or no claim commit (US3-AS4/AS5). | Medium | Open | [build] | no — sibling-WP exclusion and the fail-closed path are each asserted |
| FR-011 | Owned-workspace kind | As an operator, I want owned workspace resolution to report `resolution_kind=owned_checkout` with a null lane, and the checkout-identity guard to refuse a fact whose checkout mismatches the invoking checkout (US2-AS1). This is a workspace-resolution kind only; status-source classification is unchanged (C-002). | Medium | Open | [build] | no — a lane-mission positive control and a mismatched-fact negative are both asserted |
| FR-012 | Coordination probe hardening | As an operator, I want owned coordination-topology `next` to handle a failing coordination-workspace probe with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` in its JSON `error_code`, never an uncaught `commondir` fatal (#4867). The existing transient-lock retry stays. The red-first test uses two deterministic injections: a zero-byte `commondir` in a registered worktree's gitdir, with a test pre-assertion that `git worktree list --porcelain` really exits non-zero (the test fails loudly, never skips); and a fault at the subprocess seam used by the stale-registration probe. Assertions are on `error_code`, never on git's stderr wording. | Medium | Open | [build] | no — red on main via both injections |
| FR-013 | Owned status source under `.worktrees/` | As an operator, I want status reads for a validated owned single_branch P under `.worktrees/` to be accepted, with the decision taken by the canonical coordination surface resolver from the validated fact and the registered-worktree facts, not from path shape (US4-AS1). | High | Open | [build] | no — red on main ("…must not target coordination worktree paths") |
| FR-014 | Coordination protections unchanged | As a maintainer, I want a repository-root-labelled read of the **same** `.worktrees/<name>` path to still be refused when that path is a registered coordination worktree (US4-AS2). | High | Open | [ratchet] | yes — paired with FR-013 on the same path |
| FR-015 | Atomic finalize | As an operator, I want `finalize-tasks` to validate everything before its first write, so that a post-write refusal leaves `git status --porcelain --ignored` in P exactly as before (US4-AS3). The oracle is the porcelain status including ignored files, not the event log, which may not exist yet. **Amended after origin/main's #5100:** an owned lifecycle mission is `single_branch`, whose manifest is exactly one repo-root `lane-planning` lane (Invariant T-1), so the lane-dependency-cycle refusal is unreachable inside an owned checkout. The atomic-finalize guarantee is now proven by the single-lane finalize test (`test_cyclic_lane_fixture_finalizes_to_the_single_repo_root_lane_inside_owned_checkout_and_r_is_unchanged`: the former cyclic fixture finalizes in P to the one repo-root lane with R unchanged), while the stale-canceled, planning-pin-orphan and issue-matrix rows keep the post-write-refusal coverage. | High | Open | [build] | no — red on main via the lane-cycle refusal (WP files and `.kittify/derived/` are modified today); control: a successful finalize writes |
| FR-016 | Governance reads at owned create | As an operator, I want owned create to read charter activation, mission-type context and the spec template from P (US5-AS1..AS3). | Medium | Open | [build] | no — red on main in all three directions |
| FR-017 | Charter authoring stays at root | As a maintainer, I want charter authoring against P to stay refused (US5-AS4, #4785). | High | Open | [ratchet] | yes — paired with FR-016 on the same fixture |
| FR-018 | Typed refusal for unsupported actions | As an operator, I want `agent action implement` and `agent action review` to accept `--owned-checkout` only to refuse with `OWNED_ACTION_UNSUPPORTED` and guidance naming `next --owned-checkout` and `move-task --owned-checkout`, writing nothing (US6). | Low | Open | [build] | no — the flag does not exist on main |
| FR-019 | Per-checkout lookup isolation | As an operator, I want WP metadata lookups keyed by the checkout they read from. In one `next` process, resolving the same mission slug in R and then in P must return each checkout's own WP set. | Medium | Open | [build] | no — a two-checkout same-slug fixture inside one process; red on main |
| FR-020 | Invalid owned path refused | As an operator, I want the new `--owned-checkout` flags (on `agent tasks status`, `setup-plan`, `context resolve`, `agent action implement` and `agent action review`) to refuse each invalid value listed in US1-AS3 with its code and no writes. | High | Open | [build] | no — each invalid case is paired with the valid-P control |
| FR-021 | Validated flagless adoption | As an operator, I want a flagless command run inside a linked checkout to adopt it only when the canonical validator accepts it. The repository root checkout, lane worktrees, coordination worktrees and rejected checkouts keep today's behaviour (US7). | High | Open | [build] | no — red on main: adoption happens without validation (O10); lane and coordination controls must not change |
| FR-022 | Existing owned commands unchanged | As a maintainer, I want the existing owned-checkout tests for `move-task`, `mark-status`, `spec-commit`, `accept`, finalize outside `.worktrees/`, and coordination-topology owned `next` to pass unchanged after rewiring onto the single validator. Because the only coordination-topology owned `next` coverage today is a nightly-only e2e test, a per-PR in-process twin is added: owned `lanes_with_coord` create followed by `next`. | High | Open | [ratchet] | yes — this is the regression guard for the rewire |
| FR-023 | Topology per command | As an operator, I want the validated fact to carry the mission's stored topology, and each command to enforce its allowed set. `next` allows coordination topologies. The ADR 2026-09-03-1 lifecycle commands allow single_branch only and refuse others with `OWNED_TOPOLOGY_UNSUPPORTED`. | High | Open | [build] | no — paired: a coordination-topology mission is accepted by `next` and refused by `agent tasks status` |
| FR-024 | Glossary and ADRs | As a maintainer, I want an "owned checkout" glossary entry (with "Do NOT use when"), ADR 2026-09-03-1 amended for the validated-fact design and per-command topology, and ADR 2026-08-12-1 amended for validated flagless adoption. | Medium | Open | [build] | no — the docs freshness and terminology gates run on the new text |
| FR-025 | Unified review base | As a reviewer, I want every WP review prompt, for owned and repository-root missions alike, to find the WP's claim commit through one helper (claim event id, then the unique commit that introduced it) and to fail closed when it is ambiguous or missing. The three duplicate commit-subject matchers are deleted (decision `01M3M70Y…`). | Medium | Open | [build] | no — red on main: a non-owned finalized mission's review prompt reports the base as unavailable today |
| FR-026 | Complexity ceiling restored on touched files | As a maintainer, I want `accept` and `_create_mission_core_impl` decomposed, behaviour-preserving, to complexity ≤ 15 with focused tests, and the per-file C901 suppressions for `cli/commands/accept.py` and `core/mission_creation.py` removed (decision `01M3M718…`). | Medium | Open | [build] | no — red on main: ruff C901 fails with the suppressions removed |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Repository root checkout untouched | In every owned acceptance scenario, the R snapshot shows 0 differences. The snapshot covers: R's working tree including ignored files, **excluding exactly P's resolved subtree** when P lives under R (never a blanket `.worktrees/` exclusion, so R's own lane and coordination worktrees are still covered); R's `HEAD` and index; the shared lock root `<common-dir>/spec-kitty-locks`, with exactly one named tolerance: the pre-existing per-mission status mutex (`status/locking.py::feature_status_lock_path`) may appear as a single **empty** `<mission>.status.lock` file, because the git common dir is shared by P and R by construction (no other added, changed or removed lock key, and no holder sidecar, is tolerated; the tolerance is defined once in `tests/_owned_fixtures.py`); and an isolated `SPEC_KITTY_HOME`, with exactly one named tolerance: owned `next` may add prompt files under `SPEC_KITTY_HOME/spec-kitty-prompts/<key derived from P>` (the per-checkout prompt cache that `next` writes by design); nothing else under `SPEC_KITTY_HOME` may be added, changed or removed, and this tolerance is also defined once in `tests/_owned_fixtures.py` (operator ruling 2026-09-30). Scenarios are parametrised over cwd = R, P and an unrelated directory. | Reliability | High | Open |
| NFR-002 | Validation count | Exactly 1 ownership validation per owned command invocation, and 0 additional per-read git subprocess calls for owned status reads compared with the non-owned path. Both are measured by counting calls in an integration test through the CLI entry point. | Performance | Medium | Open |
| NFR-003 | Command latency | On the acceptance fixture, the median of 5 runs of owned `agent tasks status`, `setup-plan` and `context resolve` is < 2 s each (charter budget), measured by a `performance`-marked test in the nightly CI run. Per-PR, NFR-002's subprocess-count assertion is the proxy. | Performance | Medium | Open |
| NFR-004 | Typed errors | Every owned refusal introduced or touched here returns a code from one registered set, **data-model.md's "Error code registry" (the single authority)**: the existing claim-primitive codes (`WORKTREE_INVOCATION_REFUSED`, `OWNERSHIP_NESTED`, `OWNERSHIP_FOREIGN`, `OWNERSHIP_BROKEN_POINTER`), the existing minter/workspace codes (`OWNED_MISSION_PATH_REFUSED`, `OWNED_TOPOLOGY_UNSUPPORTED`, `OWNED_BRANCH_REFUSED`, `OWNED_INDEX_REFUSED`, `WORK_PACKAGE_UNRESOLVED`), and the codes new to this mission (`OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, `OWNED_CHECKOUT_IS_MISSION_WORKTREE`, `OWNED_ACTION_UNSUPPORTED`, `OWNED_REVIEW_BASE_UNAVAILABLE`, `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`), plus the other pre-existing wire codes the registry lists (`WORKTREE_REGISTRY_UNAVAILABLE`, `FEATURE_CONTEXT_UNRESOLVED`, `MISSION_CONTEXT_CONFLICT`, `OWNED_OPTION_UNSUPPORTED`, `OWNED_INPUT_INVALID`), in `--json` output. **Carve-out for commands with no `--json` option** (`agent action implement` / `review`, FR-018): the code appears in the human refusal line as `Error: [<CODE>] …` on stderr with a non-zero exit, in place of `--json` output. 0 surface as an uncaught exception, asserted per refusal scenario. | Reliability | High | Open |
| NFR-005 | Quality gates | New and changed code: ruff check and format clean, mypy 0 new findings, complexity ≤ 15, diff coverage ≥ 90% (CI gate). | Maintainability | High | Open |
| NFR-006 | Cross-platform identity | Owned-checkout identity is correct for one explicit symlink case (`link → real`, constructed by the test) and one case-variant path case. The case-variant test runs on the Windows CI workflow, and its file is added to `ci-windows.yml`'s path filter. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Ownership authority | The only producer of the validated ownership fact is the canonical owned-mission validator (`resolve_owned_mission`, ADR 2026-09-03-1), built on the ownership-claim primitive (`resolve_ownership_claim`, ADR 2026-08-12-1). Flagless adoption (FR-021) also goes through it. | Technical | High | Open |
| C-002 | One status-source authority | Status-source classification stays with the canonical coordination surface resolver (#4959). No parallel status-read source or label is added. | Technical | High | Open |
| C-003 | Layer rules | The validated fact is defined where the runtime and mission-runtime layers can consume it without new outbound edges into the CLI application layer. The shrink-only ledgers must not grow. | Technical | High | Open |
| C-004 | Scope boundary | Out of scope: charter context/authoring from P and hosted binding (#4250); single_branch lane allocation in `implement` (#5100); one-writer-per-checkout (#5099); create-from-worktree ergonomics (#3443); `mid8: null` after create (#3474, already fixed). | Business | High | Open |
| C-005 | ADR amendments | ADR 2026-09-03-1 and ADR 2026-08-12-1 are amended, plus a short note on ADR 2026-06-07-1 if a new public mission-runtime symbol is added. They land with this mission. | Technical | High | Open |
| C-006 | Prior-art provenance | Reusable commits from PR #5009 are carried with `cherry-pick -x`, keeping @samuelgoff's authorship. Re-expressed fixes credit him with `Co-authored-by`. #5009's session-log docs are not carried. | Business | Medium | Open |
| C-007 | Red-first | Every `[build]` FR has a reproduction through its pre-existing entry point, red on the planning base before the fix. Races are reproduced by deterministic fault injection. | Technical | High | Open |
| C-008 | Terminology | Use "Mission", "repository root checkout", "owned checkout", "coordination worktree" and "lane worktree". Do not use bare "primary" as a checkout alias, and do not use `feature` aliases. | Business | Medium | Open |

### Key Entities

- **Owned checkout (P)**: a linked checkout accepted by the canonical validator as owning mission M.
- **Validated ownership fact**: records P, the repository root checkout R, M's stored topology and M's target branch. It is produced once per command by the one validator and consumed by all owned reads. R is used only for repository-root-only concerns such as charter authoring.
- **Stale repository-root copy**: a copy of M's artifacts in R. It is never authoritative for owned reads.
- **Claim commit**: the commit on P's branch recorded by the status log for a WP's transition to `claimed`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Using only documented `--owned-checkout` commands, an operator takes an owned mission through create, spec, plan, tasks, finalize, the implement step for WP01, `move-task` to `for_review`, and WP01's review prompt. There are 0 errors and 0 R-snapshot differences. — [build] · no-op passable: no
- **SC-002**: All 10 observed defects (O1–O10) have a reproduction that fails on the planning base and passes at mission end. — [build] · no-op passable: no
- **SC-003**: With a stale copy of M in R, each of the 5 owned reads listed in FR-007 returns 0 paths under R and carries the stale-copy warning field. — [build] · no-op passable: no
- **SC-004**: The single-validator architectural check (FR-001) is red on the planning base and green at mission end. — [build] · no-op passable: no
- **SC-005**: The existing owned-command, lane-topology, coordination-topology and charter-authoring test files pass unchanged (FR-014, FR-017, FR-022). — [ratchet] · no-op passable: yes

## Assumptions

- `next` handle resolution, and owned finalize outside `.worktrees/`, already work on `main`. They are covered by FR-022 as regression guards.
- The existing frozen owned-mission value produced by `resolve_owned_mission` is the natural seed of the validated ownership fact. Where it lives, and its exact shape, are decided in plan (C-003).
- #5009's regression tests are adapted to the real command call shape before being carried.
- The claim commit's hash can be derived from the status log, either from the event itself or from the commit that `move-task` makes in P. Plan must verify this. If neither holds, plan records the commit identity at claim time as part of FR-010, still without matching commit subjects.

## Dependencies

- #4959 (merged): the canonical coordination surface resolver extended by FR-013.
- #4980 (merged): the coordination-aware task-board authority extended by FR-009.
- #5259 (merged): canonical WP task placement in prompt building, on which FR-009 and FR-010 build.
- #4785 / PR #4790 (merged): the repository-root-only charter authoring guard kept by FR-017.
