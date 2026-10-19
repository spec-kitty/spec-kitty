package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Optional;

/**
 * The artifact-path rule of the contract ({@code ArtifactPath}): the Java form of {@code malformed_artifact_path} in
 * {@code contracts/tools/leak_scan.py}, plus the reference reader's refusal of a path that has no UTF-8 form. The reasons are checked
 * in the reference's order and named as it names them. Lengths are counted in code points, as Python's {@code len} and JSON Schema's
 * {@code maxLength} count, never in UTF-16 units.
 */
public final class ArtifactPathRule {

  /** The {@code maxLength} of {@code ArtifactPath}, in code points. */
  public static final int MAX_LENGTH = 512;

  private ArtifactPathRule() {}

  /** The reason {@code path} is not an artifact path, or empty when it is one. */
  public static Optional<String> malformed(String path) {
    return Optional.ofNullable(reason(path));
  }

  /** Whether {@code path} is an artifact path. */
  public static boolean isValid(String path) {
    return reason(path) == null;
  }

  /** The length of {@code text} in code points. */
  public static int length(String text) {
    return text.codePointCount(0, text.length());
  }

  private static String reason(String path) {
    if (path.isEmpty()) {
      return "empty";
    }
    if (length(path) > MAX_LENGTH) {
      return "too_long";
    }
    String shape = shapeReason(path);
    if (shape != null) {
      return shape;
    }
    return hasLoneSurrogate(path) ? "not_utf8" : null;
  }

  /** The reasons that look at the characters of the path, in the order of {@code malformed_artifact_path}. */
  private static String shapeReason(String path) {
    if (path.startsWith("/")) {
      return "absolute";
    }
    if (path.startsWith("~/")) {
      return "tilde";
    }
    if (isDriveLetter(path)) {
      return "drive_letter";
    }
    if (path.indexOf('\\') >= 0) {
      return "backslash";
    }
    if (path.indexOf('\0') >= 0) {
      return "nul";
    }
    if (path.codePoints().anyMatch(ArtifactPathRule::isLineBreak)) {
      return "line_break";
    }
    if (path.endsWith("/")) {
      return "trailing_slash";
    }
    return segmentReason(path.split("/", -1));
  }

  private static String segmentReason(String[] segments) {
    boolean dot = false;
    boolean dotDot = false;
    for (String segment : segments) {
      if (segment.isEmpty()) {
        return "empty_segment";
      }
      dot |= segment.equals(".");
      dotDot |= segment.equals("..");
    }
    if (dot) {
      return "dot_segment";
    }
    return dotDot ? "dotdot_segment" : null;
  }

  /** {@code len(path) >= 2 and path[1] == ":" and path[0].isascii() and path[0].isalpha()}, by code point. */
  private static boolean isDriveLetter(String path) {
    int first = path.codePointAt(0);
    int next = Character.charCount(first);
    if (next >= path.length() || path.codePointAt(next) != ':') {
      return false;
    }
    return (first >= 'A' && first <= 'Z') || (first >= 'a' && first <= 'z');
  }

  /** The line boundaries of Python's {@code str.splitlines}: LF, VT, FF, CR, FS, GS, RS, NEL, LS and PS. */
  static boolean isLineBreak(int codePoint) {
    return (codePoint >= 0x0a && codePoint <= 0x0d) || (codePoint >= 0x1c && codePoint <= 0x1e) || codePoint == 0x85 || codePoint == 0x2028 || codePoint == 0x2029;
  }

  private static boolean hasLoneSurrogate(String path) {
    for (int i = 0; i < path.length(); i++) {
      char c = path.charAt(i);
      if (Character.isHighSurrogate(c) && i + 1 < path.length() && Character.isLowSurrogate(path.charAt(i + 1))) {
        i++;
      } else if (Character.isSurrogate(c)) {
        return true;
      }
    }
    return false;
  }
}
