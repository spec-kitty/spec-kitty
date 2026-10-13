package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.management.ManagementFactory;
import java.nio.file.Path;
import java.util.Locale;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * NFR-001: overview latency over {@value PerfBudgets#NFR001_MISSIONS} generated Missions, as a ratio to a floor sampled in the same run
 * (ADR 2026-10-05-2) with the spec's absolute figures beside it as provisional ceilings.
 *
 * <p>The floor is {@code GET /api/v1/openapi.yaml}: the cheapest route of the service, a classpath read with no Mission access, so it
 * pays for the connection, the Host filter, the servlet container and the response and nothing of the cache. Both routes are timed
 * over the same number of connections, in alternating rounds, after a discarded warm-up. A miss fails once: there is no retry.
 */
@Tag("perf")
class Nfr001OverviewLatencyTest {

  private static final String FLOOR_ROUTE = "/api/v1/openapi.yaml";
  private static final String OVERVIEW = "/api/v1/missions";
  private static final int CONNECTIONS = 4;
  private static final int WARMUP_PER_CONNECTION = 50;
  private static final int SAMPLES_PER_CONNECTION = 150;
  private static final int ROUNDS = 2;

  private static final double WARM_P95_RATIO_LIMIT = PerfBudgets.NFR001_WARM_P95_RATIO_LIMIT;
  private static final double COLD_RATIO_LIMIT = PerfBudgets.NFR001_COLD_RATIO_LIMIT;
  private static final double WARM_P95_CEILING_MS = PerfBudgets.NFR001_WARM_P95_CEILING_MS;
  private static final double COLD_CEILING_MS = PerfBudgets.NFR001_COLD_CEILING_MS;

  @Test
  void theWarmOverviewP95IsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    try (PerfServer server = PerfServer.start(MissionCorpus.write(PerfBudgets.NFR001_MISSIONS))) {
      // the first call fills the cache; the warm-up of both routes is discarded (state warm-up counts)
      Latency.timedGet(server.port(), OVERVIEW);
      Latency.run(server.port(), OVERVIEW, CONNECTIONS, WARMUP_PER_CONNECTION);
      Latency.run(server.port(), FLOOR_ROUTE, CONNECTIONS, WARMUP_PER_CONNECTION);

      long[] floor = new long[0];
      long[] overview = new long[0];
      for (int round = 0; round < ROUNDS; round++) {
        floor = Latency.concat(floor, Latency.run(server.port(), FLOOR_ROUTE, CONNECTIONS, SAMPLES_PER_CONNECTION));
        overview = Latency.concat(overview, Latency.run(server.port(), OVERVIEW, CONNECTIONS, SAMPLES_PER_CONNECTION));
      }
      double floorP95 = Latency.p95Ms(floor);
      double overviewP95 = Latency.p95Ms(overview);

      RatioBudget.Outcome outcome = RatioBudget.evaluate("NFR-001 warm overview p95", overviewP95, floorP95, WARM_P95_RATIO_LIMIT, WARM_P95_CEILING_MS, "ms", hint());
      System.out.println("PERF " + outcome.line() + " [" + overview.length + " samples each, " + CONNECTIONS + " connections, " + PerfBudgets.NFR001_MISSIONS + " Missions]; " + hint());
      assertThat(server.source().calls("readLedger")).as("only the first call read ledgers (588), the warm calls none").isEqualTo(PerfBudgets.NFR001_MISSIONS);
    }
  }

  @Test
  void theColdFirstCallIsWithinTheRatioToTheNoOpRouteAndUnderTheCeiling() {
    warmTheJvmOnASmallFixture();
    try (PerfServer server = PerfServer.start(MissionCorpus.write(PerfBudgets.NFR001_MISSIONS))) {
      double coldMs = Latency.timedGet(server.port(), OVERVIEW) / 1_000_000.0;
      Latency.run(server.port(), FLOOR_ROUTE, CONNECTIONS, WARMUP_PER_CONNECTION);
      double floorP95 = Latency.p95Ms(Latency.run(server.port(), FLOOR_ROUTE, CONNECTIONS, SAMPLES_PER_CONNECTION));

      RatioBudget.Outcome outcome = RatioBudget.evaluate("NFR-001 cold first call", coldMs, floorP95, COLD_RATIO_LIMIT, COLD_CEILING_MS, "ms", hint());
      System.out.println("PERF " + outcome.line() + "; " + hint());
      assertThat(server.source().calls("readLedger")).as("the cold call read every ledger once").isEqualTo(PerfBudgets.NFR001_MISSIONS);
    }
  }

  @Test
  void aCallAfterOneAppendedEventReReducesOneMissionAndReadsOneLedger() {
    Path root = MissionCorpus.write(PerfBudgets.NFR001_MISSIONS);
    try (PerfServer server = PerfServer.start(root)) {
      Latency.timedGet(server.port(), OVERVIEW);
      assertThat(server.reductions()).as("the first call reduced every Mission once").isEqualTo(PerfBudgets.NFR001_MISSIONS);

      // (d) a warm call: a stat per Mission, no whole-ledger read, no reduction
      int stamps = server.source().calls("stampLedger");
      int reads = server.source().calls("readLedger");
      int reductions = server.reductions();
      Latency.timedGet(server.port(), OVERVIEW);
      assertThat(server.source().calls("readLedger") - reads).as("a warm call performs zero readLedger calls").isZero();
      assertThat(server.reductions() - reductions).as("a warm call re-reduces nothing").isZero();
      assertThat(server.source().calls("stampLedger") - stamps).as("a warm call stamps every Mission once").isEqualTo(PerfBudgets.NFR001_MISSIONS);

      // (c) one appended event
      MissionCorpus.appendRow(root, 17, 1);
      stamps = server.source().calls("stampLedger");
      reads = server.source().calls("readLedger");
      reductions = server.reductions();
      Latency.timedGet(server.port(), OVERVIEW);
      assertThat(server.reductions() - reductions).as("the call after one appended event re-reduces ONE Mission").isEqualTo(1);
      assertThat(server.source().calls("readLedger") - reads).as("and reads ONE ledger").isEqualTo(1);
      assertThat(server.source().calls("stampLedger") - stamps).as("but stamps every Mission").isEqualTo(PerfBudgets.NFR001_MISSIONS);
    }
  }

  /** Class loading and JIT of the request path, so that the cold figure measures the empty cache and not the first use of the JVM. */
  private static void warmTheJvmOnASmallFixture() {
    try (PerfServer small = PerfServer.start(MissionCorpus.write(24))) {
      Latency.run(small.port(), OVERVIEW, 2, 40);
      Latency.run(small.port(), FLOOR_ROUTE, 2, 40);
    }
  }

  private static String hint() {
    return String.format(
        Locale.ROOT,
        "%d cpus, load %.2f, %d platform threads",
        Runtime.getRuntime().availableProcessors(),
        ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage(),
        ManagementFactory.getThreadMXBean().getThreadCount());
  }
}
