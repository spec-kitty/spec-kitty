package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;

/** The extended detail of one Work Package (the contract's {@code WorkPackageDetail}). */
public record WorkPackageDetail(
    MissionId missionId,
    WpId wpId,
    List<SubtaskEntry> subtasks,
    List<DependencyEntry> dependencies,
    List<ReviewCycleEntry> reviewCycles,
    WorkspaceView workspace,
    List<OwnedFileEntry> ownedFiles,
    ArtifactReferences artifactReferences) {

  public WorkPackageDetail {
    Objects.requireNonNull(missionId, "missionId");
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(workspace, "workspace");
    Objects.requireNonNull(artifactReferences, "artifactReferences");
    subtasks = List.copyOf(subtasks);
    dependencies = List.copyOf(dependencies);
    reviewCycles = List.copyOf(reviewCycles);
    ownedFiles = List.copyOf(ownedFiles);
  }
}
