---
work_package_id: WP11
title: Decision index merge driver
dependencies: []
requirement_refs:
- FR-009b
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T10:13:06.238571+00:00'
subtasks:
- T059
- T060
- T061
- T062
- T063
phase: Phase 4 - Decision ledger
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/drivers.py
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_decision_index_merge_driver.py
- tests/consolidation/test_decision_index_merge_driver.py
- tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/case.json
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/O
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/A
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/B
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/expected_A
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/consolidation/drivers.py
- src/specify_cli/cli/commands/merge_driver.py
- src/specify_cli/cli/commands/init.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_decision_index_merge_driver.py
- .gitattributes
- tests/consolidation/test_decision_index_merge_driver.py
- tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py
- src/specify_cli/cli/commands/__init__.py
- src/specify_cli/_completion_manifest.json
- tests/consolidation/test_merge_drivers.py
- tests/consolidation/test_merge_driver_goldens.py
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/case.json
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/O
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/A
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/B
- tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/expected_A
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Decision index merge driver

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
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

When the decision ledger becomes a PRIMARY-partition record (WP12), `decisions/index.json` starts travelling with lane and Mission branches. Two lanes that each add a decision then both rewrite the same `index.json`, and a plain `git merge` either conflicts or (under `-X theirs`) silently drops one lane's entry. This WP adds a dedicated merge driver so lane integration never loses an index entry (FR-009b, US4.9).

Done means:
- R21 is green: two branches that each add a decision to `kitty-specs/<dir>/decisions/index.json` merge with both entries present, through a real `git merge` with the driver configured.
- A driver named `spec-kitty-decision-index` exists. It is registered in every surface its siblings are registered in:
  - `_MERGE_DRIVERS` (lanes/consolidation.py);
  - `MERGE_DRIVER_BODIES` (consolidation/drivers.py);
  - the `merge-driver-decision-index` CLI command;
  - the `init` seed constants and `.gitattributes` writer;
  - this repository's `.gitattributes`;
  - an upgrade migration for already-initialized clones.
- The union is deterministic: keyed by `decision_id`, with fold precedence on collisions, sorted by `created_at` then `decision_id`. Malformed input exits non-zero (a conflict) and never fabricates a merge.
- `DM-*.md` files get no driver: they are ULID-named, one file per decision, so they cannot collide.

## Context & Constraints

- **Spec**: FR-009b (ledger durability: commit point, clone, lane merge), US4.9.
- **Plan**: IC-11, the merge-driver half. The reclassification half is WP12.
- **Research**: D13 (decision-index merge driver), D12 (why the ledger now travels with lanes), R21.
- **Data model**: §1 (the `DECISION_LEDGER` partition moves from COORD to PRIMARY).
- **Charter**: load `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`. Canonical sources only: model the new driver on its siblings and do not invent a second registration path (DIRECTIVE_044).
- **Model discipline**: implement = sonnet (`claude-sonnet-5`), review = opus.
- **Terminology**: say Mission, never feature. Name the sense of "primary" every time: the PRIMARY partition, the repository root checkout, or the target branch.
- **C-006 / NO_FULL_HEAVY_SUITES_IN_MISSION**: run targeted files only.
- **Sibling precedent** (read these before writing code):
  - `run_review_cycle_driver` (consolidation/drivers.py ≈L1056);
  - `run_issue_matrix_driver` (≈L890);
  - `MERGE_DRIVER_BODIES` (≈L1116-1126);
  - `src/specify_cli/upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py`. Its docstring explains why `target_version` must not exceed the installed package version.
  - `m_3_2_6_decisions_event_log_merge_driver.py` and the shared `_merge_driver_seeding.py`.
