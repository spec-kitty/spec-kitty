package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * A relative path as a list of segments. A segment is never empty, never {@code .} or {@code ..}, and holds no backslash, no NUL and no
 * separator, so a value of this type cannot leave the base it is resolved against. {@link #ROOT} (no segments) names the base itself.
 */
public record RelativePath(List<String> segments) {

  /** The base itself: the Mission's primary directory or the project root. */
  public static final RelativePath ROOT = new RelativePath(List.of());

  public RelativePath {
    segments = List.copyOf(segments);
    for (String segment : segments) {
      if (!safe(segment)) {
        throw new IllegalArgumentException("not a path segment");
      }
    }
  }

  private static boolean safe(String segment) {
    return segment != null
        && !segment.isEmpty()
        && !segment.equals(".")
        && !segment.equals("..")
        && segment.indexOf('/') < 0
        && segment.indexOf('\\') < 0
        && segment.indexOf('\0') < 0;
  }

  /**
   * Parses {@code a/b}. An empty segment (including a leading or a trailing slash and the empty string), {@code .}, {@code ..}, a
   * backslash and a NUL are refused with an {@link IllegalArgumentException}; the base itself is {@link #ROOT}, never {@code of("")}.
   */
  public static RelativePath of(String path) {
    return new RelativePath(List.of(path.split("/", -1)));
  }

  /** This path with one more segment. */
  public RelativePath child(String name) {
    List<String> next = new ArrayList<>(segments);
    next.add(name);
    return new RelativePath(next);
  }

  /** This path without its last segment; the parent of a one-segment path is {@link #ROOT}. */
  public RelativePath parent() {
    if (segments.isEmpty()) {
      throw new IllegalStateException("the root has no parent");
    }
    return new RelativePath(segments.subList(0, segments.size() - 1));
  }

  /** The last segment. */
  public String last() {
    if (segments.isEmpty()) {
      throw new IllegalStateException("the root has no last segment");
    }
    return segments.get(segments.size() - 1);
  }

  public boolean isRoot() {
    return segments.isEmpty();
  }

  @Override
  public String toString() {
    return String.join("/", segments);
  }
}
