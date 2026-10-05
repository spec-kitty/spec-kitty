---
work_package_id: WP09
title: Move commit, identity and effect patches to their seams
dependencies:
- WP08
requirement_refs:
- FR-007
- NFR-004
- NFR-005
- SC-003
- C-005
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
- T046
- T047
- T048
phase: Phase 3 - Tests onto the seams
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/core/test_mission_creation_branch_coverage.py
- tests/core/test_mission_creation_invariants.py
- tests/core/test_mission_creation_family.py
execution_mode: code_change
model: ''
owned_files:
- tests/core/test_mission_create_idempotency_guard.py
- tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/_factories/coord_mission.py
- tests/_factories/test_make_mission_parity.py
- tests/agent/test_agent_feature.py
- tests/agent/test_create_feature_branch_unit.py
- tests/contract/test_mission_id_creation_contract.py
- tests/core/test_mission_create_checkout_restore.py
- tests/core/test_mission_create_coord_seed_rollback.py
- tests/core/test_mission_create_coord_status_placement.py
- tests/core/test_mission_create_coord_status_seed.py
- tests/core/test_mission_create_protected_single_branch.py
- tests/core/test_mission_create_scaffold_rollback.py
- tests/core/test_mission_creation_decomposition.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/core/test_mission_creation_identity.py
- tests/core/test_mission_creation_topology.py
- tests/core/test_mission_creation_unborn_head.py
- tests/core/test_slug_validator_unit.py
- tests/integration/test_issue_4863_merge_abort_no_state.py
- tests/integration/test_placement_partition_golden_path.py
- tests/integration/test_specify_plan_commit_boundary.py
- tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
- tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py
- tests/specify_cli/cli/commands/agent/test_mission_create.py
- tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py
- tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
- tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/specify_cli/cli/commands/test_selector_resolution.py
- tests/specify_cli/core/test_feature_creation.py
- tests/specify_cli/core/test_mission_creation_fire_once.py
- tests/specify_cli/core/test_mission_creation_placement.py
- tests/specify_cli/core/test_mission_creation_specify_started.py
- tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
- tests/core/test_mission_creation_branch_coverage.py
- tests/core/test_mission_creation_invariants.py
- tests/core/test_mission_creation_family.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Move commit, identity and effect patches to their seams

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them. Load `tactic:delete-the-assertion-not-the-test` and `tactic:test-scaffolding-as-design-smell`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback.

---

## Objectives & Success Criteria

Move the remaining façade patches to the seam that owns them, or to an injected input, and produce the **final census** against NFR-004 / SC-003 (spec FR-007, US3).

Targets (static sites at the grounding baseline) are `_commit_feature_file` 41, `ULID` 11, `preflight_commit` 5, `safe_commit` 4, `now_utc_iso` 2, `_commit_create_scaffold` 2, `_consume_pending_origin_if_present` 1, `subprocess.run` 1 and `create_mission_core` 7, plus whatever WP03 added (see its `Patched façade names:` docstring).

Done means:

- **NFR-004 met**, as reported by the WP04 tool on the final commit:
  - ≤ 40 static sites in **NFR-004's scope**: (a) any patch targeting a `mission_creation*` module, anywhere in `tests/`, plus (b) source-module patches of family-read names within the **fixed file set** (fold 6). Process-global stdlib names (`subprocess`, `os`, `shutil`) are reported separately and are outside the budget. Fixture-held patches count once per applying test in the runtime report;
  - ≤ 15 static sites in scope (a), the whole module family;
  - runtime applications down ≥ 70% from the WP04 baseline.

  If a target is not reachable without weakening a test, stop and report the gap to the orchestrator with the numbers. Do not launder patches into fixtures or onto source modules; the census counts those too.
