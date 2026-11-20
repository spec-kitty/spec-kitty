---
affected_files: []
cycle_number: 2
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T20:27:21Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback (cycle 2) — reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commit c93350986c

## Verified
- Red-first: 15 failed and 90 passed against the 1f29e11d sources.
- Post-fix: 132 passed.
- HIGH closed: `merge.renormalize` is read with `--type=bool` across all scopes and env, and an unreadable value refuses.
- The pins work: on git 2.43, `GIT_CONFIG_PARAMETERS` overrides `GIT_CONFIG_COUNT`.

## Security view: filter/LFS
Refusing on every `filter` is unnecessary and over-refuses LFS. Measured on git 2.43 with a hand merge M, `* filter=evil` and the clean filter `sed s/l3/EVIL/`:
- filter, no renormalize: correct, `[f]`.
- filter with renormalize=true: laundered, `[]`.
- filter with renormalize=true plus `GIT_CONFIG_PARAMETERS 'merge.renormalize'='false'`: correct.
- `GIT_CONFIG_COUNT` true plus PARAMS false: correct.

`ll_merge` and merge-ort run `convert_to_git` only when renormalize is set.

## Required change (MED)
1. Add `("merge.renormalize", "false")` to `MERGE_PROBE_CONFIG_PINS`. This closes the gap between the guard's read and the probe's run by construction, and WP07 and WP12 get it through the same table.
2. KEEP the `merge.renormalize` refusal. It names the real cause.
3. DROP the unconditional `filter` / `ident` / `working-tree-encoding` refusal. You may keep reading them in the batched `check-attr` for messages. LFS (`filter=lfs`) and `ident` repos must not be refused.
4. Tests:
   - Convert the per-attribute refusal tests into "inert" tests. Use a hostile clean filter on the probed path, once with renormalize off and once with the pin overriding a config or COUNT `true`. Both probes must still report the hand path, and `n_way_merge_blob` must not return the hand blob.
   - Add a test with `filter=lfs` on a probed path and no renormalize: no refusal.
   - Add a pin-table test for `merge.renormalize`.
