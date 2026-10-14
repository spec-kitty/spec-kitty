package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * A context of three wiring classes only (never the full application): {@link MissionDetailWiring}, {@code DecoderWiring} and
 * {@code DetailInfrastructureWiring}. It holds exactly one {@link WorkPackageIndex} (the one bean of the whole mission, which the other
 * Work Package routes inject and never declare again) and exactly one {@link MissionDetailQuery}. The collaborators the partial context
 * cannot resolve are test-local stubs; {@code ServiceWiring} is not imported and not edited.
 */
class MissionDetailWiringTest {

  @TempDir Path root;

  /** The collaborators of ServiceWiring and LoggingDiagnostics, as stubs. */
  @Configuration(proxyBeanMethods = false)
  static class Collaborators {
    final List<Diagnostic> written = new ArrayList<>();

    @Bean
    MissionStatusProperties properties(@org.springframework.beans.factory.annotation.Value("${root}") String root) {
      return new MissionStatusProperties(root, new MissionStatusProperties.Stream(1024, java.time.Duration.ofSeconds(30), 128));
    }

    @Bean
    Consumer<Diagnostic> diagnosticsLine() {
      return written::add;
    }

    @Bean
    LeakClasses leaks() {
      return LeakPatternsFile.load();
    }

    @Bean
    MissionEventSource source(MissionStatusProperties properties) {
      return org.speckitty.missionstatus.adapter.out.filesystem.FilesystemMissionEventSource.forRoot(properties.projectRoot());
    }

    @Bean
    MissionReadModel model(MissionEventSource source, Consumer<Diagnostic> diagnosticsLine, LeakClasses leaks) {
      return new MissionReadModel(source, diagnosticsLine, leaks);
    }
  }

  @Test
  void exactlyOneWorkPackageIndexAndExactlyOneMissionDetailQueryAreDeclared() {
    new ApplicationContextRunner()
        .withPropertyValues("root=" + root)
        .withUserConfiguration(MissionDetailWiring.class, DecoderWiring.class, DetailInfrastructureWiring.class, Collaborators.class)
        .run(
            context -> {
              assertThat(context).hasNotFailed();
              assertThat(context.getBeansOfType(WorkPackageIndex.class)).hasSize(1);
              assertThat(context.getBeansOfType(MissionDetailQuery.class)).hasSize(1);
            });
  }

  @Test
  void theWiringDeclaresNothingElseOfItsOwn() {
    long beans = java.util.Arrays.stream(MissionDetailWiring.class.getDeclaredMethods()).filter(method -> method.isAnnotationPresent(Bean.class)).count();

    assertThat(beans).isEqualTo(2);
  }
}
