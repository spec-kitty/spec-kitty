---
work_package_id: WP03
title: Quarantine removal and lane relocation
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-011
- NFR-001
- NFR-004
- NFR-005
- C-001
- C-007
- SC-002
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 3ae6575b5b81e92ccad77cc6d7d1e847b2ae577f
created_at: '2026-09-30T20:54:10.086511+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 1 - Masked greens
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/acceptance/
create_intent:
- tests/specify_cli/acceptance/test_acceptance_support.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/cross_cutting/misc/test_acceptance_support.py
- tests/specify_cli/acceptance/test_acceptance_support.py
- ruff.toml
- tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Quarantine removal and lane relocation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission test-suite-remediation-01M3SSDW` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

- **FR-003**: At least one CI lane executes the five quarantined accept-diagnose tests. The same goes for the 18 unquarantined tests in their file, which today run in **no lane at all**.
- **FR-002**: The quarantine reason cites EXPERIMENTAL#171, which closed on 2026-08-26 (its visibility job was deleted the next day by `e8cc2f444f`). After this WP no marker rests on it.
- **Relocation (R5)**: Move the file with `git mv` to `tests/specify_cli/acceptance/test_acceptance_support.py`.
  - That directory is listed under `out_of_matrix_test_dirs` (`.github/ci-module-registry.yml:640`) and is claimed by no `modules[]` row.
  - So the nightly `specify-cli-out-of-matrix` job (`ci-nightly.yml:1015-1056`) collects it with `-m "not stress and not timing" -n auto --dist loadfile`, the exact condition under which the tests originally failed.
- **Residual-fragility fix**: every accept-CLI JSON parse uses `json.loads(result.stdout)`, not `result.output`. Under Click 8.3, `.output` interleaves stderr.
- **NFR-001**: 23 executed tests after the change (was 18 executed plus 5 skipped).

## Context & Constraints

- Read first: `spec.md` FR-003 and its Assumptions; `plan.md` IC-03 and the RK-2 ruling; `research.md` D-7; `research/masked-greens.md` row 5 and the "Quarantine root cause" section; `quickstart.md` §FR-003.
- **Measured on this base**: 23/23 pass serially, 3× under `-n 2 --dist loadfile` and 2× under `-n 4 --dist load`. No serial lane is needed.
- The quarantine chokepoint in `tests/conftest.py:320-338` belongs to WP04's file. **Do not edit `tests/conftest.py`.** Removing the marker from this file is enough.
- `tests/cross_cutting/misc/test_acceptance_support.py` is **not** format-excluded, so `ruff format --check` applies at its new path. It is in `ruff.toml` per-file-ignores at `:166` (`["F401"]`).
- **No fixture shadowing at the destination**: `feature_repo` is defined only in `tests/conftest.py`, and there is no `tests/specify_cli/acceptance/conftest.py`. Verify both before moving. The basename is unique.
- **Out of scope (RK-5), do not touch**:
  - the `quarantine-visibility` lane residue (`scripts/ci/quality_gate_decision.py`, arch-test docstrings, `pytest.ini` marker text);
  - the three open-issue quarantines (EXP#1021 ×2, EXP#901).

  Each gets a follow-up issue at closeout, filed by the orchestrator.
- `docs/adr/3.x/2026-08-28-1-…md:177` names the old path. ADRs are immutable (C-006), so leave it.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP03 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** A single named file under `-n 2 --dist loadfile` is allowed; it is not a directory sweep. Never run a test directory as a whole, never `make test-full`, and no stress, timing, e2e or performance suite. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** Scratch edits only; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty** for this WP) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011)**: a FIX goes red under its plant.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP03 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** Run `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" tests/specify_cli/acceptance/test_acceptance_support.py`. Expect no quarantine marker; any other hit carries a reason.
6. **Quality (NFR-005).** `uv run --frozen ruff check` and `uv run --frozen ruff format --check` on the moved file. Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions|tooling-friction --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md); never green-wash it.
9. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits.

### Additional mission-wide rules (analysis folds)

- **A. New product defect (FR-005, DM-01M3SSV4; analysis C1).** If an unmasked or converted test exposes a **new** product defect, never re-mask it.
  - If the fix fits this WP: make it red-first, as a failing test commit followed by a **separate** `fix(...)` commit touching only the product file(s). It is a sanctioned out-of-map `src/` edit: record a one-line rationale in your WP notes, file an issue (`gh issue create`) and add its issue-matrix row (`spec-kitty agent issue-verdict ... --verdict fixed`). The "`git diff --stat src/` must be empty" rule is lifted for exactly that commit.
  - Otherwise: mark the test `xfail(strict=True, reason="<newly filed open issue>")` and tell the orchestrator.
