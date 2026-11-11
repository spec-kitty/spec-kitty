---
type: reference
updated: 2026-11-11
---

# Foldable issues and PR collisions: sub-epic #7547

Audience: the operator and the planner. Reconciled from the planner-priti discovery
pass and the reviewer-renata second opinion (Appendix A holds the discovery report
verbatim). Proposed classification, pending the operator ruling recorded in the
Mission's decisions.

## 1. Proposed classification

| Issue | Class | Reason |
|---|---|---|
| #7554 | CORE | Lane test runs import the root `src`; this Mission's core. Closes on delivery. |
| #7547 | CORE (sub-epic) | Closes when all slices land. |
| #5985 item 2 | FOLD | Isolate the no-uv `sys.executable` fallback of the gate's override tier: same seam (`review/_interpreter.py`, `pre_review_gate.py`), replaced by the shared lane-invocation builder. Small. |
| #5985 item 1 | REFS | "pytest not importable should refuse instead of `no_coverage`" is a separate policy question; not delivered. #5985 stays open. |
| (no issue) gate ignores `lane_test_env` | FOLD | FR-006 lane DB isolation never reaches gate runs; the builder applies it. |
| (no issue) declared-command path does not strip interpreter-redirect env | FOLD | Only the override tier strips `PYTHONPATH`/`UV_PROJECT_ENVIRONMENT`/`VIRTUAL_ENV`; the builder unifies it. |
| #1907 detection half | FOLD (partial) | The probe detects an editable install repointed at another tree. Prevention and the stale-ancestor half (a harness concern) are not delivered: Refs. |
| #3959 | REFS | Performance (per-worktree test-venv build), not correctness; deliver under #5103. |
| #3123 | REFS | Stale-shim diagnostic lives on a different surface (post-merge env-skew report); can later reuse the builder. |
| #3074, #5140, #5071, #6851, #3260, #1224, #5064, #7361, #2624, #7336, #5103/#5105 | REFS | Adjacent seams or parent epics; see Appendix A. |
| #2330 | EXCLUDE, design constraint | Non-Python consumers: the import probe is Python-only, so they get git provenance (path, HEAD, dirty) and never a probe refusal. |
| #3046, #2762, #3943, #5334 | EXCLUDE | Budget, process hygiene, post-merge run, consolidation self-hosting. |
| new | FILE | The orchestrator-api `for_review` transition never runs the pre-review gate (`orchestrator_api/wp_lifecycle.py:910-911`). |

#2803 is closed (PR #5958); its remainder lives in #5985. #5096 is closed (PR #5913).

## 2. Open-PR collisions

| PR | Overlap |
|---|---|
| #7562 (#7545, CLI commits its own writes) | `lanes/implement_support.py` (`_claim_dirty_paths`), `cli/commands/implement_cores.py`, the `agent/tasks_move_task*.py` family except `tasks_move_task_gates.py`. Low to moderate risk; rebase after it merges. |
| #7567, #7561, #7564 | None. |
| #7425 (draft pin bump) | Soft: only if a pack prompt had to change, which this Mission avoids by using the core-owned prompt builders. |
| #7472 (fork, flake.nix) | None; another non-editable global `spec-kitty` shape the probe must tolerate. |

## 3. Decisions escalated to the operator before specify

1. Severity of a foreign-tree finding at the pre-review gate (terminal refusal, `--force`-bypassable block, or record-only), and its refusal code. Refusing needs an ADR `2026-08-13-6` amendment and a C-003 carve-out.
2. Invocation mechanism: the hybrid (shared venv + `PYTHONPATH=<lane>/src` when the lane has no venv + child-process import probe) vs a per-lane venv.
3. The fold set in §1.
4. Lane packs (the CLI in a lane fails `BuiltInPackMissing`): in scope as a redirect, a required `make sync-packs` hint, or out of scope.

---

## Appendix A — discovery report (planner lens)

## Foldable-issue and PR-collision research: sub-epic #7547 (lane worktrees verify lane code)

Read-only research, 2026-11-11. Profile: planner-priti. Core: #7554. Members: #3959, #1907. Parent: #7543.
Searched about 40 open-issue queries: lane venv, PYTHONPATH, editable install, test command, verified test, pre-review gate, pre_review, no_coverage, regression gate, evidence provenance, stale shim, global spec-kitty, import origin, wrong tree, root src, lane interpreter, test-venv, worktree pytest, sys.executable, uv run, venv, editable, `__file__`, lane src, lane code, PRIMARY src, lane pytest, verification command, worktree interpreter.

