package org.speckitty.missionstatus.adapter.in.http;

import java.math.BigDecimal;
import org.speckitty.missionstatus.adapter.in.http.model.Actor;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactContent;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactEntry;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactListing;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactReference;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactReferences;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactRefusal;
import org.speckitty.missionstatus.adapter.in.http.model.Assignment;
import org.speckitty.missionstatus.adapter.in.http.model.Authored;
import org.speckitty.missionstatus.adapter.in.http.model.Cancellation;
import org.speckitty.missionstatus.adapter.in.http.model.DependencyRef;
import org.speckitty.missionstatus.adapter.in.http.model.HistoryEntry;
import org.speckitty.missionstatus.adapter.in.http.model.MissionDetail;
import org.speckitty.missionstatus.adapter.in.http.model.MissionOverview;
import org.speckitty.missionstatus.adapter.in.http.model.MissionPhase;
import org.speckitty.missionstatus.adapter.in.http.model.OwnedFile;
import org.speckitty.missionstatus.adapter.in.http.model.Project;
import org.speckitty.missionstatus.adapter.in.http.model.Readiness;
import org.speckitty.missionstatus.adapter.in.http.model.Review;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewCycle;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewOverride;
import org.speckitty.missionstatus.adapter.in.http.model.ReviewResult;
import org.speckitty.missionstatus.adapter.in.http.model.Staleness;
import org.speckitty.missionstatus.adapter.in.http.model.Subtask;
import org.speckitty.missionstatus.adapter.in.http.model.SubtaskProgress;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackage;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetail;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetailRefusal;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackageSummary;
import org.speckitty.missionstatus.adapter.in.http.model.Workspace;

/**
 * AC-11c drift probe: one HAND-WRITTEN compile-time reference per mutation target. The nested-build drift test renames one member of
 * each model in a copy of the contract; the generated model then loses the member and this class stops compiling ("cannot find symbol").
 * Without the {@code Project} reference the removal of {@code Project.currentBranch} passes silently (research.md spike record, Review
 * cycle 2 F3). This class was moved here from the skeleton package (DD-67): do not delete it.
 *
 * <p>WP06 (P2, FR-015): one reference per model of the five detail operations. The expression text of each is quoted by
 * {@code ContractDriftNestedBuildTest}. A HAND record cannot fail on contract drift, so {@code adapter.in.http.dto.WorkPackage} is
 * guarded by its generated twin: {@link #workPackage()} references the twin's {@code forceCount}, and {@link #handWorkPackageForceCount}
 * reads the same member from the hand record, so the pair is kept together (research.md, "Plan defects found" item 1).
 */
final class ContractDriftProbe {

  private ContractDriftProbe() {}

  static MissionOverview missionOverview() {
    return new MissionOverview().blockedCount(1);
  }

  static Project project() {
    return new Project().currentBranch("main");
  }

  static Actor actor() {
    return new Actor().tool("claude");
  }

  static ArtifactContent artifactContent() {
    return new ArtifactContent().sizeBytes(1);
  }

  static ArtifactEntry artifactEntry() {
    return new ArtifactEntry().modifiedAt("2026-01-01T00:00:00Z");
  }

  static ArtifactListing artifactListing() {
    return new ArtifactListing().truncated(false);
  }

  static ArtifactReference artifactReference() {
    return new ArtifactReference().kind(null);
  }

  static ArtifactReferences artifactReferences() {
    return new ArtifactReferences().spec(null);
  }

  // The shared Problem also declares a text `code`, so a renamed member leaves `code(String)` behind; the enum argument is what breaks.
  static ArtifactRefusal artifactRefusal() {
    return new ArtifactRefusal().code(ArtifactRefusal.CodeEnum.NOT_FOUND);
  }

  static Assignment assignment() {
    return new Assignment().agentProfileVersion("1.0");
  }

  static Authored authored() {
    return new Authored().agentProfile("implementer");
  }

  static Cancellation cancellation() {
    return new Cancellation().reasonSource(null);
  }

  static DependencyRef dependencyRef() {
    return new DependencyRef().wpId("WP01");
  }

  static HistoryEntry historyEntry() {
    return new HistoryEntry().reviewVerdict(null);
  }

  static MissionDetail missionDetail() {
    return new MissionDetail().addWorkPackagesItem(null);
  }

  static MissionPhase missionPhase() {
    return new MissionPhase().basis(null);
  }

  static OwnedFile ownedFile() {
    return new OwnedFile().isGlob(false);
  }

  static Readiness readiness() {
    return new Readiness().satisfied(true);
  }

  static Review review() {
    return new Review().latestResult(null);
  }

  static ReviewCycle reviewCycle() {
    return new ReviewCycle().artifactPath("a");
  }

  static ReviewOverride reviewOverride() {
    return new ReviewOverride().complete(true);
  }

  static ReviewResult reviewResult() {
    return new ReviewResult().reference("r");
  }

  static Staleness staleness() {
    return new Staleness().minutesSinceCommit(BigDecimal.ONE);
  }

  static Subtask subtask() {
    return new Subtask().id("T001");
  }

  static SubtaskProgress subtaskProgress() {
    return new SubtaskProgress().total(1);
  }

  static WorkPackage workPackage() {
    return new WorkPackage().forceCount(1);
  }

  static int handWorkPackageForceCount(org.speckitty.missionstatus.adapter.in.http.dto.WorkPackage hand) {
    return hand.forceCount();
  }

  static WorkPackageDetail workPackageDetail() {
    return new WorkPackageDetail().artifactReferences(null);
  }

  static WorkPackageDetailRefusal workPackageDetailRefusal() {
    return new WorkPackageDetailRefusal().code(WorkPackageDetailRefusal.CodeEnum.NOT_FOUND);
  }

  static WorkPackageSummary workPackageSummary() {
    return new WorkPackageSummary().lastTransitionAt("2026-01-01T00:00:00Z");
  }

  static Workspace workspace() {
    return new Workspace().worktreePresent(true);
  }
}
