package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.OptionalLong;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.perf.MissionCorpus;
import org.speckitty.missionstatus.perf.PerfBudgets;
import org.speckitty.missionstatus.perf.RatioBudget;
import org.speckitty.missionstatus.perf.SseScenario;
import org.speckitty.missionstatus.perf.SseSwarm;

/**
 * The native legs of NFR-002 and NFR-004 (run by {@code nativePerf} with {@code -PnativeBinary=path}; never by {@code test} or {@code check}).
 * Every budget is a ratio to a floor sampled in the same run, with the spec's absolute figure beside it as a PROVISIONAL ceiling (ADR
 * 2026-10-05-2). A miss fails once and is classified; nothing is retried.
 *
 * <ul>
 *   <li>NFR-002: five interleaved start-ups of the service binary and of a trivial native binary built on the same leg (named by the
 *       environment variable {@value #FLOOR_ENVIRONMENT}); the ratio of the medians, and the median against the 2 s ceiling. When no
 *       floor binary exists the ratio is recorded as UNMEASURED and the ceiling alone is asserted (the spec permits it).
 *   <li>NFR-004: the one-connection run is the floor of the 100-connection run; threads and resident set are read from the operating
 *       system. A figure the leg cannot measure is recorded as "not measurable on this leg", never skipped silently.
 * </ul>
 */
@Tag("native-binary")
class NativePerfTest {

  static final String FLOOR_ENVIRONMENT = "MISSION_STATUS_FLOOR_BINARY";

  private static final double STARTUP_RATIO_LIMIT = PerfBudgets.NFR002_STARTUP_RATIO_LIMIT;
  private static final double STARTUP_CEILING_MS = PerfBudgets.NFR002_STARTUP_CEILING_MS;
  private static final double THREADS_RATIO_LIMIT = PerfBudgets.NFR004_THREADS_RATIO_LIMIT;
  private static final double MEMORY_RATIO_LIMIT = PerfBudgets.NFR004_MEMORY_RATIO_LIMIT;
  private static final int THREADS_CEILING = PerfBudgets.NFR004_THREADS_CEILING;
  private static final long RSS_CEILING_MIB = PerfBudgets.NFR004_RSS_CEILING_MIB;
  private static final int STARTS = 5;
  private static final Duration FLOOR_HOLD = Duration.ofSeconds(8);

  @Test
  void theFirstRequestIsAcceptedWithinTheCeilingAndTheRatioToATrivialNativeBinary() {
    Path binary = binary();
    Path floorBinary = floorBinary();
    Path root = MissionCorpus.write(3);
    List<Double> service = new ArrayList<>();
    List<Double> floor = new ArrayList<>();
    for (int round = 0; round < STARTS; round++) {
      // the order flips on odd rounds, so a drift of the machine does not favour either side
      if (round % 2 == 0) {
        service.add(startService(binary, root));
        if (floorBinary != null) {
          floor.add(startFloor(floorBinary));
        }
      } else {
        if (floorBinary != null) {
          floor.add(startFloor(floorBinary));
        }
        service.add(startService(binary, root));
      }
    }
    double serviceMedian = median(service);
    String line;
    if (floorBinary == null) {
      assertThat(serviceMedian).as("NFR-002 median start-up (ms), ceiling only: no trivial-binary floor on this leg").isLessThanOrEqualTo(STARTUP_CEILING_MS);
      line = String.format(Locale.ROOT, "NFR-002 start-up: median %.1f ms of %s, ceiling %.0f ms; ratio UNMEASURED (no trivial native binary on this leg)", serviceMedian, service, STARTUP_CEILING_MS);
    } else {
      RatioBudget.Outcome outcome =
          RatioBudget.evaluate("NFR-002 median start-up", serviceMedian, median(floor), STARTUP_RATIO_LIMIT, STARTUP_CEILING_MS, "ms", runHint());
      line = outcome.line() + " [service " + service + " ms; floor " + floor + " ms]";
    }
    record(line);
  }

