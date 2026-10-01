---
work_package_id: WP14
title: Size ratchet rows and top-level-keys floor
dependencies:
- WP12
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-011
- NFR-003
- NFR-005
- C-001
- C-003
- C-007
- C-008
- SC-004
- SC-005
- FR-010
planning_base_branch: issue-5353-test-suite-remediation
merge_target_branch: issue-5353-test-suite-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5353-test-suite-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5353-test-suite-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-test-suite-remediation-01M3SSDW
base_commit: 32c5a434a201fa818daa238b240588c602de1b77
created_at: '2026-09-30T23:18:29.436019+00:00'
subtasks:
- T065
- T066
- T067
- T068
- T069
phase: Phase 3 - Dead-symbol re-key
agent: claude
history:
- at: '2026-09-30T19:32:34Z'
  actor: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/_baselines.yaml
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_ratchet_baselines.py
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Size ratchet rows and top-level-keys floor

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

- **Charter Burn-down (a)**: every mutable architectural allowlist is capped in `_baselines.yaml`. The dead-symbol allowlist has had **no** cap since `01M0A42D` deleted the inert key. This WP adds two `_SIZE_RATCHETS` rows, both in section `test_no_dead_symbols`:
  - `allowlist_entries`, reading `tests.architectural._dead_symbol_allowlist.SYMBOL_ALLOWLIST`;
  - `widened_grandfathered_470`, reading `…WIDENED_SCOPE_GRANDFATHERED_470` (the **RK-6 ruling**: include the second leaf in the same section, so no extra top-level key).

  Both leaves carry `# justification:` comments. Their values come from the **live count at landing**, never from the plan (293 / 91 today).
- **FR-006 #5346-1 / FR-007 F2**: `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 15` (`:618`) becomes a floor equal to the **live section count at landing** (`>= 16` today, with the new `test_no_dead_symbols` section) **in this same WP**, because the new section trips it. A floor of 15 would leave exactly the new cap unprotected: deleting the new rows and leaves together would stay green (F-03). Delete the section changelog comment (`:614-617`). The duplicate `(section, leaf)` check (`:612-613`) and the YAML↔row bijection (`test_every_baseline_leaf_is_enforced_by_a_size_ratchet`) carry the rest.
- **Re-plant** `test_leaf_drift_detects_planted_unenforced_leaf` (`:554-578`). Today it plants `test_no_dead_symbols: {x: 1}` as an **unenforced** section; that section becomes enforced here.
- **FR-008 / SC-004**: record the dispositions of the ratchets this mission **keeps**, with the FR-008 history check: each historical move coincided with a debt change.
- **C-003 / C-008**: nothing is loosened, and no census gate is added. These are ordinary size ratchets.

## Context & Constraints

- Read first: `plan.md` IC-12 and the RK-6 ruling; `research.md` D-13 and the "Pin dispositions" table (the keep rows); `research/pin-inventory.md` §2.1 row 1 and §2.3's "not converted" table; `contracts/dead-symbol-allowlist.md` §2.2.
- **Anchors** in `tests/architectural/test_ratchet_baselines.py`:
  - `_SizeRatchet` at `:139-147`, with the fields `section`, `leaf`, `module` and `attr`;
  - `_SIZE_RATCHETS` at `:150-~370`;
  - `_REQUIRED_TOP_LEVEL_KEYS` at `:371`, derived from the rows;
  - `test_baseline_file_exists_with_required_keys` at `:426`;
  - `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` at `:459`;
  - `test_growing_an_allowlist_above_baseline_fails` at `:495`;
  - `test_leaf_drift_detects_planted_unenforced_leaf` at `:554-578`;
  - `test_lowering_an_enforced_leaf_below_live_fails`, parametrized over **every** row, at `:580-606`;
  - `test_size_ratchet_table_meets_floor` at `:609-618`;
  - `test_yaml_leaves_refuses_a_scalar_section` at `:621`, which uses a synthetic `{"test_no_dead_symbols": 1}` and is unaffected.
