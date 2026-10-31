# CLI Contract: `spec-kitty events tail`

The command is ADR 2026-10-13-2 D-2's local subscriber: it follows one ledger
by cursor. This contract extends the WP04 contract
(`kitty-specs/event-push-watch-channel-01M1K6W2`) with the `--log` selector
(#6611) and makes `--json` meaningful.

## Command

```
spec-kitty events tail --mission <slug> [--log <kind>] [--json] [--once]
                       [--max-events <n>] [--from-offset <n>] [--from-invariant <sha256>]
```

Registered as the `events` Typer sub-app
(`src/specify_cli/cli/commands/events.py`), mounted as `events tail`. The shell
owns no poll loop and no direct `time.sleep` (unchanged NFR-001); polling
stays in `status/tail_reader.py`.

## Arguments & options

| Name | Kind | Required | Behavior |
|------|------|----------|----------|
| `--mission` | `str` | yes | Mission slug/handle (no legacy feature-alias flag, C-003). Resolution and `mission_not_found` behaviour unchanged. |
| `--log` | choice | no (default `status`) | Which canonical ledger to follow: `status` \| `decisions` \| `mission` \| `run` \| `glossary` \| `ops` \| `canonical`. Unknown value → Typer usage error (exit 2) before any file access. |
| `--json` | flag | no (default off) | Emit one JSON line per event (byte-identical to the pre-#6611 output, incl. the reader-injected `tail_offset`/`tail_invariant` cursor keys). Without it, one human-readable plain-text line per event. |
| `--once` | flag | no | Poll exactly once and exit (unchanged). |
| `--max-events` | `int` | no | Stop after N events/signals (unchanged). |
| `--from-offset` | `int` | no | Resume from this byte offset **in the selected log**. Unchanged semantics, new path. |
| `--from-invariant` | `str` | no | SHA-256 content invariant paired with `--from-offset`; alone it is a `usage_error` (unchanged). |

## Log kinds and their paths

| Kind | Path | Notes |
|------|------|-------|
| `status` (default) | `<resolved status surface>/status.events.jsonl` | Unchanged behaviour, incl. coordination-surface routing (#5466). |
| `decisions` | `<resolved status surface>/decisions.events.jsonl` | Same resolved surface as `status` (both streams are coordination-partition). |
| `mission` | `<feature_dir>/mission-events.jsonl` | Mission v1 events. |
| `run` | latest matching `.kittify/runtime/runs/<run_id>/run.events.jsonl` | The run whose `state.json` names the mission (`mission_id`, legacy `mission_slug` fallback), most recently modified. |
| `glossary` | `.kittify/events/glossary/<mission_id>.events.jsonl` | The mission's glossary event log. |
| `ops` | `kitty-ops/lifecycle.jsonl` | Op lifecycle log (project-scoped). |
| `canonical` | `.kittify/canonical-events.jsonl` | Project canonical events. |

A not-yet-created log (any kind) is waited for, not an error: `--once` prints
nothing and exits 0; a stream starts when the first write materializes the
file.

## Output shapes

### `--json` (machine)

One `print(json.dumps(event))` line per event, in file order, exactly the
pre-#6611 shape — every pass-through event plus the reader-injected sibling
keys `tail_offset` (byte offset after the line) and `tail_invariant`
(SHA-256 of the line), and `log_truncated` signal envelopes on resync.

### default (human)

One plain-`print` line per event (no Rich markup, no ANSI on stdout):

```
<timestamp|at|-> <event_type|type|-> <compact JSON of the payload, keys sorted>
```

- The reader-injected `tail_offset`/`tail_invariant` keys are omitted (cursor
  plumbing, not content).
- A `log_truncated` signal renders as
  `log truncated (<reason>) at offset <n> — resynced from offset 0`.
- Rendering is deterministic: the same event dict always renders to the same
  line.
- Line length is capped at 400 characters; an over-long line is truncated
  to 400 characters plus a trailing `...` (bounds terminal noise on large
  payloads; the `--json` stream is never truncated).

## Dispatch order

usage check → repo root → mission resolve → kind dispatch → status-surface
resolution (only `status`/`decisions`) → log path resolution (incl. the
`run` kind's refusal) → resume validation → stream. A broken coordination
surface never blocks the project-scoped (`ops`, `canonical`, `glossary`) or
primary-partition (`mission`, `run`) kinds.

## Error envelopes (stderr, unchanged channel and shape)

| `error` | Trigger | Exit |
|---------|---------|------|
| `usage_error` | `--from-invariant` without `--from-offset` | 2 |
| `repo_root_not_found` | not inside a project | 1 |
| `mission_not_found` | unresolvable slug (from `resolve_mission_handle`) | 2 |
| `status_surface_unavailable` | surface resolver fails closed (`status`/`decisions` kinds) | 1 |
| `run_log_unavailable` (new) | `--log run` and no run journal belongs to the mission | 1 |
| `invalid_resume_offset` / `resume_content_mismatch` | refused resume against the selected log | 2 |

No Tail envelope is ever printed to stderr; no event line is ever printed
there either.

## Behavioral contract

| # | Given | When | Then |
|---|-------|------|------|
| 1 | a mission with decision rows on its resolved surface | `events tail --mission <s> --log decisions --once --json` | the decision rows print as JSON lines, exit 0 |
| 2 | same fixture | `events tail --mission <s> --log decisions --once` | one human line per row; output differs from row 1's JSON |
| 3 | same fixture, status kind | `... --once --json` | byte-identical to the pre-#6611 command output |
| 4 | `--log run`, two runs for the mission (one older) | `... --log run --once --json` | the newer run's journal is tailed |
| 5 | `--log run`, runs exist only for another mission | `... --log run --once` | `run_log_unavailable` envelope on stderr, exit 1, nothing on stdout |
| 6 | `--log glossary`/`ops`/`canonical`, log absent | `... --once` | prints nothing, exit 0 (waits in stream mode) |
| 7 | `--log decisions --from-offset 999999` | `... --once` | `invalid_resume_offset` envelope on stderr, exit 2 |
| 8 | `--log bogus` | any invocation | Typer usage error, exit 2, no file access |
| 9 | `--from-invariant` without `--from-offset`, any kind | any invocation | `usage_error` envelope, exit 2, before file access |
| 10 | surface resolver fails closed | `... --log ops --once` | tails `kitty-ops/lifecycle.jsonl` normally (lazy surface resolution); with `--log status`/`decisions` the `status_surface_unavailable` refusal applies |
