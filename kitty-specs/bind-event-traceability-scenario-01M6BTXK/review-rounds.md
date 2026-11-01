# Review record

Two review rounds, one per work package, each reviewer-loaded (`reviewer-renata`) and each
followed by a fix commit before approval. No subagent squad was deployed: the diff is two
step-definition files, one environment helper, one feature file and its docs, and the
reviewer was the mission's own registered reviewer profile.

## Round 1 — WP01 (step bindings and the crafted pulled row)

Reviewed: `git diff` of `acceptance-jvm/**` against the planning base.

Findings and fixes:

1. **Field-order fragility in the lane assertion** (fixed, `fix(WP01): read the status entry's
   own object for the lane assertion`). `AssertSteps.reportedLane` matched `"id"` then the next
   `"lane"` inside `[^}]*`; that breaks if a nested object appears before the lane or the field
   order changes. It now finds the object containing the id by brace-matching (string-aware) and
   reads the lane inside that object.
2. **The rejection needs a review reference.** `approved -> in_progress` refuses without
   `review_ref` (`ApprovedState.guard_for`). The Act step now writes the reviewer's notes outside
   the repository and passes them as `--review-ref`, as a reviewer delivers them; recorded in the
   design-decision tracer.

Disposition: `approved` after the fix commits.

## Round 2 — WP02 (gate the scenario, positive control, docs)

Reviewed: the feature diff against the planning base, the README step table, the testing guide and
the changelog fragment.

Findings and fixes:

1. **`@wip` removal and the QA promise id are entangled in the guide** (fixed,
   `docs(WP02): separate dropping @wip from the QA promise identifier`). The guide read as if the
   identifier must arrive with the binding; a bound scenario held in `@wip` for a registry id would
   never run. The paragraph now states the two steps are separate and why.
2. **Drafted assertions preserved.** Byte-comparison of the two drafted scenarios' Given/When/Then
   lines against the base: unchanged. Only the tag line, the maintainer notes and one new scenario
   differ.

Disposition: `approved`.

## Aggregate review of the integrated diff

- **Promise covered**: a rejection recorded after a clock-skewed approval puts the work package in
  `in_progress` and consolidation refuses with `not merge-ready` naming the work package; the
  positive control consolidates an approved, accepted Mission and lands the code.
- **Non-vacuity**: the assertions read the CLI's own status and refusal text (never absence of
  output), and the positive control runs the same Arrange/Act with the approval as the last
  decision.
- **No product change**: `git diff --stat` touches no `src/` file; the #4941 fix and its pytest
  guard are untouched.
- **Scoped exception**: the single status-log write is the crafted pulled row, documented in the
  helper javadoc, the scenario notes and the testing guide, and authorised by #6260.
- **Verification**: `gradle compileTestJava` clean; two independent single-feature runs had every
  step of all three scenarios pass; the per-PR scenario contract (`41 passed`) and
  `scripts.ci.scenario_contract` (exit 0, no findings for this feature) are green; docs freshness
  is `errors=0`.
- **Environment reds** (not this diff): the runs' After hook fails when another Mission on the same
  host writes `~/.spec-kitty/spec-kitty-prompts/` during the window (filed as #7026), and
  per-process ceilings trip under host load. CI runs on dedicated runners.

Outcome: `approved`. No divergences from the spec; no canvas, glossary or charter follow-up.
