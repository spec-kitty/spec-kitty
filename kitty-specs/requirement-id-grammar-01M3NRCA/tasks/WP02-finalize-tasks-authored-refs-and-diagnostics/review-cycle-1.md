---
affected_files: []
cycle_number: 1
mission_slug: requirement-id-grammar-01M3NRCA
reproduction_command:
reviewed_at: '2026-09-29T10:53:30Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review: cycle 1, changes requested (Reviewer Renata)

## Summary

The production behaviour is **correct**, and I verified it independently:

- I ran 8 real-CLI probes. All pass: the qualified citation is kept on a real run, a malformed ref leaves the file byte-identical, a scalar ref becomes a list, the foreign-only and SC-only rules hold, the no-SC-section case works, populate-when-empty works, and all three new keys are present on real-run success, validate-only success and failure.
- `finalize_tasks` changes only the gate assignment and the deleted splice, and its `noqa` is unchanged.
- C901, ruff and mypy show nothing new.

The rejection is for **missing mandated tests**. The WP prompt makes these tests mandatory, and the review focus names them. Every fix is test-only; do NOT change `src/`.

## Blocking (tests only)

1. **Missing the qualified-citation real-run retention pin** (T011 and review focus #1). Use the Half-2 fixture with `[FR-001, other-mission-01KAAAAA#FR-013]` (add `FR-006a` or map it elsewhere so the run passes). Run WITHOUT `--validate-only`, read the file back with `read_wp_frontmatter`, and assert the list item for item. Also assert `planning_base_branch == "main"` in the same file.
2. **Missing the scalar-string to list pin** (T010, marked "Mandatory: Pin it with a test"). Seed `requirement_refs: "FR-001, SC-002b"` and do a real run. Assert that the result is `["FR-001", "SC-002b"]`, with the same order and spelling.
3. **Missing the named test `test_mission_without_success_criteria_section_finalizes_unchanged`** (T012 and the spec Edge Case). Run it through the CLI. Assert `success_criteria_coverage == {"referenced": {}, "unreferenced": []}`, `parsed_spec_ids["success_criteria"] == []`, exit 0, and the pre-existing keys. Add the same-fixture positive control: leave one FR unmapped and assert exit 1 naming it.
4. **Missing the malformed-kept-on-disk real-run pin** (T011, US1 AC2). WP01 = `[FR-001, C-007-mission]`, real run. Assert:
   - exit 1;
   - the `malformed` reason is reported;
   - the WP file bytes equal the seeded bytes;
   - control: `FR-001` is not in `unmapped_functional_requirements`.
5. **A non-empty `success_criteria_coverage.unreferenced` is never pinned.**
   - Mutation M8 at `mission_finalize.py` `_build_success_criteria_coverage` (~:1275) hard-codes `unreferenced: []`. It survives the whole validation surface.
   - Add an FR-007 test on one fixture: an unreferenced declared SC appears in `unreferenced` and the run passes.
   - Its positive control: add an unmapped FR and assert exit 1 naming that FR.
6. **The T011 halves are proven only at helper level.** Tests `test_mission_finalize_phases.py:359/373/387` (and the SC-only test) call `_classify_wp_requirement_refs` directly. The WP mandates CLI-level `--validate-only` tests on one shared fixture, and tactic `acceptance-criteria-non-vacuity` names "helper-only non-vacuity" as a failure mode.
   - Add the CLI versions of Half 1 (exit 1, `unknown_requirement_refs == {"WP01": ["SC-009"]}`, `FR-001` not unmapped), Half 2 (exit 0, reported `foreign_qualified`), SC-only and foreign-only.
   - Keep the helper tests as unit coverage.

## Non-blocking

7. **No direct unit tests for the new pure builders.** `_build_requirement_diagnostics` (:1298), `_build_success_criteria_coverage` (:1275) and `_build_requirement_mapping_failure_payload` (:1326) are covered only indirectly. The WP asks for focused tests to meet NFR-004 (Sonar diff coverage). Add small direct tests.
8. **Commit hygiene.**
   - Commits `725c5e24ab` and `e518dced61` each remove a symbol while `mission_finalize.py` still imports it, until `fdd12ad49d`. The package therefore fails to import at those two commits (not bisectable).
   - The T009 tidy step was folded into the functional commit, although the prompt says "never fold T009".
   - Squash consolidation will hide both issues. Note them in the tracer notes; no rewrite is needed.
9. **Nits.**
   - `test_finalize_requirement_id_grammar.py:11` refers to a "`b_ratchet` marker below" that does not exist.
   - In `_build_success_criteria_coverage` (:1293), a WP that lists the same SC twice is appended twice to `referenced[SC]`. Consider de-duplicating.

## Verified OK (no action)

- RED at `bca6fedea1` in a throwaway worktree: (a) and (c) fail on assertions; (b) is green, the WP01 T004a ratchet. All are green at the tip.
- Mutations M1 (valid sibling counts), M2 (foreign never fails), M3 and M6 (rewrite and populate-when-empty), M4 and M5 (the success-payload spread) and M7 (foreign-only is missing) are each killed by the committed tests.
- The explicit `grammar as grammar` re-export is necessary. Without it, mypy `--strict` reports `attr-defined` at `mission_finalize.py:79`.
- The 3 `no-any-return` findings are the same at the lane base and at the tip. The 4 map-requirements reds are red at the base (WP03).
- Out-of-map edits stayed within the sanctioned hunks.
