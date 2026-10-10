# Mission Specification: Owned single-branch lifecycle authority

**Mission Branch**: `kitty/mission-owned-single-branch-lifecycle-authority-01M4J70Y`
**Created**: 2026-10-10
**Status**: Draft
**Input**: Thread the validated `OwnedCheckout` through the remaining single-branch lifecycle commands so owned missions resolve, preflight, select material and commit from the validated owned checkout instead of folding to the primary repository-root checkout. Closes #5874 #5877 #5878 #5880 #5892 #5893 #5947.

## User Scenarios & Testing *(mandatory)*

The actor throughout is an **operator (or agent on their behalf)** running a Spec Kitty mission that was created with `agent mission create --owned-checkout` — a single-branch mission whose artifacts live only in a *linked* checkout (an owned checkout), on a tool-minted mission branch, while the repository-root checkout holds no copy of that mission.

### User Story 1 - The owned single-branch lifecycle completes from the owned checkout (Priority: P1)

An operator creates a protected PR-bound `single_branch` mission in an owned checkout and runs the full lifecycle from there: open/resolve the specify Decision Moment, check prerequisites, map requirements, finalize tasks, record the analysis report, and run the review cycle. Today several of these commands fold the invocation root to the repository-root checkout (`get_main_repo_root`) and either fail to resolve the mission (`FEATURE_CONTEXT_UNRESOLVED` / `MISSION_NOT_FOUND`), compute the wrong branch verdict, or write to the wrong location.

**Why this priority**: Without it the supported owned-create route strands a mission before discovery — the mission cannot progress at all. Six of the seven issues sit on this journey.

**Independent Test**: Create an owned single_branch mission (primary checkout has no copy), then exercise each command from the owned checkout and assert exit 0, the mission resolves, writes land in `owned.mission_dir` on `owned.write_branch`, and the repository-root checkout stays byte-unchanged.

**Acceptance Scenarios**:

1. **Given** an owned single_branch mission on its minted mission branch and no copy in the repository root, **When** `agent decision open/resolve/defer/cancel/verify/list` (host CLI and `orchestrator-api`) is run from the owned checkout, **Then** the Decision Moment ledger and `status.events.jsonl` are written under `owned.mission_dir` and nothing is written under `repository_root/kitty-specs` or `repository_root/.worktrees`.
2. **Given** that mission on its minted write branch whose landing target is protected `main`, **When** `check-prerequisites` runs, **Then** `branch_matches_target` is `true`, `expected_checkout_branch` is the minted write branch, and `target_branch` still reports the protected landing target.
3. **Given** valid owned spec/WP files, **When** `tasks map-requirements` runs, **Then** the mapping reads and writes the owned WP files and commits on the owned write branch; a stale primary copy of the mission is left untouched.
4. **Given** the owned mission, **When** `finalize-tasks` (and `--validate-only`) runs, **Then** it consumes the validated owned write branch for planning and bookkeeping, preserves the canonical landing target, and does not fall into the legacy protected-target recovery path.
5. **Given** the owned mission with a valid report input, **When** `record-analysis` runs, **Then** it reads material and charter inputs from the owned checkout, writes the wrapped report under `owned.mission_dir`, and commits it on the owned write branch.

### User Story 2 - Non-owned and coordination behaviour is preserved, refusals fire before writes (Priority: P1)

Ordinary (repository-root) and coordination-topology missions must behave exactly as before, and every ownership refusal must fire before any write.

**Why this priority**: The fix threads an optional fact; it must never relax the canonical default resolver, the coordination fail-closed paths, or the ownership guards.

**Independent Test**: Run each touched command without `--owned-checkout` and confirm byte-identical behaviour on the targeted suites; drive invalid owned claims (repository root, nested, foreign mission, wrong/detached branch, symlinked path escaping the mission dir) and confirm a typed `OWNED_*` / `OWNERSHIP_*` refusal with zero writes.

**Acceptance Scenarios**:

