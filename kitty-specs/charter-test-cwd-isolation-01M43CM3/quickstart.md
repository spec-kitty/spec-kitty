# Quickstart: verifying this mission

Run from a lane worktree (a linked worktree) and again from the repository root checkout; results must match.

```bash
# the reproduction and controls
pytest tests/specify_cli/cli/commands/charter/test_charter_cwd_isolation.py -q

# the tripwire's own tests
pytest tests/specify_cli/cli/commands/charter/test_charter_cwd_tripwire.py -q

# the files named in #5317 and #5601
pytest tests/agent/cli/commands/test_charter_cli.py \
       tests/agent/cli/commands/test_charter_synthesize_cli.py \
       tests/agent/cli/commands/test_charter_status_cli.py \
       tests/charter/test_references_missing_failclosed.py \
       tests/charter/test_reject_not_drop_cli.py \
       tests/charter/test_presence_gate_bundle_authority.py \
       tests/charter/test_phase3_integration.py \
       tests/consolidation/test_profile_charter_e2e.py -q

# the guard's own tests and the inventory freshness check
pytest tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py \
       tests/release/test_pinning_inventory_fresh.py -q

# no product change
git diff --stat main -- src/    # expect no output
```

Writing a new charter command test: request `charter_cwd_isolation` and call it with your project root before invoking `generate`, `synthesize` or `resynthesize`.
