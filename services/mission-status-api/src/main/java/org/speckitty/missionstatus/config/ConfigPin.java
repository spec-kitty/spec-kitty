package org.speckitty.missionstatus.config;

import java.util.Map;
import org.springframework.boot.context.event.ApplicationEnvironmentPreparedEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.core.Ordered;
import org.springframework.core.env.MapPropertySource;

/**
 * Pins the configuration to the packaged {@code application.properties} (security fold, 2026-10-13). Boot's defaults also read
 * {@code ./config/application.properties} and {@code ./application.properties} from the WORKING DIRECTORY, and
 * {@code SPRING_CONFIG_LOCATION}, {@code SPRING_CONFIG_ADDITIONAL_LOCATION} and {@code spring.config.import} can add more: a service
 * started from inside an untrusted project would let that project reconfigure it (serve any file through the static-resource handler,
 * write a log file anywhere). The pin is a property source placed FIRST, before Boot loads its configuration data, so neither the working
 * directory, the environment nor the command line can widen it. Command-line {@code --mission-status.*} and {@code --server.*} keys
 * still apply: only the places a configuration FILE is read from are fixed.
 *
 * <p>It is registered in {@code META-INF/spring.factories} with the bind guard, so it holds in every application context, whether
 * started by {@code main()} or by a test, and in the native binary.
 */
public final class ConfigPin implements ApplicationListener<ApplicationEnvironmentPreparedEvent>, Ordered {

  /** The only configuration file read. */
  public static final String LOCATION = "classpath:/application.properties";

  static final String SOURCE_NAME = "missionStatusConfigPin";

  /** Before Boot's own configuration-data loader ({@code HIGHEST_PRECEDENCE + 10}). */
  @Override
  public int getOrder() {
    return Ordered.HIGHEST_PRECEDENCE;
  }

  @Override
  public void onApplicationEvent(ApplicationEnvironmentPreparedEvent event) {
    event
        .getEnvironment()
        .getPropertySources()
        .addFirst(
            new MapPropertySource(
                SOURCE_NAME,
                Map.of(
                    "spring.config.location", LOCATION,
                    "spring.config.additional-location", "",
                    "spring.config.import", "",
                    "spring.web.resources.add-mappings", "false")));
  }
}
