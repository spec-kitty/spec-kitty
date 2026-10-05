---
work_package_id: WP07
title: 'Track C: recipe-shape classifier and per-pull-request home for the gate'
dependencies: []
requirement_refs:
- FR-013
- FR-014
- FR-015
- FR-016
- NFR-004
- C-011
planning_base_branch: issue-5611-5419-nightly-green
merge_target_branch: issue-5611-5419-nightly-green
branch_strategy: Planning artifacts for this mission were generated on issue-5611-5419-nightly-green. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5611-5419-nightly-green unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-01M44FEP
base_commit: b7142503eb9591f47e743bd92625919781e365bd
created_at: '2026-10-05T05:36:33.351777+00:00'
subtasks:
- T034
- T035
- T036
- T037
- T038
phase: Phase 3 - Track C (commit-recipe gate)
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-05T04:58:23Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_commit_recipe_strings.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/cli/commands/test_commit_recipes.py
- tests/architectural/test_commit_recipe_strings.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP07 – Track C: recipe-shape classifier and per-pull-request home for the gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then read `.kittify/charter/charter.md` (sections "Quality & Tech-Debt Standing Orders" and "ATDD-First Discipline") and run `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission nightly-suites-green-01M44FEP` or the Activity Log below).
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

- The recipe gate flags a string only when it has the shape of a copy-paste commit recipe (FR-013), and passes on the current tree including the repeated `-m` help text (User Story 3, scenario 1).
- Each of the 11 recipes that existed before the renderer conversion is still flagged, proven by fixtures copied verbatim from the tree before commit `3e09226fb4` (FR-014).
- The allowlist holds only entries the classifier still flags; the stale-entry and distinctiveness checks stay enforced (FR-015). The grounding replay expects 2 of the 14 entries to remain.
- The gate runs in a job that pull-request CI selects for a change to any file under `src/specify_cli/`, reached by moving the gate into `tests/architectural/` and not by a workflow or registry edit (FR-016, C-006).
- The moved gate file runs in under 15 s (NFR-004). The scan scope stays `src/specify_cli/` (C-011).

This work package changes test files only. No file under `src/` is edited.

## Context & Constraints

Read first, in this order: `kitty-specs/nightly-suites-green-01M44FEP/spec.md` (User Story 3, FR-013 to FR-016, NFR-004, C-006, C-011), `plan.md` (section "Design notes / Track C"), `research.md` (D6), `research/code-grounding.md` (sections 5 and 9.5).

