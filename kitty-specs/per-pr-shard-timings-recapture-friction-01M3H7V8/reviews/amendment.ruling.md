# Design amendment ruling — operator, 2026-09-28

**Trigger:** after analyze recorded `verdict: ready` (`423463a10`), `main` was found to carry
PR #5240 (`5469c4d77`, "ci(tests): make shard-timings count drift non-blocking per PR (#5189
interim)", merged 2026-09-27, `Refs #5189`). It changes
`tests/architectural/test_module_length_agreement.py` so that count drift in **both**
live-collection gates (`test_charter_is_not_allowlisted_and_agrees` and
`test_non_allowlisted_modules_agree_with_live_collection`) emits a `ShardTimingsDriftWarning`
instead of failing; `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` restores the hard failure. Its author
states it is interim relief that "your mission can delete or absorb". The same author left
review notes on issue #5189 (comment of 2026-09-27T14:56Z) addressed to this mission.

**Ruling: absorb #5240 and amend the design; do not delete it.**

1. **Merge `origin/main` into the mission branch** before amending, so the design is written
   against the code that actually exists (the branch was 111 commits behind, including #5240 and
   a rewrite of `ci-nightly.yml`).
2. **WP01 becomes "absorb #5240".** Keep its warning class and its strict-mode flag. WP01's
   remaining job is what #5240 did not do: the red-first tests this spec requires — a test that
   fails if the demotion is reverted (drift hard-fails again without the flag), a test that drift
   is surfaced as a visible `ShardTimingsDriftWarning` (not silence), and a test that
   `SPEC_KITTY_STRICT_SHARD_TIMINGS=1` restores the hard failure — plus any spec requirement #5240
   leaves unmet. Where #5240 already satisfies a requirement, WP01 verifies it and records that,
   rather than re-implementing it.
3. **The spec's scope statement is corrected to match reality:** the per-PR demotion now covers
   both live-collection gates (from #5240), not charter only. The *recapture* scope stays
   **charter only** (operator decision 3 unchanged). The spec must not claim a charter-only
   demotion.
4. **Exact-count home (Standing Order #5, maintainer note 2):** the scheduled workflow (WP03)
   runs the architectural length-agreement gates with `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`, so the
   exact-count invariant keeps a real, scheduled, hard-failing home. Nothing runs
   `tests/architectural` nightly today; without this, the demotion is a silent removal. The
   design states what that strict run does when it fails (visible red run; relation to the
   recapture PR), and which modules it covers — charter hard-fails; the 19/20 allowlisted modules
   keep their existing allowlist semantics.
5. **Allowlist ratchet (maintainer note 4):** the design states explicitly whether a charter-only
   recapture can trip `test_allowlisted_modules_still_genuinely_mismatch` (charter is not
   allowlisted, so it should not), with the reasoning, and what happens if a future recapture
   ever covers an allowlisted module (out of scope; the PR would need to prune
   `_MISMATCH_ALLOWLIST`/`_BASELINE_ALLOWLIST_COUNT` in the same PR).
6. **Maintainer note 6** (`mypy` `no-any-return` in `_resolve_test_dirs`) is admissible as
   domain-matched campsite debt in WP01's file, as a distinct behaviour-preserving commit. It is
   optional, not required.
7. Every prior operator decision and ruling (`spec.md` §Clarifications, `spec.ruling.md`,
   `plan.ruling.md`, `tasks.ruling.md`) stands, except where points 2–4 above supersede them.

The squad reviews the **delta** introduced by this amendment against this ruling; unchanged,
already-PASSED content is not re-litigated.
