# Data Model: Status contract readers

> **Phase split (operator decision 2026-10-27, Decision Moment `01M5ZD4PNEEMAFHA7SN4VJZR2N`).** `spec-kitty-events` 11.0.0's reducer decoder (`diary.decode_actor`) accepts only the 4-key actor `{tool, role, profile, model}`, and every status read goes through it. This mission therefore WRITES the 4-key structured actor on every agent/operator path, with `profile` taken only from asserted sources (dispatch invocation → `--profile` → compact `--agent` segment → null). The WP-frontmatter fill and the `profile_source` key are deferred to a follow-up that first ships an events release whose decoder accepts the fifth key (readers first), then flips the CLI writers through an explicit pin-floor bump (never an automatic capability gate: committed logs are shared across clones on different installs). The CLI-side readers in this mission (`decode_actor` accepting the 5-key shape, `actor_full_identity` ignoring a `wp_frontmatter` profile) still land, so the CLI is ready when writers flip.

## StatusActor (value object, stored as `actor` on transitions and annotations)

| Field | Type | Rule |
|---|---|---|
| `tool` | str \| null | Agent/tool handle (bare tool from a compact `--agent`); `user` for an operator with no agent named |
| `role` | `"implementer"` \| `"reviewer"` | From the action (D-4), never from the profile |
| `profile` | str \| null | Resolved per the order below |
| `profile_source` | `"invocation"` \| `"flag"` \| `"agent_string"` \| `"wp_frontmatter"` \| null | `null` iff `profile` is `null` |
| `model` | str \| null | From the dispatch Op record, else the compact `--agent` model segment |

Invariants: exactly these five keys on write; every value a string or null; `profile_source`
null iff `profile` null.

### Profile resolution (first non-empty wins)

1. Dispatch binding from `--invocation-id` → `invocation`
2. Dispatch binding from `--profile` → `flag`
3. Profile segment of compact `--agent tool:model:profile[:role]` → `agent_string`
4. WP frontmatter `agent_profile` → `wp_frontmatter`
5. none → `profile: null, profile_source: null`

### Role per hop

| Hop | Role |
|---|---|
| to `in_review`, `approved`, `done` | reviewer |
| from `in_review` to any lane (rejection to `planned`/`in_progress`, `blocked`, `canceled`) | reviewer |
| every other hop (`claimed`, `in_progress`, `for_review`, `blocked`, `canceled`, `planned`) | implementer |

## Accepted stored shapes (readers)

| Shape | Accepted | Identity (`actor_full_identity`) |
|---|---|---|
| bare string / compact string | yes (legacy) | as today |
| 4-key dict `{tool, role, profile, model}` | yes (legacy) | `tool:model:profile` |
| 5-key dict with `profile_source` | yes | `tool:model:profile`, profile blanked when source is `wp_frontmatter` |
| any other key set, non-string values, bad `profile_source`, source/profile null mismatch | refused | n/a |

## Lane constants (`status_lanes`)

| Name | Value |
|---|---|
| `PACKAGE_LANES` | every `spec_kitty_events.status.Lane` value, package order |
| `NON_AUTHORABLE_LANES` | `{"genesis"}` |
| `CANONICAL_LANES` | `PACKAGE_LANES` minus `NON_AUTHORABLE_LANES`, order kept (the authorable lanes) |
