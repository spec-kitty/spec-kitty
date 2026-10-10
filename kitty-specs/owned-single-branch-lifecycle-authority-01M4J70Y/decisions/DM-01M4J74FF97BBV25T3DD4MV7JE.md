# Decision Moment `01M4J74FF97BBV25T3DD4MV7JE`

- **Mission:** `owned-single-branch-lifecycle-authority-01M4J70Y`
- **Origin flow:** `specify`
- **Slot key:** `specify.verification.review-cycle-disposition`
- **Input key:** `review_cycle_disposition`
- **Status:** `resolved`
- **Created:** `2026-10-10T06:13:49.161219+00:00`
- **Resolved:** `2026-10-10T06:13:58.332366+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

#5947 (nightly specify-cli-out-of-matrix red): the two named tests are empirically GREEN on current main (red nightly ran on an older commit). How to close it under red-first discipline?

## Options

- verify-green + defensive owned hardening (no fabricated red)
- write a new red first

## Final answer

verify-green + defensive owned hardening (no fabricated red): add a by-construction owned-arm test pinning that the primary resolver (get_main_repo_root) is NOT consulted for an owned single_branch review/cycle arm, and tidy the one latent smell (cycle.py ProtectionPolicy.resolve(main_repo_root) → resolve_for_owned(owned, slug), guarded by owned-is-None fallback). Do not fabricate a red or edit test expectations; let the next green nightly self-close #5947, note the scoped-green evidence in the PR.

## Rationale

_(none)_

## Change log

- `2026-10-10T06:13:49.161219+00:00` — opened
- `2026-10-10T06:13:58.332366+00:00` — resolved (final_answer="verify-green + defensive owned hardening (no fabricated red): add a by-construction owned-arm test pinning that the primary resolver (get_main_repo_root) is NOT consulted for an owned single_branch review/cycle arm, and tidy the one latent smell (cycle.py ProtectionPolicy.resolve(main_repo_root) → resolve_for_owned(owned, slug), guarded by owned-is-None fallback). Do not fabricate a red or edit test expectations; let the next green nightly self-close #5947, note the scoped-green evidence in the PR.")
