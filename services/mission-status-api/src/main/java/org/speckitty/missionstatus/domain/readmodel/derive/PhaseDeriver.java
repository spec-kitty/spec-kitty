package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionPhase;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseBasis;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseName;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseStatus;

/**
 * The five phases of a Mission, in the order specify, plan, tasks, implement, review (the oracle's {@code derive_phases}).
 *
 * <p>A planning phase is judged by, in this order: a planning file (basis {@code artifact}, complete), the Completed event (complete, basis
 * {@code lifecycle_event}), the Started event (in progress, {@code lifecycle_event}), else pending with basis {@code artifact}. Implement and
 * review rest on the lane counts and the Work Package total alone; neither reads the other, an artifact or an event.
 *
 * <p>Pure: only {@code java.lang}, {@code java.util} and the model records. What a planning file is (a regular file, not a link) is decided
 * by the caller, which has the file system; this class receives the answer.
 */
public final class PhaseDeriver {

  private static final List<Lane> REVIEWED_OR_LATER = List.of(Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE, Lane.CANCELED);
  private static final List<Lane> REVIEW_STARTED = List.of(Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED, Lane.DONE);
  private static final List<Lane> NOT_STARTED = List.of(Lane.PLANNED, Lane.BLOCKED);
  private static final List<Lane> FINISHED = List.of(Lane.DONE, Lane.CANCELED);

  private PhaseDeriver() {}

  /**
   * @param laneCounts the count of Work Packages per display lane; a lane that is missing counts as zero
   * @param wpTotal the number of Work Packages the ledger knows
   * @param artifacts the planning phases whose file is a regular file of the primary directory
   * @param lifecycleTypes the text event types of the ledger
   * @return exactly five phases, in workflow order
   */
  public static List<MissionPhase> derive(Map<Lane, Integer> laneCounts, int wpTotal, Set<PhaseName> artifacts, Set<String> lifecycleTypes) {
    List<MissionPhase> phases = new ArrayList<>(PhaseName.values().length);
    for (PhaseName name : PhaseName.values()) {
      phases.add(
          switch (name) {
            case SPECIFY, PLAN, TASKS -> planning(name, artifacts, lifecycleTypes);
            case IMPLEMENT -> implement(laneCounts, wpTotal);
            case REVIEW -> review(laneCounts, wpTotal);
          });
    }
    return phases;
  }

  private static MissionPhase planning(PhaseName name, Set<PhaseName> artifacts, Set<String> lifecycleTypes) {
    String label = name.wire().substring(0, 1).toUpperCase(java.util.Locale.ROOT) + name.wire().substring(1);
    if (artifacts.contains(name)) {
      return new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.ARTIFACT);
    }
    if (lifecycleTypes.contains(label + "Completed")) {
      return new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.LIFECYCLE_EVENT);
    }
    if (lifecycleTypes.contains(label + "Started")) {
      return new MissionPhase(name, PhaseStatus.IN_PROGRESS, PhaseBasis.LIFECYCLE_EVENT);
    }
    return new MissionPhase(name, PhaseStatus.PENDING, PhaseBasis.ARTIFACT);
  }

  private static MissionPhase implement(Map<Lane, Integer> counts, int wpTotal) {
    PhaseStatus status;
    if (wpTotal > 0 && count(counts, REVIEWED_OR_LATER) == wpTotal) {
      status = PhaseStatus.COMPLETE;
    } else if (count(counts, NOT_STARTED) == wpTotal) {
      status = PhaseStatus.PENDING;
    } else {
      status = PhaseStatus.IN_PROGRESS;
    }
    return new MissionPhase(PhaseName.IMPLEMENT, status, PhaseBasis.DERIVED_FROM_STATUS_LANES);
  }

  private static MissionPhase review(Map<Lane, Integer> counts, int wpTotal) {
    PhaseStatus status;
    if (wpTotal > 0 && count(counts, FINISHED) == wpTotal) {
      status = PhaseStatus.COMPLETE;
    } else if (count(counts, REVIEW_STARTED) == 0) {
      status = PhaseStatus.PENDING;
    } else {
      status = PhaseStatus.IN_PROGRESS;
    }
    return new MissionPhase(PhaseName.REVIEW, status, PhaseBasis.DERIVED_FROM_STATUS_LANES);
  }

  private static int count(Map<Lane, Integer> counts, List<Lane> lanes) {
    int sum = 0;
    for (Lane lane : lanes) {
      sum += counts.getOrDefault(lane, 0);
    }
    return sum;
  }
}
