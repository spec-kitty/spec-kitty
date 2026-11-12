---
type: reference
updated: 2026-11-12
---

# Contract: the review-context block

This is the text block both review entry points print. Agents parse it by eye, so this file is a stable-shape contract, not a JSON schema. A renderer unit test compares it to golden files. Lines in `<…>` are filled in. Optional lines are marked `?`.

```
REVIEW RANGE (WP02): <base12>..<tip12>  [recorded | derived | unavailable]
  base: <base12> (<window open | claim base ref | claim event commit>)
? note: recorded window not used: <gap reason>
  tip:  <tip12> (<for_review submission | for_review event commit>)
? note: <branch> has moved <N> commit(s) past the submitted tip
IMPLEMENTATION COMMITS (<n>, <m> bookkeeping-only omitted):
  <sha12> <subject>
? … <k> more (see git log command)
CHANGED FILES (owned files, +added -removed):
  +<a> -<r>  <path>
? … <k> more files
? OUTSIDE OWNED FILES (review rationale required): <path>, <path>, …
REVIEW COMMANDS:
  git log --oneline <base>..<tip> [-- <owned pathspecs>]
  git diff <base>..<tip> [-- <owned pathspecs>]
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
- Truncation bounds:
  - commits: 20 shown;
  - files: 40 shown;
  - out-of-map paths: 20 shown;
  - requirement text: 600 characters each.
- The order is deterministic: commits oldest first, files and paths sorted.
- `OWNED_REVIEW_BASE_UNAVAILABLE` (owned checkouts) is unchanged, and so is the anti-pattern checklist that follows the block.
