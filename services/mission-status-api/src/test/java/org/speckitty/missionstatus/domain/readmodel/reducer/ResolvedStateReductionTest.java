package org.speckitty.missionstatus.domain.readmodel.reducer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.historyRow;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.ledger;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.override;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.release;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.releaseAndReplace;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.replace;
import static org.speckitty.missionstatus.domain.readmodel.reducer.ResolvedLedger.subtasks;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Assignment;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpResolved;

/**
 * FR-020 / AC-20.1 to AC-20.4 at the reducer: every resolved member, hand-derived from {@code reduce_parsed} 10.4.4 (data-model.md sections
 * 3, 4 and 7). A reducer that always returns the empty members is red on every test but the control. The expectations of the end-to-end
 * ledgers were produced by the Python oracle itself ({@code LedgerLineDecoderResolvedStateTest}).
 */
class ResolvedStateReductionTest {

  private static final String T1 = "2026-09-01T10:00:00+00:00";
  private static final String T2 = "2026-09-01T10:10:00+00:00";
  private static final String T3 = "2026-09-01T10:20:00+00:00";
  private static final String T4 = "2026-09-01T10:30:00+00:00";

  private static WpResolved resolved(StatusSnapshot snapshot, String wp) {
    return snapshot.resolved().get(wp);
  }

  // ---- AC-20.1 control: no members -------------------------------------------------------------------------------------------

  @Test
  void aLedgerWithNoResolvedMembersGivesEmptyMembersAndTheActorOfTheLatestChange() {
    StatusSnapshot snapshot = ledger().move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "alice").reduce();

