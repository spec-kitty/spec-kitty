package org.speckitty.missionstatus.perf;

/**
 * The performance budgets of NFR-001, NFR-002 and NFR-004, in one place (ADR 2026-10-05-2, runner-relative performance budgets).
 *
 * <p>Two kinds of figure live here and they are never mixed up:
 *
 * <ul>
 *   <li>{@code *_CEILING_*}: the absolute figure of the spec. It is an INITIAL, PROVISIONAL ceiling that stops a test from waiting
 *       unbounded; it is amended by a measurement of the spec row, never by a retry. {@code PerfBudgetsTest} pins each of them to the
 *       spec text, so loosening one here without amending the spec turns that test red.
 *   <li>{@code *_RATIO_LIMIT}: the primary assertion, a ratio to a floor sampled in the same run. Each was set from the first
 *       measurement (see the comment beside it) and is PROVISIONAL until a CI-runner measurement confirms it.
 * </ul>
 */
public final class PerfBudgets {

  private PerfBudgets() {}

  // ---- NFR-001: GET /api/v1/missions over >= 500 Missions ---------------------------------------------------------------------

  /** Missions in the generated corpus (spec: at least 500; the planning checkout holds 588). */
  public static final int NFR001_MISSIONS = 588;

  /**
   * Spec ceiling: warm p95 of the overview, in milliseconds. Amended from the initial 200 to 400 by CI-runner measurement (ADR
   * 2026-10-05-2; spec NFR-001): on the hosted 4-cpu Linux runner, at a load of about 3.9, the warm p95 measured 212 ms and then
   * 235 ms (floor 8.5 ms, ratio 27.75 against the limit 40, so the ratio assertion held both times): the same code, a slower and busier
   * machine, no regression. 400 ms leaves about 1.7 times the worst measured figure, still far under the 5 s cold ceiling, and stops a
   * test from waiting unbounded. The ratio below stays the primary assertion and is unchanged; a regression of the route (the 50 ms
   * sleep probe) is still caught by it. A further miss is classified, never retried, and amends this value only by a new measurement.
   */
  public static final double NFR001_WARM_P95_CEILING_MS = 400;

  /** Spec ceiling: the cold first call, in milliseconds. */
  public static final double NFR001_COLD_CEILING_MS = 5_000;

  /**
   * Warm p95 of the overview divided by the p95 of the no-op route (the contract document), same run, same connections. PROVISIONAL: the
   * spec gives only the 200 ms ceiling, and the operator ruled (2026-10-12) that this ratio must be tighter than the ceiling restated.
   * Measured locally (24 cores, shared machine): clean 21.9 to 26.0; with a 50 ms sleep in the overview route 48.8 to 51.2. The limit
   * 40 sits 1.5 times above the worst clean figure and 1.2 times below the sleep figure, so the sleep is red. A miss is classified under
   * ADR 2026-10-05-2 (runner noise versus a regression) and never retried; a CI-runner measurement amends this value.
   */
  public static final double NFR001_WARM_P95_RATIO_LIMIT = 40;

  /**
   * The cold first call divided by the same floor. PROVISIONAL. Measured locally: clean 44.4 to 55.3; with a 50 ms sleep 78.3 to 87.4.
   * The limit 70 is the one value that keeps the sleep red on the cold call too (it is 1.27 times above the worst clean figure and
   * 1.12 times below the lowest sleep figure); the operator's "about 90" would let the sleep through (78.3 and 87.4 are both under
   * 90). This margin is thin on a loaded runner: classify a cold miss before touching the value, never retry it.
   */
  public static final double NFR001_COLD_RATIO_LIMIT = 70;

  // ---- NFR-002: native start-up ------------------------------------------------------------------------------------------------

  /** Spec ceiling: the first accepted request within this many milliseconds of process start. */
  public static final double NFR002_STARTUP_CEILING_MS = 2_000;

  /**
   * Median start-up of the service binary divided by the median start-up of a trivial native binary built on the same leg, five
   * interleaved starts each (the ADR sampling). Set from the first local measurement; provisional until the CI legs report.
   */
  public static final double NFR002_STARTUP_RATIO_LIMIT = 60;

  // ---- NFR-004: 100 SSE connections, 60 s, 10 appends --------------------------------------------------------------------------

  public static final int NFR004_CONNECTIONS = 100;
  public static final int NFR004_APPENDS = 10;
  public static final int NFR004_HOLD_SECONDS = 60;

  /** Spec ceiling: platform threads rise by at most this many over the count before the connections open. */
  public static final int NFR004_THREADS_CEILING = 16;

  /** Spec ceiling: used heap after a forced collection rises by at most this many MiB (JVM leg). */
  public static final long NFR004_HEAP_CEILING_MIB = 64;

  /** Spec ceiling: the resident set of the native process grows by at most this many MiB. */
  public static final long NFR004_RSS_CEILING_MIB = 128;

  /**
   * Thread rise with 100 connections divided by the rise with ONE connection (the floor run, same fixture). The floor is clamped to
   * {@link #NFR004_THREADS_FLOOR_UNIT} so a floor of zero or one thread does not make the ratio meaningless.
   */
  public static final double NFR004_THREADS_RATIO_LIMIT = 2;

  public static final long NFR004_THREADS_FLOOR_UNIT = 4;

  /** Memory rise with 100 connections divided by the rise with ONE connection, the floor clamped to {@link #NFR004_MEMORY_FLOOR_UNIT_MIB}. */
  public static final double NFR004_MEMORY_RATIO_LIMIT = 8;

  public static final long NFR004_MEMORY_FLOOR_UNIT_MIB = 8;

  /**
   * Provisional wait (not an NFR-004 budget: the spec bounds threads, memory, reducer invocations and delivery, not connect time): every
   * connection has its 200 head within this many seconds. An unscoped connect sets a floor for every Mission under the feed's one lock, so
   * 100 connects over the 588-Mission fixture are serialized. Amended by measurement from 30 s on 2026-10-14: the windows-x64 native leg
   * opened 61, then 83, of 100 within 30 s (about 0.36 to 0.5 s per connect, so 50 to 80 s for all 100).
   */
  public static final int NFR004_OPEN_CEILING_SECONDS = 120;

  /** Provisional ceiling: every connection has every forwarded append within this many seconds of the last append. */
  public static final int NFR004_DELIVERY_CEILING_SECONDS = 10;
}
