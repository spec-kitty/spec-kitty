---
work_package_id: WP02
title: 'Closed-issue markers: re-point, retire, re-cite'
dependencies: []
requirement_refs:
- FR-002
- FR-005
- FR-011
- NFR-001
- NFR-004
- NFR-005
- C-001
- C-002
- C-007
- SC-002
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 8fd7e374cd5fece981641719f396bb08976c47aa
created_at: '2026-09-30T20:53:39.272943+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Masked greens
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/migration/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_egress_consent_boundary.py
- tests/migration/test_teamspace_migration_rehearsal.py
- tests/migration/test_mission_state_repair.py
- tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
- tests/doctrine/test_packaging_parity.py
- tests/integration/test_clean_install_next.py
- tests/_support/shared_package_deferral.py
- tests/architectural/test_saas_sync_gate_selection_invariance.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Closed-issue markers: re-point, retire, re-cite

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

- **FR-002 / SC-002**: No skip, xfail or guard in this inventory rests on a closed issue.
  - **#3113** (CLOSED, COMPLETED 2026-08-02): the two strict xfails are **re-pointed** to a **newly filed open issue**. They stay `strict=True`, and the landmine guard changes **in the same edit**.
  - **#932** (the `_has_events_5` version guard, unreachable because the floor is `spec-kitty-events>=10.4.0`): **retired**. The unreachable branch is replaced by an explicit version-monkeypatch test of the product refusal.
  - **EXPERIMENTAL#828** (`clean_install_acceptance_deferred`, whose predicate is always `False` because the lock sources both shared packages from PyPI): **retired**, and the helper module is deleted.
  - **The sync gate** (premise #3213, CLOSED): **kept**, with its docstring premise re-cited.
  - **The row-8 false positive** (`test_charter_sole_door_agent_profile_repository.py`, where "828" is a line number): recorded, not edited.
- **FR-005 (honest red)**: The #3113 residual stays an honest strict xfail on an open issue.
- **FR-011 / C-002**: Every retirement names a covering guard that goes red on the same planted break.
- **NFR-001**: The executed count per file is ≥ before. The retirements here remove only dead guards, never tests.
- **NFR-004**: Every marker in the touched files cites a reason, and every defect citation resolves to an open issue.

## Context & Constraints

- Read first: `spec.md` FR-002 and the Edge Cases ("A strict xfail cites a closed issue but still fails…" → re-point); `plan.md` IC-02; `research.md` D-4, D-5 and D-6; `research/masked-greens.md` rows 4 and 6–9 plus notes 3–4; `quickstart.md` §FR-002.
- **Format-excluded** (do not run `ruff format` on them):
  - `tests/doctrine/test_packaging_parity.py`;
  - `tests/integration/test_clean_install_next.py`;
  - `tests/architectural/test_saas_sync_gate_selection_invariance.py`.
- **Not format-excluded** (run `ruff format --check`):
  - `tests/architectural/test_egress_consent_boundary.py`;
  - `tests/migration/test_teamspace_migration_rehearsal.py`;
  - `tests/migration/test_mission_state_repair.py`;
  - `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py`.
- The **wheel/venv tests** (`test_packaging_parity.py::test_clean_venv_install_imports_and_resolves_built_in` and `test_clean_install_next.py::test_clean_install_next_runs_without_runtime`) build a wheel or venv. Run them **by node id**, once each, never as a suite.
- Read-only covering guards (never edit):
  - `tests/architectural/test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies` (`:96`);
  - `::test_shared_dependencies_use_public_pypi_ranges` (`:113`);
  - `::test_events_dependency_floor_rejects_pre_v10_contract` (`:128`). This one is **not** a covering guard for #932: it overwrites the events dependency itself and never reads the live floor, so a planted floor change leaves it green.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP02 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never a test directory as a whole, never `make test-full`, and no stress, timing, e2e or performance suite.
2. **Planted breaks never land (C-007).** Scratch edits only. Revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty** for this WP, which changes no product source) and `git diff --stat` before **every** commit.
3. **Planted-break protocol (FR-011).** A FIX goes red under its plant. A RETIRE's covering guard goes red under the same plant. If a guard stays green, stop: the verdict becomes KEEP or FIX, so report it to the orchestrator.
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP02 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" <owned files>`. Every hit carries a reason, and every defect citation is to an open issue (`unset GITHUB_TOKEN && gh issue view <n> -R spec-kitty/spec-kitty --json state`).
6. **Quality (NFR-005).** `uv run --frozen ruff check <owned files>`, plus `ruff format --check` on the non-excluded files. Delete imports that become unused (for example `packaging.version.Version` once `_has_events_5` is gone). Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
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

### Subtask T006 – #3113: file the residual issue; re-point the xfails and the landmine guard in one edit

