package org.speckitty.missionstatus.application.query.port.in.exceptions;

import java.util.Objects;

/** A stream request refused before any subscription exists: a cursor that cannot be trusted, or an unknown Mission. */
public final class StreamRefused extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** The refusal kinds. The HTTP status of each is the adapter's to map. */
  public enum Kind {
    NEGATIVE("negative"),
    MISALIGNED("misaligned"),
    CURSOR_WITHOUT_MISSION("cursor_without_mission"),
    OUT_OF_RANGE("out_of_range"),
    CONTENT_MISMATCH("content_mismatch"),
    UNKNOWN_MISSION("unknown_mission");

    private final String wire;

    Kind(String wire) {
      this.wire = wire;
    }

    public String wire() {
      return wire;
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
