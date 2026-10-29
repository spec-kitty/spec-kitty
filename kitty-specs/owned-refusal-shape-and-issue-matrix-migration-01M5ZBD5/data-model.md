# Data Model: Owned-checkout issue-verdict cleanup

## Owned refusal payload (JSON mode, stdout, exit 1)

| Key | Type | Presence | Rule |
|---|---|---|---|
| `ok` | boolean | always | always `false` |
| `error` | object | always | exactly two keys: `code`, `message` |
| `error.code` | string | always | a registered owned refusal code on every renderer path; the move-task catch-all may carry any `ActionContextError` code (unchanged posture) |
| `error.message` | string | always | non-empty, human-readable |
| `context` | object | optional | command-specific facts; absent when the command has none |
| `spec_kitty_version` | string | optional | present exactly when the command stamps every payload with it |

No other top-level key is allowed. In particular there is no top-level `error_code`,
`success`, `result`, `status`, `code` or `message`.

Invariants:
- An owned refusal writes no file in either checkout (NFR-004).
- Human mode is unchanged: `Error: [<code>] <message>` on stderr, exit 1.
- Non-owned errors and success payloads are unchanged (FR-011).

## `context` per command

| Command | `context` keys | `spec_kitty_version` |
|---|---|---|
| `agent mission setup-plan` | `phase_complete: false` | yes |
| `agent mission finalize-tasks` | -- | yes |
| `agent [mission] check-prerequisites` | -- | yes |
| `agent mission record-analysis` | -- | yes |
| `agent mission create` | -- | yes |
| `agent tasks mark-status` (edge refusal and in-command owned failure) | `state_applied`, `event_ids`, `applied_wps`, `destination_ref`, `status_events_path`, `status_snapshot_path`, `dirty` | no |
| `spec-commit` | `committed: false` | no |
| every other in-scope command | -- | no |

## Legacy issue matrix migration

- Input: an owned Mission (validated `OwnedCheckout` fact) whose owned checkout holds
  `kitty-specs/<mission>/issue-matrix.md` and no `issue-matrix.json`.
- Output: `issue-matrix.json` written in the owned checkout's Mission directory, holding
  every legacy row plus the newly recorded verdict; the legacy `.md` stays in place
  (historical residue, unchanged rule).
- Non-owned Missions: unchanged (repository-root write).
