package org.speckitty.missionstatus.config;

import org.speckitty.missionstatus.adapter.out.filesystem.JsonLanesDecoder;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The single owner of the two decoder beans of FR-006: the Work Package frontmatter decoder and the {@code lanes.json} decoder. Nothing
 * else declares either. They are built at start-up with no consumer until the route services of mission #957 inject them (the index
 * and the lanes reader), so a missing native reflection hint would show here first.
 */
@Configuration(proxyBeanMethods = false)
class DecoderWiring {

  @Bean
  FrontmatterDecoder frontmatterDecoder() {
    return new YamlFrontmatterDecoder();
  }

  @Bean
  LanesDecoder lanesDecoder() {
    return new JsonLanesDecoder();
  }
}
