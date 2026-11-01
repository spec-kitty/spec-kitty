# Approach

## 2026-11-01 — seed
Mechanical migration by one committed, idempotent script; readers ported in the same PR; ATDD per WP (body-hash test first). Sequential WPs on a `single_branch` mission in the repository root checkout: the work is one corpus and one script, so lane isolation buys nothing and lane merges of ~700 frontmatter edits would only add conflict surface.

## 2026-11-01 — exclusion verified before specifying
A control build in `/tmp` proved doc-kitty's native `exclude` skips schema validation, so slice 3 shrank from "backfill 31 pages" to "no edit".
