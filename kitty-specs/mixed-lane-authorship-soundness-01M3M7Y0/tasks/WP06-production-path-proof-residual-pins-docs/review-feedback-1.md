# WP06 review feedback — cycle 1 (reviewer-renata)

Verdict: CHANGES REQUESTED. The SC-006 production-path proof, the half-by-half proof, the four residual pins, the benchmark and the docs are otherwise sound. Verified locally in lane-f:
- production_path: 4 passed (114.7 s)
- residuals: 4 xfailed. With `--runxfail`, all 4 fail on the ideal-verdict AssertionError, not on a crash.
- benchmark: skipped by default; with SPEC_KITTY_RUN_PERFORMANCE=1, 1 passed (mixed 1.16 s, baseline 0.49 s, delta 0.67 s)
- terminology: 96 passed
- check_docs_freshness --ci: exit 0, errors 0
- ruff, ruff format and mypy: clean
- `docs_index --write --strict`: drift=False, and the index diff is one line (the new heading)

## Blocking

**Issue 1 (HIGH): the fifth residual pin is missing (C-007 / traces/design-decisions.md, WP04 cycle-3 entry).**
design-decisions.md records a residual accepted at WP04 review cycle 3 and says it is "Pinned with the other residuals in WP06". The shape: a sibling that never entered implementation (planned -> blocked -> canceled) makes an out-of-workflow commit INSIDE the canceled WP's implementation window. `wp_attribution.resolve_canceled_wp` skips siblings that fail `_entered_implementation` (wp_attribution.py ~L453), so that commit is attributed to the canceled WP.

Residual #4 (`test_never_claimed_wp_commit_ideally_fails`) does not cover this shape:
- In #4 the commit lies outside every window, and today's outcome is PASS (the commit is never examined).
- In this residual the commit lies inside another canceled WP's window and is misattributed to it. Today's outcome is FAIL/finding naming the wrong WP, and the code path is different (sibling skip plus contested resolution).

Add a fifth git-backed `@pytest.mark.xfail(strict=True, reason=...)` test in `tests/consolidation/test_canceled_content_residuals.py` that asserts the IDEAL outcome. For example: the finding for the sibling's path is NOT attributed to WP02 (it names the sibling), or the result is REFUSE as contested. Pick one and justify it in the docstring, citing the WP04 cycle-3 decision and issue 5069. Confirm with `--runxfail` that it fails on the assertion, not on a crash.

**Issue 2 (MEDIUM): the docs residual paragraph needs updating (docs/architecture/status-model.md, "Known, accepted residuals").**
(a) Add the fifth residual (the out-of-workflow commit by a never-implemented sibling inside a canceled WP's window is attributed to the canceled WP).
(b) Soften the closing claim "None of these degrade PASS into a silent ship of an implemented, unsuperseded canceled WP's content". The hunk-level residual does ship an implemented canceled WP's content verbatim under a PASS; it is only "superseded" at path granularity. State it precisely: for example, "none lets a canceled WP's whole-path content ship unsuperseded while the gate reports PASS".

## Non-blocking (recommended in the same cycle)

**Issue 3 (LOW): the axis-off half is non-vacuous only by inference.** I confirmed that the sitecustomize loads under `run_terminus`'s env and that `_axis_off` matches the real signature. Still, the test only asserts exit 0, and its non-vacuity rests on the unsuperseded twin FAILing on the same shape. Make the patch observable: have `_axis_off` (or module load) write a sentinel file into tmp_path, and assert that the sentinel exists after the run. A silently dropped PYTHONPATH or a renamed method will then fail loudly (tactic architectural-gate-non-vacuity).

**Issue 4 (LOW): the benchmark discards verdicts.** `_timed_claim_and_verify` throws away the VerifyResult. Assert mixed == FAIL (with canceled_content entries) and baseline == PASS, so that an early REFUSE or short-circuit cannot produce a trivially fast "within budget". I checked by hand that they are FAIL and PASS today. Consider taking the min of N timed runs (N≥3) rather than a single run. The 0.67 s delta leaves only about 33% headroom.

**Issue 5 (LOW): the xfails would also "pass" if they crashed.** Add `raises=AssertionError` to each strict xfail, so a fixture or setup exception is not counted as the expected failure.

## Adjudications (no action)
- `reason_source="operator"` on cancel is exactly what `move-task --to canceled --note ...` emits (`_mt_hop_reason_source`). This is faithful, not a product gap.
- `subtasks: []` on WP01's task file: real `/spec-kitty.tasks` output always carries `subtasks:`, so this compensates for a gap in the WP01 test builder, not in the product. Optional follow-up: have `build_coord_mission_mixed_lane_canceled` emit `subtasks: []` itself (WP01-owned conftest; do not edit in WP06).
- SC-006: no hand-written `lane_head` in the file. Transitions go through `emit_status_transition_transactional`, which imports the probe at call time, so the capture-off monkeypatch really does reach it (asserted via `policy_metadata is None`). Both stamps are compared against real rev-parse values taken before the first commit and after the last. FAIL names WP02, lane-a and the path, and the target SHA is restored.
- The docs index regeneration is canonical, and its diff is limited to the new heading.
