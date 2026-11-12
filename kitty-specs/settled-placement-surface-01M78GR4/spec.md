# Mission Specification: One placement surface after topology settlement

**Mission Branch**: `fix/7546-settled-placement-surface` (topology `single_branch`, explicit)
**Created**: 2026-11-12
**Status**: Draft
**Input**: Sub-epic #7546 (part of #7543): after `finalize-tasks` settles a default Mission to
`lanes_with_coord`, every write, commit and remedy resolves its surface through the one placement
seam using the settled topology. Core issues #7551, #7601, #7602; folded #7595 and #7607.
Research: `research/code-grounding.md`, `research/foldable-issues.md`. Rulings: `decisions/`.

## Intent Summary

- **Primary actor**: an operator (or the agent acting for them) working a default Mission — one
  created without `--topology` — that the first `finalize-tasks` settled to `lanes_with_coord`.
- **Trigger**: any governed write after settlement: `spec-commit`, `safe-commit`,
  `agent action implement`, `agent tasks move-task` (including `--note` and the `for_review`
  baseline capture), `accept`, or reading the target banner.
- **Desired outcome**: each write lands on the Mission's branch in the checkout that actually holds
  it (the coordination worktree, after settlement), and every refusal names a surface and a remedy
  the operator can follow — with no raw `git` workaround.
- **Invariant**: one authority answers "which checkout holds this Mission write": the placement
  seam. No second resolver, no write ever reaches a protected target, no refusal code or exit code
  changes.
- **Domain terms**: *repository root checkout*, *coordination worktree*, *topic branch* (the Mission
  branch; after settlement also the coordination branch), *placement seam*, *settlement*. Never
  "main repo"; never bare "routing" or "primary" without its sense
  (here "PRIMARY partition" always means the placement partition, not the primary branch).

## Background (observed on `origin/main` @ 89217ac8, reproduced through the real CLI)

Settlement leaves the repository root checkout on `create_return_branch` and the coordination
worktree `.worktrees/<slug>-coord` on the topic branch; `coordination_branch == mission_branch`.
The Mission's topology is read correctly after settlement. The defects come from call sites that
assume the repository root checkout holds the Mission branch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Commit Mission artifacts after settlement (Priority: P1) — #7551

An operator writes a tracer, a decision record, a spec edit or a work package's
`baseline-tests.json` after settlement and commits it with `spec-commit` or `safe-commit`, from the
coordination worktree or from the repository root checkout.

**Why this priority**: today every per-WP bookkeeping commit needs raw `git` in the coordination
worktree (five Mission tracers report it).

**Independent Test**: build a default Mission with 3 code WPs, run the real `finalize-tasks`
(settles `lanes_with_coord`), then `spec-commit` a tracer, a decision and `baseline-tests.json`
with Mission-relative paths from the coordination worktree; each lands on the coordination branch.

**Acceptance Scenarios**:

1. **Given** a settled Mission and a tracer written in the coordination worktree, **When** the
   operator runs `spec-commit kitty-specs/<slug>/traces/<file>` from the coordination worktree,
   **Then** the commit lands on the topic branch and the coordination worktree is clean for that path.
2. **Given** the same, **When** the operator runs the same command from the repository root
   checkout, **Then** the commit lands on the topic branch.
3. **Given** a decision record and `tasks/<WP>/baseline-tests.json` written in the coordination
   worktree, **When** the operator runs `spec-commit` for them, **Then** both land on the topic branch.
4. **Given** a file that exists only at the repository root checkout path (a stray copy), **When**
   the operator commits it, **Then** the command refuses, copies nothing, and names the coordination
   worktree as the place the file belongs.
5. **Given** a work package moved to `for_review` with a configured test command, **When**
   `baseline-tests.json` is captured, **Then** it is committed on the topic branch (or, if it cannot
   be, a warning names the file and the checkout).

---

### User Story 2 — Start implementation from a protected repository root checkout (Priority: P1) — #7601

An operator whose repository root checkout is on a protected branch (for example `main`) runs
`agent action implement WP01` for a settled Mission.

**Independent Test**: on the same 3-WP fixture with the root on protected `main`, `implement WP01`
exits 0, the claim commit lands on the topic branch and `main` does not move.

**Acceptance Scenarios**:

1. **Given** a settled Mission and a root checkout on protected `main`, **When** the operator runs
   `agent action implement WP01`, **Then** it succeeds, the lane worktree is allocated, the claim
   is committed on the topic branch, and `main`'s tip is unchanged.
