# Tracer: Design Decisions (#6071, #6073)

1. **A — canonical reducer over the hand-rolled fold.** CLAUDE.md reducer-duality: the merge
   gate sources its claim through the Lamport wrapper. `_parse_target_lanes_by_wp` was a second,
   wall-clock authority (introduced by #5354 `063fc818`) that disagrees with `materialize` on
   causal logs. Chose to route `_assert_merged_wps_done_on_target` through the canonical reducer
   (single canonical authority, DIRECTIVE_044) rather than re-implement causal ordering in the
   fold. The #5354 invariant is preserved by the canonical reducer with realistic data; the
   #5354 unit test is re-pointed to full-envelope events (minimal events can't be reduced
   canonically — they lack from_lane).

2. **B — reuse `mission_dir_aliases` as the ONE composed-dir authority.** Rather than re-derive
   `<slug>-<mid8>`, widen `_unlanded_paths_outside_mission_dir`'s own-prefixes through the same
   `missions._read_path_resolver.mission_dir_aliases` that `interrupted_alias_fold_guidance`
   already uses (#5651 single authority).

3. **C — stale fixture re-pin, declared as a divergence.** Evidence (valid-chain experiment:
   all 3 pass) proves no product bug. Charter Standing Order 4 (stale → re-pin, realistic data)
   governs; the brief's "product fix" framing is a conflict, resolved charter-first and flagged
   in the PR. NOT green-washing: the product path is verified correct.

4. **D — detect-and-refuse, do not loosen the shared residue classifier.** The #5965/#5966
   context-aware disposability correctly treats stale coord residue as disposable; an
   interrupted-fold DELETION is a different state. Add a targeted interrupted-fold detection in
   the pre-mutation primary leg (reusing the #5748 predicate) so the existing abort advice
   renders, leaving #5965/#5966 behaviour unchanged for all other dirt.
