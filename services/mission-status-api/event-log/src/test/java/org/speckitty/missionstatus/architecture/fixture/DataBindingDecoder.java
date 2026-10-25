package org.speckitty.missionstatus.architecture.fixture;

import java.util.Map;
import tools.jackson.databind.json.JsonMapper;

/** Planted violation: a decoder that uses Jackson data binding (reflection-based) instead of the streaming parser. */
public final class DataBindingDecoder {

  private DataBindingDecoder() {}

  @SuppressWarnings("unchecked")
  public static Map<String, Object> decode(String line) {
    return JsonMapper.builder().build().readValue(line, Map.class);
  }
}