  @Test
  void aHundredConnectionsCostNoMoreNativeMemoryAndThreadsThanTheBudgetsOverOneConnection() {
    Path binary = binary();
    NativeRun floor = nativeScenario(binary, 1, FLOOR_HOLD);
    NativeRun hundred = nativeScenario(binary, PerfBudgets.NFR004_CONNECTIONS, Duration.ofSeconds(PerfBudgets.NFR004_HOLD_SECONDS));

    // (d) every connection received every forwarded append, and nothing else
    assertThat(hundred.received()).as("events per connection").hasSize(PerfBudgets.NFR004_CONNECTIONS).containsOnly(PerfBudgets.NFR004_APPENDS);
    assertThat(floor.received()).containsOnly(PerfBudgets.NFR004_APPENDS);

    List<String> lines = new ArrayList<>();
    // the carrier pool is per process and capped by the core count, whatever the number of connections (amended NFR-004(a))
    assertThat(hundred.peakCarriers()).as("native virtual-thread carriers at the peak, at most the core count").isLessThanOrEqualTo(Runtime.getRuntime().availableProcessors());
    if (hundred.threadsMeasured() && floor.threadsMeasured()) {
      RatioBudget.Outcome threads =
          RatioBudget.evaluate(
              "NFR-004 native thread rise, net of virtual-thread carriers",
              hundred.threadRise(),
              Math.max(floor.threadRise(), PerfBudgets.NFR004_THREADS_FLOOR_UNIT),
              THREADS_RATIO_LIMIT,
              THREADS_CEILING,
              "threads",
              runHint() + ", threads at the end: " + hundred.names());
      lines.add(threads.line() + " [floor rise " + floor.threadRise() + "; peak " + hundred.peakThreads() + " from " + hundred.threadsBefore() + "]");
    } else {
      lines.add("NFR-004 native thread rise: not measurable on this leg (the JVM leg carries the proof)");
    }
    if (hundred.rssMeasured() && floor.rssMeasured()) {
      RatioBudget.Outcome memory =
          RatioBudget.evaluate(
              "NFR-004 native resident set rise",
              hundred.rssRiseMib(),
              Math.max(floor.rssRiseMib(), PerfBudgets.NFR004_MEMORY_FLOOR_UNIT_MIB),
              MEMORY_RATIO_LIMIT,
              RSS_CEILING_MIB,
              "MiB",
              runHint());
      // PROVISIONAL: the one-connection floor is GC noise (local floor rises of 42 to 60 MiB against -5 to 11 MiB for 100 connections), so until a CI run re-measures it the 128 MiB ceiling is what actually protects.
      lines.add(memory.line() + " [floor rise " + floor.rssRiseMib() + " MiB]");
    } else {
      lines.add("NFR-004 native resident set rise: not measurable on this leg (the JVM leg carries the proof)");
    }
    lines.add("NFR-004 delivery: all " + PerfBudgets.NFR004_CONNECTIONS + " connections received all " + PerfBudgets.NFR004_APPENDS + " appends; reducer counter not observable on a binary (JVM leg)");
    lines.forEach(NativePerfTest::record);
  }

  // ---- NFR-002 --------------------------------------------------------------------------------------------------------------

  private static double startService(Path binary, Path root) {
    int port = port();
    try (StartupProbe.Started started = StartupProbe.start(() -> new NativeSmokeTest.BinaryProcess(binary, root, port), port)) {
      return started.millis();
    }
  }

  private static double startFloor(Path floorBinary) {
    int port = port();
    try (StartupProbe.Started started = StartupProbe.start(() -> new FloorProcess(floorBinary, port), port)) {
      return started.millis();
    }
  }

  private static double median(List<Double> values) {
    List<Double> sorted = new ArrayList<>(values);
    Collections.sort(sorted);
    return sorted.get(sorted.size() / 2);
  }

  /** The trivial native binary: it listens on the port in its first argument and answers 200 to anything. */
  private static final class FloorProcess implements Replay.Running {
    private final Process process;

    FloorProcess(Path binary, int port) {
      try {
        this.process = new ProcessBuilder(binary.toString(), Integer.toString(port)).redirectErrorStream(true).redirectOutput(ProcessBuilder.Redirect.DISCARD).start();
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }

    @Override
    public void requireAlive() {
      if (!process.isAlive()) {
        throw new AssertionError("the trivial binary exited early with status " + process.exitValue());
      }
    }

    @Override
    public OptionalLong childProcesses() {
      return OptionalLong.empty();
    }

    @Override
    public void close() {
      process.destroy();
      try {
        if (!process.waitFor(10, TimeUnit.SECONDS)) {
          process.destroyForcibly();
        }
      } catch (InterruptedException interrupted) {
        Thread.currentThread().interrupt();
        process.destroyForcibly();
      }
    }
  }

  // ---- NFR-004 --------------------------------------------------------------------------------------------------------------

