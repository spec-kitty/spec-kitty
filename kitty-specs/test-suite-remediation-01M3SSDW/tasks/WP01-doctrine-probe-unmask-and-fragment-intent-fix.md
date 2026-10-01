---
work_package_id: WP01
title: Doctrine probe unmask and fragment-intent product fix
dependencies: []
requirement_refs:
- FR-001
- FR-005
- FR-011
- NFR-001
- NFR-004
- NFR-005
- C-001
- C-005
- C-007
- SC-001
- SC-005
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 1be3b4c739fd25cded73ba0bb4df595d1ef0df25
created_at: '2026-09-30T20:53:08.227912+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Masked greens
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/doctrine/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/doctrine/pack_validator.py
- tests/specify_cli/doctrine/test_pack_validator.py
- tests/integration/test_quickstart_end_to_end.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Doctrine probe unmask and fragment-intent product fix

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

- **SC-001 / FR-001**: The 9 tests that probe for shipped doctrine execute instead of skipping. There are 5 in `TestIntentAwareCollision` and 4 in the quickstart end-to-end steps. `-rs` shows **9 SKIPPED before, 0 after**.
- **FR-005**: The defect that unmasking surfaced is fixed **red-first**, in **its own `fix(...)` commit**, through the pre-existing entry point `validate_pack(pack_dir)`.
  - The defect: intent declared in `drg/fragment.yaml` is ignored by `_collect_fragment_edge_intent`, which emits a spurious `same_id_collision` advisory.
  - A **newly filed issue** describes the defect and is cited in the regression test docstring.
- **FR-011**: Every FIX carries a planted-break record (data-model.md §4).
- **NFR-001** (amended): each file's executed count is ≥ before, and the two files together are ≥ before + 9.
- **NFR-004 / NFR-005**: every marker in the touched files carries a reason; 0 new ruff findings; complexity ≤ 15.
- **C-005**: `src/specify_cli/doctrine/pack_validator.py` changes only in the fix commit.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`, `kitty-specs/test-suite-remediation-01M3SSDW/spec.md` (FR-001, FR-005, US3), `plan.md` IC-01, `research.md` D-1 and D-3, `research/masked-greens.md` rows 1–3 plus notes 1 and 2, and `quickstart.md` §FR-001 and §FR-005.
- **Why the probe is wrong**:
  - `_has_built_in_doctrine()` reads `resolve_doctrine_root()/"tactics"/"built-in"`. That is the doctrine **package** root (`src/charter/offering`), and the directory does not exist, so all 9 tests skip on every run.
  - Packs always ship, and `charter.offering.pack_paths.built_in_dir` fails closed with `PackRootNotFound`. A "skip if absent" probe is therefore always either dead or masking.
- **Format-excluded files** (`pyproject.toml [tool.ruff.format].exclude`): all three owned files. Edit them **without** running `ruff format` on them. Reformatting would force an exclude-list removal (`test_ruff_format_exclude_ratchet.py`) and drag `pyproject.toml` into the diff.
- The CLI `doctrine … validate` calls the same `validate_pack` at `src/specify_cli/cli/commands/doctrine.py:419`, so a regression test through `validate_pack` covers the CLI path.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP01 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves. Never reconstruct `.worktrees/...` paths by hand.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001, `NO_FULL_HEAVY_SUITES_IN_MISSION`).** Run exactly the commands in this prompt, plus `make test-fast` once as the shared baseline.
   - Never pass `tests/architectural/` or any other test directory as a whole.
   - Never run `make test-full`, and run no stress, timing, e2e or performance suite.
2. **Planted breaks never land (C-007).** A planted break is a scratch edit: apply it, observe, then `git checkout -- <file>`. Before **every** commit run `git diff --stat src/` and `git diff --stat`, and confirm that only the intended changes are present.
3. **Planted-break protocol (FR-011).**
   - For a FIX: plant the break, confirm the old form stayed green (where applicable) and the new form goes red, revert, and confirm green.
   - For a RETIRE: the named covering guard goes red on the same plant.
4. **Evidence.** Write one record per item in the data-model.md §4 YAML shape, into a file in your session scratchpad, outside the repository. **Never** put evidence under `kitty-specs/`. Hand it off in two ways:
   - paste the records into the `--note` of your `move-task WP01 --to for_review` (the FULL records, never a summary; see additional rule B);
   - include them verbatim in your final report, so the orchestrator can lift them into the PR.
5. **Skip hygiene (NFR-004).** Run `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" <owned test files>`. Every hit must carry a reason, and every defect citation must resolve to an **open** issue (`unset GITHUB_TOKEN && gh issue view <n> -R spec-kitty/spec-kitty --json state`).
6. **Quality (NFR-005).** Run `uv run --frozen ruff check <owned files>` and `uv run --frozen mypy src/specify_cli/doctrine/pack_validator.py`. Add no new `noqa` or `type: ignore`. Keep complexity ≤ 15.
7. **Tracers.** Record rationale with `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "<1–3 sentences>" --actor claude-sonnet-5`. Record friction under `--category tooling-friction`.
8. **Baseline-red gotcha.** Classify any red you did not cause using CLAUDE.md: a pre-existing P0, a CI-env failure, a stale install, or a stale venv (fix the last with `uv sync --frozen --all-extras`). Never green-wash it.
9. **Commit trailers.** End every commit message with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   Do not edit CHANGELOG entries; the orchestrator writes them at closeout.

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

