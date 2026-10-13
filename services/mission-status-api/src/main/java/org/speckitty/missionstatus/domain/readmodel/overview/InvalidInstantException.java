package org.speckitty.missionstatus.domain.readmodel.overview;

/** A timestamp that is not an ISO 8601 instant; the oracle's {@code parse_iso} raises on the same input. */
public final class InvalidInstantException extends IllegalArgumentException {

  private static final long serialVersionUID = 1L;

  public InvalidInstantException() {
    super("not an ISO 8601 instant");
  }
}
