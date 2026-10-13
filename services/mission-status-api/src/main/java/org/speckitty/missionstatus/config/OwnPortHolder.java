package org.speckitty.missionstatus.config;

import org.speckitty.missionstatus.adapter.in.http.OwnPortSource;
import org.springframework.boot.web.server.context.WebServerInitializedEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.stereotype.Component;

/**
 * The port the web server is actually bound to, taken from the bound server when it has started, so a configured port 0 (an ephemeral
 * port) works and the accepted Host forms always name the port a client really connected to. Until then the port is -1 and the filter
 * accepts nothing.
 */
@Component
class OwnPortHolder implements OwnPortSource, ApplicationListener<WebServerInitializedEvent> {

  private volatile int port = -1;

  @Override
  public int port() {
    return port;
  }

  @Override
  public void onApplicationEvent(WebServerInitializedEvent event) {
    port = event.getWebServer().getPort();
  }
}
