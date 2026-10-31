---
work_package_id: WP01
title: The one sequencing decision
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-6552-upgrade-dry-run-sequenced-verdict
merge_target_branch: issue-6552-upgrade-dry-run-sequenced-verdict
branch_strategy: Planning artifacts for this mission were generated on issue-6552-upgrade-dry-run-sequenced-verdict. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6552-upgrade-dry-run-sequenced-verdict unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core change
history:
- at: '2026-10-31T08:50:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_dry_run_sequenced_verdict.py
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/runner.py
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py
- tests/upgrade/test_dry_run_sequenced_verdict.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – The one sequencing decision

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

`spec-kitty upgrade --dry-run` runs the same ordered migration loop as a real run but writes
nothing, so a migration whose `detect()` reads state an earlier migration in the same run
writes is judged against the pre-run tree and reported
`not needed (project already in target state)` while the real run applies it (#6552).

Deliver **one sequencing decision** in the runner: the run remembers which migrations it has
reported applied, and a migration that *declares* the predecessors whose writes its
`detect()` reads is reported as applied when one of them is in that set. The reported
`3.2.6_issue_matrix_driver_repoint` → `3.2.6_gate_artifact_merge_drivers` pair declares the
relationship. An *undeclared* dry-run skip stops claiming target state.

Done when:

- A dry run of the reported pair reports the same `migrations_applied` as a real run of the
  same project.
- An undeclared ordering pair is reported `not needed on the current tree` in a dry run,
  never `project already in target state`.
- A dry run still writes nothing (project tree, `.git/config`, tracked ledger, clone-local
  ledger).
- A real run's verdicts, warnings and ledger records are unchanged.

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/6552>
- Spec: `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/spec.md`
- Plan: `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/plan.md` (decisions D-001..D-004
  in `research.md`)
- Data model: `kitty-specs/upgrade-dry-run-sequenced-verdict-01M68J9V/data-model.md`

Read before editing:

- `src/specify_cli/upgrade/runner.py` — `upgrade()` (per-run state reset),
  `_upgrade()` (the ordered loop, `migrations_applied`), `_apply_migration()` (the verdict).
- `src/specify_cli/upgrade/migrations/base.py` — `BaseMigration` class attributes and their
  docstrings (match that style; the module also explains that `order_manifest.txt` owns
  execution order).
- `src/specify_cli/upgrade/migrations/order_manifest.txt` lines 120–121 — the pair's order.
- `src/specify_cli/upgrade/migrations/_merge_driver_seeding.py` — `detect()`/`apply()` of the
  reported pair, including the `dry_run` early return that causes the divergence.
- `src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py` — its docstring
  already records the ordering dependency in prose.
- `tests/upgrade/test_runner_status_classification.py` and
  `tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py` — both assert the
  substring `not needed` on a skip warning; keep that substring true.

Constraints:

- **C-001**: `order_manifest.txt` stays the single execution-order authority. The new
  declaration is detect-input metadata; it never reorders and no code reads it for ordering.
- **C-002**: real-run behaviour is unchanged — the prediction branch must be unreachable
  when `dry_run=False`.
- **C-003**: `MigrationRegistry.get_applicable` / `migration_settled` remain the only applied
  authority. The prediction never adds a migration the ledger did not select.
- **C-004**: out of scope — the worktree pass (`_upgrade_worktrees`), `--plan-json`, and the
  frozen `compat-planner.json` contract.
- Complexity ceiling 15 (`ruff` `C901`). `_apply_migration` is long; if a branch pushes it
  over, extract small helpers (for example the prediction and the skip warning).

## Branch Strategy

- **Strategy**: single checkout; planning artifacts were generated on
  `issue-6552-upgrade-dry-run-sequenced-verdict`, and completed changes merge into the same
  branch, which is the PR head.
- **Planning base branch**: `issue-6552-upgrade-dry-run-sequenced-verdict`
- **Merge target branch**: `issue-6552-upgrade-dry-run-sequenced-verdict`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first test module

- **Purpose**: Pin the reported divergence and the invariants before the fix, so the fix is
  proven by a test that fails on the pre-fix tree.
- **Steps**: Create `tests/upgrade/test_dry_run_sequenced_verdict.py` with a git-repo fixture
  builder (`.kittify/metadata.yaml`, `.gitattributes`, `git init`, and the local git config
  the merge-driver migrations read) and these cases:
  1. **Parity on the reported pair** (fails today; the red-first proof). Clear the registry,
     register only `GateArtifactMergeDriverMigration` and
     `IssueMatrixDriverRepointMigration` (or drive the real discovered set if it stays fast
     and deterministic), run `MigrationRunner(project).upgrade(target, dry_run=True)` on one
     copy and `dry_run=False` on an identical copy, and assert
     `dry.migrations_applied == real.migrations_applied` and that the repoint id is in both.
     The state must be one where the gate migration is pending and the repoint is
     pending-but-not-yet-detected (see the quickstart's fixture recipe: the repoint's
     clone-local ledger record removed).
  2. **Prediction is named**: the dry-run `migration_results[repoint].changes_made` mentions
     `dry-run: would apply after 3.2.6_gate_artifact_merge_drivers`.
  3. **Undeclared pair, honest wording** (second half of the fix): a synthetic pair `A`
     (applies by writing a marker file) and `B` (`detect()` reads the marker) with **no**
     declaration. Dry run: `B` is skipped and its warning says `not needed on the current
     tree` and never `project already in target state`. Real run on a copy: `B` is applied.
     This is the same-fixture positive control for the wording assertion.
  4. **Prediction honours `can_apply`**: a declared dependent whose `can_apply` refuses is
     skipped with its reason, not reported applied.
  5. **Settled predecessor predicts nothing**: with the predecessor already recorded in the
     ledger (so it is not selected), a `detect()`-False dependent is skipped with the
     current-tree wording.
  6. **No writes** (NFR-001): snapshot the project tree (including `.git/config`), both
     ledger partitions' bytes, and `metadata.yaml`; run the dry run; assert byte-identical.
     Positive control on the same fixture: the real run **does** change them.
- **Files**: `tests/upgrade/test_dry_run_sequenced_verdict.py` (new)
- **Parallel?**: no — it defines the contract the rest of the WP satisfies.
- **Notes**: use `MigrationRegistry.clear()` carefully and restore state (`try/finally`) so
  other tests in the same session are unaffected; prefer registering the real migration
  classes. Run it once against the pre-fix tree and record the failure output (the red-first
  proof goes in the PR body).

### Subtask T002 – `BaseMigration.sequenced_after`

- **Purpose**: One declarative place for "the migrations whose writes my `detect()` reads".
- **Steps**: Add to `BaseMigration` in `src/specify_cli/upgrade/migrations/base.py`:

  ```python
  sequenced_after: ClassVar[tuple[str, ...]] = ()
  ```

  with a docstring/comment in the surrounding house style that says: it is **detect-input
  metadata for the dry run only**; `order_manifest.txt` remains the single execution-order
  authority (ADR 2026-10-17-1 §2); a real run never consults it because the predecessor has
  already written; an unknown or unselected id changes nothing.
- **Files**: `src/specify_cli/upgrade/migrations/base.py`
- **Parallel?**: yes (small, but T003 consumes it).
- **Notes**: do not add it to `SupersededMigration` or any subclass except the one in T004.

### Subtask T003 – The runner's sequencing decision

- **Purpose**: Replace the pre-run-tree verdict with the sequenced verdict, in one place.
- **Steps**:
  1. In `MigrationRunner.__init__`, add per-run state (e.g. `self._sequenced_applied: set[str] = set()`);
     reset it in `upgrade()` next to the existing `self._seen_residue = set()`.
  2. In `_apply_migration`, after `migration_needed = migration.detect(...)` succeeds:
     - when `migration_needed` is True and the apply succeeds, the id joins the set (the
       caller already appends to `migrations_applied`; add the set there or inside
       `_apply_migration` — pick one place and keep it single);
     - when `migration_needed` is False, `dry_run` is True, and one of
       `migration.sequenced_after` is in the set: take the prediction path.
  3. The prediction path must run the **existing** `can_apply` block (do not duplicate its
     exception handling) and then, instead of `migration.apply(...)`, return
     `MigrationResult(success=True, changes_made=[f"dry-run: would apply after {', '.join(preds)}"])`
     with status `applied`. A `can_apply` refusal keeps today's skip and reason.
  4. The `not migration_needed` skip keeps its status and record behaviour; under `dry_run`
     its warning becomes `Migration <id> not needed on the current tree` (the real-run
     warning stays `Migration <id> not needed (project already in target state)`).
  5. Update the `_apply_migration` docstring to state the two-authority boundary: the ledger
     decides selection, the run's applied set decides the dry-run sequenced verdict.
- **Files**: `src/specify_cli/upgrade/runner.py`
- **Parallel?**: no.
- **Notes**: nothing may be recorded or stamped on the prediction path (`dry_run` already
  guards the record calls — verify). Keep `_apply_migration` at complexity ≤15.

### Subtask T004 – Declare the measured pair

- **Purpose**: Make the reported case predictable instead of merely honestly worded.
- **Steps**: In `m_3_2_6_issue_matrix_driver_repoint.py`, set
  `sequenced_after = ("3.2.6_gate_artifact_merge_drivers",)` on
  `IssueMatrixDriverRepointMigration`, with a comment naming the write that makes this
  migration needed (`merge.spec-kitty-issue-matrix.name` overwritten by the gate migration)
  and referencing #6552 + the docstring's existing ordering note.
- **Files**: `src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py`
- **Parallel?**: yes.
- **Notes**: the sibling merge-driver migrations (meta traces, decisions event log, review
  cycle) seed their own keys with no cross-dependency — leave them alone. Do **not** touch
  `order_manifest.txt`.

### Subtask T005 – Verification

- **Steps**:
  - `uv run pytest tests/upgrade/test_dry_run_sequenced_verdict.py -q`
  - `uv run pytest tests/upgrade/test_runner_status_classification.py tests/specify_cli/upgrade/test_migrate_activation_ledger_cmd.py tests/upgrade/test_ledger.py tests/upgrade/test_clone_local_migration_reselect.py -q`
  - `uv run pytest tests/compat/test_dry_run_parity.py -q`
  - `uv run ruff check src/specify_cli/upgrade tests/upgrade/test_dry_run_sequenced_verdict.py`
  - `uv run ruff format --check --force-exclude src/specify_cli/upgrade/runner.py src/specify_cli/upgrade/migrations/base.py src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py tests/upgrade/test_dry_run_sequenced_verdict.py`
  - `uv run mypy src/specify_cli/upgrade/runner.py src/specify_cli/upgrade/migrations/base.py` (or the project's configured invocation)
- **Notes**: do not run `make test-full`. Record command + pass/fail counts for the PR body.

## Test Strategy

Red-first (DIRECTIVE_034): T001's parity test must fail on the pre-fix tree — capture the
failure before changing `src/`. The no-writes case is a ratchet (it already passes; keep it
that way). The wording case is the second half of the fix, and it must go red if only the
prediction is reverted; the parity case must go red if only the declaration/prediction is
reverted (`acceptance-criteria-non-vacuity`, "prove compound fixes half by half").

## Risks & Mitigations

- **A second authority sneaks in** (a new status, a new list): rejected in design — the
  prediction reports `applied` through the existing channel.
- **Existing tests pin the old dry-run wording**: they assert the substring `not needed`,
  which stays; re-run them in T005.
- **The prediction overclaims** when a predecessor's real apply would not re-select the
  dependent: only a declared pair can predict, and the declaration is an author's assertion;
  the honest-wording path covers everything else.
- **Fixture fragility** (git config in a temp repo): build the repo with `git init` +
  `git config --local`, and assert the fixture's preconditions (`gate.detect()` True,
  `repoint.detect()` False) so a fixture drift fails loudly instead of passing vacuously.

## Review Guidance

- Does the prediction branch have any reachable path when `dry_run=False`? It must not.
- Does the dry run still write nothing, including `metadata.yaml` and both ledger partitions?
- Is there exactly one place that decides the sequenced verdict, and does it read only the
  run's own applied set?
- Is the declaration clearly detect-input metadata (not ordering), and is the manifest
  untouched?
- Are the real-run warnings and records byte-identical?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done` and add
history notes as you go (`spec-kitty agent tasks add-history WP01 --note "..."`).
