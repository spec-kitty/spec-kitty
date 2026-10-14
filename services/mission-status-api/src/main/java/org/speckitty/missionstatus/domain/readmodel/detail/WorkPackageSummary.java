package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;

/**
 * The summary of one Work Package in the Mission detail (the contract's {@code WorkPackageSummary}).
 *
 * @param phaseLabel the authored phase label, or null
 * @param statusLane the lane, or null for a Work Package with a planning file and no events
 * @param lastTransitionAt the time of the last transition as stored, or null
 */
public record WorkPackageSummary(
    WpId wpId,
    String title,
    String phaseLabel,
    Lane statusLane,
    List<WpId> dependencies,
    Readiness readiness,
    boolean readyToStart,
    SubtaskProgress subtaskProgress,
    String lastTransitionAt) {

  public WorkPackageSummary {
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(title, "title");
    Objects.requireNonNull(dependencies, "dependencies");
    Objects.requireNonNull(readiness, "readiness");
    Objects.requireNonNull(subtaskProgress, "subtaskProgress");
    dependencies = List.copyOf(dependencies);
  }
}
