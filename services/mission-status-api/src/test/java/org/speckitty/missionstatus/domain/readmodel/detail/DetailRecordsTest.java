package org.speckitty.missionstatus.domain.readmodel.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Assignment;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;

/** Construction, defensive copies, invariants and wire words of the detail records (shaped from the contract schemas). */
class DetailRecordsTest {

  private static final MissionId MISSION = new MissionId("01M4S6D5ABCDEFGHJKMNPQRSTV");
  private static final WpId WP = new WpId("WP01");
  private static final Readiness READY = new Readiness(true, List.of());
  private static final SubtaskProgress PROGRESS = new SubtaskProgress(1, 2);

  private static List<MissionPhase> phases() {
    return List.of(
        new MissionPhase(PhaseName.SPECIFY, PhaseStatus.COMPLETE, PhaseBasis.ARTIFACT),
        new MissionPhase(PhaseName.PLAN, PhaseStatus.IN_PROGRESS, PhaseBasis.LIFECYCLE_EVENT),
        new MissionPhase(PhaseName.TASKS, PhaseStatus.PENDING, PhaseBasis.ARTIFACT),
        new MissionPhase(PhaseName.IMPLEMENT, PhaseStatus.PENDING, PhaseBasis.DERIVED_FROM_STATUS_LANES),
        new MissionPhase(PhaseName.REVIEW, PhaseStatus.PENDING, PhaseBasis.DERIVED_FROM_STATUS_LANES));
  }

  @Test
  void enumsServeTheirContractWords() {
    assertThat(List.of(PhaseName.values())).extracting(PhaseName::wire).containsExactly("specify", "plan", "tasks", "implement", "review");
    assertThat(List.of(PhaseStatus.values())).extracting(PhaseStatus::wire).containsExactly("pending", "in_progress", "complete");
    assertThat(List.of(PhaseBasis.values())).extracting(PhaseBasis::wire).containsExactly("artifact", "lifecycle_event", "derived_from_status_lanes");
    assertThat(List.of(ReviewView.Verdict.values())).extracting(ReviewView.Verdict::wire).containsExactly("approved", "changes_requested");
    assertThat(List.of(OwnedFileEntry.ChangeState.values())).extracting(OwnedFileEntry.ChangeState::wire).containsExactly("changed", "unchanged", "unknown");
    assertThat(List.of(WorkPackageView.ReasonSource.values())).extracting(WorkPackageView.ReasonSource::wire).containsExactly("operator", "synthetic");
    assertThat(List.of(WorkPackageView.Staleness.Status.values())).extracting(WorkPackageView.Staleness.Status::wire).containsExactly("fresh", "stale", "not_applicable");
    assertThat(List.of(WorkPackageView.Staleness.Reason.values()))
        .extracting(WorkPackageView.Staleness.Reason::wire)
        .containsExactly("planning_artifact_repo_root_shared_workspace", "live_claim_process");
  }

  @Test
  void implementAndReviewRestOnLanesAndTheOthersNeverDo() {
    assertThat(PhaseName.IMPLEMENT.derivedFromLanes()).isTrue();
    assertThat(PhaseName.REVIEW.derivedFromLanes()).isTrue();
    assertThat(PhaseName.SPECIFY.derivedFromLanes()).isFalse();
    assertThatThrownBy(() -> new MissionPhase(PhaseName.IMPLEMENT, PhaseStatus.PENDING, PhaseBasis.ARTIFACT)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionPhase(PhaseName.TASKS, PhaseStatus.PENDING, PhaseBasis.DERIVED_FROM_STATUS_LANES)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionPhase(null, PhaseStatus.PENDING, PhaseBasis.ARTIFACT)).isInstanceOf(NullPointerException.class);
  }

  private static MissionOverview overview() {
    return new MissionOverview(MISSION, "01M4S6D5", "slug", "Name", null, null, "main", null, "2026-01-01T00:00:00Z", Map.of(), 0, 0, null, null, null, null, null, null, null, 0, null, null);
  }

