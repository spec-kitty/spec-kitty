---
work_package_id: WP05
title: 'Inert-slot retirement (#3026, #3962)'
dependencies: []
requirement_refs:
- C-001
- C-005
- C-006
- FR-010
- NFR-002
- NFR-003
- NFR-005
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T027
- T028
- T029
- T030
- T031
phase: Phase 2 - Baseline and inert-slot retirement
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-26T17:00:00Z'
  actor: planner-priti
  action: Folded post-tasks squad findings
- at: '2026-09-26T18:00:00Z'
  actor: planner-priti
  action: Analysis remediation (D1, I1-I8, A1, C1, D2)
agent_profile: python-pedro
authoritative_surface: tests/architectural/_inert_slots
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/_inert_slots.py
- tests/architectural/_inert_slots_baseline.yaml
- tests/architectural/test_no_inert_schema_slots.py
- tests/architectural/test_reference_enum_ratchet.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Inert-slot retirement (#3026, #3962)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action doctrine: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
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

Retire the dead inert-slot machinery that #3285 orphaned, per Decision Moment DM-01M3EW4PB6 ("retire dead machinery") and #3962 (the same restore-or-delete call).

Done means all of the following hold:

1. The uncalled symbols in `tests/architectural/_inert_slots.py` are gone: `MAX_UNASSIGNED_ENTRIES`, `MAX_MASKING_SUPPRESSIONS`, `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners`, the whole code-only suppression record (`CODE_ONLY_*`, `CodeOnlySuppression`, `load_code_only_record`, `code_only_drift`, `find_code_only_suppressions`, `code_producer_writes`), `COMPLETED_LANES`, `UNASSIGNED_OWNER`, `ALLOWLIST`, the `MINIMUM_*_BASELINE_ENTRIES_STILL_FOUND` pair, and the `materialize_snapshot` import from `specify_cli.status.reducer`.
2. `_inert_slots_baseline.yaml` holds **36** rows (down from 38). The stale rows `styleguide-references` and `model` (both `src/charter/offering/schemas/agent-profile.schema.yaml`) are gone. No row carries `owner:` or `provisional:`. There is no top-level `mission:` key and no `code_only_suppressions:` section.
3. In `tests/architectural/_baselines.yaml` (a sequenced out-of-map edit, see Context), `test_no_inert_schema_slots.baseline_entries` goes 38 → 36 with a `# justification:`. The leaves `unassigned_entries` and `masking_suppressions` are deleted together with their comment blocks.
4. The kept calibrated floors `MINIMUM_SCHEMA_SLOT_NAMES = 150` and `MINIMUM_MODEL_SLOT_NAMES = 120` are **wired**. The new test `test_live_scan_meets_per_walk_floors` checks them through the real `scanned_slots` walk and has a self-mutation arm.
5. `test_no_inert_schema_slots.py` passes with no "inert-slot baseline shrank" warning. On the planning base that warning names the 2 stale rows.
6. No live test, doc or tooling config still names a retired symbol. The token list is under T031.

## Context & Constraints

- **Mission artefacts**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/` has `spec.md` (FR-010, US2-AS5, C-001, C-005), `plan.md` (rev 2: WP05 row, Charter Check ATDD row, Coordination points), `research.md` §D4 (exact deletions), `data-model.md` ("Baseline leaf"), and `research/postspec-renata.md` ([MEDIUM] FR-010/FR-018(b) and the SC-003 token list).
- **Charter**: `.kittify/charter/charter.md`. The binding rules are: Standing Order #4 (red-first, never retry-to-green), #5 (gate non-vacuity), #6 (canonical sources), and the burn-down policy (shrink-only baselines).
- **Governance applied while authoring this prompt**: profile `planner-priti` (decomposition, sequencing, risk); `charter context --action tasks` (DIRECTIVE_003 decision records, DIRECTIVE_041/043 content anchoring and gate non-vacuity, DIRECTIVE_044 single authority, RECONCILE_CHANGE_SCOPE_TENSIONS, USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY).
- **Precondition (FR-019(b))**: issue **#5117** records the silent `model` suppression that `code_only_drift` detects. Before deleting `code_only_drift`, confirm the #5117 body contains the reproduction: slot `model` @ `src/charter/offering/schemas/agent-profile.schema.yaml`, suppressed by `Field(..., alias="model")` in `agent_profiles/profile.py` and `schema_models.py`. If the body lacks it, add a comment with the detector output you capture in T027. **Do not delete the detector before that record exists.**
- **Invariant honesty** (Renata INFO): the owner "anti-weasel" invariant was already lost when #3285 removed its enforcing tests. This WP formally abandons it and does not claim to preserve it. Say so in the tracer entry.
- **C-001 (no exception for this WP)**: your **first commit** is the failing-first behavioural test `test_load_baseline_rejects_retired_keys` (T027). It is honestly RED on the planning base: the base `load_baseline()` requires `mission:` and `owner:`, accepts `provisional:`, silently ignores `code_only_suppressions:`, and has no unknown-key check at all, so no base error message says `unknown key`. T028+T029 turn it GREEN. The base-side tracer evidence (0 callers, stale-row warning, #5117 reproduction) supports the retirement but is not the red-first test. Never add "symbol is gone" tombstone tests (the class #3285 removed). Only WP09 carries a charter exception (plan Complexity Tracking).
- **C-005**: no `src/` change at all in this WP.
- **Sequenced out-of-map edit**: `tests/architectural/_baselines.yaml` is **owned by WP06**. WP06 depends on WP05, so WP05 edits only the three `test_no_inert_schema_slots` leaves and their comment block (currently `_baselines.yaml` L239-298), in one commit. Touch nothing else in that file. **Do not edit `tests/architectural/test_ratchet_baselines.py`** either: it reads only `baseline_entries` (via `_inert_slots.BASELINE_SLOTS`, L419-424 and L581-586), and WP06 rewrites it.
- **Format-exclude rule**: `test_no_inert_schema_slots.py` (pyproject L1005) and `test_reference_enum_ratchet.py` (L1022) are listed in `[tool.ruff.format].exclude`. Do **not** run `ruff format` on them and do **not** edit `pyproject.toml` (WP13 owns those lines). `_inert_slots.py` is **not** excluded, so it must pass `ruff format --check`. If an edit accidentally makes an excluded file format-clean, `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` goes red. Stop and escalate; do not touch pyproject.
- **Keep the gate name** `test_live_tree_has_no_new_inert_slots` and its failure message. `tests/architectural/test_gate_remedy_presence.py:174` registers that qualname and checks its content-anchored remedy text.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implementers commit in their lane worktree (`spec-kitty implement WP05`). Never push, never merge.

## Subtasks & Detailed Guidance

### Subtask T027 – RED first: `test_load_baseline_rejects_retired_keys`, plus base evidence

- **Purpose**: C-001. The committed gate that detected dead inert-slot machinery was deleted by #3285, but the retirement has one behavioural contract a test can pin: the pruned parser must **reject** the retired keys instead of silently carrying them. That test is RED on base and is this WP's first commit. The base evidence in steps 1-4 supports the retirement and is captured **before** any edit.
- **Steps**:
  0. **Failing-first commit.** Add `test_load_baseline_rejects_retired_keys(tmp_path, where, key)` to `tests/architectural/test_no_inert_schema_slots.py` (keep the file's existing style; it is format-excluded). Parametrize it over four cases: an entry key `owner`, an entry key `provisional`, a top-level key `mission`, and a top-level key `code_only_suppressions`. Each case writes a tmp YAML that is valid for the **pruned** parser (top level `entries:` only; one row with `name`, `declared_at`, `disposition: wire-the-producer`, `note`) plus the one retired key with a legal-looking value, and asserts `pytest.raises(BaselineError, match=rf"unknown key '{key}'")` around `load_baseline(path)`. Import only `BaselineError` and `load_baseline`, which exist on base. Run it: all 4 cases must be RED on base (either nothing is raised, or a different `BaselineError` such as "'owner' must be a non-empty string" is raised, which does not match). Paste the failure text into the Activity Log (#5068) and commit alone: `test(WP05): load_baseline rejects retired inert-slot keys (red-first, C-001)`. This tests behaviour, not a symbol's absence, so it is not a tombstone. Do **not** match on the bare key name: base messages already contain `'owner'` and `'mission'`, which would let a case pass for the wrong reason.
  1. In the lane worktree, before editing anything, capture the **uncalled-symbol evidence**:
     ```bash
     grep -rn -E 'MAX_UNASSIGNED_ENTRIES|MAX_MASKING_SUPPRESSIONS|owner_exists|owner_is_complete|unresolved_by_completed_owners|code_only_drift|find_code_only_suppressions|load_code_only_record|code_producer_writes|CODE_ONLY_SUPPRESSIONS|COMPLETED_LANES|UNASSIGNED_OWNER' \
       --include='*.py' tests src scripts | grep -v '^tests/architectural/_inert_slots.py'
     ```
     Expected on base: **0 hits** (every one is defined in `_inert_slots.py` and called nowhere). Also record that `unassigned_entries` and `masking_suppressions` appear in `_baselines.yaml` (L284, L298) and that no comparison in `test_ratchet_baselines.py` reads them (`grep -n 'unassigned_entries\|masking_suppressions' tests/architectural/test_ratchet_baselines.py`: 0 hits).
  2. Capture the **stale-row evidence**:
     ```bash
     .venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -rw
     ```
     Expected on base: 3 passed, 1 warning, "inert-slot baseline shrank; delete cleared ledger rows: styleguide-references, model".
  3. Capture the **detector output for #5117** before deleting it:
     ```bash
     .venv/bin/python -c "from pathlib import Path; from tests.architectural._inert_slots import find_code_only_suppressions, code_only_drift, CODE_ONLY_SUPPRESSIONS; f=find_code_only_suppressions(Path('.')); print(code_only_drift(f, CODE_ONLY_SUPPRESSIONS))"
     ```
     Paste the output into #5117 if its body lacks the reproduction (see Context).
  4. Record everything, including the formal abandonment of the owner invariant:
     ```bash
     spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z \
       --category design-decisions --actor claude \
       --entry "WP05 base evidence: <failing-first test RED text>; <symbol grep: 0 callers>; <stale rows: styleguide-references, model>; <#5117 reproduction recorded>; owner anti-weasel invariant lost in #3285, formally abandoned here (DM-01M3EW4PB6)."
     ```
- **Files**: `tests/architectural/test_no_inert_schema_slots.py` (step 0 only). The tracer file under `kitty-specs/` is written by the CLI, not by hand.
- **Parallel?**: No. It must precede T028-T030.
- **Notes**: Record the RED failure text verbatim (#5068, "red for the intended reason").

### Subtask T028 – Delete the dead machinery in `_inert_slots.py`

- **Purpose**: Remove every symbol that has no caller, and the `src/` import that exists only for them.
- **Steps**: Delete the following (line anchors are from the planning base; re-locate each by symbol name).
  - `from specify_cli.status.reducer import materialize_snapshot` (L35).
  - `ALLOWLIST` (L71-73) and its only use in `_unproduced` (L348: drop `and slot.name not in ALLOWLIST`). The set is permanently empty, so this is behaviour-neutral. Also delete the `ALLOWLIST` sentences in the comment block above `BASELINE_PATH` (L403-408) that explains `ALLOWLIST` versus the baseline.
  - `find_code_only_suppressions` and `code_producer_writes` (L364-407).
  - `UNASSIGNED_OWNER`, `_MISSION_OWNER_PREFIX`, `_MISSIONS_DIR`, `_EVENT_LOG` (L416-419), and `MAX_UNASSIGNED_ENTRIES` with its comment (L421-431).
  - `COMPLETED_LANES` with its comment (L456-460).
  - `_mission_exists`, `_mission_work_packages`, `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners` (L557-633).
  - The whole code-only section (about L636-753): the section comment, `CODE_ONLY_VERDICTS`, `_GENUINE_PRODUCER`, `MAX_MASKING_SUPPRESSIONS`, `_CODE_ONLY_KEY`, `CodeOnlySuppression`, `_parse_code_only`, `load_code_only_record`, `code_only_drift`, and the `CODE_ONLY_SUPPRESSIONS` module constant.
  - `MINIMUM_SCHEMA_BASELINE_ENTRIES_STILL_FOUND` and `MINIMUM_MODEL_BASELINE_ENTRIES_STILL_FOUND` with their long comment (about L767-791). They are uncalled, and their "every baseline entry must still be found" rule contradicts the warn-on-shrink ratchet the live test implements.
  - The matching `__all__` rows (L37-69). Keep `__all__` sorted and consistent with what survives.
- **Keep**: `InertSlot`, the walk helpers, `scanned_slots`, `find_inert_slots`, `BASELINE_PATH`, `DISPOSITIONS`, `BaselineError`, `BaselineEntry`, `Baseline`, `load_baseline`, `ratchet`, `BASELINE_SLOTS`, `is_schema_declared`, `MINIMUM_SCHEMA_SLOT_NAMES`, `MINIMUM_MODEL_SLOT_NAMES`.
- **Campsite (docstrings only)**:
  - The module docstring says the definition lives in `test_no_inert_schema_slots.py`'s docstring, which is now a 5-line summary. Point it at this module instead.
  - Trim the `MINIMUM_*_SLOT_NAMES` comment (L433-452) so it no longer references the deleted entries-still-found floors. Keep its "floored per walk" rationale.
- **Files**: `tests/architectural/_inert_slots.py` (791 lines on base; expect about −330).
- **Parallel?**: T028 and T029 must land in the **same commit**: removing `owner` from the parser without removing it from the YAML (or the reverse) breaks `load_baseline()` at import time.
- **Validation**: `.venv/bin/ruff check tests/architectural/_inert_slots.py`, `.venv/bin/ruff format --check tests/architectural/_inert_slots.py`, `.venv/bin/mypy tests/architectural/_inert_slots.py`.

### Subtask T029 – Prune the baseline record and its parser

- **Purpose**: The baseline keeps only what the live ratchet reads, which is `name`, `declared_at`, `disposition` and `note`. The two stale rows are removed.
- **Steps**:
  1. In `_inert_slots.py`:
     - drop `BaselineEntry.owner` and `BaselineEntry.provisional`;
     - drop `Baseline.mission`;
     - in `_parse_entry` (L501-522), delete the `provisional` and `owner` handling and the "named owner cannot stay provisional" rule (L509-515);
     - in `load_baseline` (L525-540), delete the `mission` read.
     Keep the `disposition in DISPOSITIONS` validation, the duplicate-slot check and the fail-loud `BaselineError` messages.
  2. Make the parser **reject** the retired keys rather than silently ignoring them, so a copy-paste of an old row cannot reintroduce dead data. The allowed entry keys are exactly `{name, declared_at, disposition, note}`, and an unknown key raises `BaselineError` naming it. The allowed top-level keys are exactly `{entries}`. Keep complexity ≤ 15 by extracting a small `_reject_unknown_keys(raw, allowed, where)` helper that raises `BaselineError(f"{where}: unknown key {key!r}; allowed keys are {sorted(allowed)}")`. That wording is what T027's committed failing-first test matches; after this commit all 4 of its cases are GREEN.
  3. In `_inert_slots_baseline.yaml`:
     - delete the top-level `mission:` (L75) and the comment above it (L73);
     - delete every `owner:` and `provisional:` line (38 rows);
     - delete the rows `styleguide-references` (L271-276) and `model` (L277-282);
     - delete the whole `code_only_suppressions:` section with its preceding comment block (from the `CODE-ONLY SUPPRESSIONS` banner at about L328 to end of file; the data is L376-488).
  4. Rewrite the header prose so it no longer teaches retired rules. Remove the `provisional` paragraph, the `unassigned` cap paragraph (L30-36), and references to the deleted tests `test_baseline_entries_are_well_formed`, `test_every_named_owner_resolves` and `test_the_scan_actually_sees_the_shipped_tree`. Also fix the L70 mention of the `unassigned_entries` counter. Keep the dispositions vocabulary, the known under-count note and the burn-down history.
- **Files**: `tests/architectural/_inert_slots.py`, `tests/architectural/_inert_slots_baseline.yaml`.
- **Validation**: `python -c "from tests.architectural._inert_slots import load_baseline; print(len(load_baseline().entries))"` prints `36`. `.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -W error::UserWarning` passes (the shrink warning is a `UserWarning`, so this makes "no shrink warning" mechanical).

### Subtask T030 – Sequenced `_baselines.yaml` edit and sibling prose

- **Purpose**: Shrink the registered size to the live 36 and remove the two leaves that no comparison reads. This is the out-of-map edit sequenced before WP06 (see Context).
- **Steps**:
  1. In `tests/architectural/_baselines.yaml`, under `test_no_inert_schema_slots:`:
     - set `baseline_entries: 36` with a `# justification:` naming this mission, the 2 stale `agent-profile.schema.yaml` rows (`styleguide-references`, `model`) and #3026/#3962;
     - delete `unassigned_entries: 9` and its comment (L279-284);
     - delete `masking_suppressions: 13` and its comment (L285-298).
  2. Condense the section's preceding comment block (L239-276). Keep the gate description and the dated shrink history, but fix the stale L265 sentence ("so `unassigned_entries` stays at 19") and the L275 mention of `MAX_UNASSIGNED_ENTRIES`. Do not leave any sentence that names a retired leaf or symbol.
  3. Touch **nothing else** in `_baselines.yaml`. The other 20 leaves belong to WP06.
  4. In `tests/architectural/test_reference_enum_ratchet.py`, rewrite the `BASELINE_MEMBER_SLOTS` comment at L191-192 ("the same reasoning that registered `test_no_inert_schema_slots.unassigned_entries`"). Keep the Burn-down Policy (a) rationale and drop the retired example. This file is format-excluded: edit the comment only and do not reformat.
- **Files**: `tests/architectural/_baselines.yaml` (sequenced, WP06-owned), `tests/architectural/test_reference_enum_ratchet.py`.
- **Validation**: `.venv/bin/python -m pytest tests/architectural/test_ratchet_baselines.py -q` stays green. The growth arm now compares 36 ≤ 36. The unregistered-top-level-key arm is unaffected, because the section key remains.
- **Note**: after this commit, `_baselines.yaml` has 21 leaves. WP06's red-first leaf test then names exactly the 2 remaining non-enforcing leaves (`category_1_auto_discovered_migrations`, `skip_marker_blocks`).

### Subtask T031 – Wire the per-walk floors, then validate and record

- **Purpose**: Replace the weak `assert found` (`test_no_inert_schema_slots.py:64`) with the calibrated per-walk floors the module already declares. That gives charter §5 non-vacuity through the real scan function (NFR-002 pattern) at no new-machinery cost.
- **Steps**:
  1. In `test_no_inert_schema_slots.py`, add a pure helper `_walk_floor_shortfalls(slots: set[InertSlot]) -> list[str]`. It counts **distinct names** per walk using `is_schema_declared` and returns one message per walk below `MINIMUM_SCHEMA_SLOT_NAMES` / `MINIMUM_MODEL_SLOT_NAMES`, naming the walk, the floor and the live count.
  2. Add `test_live_scan_meets_per_walk_floors`, which asserts `_walk_floor_shortfalls(scanned_slots(_REPO_ROOT)) == []`. Live on base: 176 schema names ≥ 150 and 138 model names ≥ 120.
  3. Add the self-mutation `test_walk_floors_fail_on_a_collapsed_walk(tmp_path)`. It plants only a schema via the existing `_plant` helper, runs the **real** `scanned_slots(tmp_path)`, and asserts that the helper reports shortfalls for **both** walks: the planted schema walk falls below 150 and the model walk is empty. This proves each floor is load-bearing.
  4. In `test_live_tree_has_no_new_inert_slots`, replace `assert found, ...` with the floor helper over `scanned_slots(_REPO_ROOT)`, or leave `assert found` and rely on the new test. Either way, keep the qualname and the failure-message remedy text unchanged (`test_gate_remedy_presence.py:174`).
  5. Run the retired-token search. It must return 0 live hits (live = excluding `kitty-specs/**`, `docs/reports/**`, `docs/archive/**`, `CHANGELOG.md`):
     ```bash
     grep -rn -E 'MAX_UNASSIGNED_ENTRIES|MAX_MASKING_SUPPRESSIONS|owner_exists|owner_is_complete|unresolved_by_completed_owners|find_code_only_suppressions|code_only_drift|load_code_only_record|code_producer_writes|CODE_ONLY_SUPPRESSIONS|BASELINE_ENTRIES_STILL_FOUND|unassigned_entries|masking_suppressions|UNASSIGNED_OWNER|COMPLETED_LANES' \
       --include='*.py' --include='*.md' --include='*.yaml' --include='*.toml' . \
       | grep -v -E '^\./(kitty-specs|docs/reports|docs/archive|\.worktrees)/|CHANGELOG'
     ```
     `MINIMUM_SCHEMA_SLOT_NAMES` and `MINIMUM_MODEL_SLOT_NAMES` intentionally survive, because they are now wired.
  6. Behavioural check (Renata MEDIUM): every remaining public top-level function in `_inert_slots.py` has at least one importer outside the module. Verify it with a grep per `__all__` name and record the result.
  7. Append the green-side evidence with `spec-kitty agent tracer-append ...`: token search 0, baseline 36, no shrink warning (`-W error::UserWarning` run green), floors wired.
  8. **Issue matrix (last step)**: #3026 and #3962 are seeded `in-mission` against WP05. WP05 alone fixes both: the DM-01M3EW4PB6 resolution is the retirement of the dead machinery, and #3962 asks for the same restore-or-delete call. WP06's leaf refusal (FR-011) hardens the defect class but is not needed to close either issue. Once your last commit lands, run for each issue:
     ```bash
     spec-kitty agent issue-verdict --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --issue "#3026" --verdict fixed --actor <you> --wp WP05 --evidence-ref "dead inert-slot caps/predicates/code-only record retired (DM-01M3EW4PB6), baseline 38->36; commit <sha>"
     spec-kitty agent issue-verdict --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --issue "#3962" --verdict fixed --actor <you> --wp WP05 --evidence-ref "same deletion as #3026; commit <sha>"
     ```
     If the reviewer rejects the WP, correct the evidence SHA after rework.
- **Files**: `tests/architectural/test_no_inert_schema_slots.py` (format-excluded: do not reformat the file; keep new code in the file's existing style).
- **Parallel?**: No. It is last.

## Test Strategy

Tests are required. Run each command and record the exact command lines and passed/failed counts in the Activity Log and, later, the PR's *Tests run* section.

```bash
# Owning gate + survivors (the -W run makes "no shrink warning" mechanical)
.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -rw
.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -W error::UserWarning
.venv/bin/python -m pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_reference_enum_ratchet.py \
  tests/architectural/test_gate_remedy_presence.py tests/architectural/test_ruff_format_exclude_ratchet.py -q
# _baselines.yaml is a cross-cutting ratchet artefact -> full architectural sweep
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
# Quality gates (NFR-005)
.venv/bin/ruff check tests/architectural/_inert_slots.py tests/architectural/test_no_inert_schema_slots.py tests/architectural/test_reference_enum_ratchet.py
.venv/bin/ruff format --check tests/architectural/_inert_slots.py
.venv/bin/mypy tests/architectural/_inert_slots.py tests/architectural/test_no_inert_schema_slots.py
```

- **Pre-existing failure rule**: if a test is red on your lane, run the same test on the planning base (`git stash` or a clean checkout, `PYTHONPATH=<worktree>/src`). If it is red there too, classify it (CLAUDE.md "baseline-red gotcha"), file a GitHub issue if it is pre-existing and untracked, note it in the Activity Log, and continue. Never retry-to-green.
- **Complexity**: keep every touched function at C901 ≤ 15. Add zero new `# noqa` or `# type: ignore`.
- **Campsite (FR-020)**: clean #2972 Sonar findings (e.g. S5778/S5779/S8997) only in the test files this WP already edits. Record each before/after pair in the PR. Zero is acceptable. `scripts/ci/sonarcloud_branch_review.sh` reads the current findings.

## Risks & Mitigations

- **Import-time breakage**: `BASELINE_SLOTS = load_baseline().slots` runs at import. A parser/YAML mismatch breaks every importer, including `test_ratchet_baselines.py`. Mitigation: land T028+T029 atomically and run the import check in the T029 validation.
- **Losing the only `model` detector**: this is mitigated by the #5117 precondition in T027. Do not skip it.
- **Excluded file becomes format-clean**: escalate. Never edit `pyproject.toml` in this WP.
- **WP06 collision on `_baselines.yaml`**: edit only the `test_no_inert_schema_slots` block. WP06 depends on WP05, so it rebases onto your version.
- **Over-deletion**: `DISPOSITIONS` and the disposition validation stay, because the dispositions are still the record's meaning. `is_schema_declared` stays, because the new floor test uses it.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`, tailored to FR-010):

1. **Retirement is real, not a rename.** Run the T031 token search yourself and expect 0 live hits. Also confirm that no retired function body survives under a new name: every public function left in `_inert_slots.py` has an importer outside the module (Renata MEDIUM, SC-003).
2. **Red-first is a real test.** The first lane commit adds only `test_load_baseline_rejects_retired_keys`, and it is RED on base for all 4 cases; the T028+T029 commit turns it GREEN. The tracer also has the base-side grep (0 callers), the base-side shrink warning naming exactly `styleguide-references, model`, and the #5117 reproduction. Do not trust tracer timestamps for ordering: re-run the RED yourself on the base (see "Reviewer RED reproduction" below).
3. **No tombstone tests.** There is no test whose only assertion is "symbol X is absent" or "file Y does not exist".
4. **Floors are non-vacuous through the real scan.** `test_walk_floors_fail_on_a_collapsed_walk` calls `scanned_slots` on a planted tree and fails both walks. It does not feed a synthetic list to a reimplemented counter.
5. **Shrink-only.** `baseline_entries` went 38 → 36 with a `# justification:`. No other `_baselines.yaml` leaf changed. `git diff <base> -- tests/architectural/_baselines.yaml` touches only the `test_no_inert_schema_slots` block.
6. **Parser rejects retired keys.** The committed `test_load_baseline_rejects_retired_keys` covers `owner:`, `provisional:`, top-level `mission:` and top-level `code_only_suppressions:`, each raising `BaselineError` with `unknown key '<key>'`.
7. **Gate remedy intact.** `test_gate_remedy_presence.py` is green, and `test_live_tree_has_no_new_inert_slots` keeps its name and remedy text.
8. The implementer ran `mypy` and `ruff format --check` on `_inert_slots.py`, and the diagnostics were clean.
9. The issue-matrix rows #3026 and #3962 read `fixed` with a commit SHA in the evidence.

**Reviewer RED reproduction** (the RED is the first lane commit's test, run against the planning base; the base-side evidence is re-run alongside):

```bash
git worktree add /tmp/wp05-base 3717c7ea && cd /tmp/wp05-base
git show <first-lane-commit>:tests/architectural/test_no_inert_schema_slots.py > tests/architectural/test_no_inert_schema_slots.py
PYTHONPATH=$PWD/src <main-checkout>/.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -k rejects_retired_keys   # expect 4 failed
grep -rn -E 'MAX_UNASSIGNED_ENTRIES|MAX_MASKING_SUPPRESSIONS|owner_exists|owner_is_complete|unresolved_by_completed_owners|code_only_drift|find_code_only_suppressions|load_code_only_record|code_producer_writes|CODE_ONLY_SUPPRESSIONS|COMPLETED_LANES|UNASSIGNED_OWNER' --include='*.py' tests src scripts | grep -v '^tests/architectural/_inert_slots.py'   # expect 0 hits
PYTHONPATH=$PWD/src <main-checkout>/.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py -q -rw   # expect the shrink warning naming styleguide-references, model
cd - && git worktree remove --force /tmp/wp05-base   # --force: the test file was overwritten
```

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-010, NFR-002 (per-walk floors + self-mutation), NFR-003 (baseline 38 → 36, per-site total shrinks), NFR-005, NFR-006 (abandoned invariant recorded), C-001 (failing-first retired-key test, no exception), C-005, C-006; contributes to SC-003 and SC-004 (2 unread leaves removed), SC-006 (#3026/#3962 rows).

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

**Initial entry**:

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