- **No 1.1 s sleeps** remain in the covering set for identity collisions (`tests/core/test_mission_creation_decomposition.py` ~:166, ~:179; `tests/core/test_mission_create_idempotency_guard.py`). Identity and clock are injected instead.
- **No process-global `subprocess.run` patch**: `tests/core/test_mission_create_scaffold_rollback.py` uses adapter fault injection.
- **`tests/agent/test_agent_feature.py`**: its create-behaviour assertions that duplicate golden CLI cells are retired (naming the golden cell that covers each, with a planted break), and its CLI-wiring tests stay.
- **At least one end-to-end smoke per behaviour family remains** (spec "Behaviour families" 1–6). List which test covers each in the Activity Log.
- **Final census report**: a per-name disposition table (name → before → after → moved/rewritten/retired → proof reference), in the Activity Log in Markdown. The orchestrator copies it into the PR.
- The routing check stays green, with leaves de-routed for names no longer patched (Rule C). The golden matrix, WP03 tests and covering set are green. The golden files are untouched.

## Context & Constraints

- Verdicts: `research/test-remediation.md` §5.
- **Identity and clock injection** without changing the public signature of `create_mission_core`:
  - Option A (preferred): a module-level seam in `mission_creation_identity.py` (for example `_mint_mission_id()` and `_now()`) that the orchestrator calls. Tests patch **that owning module** in the few places they need determinism. Counts against NFR-004 scope (a), but each site becomes one per test instead of a stack.
  - Option B: private keyword-only parameters on `_create_mission_core_impl` (`_mission_id=None`, `_created_at=None`) that tests call directly. Avoid adding parameters to `create_mission_core` itself (public surface, C-006).

  Pick one and record it in `traces/design-decisions.md`. The golden matrix normalises identity, so it is unaffected.
- **`_commit_feature_file`** (41): most stubs exist only to dodge the protected-`main` refusal. Rewrite them to create on an unprotected topic branch and assert the real commit (pattern: `tests/specify_cli/test_mission_create_retention.py` ~:31). About 6 failure-injection sites stay, re-pointed to the owning module (`mission_creation_commit`) **or** to the routed façade name if the reader routes it. Choose the one that keeps the routing set minimal.
- **`tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py`** patches `resolve_primary_branch`, a source-namespace patch of a family-read name. Keep its truth-table intent; where WP02's real-repo fallback pin already covers a row, retire that row, naming the WP02 test and a planted break. Otherwise keep it as a decision-level unit with the patch, which counts toward NFR-004 (b).
- **`create_mission_core`** (7, in `tests/specify_cli/cli/commands/test_selector_resolution.py` and others): CLI tests that stub the whole core. The CLI imports it lazily from the façade, so these are legitimate seam patches. Keep them; they count toward the ≤ 15 façade budget.
- C-005: when a mock-based interaction assertion is replaced by a behavioural one, log `file::test — old → new` in the Activity Log. It must be equal or stronger.
- Golden files are frozen.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T043 – `_commit_feature_file`

- Per file, classify each site as dodge or fault injection.
  - **Dodge**: create on a `topic` branch and assert `git log -1 --name-only` shows the scaffold commit.
  - **Fault injection**: re-point to `specify_cli.core.mission_creation_commit._commit_feature_file` if its readers are all in that module and not routed; otherwise keep it on the façade (routed). Verify interception by watching the test go red when the injected fault is removed.

### Subtask T044 – `ULID` / `now_utc_iso`

- Implement the chosen injection seam.
- Remove the 1.1 s sleeps (determinism now comes from injected distinct IDs).
- `tests/contract/test_mission_id_creation_contract.py::test_t004` (25 full creates, about 16 s) becomes a seam unit test that mints 25 IDs through the identity seam and checks uniqueness and format, plus one end-to-end create. Keep the contract's intent (unique ULIDs, mid8 derivation) explicit in the docstring.

### Subtask T045 – Other adapters

- `preflight_commit`, `safe_commit`, `_commit_create_scaffold`, `_consume_pending_origin_if_present`: re-point each to the owning leaf module when the reader is not routed, or keep it routed on the façade. Choose by "fewest sites, still intercepting". Verify each patch still intercepts by removing the injected behaviour and watching the test go red.