### Subtask T001 – Delete the class probe in the pack-validator tests; assert the precondition

- **Purpose**: Make the 5 `TestIntentAwareCollision` tests execute. Replace the masking probe with a loud precondition, so the two "suppresses advisory" tests (`collision_advisories == []`) can never pass vacuously if the fixture tactic id disappears from the built-ins.
- **Files**: `tests/specify_cli/doctrine/test_pack_validator.py`.
- **Anchors**:
  - class `TestIntentAwareCollision` at `:405`;
  - the probe `_has_built_in_doctrine` at `:415-423`;
  - the skip guards at `:427`, `:452`, `:481`, `:526`, `:550`;
  - the fixture constant `_BUILT_IN_TACTIC_ID`;
  - the class docstring `:406-413`, which claims the tests "skip themselves explicitly".
- **Steps**:
  1. **Baseline first.** Record the counts:
     ```bash
     uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py -n0 -q -rs
     ```
     It should show 9 SKIPPED. Keep the pass/skip counts for NFR-001.
  2. Delete `_has_built_in_doctrine` and all 5 `if not self._has_built_in_doctrine(): pytest.skip(...)` blocks.
  3. Add one small helper (module-level or class-level) that asserts the precondition through the canonical seam:
     ```python
     from charter.offering.artifact_kinds import ArtifactKind
     from charter.offering.pack_paths import built_in_dir

     def _assert_built_in_fixture_tactic_present() -> None:
         path = built_in_dir(ArtifactKind.TACTIC) / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml"
         assert path.is_file(), f"fixture tactic {_BUILT_IN_TACTIC_ID!r} missing from shipped built-ins at {path}"
     ```
     Call it at the top of each of the 5 tests, or through an autouse fixture scoped to the class. Verify the import path first: `built_in_dir` lives in `charter.offering.pack_paths` (masked-greens note 1). `tests/architectural/test_built_in_location_authority.py` scans `src/` only, so calling it from tests is allowed.
  4. Rewrite the class docstring so it states the precondition assert instead of the self-skip.
  5. Run the file. Expect 7 of 9 to pass across both files. The two `*_suppresses_collision_advisory` tests go RED with `drg_root_graph_missing`, which is the stale `intent.graph.yaml` fixture. T003 handles them; do not paper over them with `check_drg_root=False`.
- **Edge cases**:
  - If `built_in_dir` raises `PackRootNotFound` in your environment, the environment is broken (packs always ship). Report it; do not skip.
  - Do not touch the other test classes in the file (`TestRenderValidationResult` and so on).

### Subtask T002 – Delete the module probe in the quickstart end-to-end tests

- **Purpose**: Make the 4 quickstart step tests execute.
- **Files**: `tests/integration/test_quickstart_end_to_end.py`.
- **Anchors**:
  - the module-level `_has_built_in_doctrine()` at `:394`;
  - its uses at `:411` (`test_step4a_same_id_advisory_uses_reworded_message`), `:439` (`test_step4b_inline_enhances_is_rejected_after_hard_cutover`), `:463` (`test_step4b_unknown_enhances_target_errors`) and `:558` (`test_step5_pack_validate_json_has_no_shipped_layer_label`).
