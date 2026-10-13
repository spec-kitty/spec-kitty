package org.speckitty.missionstatus.application.query.port.out.exceptions;

import java.util.Objects;

/**
 * A fault of the source, as a typed exception: never an {@code IOException}, never a path or an operating-system message. The kind is
 * the whole content.
 */
public final class SourceFault extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** What went wrong. */
  public enum Kind {
    /** The Mission directory is gone. */
    VANISHED,
    /** A symbolic link or a path outside the project root was refused. */
    PATH_REFUSED,
    /** {@code meta.json} is present but cannot be used. */
    META_UNPARSEABLE,
    /** A directory cannot be listed or stat-ed. */
    DIR_UNREADABLE,
    /** The ledger cannot be read. */
    LEDGER_UNREADABLE
  }

  private final Kind kind;

  public SourceFault(Kind kind) {
    super(Objects.requireNonNull(kind, "kind").name());
    this.kind = kind;
  }

  public Kind kind() {
    return kind;
  }
}
