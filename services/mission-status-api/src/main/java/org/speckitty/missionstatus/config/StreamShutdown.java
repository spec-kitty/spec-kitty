package org.speckitty.missionstatus.config;

import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;

/**
 * Shutting down ends every open stream first, so the container's graceful shutdown does not wait on connections that never finish. The
 * Spring event stays here because the application layer may not use Spring; a destroy method would run after the web server's graceful
 * shutdown had already waited, which is why this is a listener. It calls the primary inbound port, the bean the controllers use.
 */
@Configuration(proxyBeanMethods = false)
class StreamShutdown {

  private final MissionStatusQuery query;

  StreamShutdown(MissionStatusQuery query) {
    this.query = query;
  }

  @EventListener(ContextClosedEvent.class)
  void endStreams() {
    query.endStreams();
  }
}