- **B. Evidence completeness (FR-011; analysis C2).** The evidence in your review note and final report is the **full** per-item record, never a summary. For each item give:
  - `path::function::mutation` (the planted break);
  - the old form's result under the break;
  - the new form's (or covering guard's) result under the break;
  - the result after the revert;
  - the exact command.

  If `move-task --note` rejects the length, put the full records in the WP's review-ref artifact or the lane commit message body, and tell the orchestrator where they are. The per-WP reviewer must be able to check each item before approval.
- **C. Lint and type gates on every touched `.py` file (NFR-005; analysis C3).** Run `uv run --frozen ruff check <touched .py files>` and `uv run --frozen ruff format --check <touched files not in the format-exclude list>`. If you touch `src/` (including a sanctioned FR-005 fix), also run `uv run --frozen mypy <touched src files>`. Where findings pre-exist, compare against the base (`git stash`, or a scratch worktree of the planning base) and add **0 new** findings.

## Subtasks & Detailed Guidance

### Subtask T011 – Relocate the file with `git mv`, and rename its references

- **Purpose**: Give the file a lane. `tests/cross_cutting/misc` is out-of-matrix (`.github/ci-module-registry.yml:732`, "performance marker home…"), and the nightly interpreter shard's `-m "fast or unit"` deselects this `integration`-marked file. The destination is collected nightly.
- **Files**:
  - `tests/cross_cutting/misc/test_acceptance_support.py` → `tests/specify_cli/acceptance/test_acceptance_support.py`;
  - `ruff.toml` (the key at `:166`);
  - `tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py` (the docstring path at `:9`).
- **Steps**:
  1. Record the baseline at the old path: `SPEC_KITTY_RUN_QUARANTINE=1 uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -n0 -q -rs` should show 23 passed. Also run it without the env var, which should show 18 passed and 5 skipped.
  2. `git mv tests/cross_cutting/misc/test_acceptance_support.py tests/specify_cli/acceptance/test_acceptance_support.py`. Commit the move in a commit of its own (a pure rename) so history follows it.
  3. In `ruff.toml:166`, rename the key to `"tests/specify_cli/acceptance/test_acceptance_support.py" = ["F401"]`. Keep the sort order if the table is sorted. Then check whether `F401` is still needed after T012; if not, delete the entry (a shrink).
  4. Update the docstring reference in `test_issue_4891_accept_missing_lanes.py:9` to the new path.
  5. Confirm the imports still resolve: `from tests.lane_test_utils import write_single_lane_manifest` is absolute.
  6. Run `git grep -n "cross_cutting/misc/test_acceptance_support" -- ':!kitty-specs' ':!docs/adr' ':!docs/reports' ':!.kittify/evidence'`. It must return nothing.
- **Edge cases**:
  - If `pytest --collect-only` shows a conftest at the destination that changes fixtures, stop and report.
  - Keep `pytestmark = [pytest.mark.integration]` unchanged.

### Subtask T012 – Remove the quarantine; parse `result.stdout`

- **Purpose**: Remove the marker that makes 5 tests run only when `SPEC_KITTY_RUN_QUARANTINE=1`, which no workflow sets. Fix the residual fragility: a stray stderr line from leaked logging or warning state breaks `json.loads(result.output)`, which is exactly the "fails under -n auto, passes alone" signature.
- **Files**: `tests/specify_cli/acceptance/test_acceptance_support.py`.
- **Anchors (pre-move line numbers)**:
  - `_ACCEPT_COMMAND_XDIST_QUARANTINE` at `:22`;
  - its uses at `:284`, `:360`, `:398`, `:436` and `:498`;
  - `json.loads(result.output)` at `:271`, `:307`, `:350`, `:387`, `:426`, `:486`, `:545` and `:605`.
- **Steps**:
  1. Delete the constant and its 5 decorator uses.
  2. Replace **every** `json.loads(result.output)` with `json.loads(result.stdout)`, including the 3 de-quarantined siblings that share the pattern.
     - Keep the `assert result.exit_code == 0, result.output` diagnostics as they are (`.output` is the right diagnostic).
     - For `"Traceback" not in result.output` checks, keep `.output`: stderr is exactly where a traceback would show.
  3. Confirm the runner separates the streams. Check how `CliRunner` is constructed in this file: Click 8.3 always separates `stdout` and `stderr`, and `mix_stderr` was removed. If `result.stdout` misbehaves, report it rather than improvising.
  4. Run `uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n0 -q -rs`. Expect 23 passed, 0 skipped.
- **Edge cases**: If any payload goes to stderr by design (e.g. a `--json` error path that prints to stderr), that test must parse `result.stderr` explicitly. Note which, with the reason.

### Subtask T013 – Lane proof: collection under the nightly selection, and the registry check (RK-2)