### #2803: CLOSED, cannot be folded
- #2803 was closed 2026-10-09 by PR #5958, "run the lane pre-review gate in the lane's own environment". That PR has the gate run `uv run --project <lane>` with the `test` extra or group, and strips any inherited `PYTHONPATH`, `VIRTUAL_ENV` or `UV_PROJECT_ENVIRONMENT`.
- The issue's second `no_coverage` facet was the hard-coded `tests.architectural._gate_coverage` import, which fails in consumer repos. It looks resolved on current main. `grep -rn _gate_coverage src/` finds only a comment, at `src/specify_cli/review/pre_review_gate.py:85` ("Mirrors _gate_coverage._CompositeRoute"). No runtime import remains. #3821 and #3958 (both closed) covered the consumer-repo binding and the missing default `test_command`.
- What is left of #2803 now lives in **#5985**, which is open. See below.

### Candidate classification

| # | Title (short) | Class | Reason |
|---|---|---|---|
| 7554 | Lane test runs import root src (editable install) | CORE | This mission's core issue. |
| 5985 | Pre-review gate: should "pytest not importable" refuse instead of warning no_coverage; isolate the no-uv fallback | **FOLD** | Same root cause and same seam (`review/_interpreter.py::resolve_pytest_command`, `pre_review_gate.py::_gate_run_env`). The no-uv fallback runs `sys.executable -m pytest`, whose editable `.pth` resolves to the root `src`. That is exactly #7554 inside the gate. Slice 3 (refuse evidence from another tree) answers its policy question: fail closed when the gate cannot prove the lane's tree. Small. Needs an operator ruling on fail-closed vs advisory; it is assigned to stijn-dejongh. |
| 3959 | Share the pytest test-venv across lane worktrees | REFS (member) | Sub-epic member, but this is performance (an 80 s venv build per worktree in `tests/conftest.py`), not correctness. It is only foldable if slice 1 builds the lane environment. Otherwise deliver it separately under #5103. |
| 1907 | Stale ancestors + editable-install repoint hazard | REFS (member); partial FOLD possible | The repoint half (`pip install -e .` from a worktree rewrites the shared pointer) has the same root cause. Slice 1's `__file__` probe *detects* it but does not prevent it. The stale-ancestor half is mostly a harness concern (label `triage:needs-revision`). Fold only "detect a repointed install / wrong origin". Keep the rest. |
| 3123 | CLI env-skew warning reports the ambient PATH spec-kitty; no non-mutating verification | REFS (candidate FOLD if scope allows) | This is the "stale global spec-kitty shim" facet named in #7554. The issue body suggests "a shared resolution helper the others could use", which is slice 1's seam. Its diagnostic lives in a different surface (post-merge review / version skew). Fold only if slice 1 is also meant to report which `spec-kitty` the lane resolves. |
| 3074 | `_make_merge_env` derives the venv bin from sys.executable (wrong spec-kitty under uv run) | REFS | Same family (wrong interpreter or entry point), but it is the merge-driver path, already parented to sub-epic #7361. It could consume the slice-1 resolver later. |
| 5140 | Test fails in linked worktrees: `uv run --no-sync` picks an interpreter without deps | REFS | Same lane/worktree interpreter-resolution class, but it is one test's own driver launch (under #5105). The fix is local to that test (use `sys.executable`). It would be a good regression witness for slice 1. |
| 5071 | Dispatch template required fields (incl. env/venv constraints) | REFS | Slice 2 (WP prompt context carries the verified command) partly satisfies its env/venv field. The rest is sub-delegation and hunk overlap; parent #3809. |
| 6851 | Pre-review gate never inspects WPs whose work landed on the target branch (planning lane, single_branch) | REFS | Same gate, different root cause (scoping of changed files, not tree provenance). Slice 3's "evidence source tree" record should still name the write checkout for single_branch. |
| 3260 | Epic: regression & pre-review gate reliability | REFS | Parent of #5985, #2929, #3046, #2762, #5331 and #3943. Cross-link slice 3 here. |
| 5331 | for_review gate accepts a WP with no commits of its own in a shared lane | REFS | Touches `lanes/for_review_gate.py`, but it is about commit-range attribution, not the source tree. |
| 2929 | Baseline capture reports a missing JUnit artifact as a failed test | REFS | Pre-review baseline diagnostic; adjacent to the no_coverage classification. |
| 3046 | Pre-review gate advisory blocks on its own timeout; 300 s budget | EXCLUDE | Budget/timeout policy, not about the tree. |
| 2762 | Pre-review gate leaks orphan daemons | EXCLUDE | Process-group hygiene. |
| 3943 | Run fast tier + arch gates on the merged Mission branch before merge | EXCLUDE | A post-consolidation verification point, not lane provenance. |
| 1224 | Capture test evidence in the CLI (proof test run) | REFS | A proof-item design that slice 3's provenance record could feed; much larger, product backlog. |
| 5064 | One documented sync command yields every tool the suite/WP gates invoke | REFS | Adjacent to "lanes lack a usable venv" (missing pytest/ruff); dev-environment scope. |
| 5103 / 5105 | Test suite friction epics | REFS | Parents of #3959 and #5140. |
| 7361 | Sub-epic: entry-point and environment parity | REFS | Sibling sub-epic that owns #3074. Coordinate the shared interpreter-resolution helper with it. |
| 2624 | Root & worktree-path detection discipline | REFS | Seam for resolving lane roots. |
| 7336 | `lane_checkout_containing` fails open on a git failure | REFS | Same module family (`lanes/lane_checkout.py`); slice 1 may call `lane_checkout_containing` to decide "is the cwd a lane". |
| 5334 | consolidate crashes when lanes change spec-kitty's own source (self-hosting) | EXCLUDE | Consolidation self-hosting; under #7361. |
| 2330 | software-dev workflow assumes a Python/pytest layout | EXCLUDE (constraint) | Not delivered, but a design constraint: the verified test invocation must degrade for non-Python consumers. Probing `<pkg>.__file__` is Python-only. |