- **Purpose**: #3113 closed as COMPLETED once limit 8 was documented, and FR-015 measured a matcher tightening and rejected it. The two strict xfails still fail for their stated reason, so they are honest pins of an accepted blind spot. The spec's edge case says to re-point them, not remove them (research D-4).
- **Files**: `tests/architectural/test_egress_consent_boundary.py`.
- **Anchors**:
  - the parametrize cases of `TestGuardBites::test_scanner_detects_each_sink_shape` with ids `injected-transport-positional-url-name` and `injected-transport-positional-non-url-name`, whose `xfail(strict=True, reason="#3113 case (A)…")` / `"#3113 case (B) -- THE ADOPTION GATE…"` sit around `:963-1001`;
  - the landmine guard `test_positional_transport_strict_xfail_landmines_disposition_still_pending` at `:1013-1040`, whose `:1040` asserts `"#3113" in xfail_mark.kwargs.get("reason", "")`;
  - the module-docstring limit-8 cross-reference at `:151`, `:172` and `:176-177`;
  - `TestCompletenessLimitsDocstring::test_limit_8_positional_transport_call_is_documented` at `:861-875`.
- **Steps**:
  1. **Verify first**: confirm both cases still fail for their reason.
     ```bash
     uv run --frozen pytest "tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape" --runxfail -rxX -n0 -q
     ```
     Expect 2 FAILED with `scanner went blind to transport-call`.
  2. **File the issue before editing**:
     ```bash
     unset GITHUB_TOKEN && gh issue create -R spec-kitty/spec-kitty \
       --title "egress guard limit 8: all-positional injected transport call (accepted residual)" \
       --body "Accepted residual of #3113 (closed COMPLETED 2026-08-02): the egress sink scanner is blind to an all-positional injected transport call (no url=/headers= keywords). FR-015 measured a structural matcher tightening and rejected it for src/-wide false positives. Pinned by two strict xfails in tests/architectural/test_egress_consent_boundary.py (TestGuardBites::test_scanner_detects_each_sink_shape[injected-transport-positional-*]). Re-pointed by test-suite-remediation-01M3SSDW (#5346/#5353). Close only when the matcher closes the gap (the strict xfails then XPASS and must be removed)."
     ```
     Record `#NNNN`. Confirm it is OPEN.
  3. In **one edit**:
     - Replace `#3113` in both xfail `reason=` strings with `#NNNN`. You may keep "(accepted residual of #3113)" as provenance; the load-bearing citation must be the open issue. Keep `strict=True`.
     - Update the landmine guard: `assert "#NNNN" in xfail_mark.kwargs.get("reason", "")`. Update its docstring so it says the tracking reference is the open residual issue.
     - Update the module docstring's limit-8 cross-reference to name `#NNNN` as the open tracker, and keep `#3113` as history.
  4. Re-run the `--runxfail` command (still 2 FAIL for the reason), then the whole file: `uv run --frozen pytest tests/architectural/test_egress_consent_boundary.py -n0 -q -rxX`. The landmine guard passes, and both cases report XFAIL.
- **Planted-break proof**: plant `"#3113"` back in one reason string (scratch). The landmine guard goes RED. Revert.
- **Edge cases**:
  - Do not convert the cases to characterization asserts. R4 rejected that.
  - `TestCompletenessLimitsDocstring` must still pass. It pins the limit-8 text, not the issue number; check what it matches.

### Subtask T007 – #932: delete `_has_events_5` and its 6 guard sites

- **Purpose**: The guard is unreachable: the floor is `spec-kitty-events>=10.4.0`, so 0 of 61 fire. Dead guards that can re-disarm silently are masked greens.
- **Files and anchors**:
  - `tests/migration/test_teamspace_migration_rehearsal.py`: the def at `:22`, and the `skipif` at `:169` on `test_teamspace_mission_state_rehearsal_is_deterministic_across_clones`. The docstring at `:171` citing "#932 launch rehearsal" is **provenance** and may stay.
  - `tests/migration/test_mission_state_repair.py`: the def at `:25`, the guard sites `:631`, `:690` and `:749` (`if not _has_events_5(): pytest.skip(...)`), and the unreachable branch at `:161-164`, which T008 handles.
  - `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py`: the def at `:68`, and the `skipif`s at `:189` and `:270`.
- **Steps**:
  1. Baseline:
     ```bash
     uv run --frozen pytest tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py -n0 -q -rs
     ```
     Expect 61 passed, 0 skipped.
  2. Delete the three `_has_events_5` definitions and the 6 guard sites: `:169`, `:631`, `:690`, `:749`, `:189` and `:270` (the skipif decorators count as sites). Leave the unreachable branch at `:161-164` for T008.
  3. Remove the imports that become unused (`from packaging.version import Version`, if nothing else uses it).
  4. Re-run: 61 passed, 0 skipped. The executed count is unchanged.
