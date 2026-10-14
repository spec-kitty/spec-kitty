package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;

/**
 * The detail of one Mission (the contract's {@code MissionDetail}): every member of the overview, the five phases and one summary per Work
 * Package. The overview is held whole; the mapper writes its members at the top level of the object, as the contract does.
 *
 * @param overview the overview members
 * @param phases exactly five, in the order specify, plan, tasks, implement, review
 * @param workPackages one per Work Package, ordered by id as plain strings by whoever builds the detail
 */
public record MissionDetail(MissionOverview overview, List<MissionPhase> phases, List<WorkPackageSummary> workPackages) {

  public MissionDetail {
    Objects.requireNonNull(overview, "overview");
    Objects.requireNonNull(phases, "phases");
    Objects.requireNonNull(workPackages, "workPackages");
    phases = List.copyOf(phases);
    workPackages = List.copyOf(workPackages);
    if (phases.size() != PhaseName.values().length) {
      throw new IllegalArgumentException("a Mission has exactly five phases");
    }
    for (int i = 0; i < phases.size(); i++) {
      if (phases.get(i).name() != PhaseName.values()[i]) {
        throw new IllegalArgumentException("phases are in workflow order");
      }
    }
  }
}