- **Steps**:
  1. Delete the probe function and the 4 `if not _has_built_in_doctrine(): pytest.skip(...)` guards.
  2. Add the same precondition assert as in T001. Use a module-local helper; do not import it across test modules. Check which fixture tactic id these tests use; each test writes its own pack.
  3. Run `uv run --frozen pytest tests/integration/test_quickstart_end_to_end.py -n0 -q -rs`. Expect the 4 former skips to pass (masked-greens verified 4/4).
- **Parallel?**: Yes, alongside T001.
- **Edge cases**: The file is `integration`-marked and may need a git fixture; running it by name is allowed (C-001).

### Subtask T003 – RED commit: fragment.yaml fixture, regression test, new issue

- **Purpose**: Turn the two stale intent-suppression tests into honest regression tests of the shape the runtime actually reads (`drg/fragment.yaml`), and add an explicit regression test that is RED on today's product. This is the red-first half of FR-005.
- **Files**: `tests/specify_cli/doctrine/test_pack_validator.py`.
- **Anchors**:
  - `_write_drg_intent` at `:382-402`, which writes `drg/intent.graph.yaml` with `nodes: []` and an `edges:` list of `tactic:<id> —<relation>→ tactic:<id>`;
  - `test_enhances_suppresses_collision_advisory` at `:425`;
  - `test_overrides_suppresses_collision_advisory` at `:450`.
- **Steps**:
  1. **File the issue first**, so its number can be cited:
     ```bash
     unset GITHUB_TOKEN && gh issue create -R spec-kitty/spec-kitty \
       --title "pack validator ignores drg/fragment.yaml augmentation intent (spurious same_id_collision advisory)" \
       --body "<repro: tactic adversarial-qa-handoff + drg/fragment.yaml enhances edge -> validate_pack ok=True + same_id_collision advisory telling the author to declare the intent already declared; *.graph.yaml is a hard error since #3387, so no DRG shape validates clean with declared intent. Found by test-suite-remediation-01M3SSDW (#5346 / #5353).>"
     ```
     Record the number (call it `#NNNN`).
  2. Re-author the fixture writer so it writes `drg/fragment.yaml` in the **org-fragment** shape the runtime reads. Rename it, e.g. `_write_fragment_intent`, and keep the old writer only if the step below needs it.
     - Before writing it, read `src/specify_cli/doctrine/pack_validator.py:543-570` (`_validate_org_fragment` → `load_org_pack`) and `tests/doctrine/drg/test_org_fragment_validation.py` for a valid minimal `fragment.yaml`.
     - The fragment must validate cleanly through `load_org_pack`. Otherwise the test goes red for the wrong reason (an `org_pack_*` finding).
  3. Point the two `*_suppresses_collision_advisory` tests at the fragment writer. They should now be RED on the spurious `same_id_collision` advisory, not on `drg_root_graph_missing`.
  4. Add one **regression test** through `validate_pack(pack_dir)`, for example `test_fragment_yaml_augmentation_intent_suppresses_same_id_collision`, parametrized over `enhances` and `overrides`. It asserts:
     - `result.ok`;
     - **no** issue with `category == "same_id_collision"` for `_BUILT_IN_TACTIC_ID`;
     - no `drg_root_graph_missing`.

     Its docstring cites `#NNNN` and FR-005.
     - **Positive-control arm on the same fixture (m7)**: add a parametrize case with the same `_write_tactic(...)` but **no** `drg/fragment.yaml`, which asserts that the `same_id_collision` advisory **is** present. This proves the absence assertion is not vacuous.
  5. Keep **one** `drg/*.graph.yaml`-shaped case with `validate_pack(pack_dir, check_drg_root=False)`, so the `_DRG_GRAPH_GLOB` path of `_collect_fragment_edge_intent` stays covered. You can re-point one existing graph-shaped assertion or add a small new test; the existing writer is the natural fixture.
  6. Run the file and confirm the new or re-pointed fragment tests are RED **on the advisory** (read the failure text).
  7. Commit the test-only change:
     ```
     test(doctrine): pin drg/fragment.yaml intent against spurious same_id_collision (red) (#NNNN)
     ```
     `git diff --stat src/` must be empty for this commit.
