# Data Model: Quick-win remediation

No new persisted entity. The Mission tightens the accepted/refused input rules of existing files.

## Status event log row (`status.events.jsonl`)

| Rule | Before | After |
|---|---|---|
| Row boundary | any `str.splitlines()` separator | LF, CRLF or lone CR only |
| U+2028/U+2029/U+0085/VT/FF/FS/GS/RS inside a string | row split → "Invalid JSON" (strict) / dropped (lenient) | part of the row |
| Integer > 4300 digits, nesting too deep | raw `ValueError` / `RecursionError` | strict: `StoreError("Invalid JSON on line N: …")`; lenient: row skipped; seeding: `ValueError` |
| Written number NaN / ±Infinity | written as `NaN` / `Infinity` | refused (`StoreError` naming the event); file unchanged |
| Written line ending | platform text mode (CRLF on Windows) | LF on every OS |
| Byte rule | — | `json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"` = `spec_kitty_events` `serialize_record` |

Invariant: an append either writes every addition or none (refusal happens before the temp file is created).

## Sanitised event session fields

| `session_started_at` | `session_ended_at` | Result |
|---|---|---|
| aware | aware | `session_duration_s`, both removed (unchanged) |
| naive | naive | `session_duration_s`, both removed (unchanged) |
| naive | aware (or reverse) | both removed, no duration (was `TypeError`) |
| unparseable | any | both removed (unchanged) |

## WP task file (`<mission>/tasks/*.md`)

Matching rule (one authority, `core/wp_task_files.py`): name matches `^<WP id>(?:[-_.]|\.md$)` case-insensitively; `readme.md` never matches (any case).

| Matches | Dependency guard | Subtask roster | WP view / phase-1 mirror |
|---|---|---|---|
| 0 | declares nothing | `SubtaskRosterResolutionError` (missing) | no file |
| 1 regular file | read it | read it | read it |
| 1+ any non-regular (dir, dangling link) | unresolvable `TransitionError` | `SubtaskRosterResolutionError` (not a regular file) | no file |
| >1 | unresolvable `TransitionError` (ambiguous) | `SubtaskRosterResolutionError` (ambiguous) | no file |

## Subtask roster entry (`subtasks:` frontmatter list)

| Entry type | Result |
|---|---|
| `str` (stripped, non-empty) | accepted |
| `int` (not `bool`), ≤ 4300 digits | accepted as its decimal text |
| `int` > 4300 digits | refused: `SubtaskRosterResolutionError` subclass |
| `bool`, `float`, `date`/`datetime`, `None`, mapping, list | refused: same error, naming WP file, entry position, type and the expected form `- T001` |

Consumers: `for_review` gate (emit + CLI door) — refuse; `mark-status` owner map — refuses Mission-wide; advisory owner lookup — skips; WP view — empty authored list.

## Mission metadata (`meta.json`)

| Input | `load_meta` / `parse_meta_file` | `load_meta_strict(bom_tolerant=False)` | kernel `decode_meta` |
|---|---|---|---|
| UTF-8, no BOM | dict (unchanged) | dict | dict |
| UTF-8 with BOM | dict (was `ValueError` / `None`) | rejected (unchanged) | rejected (unchanged) |

## Glossary conflict record

One record per distinct `conflict_id`, in event order; a repeated resolved event for a known id adds nothing. Cost: one pass with a running id set.

## Archive correction (`tests/architectural/test_archive_root_byte_identical.py`)

`_OPERATOR_SANCTIONED_CORRECTIONS` gains the six Mission 058 WP paths, with a dated comment (operator decision 2026-11-10, #7442). Lifecycle: added in this PR → removed by a follow-up after the PR is on `main`.
