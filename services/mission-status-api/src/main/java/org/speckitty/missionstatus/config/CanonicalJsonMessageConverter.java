package org.speckitty.missionstatus.config;

import org.springframework.core.ResolvableType;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.JacksonJsonHttpMessageConverter;
import tools.jackson.core.JsonGenerator;
import tools.jackson.databind.json.JsonMapper;

/**
 * Writes the documents of the HTTP adapter (the contract models and the Problem) as the canonical form: the configured mapper's compact
 * output followed by exactly one newline, like the committed goldens. Other JSON bodies (the Problem bodies and the stream events, which are not documents) keep the default converter.
 */
final class CanonicalJsonMessageConverter extends JacksonJsonHttpMessageConverter {

  private static final String ADAPTER_PACKAGE = "org.speckitty.missionstatus.adapter.in.http.";

  CanonicalJsonMessageConverter(JsonMapper mapper) {
    super(mapper);
  }

  @Override
  public boolean canWrite(Class<?> clazz, MediaType mediaType) {
    return clazz.getName().startsWith(ADAPTER_PACKAGE) && super.canWrite(clazz, mediaType);
  }

  @Override
  public boolean canWrite(ResolvableType type, Class<?> clazz, MediaType mediaType) {
    return clazz.getName().startsWith(ADAPTER_PACKAGE) && super.canWrite(type, clazz, mediaType);
  }

  @Override
  protected void writeSuffix(JsonGenerator generator, Object object) {
    generator.writeRaw("\n");
  }
}
