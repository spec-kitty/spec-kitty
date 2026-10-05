# Mission Specification: Implement command degod (tidy-first)

**Mission Branch**: `issue-5635-implement-degod`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief (semi-automatic): deliver #5635 and #5232 as one tidy-first,
behaviour-preserving decomposition of the implement command. Remove the meta-derived
coordination fallback, move the tests onto the seams, and deliver as one PR on
spec-kitty/spec-kitty (milestone "4.0.0 release scope").

## Intent Summary (confirmed)

- **Primary actors:**
  - Spec Kitty maintainers who land the remaining milestone-11 fixes in the implement area,
    such as #5673, #5676 and #5669.
  - Operators and agents who run `spec-kitty implement WP##`, directly or through
    `spec-kitty agent action implement`.
- **Trigger:** the implement command file is a hotspot.
  - 2,304 lines; 53 commits in 90 days, 18 of them fixes.
  - 112 test patch sites reach into its internals.
  - Every fix in this area is costly to make and hard to pin with a test.
- **Desired outcome:** a thin command layer that only parses arguments and presents output,
  over an ordered sequence of implement phases.
  - Each phase's decisions live in the existing domain seams (workspace context, lanes,
    coordination, status, dependency graph), where a test can pin them without patching the
    command module.
  - The tests follow the code onto those seams.
- **Rule that must always hold:** an operator sees exactly the same behaviour before and after.
  - Same refusals, error codes, exit codes and console/JSON output, and the same commits and
    state files.
  - The one exception is #5232: the legacy meta-derived coordination fallback is replaced by a
    seam-owned placement resolution (see FR-008).