- **Covering guard (C-002)**: `tests/architectural/test_pyproject_shape.py::test_shared_dependencies_use_public_pypi_ranges` (`:113`). It asserts the exact `_EXPECTED_SHARED_RANGES` (`:27-30`, `spec-kitty-events>=10.4.0,<11`) against the **live** `pyproject.toml`.
  - Plant `spec-kitty-events>=4.0` as the floor in a scratch copy of `pyproject.toml` (**revert**). The guard goes RED at `:118`.
  - Do **not** use `test_events_dependency_floor_rejects_pre_v10_contract` (`:128`): it overwrites the dependency itself and stays green under this plant.
- **Parallel?**: Yes, alongside T009.

### Subtask T008 – Version-monkeypatch refusal test replacing the unreachable branch

- **Purpose**: The unreachable `if not _has_events_5():` branch at `test_mission_state_repair.py:161-164` was the **only** test of the product refusal at `src/specify_cli/migration/mission_state.py:1183-1184`:

  ```python
  if package_version < REQUIRED_EVENTS_PACKAGE:
      raise MissionStateDryRunError(f"TeamSpace dry-run requires spec-kitty-events >= {REQUIRED_EVENTS_PACKAGE}; …")
  ```

  `REQUIRED_EVENTS_PACKAGE = Version("5.0.0")` is defined at `:71`. Retiring the guard without a replacement would leave that product branch untested (research D-5).
- **Files**: `tests/migration/test_mission_state_repair.py`.
- **Steps**:
  1. Delete the branch at `:161-164`, so the test proceeds straight to `teamspace_dry_run(...)`.
  2. Add a focused test, e.g. `test_teamspace_dry_run_refuses_events_package_below_required_floor`:
     - Build the same minimal repo fixture the surrounding test uses. Reuse its helper; do not copy 80 lines. If the refusal happens before any repo read, a smaller fixture is fine: check `_load_events_contract` call order in `teamspace_dry_run`.
     - `monkeypatch.setattr(spec_kitty_events, "__version__", "4.9.0")`.
     - `with pytest.raises(MissionStateDryRunError, match=r"requires spec-kitty-events >="): teamspace_dry_run(repo, mission=...)`.
  3. Run the file. The new test passes.
- **Planted-break proof (FIX)**: delete the `raise` at `mission_state.py:1183-1184` (scratch; revert with `git checkout -- src/specify_cli/migration/mission_state.py`). The new test goes RED. The old form could never run, so it stayed "green" under the break. Record both.
- **Edge cases**:
  - Patch the attribute on the module object that `mission_state` imports (`import spec_kitty_events` inside the function reads the module attribute at call time), so `monkeypatch.setattr(spec_kitty_events, "__version__", ...)` works.
  - Do not patch `Version`.

### Subtask T009 – EXPERIMENTAL#828: retire both skipifs and delete the helper

- **Purpose**: `clean_install_acceptance_deferred()` is true only when `uv.lock` has a **git** source for events or tracker. The lock takes both from PyPI, so the guard never fires, but it could silently re-disarm the two clean-install acceptance tests.
- **Files and anchors**:
  - `tests/doctrine/test_packaging_parity.py`: the import at `:40`, the skipif at `:186-189`.
  - `tests/integration/test_clean_install_next.py`: the import at `:30`, the skipif at `:59-62`.
  - `tests/_support/shared_package_deferral.py`: delete it (15 lines). Its only importers are these two files; verify with `git grep -n "shared_package_deferral"`.
- **Steps**:
  1. Remove both decorators and both imports, and delete the helper with `git rm`.
  2. `rg -n "_has_events_5|clean_install_acceptance_deferred|shared_package_deferral" tests` must return nothing (this also covers T007).
  3. Run each wheel test **once, by node**:
     ```bash
     uv run --frozen pytest "tests/doctrine/test_packaging_parity.py::test_clean_venv_install_imports_and_resolves_built_in" -n0 -q -rs
     uv run --frozen pytest "tests/integration/test_clean_install_next.py::test_clean_install_next_runs_without_runtime" -n0 -q -rs
     ```
     If either fails for a network or tooling reason, classify it with the baseline-red gotcha, compare against the base, and record it. Do not re-add a skip.
- **Covering guards (C-002)**: `test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies` and `::test_shared_dependencies_use_public_pypi_ranges`. Planted break: add `[tool.uv.sources] spec-kitty-events = { git = "https://github.com/spec-kitty/spec-kitty-events", rev = "deadbeef" }` to a scratch `pyproject.toml`, which is how a git pin re-enters the lock. Both guards go RED ("committed local source for spec-kitty-events"). Revert.
- **Evidence note**: state the ambiguity. The cited "#828" is **EXPERIMENTAL#828** ("de-factory dependency pins → PyPI ranges", CLOSED 2026-09-01). `spec-kitty/spec-kitty#828` is an unrelated docs issue, the same ambiguity class as #171.

