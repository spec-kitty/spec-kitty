# Code grounding — #5573: a re-finalize must never move a started work package

- **Mission:** `frozen-started-lanes-01M444FM` (topology `lanes`)
- **Base:** `origin/main` @ `9adc6880` (2026-10-04), CLI `4.0.0rc6` installed editable from this checkout
- **Point-cut:** pre-spec, brownfield; read-only grounding squad
- **Reader:** the mission's specifier, planner, implementer and reviewer (software-engineer persona)

The squad had five profile-loaded, read-only delegates. Each ran `spec-kitty agent profile show <id>` and
`spec-kitty charter context --action <action>` before working.

| Lens | Profile | Action context |
|---|---|---|
| Reproducer | `python-pedro` | implement |
| Root-cause tracer | `debugger-debbie` (+ procedure `disciplined-defect-diagnosis`) | implement |
| Related-issue researcher | `researcher-robbie` | specify |
| Architect | `architect-alphonso` | plan |
| Test-suite | `reviewer-renata` | review |

All file:line references are to the base commit. #5679 split `mission_finalize.py` into phase modules on
2026-10-04, so the line numbers quoted in the issue body have moved.

---

## 1. Reproduction (live, through the CLI entry point)

The issue's own reproducer runs unchanged against this checkout. It uses real `spec-kitty agent mission finalize-tasks`
subprocesses, and the production `allocate_lane_worktree` / `emit_status_transition` for steps 2 and 5. It needed no
adaptation (`make_mission` now lives at `tests/_factories/__init__.py:65`).

**Starting state for every arm:** lane-a = [WP01] (`a.py`), lane-b = [WP02] (`b.py`). WP02 is allocated, has a commit
`b = 42` on lane-b, and its status is `claimed` → `in_progress`.

| Arm | `finalize-tasks` | WP02's lane after | Verdict |
|---|---|---|---|
| `--amend` (WP01 also owns `b.py` and depends on WP02) | **exit 0**, `result: success`; both WPs collapse into **lane-a** (`write_scope_overlap`) | lane-b → **lane-a** | **REPRODUCES** |
| `--retire-scope` (WP01 canceled, `owned_files: []`) | exit 1, `OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES` | stays lane-b | #3432 residual reproduces |
| no flag (control) | exit 0, lanes unchanged | stays lane-b | control holds |
| `--amend`, WP02 only `claimed` (no commit) | exit 0 | lane-b → lane-a | re-lettering reproduces; the old lane-b worktree and branch are orphaned without a warning |
| `--amend`, WP01 started instead of WP02 | exit 0, WP01 keeps lane-a | — | does not reproduce: the outcome depends on the tie direction |

**What the user sees next.** `spec-kitty implement WP02 --mission <slug>` exits 1 with `LaneWorkTipUnknownError`:
"cannot allocate lane 'lane-a' for 'WP02': its branch … and worktree are both gone". The work is still on
`kitty/mission-…-lane-b`, but the manifest no longer points to it. The error's "context cleanup and retry" advice would
restart WP02 on an empty lane-a.

The finalize JSON also hides the move: it reports `unchanged_wps: [WP02, WP01]` and `updated_wp_count: 0`.

Logs: the squad scratchpad (`repro.py`, `log-*.txt`). They are not committed; the red-first test in this mission
replaces them.

## 2. Root cause (disciplined diagnosis, falsified alternatives)

### Call path

1. `mission.py:336` → `finalize_tasks` (`mission_finalize.py:1028`).
2. The ownership gates run: the bootstrap loop at `mission_finalize_bootstrap.py:340`, the #3432 guard at `:208-214`,
   and `_project_lane_inputs` at `:536`.
3. `_run_commit_pipeline` (`mission_finalize_commit.py:608`) writes status first: canonical events and bootstrap at
   `:690-700`. It then computes lanes at `:702`.
4. `mission_finalize_lanes._compute_and_write_lanes` (`:30`) resolves `planning_commit_sha`
   (`_execution_has_begun`, `mission_finalize_planning_pin.py:42`).
5. It then calls `lanes/compute_and_persist.compute_and_write_lanes` (`:102`), which reads `previous_lanes` (`:190`)
   and calls `compute_lanes` (`lanes/compute.py:646`).
6. `compute_lanes` calls `_assign_stable_lane_ids` (`:847`, defined at `:505`).
7. `write_lanes_json` (`compute_and_persist.py:238`) writes the manifest.
8. On the next allocation, `allocate_lane_worktree` composes the branch from the new lane id, finds nothing there, and
   `_refuse_if_lane_destroyed` raises `LaneWorkTipUnknownError` (`worktree_allocator.py:525`).

### The wrong decision point

