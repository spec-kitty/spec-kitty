package org.speckitty.missionstatus.adapter.in.http;

import org.speckitty.missionstatus.adapter.in.http.model.MissionOverview;
import org.speckitty.missionstatus.adapter.in.http.model.Project;

/**
 * AC-11c drift probe: one HAND-WRITTEN compile-time reference per mutation target. The nested-build drift test renames
 * {@code MissionOverview.blockedCount} and removes the required {@code Project.currentBranch} in a copy of the contract; the
 * generated models then lose the member and this class stops compiling ("cannot find symbol"). Without the {@code Project}
 * reference the second mutation passes silently (research.md spike record, Review cycle 2 F3). This class was moved here from the skeleton
 * package (DD-67): do not delete it.
 */
final class ContractDriftProbe {

  private ContractDriftProbe() {}

  static MissionOverview missionOverview() {
    return new MissionOverview().blockedCount(1);
  }

  static Project project() {
    return new Project().currentBranch("main");
  }
}
