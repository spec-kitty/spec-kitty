---
title: Profile Invocation Reference
description: Reference for dispatch, profile-invocation complete, invocation trail fields, and lifecycle states.
doc_status: active
updated: '2026-06-15'
related:
- docs/context/charter-overview.md
---
# Profile Invocation Reference

Profile invocation is the local audit-trail mechanism used by standalone
`spec-kitty dispatch` calls. Each dispatch loads Charter context, opens an Op,
and writes an append-only JSONL record. For an explanation of the model, see
[Understanding Governed Profile Invocation](../architecture/governed-profile-invocation.md).

`spec-kitty next` is the canonical mission loop. In the current 3.2.x CLI it
issues governed prompt files and separate mission-step lifecycle records; it
does not open these standalone Op JSONL files directly.

---

## spec-kitty dispatch

**Synopsis**: `spec-kitty dispatch [OPTIONS] REQUEST`

**Description**: Dispatch a natural-language request to a governed Op. The
router picks the best profile by default. Pass `--profile` only when the caller
has a specific profile in mind or needs to bypass routing.

| Argument/Flag | Description |
|---|---|
| `REQUEST` | Natural-language request [required] |
| `--profile TEXT` | Optional profile ID; bypasses routing |
| `--json` | Output JSON payload |

**Example**:
```bash
uv run spec-kitty dispatch "Review this implementation approach" --json
uv run spec-kitty dispatch "Implement token validation" --profile implementer-ivan --json
```

---

## spec-kitty profile-invocation complete

**Synopsis**: `spec-kitty profile-invocation complete [OPTIONS]`

**Description**: Close an open invocation record. This is the signal that closes
the invocation trail. Call it when execution finishes to append a `completed`
event to the trail file.

| Flag | Description |
|---|---|
| `--invocation-id`, `-i TEXT` | Invocation ULID to close [required] |
| `--outcome TEXT` | `done`, `failed`, or `abandoned` [required] |
| `--evidence TEXT` | Path to a UTF-8 text evidence file (Tier 2 promotion). Accepted for evidence-eligible records. |
| `--artifact TEXT` | Path to an artifact produced by this invocation (repeatable) |
| `--commit TEXT` | Git commit SHA most directly produced by this invocation (singular) |
| `--json` | Output JSON payload |

**Example**:
```bash
uv run spec-kitty profile-invocation complete \
  --invocation-id 01KQABCDEF1234567890 \
  --outcome done \
  --artifact docs/guides/my-guide.md \
  --commit abc123def456

uv run spec-kitty profile-invocation complete \
  --invocation-id 01KQABCDEF1234567890 \
  --outcome failed
```

---

## Invocation Trail Fields

Trail records are stored in `kitty-ops/{invocation_id}.jsonl`. Each file
contains a `started` event and, once closed, a `completed` event. It may also
contain additional append-only events such as `glossary_checked`,
`artifact_link`, or `commit_link`.

### started event fields

| Field | Type | Description |
|---|---|---|
| `invocation_id` | ULID string | Unique identifier for this invocation |
| `event` | string | `started` |
| `profile_id` | string | Resolved profile identifier |
| `action` | string | Action token resolved for governance context |
| `request_text` | string | Natural-language request supplied to `dispatch` |
| `governance_context_hash` | string | First 16 hex characters of the rendered Charter context SHA-256 |
| `governance_context_available` | boolean | Whether Charter context was available when the record was opened |
| `actor` | string | Caller identity such as `operator`, `claude`, or `codex` |
| `router_confidence` | string/null | Router confidence for auto-routed requests |
| `started_at` | ISO 8601 timestamp | When the invocation was opened |
| `mode_of_work` | string | `task_execution`, `mission_step`, or `query` |

### completed event fields

| Field | Type | Description |
|---|---|---|
| `event` | string | `completed` |
| `invocation_id` | ULID string | Matches the `started` event |
| `outcome` | string | `done`, `failed`, or `abandoned` |
| `completed_at` | ISO 8601 timestamp | When `profile-invocation complete` was called |
| `closed_by` | string | `agent` or `doctor_sweep` |
| `evidence_ref` | string/null | Evidence path or text supplied with `--evidence` |

### correlation events

When `--artifact` or `--commit` is supplied to `profile-invocation complete`,
the CLI appends separate correlation events after the completed record:

| Event | Key fields | Description |
|---|---|---|
| `artifact_link` | `kind`, `ref`, `at` | Repo-relative or absolute artifact reference |
| `commit_link` | `sha`, `at` | Primary git commit SHA |

---

## Lifecycle States

An invocation passes through two durable states:

1. **open**: A `started` event has been written. The invocation ID is
   available. Execution has not yet completed.
2. **closed**: `profile-invocation complete` has been called. A `completed`
   event with the final outcome is appended to the trail file.

An invocation that was opened but never completed is stale. Use
`spec-kitty invocations list` to find open records.

---

## Mode-of-work Enforcement

`--evidence` on `profile-invocation complete` is enforced against the
invocation's `mode_of_work`. Attempting to promote evidence on a non-eligible
record results in `InvalidModeForEvidenceError`, and no write occurs. Re-run
`complete` without `--evidence` to close the invocation cleanly.

Evidence must be UTF-8 text. A file that is not (for example a PNG screenshot),
or inline text that cannot be encoded as UTF-8, is refused **before any write**
with `complete_failed` (exit 1) and the message "No completion was recorded".
The invocation stays open, so re-run `complete` with a text evidence file. A
path that cannot be read, or a relative path that escapes the repository, is
still stored as the inline text you passed.

| mode_of_work | Tier 2 evidence (`--evidence`) eligible |
|---|---|
| `task_execution` | Yes |
| `mission_step` | Yes |
| `query` | No |

---

## Example Trail Record

```jsonl
{"event":"started","invocation_id":"01KQA1B2C3D4E5F6G7H8J9K0","profile_id":"implementer-ivan","action":"implement","request_text":"Implement token validation","governance_context_hash":"0123abcd4567ef89","governance_context_available":true,"actor":"operator","started_at":"2026-04-29T10:00:00Z","mode_of_work":"task_execution"}
{"event":"completed","invocation_id":"01KQA1B2C3D4E5F6G7H8J9K0","completed_at":"2026-04-29T10:45:00Z","outcome":"done","closed_by":"agent"}
{"event":"artifact_link","invocation_id":"01KQA1B2C3D4E5F6G7H8J9K0","kind":"artifact","ref":"src/auth/token.py","at":"2026-04-29T10:45:02Z"}
{"event":"commit_link","invocation_id":"01KQA1B2C3D4E5F6G7H8J9K0","sha":"abc123def456789","at":"2026-04-29T10:45:03Z"}
```

---

## See Also

- [Understanding Governed Profile Invocation](../architecture/governed-profile-invocation.md)
- [How to Run a Governed Mission](../guides/how-to/governance/run-governed-mission.md)
- [How Charter Works](../context/charter-overview.md)
