# Work Packages: Every Mission-file writer takes the lock, and the runtime never cuts a log it cannot prove is its own

**Inputs**: Design documents from `/kitty-specs/mission-writer-followups-01M4CYWW/`
**Prerequisites**: plan.md (including "Amendments after the post-plan squad", which are binding), spec.md, research.md, data-model.md

**Tests**: Required. Every bug fix is red-first: a deterministic reproduction is committed and shown failing on the pre-fix code before the fix lands (ADR 2026-07-17-1).

**Topology**: single_branch. WPs run sequentially in the repository root checkout.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: One canonical Mission lock key: the key function and the core doors (Priority: P1)

**Goal**: `mission_lock_key(feature_dir)` exists and the core doors use it: `mission_write_lock`, `_holds_mission_lock`/`capture_rollback_point`, `mission_write_lock_dir`, `BookkeepingTransaction` and `coord_status_lock`. On a legacy bare-directory coordination Mission (`060-test` primary with a `060-test-<mid8>` coordination surface), these resolve one lock file. WP13 then moves every remaining caller onto the key.
**Independent Test**: `tests/status/test_mission_lock_key.py`: key equality across primary, coordination, flat and bare-directory coordination Missions; the mid8 cascade; the empty-mid8 typed error; key stability inside a hold; capture under a held primary lock; the subprocess-count check.
**Prompt**: `/tasks/WP01-canonical-lock-key.md`
**Requirement Refs**: FR-005, C-002, NFR-002, NFR-003, C-006, NFR-005

### Included Subtasks

