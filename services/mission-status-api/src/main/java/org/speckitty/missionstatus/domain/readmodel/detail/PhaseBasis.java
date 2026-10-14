package org.speckitty.missionstatus.domain.readmodel.detail;

/** What a phase status rests on (the contract's {@code MissionPhase.basis}). */
public enum PhaseBasis {
  ARTIFACT("artifact"),
  LIFECYCLE_EVENT("lifecycle_event"),
  DERIVED_FROM_STATUS_LANES("derived_from_status_lanes");

  private final String wire;

  PhaseBasis(String wire) {
    this.wire = wire;
  }

  public String wire() {
    return wire;
  }
}
