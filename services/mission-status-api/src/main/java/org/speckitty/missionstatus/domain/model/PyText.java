package org.speckitty.missionstatus.domain.model;

/** The few Python {@code str} behaviours the oracle relies on, kept in one place. */
public final class PyText {

  private PyText() {}

  private static boolean isPyWhitespace(int c) {
    return Character.isWhitespace(c) || Character.isSpaceChar(c) || c == 0x85;
  }

  /** {@code not (value or "").strip()}. */
  public static boolean isBlank(String value) {
    return value == null || value.codePoints().allMatch(PyText::isPyWhitespace);
  }

  /** {@code value.strip()} for a non-null value. */
  public static String strip(String value) {
    int start = 0;
    int end = value.length();
    while (start < end && isPyWhitespace(value.charAt(start))) {
      start++;
    }
    while (end > start && isPyWhitespace(value.charAt(end - 1))) {
      end--;
    }
    return value.substring(start, end);
  }

  /** The oracle's {@code _optional_text}: an empty string is absent. */
  public static String nullIfEmpty(String value) {
    return value == null || value.isEmpty() ? null : value;
  }
}