### Subtask T010 – Sync gate re-cite, row-8 false positive, hygiene, evidence

- **Purpose**: The sync gate is a live guard with a stale premise. KEEP it and correct the citation (research D-6). Retiring it would violate C-002, because no other gate bans module-scope env writes in `tests/`.
- **Files**: `tests/architectural/test_saas_sync_gate_selection_invariance.py` (format-excluded; **docstring only**).
- **Steps**:
  1. Rewrite the module docstring (`:1-24`). Its premise today is "import-time `skipif(not os.environ.get(...))` gates are selection-dependent (#3213)"; zero such gates remain.
     - The live premise: **process-global opt-out kill-switch pollution (post-#3980)**. Product still reads `SPEC_KITTY_ENABLE_SAAS_SYNC` at runtime as an opt-out kill switch (`src/specify_cli/core/saas_sync_config.py:28`, `src/specify_cli/tracker/saas_readiness.py`). So a module-scope write, e.g. `"0"`, pollutes every later test in the worker.
     - Keep #3213 and #3980 as history.
     - Do not change any test logic.
  2. Run `uv run --frozen pytest tests/architectural/test_saas_sync_gate_selection_invariance.py -n0 -q`. Expect 3 passed.
  3. **KEEP proof**: add `os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"` at module scope of a **scratch** file `tests/unit/test_zz_scratch_sync_flag.py` (never committed; delete it afterwards). `test_no_test_module_sets_the_flag_at_import_time` goes RED. Delete the scratch file.
  4. **Row 8 (false positive)**: record a NO-OP evidence item. `tests/architectural/test_charter_sole_door_agent_profile_repository.py` has no skip or xfail; its "828" is a line number (`_doctrine_collect.py` sites 193/283/420/828). Do **not** edit that file.
  5. **Skip hygiene** over all 8 owned files (rule 5), and `gh issue view` for every cited issue.
  6. **Issue matrix**:
     ```bash
     spec-kitty agent issue-verdict --mission test-suite-remediation-01M3SSDW --issue "#NNNN" --verdict deferred-with-followup --actor claude-sonnet-5 --wp WP02 --evidence-ref "Follow-up: #NNNN accepted residual (strict xfail re-pointed)"
     ```
     If the matrix already carries #3113, #932 or #3213 rows, add verdicts for them only when the matrix asks for them. Report what you did.
  7. `make test-fast` once.
- **Evidence records**:
  - MG-04 (RE-POINT; `--runxfail` output);
  - MG-06 (RETIRE plus the new FIX test, with the pyproject-floor plant and the `raise` deletion plant);
  - MG-07 (RETIRE, git-source plant);
  - MG-08 (NO-OP);
  - MG-09 (KEEP, scratch module plant).

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_egress_consent_boundary.py tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py tests/architectural/test_saas_sync_gate_selection_invariance.py tests/architectural/test_pyproject_shape.py -n0 -q -rs
uv run --frozen pytest "tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape" --runxfail -rxX -n0 -q
uv run --frozen pytest "tests/doctrine/test_packaging_parity.py::test_clean_venv_install_imports_and_resolves_built_in" -n0 -q -rs
uv run --frozen pytest "tests/integration/test_clean_install_next.py::test_clean_install_next_runs_without_runtime" -n0 -q -rs
uv run --frozen ruff check tests/architectural/test_egress_consent_boundary.py tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py tests/doctrine/test_packaging_parity.py tests/integration/test_clean_install_next.py tests/architectural/test_saas_sync_gate_selection_invariance.py
uv run --frozen ruff format --check tests/architectural/test_egress_consent_boundary.py tests/migration/test_teamspace_migration_rehearsal.py tests/migration/test_mission_state_repair.py tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
make test-fast
```

## Risks & Mitigations

- **The issue number must exist before the reason is edited.** File it first; T006 enforces this order.
- **The wheel tests are slow or network-dependent.** Run each once by node and classify any environment red; do not loop them.
- **Deleting the helper module** might break an importer outside these two files. Run the `git grep` in T009 first.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- The `--runxfail` output still shows 2 FAIL for the stated reason, and the reasons cite an **open** issue.
- The landmine guard and the xfail reasons changed in the **same commit**.
- The new version-monkeypatch test goes RED when the `raise` is deleted (SC-005 pick: quickstart Break #4).
- The git-source plant reds both pyproject-shape guards (SC-005 pick: Break #5).
- The sync gate kept its logic; only the docstring premise changed.
- `rg` for the retired helpers returns nothing.

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
spec-kitty agent tasks mark-status T006 T007 T008 T009 T010 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP02 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
