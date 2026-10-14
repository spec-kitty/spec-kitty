package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionPhase;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseBasis;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseName;
import org.speckitty.missionstatus.domain.readmodel.detail.PhaseStatus;

/**
 * The phase table (the oracle's {@code derive_phase_status}): specify, plan and tasks by file, then Completed event, then Started event,
 * then pending; implement and review from the lane counts alone.
 */
class PhaseDeriverTest {

  private static Map<Lane, Integer> counts(Object... laneThenCount) {
    Map<Lane, Integer> counts = new EnumMap<>(Lane.class);
    for (Lane lane : Lane.displayLanes()) {
      counts.put(lane, 0);
    }
    for (int i = 0; i < laneThenCount.length; i += 2) {
      counts.put((Lane) laneThenCount[i], (Integer) laneThenCount[i + 1]);
    }
    return counts;
  }

  private static MissionPhase phase(List<MissionPhase> phases, PhaseName name) {
    return phases.stream().filter(candidate -> candidate.name() == name).findFirst().orElseThrow();
  }

  private static MissionPhase planning(PhaseName name, Set<PhaseName> files, Set<String> events) {
    return phase(PhaseDeriver.derive(counts(), 0, files, events), name);
  }

  @Test
  void theFivePhasesComeInWorkflowOrderWhateverTheInput() {
    List<MissionPhase> phases = PhaseDeriver.derive(counts(), 0, Set.of(), Set.of());

    assertThat(phases).extracting(MissionPhase::name).containsExactly(PhaseName.SPECIFY, PhaseName.PLAN, PhaseName.TASKS, PhaseName.IMPLEMENT, PhaseName.REVIEW);
  }

