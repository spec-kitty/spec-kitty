# Contract: status event actor

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
