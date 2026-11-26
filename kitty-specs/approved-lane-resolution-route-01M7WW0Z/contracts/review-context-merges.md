# Contract: review context merge lines (amends review-context contract C-001)

> **Superseded in part.** The landed review-context merge lines are recorded in ADR `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md`, Amendment 2026-11-26. The printed resolution command now carries the pinned merge config as `-c` flags. It also carries `--attr-source=<target tip>`, which falls back to the empty tree when the target is unreadable, and `--no-ext-diff --no-textconv`. On git < 2.40 it adds a version-gated "cannot neutralise attributes" line (WP12). Read the ADR for the current form.

C-001 is kept: the review context renders commands only, never patch text. This contract adds one kind of command line.

- `resolve_wp_review_range` lists every merge in the review range. It uses `git rev-list --merges --full-history <base>..<tip>` and applies no pathspec simplification.
- For each merge the renderer prints:
  `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <sha>`
- If remerge-diff is unavailable, it prints instead:
  `RESOLUTION MERGE <sha12>: this git cannot show the resolution (needs git >= 2.36); review the merge by hand`
- When the range has no merges, the output is unchanged.