- **Out of scope**: the class-guard amendment in `tests/architectural/test_merge_reconciliation_class_guard.py` belongs to WP12, which depends on this WP. If this WP on its own turns that guard red, stop and report it in the activity log rather than editing the guard.
- **Brownfield scout (binding read)**: before coding, read `## WP11` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- Execution worktrees are allocated per computed lane from `lanes.json` (written by `finalize-tasks`).
- Start with `spec-kitty agent action implement WP11 --agent claude`. Consume the workspace path it resolves; never reconstruct it.
- **Lane-relevant sharing**: none. This WP has no dependencies and its ownership is disjoint, so it can start in parallel from the beginning. WP12 depends on it.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T059 – Red-first R21: two lanes adding decisions merge without loss

- **Purpose**: Prove the loss before fixing it (C-005, charter ATDD-First). Commit this test on its own, before any driver code.
- **Steps**:
  1. Create `tests/consolidation/test_decision_index_merge_driver.py`.
  2. Build a throwaway git repository in `tmp_path`:
     - `git init -b main` and set `user.email` / `user.name`;
     - commit `kitty-specs/m-01ABCDEF/decisions/index.json` holding one entry (look up the real index schema in `src/specify_cli/decisions/` before writing the fixture; never invent fields);
     - branch `lane-a` adds entry `A`, branch `lane-b` adds entry `B`. Write both through the production index writer if one is reachable, or with JSON that matches the schema exactly.
  3. Seed the driver configuration the way production does:
     - `.gitattributes` line `kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index`;
     - `git config merge.spec-kitty-decision-index.driver "<python> -m specify_cli merge-driver-decision-index %O %A %B"`, or whatever invocation the sibling tests use. Copy the pattern from `tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py`.
  4. Check out `lane-a`, run `git merge lane-b`, and assert:
     - exit 0;
     - both `A` and `B` are in `entries`;
     - the original entry is preserved;
     - no conflict markers remain.
  5. Add `test_two_lanes_adding_decisions_merge_without_loss` as the R21 name. Add a unit-level sibling that calls the driver body directly with three temp files (base, ours, theirs).
- **Files**: `tests/consolidation/test_decision_index_merge_driver.py` (new).
- **Validation**: the test is red at the WP base. Without a driver, git conflicts on `index.json`, or `-X theirs` loses `A`. Paste the red output into the activity log.
- **Edge cases**:
  - Use the repo's real JSON layout of `index.json` (`entries` list vs map): read `decisions/store.py` and `index_fold.py`.
  - Mark the test the way the sibling driver tests are marked. Do not invent a marker.

### Subtask T060 – Union function with fold precedence and deterministic order

