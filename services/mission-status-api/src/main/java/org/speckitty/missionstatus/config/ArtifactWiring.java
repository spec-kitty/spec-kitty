package org.speckitty.missionstatus.config;

import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.ArtifactQueryService;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** The inbound port of the artifact routes, built from the existing beans. */
@Configuration(proxyBeanMethods = false)
class ArtifactWiring {

  @Bean
  ArtifactQuery artifactQuery(MissionReadModel model, TextSource source, AdmissionGate gate, Consumer<Diagnostic> diagnosticsLine, LeakClasses leaks) {
    return new ArtifactQueryService(model, source, gate, diagnosticsLine, new TextScreen(leaks));
  }
}