T001 Red-first: the bare-directory coordination fixture shows the transaction and `mission_write_lock`/emit resolving different lock files, and `capture_rollback_point` raising under a held primary lock after a naive rekey (plan A1, A2) (WP01)
T002 `mission_lock_key(feature_dir)` in `status/mission_write.py`, using the transaction's mid8 cascade through one shared helper (with `branch_naming`/`resolve_transaction_mid8`); a typed error for a coordination-routed Mission with no resolvable mid8, and the transaction's trailing-dash key (`status_transition.py` legacy NNN arm) fixed to use the same function; the key read from the canonical primary `meta.json` via the read-path resolver (A3, A4) (WP01)
T003 Thread-local held-key reuse: nested entries for the same Mission reuse the held key; a test with `flatten_coordination_metadata`-style meta mutation inside a hold (A4) (WP01)
T004 Route the core doors through the key: `mission_write_lock`, `_holds_mission_lock`/`capture_rollback_point`, `mission_write_lock_dir`, `BookkeepingTransaction._mission_specs_dir_name`, `coord_status_lock`; the NFR-003 subprocess delta with a warmed `git_common_dir` cache (A12) (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Keep `feature_status_lock`'s signature. Handoff: the remaining direct `feature_status_lock` callers and `hold_mission_write_lock` move in WP13, and `implement_phases.py` is later edited for wording by WP10.

---

## Work Package WP13: Every per-Mission lock caller uses the canonical key (Priority: P1)

**Goal**: Every remaining per-Mission lock caller takes its key from `mission_lock_key(...)` and its path from `mission_write_lock_dir(...)` or a function parameter. That covers every direct `feature_status_lock(root, X.name)` caller, `hold_mission_write_lock`, and the lock-path arguments in `workflow_executor`, `implement_phases` and `commit_router`. A legacy bare-directory coordination Mission locks one file in one order from every door.
**Independent Test**: `tests/status/test_mission_lock_order.py`: on the bare-directory coordination fixture, the lifecycle path and the implement claim path run on two threads without deadlocking and serialize on one lock file; a parametrized check over every converted caller.
**Prompt**: `/tasks/WP13-lock-key-caller-sweep.md`
**Requirement Refs**: C-002, NFR-001, NFR-002, NFR-005, C-006

### Included Subtasks

T005 Red-first: on the bare-directory coordination fixture, after WP01, a direct `feature_status_lock(root, X.name)` caller (for example the lifecycle path) and `hold_mission_write_lock` take different lock files and can invert order against `BookkeepingTransaction` (A1) (WP13)
T053 Convert every direct `feature_status_lock` caller listed in A1 (emit, work_package_lifecycle, lifecycle_events, migrate_lifecycle_envelope, move-task, mark-status, agent status, decisions emit, finalize status surface, retrospective lifecycle events, review cycle, coord_seed, the migrations), and route `hold_mission_write_lock` plus the lock-path arguments in `workflow_executor.py` (`:230`, `:1085`, `:1888`), `implement_phases.py:415` and `commit_router.py:799` through `mission_write_lock_dir(...)` or a parameter (gate Rule 3 shape, A6) (WP13)
T054 Disposition the two Rule 1 whole-file rewrites: `migration/rebuild_state.py` (`os.replace` onto the events log) and `status/migrate_lifecycle_envelope.py` run their rewrite under the Mission lock (A7); the cross-thread lock-order test (WP13)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Re-derive the caller list with `grep -rn "feature_status_lock(\|mission_write_lock(\|hold_mission_write_lock(\|coord_status_lock(" src`. Handoff: `implement_phases.py` is edited again by WP10 (wording).

---

## Work Package WP02: Locked meta.json helper, setters and accept restamps (Priority: P1)

**Goal**: Every `mission_metadata` read-modify-write and accept's direct restamp writes run through `locked_update_meta(feature_dir, mutate, ...)`: the lock is taken, `meta.json` is re-read under it, `mutate` is applied, and the result is written atomically. The acceptance verdict guard locks through `mission_write_lock`. The three dead setters are removed.
**Independent Test**: `tests/specify_cli/test_locked_meta_writers.py`: for each setter family a deterministic two-thread overlap keeps both writes (US1); nested use under `ensure_vcs_locked`; the bounded wait fails with `STATUS_LOCK_HELD` (NFR-002); the uncontended path adds one lock acquisition and no subprocess.
**Prompt**: `/tasks/WP02-locked-meta-helper.md`
**Requirement Refs**: FR-001, FR-005, FR-020, NFR-001, NFR-002, NFR-005, C-006

### Included Subtasks

T006 Red-first: two overlapping `meta.json` writers (for example `record_acceptance` vs `set_target_branch`, `set_origin_ticket` vs `record_discard`) lose a write today (US1) (WP02)
T007 `locked_update_meta(feature_dir, mutate, *, repo_root=None, timeout=BOUNDED)` in `mission_metadata.py`; every setter (`record_acceptance`, `record_discard`, `flatten_coordination_metadata`, `clear_merge_metadata`, `set_target_branch`, `set_origin_ticket`, `set_documentation_state`, `set_vcs_lock`) uses it; `restore_meta_text` gets a compare-and-swap variant for WP04 (A8) (WP02)
T008 Remove `set_change_mode`, `clear_coordination_metadata` and `set_purpose_summary` with their `dead_symbol_allowlist.yaml` entries and tests (WP02)
T009 acceptance: the planning-only `record_acceptance` call and the direct restamp writes go through the helper (the verdict guard in `acceptance/matrix.py` is rekeyed in WP04, A13) (WP02)
T010 Callers: `core/mission_creation_meta.py`, `tracker/origin.py`, `cli/commands/mission_type.py` (discard, flatten, reopen), `_coordination_doctor.py`, `lanes/implement_support.py` (`set_vcs_lock` under `ensure_vcs_locked`, unbounded wait unchanged) (WP02)

### Dependencies

- Depends on WP13.

### Risks & Mitigations

- `mutate` is a pure function that is only called, never stored, returned or assigned (gate Rule 2). Watch for nesting: `ensure_vcs_locked` already holds the same per-thread re-entrant lock. A subprocess cannot re-enter its parent's hold; document that edge case if one exists. Edit `dead_symbol_allowlist.yaml` wherever it lives (`grep -rn set_change_mode tests`). Handoff: `implement_support.py` is edited again by WP04 (`update_fields`); `acceptance/__init__.py` and `cli/commands/mission_type.py` are edited again by WP10 (wording).

---

## Work Package WP03: Remaining meta.json writers take the lock (Priority: P1)

**Goal**: Every other read-modify-write of `meta.json` runs through `locked_update_meta`, so gate Rule 4 (WP08) passes on the real tree with no allowlist. This covers the documentation-state writers, consolidation teardown, baseline and mission-number bake, and the migrations and upgrades.
**Independent Test**: `tests/specify_cli/test_remaining_meta_writers.py`: one overlap test per writer family (documentation state, consolidation, migrations) and a parametrized check that each writer calls the locked helper.
**Prompt**: `/tasks/WP03-remaining-meta-writers.md`
**Requirement Refs**: FR-020, NFR-002, NFR-005, C-006

### Included Subtasks

T011 Red-first per family: a documentation-state writer, a consolidation writer and a migration writer each lose a concurrent locked write today (C-006 part by part) (WP03)
T012 `doc_analysis/doc_state.py` (`set_audit_metadata`, `set_generators_configured`, `set_iteration_mode`, `set_divio_types_selected`, `write_documentation_state`, `ensure_documentation_state`) and their `mission_setup_plan.py` callers (WP03)
T013 Consolidation: `phase_teardown` (flatten caller and `_clear_landed_single_branch_mission_branch`), `baseline.record_baseline_merge_commit`/`_stamp_pr_merge_provenance`, `mission_number/bake.py` (the scratch-checkout write locks the scratch Mission's key) (WP03)
T014 Migrations and upgrades: `migration/mission_state.py`, `runtime_state_cutover.py`, `upgrade/feature_meta.py`, raw meta writes in `backfill_mission_type.py`, `backfill_identity.py` (including the `open(meta_path, "w")`+`json.dump` form), `backfill_topology.py`, `m_0_13_8_target_branch.py` (WP03)

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Migrations get no exemption (plan D5); they write through the helper. The merge driver (`consolidation/drivers.py`) is out of scope: it writes the temporary path git hands it, and WP08 excludes it structurally. Re-derive line numbers (lens A10). Handoff: `mission_setup_plan.py` is edited again by WP10 (commit subjects).

---

## Work Package WP04: Frontmatter, finalize and matrix writers take the lock (Priority: P1)

**Goal**: map-requirements, the finalize flush, the finalize write-scope restore, the issue-matrix scaffold, the matrix helpers and the remaining frontmatter writers read and write inside one Mission-lock hold. `locked_update_frontmatter(wp_path, mutate, *, feature_dir, ...)` is the helper. The finalize restore is a compare-and-swap on every branch.
**Independent Test**: `tests/specify_cli/test_locked_frontmatter_writers.py` (US2): map-requirements overlap; finalize vs a concurrent map-requirements ref and a concurrent body note; the compare-and-swap restore for rewrite, unlink and `restore_meta_text`. `tests/specify_cli/test_matrix_writer_locks.py` (US3): the scaffold vs a recorded verdict; the two-worktree matrix writers on the bare-directory coordination fixture.
**Prompt**: `/tasks/WP04-frontmatter-and-matrix.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005, FR-020, NFR-001, NFR-005, C-006

### Included Subtasks

T015 Red-first: map-requirements overlap (FR-002); finalize erasing a concurrent frontmatter field and body note (FR-003, A9); the scaffold overwriting a verdict (FR-004); matrix helpers on the bare-directory coordination fixture, identifying key vs root as the cause (FR-005, A9) (WP04)
T016 `locked_update_frontmatter` in `frontmatter.py`, preserving the body byte for byte; map-requirements uses it (re-read refs under the lock) (WP04)
T017 Finalize flush applies its field delta to the freshly read frontmatter and body under the lock; the write-scope restore (rewrite and unlink branches) and `restore_meta_text` become compare-and-swap inside the lock and report kept files (A8); `mission_finalize_branch_contract.py` meta writes use `locked_update_meta` (WP04)
T018 `scaffold_issue_matrix` exists-check and write in one hold; `acceptance/matrix.py` (re-read helper and `locked_acceptance_verdict_guard`, A13) and `issue_verdict.py` lock through `mission_write_lock` keyed via WP01 (WP04)
T019 Other frontmatter and `tasks.md` writers: `task_metadata_validation.py` (`validate-tasks` repair), `lanes/implement_support.py` `update_fields`, the frontmatter migrations (`backfill_ownership`, `strip_frontmatter`, `m_2_0_6_consistency_sweep` including its `tasks.md` write), and the finalize `tasks.md` write in `mission_finalize_bootstrap.py` (A10); the lane mirror in `emit.py` stays as it is (runtime-locked; WP15 recognizes it) (WP04)
T058 CLI-entry overlap test: two overlapping `spec-kitty agent tasks map-requirements` invocations (via the Typer runner on two threads with an injected pause) keep both refs (FR-002, US2 through the CLI) (WP04)

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- `review/prompt_metadata.write_frontmatter` is out of scope (C-007): it writes a per-invocation temporary file. Finalize keeps a long in-memory window, so apply deltas rather than writing back the model.

---

## Work Package WP05: Runtime terminal gate runs before completion; speculative rollback removed (Priority: P1)

**Goal**: On every legacy `next` path, including the stale-plan and no-plan fallbacks, the retrospective gate runs as the engine's abort-only `before_run_completed` hook before anything is appended to `run.events.jsonl` or `state.json`. A refusal reads as a typed retrospective-gate refusal. The speculative capture, the rollback and `_BufferingRuntimeEmitter` are deleted.
**Independent Test**: `tests/runtime/test_terminal_gate_before_completion.py` (US5): a refused terminal step leaves both files byte-identical to what other writers left, on `commit_advance`, the stale-plan fallback and the no-plan fallback; a concurrent append from another writer survives a refusal; the refusal decision shape on the legacy and composition paths; a terminal re-poll does not re-run the gate or the non-blocking capture.
**Prompt**: `/tasks/WP05-runtime-terminal-gate.md`
**Requirement Refs**: FR-009, FR-010, FR-011, NFR-001, NFR-005, C-006

### Included Subtasks

T020 Red-first: a foreign append made between the speculative capture and the rollback is cut today; the stale-plan fallback appends completion before the gate (FR-009, FR-011) (WP05)
T021 `engine.next_step` takes `before_run_completed: Callable[[], None] | None`; `_dn_advance_engine` passes the retrospective hook to both `commit_advance` and `next_step` (WP05)
T022 One bridge-level adapter wraps every hook failure (`MissionCompletionBlocked(decision)`, the policy error, a capture exception) in one typed refusal on the legacy and composition paths, caught before the generic engine-error and `_advance_failed_decision` handlers (B6) (WP05)
T023 Delete `_dn_capture_pre_speculative_state`, `_dn_rollback_buffered_run_state`, `_BufferingRuntimeEmitter` and their tests; update the five test files R4 names (FR-010) (WP05)
T024 Pin the re-poll behaviour: the gate and the non-blocking learning capture fire only on the transition into terminal (B7) (WP05)

### Dependencies

- None.

### Risks & Mitigations

- `src/runtime` must not gain a `specify_cli` import (C-001). Keep `engine._append_event` append-only. Run `tests/runtime tests/next` plus `tests/architectural/test_layer_rules.py`. The T020 foreign-append reproduction is FR-010's red proof; the Rule 1 runtime scan arrives later in WP08. Handoff: `runtime_bridge.py` is edited again by WP07 (board override); `tests/next/test_runtime_bridge_unit.py` again by WP06 (template path).

---

## Work Package WP06: next reads the pack runtime templates; in-flight runs keep working (Priority: P1)

**Goal**: The runtime resolves built-in runtime templates from `packs/built-in/missions` through `charter.activation.mission_type_profile_repository.builtin_missions_root()`, with the same tier order. The four `src` `mission-runtime.yaml` copies are deleted, and the runtime→specify_cli ledger drops from 23 to 22. Each pack runtime template matches what the CLI runs today (FR-023): software-dev and plan take the src content, while the documentation and research bytes stay unchanged. In-flight runs keep working.
**Independent Test**: `tests/runtime/test_pack_runtime_template_parity.py`: for each type, the resolved template plans the same step sequence and the same dispatch route per step as the committed baseline fixture recorded from today's resolver (NFR-006, SC-009). The software-dev analyze step is exempt from the start, so WP07 does not have to edit this test. A persisted run whose recorded src path is gone still advances and answers query mode (B1).
**Prompt**: `/tasks/WP06-canonical-runtime-templates.md`
**Requirement Refs**: FR-017, FR-018, FR-020, FR-023, NFR-006, C-001, C-004, C-008, NFR-005, C-006

### Included Subtasks

T025 Red-first: record today's resolved template plan per type (step sequence and dispatch route) into the committed fixture `tests/runtime/fixtures/runtime_template_baseline.json` BEFORE any copy is deleted; then show the pack software-dev/plan templates diverge (agent-profile routing widening, plan does not load) and that query mode on a run with a vanished recorded path raises `QueryModeValidationError` (WP06)
T026 Built-in tier via `builtin_missions_root()`, `PackRootNotFound` failing closed with a named error and a test; `mission_loader/command.py` switches to the same accessor and its `write_meta` goes through `locked_update_meta` (FR-020); both bare `import specify_cli` edges removed; the ledger entry removed, cap 23→22, and the `_baselines.yaml` justification updated (B8) (WP06)
T027 Reconcile the pack runtime templates per B2: software-dev and plan take the src content; documentation and research stay byte-unchanged. Delete the four src `mission-runtime.yaml` copies and the deprecation banner. Move every test that hard-codes the src runtime path (the owned test list) to the pack path, then run `spec-kitty doctrine regenerate-graph` if the manifest hashes them (B8) (WP06)
T029 Query mode loads `run_dir/mission_template_frozen.yaml`; the live path is used only for drift (B1); confirm the planner drift-skip keeps an in-flight software-dev run on its frozen order (FR-017) (WP06)
T059 CLI-entry red test: edit a pack runtime-template fixture (a copied pack root) and show that `spec-kitty next` ignores it today and honours it after the change (FR-018) (WP06)

### Dependencies

- Depends on WP05, WP02.

### Risks & Mitigations

- Only `mission-runtime.yaml` moves (C-008). Before trusting `tests/doctrine/test_doctrine_regenerate_graph_roundtrip.py`, reinstall with `pip install -e .` or `uv sync --frozen` (C13). Handoffs: WP14 does `mission.yaml` parity; WP07 edits `runtime_bridge_query.py`, `runtime_bridge_io.py` and the pack software-dev runtime template again (analyze); WP14, WP17 and WP11 edit `pack-manifest.yaml` and the graph files again.

---

## Work Package WP14: Pack mission.yaml equals the copy the CLI runs (Priority: P1)

**Goal**: Each built-in type's pack `mission.yaml` is byte-equal to the src copy the CLI reads today (operator ruling, FR-023). The unread `task_types` blocks and the documentation `deliverables: docs/output/` are dropped from the pack. Wording-only fixes ("feature" to "mission") land in both copies. The charter-bundle goldens that embed the pack `mission.yaml` are regenerated.
**Independent Test**: `tests/specify_cli/missions/test_pack_mission_config_parity.py`: pack and src `mission.yaml` are byte-equal for all four types while the src copy exists (SC-009).
**Prompt**: `/tasks/WP14-mission-config-parity.md`
**Requirement Refs**: FR-023, NFR-005, C-006

### Included Subtasks

T028 Red-first: the parity test fails on today's four pairs. Then confirm that no reader of the pack copy (`charter/offering/missions/repository.py`, `charter/activation/*`, `dossier/manifest.py`, the neutrality lint) consumes `task_types` or `paths.deliverables`; if one does, stop and raise an owner decision instead of dropping the key. Make the copies equal, with the wording fixes in both (WP14)
T055 Regenerate the charter-bundle goldens the compiler embeds (`compiler.py:1992-2005`) and run `spec-kitty doctrine regenerate-graph`; record every changed golden in the Activity Log, because the PR calls them out (WP14)

### Dependencies

- Depends on WP06.

### Risks & Mitigations

- `templates/` and the Python modules are out of scope (C-008). Handoff: WP17 and WP11 edit `pack-manifest.yaml` and the graph files again.

---

## Work Package WP07: next issues a guarded analyze step between tasks and implement (Priority: P1)

**Goal**: The software-dev runtime order becomes `discovery → specify → plan → tasks → analyze → implement → review → accept`. `analyze` completes only while the analysis report is current. Otherwise it is re-issued with `error_code` `ANALYSIS_REPORT_MISSING`, `ANALYSIS_REPORT_STALE` or `ANALYSIS_CURRENCY_UNAVAILABLE`, and `guard_failures` naming each stale input. The finalized-board override and query mode apply the same check before they hand out implement.
**Independent Test**: `tests/runtime/test_analyze_step.py` (US7): missing, stale and current reports on the analyze step; the finalized-board override with hand-run specify/plan/tasks in both decide and query modes (B3); the orchestrator-api `decide_next` path; a missing callable failing closed; error-code precedence; `_state_to_action("analyze")` and `_build_prompt_or_error` resolving; `_with_guard_failure_paths` rendering stale inputs; an in-flight frozen run keeping its order.
**Prompt**: `/tasks/WP07-analyze-step.md`
**Requirement Refs**: FR-016, FR-017, C-001, C-004, NFR-005, C-006

### Included Subtasks

T030 Red-first: today `next` after tasks returns implement while `agent action implement` refuses on the missing analysis report; the finalized-board override skips analyze (B3) (WP07)
T031 Add the analyze step to the pack software-dev runtime template (analyze stays `in_action_sequence: false`, C6) (WP07)
T032 Inject the analysis-currency callable inside the shared `next_cmd.decide_next` wrapper and route `orchestrator_api/decision_verbs.py` through it (B4); the bridge computes the verdict into `status_facts` only for `analyze` or the board override, so the cores module stays pure (B5) (WP07)
T033 `analyze` guard in `_evaluate_software_dev_guards`, error codes in `decision.py`, the precedence rule (a prompt-resolution failure wins), and the board override in decide and query modes (B3, B5) (WP07)
T056 Update the tests that pin the software-dev tasks→implement order and go red; check whether the `runtime_bridge_composition.py` tasks→implement advance can skip analyze, and add a red test and a fix if it can. Record every other test that turns red, and its fix, in the Activity Log (WP07)
T060 CLI-entry test: `spec-kitty next --json` after tasks issues analyze with `ANALYSIS_REPORT_MISSING`; after `record-analysis`, `next --result success` advances to implement (SC-005, US7) (WP07)

### Dependencies

- Depends on WP14.

### Risks & Mitigations

- The runtime gets the callable injected; it imports nothing new from `specify_cli` (C-001). The callable wraps `analysis_report.check_analysis_report_current`. `status_facts` is built in `runtime_bridge_io.py`, and B5 puts the verdict there. The WP06 parity test already exempts the analyze step.

---

## Work Package WP08: Mission write discipline gate: Rules 1 and 3 (Priority: P1)

**Goal**: With an empty allowlist, Rule 1 catches whole-file rewrites and replaces of status and run logs, including in `src/runtime`, while appends and fresh-snapshot publishes stay legitimate by a stated structural rule. Rule 3 accepts only `mission_lock_key(...)` for keys and only `mission_write_lock_dir(...)` or a parameter for paths.
**Independent Test**: `tests/architectural/test_mission_write_discipline.py`: a synthetic offender, a near-miss negative and a self-mutation proof per extended rule (NFR-004); both rules pass on the real tree.
**Prompt**: `/tasks/WP08-gate-rules.md`
**Requirement Refs**: FR-007, FR-008, NFR-004, NFR-005, C-006

### Included Subtasks

T034 Rule 1 (FR-008, A7): track target names assigned from the log, meta and state filenames through assignments and `/` joins. Sinks: truncate, `write_text`, `write_bytes`, `open` in w/x/r+ modes, `shutil.move` onto a target, and a whole-file `os.replace`/`atomic_write` onto a target. Structural near-misses that are not sinks, each with a test: an append-only `"a"` open (`engine._append_event`, `status/store.py`), and the tmp-then-`os.replace` publish of a freshly built snapshot (`engine._write_snapshot`). Scan `src/runtime` with the run-log and run-state names. Fix the consolidation bookkeeping projection (rewrite under the status lock) and the lane auto-rebase create-if-missing (exclusive create). Confirm WP13's dispositions of `rebuild_state.py` and `migrate_lifecycle_envelope.py` pass. Exclude the merge driver by a stated structural rule (WP08)
T036 Rule 3 (FR-007, A6): keys only as `mission_lock_key(...)`; paths as `mission_write_lock_dir(...)` or a function parameter; a bare `.name` is refused (WP08)

### Dependencies

- Depends on WP03, WP04, WP07.

### Risks & Mitigations

- Fix real-tree hits in the owning code, never by allowlisting. When a hit sits in a file this WP does not own, make the minimal fix, list the file in the Activity Log as a handoff, and name it in the review request.

---

## Work Package WP15: Mission write discipline gate: Rules 2 and 4 (Priority: P1)

**Goal**: Rule 2 treats every non-call reference to the callable parameter as an escape. New Rule 4 keeps `meta.json`, `tasks/WP*.md` and `tasks.md` writes inside a lock region or a registered locked helper, with region recognition that is structural, not name-based.
**Independent Test**: `tests/architectural/test_mission_write_discipline.py`: a synthetic offender, a near-miss negative and a self-mutation proof for Rules 2 and 4 (NFR-004); both rules pass on the real tree with an empty allowlist.
**Prompt**: `/tasks/WP15-gate-rules-2-and-4.md`
**Requirement Refs**: FR-006, FR-019, NFR-004, NFR-005, C-006

### Included Subtasks

T035 Rule 2 (FR-006, A11): any non-call-func reference to the parameter, including passing it as an argument or keyword or capturing it in a nested def or lambda, is an escape; an unresolvable callee fails closed (WP15)
T037 Rule 4 (FR-019, A5). Regions: a lexical lock `with`, `ExitStack.enter_context(<lock cm>)`, `__enter__`..`__exit__`, a `with` on a name assigned from a lock cm, and `locked_acceptance_verdict_guard`. A sink in function F is accepted when F is a registered locked helper or every same-module call site of F sits in a region. Unresolvable cross-module callers fail closed. `write_frontmatter`/`update_fields` are sinks only when the target resolves to `tasks/WP*.md` or `tasks.md`, so `review/prompt_metadata.py`'s temporary file is a near-miss (C-007). No name-based exemptions; the merge-driver exclusion applies (WP15)

### Dependencies

- Depends on WP08.

### Risks & Mitigations

- Fix real-tree hits in the owning code, never by allowlisting. When a hit sits in a file this WP does not own, make the minimal fix, list the file in the Activity Log as a handoff, and name it in the review request. Rule 4's cross-call-site region analysis is the heavy part: keep each helper ≤ 15 complexity, with its own tests.

---

## Work Package WP09: Step contracts and the tasks-family prompts (Priority: P1)

**Goal**: Every built-in step contract renders a bootstrap command the CLI accepts, and the software-dev contracts carry no stale text. The tasks, tasks-outline, tasks-packages and tasks-finalize prompts and `tasks/guidelines.md` describe what the CLI does. In particular they name `/spec-kitty.analyze` as required before implement, with its staleness rule (FR-015).
**Independent Test**: `tests/doctrine/mission_step_contracts/test_contract_bootstrap_commands.py`: renders each contract's bootstrap command through `_render_declared_command` and parses it against the Click command. `tests/prompts/test_tasks_prompts_name_analyze.py`: section-scoped asserts that the report and next-step sections name analyze as required and state the staleness rule.
**Prompt**: `/tasks/WP09-pack-software-dev-cleanup.md`
**Requirement Refs**: FR-015, FR-022, C-003, NFR-005, C-006

### Included Subtasks

T038 Red-first: both new tests fail on today's files (`charter context --profile/--tool` refused; the tasks report sections do not require analyze) (WP09)
T039 Step contracts: drop the `--profile`/`--tool` bootstrap inputs in every built-in contract (C1, the one Locality exception); fix the C2 items; update `test_shipped_contracts.py` (WP09)
T040 Tasks-family prompts and `tasks/guidelines.md`: analyze required with its staleness rule (FR-015), dedupe, false "next advances" claims, the template reference (C6), the dependency command, provenance tokens, "feature" wording, `/ad-hoc-profile-load`; the `tasks-finalize/step.yaml` dependency on tasks-packages; update the pinning tests (C7) (WP09)

### Dependencies

- Depends on WP07.

### Risks & Mitigations

- Do not raise the provenance ratchet counts: the baseline is lowered in WP17, so edits here must not add tokens. If an edit trips the ratchet's shrink rule because a count dropped, lower that file's entry here by hand (C8). Handoff: WP17 regenerates the graph and snapshots.

---

## Work Package WP16: Other software-dev prompts and pack files (Priority: P1)

**Goal**: The analyze, accept, implement, review, plan and specify prompts, the README files, `expected-artifacts.yaml`, the governance profile and the analyze `step.yaml` describe what the CLI does: the R7 items plus C3, C4, C5 and C10.
**Independent Test**: `tests/prompts/test_software_dev_prompt_sections.py`: section-scoped asserts for each fixed item. These cover the accept worktree root, the implement analysis gate and its absence of retired paths, the analyze staleness rule and recovery recipe, `--mission` on `next` and `move-task`, and the "every command that accepts `--mission`" wording.
**Prompt**: `/tasks/WP16-software-dev-prompts-and-pack-files.md`
**Requirement Refs**: FR-022, C-003, NFR-005, C-006

### Included Subtasks

T041 Red-first, then the prompts: the analyze, accept, implement, review, plan and specify prompts get the R7 items plus C3 (`--mission` boilerplate), C4, C5 and C10 (the recovery recipe outside the checkout) (WP16)
T042 Pack files: `software-dev/README.md`, `missions/README.md`, `expected-artifacts.yaml` (retired tasks_* ids; the analysis report on implement), `governance-profile.yaml`, and `analyze/step.yaml`, which depends on tasks; update the pinning tests (C7) (WP16)

### Dependencies

- Depends on WP09.

### Risks & Mitigations

- The specify prompt change requires regenerating the rendered snapshots; WP17 owns those and regenerates them. Do not raise any provenance ratchet count (C8).

---

## Work Package WP17: Scripted prompt walk gate, ratchet, snapshots and graph (Priority: P1)

**Goal**: SC-008 is enforced by a gate: a scripted walk of the software-dev step prompts and contracts finds 0 refused instructions and 0 non-existent references. The provenance ratchet baseline counts are lowered, the rendered snapshots are regenerated, and the graph is regenerated.
**Independent Test**: `tests/doctrine/test_software_dev_prompt_walk.py` (C12) extends `test_builtin_cli_command_references.py`:
  1. command paths and each `--option` resolve against Click;
  2. rendered step-contract `command:` values parse;
  3. every "next advances to X" claim matches the runtime order;
  4. consumer paths resolve against a `spec-kitty init` fixture with an explicit placeholder list.

  It covers the CLI-driven implement, review, accept and tasks-finalize prompts.
**Prompt**: `/tasks/WP17-prompt-walk-gate.md`
**Requirement Refs**: FR-022, C-003, NFR-005, C-006

### Included Subtasks

T057 Red-first: write the walk gate and show it failing against the pre-cleanup prompt tree (a temporary `git worktree add` at the WP09 base commit, removed afterwards), then passing on the current tree (WP17)
T043 Lower the ratchet baseline by hand, entry by entry, so the diff only goes down (C8). Regenerate the rendered snapshots with the repository's snapshot update flag. Run `spec-kitty doctrine regenerate-graph`, reinstall, then run the regenerate-graph roundtrip test and `tests/doctrine/test_builtin_cli_command_references.py` (WP17)

### Dependencies

- Depends on WP16.

### Risks & Mitigations

- Never `git stash`; use a temporary worktree for the pre-fix comparison and remove it. Handoff: WP11 edits `pack-manifest.yaml` and the graph files again.

---

## Work Package WP10: Operator-facing text and generated commits say mission (Priority: P1)

**Goal**: The five planning commit builders and the operator-facing CLI errors say "mission". The finalize drift check accepts both the new and the legacy subjects. An AST scan keeps "for feature" out of operator text. commitlint covers every planning subject for both words.
**Independent Test**: `tests/specify_cli/test_no_for_feature_operator_text.py` (FR-014, C9): scans every non-docstring string constant under `src/specify_cli` for "for feature" or a leading "Feature:"; a synthetic offender per construction form (f-string, concatenation, variable).
**Prompt**: `/tasks/WP10-mission-wording.md`
**Requirement Refs**: FR-012, FR-013, FR-014, NFR-005, C-006

### Included Subtasks

T044 Red-first: the FR-014 scan fails on today's tree, and so does the drift check on a legacy-subject Mission. The scan gets two structural exemptions, each with a test: the legacy-subject constant the drift check must keep (a module-level constant named for that purpose), and hosted-only modules (`tracker/saas_*`, C-007) (WP10)
T045 Commit builders: finalize planning pin, `mission_setup_plan` (spec/plan setup, gap analysis, generator config), `core/mission_creation_commit`; the drift check accepts the old and new subjects (FR-013) (WP10)
T046 CLI errors from R8 and C9; `FEATURE_CONTEXT_UNRESOLVED` stays (machine contract) and is filed as a follow-up (WP10)
T047 commitlint: the planning-subject rule covers the scaffold, gap-analysis, generator-config and origin-ticket-binding subjects for both words; update tests and goldens that assert the old text (R8, C7) (WP10)
T061 CLI-entry test: `spec-kitty agent mission finalize-tasks` on a fixture Mission writes a commit whose subject says "for mission" (FR-012) (WP10)

### Dependencies

- Depends on WP03, WP04.

### Risks & Mitigations

- Golden and fixture files that assert the old subjects (R8, C7 wording pins) change in this WP. Find them with `grep -rn "for feature" tests`. `src/specify_cli/verify_enhanced.py` (`"   Feature: "`) is in scope. Handoff: `acceptance/__init__.py` and `mission_type.py` were last edited in WP02 or WP03, `mission_setup_plan.py` in WP03, and `implement_phases.py` in WP13. `tests/next/test_next_command_integration.py:556` asserts the old "Canonical status not found for feature" text but is owned by WP06; update that one assertion here and record the handoff in the Activity Log.

---

## Work Package WP11: The glossary defines topic branch, Mission and Mission Run consistently (Priority: P1)

**Goal**: topic branch is added, Mission and Mission Run are rewritten, and feature branch becomes an alias of topic branch. All of this is consistent across `docs/context`, the YAML seed, the built-in glossary pack and the regenerated contextive glossaries. The R9 and C11 inconsistencies are fixed.
**Independent Test**: The glossary parity gates (`test_glossary_pack_parity.py`, `test_glossary_authority_parity.py`, `tests/glossary/test_seed_validation.py`) and `tests/architectural/test_no_legacy_terminology.py`; the regenerate-graph roundtrip.
**Prompt**: `/tasks/WP11-glossary.md`
**Requirement Refs**: FR-021, NFR-005, C-006

### Included Subtasks

T048 Entries: topic branch (new), Mission, Mission Run, feature branch → alias of topic branch, across the four surfaces (WP11)
T049 Fix the R9 and C11 inconsistencies (WP11)
T050 Regenerate the contextive glossaries (`scripts/generate_contextive_glossaries.py`) and the graph (`spec-kitty doctrine regenerate-graph`); the `test_no_legacy_terminology` baseline only shrinks (WP11)

### Dependencies

- Depends on WP17.

### Risks & Mitigations

- If a `docs/context` file named here does not exist, find the real one. This WP has no code-behaviour change, so red-first does not apply beyond the parity gates.

---

## Work Package WP12: CHANGELOG and architecture docs (Priority: P1)

**Goal**: `[Unreleased]` CHANGELOG entries describe the user-visible changes: the lock key, the locked writers, the runtime gate, the analyze step, the pack templates and config parity, the prompt cleanup and the wording. The "Mission write lock and rollback" section in `docs/architecture/status-model.md` describes the canonical key, the locked helpers and Rule 4.
**Independent Test**: `tests/docs/test_changelog_style.py`, `tests/docs/test_docs_index_freshness.py`, `tests/architectural/test_no_legacy_terminology.py`.
**Prompt**: `/tasks/WP12-changelog-and-docs.md`
**Requirement Refs**: C-005, C-007

### Included Subtasks

T051 CHANGELOG `[Unreleased]` entries in the repository's changelog style (WP12)
T052 status-model.md: canonical lock key, locked helpers, Rule 4; refresh the docs retrieval index if it is required (WP12)

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP05, WP06, WP07, WP08, WP09, WP10, WP11, WP13, WP14, WP15, WP16, WP17.

### Risks & Mitigations

- Describe behaviour, not WP ids or requirement ids.

---