**The defect (#5708).** The gate flags any string containing the bare substring `git commit`. Commit `22994ca25` added CLI help text that mentions `git commit`, which reds the gate on `main` and with it two nightly jobs (interpreter shard 3 and out-of-matrix). The gate only ran nightly, so the introducing pull request stayed green.

**Operator ruling (2026-10-05): move the gate.** The scanner and allowlist tests move to `tests/architectural/`, following the precedent `tests/architectural/test_completion_manifest_freshness.py` (`pytestmark = [pytest.mark.architectural]` at `:35`). The architectural jobs are selected for every `src/specify_cli` change.

**Do not edit, in addition to the table below:** `src/specify_cli/cli/commands/_commit_message.py` (the help text is correct; the scanner is wrong), `src/specify_cli/cli/commands/_git_remedies.py`, `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`, `src/specify_cli/cli/commands/agent/tasks_move_task*.py`, `src/specify_cli/cli/commands/implement*.py`, `src/specify_cli/core/mission_creation*.py`. Two remaining allowlist entries point at `implement.py` and `core/mission_creation.py`; only the allowlist text refers to them.

**Verified code facts for this work package (base `9adc68803f`).**

- `tests/specify_cli/cli/commands/test_commit_recipes.py` (393 lines): `pytestmark = [pytest.mark.unit, pytest.mark.fast]` (`:42`); `_SRC_ROOT = Path(__file__).resolve().parents[4] / "src" / "specify_cli"` (`:44`); `_NEEDLE = "git commit"` (`:45`); `_MIN_DISTINCTIVE_LEN = 16` (`:46`); `_ALLOWED_GIT_COMMIT_HITS` (`:55`, 14 entries keyed by path and substring); `_is_subprocess_argv_element` (`:168`); `find_git_commit_recipe_hits` (`:189`); `_scan_src_specify_cli` (`:219`); `_allowlist_covers` (`:229`).
- Scanner and allowlist tests, which move: `test_no_unallowed_git_commit_recipe_strings_in_src` (`:234`, red today), `test_allowlist_has_no_stale_entries` (`:249`), `test_allowlist_entries_are_specific_enough_to_be_stable_keys` (`:261`), `test_allowlist_matching_ignores_line_numbers` (`:267`), and the six fixture controls `:278` to `:316`.
- Renderer unit tests, which stay: `:328` to `:370` (`test_safe_commit_recipe_*`, `test_protected_primary_hint_never_suggests_env_bypass`, `test_planning_artifact_recipe_pins_to_branch_on_the_planning_branch`).
- From `tests/architectural/`, the repository root is `parents[2]`, so the anchor becomes `Path(__file__).resolve().parents[2] / "src" / "specify_cli"`.
- Commit `3e09226fb4` introduced the gate (the file does not exist at `3e09226fb4^`); the tree at `3e09226fb4^` holds the unconverted recipes. `git grep -n "git commit" '3e09226fb4^' -- 'src/specify_cli/*.py'` lists 23 files with the substring; the 11 true recipes are among them.
- The current hit: `MESSAGE_OPTION_HELP` at `src/specify_cli/cli/commands/_commit_message.py:13`, consumed as `typer.Option(help=...)`.
- Job selection: `scripts/ci/gate_selection.py` `select_gates` (`:134`), `select_modules` (`:270`).

### Paths owned by running missions (do not edit)

Copied from `research/code-grounding.md` section 6. Paths are relative to `src/specify_cli/` unless they start with `tests/` or are a root file.

| Running mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_wp_integrity_partition_call_shape.py`, `tests/architectural/dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `lanes/compute_and_persist.py`, `lanes/frozen_membership.py`, `lanes/lane_tip.py`, `lanes/models.py`, `cli/commands/agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `lanes/auto_rebase.py`, `lanes/stale_check.py`, `lanes/worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound. Only the body of `_is_bookkeeping` may change, and only in WP03. |
| #3931 | `cli/commands/agent/tasks_move_task*.py`, `cli/commands/_git_remedies.py`, `cli/commands/agent/tasks_parsing_validation.py` |

Also off limits for every work package of this mission: `src/mission_runtime/artifacts.py`, any `.github/workflows/*.yml`, `.github/ci-module-registry.yml`, and `kitty-specs/**`.

**Rule.** An edit outside this work package's `owned_files` needs a one-line rationale in your hand-back. An edit in a path listed above is a STOP: make no such edit, and report to the orchestrator what you found and why the listed path seems to need a change.

### Commit order and commit hygiene (charter C-011, spec C-005)

1. Tidy-first enabler commit(s): behaviour-preserving, with their focused tests.
2. Failing-test commit: the test goes through the pre-existing entry point and is red on this work package's base for the reason named in the subtask. Record the red output (test id plus the failing assertion line) in your hand-back.
3. Fix commit(s): the failing test turns green; new branches are covered by tests in the same commit.

Marker convention (ADR `docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md`, amendment at line 70): `p0_repro(issue=N)` is only for a reproduction of an OPEN P0 that must stay off the per-pull-request path; `regression` is the marker for an issue-pinned guard of a bug that is fixed, and it runs per pull request. Tests added here guard bugs fixed in the same pull request, so they never carry `p0_repro`.

Every commit message ends with the trailer `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No commit message, code comment, docstring or document names an AI tool or a model.

### Quality bar (spec NFR-005)

- Cyclomatic complexity at most 15 per function (`ruff` C901). Extract a helper before a function reaches 16.
- `mypy --strict` clean for every changed source file; no new `# type: ignore`, no new `# noqa`.
- A string literal used three or more times in one module becomes a named module constant.
- Every new branch and helper has a test in the same commit.
- No empty or effect-free `except` block.

### Tracer files

Do not edit anything under `kitty-specs/`, including `kitty-specs/nightly-suites-green-01M44FEP/traces/`. Put tooling friction, approach changes and design choices in your hand-back as three short lists; the orchestrator appends them to the tracer files.

## Branch Strategy

- **Strategy**: lane worktree per computed lane (`lanes.json`); this mission's topology is `lanes`.
- **Planning base branch**: `issue-5611-5419-nightly-green`
- **Merge target branch**: `issue-5611-5419-nightly-green`
- **Dependencies**: none

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Start with `spec-kitty agent action implement WP07 --agent claude --mission nightly-suites-green-01M44FEP`. It allocates or reuses the lane worktree and prints its path; work only there and never reconstruct the path yourself. Do not push, and do not open or merge a pull request: the orchestrator consolidates and the operator merges.

## Subtasks & Detailed Guidance

### Subtask T034 – Tidy-first move, still red

- **Purpose**: Give the gate its per-pull-request home (FR-016) without changing what it checks, as its own commit.
- **Steps**:
  1. Create `tests/architectural/test_commit_recipe_strings.py`. Move verbatim: the module-level scanner pieces (`_NEEDLE`, `_MIN_DISTINCTIVE_LEN`, `_ALLOWED_GIT_COMMIT_HITS`, the AST helper classes, `_is_subprocess_argv_element`, `find_git_commit_recipe_hits`, `_scan_src_specify_cli`, `_allowlist_covers`) and the ten scanner, allowlist and fixture tests (`:234` to `:316`).
  2. Set `pytestmark = [pytest.mark.architectural]` and the anchor `parents[2]`. Add a guard that the anchor resolves to an existing directory with Python files, so a wrong anchor cannot pass as "no hits".
  3. Leave the renderer unit tests in `tests/specify_cli/cli/commands/test_commit_recipes.py` with the imports they need; remove from it everything that moved. Update both module docstrings to say where the other half lives.
  4. Run both files: the moved `test_no_unallowed_git_commit_recipe_strings_in_src` is red with the same single hit as before; everything else is green. Commit this as the tidy-first commit ("move, no behaviour change") and record the red output. This existing failing test is the red-first reproduction for the track.
- **Files**: both owned files.
- **Parallel?**: No.
- **Notes**: Use `git mv`-style history where practical (move the file, then restore the renderer half) so blame survives; say in the commit body which approach you took. Check `tests/architectural/test_battery_partition_proof.py` and `test_gate_selection_authority.py` after the move: the grounding found no duration seed is needed for a new architectural file (10 of 247 files untimed against a 10 percent tolerance), but if a gate asks for a seed or a naming change, stop and report rather than editing a registry or timing file.

### Subtask T035 – Fixtures: 11 historical recipes, one positive per shape, negatives

- **Purpose**: Define the classifier's contract in data before writing it (FR-013, FR-014).
- **Steps**:
  1. Extract the 11 historical recipes verbatim with `git show '3e09226fb4^:<path>'` for each path the grounding replay used; identify them by comparing the `git grep` list at `3e09226fb4^` with the conversions that `3e09226fb4` made (`git show 3e09226fb4 -- src/specify_cli` shows which strings became `safe_commit_recipe(...)` calls). Store each as fixture data in the moved file, with its source path and the fact that it predates `3e09226fb4`. Keep exact whitespace and placeholders.
  2. Add one positive fixture per shape in FR-013: `git commit` followed by a flag (`-m`, `--amend`), a quote, a placeholder (`<message>`, `{msg}`), a `$` expansion, a path, a shell operator (`&&`, `;`, a pipe, a backslash line continuation), the end of a string, the end of a line, the end of a backtick span; `git -C <dir> commit -m ...`; `git -c <key>=<value> commit ...`; a string that also contains `git add` (including the ellipsis form `git add ... && git commit ...` and the flagless imperative form from #3931); an f-string with interpolated parts.
  3. Add negatives: the exact `MESSAGE_OPTION_HELP` text (copy the string into the fixture; do not import it), a log line such as "git commit-tree failed", and prose that mentions `git commit` in passing. Take at least four negatives from the 12 allowlist entries the replay classed as log lines.
  4. Write the parametrised tests against a function `is_recipe_shaped(text: str) -> bool` that does not exist yet (or exists as a stub returning the old substring rule). Commit: positives for the new shapes and all negatives are red under the old rule. Record which are red.
- **Files**: `tests/architectural/test_commit_recipe_strings.py`.
- **Parallel?**: No.
- **Notes**: If you find fewer or more than 11 historical recipes, do not adjust the number to fit: list what you found and report the difference in the hand-back. The fixtures are data inside a test file; the scanner reads `src/specify_cli/` only, so they are never scanned.

### Subtask T036 – The shape classifier

- **Purpose**: FR-013.
- **Steps**:
  1. Implement `is_recipe_shaped(text)`: true when a `git ... commit` command (`git commit`, `git -C <dir> commit`, `git -c <key>=<value> commit`) is followed by a flag, a quote, a placeholder, a `$` expansion, a path, a shell operator (`&&`, `;`, a pipe, a line continuation) or the end of a string, line or backtick span; or when the same string also contains `git add`. False for any other mention.
  2. Wire it into `find_git_commit_recipe_hits` in place of the bare substring test, for string constants and for the joined literal parts of f-strings as today. The docstring exemption and the argv-list exemption (`_is_subprocess_argv_element`) stay as they are.
  3. Keep the implementation readable: named compiled patterns as module constants, one small function per concern, each under complexity 15. `git commit-tree`, `git commit-graph` and similar subcommands are not `git commit`.
  4. All T035 fixtures pass: 11 historical recipes flagged, every positive flagged, every negative clean. `test_no_unallowed_git_commit_recipe_strings_in_src` is now green for the help text.
- **Files**: `tests/architectural/test_commit_recipe_strings.py`.
- **Parallel?**: No.
- **Notes**: The existing control `test_scanner_flags_joined_guidance_list` (`:302`) and `test_scanner_flags_fstring_recipe` (`:316`) must stay green unchanged.

### Subtask T037 – Shrink the allowlist to live hits

- **Purpose**: FR-015.
- **Steps**:
  1. Run `test_allowlist_has_no_stale_entries`: it now lists every allowlist entry the classifier no longer flags. Remove exactly those entries.
  2. For each remaining entry, confirm it is a real recipe-shaped string and that its rationale is still true; the replay expects two (`implement.py`, `core/mission_creation.py`). If the number is not two, report the difference with the entries.
  3. Keep `test_allowlist_has_no_stale_entries`, `test_allowlist_entries_are_specific_enough_to_be_stable_keys` and `test_allowlist_matching_ignores_line_numbers` enforced and unchanged in meaning.
  4. Do not add an entry. If the classifier flags a string in the current tree that is not on the allowlist and is not the help text, it is a real finding: report it; do not allowlist it and do not edit the source file.
- **Files**: `tests/architectural/test_commit_recipe_strings.py`.
- **Parallel?**: No.
- **Notes**: Charter Standing Order 5 treats an allowlist as priced debt. The two remaining entries keep their rationale text; note in the hand-back that they need an owner issue and exit date so the orchestrator can file it.

### Subtask T038 – Proof: selection dry run, planted recipe, timing, gates

- **Purpose**: FR-016 and NFR-004 with evidence.
- **Steps**:
  1. Dry run for three `src/specify_cli` paths and record the output:
     ```bash
     $PY -c "from scripts.ci.gate_selection import select_gates, select_modules
     for p in (['src/specify_cli/cli/commands/_commit_message.py'], ['src/specify_cli/git/commit_helpers.py'], ['src/specify_cli/status/store.py']):
         print(p, select_gates(p).selected_jobs, select_modules(p))"
     ```
     Each must select a job that runs the architectural battery containing the moved file. Name the job and how you confirmed the moved file is in it.
  2. Planted recipe: copy one `src/specify_cli` file to a scratch directory outside the repository, add a recipe-shaped string, and run the scanner function on that source text (or use the fixture controls). Show the gate flags it. Never commit a planted string under `src/`, and never edit a file under `src/`.
  3. Time the moved file: under 15 s on the development machine (`--durations=5`).
  4. Run every command in the Test Strategy section.
  5. Hand-back: commits, counts, dry-run output, planted-recipe output, timing, the allowlist before and after (14 to N), the list of 11 historical recipes with source paths, tracer notes.
- **Files**: none new.
- **Parallel?**: No.

## Test Strategy

### Validation commands

Run from the root of your lane worktree. Use the repository root checkout's environment, never a bare `uv run` (it re-syncs the environment) and never the globally installed `spec-kitty` binary for product behaviour (it is a different build).

```bash
export PY=/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/python
export PYTHONPATH=$(pwd)/src

# behavioural tests (named files only)
$PY -m pytest \
  tests/architectural/test_commit_recipe_strings.py \
  tests/specify_cli/cli/commands/test_commit_recipes.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# architectural and CI gate files this change implicates (named files only)
$PY -m pytest \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_out_of_matrix_evidence.py \
  tests/architectural/test_battery_partition_proof.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_interpreter_shard_coverage.py \
  tests/architectural/test_marker_job_completeness.py \
  tests/architectural/test_no_duplicate_suite_execution.py \
  tests/architectural/test_fast_tier_marker_completeness.py \
  -n 4 --dist loadfile -p no:cacheprovider -q

# lint and format
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff check tests/architectural/test_commit_recipe_strings.py tests/specify_cli/cli/commands/test_commit_recipes.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/ruff format --check --force-exclude tests/architectural/test_commit_recipe_strings.py tests/specify_cli/cli/commands/test_commit_recipes.py
/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.venv/bin/mypy --strict tests/architectural/test_commit_recipe_strings.py
```

**Named files only.** No whole directory, no `make test-fast`, no `make test-full`, no bare `tests/architectural/`. Never more than `-n 4` pytest workers; use `-n0` when you need a readable single failure. If a named file is red on your base commit as well, classify it (pre-existing, environment, stale install) and report it; do not fix it here.

If `mypy --strict` is not applied to test files by the project's configuration, run the project's configured check for tests instead and say which.

### Non-vacuity controls (as test cases)

- FR-013: one positive fixture per shape and the prose, help-text and log-line negatives, in one parametrised set.
- FR-014: the 11 historical recipes, paired in the same fixture set with the FR-013 negatives, so a classifier that flags nothing and one that flags everything both fail.
- FR-015: `test_allowlist_has_no_stale_entries` stays enforced; an allowlist entry added for the help text would be stale-checked and is forbidden by T037 step 4.
- FR-016: the planted recipe turning the moved file red, plus the job-selection dry run.
- The anchor guard of T034 step 2: a wrong `parents[...]` index fails loudly.

## Definition of Done

- The move is its own commit, behaviour unchanged, the existing gate test still red in it.
- Fixtures: 11 historical recipes verbatim, one positive per FR-013 shape, negatives including the help text; committed red before the classifier.
- The classifier makes the gate green on the current tree; the allowlist holds only live hits; no entry was added.
- No file under `src/` changed; no workflow or registry edit.
- Dry run, planted recipe and timing evidence in the hand-back; all Test Strategy commands pass.
- Subtasks T034 to T038 recorded with `spec-kitty agent tasks mark-status`.

## Risks & Mitigations

- **False negatives on unusual shapes.** The co-occurring `git add` rule and the per-shape fixtures cover the known ones (ellipsis, flagless imperative, `git -C`). Add a fixture for any shape you find in the historical tree that the rule misses.
- **The count is not 11, or not 2.** Report; do not bend the fixtures or the allowlist to the expected numbers.
- **Battery or naming gates.** A new architectural file may be asked for a duration seed or a name pattern; that is a stop-and-report, not a registry edit.
- **Marker loss on the renderer half.** The file that stays keeps `unit`/`fast` markers and must still be collected by its current jobs.
- **Regex complexity.** Keep patterns named and small; one catastrophic pattern would breach NFR-004.

## Review Guidance

Reviewer: `reviewer-renata` on the strongest available model, never the implementing agent.

What a lazy implementation looks like here, and how to detect it:

- **An allowlist entry for the help text.** The allowlist must shrink (14 to the live hits) and gain nothing. Diff the dictionary.
- **Rewording the help text or editing `_commit_message.py`.** No file under `src/` may appear in the diff.
- **Exempting `help=` strings.** A rule keyed on where the string is used instead of its shape; a real recipe in help text would then pass. The classifier must take only the text.
- **A classifier fitted to the fixtures.** Ask for one more recipe of your own for each of three shapes and run it; also try `git commit-tree failed` and `after git commit, run ...`.
- **Historical fixtures paraphrased.** Spot-check three of the 11 against `git show '3e09226fb4^:<path>'`.
- **The move mixed with behaviour change.** The first commit must be a pure move with the anchor and marker change.
- **Stale-entry or distinctiveness checks weakened.** Compare the three allowlist tests with the base.
- **A workflow or registry edit to get per-pull-request coverage.** None is allowed.

Run the dry run yourself for one path. Confirm the trailer on every commit and no AI or model identifier.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Append the new entry at the END of this section; never prepend or insert in the middle.
2. Use the format `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>`.
3. The timestamp is the current UTC time (`date -u "+%Y-%m-%dT%H:%M:%SZ"`), never a future one.

The acceptance system reads the LAST entry as the current state, so order matters.

**Initial entry**:

- 2026-10-05T04:58:23Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status, and `spec-kitty agent tasks mark-status <Txxx> --status done` to record a finished subtask.
