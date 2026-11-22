# Approach

- Research first: two grounding agents (#7809, #7802 + #7806), then an architect + researcher squad over the findings doc, then operator rulings via AskUserQuestion.
- The squad changed three proposals:
  - #7802: refusing an unpushed stamp became the dual stamp;
  - #7806: the branch is created in the review's origin step, not in `lifecycle_sync`;
  - #7809: open issue #7759 contradicts a topic-branch-only fix.
- The operator then chose the larger "docs WPs get a lane" fix.
- Five independent WPs, one per issue, so they run in parallel lanes. Files owned per WP do not overlap.
