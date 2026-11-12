---
type: how-to
updated: 2026-11-12
---

# Quickstart: see a work package's review range

1. Move a work package to `for_review`.
2. Open its review: `spec-kitty agent action review WP02 --agent <name> --mission <handle>`, or let `spec-kitty next` issue the review step.
3. Read the `REVIEW RANGE` block. It names the base and tip and says where each came from.
4. Run the printed `git diff <base>..<tip> -- <owned paths>` to read the change. The commit list shows only this work package's implementation commits.
5. Check the `CITED REQUIREMENTS` block against the diff. There is no need to open `spec.md`.

If the block says `unavailable`, the reason names the missing record, for example a Mission created before window recording.