1. **Given** a non-owned invocation, **When** any touched command runs, **Then** resolution and placement are unchanged from current `main`.
2. **Given** an `--owned-checkout` that names the repository root, a mission worktree, a foreign mission, or a wrong/detached branch, **When** a command runs, **Then** it refuses with the typed ownership code before writing anything.
3. **Given** an owned ledger/report path that would escape the mission directory via a symlink, **When** a command runs, **Then** it refuses with `OWNED_MISSION_PATH_REFUSED` and leaves events/files untouched.

### User Story 3 - The validate-only finalize preview matches the real run (Priority: P2)

The read-only `finalize-tasks --validate-only` lane preview must report the same lanes finalization actually writes for a single_branch mission.

**Why this priority**: A preview that disagrees with the real run gives an incorrect basis for approving finalization; it is lower priority than resolution because the command still exits and the real run is correct.

**Independent Test**: For a single_branch mission with two independent code WPs, assert the preview reports one `lane-planning` lane (not the default multi-lane split) and that the previewed mission branch / landing target match `meta.json`, with zero mutation.

**Acceptance Scenarios**:

1. **Given** a single_branch mission with two independent code WPs, **When** `finalize-tasks --validate-only` runs, **Then** the lane preview reports exactly one repository-root lane holding both WPs, matching the real finalization output.

### Edge Cases

