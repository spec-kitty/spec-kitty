package org.speckitty.missionstatus.domain.readmodel.reducer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.cancel;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.claim;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.forced;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.forcedCancel;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.move;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.withReviewRef;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpState;

/** Pure unit tests of the reduction; no Spring annotation and no context (AC-5c). Expectations are derived by hand from reduce_parsed. */
class StatusReducerTest {

  private static final String T1 = "2026-09-01T09:00:00Z";
  private static final String T2 = "2026-09-01T10:00:00Z";
  private static final String T3 = "2026-09-01T11:00:00Z";

  private static final StatusReducer reducer = new StatusReducer(new AtThenEventId());

  /** The interleaved shape: five work packages, each isolating one rule. */
  static List<StatusEvent> interleaved() {
    return List.of(
        // WP01: equal at, different event_id; file order is the reverse of sort order. Sorted: A (planned->claimed), B (planned->blocked);
        // B does not continue the lane in force, so arm (ii) drops it.
        move("B", T1, "WP01", Lane.PLANNED, Lane.BLOCKED),
        move("A", T1, "WP01", Lane.PLANNED, Lane.CLAIMED),
        // WP02: a duplicated event_id, the first wins.
        move("D", T1, "WP02", Lane.PLANNED, Lane.CLAIMED),
        move("D", T2, "WP02", Lane.CLAIMED, Lane.DONE),
        // WP03: a +02:00 row against a Z row. As text Z1 < Z2, although the instant of Z2 is earlier: Z1 applies, Z2 is dropped.
        move("Z1", "2026-09-01T09:00:00Z", "WP03", Lane.PLANNED, Lane.CLAIMED),
        move("Z2", "2026-09-01T10:30:00+02:00", "WP03", Lane.PLANNED, Lane.BLOCKED),
        // WP04: two rows differing only in the fractional-second digit count. As text ".5Z" < "Z": F2 applies, F1 is dropped.
        move("F1", "2026-09-01T10:00:00Z", "WP04", Lane.PLANNED, Lane.BLOCKED),
        move("F2", "2026-09-01T10:00:00.5Z", "WP04", Lane.PLANNED, Lane.CLAIMED),
        // WP05: sort order differs from file order by time.
        move("L2", T3, "WP05", Lane.CLAIMED, Lane.IN_PROGRESS),
        move("L1", T1, "WP05", Lane.PLANNED, Lane.CLAIMED));
  }

