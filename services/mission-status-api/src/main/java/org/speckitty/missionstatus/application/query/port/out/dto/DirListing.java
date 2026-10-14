package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.List;
import java.util.Objects;

/** The result of listing a directory. */
public sealed interface DirListing {

  /**
   * The names, at most the caller's limit, in the order the file system gave them. {@code limitReached} is true when more entries
   * existed; {@code trustworthy} is false on a host whose file-name decoding cannot be relied on (a non-UTF-8 name encoding).
   */
  record Names(List<String> names, boolean limitReached, boolean trustworthy) implements DirListing {
    public Names {
      names = List.copyOf(Objects.requireNonNull(names, "names"));
    }
  }

  /** Nothing is at the path. */
  record Absent() implements DirListing {}

  /** Something is there, and it is not a directory. */
  record NotADirectory() implements DirListing {}
}
