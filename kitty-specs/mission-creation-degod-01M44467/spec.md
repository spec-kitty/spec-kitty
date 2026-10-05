# Mission Specification: Mission creation degod

**Mission Branch**: `issue-5634-mission-creation-degod` (lanes topology)
**Created**: 2026-10-04
**Status**: Draft (revision 2, post-specify squad folded; see `research/code-grounding.md` and the findings table at the end)
**Input**: Issue #5634, "Investigate & refactor: core/mission_creation.py hotspot (2,363 LOC, 42 commits / 28 fixes in 90 days)", plus the operator's dispatch brief: a tidy-first, behaviour-preserving decomposition into pure decision cores and effect adapters, with the tests moved onto the new seams. Grounding: `research/code-grounding.md`, `research/test-remediation.md`.

## Intent Summary

- **Primary actor**: a Spec Kitty maintainer fixing a mission-create defect in the 4.0.0 cycle (follow-up: #5676 occupancy, #5704 orphan scaffold on a mint refusal).
- **Trigger**: the maintainer must change one create-time decision (protected-target mint, coordination-routed scaffold, duplicate detection, rollback) and pin it with a test. Today that decision sits inside a 2,363-line module that tests patch 277 times.
- **Desired outcome**: each create-time decision is a pure function that a unit test pins with plain inputs. Git and filesystem effects sit in small adapter modules. The create entry point is a thin orchestrator. Operators see identical behaviour.
- **Invariant**: behaviour is byte-identical (meta.json, branch names, worktree paths, checkout HEAD, commits, status events, refusal texts, error codes, exit codes, residue left after a refusal). Every test patch on the module either still intercepts or is moved or retired with proof.
- **Boundary**: no behaviour change (follow-up: #5676, #5704, #5707 stay out, decision `01M446WTGDPEAGV4MSRD1CJK75`); no new size or count gate; CLI topology-default code is not moved.

**Terms.** *Façade*: the create module `core/mission_creation.py` after the split. *Routing* in this spec always means **patch-interception routing**: a call made through the façade module object so a test patch on the façade intercepts it. It never means placement, branch-target, dispatch or commit routing. *Primary Branch* follows the glossary (`docs/context/orchestration.md#primary-branch`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pin a create-time decision without patching internals (Priority: P1)

A maintainer changes the protected-target mint rule (follow-up: #5676 adds an occupancy precondition). They change one pure decision function and add one unit test that feeds it plain facts, with no git repo and no monkeypatch.

**Why this priority**: this is the enabling value the issue names. Later milestone-11 fixes in this area must be cheap to make and to pin.

**Independent Test**: the decision functions import and run with no git, filesystem, subprocess, environment or clock access, and their unit tests construct inputs directly. Each decision function is also wired into the production path: a planted break inside it turns a golden or end-to-end test red.

**Acceptance Scenarios**:

1. **Given** the refactored tree, **When** a maintainer looks for the protected-mint decision, **Then** it is one pure function returning "no mint", "refuse (error kind, message)" or "mint (branch name)" from a facts value.
2. **Given** the facts that today produce each mint refusal (target without a commit, dirty checkout outside the scaffold, branch already exists), **When** the decision function runs, **Then** it returns the same refusal kind and message text as the current code.

### User Story 2 - Operators see no behaviour change (Priority: P1)

An operator runs `spec-kitty agent mission create` with any topology, on a protected or unprotected target, with any of the create flags. They get byte-identical results, refusals and exit codes.

**Why this priority**: the module has a 28-of-42 fix ratio, and a regression here breaks every new mission.

**Independent Test**: a golden behaviour matrix captured on the unchanged code passes unchanged after every work package.

**Acceptance Scenarios**:

1. **Given** the golden matrix snapshot captured on the unchanged base, **When** it runs after the refactor, **Then** every cell matches with no snapshot edit and no edit to the golden test or its normaliser.
2. **Given** a refusal cell (for example a live duplicate), **When** it runs, **Then** the exception kind, message, error code and exit code match. The repository state after the refusal also matches the state captured on the base, including today's residue (for example the orphan scaffold that the refused-mint cell leaves, baseline-red follow-up: #5704).

### User Story 3 - Tests exercise behaviour, not namespaces (Priority: P2)

A maintainer reads a mission-create test and sees either real behaviour on a real repository or a pure-core unit test, not a stack of patches that fake the environment.

**Why this priority**: 82% of today's patch sites target names the module imports, so they silently stop intercepting when code moves; about 42 are already dead, and about 33 creates assert on a faked branch.

**Independent Test**: patch use is measured before and after by a committed counter, and every remaining patch provably intercepts.

**Acceptance Scenarios**:

1. **Given** a test that patches a name on the create module, **When** the patched path runs inside a moved module, **Then** the patch intercepts the call, or the test was moved to the owning module.
2. **Given** a retired test or patch, **When** the reviewer checks the WP record, **Then** the record names the covering guard and the planted break that turned that guard red, or for a dead patch, the coverage-context proof that the patched call site never ran under that test.

### User Story 4 - Structural guards keep watching the moved code (Priority: P2)

Architectural gates that read the create module's source keep covering every relocated function. These are the coord-writer census, the write-dir consumer scan, the mission resolver walker exemption, the single-mission surface resolver, the commit-recipe scan, the adapter-boundary scan, the dead-symbol gate and the mission-type reader census.

**Why this priority**: a gate that silently loses scope is worse than a failing one.

**Independent Test**: each re-pointed gate passes and still finds the function or call site it guards in its new module.

**Acceptance Scenarios**:

1. **Given** a gate that pinned `_emit_create_events` in the create module, **When** the function moves, **Then** the gate pins it in its new module, and still fails if the guarded call is removed.

### Behaviour families

The families are used by FR-007 (one end-to-end smoke kept per family) and by the golden matrix:

1. Branch-flat create (`single_branch`, `lanes`) on an unprotected target.
2. Protected-target `single_branch` create (mission-branch mint and checkout, `--commit-to-target`).
3. Coordination-routed create (`coord`, `lanes_with_coord`): coordination branch mint, worktree and seeded creation events.
4. Owned-checkout create (`--owned-checkout`).
5. Create-time refusals and rollback (duplicate, input validation, root guards, mint refusals, failed-create restore).
6. Derived default topology (no `--topology`, decided in the CLI).

### Edge Cases

- **No `origin/HEAD`**: the default topology falls back to treating the current branch as the Primary Branch, so a create on that branch is `coord`. Pinned, not changed.
- **Create refused by the protected mint**: today it leaves a scaffold without `meta.json`, and the retry is refused MISSION_ALREADY_EXISTS (baseline-red, follow-up: #5704). Pinned as-is, not fixed.
- **Malformed protection configuration**: the error is raised at exactly the same point in the create as today, so the same residue (or none) is left behind.
- **Test process inside a lane worktree**: the worktree-context guard still refuses unless `allow_worktree_context` is passed.
- **Import order**: importing a leaf module before the façade must not cause an import cycle. Function-local imports that avoid cycles or preserve adapter registration order stay local.
- **Reused mission directory with a pre-existing `meta.json`**: the mint keeps reading `commit_to_target` from the merged meta. A stale `"true"` string still raises at the same point. The recreate guard keeps reading the parameter, so both sources are preserved.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Core golden matrix | As a maintainer, I want a zero-patch golden matrix captured on the unchanged code, so that byte-identical behaviour is proven for every later change. It covers topology × protected/unprotected target × create flags, plus the refusal cells named in SC-001. Each cell captures normalised meta.json, branch names, worktree paths, checkout HEAD in the write checkout and the repository root checkout, the files of each new commit, the status event sequence and the checkout that holds the status log, refusal kind, message, error code, and the post-refusal repository state. Normalisation is whitelisted to mission_id, mid8, ISO timestamps and absolute paths only. The snapshot records the base commit it was captured on, and regenerating it on that base reproduces it byte for byte. | High | Open | [build] | no — green on the unchanged base AND red on one planted break per captured dimension |
| FR-002 | CLI golden cells | As a maintainer, I want CLI-level golden cells for the derived default topology, so that the command surface is pinned too. The cells cover a create on the Primary Branch with `origin/HEAD`, on a non-primary branch, with `--pr-bound`, with no `origin/HEAD`, and with `--owned-checkout` and no `--topology`. Each behaviour family also gets one success smoke and one refusal smoke, capturing the JSON envelope, error code and exit code. | High | Open | [build] | no — same per-dimension planted-break control as FR-001 |
| FR-003 | Pure decision cores | As a maintainer, I want the create-time decisions as pure functions, so that unit tests pin them with plain inputs. The decisions: protected-target check, mint applicability, protected-mint decision, coordination-routed predicate, meta flag patch (retention, `pr_bound` and `commit_to_target` absent unless true), duplicate match and abandonment, orphan-scaffold plan, coordination rollback action, scaffold-commit outcome, and created/uncommitted file sets. A core delegates to the existing authorities (`ProtectionPolicy.is_protected_target`, `topology_mints_coordination_branch`, `mission_branch_name`, `classify_topology`) and never re-encodes their rules. | High | Open | [build] | no — an AST purity check (no subprocess, os, shutil, Path I/O, clock, ULID or git helper use in the decision module) fails on a planted positive control, and a planted break in each core turns a golden or end-to-end test red |
| FR-004 | Effect adapters behind a façade | As a maintainer, I want the git and filesystem effects moved into cohesive sibling modules by responsibility (roots, identity, duplicates, protected mint, scaffold, meta, events, commit, rollback), so that each responsibility can be read and changed alone. The façade keeps the public entry point, the orchestration and re-exports of every moved name. | High | Open | [build] | no — an exactly-once proof shows every pre-split top-level definition appears once across the family |
| FR-005 | Patches keep intercepting | As a maintainer, I want every name that tests patch on the façade to still intercept after the code that reads it has moved, so that no test silently runs real effects. The rule is enforced by a check over the whole module family: the routed-name list equals the set of names tests patch on the façade and that a leaf reads (set equality, computed from the tests), and no leaf reads a routed name except through the façade module object. The check has an empty allowlist. `subprocess` is out of its scope by design: patching `mission_creation.subprocess.run` patches the process-global module, and the mission removes the one such patch instead of routing it. | High | Open | [build] | no — two planted controls must fail it: a bare call to a routed name, and a newly patched name missing from the list |
| FR-006 | Structural gates follow the code | As a maintainer, I want every gate that names the create module or its functions re-pointed or widened to the module family, with no new allowlist entry, so that no gate loses scope. This covers: the single-mission surface resolver descriptor; the coord-writer census pair; the write-dir consumer scan (new modules join the consumer list, not the frozen pre-adoption list); the resolver walker exemption; the commit-recipe path key; the adapter-boundary scan (widened to the family); the mission-type reader census path; and the dead-symbol gate (constants and classes move with their readers; no unused logger). | High | Open | [ratchet] | yes — paired with each gate's own failure on a planted removal of the guarded call in the new module |
| FR-007 | Tests moved onto the seams | As a maintainer, I want the patch-heavy tests moved onto the pure cores and owning adapters, so that the suite tests behaviour. Dead patches are retired with coverage-context proof; faked-branch tests are rewritten onto real repositories; the 1.1 s identity-collision sleeps are replaced by injected identity and clock; the process-global `subprocess.run` patch becomes adapter fault injection; at least one end-to-end smoke is kept per behaviour family. Patch use is reported before and after with a per-name disposition table: moved / rewritten / retired, with proof. | High | Open | [build] | no — the committed counter must show the drop stated in NFR-004 |
| FR-008 | Uncovered branches covered | As a maintainer, I want each decision branch that no test exercises today covered by a pure-core unit test or a golden/adapter test, so that the move is protected where it is riskiest. The branches: dirty-checkout mint refusal, `checkout -b` failure, topology corroboration failure, MissionCreated payload mismatch, coordination commit failure, bootstrap meta-commit skip, duplicate scan fail-closed on missing meta, abandonment read failure, same-prefix neighbour guard in orphan cleanup, and coordination rollback early return. | High | Open | [build] | no — each new test must fail on a planted break of its branch |
| FR-009 | Behaviour-neutral seam cleanups | As a maintainer, I want the seams to match the responsibilities, with no change to when errors are raised. Protection is resolved at most once per create, at the moment it is first needed today. The protected mint is invoked from the orchestrator instead of from inside the meta builder, in the same order. The coordination-routed predicate is defined once, as a thin wrapper over `topology_mints_coordination_branch` plus the owned-checkout condition. The rollback holder is typed. | Medium | Open | [build] | no — a structural check finds exactly one definition of the predicate and no mint call inside the meta builder; the golden matrix (including the malformed-protection-config cell) proves neutrality |
| FR-010 | Topology fallback pinned | As a maintainer, I want the no-origin/HEAD create-time topology fallback pinned by decision-level tests that call the existing `_resolve_default_topology_phase` and `coord_topology_reachable`, not a copy, so that #5707 can later change it deliberately (follow-up: #5707). The two Primary Branch inputs (bias=True for the topology default, bias=False for the protection check) are named explicitly in those tests. | Medium | Open | [ratchet] | yes — paired with a planted break of the fallback that must turn the test red |
| FR-011 | Create invariants pinned | As a maintainer, I want the grounding invariants pinned by golden cells or focused tests, so that the move cannot drop them. Coordination-routed creation events land in the coordination worktree and the status log stays off the target. A failed create restores in order: checkout first, then the orphan branches and the coordination surface (the coordination Mission dir is cleared before the coordination worktree is torn down and before its branch is deleted or CAS-reset), then the disposable scaffold, which is planned before the index is restored. MISSION_ALREADY_EXISTS is raised before the mint refusal. The scaffold commit lands on the minted branch. At create, `tasks/README.md` is committed and `spec.md` is left untracked (the specify commit boundary; corrected from the observed behaviour that WP03 pinned). The meta commit happens after origin binding. mid8 is derived once and shared by the directory name and meta. | High | Open | [ratchet] | yes — each pin paired with a planted break of its invariant |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte-identical behaviour | The freeze set (golden snapshots, golden test modules, normaliser and the fixture builders they use: `tests/_support/git_template/**`, `tests/_factories/__init__.py`) is unchanged (0 diff lines against the WP01 commit) after every later work package, and all cells pass. The only exception is the documented re-capture after a rebase that brings a real upstream change to the create module: a separate commit made on the still-unsplit code, carrying the upstream diff. | Reliability | High | Open |
| NFR-002 | Golden matrix runtime | The core and CLI golden files together finish in at most 45 s wall under `-n 4 --dist loadfile` on the development container. | Performance | Medium | Open |
| NFR-003 | Static quality | Every new or changed module passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with 0 issues. No function exceeds cyclomatic complexity 15. No new `# noqa` or `# type: ignore` is added. | Maintainability | High | Open |
| NFR-004 | Patch reduction | Measured by a committed patch counter that resolves f-string targets. **Scope**: (a) every patch, anywhere in `tests/`, whose target is a module of the `mission_creation` family (the façade or a sibling); (b) patches of a name the family imports, in that name's source module (for example `specify_cli.core.git_ops.get_current_branch`), counted **within the covering set and every test file this mission touches**. Process-global standard-library names (`subprocess`, `os`, `shutil`) are reported separately and excluded from the budget; patching them is not family-specific. Fixture-held patches also count once per test that applies them (runtime applications). **Budget**: static (a) sites drop from the WP04-measured baseline (279: the 277 grounding sites plus 2 parametrized fault-injection targets the census now resolves) to at most 15; static (a)+(b) sites end at most 40; runtime applications of (a)+(b) drop by at least 70% against the WP04 baseline. The counter's output on the WP04 baseline and on the final commit is reported in the PR. | Maintainability | High | Open |
| NFR-005 | No new reds | `make test-fast`, the owning test directories and the implicated architectural gate files show no failure that is not also red on the base (baseline-red: #5705, #5706). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No behaviour change | Refusal text, error codes, exit codes, meta.json, branch names, worktree paths, state files and refusal residue stay byte-identical, and every error is raised at the same point in the create. Out of scope (follow-up: #5676, #5704, #5707, INV-COORD-HOME residual). | Technical | High | Open |
| C-002 | No new gates of size or count | No size, LOC or patch-count ratchet gate and no new allowlist entry or baseline bump (operator ruling; ADR `docs/adr/4.x/2026-09-30-1`). Liveness, routing and purity checks with an empty allowlist are allowed. The patch counter is a reporting tool, not a gate. | Technical | High | Open |
| C-003 | Move first, then adjust | Code is moved verbatim before callers are adjusted, and logic is not edited while moving. Any deviation from verbatim is listed with its reason in the WP review record. | Technical | High | Open |
| C-004 | Routing rule | A leaf module reaches names tests patch on the façade, and functions another family module owns, through a lazy in-function import of the façade module object. No leaf imports the façade at module scope (precedent: PR #5679). | Technical | High | Open |
| C-005 | Assertions are not edited to pass | No test assertion is changed to make a move pass. When a test is rewritten from mocks to real behaviour (for example a `_commit_feature_file` mock to a real commit), an interaction assertion may be replaced only by an equal-or-stronger behavioural assertion, logged in the WP record. A test is retired only with its covering guard named and re-proven by a planted break. | Technical | High | Open |
| C-006 | Public surface stable | Every name imported from the façade today by `src/` or `tests/` stays importable from it, and the logger name `specify_cli.core.mission_creation` is unchanged. Both are enforced by tests. | Technical | High | Open |
| C-007 | File set | The CLI topology-default code (`cli/commands/agent/mission_create.py`) and the `implement` modules (sibling mission, follow-up: #5635) are not edited. Local imports that avoid cycles or preserve adapter registration order stay local, enforced by an AST pin. | Technical | Medium | Open |
| C-008 | Order of work | The golden matrix (FR-001, FR-002) and the uncovered-branch tests (FR-008) land green on the unchanged code before any code moves. Pure-core unit tests land before or with each core. Seam tests land before any end-to-end test is trimmed. | Technical | High | Open |

### Key Entities

- **Create decision core**: a pure function from a frozen facts value to a decision (for example protected-mint facts → no mint / refuse / mint).
- **Effect adapter**: a module that queries or mutates git or the filesystem, and either feeds facts to a core or applies a decision.
- **Façade**: the create module. It owns the public entry point and orchestration and re-exports moved names.
- **Golden cell**: one create scenario (topology, target, flags) with its normalised observable outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The golden matrix is green on the unchanged base and on every WP's final commit, with 0 edits to snapshot, test or normaliser. It has at least 40 success cells and these 13 refusal cells: live duplicate, mission branch exists, dirty checkout under the protected mint, target without a commit, invalid slug, empty friendly name, `commit_to_target` without `single_branch`, unborn HEAD, detached HEAD, worktree context without the allow flag, owned-root mismatch, protected recreate, and the refused-mint orphan followed by its retry (baseline-red, follow-up: #5704). — [build] · no-op passable: no
- **SC-002**: The façade keeps only the entry point, orchestration and re-exports. Every responsibility in the grounding map has one owning module. — [build] · no-op passable: no
- **SC-003**: Patch sites in NFR-004's scope drop to at most 40 (at most 15 on the module family), with a per-name disposition table in the PR. — [build] · no-op passable: no
- **SC-004**: Each of the ten previously uncovered decision branches has a test that fails on a planted break. — [build] · no-op passable: no
- **SC-005**: Every architectural gate that referenced the create module passes, with 0 new allowlist entries. — [ratchet] · no-op passable: yes — paired with each gate's planted removal

## Assumptions

- The test fixtures behind `tests/_factories/coord_mission.py` and `clone_template` give a real repository on a `main` branch, fast enough for the golden matrix.
- `ProtectionPolicy` is already a frozen, I/O-free value once resolved, so the protection check can take it as input.
- Main moves fast. The mission rebases at every phase boundary, and the sibling `implement.py` mission (follow-up: #5635) shares no helper with this module.

## Out of Scope (tracked)

- Follow-up: #5676 occupancy precondition, #5704 mint-before-scaffold hoist, #5707 bias unification, the INV-COORD-HOME residual.
- Baseline-red: #5705 (commit-recipe scan) and #5706 (fire_once flake).
- Follow-up: making `_commit_feature_file` mocks the default in the incidental factory consumers that only use `create_mission_core` (44 files) is not in this mission's file set.

## Post-specify squad findings (disposition)

| Finding | Lens | Disposition | Evidence |
|---|---|---|---|
| NFR-004 could be met by fixture laundering, source-module patching or leaving dead patches; thresholds too loose | reviewer | accepted | NFR-004, SC-003 (scope (a) family anywhere + (b) source namespaces in the covering and touched files, runtime applications, 40/15) |
| The golden matrix could be made vacuous via the normaliser or capture | reviewer | accepted | FR-001, NFR-001 (frozen test and normaliser, whitelist, base reproducibility, one break per dimension) |
| "Gather once" moves the error point (#5704-shaped) | reviewer | changed | FR-009 (at most once, at the first-use point today), C-001, malformed-config edge case |
| G5 single `commit_to_target` source has no proof | reviewer | changed | Edge case keeps both sources; removed from FR-009 |
| FR-005 is not enforceable as written | reviewer | accepted | FR-005 (set equality, façade-object form, family-wide, two planted controls) |
| Purity check is too weak; a core might not be wired | reviewer | accepted | FR-003 (AST ban list, positive control, a planted break per core turns a golden test red) |
| Missing invariants and gate items, T5/T7 not traced | reviewer | accepted | FR-011, FR-006, FR-007, C-006, C-007 |
| Ordering not stated; behaviour family undefined; no proof for dead-patch retirement | reviewer | accepted | C-008, "Behaviour families", US3 scenario 2 |
| C-005 too strict for mock-to-real rewrites | reviewer | changed | C-005 (equal-or-stronger replacement, logged) |
| SC-001 lets refusal cells drop | reviewer | accepted | SC-001 (13 cells named) |
| Cores must delegate, not re-encode, existing authorities | doctrine | accepted | FR-003, FR-009 |
| The topology pin must call the existing functions | doctrine | accepted | FR-010 |
| Name the sense of "routing"; Primary Branch wording | doctrine | accepted | "Terms" paragraph, FR-010 |
| Bare issue references would gate approval | doctrine | accepted | context markers (`follow-up:`, `baseline-red`) on every non-target reference; #5634 is the only implementation target |
| Refactoring procedure's "full test suite" step | doctrine | changed | NFR-005 uses the blast-radius rule (`NO_FULL_HEAVY_SUITES_IN_MISSION`); stated again in the plan |
