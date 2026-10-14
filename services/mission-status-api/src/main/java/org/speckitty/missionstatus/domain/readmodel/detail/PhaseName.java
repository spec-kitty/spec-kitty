package org.speckitty.missionstatus.domain.readmodel.detail;

/** The five Mission phases, in workflow order (the contract's {@code MissionPhase.name}). Not the glossary term phase. */
public enum PhaseName {
  SPECIFY("specify"),
  PLAN("plan"),
  TASKS("tasks"),
  IMPLEMENT("implement"),
  REVIEW("review");

  private final String wire;

  PhaseName(String wire) {
    this.wire = wire;
  }

  public String wire() {
    return wire;
  }

  /** True for the two phases that rest on the status lanes and never on an artifact. */
  public boolean derivedFromLanes() {
    return this == IMPLEMENT || this == REVIEW;
  }
}
