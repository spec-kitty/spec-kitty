package org.speckitty.missionstatus.domain.readmodel.cursor;

/** A forged, malformed or no-longer-valid page cursor; the adapter answers it with 400 {@code invalid_page_cursor}. */
public final class InvalidPageCursor extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** Why the cursor was refused; for tests and diagnostics, never served. */
  public enum Reason {
    EMPTY,
    NOT_V1,
    TOO_LONG,
    NOT_BASE64,
    NOT_UTF8,
    NO_SEPARATOR,
    UNLISTED,
    CREATED_AT_MISMATCH
  }

  private final Reason reason;

  public InvalidPageCursor(Reason reason) {
    super("invalid page cursor: " + reason);
    this.reason = reason;
  }

  public Reason reason() {
    return reason;
  }
}
