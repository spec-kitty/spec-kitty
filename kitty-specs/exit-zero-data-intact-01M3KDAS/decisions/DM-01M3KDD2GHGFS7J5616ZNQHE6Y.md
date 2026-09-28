# Decision Moment `01M3KDD2GHGFS7J5616ZNQHE6Y`

- **Mission:** `exit-zero-data-intact-01M3KDAS`
- **Origin flow:** `specify`
- **Slot key:** `specify.intent.failure-policy`
- **Input key:** `failure_policy`
- **Status:** `resolved`
- **Created:** `2026-09-28T07:06:54.865798+00:00`
- **Resolved:** `2026-09-28T07:11:13.660585+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

Confirm the intent summary and pick the failure policy for the three open design points: #4933 dirty user meta.json at merge, #4940 undecodable .claude/settings.json, #4964 group-level migrate --dry-run

## Options

- Recommended defaults
- Other

## Final answer

Intent confirmed. #4933: refuse with non-zero exit before any reset; only spec-kitty's own mission metadata stays exempt. #4940: decode (BOM/UTF-16 and other tolerated encodings), reuse existing encoding libraries in the stack; a recently merged PR fixed a similar issue in the CLI runtime cycle JSON path; consider extracting a shared encoding helper into kernel. Undecodable files are left untouched with non-zero exit. #4964: honour group-level --dry-run/--force/--verbose by propagating to the subcommand; subcommands without a dry-run mode refuse with a usage error.

## Rationale

_(none)_

## Change log

- `2026-09-28T07:06:54.865798+00:00` — opened
- `2026-09-28T07:11:13.660585+00:00` — resolved (final_answer="Intent confirmed. #4933: refuse with non-zero exit before any reset; only spec-kitty's own mission metadata stays exempt. #4940: decode (BOM/UTF-16 and other tolerated encodings), reuse existing encoding libraries in the stack; a recently merged PR fixed a similar issue in the CLI runtime cycle JSON path; consider extracting a shared encoding helper into kernel. Undecodable files are left untouched with non-zero exit. #4964: honour group-level --dry-run/--force/--verbose by propagating to the subcommand; subcommands without a dry-run mode refuse with a usage error.")
