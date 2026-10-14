package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Loads only {@link DetailInfrastructureWiring} (never the application context) and asserts the two positive facts: one text source and
 * one admission gate. It says nothing about the inbound interfaces, so it stays green when later wiring adds their beans.
 */
class DetailInfrastructureWiringTest {

  @TempDir Path projectRoot;

  /** The collaborator the wiring takes, supplied here so the test needs no other configuration class. */
  @Configuration(proxyBeanMethods = false)
  static class Collaborators {
    @Bean
    MissionStatusProperties properties(@org.springframework.beans.factory.annotation.Value("${root}") String root) {
      return new MissionStatusProperties(root, new MissionStatusProperties.Stream(1024, java.time.Duration.ofSeconds(30), 128));
    }
  }

  private ApplicationContextRunner runner() {
    return new ApplicationContextRunner()
        .withUserConfiguration(Collaborators.class, DetailInfrastructureWiring.class)
        .withPropertyValues("root=" + projectRoot);
  }

  @Test
  void exactlyOneTextSourceAndExactlyOneAdmissionGate() {
    runner()
        .run(
            context -> {
              assertThat(context).hasNotFailed();
              assertThat(context.getBeansOfType(TextSource.class)).hasSize(1);
              assertThat(context.getBean(TextSource.class)).isInstanceOf(FilesystemTextSource.class);
              assertThat(context.getBeansOfType(AdmissionGate.class)).hasSize(1);
            });
  }

  @Test
  void theGateBeanIsASingletonSharedByEveryConsumer() {
    runner().run(context -> assertThat(context.getBean(AdmissionGate.class)).isSameAs(context.getBean(AdmissionGate.class)));
  }
}