- **Edge cases**:
  - If the fragment fixture triggers `org_pack_missing`, `org_pack_schema` or similar, the fixture is wrong. Fix the fixture; never weaken the assertion.
  - Do not use `check_drg_root=False` on the fragment tests. That was the rejected fallback (research D-3), which would re-mask the defect.

### Subtask T004 – Product fix: `_collect_fragment_edge_intent` folds `drg/fragment.yaml`

- **Purpose**: The green half of FR-005, in its **own** commit, touching only the product file (C-005).
- **Files**: `src/specify_cli/doctrine/pack_validator.py` (format-excluded; do not reformat it).
- **Anchors**:
  - `_collect_fragment_edge_intent` at `:1260-1300`. It globs only `drg/*.graph.yaml` (`_DRG_GRAPH_GLOB`) and loads each file with `charter.offering.drg.loader.load_graph`.
  - `_validate_org_fragment` at `:543-570`, which uses `load_org_pack(pack_name=..., pack_root=..., layer_index=1)`.
  - The call site that consumes the collected intent. Grep `_collect_fragment_edge_intent(`.
- **Steps**:
  1. Add a branch: when `drg_dir / "fragment.yaml"` exists, fold its augmentation edges (`enhances`, `overrides`) into the same `intent` mapping, through the **same org-fragment loading authority** `_validate_org_fragment` uses. That is the single-loader direction (#4189); do not write a second YAML parser.
     - Check what `load_org_pack` returns (the graph or fragment object with `.edges`), or reuse the loader's fragment-parsing helper.
     - Keep the function best-effort: a fragment that fails to load is skipped, because `_validate_org_fragment` already surfaces the load error.
     - **Do not import any name listed in the dead-symbol allowlist (F-04).** `charter.offering.drg.org_pack_loader` carries three allowlisted dead `__all__` symbols (`AUGMENTATION_RELATIONS`, `TOPOLOGY_KINDS`, `merge_topology_artifact`; `test_no_dead_symbols.py:1069-1078`). `AUGMENTATION_RELATIONS` is exactly the tempting "enhances/overrides relation set".
       - Importing one would turn its entry REVIVED/stale, red the dead-symbol gate after lane consolidation, and shift the parity that WP10–WP12 freeze.
       - `load_org_pack` is already live and safe to reuse; so is the local `Relation.ENHANCES/OVERRIDES` set the function already builds.
       - If reusing an allowlisted name is unavoidable, stop and report, so that the dead-symbol chain can remove the entry.
  2. The record path stored with the intent (`fragment_path`) must be the `fragment.yaml` path, so messages name the right file.
  3. Keep complexity ≤ 15. If the function grows, extract a helper, e.g. `_fold_augmentation_edges(edges, source_path, intent)`, shared by the glob loop and the fragment branch. That also removes duplication.
  4. **Do not change** `_check_drg_root_graph_missing` (`:764`) or the `drg_root_graph_missing` error from #3387.
  5. Run:
     ```bash
     uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py tests/doctrine/drg/test_org_fragment_validation.py -n0 -q -rs
     uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q   # named gate file, ~4 min (F-04)
     ```
     All green, 0 skipped among the 9. The dead-symbol gate stays green: the fix revived no allowlisted symbol and created no new dead one.
  6. Run `uv run --frozen ruff check src/specify_cli/doctrine/pack_validator.py` and `uv run --frozen mypy src/specify_cli/doctrine/pack_validator.py`.
  7. Commit **only** the product file:
     ```
     fix(doctrine): fold drg/fragment.yaml augmentation intent into the collision pass (#NNNN)
     ```
     `git show --stat HEAD` must list exactly one file.
- **Edge cases**: A pack with **both** `drg/fragment.yaml` and a `*.graph.yaml`: the graph file is still a `drg_root_graph_missing` error. The intent from both sources may be folded, but the error must stay.

### Subtask T005 – Planted breaks, counts, hygiene, issue matrix, evidence

- **Purpose**: FR-011 proof for each FIX, the NFR-001 count, the NFR-004 hygiene check and tracker bookkeeping.
- **Planted breaks** (scratch only; revert each with `git checkout -- src/specify_cli/doctrine/pack_validator.py`). The first three come from quickstart §FR-001 and §FR-005.
  1. **Reworded wording.** Make `_load_built_in_ids_per_kind` (`:1068`) return `{}`. `test_same_id_collision_uses_reworded_wording` and `test_step4a_same_id_advisory_uses_reworded_message` must go RED. Before this WP they SKIPPED, which is the old form.
  2. **Unknown target.** Drop **both** `unknown_target` appends, each in its own scratch run:
     - `:1180`, the `overrides` branch: `test_overrides_unknown_target_errors` goes RED;
     - `:1198`, the `enhances` branch: `test_enhances_unknown_target_errors` and `test_step4b_unknown_enhances_target_errors` go RED.
  3. **Intent suppression.** Make `_collect_fragment_edge_intent` return `{}`. Both `*_suppresses_collision_advisory` tests and the new regression test must go RED.
  4. **Precondition.** Point the precondition assert at a nonexistent tactic id, in scratch. The tests fail loudly and do not pass vacuously.
  5. **Inline enhances cutover.** Stop rejecting the inline `enhances` field. `test_step4b_inline_enhances_is_rejected_after_hard_cutover` goes RED.
- **Counts (NFR-001)**: Re-run the baseline command. Record the executed count before and after (pass + fail + xfail, not skip) for each file. Each file must be ≥ before, and the two files together ≥ before + 9 (amended NFR-001).
- **Skip hygiene**: `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py`. Each remaining hit must carry a reason, and any defect citation must point to an open issue.
- **Issue matrix**:
  ```bash
  spec-kitty agent issue-verdict --mission test-suite-remediation-01M3SSDW --issue "#NNNN" --verdict fixed --actor claude-sonnet-5 --wp WP01 --evidence-ref "<fix commit sha>"
  ```
- **Evidence records** (data-model §4): one each for MG-01 (rows 1 and 3, RUN), MG-02 (row 2, RUN+FIX) and the FR-005 fix (kind FIX, red commit sha, fix commit sha).
- **Baseline**: `make test-fast` once.

## Test Strategy

The named-file runs, all with `-n0 -q -rs`:

```bash
uv run --frozen pytest tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py tests/doctrine/drg/test_org_fragment_validation.py -n0 -q -rs
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q
uv run --frozen ruff check src/specify_cli/doctrine/pack_validator.py tests/specify_cli/doctrine/test_pack_validator.py tests/integration/test_quickstart_end_to_end.py
uv run --frozen mypy src/specify_cli/doctrine/pack_validator.py
make test-fast
```

`tests/doctrine/drg/test_org_fragment_validation.py` is a read-only covering guard. Do not edit it.

## Risks & Mitigations

- **A fragment fixture that is itself invalid** makes the red look right for the wrong reason. Read the failure message: it must name `same_id_collision`.
- **The fix leaks into the `*.graph.yaml` error path.** The org-fragment validation file guards it. Also plant a graph-only pack and confirm `drg_root_graph_missing` still fires.
- **Commit mixing.** The fix commit must contain only `pack_validator.py`. The red commit must contain no `src/` change.

## Definition of Done (C-011)

- **C-011 (product code; D1 reading, `traces/design-decisions.md`)**: the T003 red commit is RED on the planning base (the fragment-intent regression test fails on `same_id_collision`). It is GREEN at this WP's final commit, after the separate T004 `fix(...)` commit that touches only `pack_validator.py`. The test-only unmasks (T001/T002) carry the planted-break red→green proof.

## Review Guidance

- Check out the red commit and confirm the regression test is RED on `same_id_collision`. On the fix commit it is GREEN (quickstart §FR-005).
- `git diff <base>..HEAD -- src/` shows only the `pack_validator.py` fix.
- `-rs` shows 0 SKIPPED for the 9 former probe tests.
- Re-run planted breaks #1 and #3 yourself (SC-005 picks).
- The regression test docstring cites the new, open issue, and the issue-matrix row exists.
- `ruff check` and `mypy` are clean on the product file.

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
spec-kitty agent tasks mark-status T001 T002 T003 T004 T005 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP01 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
