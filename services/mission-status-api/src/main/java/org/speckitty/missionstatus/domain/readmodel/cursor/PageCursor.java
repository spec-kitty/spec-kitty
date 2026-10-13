package org.speckitty.missionstatus.domain.readmodel.cursor;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Base64;

/**
 * The position after the last returned item of a listing: {@code v1.} plus the URL-safe base64, without padding, of the UTF-8
 * text {@code <createdAt>} LF {@code <missionId>} LF {@code <directory>}. The directory name is the tie-breaker of two Mission
 * directories that carry the same {@code mission_id}: without it the position after the first copy and the position after the second
 * would be the same text, and a page walk would never leave them. Stateless and deterministic; at most 512 characters. Whether the
 * position is in the current listing is decided by the pager, not here.
 */
public record PageCursor(String createdAt, String missionId, String directory) {

  private static final String PREFIX = "v1.";
  private static final int MAX_LENGTH = 512;

  public static String encode(String createdAt, String missionId, String directory) {
    byte[] body = (createdAt + "\n" + missionId + "\n" + directory).getBytes(StandardCharsets.UTF_8);
    return PREFIX + Base64.getUrlEncoder().withoutPadding().encodeToString(body);
  }

  public static PageCursor decode(String cursor) {
    if (cursor == null || cursor.isEmpty()) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.EMPTY);
    }
    if (!cursor.startsWith(PREFIX)) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.NOT_V1);
    }
    if (cursor.length() > MAX_LENGTH) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.TOO_LONG);
    }
    String text = utf8(base64(cursor.substring(PREFIX.length())));
    int first = text.indexOf('\n');
    int second = first < 0 ? -1 : text.indexOf('\n', first + 1);
    if (second < 0) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.NO_SEPARATOR);
    }
    return new PageCursor(text.substring(0, first), text.substring(first + 1, second), text.substring(second + 1));
  }

  /** Decode, then require the canonical form: one text has exactly one cursor. */
  private static byte[] base64(String body) {
    try {
      byte[] bytes = Base64.getUrlDecoder().decode(body);
      if (!Base64.getUrlEncoder().withoutPadding().encodeToString(bytes).equals(body)) {
        throw new InvalidPageCursor(InvalidPageCursor.Reason.NOT_BASE64);
      }
      return bytes;
    } catch (IllegalArgumentException notBase64) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.NOT_BASE64);
    }
  }

  /** Strict UTF-8: a decode that substitutes anything does not round-trip to the same bytes. */
  private static String utf8(byte[] bytes) {
    String text = new String(bytes, StandardCharsets.UTF_8);
    if (!Arrays.equals(text.getBytes(StandardCharsets.UTF_8), bytes)) {
      throw new InvalidPageCursor(InvalidPageCursor.Reason.NOT_UTF8);
    }
    return text;
  }
}
