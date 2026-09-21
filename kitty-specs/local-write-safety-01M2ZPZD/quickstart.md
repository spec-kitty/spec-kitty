# Quickstart: verifying Local Write-Safety Hardening

All checks run under an **isolated HOME/TMPDIR**, never the real `~/.spec-kitty`.

## WP01/WP01b/WP06 — symlink-safe + per-user (#4756, #4721)
```bash
# For each surface path (cold-install lock, prompt temp, credential temp, mission-state lock):
# plant a symlink at the computed path → a victim file with known bytes, run the op, assert:
#   1) victim bytes UNCHANGED   2) op exits non-zero (refuses)
# and assert the sentinel/prompt dir resolves under $HOME/.spec-kitty (0700), not $TMPDIR.
```
Expected: 0 truncations; each op refuses; relocated paths under the per-user root (SC-001, SC-005, SC-006).

## WP02 — decisions concurrency + repair (#4757)
```bash
# Red-first, barrier-synchronized: N=8 workers released together, repeated:
#   assert index has 8 entries == 8 DecisionPointOpened events (1:1)
# Repair: seed log=8/index=5, run `spec-kitty doctor decisions --mission <h> --repair`:
#   assert index rebuilt to 8; re-run on agreeing corpus = no-op.
```
Expected: 8==8, heal 5→8, idempotent repair (SC-002). The proof must FAIL without the fix.

## WP03 — init never destroys operator content (#4759)
```bash
# For EACH destructive site (>=3): create .kittify/missions/<c>/ + .kittify/memory/<n> with
# known bytes, no config.yaml, run that init path, assert content present in a reported
# .kittify/.backup-<ts>/ and nothing deleted.
```
Expected: 100% survival, backup path reported, at every site (SC-003).

## WP05 — credentials owner-only by construction (#4812, #4760)
```bash
# For zeitgeist AND tracker credential writes: assert the file is mode <=0600 at every instant
# (no 0644-then-chmod window) and a planted symlink at the temp path is refused.
```
Expected: no world-readable window; symlink refused (SC-005, SC-001).

## WP04 — mission_state lock canonical (#4811)  [after PR #4813 merges]
```bash
# Assert the mission-state lock routes through kernel.locks (ban gate) and does not follow a symlink.
```

## Full-surface + compatibility
```bash
# Blast radius (WP01): run all kernel.locks consumer tests (auth, checkout, status, merge, review)
# + tests/architectural/test_lock_primitive_ban.py + test_layer_rules.py, on POSIX and Windows.
```
Expected: all green; lock re-acquisition unbroken (SC-004, NFR-004).
