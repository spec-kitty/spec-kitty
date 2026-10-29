package org.speckitty.missionstatus.spike.lockinterop;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;

/**
 * One way a Java writer can take the interim event-log lock file of {@code kernel.event_log_append}. The spike runs every scenario once
 * per implementation, so the report can say which of them excludes the Python writer on which OS.
 */
interface JavaLock {

  /** A held lock; closing it releases the lock and the file handle. */
  interface Held extends AutoCloseable {
    @Override
    void close() throws IOException;
  }

  /** The name in the spike results. */
  String name();

  /** One non-blocking attempt; {@code null} when another holder has the lock. */
  Held tryAcquire(Path lockFile) throws IOException;

  /** Retries {@link #tryAcquire} until it succeeds or {@code timeout} elapses (the Python side polls the same way). */
  default Held acquire(Path lockFile, Duration timeout) throws IOException, InterruptedException {
    long deadline = System.nanoTime() + timeout.toNanos();
    while (true) {
      Held held = tryAcquire(lockFile);
      if (held != null) {
        return held;
      }
      if (System.nanoTime() >= deadline) {
        throw new IOException(name() + ": lock " + lockFile + " not acquired within " + timeout);
      }
      Thread.sleep(1);
    }
  }
}
