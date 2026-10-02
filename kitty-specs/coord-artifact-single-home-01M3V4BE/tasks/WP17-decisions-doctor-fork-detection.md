---
work_package_id: WP17
title: doctor decisions fork detection, honest verify, non-destructive repair, teardown and preflight refusal
dependencies:
- WP12
- WP09
requirement_refs:
- FR-009c
- FR-010
- FR-010a
- FR-011
- FR-016
- SC-004
- NFR-002
- C-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T090
- T091
- T092
- T093
- T094
- T095
- T096
phase: Phase 6 - Decision doctor and consolidation
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
agent: claude
authoritative_surface: src/specify_cli/decisions/fork.py
create_intent:
- src/specify_cli/decisions/fork.py
- tests/decisions/test_decision_fork_detector.py
- tests/consolidation/test_executor_ledger_preflight.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/decisions/fork.py
- src/specify_cli/decisions/verify.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- src/specify_cli/cli/commands/decision.py
- src/specify_cli/coordination/teardown.py
- src/specify_cli/consolidation/executor.py
- tests/decisions/test_decisions_reconciler.py
- tests/decisions/test_decision_fork_detector.py
- tests/specify_cli/decisions/test_verify_integration.py
- tests/coordination/test_projection_teardown.py
- tests/consolidation/test_executor_ledger_preflight.py
- src/specify_cli/cli/commands/mission_type.py
- tests/status/test_authoritative_non_lane_registry_4897.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP17 – doctor decisions fork detection, honest verify, non-destructive repair, teardown and preflight refusal

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`doctor decisions`, `decision verify`, coordination teardown and consolidation must stop losing or hiding decisions. When this WP is done:

- **One read-only detector, `src/specify_cli/decisions/fork.py`**, compares both decision-event streams (`status.events.jsonl` decision events and `decisions.events.jsonl`) on both surfaces:
  - each surface is read from its working tree when present, else from its branch ref, so it works in a fresh clone;
  - it reports `forked` per stream and which decisions are on which surface (FR-010, US4.1).
- **`decision verify`** reports a forked Mission as not clean (`DECISION_LOG_FORKED`, exit 1). This is proven separately from doctor (FR-010a, US4.2).
- **`doctor decisions --repair`**:
  - never removes an index entry whose events exist on either surface, prints the reconcile steps, and never re-sequences (FR-011, C-003, US4.3);
  - still repairs a genuine orphan on an unforked Mission (positive control, US4.4).
- **A pre-fix coordination-only ledger** is reported (`DECISION_LEDGER_ONLY_ON_COORDINATION`), and `--repair` copies it additively into the PRIMARY-partition ledger dir with no auto-commit (FR-009c, US4.5).
- **Coordination teardown and consolidation refuse** to destroy a coordination branch that holds the only copy of a ledger (`COORDINATION_LEDGER_UNREPAIRED`, hint `spec-kitty doctor decisions --repair`; US4.6). The consolidation porcelain-invariant refusal for uncommitted ledger dirt, which is real work now that WP12 reclassified the ledger, names `accept`/`spec-commit`.
- **NFR-002 / SC-004:** across the four fork fixtures, 0 index entries and 0 events are lost.

## Context & Constraints

- **Spec**: FR-009c, FR-010, FR-010a, FR-011, FR-016 (R3, R14, R15, R16), SC-004, NFR-002, C-003; US4.1-4.6.
- **Plan**: IC-12. Shared-file map: `consolidation/executor.py` is touched by IC-11's reader message (here), IC-12 (here) and IC-18 (WP18). This WP is first; WP18 follows **in the same lane**.
- **Research**:
  - D14: detector inputs and callers;
  - D15: teardown refusal and the preflight;
  - D12: the consolidation porcelain invariant (`executor.py` ≈L2033-2041, inside `_phase_porcelain_invariant` at L2013) now treats ledger dirt as real work, so its message must name `accept`/`spec-commit`.
- **Contracts**: `contracts/doctor-decisions-fork-report.md` (report shape, rules 1-6, codes). Value objects are in `data-model.md` §4 (`SurfaceLog`, `StreamForkFinding`, `LedgerHomeFinding`, `DecisionsForkReport`).
- **Depends on**:
  - WP12: `DECISION_LEDGER` is PRIMARY; `artifacts.py`.
  - WP02: the NFR-002 fork fixtures `fork_fixture` (a)-(d) and the probes in `tests._factories.coord_mission`.
