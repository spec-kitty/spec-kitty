package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;

/** One owned-file pattern of a Work Package and whether the lane changed it (the contract's {@code OwnedFile}). */
public record OwnedFileEntry(String pattern, boolean isGlob, ChangeState changeState) {

  /** The change state of an owned file (the contract's {@code ChangeState}). */
  public enum ChangeState {
    CHANGED("changed"),
    UNCHANGED("unchanged"),
    UNKNOWN("unknown");

    private final String wire;

    ChangeState(String wire) {
      this.wire = wire;
    }

    public String wire() {
      return wire;
    }
  }

  public OwnedFileEntry {
    Objects.requireNonNull(pattern, "pattern");
    Objects.requireNonNull(changeState, "changeState");
  }
}