- `_baselines.yaml` sections carry a comment header and `# justification:` per leaf (house style, e.g. `test_no_inert_schema_slots` at `:230`).
- Neither file is format-excluded. `_baselines.yaml` is YAML (no ruff).
- The loader module exists since WP11, and the gate reads it since WP12.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5353-test-suite-remediation; completed changes must merge back into issue-5353-test-suite-remediation.
- **Planning base branch**: issue-5353-test-suite-remediation
- **Merge target branch**: issue-5353-test-suite-remediation

Execution worktrees are allocated **per computed lane** from `lanes.json`. This WP depends on WP12 and can run in parallel with WP13. Start with:

```bash
spec-kitty agent action implement WP14 --agent claude --mission test-suite-remediation-01M3SSDW
```

Work only in the workspace path it resolves.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Mission-wide rules for this WP

1. **Named-file test runs only (C-001).** Never run `tests/architectural/` as a directory, never `make test-full`, and no heavy suites. Run `make test-fast` once.
2. **Planted breaks never land (C-007).** Plants in the YAML or allowlist data are scratch edits; revert with `git checkout -- <file>`. Run `git diff --stat src/` (it must be **empty**) and `git diff --stat` before **every** commit.
3. **Evidence.** Write data-model §3/§4 YAML records into a scratchpad file outside the repository, never under `kitty-specs/`. Paste them into the `--note` of the hand-off (the FULL records, never a summary; see additional rule B), and include them verbatim in your final report.
4. **Quality (NFR-005).** `uv run --frozen ruff check` and `ruff format --check` on `test_ratchet_baselines.py`. Add no new `noqa`.
5. **Tracers.** `spec-kitty agent tracer-append --mission test-suite-remediation-01M3SSDW --category design-decisions --entry "..." --actor claude-sonnet-5`.
6. **Commit trailers.** End every commit with:
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

### Subtask T065 – Red-first: the new row trips `:618`; convert it to a floor

