package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.ThreadMXBean;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Locale;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * NFR-004 on the JVM leg: 100 unscoped event-stream connections held for 60 s over the generated corpus while 10 rows are appended to
 * different Missions. The floor of every budget is the SAME scenario with ONE connection, run first in this JVM (ADR 2026-10-05-2);
 * the spec's absolute figures stand beside each ratio as provisional ceilings. Reducer-invocation counts and delivery are exact, not
 * ratios. A miss fails once; there is no retry.
 */
@Tag("perf")
class Nfr004SseConnectionsTest {

  private static final int CONNECTIONS = PerfBudgets.NFR004_CONNECTIONS;
  private static final int APPENDS = PerfBudgets.NFR004_APPENDS;
  private static final Duration HOLD = Duration.ofSeconds(PerfBudgets.NFR004_HOLD_SECONDS);
  /** The one-connection floor only has to outlast its appends (1 s lead, 10 x 0.3 s), not the whole hold. */
  private static final Duration FLOOR_HOLD = Duration.ofSeconds(8);

  private static final double THREADS_RATIO_LIMIT = PerfBudgets.NFR004_THREADS_RATIO_LIMIT;
  private static final double MEMORY_RATIO_LIMIT = PerfBudgets.NFR004_MEMORY_RATIO_LIMIT;
  private static final int THREADS_CEILING = PerfBudgets.NFR004_THREADS_CEILING;
  private static final long HEAP_CEILING_MIB = PerfBudgets.NFR004_HEAP_CEILING_MIB;

  private static final ThreadMXBean THREAD_BEAN = ManagementFactory.getThreadMXBean();
  private static final MemoryMXBean MEMORY_BEAN = ManagementFactory.getMemoryMXBean();

  /** What one scenario measured. */
  private record Measured(int connections, long threadRise, long rawThreadRise, int peakCarriers, long heapRiseMib, int reducedAtConnect, int reducedAfterOverview, int[] received, long peakThreads, long threadsBefore, String threadNames) {}

  @Test
  void aHundredConnectionsCostNoMoreThanTheBudgetsOverOneConnection() {
    Measured floor = scenario(1, FLOOR_HOLD);
    Measured hundred = scenario(CONNECTIONS, HOLD);

    // (c) no per-connection rescan: connecting reduces nothing, and the appends cost the same number of reductions as with one connection
    assertThat(hundred.reducedAtConnect()).as("reducer invocations caused by connecting 100 clients").isEqualTo(floor.reducedAtConnect()).isZero();
    assertThat(hundred.reducedAfterOverview()).as("reducer invocations after the 100 connections and the appends").isEqualTo(floor.reducedAfterOverview()).isEqualTo(APPENDS);

    // (d) every connection received every forwarded append, and nothing else
    assertThat(hundred.received()).as("events per connection").hasSize(CONNECTIONS).containsOnly(APPENDS);
    assertThat(floor.received()).containsOnly(APPENDS);

    // (a) platform threads and (b) used heap after a forced collection: a ratio to the one-connection run, and the spec ceiling
    String hint = hint(hundred) + ", platform threads at the end: " + hundred.threadNames();
    RatioBudget.Outcome threads =
        RatioBudget.evaluate(
            "NFR-004 platform thread rise, net of virtual-thread carriers", hundred.threadRise(), Math.max(floor.threadRise(), PerfBudgets.NFR004_THREADS_FLOOR_UNIT), THREADS_RATIO_LIMIT, THREADS_CEILING, "threads", hint);
    RatioBudget.Outcome heap =
        RatioBudget.evaluate(
            "NFR-004 used heap rise after GC", hundred.heapRiseMib(), Math.max(floor.heapRiseMib(), PerfBudgets.NFR004_MEMORY_FLOOR_UNIT_MIB), MEMORY_RATIO_LIMIT, HEAP_CEILING_MIB, "MiB", hint);
    System.out.println(
        "PERF "
            + threads.line()
            + " [floor rise "
            + floor.threadRise()
            + ", peak "
            + hundred.peakThreads()
            + " from "
            + hundred.threadsBefore()
            + "; raw total rise "
            + hundred.rawThreadRise()
            + " with "
            + hundred.peakCarriers()
            + " carrier threads]; "
            + hint);
    assertThat(hundred.peakCarriers()).as("the carrier pool is capped by the core count, whatever the number of connections").isLessThanOrEqualTo(Runtime.getRuntime().availableProcessors());
    System.out.println("PERF " + heap.line() + " [floor rise " + floor.heapRiseMib() + " MiB]; " + hint);
  }

