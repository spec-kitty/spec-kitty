package org.speckitty.missionstatus.config;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.time.Clock;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ScheduledExecutorService;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemMissionEventSource;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The composition root: the ONE place that constructs the filesystem event source, the leak-class value and the Mission status service.
 * {@code leak-patterns.json} (committed, generated from the Python source of truth) is read from the classpath and every pattern in it
 * is compiled through {@link LeakClasses#compile}, never with {@code Pattern.compile} directly.
 */
@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(MissionStatusProperties.class)
class ServiceWiring {

  static final String LEAK_PATTERNS = "leak-patterns.json";

  @Bean
  MissionEventSource missionEventSource(MissionStatusProperties properties) {
    return FilesystemMissionEventSource.forRoot(properties.projectRoot());
  }

  @Bean
  LeakClasses leakClasses() {
    return loadLeakClasses();
  }

  @Bean
  Clock clock() {
    return Clock.systemUTC();
  }

  /** The read path (lookup, head derivation and the one projection cache), built once and shared by every service of the query side. */
  @Bean
  MissionReadModel missionReadModel(MissionEventSource source, Consumer<Diagnostic> diagnosticsLine, LeakClasses leaks) {
    return new MissionReadModel(source, diagnosticsLine, leaks);
  }

  @Bean
  MissionStatusQuery missionStatusQuery(
      MissionEventSource source,
      Clock clock,
      Consumer<Diagnostic> diagnosticsLine,
      ScheduledExecutorService feedExecutor,
      LeakClasses leaks,
      MissionReadModel readModel,
      MissionStatusProperties properties) {
    StreamSettings settings = new StreamSettings(
            Duration.ofMillis(500), Duration.ofSeconds(1), properties.stream().queueCapacity(), properties.stream().maxConnections());
    return new MissionStatusQueryService(source, clock, diagnosticsLine, feedExecutor, settings, leaks, readModel);
  }

  static LeakClasses loadLeakClasses() {
    JsonNode document;
    try (InputStream in = ServiceWiring.class.getClassLoader().getResourceAsStream(LEAK_PATTERNS)) {
      if (in == null) {
        throw new IllegalStateException(LEAK_PATTERNS + " is not on the classpath");
      }
      document = JsonMapper.builder().build().readTree(in.readAllBytes());
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
    List<Pattern> strict = new ArrayList<>();
    List<Pattern> human = new ArrayList<>();
    List<Pattern> secrets = new ArrayList<>();
    Pattern email = null;
    Pattern emailAnchored = null;
    for (JsonNode entry : document.get("patterns")) {
      Pattern compiled = LeakClasses.compile(entry.get("pattern").asString());
      switch (entry.get("kind").asString()) {
        case "host_path" -> (entry.get("fieldClass").asString().equals("strict") ? strict : human).add(compiled);
        case "email" -> {
          if (entry.get("id").asString().equals("email-anchored")) {
            emailAnchored = compiled;
          } else {
            email = compiled;
          }
        }
        case "secret" -> secrets.add(compiled);
        default -> throw new IllegalStateException("unknown pattern kind " + entry.get("kind").asString());
      }
    }
    return new LeakClasses(strict, human, email, emailAnchored, secrets);
  }
}
