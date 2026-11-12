# Mission Specification: Lane worktrees run and verify lane code

**Mission Branch**: `kitty/mission-lane-code-verification-01M76AC0`
**Created**: 2026-11-12
**Status**: Draft
**Input**: Operator brief for sub-epic #7547 (core issue #7554), the research in
`research/code-grounding.md` and `research/foldable-issues.md`, and the operator rulings
recorded as decisions `01M7733YYK1615ERKAY41C2M7C` (gate severity),
`01M7734HC608E8NG5FE016CSP9` (invocation mechanism), `01M7734NZMVP792H8786FN1GB4`
(fold set), `01M7734TCRQ2K3N0RCKVY065WP` (lane packs) and `01M7736Z82HQKQPYB8A40PDVC3`
(intent summary).

## Intent Summary

Agents that implement or review a work package inside a lane worktree today verify the
wrong code. A plain interpreter call, the `spec-kitty` command and any process a test
spawns load the repository root checkout's source through its shared editable install;
only an in-process pytest run that happens to honour the repository's own test
configuration loads the lane. Lanes usually have no environment of their own, the
implement output never tells the agent how to test, and the pre-review gate records
nothing about which tree its evidence came from. So a review can pass against unfixed
code (#7554, seen in more than eight Mission tracers and in the rc7 benchmark register
items C6, 3.3, 6.7 and 7.5).

- **Primary actors:** the implementing agent and the reviewing agent working in a lane
  worktree, and the CLI's pre-review gate acting for them.
- **Trigger:** `spec-kitty implement` (or `spec-kitty agent action implement` /
  `review`) on a work package, then `move-task --to for_review`.
- **Outcome:** implement hands the lane one test invocation, checks that it loads the
  lane's own code, and says so; the prompts carry it; the gate runs the same invocation,
  records which tree its evidence came from, and refuses evidence that came from another
  tree.
- **Rule that always holds:** every gate verdict carries the evidence tree; a run proven
  to load another tree never passes silently. Projects whose code cannot be probed are
  recorded, never refused on provenance grounds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The lane gets a test invocation that provably runs the lane's code (Priority: P1)

An implementing agent runs `spec-kitty implement WP01`. Besides `cd <lane>`, the output
(and its JSON form) gives the test invocation for this lane: the project's declared test
command, the lane as working directory, and the environment to run it in. Implement has
already checked, in a child process started exactly that way, that the code it loads
lives in the lane, and it reports the result.

**Why this priority**: It is the root cause. Without a verified invocation every later
check rests on guesswork, and agents spend dozens of commands rediscovering how to test.

**Independent Test**: Create a lane, plant a change in the lane's copy of a module that
the root checkout does not have, run the reported invocation, and observe the planted
change; then run the root environment's bare interpreter from the lane and observe that
it does not.

**Acceptance Scenarios**:

1. **Given** a Python source-layout project whose shared environment's editable install
   points at the repository root checkout, and a fresh lane with no environment of its
   own, **When** the agent runs `spec-kitty implement WP01`, **Then** the output names
   the lane test invocation and reports it as verified, and a planted change in the lane
   is visible to a child process started with that invocation.
2. **Given** the lane has an environment of its own whose installation of the project
   points outside the lane's source (the #1907 repoint hazard), **When** implement runs,
   **Then** it still prepares the lane but reports the invocation as foreign and names the
   observed origin; after the installation is pointed back at the lane, the same fixture
   reports verified.
3. **Given** a project with no probe-able package (for example a non-Python project),
   **When** implement runs, **Then** it reports the invocation as unverified with the
   reason, and nothing fails.
4. **Given** the agent's shell exports `PYTHONPATH`, `VIRTUAL_ENV` or
   `UV_PROJECT_ENVIRONMENT` pointing at the root checkout, **When** implement builds the
   invocation, **Then** those inherited redirects are not part of it and the probe still
   reports verified.

---

### User Story 2 - Prompts carry the verified invocation forward (Priority: P1)

The implement and review prompts that the CLI generates for a work package include the
lane test invocation and its verification status, so the reviewer runs the same
command in the same tree instead of rediscovering one.

**Why this priority**: The benchmark register shows the same discovery repeated in plan,
every implement session and every review (C6, 6.7, 7.5). Carrying the fact forward is
what removes that repetition.

