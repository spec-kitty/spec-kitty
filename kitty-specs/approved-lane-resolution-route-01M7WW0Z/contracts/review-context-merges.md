# Contract: review context merge lines (amends review-context contract C-001)

C-001 is kept: the review context renders commands only, never patch text. This contract adds one kind of command line.

- `resolve_wp_review_range` lists every merge in the review range. It uses `git rev-list --merges --full-history <base>..<tip>` and applies no pathspec simplification.
- For each merge the renderer prints:
  `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`
- If remerge-diff is unavailable, it prints instead:
  `RESOLUTION MERGE <sha12>: this git cannot show the resolution (needs git >= 2.36); review the merge by hand`
- When the range has no merges, the output is unchanged.