2. **Given** the same, **When** the operator runs `agent tasks move-task WP01 --to <lane> --note …`,
   **Then** the WP metadata is committed on the topic branch instead of being refused.
3. **Given** an explicit `--topology lanes_with_coord` Mission whose write target is protected
   `main`, **When** the operator runs `implement`, **Then** it still refuses (no protected write).
4. **Given** any refusal of this preflight, **Then** its remedy names an option or command the
   invoked command actually accepts.

---

### User Story 3 — Read correct targets and paths after settlement (Priority: P2) — #7595, #7602

**Acceptance Scenarios**:

1. **Given** a settled Mission whose `meta.json` exists only in the coordination worktree, **When**
   `implement` or `move-task` prints its branch banner, **Then** it names the Mission's declared
   `target_branch`, never a fallback `main`.
2. **Given** a settled Mission missing an artifact-tagged path-convention deliverable, **When**
   `accept` reports it, **Then** the message names the path relative to the checkout that holds it
   (`kitty-specs/<slug>/…`), not `.worktrees/<slug>-coord/…`.

---

### User Story 4 — Serialized status commits and followable remedies (Priority: P2) — #7607, #7546

**Acceptance Scenarios**:

1. **Given** a settled Mission, **When** a coordination status file is committed through the
   Mission commit path, **Then** the coordination status lock is taken.
2. **Given** a commit refused because the checkout's HEAD is not the Mission branch while another
   worktree holds that branch, **Then** the remedy names that worktree instead of telling the
   operator to check the branch out in the repository root checkout.

### Edge Cases

- The repository root checkout keeps empty, untracked `kitty-specs/<slug>/{checklists,research}`
  leftovers after settlement; their existence must not change which checkout a write resolves to.
- A Mission-relative path given as an absolute path into the coordination worktree keeps working.
- Landed, PUBLISHED or consolidated default Missions (coordination worktree torn down) keep today's
  behaviour.
- Explicit-topology and `single_branch` Missions keep today's behaviour; their checkout is the
  repository root checkout (or the owned checkout).
- A flat Mission whose root HEAD differs from a protected target: still refused; the message may be
  the protected refusal instead of the HEAD-mismatch refusal (accepted ruling).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One checkout authority | As an operator, I want the placement seam to answer which checkout holds a Mission write for every artifact kind (including PRIMARY-partition kinds of an unlanded default Mission) so that no call site keeps its own answer. | High | Open | [build] | no — the seam returns the repository root checkout for a settled Mission's spec today |