- **Charter**: `.kittify/charter/charter.md`; `spec-kitty charter context --action implement`. ATDD-first (C-011).
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: say Mission, never feature. "PRIMARY partition" (where the ledger lives), "repository root checkout", "target branch", "coordination branch/surface". Never write bare "primary".
- **C-003**: never merge or re-sequence forked logs automatically; detect and guide only.
- **C-004**: fix forward; the repair is additive and rewrites no history.
- **Brownfield scout (binding read)**: before coding, read `## WP17` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP17 --agent claude`, and use the resolved workspace path.
- **Lane sharing**: `src/specify_cli/consolidation/executor.py` is shared with WP18, which depends on this WP. That overlap is dependency-ordered and deliberate, so it runs in **lane B**: WP17 → WP18. Keep your executor edits to the three sites named in T096 so WP18's diff stays clean.

## Subtasks & Detailed Guidance

### Subtask T090 – Red-first reproductions over the NFR-002 fork fixtures (ATDD commit)

- **Purpose**: Pin each defect through its pre-existing entry point (C-005, FR-016) before any fix.
- **Steps**:
  1. **R3** `tests/decisions/test_decisions_reconciler.py::test_repair_never_drops_entries_on_forked_log`:
     - use WP02 fixture (a), root uncommitted plus coordination untracked (the #5519 shape);
     - count `decisions/index.json` entries, run the CLI `spec-kitty doctor decisions --mission <M> --repair --json`, count again;
     - assert the count is unchanged and the output names the fork.
     - Red at base: `_diagnose` builds `orphaned_in_index` from one surface's log (`_decisions_doctor.py:397`), and `_repair` drops those entries.
  2. **R15** `::test_doctor_reports_fork_from_refs_only`:
     - use fixture (c), a fresh clone of (b) with no coordination worktree;
     - run `doctor decisions --json` and assert `forked: true` with per-surface decision ids.
     - Red at base: the field is absent and the report is clean.
  3. **R16 (doctor half)** `::test_doctor_reports_and_repairs_coord_only_ledger`:
     - use fixture (d), a ledger only on the coordination branch;
     - assert `DECISION_LEDGER_ONLY_ON_COORDINATION` is reported;
     - after `--repair`, assert the missing `DM-*.md` files and index entries exist in the PRIMARY ledger dir, and no new commit was created.
  4. **R16 (teardown half)** `tests/coordination/test_projection_teardown.py::test_teardown_refuses_coord_only_ledger`: on fixture (d), `teardown_coordination_topology(...)` raises `ProjectionTeardownAbort` with `error_code == "COORDINATION_LEDGER_UNREPAIRED"`, and the coordination branch still exists.
  5. **R14** `tests/specify_cli/decisions/test_verify_integration.py::test_verify_not_clean_on_forked_log`: CLI `spec-kitty agent decision verify --mission <M> --json` on fixture (a) exits 1 with `DECISION_LOG_FORKED` in `findings[]`. At base it exits 0.
  6. Preflight: `tests/consolidation/test_executor_ledger_preflight.py::test_consolidation_preflight_refuses_coord_only_ledger` (`_pre_mutation_safety_preflight` refuses on fixture (d) before any ref moves). Also add `::test_porcelain_invariant_names_accept_for_ledger_dirt`.
  7. Run on your base. Confirm each is red for the stated reason, commit them alone (`test(decisions): red-first fork/repair/verify/teardown reproductions (WP17)`), and record the red evidence in the activity log.
- **Files**: the five test files above.
- **Edge cases**:
  - Fixture (b) committed both sides; its fork is visible in both refs and worktrees, so assert both inputs.
  - Use the WP02 probes (`event_ids`, `coord_tree_has`) rather than ad-hoc git calls.
  - No `xfail`.
- **R14 parametrized (post-tasks squad R-m1)**: parametrize `test_verify_not_clean_on_forked_log` over WP02's fork fixtures (a) root-uncommitted + coordination-untracked, (b) both committed, (c) fresh clone. Each must exit 1 with `DECISION_LOG_FORKED`.

### Subtask T091 – `detect_decision_forks` (read-only detector)

- **Purpose**: One detector shared by doctor, verify and teardown (research D14; DIRECTIVE_044, one authority).
- **Steps**:
  1. Create `src/specify_cli/decisions/fork.py` with frozen dataclasses per data-model §4: `SurfaceLog`, `StreamForkFinding`, `LedgerHomeFinding`, `DecisionsForkReport`. Use `Literal` types for `surface`, `source` and `state`.
  2. Define `detect_decision_forks(repo_root: Path, mission_slug: str) -> DecisionsForkReport`:
     - **PRIMARY side**: the repository root checkout's Mission dir (`placement_seam(...).read_dir(PRIMARY_METADATA)`) when the stream file is present; else `git show <target_branch>:kitty-specs/<dir>/<stream>` (target branch from `meta.json`).
     - **COORD side**: `CoordinationWorkspace.worktree_path` (coordination/workspace.py) when the Mission dir exists there; else `git show <coordination_branch>:kitty-specs/<dir>/<stream>` (`coordination_branch` from `meta.json`).
     - **Streams**: `status.events.jsonl` (decision events only, filtered by `event_type` prefix `Decision`; use the project's event parser rather than ad-hoc JSON) and `decisions.events.jsonl`.
     - **State per stream**: `absent` (neither side), `single_home` (one side only), `prefix` (one event-id sequence is a prefix of the other), `forked` (both non-empty, neither a prefix).
     - **Decision ids** grouped as only-on-primary, only-on-coordination and on-both.
     - `forked = any(stream.state == "forked")`; `reconcile_steps` is a tuple of human-readable steps (printed, never executed).
  3. **READ-ONLY**: never call `write_dir`, `materialize_coord_surface_for_write` or anything that creates worktrees. Assert this in a test by checking that `git worktree list` is unchanged.
  4. For non-coordination topologies, report the PRIMARY side only, with a `single_home` or `absent` state.
  5. Keep each function ≤ 15 C901: split the reading (`_read_stream(surface, ...)`), the comparison (`_classify_stream(R, C)`) and the grouping. Consider reusing WP03's pure prefix classifier if it is importable (`coord_seed`'s classifier) rather than duplicating the prefix rule. If it lives in `specify_cli.coordination.coord_seed`, importing it from `decisions/` is fine (same package); otherwise lift it.
- **Files**: `src/specify_cli/decisions/fork.py`; `tests/decisions/test_decision_fork_detector.py`, with table-driven tests over the four fixtures and each state, plus a non-coordination control.
- **Validation**: unit tests green; `tests/architectural/test_no_dead_symbols.py` passes, since the new public symbols are used by doctor, verify and teardown.
- **Edge cases**:
  - Malformed JSONL lines: surface them as a finding, never crash, never drop.
  - A missing branch (DELETED): treat that side as absent and add a warning.
  - `<dir>` naming: use the canonical Mission dir name (slug including mid8 where applicable) exactly as the seam resolves it.
- **Mandatory reuse (post-tasks squad P-M6, P-M4)**: classify streams with WP03's pure `coordination/event_prefix.py` classifier; no second prefix/fork implementation. Compose every Mission dir name only via `lanes.branch_naming` (`coord_mission_dir_name` and siblings); never hand-join `<slug>` or `<slug>-<mid8>`. Read the legacy `kitty-specs/<slug>/decisions.events.jsonl` shape exactly as WP09 ruled (this WP now depends on WP09).
- Keep `tests/architectural/test_no_worktree_name_guess.py` green as a general gate. It is not the P-M3 guard; P-M3 is enforced by WP20.

### Subtask T092 – `coordination_only_ledger`

- **Purpose**: Detect pre-fix Missions whose ledger was committed only on the coordination branch (FR-009c; the bookkeeping projection at `bookkeeping_projection.py:481` excludes PRIMARY kinds, so such a ledger would be lost at teardown).
- **Steps**:
  1. Define `coordination_only_ledger(repo_root, mission_slug) -> LedgerHomeFinding`.
  2. The PRIMARY side is `decisions/` in the repository root checkout's Mission dir, or at the target ref when absent there.
  3. The coordination side is `git ls-tree`/`git show` of `kitty-specs/<dir>/decisions/` on the coordination branch. Prefer refs here: the worktree copy may be stale, and the branch is what teardown destroys.
  4. Compute `entries_only_on_coordination` (index entries by `decision_id`) and `dm_files_only_on_coordination`, and derive `state` (`primary` / `coordination_only` / `both` / `absent`).
  5. Include it in `DecisionsForkReport.ledger`.
- **Files**: `fork.py`, `tests/decisions/test_decision_fork_detector.py`.
- **Validation**: fixture (d) yields `coordination_only`; a post-fix Mission yields `primary`; a Mission with no decisions yields `absent`.
- **Edge cases**: the coordination branch is missing yields `absent`/`primary` with no exception; the index exists but the DM file is missing (or vice versa) is reported per item.

### Subtask T093 – `doctor decisions` diagnosis: two-surface orphan rule and fork report

- **Purpose**: FR-010; contract rule 1.
- **Steps**:
  1. In `_decisions_doctor._diagnose` (L372), call `detect_decision_forks`.
  2. Replace the single-surface orphan computation (`orphaned_in_index=sorted(index_ids - log_ids)` at ≈L397): an id is orphaned only when absent from **every** stream on **both** surfaces (the union of all ids in the report).
  3. Extend the report dataclass (≈L101) additively with `forked`, `streams`, `ledger` and `reconcile_steps`.
  4. JSON (≈L519): add the keys per the contract envelope.
  5. Text (≈L500): one line per stream and surface, then the reconcile steps.
  6. Findings: `DECISION_LOG_FORKED` when `forked`; `DECISION_LEDGER_ONLY_ON_COORDINATION` when the ledger state is `coordination_only`, or `both` with entries only on the coordination side.
  7. Update `clean` (≈L128) so forked or coordination-only-ledger Missions are not clean.
  8. The ledger stays read on the PRIMARY partition (`_decisions_doctor.py:146-156`; FR-009a, WP12's ratchet). Do not change that read.
- **Files**: `src/specify_cli/cli/commands/_decisions_doctor.py`, `tests/decisions/test_decisions_reconciler.py`.
- **Validation**: R15 is green; existing reconciler tests (#4919 malformed folds, `status_mismatch`) stay green.
- **Edge cases**: a genuinely orphaned entry on an unforked Mission is still reported as orphaned (US4.4 control).

### Subtask T094 – Non-destructive `--repair` and coordination-only ledger copy

- **Purpose**: FR-011, FR-009c; contract rules 2-4.
- **Steps**:
  1. In `_repair` (L404) and `run_decisions_reconciliation` (L529; repair gate ≈L572, exit ≈L589):
     - when `forked` is true, perform **no** index rewrite for the forked decisions, print `reconcile_steps`, and exit 1 (C-003: no re-sequencing);
     - non-forked missing entries may still be added, but never remove an entry whose events exist on either surface.
  2. On an unforked Mission, keep today's repair: drop a genuine orphan and add `missing_from_index`. This is the positive control.
  3. Coordination-only ledger:
     - copy the missing `DM-*.md` files from the coordination ref into the PRIMARY ledger dir (the `_ledger_dir` resolution that `decisions/service.py` already uses: PRIMARY_METADATA);
     - union-merge the missing index entries into `index.json`;
     - do both under the existing `index.json.lock` (`_LOCK_FILENAME`, L86);
     - additive only: never overwrite an existing PRIMARY entry or file.
  4. Print the commit hint `spec-kitty spec-commit -m "…" kitty-specs/<dir>/decisions/`. Make **no commit** (FR-009b: the existing PRIMARY committers commit it).
  5. Exit codes:
     - forked: 1;
     - malformed remaining: 1 (today's behaviour);
     - otherwise 0.
- **Files**: `_decisions_doctor.py`, `tests/decisions/test_decisions_reconciler.py`.
- **Validation**: R3 and R16 (doctor half) are green; US4.4 control is green; NFR-002 assertion across fixtures (a)-(d): entry count after ≥ before, and no event file modified.
- **Edge cases**:
  - The index merge must use the same entry ordering as the index writer (`created_at`, then `decision_id`) so the result is deterministic.
  - A DM file present on both sides with different content: keep the PRIMARY one, and report the difference.
- **Shared union (P-M6)**: the coordination-only-ledger repair merges index entries with WP11's pure `union_decision_index(ours, theirs)`. Do not write a second union.

### Subtask T095 – `decision verify` reports forks

- **Purpose**: FR-010a; contract rule 5.
- **Steps**:
  1. In `decisions/verify.py::verify` (L104), call `detect_decision_forks(repo_root, mission_slug)`. Resolve `repo_root` from `mission_dir` the way the module already does, or extend the signature carefully; the `mission_slug` parameter is currently unused (`# noqa: ARG001`), so start using it and drop that noqa.
  2. Add the finding `DECISION_LOG_FORKED`, with the forked decision ids, to `findings`.
  3. In the CLI `cmd_verify` (`cli/commands/decision.py:567-599`), make sure a forked result exits 1 and appears in JSON `findings[]`. Existing findings (`DEFERRED_WITHOUT_MARKER`, `MARKER_WITHOUT_DECISION`, `STALE_MARKER`) are unchanged.
  4. Keep `verify` C901 (10) ≤ 15. Put the fork check in a helper.
