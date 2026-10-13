package org.speckitty.missionstatus.domain.readmodel.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.domain.readmodel.overview.Fixtures.meta;
import static org.speckitty.missionstatus.domain.readmodel.overview.Fixtures.snapshot;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;

class OverviewDeriverTest {

  private static LifecycleStatus status(MissionMeta meta, Lane... lanes) {
    return OverviewDeriver.derive(meta, snapshot(lanes), StreamCursor.start()).lifecycleStatus();
  }

  private static final MissionMeta PLAIN = meta("alpha", "Alpha", null, null, false);
  private static final MissionMeta ACCEPTED = meta("alpha", "Alpha", "2026-09-05T00:00:00Z", null, false);
  private static final MissionMeta DISCARDED = meta("alpha", "Alpha", null, "2026-09-06T00:00:00Z", false);

  // ------------------------------------------------------------------ lifecycleStatus, each rule its own branch

  @Test
  void ruleOneDiscardedIsEvaluatedBeforeEverythingElse() {
    assertThat(status(DISCARDED)).isEqualTo(LifecycleStatus.DISCARDED); // wpTotal 0 would be draft
    assertThat(status(DISCARDED, Lane.IN_PROGRESS)).isEqualTo(LifecycleStatus.DISCARDED); // an active lane would be active
    assertThat(status(meta("alpha", "Alpha", "2026-09-05T00:00:00Z", "2026-09-06T00:00:00Z", false), Lane.DONE)).isEqualTo(LifecycleStatus.DISCARDED);
  }

  @Test
  void ruleTwoNoWorkPackagesIsDraft() {
    assertThat(status(PLAIN)).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(status(ACCEPTED)).isEqualTo(LifecycleStatus.DRAFT);
  }

  @Test
  void ruleThreeAnyActiveLaneIsActive() {
    for (Lane lane : List.of(Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED)) {
      assertThat(status(PLAIN, Lane.PLANNED, lane)).as(lane.wire()).isEqualTo(LifecycleStatus.ACTIVE);
    }
  }

  @Test
  void ruleFourPlannedOrBlockedIsPlannedIncludingTheBlockedOnlyQuirk() {
    assertThat(status(PLAIN, Lane.PLANNED, Lane.DONE)).isEqualTo(LifecycleStatus.PLANNED);
    assertThat(status(PLAIN, Lane.BLOCKED)).isEqualTo(LifecycleStatus.PLANNED);
    assertThat(status(ACCEPTED, Lane.BLOCKED, Lane.DONE)).isEqualTo(LifecycleStatus.PLANNED);
  }

  @Test
  void ruleFiveFinishedIsActiveUntilAcceptedThenDone() {
    assertThat(status(PLAIN, Lane.DONE, Lane.CANCELED)).isEqualTo(LifecycleStatus.ACTIVE);
    assertThat(status(ACCEPTED, Lane.DONE, Lane.CANCELED)).isEqualTo(LifecycleStatus.DONE);
    assertThat(status(ACCEPTED, Lane.CANCELED, Lane.CANCELED)).isEqualTo(LifecycleStatus.DONE); // the all-canceled quirk
    assertThat(status(PLAIN, Lane.CANCELED)).isEqualTo(LifecycleStatus.ACTIVE);
  }

  @Test
  void aWorkPackageHeldOnlyByAnnotationsCountsInWpTotalButInNoLane() {
    MissionOverview overview = OverviewDeriver.derive(ACCEPTED, snapshot(Lane.UNINITIALIZED), StreamCursor.start());
    assertThat(overview.wpTotal()).isEqualTo(1);
    assertThat(overview.lifecycleStatus()).isEqualTo(LifecycleStatus.DONE);
    assertThat(overview.statusLaneCounts().values()).containsOnly(0);
  }

  @Test
  void theLifecycleVocabularyIsTheContractsFive() {
    assertThat(Arrays.stream(LifecycleStatus.values()).map(LifecycleStatus::wire)).containsExactlyInAnyOrder("active", "planned", "done", "draft", "discarded");
  }

  // ------------------------------------------------------------------ the overview as a whole

