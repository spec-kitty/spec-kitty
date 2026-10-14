package org.speckitty.missionstatus.perf;

import java.nio.file.Path;
import java.time.Duration;
import java.util.function.LongSupplier;

/**
 * The NFR-004 scenario, shared by the JVM leg and the native leg: connect, hold, append rows to different Missions, check delivery.
 * The caller creates the {@link SseSwarm} BEFORE it takes its baseline (so the swarm's one thread is part of the baseline), and measures
 * heap or resident set itself around this call. The connections stay open when it returns; the caller closes the swarm.
 */
public final class SseScenario {

  /** What the hold saw. */
  public record Outcome(int connections, int appends, long peakThreads, int[] received, Duration held) {}

  private static final Duration SAMPLE_EVERY = Duration.ofMillis(200);
  private static final Duration APPEND_EVERY = Duration.ofMillis(300);
  /** The hold is the measuring window; the appends may run past it, up to this deadline, when the machine is loaded. */
  private static final Duration APPEND_DEADLINE = Duration.ofSeconds(30);

  private SseScenario() {}

  /**
   * @param threads the thread count of the service (ThreadMXBean on the JVM leg, the process thread count on the native leg), sampled
   *     every 200 ms of the hold; the peak is the largest sample
   * @param afterConnect called once, when every connection has its 200 head and before the first append (the reducer counter is read here)
   */
  public static Outcome drive(
      SseSwarm swarm, int port, Path root, int connections, int appends, Duration hold, int missions, LongSupplier threads, Runnable afterConnect) {
    swarm.connect(port, connections);
    swarm.awaitOpen(connections, Duration.ofSeconds(PerfBudgets.NFR004_OPEN_CEILING_SECONDS));
    afterConnect.run();

    long peak = threads.getAsLong();
    long start = System.nanoTime();
    long end = start + hold.toNanos();
    long deadline = start + Math.max(hold.toNanos(), APPEND_DEADLINE.toNanos());
    long nextAppend = start + Duration.ofSeconds(1).toNanos();
    int appended = 0;
    while (System.nanoTime() < end || (appended < appends && System.nanoTime() < deadline)) {
      peak = Math.max(peak, threads.getAsLong());
      if (appended < appends && System.nanoTime() >= nextAppend) {
        // different Missions, spread over the corpus
        MissionCorpus.appendRow(root, (appended * (missions / appends) + 3) % missions, appended + 1);
        appended++;
        nextAppend += APPEND_EVERY.toNanos();
      }
      pause(SAMPLE_EVERY.toMillis() / 2);
    }
    peak = Math.max(peak, threads.getAsLong());
    if (appended < appends) {
      throw new AssertionError("only " + appended + " of " + appends + " rows were appended within " + APPEND_DEADLINE.toSeconds() + " s");
    }
    return new Outcome(connections, appends, peak, swarm.received(), Duration.ofNanos(System.nanoTime() - start));
  }

  /** Fails once, naming how far delivery got, when a connection lacks an append after the provisional delivery ceiling. */
  public static void requireDelivery(SseSwarm swarm, int appends, Duration ceiling) {
    if (!swarm.awaitEveryConnectionHas(appends, ceiling)) {
      int[] received = swarm.received();
      int min = Integer.MAX_VALUE;
      int max = 0;
      int complete = 0;
      for (int count : received) {
        min = Math.min(min, count);
        max = Math.max(max, count);
        if (count >= appends) {
          complete++;
        }
      }
      throw new AssertionError(
          "delivery: " + complete + " of " + received.length + " connections have all " + appends + " appends after " + ceiling.toSeconds() + " s (fewest " + min + ", most " + max
              + "). Classify under ADR 2026-10-05-2; not retried.");
    }
  }

  private static void pause(long millis) {
    try {
      Thread.sleep(millis);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }
}
