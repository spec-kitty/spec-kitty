# IC-08 — FR-007 class: corpus, data-artefact and agent-registry counts (WP09)

Materialized at closeout from WP09's reported evidence (scratchpad `WP09_evidence_records.md`)
and the reviewer's full approval note (`status.events.jsonl`,
`review_ref: auto-approval:WP09:20260930` — considerably more itemized than the one-line
`review-cycle-1.md`).

## F4 — `tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py`

```yaml
id: EV-IC08-F4
item: F4
kind: FIX
planted_break:
  target: "packs/built-in/agent_profiles/zzz-scratch-plant.agent.yaml (new, scratch) + scripts/doctrine/inline_reference_inventory.py::_classify_reference_entry"
  description: >
    neutral: added a scratch agent-profile file with a directive-references field.
    violation: changed the terminal `return RAW_MATERIAL, raw` to `return GOVERNANCE, raw`.
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py -n0 -q"
results:
  old_form_under_break: "RED (neutral) — test_governance_occurrences_and_files_match_sc011: assert len(gov) == 101 -> AssertionError: assert 102 == 101"
  new_form_under_break: "GREEN (neutral) — test_governance_and_raw_material_occurrences_have_the_sc011_shape: 1 passed; RED (violation) — AssertionError: assert ([...] and []) (raw emptied, every RAW_MATERIAL path reclassified GOVERNANCE)"
  clean_tree: "pass — 19 passed"
counts: {executed_before: 19, executed_after: 19}
reviewer_rerun: false
```

## F5 — `tests/docs/test_glossary_linker.py`

```yaml
id: EV-IC08-F5
item: F5
kind: FIX
planted_break:
  target: ".kittify/glossaries/spec_kitty_core.yaml + scripts/docs/generate_kitty_specs_docs.py::assign_anchor_ids"
  description: >
    neutral: appended a new term ("zzz scratch t041 plant") to the seed file.
    violation: appended a duplicate "surface: build" term AND edited assign_anchor_ids to
    `continue` (skip) on a collision instead of appending a numeric suffix.
  reverted: true
command: "uv run --frozen pytest tests/docs/test_glossary_linker.py -n0 -q"
results:
  old_form_under_break: "RED (neutral) x2 — test_real_glossary_seed_yields_104_unique_anchor_ids / test_load_link_terms_from_real_seed: assert len(terms) == 103 -> AssertionError: assert 104 == 103"
  new_form_under_break: "GREEN (neutral) x2 (2 passed); RED (violation) x2 — assert len(terms) == len(parsed/expected) -> AssertionError: assert 103 == 104 (the colliding build term silently dropped instead of suffixed)"
  clean_tree: "pass — 16 passed"
counts: {executed_before: 16, executed_after: 16}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP09:20260930): "F5 neutral: seed +=
  well-formed term -> new form 2 passed, old form (from 162b3435cd^) 2 failed" — exactly this
  record's neutral plant, reproduced independently against the pre-commit tree. The reviewer
  also ran an additional plant not in the WP's own report: "keyword-contract probe: blank a
  real term surface -> new form 16/16 GREEN, old form RED; covered elsewhere by
  tests/architectural/test_glossary_pack_parity.py::test_surface_set_parity (RED under same
  plant), so no unguarded contract" — recorded here since it extends this same F5 surface,
  not as a separate WP-reported item. Tallied in evidence/README.md.
```

## F7 — `tests/unit/convergence/test_census_status.py` (RETIRE + floor)

```yaml
id: EV-IC08-F7
item: F7
kind: RETIRE
planted_break:
  target: ".kittify/convergence-map.json"
  description: >
    neutral: appended a consistent cluster (id SCRATCH#T042, disposition PORT, one commit,
    census_commit_count: 1 matching). violation (covering guard): set
    clusters[0].census_commit_count to 999 (mismatching its 1-item commit list).
  reverted: true
command: "uv run --frozen pytest tests/unit/convergence/test_census_status.py -n0 -q"
results:
  old_form_under_break: "RED (neutral) — test_seed_map_has_complete_nonpending_dispositions: assert len(census_map.clusters) == 74 -> AssertionError: assert 75 == 74"
  new_form_under_break: "GREEN (neutral, floor form) — 1 passed"
covering_guard:
  node_id: "test_seed_map_census_counts_match_commit_lists"
  under_break: fail   # AssertionError: PR#2239 / assert 999 == 1
results_clean_tree: "pass — 5 passed"
counts: {executed_before: 5, executed_after: 5}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "F7 covering guard census_commit_count 1->2 on PR#2239 ->
  test_seed_map_census_counts_match_commit_lists RED, other 4 green" — exactly this record's
  covering-guard plant, reproduced independently. Tallied in evidence/README.md. C-002
  satisfied: the covering guard catches what the retired absolute count no longer does.
```

