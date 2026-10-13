package org.speckitty.missionstatus.domain.readmodel.overview;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.EnumMap;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpState;

/** The port of {@code compute_weighted_progress} with default weights: lane weight over work packages, summed in id order. */
public final class ProgressCalculator {

  private static final Map<Lane, Double> LANE_WEIGHTS = new EnumMap<>(Lane.class);

  static {
    LANE_WEIGHTS.put(Lane.GENESIS, 0.0);
    LANE_WEIGHTS.put(Lane.UNINITIALIZED, 0.0);
    LANE_WEIGHTS.put(Lane.PLANNED, 0.0);
    LANE_WEIGHTS.put(Lane.CLAIMED, 0.05);
    LANE_WEIGHTS.put(Lane.IN_PROGRESS, 0.3);
    LANE_WEIGHTS.put(Lane.FOR_REVIEW, 0.6);
    LANE_WEIGHTS.put(Lane.IN_REVIEW, 0.7);
    LANE_WEIGHTS.put(Lane.APPROVED, 0.8);
    LANE_WEIGHTS.put(Lane.DONE, 1.0);
    LANE_WEIGHTS.put(Lane.BLOCKED, 0.0);
    LANE_WEIGHTS.put(Lane.CANCELED, 0.0);
  }

  private ProgressCalculator() {}

  public static Progress compute(StatusSnapshot snapshot) {
    if (snapshot.workPackages().isEmpty()) {
      return new Progress(0.0, 0.0, 0);
    }
    double weightedSum = 0.0;
    double weightTotal = 0.0;
    int doneCount = 0;
    // Python iterates sorted(work_packages.items()); floating-point addition order is part of the result.
    for (WpState state : snapshot.workPackages().entrySet().stream().sorted(Map.Entry.comparingByKey(CodePoints::compare)).map(Map.Entry::getValue).toList()) {
      weightedSum += 1.0 * LANE_WEIGHTS.get(state.lane());
      weightTotal += 1.0;
      doneCount += state.lane() == Lane.DONE ? 1 : 0;
    }
    double percentage = weightedSum / weightTotal * 100.0;
    double donePercentage = (double) doneCount / snapshot.workPackages().size() * 100.0;
    return new Progress(round4(percentage), round4(donePercentage), doneCount);
  }

  static double round4(double value) {
    return new BigDecimal(value).setScale(4, RoundingMode.HALF_EVEN).doubleValue();
  }
}
