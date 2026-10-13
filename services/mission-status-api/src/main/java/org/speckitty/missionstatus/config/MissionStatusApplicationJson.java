package org.speckitty.missionstatus.config;

import java.math.BigDecimal;
import org.speckitty.missionstatus.domain.readmodel.overview.Progress;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.MapperFeature;
import tools.jackson.databind.SerializationFeature;
import tools.jackson.databind.cfg.DateTimeFeature;
import tools.jackson.core.JsonGenerator;
import tools.jackson.databind.SerializationContext;
import tools.jackson.databind.ValueSerializer;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.module.SimpleModule;

/**
 * The production Jackson 3 mapper, configured explicitly instead of left at the Boot defaults (research.md spike record, T005
 * criteria 3 and 4). With the Boot plugin compiling {@code -parameters}, Jackson 3 detects the generated all-required-arguments
 * constructor as a creator and sorts its parameters first; the canonical order is alphabetical, so creator-first sorting is off.
 * Null members are written (Jackson 3 default), non-ASCII text is written as UTF-8. A {@link BigDecimal} (only the two percentages of
 * {@code progress} are one) is written by the ONE pinned function {@link Progress#render}, which is what Python's {@code json.dumps}
 * writes for {@code round(x, 4)}.
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
        .addModule(new SimpleModule("mission-status-numbers").addSerializer(BigDecimal.class, new PinnedPercentage()))
        .build();
  }

  @Bean
  JsonMapper missionStatusJsonMapper() {
    return mapper();
  }

  /** The one pinned rendering of a percentage (research.md spike record, T005 criterion 4; DD-72). */
  static final class PinnedPercentage extends ValueSerializer<BigDecimal> {
    @Override
    public void serialize(BigDecimal value, JsonGenerator generator, SerializationContext context) {
      generator.writeNumber(Progress.render(value.doubleValue()));
    }
  }
}