## F10 — `tests/agent/test_agent_config_migration.py` + `tests/specify_cli/regression/test_twelve_agent_parity.py`

```yaml
id: EV-IC08-F10
item: F10
kind: FIX
planted_break:
  target: "src/specify_cli/agent_utils/directories.py + src/specify_cli/core/config.py"
  description: >
    neutral: registered a new agent ".zzzscratch" consistently across AGENT_DIRS,
    AGENT_DIR_TO_KEY, and AGENT_COMMAND_CONFIG. violation 1: added to AGENT_DIRS only, no
    AGENT_DIR_TO_KEY entry. violation 2: added AGENT_COMMAND_CONFIG["zzzscratch"] only, no
    AGENT_DIRS/AGENT_DIR_TO_KEY entry.
  reverted: true
command: >
  uv run --frozen pytest
  "tests/agent/test_agent_config_migration.py::TestAgentDirMapping::test_agent_dir_to_key_complete"
  "tests/specify_cli/regression/test_twelve_agent_parity.py::test_non_migrated_agents_count" -n0 -q
results:
  old_form_under_break: "RED (neutral) x2 — test_agent_dir_to_key_complete: assert len(AGENT_DIR_TO_KEY) == 13 -> assert 14 == 13; test_non_migrated_agents_count: assert len(NON_MIGRATED_AGENTS) == 13 -> got 14"
  new_form_under_break: >
    GREEN (neutral) x2; RED (violation 1) — test_agent_dir_to_key_complete:
    assert set(AGENT_DIR_TO_KEY) == {...} -> Extra items in the right set: '.zzzscratch';
    RED (violation 2) — test_non_migrated_agents_count: Extra items in the left set: 'zzzscratch'
  clean_tree: "pass — 228 passed (combined with test_shape_guard_membership.py)"
counts: {executed_before: 228, executed_after: 228}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "F10 V1 AGENT_DIRS += .plantdir w/o key ->
  test_agent_dir_to_key_complete RED, parity count GREEN (old len==13 would stay GREEN: new
  form strictly stronger); F10 V2 AGENT_COMMAND_CONFIG += plantkey w/o dir ->
  test_non_migrated_agents_count RED ('plantkey' extra left)" — both violation plants
  recorded here, reproduced independently with sha256-verified byte-exact reverts. Re-run per
  Review Guidance quickstart #17 for violation 2. Tallied in evidence/README.md.
```

## Final named-file run, quality gates, make test-fast

- `uv run --frozen pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/docs/test_glossary_linker.py tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py tests/specify_cli/regression/test_twelve_agent_parity.py tests/architectural/test_shape_guard_membership.py -n0 -q` -> **268 passed**.
- `ruff check <5 files>` -> All checks passed!
- `ruff format --check tests/unit/convergence/test_census_status.py tests/agent/test_agent_config_migration.py` -> 2 files already formatted.
- Skip hygiene: 1 pre-existing hit, untouched by this WP's diff (`tests/specify_cli/regression/test_twelve_agent_parity.py:111`, its own reason, unrelated to F10's edit at :225-237).
- `make test-fast` -> `2169 passed, 5 skipped, 5 warnings in 274.09s`, exit 0 (5 skips pre-existing, outside this WP's 5 owned files).
- `git diff --stat src/ packs/ .kittify/` -> empty, verified after every plant revert and before final commit.

## Definition of Done (C-011) — test-only WP

Every FIX (F4, F5, F10 x2) and RETIRE (F7) carries the planted-break red->green proof above:
red on the planted defect (old form for FIX rows; new form for the violation row), green on
the real code, plant never committed. No sanctioned FR-005 product fix was needed for this
WP — no new product defect was uncovered by any unmasked/converted test.
