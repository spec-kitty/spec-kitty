# Dead-symbol allowlist parity snapshot (FR-009 / SC-003)

Materialized at closeout (tasks.md "Closeout (orchestrator)" step 1) from the scratchpad
copies WP10 and WP12 produced during implementation. Content is copied verbatim; nothing
here was regenerated or recomputed by the orchestrator.

## Files

| File | Produced by | `base_sha` | `counts` |
|---|---|---|---|
| `before.json` | WP10 (data-model §1.7 snapshot, lane-j) | `68f7418bb4c55888d06b05b7785aaf62a0a1d9dc` | `{"allowlist": 293, "widened_470": 91}` |
| `before-wp12.json` | WP12 T054 re-take ("no base drift" check) | `b534f4247a0494af1ef053faf03e9d521216f9c6` | `{"allowlist": 293, "widened_470": 91}` |
| `after.json` | WP12 T060.1 (post-rekey gate output) | `b534f4247a0494af1ef053faf03e9d521216f9c6` | `{"allowlist": 293, "widened_470": 91}` |
| `parity_before.py` | WP10's snapshot script (produces `before.json`-shaped output) | — | — |
| `parity_after.py` | WP12's snapshot script (produces `after.json`-shaped output) | — | — |
| `wp11_parity.py` | WP11's cross-check script (YAML rows vs. the `before*.json` form) | — | — |

`before_wp12.json` is committed here as `before-wp12.json` (hyphen, matching the closeout
instruction's literal naming) to avoid colliding with WP10's `before.json` in the same
directory.

## Digest

All three JSON files reduce to the **same** parity digest when hashed over
`{allowlist, widened_470, offenders, stale}` with `sort_keys=True` and `separators=(",", ":")`:

```
c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1
```

(Re-derived independently by the orchestrator at materialization time; matches the digest
recorded in WP10's `EV-IC09-03` and WP12's `EV-IC10b-00` / `EV-IC10b-01` evidence records.)

`offenders` and `stale` are `[]` in all three files. Only `base_sha` differs between
`before.json` (WP10, pre-rebase) and the `before-wp12.json` / `after.json` pair (WP12,
re-taken after a lane merge, "no base drift" per WP12's own T054 check) — exactly the
tolerance data-model §1.7 allows ("`base_sha` may differ only if the mission rebased").

## Quickstart FR-009 `diff` command

`quickstart.md`'s FR-009 section already points its parity `diff` at
`kitty-specs/test-suite-remediation-01M3SSDW/evidence/dead-symbol-parity/{before,after}.json`
— the exact paths these files now occupy. No edit to `quickstart.md` was needed at closeout;
the command was already correct for this location.