**Independent Test**: Render the implement and review prompts for a lane-backed work
package and find the invocation and its status in both.

**Acceptance Scenarios**:

1. **Given** a lane-backed work package, **When** `spec-kitty agent action implement`
   renders its prompt, **Then** the prompt contains the lane test invocation and its
   status.
2. **Given** the same work package in review, **When** `spec-kitty agent action review`
   renders its prompt, **Then** the prompt contains the same invocation and status.

---

### User Story 3 - The pre-review gate records and checks the evidence tree (Priority: P1)

When the agent moves a work package to `for_review`, the pre-review gate runs the
project's test command through the same lane invocation, records the evidence tree with
its verdict (lane path, lane commit, whether the tree had uncommitted changes, and the
probe result with the observed origin), and refuses the transition when the probe shows
the run loaded code from another tree.

**Why this priority**: It closes the correctness hole: evidence produced against another
tree must not count as review evidence.

**Independent Test**: Run `move-task --to for_review` twice on one fixture lane: once
with a correct environment (the gate proceeds and records a verified evidence tree), once
with the environment arranged so the run loads the root checkout's code (the gate
refuses with `EVIDENCE_TREE_MISMATCH`).

**Acceptance Scenarios**:

1. **Given** a lane whose invocation verifies, **When** the agent moves the work package
   to `for_review`, **Then** the transition proceeds and the recorded gate evidence names
   the lane path, lane commit, dirty flag and a verified probe.
2. **Given** a lane whose run loads code from another tree, **When** the agent moves the
   work package to `for_review`, **Then** the transition is refused with exit code 1 and
   refusal code `EVIDENCE_TREE_MISMATCH`, whatever the project's
   `review.fail_on_pre_review_regression` setting, and nothing is recorded as applied.
3. **Given** the same refusal, **When** the agent repeats the move with `--force`,
   **Then** the transition proceeds and the recorded gate evidence says the refusal was
   bypassed.
4. **Given** a project whose code cannot be probed, **When** the gate runs, **Then** the
   evidence tree is recorded as unverified with git facts and the transition is never
   refused on provenance grounds.
5. **Given** the gate is skipped with the existing flag or environment variable, **When**
   the agent moves the work package, **Then** the skip behaves exactly as today: no probe
   runs and no evidence tree is recorded (a skipped gate checks nothing, provenance
   included).

### Edge Cases

- The lane already has its own environment: the invocation uses it and adds no source
  override.
- The probe cannot run (interpreter missing, timeout, crash): the result is unverified
  with the cause; implement and the gate proceed as they do today.
- The project declares no test command: implement reports that there is no invocation;
  the gate keeps today's `no_coverage` behaviour.
- A source directory without an `__init__.py` (a namespace or loose module directory) is
  not probed; when no tracked package exists under the source directory the probe is
  unverified.