- **Purpose**: Show the pin taxing a legitimate addition (NFR-003), then remove the toll.
- **Steps**:
  1. **Neutral plant, before the conversion**: add the `allowlist_entries` row (T066's text) and its leaf, **without** touching `:618`. Run `uv run --frozen pytest tests/architectural/test_ratchet_baselines.py -n0 -q -k test_size_ratchet_table_meets_floor`. It must go **RED** (`16 != 15`). Record it. Do **not** commit this state.
  2. Replace `assert len(_REQUIRED_TOP_LEVEL_KEYS) == 15, sorted(...)` with `assert len(_REQUIRED_TOP_LEVEL_KEYS) >= <live section count with the new section>, sorted(_REQUIRED_TOP_LEVEL_KEYS)`. That is `>= 16` today; print `len(_REQUIRED_TOP_LEVEL_KEYS)` after T066 to confirm.
     - Comment it as a **shrink-only non-vacuity floor** on the gated-section set. A legitimate section retirement tightens it as a deliberate ratchet step (spec Edge Case 4), while a legitimate addition needs 0 edits (NFR-003).
     - Delete the "15 gated test-modules: …" changelog comment (`:614-617`).
  3. Re-run: GREEN with the new row present. Keep `len(_SIZE_RATCHETS) >= 19` (`:611`), which is already a floor.
  4. **Violation plant (F-03)**: delete **both** new rows **and** both new `test_no_dead_symbols` leaves (scratch). `test_size_ratchet_table_meets_floor` must go **RED** (15 < 16). Revert. Record this; it proves the new cap cannot be removed silently.
- **Violations** (scratch, each reverted):
  - duplicate a row → the duplicate `(section, leaf)` check at `:612-613` reds;
  - delete a row whose leaf remains in the YAML → `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` reds;
  - delete a whole YAML section → `test_baseline_file_exists_with_required_keys` reds.

### Subtask T066 – The `allowlist_entries` row and leaf

- **Steps**:
  1. In `_SIZE_RATCHETS`, add, with a comment block explaining Burn-down (a), FR-009 and #5346:
     ```python
     _SizeRatchet(
         "test_no_dead_symbols",
         "allowlist_entries",
         "tests.architectural._dead_symbol_allowlist",
         "SYMBOL_ALLOWLIST",
     ),
     ```
     Hoist `"tests.architectural._dead_symbol_allowlist"` into a module constant, since it is used twice with T067 (the `_NO_DEAD_MODULES_MODULE` precedent at `:147`).
  2. **Read the live count**:
     ```bash
     uv run --frozen python -c "from tests.architectural._dead_symbol_allowlist import SYMBOL_ALLOWLIST; print(len(SYMBOL_ALLOWLIST))"
     ```
     Expect 293 on today's base; use whatever it prints.
  3. In `_baselines.yaml`, add a new section with a comment header naming `tests/architectural/test_no_dead_symbols.py` and the data file `dead_symbol_allowlist.yaml`, and stating that the count lives **only** here, never in the data file:
     ```yaml
     test_no_dead_symbols:
       allowlist_entries: <live>  # justification: first cap (Burn-down (a)) on the (module, name) dead-symbol allowlist introduced by test-suite-remediation-01M3SSDW (#5346); value = live count at landing.
     ```
     Place it consistently with the file's ordering (appending at the end is fine).
  4. Run the file. `test_lowering_an_enforced_leaf_below_live_fails[test_no_dead_symbols.allowlist_entries]` passes, which proves the row reads its own leaf.

### Subtask T067 – The RK-6 `widened_grandfathered_470` row and leaf

- **Purpose**: WP11 moved the widened #470 list into the YAML, where it is also a mutable architectural allowlist (Burn-down (a)). RK-6 ruled to cap it with a second leaf in the **same** section, which needs no new top-level key.
- **Steps**:
  1. Add `_SizeRatchet("test_no_dead_symbols", "widened_grandfathered_470", <the constant>, "WIDENED_SCOPE_GRANDFATHERED_470")`.
  2. Read the live count (`len(WIDENED_SCOPE_GRANDFATHERED_470)`, 91 today) and add the leaf `widened_grandfathered_470: <live>  # justification: RK-6 …` under the same section.
  3. Run the file. The parametrized `test_lowering_…[test_no_dead_symbols.widened_grandfathered_470]` passes. `_REQUIRED_TOP_LEVEL_KEYS` grows by one section only, not two.

### Subtask T068 – Re-plant the planted-leaf test

- **Purpose**: `test_leaf_drift_detects_planted_unenforced_leaf` (`:554-578`) plants `planted["test_no_dead_symbols"] = {"x": 1}` as an **unenforced** section (the FR-005 re-entry guarantee of an earlier mission). With the section now enforced, that plant would **replace** the real section, change the expectations and lose the test's meaning.
- **Steps**:
  1. Change the plant to a section that has **no** enforced row, e.g. `planted["test_never_enforced_section"] = {"x": 1}`, and update the expected unenforced list accordingly (sorted: `["test_layer_rules.planted_leaf", "test_never_enforced_section.x"]`). Keep the "removed enforced leaf is reported missing" half unchanged.
  2. Update the docstring. Drop the "re-added `test_no_dead_symbols` section (FR-005 re-entry guarantee…)" framing; that section is now legitimately enforced. Keep the intent: a section with no enforcing row is reported.
  3. Run the file: green.
- **Planted proof**: remove your new rows but keep their leaves (scratch). `_leaf_drift` reports `test_no_dead_symbols.allowlist_entries` and `…widened_grandfathered_470` as unenforced, so `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` reds.

### Subtask T069 – Violation plants, kept-ratchet dispositions (SC-004 / FR-008), evidence

- **Purpose**: Prove the cap bites, and close SC-004's "every pin has a recorded disposition" for the rows no other WP records.
- **Steps**:
  1. **Growth plant (quickstart Break #23)**: in a scratch copy, append one valid entry for a genuinely dead symbol to `dead_symbol_allowlist.yaml` without raising the leaf. Run `test_ratchet_baselines.py::test_growing_an_allowlist_above_baseline_fails`: it must go **RED**, naming `test_no_dead_symbols.allowlist_entries (SYMBOL_ALLOWLIST)`. Revert. Do the same for the widened leaf.
  2. **Kept-ratchet history check (FR-008)**:
     ```bash
     git log --since=2026-08-01 -p -- tests/architectural/_baselines.yaml
     ```
     For each kept ratchet, confirm that every move coincided with a justified allowlist or debt row:
     - the destructive-op allowlist (`test_mutation_ownership_routing.destructive_op_allowlist`);
     - the inert-slot ceiling (`test_no_inert_schema_slots.baseline_entries`);
     - `category_7_grandfathered_orphans`;
     - `egress_allowlist_files`;
     - the other leaves listed in research.md "Pin dispositions" as keep-ratchet.

     Record one disposition record per kept row: `disposition: keep-ratchet` plus `keep_reason` (data-model §3).
  3. **Other disposition rows** from research.md "Pin dispositions" that no other WP owns. Record each with its reason or commit:
     - **keep-ratchet**: `CHARTER_PATH_LITERAL_FLOOR`, noting the `583db03345` historical lapse; the file is not touched;
     - **keep-ratchet**: `INLINE_META_READ_FLOOR` / `:971`, and `_FR014_DEFERRED_CENSUS_ALLOWLISTS`;
     - **keep-ratchet**: the `>=` / `<=` floors;
     - **not-a-pin**: the LOCAL TEST VALUE rows;
     - **keep-contract**: `test_timing_coverage_invariant.py:386` `== 62`;
     - **resolved**: `ROUTED_LOAD_META_FLOOR` (`dd82bd340b`), the DRG counts (`2e40057da1`) and the destructive-op line re-pins (#5085 / `133755de03`).

     F12b and `test_symbol_key.py` `== 400` are recorded by WP08 and WP13. Reference them; do not duplicate.
     - **FR-010 (withdrawn, DM-01M3SVDP)**: record one disposition line, "withdrawn; no census gate added (C-008, ADR 2026-09-14-1); regrowth of exact-count pins stays a review concern". This WP carries the FR-010 mapping only so that the finalize-tasks coverage check has a home for the withdrawn row. **Do not implement any gate.**
  4. The full named-file run (Test Strategy), then `make test-fast`.
  5. **Evidence records**:
     - **#5346-1 / F2**: FIX (neutral red-first at `:618`, then green; the three violations);
     - **the two cap rows**: FIX / KEEP-ratchet new (the growth plant red; the lowering tests pass);
     - **the planted-leaf re-plant**;
     - **the SC-004 disposition table** from steps 2–3.

## Test Strategy

```bash
uv run --frozen pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_loader.py -n0 -q
uv run --frozen ruff check tests/architectural/test_ratchet_baselines.py
uv run --frozen ruff format --check tests/architectural/test_ratchet_baselines.py
make test-fast
```

## Risks & Mitigations

- **Hand-computing the leaf.** Always print the live count at landing (plan risk).
- **Replacing the real section in the planted-leaf test** by accident. The new synthetic section name must not collide with any real section.
- **A second authority for the count.** The count lives in `_baselines.yaml` only. Grep that the data YAML has no count field.

## Definition of Done (C-011)

- **C-011 (test-only WP; D1 reading, `traces/design-decisions.md`)**: every FIX and RETIRE carries the planted-break red→green proof, red on the planted defect and green on the real code (the break is never committed, C-007). Any sanctioned FR-005 product fix (additional rule A) takes the strict form: a failing-first test commit, red on the planning base, then a separate `fix(...)` commit, green at this WP's final commit.

## Review Guidance

- `:618` is a floor at the live section count (`>= 16`), and its changelog comment is gone. The delete-the-section plant is RED (F-03).
- The two rows exist, and the parametrized lowering test passes for both.
- Re-run Break #23 yourself: growth above the leaf is RED.
- The SC-004 disposition table covers every keep, not-a-pin and resolved row from research.md.

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
spec-kitty agent tasks mark-status T065 T066 T067 T068 T069 --status done --mission test-suite-remediation-01M3SSDW
spec-kitty agent tasks move-task WP14 --to for_review --agent claude --mission test-suite-remediation-01M3SSDW --note "<full evidence records>"
```