    WpResolved wp = resolved(snapshot, "WP01");
    assertThat(wp.assignment()).isEqualTo(Assignment.EMPTY);
    assertThat(wp.subtasks()).isEmpty();
    assertThat(wp.reviewResult()).isNull();
    assertThat(wp.reviewOverride()).isNull();
    assertThat(wp.actor()).isEqualTo(Actor.ofText("alice"));
    assertThat(wp.history()).isEmpty();
    assertThat(snapshot.lifecycleTypes()).isEmpty();
  }

  @Test
  void anEmptyLedgerHasNoResolvedStateAndNoLifecycleTypes() {
    StatusSnapshot snapshot = ledger().reduce();
    assertThat(snapshot.resolved()).isEmpty();
    assertThat(snapshot.lifecycleTypes()).isEmpty();
  }

  // ---- assignment ------------------------------------------------------------------------------------------------------------

  @Test
  void theClaimSidecarWritesTheAgentAndALaterTransitionCarriesItForward() {
    StatusSnapshot snapshot =
        ledger()
            .claim("E1", T1, "WP01", "alice", SlotText.of("claude"))
            .move("E2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, "bob")
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isEqualTo("claude");
    assertThat(resolved(snapshot, "WP01").actor()).isEqualTo(Actor.ofText("bob"));
  }

  @Test
  void aSidecarOnAnyTransitionButPlannedToClaimedWritesNothing() {
    StatusSnapshot snapshot =
        ledger()
            .transition(new org.speckitty.missionstatus.domain.model.StatusEvent("E1", T1, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, false, null, null, null, null, Actor.ofText("a"), null, SlotText.of("ignored"), "a", null))
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isNull();
  }

  @Test
  void aNumericOrBooleanAgentIsStoredAsItIsAndShownAsItsPythonText() {
    StatusSnapshot snapshot =
        ledger().claim("E1", T1, "WP01", "a", SlotText.of("123")).claim("E2", T1, "WP02", "a", SlotText.of("True")).claim("E3", T1, "WP03", "a", SlotText.UNSHOWN).reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isEqualTo("123");
    assertThat(resolved(snapshot, "WP02").assignment().agent()).isEqualTo("True");
    // a list or an object has no handle shape in Python either
    assertThat(resolved(snapshot, "WP03").assignment().agent()).isNull();
  }

  @Test
  void theReleaseClearsTheClaimBeforeTheReplaceSoAConcreteValueInTheSameDeltaWinsAndTheAssigneeIsKept() {
    StatusSnapshot snapshot =
        ledger()
            .claim("E1", T1, "WP01", "a", SlotText.of("dev"))
            .annotation("WP01", T2, "A1", "x", replace("assignee", "keep"))
            .annotation("WP01", T3, "A2", "x", release())
            .claim("E2", T1, "WP02", "a", SlotText.of("dev"))
            .annotation("WP02", T3, "A3", "x", releaseAndReplace("agent", "dev2"))
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isNull();
    assertThat(resolved(snapshot, "WP01").assignment().assignee()).isEqualTo("keep");
    assertThat(resolved(snapshot, "WP02").assignment().agent()).isEqualTo("dev2");
  }

  @Test
  void theResolverSentinelsReadAsNullAndTheLatestAnnotationBySortOrderWinsNotFileOrder() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "a")
            // file order: the later one first
            .annotation("WP01", T3, "A2", "x", replace("model", "sonnet"))
            .annotation("WP01", T2, "A1", "x", replace("model", "__resolved_model_absent__"))
            .annotation("WP01", T2, "A3", "x", replace("agent_profile", "__resolved_profile_absent__"))
            .annotation("WP01", T2, "A4", "x", replace("agent_profile_version", "3"))
            .annotation("WP01", T2, "A5", "x", replace("provider", "__resolved_provider_absent__"))
            .annotation("WP01", T2, "A6", "x", replace("role", "implementer"))
            .reduce();

    Assignment assignment = resolved(snapshot, "WP01").assignment();
    assertThat(assignment.model()).isEqualTo("sonnet");
    assertThat(assignment.agentProfile()).isNull();
    assertThat(assignment.agentProfileVersion()).isEqualTo("3");
    assertThat(assignment.provider()).isNull();
    assertThat(assignment.role()).isEqualTo("implementer");
  }

  @Test
  void aSentinelThatArrivesLastReplacesARealModel() {
    StatusSnapshot snapshot =
        ledger()
            .annotation("WP01", T1, "A1", "x", replace("model", "sonnet"))
            .annotation("WP01", T2, "A2", "x", replace("model", "__resolved_model_absent__"))
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().model()).isNull();
  }

  // ---- subtasks --------------------------------------------------------------------------------------------------------------

  @Test
  void subtasksMergeByIdInTheOrderTheIdsFirstAppearAcrossTheSortedAnnotations() {
    Map<String, Lane> first = new LinkedHashMap<>();
    first.put("T1", Lane.PLANNED);
    first.put("T2", Lane.DONE);
    Map<String, Lane> second = new LinkedHashMap<>();
    second.put("T2", Lane.PLANNED);
    second.put("T3", Lane.DONE);

    StatusSnapshot snapshot =
        ledger().annotation("WP01", T2, "A2", "x", subtasks(second)).annotation("WP01", T1, "A1", "x", subtasks(first)).reduce();

    assertThat(resolved(snapshot, "WP01").subtasks()).containsExactly(Map.entry("T1", Lane.PLANNED), Map.entry("T2", Lane.PLANNED), Map.entry("T3", Lane.DONE));
  }

  // ---- review result ---------------------------------------------------------------------------------------------------------

  private static final ReviewResultRecord APPROVED = new ReviewResultRecord("rev", "approved", "cycle-1");
  private static final ReviewResultRecord CHANGES = new ReviewResultRecord("rev", "changes_requested", "feedback://x");

  @Test
  void anyTransitionThatCarriesAResultWritesItAndALaterOneWithoutKeepsIt() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "a")
            .judged("E2", T2, "WP01", Lane.CLAIMED, Lane.APPROVED, "rev", APPROVED)
            .move("E3", T3, "WP01", Lane.APPROVED, Lane.DONE, "a")
            .reduce();

    assertThat(resolved(snapshot, "WP01").reviewResult()).isEqualTo(APPROVED);
  }

  @Test
  void aForcedExitFromInReviewWithNoResultLandsAnExplicitNullAndAWorkPackageThatNeverHadOneHasNone() {
    StatusSnapshot snapshot =
        ledger()
            .judged("E1", T1, "WP01", Lane.FOR_REVIEW, Lane.IN_REVIEW, "rev", CHANGES)
            .forced("E2", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED, "boss")
            .move("E3", T1, "WP02", Lane.PLANNED, Lane.CLAIMED, "a")
            .reduce();

    assertThat(resolved(snapshot, "WP01").reviewResult()).isNull();
    assertThat(resolved(snapshot, "WP02").reviewResult()).isNull();
  }

  @Test
  void aLaterResultReplacesAnEarlierOne() {
    StatusSnapshot snapshot =
        ledger()
            .judged("E1", T1, "WP01", Lane.FOR_REVIEW, Lane.IN_REVIEW, "rev", CHANGES)
            .judged("E2", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED, "rev", APPROVED)
            .reduce();

    assertThat(resolved(snapshot, "WP01").reviewResult()).isEqualTo(APPROVED);
  }

  // ---- review override -------------------------------------------------------------------------------------------------------

  @Test
  void aPartialOverrideIsKeptAndTheReleaseSentinelClearsIt() {
    StatusSnapshot snapshot =
        ledger()
            .annotation("WP01", T1, "A1", "x", override("2026-09-01T10:00:00+00:00", "arb", "WP01", ""))
            .annotation("WP02", T1, "A2", "x", override("2026-09-01T10:00:00+00:00", "arb", "WP02", "why"))
            .annotation("WP02", T2, "A3", "x", override("", "", "", ""))
            .annotation("WP03", T1, "A4", "x", override("t", "a", "WP03", "r"))
            .reduce();

    ReviewOverrideRecord partial = resolved(snapshot, "WP01").reviewOverride();
    assertThat(partial).isEqualTo(new ReviewOverrideRecord("2026-09-01T10:00:00+00:00", "arb", "WP01", ""));
    assertThat(partial.complete()).isFalse();
    assertThat(resolved(snapshot, "WP02").reviewOverride()).as("released").isNull();
    assertThat(resolved(snapshot, "WP03").reviewOverride().complete()).isTrue();
  }

  @Test
  void twoOverridesResolveByTimeNotByFileOrder() {
    StatusSnapshot snapshot =
        ledger()
            .annotation("WP01", T3, "A2", "x", override("t", "newer", "WP01", "r"))
            .annotation("WP01", T2, "A1", "x", override("t", "older", "WP01", "r"))
            .reduce();

    assertThat(resolved(snapshot, "WP01").reviewOverride().actor()).isEqualTo("newer");
  }

  // ---- actor -----------------------------------------------------------------------------------------------------------------

  @Test
  void theActorIsThatOfTheLatestAppliedTransitionNotOfOneThatLostArbitration() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "alice")
            .move("E2", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, "bob")
            // from_lane does not continue the lane in force: dropped by arm (ii), so carol is never the actor
            .move("E3", T3, "WP01", Lane.PLANNED, Lane.BLOCKED, "carol")
            .annotation("WP01", T4, "A1", "dave", replace("role", "r"))
            .reduce();

    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.IN_PROGRESS);
    assertThat(resolved(snapshot, "WP01").actor()).isEqualTo(Actor.ofText("bob"));
  }

  @Test
  void aWorkPackageKnownOnlyFromAnnotationsTakesTheActorOfTheFirstAnnotationInSortOrder() {
    StatusSnapshot snapshot =
        ledger()
            .annotation("WP01", T3, "A2", "ann-2", replace("role", "r"))
            .annotation("WP01", T1, "A1", "ann-1", replace("assignee", "zed"))
            .reduce();

    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.UNINITIALIZED);
    assertThat(resolved(snapshot, "WP01").actor()).isEqualTo(Actor.ofText("ann-1"));
    assertThat(resolved(snapshot, "WP01").assignment().role()).isEqualTo("r");
  }

  @Test
  void anActorIdentityIsTheSnapshotTextNotAHandleSoANullActorReadsAsNone() {
    // The row's actor was null: Python's str() makes the snapshot slot the text "None", which fits the handle shape.
    StatusSnapshot snapshot =
        ledger()
            .transition(new org.speckitty.missionstatus.domain.model.StatusEvent("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null, Actor.NONE, null, null, "None", null))
            .reduce();

    assertThat(resolved(snapshot, "WP01").actor().tool()).isEqualTo("None");
  }

  // ---- A4: the seed payload fold ---------------------------------------------------------------------------------------------

  @Test
  void aSeedThatLostOnContinuityStillFoldsItsClaimAgentWhileTheLaneStaysWithTheRealTransition() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.BLOCKED, "bob")
            .seed("S1", T2, "WP01", Lane.PLANNED, Lane.CLAIMED, SlotText.of("seed-agent"), null)
            .reduce();

    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.BLOCKED);
    assertThat(resolved(snapshot, "WP01").assignment().agent()).isEqualTo("seed-agent");
    assertThat(resolved(snapshot, "WP01").actor()).as("the slot of the lane setter is untouched").isEqualTo(Actor.ofText("bob"));
  }

  @Test
  void aSeedNeverOverwritesASlotARealEventWrote() {
    StatusSnapshot snapshot =
        ledger()
            .claim("E1", T1, "WP01", "bob", SlotText.of("real-agent"))
            .seed("S1", T2, "WP01", Lane.PLANNED, Lane.CLAIMED, SlotText.of("seed2"), null)
            .judged("E2", T1, "WP02", Lane.PLANNED, Lane.BLOCKED, "bob", APPROVED)
            .seed("S2", T2, "WP02", Lane.IN_REVIEW, Lane.APPROVED, null, CHANGES)
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isEqualTo("real-agent");
    assertThat(resolved(snapshot, "WP02").reviewResult()).isEqualTo(APPROVED);
  }

  @Test
  void aSeedThatLostFoldsAVerdictOnlyWhenItCarriesOneAndALaterSeedOverwritesAnEarlierOne() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.BLOCKED, "bob")
            .seed("S1", T2, "WP01", Lane.IN_REVIEW, Lane.APPROVED, null, null)
            .move("E2", T1, "WP02", Lane.PLANNED, Lane.BLOCKED, "bob")
            .seed("S2", T2, "WP02", Lane.IN_REVIEW, Lane.APPROVED, null, new ReviewResultRecord("first", "approved", "1"))
            .seed("S3", T3, "WP02", Lane.IN_REVIEW, Lane.DONE, null, new ReviewResultRecord("second", "approved", "2"))
            .reduce();

    assertThat(resolved(snapshot, "WP01").reviewResult()).as("a verdict-less loser writes nothing").isNull();
    assertThat(resolved(snapshot, "WP02").reviewResult().reviewer()).isEqualTo("second");
  }

  @Test
  void aSeedThatAppliedKeepsItsClaimAgentThroughALaterRealTransition() {
    StatusSnapshot snapshot =
        ledger()
            .seed("S1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, SlotText.of("s5"), null)
            .move("E1", T2, "WP01", Lane.CLAIMED, Lane.IN_PROGRESS, "carol")
            .reduce();

    assertThat(resolved(snapshot, "WP01").assignment().agent()).isEqualTo("s5");
    assertThat(resolved(snapshot, "WP01").actor()).isEqualTo(Actor.ofText("carol"));
  }

  @Test
  void aSeedThatLostToASameInstantRollbackContributesNothing() {
    // arm (i): a same-at forward event never beats a rollback, and what it would have written is not folded
    StatusSnapshot snapshot =
        ledger()
            .transition(new org.speckitty.missionstatus.domain.model.StatusEvent("R1", T2, "WP01", Lane.IN_REVIEW, Lane.PLANNED, false, null, null, null, null, Actor.ofText("rev"), null, null, "rev", null))
            .seed("S1", T2, "WP01", Lane.PLANNED, Lane.CLAIMED, SlotText.of("seed-agent"), null)
            .reduce();

    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.PLANNED);
    assertThat(resolved(snapshot, "WP01").assignment().agent()).isNull();
  }

  // ---- history (OO-1) --------------------------------------------------------------------------------------------------------

  @Test
  void theHistoryListsEveryToLaneRowOfTheWorkPackageEvenADuplicateIdAndEvenARowTheArbitrationDropped() {
    StatusSnapshot snapshot =
        ledger()
            .move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "a")
            .history(historyRow("WP01", "E1", T1, "planned", "claimed"))
            // the same id again, later: the fold keeps the first, the history lists both
            .move("E1", T2, "WP01", Lane.CLAIMED, Lane.DONE, "a")
            .history(historyRow("WP01", "E1", T2, "claimed", "done"))
            // from_lane does not continue the lane: dropped by arm (ii), listed all the same
            .move("E2", T3, "WP01", Lane.PLANNED, Lane.BLOCKED, "a")
            .history(historyRow("WP01", "E2", T3, "planned", "blocked"))
            .reduce();

    assertThat(snapshot.workPackages().get("WP01").lane()).isEqualTo(Lane.CLAIMED);
    assertThat(resolved(snapshot, "WP01").history()).extracting(HistoryRow::eventId, HistoryRow::toLane).containsExactly(org.assertj.core.groups.Tuple.tuple("E1", "claimed"), org.assertj.core.groups.Tuple.tuple("E1", "done"), org.assertj.core.groups.Tuple.tuple("E2", "blocked"));
  }

  @Test
  void theHistoryIsOrderedByInstantAndAnAnnotationRowIsNotInIt() {
    StatusSnapshot snapshot =
        ledger()
            .history(historyRow("WP01", "B", "2026-09-01T12:00:00+02:00", "planned", "claimed"))
            .annotation("WP01", T2, "A1", "x", replace("role", "r"))
            .history(historyRow("WP01", "A", "2026-09-01T09:00:00Z", "genesis", "planned"))
            .history(historyRow("WP02", "C", "2026-09-01T09:00:00Z", "planned", "claimed"))
            .reduce();

    assertThat(resolved(snapshot, "WP01").history()).extracting(HistoryRow::eventId).containsExactly("A", "B");
    assertThat(resolved(snapshot, "WP02").history()).extracting(HistoryRow::eventId).containsExactly("C");
    assertThat(snapshot.workPackages()).doesNotContainKey("WP02");
  }

  // ---- lifecycleTypes --------------------------------------------------------------------------------------------------------

  @Test
  void lifecycleTypesAreTheDistinctEventTypesInTheOrderFirstMetWhateverTheLineWasClassifiedAs() {
    StatusSnapshot snapshot = ledger().typed("PlanStarted").typed("DecisionPointOpened").typed("PlanStarted").move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "a").reduce();

    assertThat(snapshot.lifecycleTypes()).containsExactly("PlanStarted", "DecisionPointOpened");
  }

  @Test
  void aWorkPackageWithOnlyHistoryRowsStillHasAResolvedEntry() {
    StatusSnapshot snapshot = ledger().history(historyRow("WP09", "A", T1, "planned", "claimed")).reduce();

    assertThat(snapshot.workPackages()).isEmpty();
    assertThat(resolved(snapshot, "WP09").assignment()).isEqualTo(Assignment.EMPTY);
    assertThat(resolved(snapshot, "WP09").history()).hasSize(1);
  }

  @Test
  void theFourArgumentSnapshotHasNoResolvedMembersAndTheSameLaneCounts() {
    StatusSnapshot full = ledger().move("E1", T1, "WP01", Lane.PLANNED, Lane.CLAIMED, "a").typed("PlanStarted").reduce();
    StatusSnapshot floor = new StatusSnapshot(full.workPackages(), full.eventCount(), full.lastEventId(), full.materializedAt());

    assertThat(floor.resolved()).isEmpty();
    assertThat(floor.lifecycleTypes()).isEmpty();
    assertThat(floor.laneCounts()).isEqualTo(full.laneCounts());
    assertThat(floor.workPackages()).isEqualTo(full.workPackages());
    assertThat(List.copyOf(full.resolved().keySet())).containsExactly("WP01");
  }
}