| FR-002 | spec-commit after settlement | As an operator, I want `spec-commit` of tracer, decision and baseline paths, given Mission-relative from the coordination worktree or the repository root checkout, to land on the topic branch (#7551). | High | Open | [build] | no — refuses `WRONG_SURFACE` today |
| FR-003 | Refuse, never copy, a stray root copy | As an operator, I want a Mission file that exists only at the repository root checkout path to be refused with a remedy naming the holding worktree, without copying it. | High | Open | [build] | no — paired with FR-002 on the same fixture |
| FR-004 | safe-commit after settlement | As an operator, I want `safe-commit --to-branch <topic>` to commit a settled Mission's files from the coordination worktree, and a refusal from the repository root checkout to name the worktree holding the branch (#7551). | High | Open | [build] | no — remedy names an impossible checkout today |
| FR-005 | Baseline committed after settlement | As an operator, I want the `for_review` baseline capture to commit `baseline-tests.json` on the topic branch after settlement, and to warn naming the file when it cannot. | High | Open | [build] | no — silently left untracked today |
| FR-006 | implement from a protected root | As an operator, I want `agent action implement` on a settled Mission to judge the protected-branch rule against the branch its status commit lands on, so it runs from a root checkout on a protected branch without moving it (#7601). | High | Open | [build] | no — refuses on protected `main` today |
| FR-007 | move-task --note after settlement | As an operator, I want `move-task --note` metadata on a settled Mission judged against the branch it lands on, so it is not refused from a protected root checkout. | High | Open | [build] | no — refuses `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH` today |
| FR-008 | Protected writes still refused | As a maintainer, I want an explicit-topology Mission whose write target is protected to keep being refused by the same preflights. | High | Open | [ratchet] | yes — paired with FR-006 on the same fixture as its positive control |
| FR-009 | Target banner reads the Mission's metadata | As an operator, I want the `implement` / `move-task` branch banner to name the declared `target_branch` when `meta.json` lives only in the coordination worktree (#7595). | Medium | Open | [build] | no — prints `main` today |
| FR-010 | Path-convention message frame | As an operator, I want accept's path-convention message to name artifact paths relative to the checkout that holds them (#7602). | Low | Open | [build] | no — prints `.worktrees/<slug>-coord/…` today |
| FR-011 | Coordination status lock after settlement | As a maintainer, I want the coordination status lock taken whenever a status file is committed in the coordination worktree, whatever the branch names (#7607). | High | Open | [build] | no — the lock is skipped today |
| FR-012 | Followable remedies | As an operator, I want every refusal on these paths to name a surface and a command the invoked command accepts: no "check out the Mission branch" in the repository root checkout while another worktree holds it, no `--no-auto-commit` advice on `agent action implement`. | Medium | Open | [build] | no — both remedies are wrong today |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added latency | A settled-Mission `spec-commit` of one file completes within 2 s on the test fixture (charter CLI budget), and the seam resolves the holding checkout with at most one extra `git` subprocess per command. | Performance | Medium | Open |
| NFR-002 | Quality gates | Every changed file passes `ruff check`, `ruff format --check --force-exclude` and `mypy`; no new suppressions; every touched function stays at cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Coverage | Diff coverage of the change ≥ 90 % (the CI diff-cover gate). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No second resolver | The fix strengthens the one placement seam; call sites delegate to it and keep no private "which checkout" probe. | Technical | High | Open |
| C-002 | Protection unchanged | ProtectionPolicy is not changed and no write reaches a protected target. | Technical | High | Open |
| C-003 | Refusal contract unchanged | No refusal code or exit code changes; only remedy text changes. | Technical | High | Open |
| C-004 | Topology authority unchanged | Settled topology stays read from `meta.json` through the existing locator; no read from `lanes.json`, no cache. | Technical | High | Open |
| C-005 | Gate-clean | No new `mission_runtime → specify_cli` outbound edge; no raw `kitty-specs/<slug>` joins; no commit ref from a current-checkout expression; allow-list entry #2453 is drained, not grown. | Technical | High | Open |
| C-006 | Out of scope | No consolidation recovery/teardown change (sub-epic A2, #7598), no `packs/built-in` edit, no new size or ratchet gate, #7594 not delivered. | Business | High | Open |
| C-007 | Red first | Every behaviour change is reproduced by a failing test through the pre-existing entry point (`spec-commit`, `safe-commit`, `implement`, `move-task`, `accept`) on a fixture that settles to `lanes_with_coord`, committed before the fix. | Technical | High | Open |

### Key Entities

- **Settled default Mission**: a Mission with `topology_source: default` whose first
  `finalize-tasks` settled it; for `lanes_with_coord`, the topic branch is also the coordination
  branch and is held by the coordination worktree until the landing.
- **Holding checkout**: the checkout that has the branch a write resolves to checked out (the
  repository root checkout, an owned checkout, or the coordination worktree).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #7551 regression (default Mission, 3 WPs, `finalize-tasks`, then `spec-commit`
  of a tracer, a decision and `baseline-tests.json`), 3 of 3 artifacts land on the coordination
  branch with zero raw `git` commands. — [build] · no-op passable: no
- **SC-002**: `implement WP01` from a root checkout on protected `main` exits 0 for a settled
  Mission and leaves `main`'s tip unchanged. — [build] · no-op passable: no
- **SC-003**: Every refusal raised on the paths in FR-002..FR-012 names a remedy that, when followed
  verbatim on the fixture, the command accepts (0 impossible remedies). — [build] · no-op passable: no
- **SC-004**: Existing explicit-topology and `single_branch` behaviour unchanged: the targeted
  coordination, mission_runtime, lanes, spec-commit, safe-commit, implement and acceptance test
  suites stay green. — [ratchet] · no-op passable: yes — paired with SC-001/SC-002 on the same fixture

## Assumptions

- The topology locator already returns the settled value (verified live); no topology read changes.
- Issue references: #7551, #7601, #7602, #7595, #7607 are delivered here; #7546 closes when they
  land; #7540 is referenced (its last open item). Context only: parent epic #7543, epics #1878, #1619;
  see #5501 (re-checked, not regressed); later slice #7594.
