# Tasks: Mission creation degod

**Mission**: `mission-creation-degod-01M44467` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)
**Planning base / merge target**: `issue-5634-mission-creation-degod` · **Topology**: lanes

Subtask completion is event-sourced: `spec-kitty agent tasks mark-status Txxx --status done`. The rows below are reference rows, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Golden harness: real-repo fixture, observable capture, whitelisted normaliser, snapshot I/O | WP01 | |
| T002 | Success cells: branch-flat and coordination-routed families | WP01 | [P] |
| T003 | Success cells: protected single_branch, owned checkout, flag cross-products | WP01 | [P] |
| T004 | Refusal cells (13 named + malformed protection config) with post-state capture | WP01 | |
| T005 | Capture on base, regen reproducibility, per-dimension planted breaks | WP01 | |
| T006 | CLI golden harness (CliRunner + chdir, zero patches) | WP02 | |
| T007 | Derived default-topology cells incl. no-origin/HEAD fallback | WP02 | |
| T008 | One success + one refusal CLI smoke per behaviour family | WP02 | |
| T009 | Decision-level topology fallback pin naming both Primary Branch inputs | WP02 | [P] |
| T010 | Protected-mint branch coverage (checkout -b failure) | WP03 | [P] |
| T011 | Meta/events branch coverage (corroboration, payload mismatch, coord commit failure, bootstrap skip) | WP03 | [P] |
| T012 | Duplicates/rollback branch coverage (missing meta, abandonment read failure, neighbour guard, rollback early return) | WP03 | [P] |
| T013 | FR-011 invariant pins not observable in the snapshot | WP03 | |
| T014 | Static patch scanner (f-strings, constants, object forms; any namespace for family-read names) | WP04 | |
| T015 | Runtime patch-application counter (opt-in pytest plugin) | WP04 | |
| T016 | `patched_names_on()` API for the routing check | WP04 | |
| T017 | Self-test with positive and negative controls; baseline report | WP04 | |
| T018 | `mission_creation_decisions.py` skeleton + protection/applies cores | WP05 | |
| T019 | Protected-mint facts/decision core, wired into the mint | WP05 | |
| T020 | Coordination-routed predicate: one definition for the two topology-based sites (third site per WP05 fold 4) | WP05 | |
| T021 | Meta flag patch core, wired into `_build_create_meta` | WP05 | |
| T022 | Duplicate match + abandonment cores, wired | WP05 | |
| T023 | Rollback cores (orphan plan, coord rollback action, disposable refusal), wired | WP05 | |
| T024 | Scaffold-commit outcome + created/uncommitted file-set cores, wired | WP05 | |
| T025 | Purity AST check + positive control; per-core planted-break evidence | WP05 | |
| T026 | Scripted verbatim move into leaf modules + façade re-exports + exactly-once proof | WP06 | |
| T027 | Patch-interception routing (`_mc.`) in leaves | WP06 | |
| T028 | Family source helper + self-test | WP06 | |
| T029 | Family checks: re-export identity, no module-scope façade import, logger pin, local-import pin | WP06 | |
| T030 | Routing set-equality check + two planted controls | WP06 | |
| T031 | Re-pin the architectural gates (6) | WP06 | |
| T032 | Module map (façade docstring + docs) and CHANGELOG Internal entry | WP06 | |
| T033 | Protection resolved at most once, memoised at first-use point | WP07 | |
| T034 | Protected mint invoked from the orchestrator, not the meta builder | WP07 | |
| T035 | Typed rollback journal replaces the list holder | WP07 | |
| T036 | Split `_build_create_result` fan-out from the pure file sets | WP07 | |
| T037 | Structural checks: one predicate definition, no mint in the meta builder | WP07 | |
| T038 | `is_worktree_context` patches → allow flag / chdir; 3 refusal guards on real worktrees | WP08 | |
| T039 | `locate_project_root` dead patches retired with coverage-context proof | WP08 | |
| T040 | `is_git_repo` patches retired; guard re-proved by planted break | WP08 | |
| T041 | `get_current_branch` patches → real `main` repos (faked-branch tests rewritten) | WP08 | |
| T042 | Routing list update + interim census report | WP08 | |
| T043 | `_commit_feature_file` patches → real commits / adapter fault injection | WP09 | |
| T044 | `ULID` / `now_utc_iso` → injected identity and clock; sleeps removed | WP09 | |
| T045 | `preflight_commit`, `safe_commit`, `_commit_create_scaffold`, `_consume_pending_origin_if_present` → owning modules | WP09 | |
| T046 | Global `subprocess.run` patch → adapter fault injection | WP09 | |
| T047 | `test_agent_feature.py` create assertions → golden CLI smoke; final routing list | WP09 | |
| T048 | Final census report with per-name disposition table | WP09 | |

