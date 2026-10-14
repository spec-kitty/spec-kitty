package org.speckitty.missionstatus.application.query.index;

import java.util.Objects;

/**
 * The index could not be built, and serving a partial one would hide a Work Package (FR-006, rows M10 and W3). A route answers 500
 * {@code source_unreadable}. Unchecked, with no message, no cause and no path, so nothing of the file system can reach a response. A fault
 * of the text-read port itself (a link in a path, a vanished directory) propagates as the port's own {@code TextFault}.
 */
public final class WorkPackageIndexFault extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** Why the index was refused. */
  public enum Kind {
    /** {@code tasks/} exists and is not a directory (a regular file). */
    TASKS_NOT_A_DIRECTORY,
    /** {@code tasks/} holds more entries than the listing window. */
    LISTING_TOO_LARGE,
    /** The host cannot decode file names faithfully and a candidate name is not ASCII (D-73). */
    NAMES_UNTRUSTWORTHY,
    /** A candidate file could not be read: it vanished after it was listed. */
    FILE_UNREADABLE,
    /** A candidate file is larger than 1 MiB. */
    FILE_TOO_LARGE
  }

  private final Kind kind;

  public WorkPackageIndexFault(Kind kind) {
    super(null, null, false, false);
    this.kind = Objects.requireNonNull(kind, "kind");
  }

  public Kind kind() {
    return kind;
  }
}
