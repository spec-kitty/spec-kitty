package org.speckitty.missionstatus.domain.model;

/** The stored shape of a Mission's branches and lanes; {@code unknown} when none is stored or the value is not one of the four. */
public enum Topology {
  SINGLE_BRANCH("single_branch"),
  LANES("lanes"),
  COORD("coord"),
  LANES_WITH_COORD("lanes_with_coord"),
  UNKNOWN("unknown");

  private final String wire;

  Topology(String wire) {
    this.wire = wire;
  }

  public String wire() {
    return wire;
  }

  /** The two shapes whose status is read from the coordination worktree. */
  public boolean routesThroughCoordination() {
    return this == COORD || this == LANES_WITH_COORD;
  }

  public static Topology fromStored(String stored) {
    for (Topology topology : values()) {
      if (topology != UNKNOWN && topology.wire.equals(stored)) {
        return topology;
      }
    }
    return UNKNOWN;
  }
}
