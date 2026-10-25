package org.speckitty.missionstatus.architecture.fixture;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import tools.jackson.core.JsonParser;
import tools.jackson.core.json.JsonFactory;

/** Positive control: a decoder that uses only the allowed packages, the Jackson streaming parser included. */
public final class ConformingDecoder {

  private ConformingDecoder() {}

  public static boolean startsAnObject(byte[] bytes) {
    String text = StandardCharsets.UTF_8.decode(ByteBuffer.wrap(bytes)).toString();
    try (JsonParser parser = new JsonFactory().createParser(text)) {
      return parser.nextToken() != null;
    }
  }
}