  @ParameterizedTest
  @EnumSource(value = PhaseName.class, names = {"SPECIFY", "PLAN", "TASKS"})
  void aPlanningPhaseChecksTheFileFirstThenTheCompletedEventThenTheStartedEventThenIsPending(PhaseName name) {
    String started = label(name) + "Started";
    String completed = label(name) + "Completed";

    // a file wins over everything, and says artifact
    assertThat(planning(name, Set.of(name), Set.of(completed, started))).isEqualTo(new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.ARTIFACT));
    assertThat(planning(name, Set.of(name), Set.of())).isEqualTo(new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.ARTIFACT));
    // no file: the Completed event wins over the Started event
    assertThat(planning(name, Set.of(), Set.of(completed, started))).isEqualTo(new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.LIFECYCLE_EVENT));
    assertThat(planning(name, Set.of(), Set.of(completed))).isEqualTo(new MissionPhase(name, PhaseStatus.COMPLETE, PhaseBasis.LIFECYCLE_EVENT));
    assertThat(planning(name, Set.of(), Set.of(started))).isEqualTo(new MissionPhase(name, PhaseStatus.IN_PROGRESS, PhaseBasis.LIFECYCLE_EVENT));
    // nothing: pending, and the basis stays artifact
    assertThat(planning(name, Set.of(), Set.of())).isEqualTo(new MissionPhase(name, PhaseStatus.PENDING, PhaseBasis.ARTIFACT));
  }

  @Test
  void aFileOfAnotherPlanningPhaseOrAnEventOfAnotherPhaseSaysNothing() {
    assertThat(planning(PhaseName.PLAN, Set.of(PhaseName.SPECIFY, PhaseName.TASKS), Set.of("SpecifyCompleted", "TasksCompleted")))
        .isEqualTo(new MissionPhase(PhaseName.PLAN, PhaseStatus.PENDING, PhaseBasis.ARTIFACT));
    assertThat(planning(PhaseName.TASKS, Set.of(), Set.of("tasksstarted", "TasksStarted ", "Tasks")))
        .isEqualTo(new MissionPhase(PhaseName.TASKS, PhaseStatus.PENDING, PhaseBasis.ARTIFACT));
  }

  @Test
  void implementRestsOnTheLaneCountsAndTheTotalAlone() {
    // an empty Mission, or one with every Work Package planned or blocked: pending
    assertThat(implement(counts(), 0)).isEqualTo(PhaseStatus.PENDING);
    assertThat(implement(counts(Lane.PLANNED, 2, Lane.BLOCKED, 1), 3)).isEqualTo(PhaseStatus.PENDING);
    // anything claimed, in progress or in review, or a mix with one planned: in progress
    assertThat(implement(counts(Lane.CLAIMED, 1, Lane.PLANNED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(implement(counts(Lane.IN_PROGRESS, 1), 1)).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(implement(counts(Lane.FOR_REVIEW, 1, Lane.PLANNED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
    // every Work Package at for_review or later (done and canceled count): complete
    assertThat(implement(counts(Lane.FOR_REVIEW, 1, Lane.IN_REVIEW, 1, Lane.APPROVED, 1, Lane.DONE, 1, Lane.CANCELED, 1), 5)).isEqualTo(PhaseStatus.COMPLETE);
    assertThat(implement(counts(Lane.CANCELED, 2), 2)).isEqualTo(PhaseStatus.COMPLETE);
    // blocked is not reviewed
    assertThat(implement(counts(Lane.DONE, 1, Lane.BLOCKED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
  }

  @Test
  void reviewRestsOnTheLaneCountsAndTheTotalAlone() {
    // nothing at for_review or later: pending, whatever is planned or claimed
    assertThat(review(counts(), 0)).isEqualTo(PhaseStatus.PENDING);
    assertThat(review(counts(Lane.PLANNED, 1, Lane.CLAIMED, 1, Lane.IN_PROGRESS, 1, Lane.BLOCKED, 1), 4)).isEqualTo(PhaseStatus.PENDING);
    assertThat(review(counts(Lane.CANCELED, 1, Lane.PLANNED, 1), 2)).isEqualTo(PhaseStatus.PENDING);
    // started once one Work Package is at for_review, in_review, approved or done
    assertThat(review(counts(Lane.FOR_REVIEW, 1, Lane.PLANNED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(review(counts(Lane.IN_REVIEW, 1), 1)).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(review(counts(Lane.APPROVED, 2), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(review(counts(Lane.DONE, 1, Lane.PLANNED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
    // complete only when every Work Package is done or canceled
    assertThat(review(counts(Lane.DONE, 2, Lane.CANCELED, 1), 3)).isEqualTo(PhaseStatus.COMPLETE);
    assertThat(review(counts(Lane.CANCELED, 3), 3)).isEqualTo(PhaseStatus.COMPLETE);
    assertThat(review(counts(Lane.DONE, 1, Lane.APPROVED, 1), 2)).isEqualTo(PhaseStatus.IN_PROGRESS);
  }

  @Test
  void implementAndReviewNeverReadEachOtherOrTheArtifactsOrTheEvents() {
    Set<PhaseName> allFiles = Set.of(PhaseName.SPECIFY, PhaseName.PLAN, PhaseName.TASKS);
    Set<String> allEvents = Set.of("SpecifyCompleted", "PlanCompleted", "TasksCompleted", "SpecifyStarted");
    Map<Lane, Integer> mixed = counts(Lane.IN_PROGRESS, 1, Lane.DONE, 1);

    List<MissionPhase> with = PhaseDeriver.derive(mixed, 2, allFiles, allEvents);
    List<MissionPhase> without = PhaseDeriver.derive(mixed, 2, Set.of(), Set.of());

    assertThat(phase(with, PhaseName.IMPLEMENT)).isEqualTo(phase(without, PhaseName.IMPLEMENT));
    assertThat(phase(with, PhaseName.REVIEW)).isEqualTo(phase(without, PhaseName.REVIEW));
    assertThat(phase(with, PhaseName.IMPLEMENT).basis()).isEqualTo(PhaseBasis.DERIVED_FROM_STATUS_LANES);
    assertThat(phase(with, PhaseName.REVIEW).basis()).isEqualTo(PhaseBasis.DERIVED_FROM_STATUS_LANES);
    assertThat(phase(with, PhaseName.IMPLEMENT).status()).isEqualTo(PhaseStatus.IN_PROGRESS);
    assertThat(phase(with, PhaseName.REVIEW).status()).isEqualTo(PhaseStatus.IN_PROGRESS);
  }

  @Test
  void aLaneMissingFromTheCountsCountsAsZero() {
    Map<Lane, Integer> sparse = new LinkedHashMap<>();
    sparse.put(Lane.DONE, 1);

    List<MissionPhase> phases = PhaseDeriver.derive(sparse, 1, Set.of(), Set.of());

    assertThat(phase(phases, PhaseName.IMPLEMENT).status()).isEqualTo(PhaseStatus.COMPLETE);
    assertThat(phase(phases, PhaseName.REVIEW).status()).isEqualTo(PhaseStatus.COMPLETE);
  }

  private static PhaseStatus implement(Map<Lane, Integer> counts, int total) {
    return phase(PhaseDeriver.derive(counts, total, Set.of(), Set.of()), PhaseName.IMPLEMENT).status();
  }

  private static PhaseStatus review(Map<Lane, Integer> counts, int total) {
    return phase(PhaseDeriver.derive(counts, total, Set.of(), Set.of()), PhaseName.REVIEW).status();
  }

  private static String label(PhaseName name) {
    return switch (name) {
      case SPECIFY -> "Specify";
      case PLAN -> "Plan";
      case TASKS -> "Tasks";
      default -> throw new IllegalArgumentException();
    };
  }
}