  private record NativeRun(long peakCarriers, String names, boolean threadsMeasured, long threadRise, long peakThreads, long threadsBefore, boolean rssMeasured, long rssRiseMib, int[] received) {}

  private static NativeRun nativeScenario(Path binary, int connections, Duration hold) {
    Path root = MissionCorpus.write(PerfBudgets.NFR001_MISSIONS);
    int port = port();
    try (StartupProbe.Started started = StartupProbe.start(() -> new NativeSmokeTest.BinaryProcess(binary, root, port), port);
        SseSwarm swarm = SseSwarm.start()) {
      long pid = ((NativeSmokeTest.BinaryProcess) started.running()).pid();
      // the first overview fills the cache (the 588 ledgers are read and reduced once), as the JVM leg does before its baseline
      RawHttp.exchange(port, "GET", "/api/v1/missions", java.util.Map.of());
      OptionalLong threadsBefore = netThreads(pid);
      OptionalLong rssBefore = ProcessMetrics.residentBytes(pid);

      long[] peakCarriers = {ProcessMetrics.carriers(pid).orElse(0)};
      SseScenario.Outcome outcome =
          SseScenario.drive(
              swarm,
              port,
              root,
              connections,
              PerfBudgets.NFR004_APPENDS,
              hold,
              PerfBudgets.NFR001_MISSIONS,
              () -> {
                long carriers = ProcessMetrics.carriers(pid).orElse(0);
                peakCarriers[0] = Math.max(peakCarriers[0], carriers);
                return ProcessMetrics.threads(pid).orElse(0) - carriers;
              },
              () -> {});
      SseScenario.requireDelivery(swarm, PerfBudgets.NFR004_APPENDS, Duration.ofSeconds(PerfBudgets.NFR004_DELIVERY_CEILING_SECONDS));
      String names = ProcessMetrics.threadNames(pid);
      OptionalLong rssAfter = ProcessMetrics.residentBytes(pid);
      boolean threads = threadsBefore.isPresent() && outcome.peakThreads() > 0;
      boolean rss = rssBefore.isPresent() && rssAfter.isPresent();
      return new NativeRun(
          peakCarriers[0],
          names,
          threads,
          threads ? outcome.peakThreads() - threadsBefore.getAsLong() : 0,
          outcome.peakThreads(),
          threadsBefore.orElse(0),
          rss,
          rss ? (rssAfter.getAsLong() - rssBefore.getAsLong()) / (1024 * 1024) : 0,
          swarm.received());
    }
  }

  /** Threads of the process net of the virtual-thread carrier pool (raw when the leg cannot name threads). */
  private static OptionalLong netThreads(long pid) {
    OptionalLong threads = ProcessMetrics.threads(pid);
    return threads.isPresent() ? OptionalLong.of(threads.getAsLong() - ProcessMetrics.carriers(pid).orElse(0)) : threads;
  }

  // ---- shared ---------------------------------------------------------------------------------------------------------------

  private static Path binary() {
    String binary = System.getProperty("nativeBinary");
    assertThat(binary).as("the nativeBinary system property (-PnativeBinary)").isNotBlank();
    return Path.of(binary);
  }

  /** The trivial native binary of this leg, or null when the leg did not build one. */
  private static Path floorBinary() {
    String path = System.getenv(FLOOR_ENVIRONMENT);
    if (path == null || path.isBlank()) {
      return null;
    }
    // the leg promised a floor and did not deliver it: that is a failure, not a quiet ceiling-only run
    assertThat(Path.of(path)).as(FLOOR_ENVIRONMENT + " is set but names no file").isRegularFile();
    return Path.of(path);
  }

  private static int port() {
    return Replay.freePort();
  }

  private static String runHint() {
    return String.format(
        Locale.ROOT,
        "%s-%s, %d cpus, load %.2f",
        Digest.osToken(System.getProperty("os.name")),
        Digest.archToken(System.getProperty("os.arch")),
        Runtime.getRuntime().availableProcessors(),
        ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage());
  }

  /** Prints the line and appends it to the leg's perf summary, which the workflow adds to the job summary. */
  private static void record(String line) {
    System.out.println("PERF " + line);
    try {
      Files.createDirectories(NativeSmokeTest.OUTPUT);
      String name = "perf-summary-" + Digest.osToken(System.getProperty("os.name")) + "-" + Digest.archToken(System.getProperty("os.arch")) + ".txt";
      Files.writeString(NativeSmokeTest.OUTPUT.resolve(name), line + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
