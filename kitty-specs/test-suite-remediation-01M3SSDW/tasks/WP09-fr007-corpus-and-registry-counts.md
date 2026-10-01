---
work_package_id: WP09
title: 'FR-007 class: corpus, data-artefact and agent-registry counts'
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-011
- NFR-003
- NFR-005
- C-001
- C-002
- C-006
- C-007
- SC-004
- SC-005
- NFR-004
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: c1ff52cfd5b5a987d232c5d2c87bfff9fbb20b2b
created_at: '2026-09-30T21:35:57.081391+00:00'
subtasks:
- T040
- T041
- T042
- T043
- T044
phase: Phase 2 - Pin honesty
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/bulk_edit/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py
- tests/docs/test_glossary_linker.py
- tests/unit/convergence/test_census_status.py
- tests/agent/test_agent_config_migration.py
- tests/specify_cli/regression/test_twelve_agent_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – FR-007 class: corpus, data-artefact and agent-registry counts

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

- **FR-007 (pin-inventory groups G6 + G7)**:
  - **F4, CONVERT (shape)**: `len(gov) == 101`, `len(raw) == 20` and the literal file-set pins over the **shipped doctrine corpus**, in `test_governance_occurrences_and_files_match_sc011`.
  - **F5, CONVERT (relational)**: `len(terms) == 103` twice, over the shipped glossary seed. Rename the `_104_` test.
  - **F7, RETIRE + floor**: `len(census_map.clusters) == 74` and `sum(commits) == 800` over the committed `.kittify/convergence-map.json`.
  - **F10, CONVERT (set equality)**: `len(AGENT_DIR_TO_KEY) == 13` and `len(NON_MIGRATED_AGENTS) == 13`. The supported-agent **set** is a product contract; its **count** is derived.
- **NFR-003**: A legitimate addition (a new profile, a glossary term, a census cluster, a consistently registered agent) needs 0 test edits. A violation reds.
- **FR-011 / C-002**: planted-break records; retirements name covering guards.
- **C-006**: F4's docstring calls SC-011 a "cardinality contract". SC-011 is an archived mission's measurement. Correct the claim **here**, in the test, and never edit the archived spec.

## Context & Constraints

