package org.speckitty.missionstatus.domain.readmodel.cursor;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * A resumable position in one Mission's physical event log: the byte offset just after the last consumed line and the SHA-256 hex
 * of that single line (its line ending included). Offset 0 carries the digest of the empty input. Text form {@code offset:invariant}.
 */
public record StreamCursor(long offset, String invariant) {

  private static final Pattern TEXT = Pattern.compile("^(0|[1-9][0-9]*):([0-9a-f]{64})$");
  private static final Pattern NEGATIVE_TEXT = Pattern.compile("^-[0-9]+:[0-9a-f]{64}$");
  private static final Pattern INVARIANT = Pattern.compile("^[0-9a-f]{64}$");
  private static final String EMPTY_DIGEST = digestOf(new byte[0]);

  public StreamCursor {
    if (offset < 0) {
      throw new StreamCursorException(StreamCursorException.Reason.NEGATIVE);
    }
    Objects.requireNonNull(invariant, "invariant");
    if (!INVARIANT.matcher(invariant).matches()) {
      throw new StreamCursorException(StreamCursorException.Reason.MALFORMED);
    }
  }

  /** Nothing consumed yet. */
  public static StreamCursor start() {
    return new StreamCursor(0, EMPTY_DIGEST);
  }

  public static StreamCursor parse(String text) {
    if (text != null && NEGATIVE_TEXT.matcher(text).matches()) {
      throw new StreamCursorException(StreamCursorException.Reason.NEGATIVE);
    }
    Matcher matcher = text == null ? null : TEXT.matcher(text);
    if (matcher == null || !matcher.matches()) {
      throw new StreamCursorException(StreamCursorException.Reason.MALFORMED);
    }
    try {
      return new StreamCursor(Long.parseLong(matcher.group(1)), matcher.group(2));
    } catch (NumberFormatException overflow) {
      throw new StreamCursorException(StreamCursorException.Reason.MALFORMED);
    }
  }

  public String toText() {
    return offset + ":" + invariant;
  }

  /** The invariant of a consumed line: the SHA-256 hex of its raw bytes, line ending included. */
  public static String digestOf(byte[] rawLine) {
    try {
      return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(rawLine));
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException("SHA-256 is part of every Java platform", impossible);
    }
  }
}
