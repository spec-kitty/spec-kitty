package org.speckitty.missionstatus.nativesmoke;

import java.time.Duration;
import java.util.function.Supplier;

/**
 * The NFR-002 timer: the time from the moment BEFORE the process is started to the first accepted {@code GET /api/v1/project}
 * (the accepted Host {@code 127.0.0.1:<port>}; a 403 is the Host filter before the server knows its own port and does not count, and
 * neither does a refused connection). The clock starts before the launch call, because the launch is part of "process start", and
 * stops when the 200 has been read. {@code StartupProbeTest} proves both ends.
 */
final class StartupProbe {

  private static final Duration BOUND = Duration.ofSeconds(30);

  private StartupProbe() {}

  /** Starts the process with {@code launch}, waits for the first accepted answer, and returns the elapsed milliseconds with the process left running. */
  static Started start(Supplier<Replay.Running> launch, int port) {
    long begin = System.nanoTime();
    Replay.Running running = launch.get();
    try {
      long deadline = begin + BOUND.toNanos();
      while (System.nanoTime() < deadline) {
        running.requireAlive();
        int status = RawHttp.probe(port, "/api/v1/project");
        long answered = System.nanoTime();
        if (status == 200) {
          return new Started(running, (answered - begin) / 1_000_000.0);
        }
        if (status != 0 && status != 403) {
          throw new AssertionError("the first accepted request answered " + status + " instead of 200");
        }
        pause();
      }
      throw new AssertionError("no accepted answer within " + BOUND.toSeconds() + " s of process start");
    } catch (RuntimeException | Error failure) {
      running.close();
      throw failure;
    }
  }

  private static void pause() {
    try {
      Thread.sleep(2);
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException(interrupted);
    }
  }

  /** A process that answered, and how long that took from before its start. */
  record Started(Replay.Running running, double millis) implements AutoCloseable {
    @Override
    public void close() {
      running.close();
    }
  }
}
