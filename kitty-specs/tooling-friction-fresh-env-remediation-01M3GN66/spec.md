# Mission Specification: Tooling friction — fresh-env derived-state & partition remediation

**Mission Branch**: `claude/tooling-friction-investigation-gpb1yl`
**Created**: 2026-09-27
**Status**: Draft
**Input**: Remediate the tooling-friction cluster that plagues contributors on fresh environments/worktrees/lanes — tracked in #4873, #4955, #5160, and #5113.

## Context & Root-Cause Theme

A grounding squad root-caused the four tickets. Three of them are facets of **one architectural defect**: *derived / append-only mission state is treated as authoritative-and-git-mergeable, and coord-vs-primary partition surfaces disagree about who owns a write.* The fourth is a dev-dependency packaging miss. The canonical Status Model already names the append-only event log (`status.events.jsonl`) as the sole authority and the snapshot (`status.json`) as a derived, regeneratable view (`status/reducer.py::materialize`); several seams never adopted that contract once `-X theirs` (#4892) stopped masking the divergence.

Scope decisions confirmed by the operator:
- **#5113**: only the fully-independent misleading-remedy-text fix lands here; the materialize-before-write change is deferred to the in-flight P1 mission `lane-branch-naming-authority-01M3EVC4` (#5108), which owns the `CoordinationWorkspace.resolve` naming/resolve authority it would touch.
- **Topology**: `single_branch`, so this remediation does not run on the coord/lane machinery it repairs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Green `make test-fast` from an isolated worktree (Priority: P1)

A contributor follows the mandated isolated-linked-worktree workflow and runs the required `make test-fast` baseline. Today three charter JSON error-contract tests fail because the production charter write-guard detects the real linked worktree before the tests' mocked conditions run, obscuring change-specific regressions. (#4873)

**Why this priority**: It blocks the *entry* signal every contributor relies on; the failure is loud, misattributed, and hits everyone on the mandated workflow.

**Independent Test**: From a `git worktree add` linked worktree, run `PWHEADLESS=1 pytest tests/cli/commands/test_charter_json_error_contract.py -q` — all pass.

**Acceptance Scenarios**:

1. **Given** a checkout inside a linked git worktree, **When** the charter JSON error-contract tests run, **Then** each asserts its intended error contract instead of the worktree-guard refusal.
2. **Given** the same tests running from a repository-root checkout, **When** they run, **Then** behaviour is unchanged (still green).

---

### User Story 2 - Lane worktree `make test-fast` has its test dependencies (Priority: P1)

A contributor runs `make test-fast` inside a lane worktree; its ephemeral `uv` venv is built without the `test` extra, so `pytestarch` is missing and architectural-style tests false-red on `ModuleNotFoundError` rather than a real regression. (#5160 friction 2)

**Why this priority**: A missing-dependency false-red is indistinguishable from a real break in raw pytest output and wastes contributor time on every fresh lane.

**Independent Test**: In a clean checkout, `uv sync --frozen` (no extras) then `uv run --frozen python -c "import pytestarch"` succeeds.

**Acceptance Scenarios**:

1. **Given** a plain `uv sync` (dev group, no `--all-extras`), **When** a lane worktree runs an architectural test, **Then** `pytestarch` imports and the test executes on its merits.
2. **Given** the pyproject shape guard, **When** it runs, **Then** it fails closed if any plugin that `make test-fast`/`test-full` needs without `--all-extras` is absent from the `dev` dependency group.

---

### User Story 3 - Lane allocation regenerates derived state instead of merging it (Priority: P1)

`spec-kitty agent action implement` (lane allocation) fails with "cannot auto-merge the recorded planning commit"/"dependency lane" whenever the *derived* `status.json` has diverged from the event log, because the allocator git-merges the stale snapshot instead of regenerating it from the union-merged log. (#5160 friction 1)

**Why this priority**: It blocks implementation on a routine, safe divergence of a disposable artifact — a hard stop with no operator-fixable cause.

**Independent Test**: Two branches with divergent committed `status.json` but union-able `status.events.jsonl`; `allocate_lane_worktree` completes and the resulting `status.json` equals `materialize(reduce(union events))`.

**Acceptance Scenarios**:

1. **Given** divergent derived `status.json` and union-able event logs, **When** the reuse / crash-recovery / fresh allocation paths run, **Then** allocation succeeds and the snapshot is regenerated from the merged log.
2. **Given** a genuine conflict in a human-authored path (`tasks/WP*.md`), **When** allocation runs, **Then** it still fails closed with the existing conflict error (no green-washing).

---

### User Story 4 - Branch integration reconciles append-only & derived mission state (Priority: P1)

Since #4892 dropped `-X theirs`, the mission→target squash correctly fails closed on genuine conflicts — but also blocks on derived/append-only artifacts that have no reconciling driver: `status.json`, `mission-events.jsonl`, `kitty-ops/lifecycle.jsonl`, `decisions/index.json`. Two of these are invisible to the C-006 completeness guard. (#4955)

**Why this priority**: It blocks legitimate merges on state that should reconcile deterministically, and the current guard silently classifies two artifacts as safe when they are not.

**Independent Test**: A both-sides-divergent squash integration reconciles `status.json` (re-materialize) and `mission-events.jsonl` (union) without blocking; the completeness guard enumerates every reconciled artifact.

**Acceptance Scenarios**:

1. **Given** both sides diverged on `status.json`, **When** the squash seam integrates, **Then** the snapshot is re-materialized from the merged event log and the merge proceeds.
2. **Given** both sides appended to `mission-events.jsonl`, **When** the squash seam integrates, **Then** the union driver reconciles it and it is enumerated by the C-006 guard.
3. **Given** the reconciliation class guard, **When** it runs, **Then** every canonical artifact carries a registered driver OR an explicitly documented non-divergent/re-materialized classification — no silent exemption.

---

### User Story 5 - Planning entry points agree on `feature_dir` (Priority: P2)

`spec-kitty agent context resolve --action tasks` returns a coord-worktree `feature_dir` while `check-prerequisites` returns the primary-checkout `feature_dir` for the same mission, so tasks authoring can silently split from where `finalize-tasks` reads. (#5160 friction 3)

**Why this priority**: The split is silent and corrupts where planning artifacts land; lower than P1 because it bites coord-topology missions specifically.

**Independent Test**: On a materialized coord-topology mission, `context resolve --action tasks --json` `feature_dir` equals `check-prerequisites --json` `FEATURE_DIR` (both primary).

**Acceptance Scenarios**:

1. **Given** a coord-topology mission, **When** both entry points resolve `feature_dir` for a planning action, **Then** they return the same primary-anchored directory.
2. **Given** a status-reading action (`status`/`analyze`/`accept`), **When** `context resolve` runs, **Then** it still resolves the coord status surface (no regression).

---

### User Story 6 - Coordination-materialization remedy text is actionable (Priority: P2)

On a fresh coord mission, `decision open`/`resolve` raises `CoordinationWorktreeUnmaterialized`, whose remedy text points at `spec-kitty doctor workspaces --fix` (which only removes husks and cannot materialize a worktree). (#5113 — remedy text only in this mission)

**Why this priority**: The misleading remedy sends operators toward improvised workarounds; the deeper materialize-before-write fix is deferred to #5108, but the remedy text is fully independent and cheap to correct now.

**Independent Test**: The `CoordinationWorktreeUnmaterialized` message names a `git worktree add …` command that actually materializes the coord worktree, not `doctor workspaces --fix`.

**Acceptance Scenarios**:

1. **Given** the unmaterialized-coord error is raised, **When** an operator reads the remedy, **Then** it names the concrete `git -C <repo> worktree add <worktree> <coord_branch>` command (mirroring the #2240 doctor hint).

### Edge Cases

- Lane allocation where BOTH the derived snapshot AND a human-authored file conflict: human conflict must still block; only the derived snapshot is auto-regenerated.
- `kitty-ops/lifecycle.jsonl` has no `event_id`, so it cannot reuse the generic event-log union engine — needs a bespoke union driver or an explicitly documented block, never a silent gap.
- `decisions/index.json` is a single JSON object (a fold of `decisions.events.jsonl`), so union does not fit — re-fold or documented block, with the guard classification re-decided rather than silently changed.
- Coord-less topologies (`single_branch`/`lanes`/flat) must be unaffected by any coord-partition change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Isolate charter-write-guard in JSON contract tests | As a contributor, I want the charter JSON error-contract tests to assert their contracts from any cwd so that `make test-fast` is green from an isolated worktree. | High | Open | [folded] | no — paired with a from-linked-worktree reproduction |
| FR-002 | Mirror `pytestarch` into the dev dependency group | As a contributor, I want lane-worktree venvs to carry every test plugin `make test-fast` needs so that architectural tests do not false-red. | High | Open | [build] | no — guard asserts presence, red without the mirror |
| FR-003 | Regenerate `status.json` in lane allocation | As an implementer, I want lane allocation to regenerate the derived snapshot from the union-merged event log so that a disposable-artifact divergence never blocks allocation. | High | Open | [build] | no — paired with a human-authored-conflict control that still blocks |
| FR-004 | Re-materialize/re-fold derived state on the squash seam | As an operator, I want the mission→target squash to reconcile derived/append-only mission state so that legitimate merges do not block. | High | Open | [build] | no — both-sides-divergence reproduction |
| FR-005 | Union driver for `mission-events.jsonl` across all four registry surfaces | As a maintainer, I want `mission-events.jsonl` reconciled by the canonical event-log union driver and seeded across registry/gitattributes/init/migration. | High | Open | [build] | no |
| FR-006 | Correct the C-006 reconciliation class guard classification | As a maintainer, I want every canonical mission artifact to be explicitly reconciled or documented-blocked, with none silently exempt. | High | Open | [ratchet] | no — guard fails on an unclassified artifact |
| FR-007 | `kitty-ops/lifecycle.jsonl` reconciliation decision | As a maintainer, I want the driver-less lifecycle log either given a bespoke union driver or an explicitly documented block, never a silent gap. | Medium | Open | [build] | no |
| FR-008 | `decisions/index.json` reconciliation decision | As a maintainer, I want the derived decisions index re-folded from its event log on integration, or an explicitly documented block, with the guard classification re-decided. | Medium | Open | [build] | no |
| FR-009 | Primary-anchor planning-action `feature_dir` in `resolve_action_context` | As an agent, I want `context resolve` and `check-prerequisites` to agree on the primary `feature_dir` for planning actions so that authoring and finalize read the same directory. | Medium | Open | [folded] | no — cross-entry-point agreement assertion |
| FR-010 | Actionable `CoordinationWorktreeUnmaterialized` remedy text | As an operator, I want the unmaterialized-coord error to name a command that actually materializes the worktree. | Medium | Open | [folded] | no — asserts `git worktree add`, not `doctor workspaces --fix` |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new merge-driver authority | Every driver change is seeded across all four bound surfaces (in-code registry, `.gitattributes`, init seed, upgrade migration); the four `test_*_superset*`/`test_declared_*` guards stay green. | Reliability | High | Open |
| NFR-002 | Single regeneration authority | Lane allocation and the squash seam share one `status.json` re-materialization helper (no second copy of the reduce→materialize logic). | Maintainability | High | Open |
| NFR-003 | Coord-less topologies unaffected | Changes to coord/partition surfaces are gated so `single_branch`/`lanes`/flat behaviour is byte-identical. | Reliability | High | Open |
| NFR-004 | Complexity ceiling ≤15 | New/edited functions stay at or below the aligned Ruff C901 / Sonar S3776 ceiling; extract helpers rather than exceed it. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No production change to the charter write-guard | #4873 is fixed by test isolation only; the guard-before-`find_repo_root` invariant (#4785 single canonical authority) is preserved. | Technical | High | Open |
| C-002 | #5113 remedy-text-only | The materialize-before-write change is out of scope here and belongs to #5108; only the remedy text and (optionally) a defensive CLI `except` arm land in this mission. | Technical | High | Open |
| C-003 | Canonical sources only | Merge drivers, templates, and reducers use the documented canonical seams; no improvised substitutes. | Technical | High | Open |
| C-004 | No test skip/disable to green | No test is skipped, disabled, quarantined, or green-washed to pass a gate. | Technical | High | Open |

### Key Entities

- **`status.json`**: derived reduced snapshot of `status.events.jsonl`; disposable, regeneratable via `status/reducer.py::materialize`; never authoritative.
- **`_MERGE_DRIVERS` registry** (`lanes/merge.py`): the C-006 governed driver set, seeded across four surfaces and bound by `test_merge_reconciliation_class_guard.py`.
- **Reconciliation class guard**: `tests/architectural/test_merge_reconciliation_class_guard.py`, enumerating canonical artifacts from `mission_runtime.artifacts` and asserting each carries a driver or an explicit non-divergent classification.
- **Placement seam / partitions**: coord vs primary; planning artifacts belong to primary, status to the resolved status surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `PWHEADLESS=1 pytest tests/cli/commands/test_charter_json_error_contract.py -q` passes from a linked worktree AND a root checkout — [folded] · no-op passable: no
- **SC-002**: `uv sync --frozen` (no extras) followed by `uv run --frozen python -c "import pytestarch"` exits 0, and the pyproject-shape guard fails closed on a removed mirror — [build] · no-op passable: no
- **SC-003**: A both-sides-divergent `status.json` no longer blocks lane allocation or the squash seam; the reconciled snapshot equals `materialize(reduce(union events))` in both paths — [build] · no-op passable: no
- **SC-004**: The C-006 reconciliation class guard enumerates and classifies every canonical mission artifact (incl. `mission-events.jsonl`); no artifact is silently exempt — [ratchet] · no-op passable: no
- **SC-005**: `context resolve --action tasks` and `check-prerequisites` return the same primary `feature_dir` on a coord-topology mission; status actions still resolve the coord surface — [folded] · no-op passable: no
- **SC-006**: The `CoordinationWorktreeUnmaterialized` remedy text names a working `git worktree add` command; no reference to `doctor workspaces --fix` for materialization — [folded] · no-op passable: no
