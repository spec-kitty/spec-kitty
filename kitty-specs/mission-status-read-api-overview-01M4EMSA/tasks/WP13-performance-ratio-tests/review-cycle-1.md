---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T19:29:06Z'
reviewer_agent: reviewer-renata
wp_id: WP13
---

# WP13 review cycle 1: REJECT (reviewer-renata), operator and orchestrator dispositions

The full evidence is in wp13-review-verdict.md (orchestrator scratchpad). The gates are green, and the thread-per-connection and cache-disabled mutations go red. The operator ruled F1 (end of reviews/analyze.ruling.md); the orchestrator picked the remedy for the forks F2 and F4.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | high | perf/PerfBudgets.java (NFR001_WARM_P95_RATIO_LIMIT = 75, COLD = 150) | The WP's revert row "50 ms sleep → ratio red" fails. A 50 ms sleep gives a warm ratio of 51 and a cold ratio of 78, both green. | Operator ruling: warm limit about 40, cold about 90. Pick the exact values so that a 50 ms sleep in the overview route is red on both warm and cold, and record the measured margin. Add that 50 ms sleep as a real revert row, run in a scratch worktree, and show it red. Keep the PerfBudgetsTest pins in sync. Update the comments: the limits are provisional, and a miss is classified, never retried. |
| F2 | medium | workflow (WP13 steps before the digest upload) | A nativePerf miss skips the digest upload, native-tag-floor and staging steps, so the digest gate then fails for an unrelated reason. | Give those steps `if: ${{ !cancelled() }}` (the orchestrator's choice; nativePerf stays where it is). Pin it in tests/ci with a revert row. |
| F3 | medium | nativesmoke/NativePerfTest.java, ProcessMetrics.carriers | The native leg never asserts carriers ≤ cores (amended NFR-004(a)). The tail regex also nets out any `…pool-N-worker-M` thread. | Assert peak native carriers ≤ `availableProcessors`. Narrow the match to the carrier pool's kernel-truncated name as tightly as the 15-character limit allows, document what it can and cannot see, and add a unit test with lookalike names. |
| F4 | low | workflow floor step `continue-on-error: true`; NativePerfTest.floorBinary() | A failed floor build silently makes the leg ceiling-only. | The test fails when `MISSION_STATUS_FLOOR_BINARY` is set but the file is missing. The floor step's outcome goes into the job summary (the orchestrator's choice). |
| F5 | low | tests/ci (WP13 section) | No pin for the `MISSION_STATUS_FLOOR_BINARY=` write to `GITHUB_ENV`, the `cygpath` fallback, `continue-on-error`, or nativePerf coming before the digest upload. | Add source-text pins for each, with revert rows. |
| F6 | low | native RSS ratio | The one-connection floor is GC noise. | Accepted as provisional. Add one comment line saying that, until CI re-measures, the 128 MiB ceiling is what actually protects. |

Run all mutations in a scratch worktree. Do not use `sh -c` scripts; run separate plain commands.
