package org.speckitty.missionstatus.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.MapperFeature;
import tools.jackson.databind.SerializationFeature;
import tools.jackson.databind.cfg.DateTimeFeature;
import tools.jackson.databind.json.JsonMapper;

/**
 * The production Jackson 3 mapper, configured explicitly instead of left at the Boot defaults (research.md spike record, T005
 * criteria 3 and 4). With the Boot plugin compiling {@code -parameters}, Jackson 3 detects the generated all-required-arguments
 * constructor as a creator and sorts its parameters first; the canonical order is alphabetical, so creator-first sorting is off.
 * Null members are written (Jackson 3 default), non-ASCII text is written as UTF-8. The pinned BigDecimal function for
 * {@code progress} is added with the controllers that need it.
 */
@Configuration(proxyBeanMethods = false)
public class MissionStatusApplicationJson {

  /** The canonical-order mapper. */
  public static JsonMapper mapper() {
    return JsonMapper.builder()
        .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
        .disable(MapperFeature.SORT_CREATOR_PROPERTIES_FIRST)
        .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
        .disable(DateTimeFeature.WRITE_DATES_AS_TIMESTAMPS)
        .build();
  }

  @Bean
  JsonMapper missionStatusJsonMapper() {
    return mapper();
  }
}
