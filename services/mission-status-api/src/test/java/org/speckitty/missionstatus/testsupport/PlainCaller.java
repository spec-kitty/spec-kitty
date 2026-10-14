package org.speckitty.missionstatus.testsupport;

import java.util.Objects;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.ArtifactPathInput;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;

/**
 * The second adapter, in plain Java (AC-13.3): it drives the four inbound ports with typed arguments only. Text goes in through the
 * {@code parse} factories, an id that does not parse is {@link DetailRefusal#notFound()} before any port is called (so no adapter chooses
 * between a 400 and a 404), and a refusal is the typed exception, never a status. The raw-string parameters live here, in test support,
 * not on the interfaces (rule 16 clause c).
 */
public final class PlainCaller {

  private final MissionDetailQuery missions;
  private final WorkPackageQuery workPackages;
  private final WorkPackageDetailQuery workPackageDetails;
  private final ArtifactQuery artifacts;

  public PlainCaller(MissionDetailQuery missions, WorkPackageQuery workPackages, WorkPackageDetailQuery workPackageDetails, ArtifactQuery artifacts) {
    this.missions = Objects.requireNonNull(missions, "missions");
    this.workPackages = Objects.requireNonNull(workPackages, "workPackages");
    this.workPackageDetails = Objects.requireNonNull(workPackageDetails, "workPackageDetails");
    this.artifacts = Objects.requireNonNull(artifacts, "artifacts");
  }

  public MissionDetail mission(String rawMission) {
    return missions.mission(missionId(rawMission));
  }

  public WorkPackageView workPackage(String rawMission, String rawWp, boolean includePrompt) {
    return workPackages.workPackage(missionId(rawMission), wp(rawWp), includePrompt);
  }

  public WorkPackageDetail workPackageDetail(String rawMission, String rawWp) {
    return workPackageDetails.workPackageDetail(missionId(rawMission), wp(rawWp));
  }

  public ArtifactListing artifacts(String rawMission) {
    return artifacts.list(missionId(rawMission));
  }

  /** The path is passed on as given: whether zero, two or undecodable values are refused is the port's rule, not the caller's. */
  public ArtifactContent artifact(String rawMission, ArtifactPathInput path) {
    return artifacts.content(missionId(rawMission), path);
  }

  private static MissionId missionId(String raw) {
    return MissionId.parse(raw).orElseThrow(DetailRefusal::notFound);
  }

  private static WpId wp(String raw) {
    return WpId.parse(raw).orElseThrow(DetailRefusal::notFound);
  }
}
