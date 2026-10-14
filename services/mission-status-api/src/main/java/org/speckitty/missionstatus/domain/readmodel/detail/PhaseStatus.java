package org.speckitty.missionstatus.domain.readmodel.detail;

/** How far a Mission phase has got (the contract's {@code MissionPhase.status}). */
public enum PhaseStatus {
  PENDING("pending"),
  IN_PROGRESS("in_progress"),
  COMPLETE("complete");

  private final String wire;

  PhaseStatus(String wire) {
    this.wire = wire;
  }

  public String wire() {
    return wire;
  }
}
