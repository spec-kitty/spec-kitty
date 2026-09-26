---
affected_files: []
cycle_number: 1
mission_slug: criterion-labels-positive-controls-01M3EWRT
reproduction_command:
reviewed_at: '2026-09-26T14:07:54Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review (reviewer-renata): REJECT, changes requested

The template, prompt and snapshot changes are mostly sound. C-007 (`FR-EXAMPLE`) and C-004 hold, and the mis-placed-label pair is a real same-fixture control. The test suite fails the mission's own non-vacuity doctrine in three places, all confirmed with deletion tests.

## Blocking

1. [MAJOR] tests/specify_cli/test_requirement_mapping.py `test_labelled_and_twin_give_same_unmapped_set_through_production_path` is vacuous (the production-path non-vacuity rule is broken).
   Evidence: when the label is moved into the FR-001 id cell of `_SPEC_LABELLED`, the parser drops FR-001, yet this test still PASSES (3 other tests go red). The reason: `existing_all_refs={"WP01":["FR-001"]}` makes `unmapped_fr == []` on both sides, and an empty functional set gives the same `[]`.
   Fix: map nothing (or map an id other than FR-001), then assert `labelled_plan.unmapped_fr == twin_plan.unmapped_fr == ["FR-001"]`. The reviewer confirmed this version goes red under the same deletion. Optionally also assert FR-002 (the mis-placed row) is absent from `unmapped_fr`, so the production path shows the control too.

2. [MAJOR] FR-001 / FR-002 (both `[build]`, no-op passable: no) have no pinning test (§4a item 4).
   Evidence: `git checkout <base> -- packs/built-in/missions/software-dev/templates/spec-template.md` leaves all 87 tests in test_substantive_gate_formats.py + test_requirement_mapping.py green. The T008 tests are ratchets that pass on the pre-change template, and `"FR-EXAMPLE" not in declared["all"]` holds trivially.
   Fix: add build assertions on the live template: the FR header carries trailing `Delivery | No-op passable?`, every placeholder FR row ends with the label and mark placeholders, every SC bullet carries the suffix, the legend contains the `FR-EXAMPLE` row and the tactic pointer, and NFR/C headers are unchanged. The `FR-EXAMPLE` assertion needs a positive control: show that the example line is present in the template text, so the "not declared" claim does not pass vacuously.

3. [MAJOR] C-006 is violated in spec-template.md legend items 5 and 6 (about lines 87-93). They define all three labels and the no-op mark over about 6 lines and are not marked as a summary. Item 7 then says "Do not redefine the labels here", which contradicts them. The "summary of tactic acceptance-criteria-non-vacuity" marker sits on the filled-example line, not on the gloss.
   Fix: shrink items 5 and 6 to a single gloss line marked "(summary of tactic acceptance-criteria-non-vacuity)" plus the pointer (item 7), and keep the placement rule (item 8).

## Non-blocking

4. [MINOR] test_requirement_mapping.py `test_trailing_label_citation_does_not_create_bare_prose_finding` asserts absence (`== []`) with no same-fixture positive control. Add a variant of the same fixture with a bare-prose undeclared id (e.g. an `FR-011 must hold.` line under the heading) and assert it IS reported.
5. [MINOR] spec-template.md:105 has the example mark "yes — paired with a same-fixture positive control" but does not name the control. The tactic requires naming it (e.g. "paired with the well-formed-input row on the same fixture").
6. [MINOR] specify/prompt.md:702 has an inline label gloss that is not explicitly marked as a summary of the tactic (C-006). Prefix it with "summary of tactic acceptance-criteria-non-vacuity:".

## Verified OK
- C-007: a real `FR-004` in the example makes tests (1) and (3) go red.
- C-004: parser untouched, no inline or ID-cell labels.
- Terminology is clean. The snapshot diff is limited to the 3 new guidance lines.
- The ruff-format campsite commit is legitimate: the base file was unformatted.
- 3 skills-installer failures are also red on the base (pre-existing, not WP02).
