---
name: spec-kitty
description: >-
  Standalone Spec Kitty governance invocation: run Spec Kitty when the user
  indicates they want Spec Kitty involved, load governance context, open an Op,
  do the work under that context, and close the Op with the real outcome.
  Documents dispatch, profiles list, invocations list, and
  profile-invocation complete. Triggers: "use spec kitty to", "hey spec kitty",
  "spec kitty <anything>", ad-hoc requests that are not part of a running full
  mission workflow.
---

# spec-kitty

Use this skill when the user seems to want Spec Kitty involved and the request
is not clearly a full mission workflow.

Spec Kitty does not spawn another LLM. You are the host. Spec Kitty routes the
request, assembles governance context, opens an Op record, and returns. You then
do the work under that governance context and close the Op with the real
outcome.

## Default Mental Model

If the user says anything like "use spec kitty to ...", "hey spec kitty ...",
"spec kitty fix ...", or "spec kitty <anything>", treat it as a standalone
governed invocation unless they clearly ask for a full mission.

Run:

```bash
spec-kitty dispatch "<request verbatim>" --json
```

If the user names a specific profile, or you have a strong reason to bypass
routing, pass it explicitly:

```bash
spec-kitty dispatch "<request verbatim>" --profile <profile-id> --json
```

Do not answer directly before dispatching. The point is to load governance and
record the Op before doing the work.

When the user asks to show, explain, compare, map, or visualize the governed
work—or when dense prose hides its structure—also load `spk-doctrine-show-me`.
Use its smallest-useful-visual rule while keeping the dispatch lifecycle here
authoritative.

## The open->work->close contract

Every standalone invocation follows the same three-step lifecycle:

1. **Open** — `spec-kitty dispatch` opens the Op and loads governance context.
   It does not do the work and it does not close the Op.
2. **Work** — read `governance_context_text` and do the work under that binding
   context.
3. **Close** — close the Op with the real outcome:

   ```bash
   spec-kitty profile-invocation complete \
     --invocation-id <id> \
     --outcome <done|failed|abandoned> [--evidence <path>]
   ```

Failed work closes as `failed`; dropped work closes as `abandoned`. Never leave
an Op open deliberately. `spec-kitty doctor ops` reports orphaned open Ops, and
`spec-kitty doctor ops --close-stale` sweeps stale ones closed as `abandoned`
with `closed_by: doctor_sweep`.

## Usage

### Discover profiles

```bash
spec-kitty profiles list --json
```

Profiles are an optional routing escape hatch, not the primary UX.

### Open a governed invocation

```bash
spec-kitty dispatch "implement WP03" --json
spec-kitty dispatch "review this migration" --profile reviewer --json
```

Response fields:

| Field | Type | Description |
|-------|------|-------------|
| `invocation_id` | string (ULID) | Unique ID for this Op |
| `profile_id` | string | Resolved profile identifier |
| `action` | string | Normalised action string |
| `governance_context_text` | string | Full governance context assembled from the project DRG |
| `governance_context_hash` | string | SHA-256 hash of `governance_context_text` |
| `governance_context_available` | boolean | `false` when charter has not been synthesised |
| `router_confidence` | string or null | Routing confidence score |
| `status` | `"open"` | The Op is open until you close it |
| `close_contract` | object | Exact close command, accepted outcomes, and flags |

### Governance context injection

After calling `dispatch`, the response includes `governance_context_text`.

You must inject this text into your working context before executing the task.

Steps:
1. Read `governance_context_text` from the JSON response.
2. Add the text to the beginning of your task execution context. Treat it as
   binding governance: follow any directives, constraints, and guidelines it
   contains when generating code, plans, or analyses.
3. If `governance_context_available` is `false`, note it to the user
   ("governance context unavailable — run `spec-kitty charter synthesize` to
   build the DRG") but proceed with the task. The Op trail is still recorded.
4. After completing the work, close the Op.

### Close the Op

```bash
spec-kitty profile-invocation complete \
  --invocation-id <id> \
  --outcome <done|failed|abandoned>
```

`--outcome` is required and must reflect what actually happened: `done` for
completed work, `failed` for work that did not succeed, `abandoned` for work
that was dropped. Optional flags: `--evidence <path>`, `--artifact <ref>`,
`--commit <sha>`.

### After closing

When a human is in the loop, run the Feedback Survey Check once, only after
closing the Op with outcome `done` or `failed` (never `abandoned`). Skip it
entirely in unattended runs; never answer on the human's behalf:

```bash
spec-kitty feedback --agent-check --trigger op_close --agent <your-agent-key> --json
```

If `action` is `none`, continue silently. If `action` is `prompt`, ask with
host-native UI using the JSON `survey` wording, then ask "Send feedback?" and
record with `--agent-submit ... --consent yes` (without `--consent yes` nothing
is sent) or `--agent-choice skip|never`.

### Review recent invocations

```bash
spec-kitty invocations list --json
spec-kitty invocations list --profile <profile-id> --json
spec-kitty invocations list --limit 10 --json
```

## What Gets Recorded

Every `dispatch` call writes one JSONL file to
`kitty-ops/<invocation_id>.jsonl` with a `started` event. Closing the Op appends
a `completed` event carrying the real `outcome` and `closed_by`.

An Op without a `completed` event is an orphan: visible in
`spec-kitty invocations list` as `open`, reported by `spec-kitty doctor ops`,
and surfaced at session boundaries.

## Invariants

- `dispatch` never spawns a separate LLM call.
- `dispatch` opens the Op and returns. The working agent closes it with the
  real outcome.
- `governance_context_text` is assembled from the project DRG; no network calls
  are made if the charter has already been synthesised.
- If `governance_context_available` is `false`, run
  `spec-kitty charter synthesize` to build the DRG before the next invocation.