  @Test
  void theOverviewCarriesTheContractMembers() {
    StatusSnapshot snapshot = snapshot(Lane.DONE, Lane.BLOCKED, Lane.BLOCKED, Lane.IN_PROGRESS);
    MissionMeta meta = meta("alpha", "  Alpha  ", null, null, false);
    StreamCursor cursor = new StreamCursor(42, "a".repeat(64));
    MissionOverview overview = OverviewDeriver.derive(meta, snapshot, cursor);
    assertThat(overview.missionId()).isEqualTo(meta.missionId());
    assertThat(overview.mid8()).isEqualTo("01J00000");
    assertThat(overview.slug()).isEqualTo("alpha");
    assertThat(overview.friendlyName()).isEqualTo("Alpha");
    assertThat(overview.displayNumber()).isEqualTo(12);
    assertThat(overview.missionType()).isEqualTo("software-dev");
    assertThat(overview.targetBranch()).isEqualTo("main");
    assertThat(overview.topology().wire()).isEqualTo("lanes");
    assertThat(overview.createdAt()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(overview.statusLaneCounts()).containsExactly(
        Map.entry(Lane.PLANNED, 0), Map.entry(Lane.CLAIMED, 0), Map.entry(Lane.IN_PROGRESS, 1), Map.entry(Lane.FOR_REVIEW, 0), Map.entry(Lane.IN_REVIEW, 0),
        Map.entry(Lane.APPROVED, 0), Map.entry(Lane.DONE, 1), Map.entry(Lane.BLOCKED, 2), Map.entry(Lane.CANCELED, 0));
    assertThat(overview.wpTotal()).isEqualTo(4);
    assertThat(overview.blockedCount()).isEqualTo(2);
    assertThat(overview.eventCount()).isEqualTo(4);
    assertThat(overview.lastEventId()).isEqualTo("LAST");
    assertThat(overview.lastActivityAt()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(overview.streamCursor()).isSameAs(cursor);
    assertThat(overview.progress().doneCount()).isEqualTo(1);
    assertThat(overview.acceptedAt()).isNull();
    assertThat(overview.mergedAt()).isNull();
    assertThat(overview.discardedAt()).isNull();
    assertThat(overview.nextAction()).isNull();
  }

  @Test
  void theFriendlyNameFallsBackToTheSlugWhenBlankOrAbsent() {
    assertThat(OverviewDeriver.derive(meta("alpha", null, null, null, false), snapshot(), StreamCursor.start()).friendlyName()).isEqualTo("alpha");
    assertThat(OverviewDeriver.derive(meta("alpha", "    ", null, null, false), snapshot(), StreamCursor.start()).friendlyName()).isEqualTo("alpha");
  }

  // ------------------------------------------------------------------ lastActivityAt

  @Test
  void lastActivityIsTheMaximumByInstantNotByText() {
    // As text the +02:00 value is greater; as an instant it is earlier.
    assertThat(OverviewDeriver.lastActivityAt(List.of("2026-09-01T10:30:00+02:00", "2026-09-01T09:00:00Z"))).isEqualTo("2026-09-01T09:00:00Z");
  }

  @Test
  void lastActivityKeepsTheFirstOfEqualInstantsAndServesItsOwnText() {
    assertThat(OverviewDeriver.lastActivityAt(List.of("2026-09-01T12:00:00+02:00", "2026-09-01T10:00:00Z"))).isEqualTo("2026-09-01T12:00:00+02:00");
    assertThat(OverviewDeriver.lastActivityAt(List.of("2026-09-01T10:00:00Z", "2026-09-01T12:00:00+02:00"))).isEqualTo("2026-09-01T10:00:00Z");
  }

  @Test
  void lastActivityIgnoresAbsentValuesAndIsNullWhenThereIsNone() {
    assertThat(OverviewDeriver.lastActivityAt(Arrays.asList(null, "", null))).isNull();
    assertThat(OverviewDeriver.lastActivityAt(List.of())).isNull();
    assertThat(OverviewDeriver.lastActivityAt(Arrays.asList(null, "2026-09-01T10:00:00Z"))).isEqualTo("2026-09-01T10:00:00Z");
  }

  @Test
  void anInvalidInstantFailsTheDerivationLikeThePythonHelper() {
    assertThatThrownBy(() -> OverviewDeriver.lastActivityAt(List.of("2026-09-01T10:00:00Z", "garbage"))).isInstanceOf(InvalidInstantException.class);
  }

  // ------------------------------------------------------------------ nextAction

  @Test
  void nextActionFollowsTheThreeRules() {
    MissionMeta baseline = meta("alpha", "Alpha", null, null, true);
    MissionMeta acceptedBaseline = meta("alpha", "Alpha", "2026-09-05T00:00:00Z", null, true);
    StreamCursor c = StreamCursor.start();
    assertThat(OverviewDeriver.derive(acceptedBaseline, snapshot(Lane.DONE), c).nextAction()).isNull();
    assertThat(OverviewDeriver.derive(baseline, snapshot(Lane.PLANNED), c).nextAction()).isEqualTo("Run /spec-kitty.review in your coding agent, then: spec-kitty accept --mission alpha");
    assertThat(OverviewDeriver.derive(PLAIN, snapshot(Lane.DONE, Lane.CANCELED), c).nextAction()).isEqualTo("Run: spec-kitty consolidate --mission alpha");
    assertThat(OverviewDeriver.derive(PLAIN, snapshot(Lane.CANCELED, Lane.CANCELED), c).nextAction()).isNull();
    assertThat(OverviewDeriver.derive(PLAIN, snapshot(Lane.DONE, Lane.PLANNED), c).nextAction()).isNull();
    assertThat(OverviewDeriver.derive(PLAIN, snapshot(), c).nextAction()).isNull();
    assertThat(OverviewDeriver.derive(ACCEPTED, snapshot(Lane.DONE), c).nextAction()).isNull();
  }

  // ------------------------------------------------------------------ annotation-only work packages (review cycle 1, R1)

  private static MissionOverview overviewOfLines(MissionMeta meta, LineKind... kinds) {
    List<LedgerLine> lines = new java.util.ArrayList<>();
    for (LineKind kind : kinds) {
      lines.add(new LedgerLine(lines.size() + 1L, "0".repeat(64), 10, kind));
    }
    return OverviewDeriver.derive(meta, new StatusReducer(new AtThenEventId()).reduceLines(lines), StreamCursor.start());
  }

  /**
   * Oracle run (materialize_snapshot, derive_lifecycle_status, compute_weighted_progress, repo .venv python) on rows [annotation of WP09 at
   * 09:00Z]: wpTotal 1, no lane count, percentage 0.0 over total_count 1, lifecycle "active" (unaccepted) and "done" (accepted).
   */
  @Test
  void anAnnotationOnlyWorkPackageCountsInWpTotalAndTheProgressDenominatorButInNoLane() {
    MissionOverview unaccepted = overviewOfLines(PLAIN, new LineKind.Annotation("WP09"));
    assertThat(unaccepted.wpTotal()).isEqualTo(1);
    assertThat(unaccepted.statusLaneCounts().values().stream().mapToInt(Integer::intValue).sum()).isZero();
    assertThat(unaccepted.progress().weightedPercentage()).isZero();
    assertThat(unaccepted.lifecycleStatus()).isEqualTo(LifecycleStatus.ACTIVE);
    assertThat(overviewOfLines(ACCEPTED, new LineKind.Annotation("WP09")).lifecycleStatus()).isEqualTo(LifecycleStatus.DONE);
    assertThat(overviewOfLines(PLAIN).lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
  }

  /** Oracle run on rows [WP01 planned->claimed, annotation of WP09]: wpTotal 2, lanes {claimed: 1}, percentage 2.5 (0.05 / 2), active. */
  @Test
  void anAnnotationOnlyWorkPackageDilutesTheProgressOfTheTransitionedOnes() {
    StatusEvent claim = new StatusEvent("1", "2026-09-01T09:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null);
    MissionOverview overview = overviewOfLines(PLAIN, new LineKind.Status(claim), new LineKind.Annotation("WP09"));
    assertThat(overview.wpTotal()).isEqualTo(2);
    assertThat(overview.statusLaneCounts().get(Lane.CLAIMED)).isEqualTo(1);
    assertThat(overview.progress().weightedPercentage()).isEqualTo(2.5);
    assertThat(overview.lifecycleStatus()).isEqualTo(LifecycleStatus.ACTIVE);
  }
}
