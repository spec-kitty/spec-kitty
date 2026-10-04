# Tracer: design decisions

Decisions D-01 to D-13 are recorded with rationale and alternatives in `../research.md`. Operator rulings are Decision Moments `01M42V5PVVQ0W5D0SJ60A4X6AA`, `01M42VM0CEBBZHCJEAN4KTDYYC`, `01M42V5RDSJN1R0C7R4YKEB0E1` and `01M42VM1YPDQPPGP1FK0W9AECK`.

- 2026-10-04 — Key on the committed tree id instead of an enumerated input list: collection reads files across the whole repository, so any list would go stale.
- 2026-10-04 — A fallback after a successful pre-test step fails the job's reuse check. Without it a never-matching key is invisible, because the fallback keeps every gate green.
- 2026-10-04 — The allowlist is deleted rather than emptied, so its shape tests cannot pass vacuously (ADR `2026-09-30-1`).
- 2026-10-04 — The 90 s first-run bound for the pre-test step and the 10 s reused-path bound are planning thresholds derived from the measured 35–45 s uncontended collection; they are confirmed or corrected by the first three CI runs.
- 2026-10-04 — The key excludes `SPEC_KITTY_*` variables the test session sets for itself (conftest writes two into every pytest process). Without that, a pre-test step and a test could never share a key and the reuse check would red every job. Pinned by a test that compares the key inside pytest with the key in a plain process.
- 2026-10-04 — Shard counts are never reduced by the mission: the skew check passes trivially at one shard, and counts also encode the per-shard time cap.
- 2026-10-04 — The cache save sits directly after the pre-test step, not after pytest: failed jobs are the ones that get re-run.
- 2026-10-04 — With an open recapture proposal, drift is computed against the proposal branch's data so the time-budget carry-over makes progress.
- 2026-10-04 — A pre-test step that cannot store (dirty checkout, git unavailable, lock or store failure, collected but not stored) fails `collect` and `check`. Only an unsupported platform is a legitimate fallback. One predicate serves both commands.
- 2026-10-04 — Recapture: a `detect` phase holds the token and learns whether a proposal is open; the long capture step runs without the token. A failed capture restores the whole timings file from bytes. A valid capture must carry the run id the script passed.
- 2026-10-04 — Accepted residual from the WP04 review: the count-only pass is capped per module (300 s) but not by the overall budget. To be folded before the pull request: check the budget before each count pass and report uncounted modules as deferred.
- 2026-10-04 — Open risk carried to the CI evidence step: a test that creates an untracked file in the checkout while a collecting test runs makes that request `bypassed` and fails the reuse check. The report line names the dirty paths so a red job explains itself.
- 2026-10-04 — The key overlays the operator env file through the product's loader (research D-16). Found in the repository root checkout, which has such a file; lanes and CI do not.
- 2026-10-04 — The key-equality test now collects each consuming job's real file list. Any test module that sets a `SPEC_KITTY_*` variable on import breaks key equality for its leg; the test fails in the change that introduces it instead of in the CI reuse check.
- 2026-10-04 — The store reads the checkout after taking the lock and again after collecting; a collection is stored only if the checkout did not move.
- 2026-10-04 — Not folded, for a follow-up: the module-collection command exists in three places (`shard_select`, the strict agreement test, the recapture's count pass) with different accepted exit codes; `shard_select` should own one.
