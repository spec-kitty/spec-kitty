package org.speckitty.missionstatus.config;

import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.WorkPackageQueryService;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The wiring of the Work Package route. The Work Package index and the admission gate are the two beans every detail route shares
 * ({@code MissionDetailWiring} and {@code DetailInfrastructureWiring}); this class declares neither.
 */
@Configuration(proxyBeanMethods = false)
class WorkPackageWiring {

  @Bean
  WorkPackageQuery workPackageQuery(MissionReadModel model, WorkPackageIndex index, Consumer<Diagnostic> diagnosticsLine, LeakClasses leaks, AdmissionGate gate) {
    return new WorkPackageQueryService(model, index, diagnosticsLine, leaks, gate);
  }
}
