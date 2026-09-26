# Quickstart: verifying the mission

Run from the repository root with the synced `.venv`.

```bash
# Widened ban, pinned-empty exemptions, orphan data retired (WP01, WP13)
.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q --durations=5

# Hand-curated allowlists survive drift and fail on stale entries (WP02, WP03)
.venv/bin/python -m pytest tests/architectural/test_content_identity.py \
  tests/architectural/test_built_in_location_authority.py \
  tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/test_os_detection_ban.py -q

# Census re-key and equivalence proof (WP04, all 80 keys)
.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py -q
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea

# Inert-slot retirement (WP05) + baseline leaf enforcement (WP06)
.venv/bin/python -m pytest tests/architectural/test_ratchet_baselines.py tests/architectural/test_no_inert_schema_slots.py -q

# Surface-resolution converter retirement: survivor imports the kept scanner (WP07)
.venv/bin/python -m pytest tests/architectural/test_single_mission_surface_resolver.py -q

# Parity remediation (WP08–WP11)
.venv/bin/python -m pytest tests/next/ tests/contract/test_next_no_unknown_state.py tests/status/ tests/charter/ \
  tests/runtime/test_next_board_authority.py -q

# Parity verdict catalog completeness (WP12)
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py --base 3717c7ea

# Final gate sweep
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
```