- **Files**: `src/specify_cli/decisions/verify.py`, `src/specify_cli/cli/commands/decision.py`, `tests/specify_cli/decisions/test_verify_integration.py`.
- **Validation**: R14 is green; an unforked Mission still verifies clean (control).
- **Edge cases**: verify runs in a fresh clone (refs only), and works there because the detector is read-only.

### Subtask T096 – Teardown, consolidation preflight and porcelain-invariant refusals

- **Purpose**: FR-009c, US4.6; research D15 and D12.
- **Steps**:
  1. **Teardown.** In `coordination/teardown.py::teardown_coordination_topology` (L222), at the top, before the projection gate at ≈L283:
     - call `coordination_only_ledger(repo_root, mission_slug)`;
     - when entries or DM files exist only on the coordination side, raise `ProjectionTeardownAbort` (L90) with a new error code `COORDINATION_LEDGER_UNREPAIRED`.
     - The class currently pins `error_code = "PROJECTION_TEARDOWN_ABORTED"` as a class attribute, so add an instance-level override (for example an `error_code` kwarg in `__init__`) without breaking existing callers.
     - The message names the Mission, the coordination branch and the hint `spec-kitty doctor decisions --repair`.
     - This covers every caller: consolidate abort (`cli/commands/consolidate.py` ≈L408), close/discard (`mission_type.py` ≈L1144) and consolidation (`executor.py` ≈L3126). Verify each caller renders `error_code` and the message, and does not swallow it.
  2. **Consolidation preflight.** In `consolidation/executor.py::_pre_mutation_safety_preflight` (L3450), refuse with the same code before any mutation (NFR-001 byte-identical-to-pre-invocation principle stated in its docstring).
  3. **Porcelain invariant.** In `_phase_porcelain_invariant` (L2013; the predicate wiring is at ≈L2033-2041), the residue predicate no longer exempts uncommitted `decisions/` files now that the ledger is PRIMARY (WP12). Make the refusal message name the remedy: commit them with `spec-kitty accept` or `spec-kitty spec-commit … kitty-specs/<dir>/decisions/`. Message-only change; do not alter the predicate.
  4. Edit **only** these three executor sites. IC-18's edits (`_run_lane_based_consolidation` ≈L4181 and `_phase_baseline_and_surface` L825) are WP18's.
