package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.detail.Readiness;

/**
 * The readiness of a Work Package's dependencies: a port of {@code dependency_readiness_for_wp}. A dependency is satisfied once it has
 * reached an acceptable ending: {@code approved} or {@code done}, or {@code canceled} with operator-authored provenance. Every other lane,
 * and an identifier that names no Work Package of the Mission (it reads as planned), leaves the dependency unsatisfied. Pure.
 */
public final class ReadinessDeriver {

  /** The {@code reason_source} of a cancellation an operator wrote (the oracle's {@code OPERATOR_REASON_SOURCE}). */
  static final String OPERATOR = "operator";

  private ReadinessDeriver() {}

  /**
   * @param dependencies the authored dependency identifiers, in authored order (kept, repeats included)
   * @param states the reduced state of each Work Package of the ledger, by identifier
   * @return whether all are satisfied, and the ones that are not in dependency order
   */
  public static Readiness derive(List<WpId> dependencies, Map<String, WpState> states) {
    List<WpId> unsatisfied = new ArrayList<>();
    for (WpId dependency : dependencies) {
      if (!resolved(states.get(dependency.value()))) {
        unsatisfied.add(dependency);
      }
    }
    return new Readiness(unsatisfied.isEmpty(), unsatisfied);
  }

  /** True only for a planned Work Package whose dependencies are satisfied; a Work Package with no lane is never ready. */
  public static boolean readyToStart(Lane statusLane, Readiness readiness) {
    return statusLane == Lane.PLANNED && readiness.satisfied();
  }

  private static boolean resolved(WpState state) {
    if (state == null) {
      return false;
    }
    return switch (state.lane()) {
      case APPROVED, DONE -> true;
      case CANCELED -> OPERATOR.equals(state.reasonSource());
      default -> false;
    };
  }
}
