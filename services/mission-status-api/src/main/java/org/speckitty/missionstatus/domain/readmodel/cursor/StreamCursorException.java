package org.speckitty.missionstatus.domain.readmodel.cursor;

/** A stream cursor refused by the domain. {@code misaligned} and the 409 reasons are decided by the adapter against the file. */
public final class StreamCursorException extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** The parse reasons that exist in the domain. */
  public enum Reason {
    NEGATIVE,
    MALFORMED
  }

  private final Reason reason;

  public StreamCursorException(Reason reason) {
    super("stream cursor refused: " + reason);
    this.reason = reason;
  }

  public Reason reason() {
    return reason;
  }
}