- **Files**: `src/specify_cli/coordination/teardown.py`, `src/specify_cli/consolidation/executor.py`, `tests/coordination/test_projection_teardown.py`, `tests/consolidation/test_executor_ledger_preflight.py`.
- **Validation**:
  - R16 (teardown) and the preflight tests are green.
  - `tests/consolidation/test_single_rollback_authority.py` (AST-pinned caller set) and `tests/consolidation/test_coord_teardown_order_3926.py` stay green.
  - A post-fix Mission (ledger PRIMARY) tears down normally (control).
- **Edge cases**:
  - The coordination branch is already deleted: no ledger to protect, so no refusal.
  - `--abort` (consolidate) must refuse too; per CLAUDE.md, rollback restores before clearing the record, so the refusal happens before any teardown.
- **Caller rendering (post-tasks squad P-m1)**: `consolidate.py` (≈L408) and `mission_type.py` (≈L1144) are not owned. Scope to reporting: verify through each CLI entry that the `COORDINATION_LEDGER_UNREPAIRED` message and hint reach the operator via the existing `ProjectionTeardownAbort` rendering. If a caller swallows it, record a follow-up in the activity log instead of editing those files.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **`ProjectionTeardownAbort` (teardown.py:90; operator decision)**:
  - today `error_code` is a class attribute, `__init__(*, reason, coord_ref, expected_sha, actual_sha=None)` has a required `expected_sha`, and the message hard-codes the remedy "re-run the merge (`spec-kitty consolidate --resume`)";
  - add a **kw-only `error_code` override**, a **`remedy` override** and an **optional `expected_sha`**;
  - existing callers stay unchanged.
