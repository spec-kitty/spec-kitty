---
work_package_id: WP06
title: Baseline leaf enforcement
dependencies:
- WP05
requirement_refs:
- FR-011
- NFR-003
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T032
- T033
- T034
- T035
- T036
- T037
phase: Phase 2 - Baseline and inert-slot retirement
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_ratchet_baselines.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_ratchet_baselines.py
- tests/architectural/_baselines.yaml
- tests/contract/test_example_round_trip.py
- docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Baseline leaf enforcement

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

Make the charter ratchet refuse any `_baselines.yaml` leaf that no comparison enforces (FR-011, the #3026 defect class). Derive "enforced" from **one** hoisted comparison table, not from a name search or a hand registry.

Done means all of the following hold:

1. `tests/architectural/test_ratchet_baselines.py` has **one** module-level table, `_SIZE_RATCHETS: tuple[_SizeRatchet, ...]`, with 19 rows: the 6 `test_no_dead_modules` categories 2..7 and 13 single ratchets. Both the growth arm (`test_growing_an_allowlist_above_baseline_fails`) and the shrink arm (`test_growth_fails_shrinkage_warns`) iterate it. The two duplicated local tables (`per_category_attrs` and `single_baselines`, each defined twice) are gone.
2. `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` asserts `_yaml_leaves(data) == _enforced_leaves()` in both directions and names the unenforced and missing leaves. It went RED first, naming exactly `test_no_dead_modules.category_1_auto_discovered_migrations` and `test_example_round_trip.skip_marker_blocks` on this lane's base (after WP05). Against the planning-base YAML it names those two plus `test_no_inert_schema_slots.unassigned_entries` and `test_no_inert_schema_slots.masking_suppressions`.
3. The hand-kept key lists are **derived** from `_SIZE_RATCHETS`:
   - `_REQUIRED_TOP_LEVEL_KEYS` (the 12 sections);
   - `_REQUIRED_NO_DEAD_MODULES_CATEGORIES`.

   `_GRANDFATHERED_UNREGISTERED_KEYS` is retired, and the top-level unregistered-key check is subsumed by the leaf test.
4. The `category_1` and `skip_marker_blocks` leaves are **removed** (D-OP-2), together with their derived/advisory machinery and the tests that pinned that machinery. Each retirement names its surviving enforcer (NFR-006).
5. `test_lowering_an_enforced_leaf_below_live_fails` is parametrized over `_SIZE_RATCHETS` (19 ids, with a floor of `len(_SIZE_RATCHETS) >= 19`). It proves that every row reads *its own* leaf: setting that leaf to `live - 1` makes the real growth arm fail and name the row's `attr`.
6. `test_leaf_drift_detects_planted_unenforced_leaf` proves `_leaf_drift` catches a planted extra leaf (self-mutation through the same pure helper the production test uses).
7. `_baselines.yaml` ends with **19 leaves in 12 sections**, and no leaf value increases (NFR-003 shrink-only).

## Context & Constraints

- **Mission artefacts**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/`. Read:
  - `spec.md`: FR-011, US2-AS3/AS4, SC-004, NFR-003, NFR-006;
  - `plan.md` rev 2: the WP06 row, D-OP-2, the Coordination points, and the `_baselines.yaml` owner WP06 (WP05 edits its three inert leaves first);
  - `research.md` §D1-D3;
  - `data-model.md`: "Baseline leaf";
  - `research/postspec-renata.md`: [CRITICAL] FR-011, which lists three fakes to avoid;
  - `research/postplan-paula.md`: [MEDIUM] "the hoist removes 2 of 5 hand registries";
  - `research/postplan-debbie.md`: [LOW] live-0 leaves.
- **Charter**: `.kittify/charter/charter.md`. The binding rules are Standing Orders #4 (red-first) and #5 (gate non-vacuity), the burn-down policy (shrink-only), DIRECTIVE_044 (single canonical authority: one table, not two lists plus registries), and the `delete-the-assertion-not-the-test` tactic.
- **Governance applied while authoring this prompt**: profile `planner-priti`; `charter context --action tasks` (DIRECTIVE_003, 041, 043, 044, USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY, RECONCILE_CHANGE_SCOPE_TENSIONS).
- **Dependency**: WP05 must be merged into this lane's base first. After WP05, `_baselines.yaml` has 21 leaves, `baseline_entries: 36`, and no `unassigned_entries` or `masking_suppressions`. Do **not** reintroduce or edit the `test_no_inert_schema_slots` block beyond what is needed here (nothing is needed).
- **The three fakes this design must avoid** (Renata CRITICAL):
  - (a) "read" means "the key name occurs in a test file". This is green on base because `test_reference_enum_ratchet.py:192` and `_inert_slots.py` mention the names.
  - (b) A hand registry of allowed nested keys, which you satisfy by listing the dead keys.
  - (c) A test that merely loads the value.

  Enforcement must be **by construction**: a leaf is enforced iff it has a `_SIZE_RATCHETS` row, and every row is compared by the growth arm with a failing `>`. The lowering-mutation test then proves each row really reads its leaf.
- **Coupling with WP04 (census)**: the `destructive_op_allowlist` row reads `len(test_mutation_ownership_routing._ALLOWLIST)` (live 56). WP04 keeps `_ALLOWLIST` a sized mapping of 56 entries. Do not edit the census module. The post-consolidation integration run includes this file (#1979 class).
- **C-005**: no `src/` edits.
- **Format-exclude rule**: `test_ratchet_baselines.py` (pyproject L1018) and `tests/contract/test_example_round_trip.py` (L1278) are format-excluded. Do **not** run `ruff format` on them and do **not** edit `pyproject.toml` (WP13 owns those lines). WP01's ban file is on the adjacent pyproject line L1019, so never touching pyproject avoids that conflict. New code must still be tidy and `ruff check`-clean. If an edit makes an excluded file format-clean, `test_every_exclude_entry_still_genuinely_reformats` goes red: stop and escalate.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implementers commit in their lane worktree (`spec-kitty implement WP06`). Never push, never merge.

## Subtasks & Detailed Guidance

### Subtask T032 – RED first: hoisted table, pure leaf helpers, leaf-enforcement test

- **Purpose**: Land the acceptance test failing for the intended reason, before any behaviour change (C-001).
- **Steps**:
  1. Add a frozen dataclass `_SizeRatchet(section: str, leaf: str, module: str, attr: str)` and the module-level table `_SIZE_RATCHETS`. It has exactly the 19 rows the arms enforce today:
     - the 6 categories `category_2_build_schema_generators` .. `category_7_grandfathered_orphans`, with module `tests.architectural.test_no_dead_modules` and attrs `_CATEGORY_2_BUILD_SCHEMA_GENERATORS` .. `_CATEGORY_7_GRANDFATHERED_ORPHANS`;
     - the 13 rows of today's `single_baselines` (L365-469): `test_layer_rules` ×2, `test_runtime_charter_doctrine_boundary`, `test_doctrine_census`, `test_migration_chain_integrity`, `test_auth_transport_singleton`, `test_example_round_trip.legacy_contract_allowlist`, `test_no_inert_schema_slots.baseline_entries`, `test_reference_enum_ratchet`, `test_egress_consent_boundary` ×2, `test_cli_error_surface_seam`, `test_mutation_ownership_routing`.

     Copy the per-row explanatory comments from the arms into the table.

     `category_1` is **not** a row: it is derived, and its growth arm is a no-op. `skip_marker_blocks` is **not** a row: it is advisory.
  2. Add the pure helpers:
     - `_enforced_leaves() -> frozenset[tuple[str, str]]`, which is `{(r.section, r.leaf) for r in _SIZE_RATCHETS}`;
     - `_yaml_leaves(data) -> frozenset[tuple[str, str]]`, which also raises (or reports) when a top-level value is not a mapping;
     - `_leaf_drift(data) -> tuple[list[str], list[str]]`, returning `(unenforced, missing)` as sorted `"section.leaf"` strings.
  3. Add `test_every_baseline_leaf_is_enforced_by_a_size_ratchet`. It asserts `_leaf_drift(_load_baselines()) == ([], [])` with a message that names each unenforced leaf ("no comparison fails when the live size exceeds it: make it enforcing by adding a `_SIZE_RATCHETS` row, or delete it") and each missing leaf.
  4. **Do not** rewire the arms yet. The table is consumed only by the new test in this commit.
  5. Show RED:
     - `pytest tests/architectural/test_ratchet_baselines.py::test_every_baseline_leaf_is_enforced_by_a_size_ratchet -q` fails, naming exactly `test_no_dead_modules.category_1_auto_discovered_migrations` and `test_example_round_trip.skip_marker_blocks`, with missing = [].
     - Planning-base proof:
       ```bash
       git show <planning-base-sha>:tests/architectural/_baselines.yaml > /tmp/wp06_base_baselines.yaml
       .venv/bin/python -c "import yaml; from tests.architectural.test_ratchet_baselines import _leaf_drift; print(_leaf_drift(yaml.safe_load(open('/tmp/wp06_base_baselines.yaml'))))"
       ```
       It names 4 leaves (the two above plus `test_no_inert_schema_slots.unassigned_entries` and `.masking_suppressions`).
  6. Commit this alone ("test(WP06): RED ..."). Record both RED outputs verbatim with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category design-decisions --actor claude --entry "..."`.
- **Files**: `tests/architectural/test_ratchet_baselines.py`.
- **Notes**: Keep `_import_module_attr` as the single lookup. Do not import `tests.contract.test_example_round_trip` at module scope, because `test_fast_collection_does_not_import_round_trip_corpus` guards that. Store dotted module paths in the table, never module objects.

### Subtask T033 – Rewire both comparison arms onto `_SIZE_RATCHETS`

- **Purpose**: One comparison table, iterated by both arms. This removes the "register in BOTH lists" drift hazard called out in the old docstrings (L668, L680, L688).
- **Steps**:
  1. In `test_growing_an_allowlist_above_baseline_fails` (L328-486), replace the per-category loop and the local `single_baselines` list with one loop over `_SIZE_RATCHETS`:
     - `baseline = data[r.section][r.leaf]`;
     - `current = len(_import_module_attr(r.module, r.attr))`;
     - `current > baseline` appends a failure line.

     Keep the failure-line text shape, and make sure it names both `r.section.r.leaf` and `r.attr`: existing tests match on the attr name (e.g. `match="_LEGACY_CONTRACT_ALLOWLIST"`) and on the category key (`match="category_6_frozen_runtime_reexports"`).
  2. Do the same in `test_growth_fails_shrinkage_warns` (L489-651) with `current < baseline` routed to `record_property`. Keep the "never fails on shrinkage" contract.
  3. Extract a shared pure helper `_size_comparisons(data) -> list[tuple[_SizeRatchet, int, int]]` returning `(row, baseline, current)`, used by both arms. Each arm then only filters and formats. This keeps both test functions far below complexity 15.
  4. `category_1` drops out of both arms here. Its growth check was already a no-op because it is derived. `_category_baseline` becomes dead: leave its deletion to T035 so this commit stays a pure rewire.
  5. Every pre-existing arm test must stay green unchanged:
     - `test_non_derived_category_growth_still_reds`
     - `test_non_derived_category_shrink_still_records`
     - `test_runtime_ledger_growth_with_live_import_still_fails`
     - `test_runtime_ledger_shrink_is_reported`
     - `test_doctrine_pair_allowlist_growth_fails_and_shrink_is_reported`
     - `test_legacy_contract_allowlist_growth_still_fails`

     They are the behavioural proof that the rewire preserved both arms.
- **Files**: `tests/architectural/test_ratchet_baselines.py`.
- **Validation**: `pytest tests/architectural/test_ratchet_baselines.py -q`. Only the T032 leaf test is still red.

### Subtask T034 – Derive the hand-kept key lists and retire the grandfather set

- **Purpose**: DIRECTIVE_044. Without this, three registries (`_REQUIRED_TOP_LEVEL_KEYS`, `_REQUIRED_NO_DEAD_MODULES_CATEGORIES`, `_GRANDFATHERED_UNREGISTERED_KEYS`) remain a second authority for "what keys may exist" (Paula MEDIUM).
- **Steps**:
  1. `_REQUIRED_TOP_LEVEL_KEYS = frozenset(r.section for r in _SIZE_RATCHETS)`. This must still equal the 12 sections at L125-140. Assert that equality once in the T037 floor test, not as a module-level assert.
  2. `_REQUIRED_NO_DEAD_MODULES_CATEGORIES = frozenset(r.leaf for r in _SIZE_RATCHETS if r.section == "test_no_dead_modules")`. After T035 removes `category_1`, that is 6 categories.
  3. Retire `_GRANDFATHERED_UNREGISTERED_KEYS` (L142-151). Fold `test_no_unregistered_baseline_keys_are_added` (L654-690) into the leaf test: an unregistered top-level key produces unenforced leaves, which is strictly stronger (leaf granularity). Before removing the old test name, grep `tests/ docs/ .kittify/` for references. Earlier probes found none, but keep the name as a thin delegating test if any live reference exists.
  4. Replace `test_readding_inert_dead_symbols_key_is_now_rejected` (L693-709) with an arm of T037's planted-leaf test that re-adds `test_no_dead_symbols: {x: 1}` and asserts `_leaf_drift` names `test_no_dead_symbols.x`. This keeps the FR-005 re-entry guarantee, now at leaf granularity (`delete-the-assertion-not-the-test`: the scenario survives, only the mechanism changes).
  5. `test_baseline_file_exists_with_required_keys` keeps working off the derived sets. Update its docstrings and messages so they no longer tell authors to "register in BOTH lists". The instruction is now "add one `_SIZE_RATCHETS` row".
- **Files**: `tests/architectural/test_ratchet_baselines.py`.
- **NFR-006 record**: for each retired test, name the survivor (`test_every_baseline_leaf_is_enforced_by_a_size_ratchet`, `test_leaf_drift_detects_planted_unenforced_leaf`) in the tracer entry.

### Subtask T035 – Remove the `category_1` leaf and its derived machinery (D-OP-2)

- **Purpose**: `category_1` is not a size ceiling. Its growth arm is a no-op, and `test_decorative_category_1_yaml_matches_frozenset` pins YAML == `len(frozenset)` by equality, so every new auto-discovered migration still reds the suite. The "toll drain" of `frozen-baseline-toll-reduction` never actually removed the toll (research §D1).
- **Steps**:
  1. `_baselines.yaml`: delete `category_1_auto_discovered_migrations: 106` (L43) and its justification comment block (L31-42).
  2. `test_ratchet_baselines.py`: delete
     - `_CATEGORY_1_YAML_KEY` and `_CATEGORY_1_ATTR` with their comment (L170-181);
     - `_category_baseline` (L190-202);
     - `test_decorative_category_1_yaml_matches_frozenset` (L712-725);
     - `test_category_1_derived_baseline_absorbs_growth` (L734-748);
     - `test_category_1_derived_baseline_absorbs_shrink` (L751-768).

     Keep `_synthetic_frozenset`, which T037 and the kept tests use.
  3. Update the docstrings of `test_non_derived_category_growth_still_reds` and `test_non_derived_category_shrink_still_records` so they no longer say "only category_1 was made count-independent". Their assertions stay.
  4. **NFR-006 survivor + mutation proof**: `tests/architectural/test_no_dead_modules.py::test_no_new_dead_modules_under_src` (L788) fails on any unlisted importer-less migration, so growth of `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS` is already a visible diff there. Demonstrate it in a tmp copy or by monkeypatching the scan inputs: plant an importer-less `m_*.py` name that is not in the frozenset, and the survivor goes red. Record the command and output in the tracer.
  5. `docs/adr/3.x/2026-07-07-1-ignored-surface-backfill-migration-pattern.md:114-115` has a checklist bullet that tells authors to "bump `category_1_auto_discovered_migrations` in `tests/architectural/_baselines.yaml`". Leave the decision text intact. Replace only that bullet with a dated supersession note: "(superseded 2026-09, mission ratchet-baseline-census-gate-remediation-01M3EW3Z: the `category_1` baseline leaf was retired; adding the migration to `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS` is sufficient)".
- **Files**: `tests/architectural/_baselines.yaml`, `tests/architectural/test_ratchet_baselines.py`, the ADR above.

### Subtask T036 – Remove the `skip_marker_blocks` leaf and its advisory machinery (D-OP-2)

- **Purpose**: `skip_marker_blocks` is advisory by design: the `record_property` values are write-only, and the docstring at L219-226 calls the count "intentionally NOT machine-enforced". It is a non-enforcing leaf, so it goes.
- **Steps**:
  1. `_baselines.yaml`: delete `skip_marker_blocks: 13` (L237) and its justification comment (L212-236). Keep `legacy_contract_allowlist: 151`, its comment, and the section header comment (L194-197, which describes only the legacy allowlist).
  2. `test_ratchet_baselines.py`: delete
     - `_SKIP_MARKER_GROWTH_PROP` and `_SKIP_MARKER_SHRINK_PROP` (L183-187);
     - `_emit_skip_marker_delta` (L205-240);
     - `test_skip_marker_growth_is_recorded_not_failed`, `test_skip_marker_shrink_is_recorded` and `test_skip_marker_live_count_never_blocks` (L887-935);
     - the FR-003 comments in the arms that refer to them (they may already have gone with T033).

     Keep `test_legacy_contract_allowlist_growth_still_fails` (L938-954), but update its docstring's "removing `_SKIP_MARKED_BLOCKS`" wording.
  3. `tests/contract/test_example_round_trip.py`:
     - Rewrite the comment above `_SKIP_MARKED_BLOCKS` (L584-587). It must no longer claim the set is "Introspected by `tests.architectural.test_ratchet_baselines` against `_baselines.yaml::test_example_round_trip.skip_marker_blocks`". State that the per-block `_SKIP_MARKER_RE` gate is the enforcer and the set exists for the invariants self-test.
     - Fix the docstring of `test_skip_marked_blocks_invariants` (about L801-805: "the baseline in `_baselines.yaml` owns the count").
     - **Keep** `_SKIP_MARKED_BLOCKS` and its self-test (L803-808).
     - Comment and docstring edits only. The file is format-excluded, so do not reformat it.
  4. **NFR-006 survivor**: the per-block `_SKIP_MARKER_RE` gate in `tests/contract/test_example_round_trip.py`. A block with neither `# pydantic_model:` nor a `# round-trip: skip: <reason>` marker fails that gate directly. Record the survivor's node ID and a one-line mutation demonstration (a tmp contract block with an empty skip reason fails it) in the tracer.
- **Files**: `tests/architectural/_baselines.yaml`, `tests/architectural/test_ratchet_baselines.py`, `tests/contract/test_example_round_trip.py`.
- **Validation**: `_leaf_drift(_load_baselines()) == ([], [])`, so the T032 test is now GREEN. The YAML holds 19 leaves in 12 sections. The `BaselinesFile` pydantic fields (L113-116) still validate.

### Subtask T037 – Lower-below-live mutations, planted-leaf self-mutation, floors, validation

- **Purpose**: Prove that "enforced" is real (US2-AS4) and that the leaf check itself is non-vacuous (NFR-002 pattern).
- **Steps**:
  1. Write `test_lowering_an_enforced_leaf_below_live_fails(monkeypatch, row)`, parametrized over `_SIZE_RATCHETS` with `ids=[f"{r.section}.{r.leaf}" for r in _SIZE_RATCHETS]`. For each row:
     - deep-copy `_load_baselines()`;
     - set `copy[row.section][row.leaf] = live - 1`, where `live = len(_import_module_attr(row.module, row.attr))`;
     - `monkeypatch.setattr(<this module>, "_load_baselines", lambda: copy)`;
     - `pytest.raises(AssertionError, match=re.escape(row.attr))` around `test_growing_an_allowlist_above_baseline_fails()`.

     For the two live-0 rows, `known_ungated_files` (egress) and `category_3_external_cli_entrypoints` (live 0, YAML 2), `live - 1 == -1` and the growth arm still fails (0 > -1). State that in a comment rather than special-casing it (Debbie LOW). This proves each row reads **its** leaf: a row wired to the wrong leaf would not red.
  2. Write `test_size_ratchet_table_meets_floor`:
     - `len(_SIZE_RATCHETS) >= 19`;
     - no duplicate `(section, leaf)`;
     - `_REQUIRED_TOP_LEVEL_KEYS` has 12 members.
  3. Write `test_leaf_drift_detects_planted_unenforced_leaf`. Take a synthetic copy of the live YAML plus:
     - (a) an extra leaf under an existing section (`test_layer_rules.planted_leaf: 1`);
     - (b) a re-added `test_no_dead_symbols: {x: 1}` section (T034 step 4).

     Assert `_leaf_drift` returns exactly those as unenforced. Removing an enforced leaf from the copy makes it appear in `missing`. Use the **same** `_leaf_drift` the production test calls.
  4. Load-bearing proof: monkeypatching `_enforced_leaves` to return the YAML's own leaf set turns the planted test green. That shows the derivation, not a tautology, is what fails it. Record this as a one-off mutation in the tracer, not as a committed test.
  5. Shrink-only proof for NFR-003: `git diff <planning-base> -- tests/architectural/_baselines.yaml | grep '^+ *[a-z_0-9]*: [0-9]'` must show no increased value. Record the leaf counts (23 on the planning base → 21 after WP05 → 19 after this WP).
  6. Record the green-side evidence with `spec-kitty agent tracer-append`.
- **Files**: `tests/architectural/test_ratchet_baselines.py`.
- **Parallel?**: No. It is last.

## Test Strategy

Tests are required. Record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run* section.

```bash
.venv/bin/python -m pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_no_inert_schema_slots.py \
  tests/architectural/test_reference_enum_ratchet.py tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_gate_remedy_presence.py tests/contract/test_example_round_trip.py \
  tests/architectural/test_ruff_format_exclude_ratchet.py -q
# _baselines.yaml is cross-cutting -> full architectural sweep
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
.venv/bin/ruff check tests/architectural/test_ratchet_baselines.py tests/contract/test_example_round_trip.py
.venv/bin/mypy tests/architectural/test_ratchet_baselines.py
```

- Complexity: C901 ≤ 15 for every touched function. The `_size_comparisons` extraction exists for exactly this reason. Add zero new suppressions.
- **Pre-existing failure rule**: classify any red that also appears on the planning base (CLAUDE.md "baseline-red gotcha"). If it is pre-existing and untracked, file a GitHub issue before continuing and note it here. Never retry-to-green.
- **Campsite (FR-020)**: clean #2972 Sonar findings (S5778/S5779/S8997 class) only in `test_ratchet_baselines.py` and `test_example_round_trip.py`, and only where you already edit. Record before/after pairs. Zero is acceptable.

## Risks & Mitigations

- **Arm rewire silently drops a row**: mitigated by the parametrized lowering test (19 ids plus a floor) and by the unchanged pre-existing arm tests.
- **Fast-tier import hygiene**: `test_fast_collection_does_not_import_round_trip_corpus` fails if the table imports the corpus at module scope. Keep dotted strings and resolve lazily.
- **Cross-lane semantic coupling with WP04** (`_ALLOWLIST` container type): the lowering test uses `len()` only, and the integration run after lane consolidation includes this file.
- **Stale prose elsewhere**: `tests/architectural/test_no_dead_symbols.py:130,2295` still says its categories are "introspected by the ratchet-baseline meta-test". That has been false since `test_no_dead_symbols` left `_baselines.yaml`. The file is not owned here: record it in the tracer as a residual and do not edit it.
- **Excluded file becomes format-clean**: escalate. Never edit `pyproject.toml` in this WP.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md` [CRITICAL] FR-011):

1. **Enforcement is derived, not listed.** `_enforced_leaves()` is computed from `_SIZE_RATCHETS`, and both comparison arms iterate `_SIZE_RATCHETS` (verify by reading them). There must be no separate hand list of allowed nested keys anywhere in the module.
2. **Red-first for the intended reason.** The T032 commit precedes the implementation commits. Its recorded failure names exactly the 2 lane leaves, and the planning-base run of `_leaf_drift` names exactly the 4.
3. **Each row reads its own leaf.** `pytest tests/architectural/test_ratchet_baselines.py -k lowering -v` shows 19 passing ids. Reviewer spot-mutation: swap two rows' `leaf` values and at least two ids go red.
4. **Planted leaf fails.** A tmp edit adding `foo: 1` under any section reds `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` with `section.foo` named.
5. **Retirements name survivors** (NFR-006):
   - `category_1` → `test_no_dead_modules.py::test_no_new_dead_modules_under_src`, with a mutation proof in the tracer;
   - `skip_marker_blocks` → the `_SKIP_MARKER_RE` gate in `tests/contract/test_example_round_trip.py`;
   - the grandfather/unregistered tests → the leaf test.
6. **Shrink-only.** No `_baselines.yaml` value increased. The final shape is 19 leaves in 12 sections.
7. **No `src/` or `pyproject.toml` diff.** The ADR edit is a single dated supersession bullet.
8. `mypy` and `ruff check` are clean on the changed Python files.

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