- A lane environment that installs a copy of the project (not the lane's source) is
  foreign: only an origin inside the lane's source directory counts as verified.
- A test spawns a subprocess: because the invocation is an environment, not an in-process
  setting, the child loads the lane's code too.
- Windows path forms (case, separators, drive letters) and symlinked lane paths compare
  correctly when deciding whether an origin is inside the lane.
- The baseline is captured in another tree on purpose; recording the evidence tree must
  not turn existing baselines into source mismatches.
- A lane checkout without the fetched packs tree in this repository: out of scope; filed
  as a follow-up issue.

## Domain Language

| Term | Meaning | Avoid |
|---|---|---|
| lane test invocation | the declared test command plus the lane as working directory and the environment to run it in | "test command" alone (that is the project config value) |
| evidence tree | the tree a gate run's evidence came from: lane path, commit, dirty flag, probe result and observed origin | "provenance" without saying of what |
| probe result | `verified` (origin inside the lane), `foreign` (origin outside), `unverified` (could not tell) | "pass/fail" |
| repository root checkout | the non-worktree checkout | "main repo", "primary" (overloaded) |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Implement reports the lane test invocation | As an implementing agent, I want `spec-kitty implement` to print and return in JSON the lane test invocation (declared test command, lane working directory, environment) with its probe result, and every later step (the prompts and the gate) to re-derive and re-probe it from the lane rather than trust a stored copy, so that I do not have to rediscover how to test and never act on a stale verdict. | High | Open | [build] | no |
| FR-002 | Invocation is verified by a child-process probe | As an implementing agent, I want implement to check, in a child process started with exactly the invocation's working directory and environment (using the lane's own interpreter when it has one, otherwise the CLI's), where each package tracked under the lane's source directory is loaded from, and to report verified, foreign or unverified with the observed origin, so that I know the command tests the lane. | High | Open | [build] | no — paired with the foreign-origin scenario on the same fixture |
| FR-003 | Lane source takes precedence when the lane has no environment | As an implementing agent in a Python source-layout lane without its own environment, I want the invocation to make the lane's source win over the shared editable install, so that a planted change in the lane is visible to the command and to processes it spawns. | High | Open | [build] | no — the planted change is absent under the bare root interpreter on the same fixture |
| FR-004 | Inherited interpreter redirects are dropped and lane test env applied | As an agent, I want the invocation to drop inherited `PYTHONPATH`, `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT` and to include the lane-scoped test environment (the per-lane test database name), so that my shell cannot silently redirect the run. | High | Open | [build] | no |
| FR-005 | Prompts carry the invocation | As a reviewing agent, I want the implement and review prompts generated by the CLI for a lane-backed work package to state the lane test invocation and its probe result, so that I run the same command in the same tree. | High | Open | [build] | no |
| FR-006 | The gate runs through the same invocation | As the operator, I want the pre-review gate to run the declared test command, and the work-package override scope, through the same lane invocation, so that redirect stripping and the lane test environment apply on every path and the override tier's interpreter fallback can no longer load another tree (#5985 item 2). | High | Open | [build] | no |
| FR-007 | The gate records the evidence tree | As a reviewer, I want every pre-review gate verdict for which the gate built a lane invocation to record the evidence tree (lane path, lane commit, dirty flag, probe result, observed origin), so that I can see which code the evidence is about. | High | Open | [build] | no |
| FR-008 | The gate refuses foreign evidence | As the operator, I want the pre-review gate to refuse the move to `for_review` with exit code 1 and refusal code `EVIDENCE_TREE_MISMATCH` when the probe shows the run loaded code from outside the lane, regardless of `review.fail_on_pre_review_regression`, so that evidence from another tree cannot pass review unnoticed (an explicit skip of the gate, which checks nothing, stays as it is). | High | Open | [build] | no — paired with the verified-lane scenario that proceeds on the same fixture |
| FR-009 | `--force` bypasses the refusal and is recorded | As the operator, I want `--force` to let the transition proceed past `EVIDENCE_TREE_MISMATCH` and the recorded evidence to say so (force bypassed, which refusal, and that no test evidence was produced), even when the regression block is not enabled, so that a probe false positive cannot stall work invisibly. | Medium | Open | [build] | no |
| FR-010 | Unprobe-able projects are recorded, never refused | As a consumer with a non-Python project, I want the invocation and the gate to record an unverified probe with git facts and never refuse on provenance grounds, so that the check does not break projects it cannot judge. | High | Open | [build] | no — paired with FR-008 on a probe-able fixture |
| FR-011 | Existing gate behaviour stays as it is | As the operator, I want existing gate outcomes, their severities, the skip flag and environment variable, and baseline source identity to behave exactly as today, so that this change adds a check without weakening or reshaping the gate. | High | Open | [ratchet] | yes — pinned by the existing gate test suites, which must stay green unchanged |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Probe cost | The probe adds at most 2 seconds to `implement` on a typical project and is bounded by a timeout of at most 15 seconds, after which it reports unverified. | Performance | High | Open |
| NFR-002 | Backward compatibility | Lane workspace contexts persisted before this change load without error; every key that `implement --json` returns today is still returned with the same meaning. | Reliability | High | Open |
| NFR-003 | Code quality | New and changed code passes `ruff check`, `ruff format --check` and `mypy` with zero findings and no new suppressions; no function exceeds complexity 15; diff coverage is at least 90%. | Maintainability | High | Open |
| NFR-004 | Cross-platform origin comparison | Deciding whether an origin is inside the lane is correct for POSIX and Windows path forms, including case-insensitive drives and symlinked lane paths, verified by unit tests for each form. | Portability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No pack edits | Do not edit `packs/built-in` or `packs/internal`; agent-facing wording goes through the core-owned prompt builders. | Technical | High | Open |
| C-002 | One test-command authority | `review.test_command` stays the only project test-command setting; no new configuration key. | Technical | High | Open |
| C-003 | Do not weaken the gate | No existing refusal, outcome or severity is relaxed; no retry-to-green; no new size or ratchet gates. | Technical | High | Open |
| C-004 | ADR amendment for the new refusal | The new refusal is recorded as an amendment to ADR `2026-08-13-6` (gate outcomes carry severity), including the carve-out from the rule that gate evaluation faults never refuse `move-task`: only a proven foreign tree refuses; probe faults stay unverified and proceed. | Governance | High | Open |
| C-005 | Out-of-scope surfaces | Do not change consolidation, the commit router or the decisions subsystem; the orchestrator-api `for_review` transition (which never runs the gate) and lane packs are filed as follow-up issues. | Business | High | Open |
| C-006 | Red first through the CLI | Each behaviour change is preceded by a failing test through the pre-existing entry point (`spec-kitty implement`, `move-task --to for_review`, the prompt renderers), committed before the fix; tidy-first enablers come before the red tests. | Process | High | Open |
| C-007 | Architectural seams | Git facts are read through `kernel.git`; operating-system detection goes through `kernel.paths`; new public names have production callers; the module layer direction is unchanged. | Technical | High | Open |
| C-008 | Baseline identity untouched | Evidence-tree data is kept out of the baseline source identity, so baselines captured in another tree on purpose keep matching. | Technical | High | Open |

### Key Entities

- **Lane test invocation**: working directory, command, environment additions and
  removals, and the probe result. Built once per lane and shared by implement, the
  prompts and the gate.
- **Probe result**: status (`verified`, `foreign`, `unverified`), observed origin(s),
  and a reason when unverified.
- **Evidence tree**: lane path, lane commit, dirty flag and the probe result, recorded
  with each pre-review gate verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fresh lane with a planted change, the reported test invocation observes the planted change in 100% of runs, while the root environment's bare interpreter run from the same lane observes it in 0% — [build] · no-op passable: no
- **SC-002**: A pre-review gate run that loads another tree's code is refused in 100% of attempts without `--force`, and the same fixture with a correct environment proceeds — [build] · no-op passable: no
- **SC-003**: 100% of implement and review prompts generated for lane-backed work packages state the lane test invocation and its probe result — [build] · no-op passable: no
- **SC-004**: Every pre-review gate verdict that ran tests carries an evidence tree with all four facts (path, commit, dirty flag, probe result) — [build] · no-op passable: no
- **SC-005**: The existing pre-review gate, lane, workspace and implement test suites pass unchanged, except the two exact-shape `implement --json` goldens, which each gain only the new `lane_test_invocation` key — [ratchet] · no-op passable: yes (pinned regression suite)

## Tracker

- Closes #7554; closes #7547 when every slice lands.
- Folds #5985 item 2 (Refs #5985; item 1 stays open) and the detection half of #1907
  (Refs #1907).
- Refs #3959, #3123, #3074, #5140, #5071, #6851, #3260, #1224, #5064, #7361, #2624,
  #7336, #2330, #5096, #2803, and the epics #7543, #5103.
- Follow-ups: the orchestrator-api `for_review` transition does not run the pre-review
  gate (owned by #7407, not re-filed); lane worktrees of this repository lack the fetched
  packs tree (#7577).

## Assumptions

- `review.test_command` is the project's test command; when it is unset, there is no
  invocation to report and today's `no_coverage` behaviour stays.
- For Python projects, the packages to probe are the regular packages (with an
  `__init__.py`) the lane tracks directly under its `src/` directory; when none exist, the
  probe is unverified. Workspace member packages outside `src/` are not probed.
- Recorded paths are relative to the repository root checkout where they lie under it,
  so the tracked status log does not carry machine-specific absolute paths needlessly.
- Agents start test runs with the reported invocation; the CLI cannot observe ad-hoc
  runs, so only the gate's own run is checked end to end (agent-reported evidence would
  need a `spec-kitty-events` release and is out of scope).