- **Purpose**: Define the merge semantics once (research D13).
- **Steps**:
  1. In `src/specify_cli/consolidation/drivers.py`, beside the other `run_*_driver` bodies, add `run_decision_index_driver(base_path: str, ours_path: str, theirs_path: str) -> MergeDriverOutcome`.
  2. Parse all three sides as JSON. If base is missing, use an empty index.
  3. Union `entries` keyed by `decision_id`:
     - an id present on only one side → taken as is;
     - the same id on both sides with equal content → kept once;
     - the same id with different content → resolve with the existing fold precedence in `src/specify_cli/decisions/index_fold.py` (`_select_terminal_event` ≈L215, `apply_terminal` ≈L144), so a terminal status (resolved / deferred / canceled) beats `open`;
     - two different terminal states for the same id → do NOT pick one silently. Return a conflict outcome, as the review-cycle driver does for genuine two-verdict collisions.
  4. Sort the output deterministically by `created_at`, then `decision_id`. Keep every other top-level key from `ours`; if the sides differ on such a key, follow the sibling drivers' rule for non-keyed fields.
  5. Write the result to `ours_path` (git's `%A`) with the same serializer the index writer uses: same indent and same trailing newline, so a no-op merge is byte-stable.
  6. Malformed JSON or a missing `decision_id` produces a non-zero exit (conflict) with a diagnostic on stderr. Never fabricate a merge.
- **Files**: `src/specify_cli/consolidation/drivers.py`.
- **Validation**: unit tests cover:
  - disjoint additions;
  - an identical entry on both sides;
  - `open` vs `resolved` (terminal wins in both directions);
  - two conflicting terminals → conflict outcome;
  - malformed `ours` → conflict;
  - byte-stable output for `ours == theirs`.

  Keep each helper's C901 at or below 15 by splitting parse, union and serialize.
- **Edge cases**:
  - `index_fold` helpers may be private (`_select_terminal_event`). Import the public entry if one exists. Otherwise expose a narrow public wrapper inside the decisions package. That needs an out-of-map one-line edit to `index_fold.py`, recorded with a rationale; prefer avoiding it if `apply_terminal` suffices.
  - Respect the module's `__all__` scoping note (drivers.py ≈L1132): only names another `src/` module imports go in `__all__`.
- **Pure, shared union (post-tasks squad P-M6)**: expose `union_decision_index(ours: Mapping[str, object], theirs: Mapping[str, object]) -> dict[str, object]` as a pure public function in `consolidation/drivers.py`. The merge-driver body is a thin IO wrapper around it. WP17's `doctor decisions --repair` reuses it for the coordination-only-ledger merge, so there is no second union implementation. Test it directly (keyed union, terminal-beats-open, deterministic order, malformed input raises).

### Subtask T061 – Register `spec-kitty-decision-index` (registry, consolidation, CLI)

- **Purpose**: Wire the driver everywhere its siblings are wired, with no second registration path.
- **Steps**:
  1. Add `"merge-driver-decision-index": run_decision_index_driver` to `MERGE_DRIVER_BODIES` (drivers.py ≈L1116-1126).
  2. Add a `_MergeDriverSpec` to `_MERGE_DRIVERS` (lanes/consolidation.py ≈L60) with:
     - name `spec-kitty-decision-index`;
     - attributes line `kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index`;
     - the command string shaped exactly like the siblings (`spec-kitty merge-driver-decision-index %O %A %B`).

     The missing-attributes check (≈L488) then covers it automatically.
  3. Add a `merge_driver_decision_index` command in `cli/commands/merge_driver.py` mirroring `merge_driver_review_cycle` (≈L130), dispatching through `_run(body, …)` (≈L59).
  4. Confirm the CLI is reachable: `spec-kitty merge-driver-decision-index --help`.
- **Files**: `src/specify_cli/consolidation/drivers.py`, `src/specify_cli/lanes/consolidation.py`, `src/specify_cli/cli/commands/merge_driver.py`.
- **Validation**:
  - the R21 integration test is now green;
  - the existing driver-registry tests are green (find them with `grep -rl "_MERGE_DRIVERS\|MERGE_DRIVER_BODIES" tests/`);
  - CLI help lists the command.
- **Edge cases**:
  - **Stale install** (CLAUDE.md baseline-red category 3): the driver shells out to `spec-kitty`. Run `uv sync --frozen --all-extras` or `pip install -e .` before trusting a red merge test.
  - Command help text must use canonical terms (Mission).

### Subtask T062 – init seed and repository `.gitattributes`

- **Purpose**: New projects get the driver at `spec-kitty init`, and this repository dogfoods it.
- **Steps**:
  1. In `src/specify_cli/cli/commands/init.py`, add `_DECISION_INDEX_GITATTRIBUTES_ENTRY = "kitty-specs/**/decisions/index.json merge=spec-kitty-decision-index"` beside the sibling constants (≈L67-80), with a short comment citing FR-009b / D13.
  2. Include the new constant in `_ensure_event_log_merge_attributes` (≈L455) and in any list of entries it writes. If git config is seeded at init, mirror the sibling drivers.
  3. Add the same line to this repository's `.gitattributes`, next to the other `merge=` lines (after the `review-cycle` line).
  4. `DM-*.md` gets nothing. Say so in the comment.
- **Files**: `src/specify_cli/cli/commands/init.py`, `.gitattributes`.
- **Validation**: run the init tests that assert `.gitattributes` content (`grep -rl "_ensure_event_log_merge_attributes\|merge=spec-kitty" tests/init tests/specify_cli tests/cli`). Update count-based expectations only where they enumerate drivers, and record each such re-pin in the activity log.
- **Edge cases**: the writer must be idempotent: running init twice writes the line once.

### Subtask T063 – Upgrade migration for already-initialized clones

- **Purpose**: Existing consumer projects get the driver on `spec-kitty upgrade`.
- **Steps**:
  1. Create `src/specify_cli/upgrade/migrations/m_4_0_0rc5_decision_index_merge_driver.py`, modelled on `m_3_2_7_review_cycle_merge_driver.py`.
     - Use its own migration id.
     - `target_version` must not exceed the installed package version (`4.0.0rc5`, from `pyproject.toml`). Read the m_3_2_7 docstring and `test_discovered_migration_targets_do_not_exceed_package_version`.
     - Use the `_merge_driver_seeding.py` helpers for both the `.gitattributes` entry and the local git config.
  2. The migration must be idempotent: detect presence, write only what is missing, and report.
  3. Respect agent-config rules: this migration touches no agent directories. If a helper needs a project path, use the config-aware helpers.
  4. Tests in `tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py`, mirroring `tests/upgrade/migrations/test_m_3_2_6_decisions_event_log_merge_driver.py`:
     - fresh repository → line plus config added;
     - already present → no-op;
     - detect/apply contract.
  5. Run the migration-registry tests that discover migrations (`grep -rl "discover\|registry" tests/upgrade/*.py | head`) and `tests/architectural/test_no_dead_modules.py`, which references migration modules.
- **Files**: the new migration and its test.
- **Validation**: migration tests are green and the registry discovers the new id. The `target_version` guard test is green.
- **Edge cases**:
  - Never assume `.gitattributes` exists: create it when absent, as the sibling does.
  - Never reorder existing lines.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Owned files added (operator decision)**:
  - `src/specify_cli/cli/commands/__init__.py`: L362 hidden `app.command(name="merge-driver-decision-index", hidden=True)` and L656 `_COMMAND_REGISTRARS`;
  - `src/specify_cli/_completion_manifest.json` (`test_completion_manifest_freshness.py`);
  - golden case `tests/consolidation/merge_driver_goldens/merge-driver-decision-index/union-two-lanes/{case.json,O,A,B,expected_A}`, mirroring the sibling dirs; add more cases (collision terminal-beats-open, malformed) under the same dir if needed;
  - the count pins 6 → 7: `tests/consolidation/test_merge_drivers.py::test_merge_driver_bodies_matches_the_two_other_driver_name_authorities`, `tests/consolidation/test_merge_driver_goldens.py::test_golden_cases_are_discovered_and_cover_all_six_commands` and `::test_distinct_config_key_count_matches_six_registered_commands`.
- **`_MergeDriverSpec` fields** are `config_key`, `name`, `command` and `pattern` (`attributes_line` is derived). Use `config_key="spec-kitty-decision-index"`, `pattern="kitty-specs/**/decisions/index.json"`.
- **Terminal-beats-open must be written**: `index_fold.apply_terminal` (L144) and `_select_terminal_event` (L215) never compare two `IndexEntry` versions. `is_allowed_terminal_reopen` (L90) helps.
- **Byte-stability**: the serializer is inline in `decisions/store.py:124-145` (`json.dumps(DecisionIndex(...).model_dump(mode="json"), sort_keys=True, indent=2) + "\n"`, sorted by `(created_at.isoformat(), decision_id)`). Round-trip through the `DecisionIndex` model, never raw JSON sorting.
- **Migration**:
  - it must **subclass `MergeDriverSeedingMigration`** (like `m_3_2_7`);
  - `target_version="4.0.0rc5"` equals the package version, so already-rc5 projects get it only through `detect()`; `detect()` must return true when the line or config is missing (`upgrade/registry.py:94-100`).
- **Dead symbols**: keep `union_decision_index` public but **out of `__all__`** until WP17 imports it (intra-module use rescues non-`__all__` names).
- **Wider reach**: `_MERGE_DRIVERS` also feeds `_ensure_info_attributes` (`consolidation.py:488`) and `git_probes._resolve_registered_driver_callable` (#5038 squash replay). The new driver becomes authoritative in reconciliation blob attribution immediately. Run by name: `tests/consolidation/test_reconciliation.py`, `test_reconciliation_divergent.py`, `test_squash_reconcilers_2709.py`, `test_issue_2709_projection_union.py`.
- **Stale install**: the real `git merge` test shells out. Use the sibling pattern (absolute interpreter, `python -m specify_cli`).
- **Valid guards**: in `test_merge_reconciliation_class_guard.py`, `test_declared_merge_drivers_are_registered_in_gitattributes`, `test_init_seed_is_superset_of_registry_merge_drivers` and `test_migration_seed_is_superset_of_registry_merge_drivers`; also `tests/agent/test_init_command.py` L290-345.
- **C3**: the merge-driver command is hidden; state the migration's operator-visible effect in its description. The CHANGELOG entry is a closeout item.

## Targeted test surface

```bash
uv run --frozen pytest tests/consolidation/test_decision_index_merge_driver.py -q
uv run --frozen pytest tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py -q
uv run --frozen pytest tests/upgrade/migrations/ -q            # owning migration directory
uv run --frozen pytest tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py -q   # sibling regression
uv run --frozen pytest $(grep -rl "_MERGE_DRIVERS\|MERGE_DRIVER_BODIES\|_ensure_event_log_merge_attributes" tests --include="test_*.py" | grep -v architectural) -q
uv run --frozen pytest tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py -q
make test-fast
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record every command with its pass/fail counts in the activity log, for the PR's *Tests run* section.
- **Baseline-red gotcha**: classify any red you did not cause into one of these before chasing it:
  - a known P0;
  - CI-environment configuration;
  - a stale install (a `spec-kitty` shell-out; reinstall);
  - a stale venv (`uv sync --frozen --all-extras`).

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). Keep the driver as parse, union and serialize helpers.
- `ruff check` and `ruff format --check` on the changed files; `mypy --strict` on the changed files. No new suppressions (NFR-005).
- ≥ 90% new-line coverage, and every new branch (conflict, malformed input, terminal precedence) has a focused test (NFR-003).
- New public symbols: `tests/architectural/test_no_dead_symbols.py` must stay green. Every new symbol needs a caller in `src/`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5023

## Definition of Done

- R21 was red on the WP base and is green on the final commit. The red-first test commit precedes the driver commits.
- The driver is registered in `MERGE_DRIVER_BODIES`, `_MERGE_DRIVERS`, the CLI, the init seed, this repository's `.gitattributes`, and the new migration.
- Collision semantics are documented in the driver docstring: terminal beats open, two conflicting terminals produce a conflict, and malformed input produces a conflict.
- Migration tests are green and the migration is idempotent.
- ruff, format and mypy are clean; coverage is at least 90%.
- The activity log lists the commands and counts, plus any init or registry test re-pins with a one-line rationale each.

## Risks & Mitigations

- **Silent wrong merge** of two conflicting terminal states. Mitigation: return a conflict outcome and never pick one; test it.
- **Stale-install false reds** (the driver shells out). Mitigation: reinstall before diagnosing.
- **The class guard reacts** to a driver registered for `decisions/` while it is still ruled single-writer. Mitigation: WP12 owns that amendment. Report it here; do not edit the guard.
- **Migration version gate**: a `target_version` above the installed version silently never runs. Mitigation: pin it to `4.0.0rc5` and run the discovery guard test.

## Review Guidance

- The reviewer (opus, a different agent from the implementer) verifies red→green:
  - R21 was RED on the WP base, before the driver commits (check out the red-first commit and run it);
  - R21 is GREEN on the final commit.
- Confirm there is a single registration path, mirroring the siblings, and no ad-hoc git config writer.
- Confirm the collision rule reuses `index_fold` precedence rather than re-deriving it.
- Confirm a no-op merge produces byte-stable output, and that `DM-*.md` received no driver.
- Confirm the migration `target_version` does not exceed the installed package version.

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
