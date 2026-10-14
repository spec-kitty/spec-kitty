package org.speckitty.missionstatus.config;

import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.WorkPackageDetailQueryService;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The inbound port of the Work Package detail route, built from beans that already exist: the read model, the one Work Package index
 * ({@code MissionDetailWiring}), the one text source and the one admission gate ({@code DetailInfrastructureWiring}), and the two decoders
 * ({@code DecoderWiring}). It declares none of them.
 */
@Configuration(proxyBeanMethods = false)
class WorkPackageDetailWiring {

  @Bean
  WorkPackageDetailQuery workPackageDetailQuery(
      MissionReadModel model,
      WorkPackageIndex index,
      TextSource textSource,
      FrontmatterDecoder frontmatterDecoder,
      LanesDecoder lanesDecoder,
      AdmissionGate gate,
      Consumer<Diagnostic> diagnosticsLine,
      LeakClasses leaks) {
    return new WorkPackageDetailQueryService(model, index, textSource, frontmatterDecoder, lanesDecoder, gate, diagnosticsLine, leaks);
  }
}