  /** The assertions of the interleaved shape; a wrong ordering or a last-wins dedup makes them fail. */
  static void assertInterleaved(StatusSnapshot snapshot) {
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.workPackages().get("WP01").lastEventId()).isEqualTo("A");
    assertThat(snapshot.workPackages().get("WP02").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.workPackages().get("WP03").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.workPackages().get("WP03").lastEventId()).isEqualTo("Z1");
    assertThat(snapshot.workPackages().get("WP04").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.workPackages().get("WP04").lastEventId()).isEqualTo("F2");
    assertThat(snapshot.workPackages().get("WP05").lane()).isEqualTo(Lane.IN_PROGRESS);
    assertThat(snapshot.eventCount()).isEqualTo(9);
  }

  @Test
  void theInterleavedShapeReducesToTheHandDerivedLanes() {
    StatusSnapshot snapshot = reduce(interleaved());
    assertInterleaved(snapshot);
    assertThat(snapshot.laneCounts()).containsEntry(Lane.CLAIMED, 4).containsEntry(Lane.IN_PROGRESS, 1).containsEntry(Lane.BLOCKED, 0).containsEntry(Lane.DONE, 0);
    assertThat(snapshot.workPackages()).hasSize(5);
    // The last event in sorted order: the latest text among the nine distinct rows is "2026-09-01T11:00:00Z" (L2).
    assertThat(snapshot.lastEventId()).isEqualTo("L2");
    assertThat(snapshot.materializedAt()).isEqualTo(T3);
  }

  @Test
  void aWrongOrderingIsDetectedByTheInterleavedShape() {
    EventOrdering atOnly = (left, right) -> left.at().compareTo(right.at());
    StatusSnapshot wrong = reduce(new StatusReducer(atOnly), interleaved());
    assertThatThrownBy(() -> assertInterleaved(wrong)).isInstanceOf(AssertionError.class);
  }

  @Test
  void aUtf16OrderingIsDetectedBySupplementaryCharacters() {
    List<StatusEvent> events =
        List.of(
            move("U1", "～", "WP01", Lane.PLANNED, Lane.CLAIMED),
            move("U2", new String(Character.toChars(0x1F600)), "WP01", Lane.PLANNED, Lane.BLOCKED));
    assertThat(reduce(events).workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
    EventOrdering utf16 = (left, right) -> left.at().compareTo(right.at());
    assertThat(reduce(new StatusReducer(utf16), events).workPackages().get("WP01").lane()).isEqualTo(Lane.BLOCKED);
  }

  @Test
  void theResultDoesNotDependOnTheInputPermutation() {
    List<StatusEvent> forward = interleaved();
    List<StatusEvent> reversed = new ArrayList<>(forward);
    java.util.Collections.reverse(reversed);
    StatusSnapshot a = reduce(forward);
    StatusSnapshot b = reduce(reversed);
    // The duplicated D differs between the two orders (first occurrence wins), so compare everything else.
    assertThat(b.workPackages().get("WP01")).isEqualTo(a.workPackages().get("WP01"));
    assertThat(b.workPackages().get("WP03")).isEqualTo(a.workPackages().get("WP03"));
    assertThat(b.workPackages().get("WP04")).isEqualTo(a.workPackages().get("WP04"));
    assertThat(b.lastEventId()).isEqualTo(a.lastEventId());
  }

  @Test
  void anEmptyStreamIsAnEmptyZeroedSnapshot() {
    StatusSnapshot snapshot = reduce(List.of());
    assertThat(snapshot.workPackages()).isEmpty();
    assertThat(snapshot.eventCount()).isZero();
    assertThat(snapshot.lastEventId()).isNull();
    assertThat(snapshot.materializedAt()).isEmpty();
    assertThat(snapshot.laneCounts().values()).containsOnly(0);
    assertThat(snapshot.laneCounts()).hasSize(9);
  }

  @Test
  void forceCountsAccumulateAndAreCarriedForward() {
    StatusSnapshot snapshot =
        reduce(
            List.of(
                forced("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED),
                move("2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS),
                forced("3", T3, "WP01", Lane.IN_PROGRESS, Lane.DONE)));
    assertThat(snapshot.workPackages().get("WP01").forceCount()).isEqualTo(2);
    assertThat(snapshot.workPackages().get("WP01").lastTransitionAt()).isEqualTo(T3);
  }

  @Test
  void theNonDisplayLanesAreHeldButNeverCounted() {
    StatusSnapshot snapshot = reduce(List.of(move("1", T1, "WP01", Lane.GENESIS, Lane.GENESIS), move("2", T1, "WP02", Lane.GENESIS, Lane.PLANNED)));
    assertThat(snapshot.workPackages()).hasSize(2);
    assertThat(snapshot.laneCounts().values().stream().mapToInt(Integer::intValue).sum()).isEqualTo(1);
  }

  // ------------------------------------------------------------------ rollback-aware precedence

  @Test
  void aSameTimestampRollbackBeatsAForwardMove() {
    // Sorted by id: "a" (forward in_progress->in_review) then "b" (rollback in_review->planned), same at. The rollback applies.
    StatusSnapshot snapshot =
        reduce(List.of(move("a", T1, "WP01", Lane.IN_PROGRESS, Lane.IN_REVIEW), move("b", T1, "WP01", Lane.IN_REVIEW, Lane.PLANNED)));
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
  }

  @Test
  void aSameTimestampForwardMoveDoesNotBeatAnAppliedRollback() {
    // Arm (i) alone: the forward move starts from the lane the rollback left (planned), so arm (ii) does not fire.
    StatusSnapshot snapshot =
        reduce(List.of(move("r", T1, "WP01", Lane.IN_REVIEW, Lane.PLANNED), move("s", T1, "WP01", Lane.PLANNED, Lane.CLAIMED)));
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
  }

  @Test
  void aLaterStaleApprovalDoesNotOverwriteARollback() {
    List<StatusEvent> events =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.PLANNED),
            move("3", T3, "WP01", Lane.IN_REVIEW, Lane.APPROVED));
    assertThat(reduce(events).workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
  }

  @Test
  void aForcedMoveOverridesTheRollbackPrecedence() {
    List<StatusEvent> events =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.PLANNED),
            forced("3", T3, "WP01", Lane.IN_REVIEW, Lane.APPROVED));
    assertThat(reduce(events).workPackages().get("WP01").lane()).isEqualTo(Lane.APPROVED);
  }

  @Test
  void aGenuineReworkAfterARollbackApplies() {
    List<StatusEvent> events =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.PLANNED),
            move("3", T3, "WP01", Lane.PLANNED, Lane.CLAIMED));
    assertThat(reduce(events).workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
  }

  @Test
  void aLegacyRollbackAppliesWhateverLaneIsInForceAndAPlainStaleExitDoesNot() {
    // Oracle (spec-kitty-events 10.4.4 reduce_parsed): with a review_ref the for_review exit is a rollback, so it is exempt from
    // from_lane continuity and applies; without one it is a stale forward step (from_lane for_review, lane in force in_progress) and is dropped.
    List<StatusEvent> withRef =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED),
            move("2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS),
            withReviewRef("3", T3, "WP01", Lane.FOR_REVIEW, Lane.PLANNED, "review-1"));
    assertThat(reduce(withRef).workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
    List<StatusEvent> withoutRef =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED),
            move("2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS),
            move("3", T3, "WP01", Lane.FOR_REVIEW, Lane.PLANNED));
    assertThat(reduce(withoutRef).workPackages().get("WP01").lane()).isEqualTo(Lane.IN_PROGRESS);
  }

  @Test
  void aSecondExitFromReviewIsStaleOnceTheLaneHasMovedOn() {
    // Oracle (10.4.4): the second in_review exit starts from a lane that is no longer in force (approved), so it is dropped.
    List<StatusEvent> events =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED),
            move("3", T3, "WP01", Lane.IN_REVIEW, Lane.DONE));
    assertThat(reduce(events).workPackages().get("WP01").lane()).isEqualTo(Lane.APPROVED);
    assertThat(reduce(events).workPackages().get("WP01").lastEventId()).isEqualTo("2");
    List<StatusEvent> forcedLast =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED),
            forced("3", T3, "WP01", Lane.IN_REVIEW, Lane.DONE));
    assertThat(reduce(forcedLast).workPackages().get("WP01").lane()).isEqualTo(Lane.DONE);
  }

  // ------------------------------------------------------------------ 10.4.4 arm (ii) for every setter, and reconstruction seeds

  @Test
  void aStaleApprovalAfterDoneDoesNotUndoDone() {
    // The real case (a repository mission, WP03): approved -> done, then a stale unforced in_review -> approved with a later at.
    List<StatusEvent> events =
        List.of(
            move("1", "2026-07-22T01:00:00Z", "WP03", Lane.PLANNED, Lane.CLAIMED),
            move("2", "2026-07-22T02:00:00Z", "WP03", Lane.CLAIMED, Lane.IN_PROGRESS),
            move("3", "2026-07-22T03:00:00Z", "WP03", Lane.IN_PROGRESS, Lane.FOR_REVIEW),
            move("4", "2026-07-22T04:00:00Z", "WP03", Lane.FOR_REVIEW, Lane.IN_REVIEW),
            move("5", "2026-07-22T05:00:00Z", "WP03", Lane.IN_REVIEW, Lane.APPROVED),
            move("6", "2026-07-22T06:00:00Z", "WP03", Lane.APPROVED, Lane.DONE),
            move("7", "2026-07-23T01:00:00Z", "WP03", Lane.IN_REVIEW, Lane.APPROVED));
    WpState wp = reduce(events).workPackages().get("WP03");
    assertThat(wp.lane()).isEqualTo(Lane.DONE);
    assertThat(wp.lastEventId()).isEqualTo("6");
    assertThat(wp.lastTransitionAt()).isEqualTo("2026-07-22T06:00:00Z");
  }

  @Test
  void aStaleStepAfterACancelOrAReclaimedReworkIsDropped() {
    // Oracle (10.4.4, #5967): the setters are a cancel and a rework claim, neither a rollback.
    List<StatusEvent> afterCancel =
        List.of(
            move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED),
            cancel("2", T2, "WP01", Lane.CLAIMED, "stop", null),
            move("3", T3, "WP01", Lane.IN_PROGRESS, Lane.FOR_REVIEW));
    assertThat(reduce(afterCancel).workPackages().get("WP01").lane()).isEqualTo(Lane.CANCELED);
    List<StatusEvent> afterRework =
        List.of(
            move("1", "2026-09-01T08:00:00Z", "WP01", Lane.PLANNED, Lane.IN_REVIEW),
            move("2", "2026-09-01T09:00:00Z", "WP01", Lane.IN_REVIEW, Lane.PLANNED),
            move("3", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED),
            move("4", "2026-09-01T11:00:00Z", "WP01", Lane.IN_REVIEW, Lane.APPROVED));
    assertThat(reduce(afterRework).workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
  }

  @Test
  void aSeedClaimYieldsToTheRecordedLiveLifecycleButASeedRollbackKeepsItsAuthority() {
    // Oracle (10.4.4): a seed that is not a rollback is not a decision, so the real planned -> blocked applies; a seed rollback is.
    List<StatusEvent> seedClaim =
        List.of(
            Events.seed("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "{seed 1}"),
            move("2", T2, "WP01", Lane.PLANNED, Lane.BLOCKED));
    assertThat(reduce(seedClaim).workPackages().get("WP01").lane()).isEqualTo(Lane.BLOCKED);
    List<StatusEvent> seedRollback =
        List.of(
            Events.seed("1", T1, "WP01", Lane.IN_REVIEW, Lane.PLANNED, "{seed 1}"),
            move("2", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED));
    assertThat(reduce(seedRollback).workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
  }

  @Test
  void aRollbackSeedThatDoesNotContinueTheLaneIsDroppedAnAppliedOneYieldsToARealEventAndAnApprovalFollowsItsSameAtTwin() {
    // Oracle (10.4.6, #6061 R1/R2, events#87), checked against spec_kitty_events.diary.reduce_parsed.
    // R1: the seed leaves in_review, the lane in force is planned (set by a real, non-rollback move), so it never reopens the work package.
    List<StatusEvent> arriving =
        List.of(
            move("1", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED),
            move("2", "2026-09-01T10:00:01Z", "WP01", Lane.CLAIMED, Lane.PLANNED),
            Events.seed("3", "2026-09-01T10:00:02Z", "WP01", Lane.IN_REVIEW, Lane.IN_PROGRESS, "{seed 3}"));
    assertThat(reduce(arriving).workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
    // R2: a seed that does continue the lane is applied, then yields to a later real step that is not its bare sibling approval.
    List<StatusEvent> yielding =
        List.of(
            move("1", "2026-09-01T11:00:00Z", "WP02", Lane.FOR_REVIEW, Lane.IN_REVIEW),
            Events.seed("2", "2026-09-01T11:01:00Z", "WP02", Lane.IN_REVIEW, Lane.PLANNED, "{seed 2}"),
            move("3", "2026-09-01T11:02:00Z", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW));
    assertThat(reduce(yielding).workPackages().get("WP02").lane()).isEqualTo(Lane.FOR_REVIEW);
    // events#87: approved -> done shares its at with the approval and has the smaller event_id, yet follows it.
    List<StatusEvent> twins =
        List.of(
            move("1", "2026-09-01T12:00:00Z", "WP03", Lane.FOR_REVIEW, Lane.IN_REVIEW),
            move("3", "2026-09-01T12:01:00Z", "WP03", Lane.IN_REVIEW, Lane.APPROVED),
            move("2", "2026-09-01T12:01:00Z", "WP03", Lane.APPROVED, Lane.DONE));
    StatusSnapshot done = reduce(twins);
    assertThat(done.workPackages().get("WP03").lane()).isEqualTo(Lane.DONE);
    assertThat(done.lastEventId()).isEqualTo("2");
  }

  @Test
  void sameIdSeedsKeepTheCanonicalMinimumWhateverTheFileOrderAndARealRowKeepsTheFirst() {
    StatusEvent claimedSeed = Events.seed("S", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "{\"to_lane\": \"claimed\"}");
    StatusEvent blockedSeed = Events.seed("S", T1, "WP01", Lane.PLANNED, Lane.BLOCKED, "{\"to_lane\": \"blocked\"}");
    assertThat(reduce(List.of(claimedSeed, blockedSeed)).workPackages().get("WP01").lane()).isEqualTo(Lane.BLOCKED);
    assertThat(reduce(List.of(blockedSeed, claimedSeed)).workPackages().get("WP01").lane()).isEqualTo(Lane.BLOCKED);
    // A real row sharing the id: the first in file order wins, seed or not.
    StatusEvent real = move("S", T1, "WP02", Lane.PLANNED, Lane.CLAIMED);
    StatusEvent seedTwin = Events.seed("S", T1, "WP02", Lane.PLANNED, Lane.BLOCKED, "{\"to_lane\": \"blocked\"}");
    assertThat(reduce(List.of(real, seedTwin)).workPackages().get("WP02").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(reduce(List.of(seedTwin, real)).workPackages().get("WP02").lane()).isEqualTo(Lane.BLOCKED);
    assertThat(reduce(List.of(claimedSeed, blockedSeed)).eventCount()).isEqualTo(1);
  }

  // ------------------------------------------------------------------ annotation pass

  @Test
  void anAnnotationOnlyWorkPackageIsHeldInTheNonDisplayLane() {
    // Oracle (spec_kitty_events reduce_parsed via materialize_snapshot), rows: one transition WP01 planned->claimed at 09:00Z, one annotation row of
    // WP09 at 10:00Z. Python: wpTotal 2, lanes {claimed: 1}, WP09 lane "uninitialized", event_count 1, last_event_id "1",
    // weighted percentage 2.5, lifecycle active (unaccepted and accepted).
    StatusSnapshot snapshot =
        reducer.reduceLines(
            List.of(
                line(1, new LineKind.Status(move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED))),
                line(2, new LineKind.Annotation("WP09"))));
    assertThat(snapshot.workPackages()).containsOnlyKeys("WP01", "WP09");
    assertThat(snapshot.workPackages().get("WP09").lane()).isEqualTo(Lane.UNINITIALIZED);
    assertThat(snapshot.workPackages().get("WP09").lastTransitionAt()).isNull();
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.laneCounts().values().stream().mapToInt(Integer::intValue).sum()).isEqualTo(1);
    assertThat(snapshot.laneCounts().get(Lane.CLAIMED)).isEqualTo(1);
    assertThat(snapshot.eventCount()).isEqualTo(1);
    assertThat(snapshot.lastEventId()).isEqualTo("1");
  }

  @Test
  void anAnnotationOnlyStreamIsNotEmptyButHasNoEvents() {
    // Oracle, rows: one annotation row of WP09 and nothing else. Python: wpTotal 1, no lane count, event_count 0, last_event_id None,
    // materialized_at "".
    StatusSnapshot snapshot = reducer.reduceLines(List.of(line(1, new LineKind.Annotation("WP09"))));
    assertThat(snapshot.workPackages()).containsOnlyKeys("WP09");
    assertThat(snapshot.eventCount()).isZero();
    assertThat(snapshot.lastEventId()).isNull();
    assertThat(snapshot.materializedAt()).isEmpty();
    assertThat(snapshot.laneCounts().values().stream().mapToInt(Integer::intValue).sum()).isZero();
  }

  @Test
  void anAnnotationForAWorkPackageWithATransitionChangesNothing() {
    StatusSnapshot snapshot =
        reducer.reduceLines(
            List.of(
                line(1, new LineKind.Annotation("WP01")),
                line(2, new LineKind.Status(move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED)))));
    assertThat(snapshot.workPackages()).containsOnlyKeys("WP01");
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(snapshot.workPackages().get("WP01").lastEventId()).isEqualTo("1");
  }

  // ------------------------------------------------------------------ sort-then-dedup of the projections (review cycle 1, R2)

  /**
   * Oracle run on these rows (jsonl, in file order; every other field null/false, actor "x"), through
   * {@code specify_cli.status.reducer.materialize_snapshot} with {@code <repo>/.venv/bin/python}:
   *
   * <pre>
   * A  at 2026-09-01T09:00:00Z WP01 planned->claimed
   * C1 at 2026-09-01T12:00:00Z WP01 claimed->canceled reason "operator says stop"
   * C1 at 2026-09-01T10:00:00Z WP01 claimed->canceled force=true reason "Force move to canceled"   (same event_id, earlier at)
   * B  at 2026-09-01T11:00:00Z WP02 planned->claimed
   * </pre>
   *
   * Python: event_count 3, last_event_id "C1", materialized_at "2026-09-01T12:00:00Z"; WP01 lane canceled, last_event_id "C1",
   * last_transition_at "2026-09-01T12:00:00Z", force_count 0 (the fold keeps the first copy in file order), cancellation_reason
   * "Force move to canceled", reason_source "synthetic" (the projection keeps the first copy in sorted order, the 10:00Z one); WP02 claimed.
   */
  @Test
  void aDuplicatedEventIdWithADifferentAtSplitsTheFoldFromTheProjections() {
    List<StatusEvent> rows =
        List.of(
            move("A", "2026-09-01T09:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED),
            cancel("C1", "2026-09-01T12:00:00Z", "WP01", Lane.CLAIMED, "operator says stop", null),
            forcedCancel("C1", "2026-09-01T10:00:00Z", "WP01", Lane.CLAIMED, "Force move to canceled"),
            move("B", "2026-09-01T11:00:00Z", "WP02", Lane.PLANNED, Lane.CLAIMED));
    StatusSnapshot snapshot = reduce(reducer, rows);
    assertThat(snapshot.eventCount()).isEqualTo(3);
    assertThat(snapshot.lastEventId()).isEqualTo("C1");
    assertThat(snapshot.materializedAt()).isEqualTo("2026-09-01T12:00:00Z");
    WpState wp01 = snapshot.workPackages().get("WP01");
    assertThat(wp01.lane()).isEqualTo(Lane.CANCELED);
    assertThat(wp01.lastEventId()).isEqualTo("C1");
    assertThat(wp01.lastTransitionAt()).isEqualTo("2026-09-01T12:00:00Z");
    assertThat(wp01.forceCount()).isZero();
    assertThat(wp01.cancellationReason()).isEqualTo("Force move to canceled");
    assertThat(wp01.reasonSource()).isEqualTo("synthetic");
    assertThat(snapshot.workPackages().get("WP02").lane()).isEqualTo(Lane.CLAIMED);
  }

  // ------------------------------------------------------------------ projections of materialize_snapshot

  @Test
  void cancellationProvenanceIsClassifiedForEachReasonShape() {
    StatusSnapshot snapshot =
        reduce(
            List.of(
                cancel("1", T1, "WP01", Lane.PLANNED, "Force move to canceled", null),
                cancel("2", T1, "WP02", Lane.PLANNED, "move-task: reset", null),
                cancel("3", T1, "WP03", Lane.PLANNED, "Superseded by WP09", null),
                cancel("4", T1, "WP04", Lane.PLANNED, null, null),
                cancel("5", T1, "WP05", Lane.PLANNED, "   ", null),
                cancel("6", T1, "WP06", Lane.PLANNED, "Force move to x", "operator")));
    assertThat(snapshot.workPackages().get("WP01").reasonSource()).isEqualTo("synthetic");
    assertThat(snapshot.workPackages().get("WP02").reasonSource()).isEqualTo("synthetic");
    assertThat(snapshot.workPackages().get("WP03").reasonSource()).isEqualTo("operator");
    assertThat(snapshot.workPackages().get("WP03").cancellationReason()).isEqualTo("Superseded by WP09");
    assertThat(snapshot.workPackages().get("WP04").reasonSource()).isEqualTo("synthetic");
    assertThat(snapshot.workPackages().get("WP04").cancellationReason()).isNull();
    assertThat(snapshot.workPackages().get("WP05").reasonSource()).isEqualTo("synthetic");
    assertThat(snapshot.workPackages().get("WP06").reasonSource()).isEqualTo("operator");
  }

  @Test
  void cancellationProvenanceOnlyAppliesWhileTheWorkPackageIsStillCanceled() {
    StatusSnapshot snapshot =
        reduce(
            List.of(
                cancel("1", T1, "WP01", Lane.PLANNED, "Superseded", null),
                forced("2", T2, "WP01", Lane.CANCELED, Lane.PLANNED),
                cancel("3", T1, "WP02", Lane.PLANNED, "first", null),
                cancel("4", T2, "WP02", Lane.CANCELED, "second", null)));
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
    assertThat(snapshot.workPackages().get("WP01").cancellationReason()).isNull();
    assertThat(snapshot.workPackages().get("WP02").cancellationReason()).isEqualTo("second");
  }

  @Test
  void theImplementerOfRecordIsTheLatestClaimWithAnAgent() {
    StatusSnapshot snapshot =
        reduce(
            List.of(
                claim("1", T1, "WP01", "agent-a"),
                move("2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS),
                move("3", T2, "WP01", Lane.IN_PROGRESS, Lane.PLANNED),
                claim("4", T3, "WP01", "agent-b"),
                claim("5", T1, "WP02", ""),
                claim("6", T1, "WP03", null),
                move("7", T1, "WP04", Lane.PLANNED, Lane.CLAIMED)));
    assertThat(snapshot.workPackages().get("WP01").implementerOfRecord()).isEqualTo("agent-b");
    assertThat(snapshot.workPackages().get("WP02").implementerOfRecord()).isNull();
    assertThat(snapshot.workPackages().get("WP03").implementerOfRecord()).isNull();
    assertThat(snapshot.workPackages().get("WP04").implementerOfRecord()).isNull();
  }

  @Test
  void theImplementerProjectionNeverTouchesALaterLaneOrForceCount() {
    StatusSnapshot snapshot = reduce(List.of(claim("1", T1, "WP01", "agent-a"), move("2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS)));
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.IN_PROGRESS);
    assertThat(snapshot.workPackages().get("WP01").forceCount()).isZero();
  }

  // ------------------------------------------------------------------ ledger lines (parse_diary's skip rule)

  /** The only public path is {@code reduceLines}; this wraps transitions into status lines. */
  private static StatusSnapshot reduce(StatusReducer reducer, List<StatusEvent> events) {
    List<LedgerLine> lines = new ArrayList<>();
    for (StatusEvent event : events) {
      lines.add(line(lines.size() + 1L, new LineKind.Status(event)));
    }
    return reducer.reduceLines(lines);
  }

  private static StatusSnapshot reduce(List<StatusEvent> events) {
    return reduce(reducer, events);
  }

  private static LedgerLine line(long number, LineKind kind) {
    return new LedgerLine(number, "0".repeat(64), 10, kind);
  }

  @Test
  void lifecycleIgnoredAndBlankLinesAreSkippedInPlace() {
    StatusEvent event = move("1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED);
    StatusSnapshot snapshot =
        reducer.reduceLines(
            List.of(
                line(1, new LineKind.Lifecycle(new LifecycleEvent("L1", "MissionCreated", T1))),
                line(2, new LineKind.Ignored()),
                line(3, new LineKind.Blank()),
                line(4, new LineKind.Status(event))));
    assertThat(snapshot.eventCount()).isEqualTo(1);
    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
  }

  @Test
  void aMalformedLineMakesTheLogUnreducibleAndNamesTheLine() {
    for (MalformedReason reason : MalformedReason.values()) {
      assertThatThrownBy(() -> reducer.reduceLines(List.of(line(1, new LineKind.Blank()), line(7, new LineKind.Malformed(reason)))))
          .isInstanceOfSatisfying(
              UnreducibleLedgerException.class,
              error -> {
                assertThat(error.lineNumber()).isEqualTo(7);
                assertThat(error.reason()).isEqualTo(reason);
              });
    }
  }
}