- **`fork.py` imports (shrink-only door gate `tests/architectural/test_status_unsafe_allowlist.py`)**:
  - never `import specify_cli.status.store`, never `from specify_cli.status import store`, never import any `append_*`;
  - `from specify_cli.status.store import read_events` is fine;
  - for ref reads, parse the bytes with an existing non-door parser.
  - `teardown.py` late-imports `decisions.fork` (stdlib-only top-level imports).
- **New raises in no-raise callers (operator decision)**: `mission_type.py:1144` (discard/close) carries the comment "this never raises". This WP now owns `src/specify_cli/cli/commands/mission_type.py`.
  - Handle `ProjectionTeardownAbort(COORDINATION_LEDGER_UNREPAIRED)` there: render the refusal and the hint, exit non-zero, no partial teardown. Update the comment and add a test.
  - `consolidate.py:408` (`--abort`, after the rollback restore) is unowned. Verify through the CLI that the message reaches the operator; if it is swallowed, report it per the Pre-existing Failure Reporting Rule.
  - The `executor.py:3126` path is covered by the preflight.
- **`_diagnose(events_dir, ledger_dir, mission_slug)` has no `repo_root`**: thread it from `run_decisions_reconciliation` (L529) as a kw-only parameter with a default. `tests/status/test_authoritative_non_lane_registry_4897.py` drives `_diagnose` directly; it is now owned, so re-pin it if needed.
- **`verify` is public API** (re-exported from `decisions/__init__.py:32`): add a kw-only `repo_root: Path | None = None`, or do the fork check in `cmd_verify` (`decision.py:568`).
  - Decide the `--no-fail-on-stale` precedence; the contract says a fork exits 1. Document it.
  - `decision.py` is co-owned with WP09 (dependency-ordered; same lane).
