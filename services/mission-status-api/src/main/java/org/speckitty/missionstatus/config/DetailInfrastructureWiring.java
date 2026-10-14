package org.speckitty.missionstatus.config;

import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The infrastructure the detail operations share, constructed once: the one {@link TextSource} over the project root with the production
 * allow-list, and the one {@link AdmissionGate}. Both are plan section 7.1 seams that #5533's own wiring injects. No inbound interface has a
 * bean here; each later wiring class adds its own.
 */
@Configuration(proxyBeanMethods = false)
class DetailInfrastructureWiring {

  @Bean
  TextSource textSource(MissionStatusProperties properties) {
    return FilesystemTextSource.forRoot(properties.projectRoot());
  }

  @Bean
  AdmissionGate admissionGate() {
    return new AdmissionGate();
  }
}
