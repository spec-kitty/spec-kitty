---
affected_files: []
cycle_number: 1
mission_slug: criterion-labels-positive-controls-01M3EWRT
reproduction_command:
reviewed_at: '2026-09-26T14:30:32Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review — reviewer-renata — REJECT (changes requested)

Half-by-half passes: deleting the tactic file, the review `index.yaml` entry (via the regen roundtrip gate), prompt §4b, or either sibling step reference each turns a test red. The requirements below are what still needs fixing.

## [HIGH] The fetch command strips the canonical labels (FR-007, C-006, rule 3 "production path")

`spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity` (the command §4b tells every reviewer to run) prints through `console.print(included_text)` in
`src/specify_cli/cli/commands/charter/context.py:120`. Rich parses `[build]`, `[ratchet]` and `[folded]` as markup tags and drops them. The live output reads:

    delivery label:  (new behavior),  (existing behavior pinned against regression), or  (satisfied by another item ...)
    "notes": "... Delivery labels -- : new behavior ... : existing behavior ... a  row guarded by ..."

So the single canonical legend cannot be read through the prescribed channel. The bracketing is a pre-existing CLI bug, but this WP is the first content to trip it, and FR-007 is this WP's requirement.

`test_named_tactic_id_resolves_through_the_charter_context_include_path` calls the helper `build_charter_context_include`, not the CLI. That is the "helper-only non-vacuity" failure mode this tactic defines, and the tactic's own step-5 example calls it the production path.

Fix:
- (a) Add `markup=False` to that `console.print` (or `rich.markup.escape`). This is a small, justified out-of-map crossing; log a one-line rationale.
- (b) Change or add a test that invokes the real CLI (`typer.testing.CliRunner` on the charter app) and asserts `[build]`, `[ratchet]` and `[folded]` appear in stdout.
- (c) Add a same-fixture positive control: an unknown id such as `tactic:<id>-x` must fail (it raises `ValueError` today).

## [MEDIUM] Silent loss of `review -> tactic:boring-code-review` from review context

The regenerated `action.graph.yaml` drops that scope edge. `resolve_context(action:software-dev/review)` no longer contains `tactic:boring-code-review` at depth 1 or depth 2. That is a code-review tactic leaving the review action's context.

The drop is noted in commit ea6eaa953/dd7166df6, but not in the WP Activity Log, and it was not adjudicated with the operator. T006 required it in the Activity Log.

Fix: either list `boring-code-review` explicitly in `review/index.yaml` and pin it in `test_reachability.py`, or record an explicit, reasoned acceptance in the Activity Log.

## [LOW] The comment about prose mentions is false

`acceptance-criteria-non-vacuity.tactic.yaml` has a comment in its `references:` block saying that `architectural-gate-non-vacuity` is "named only in this tactic's own prose (see purpose/step 1 wording)". No loaded field names it, and neither `acceptance-test-first` nor `delete-the-assertion-not-the-test` is named either. They appear only in YAML comments, which the loader drops.

Fix: add one sentence to `notes` naming these sibling ids. The DRG extractor ignores prose, so this adds no edge and no cycle. Then correct the comment.

## [LOW] The rationale comment for the cascade totals contradicts itself

In `tests/charter/test_cascade.py` (~line 882), the comment says "+4 for every governance-bearing mission type, except documentation", but the numbers are documentation +4 and the other three +1. The pinned numbers themselves are correct: the test is green. Only the wording needs fixing.

## [LOW] The no-copy guard has no positive control and is evadable

`test_sibling_does_not_copy_the_rule_text` asserts `"same fixture" not in blob`. `atdd-adversarial-acceptance` now says "same-fixture positive control" (hyphenated), so the probe cannot see the rule wording that actually shipped. It also has no same-fixture control.

Fix: normalise hyphens and whitespace. Add a control that runs the same blob builder on the new tactic and asserts the phrases are present. Keep the one-sentence gloss, which the WP allowed, but mark it as a summary of the tactic per C-006.