- **Doctor golden**: `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` (now owned) may need a refresh for the additive JSON.
- **Dead symbols**: every public name in `fork.py` needs a `src` importer. Keep the value-object dataclasses out of `__all__` unless doctor or verify imports them. Import WP11's `union_decision_index`; that also makes it live.
- **Reuse (P-M6)**: use WP03's `coordination/event_prefix.py` classifier, and compose dir names only via `lanes.branch_naming`.
- **Executor**: `_phase_porcelain_invariant` (L2013) uses `is_toolchain_generated_churn`; its topology handling is WP12's. Only the message changes here.
- R16 fixture (d) comes from WP02.
- **Gate citation fix**: `test_no_worktree_name_guess.py` is a general gate to keep green, **not** the P-M3 guard (it excludes `.parent.parent`). P-M3 is enforced by WP20.
- **C3 (round 4)**: update the help text and record reference deltas for WP22:
  - `doctor decisions` prints a fork report, and `--repair` exits 1 on a fork without ever dropping an entry;
  - `decision verify` exits 1 with `DECISION_LOG_FORKED`;
  - teardown/discard and consolidation refuse with `COORDINATION_LEDGER_UNREPAIRED`.
  The reference anchors are `docs/api/cli-commands.md` ≈L1864 (doctor decisions) and `docs/api/agent-subcommands.md` ≈L596 (decision verify).

## Targeted test surface

