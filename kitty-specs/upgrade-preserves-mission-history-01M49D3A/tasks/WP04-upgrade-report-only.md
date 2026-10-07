---
work_package_id: WP04
title: Upgrade becomes report-only under drain
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-007
- FR-010
- FR-011
- NFR-002
- C-001
- C-003
- C-004
- SC-004
planning_base_branch: issue-5811-upgrade-preserves-mission-history
merge_target_branch: issue-5811-upgrade-preserves-mission-history
branch_strategy: Planning artifacts for this mission were generated on issue-5811-upgrade-preserves-mission-history. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5811-upgrade-preserves-mission-history unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-preserves-mission-history-01M49D3A
base_commit: 2676d22e844261054705eb001257eac9054a7014
created_at: '2026-10-07T04:57:22.400445+00:00'
subtasks:
- T017
- T018
- T019
- T020
- T021
phase: Phase 2 - Fixes
history:
- at: '2026-10-07T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/architectural/test_mission_state_repair_sole_caller.py
- docs/adr/4.x/2026-10-07-1-upgrade-never-runs-mission-state-repair.md
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/upgrade.py
- src/specify_cli/cli/commands/_teamspace_mission_state_gate.py
- src/specify_cli/cli/commands/_mission_state_doctor.py
- tests/upgrade/test_teamspace_consent_scope.py
- tests/upgrade/test_yes_consent_exit_honesty.py
- tests/upgrade/test_upgrade_outcome_rendering.py
- tests/upgrade/test_upgrade_auto_commit_unit.py
- tests/upgrade/test_recovery_composition.py
- tests/upgrade/test_mission_corpus_recovery.py
- tests/architectural/test_mission_state_repair_sole_caller.py
- docs/adr/4.x/2026-10-07-1-upgrade-never-runs-mission-state-repair.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04: Upgrade becomes report-only under drain

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ Review Feedback

If this WP came back from review, read the `review_ref` in the event log first (`.venv/bin/spec-kitty agent tasks status --mission 01M49D3A`). Every feedback item is part of your work.

## Objective

`spec-kitty upgrade`, including `--yes`, never runs the mission-state repair.
- **Drain on:** the TeamSpace mission-state gate reports the blocker count and finding codes, then names `spec-kitty doctor mission-state --fix`.
- **Drain off** (the default; Team Kitty is unsupported, ADR `2026-10-06-1`): readiness is not evaluated at all.
- **Explicit repair:** `doctor mission-state --fix` remains the only consent path. It names errored Missions and exits non-zero when any errored.
- **Records:** an ADR records the reversal of the #4775 decision that `--yes` consents to the repair, and a gate pins doctor as the sole repair caller.

Spec references: FR-001, FR-002, FR-007 (rendering), FR-010, FR-011, C-003, C-004, User Story 1 scenarios 2–5.

## Branch Strategy

- Planning base and final merge target: `issue-5811-upgrade-preserves-mission-history`.
- Own lane, parallel to WP02 and WP03. Prepare with `.venv/bin/spec-kitty agent action implement WP04 --agent claude`.

## Seam Map (brownfield scout; re-check lines)

