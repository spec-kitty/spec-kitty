---
affected_files: []
cycle_number: 1
mission_slug: requirement-id-grammar-01M3NRCA
reproduction_command:
reviewed_at: '2026-09-29T10:42:35Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (cycle 1): changes requested, narrow

Overall, this is strong work. The red-first evidence was verified through the real CLI: 2 failed at `a3c7dc40fb` and green at the tip. Each part of the compound fix goes red on its own when reverted:
- normalising reader;
- sorted-set merge;
- `.upper()` input.

233 tests pass (185 surface + 48 gates). `mypy --strict`, `ruff check` and C901 are clean. The byte-contract re-pins are exactly the two sanctioned ones, and `map_requirements_success` and `unknown_spec_ref_error` are untouched. Once the item below is fixed this should be approvable in one pass.

## Blocking

**B1: T017 step 1's legacy scalar / compound-item edge has no pinning test and no tracer note (required deliverable).**
The WP prompt says: "Two edges need a pinning test each, plus a one-line entry in `## Tracer notes`". Only the `<NON_STRING:…>` edge is pinned (`test_non_string_frontmatter_item_fails_typed_write_file_unchanged`).

The reviewer probe at the tip found that both `requirement_refs: "FR-001, FR-002"` (scalar) and `requirement_refs: ["FR-001, FR-002"]` (one compound item), mapped with `--refs NFR-001`, give exit 0 and write `["FR-001", "FR-002", "NFR-001"]`. The compound item is split into separate items. No ID is lost, but this is the one path where FR-005's "existing items byte-identical" does NOT hold, and nothing pins it.

Fix:
- Add a CLI-level test in `test_map_requirements_grammar.py` asserting that defined behaviour for both shapes: the IDs survive, in order, split into single-ID items, followed by the appended ref.
- Add the one-line tracer note stating that this is the defined behaviour.

## Non-blocking (fold in while you are there)

- **L1:** `tests/specify_cli/cli/commands/agent/test_tasks_mapping_core.py:165` (new test `test_append_only_never_collapses_pre_existing_duplicates`) is not `ruff format`-clean. The file was already format-red on the base, but these are new lines, so run `ruff format` on the new hunks only, or reword the docstring so it does not open with `""""`.
- **L2:** `tasks_map_requirements.py:68`. A comment still contains the literal `FR-NNN`, so the review-guidance grep (`grep -n "FR-NNN"` → nothing) is not empty. Reword the comment, for example "the retired per-kind rule text".
- **L3:** T017 step 3 asked for a pure coverage-projection helper with its own tests. It was not extracted. The behaviour is equivalent because `compute_coverage` already matches by canonical form, a foreign ref's canonical form is qualified, and functional ⊂ declared. The CLI test `test_foreign_qualified_never_blocks_or_covers` covers it. Either add a one-line note on `plan_mapping` explaining why no helper is needed, or extract it.
- **L4:** In `test_replace_lists_what_it_removed_positive_control`, the non-`--replace` control runs on a different WP (`WP02 ["FR-002"]`), not on the same fixture. That is acceptable, because the same fixture would exit 1 on `FR_009`. Say so in a one-line comment, so the deviation from "same fixture" reads as deliberate.

## Coordination note

`src/specify_cli/requirement_mapping/__init__.py` is also edited by WP02, in a distant hunk. The WP03 hunk is a pure deletion at about lines 454–528 and is minimal. Keep it that way on rework.
