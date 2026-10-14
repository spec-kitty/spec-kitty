package org.speckitty.missionstatus.application.query.port.in.exceptions;

/**
 * The service already holds {@code mission-status.stream.max-connections} open streams: the subscribe is refused before it costs
 * anything. Unchecked, with no message detail and no stack, so an adapter maps it to its own refusal (HTTP: 503).
 */
public final class StreamCapacityReached extends RuntimeException {

  private static final long serialVersionUID = 1L;

  public StreamCapacityReached() {
    super("stream capacity reached", null, false, false);
  }
}
