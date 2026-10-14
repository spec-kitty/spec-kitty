package org.speckitty.missionstatus.domain.readmodel.derive;

/**
 * The artifact-path rule, once (D-111): the index, the review-cycle references and the artifact routes all apply it. It restates the
 * contract's {@code ArtifactPath} schema and decides the same way on every string, plus two refusals the schema leaves to the string
 * level: a U+FFFD (the JDK's stand-in for bytes it could not decode) and an unpaired surrogate.
 *
 * <p>A path is relative to the Mission directory and written with forward slashes: 1 to 512 characters (code points), no empty segment
 * (so no leading or trailing slash), no segment that is {@code .} or {@code ..}, no backslash, no NUL, no line break (line feed,
 * carriage return, vertical tab, form feed, the three information separators, next line, line and paragraph separator), no drive
 * letter and colon at the start, no {@code ~/} at the start. Pure functions over strings; no file API.
 */
public final class ArtifactPaths {

  /** The longest path, in characters (code points). */
  public static final int MAX_LENGTH = 512;

  private static final char REPLACEMENT = '�';

  private ArtifactPaths() {}

  /** Whether {@code path} is an acceptable artifact path. A null is not. */
  public static boolean isValid(String path) {
    if (path == null || path.isEmpty() || path.codePointCount(0, path.length()) > MAX_LENGTH) {
      return false;
    }
    if (path.startsWith("~/") || startsWithDriveLetter(path)) {
      return false;
    }
    int segmentStart = 0;
    for (int i = 0; i <= path.length(); i++) {
      if (i == path.length() || path.charAt(i) == '/') {
        if (!validSegment(path, segmentStart, i)) {
          return false;
        }
        segmentStart = i + 1;
      }
    }
    return true;
  }

  /** Whether the string holds a U+FFFD, the mark of a name that was not valid UTF-8. */
  public static boolean hasReplacementCharacter(String text) {
    return text.indexOf(REPLACEMENT) >= 0;
  }

  private static boolean startsWithDriveLetter(String path) {
    if (path.length() < 2 || path.charAt(1) != ':') {
      return false;
    }
    char first = path.charAt(0);
    return (first >= 'A' && first <= 'Z') || (first >= 'a' && first <= 'z');
  }

  private static boolean validSegment(String path, int start, int end) {
    if (start == end) {
      return false;
    }
    int length = end - start;
    if ((length == 1 && path.charAt(start) == '.') || (length == 2 && path.charAt(start) == '.' && path.charAt(start + 1) == '.')) {
      return false;
    }
    for (int i = start; i < end; i++) {
      char c = path.charAt(i);
      if (forbidden(c)) {
        return false;
      }
      if (Character.isHighSurrogate(c)) {
        if (i + 1 >= end || !Character.isLowSurrogate(path.charAt(i + 1))) {
          return false;
        }
        i++;
      } else if (Character.isLowSurrogate(c)) {
        return false;
      }
    }
    return true;
  }

  private static boolean forbidden(char c) {
    return c == '\\'
        || c == '\0'
        || c == '\n'
        || c == '\r'
        || c == '\u000B'
        || c == '\u000C'
        || (c >= '\u001C' && c <= '\u001E')
        || c == '\u0085'
        || c == ' '
        || c == ' '
        || c == REPLACEMENT;
  }
}
