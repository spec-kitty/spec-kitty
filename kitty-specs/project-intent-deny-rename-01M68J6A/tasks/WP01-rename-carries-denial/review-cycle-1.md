---
affected_files: []
cycle_number: 1
mission_slug: project-intent-deny-rename-01M68J6A
reproduction_command:
reviewed_at: '2026-10-31T09:46:38Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 review cycle 1 — changes requested

Reviewed `git diff 13ae304e5..7af7c3054` (red commit + fix commit) against spec FR-001..FR-005 and the
plan's design section. The behaviour is right: the red test is genuinely red on the base and green
after the fix, the deny rename rides the same single `save` as the allow rename, and the gate pins the
new origin in both directions with a positive control. Three findings.

## R1 (medium) — `_is_ledger_target` re-derives the write target's mode instead of asking the resolver

`_is_ledger_target(repo_root, target_path)` decides "is this the ledger?" by comparing the resolved
path with `activation_ledger_path(repo_root)`. The write target's mode is decided one line earlier by
`resolve_ledger_source(repo_root).source is ActivationSource.LEDGER` (that is literally how
`resolve_activation_write_target`, `prepare_activation_write` and `prepare_ledger_write` branch).
Comparing the path is a second statement of the same fact: if the target function ever returns a
ledger path through a different route (or a future write target changes), the predicate silently says
"not the ledger" and the deny rename stops happening with no test catching it, because the unit tests
all construct the path the same way.

Fix: ask the resolver.

```python
from charter.activation.activation_ledger import DENY_KEYS, ActivationSource??  # ActivationSource lives in kernel
```

Keep the predicate inside the existing `try:` in `_check_tokens` so an unreadable `config.yaml` still
takes the soft-refusal path (a resolver call can raise `ActiveCharterConfigError`; the path comparison
could not).

## R2 (low) — a deferred import whose stated reason does not apply

`_legacy_token_keys` imports `DENY_KEYS` with the comment `# deferred: import cycle: pack_manager
imports synthesizer modules`. That cycle is real for the `pack_manager` import on the next line, not
for `activation_ledger` (it imports no synthesizer module at runtime, and `pack_context` — already a
module-level import here — imports `activation_ledger` anyway). Either import `DENY_KEYS` and
`DenyListChoice` at module level, or give the deferred import its own true reason. Do not leave a
comment that a reader can disprove in one `grep`.

While there: `_renames_a_deny_key(keys)` is a second `DENY_KEYS` import plus a helper for one
`any(key in DENY_KEYS for key in keys)`; fold it into `_apply_tokens`.

## R3 (low) — one test pins a whole action sentence

`test_a_deny_only_project_is_detected_and_carried` asserts the full action tuple including the message
wording. Assert the key and the ledger path instead, so a wording tweak in the report does not fail a
behaviour test.

## Confirmed, no change needed

- The red commit precedes the fix and is a real red on the base (`report.actions` has only the allow
  rewrite).
- One write, one choice: no second `save`, no raw YAML, no new mapping.
- Legacy surface behaviour is unchanged and pinned by `test_a_legacy_surface_deny_key_is_left_alone`.
- The pins in `test_deny_list_survives_upgrade.py` name the origin *and* the forward, and the positive
  control uses the same `post_ledger_fixture` family as the dynamic half.
- The `DenyListWriteRefused` message change is accurate and no test/Doc quote depends on it.

Please fix R1..R3 as one commit and resubmit for review.
