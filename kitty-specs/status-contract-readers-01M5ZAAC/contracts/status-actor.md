# Contract: status event actor

> **Phase split (operator decision 2026-10-27, Decision Moment `01M5ZD4PNEEMAFHA7SN4VJZR2N`).** `spec-kitty-events` 11.0.0's reducer decoder (`diary.decode_actor`) accepts only the 4-key actor `{tool, role, profile, model}`, and every status read goes through it. This mission therefore WRITES the 4-key structured actor on every agent/operator path, with `profile` taken only from asserted sources (dispatch invocation → `--profile` → compact `--agent` segment → null). The WP-frontmatter fill and the `profile_source` key are deferred to a follow-up that first ships an events release whose decoder accepts the fifth key (readers first), then flips the CLI writers through an explicit pin-floor bump (never an automatic capability gate: committed logs are shared across clones on different installs). The CLI-side readers in this mission (`decode_actor` accepting the 5-key shape, `actor_full_identity` ignoring a `wp_frontmatter` profile) still land, so the CLI is ready when writers flip.

Applies to the `actor` field of status transitions and `InnerStateChanged` annotations in
`status.events.jsonl` written by agent/operator commands. Proposed to spec-kitty-events #92 as
the shape the write core enforces.

```json
{"tool": "claude", "role": "implementer", "profile": "python-pedro", "profile_source": "wp_frontmatter", "model": null}
```

- Keys: exactly `tool`, `role`, `profile`, `profile_source`, `model`.
- `role` ∈ {`implementer`, `reviewer`}.
- `profile_source` ∈ {`invocation`, `flag`, `agent_string`, `wp_frontmatter`, `null`}; `null` iff `profile` is `null`.
- Readers MUST also accept legacy strings and legacy 4-key dicts (no `profile_source` → unknown source).
- A `wp_frontmatter` profile is planned, not proven: it MUST NOT take part in reviewer≠implementer identity.
- System writers (`migration:*`, consolidation bookkeeping) may still write a string actor.

Exit/JSON contracts of the commands do not change; only the stored event actor does.
