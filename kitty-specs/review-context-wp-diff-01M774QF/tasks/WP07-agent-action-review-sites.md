---
work_package_id: WP07
title: Agent action review render sites (2 and 3) on the shared renderer
dependencies:
- WP05
requirement_refs:
- FR-012
- FR-013
- NFR-004
- C-002
- C-004
- C-010
- SC-003
planning_base_branch: feat/7578-review-context
merge_target_branch: feat/7578-review-context
branch_strategy: Planning artifacts for this mission were generated on feat/7578-review-context. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/7578-review-context unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
- T036
- T037
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/integration/review/test_review_range_acceptance_action.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/workflow_cores.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/review/prompt_metadata.py
- tests/integration/review/test_review_range_acceptance_action.py
- tests/specify_cli/cli/commands/agent/test_workflow_cores.py
- tests/agent/test_workflow_mixed_dependency_review_context.py
- tests/integration/review/test_canonical_review_diff_refs.py
- tests/characterization/test_trio_pure_cores.py
role: implementer
tags: []
tracker_refs: []
---

# WP07: Agent action review render sites (2 and 3) on the shared renderer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Move **render site 2** (the `spec-kitty agent action review` prompt) and **render site 3** (its stdout finalize summary) onto WP05's `render_review_context`, so all three review surfaces print the same range from one `WpReviewRange` (FR-012, SC-003). Make `ReviewPromptMetadata.base_ref` the range base. Retire the second pathspec builder, `workflow_cores.build_owned_files_review_pathspecs`. ATDD-first: the lane's first commit is a red acceptance test for sites 2 and 3, including cross-site equality with site 1.

Implementation command:

```bash
spec-kitty agent action implement WP07 --agent claude --mission review-context-wp-diff-01M774QF
```

## Context

**Why this WP exists.** The `agent action review` path disagrees with the `next` path (research/code-grounding.md §2): `workflow._resolve_review_context` (~1956) → `workflow_executor.review_context_for_repo_root_workspace` (~2534: `claim_commit..HEAD`, open above, last-claim lower bound) or `review_context_for_worktree_branch` (~2610: lane base / mission branch / scored search, whole lane) → `build_review_prompt_lines` (~2262) → `_review_context_line` (~2115). The post-plan squad (research.md P1) found a third render site, `_review_print_finalize_summary` (~2473-2510), and (P2) a second pathspec builder, `workflow_cores.build_owned_files_review_pathspecs` (~540), used at ~2126 and ~2503.

**What this WP consumes (do not reimplement):**

- **WP05**: `specify_cli.review.context_block.render_review_context(review_range, cited) -> list[str]`; site 1 already renders through it. The shared acceptance fixtures and helpers in `tests/integration/review/review_range_fixtures.py` (owned by WP05; import them, do not edit them): the four review-ready fixtures, `lanes_stamp_stripped`, `review_block`, `run_printed_command`, `assert_no_patch_text`, `snapshot_tree`. If a variant you need is missing, report it in your completion note rather than building a parallel fixture module.
- **WP03**: `resolve_wp_review_range(...) -> WpReviewRange`; `owned_pathspecs` is the one pathspec authority. WP03's tests pin the mission-dir bookkeeping rule ("excluded only when the mission dir is owned").
- **WP04**: `resolve_requirement_texts(...)`.

**Binding constraints.**