## Phase 1 — Behaviour freeze (test-only; parallel)

### WP01 — Core golden behaviour matrix

- **Goal**: freeze today's observable `create_mission_core` behaviour with zero patches (FR-001, FR-011 snapshot dimensions, SC-001).
- **Priority**: P1 (the MVP; every later WP is judged against it).
- **Independent test**: green on the unchanged base; red on one planted break per captured dimension.
- **Subtasks**: T001, T002, T003, T004, T005.
- **Dependencies**: none.
- **Prompt**: [tasks/WP01-core-golden-matrix.md](tasks/WP01-core-golden-matrix.md) (~330 lines).
- **Risks**: normaliser too broad; fixture cost; the #5706 fan-out leak (baseline-red).

### WP02 — CLI golden cells and topology fallback pin

- **Goal**: pin the CLI surface (envelope, error code, exit code) and the derived default topology, including the no-origin/HEAD fallback (FR-002, FR-010).
- **Subtasks**: T006, T007, T008, T009. **Dependencies**: none.
- **Prompt**: [tasks/WP02-cli-golden-topology-pin.md](tasks/WP02-cli-golden-topology-pin.md) (~240 lines).

### WP03 — Uncovered decision branches and create invariants

- **Goal**: cover the ten untested branches and the FR-011 invariants that the snapshot cannot observe (FR-008, FR-011, SC-004).
- **Subtasks**: T010, T011, T012, T013. **Dependencies**: none.
- **Prompt**: [tasks/WP03-branch-coverage-invariants.md](tasks/WP03-branch-coverage-invariants.md) (~260 lines).

### WP04 — Patch census tool

- **Goal**: a committed reporting tool (not a gate) that counts static and runtime patch use for the module family. It also exposes the patched-name set the WP06 routing check needs (NFR-004 baseline, FR-005 input).
- **Subtasks**: T014, T015, T016, T017. **Dependencies**: none.
- **Prompt**: [tasks/WP04-patch-census.md](tasks/WP04-patch-census.md) (~220 lines).

## Phase 2 — Decision cores and the split (sequential)

### WP05 — Pure decision cores, wired in place

- **Goal**: introduce `mission_creation_decisions.py` and make the existing functions delegate to it, without moving anything else (FR-003, FR-009 predicate).
- **Subtasks**: T018–T025. **Dependencies**: WP01, WP02, WP03.
- **Prompt**: [tasks/WP05-pure-decision-cores.md](tasks/WP05-pure-decision-cores.md) (~420 lines).

### WP06 — Verbatim module split, routing and gate re-pins

- **Goal**: move each responsibility to its leaf module verbatim, route patched names through the façade, and re-pin every gate (FR-004, FR-005, FR-006).
- **Subtasks**: T026–T032. **Dependencies**: WP04, WP05.
- **Prompt**: [tasks/WP06-module-split-routing-gates.md](tasks/WP06-module-split-routing-gates.md) (~430 lines).

### WP07 — Behaviour-neutral seam cleanups

- **Goal**: protection resolved once (at first use), mint called from the orchestrator, typed rollback journal, fan-out split (FR-009).
- **Subtasks**: T033–T037. **Dependencies**: WP06.
- **Prompt**: [tasks/WP07-seam-cleanups.md](tasks/WP07-seam-cleanups.md) (~250 lines).

## Phase 3 — Tests onto the seams (sequential)

### WP08 — Retire the environment patch stack

- **Goal**: remove the `is_worktree_context` / `locate_project_root` / `is_git_repo` / `get_current_branch` patch stack (203 sites) using real repos, allow flags and proofs (FR-007).
- **Subtasks**: T038–T042. **Dependencies**: WP07.
- **Prompt**: [tasks/WP08-retire-environment-patch-stack.md](tasks/WP08-retire-environment-patch-stack.md) (~300 lines).

### WP09 — Move commit, identity and effect patches to their seams