- Read first: `plan.md` IC-08; `research.md` rows F4, F5, F7 and F10; `research/pin-inventory.md` §2.3 (plants) and §2.4 (the `2e40057da1` / #3234 precedent: filesystem-derived counts).
- **Format-excluded** (edit without `ruff format`):
  - `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`;
  - `tests/docs/test_glossary_linker.py`;
  - `tests/specify_cli/regression/test_twelve_agent_parity.py`.
- **Not excluded**: `tests/unit/convergence/test_census_status.py`, `tests/agent/test_agent_config_migration.py`.
- `tests/specify_cli/regression/test_twelve_agent_parity.py` is classified `behavioral` in `tests/architectural/shape_guard_membership.yaml`. Keep its test functions' names unless a rename is required; run `tests/architectural/test_shape_guard_membership.py` by name.
- **F10 import source (correction to plan IC-08)**: `specify_cli.upgrade.migrations.m_0_9_1_complete_lane_migration` exposes `AGENT_DIRS` only as a **class attribute** (`CompleteLaneMigration.AGENT_DIRS`, imported from `specify_cli.agent_utils.directories`). The canonical module-level source is `specify_cli.agent_utils.directories.AGENT_DIRS`; import it from there, and do not re-list it.
  - Verified on this base: `set(AGENT_DIR_TO_KEY) == {d for d, _ in AGENT_DIRS}` (13 dirs), and `set(AGENT_DIR_TO_KEY.values()) == set(AGENT_COMMAND_CONFIG)` (13 keys).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`, which `finalize-tasks` writes. Start with:

```bash
spec-kitty agent action implement WP09 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Run the commands in this prompt plus `make test-fast` once. Never run a test directory as a whole, never `make test-full`, and no heavy suites.
2. **Planted breaks never land (C-007).** Plants in `src/`, `packs/`, `.kittify/` or `docs/` are **scratch edits**; revert with `git checkout -- <file>`, or delete the scratch file. Run `git diff --stat src/ packs/ .kittify/` (it must be **empty**) and `git diff --stat` before **every** commit.
   - A plant under `packs/` also trips the pack-manifest regen gate. That is fine for a scratch run, but never commit it.
3. **Planted-break protocol (FR-011)**:
   - For a convert: the neutral plant stays green with 0 test edits (the old form reds on it), and the violation plant reds the new form.
   - For a retire: the covering guard reds. If it stays green, stop (C-002).
4. **Evidence.** Write data-model §4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of `move-task WP09 --to for_review` (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
5. **Skip hygiene (NFR-004).** `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail)|importorskip" <owned files>`. Each hit carries a reason.
6. **Quality (NFR-005).** `uv run --frozen ruff check` on all five files, and `ruff format --check` on the two non-excluded ones. Add no new `noqa`.
7. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
8. **Baseline-red gotcha.** Classify any red you did not cause (CLAUDE.md).
9. **Commit trailers.** End every commit with:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_016Yu85b3RXSx3QzQphAUzpf
   ```
   No CHANGELOG edits. One commit per row is preferred.

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

### Subtask T040 – F4: shape invariants over the bulk-edit inventory

- **Purpose**: `test_governance_occurrences_and_files_match_sc011` (`:441-~620`) pins occurrence counts and literal file sets over the shipped doctrine corpus. `len(gov)` moved 6 times and `len(raw)` 3 times, and the file sets moved alongside. Every new profile or styleguide forces a test edit.
- **Files**: `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py` (format-excluded).
- **Anchors**:
  - `:444-~460`: the docstring claiming SC-011 "cardinality contracts";
  - `:505-510`: `gov_files`, `raw_files` and `migrate_files`;
  - `:511-521`: the count history comment and `assert len(gov) == 101` / `assert len(raw) == 20`;
  - `:525-575`: `assert gov_files == {...}` and the RAW_MATERIAL set;
  - `:576-~590`: `assert gov_files & migrate_files == {...}` (the named overlap).
  - Keep untouched: `test_every_real_governance_field_is_expressible_as_field_path_exception` (`:629`), the per-triple contract.
- **Steps**:
  1. Replace the counts and literal sets with shape invariants:
     - `assert gov and raw` (non-vacuity);
     - every GOVERNANCE path matches `agent_profiles/*.agent.yaml`, via `fnmatch` or `PurePosixPath(...).match(...)`;
     - every RAW_MATERIAL path is under `styleguides/` or `toolguides/`;
     - the overlap: `gov_files & migrate_files` is non-empty, and every member is also an `agent_profiles/*.agent.yaml` path. This keeps the inexpressibility argument's target set non-vacuous without naming its members.
  2. Rename the test to what it now checks, e.g. `test_governance_and_raw_material_occurrences_have_the_sc011_shape`.
  3. Rewrite the docstring. Say that SC-011 is an archived measurement of the corpus at authoring time, **not** a live cardinality contract (C-006: the archived spec is not edited; the claim is corrected here). Delete the count-history comment.
- **Planted breaks**:
  - **Neutral**: add a scratch profile under the built-in pack's `agent_profiles/` with a `directive-references` field (delete it afterwards). The new form is green; the old `len(gov) == 101` reds.
  - **Violation**: make the inventory classify a styleguide path reference as GOVERNANCE. Use a scratch edit of the classifier in the bulk-edit inventory module (`inline_reference_inventory`; find it via the test's imports). The shape check reds.
- **Edge cases**: Do not touch the other tests in the file.

### Subtask T041 – F5: relational glossary anchors; rename the `_104_` test

- **Purpose**: `assert len(terms) == 103` at `:69` and `:101` pins the size of the shipped `GLOSSARY_SEED`. The contract is "no term dropped, and anchors are unique".
- **Files**: `tests/docs/test_glossary_linker.py` (format-excluded).
- **Anchors**:
  - `test_real_glossary_seed_yields_104_unique_anchor_ids` at `:62-71`, which builds `terms = assign_anchor_ids(parse_glossary_seed(GLOSSARY_SEED))`;
  - `test_load_link_terms_from_real_seed` at `:97-102`.
- **Steps**:
  1. First test: `parsed = parse_glossary_seed(GLOSSARY_SEED)`, `terms = assign_anchor_ids(parsed)`, then:
     - `assert parsed`;
     - `assert len(terms) == len(parsed)`: relational, no term dropped;
     - keep the uniqueness assert.

     Rename it to `test_real_glossary_seed_yields_one_unique_anchor_per_term`. Delete the "Re-pinned 104 -> 103" comment.
  2. Second test: assert one `LinkTerm` per seed term that has a surface. Derive the expected count from `parse_glossary_seed(GLOSSARY_SEED)`, filtered on whatever `load_link_terms` requires; read `scripts/docs/glossary_linker.py::load_link_terms`. Keep `all(t.surface and t.anchor_id for t in terms)`. Delete the re-pin comment.
- **Planted breaks**:
  - **Neutral**: add a glossary term to the seed (scratch edit of the `GLOSSARY_SEED` file). Green; the old `== 103` reds.
  - **Violation**: make `assign_anchor_ids` skip a colliding term (scratch edit in `scripts/docs/generate_kitty_specs_docs.py`). The relational check reds.
- **Parallel?**: Yes.

### Subtask T042 – F7: retire the absolute census counts; floor `>= 1`

- **Purpose**: `len(census_map.clusters) == 74` and `sum(len(c.commits)) == 800` (`:31-32`) pin the size of a **growing** committed data artefact (5 + 5 re-pins, all upward).
- **Files**: `tests/unit/convergence/test_census_status.py`.
- **Anchors**: `test_seed_map_has_complete_nonpending_dispositions` at `:27-33`, with the counts at `:31-32` and the PENDING check at `:33`; the covering guard `test_seed_map_census_counts_match_commit_lists` at `:36-40` (per-cluster `census_commit_count == len(commits)`).
- **Steps**:
  1. Delete the two absolute asserts. Add `assert len(census_map.clusters) >= 1` (non-vacuity) and keep the PENDING check.
  2. Consider renaming the test if its name still claims completeness; it can keep its name.
- **Planted breaks**:
  - **Neutral**: append a consistent cluster to a scratch copy of `.kittify/convergence-map.json` (or monkeypatch the path to a scratch copy). Green; the old form reds.
  - **Violation (C-002 covering guard)**: a cluster whose `census_commit_count` disagrees with its list. `:36` reds.
- **Parallel?**: Yes.

### Subtask T043 – F10: cross-registry set equality

- **Purpose**: `len(AGENT_DIR_TO_KEY) == 13` (`tests/agent/test_agent_config_migration.py:238`) and `len(NON_MIGRATED_AGENTS) == 13` (`tests/specify_cli/regression/test_twelve_agent_parity.py:233`) re-pin every time an agent is added or removed (`329e6fae11` 12→13, LLxprt).
- **Watch out for a tautology**: `NON_MIGRATED_AGENTS` is defined in the test file as `tuple(AGENT_COMMAND_CONFIG.keys())` (`:71`). So "`NON_MIGRATED_AGENTS` equals the `AGENT_COMMAND_CONFIG` keys" is **tautological** and guards nothing. Use cross-registry relations instead.
- **Files**: `tests/agent/test_agent_config_migration.py`, `tests/specify_cli/regression/test_twelve_agent_parity.py`.
- **Steps**:
  1. `test_agent_config_migration.py::TestAgentDirMapping::test_agent_dir_to_key_complete` (`:231-245`): replace `assert len(AGENT_DIR_TO_KEY) == 13` with:
     ```python
     from specify_cli.agent_utils.directories import AGENT_DIRS
     assert set(AGENT_DIR_TO_KEY) == {agent_dir for agent_dir, _subdir in AGENT_DIRS}
     ```
     Keep the special-mapping asserts (`:241-247`). Update the comment: the slash-command dirs of the canonical `AGENT_DIRS` are the authority. The test already imports `AGENT_DIR_TO_KEY` from the migration module, which re-exports it; keep that import.
  2. `test_twelve_agent_parity.py:225-233` (the count test): replace the count with a relation between two **independent** registries:
     ```python
     from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY
     assert set(NON_MIGRATED_AGENTS) == set(AGENT_DIR_TO_KEY.values())
     ```
     Every command-file agent has exactly one slash-command directory, and vice versa. Keep the existing codex/skill-agent exclusion tests. Rewrite the docstring to drop the count narrative.
  3. Run both files, plus `tests/architectural/test_shape_guard_membership.py` by name.
- **Planted breaks**:
  - **Violation 1**: add a dir to `AGENT_DIRS` without a key mapping (scratch edit of `src/specify_cli/agent_utils/directories.py`). The first set equality reds.
  - **Violation 2**: add an agent to `AGENT_COMMAND_CONFIG` without a directory mapping (scratch edit of `src/specify_cli/core/config.py`; `AGENT_COMMAND_CONFIG` at `:55`). The second set equality reds.
  - **Neutral**: register a new agent consistently in all three registries (scratch). Green; the old counts red.
- **Parallel?**: Yes (both files).

### Subtask T044 – Plants, counts, evidence

- **Steps**:
  1. The full named-file run (Test Strategy). All green.
  2. One evidence record per row: F4 FIX, F5 FIX, F7 RETIRE + floor (covering guard `:36`), F10 FIX. Also fill the data-model §3 pin-item fields.
  3. `make test-fast` once.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/docs/test_glossary_linker.py tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py tests/specify_cli/regression/test_twelve_agent_parity.py tests/architectural/test_shape_guard_membership.py -n0 -q
uv run --frozen ruff check tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/docs/test_glossary_linker.py tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py tests/specify_cli/regression/test_twelve_agent_parity.py
uv run --frozen ruff format --check tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py
make test-fast
```

## Risks & Mitigations

- **F4 has the largest docstring and the densest set pins.** Change only that test, and keep the per-triple contract test untouched.
- **The F10 tautology.** Use the two cross-registry relations above, never `NON_MIGRATED_AGENTS == AGENT_COMMAND_CONFIG`.
- **Scratch plants under `packs/`** trip the pack-manifest regen gate. Never commit them, and revert immediately.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- Re-run the F10 violation 1: the set equality is RED (quickstart #17).
- The F4 docstring no longer calls SC-011 a live cardinality contract.
- No test in these five files asserts an absolute count of live structure anymore, except the fixture-local behavioural counts noted as LOCAL TEST VALUE in pin-inventory §2.3 (e.g. `test_agent_config_migration.py:70/85/103`).

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
spec-kitty agent tasks mark-status T040 T041 T042 T043 T044 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP09 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
