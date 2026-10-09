## PROCEDURE_issue_matrix_autoscaffold

`issue-matrix.md` is a gate-required mission artifact per FR-037 of
the `spec-kitty-mission-review` skill (Gate 4). The post-merge
mission-review audit FAILs the mission if the matrix is missing, or
if any row has an empty/`unknown` verdict, or if a
`deferred-with-followup` row lacks a follow-up handle.

At `/spec-kitty.tasks` (or `finalize-tasks`) generation time:

1. Scan `spec.md` and `tasks.md` for GitHub issue references:
   - `#NNN` style links
   - Full `https://github.com/.../issues/NNN` URLs
   - `external_ref:` declarations in WP frontmatter
2. Deduplicate the issue set across all sources.
3. If the set is non-empty, scaffold
   `kitty-specs/<slug>/issue-matrix.md` with:
   - Header pointing at the canonical issue-matrix schema (inline
     the schema docs from the mission-review skill).
   - One pre-populated row per referenced issue with columns:
     `issue` (linked), `repo`, `title` (fetched via `gh issue view`
     if `gh` is authenticated, else blank), `verdict` (blank),
     `evidence_ref` (blank).
   - A note section explaining that operators fill in `verdict` and
     `evidence_ref` as the investigation completes.
4. Commit the scaffold as part of the finalize-tasks commit.

### Reference cases

- spec-kitty PR #1160 — mission referenced #1141 and #1142
  explicitly; matrix was authored during mission-review pass
  (commit f37053cb5) as a fix-up rather than during planning.
- Filed as spec-kitty#1163 (engineering implementation tracker).
