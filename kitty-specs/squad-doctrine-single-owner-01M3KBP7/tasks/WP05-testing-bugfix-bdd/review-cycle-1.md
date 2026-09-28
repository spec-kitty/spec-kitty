---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T12:31:09Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review — cycle 1 (reviewer-renata): CHANGES REQUESTED

The red-first pin works: 27 failed at 97217458 and 45 passed at 06620a5a. The fold of the four checklist lines, the BDD rename, the development-bdd order, the paradigm references, the TS `break: 0` opt-in and the testing-principles renames are good. Dropping "Predictive" loses no meaning, because test-desiderata-and-boundaries:31 owns it ("fit for production"). The items below must be fixed before approval.

## Blocking

1. **Dangling references to the retired `behavior-driven-development` tactic in unassigned built-in YAML.** No WP owns these files, so they are not graph staleness and they are not WP09's to fix. Retarget both to `bdd-scenario-formulation` as small out-of-map edits, with a one-line rationale in the Activity Log:
   - `packs/built-in/tactics/testing/test-readability-clarity-check.tactic.yaml:51`
   - `packs/built-in/tactics/testing/function-over-form-testing.tactic.yaml:72`

   After the fix, `tests/doctrine/test_directive_consistency.py::test_tactic_references_resolve_to_known_tactics` should be green. Remove it from `Expected-red-until-WP09`.
2. **A stale id remains in an owned file.** `packs/built-in/tactics/architecture/development-bdd.tactic.yaml:9` still says "(see the behavior-driven-development tactic for that)". Retarget it to `bdd-scenario-formulation`. Widen `test_no_stray_reference_to_retired_behavior_driven_development_tactic_id` so it catches the bare id, not only `id: behavior-driven-development`.
3. **Mutation band table is framed as a target, not as triage bands (T024 / recorded decision).** `mutation-testing-workflow.tactic.yaml` notes still read "Target mutation scores: < 60% ... > 90% strong". The decision was: no numeric target, and one table framed as triage bands. Reframe it, for example "Triage bands (a signal for where to look, not a goal): ...". Pin the framing in the test: the owner carries triage wording and no "target".
4. **Tidy-first sequencing and the 025 reference are missing (T022 / recorded decision).** The decision is a separate behaviour-preserving tidy-first commit on the surfaces the fix will touch, *before the red reproduction test*, and 025 owns that rule. `test-first-bug-fixing` only says "a separate, preceding tidy-first commit", which is ambiguous about what it precedes, and it has no reference to DIRECTIVE_025. Two changes are needed:
   - State the order explicitly: tidy-first, then red repro, then fix, then refactor scoped to the fix. Cite 025 by id instead of restating the rule.
   - Add the 025 reference, or hand the edge to WP09 as curated. Say which in `Handoff-to-WP09`; WP09's prompt lists `test-first-bug-fixing → 025` as a required edge.

   Also fix the vacuous test `test_states_refactor_after_green_before_the_fix_step`. It only checks that "refactor" appears somewhere, which already passed on the base. Assert the tidy-first-before-repro order and the 025 citation instead.

## Should fix (small)

5. **The BDD tactic's toolchain pointer is wrong.** The trimmed note in `bdd-scenario-formulation` says "For the toolchain landscape (runners, browser automation, narrative reports...) see the Gherkin toolguide". But GHERKIN.md explicitly puts runners out of scope (lines 5-7 and 115-127), so the pointer sends readers to a document that disclaims the content.

   The deviation itself (trim rather than move) is reasonable. Two options:
   - keep a condensed two-line runner/automation note in the tactic, including the custom-DSL-vs-Gherkin trade-off, which is real guidance that was lost;
   - or point only at what the toolguide actually covers (notation) and record the lost landscape as a follow-up for WP10.

## Non-blocking notes

- The checklist's "Link to the bug report or ticket" line was dropped from "Document the fix". Consider keeping it.
- The `Handoff-to-WP09` prose for the disciplined-defect-diagnosis edge contains a self-correction ("... no, the LIVE edge is ..."). Clean it up so WP09 reads one clear instruction.

## Test gap: a mutation-probe survivor (fix together with blocking item 3)

In a scratch copy, reverting the TS JSON example to `"break": 60` left the whole suite GREEN. Two assertions miss it:
- `test_no_break_60_ci_gate_example_anywhere` checks the literal `break: 60`, but the JSON form is `"break": 60`.
- `test_typescript_toolguide_ci_example_is_marked_opt_in_with_break_zero` is satisfied by the prose "ships `break: 0`", not by the JSON example.

Match the JSON form with a regex such as `"?break"?\s*:\s*60`, and assert the JSON example itself carries `"break": 0`. The injected Python band table was correctly caught.

## Evidence
- Red to green: 27 failed / 16 passed at 97217458; 45 passed at 06620a5a.
- `pytest tests/doctrine -m "not slow" -k "tactic or procedure or styleguide or toolguide or directive or paradigm or mutation or bdd"`: 583 passed, 7 skipped, 2 failed.
  - `test_path_ref_resolver.py::TestGraphWithStyleguideEdges::test_shipped_graph_is_fresh` is regeneration staleness and is expected.
  - `test_directive_consistency.py::test_tactic_references_resolve_to_known_tactics` is a REAL failure (item 1).
- Provenance ratchet and terminology: 100 passed.
