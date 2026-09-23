# Decision Moment `01M3584PY5A6F79DWX1QFDHW87`

- **Mission:** `ci-nightly-wallclock-budget-01M34HNZ`
- **Origin flow:** `plan`
- **Slot key:** `plan.wp05.charter-shard-count-skew-gate-claim`
- **Input key:** `charter-shard-count-skew-gate-claim`
- **Status:** `resolved`
- **Created:** `2026-09-22T19:05:35.941637+00:00`
- **Resolved:** `2026-09-22T19:07:50.814256+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

WP05's committed justification comment on charter's row in .github/ci-module-registry.yml (commit ea26fa934) claims: "the same method finds skew first exceeds the 20% NFR-005 ceiling at shard_count=68 (21.1%), so this is not vacuous over a real, reachable range." Independent re-measurement using the gate's own _lpt_bin_pack/_skew_of (tests/architectural/test_module_shard_registry.py) against both the pre-recapture timings (git show 66e5255dc~1:.github/ci-shard-timings.json, 4211 entries) and the current post-recapture timings (6156 entries) found: (1) over the whole 2-40 shard_count operating range skew is ~0% both before and after the recapture -- unchanged at the configured shard_count=5; (2) the pre-recapture data ALSO exceeded the 20% ceiling, reading 39.4% at shard_count=67 (worse than post's 19.9% at the same k); (3) the k>=68 failure is structural (the largest single test, 20.99s, exceeding one ideal bin, 16.7s at k=68), not the gate detecting genuine imbalance. Is the committed claim -- that the recapture produced gate non-vacuity / shard_count-sensitivity -- an accurate characterization, and should it stand as written?

## Options

_(none)_

## Final answer

No. The committed claim does not stand as written and must be reframed honestly: the recapture did not make the skew gate non-vacuous or shard_count-sensitive.

## Rationale

Operator ruling, binding, implemented by a fresh corrective agent (not the WP05 author).

WRONG CLAIM: WP05's committed comment on charter's row in .github/ci-module-registry.yml (commit ea26fa934) asserted that re-deriving shard_count=5 from the recaptured timings showed "the same method finds skew first exceeds the 20% NFR-005 ceiling at shard_count=68 (21.1%), so this is not vacuous over a real, reachable range" -- implying the recapture gave the skew gate new discriminating power.

MEASURED EVIDENCE (independently re-run against the gate's own _lpt_bin_pack/_skew_of in tests/architectural/test_module_shard_registry.py, comparing the true pre-recapture file `git show 66e5255dc~1:.github/ci-shard-timings.json` [4211 per-test entries] to the current post-recapture file [6156 entries]):
- shard_count 2-40: skew ~0.000% both before and after the recapture. At the configured shard_count=5 specifically: pre 0.0001%, post 0.0003% -- both trivially near-zero, unchanged in substance.
- shard_count=67: pre 39.4%, post 19.9%.
- shard_count=68: pre 40.4%, post 21.1%.
- Re-verification beyond the dispatched figures: the pre-recapture data's OWN first crossing of the 20% ceiling is earlier than k=67/68 -- it first exceeds 20% at shard_count=52 (20.1%), rising steadily from shard_count~42 onward. This confirms the high-60s threshold is a sampling artifact of test-count-vs-bin-count, not a property the recapture introduced or removed.
- The failure mode at k>=68 is structural: it triggers once the single largest recorded test (post-recapture: 20.99s) exceeds one ideal bin's share of total duration (1134.188s / 68 ~= 16.7s) -- LPT bin-packing cannot avoid that regardless of how balanced the rest of the distribution is. It is not the gate detecting genuine per-test-duration imbalance.

CONCLUSIONS:
1. Over the whole realistic operating range, skew is ~0% both before and after recapture; the gate's verdict at the configured shard_count=5 is unchanged. The recapture gave the skew gate no new discriminating power there.
2. The pre-recapture data ALSO exceeded the 20% ceiling (39.4% at k=67, first crossing it already at k=52) -- worse than post-recapture's 19.9% at k=67. "First fails at k=68" does not distinguish after from before; if anything the recapture pushed that structural failure point further out.
3. The k>=68 region is not evidence of gate non-vacuity -- it is a structural artifact (largest single test exceeding one ideal bin), unrelated to whether the gate can detect real imbalance.

RULING (operator, binding): Reframe the .github/ci-module-registry.yml charter-row comment honestly. It may state only what is true: the timings were recaptured with the purpose-built producer (scripts/ci/capture_shard_timings.py, provenance recorded, exit_code 0); the committed list length (6156) now equals what the consumer actually collects (pytest tests/charter tests/doctrine -m "not performance and not stress" --collect-only -q), fixing #4864's silent-uniform-weight fallback that caused the observed 31m13s long pole on run 35756657364; and shard_count=5 is justified by projected per-shard wall-clock against module-tests.yml's real 40-minute timeout, using the empirically measured CI/local ratio (~6.7x, from run 35756657364: ~7624s CI across 5 shards vs 1134.188s local) -- NOT by skew, which does not discriminate in this range. The comment must NOT claim the recapture produced skew-gate non-vacuity or shard_count-sensitivity, and must not present "first fails at k=68" as new or meaningful without noting the pre-recapture ceiling-crossing was earlier, not later. shard_count's numeric value (5) is correct and unchanged by this ruling. A separate, later dispatch repoints WP06 away from "skew is shard_count-sensitive" toward a committed length-agreement test (committed-list-length == collected-test-count); this decision does not implement that repoint and must not be read as contradicting it.

HONESTY NOTE (for the record, not actioned by this decision): the mission's own spec premise -- FR-008 / NFR-003 / SC-006, which require the skew gate to become "genuinely shard_count-sensitive" post-recapture -- is NOT satisfied by this recapture and rests on an inaccurate characterization that originated in the mission's readiness probe / spec.md (~line 370), which claimed the OLD pre-recapture data made the gate "mathematically vacuous," returning "~0% skew for ANY shard_count from 1 to 4211." Independent re-measurement of that same pre-recapture 4211-entry file shows this is false: skew is negligible only through roughly shard_count~41, rises through the 40s, and exceeds the 20% NFR-005 ceiling by shard_count=52 -- nowhere near "any shard_count... to 4211." The gate was therefore never as vacuous as the readiness probe claimed, and the recapture (which keeps skew ~0% through the same low range, k~2-40/54, and pushes the ceiling-crossing point from k=52 to k=68) did not change that qualitative picture at the shard counts the registry could plausibly use. This is flagged for whoever next reconciles spec.md's acceptance criteria against what was actually delivered; it is out of scope for this WP05 comment correction and for the separate WP06 repoint dispatch.

Resolved by: operator ruling, recorded by a fresh corrective agent (Wrangler Wendy) per dispatch for mission ci-nightly-wallclock-budget-01M34HNZ, WP05 (branch issue-4865-ci-nightly-wallclock-budget).

## Change log

- `2026-09-22T19:05:35.941637+00:00` — opened
- `2026-09-22T19:07:50.814256+00:00` — resolved (final_answer="No. The committed claim does not stand as written and must be reframed honestly: the recapture did not make the skew gate non-vacuous or shard_count-sensitive.")
