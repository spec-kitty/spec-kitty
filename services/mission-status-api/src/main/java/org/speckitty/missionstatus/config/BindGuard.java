package org.speckitty.missionstatus.config;

import java.net.InetAddress;
import java.util.Optional;
import org.apache.catalina.connector.Connector;
import org.springframework.boot.context.event.ApplicationEnvironmentPreparedEvent;
import org.springframework.boot.tomcat.TomcatWebServer;
import org.springframework.boot.web.server.WebServer;
import org.springframework.boot.web.server.context.WebServerInitializedEvent;
import org.springframework.context.ApplicationListener;

/**
 * The loopback-only bind (AC-9a). Before the web server starts, the EFFECTIVE {@code server.address} must be the literal
 * {@code 127.0.0.1}: any other value exits non-zero naming the address, an absent or blank one exits non-zero naming "unset" (Boot
 * would otherwise bind every interface). After the server starts, the address the connector was configured with must be a loopback
 * address and never null (null means all interfaces); the public accessors echo the configured address, not the socket's (research.md,
 * Unverified 19), so the pre-start check is the real guard. A port already in use is Boot's own start-up failure (non-zero, names the
 * port).
 */
public final class BindGuard {

  public static final String KEY = "server.address";
  public static final String LOOPBACK = "127.0.0.1";

  /**
   * Set by Spring's AOT processor while it runs main() at build time, when no server starts and no root is given. Spring offers no
   * signal for "inside AOT processing" that a user cannot also set, so the property is accepted as a skip condition for ONE case only:
   * an unset or blank {@code server.address}. A non-blank address that is not loopback is refused before start under the switch too,
   * so a hand-set property buys nothing; {@link AfterStart} (which has no such skip) remains as the second line.
   */
  private static final String AOT_PROCESSING = "spring.aot.processing";

  private BindGuard() {}

  /** The reason the effective value is refused, or empty when it is the literal loopback address. */
  public static Optional<String> refusal(String address) {
    if (address == null || address.isBlank()) {
      return Optional.of(KEY + ": unset; the service binds " + LOOPBACK + " only (refusing to start on all interfaces)");
    }
    if (!address.equals(LOOPBACK)) {
      return Optional.of(KEY + ": refused address " + address.trim() + "; the service binds " + LOOPBACK + " only");
    }
    return Optional.empty();
  }

  /** The reason the connector's configured address is refused, or empty when it is loopback. */
  public static Optional<String> connectorRefusal(InetAddress configured) {
    if (configured == null) {
      return Optional.of(KEY + ": the connector is bound to all interfaces; the service binds " + LOOPBACK + " only");
    }
    if (!configured.isLoopbackAddress()) {
      return Optional.of(KEY + ": the connector is bound to " + configured.getHostAddress() + "; the service binds " + LOOPBACK + " only");
    }
    return Optional.empty();
  }

  /** The address the connector was configured with (null: all interfaces), or null for a web server that is not Tomcat. */
  public static InetAddress configuredAddress(WebServer server) {
    if (server instanceof TomcatWebServer tomcat) {
      Connector connector = tomcat.getTomcat().getConnector();
      Object address = connector.getProperty("address");
      return address instanceof InetAddress inet ? inet : null;
    }
    return null;
  }

  /** Before the web server starts: exits non-zero when the effective address is not the loopback literal. */
  public static final class BeforeStart implements ApplicationListener<ApplicationEnvironmentPreparedEvent> {
    @Override
    public void onApplicationEvent(ApplicationEnvironmentPreparedEvent event) {
      String address = event.getEnvironment().getProperty(KEY);
      if (Boolean.getBoolean(AOT_PROCESSING) && (address == null || address.isBlank())) {
        return;
      }
      Optional<String> refusal = refusal(address);
      if (refusal.isPresent()) {
        System.err.println(refusal.get());
        System.exit(1);
      }
    }
  }

  /** After the web server starts: exits non-zero when the connector is not bound to loopback. */
  public static final class AfterStart implements ApplicationListener<WebServerInitializedEvent> {
    @Override
    public void onApplicationEvent(WebServerInitializedEvent event) {
      WebServer server = event.getWebServer();
      if (!(server instanceof TomcatWebServer)) {
        return;
      }
      Optional<String> refusal = connectorRefusal(configuredAddress(server));
      if (refusal.isPresent()) {
        System.err.println(refusal.get());
        System.exit(1);
      }
    }
  }
}
