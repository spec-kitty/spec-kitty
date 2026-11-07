# Design decisions

- **[2026-11-07][plan] New `checkout_file_recipe` renderer, not `restore_recipe`.** `git restore --source HEAD --staged --worktree` would drop the staged edit the `staged_differs` branch deliberately keeps (5b822c28ca) and fails for `index_only`; the new sibling lives in the excluded canonical home `_git_remedies.py`. Notice module imports it lazily (same precedent as `migration/mission_state.py`).
- **[2026-11-07][plan] #7111 rewrites in place instead of asserting the refusal.** The refusal is already covered for all four verbs by `tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py`; the in-process seed keeps the stored-whole pin a home.
- **[2026-11-07][plan] #7182 interview nodes keep the interview's own error JSON.** `_emit_error` shape, not the `charter status` typed envelope.