- **Goal**: move the remaining patches to their owning modules or to injected inputs, and report the final census against NFR-004 (FR-007, SC-003).
- **Subtasks**: T043–T048. **Dependencies**: WP08.
- **Prompt**: [tasks/WP09-move-effect-patches-final-census.md](tasks/WP09-move-effect-patches-final-census.md) (~320 lines).

## Dependency graph

```
WP01 ─┐
WP02 ─┼─► WP05 ─┐
WP03 ─┘         ├─► WP06 ─► WP07 ─► WP08 ─► WP09
WP04 ───────────┘
```

## Parallelization and MVP

- WP01–WP04 run in parallel lanes (disjoint files, test-only).
- WP05 onward is a chain. They share `src/specify_cli/core/mission_creation*.py` and the patch-carrying test files, and the dependency order exempts them from the ownership-overlap check.
- **MVP**: WP01. It is the behaviour-preservation proof that makes every later WP reviewable.

## Post-tasks squad findings (disposition)

| Finding | Lens | Disposition | Evidence |
|---|---|---|---|
| Golden fixture helpers outside the freeze set (WP08 edits `coord_mission.py`) | reviewer | accepted | WP01 fold 1 (vendored builder), spec NFR-001 freeze set, WP08/WP09 fold 1 |
| No re-capture protocol for a rebase that brings real upstream change | reviewer | accepted | plan "Rebase protocol", WP06 fold 1, NFR-001 |
| Routing check loopholes (aliases, module scope, other façade aliases, getattr) | reviewer | accepted | WP06 fold 2 |
| Census misses laundering forms; hand-listed read names | reviewer | accepted | WP04 folds 1–4 |
| Not one planted break per capture key; padding risk; unreachable-cell escape | reviewer | accepted | WP01 folds 5–7 |
| "Today's order, stopping early" unverifiable; "resolved at most once" unproven | reviewer | accepted | WP05 fold 3, WP07 fold 1 (`GIT_TRACE` command-sequence tests) |
| Per-gate planted removal missing | reviewer | accepted | WP06 fold 4 |
| Exactly-once comparison flags every routed function; no frozen façade attribute list | reviewer | accepted | WP06 T026 text, WP06 fold 3 |
| Free-form planted-break records | reviewer | accepted | "as `git diff` patch blocks" in every WP's folds |
| mid8-dependent cells flaky under load | implementer | accepted | WP01 fold 3 (predict-then-plant with assertion) |
| Normaliser cannot handle a second mission's mid8 | implementer | accepted | WP01 fold 2, WP02 fold 2 |
| "Create the same slug twice" does not refuse (genesis prior is abandoned) | implementer | accepted | WP01 T004 #1, WP02 T008, WP03 fold 2 |
| `exc_type` qualified name breaks after the move | implementer | accepted | WP01 T001 (`__qualname__` only) |
| WP05 purity ban contradicts the cores that need `specify_cli.git` types | implementer | changed | WP05 Objectives + fold 1 (runtime I/O ban, `TYPE_CHECKING` allowed, classification stays in adapters) |
| Dead-symbol gate covers decision variants | implementer | accepted | WP05 fold 2 |
| Unprotected unborn target creates instead of refusing | implementer | accepted | WP01 T004 #4 |
| Malformed config has two raise points | implementer | accepted | WP01 fold 4, WP07 fold 2 |
| CLI envelope `spec_kitty_version` would freeze a version | implementer | accepted | WP02 fold 1 |
| tasks README vs spec.md commit state | implementer | accepted | WP03 invariant 5 |
| The three predicate "copies" differ | implementer | accepted | WP05 fold 4 |
| Issue-matrix finalization unassigned | planner | changed | the orchestrator sets the #5634 terminal verdict at accept (code WPs cannot own `kitty-specs/`); row re-pointed to WP09 |
| WP03 files in WP08 ownership | planner | accepted | removed from WP08; WP09 keeps them (it moves their fault injections) |
| Trim WP08/WP09 `owned_files` | planner | deferred_with_rationale | which files each WP edits is only known once WP06 lands; sequential ownership is legal and the review records the touched set |
| Split WP06 | planner | deferred_with_rationale | the gate re-pins must be atomic with the move (otherwise the surface-resolver collection error turns about 20 gates red mid-chain), and the family checks are WP06's own review evidence |