The tie-break alone is not the defect. The defect is that **lane computation has no lifecycle input at all**: it
rebuilds lane identity from WP-membership overlap only. It reads status once (`planning_pin.py:101`,
`get_all_wp_lanes`) and reduces it to a single boolean, which only decides whether to preserve `planning_commit_sha`
(the #3311 fix). Three code paths in `_assign_stable_lane_ids` can then rebind a started WP; all three were confirmed by
calling the function directly:

| # | Path | Location | Effect |
|---|---|---|---|
| H1 | Tie | `compute.py:537-544`: strict `>` over `sorted(existing.items())` | lowest lane id wins (the issue's case) |
| H2 | Greedy order | `:534-546` | an earlier group with no started WP takes the started WP's old id (probe: `['lane-b','lane-a']`) |
| H3 | Re-mint | `_next_free_lane_id`, `:489/:551` | only ids claimed in this run are reserved, so an orphaned old id, whose branch still holds another WP's commits (including canceled ones), goes to a new group |

**Falsified: "the allocator should tolerate a moved lane".** The branch and the worktree are keyed only on the lane id
(`branch_naming.py:507`, `.worktrees/<slug>-lane-<id>`). A started WP's work lives on its old lane's branch and its tip
ref `refs/spec-kitty/lane-tip/<branch>`. Changing a started WP's lane id is therefore **always** harmful. It does one of
three things:
- strands the work (`LaneWorkTipUnknownError` / `DestroyedLaneError`);
- rebinds another WP onto a branch that carries foreign commits;
- poisons the #5046 per-WP attribution. Every transition stamps `policy_metadata["lane_head"]` from the lane that
  `lanes.json` maps the WP to (`status/lane_head.py`). After a move, later stamps come from a different branch, so
  `consolidation/wp_attribution.py` sees a contradiction and consolidate refuses.

### "Has execution begun?" today

`mission_finalize_planning_pin.py:42-110` (`_execution_has_begun`) is:

- **current-state:** `any(lane != PLANNED)`. It misses a WP that worked and was then reset. The FSM allows
  `in_progress→planned`, `in_review→planned` and `approved→planned`.
- **fail-open:** it returns `False` on an unreadable surface or a `StoreError` (`:96`, `:104`).
- **duplicated:** `migration/mission_state.py:1498` (`_execution_has_begun_in_snapshot`) restates the same rule.

### Cancellation projection (context for the #3432 decision)

`_project_lane_inputs` (`mission_finalize_bootstrap.py:543`) and `_lane_computation_empty_input_error` (`:592`) read the
**retired frontmatter `lane`** field. `read_wp_frontmatter` never fills it from status (`status/wp_metadata.py:620-650`),
so a WP canceled through the event log is still lane-eligible. Tests pin the frontmatter form
(`test_mission_finalize_phases.py:147,168`, `tests/integration/test_owned_lifecycle_acceptance_finalize.py:313-327`).

## 3. When can "a started WP keeps its lane id" be satisfied?

| # | Scenario | Satisfiable? | Handling |
|---|---|---|---|
| 1 | A group with one started WP ties or loses on overlap (#5573) | yes | the started WP's old id wins |
| 2 | A group with no started WP would take a started WP's id (greedy) | yes | pinned groups claim their ids before overlap read-back |
| 3 | A fresh mint would reuse an orphaned id whose branch holds work | yes | never mint an id whose prior lane held a started WP |
| 4 | Two started WPs that shared one lane are split apart by an amendment | yes, constrained | started WPs that share a prior lane stay together |
| 5 | One group holds started WPs from two different prior lanes | **no** | **refuse before writing** |
| 6 | A planned WP joins a started WP's lane (the intended #5573 outcome: WP01 joins lane-b) | yes | allowed; topological order puts WP01 after WP02 |
| 7 | A started WP disappears from the task set (WP file removed) | **no** | **refuse**: the work would be stranded; cancel it instead |
| 8 | A started WP changes kind (code ↔ planning artifact), crossing the `lane-planning` boundary | **no** | **refuse** |
| 9 | Done or approved WPs | yes | count as started (their lane branch holds content consolidation must merge) |
| 10 | The status log is unreadable while a previous `lanes.json` exists | — | **fail closed** (refuse), unlike `_execution_has_begun` |

## 4. Where the structural fix belongs (architect)

**Owner of the invariant:** `specify_cli.lanes.compute`, which stays pure (no git, no `meta.json`). It takes a new
already-resolved constraint input. The finalize IO shell gathers the evidence, the same pattern it uses to supply
`planning_commit_sha`. No layer move is needed: `lanes`, `status`, `cli` and `migration` all live inside `specify_cli`,
and `lanes → status` facade imports already exist (`lanes/claim_base.py:155`).

- **Compute.** `compute_lanes(..., frozen_membership: Mapping[wp_id, lane_id])` makes four changes:
  - Pass 0, before overlap read-back, binds each group to its started members' single recorded lane id.
  - Pinned ids are reserved from minting.
  - Started lane-mates are pre-unioned.
  - On scenarios 5, 7 and 8 it raises a typed `LaneComputationError` subclass carrying a `ClassVar` `error_code`.
    The precedent is `LaneDependencyCycleError` (`compute.py:218`, `LANE_DEPENDENCY_CYCLE`).
- **Writer chokepoint.** `compute_and_write_lanes` re-asserts the invariant before `write_lanes_json`, at the same point
  as the `assert_topology_matches_manifest` precedent (`compute_and_persist.py:216`).
- **Before the first write.** Today lanes are computed *after* the status writes
  (`mission_finalize_commit.py:690-716`), so a refusal there relies on the #5662 restore path. The refusal must instead
  happen in a read-only preflight before any write, and `--validate-only` must report it too.
- **CLI.** The JSON envelope follows the existing convention, `{"error", "error_code", ...}` through `_emit_json`, exit 1,
  `lanes.json` byte-unchanged. There is no central code registry. Codes live as class attributes; operator docs go in
  the glossary (`docs/context/topology.md`) and the CHANGELOG.

**Rejected alternative: a post-hoc diff in finalize** (compare the new and old membership of started WPs, refuse on a
difference). The heuristic would remain the deciding authority, and it would *refuse* the issue's own reproduction
instead of preserving WP02 on lane-b.

**Also rejected:**
- *Freeze all lanes once execution has begun.* This contradicts the supported amendment of unstarted WPs (#4141, ADR
  `2026-07-29-1`).
- *Let compute read status or git itself.* This breaks the documented purity of compute.

**Governing decisions:**
- **ADR 3.x `2026-07-29-1`:** finalize-tasks is the single writer of `lanes.json`, and re-running it is supported.
- **ADR 3.x `2026-09-26-2`:** degraded input is "migrated or refused, never rescued by a second code path". FR-011 keeps
  `mission_branch` byte-identical on re-finalize.
- **terminus-merge-integrity FR-010 / PP-F5 (#4945):** "a lane's identity is bound to its git branch at creation and
  never re-derived positionally". This binds *lane id ↔ branch*. It does not cover *started WP ↔ lane membership*, and
  that gap is #5573.

The squad recommends a new 4.x ADR recording this invariant.

## 5. Test suite: why the defect escaped, and the harness to use

**Why it escaped:**
- `test_finalize_provenance_guard.py:300-354` (`test_execution_begun_path_does_not_write_status_json`) **already runs the
  exact #5573 scenario**: it seeds WP02 on lane-b as started and applies a collapsing amendment. It asserts only
  status-file hashes. One lane-id assertion would have caught the bug.
- `test_issue_3311_finalize_rewrites_active_lanes.py:78` promises "preserves established lanes" in its name, but asserts
  only `planning_commit_sha` (`:152`). It also seeds WP01, which wins the tie anyway. Its docstring (`:17-20`) records
  "lane collapse does not reproduce"; #5573 disproves that.
- `tests/lanes/test_lane_identity.py::TestStableLaneIdentity` covers only one-to-one remove/add mappings. No test covers
  a merge, a split or a tie, and none can say "started", because `compute_lanes` takes no lifecycle input.
- `tests/terminus/test_repro_4945.py` plants commits directly and never runs finalize.
- Both `_run_finalize` helpers (`test_finalize_provenance_guard.py:72`, `test_issue_3311…:71`) swallow the exit code, so
  a refusal and a success look the same.

**Harness for the red-first test.** Use the `test_finalize_tasks_commit_surface.py` pattern: a real `finalize_tasks`
with real git, no commit-router mock, and the exit code captured. Add a plain `LANES` mission
(`make_mission(topology=MissionTopology.LANES)`), because `COORD_TOPOLOGIES` excludes it. Lane allocation follows
`test_refinalize_mission_branch.py:140`. Measured cost is about 1.5–2 s per case.

**Markers:**
- end-to-end test: `integration` + `git_repo` (+ `regression` once fixed);
- compute-level tests: `fast`.

**Property test.** `hypothesis` is not a dependency, and the supply-chain tactic says not to add one. Use a
`parametrize` over `itertools` permutations instead; the precedent is
`tests/terminus/test_terminus_reconciliation_property.py:124`. The invariant: a started WP keeps its lane id, or the
run refuses.

**Baseline:** `pytest tests/lanes -n 4 --dist loadfile` gives 714 passed, 1 skipped, 0 failed in 69.7 s.

## 6. Related issues (researcher)

| Issue | Classification | Reason |
|---|---|---|
| #3311 (closed) | cross-ref: origin | its "Expected" text is the bar a fix must meet: keep the lane, or refuse with an amendment path |
| #4945 / PR #5020 (closed) | cross-ref, regression guard | added the lane-id ↔ branch read-back; its WP-removal reproducer must stay green |
| #3432 (closed; residual) | **deferred** (decision below) | same family, different mechanism and blast radius |
| #5080 (open) | cross-ref | complementary half of "lane identity is an invariant" (allocator/`--base` side); not a superset |
| #5539 (open) | cross-ref | re-finalize mid-mission; a cached workspace context keeps stale `lane_wp_ids`. Same theme, different code site (`workspace/context.py`) |
| #5115 | cross-ref | lane work-tip guard; provides the tip data and the downstream refusal the fix makes unreachable from finalize |
| #3431 | cross-ref | the `write_scope_overlap` collapse and acyclicity checks must keep holding |
| #5641 / PR #5662 | cross-ref, do not regress | finalize atomicity; a refusal must go through, or come before, the restore path |
| #5672, #5674 | out of scope | finalize input integrity (frontmatter cut, duplicate FR id); different mechanism |
| #3550 (epic), #1795 (epic), #1676 (epic) | parents / context | #3550 owns WP retirement; #1795 parents #5573 |
| #5635, #5634 | collision notes | in-flight sibling missions on `implement.py` and `core/mission_creation.py`; this mission touches neither |

## 7. Decisions taken from this grounding (carried into the spec)

**D1 – Structural, not a tie-break patch.** Started WPs' lane membership becomes a constraint input to the pure lane
computation, which honours it by construction (scenarios 1–4, 6, 9) and refuses only in the unsatisfiable cases (5, 7,
8, 10). The #5573 reproduction becomes a **success that keeps WP02 on lane-b**: the unstarted WP01 joins it.

**D2 – "Started" is history-based.** A WP counts as started if its event log ever recorded a move into `claimed`,
`in_progress`, `for_review`, `in_review`, `approved` or `done`.
- Being reset to `planned` or canceled after working does not unfreeze it.
- Moving `planned → canceled` or `planned → blocked` does not count as started.
- **Fallback evidence:** a prior lane whose branch has a recorded lane work tip, but no history-started WP, has all its
  prior members treated as started. This covers the brief's "any WP whose lane has a recorded work tip" without
  over-freezing in the normal case.
- The predicate is pure and lives in the `specify_cli.status` facade.

**D3 – Fail closed.** When a previous `lanes.json` exists and the status log cannot be read, finalize refuses. It never
degrades to "nothing started".

**D4 – One named refusal code.**
- **Code:** `LANE_MEMBERSHIP_FROZEN`, with a machine-readable `reason` per case and a structured `conflicts` list.
- **Non-destructive remedies:** split the amendment so that the started WP's group keeps one recorded lane, or cancel
  and re-plan the WP.
- **Never suggested:** deleting `lanes.json`, forcing, or `git reset`/`restore`. See #3931 / #5078.

**D5 – Refuse before the first write.** The check runs as a read-only preflight before any status or manifest write,
and `--validate-only` reports it.

**D6 – Unstarted regrouping stays allowed.** The tie-break among unpinned groups is deterministic and documented:
- most shared members;
- then the lowest prior lane id;
- prior lanes that held started WPs are never re-minted for a new group.

**D7 – #3432 residual: deferred, with a follow-up issue under #3550.**
- **Why folding is not a cheap rider.** Excluding canonically-canceled WPs from lane inputs would:
  - activate `STALE_CANCELED_DEPENDENCIES` for real cancellations whose dependents still list the canceled WP, so
    finalize runs that pass today would refuse (post-specify squad correction);
  - drop canceled WPs that have already started from `lanes.json`. Consolidation's canceled-content checks read
    `lane.wp_ids` to find canceled WPs (`reconciliation.py:1552,1646`, `executor.py:235`), so they would be blinded.
- That is a product behaviour change owned by the WP-retirement epic.
- The supported retirement route still works today: cancel the WP without clearing its scope.

**D8 – Out of scope, recorded as follow-ups.**
- The `doctor mission-state --fix` rebuild (`migration/mission_state.py:1645`) re-mints lane ids with no previous
  manifest. Same class of defect, different writer.
- Moving `_execution_has_begun` (the planning-pin predicate) onto the history-based predicate. It would change the
  #3311/#4141 pin behaviour.
- The allocator's `LaneWorkTipUnknownError` remedy wording.
- Reporting lane changes for unstarted WPs in the finalize JSON.
- #5539.
