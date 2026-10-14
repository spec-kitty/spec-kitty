package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.WpId;

/** Whether every dependency of a Work Package has reached an acceptable ending, and the ones that have not, in dependency order. */
public record Readiness(boolean satisfied, List<WpId> unsatisfied) {

  public Readiness {
    Objects.requireNonNull(unsatisfied, "unsatisfied");
    unsatisfied = List.copyOf(unsatisfied);
  }
}
