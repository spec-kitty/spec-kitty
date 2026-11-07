# Mission Specification: Provision the move-task git-validation fixture's charter (#7073)

**Mission Branch**: `issue-7073-move-task-fixture-charter-provisioning`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue #7073 — "[bug] 8 move-task git-validation tests hard-fail with UnknownMissionTypeError on an unprovisioned fixture"; operator guidance: "Fix the subject, not the assertion", and do not collide with #7057/PR #7100 which re-pins a neighbouring fixture in the same module.

## Context and grounding (what the issue is, after reproduction)

`tests/tasks/test_move_task_git_validation_unit.py` builds its project with `git_repo_with_worktree`,
which writes `.kittify/config.yaml` containing only `# Config\n` and never provisions the project charter.
`charter.activation.pack_context._read_activated_mission_types` is deliberately total (absent key →
`frozenset()`, no all-four backfill — #2657), so on that fixture `existing_mission_types()` is `[]` and
`resolve_mission_type_context(repo, mission_type="software-dev")` raises `UnknownMissionTypeError`.

The review-ward guard the module exercises reads the `code_producing` capability through
`charter.activation.api.code_producing_for` (`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py:956`),
which catches that exception, logs it at WARNING with `exc_info=True` (the traceback the issue quotes) and
returns the built-in fallback. So every one of these nodes exercises the *fallback* branch of the capability
read, not the resolved mission-type profile a real project has. The reported "hard-fail" is that logged
traceback plus the downstream node failures.

Reproduced on `main` @ `d18c4f1d58`: `uv run --frozen pytest -q -p no:randomly -n0
tests/tasks/test_move_task_git_validation_unit.py` → **8 failed, 7 passed**, with the
`UnknownMissionTypeError` traceback in the output and the 8 nodes stopping at
`IMPLEMENTATION_MISSING` (that gate refusal is #7057's subject, fixed by the still-open PR #7100).
With #7100's fixture re-pin applied locally, all 15 pass **and the `UnknownMissionTypeError` fallback
warning still fires on every node** — which is exactly this issue's subject.

**Scope boundary.** PR #7100 re-pins the same helper's *evidence* half (`owned_files` on WP01, the lane
branch's `Add implementation` commit writing `src/implementation.py`, and one node's `--agent`). This mission
touches the *charter provisioning* half: the `.kittify/config.yaml` write and one new regression test. The two
edits are textually disjoint inside `git_repo_with_worktree`, and neither needs the other to be correct.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The move-task git-validation fixture is a provisioned project (Priority: P1)

A maintainer runs the out-of-matrix `tests/tasks/` suite. The fixture project that the 15 move-task
git-validation nodes build should look like a project `spec-kitty init` produced — including an activated
mission type — so the capability the review-ward guard reads comes from the resolved `software-dev` profile
rather than from a swallowed resolution failure.

**Why this priority**: it is the issue's stated remedy ("the fixture must provision
`mission_type_activations`") and it removes the only place in this module where production code takes an
exception path that no assertion covers.

**Independent Test**: run the module and assert that the fixture's mission type resolves through the
pre-existing resolver, and that the capability read records no fallback warning.

**Acceptance Scenarios**:

1. **Given** the shared `git_repo_with_worktree` fixture, **When** `resolve_mission_type_context(repo_root,
   mission_type="software-dev")` is called, **Then** it returns a bundle whose `mission_type` is
   `software-dev` and whose `action_sequence` is the real curated sequence (non-empty), with no
   `UnknownMissionTypeError`.
2. **Given** the same fixture, **When** `charter.activation.api.code_producing_for(repo_root,
   "software-dev")` is called at WARNING capture level, **Then** it returns `True` and
   `charter.activation.mission_type_profiles` logs no record — in particular no
   "using the built-in default" fallback warning.
3. **Given** the fixture is provisioned, **When** the whole module runs, **Then** the 15 existing node ids,
   decorators and assertions are unchanged and the nodes fail/pass exactly as they do on the base commit.

---

### User Story 2 - Provisioning does not move the module's red/green baseline (Priority: P2)

Whoever lands PR #7100 and this mission must not discover a new interaction between them: this change is
behaviour-neutral for the 15 nodes and changes no `src/` file.

**Why this priority**: the mission must be reviewable as test-infrastructure fidelity, not as a behaviour
change smuggled in beside a red suite.

**Independent Test**: compare the node set and the failing-node set before and after the fixture change on the
same base commit; `git diff <base>..HEAD -- src/` must be empty.

**Acceptance Scenarios**:

1. **Given** the base commit's module state, **When** the fixture is provisioned, **Then** `pytest
   --collect-only` reports the same 15 node ids and the same 8 nodes fail with the same
   `IMPLEMENTATION_MISSING` message that #7057/PR #7100 owns.
2. **Given** the branch, **When** `git diff origin/main..HEAD -- src/` runs, **Then** it is empty.

---

### Edge Cases

- **Provisioning is idempotent**: `provision_default_mission_type_activations` writes only when the key is
  absent. Calling it on an already-provisioned project must be a no-op (returns `False`) and must not create a
  second activation surface.
- **Commit shape must not change**: the fixture's commit count and the `Add implementation` head subject are
  asserted by existing nodes. The provisioned ledger file must therefore land inside the fixture's *Initial
  commit*, i.e. provisioning runs before the first `git add .` / `git commit`.
- **Ledger target, not a hand-written key**: on a fresh project the activation authority is
  `.kittify/charter/activation.yaml` (ADR `2026-10-19-1`), not `config.yaml`. Hand-writing the key into `config.yaml`
  would create a second, divergent seeder; the fixture must use the production provisioner.
- **PR #7100 overlap**: the two edits sit in the same helper. Whichever lands first, the other must apply
  without textual conflict (mine is the `config.yaml` write + a new test; #7100's is the WP01 frontmatter,
  the lane commit and one `--agent` flag).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fixture provisions its charter | As a maintainer, I want the move-task fixture project provisioned through the production provisioner so that mission-type resolution succeeds instead of falling back. | High | Open | [build] | no |
| FR-002 | Pin resolution with a regression test | As a maintainer, I want one regression test that resolves the fixture's mission type and asserts no fallback warning so that an unprovisioned fixture fails loudly instead of degrading silently. | High | Open | [build] | no |
| FR-003 | Node set and behaviour unchanged | As a maintainer, I want the 15 existing node ids, decorators, assertions and their fail/pass set unchanged so that this mission lands as fixture fidelity, not behaviour drift. | High | Open | [ratchet] | yes — paired with FR-002, whose positive control fails on a no-op branch |
| FR-004 | No production change | As a maintainer, I want `git diff origin/main..HEAD -- src/` empty so that the fix cannot alter the guard it is exercising. | High | Open | [ratchet] | yes — paired with FR-001, which requires the fixture change |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Module runtime stays flat | The module's wall time on this host stays under 180 s for all 15 nodes (base measured 115–137 s); provisioning adds one small YAML write at fixture setup, not per node. | Performance | Medium | Open |
| NFR-002 | No swallowed production exception remains unasserted | Zero `charter.activation.mission_type_profiles` WARNING records (the `exc_info=True` fallback) are emitted while the module runs. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-side only | No `src/` edit; no gate weakened, no skip, xfail, deselection, marker or `--force` added. | Technical | High | Open |
| C-002 | Disjoint from PR #7100 | This mission's hunks in `git_repo_with_worktree` must not overlap #7100's (`owned_files` frontmatter, lane commit, `--agent` flag). | Technical | High | Open |
| C-003 | Canonical provisioner only | Provision through `specify_cli.provisioning.default_charter.provision_default_mission_type_activations` (used via `tests/_factories.provision_test_charter`), never a second hand-rolled seeder. | Technical | High | Open |

### Key Entities

- **Fixture project (`git_repo_with_worktree`)**: a temporary git repo the module builds, containing
  `.kittify/`, `kitty-specs/017-test-feature/` (lane manifest, `meta.json`, WP01 task file) and one lane
  worktree. Its charter state is the subject of this mission.
- **Activation ledger (`.kittify/charter/activation.yaml`)**: the provisioned holder of mission-type
  activation for a fresh project (the activation-ledger seam, ADR `2026-10-19-1`); the file the fixture must gain.
- **Resolved mission type**: the bundle `resolve_mission_type_context` returns (`mission_type`,
  `action_sequence`, `code_producing`, `provenance`); the capability the review-ward guard consumes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the base commit with only this mission's fixture change applied, the new regression test goes from failing with `UnknownMissionTypeError` to passing, and `pytest --collect-only -q` still reports 15 node ids. — [build] · no-op passable: no
- **SC-002**: A full module run emits zero `charter.activation.mission_type_profiles` WARNING records and still shows the same 8 `IMPLEMENTATION_MISSING` failures on a base without #7100's re-pin (and 15/15 with it applied). — [ratchet] · no-op passable: no
- **SC-003**: `git diff origin/main..HEAD -- src/` is empty and the diff touches only the test module, a changelog fragment and the mission's own records. — [ratchet] · no-op passable: yes — paired with SC-001, which fails on a no-op branch
