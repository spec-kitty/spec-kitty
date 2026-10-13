package org.speckitty.missionstatus.application.query.stream;

import java.time.Duration;
import java.util.Objects;

/** The stream knobs: the poll tick, the re-list interval for Mission discovery, and the capacity of each subscriber's queue. */
public record StreamSettings(Duration pollInterval, Duration relistInterval, int queueCapacity) {

  public static final int DEFAULT_QUEUE_CAPACITY = 1024;

  public StreamSettings {
    Objects.requireNonNull(pollInterval, "pollInterval");
    Objects.requireNonNull(relistInterval, "relistInterval");
    if (pollInterval.isNegative() || pollInterval.isZero()) {
      throw new IllegalArgumentException("pollInterval must be positive");
    }
    if (queueCapacity < 1) {
      throw new IllegalArgumentException("queueCapacity must be at least 1");
    }
  }

  /** A 500 ms poll tick, a 1 s re-list and a queue of 1024 signals. */
  public static StreamSettings defaults() {
    return new StreamSettings(Duration.ofMillis(500), Duration.ofSeconds(1), DEFAULT_QUEUE_CAPACITY);
  }

  public StreamSettings withQueueCapacity(int capacity) {
    return new StreamSettings(pollInterval, relistInterval, capacity);
  }
}
