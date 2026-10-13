package org.speckitty.missionstatus.adapter.out.filesystem;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.Set;
import tools.jackson.core.JacksonException;
import tools.jackson.core.JsonParser;
import tools.jackson.core.JsonToken;
import tools.jackson.core.json.JsonReadFeature;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The JSON reading the resolver needs for {@code meta.json} and {@code lanes.json}: the way the oracle decodes them
 * ({@code decode_meta}: strict UTF-8, {@code json.loads}, a top level that is an object, anything else malformed), and Python's
 * truthiness for the values it tests with {@code or}. Package-private; the ledger has its own codec.
 */
final class ReadDirResolverJson {

  private static final JsonMapper MAPPER =
      JsonMapper.builder()
          .enable(JsonReadFeature.ALLOW_NON_NUMERIC_NUMBERS)
          .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
          .build();

  private static final Set<String> NON_NUMERIC_SPELLINGS = Set.of("NaN", "Infinity", "-Infinity");

  private ReadDirResolverJson() {}

  /** The document as an object, or empty when it is not UTF-8, not JSON, or not an object (all "malformed" to the oracle). */
  static Optional<JsonNode> object(byte[] bytes) {
    String text;
    try {
      text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
    } catch (CharacterCodingException notUtf8) {
      return Optional.empty();
    }
    try {
      if (!spellingsAreJsonLoads(text)) {
        return Optional.empty();
      }
      JsonNode node = MAPPER.readTree(text);
      return node != null && node.isObject() ? Optional.of(node) : Optional.empty();
    } catch (JacksonException malformed) {
      return Optional.empty();
    }
  }

  /**
   * Jackson's non-numeric-number feature, needed for {@code NaN}, {@code Infinity} and {@code -Infinity} (which {@code json.loads}
   * reads), also admits {@code +Infinity}, {@code INF}, {@code +INF} and {@code -INF}, which it refuses. Those are refused here, by
   * the token text.
   */
  private static boolean spellingsAreJsonLoads(String text) {
    try (JsonParser parser = MAPPER.createParser(text)) {
      for (JsonToken token = parser.nextToken(); token != null; token = parser.nextToken()) {
        if (token == JsonToken.VALUE_NUMBER_FLOAT) {
          String number = parser.getString();
          boolean signed = number.startsWith("+") || number.startsWith("-");
          boolean word = !number.isEmpty() && Character.isLetter(number.charAt(signed && number.length() > 1 ? 1 : 0));
          if (word && !NON_NUMERIC_SPELLINGS.contains(number)) {
            return false;
          }
        }
      }
      return true;
    } catch (JacksonException malformed) {
      return false;
    }
  }

  /** Python's {@code bool(value)} of a JSON value: false for null, false, 0, "", [] and {}. */
  static boolean truthy(JsonNode value) {
    if (value == null || value.isNull() || value.isMissingNode()) {
      return false;
    }
    if (value.isBoolean()) {
      return value.booleanValue();
    }
    if (value.isNumber()) {
      // NaN is truthy in Python (it is not equal to zero)
      return value.isIntegralNumber() ? value.bigIntegerValue().signum() != 0 : value.doubleValue() != 0.0;
    }
    if (value.isString()) {
      return !value.stringValue().isEmpty();
    }
    return !value.isEmpty();
  }
}
