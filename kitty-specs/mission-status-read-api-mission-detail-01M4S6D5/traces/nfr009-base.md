# NFR-009 base figure (WP05, P3, T030)

A corroboration taken once under operator ruling E-7 (S-24). It is not a condition of the criterion: the criterion (AC-20.5) is asserted by CI's `perfTest` through the same-run floor of `Nfr009CacheGrowthTest`.

- Commit measured: `891f4ff4d` (the first commit of WP05, `test(perf)`; it carries no production line, so the resolved members do not exist yet).
- Date: 2026-10-14.
- JVM: OpenJDK 25.0.2 (GraalVM CE 25.0.2+10.1), 24 cpus, the lane worktree detached at the commit above (a scratch worktree).
- Command, from `services/mission-status-api`, with the contract bundle variables set (digest `fadf8a86...0effd`):
  `LC_ALL=C.UTF-8 ./gradlew --offline perfTest --tests 'org.speckitty.missionstatus.perf.Nfr009CacheGrowthTest'`
- Corpus: 500 Missions, 10 Work Packages and 100 transition rows each (`MissionCorpus.nfr009Spec`), seed `MissionCorpus.SEED`.

| Quantity (median of 5 GC-settled samples) | Bytes |
|---|---|
| Retained by the real snapshots (500) | 1,690,096 |
| Retained by the same snapshots through the 4-argument constructor (history-less) | 1,426,448 |
| Difference (the asserted quantity) | 263,648 |
| Ceiling `CEILING_BYTES` (NFR-009, initial and provisional, ADR `2026-10-05-2`) | 67,108,864 |
| Sensitivity control, one copy of a stand-in structure | 10,242,240 |
| Sensitivity control, ten copies | 102,559,768 |

At this commit the two legs are structurally equal, so the difference (about 0.26 MB, GC noise between two separate builds) is the base shape: nothing resolved is retained yet. The control sees ten times the structure (ratio 10.01 against the asserted factor 4).

## Figure at the P3 tip (T033, T036), same command and machine class

| Quantity | Bytes |
|---|---|
| Retained by the real snapshots (500) | 23,568,376 |
| History-less leg | 1,527,048 |
| Difference (resolved members of 500 Missions x 10 Work Packages x 10 rows) | 22,041,328 (ceiling 67,108,864; about a third of it) |
| Control, one copy of the real resolved structure / ten independent copies | 22,386,336 / 223,764,392 (ratio 10.0, asserted factor 4) |

Side finding, not part of NFR-009: the cold first call of NFR-001 over 588 Missions rose from about 95 ms (base, two runs) to about 110 ms (tip, calm machine); the warm p95 did not move. One run at load 9.6 missed the cold ratio limit (73.9 against 70) and the same test passed in the next `check`.

## NFR-001 cold first call, cycle 2 (review R1)

Profiled with temporary `System.nanoTime` sections in scratch worktrees (not committed), cold server, 588 Missions. Over the reduction of all Missions the resolved fold (`ResolvedFold.resolve`) cost about 32 ms of the 56 ms spent in `reduceLines` (base: 10 ms in all). It was dominated by `HistoryOrder`: `OffsetDateTime.parse` ran on every comparison, and the formatter machinery is slow on a cold JVM. Fixes, behaviour unchanged: decorate each row with its key once; read the canonical stamp form (`YYYY-MM-DDThh:mm:ss[.f]Z|+hh:mm`) by hand in `Instants.parse`, falling through to the formatters for anything else (a differential test pins equality on 4,000 generated and 40 hand-picked texts); drop the redundant list copy; replace the per-event `EnumSet` of served-slot provenance with bit masks. After the fix the resolved fold costs about 6.5 ms cold.

Alternating base (5a6929ecb) and tip (ce8ec53c3) `perfTest --tests '*Nfr001*'`, each in its own scratch worktree, 10 pairs, cold first call ms / ratio (limit 70), 1-minute load before the run:

| pair | base ms / ratio / load | tip ms / ratio / load |
|---|---|---|
| 1 | 125.6 / 19.0 / 9.6 | 110.7 / 55.5 / 9.1 |
| 2 | 112.4 / 68.2 / 10.3 | 107.0 / 50.4 / 8.3 |
| 3 | 105.0 / 52.2 / 7.2 | 111.2 / 54.6 / 6.5 |
| 4 | 108.6 / 61.0 / 5.6 | 112.5 / 54.6 / 5.1 |
| 5 | 103.7 / 57.6 / 5.5 | 109.7 / 53.6 / 5.4 |
| 6 | 101.2 / 50.7 / 5.7 | 110.6 / 53.7 / 5.2 |
| 7 | 110.2 / 56.2 / 5.2 | 111.5 / 60.0 / 5.9 |
| 8 | 109.1 / 53.8 / 6.6 | 104.1 / 53.8 / 6.3 |
| 9 | 102.8 / 60.4 / 5.9 | 102.6 / 51.4 / 6.0 |
| 10 | 105.0 / 51.3 / 6.6 | 106.5 / 58.7 / 6.0 |
| median | 106.8 ms / ratio 55.0 | 110.2 ms / ratio 54.2 |

Tip: 0 of 10 over 70 (worst 60.0). Base: 0 of 10 over 70 (worst 68.2). The cold median is 3.4 ms (3%) above base in milliseconds; the ratio median is not above base. An earlier 9-pair series at the first fix (d17952780, before the bit masks) gave tip 109.0 ms against base 103.3 ms. The remainder is the unavoidable cost of building the resolved members eagerly; a lazy history would remove it but changes where the order is computed.
