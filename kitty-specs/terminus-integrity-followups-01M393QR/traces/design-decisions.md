# Design-Decisions Tracer — terminus-integrity-followups

- WS1: blob-attribution (content identity), NOT patch-id-of-squash (opaque aggregate) and NOT lane-tip replay (carrier tip contains smuggled content). First-parent authorship is the exclusion signal.
- WS2: mirror the landed C-1 target-authority precedence for strategy; persist coord base symmetrically to pre_mutation_target_sha; per-lane tip as a CAS expectation.
- WS3: committed-content probe inside coordination.surface_resolver (already-ledgered), no blanket terminus_write flip.
- Fail-closed everywhere: probe error / None base / unreadable git ⇒ REFUSE, never vacuous PASS.

## Post-plan squad corrections (folded 2026-09-24)
- F5: authored_blobs = FINAL first-parent blob per (lane,path), not union of all — closes the superseded-intermediate-blob false-PASS; makes the 3-way defer sound.
- F1: squash content loop drives off `git diff --name-status B..T` (A/M only), REFUSE on unexpected empty blob — never infer deletion from a rev-parse failure.
- F3/F9: resume anchors (coord base, lane tips) read-persisted-first (mirror _resolve_pre_mutation_target_sha); consume the persisted value at the coord_base site, not the live checkpoint.
- D/F8: lane-tip CAS compares as a git OBJECT and ACCEPTS behind-HEAD (strict ancestor) — that IS the #4982 window; branch ref may be gone; REFUSE only true divergence.
- Arch-A: strategy persisted via WP05 executor reseed (not resolve.py) — keeps WP04↔WP05 additive-only.
- F2: WS3 committed-content probe derives path from placement authority / ls-tree; path-drift must not read as absent.

## Implementation deviations (WP01-04, for pre-merge squad)
- WP02: T008 up-front resolve_for_write exposed a latent bug — _mission_meta_exists checked the COORD feature dir (meta.json lives on PRIMARY), falsely refusing every 2nd coord write. Fixed to anchor on read_primary_meta. SHARED-HELPER widening (also affects decision_log/bookkeeping/status_transition callers); F11 blast-radius green apart from pre-existing reds. Pre-merge squad MUST confirm the widening is safe.
- WP03 deviation-3 (LOAD-BEARING): coord-topology e2e harnesses yield approved={'WP01': ()} → empty authored_blobs → squash axis DEFERS not attributes. WP03 split the empty-authored guard (REFUSE only when real commits resolve but no blobs; DEFER when no commits resolve at all) to preserve legit merges. OPEN QUESTION assigned to WP05+pre-merge: does the axis ATTRIBUTE (fire) on a REAL coord-topology production merge, or also defer? If it defers in production, #5013 P0 closure is narrower than claimed. property[squash] terminus test XPASSes (axis fires there).
- WP01: clean-squash added as a standalone test (not @parametrize) since clean_merge is standalone — trivial, reviewer optional.
- WP04: lane_tip_cas_ok is a producer-without-consumer until WP05 wires it (expected; dead-symbol gate clears when WP05 lands).

## Terminus integration outcome (2026-09-24)
- 8 markers removed genuinely green: #4945/#4977/#4981 default-squash variants, #4970, #4985, #4991, property[squash], #4982.
- #4982 closed for the RIGHT reason: pre-interrupt lane-tip commit OBJECTS reachable + ancestors of target after resume (squash would mint new SHAs); discrimination proof = #4997 identical assertion stays RED.
- #4997 HONEST XFAIL (real residual, NOT green-washed): its window is behind-HEAD WITH a staged deletion -> classified LOCAL_CHANGES -> behind-own-HEAD preservation remedy does not fire -> already-merged lane SHA not carried onto target. FOLLOW-UP: extend resume-consolidation preservation to the staged-deletion/LOCAL_CHANGES behind-HEAD window. #4997 referenced-not-closed.
- IN-SCOPE TALLY: 8/9 genuinely closed (#5013 #4945 #4977 #4981 #4970 #4985 #4991 #4982); #4997 partial+follow-up.
