package org.speckitty.missionstatus.config;

import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.MissionDetailQueryService;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** The wiring of the Mission detail route: the work-package index, its collaborators and the detail query service. */
@Configuration(proxyBeanMethods = false)
class MissionDetailWiring {

  @Bean
  WorkPackageIndex workPackageIndex(TextSource textSource, FrontmatterDecoder decoder) {
    return new WorkPackageIndex(textSource, decoder);
  }

  @Bean
  MissionDetailQuery missionDetailQuery(
      MissionReadModel model, WorkPackageIndex index, TextSource textSource, Consumer<Diagnostic> diagnosticsLine, LeakClasses leaks) {
    return new MissionDetailQueryService(model, index, textSource, diagnosticsLine, leaks);
  }
}
