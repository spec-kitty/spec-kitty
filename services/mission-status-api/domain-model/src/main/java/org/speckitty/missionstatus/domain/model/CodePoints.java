package org.speckitty.missionstatus.domain.model;

/** Text comparison by Unicode code point, the way a Python {@code str} compares (not UTF-16 units, not parsed instants). */
public final class CodePoints {

  private CodePoints() {}

  public static int compare(String left, String right) {
    int i = 0;
    int j = 0;
    while (i < left.length() && j < right.length()) {
      int a = left.codePointAt(i);
      int b = right.codePointAt(j);
      if (a != b) {
        return Integer.compare(a, b);
      }
      i += Character.charCount(a);
      j += Character.charCount(b);
    }
    return Integer.compare(left.length() - i, right.length() - j);
  }
}
