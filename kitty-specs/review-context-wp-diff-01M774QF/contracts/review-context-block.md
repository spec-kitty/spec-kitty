---
type: reference
updated: 2026-11-12
---

# Contract: the review-context block

This is the text block both review entry points print. Agents parse it by eye, so this file is a stable-shape contract, not a JSON schema. A renderer unit test compares it to golden files. Lines in `<…>` are filled in. Optional lines are marked `?`.

```
REVIEW RANGE (WP02): <base12>..<tip12>  [recorded | derived | unavailable]
  base: <base12> (<window open | opener lane_head stamp | claim base ref | claim event commit>)
? note: recorded window not used: <gap reason>
? scope: unscoped (no owned_files declared)
  tip:  <tip12> (<for_review submission | for_review event commit>)
? note: <branch> has moved <N> commit(s) past the submitted tip
IMPLEMENTATION COMMITS (<n>; = output of the git log command below):
  <sha12> <subject>
? … <k> more (see git log command)
CHANGED FILES (owned files, +added -removed):
  +<a> -<r>  <path>
? … <k> more files
? OUTSIDE OWNED FILES (<p> path(s) changed in the range; <q> commit(s) touch no owned file; review rationale required): <path>, <path>, …
REVIEW COMMANDS:
  git log --oneline <base>..<tip> -- <listing pathspecs>
  git diff <base>..<tip> -- <listing pathspecs>
CITED REQUIREMENTS:
  FR-003 — <title>: <statement>
  NFR-001 — <text>
? C-009 — not declared in this Mission's spec
? other-mission#FR-002 — cites another Mission (not resolved here)
```

When no range can be determined:

```
REVIEW RANGE (WP02): unavailable — <reason>
REVIEW COMMANDS:
  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)
```

## Rules

- A full SHA is used inside commands. Labels may abbreviate to 12 characters.
- Byte budget: the block, without CITED REQUIREMENTS and without the REVIEW COMMANDS lines, is at most 4,096 bytes (NFR-001, ruling Q11). The command lines are exempt: they are always printed in full so they run verbatim over the listing pathspecs, so a work package that owns many files can exceed 4,096 bytes in total. Lists are filled in order (commits, files, out-of-map) until the budget is reached. The rest of each list is replaced by one `… <k> more` line. The header, provenance and command lines are always kept.
- Requirement text: 600 characters each (NFR-003).
- The commit list equals the printed `git log` command's output: both use one value, the listing pathspecs. With `owned_files` declared, these are the owned-file glob pathspecs plus an `:(exclude)<prefix>*` for each bookkeeping prefix (the status-only prefixes of `status_only_excluded_prefixes`, `.kittify/` included, and the Mission's `tasks.md`) that an owned glob can reach; a glob reaches a prefix when one of the two is a prefix of the glob's literal lead (its text before the first wildcard). With no `owned_files` (unscoped), they are `.` plus an `:(exclude)<prefix>*` for every status-only prefix. Commits that touch only bookkeeping paths therefore never appear. The OUTSIDE OWNED FILES line counts two different things: `<p>` is the number of out-of-map paths the range's tree diff (`base..tip`) changed, whichever commits changed them; `<q>` is the number of non-bookkeeping commits that touch no owned file (the range's commits missing from the commit list). A path changed by a commit that also touches an owned file counts in `<p>`, and its commit does not count in `<q>`.
- The moved-past note counts non-bookkeeping commits only.
- The order is deterministic: commits oldest first, files and paths sorted.
- `OWNED_REVIEW_BASE_UNAVAILABLE` (owned checkouts) is unchanged, and so is the anti-pattern checklist that follows the block.