- **Purpose**: Show that the destination is collected by a real lane and stays collected (RK-2). This is the FR-003 acceptance evidence.
- **Steps**:
  1. **Collection under the lane's markers**:
     ```bash
     uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -m "not stress and not timing" --collect-only -q | grep -c accept_diagnose
     ```
     Expect ≥ 5. Also list the 5 former-quarantine node ids by name in the evidence.
  2. **Registry check** (the same logic as the nightly job's `--ignore` builder at `ci-nightly.yml:1040-1049`):
     ```bash
     uv run --frozen python -c "import yaml;r=yaml.safe_load(open('.github/ci-module-registry.yml'));claimed={d for m in r['modules'] for d in m.get('test_dirs',[]) if d.startswith('tests/specify_cli/')};print('claimed:', 'tests/specify_cli/acceptance' in claimed);print('out_of_matrix:', any('tests/specify_cli/acceptance' in (g.get('dirs') or []) for g in (r.get('out_of_matrix_test_dirs') or []) if isinstance(g, dict)))"
     ```
     Expect `claimed: False`. Also confirm the `out_of_matrix` listing; adapt the snippet to the registry's real shape and record the exact command you ran.
  3. **The named architectural gates** (by file, never the directory):
     ```bash
     uv run --frozen pytest tests/architectural/test_quarantine_marker.py tests/architectural/test_out_of_matrix_evidence.py tests/architectural/test_module_shard_registry.py tests/architectural/test_ruff_pytest_style_baseline.py -n0 -q
     ```
     If one reds because it pins the old path, the file belongs to another surface. Stop and report to the orchestrator; do not edit it.
- **Edge cases**: A future registry row claiming `tests/specify_cli/acceptance` would move the file into the per-PR matrix, which is still a lane (RK-2, accepted). Only a demotion to `--ignore` without a row would orphan it; record that in the evidence.

### Subtask T014 – Per-test planted break, single-file xdist run, evidence

- **Purpose**: FR-011 per-test proof that the de-quarantined tests guard a real contract, and a parallel-safety check on this one file.
- **Steps**:
  1. **Parallel run** (a single named file, allowed):
     ```bash
     uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n 2 --dist loadfile -q
     ```
     Expect 23 passed, 0 skipped. Run it twice and record both.
  2. **Planted break (FIX proof)**: make `accept --diagnose` mutate state. In `src/specify_cli/cli/commands/accept.py`, drop the `not diagnose` guard on the commit or stamp path, e.g. the `commit_required = ... and not diagnose` at `:874`, or the diagnose short-circuit before the matrix or `meta.json` stamp. Find the exact line that keeps `--diagnose` read-only. This is a scratch edit; revert with `git checkout -- src/specify_cli/cli/commands/accept.py`.
     - `test_accept_diagnose_json_reports_skipped_checks_without_mutation` and `test_accept_diagnose_does_not_mutate_matrix_metadata_or_events` must go RED.
     - Before this WP, the old form SKIPPED under the same plant, because the quarantine opt-in was unset.
  3. **NFR-001 counts**: before, 18 executed and 5 skipped. After, 23 executed and 0 skipped.
  4. **Skip hygiene** and `ruff` on the moved file.
  5. `make test-fast` once.
- **Evidence records**:
  - MG-05 (DE-QUARANTINE + RELOCATE): the collect-only output, the registry-check output, the xdist runs and the planted break.
  - A FR-002 note: the EXPERIMENTAL#171 citation is removed, and #171 was closed.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n0 -q -rs
uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -m "not stress and not timing" --collect-only -q
uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n 2 --dist loadfile -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -n0 -q
uv run --frozen pytest tests/architectural/test_quarantine_marker.py tests/architectural/test_out_of_matrix_evidence.py tests/architectural/test_module_shard_registry.py tests/architectural/test_ruff_pytest_style_baseline.py -n0 -q
uv run --frozen ruff check tests/specify_cli/acceptance/test_acceptance_support.py tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py
uv run --frozen ruff format --check tests/specify_cli/acceptance/test_acceptance_support.py
make test-fast
```

## Risks & Mitigations

- **A hidden cross-file leak under the nightly `-n auto`.** The residual stderr fragility is fixed by `result.stdout`. The nightly job is the regression surface for anything else; note that in the evidence.
- **Registry drift** (RK-2). The registry check is recorded. The orchestrator files the "collected by some lane" follow-up at closeout.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- The history follows the file (`git log --follow tests/specify_cli/acceptance/test_acceptance_support.py`).
- No `quarantine` marker remains, and no `json.loads(result.output)` remains.
- Re-run the collect-only and registry snippets yourself.
- Re-run planted break #7 (quickstart) yourself.
- `ruff.toml` changed only by the key rename (or the entry's deletion, if `F401` became unnecessary).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-5, etc.)

**Initial entry**:

- 2026-09-30T19:32:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

Hand-off:

```bash
spec-kitty agent tasks mark-status T011 T012 T013 T014 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP03 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