  private static Measured scenario(int connections, Duration hold) {
    Path root = MissionCorpus.write(PerfBudgets.NFR001_MISSIONS);
    try (PerfServer server = PerfServer.start(root);
        SseSwarm swarm = SseSwarm.start()) {
      // the cache is warm and the swarm's one thread exists before the baseline is taken
      Latency.timedGet(server.port(), "/api/v1/missions");
      long heapBefore = usedHeapAfterCollection();
      PlatformThreads.Count before = PlatformThreads.count();
      long threadsBefore = before.net();
      int[] peakCarriers = {before.carriers()};
      int[] peakTotal = {before.total()};
      int reducedBefore = server.reductions();
      int[] reducedAtConnect = new int[1];

      SseScenario.Outcome outcome =
          SseScenario.drive(
              swarm,
              server.port(),
              root,
              connections,
              APPENDS,
              hold,
              PerfBudgets.NFR001_MISSIONS,
              () -> {
                PlatformThreads.Count now = PlatformThreads.count();
                peakCarriers[0] = Math.max(peakCarriers[0], now.carriers());
                peakTotal[0] = Math.max(peakTotal[0], now.total());
                return now.net();
              },
              () -> reducedAtConnect[0] = server.reductions() - reducedBefore);
      SseScenario.requireDelivery(swarm, APPENDS, Duration.ofSeconds(PerfBudgets.NFR004_DELIVERY_CEILING_SECONDS));

      long peak = outcome.peakThreads();
      String threadNames = threadHistogram();
      long heapAfter = usedHeapAfterCollection();
      // the overview after the appends re-reduces exactly the appended Missions, however many connections are open
      Latency.timedGet(server.port(), "/api/v1/missions");
      int reducedAfterOverview = server.reductions() - reducedBefore;
      return new Measured(connections, peak - threadsBefore, peakTotal[0] - before.total(), peakCarriers[0], (heapAfter - heapBefore) / (1024 * 1024), reducedAtConnect[0], reducedAfterOverview, swarm.received(), peak, threadsBefore, threadNames);
    }
  }

  /** The live platform threads grouped by name without digits: the classification input of a thread-count miss. */
  private static String threadHistogram() {
    java.util.Map<String, Integer> byName = new java.util.TreeMap<>();
    for (java.lang.management.ThreadInfo info : THREAD_BEAN.dumpAllThreads(false, false)) {
      byName.merge(info.getThreadName().replaceAll("[0-9]+", "#"), 1, Integer::sum);
    }
    return byName.toString();
  }

  /** The number of GC-settled heap samples whose median is the used heap (pre-merge fold J10: a single sample ranged 20 to 82 MiB). */
  static final int HEAP_SAMPLES = 5;

  /** The median of {@link #HEAP_SAMPLES} readings, each taken after three collections and a settle. */
  private static long usedHeapAfterCollection() {
    long[] samples = new long[HEAP_SAMPLES];
    for (int sample = 0; sample < samples.length; sample++) {
      for (int i = 0; i < 3; i++) {
        System.gc();
        try {
          Thread.sleep(100);
        } catch (InterruptedException interrupted) {
          Thread.currentThread().interrupt();
          throw new IllegalStateException(interrupted);
        }
      }
      samples[sample] = MEMORY_BEAN.getHeapMemoryUsage().getUsed();
    }
    return median(samples);
  }

  static long median(long[] samples) {
    long[] sorted = samples.clone();
    java.util.Arrays.sort(sorted);
    return sorted[sorted.length / 2];
  }

  private static String hint(Measured run) {
    return String.format(
        Locale.ROOT,
        "%d connections, %d cpus, load %.2f",
        run.connections(),
        Runtime.getRuntime().availableProcessors(),
        ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage());
  }
}
