# Contract: Op Record Shape And Op-Commit Attribution

**Mission**: `op-record-model-and-coauthor-01M6EJV5` · **Issue**: #7013
**Owners**: `src/specify_cli/invocation/record.py` (record shape),
`src/specify_cli/invocation/executor.py` (commit message),
`src/specify_cli/git/commit_attribution.py` (trailer resolution)

## 1. The `started` event carries no model identifier

The first JSON line of `kitty-ops/<ULID>.jsonl` is an `OpStartedEvent`. Its
declared fields are unchanged **except** that `model_id` no longer exists:

| Field | Required | Notes |
| --- | --- | --- |
| `event` | yes | literal `"started"` |
| `invocation_id` | yes | 26-char Crockford ULID |
| `profile_id`, `action`, `actor`, `mode_of_work`, `started_at` | yes | non-empty / enumerated, unchanged |
| `governance_context_hash`, `governance_context_available` | yes | unchanged |
| `request_text` | yes | may be empty only in query mode (executor enforces) |
| `router_confidence`, `mission_id`, `wp_id` | no | omitted when absent, unchanged |
| ~~`model_id`~~ | — | **removed.** `actor` is the harness key and the only runtime identity the committed record carries. |

Rules:

- **R-1** No writer fills a model identifier. `to_jsonl_line()` omits `None`
  fields, so a record written after this change has no model key at all.
- **R-2** A line that still carries `model_id` (written before this change)
  validates; the undeclared key is dropped on parse and never re-serialised.
  No migration rewrites such a file.
- **R-3** The record remains `schema v2`: required fields, on-disk version and
  every reader are unchanged. Removing an optional key is not a version bump.

## 2. The auto-commit is attributed

`ProfileInvocationExecutor._commit_op_record` builds the message and appends the
trailer as its final paragraph:

```
op(<profile_id>): <action> [<invocation_id[:8]>]

Co-Authored-By: <Name> <email>
```

The doctor-sweep variant keeps its `(doctor sweep)` suffix on the subject and
gains the same trailer paragraph.

Resolution order (first non-empty wins):

1. the value passed to `complete_invocation(..., co_author=...)` — from
   `spec-kitty profile-invocation complete --co-author`;
2. `commit.co_author` in `.kittify/config.yaml`;
3. none — the message is the bare subject, exactly as before this change.

Rules:

- **R-1** A value is a display name plus an address, `Name <email>`; a value that
  already starts with `Co-Authored-By:` is accepted as a whole trailer and is
  not double-prefixed.
- **R-2** Empty or whitespace-only values are not a trailer: a CLI-supplied one
  is a usage error (exit 2, nothing written); a configured one is ignored.
- **R-3** A configured value that is present but does not parse as
  `Name <email>` (or `Co-Authored-By: Name <email>`) refuses the auto-commit:
  the outcome is `OpCommitOutcome(committed=False, refusal=...)` and the refusal
  text names `commit.co_author`. The close itself still succeeds; the completed
  event is already durable, and the record stays on disk uncommitted.
- **R-4** The trailer never applies to a commit the #6410 skip rules suppress,
  and never causes a second commit for an already-closed Op.

## 3. Claim-time model assertion

`_resolve_dispatch_binding` reads only fields the Op still owns
(`profile_id`, `mission_id`, `wp_id`, `action`).

- **R-1** A `--model` supplied with `--invocation-id` raises `ValueError` whose
  message says the Op record no longer carries a model, so `--model` must be
  omitted.
- **R-2** With no model resolved, the claim records `RESOLVED_MODEL_ABSENT`
  through the existing `ResolvedBinding.to_delta` path. No model string is
  fabricated and the frontmatter recommendation is never promoted to an actual.
