package org.speckitty.missionstatus.application.query.port.out.exceptions;

import java.util.Objects;

/**
 * A fault of the text-read port, thrown and never returned: unchecked, with no message, no cause and no path, so nothing of the file
 * system can reach a response. It is its own type, not a constant of {@code SourceFault.Kind}, so no exhaustive switch over that enum
 * changes (D-91).
 */
public final class TextFault extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** What went wrong. */
  public enum Kind {
    /** A symbolic link in any component, or a path that leaves the root. */
    PATH_REFUSED,
    /** The Mission directory (or the file) disappeared between the lookup and the read. */
    VANISHED,
    /** A listing or a stat failed. */
    DIR_UNREADABLE,
    /** A read failed. */
    FILE_UNREADABLE
  }

  private final Kind kind;

  public TextFault(Kind kind) {
    super(null, null, false, false);
    this.kind = Objects.requireNonNull(kind, "kind");
  }

  public Kind kind() {
    return kind;
  }
}