- `src/specify_cli/cli/commands/upgrade.py:1255–1290`: `_finalizer_step_offer_repair`, registered at :1912. It skips on `json_output`, failed migration, or `commit_recovery_failed`; otherwise it passes `assume_yes=confirm, repair_opt_in=confirm` (comment cites #4775 / FR-017).
- `src/specify_cli/cli/commands/_teamspace_mission_state_gate.py`:
  - `_should_run_repair` :144;
  - `offer_teamspace_mission_state_migration` :170;
  - `repair_repo(project_path)` ~:232;
  - error outcomes ~:235–239;
  - "blockers remain" ~:265;
  - "TeamSpace mission-state blockers cleared." :270–271.

  `--dry-run` already skips the repair (~:221).
- `src/specify_cli/core/hosted_posture.py:307`: `drain_posture(project_root=None) -> DrainPosture`; check `.enabled`. **Call it as `hosted_posture.drain_posture(...)` through the module attribute** (`from specify_cli.core import hosted_posture`). A `from ... import drain_posture` defeats the autouse test patch (module docstring, lines 28–39).
- `_mission_state_doctor.py:275`: the doctor's `repair_repo(...)` call. Keep its signature compatible.
- `enforce_teamspace_mission_state_ready` (`tracker.py:247`) is the **blocking** gate for hosted operations. Do not touch it.
- `tests/architectural/test_upgrade_outcome_single_rendering.py` covers the single rendering path. Run it.

## Subtasks

### T017: The gate evaluates readiness only under drain and only reports

1. In `offer_teamspace_mission_state_migration`, or rename it to something like `report_teamspace_mission_state_blockers` (if you rename it, update every caller and keep the name Mission-canonical):
   - First check `hosted_posture.drain_posture(project_root=project_path).enabled`. If it is False, return an outcome meaning "not evaluated" without calling the readiness check, and print **nothing**.
   - If drain is on, evaluate readiness. If blocked, print the blocker count, the finding codes and the exact remediation command `spec-kitty doctor mission-state --fix`. Never call `repair_repo`. Return a report-only outcome.
2. Delete `_should_run_repair`, the consent prompt and the `repair_opt_in` / `assume_yes` repair parameters if nothing else needs them. Grep before deleting, and leave no dead code.
3. Keep the `RepairOutcome` (or equivalent) consumers in `upgrade.py` compiling and semantically honest: a report-only outcome never claims "cleared".
4. The upgrade's exit code stays 0 when blockers are only reported (spec US1 scenario 4).

### T018: `upgrade.py` stops passing consent; the doctor renders errored Missions

1. In `_finalizer_step_offer_repair`, stop passing `repair_opt_in=confirm` and `assume_yes=confirm` for the repair. Rename the step to reflect report-only if that is clearer, for example `_finalizer_step_report_mission_state`. Update the comment to cite the new ADR instead of #4775 FR-017.
2. `--yes` must stay fully non-interactive (C-003): the step never prompts.
3. `_mission_state_doctor.py:298-307` already prints each errored Mission's `validation_errors`. Keep that rendering and add **no** `getattr` shim and no dependency on a WP02 field. Add only two things:
   - the doctor exits non-zero when any Mission errored;
   - neither the doctor nor the gate ever prints "cleared" when any Mission errored.

   Add one focused test for each.

### T019: Sole-caller pin

**File**: `tests/architectural/test_mission_state_repair_sole_caller.py` (new)
1. AST-scan `src/` for calls to `repair_repo`, both as a name call and as an attribute call `mission_state.repair_repo`. Assert that the set of calling modules is exactly `{"specify_cli/cli/commands/_mission_state_doctor.py"}`; `mission_state.py` itself is excluded.
2. **Non-vacuity**: assert that the scan finds at least one call (the doctor's), and add a self-mutation test that feeds a synthetic source string with an extra `repair_repo(...)` call into the scanner and asserts it is flagged. Follow the pattern of `tests/consolidation/test_single_rollback_authority.py` if it fits.
3. Start with an empty allowlist (charter SO #5).

### T020: Retire or re-pin the consent tests

These tests assert that `--yes` runs the repair or depend on it:
- `tests/upgrade/test_teamspace_consent_scope.py` (e.g. `test_explicit_repair_opt_in_bypasses_the_prompt_and_runs_repair` ~:155)
- `test_yes_consent_exit_honesty.py`
- `test_upgrade_outcome_rendering.py`
- `test_upgrade_auto_commit_unit.py`
- `test_recovery_composition.py`
- `test_mission_corpus_recovery.py`

For **each affected test**, decide:
- **RE-PIN**: the test guards a still-valid behaviour (non-interactive `--yes`, exit honesty, single rendering, auto-commit scope). Rewrite its assertion to the new contract: `repair_repo` is never called, the blockers are reported under drain, nothing is evaluated with drain off.
- **RETIRE**: the test only asserted that the repair runs from upgrade. Delete it and name it in the commit message.
- **KEEP**: unaffected.

Add the drain-off case (`@pytest.mark.real_drain_posture`, or a monkeypatch of `hosted_posture.drain_posture` to disabled) where it best fits in `test_teamspace_consent_scope.py`: readiness is not called (spy) and no mission-state output appears. Record the verdict list in your hand-off note.

### T021: ADR, and turn the #5811 repro into a regular test

1. Write `docs/adr/4.x/2026-10-07-1-upgrade-never-runs-mission-state-repair.md`. Follow the shape of a recent ADR in `docs/adr/4.x/` (read `2026-10-06-1-*.md` and copy its section headings, not its content).
   - **Context**: #5811, #4775, #3653.
   - **Decision**: upgrade is report-only and drain-gated; the only consent path is `doctor mission-state --fix`.
   - **Consequences**: `--yes` is still non-interactive; already-damaged history is not restored (C-002).
   - **Status**: Accepted. Update `docs/adr/4.x/index.md` if it lists ADRs.
2. Remove `@pytest.mark.p0_repro(issue=5811)` and `@pytest.mark.regression` from the WP01 file `tests/integration/migration/test_noop_upgrade_history_untouched_5811.py` (out-of-map, with the reason "the fix WP removes the marker per ADR 2026-07-17-1"). Confirm it is green in a default run.
3. Regenerate the docs index and check freshness:
   ```bash
   .venv/bin/python scripts/docs/docs_index.py --write
   .venv/bin/python scripts/docs/check_docs_freshness.py --ci
   ```
   Errors must be 0. Commit the regenerated index; it is a gate companion.
4. Run `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.

## Constraints

- Complexity at most 15; ruff, `ruff format --force-exclude` and mypy clean.
- Do not edit `mission_state.py` (WP02 and WP03).
- Mission terminology only.
- Test economy: re-pin or retire is preferred over adding tests. The only new test file is the sole-caller gate.

## Tests to Run

```bash
.venv/bin/python -m pytest tests/upgrade/ -q
.venv/bin/python -m pytest tests/integration/migration/test_noop_upgrade_history_untouched_5811.py -q
.venv/bin/python -m pytest tests/architectural/test_mission_state_repair_sole_caller.py tests/architectural/test_upgrade_outcome_single_rendering.py tests/architectural/test_no_legacy_terminology.py -q
.venv/bin/python -m pytest tests/cli/ -q -k "doctor and mission_state"
make test-fast
```

## Definition of Done

- `upgrade --yes` never calls `repair_repo`. It reports under drain, evaluates nothing with drain off, and exits 0.
- The doctor names errored Missions and exits non-zero.
- The sole-caller gate is green and non-vacuous.
- Consent tests are re-pinned or retired, with the list recorded.
- The ADR is written and indexed; docs freshness is at 0 errors.
- The #5811 repro is green as a regular test.

## Reviewer Guidance

- Verify that `drain_posture` is called through the module attribute.
- Verify that no consent prompt or `repair_opt_in` path survives as dead code.
- Verify that the retired tests only asserted the removed behaviour.
