package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;

/**
 * One of the five phases of a Mission. Implement and review always rest on the status lanes; specify, plan and tasks on an artifact or a
 * lifecycle event. The constructor refuses the combinations the contract excludes.
 */
public record MissionPhase(PhaseName name, PhaseStatus status, PhaseBasis basis) {

  public MissionPhase {
    Objects.requireNonNull(name, "name");
    Objects.requireNonNull(status, "status");
    Objects.requireNonNull(basis, "basis");
    if (name.derivedFromLanes() != (basis == PhaseBasis.DERIVED_FROM_STATUS_LANES)) {
      throw new IllegalArgumentException("basis does not fit the phase");
    }
  }
}
