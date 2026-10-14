package org.speckitty.missionstatus.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * The service's own configuration keys. {@code mission-status.project-root} is required (the project-root guard refuses an unset or
 * non-directory value before the web server starts), {@code mission-status.port} (default 8787, 0 for an ephemeral port) feeds
 * {@code server.port} in the packaged defaults, and the stream keys are read by the wiring and by the events controller.
 *
 * @param projectRoot the project directory the service reads
 * @param stream the stream knobs
 */
@ConfigurationProperties("mission-status")
public record MissionStatusProperties(String projectRoot, @DefaultValue Stream stream) {

  /**
   * @param queueCapacity the capacity of each subscriber's queue (key {@code mission-status.stream.queue-capacity}, default 1024)
   * @param heartbeatInterval how often an idle stream sends its heartbeat comment (key {@code mission-status.stream.heartbeat-interval},
   *     an ISO-8601 duration, default {@code PT30S}; the event stream reads this key)
   */
  public record Stream(@DefaultValue("1024") int queueCapacity, @DefaultValue("PT30S") Duration heartbeatInterval) {}
}
