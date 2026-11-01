# Contracts

This mission introduces **no new external interface contract**. It changes the behaviour
of an existing surface, `spec-kitty dispatch`, and keeps that surface's machine contract
byte-identical:

- The `--json` refusal envelope keeps exactly its five keys — `error`, `error_code`,
  `message`, `candidates`, `suggestion` — and is still written to stderr with exit 1.
- The `--dry-run` success payload keeps its `dry_run` status and its `alternatives`
  list; a `ROUTER_AMBIGUOUS` dry run still exits 0 with that payload.
- The `router_confidence` vocabulary is unchanged (no new value; a documentation route
  reports `domain_keyword`).

What is *new* is the content of `candidates` on a `ROUTER_NO_MATCH` refusal (up to three
nearest profiles, each with `profile_id`, `action`, `match_reason` and `partial`
confidence) and a suggestion that carries a runnable `--profile <id>` command. Both are
pinned by tests rather than by a versioned schema:

- `tests/specify_cli/invocation/test_router.py` — candidate ordering, bound, empty case.
- `tests/specify_cli/invocation/cli/test_dispatch.py` — the five-key envelope and the
  rendered human refusal.

The user-facing description of the behaviour lives in
[`docs/api/profile-invocation.md`](../../../docs/api/profile-invocation.md)
("How routing picks a profile", "When routing refuses").