### Subtask T046 – Global `subprocess.run`

- `tests/core/test_mission_create_scaffold_rollback.py` patches `specify_cli.core.mission_creation.subprocess.run`, which replaces `subprocess.run` for the whole process. Rewrite it as fault injection on the narrowest adapter function that runs the git call it is targeting, or reproduce the failure for real (see WP03 row 2's ref-conflict trick).

### Subtask T047 – `test_agent_feature.py` and routing

- For each create-behaviour assertion duplicated by a golden CLI cell, retire it, naming the golden cell and the planted break that turns it red. Keep the CLI-wiring tests.
- Re-run the WP06 routing check and de-route stale leaves.

### Subtask T048 – Final census and disposition table

- Run:

  ```bash
  python -m tests._support.patch_census --report --json
  ```

  plus the runtime plugin over the covering set, on the final commit.
- Write the per-name disposition table. Compute the reduction against the WP04 baseline numbers recorded in WP04's Activity Log.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest $(grep '^tests/' <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md)) tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/core/test_mission_creation_family.py tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py tests/_support/ -q
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py -q
git diff <lane-base> -- tests/core/golden tests/core/test_mission_creation_golden_* tests/core/_mission_create_golden.py tests/specify_cli/cli/commands/agent/golden   # must be empty
uv run --frozen ruff check <changed files> && uv run --frozen ruff format --check --force-exclude <changed files>
.venv/bin/mypy <changed src files>
make test-fast
```

Baseline reds to classify, not chase: baseline-red #5705, #5706.

## Risks & Mitigations

- **Hitting NFR-004 by laundering**: the census counts every namespace and runtime applications. Report honestly.
- **Losing an end-to-end family smoke**: keep the family → test list in the Activity Log.
- **Weakened assertions**: C-005 log, reviewed line by line.

## Review Guidance

- Re-run the census and compare it with the Activity Log table.
- Pick 3 re-pointed fault injections and remove the fault: each test must go red.
- `rg -n "time\.sleep\(1\.1\)" tests/` finds nothing in the covering set.

## Post-tasks squad folds (binding)

1. **Freeze set is read-only for this WP** (NFR-001): the golden modules, the snapshots, `tests/core/_mission_create_golden.py`, `tests/_support/git_template/**` and `tests/_factories/__init__.py`. Check `git diff <WP01-commit> -- <freeze set>` is empty.
2. **Removing a name from the façade attribute list** (WP06 fold 3) happens only when de-routing, in the same commit, with a reason.
3. **Census**: report family-namespace **and** source-namespace counts, runtime applications and collected test counts (WP04 folds 2–4). NFR-004's budget is scope (a), family-module patches anywhere, plus scope (b), source-module patches of family-read names within the fixed file set (WP09 fold 6). Stdlib process-global names are reported separately.
4. Record planted breaks and retirement proofs as `git diff` patch blocks or exact commands in the Activity Log.
5. **Failing-first evidence (charter C-011) for a test-migration WP**: before rewriting a test, record a planted break of the behaviour it guards, which turns it red. Then show that the rewritten test turns red on the **same** break. That pair, one per migrated test or one per file for mechanical allow-flag swaps, is this WP's red→green record. The census baseline from WP04 is the measured "before".
6. **Fixed file set and baseline for NFR-004 (analysis A2/I6).** The (b) file set is the 42-file covering set plus every test file the mission touched (`git diff --name-only <mission-base>..HEAD -- tests/`), computed once at T048. Create a temporary worktree of the mission base commit and run the **HEAD version** of `tests/_support/patch_census.py` against it: static with `--files <set>`, and runtime over the same set, loading the plugin from the HEAD checkout via `PYTHONPATH`. Then run the same commands on the final commit. Both counts use the same tool and file set. This re-measured base is the NFR-004 baseline for the ≥70% runtime drop and the static budgets. WP04's original numbers are reported alongside for reference.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
