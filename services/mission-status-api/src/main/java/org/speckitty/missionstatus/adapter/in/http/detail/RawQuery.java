package org.speckitty.missionstatus.adapter.in.http.detail;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;

/**
 * Reads the {@code path} values of an artifact request from the raw query string, because a framework parameter would join a repeated
 * parameter and replace invalid UTF-8 with U+FFFD. Every value of {@code path} is kept in order, percent-decoded once and strictly as
 * UTF-8; a {@code +} is a literal plus sign. A value that does not decode (an invalid or truncated UTF-8 sequence, an encoded surrogate, a
 * broken percent sequence) makes the whole input {@link ArtifactPathInput.Undecodable}. A plain helper: no Spring type in its signature.
 */
public final class RawQuery {

  private static final String PATH = "path";

  private RawQuery() {}

  /** The {@code path} values of {@code rawQuery} (null or empty: none). */
  public static ArtifactPathInput path(String rawQuery) {
    List<String> values = new ArrayList<>();
    if (rawQuery != null && !rawQuery.isEmpty()) {
      for (String pair : rawQuery.split("&", -1)) {
        int equals = pair.indexOf('=');
        String rawName = equals < 0 ? pair : pair.substring(0, equals);
        String name = decode(rawName);
        if (!PATH.equals(name)) {
          continue;
        }
        String value = decode(equals < 0 ? "" : pair.substring(equals + 1));
        if (value == null) {
          return new ArtifactPathInput.Undecodable();
        }
        values.add(value);
      }
    }
    return new ArtifactPathInput.Values(values);
  }

  /** The value of an ASCII hex digit ({@code 0-9A-Fa-f}); -1 for anything else, Unicode digits included. */
  private static int asciiHex(char c) {
    if (c >= '0' && c <= '9') {
      return c - '0';
    }
    if (c >= 'A' && c <= 'F') {
      return c - 'A' + 10;
    }
    if (c >= 'a' && c <= 'f') {
      return c - 'a' + 10;
    }
    return -1;
  }

  /** Decoded once, strictly; null when it does not decode. */
  private static String decode(String raw) {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream(raw.length());
    for (int i = 0; i < raw.length(); i++) {
      char c = raw.charAt(i);
      if (c == '%') {
        int high = i + 1 < raw.length() ? asciiHex(raw.charAt(i + 1)) : -1;
        int low = i + 2 < raw.length() ? asciiHex(raw.charAt(i + 2)) : -1;
        if (high < 0 || low < 0) {
          return null;
        }
        bytes.write(high * 16 + low);
        i += 2;
      } else {
        int codePoint = raw.codePointAt(i);
        if (Character.isSurrogate(c) && !Character.isSupplementaryCodePoint(codePoint)) {
          return null;
        }
        bytes.writeBytes(new String(Character.toChars(codePoint)).getBytes(StandardCharsets.UTF_8));
        i += Character.charCount(codePoint) - 1;
      }
    }
    try {
      return StandardCharsets.UTF_8
          .newDecoder()
          .onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT)
          .decode(ByteBuffer.wrap(bytes.toByteArray()))
          .toString();
    } catch (CharacterCodingException invalid) {
      return null;
    }
  }
}