- **FR-012 / SC-003**: sites 1, 2 and 3 show the same range; the recorded `ReviewPromptMetadata.base_ref` is the range base.
- **C-002 / FR-013 / NFR-004 and operator ruling Q7**: no new gate, refusal code or exit code. A non-owned `agent action review` with an unavailable range proceeds (exit 0) with the renderer's unavailable notice. `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and message and fires only when an owned checkout's scoped review range is unavailable or the WP declares no `owned_files`; `agent action review` already refuses owned checkouts before any render, and that stays.
- **C-004**: the pre-review gate, its changed-file authority and the for_review gate predicate are not touched.
- **C-010 (per work package)**: the lane's first commit is the failing acceptance test (T032), alone.
- **No path reconstruction.** The builders get `mission_slug`, `owned_files` and `owned` from the caller (T033); they never rebuild a mission directory path.
- Do **not** edit `tests/integration/test_single_branch_write_checkout_e2e.py` (PR #7562 overlap) or anything under `packs/built-in/` (C-003).

**Downstream.** WP06 (docs close-out) depends on this WP.

---

### Subtask T032: ATDD acceptance test for sites 2 and 3, committed RED first

**Purpose**: the executable contract for FR-012, SC-003, FR-013 and NFR-004 on sites 2 and 3, committed red before any production change (C-010).

**Steps**:

1. Create `tests/integration/review/test_review_range_acceptance_action.py`, parametrized over WP05's four review-ready fixtures (`single_branch_commit_to_target`, `single_branch_minted`, `lanes`, `lanes_with_coord`).
2. Drive the production entry points only:
   - **Site 2**: invoke `review WP02 --mission <slug> --agent claude` through the workflow Typer app (`specify_cli.cli.commands.agent.workflow.app`, the way `tests/integration/review/test_canonical_review_diff_refs.py` does), read the written prompt file, and read the `ReviewPromptMetadata` written beside it.
   - **Site 3**: the same invocation's stdout (the finalize summary).
   - **Site 1** (for comparison only): `runtime.next.prompt_builder.build_prompt("review", ...)` on the same fixture copy and repository state.
3. Assertions per fixture:
   - **Exact provenance.** Every fixture prints `[recorded]` with `base: <base12> (window open)` and `tip:  <tip12> (for_review submission)` on site 2. Never accept "recorded or derived".
   - **Cross-site equality (SC-003).** `review_block(site2_prompt) == review_block(site1_prompt)`, byte for byte, including CITED REQUIREMENTS. Site 3 prints the header line and the `git log` command line of that same block (T034), so assert both lines appear verbatim in stdout and that stdout names no other `..` range (in particular no `..HEAD`).
   - **Metadata (FR-012).** `ReviewPromptMetadata.base_ref` equals the full range base SHA printed in the block's `git log` command.
   - **Commit list and CHANGED FILES.** Equal to the fixture's expected commits and exact `+<a> -<r>  <path>` lines; the lane-mate commit on WP02's owned path is absent.
   - **Printed commands run as written (FR-008 on site 2).** Each `git log` / `git diff` line from site 2 runs through `run_printed_command` (`bash -c`) with non-empty output that names no excluded SHA or path. The site-3 `git log` line is run the same way.
   - **No patch text, no diff file (C-001).** `assert_no_patch_text` on the prompt and on stdout; `snapshot_tree` of the prompt directory and the tmp root before and after: no new file besides the prompt and its metadata.
   - **Determinism (NFR-005).** Run site 2 twice in fresh interpreters with `PYTHONHASHSEED=0` and `PYTHONHASHSEED=1` (a `subprocess.run([sys.executable, "-m", "specify_cli", "agent", "action", "review", ...])` or the CLI entry point with the fixture's env), on two copies of the same fixture state, and assert the two blocks are byte-identical.
4. **Unavailable notice (FR-013, NFR-004).** On `lanes_stamp_stripped`: site 2 exits 0, its prompt contains `REVIEW RANGE (WP02): unavailable — <reason>` with the expected reason and the unavailable command line, `ReviewPromptMetadata.base_ref` keeps today's "no base" value (see T033), and site 3 prints `Review range unavailable — <reason>`. No refusal, no traceback.
5. Run the file on the lane base and confirm it is **red for the right reason** (site 2 has no REVIEW RANGE block, the metadata names the old base), not because of an import or fixture error. Commit only this file as the lane's first commit, e.g. `test(review): red acceptance for agent action review sites 2 and 3 (C-010)`.

**Files**: `tests/integration/review/test_review_range_acceptance_action.py` (~250 lines).

**Validation**: `uv run --frozen pytest tests/integration/review/test_review_range_acceptance_action.py -q` fails with assertion errors (not collection errors); `git log -1 --stat` shows only this file.

---

### Subtask T033: Plumb the range into the review-context builders

**Purpose**: resolve one `WpReviewRange` per review and carry it to every render site, without path reconstruction.

**Steps**:

1. In `src/specify_cli/cli/commands/agent/workflow.py` (~2021-2032), change only the two builder calls (2-4 lines): pass `mission_slug=mission_slug`, `owned_files=<the WP's owned_files from the metadata the function already holds>` and `owned=<the owned checkout the caller already holds, or None>` to `review_context_for_repo_root_workspace`, and `owned_files` / `owned` to `review_context_for_worktree_branch` (it already receives `mission_slug`). No other change to `_resolve_review_context`, and no mission-directory path built from strings.
2. In `src/specify_cli/cli/commands/agent/workflow_executor.py`, `review_context_for_repo_root_workspace` (~2534) and `review_context_for_worktree_branch` (~2610): resolve `WpReviewRange` once with `resolve_wp_review_range(repo_root, mission_slug, wp_id, owned_files=..., owned=...)` and fill the existing dict keys from it: `base_branch` = `base_ref` = range base (full SHA), `lane_branch` / `branch_name` = the branch name for display (the commands use the tip SHA), `commit_count` = `len(range.commits)`. Store the range object under one new key, `ctx["review_range"]`, so render sites never re-resolve. When the range is unavailable, leave `base_branch` / `base_ref` at `"unknown"` exactly as today, so downstream truthiness checks keep working.
3. Remove the code paths the range replaces (the claim-commit `..HEAD` arm, the lane-base / mission-branch / scored-search base selection) only where the range now supplies the value. Keep `review_context_search_unknown_base` / `pick_best_base_branch` only if another caller remains; if `test_no_dead_symbols.py` reports them dead after this change, delete them in this WP (no allowlist entry).
4. Keep every touched function ≤ 15 complexity; extract helpers rather than growing functions.

**Files**: `workflow.py` (2-4 lines), `workflow_executor.py` (~-50/+30).

**Validation**: `uv run --frozen pytest tests/agent/ -q`; `tests/architectural/test_execution_context_parity.py`.

---

### Subtask T034: Render sites 2 and 3, and the metadata base

**Purpose**: `agent action review` and its stdout summary show the same block as site 1.

**Steps**:

1. `build_review_prompt_lines` (~2262): resolve the cited requirements once (`resolve_requirement_texts`, `spec.md` read through the placement seam; unreadable → `""`, so IDs render as not declared, NFR-004) and pass them to `_review_context_line`.
2. `_review_context_line` (~2115): render `render_review_context(ctx["review_range"], cited)` inside the existing `─── GIT REVIEW CONTEXT` frame, prefixed by `cd {workspace_path}`. Drop the old `Branch:` / `Base branch:` / `..HEAD` command lines. An unavailable range gives the renderer's unavailable form (no refusal).
3. `_review_print_finalize_summary` (~2473-2510): replace the `Review diff: git log {base}..{branch}` lines with the header line and the `git log` command line taken from the same `render_review_context(...)` output (select by the `REVIEW RANGE (` prefix and the `  git log ` prefix), so the text has one source and no new renderer helper is needed. Unavailable: print `Review range unavailable — <reason>` from the same header line.
4. `ReviewPromptMetadata`: `base_ref` must be the range base. The call at ~2454 already reads `review_ctx["base_ref"]`; confirm it. Touch `src/specify_cli/review/prompt_metadata.py` only if validation rejects a full SHA or the tip must be recorded; any schema change stays backward compatible and is stated in the PR.
5. `workflow*.py` are on the ruff format ratchet: check with `uv run --frozen ruff format --check --force-exclude <files>` (never a bare per-file `ruff format`, which reformats the whole file).

**Files**: `workflow_executor.py` (~-30/+25), possibly `prompt_metadata.py` (0-10).

**Validation**: `uv run --frozen pytest tests/integration/review/ -q`.

---

### Subtask T035: Retire `workflow_cores.build_owned_files_review_pathspecs`

**Purpose**: one pathspec authority, `WpReviewRange.owned_pathspecs`.

**Steps**:

1. Delete `build_owned_files_review_pathspecs` (~540) from `src/specify_cli/cli/commands/agent/workflow_cores.py` and its import in `workflow_executor.py` (~54) and both call sites (~2126, ~2503), which T034 already replaced.
2. `rg -n build_owned_files_review_pathspecs src tests` is empty afterwards, except the test class T036 re-pins in the same lane.

**Files**: `workflow_cores.py` (~-30).

**Validation**: `uv run --frozen ruff check src/specify_cli/cli/commands/agent/workflow_cores.py`.

---

### Subtask T036: Re-pin the executor-side tests (DIRECTIVE_041; re-pin, never delete)

**Purpose**: tests pinning the retired text or builder are stale in their expected text, not wrong in intent. Re-pin each; delete no test function.

**Steps**:

1. `tests/specify_cli/cli/commands/agent/test_workflow_cores.py`: the `build_owned_files_review_pathspecs` class (~105-140) loses its function. Re-pin each case to `WpReviewRange.owned_pathspecs` as produced by `resolve_wp_review_range` on a small fixture (mission-dir bookkeeping excluded only when the mission dir is owned; no excludes when it is not; empty owned files → unscoped). Update the module docstring (~line 8).
2. `tests/agent/test_workflow_mixed_dependency_review_context.py`: re-pin the expected `base_ref` / command text to the range.
3. `tests/integration/review/test_canonical_review_diff_refs.py`: re-pin the canonical-manifest assertion to the new block (the slug-prefixed manifest must still resolve the right branch and tip).
4. `tests/characterization/test_trio_pure_cores.py`: re-pin any pinned summary or pathspec text.
5. `tests/integration/test_owned_lifecycle_acceptance_review.py::TestFr025RepositoryRootReviewBase` drives site 2 and goes stale here (it asserts the claim commit appears in the output). The file is owned by WP05. Editing this one class is a sanctioned out-of-map edit under the charter's ownership-map leeway: WP07 depends on WP05, so the two never edit the file in parallel. State the one-line rationale in the commit message. Re-pin the cell to the range base (the printed `git log <base>..<tip>` of the repository-root `single_branch` planning-artifact WP), keep its FR-025 intent and docstring reference, and never delete it. Touch no other cell in that file.
6. One commit per file (or one commit with one rationale line per file), e.g. `re-pin: claim..HEAD text replaced by the WP review range (IC-05, DIRECTIVE_041)`.

**Files**: the four owned test files above, plus the transferred cell.

**Validation**: each file green; the diff removes no test function.

---

### Subtask T037: Green, and the validation sweep

**Purpose**: prove red → green on sites 2 and 3 and run the blast radius.

**Steps**:

1. Run `uv run --frozen pytest tests/integration/review/test_review_range_acceptance_action.py tests/integration/review/test_review_range_acceptance.py -q`; iterate on T033-T035 (not on the assertions) until both pass. A genuinely wrong assertion is fixed in a separate commit with the reason.
2. Confirm no new refusal or exit code: `git diff <lane base>..HEAD -- src | rg -n '^\+.*(OwnedRefusalCode|ActionContextError|typer\.Exit\()'` shows no added refusal or exit.
3. Dead-code gates: `test_no_dead_symbols.py` and `test_no_dead_modules.py` green (confirming WP03's and WP04's expected reds stay cleared, and nothing this WP removed left a dead helper).
4. Record each command and its pass/fail counts for the PR:

```bash
make test-fast
uv run --frozen pytest tests/agent/ tests/review/ tests/integration/review/ -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_workflow_cores.py -q   # out-of-matrix, run explicitly
uv run --frozen pytest tests/characterization/test_trio_pure_cores.py tests/integration/test_owned_lifecycle_acceptance_review.py tests/integration/test_owned_lifecycle_acceptance_e2e.py -q
uv run --frozen pytest tests/architectural/test_execution_context_parity.py tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_status_read_single_door.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/review/prompt_metadata.py
make format-check-files FILES="src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/review/prompt_metadata.py"
uv run --frozen mypy --strict src/specify_cli/cli/commands/agent/workflow_executor.py src/specify_cli/cli/commands/agent/workflow_cores.py src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/review/prompt_metadata.py
```

Do **not** run `make test-full` or the whole `tests/architectural/` directory. Classify any red you did not cause with the CLAUDE.md baseline-red gotcha.

---

## Definition of Done

- [ ] C-010 (per work package): T032's test file is the lane's **first** commit, red on the lane base for an assertion reason (red output recorded in the PR).
- [ ] Sites 2 and 3 render from the `WpReviewRange` resolved once per review; the acceptance test proves per fixture exact provenance (`[recorded]`, `window open`), a site-2 block byte-identical to site 1 (SC-003), site-3 lines taken verbatim from that block, `ReviewPromptMetadata.base_ref` = range base (FR-012), printed commands that run through `bash -c`, no patch text and no diff file (C-001), and byte-identical output under two `PYTHONHASHSEED` values.
- [ ] The stamp-stripped lanes cell exits 0 with the `unavailable — <reason>` notice on sites 2 and 3 (FR-013, NFR-004); no new gate, refusal or exit code (C-002); pre-review gate untouched (C-004); `OWNED_REVIEW_BASE_UNAVAILABLE` unchanged per operator ruling Q7.
- [ ] `workflow.py` changed only in the two builder calls; no mission path reconstructed.
- [ ] `build_owned_files_review_pathspecs` is gone; `WpReviewRange.owned_pathspecs` is the only pathspec authority (`rg -n "build_owned_files_review_pathspecs|_review_pathspecs" src tests` is empty).
- [ ] Stale executor-side tests (and the transferred FR-025 cell) re-pinned with one-line rationales; no test function deleted.
- [ ] `test_no_dead_symbols.py` and `test_no_dead_modules.py` green, with no allowlist entry.
- [ ] NFR-006: ruff, ruff format (`--force-exclude`) and `mypy --strict` clean on touched files, no new suppressions, touched functions ≤ 15 complexity; T037 commands pass with counts recorded.
- [ ] No `tracer-*.md` edited from the lane; anything to record goes in the completion note for the orchestrator.
- [ ] Each subtask recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission review-context-wp-diff-01M774QF`.

## Risks

- **Hot files / format ratchet.** `workflow*.py` are large and on the formatter-debt ratchet. Mitigation: minimal diffs, `--force-exclude` checks, no whole-file reformat.
- **Downstream truthiness on `base_branch`.** Code checks `base_branch != "unknown"`. Mitigation: keep `"unknown"` for an unavailable range, and run `test_execution_context_parity.py`.
- **Site 3 drifting from the block.** A hand-written summary line would fork the text. Mitigation: select the lines from the renderer's output; the acceptance test compares them verbatim.
- **Cross-WP test ownership.** The FR-025 cell lives in a WP05-owned file. Mitigation: T036 step 5 waits for the orchestrator's ownership transfer; it is never edited without it and never deleted.
- **Dead helpers.** Removing the base-search arm may leave `review_context_search_unknown_base` / `pick_best_base_branch` unused. Mitigation: `test_no_dead_symbols.py` decides; delete them here if dead.

## Reviewer Guidance

- **Red → green**: the first lane commit contains only `test_review_range_acceptance_action.py` and the PR records its red run.
- **Three sites identical**: run the acceptance test; the site-1 and site-2 blocks compare equal and the site-3 lines are verbatim copies.
- **Metadata**: `ReviewPromptMetadata.base_ref` is the range base in every fixture.
- **No path reconstruction**: the `workflow.py` diff is the two calls only.
- **One pathspec builder**: `rg -n "build_owned_files_review_pathspecs|_review_pathspecs" src tests` is empty.
- **Fail-soft**: the stamp-stripped cell exits 0 with the notice; no new refusal appears in the diff.
- **Re-pins**: each stale test re-pinned, not deleted, with a rationale in the commit message.