  @Test
  void aMissionDetailHasExactlyFivePhasesInWorkflowOrderAndCopiesItsLists() {
    List<WorkPackageSummary> summaries = new ArrayList<>(List.of(new WorkPackageSummary(WP, "t", null, null, List.of(), READY, false, PROGRESS, null)));
    MissionDetail detail = new MissionDetail(overview(), phases(), summaries);
    summaries.clear();

    assertThat(detail.workPackages()).hasSize(1);
    assertThatThrownBy(() -> detail.phases().add(detail.phases().get(0))).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> new MissionDetail(overview(), phases().subList(0, 4), List.of())).isInstanceOf(IllegalArgumentException.class);
    List<MissionPhase> swapped = new ArrayList<>(phases());
    swapped.set(0, phases().get(1));
    swapped.set(1, phases().get(0));
    assertThatThrownBy(() -> new MissionDetail(overview(), swapped, List.of())).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionDetail(null, phases(), List.of())).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aSubtaskProgressRefusesImpossibleCounts() {
    assertThatThrownBy(() -> new SubtaskProgress(-1, 0)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new SubtaskProgress(3, 2)).isInstanceOf(IllegalArgumentException.class);
    assertThat(new SubtaskProgress(0, 0).total()).isZero();
  }

  @Test
  void readinessAndSummaryCopyTheirLists() {
    List<WpId> unsatisfied = new ArrayList<>(List.of(WP));
    Readiness readiness = new Readiness(false, unsatisfied);
    unsatisfied.clear();

    assertThat(readiness.unsatisfied()).containsExactly(WP);
    assertThatThrownBy(() -> new WorkPackageSummary(WP, "t", null, null, null, READY, false, PROGRESS, null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aWorkPackageViewKeepsItsSubtaskOrderAsAListOfEntries() {
    List<Map.Entry<String, Lane>> subtasks = new ArrayList<>(List.of(Map.entry("T002", Lane.DONE), Map.entry("T001", Lane.PLANNED)));
    WorkPackageView view = view(subtasks);
    subtasks.clear();

    assertThat(view.subtasks()).extracting(Map.Entry::getKey).containsExactly("T002", "T001");
    assertThatThrownBy(() -> view.subtasks().add(Map.entry("T003", Lane.DONE))).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> view.history().add(null)).isInstanceOf(UnsupportedOperationException.class);
    assertThat(view.review().latestResult()).isNull();
  }

  private static WorkPackageView view(List<Map.Entry<String, Lane>> subtasks) {
    return new WorkPackageView(
        WP, "title", null, new WorkPackageView.Authored(null, null, null, List.of()), List.of(), List.of(), List.of(), null, null, null, null, List.of(),
        null, Assignment.EMPTY, subtasks, PROGRESS, null, null, 0, null, Actor.NONE, null, READY, false, new ReviewView(null, null), List.of(), null, null);
  }

  @Test
  void reviewAndCancellationValuesCarryTheirMembers() {
    ReviewView.Result result = new ReviewView.Result(null, ReviewView.Verdict.APPROVED, "ref");
    ReviewView.ReviewOverride partial = new ReviewView.ReviewOverride(false, null, null, null);
    ReviewView review = new ReviewView(result, partial);

    assertThat(review.latestResult().verdict().wire()).isEqualTo("approved");
    assertThat(review.override().complete()).isFalse();
    assertThat(new WorkPackageView.Cancellation(WorkPackageView.ReasonSource.OPERATOR, null).reasonSource().wire()).isEqualTo("operator");
    assertThat(new WorkPackageView.Staleness(WorkPackageView.Staleness.Status.STALE, WorkPackageView.Staleness.Reason.LIVE_CLAIM_PROCESS, 12.5).minutesSinceCommit()).isEqualTo(12.5);
    assertThat(new WorkPackageView.Staleness(WorkPackageView.Staleness.Status.FRESH, null, 0.0).reason()).isNull();
  }

  @Test
  void nestedValueRecordsHoldTheirInvariants() {
    assertThatThrownBy(() -> new ReviewView.Result("r", null, "ref")).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WorkPackageView.Cancellation(null, "x")).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WorkPackageView.Staleness(WorkPackageView.Staleness.Status.FRESH, null, -0.5)).isInstanceOf(IllegalArgumentException.class);
    assertThat(new WorkPackageView.Staleness(WorkPackageView.Staleness.Status.NOT_APPLICABLE, null, null).minutesSinceCommit()).isNull();
    assertThat(new WorkPackageView.Authored("r", "p", "m", new ArrayList<>(List.of("T1"))).subtasks()).containsExactly("T1");
  }

  @Test
  void detailRecordsRefuseNullRequiredMembersAndCopyLists() {
    WorkPackageDetail detail =
        new WorkPackageDetail(
            MISSION, WP, new ArrayList<>(List.of(new SubtaskEntry("T001", null, null))), List.of(new DependencyEntry(WP, "d", Lane.DONE)),
            List.of(new ReviewCycleEntry(1, null, null, null, null, null)), new WorkspaceView(null, null, null, false),
            List.of(new OwnedFileEntry("src/**", true, OwnedFileEntry.ChangeState.UNKNOWN)), new ArtifactReferences(null, new ArtifactReference("spec.md", ArtifactKind.SPEC)));

    assertThat(detail.subtasks()).hasSize(1);
    assertThatThrownBy(() -> detail.subtasks().clear()).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> new SubtaskEntry(null, null, null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new DependencyEntry(WP, null, null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new OwnedFileEntry("a", false, null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new ReviewCycleEntry(0, null, null, null, null, null)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new ArtifactReference("a", null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WorkPackageDetail(null, WP, List.of(), List.of(), List.of(), new WorkspaceView(null, null, null, false), List.of(), new ArtifactReferences(null, null)))
        .isInstanceOf(NullPointerException.class);
  }

  @Test
  void artifactRecordsBoundTheirSizesAndEntries() {
    ArtifactEntry entry = new ArtifactEntry("spec.md", ArtifactKind.SPEC, 10, "2026-01-01T00:00:00Z", true);

    assertThat(new ArtifactListing(MISSION, List.of(entry), false).entries()).containsExactly(entry);
    assertThat(ArtifactListing.MAX_ENTRIES).isEqualTo(1000);
    assertThatThrownBy(() -> new ArtifactListing(MISSION, java.util.Collections.nCopies(1001, entry), true)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new ArtifactEntry("a", ArtifactKind.OTHER, -1, "x", false)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new ArtifactContent("a", ArtifactKind.OTHER, "text/plain", -1, false, "")).isInstanceOf(IllegalArgumentException.class);
    assertThat(new ArtifactContent("a", ArtifactKind.OTHER, "text/plain", 0, false, "").content()).isEmpty();
    assertThatThrownBy(() -> new ArtifactContent("a", ArtifactKind.OTHER, "text/plain", 0, false, null)).isInstanceOf(NullPointerException.class);
  }
}
