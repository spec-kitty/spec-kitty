# Approach

- The defect has two independent causes (see `../research/code-grounding.md`): a
  positional citation label matched anywhere on the line, and no notion at all of
  "the issue this Mission exists to fix".
- Fix cause 1 where the information is lost: retain the citation's position on
  `Occurrence` and require a positional label to end at the reference it leads into.
- Fix cause 2 in the one gating seam every consumer already shares (`is_gating` /
  `gating_issue_numbers`), so the scaffold, approval blocker, doctor and merge gate
  cannot disagree.
- Red-first: both behaviours are driven through `scaffold_issue_matrix` (the
  observable production path) before the classifier is touched.

## Slice order

1. WP01 — occurrence position + positional label scoping (cause 1).
2. WP02 — source-issue derivation and promotion across scaffold + discovery (cause 2).
3. WP03 — cross-consumer agreement, regression pin, docs/changelog.
