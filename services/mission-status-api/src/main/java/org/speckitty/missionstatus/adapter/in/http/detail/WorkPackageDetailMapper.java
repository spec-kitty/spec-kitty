package org.speckitty.missionstatus.adapter.in.http.detail;

import org.speckitty.missionstatus.adapter.in.http.model.ArtifactReference;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactReferences;
import org.speckitty.missionstatus.adapter.in.http.model.DependencyRef;
import org.speckitty.missionstatus.adapter.in.http.model.OwnedFile;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewCycle;
import org.speckitty.missionstatus.adapter.in.http.model.Subtask;
import org.speckitty.missionstatus.adapter.in.http.model.Workspace;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.detail.DependencyEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.OwnedFileEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewCycleEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkspaceView;

/**
 * Shapes the records of the Work Package detail into the generated contract model. It holds no logic of the route: ordering, projection and
 * derivation are done by the application layer, so the mapper imports nothing of {@code domain.readmodel.derive}, {@code domain.redaction}
 * or {@code application} other than the inbound port (rule 15). Every array is present, and possibly empty.
 */
public final class WorkPackageDetailMapper {

  private WorkPackageDetailMapper() {}

  public static org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetail detail(WorkPackageDetail detail) {
    return new org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetail(
        detail.missionId().value(),
        detail.wpId().value(),
        detail.subtasks().stream().map(WorkPackageDetailMapper::subtask).toList(),
        detail.dependencies().stream().map(WorkPackageDetailMapper::dependency).toList(),
        detail.reviewCycles().stream().map(WorkPackageDetailMapper::cycle).toList(),
        workspace(detail.workspace()),
        detail.ownedFiles().stream().map(WorkPackageDetailMapper::owned).toList(),
        new ArtifactReferences(reference(detail.artifactReferences().prompt()), reference(detail.artifactReferences().spec())));
  }

  private static Subtask subtask(SubtaskEntry entry) {
    return new Subtask(entry.id(), entry.title(), entry.statusLane() == null ? null : Subtask.StatusLaneEnum.fromValue(entry.statusLane().wire()));
  }

  private static DependencyRef dependency(DependencyEntry entry) {
    Lane lane = entry.statusLane();
    return new DependencyRef(entry.wpId().value(), entry.title(), lane == null ? null : DependencyRef.StatusLaneEnum.fromValue(lane.wire()));
  }

  private static ReviewCycle cycle(ReviewCycleEntry entry) {
    return new ReviewCycle(
        entry.cycleNumber(),
        entry.reviewedAt(),
        entry.reviewer(),
        entry.verdict() == null ? null : ReviewCycle.VerdictEnum.fromValue(entry.verdict().wire()),
        entry.feedbackReference(),
        entry.artifactPath());
  }

  private static Workspace workspace(WorkspaceView view) {
    return new Workspace(view.laneId(), view.laneBranch(), view.planningBranch(), view.worktreePresent());
  }

  private static OwnedFile owned(OwnedFileEntry entry) {
    return new OwnedFile(entry.pattern(), entry.isGlob(), OwnedFile.ChangeStateEnum.fromValue(entry.changeState().wire()));
  }

  private static ArtifactReference reference(org.speckitty.missionstatus.domain.readmodel.detail.ArtifactReference reference) {
    return reference == null ? null : new ArtifactReference(reference.path(), ArtifactReference.KindEnum.fromValue(reference.kind().wire()));
  }
}
