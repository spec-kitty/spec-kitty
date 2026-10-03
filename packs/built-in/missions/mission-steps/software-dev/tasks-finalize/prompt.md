---
description: Validate dependencies, finalize WP metadata, and commit all task artifacts.
---
# /spec-kitty.tasks-finalize - Finalize Tasks

**Version**: 3.2.0

## Purpose

Run the finalization command to parse dependencies from `tasks.md`, validate
them, update WP frontmatter, and commit all task artifacts to the target branch.

---

## 📍 WORKING DIRECTORY: Stay in planning repository

**IMPORTANT**: This step works in the planning repository. NO worktrees created.

## User Input

```text
$ARGUMENTS
```

## Steps

### 1. Run Validate-Only Preflight

**CRITICAL**: Run this preflight command from repo root before any mutating
finalization:

```bash
spec-kitty agent mission finalize-tasks --validate-only --mission <mission-slug> --json
```

This command will:

- Parse dependencies from tasks.md
- Parse `Requirement Refs` from tasks.md
- Preview WP frontmatter updates without writing files
- Validate dependencies (check for cycles, invalid references)
- Validate requirement mapping:
  - Every WP has at least one accepted requirement reference (a declared FR, NFR, C or SC; a `<mission-slug>#<ID>` citation does not count)
  - Every ref gets one verdict: `malformed` and `unknown_spec_id` fail; `foreign_qualified` (another mission's ID) never fails; valid refs always count
  - Every functional requirement declared in spec.md (`FR-###`, including one with a lowercase letter suffix such as `FR-###a`) is mapped to at least one WP
  - Declared success criteria (`SC-###`) are tracked, not gating: they appear in `success_criteria_coverage` but never fail validation
- Keep every authored `requirement_refs` item: finalize never erases or rewrites refs

If the JSON output contains `"error": "Requirement mapping validation failed"`,
do **not** run finalization. Report the blocking fields
(`missing_requirement_refs_wps`, `unknown_requirement_refs`,
`unmapped_functional_requirements`, and `rejected_requirement_refs` with each
ref's reason), compare them with `parsed_spec_ids` (the IDs finalize read from
spec.md, grouped by kind), then fix mappings with
`spec-kitty agent tasks map-requirements --mission <mission-slug> --json` or by
updating WP `requirement_refs`.

### 1b. Ownership Overlap — domain-focused / refactor missions

If validate-only fails with `"error": "Ownership validation failed"` and
`ownership_errors` listing overlapping `owned_files`:

**Ownership collisions are EXPECTED for domain-focused and refactor-oriented
missions** (cross-cutting strangler work, repo-wide migrations, boundary
enforcement) where many work packages legitimately edit the same files. This is
not a defect in the slicing. Handle it as follows:

1. **Linearize shared surfaces (execution safety).** Work packages that touch the
   same files MUST be made dependent/linear (via `Depends on WPxx`) so they
   execute sequentially in one lane and **share a single worktree** (or run
   direct-to-branch). Limited parallelism is acceptable and expected for these
   missions — do not force artificial parallelism. Note: linearization protects
   the *worktree* from concurrent edits; it does **not** by itself satisfy
   ownership validation (see step 3).
2. **Declare cross-cutting WPs codebase-wide (the exemption).** A WP that is
   expected to overlap broadly should carry `scope: codebase-wide` in its
   frontmatter; the ownership validator exempts codebase-wide WPs from overlap
   and authoritative-surface checks. Keep the genuinely-targeted WPs (single test
   file, single module) narrow and mutually disjoint.
3. **`codebase-wide` is the ONLY exemption.** Two *narrow* WPs that claim the same
   files **always** fail ownership validation — regardless of whether they sit in
   different lanes or are linked in a dependency hierarchy. Dependency/lane
   structure never bypasses the overlap check. If WPs legitimately share a
   surface, mark the broadly-overlapping one `scope: codebase-wide`; otherwise
   re-slice so the narrow WPs are disjoint.

Do **not** fabricate disjoint `owned_files` that misrepresent which WP edits
which files solely to pass validation — linearize and/or declare codebase-wide
instead.

### 2. Run Finalization Command

Only after validate-only exits successfully, run the mutating finalization
command from repo root:

```bash
spec-kitty agent mission finalize-tasks --mission <mission-slug> --json
```

This command will update WP frontmatter, compute lanes, and commit all tasks to
the target branch.

### 3. Check Output

The JSON output includes:

- `"commit_created": true/false` — whether a commit was made
- `"commit_hash"` — the commit hash if created
- `"wp_count"` — number of WP files processed
- `"dependencies_parsed"` — dependency relationships found
- `"requirement_refs_parsed"` — requirement reference mapping found
- `"ownership_warnings"` — soft warnings (glob-pattern zero-match, audit coverage)
- `"parsed_spec_ids"` — requirement IDs parsed from spec.md, grouped as `functional`, `non_functional`, `constraint`, `success_criteria`
- `"rejected_requirement_refs"` — per WP, each unusable ref with one reason: `malformed`, `unknown_spec_id` or `foreign_qualified`
- `"success_criteria_coverage"` — informational: `referenced` (SC → WPs) and `unreferenced`; never fails the run
- Validation details when checks fail (`missing_requirement_refs_wps`, `unknown_requirement_refs`, `unmapped_functional_requirements`, `rejected_requirement_refs`)

**CRITICAL — Ownership warnings require action before proceeding:**

If `ownership_warnings` is non-empty, or if the command emits `ERROR: Ownership`
lines to stderr, you MUST act on each issue before starting implementation:

- **Hard error** (`ownership_literal_path_errors` present, exit 1): A
  `owned_files` entry is a literal file path that does not exist in the
  repository. Fix by:
  1. Correcting the path (typo / wrong relative path), or
  2. Adding the path to `create_intent` in the WP frontmatter if the file will
     be created by this WP (planned-new-file).

  **Do NOT proceed to implement while any hard error is present.**

- **Soft warning** (`ownership_warnings` non-empty, exit 0): A `owned_files`
  glob pattern matched zero files. This may indicate in-flight work. Verify the
  pattern is correct and adjust if needed before starting implementation.

Example `create_intent` frontmatter for a planned-new-file entry:

```yaml
owned_files:
  - "src/specify_cli/new_module.py"
create_intent:
  - "src/specify_cli/new_module.py"  # will be created by this WP
```

### 4. Verify

**IMPORTANT — DO NOT COMMIT AGAIN AFTER THIS COMMAND**:

- `finalize-tasks` commits the files automatically
- If `commit_created=true`, files are ALREADY committed — do not run `git commit` again
- Other dirty files shown by `git status` (templates, config) are UNRELATED
- Verify using the `commit_hash` from JSON output, not by running `git add/commit` again

### 5. Report

Provide a concise outcome summary:

- Path to `tasks.md`
- Work package count and per-package subtask tallies
- Parallelization highlights
- MVP scope recommendation
- Finalization status (dependencies parsed, X WP files updated, committed to target branch)
- Next suggested command (e.g., `/spec-kitty.analyze` or `/spec-kitty.implement`)

## Output

After completing this step:

- All WP files have `dependencies` field in frontmatter
- All WP files have `requirement_refs` field in frontmatter
- Dependencies are validated (no cycles, no invalid references)
- Requirement references are validated against spec.md
- Task artifacts are committed to the target branch

**Next step**: `spec-kitty next --agent <name>` will advance to implementation.

<!-- spec-kitty:feedback-survey-check:begin -->
## Feedback Survey Check

Run this once per session, only after the command above has succeeded, and only when a human is in the loop (skip it entirely in unattended or automated runs):

```bash
spec-kitty feedback --agent-check --trigger planning_complete --agent <your-agent-key> --json
```

If JSON `action` is `none`, continue silently; do not mention the survey.
If `action` is `prompt`, ask the human using your host-native question UI (plain text if you have none), with the exact wording from the JSON `survey` object: the rating (1-5), the optional comment, and the optional email. Then ask the consent question "Send feedback?". Offer "Skip" and "Don't ask again" at the first question. Never answer on the human's behalf and never pre-fill answers. If the comment is longer than `comment_max_length`, tell the human it will be cut before asking for consent.

Record exactly one result:

```bash
spec-kitty feedback --agent-submit --trigger planning_complete --agent <your-agent-key> --rating <1-5> [--comment '<text>'] [--email '<address>'] --consent yes --json
spec-kitty feedback --agent-choice skip --trigger planning_complete --json    # human skipped or declined
spec-kitty feedback --agent-choice never --trigger planning_complete --json   # human chose "Don't ask again"
```

Pass `<text>` and `<address>` as single-quoted shell arguments, writing each `'` inside them as `'\''`, and collapse newlines to spaces; never put the human's words in double quotes (`$(...)` and backticks would run).

Show the returned `message` if present, then continue. Never report delivery problems: sending is fire-and-forget.
<!-- spec-kitty:feedback-survey-check:end -->