- WP tests: `uv run --frozen pytest tests/decisions/test_decisions_reconciler.py tests/decisions/test_decision_fork_detector.py tests/specify_cli/decisions/test_verify_integration.py tests/coordination/test_projection_teardown.py tests/consolidation/test_executor_ledger_preflight.py -q`.
- Owning-module directories (fast tier): `tests/decisions/`, `tests/specify_cli/decisions/`.
- Consolidation guards (named files):
  - `tests/consolidation/test_single_rollback_authority.py`
  - `tests/consolidation/test_rollback_authority.py`
  - `tests/consolidation/test_coord_teardown_order_3926.py`
  - `tests/consolidation/test_issue_4764_terminus_safety.py`
  - `tests/consolidation/test_coord_deleted_degrade_paths.py`
  - `tests/cli/commands/test_merge_status_commit.py`
- Baseline: `make test-fast`.
- Named architectural gates:
  - `tests/architectural/test_merge_reconciliation_class_guard.py`
  - `tests/architectural/test_layer_rules.py`
  - `tests/architectural/test_no_dead_symbols.py` (new public symbols)
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance/stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands and counts in the activity log. Classify unrelated reds per CLAUDE.md's baseline-red gotcha.
- Post-tasks squad additions (P-m1), each by name, never the directory (the same list as WP18 T102):
  - `tests/consolidation/test_reconciliation.py`, `test_reconciliation_divergent.py`, `test_squash_reconcilers_2709.py`;
  - `tests/consolidation/test_bookkeeping_projection_seam.py`, `test_issue_2709_projection_union.py`, `test_projection_source_status_fallback_2709.py`;
  - `tests/consolidation/test_done_bookkeeping_seam.py`, `test_done_bookkeeping_rollback_coherence.py`;
  - `tests/consolidation/test_canceled_content_residuals.py` (strict xfails stay xfail);
  - `tests/consolidation/test_single_rollback_authority.py`, `test_rollback_authority.py`;
  - `tests/architectural/test_no_worktree_name_guess.py`.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). `_diagnose`/`_repair`/`run_decisions_reconciliation` must stay under the ceiling; extract helpers.
- ruff check, ruff format --check, mypy --strict on changed files: 0 issues, no new suppressions (NFR-005). Remove the `ARG001` noqa on `verify` once `mission_slug` is used.
- ≥ 90% coverage of new and changed lines (NFR-003). `fork.py` is core domain logic, so apply higher rigour (tiered standards): table tests for every state.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #5023

## Definition of Done

- The red-first commit precedes the fixes; R3, R14, R15, R16 and the preflight tests are red at base and green at the end.
- `decisions/fork.py` is the single detector, used by doctor, verify, teardown and preflight; it is read-only.
- Repair never removes an entry with events on either surface; a forked repair exits 1 with reconcile steps; the unforked orphan control is green.
- The coordination-only ledger is reported and copied additively, with no commit.
- Teardown and preflight refuse with `COORDINATION_LEDGER_UNREPAIRED`; the porcelain refusal names accept/spec-commit.
- The NFR-002 zero-loss assertion over the four fixtures is green; quality gates are clean; the activity log is complete.

## Risks & Mitigations

- **Detector accidentally materializes** (breaks fresh clones): a test asserts the worktree list is unchanged, and the detector never imports writer APIs.
- **`ProjectionTeardownAbort` error-code change breaks callers**: keep the class default, add an override, and run every caller's test.
- **Executor lane conflict with WP18**: touch only the three named sites, and keep the diff small and local.
- **`verify` signature change ripples**: prefer deriving `repo_root` inside `verify` over changing callers.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green. The T090 tests are RED on the WP's base and GREEN on the final commit; the ATDD commit comes first.
- Check fresh-clone behaviour (fixture (c)): no worktree created, fork detected from refs.
- Check no auto-commit in repair, and no re-sequencing (C-003).
- Check the executor diff is confined to `_pre_mutation_safety_preflight` and the porcelain-invariant message.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T14:37:52Z – cursor – shell_pid=941655 – Cycle 2: --repair retains index entries whose events exist on either surface (prefix/single-home and the unmaterialized placeholder no longer wipe them). NFR-002 test over fixtures a-d plus the primary-event retention test: 5 passed in 51.69s. Commit b4ae55caf5.
