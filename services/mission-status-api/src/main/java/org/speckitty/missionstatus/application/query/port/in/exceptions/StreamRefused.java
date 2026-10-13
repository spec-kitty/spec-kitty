package org.speckitty.missionstatus.application.query.port.in.exceptions;

import java.util.Objects;

/** A stream request refused before any subscription exists: a cursor that cannot be trusted, or an unknown Mission. */
public final class StreamRefused extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** The refusal kinds, with the HTTP status the contract fixes for each. */
  public enum Kind {
    NEGATIVE("negative", 400),
    MISALIGNED("misaligned", 400),
    CURSOR_WITHOUT_MISSION("cursor_without_mission", 400),
    OUT_OF_RANGE("out_of_range", 409),
    CONTENT_MISMATCH("content_mismatch", 409),
    UNKNOWN_MISSION("unknown_mission", 404);

    private final String wire;
    private final int status;

    Kind(String wire, int status) {
      this.wire = wire;
      this.status = status;
    }

    public String wire() {
      return wire;
    }

    public int status() {
      return status;
    }
  }

  private final Kind kind;

  public StreamRefused(Kind kind) {
    super("stream refused: " + Objects.requireNonNull(kind, "kind").wire());
    this.kind = kind;
  }

  public Kind kind() {
    return kind;
  }

  public String code() {
    return kind.wire();
  }
}