- **Discovery mode:** brief intake.
  - The operator's brief is comprehensive and asks for autonomous execution, stopping only on
    charter conflicts, real behaviour-change decisions, or a gate that cannot be kept green
    honestly.
  - The one design decision with behaviour impact (#5232 shape) is recorded as Decision Moment
    `01M4455PBFDASHQ7R9DN5ZQRMW`.
  - Grounding evidence is in [`research/code-grounding.md`](research/code-grounding.md) and
    [`research/test-remediation.md`](research/test-remediation.md). Every requirement below
    traces to a decision (D1–D10) in `code-grounding.md` §2.

## Domain Language

| Term | Meaning here | Do not confuse with |
|---|---|---|
| **implement phase** | One ordered step of `spec-kitty implement`: context, claim preflight and dependency gate, planning-artifact commit, bulk-edit gate and operational context, workspace/lane selection, allocate, record claim, present. | "Auto-rebase". It is **not** on this path (it lives in lane lifecycle sync and consolidation) and is out of scope. |
| **seam** | An existing package module that owns a domain decision: `workspace/context.py`, `lanes/implement_support.py`, `coordination/`, the status facade, `core/dependency_graph.py`. | A new package. None is introduced. |
| **legacy meta-derived fallback** (#5232) | The implement-local branch that derives the coordination branch from `meta.json` when the context placement ref fails to resolve. The implement code calls it the "C-004 strangler". | ADR `2026-06-24-1`'s C-004 ("the coordination-worktree mechanism stays"), and this spec's own constraint IDs. |
| **placement ref** | The single commit target that planning artifacts and status events resolve to (C-PLACE-1). | A branch name read directly from `meta.json`. |
| **patch site** | A test `patch`/`monkeypatch` that replaces a name in a module's namespace. | Patches of shared objects (`console.print`). |
| **routing** | Not used unqualified. Here it only ever means *placement* (which branch a planning artifact commits to). | Dispatch, model or event routing. |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer pins a fix in one phase without patching the command module (Priority: P1)

A maintainer picks up a milestone-11 bug in the implement area. #5673 is the example: the claim
commit sweeps the operator's uncommitted `.kittify/config.yaml`. They find the decision in its
seam module, change it there, and pin it with a seam unit test that needs neither the CLI nor a
dozen patches on the command module.

**Why this priority**: this is the reason for the mission. Later fixes in this area become
cheap to make and to pin.

**Independent Test**: for each phase, at least one seam unit test calls the phase's decision
directly with plain inputs and asserts its verdict or typed error, with no patch on the
implement command module.

**Acceptance Scenarios**:

1. **Given** the claim-commit path bundle, **When** a test calls the seam function with a
   feature dir, a WP file and a topology flag, **Then** it gets the exact list of paths the claim
   commit would stage, without running git or the CLI.
2. **Given** a reduced status snapshot in which a dependency is `planned`, **When** a test calls
   the dependency-gate decision, **Then** it raises the same `dependencies_not_satisfied: …`
   error the command raises today, with no git repository involved.
3. **Given** a list of dirty planning paths, **When** a test calls the planning-commit partition
   decision, **Then** it gets the same PRIMARY and coordination-residue groups the command commits
   today.

---

### User Story 2 - An operator sees no change when running implement (Priority: P1)

An operator runs `spec-kitty implement WP##` (or `agent action implement`) on any topology:
flat, `lanes`, coordination, `single_branch`. They get the same workspace, the same commits,
the same refusals, codes, exit codes and console/JSON output as before the decomposition.

**Why this priority**: a tidy-first refactor that changes behaviour is a regression.

**Independent Test**: a characterization suite lands before any code moves. It covers every
refusal family and the side-effect order, and stays green, unedited, through every later
work package.

**Acceptance Scenarios**:

1. **Given** a WP whose dependency is not yet approved, **When** the operator runs implement,
   **Then** the command exits 1 with the same `dependencies_not_satisfied` text. No worktree, VCS
   lock or status event is created.
2. **Given** a WP that has not been finalized, **When** the operator runs implement, **Then** the
   command exits 1 with "WP <id> is not finalized; run `spec-kitty agent mission finalize-tasks`".
3. **Given** a `single_branch` mission whose write checkout is on the wrong branch, occupied or
   dirty, **When** the operator runs implement, **Then** the same `WRITE_CHECKOUT_*` refusal is
   shown, and `meta.json` carries no `vcs` lock afterwards.
4. **Given** the workspace was created but starting the WP status fails, **When** the operator runs
   implement, **Then** the same "Workspace was created but starting the WP status failed" message
   is shown with exit 1.
5. **Given** `--json`, **When** implement succeeds or fails, **Then** stdout carries the same
   machine-readable payload shape as before.
6. **Given** `agent action implement` calls the command programmatically, **When** it omits
   optional keyword arguments, **Then** the call behaves as before (no `OptionInfo` leakage).

---

### User Story 3 - Planning-artifact placement always comes from the canonical seam (Priority: P2)

An operator claims a WP on a coordination-topology mission whose action context cannot be
resolved (for example an empty coordination branch or a topology mismatch). Today implement
silently falls back to a coordination branch read from `meta.json`, which can split planning
artifacts between the primary branch and the coordination branch. After this mission the
placement always comes from the placement seam. If the seam itself cannot resolve, the claim
fails closed with an actionable remedy (`spec-kitty doctor coordination --mission <slug> --fix`).

**Why this priority**: it closes #5232, a recorded split-brain risk, as one slice of the
refactor.

**Independent Test**: on real-git fixtures for each topology, the seam-resolved placement equals
today's context placement wherever the latter resolves. A mission whose placement cannot be
resolved is refused with `PlacementResolutionRequired` and the doctor remedy, and nothing is
committed.

**Acceptance Scenarios**:

1. **Given** a flat mission, **When** the operator claims a WP with dirty planning artifacts,
   **Then** they are committed to the planning branch exactly as today.
2. **Given** a coordination mission with dirty PRIMARY and coordination-residue artifacts,
   **When** the operator claims a WP, **Then** each group lands on the same branch as today.
3. **Given** a mission whose placement the seam cannot resolve, **When** the operator claims a WP,
   **Then** the claim exits 1 with the doctor remedy, and no planning-artifact commit lands. The
   refusal fires in the planning-artifact commit phase, which runs inside the command's
   `validate` tracker step.
4. **Given** a state in which today's read-shaped context resolution fails and the meta-derived
   fallback commits (see FR-015), **When** the operator claims a WP, **Then** the outcome matches
   the FR-015 reachability table row for that state. Any row whose outcome changes was escalated
   under C-007 before FR-008 landed.

---

### Edge Cases

- **Exit codes before recover.** `--recover` without `--mission` still exits 2, and the
  `--mission` guard runs before recover mode.
- **Commit before late refusals.** The planning-artifact commit still runs before the bulk-edit,
  operational-context and checkout-identity refusals. This existing order is preserved and
  recorded as a follow-up, not changed.
- **Claim-commit exceptions.** The claim commit still re-raises `SafeCommitPathPolicyError`,
  `SafeCommitHeadMismatch` and `PlacementResolutionRequired`, and still downgrades any other
  failure to a warning with exit 0.
- **`--base` on a repository-root planning lane.** It stays a warned no-op. An unresolvable
  `--base` still prints the single canonical error and exits 1.
- **Coordination worktree not materialized.** The coordination branch exists but its worktree
  does not (fresh clone or CI). Behaviour is unchanged wherever today's flow already refuses
  earlier. Elsewhere the write-shaped seam composes the coordination ref instead of refusing.
- **Patch target moves.** A test patch whose target moved to a seam must fail loudly (attribute
  error or liveness gate), never pass silently.
- **Recover mode.** `--recover` keeps its exact output. It moves with the other presentation-only
  adapters and is not part of the phase sequence.
- **`--json` output.** The `--json` error text is the last 20 captured console lines, so print order
  is part of C-001. Moved code prints through the shared console singleton and never caches
  `console.file`.
- **Legacy console line.** The "(legacy path -- mission has no coordination_branch …)" console line
  is operator output. It is kept wherever it prints today; only the docstrings and comments drop
  the C-004 wording.
- **Planning partition on the e2e path.** The #3371 lesson applies: partition and reader moves
  are only caught end to end, so `tests/e2e/test_cli_smoke.py::test_full_workflow_sequence` is part
  of the blast radius of every planning-commit change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Thin command layer | As a maintainer, I want the implement command module to hold only argument parsing, the JSON-safe output wrapper, presentation and the call into the phase sequence. It then contains no planning-commit, dependency-gate, lane-selection or claim-commit decision code. The phase sequence and the printing effect adapters (planning-artifact commit adapter, claim-commit adapter, recover mode) live in sibling modules of the command package; pure decisions live in the seams (FR-003–FR-007). | High | Open | [build] | no — today all four decision families live in the module |
| FR-002 | Ordered implement phases | As a maintainer, I want the implement flow expressed as named phase functions called in this order: context → claim preflight and dependency gate → planning-artifact commit → bulk-edit gate and operational context → workspace and lane selection → allocate → record claim (status start and claim commit) → present. Presentation stays in the command layer. Today's side-effect order is kept. | High | Open | [build] | no — checked by a test that records the phase-function call order through the public command, plus FR-009's phase-order characterization |
| FR-003 | Dependency gate in the dependency-graph seam | As a maintainer, I want the claim-precondition decision (unseeded-WP rejection plus dependency readiness) to be a pure function in the dependency-graph seam that takes a reduced status snapshot and raises the same exception types and messages as today. Event reading and reduction stay with the caller. The lane-map derivation is pinned as it is and is not deduplicated with `status/dependency_verdict.py` in this mission. | High | Open | [build] | no — a seam unit test calls it without git |
| FR-004 | Planning-commit decisions in the coordination seam | As a maintainer, I want the pure planning-artifact commit decisions to live in the coordination seam beside the bookkeeping transaction and to return typed results or raise typed errors. They are the PRIMARY/coordination-residue partition, the partition guard, the `meta.json` demotion predicate, the bookkeeping identifiers and the candidate-file enumeration. The transaction execution and every print stay in the command package's planning-commit adapter, which renders the identical text. | High | Open | [build] | no — seam unit tests call them directly |
| FR-005 | Lane selection in the lanes seam | As a maintainer, I want these to live in the lanes implement-support seam with typed errors: lane lookup from `lanes.json`, origin-preferred `--base` resolution, the repository-root write-checkout refusal, and the VCS lock preparation. | High | Open | [build] | no — seam unit tests call them directly |
| FR-006 | Workspace context reads in the workspace seam | As a maintainer, I want the WP-prompt-file lookup, the `lanes.json` directory and the target-branch reads used by implement to resolve through the workspace-context seam. Their production importers are re-pointed, and the public `find_wp_file` name keeps an `__all__` entry where it lands. | Medium | Open | [build] | no — seam unit tests call them directly |
| FR-007 | Claim-commit bundle as a pure decision | As a maintainer, I want the claim-commit path bundle (which files the claim commit stages) to be a pure, directly testable function. It lives with the claim-commit adapter in the command package, because its status-artifact collector lives in the CLI layer. The claim policy metadata becomes one helper shared with `agent action implement`, which carries a duplicate today. This turns the #5673 fix into a change to one function plus one test. | High | Open | [build] | no — a seam test of the bundle; the dedupe is checked by a single definition remaining |
| FR-008 | Seam-owned planning placement (#5232) | As an operator, I want implement-claim to take the planning-artifact placement from a typed placement value that the coordination seam owns, instead of an optional parameter whose `None` silently triggers an implement-local fallback to `meta.json`. Mechanics: the `None` default and the implement-local meta read are removed; when the WP action context resolves, the placement is the canonical context placement ref; when it does not resolve, the seam supplies the documented degrade, which is the mission's declared coordination-branch value. That degrade is computed at the same point in the flow as today, after the #1598 structural check, so every reachable outcome is unchanged. This is #5232's accepted shape 2. Identity reads of `meta.json` are kept: the bookkeeping tuple, mid8 and the legacy console line. Only docstrings and comments drop the C-004 wording. The design is fixed by research.md R-1b (B2\*\*). | High | Open | [build] | no — same-fixture positive control: the FR-015 rows, including the double-fault rows, are identical before and after, and a planted break in the adapter's use of the seam value turns a coordination row red |
| FR-009 | Behaviour characterization first | As an operator, I want a characterization suite to land before any code moves and stay green through every later step with no assertion edited. It drives only public entry points: the CLI, the `implement` command function and `agent action implement`. Its assertions never reference implement-family internals. Where a failure can only be induced by substituting a collaborator, the substitution target is declared once, in a dispatch map fixture. A moving WP updates that map, never an assertion, and the liveness gate checks it. It pins: every refusal family (text or code, exit code, no mutation), the side-effect order, the genesis rejection, the #4888 message, the claim-commit propagate/soften exception table, the `--json` payloads, and the programmatic-call contract. The #5232 placement outcomes are pinned separately under FR-015, because FR-008 changes the code that produces them. | High | Open | [ratchet] | yes — positive control: a planted break per family, proven red before the suite is accepted |
| FR-010 | Patch-liveness coverage | As a maintainer, I want the existing patch-target liveness gate widened to the implement command family (the command module, its new siblings and `implement_cores`) before anything moves, so a patch on a name that no longer dispatches through that module fails. Widening does not raise the gate's unresolvable-target baseline, and dead patches it finds are fixed, not allow-listed. | High | Open | [build] | no — a planted dead patch must turn the gate red |
| FR-011 | Tests follow the code | As a maintainer, I want tests that string-patch implement internals moved onto the seams. Each test either calls the seam decision directly or patches the seam module that owns the name. A moved name loses its re-export from the command module unless production code imports it there, so a stale patch fails loudly. I want the patch-site count reported before and after with the committed counter (SC-002), and at least one end-to-end smoke test kept per behaviour family. | High | Open | [build] | no — the measured count must drop (SC-002) |
| FR-012 | Gates follow the code | As a maintainer, I want every architectural census or scan list that names the implement module to gain the module(s) the code moved to, and every path or source-text pin re-pointed. The checklist is research/code-grounding.md §1.5 plus research/test-remediation.md §5. Every lower-package module that receives moved code is covered by a no-CLI import guard. No gate is loosened or newly added for size. A non-vacuity floor that drops only because FR-008 deletes the code it counted is re-calibrated with a written rationale and a planted-break proof. | High | Open | [ratchet] | yes — positive control: a planted violation in each new module turns each widened scan red |
| FR-013 | Vacuous tests repaired | As a maintainer, I want the tests the grounding found vacuous repaired, each through the planted break named in research/test-remediation.md §5. `test_issue_1615_1616_1617_1618.py::test_resolve_mission_read_path_used_in_implement` gets a behavioural oracle. `test_implement_command.py::test_implement_requires_lanes_json`, `test_implement.py::test_implement_command_callable` and the `hasattr(implement, "safe_commit")` smoke are retired, each naming its covering guard. | Medium | Open | [build] | no — the planted break must turn the covering guard red |
| FR-014 | Programmatic call contract | As an agent, I want `agent action implement` to keep calling the implement command with an unchanged signature, unchanged option defaults and unchanged decorators, so programmatic callers see no difference. | High | Open | [ratchet] | yes — positive control: the existing programmatic-call tests fail when an optional keyword default is changed |
| FR-015 | #5232 reachability table | As an operator, I want every state in which today's read-shaped placement resolution fails on the real implement path characterized before FR-008 lands. Each row of the table records today's outcome (refused earlier, or which commit arm ran, with how many transactions to which refs) and the post-FR-008 outcome, on real-git fixtures. It also covers every topology, and the lifecycle phases (pre-consolidation, consolidated, published, torn-down coordination branch), where the seam's artifact kinds diverge. Under the chosen design (research.md R-1b, B2**) every row's outcome is unchanged, including the double-fault rows D1–D5 from the WP06 review. The behavioural rows are therefore green on the base and stay green. The red-first evidence is the new typed-placement API's unit tests (red until it exists), plus a planted break in the adapter's use of the seam value that turns a coordination row red. These tests live outside FR-009's frozen set. | High | Open | [build] | no — each row is a real-git fixture whose outcome differs between the fallback and the seam unless the seam is wired |
| FR-016 | Docs and changelog follow the code | As a maintainer, I want the docs that cite implement-module lines or symbols re-pointed: `docs/architecture/wp-runtime-state-eviction.md`, `docs/development/reference/read-side-seam-classification.md`, the git-operations-matrix `Source File` cells, and `docs/architecture/04_implementation_mapping/README.md`. I also want a CHANGELOG `[Unreleased]` entry for the operator-visible part of FR-008. | Medium | Open | [build] | no — the docs gates (`test_git_matrix_paths_resolve`, the docs freshness check) fail on a stale path |
| FR-017 | Tracker hygiene | As a maintainer, I want an issue-matrix row per addressed issue: #5635 and #5232 closed by the PR; #5673 shaped, not fixed; #5676, #5669 and #3931 out of scope. I want follow-up issues filed for the items under Assumptions, plus the #5232 single-path end state and any deferred test-remediation items, with their numbers in the PR and the issue matrix. | Medium | Open | [build] | no — the matrix rows and issue numbers are checked at accept |
| FR-018 | Dead placement helper and duplicate remedy | As a maintainer, I want the production-dead `_resolve_claim_commit_target` either made live as the FR-008 fail-closed helper or deleted, and the byte-duplicated `PlacementResolutionRequired` remedy reduced to one definition. | Low | Open | [build] | no — a single remedy definition is checkable by search |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complexity ceiling | Every function added or touched has cyclomatic complexity ≤ 15 (ruff C901), and `implement()` drops below 15. | Maintainability | High | Open |
| NFR-002 | Strict typing | Every new or receiving module passes `mypy --strict` with 0 errors, and no module is added to the mypy quarantine. Code that moves out of the quarantined command module is fixed to strict-clean in its adjust commit. The command module's quarantine entry is removed if the thin module is strict-clean; otherwise it is kept unchanged with the remaining errors listed in the PR. The two pre-existing strict errors in `core/dependency_graph.py` are fixed in passing (boy-scout rule), since FR-003 touches that file. | Maintainability | High | Open |
| NFR-003 | Fast feedback | The implement-direct regression subset (the command recorded in `research/test-remediation.md` §6, extended with the new seam and phase unit tests) completes in ≤ 30 s with `-n auto --dist loadfile`. Baseline: 18.3 s. The FR-009 characterization suite and the FR-015 reachability suite are real-git suites, timed separately at ≤ 60 s each. Each WP measures this. | Performance | Medium | Open |
| NFR-004 | Lint and format clean | `ruff check` and `ruff format --check --force-exclude` report 0 issues on every changed file, and no new `noqa` or `type: ignore` is added without an inline rationale. A format-excluded file that gets formatted loses its exclude entry. | Maintainability | High | Open |
| NFR-005 | Reviewable slices | Each work package lands its code move as its own commit, which `git diff --color-moved=zebra` shows as moved blocks only. Caller adjustments go in a separate commit. The PR lists the move commits. | Process | Medium | Open |
| NFR-006 | Out-of-matrix tests run locally | `tests/specify_cli/cli/commands/` and `tests/agent/` do not run in the CI matrix for an implement-module diff. Every work package runs them locally (targeted files), and the PR records the commands and pass/fail counts. Code moved into `status/` is covered by in-matrix tests so the diff-cover ≥ 90% gate holds. | Process | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Behaviour preserved | No change to refusal texts, error codes, exit codes, console or JSON output (including print order), commits or state files. The only exception is an FR-008 change that the FR-015 table records and the operator accepted under C-007. | Technical | High | Open |
| C-002 | Move, then adjust | Code is moved verbatim first and callers are adjusted second; logic is never edited inside a move. The adjust commit may also carry typing-only fixes for moved code (NFR-002) and the deletion of re-exports (FR-011). The move commit alone may be transiently mypy- or import-red. | Process | High | Open |
| C-003 | No new size or ratchet gates | Operator ruling: refactoring is engineering discipline, not a gate. Existing gates are widened or re-pointed, never loosened (FR-010, FR-012). | Process | High | Open |
| C-004 | Existing packages only | Decisions move into existing packages. Sibling modules may be added inside an existing package (for example `coordination/`, or the command package for adapters), but no new top-level package is created and no module is converted into a package. Lower packages (`lanes`, `workspace`, `coordination`, `status`, `core`) never import the CLI layer: they return typed results or raise typed errors, and only the command package prints. | Technical | High | Open |
| C-005 | Scope boundary | Out of scope: the #5673 and #5676 fixes, #5669, #3931, the move-task seam modules, `core/mission_creation.py` (sibling mission #5634), auto-rebase, a shared implement application service, and reordering the planning-artifact commit relative to late validation. | Business | High | Open |
| C-006 | Recognized raise sites stay | The `WRITE_CHECKOUT_*`, `MissingLanesError`, `DESTROYED_LANE` and `LANE_WORK_TIP_UNKNOWN` raise sites already live in the lanes package and are not moved or reworded. | Technical | Medium | Open |
| C-007 | Escalation | The mission stops for an operator decision before FR-008 lands if any reachable FR-015 row would change outcome: a newly refused claim, a different destination ref, or a different number of commits or transactions. | Process | High | Open |
| C-008 | Traceability | Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier appears in commits or the PR; this operator rule overrides any default tool attribution trailer. The operator merges. | Process | High | Open |

### Key Entities

- **Implement phase**: one ordered step of the implement flow. It consumes the previous phase's
  result and either produces its own result or raises a typed refusal.
- **Seam decision**: a pure function in an existing seam module that returns a verdict or raises a
  typed error. Its effect adapter performs the I/O; the command renders the outcome.
- **Placement ref**: the single commit target for planning artifacts and status events, resolved
  by the placement seam.
- **Patch site**: one test replacement of a name in a module namespace, counted to measure how
  tightly tests couple to internals.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The implement command module shrinks from 2,304 lines to at most 800 (`wc -l`).
  No sibling module created by this mission exceeds 800 lines. — [build] · no-op passable: no
- **SC-002**: Test patch sites into the implement command *family* drop from 119 to at most 45, a
  reduction of more than 60%. The 119 counts string, object and dispatch-map
  (`patch_collaborator`) patches, measured on the mission
  base commit by the counter committed at `tools/count_patch_sites.py`. The family is the command
  module, every sibling this mission adds, and `implement_cores`. The counter also reports console
  couplings and private-name imports. Re-pointing a patch from the command module to a sibling does
  not reduce the count. — [build] · no-op passable: no
- **SC-003**: The characterization suite (FR-009) is green on the base commit and on the final
  commit, with zero assertions edited in between. — [ratchet] · no-op passable: yes — positive control: planted breaks per refusal family
- **SC-004**: The implement command family no longer derives a commit destination or placement
  ref from `meta.json` itself. The one remaining meta-derived value, the degrade used when the WP
  context does not resolve, is owned, documented and tested in the coordination seam
  (`coordination/planning_commit.py`). Identity reads remain: the bookkeeping tuple, mid8, the legacy
  console line and the demotion guard. #5232 is closed by the PR. — [build] · no-op passable: no — positive control: a search for the implement-local fallback finds it on the base commit
- **SC-005**: Every implement phase has at least one seam unit test that exercises its decision
  without the CLI and without patching the implement command family. — [build] · no-op passable: no

## Assumptions

- research.md R-1b settled the degrade: the mission's declared coordination-branch value, owned by
  the coordination seam. The seam-probing alternatives (R-1 B1/B2\*) change reachable outcomes and
  stay an operator follow-up. FR-015 pins the reachable states, including the double faults found in
  the WP06 review (see C-007).
- The pre-existing red `test_commit_recipes.py::test_no_unallowed_git_commit_recipe_strings_in_src`
  (#5699, nightly P0) is unrelated and stays red. It is not chased here.
- Follow-ups are filed rather than folded:
  - the planning-artifact commit lands before late validation;
  - the misleading "not finalized" refusal for an unmaterialized coordination worktree;
  - a shared implement application service (needs an ADR).
