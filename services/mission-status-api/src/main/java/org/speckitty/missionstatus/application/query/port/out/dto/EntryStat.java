package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.Objects;

/** The result of a stat that never follows a link ({@code lstat}). */
public sealed interface EntryStat {

  /** What kind of entry it is. A link is {@code SYMLINK} and is never followed. */
  enum EntryKind {
    FILE,
    DIRECTORY,
    SYMLINK,
    OTHER
  }

  /** Nothing is at the path. */
  record Absent() implements EntryStat {}

  /** An entry, with its size in bytes and its modification time in epoch seconds. */
  record Present(EntryKind kind, long sizeBytes, long modifiedEpochSecond) implements EntryStat {
    public Present {
      Objects.requireNonNull(kind, "kind");
    }
  }
}