- Wrong checkout branch or detached HEAD on the owned checkout → `OWNED_BRANCH_REFUSED` before any write.
- Owned checkout that is the repository root, a coordination worktree, or a lane worktree → `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` / `OWNED_CHECKOUT_IS_MISSION_WORKTREE`.
- A ledger, events path, or report path that escapes `owned.mission_dir` (including via symlink) → `OWNED_MISSION_PATH_REFUSED`.
- A stale copy of the mission in the repository-root checkout → the owned path resolves the owned mission and never reads or mutates the stale copy.
- An owned invocation with no `--owned-checkout` but a current-checkout that owns the mission → flagless adoption applies the same validated fact; an unrelated or ambiguous checkout falls back to repository-root behaviour.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Decision Moment owned resolution (#5874) | As an operator, I want `agent decision` (host CLI and `orchestrator-api` verbs: open/resolve/defer/cancel/verify/list) to resolve an owned single_branch mission from the owned checkout so the specify interview can run and its ledger/events land under `owned.mission_dir` with nothing written to the repository root. | High | Open | [build] | no — repro exercises open→list→resolve→verify and asserts no repository-root leak |
| FR-002 | Owned prerequisite branch match (#5877) | As an operator, I want `check-prerequisites` to report `branch_matches_target: true` with `expected_checkout_branch` set to the validated owned write branch while keeping the protected landing target, so task authoring is not falsely gated. | High | Open | [build] | no — repro pins a protected-mint mission whose write branch ≠ landing target |
| FR-003 | Owned requirement mapping (#5878) | As an operator, I want `tasks map-requirements` to resolve the owned mission, read/write the owned WP and spec surface, and commit on the owned write branch, so the mandatory mapping step reaches finalization. | High | Open | [build] | no — repro asserts mapping lands owned and leaves a stale primary copy untouched |
| FR-004 | Owned finalize branch contract (#5880) | As an operator, I want `finalize-tasks` to consume the validated owned write branch and preserve the canonical landing target rather than refusing a PR-bound owned mission as legacy branch metadata. | High | Open | [build] | no — repro asserts the legacy recovery triad is never invoked for a validated owned mission |
| FR-005 | Single-branch lane preview parity (#5892) | As an operator, I want `finalize-tasks --validate-only` to compute its lane preview with the stored `single_branch` topology and mission branch so the preview equals the real finalization output. | Medium | Open | [build] | no — repro compares preview lanes to the captured real-run manifest |
| FR-006 | Owned analysis recording (#5893) | As an operator, I want `record-analysis` to resolve the owned mission, read material/charter inputs from the owned checkout, write the wrapped report under `owned.mission_dir`, and commit it on the owned write branch. | High | Open | [build] | no — repro asserts the report commits on the owned HEAD and the primary stays unchanged |
| FR-006a | Owned material/charter authority (#5893, operator-ruled) | As an operator, I want a package-identical GLOBAL template mirror admitted as a material input (byte-compared to the package default, with a `template-selection:<kind>` freshness identity) and `charter generate` to honour `--owned-checkout`/`--mission-handle` destinations, so a legitimate package-mirror owned checkout can record analysis. | Medium | Open | [build] | no — repro admits a package-identical mirror and fails freshness when the selection changes |
| FR-007 | Review/cycle owned resolver invariant (#5947) | As an operator, I want a validated owned single_branch `review/cycle` arm to never consult the primary resolver (`get_main_repo_root`), pinned by a by-construction test, so the nightly `specify-cli-out-of-matrix` red cannot recur. | High | Open | [ratchet] | no — the invariant test fails if an owned arm consults the poisoned resolver |
| FR-008 | Single resolver authority & non-owned preservation | As a maintainer, I want all owned resolution to route through the one minter (`resolve_owned_mission`) and the `owned=` placement/protection seam — with no second ownership resolver and no change to `core/paths.py` — while non-owned primary/coordination behaviour and every ownership refusal are preserved. | High | Open | [ratchet] | no — non-owned snapshot tests and refusal-before-write tests pin the preserved behaviour |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new tree scans | Owned resolution introduces no additional O(tree) walks or extra `get_main_repo_root` calls; each command resolves ownership at most once (reusing the minted fact) and typical CLI operations stay under 2s. | Performance | Medium | Open |
| NFR-002 | Clean lint/type gates | All new or changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero issues and zero new blanket `# noqa` / `# type: ignore` / per-file ignores. | Maintainability | High | Open |
| NFR-003 | Targeted coverage | Every new branch/helper added to thread `owned=` is exercised by a focused test in the same work package (≥90% new-code coverage intent). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority | Thread the one validated `OwnedCheckout`; introduce no second ownership resolver and make no change to `src/specify_cli/core/paths.py` or the placement-seam contract. | Technical | High | Open |
| C-002 | Scope fence | Exactly the seven issues (#5874 #5877 #5878 #5880 #5892 #5893 #5947). #5882 and the broader external-authority classes (#5253/#5380) stay out of scope, except the reviewed package-identical GLOBAL-template-mirror relaxation the operator ruled into #5893. | Business | High | Open |
| C-003 | ATDD / red-first | Each functional requirement is pinned by a reproduction test that is RED on `planning_base_branch` and GREEN on the final commit; no test is skipped, disabled, xfail-ed, or quarantined, and no flake is retried to green. | Technical | High | Open |
| C-004 | Terminology canon | User-facing language uses Mission (never feature); run the terminology guard (`tests/architectural/test_no_legacy_terminology.py`) when touching `src/charter/offering/` or user-facing prose. | Technical | Medium | Open |

### Key Entities

- **OwnedCheckout**: the validated ownership fact minted once per command by `resolve_owned_mission` — carries `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology`, and `write_branch`. Immutable, never persisted.
- **Owned write branch vs landing target**: `owned.write_branch` (the tool-minted `mission_branch` that owned writes land on and the checkout must be ON) is distinct from `target_branch` (the protected merge/landing destination). The defect is treating the landing target as the write branch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An owned single_branch mission created in a linked checkout runs the full lifecycle (decision → prerequisites → map-requirements → finalize → record-analysis → review) from that checkout, and every reproduction test for the seven issues that was RED on the planning base passes on the final commit, with zero artifacts written to the repository-root checkout. — [build] · no-op passable: no
- **SC-002**: Non-owned and coordination missions show unchanged behaviour on the targeted suites (no regressions), and every invalid owned claim refuses with a typed code before any write. — [ratchet] · no-op passable: no
- **SC-003**: `finalize-tasks --validate-only` reports the same lanes the real finalization writes for a single_branch mission (one repository-root lane). — [build] · no-op passable: no
- **SC-004**: The diff introduces no second ownership resolver and no change to `core/paths.py`, and all new/changed code passes `ruff`, `ruff format --check`, and `mypy --strict`. — [ratchet] · no-op passable: no