Closed issues seen for context: #5096 (lane interpreter; conftest import-origin guard via PR #5913), #2803 (via #5958), #3821, #3958, #3224, #3594, #3611 and #3612 (`review.test_command` scope-source symmetry; relevant to slice 3 provenance).

### Open-PR collision check

Open PRs in total: 6 (#7567, #7564, #7562, #7561, #7472 from a fork, #7425 draft). No other open PR touches `lanes/`, `review/`, `workspace/` or the implement CLI.

| PR | Title | Files | Overlap with watched files |
|---|---|---|---|
| #7567 | [#7544] Coordination-topology closeout recovers from its own commits | 56 (src: acceptance/__init__, cli/commands/accept.py, consolidation/entry_preflight.py, consolidation/executor.py, coordination/coherence.py, git/commit_helpers.py, git/ref_advance.py) | **None** |
| #7562 | [#7545] The CLI commits its own writes; dirty-tree gates count only the Mission's paths | 91 | **YES**: `lanes/implement_support.py` (+17/-1 in `_claim_dirty_paths`, #7556, Mission-scoped dirt partition); `cli/commands/implement_cores.py` (+3/-2 in `_is_coord_legacy_mission_event_log`); `cli/commands/agent/tasks_move_task.py` (`status_commit` field, `_mt_resolve_targets`) plus `tasks_move_task_executor.py`, `tasks_move_task_hops.py`, `tasks_shared.py`, `tasks.py`, `tasks_mark_status.py`, `tasks_verdict_persistence.py`, `mission_record_analysis.py`, `mission_setup_plan.py`. It does NOT touch `tasks_move_task_gates.py` (where `_mt_pre_review_*` lives), `review/pre_review_gate.py`, `review/_interpreter.py`, `lanes/lane_checkout.py`, `lanes/for_review_gate.py`, `workspace/context.py`, `implement.py`, or any `agent/*action*` file. |
| #7561 | [#7549] doctor coordination --fix acts only on named Missions; decisions runtime lock never committed | 61 (src: runtime_bridge, _coordination_doctor, decision, doctor, phase_teardown, surface_resolver, transaction_errors, core/errors, core/git_ops, decisions/lock, git/commit_helpers, git/ref_advance, missions/_read_path_resolver) | **None** (indirect: `missions/_read_path_resolver.py`, which #7562 also imports from `implement_support`) |
| #7564 | [#7539] next and recovery read Mission status once | 15 (src: runtime/next/* x4, lanes/recovery.py, status/read_surface.py) | **None** (`lanes/recovery.py` is a neighbor of `implement_recover.py`, not watched) |
| #7472 (fork) | feat: Package with flake.nix | flake.nix, flake.lock | None. Note: the Nix wrapper installs a non-editable spec-kitty on PATH, another "global spec-kitty" shape for slice 1's probe to tolerate. |
| #7425 (draft) | chore(packs): bump open-packs pin for ASCII templates | packs/built-in.source.yaml, spdd template_renderer, migration m_3_2_0rc35, tests | None in src watch list. **Soft collision for slice 2**: if the WP prompt template (mission-steps/software-dev/implement or tasks prompt) must carry the verified command, that is an open-packs edit plus a pin bump, which competes with #7425's pin bump. Sequence after #7425 lands, or rebase the pin. |

#### Collision summary
- Only **#7562** overlaps directly: `lanes/implement_support.py` and `implement_cores.py` (slice 2, implement prints and records the command), and the `tasks_move_task*.py` family that calls the pre-review gate (slice 3). The hunks are small and local (`_claim_dirty_paths`, `_is_coord_legacy_mission_event_log`), so the conflict risk is low to moderate. Rebase slices 2 and 3 after #7562 merges.
- Slice 1 (new seam, likely `lanes/` or `review/_interpreter.py`) is collision-free today.
- Slice 3's natural home (`review/pre_review_gate.py`, `review/_interpreter.py`, `agent/tasks_move_task_gates.py`) is untouched by every open PR.
