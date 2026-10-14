package org.speckitty.missionstatus.application.query.stream;

import java.time.Duration;
import java.util.Objects;

/**
 * The stream knobs: the poll tick, the re-list interval for Mission discovery, the capacity of each subscriber's queue and the bound on
 * open streams (one cap for every inbound adapter of the service).
 */
public record StreamSettings(Duration pollInterval, Duration relistInterval, int queueCapacity, int maxConnections) {

  public static final int DEFAULT_QUEUE_CAPACITY = 1024;

  /** The default bound on open streams; the packaged {@code application.properties} says the same. */
  public static final int DEFAULT_MAX_CONNECTIONS = 128;

  public StreamSettings {
    Objects.requireNonNull(pollInterval, "pollInterval");
    Objects.requireNonNull(relistInterval, "relistInterval");
    if (pollInterval.isNegative() || pollInterval.isZero()) {
      throw new IllegalArgumentException("pollInterval must be positive");
    }
    if (queueCapacity < 1) {
      throw new IllegalArgumentException("queueCapacity must be at least 1");
    }
    if (maxConnections < 1) {
      throw new IllegalArgumentException("mission-status.stream.max-connections must be at least 1");
    }
  }

  /** The three feed knobs, with the default bound on open streams. */
  public StreamSettings(Duration pollInterval, Duration relistInterval, int queueCapacity) {
    this(pollInterval, relistInterval, queueCapacity, DEFAULT_MAX_CONNECTIONS);
  }

  /** A 500 ms poll tick, a 1 s re-list, a queue of 1024 signals and 128 open streams. */
  public static StreamSettings defaults() {
    return new StreamSettings(Duration.ofMillis(500), Duration.ofSeconds(1), DEFAULT_QUEUE_CAPACITY, DEFAULT_MAX_CONNECTIONS);
  }

  public StreamSettings withQueueCapacity(int capacity) {
    return new StreamSettings(pollInterval, relistInterval, capacity, maxConnections);
  }

  public StreamSettings withMaxConnections(int connections) {
    return new StreamSettings(pollInterval, relistInterval, queueCapacity, connections);
  }
}
