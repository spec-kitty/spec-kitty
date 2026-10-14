package org.speckitty.missionstatus.application.query.stream;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * Every branch of the allow-list that moved from the HTTP adapter into {@link EventProjection}, with the cases the adapter's data builder
 * had through HTTP: an invalid work package id and a non-display target lane drop the row silently; an instant that is missing, not an
 * instant or without an offset, and a strict field that cannot be represented, drop it with one path-free {@code projection_refused}
 * diagnostic; a handle that cannot be a handle is served as null.
 */
class EventProjectionTest {

  private static final MissionId MISSION = new MissionId(Rows.ALPHA_ID);
  private static final String MID8 = Rows.ALPHA_ID.substring(0, 8);
  private static final String AT = "2026-09-01T10:00:00+00:00";
  private static final StreamCursor CURSOR = new StreamCursor(107, "b1d594537c90f3bcff0ab6fb7777af9b65b246cac14067a309276efff8faed95");
  private static final String TOKEN = "ghp_" + "a".repeat(36);

  private final List<Diagnostic> diagnostics = new ArrayList<>();
  private final EventProjection projection = new EventProjection(LeakPatternsFile.load(), diagnostics::add);

  private static Change status(String wpId, Lane from, Lane to, String at, Actor actor, String eventId) {
    return new Change(MISSION, new LineKind.Status(new StatusEvent(eventId, at, wpId, from, to, false, "ref", "why", "source", "agent", actor)), CURSOR);
  }

  private static Change status(String wpId, Lane to, String at) {
    return status(wpId, Lane.PLANNED, to, at, new Actor("claude", null, null), Rows.id(2));
  }

  private static Change lifecycle(String eventId, String at) {
    return new Change(MISSION, new LineKind.Lifecycle(new LifecycleEvent(eventId, "MissionCreated", at)), CURSOR);
  }

  private void assertRefusedWithOneDiagnostic(Optional<StreamEvent> event) {
    assertThat(event).isEmpty();
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null));
  }

  // ---- status transitions ------------------------------------------------------------------------------------------------------

  @Test
  void aStatusTransitionIsProjectedToItsWireValuesAndNothingElse() {
    Change change = status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, new Actor("claude", "implementer", "java-jenny"), Rows.id(2));

    Optional<StreamEvent> event = projection.project(change);

    assertThat(event)
        .contains(
            new StreamEvent.StatusTransition(
                Rows.ALPHA_ID, Rows.id(2), "WP01", "planned", "claimed", AT, new StreamEvent.ActorHandles("claude", "implementer", "java-jenny"), false, CURSOR));
    assertThat(event.orElseThrow().resumeCursor()).contains(CURSOR);
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aForcedTransitionKeepsItsFlag() {
    StatusEvent forced = new StatusEvent(Rows.id(2), AT, "WP01", Lane.PLANNED, Lane.CLAIMED, true, null, null, null, null, Actor.NONE);

    Optional<StreamEvent> event = projection.project(new Change(MISSION, new LineKind.Status(forced), CURSOR));

    assertThat(event.orElseThrow()).isInstanceOfSatisfying(StreamEvent.StatusTransition.class, transition -> assertThat(transition.force()).isTrue());
  }

  @Test
  void aSourceLaneThatIsNotADisplayLaneIsServedAsNull() {
    Optional<StreamEvent> event = projection.project(status("WP01", Lane.GENESIS, Lane.PLANNED, AT, Actor.NONE, Rows.id(2)));

    assertThat(event.orElseThrow()).isInstanceOfSatisfying(StreamEvent.StatusTransition.class, transition -> {
      assertThat(transition.fromStatusLane()).isNull();
      assertThat(transition.toStatusLane()).isEqualTo("planned");
    });
  }

  @ParameterizedTest
  @ValueSource(strings = {"WP1", "wp01", "WP01a", "WP-1", "", " WP01", "WP01\n", "TASK01", "WP0x"})
  void aWorkPackageIdThatDoesNotMatchTheContractDropsTheRowWithoutADiagnostic(String wpId) {
    assertThat(projection.project(status(wpId, Lane.CLAIMED, AT))).isEmpty();
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aLongWorkPackageIdIsAcceptedUpToTheBoundAndRefusedBeyondIt() {
    String atBound = "WP" + "1".repeat(62);
    String beyond = "WP" + "1".repeat(63);

    assertThat(projection.project(status(atBound, Lane.CLAIMED, AT))).isPresent();
    assertThat(diagnostics).isEmpty();
    assertRefusedWithOneDiagnostic(projection.project(status(beyond, Lane.CLAIMED, AT)));
  }

  @ParameterizedTest
  @ValueSource(strings = {"GENESIS", "UNINITIALIZED"})
  void aTransitionToANonDisplayLaneDropsTheRowWithoutADiagnostic(String lane) {
    assertThat(projection.project(status("WP01", Lane.valueOf(lane), AT))).isEmpty();
    assertThat(diagnostics).isEmpty();
  }

  @ParameterizedTest
  @ValueSource(strings = {"yesterday", "2026-09-01T10:00:00", "2026-09-01", ""})
  void anInstantThatIsNotAnInstantWithAnOffsetRefusesTheRow(String at) {
    assertRefusedWithOneDiagnostic(projection.project(status("WP01", Lane.CLAIMED, at)));
  }

  @Test
  void aStrictEventIdThatCarriesASecretRefusesTheRow() {
    assertRefusedWithOneDiagnostic(projection.project(status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, Actor.NONE, TOKEN)));
  }

  @Test
  void anEventIdBeyondTheContractBoundRefusesTheRow() {
    assertRefusedWithOneDiagnostic(projection.project(status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, Actor.NONE, "e".repeat(65))));
    diagnostics.clear();
    assertThat(projection.project(status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, Actor.NONE, "e".repeat(64)))).isPresent();
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aMissionIdThatTheLeakClassesFlagRefusesTheRow() {
    EventProjection flagging = new EventProjection(flagging(Rows.ALPHA_ID), diagnostics::add);

    assertThat(flagging.project(status("WP01", Lane.CLAIMED, AT))).isEmpty();
    assertThat(flagging.project(lifecycle(Rows.id(1), AT))).isEmpty();
    assertThat(diagnostics).hasSize(2).allSatisfy(diagnostic -> assertThat(diagnostic).isEqualTo(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, MID8, null)));
  }

  @Test
  void aHandleShapedLikeASecretIsServedAsNullAndTheEventIsKept() {
    // each handle is strict-projected and nullable: a token-shaped one is dropped, not the event (pre-merge fold J8)
    Optional<StreamEvent> event = projection.project(status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, new Actor(TOKEN, "implementer", TOKEN), Rows.id(2)));

    assertThat(event.orElseThrow()).isInstanceOfSatisfying(StreamEvent.StatusTransition.class, transition -> assertThat(transition.actor()).isEqualTo(new StreamEvent.ActorHandles(null, "implementer", null)));
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aRoleThatIsASecretIsServedAsNull() {
    Optional<StreamEvent> event = projection.project(status("WP01", Lane.PLANNED, Lane.CLAIMED, AT, new Actor("claude", TOKEN, "p"), Rows.id(2)));

    assertThat(event.orElseThrow()).isInstanceOfSatisfying(StreamEvent.StatusTransition.class, transition -> assertThat(transition.actor()).isEqualTo(new StreamEvent.ActorHandles("claude", null, "p")));
  }

  @Test
  void theRawLedgerMembersNeverReachTheEvent() {
    StatusEvent raw = new StatusEvent(Rows.id(2), AT, "WP01", Lane.PLANNED, Lane.CLAIMED, false, "CANARYREF", "CANARYWHY", "CANARYSRC", "CANARYAGENT", Actor.NONE);

    Optional<StreamEvent> event = projection.project(new Change(MISSION, new LineKind.Status(raw), CURSOR));

    assertThat(event.orElseThrow().toString()).doesNotContain("CANARY");
  }

  // ---- lifecycle events --------------------------------------------------------------------------------------------------------

  @Test
  void aLifecycleEventIsProjectedWithItsTypeAndTimestamp() {
    Optional<StreamEvent> event = projection.project(lifecycle(Rows.id(1), AT));

    assertThat(event).contains(new StreamEvent.Lifecycle(Rows.ALPHA_ID, Rows.id(1), "MissionCreated", AT, CURSOR));
    assertThat(event.orElseThrow().resumeCursor()).contains(CURSOR);
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aLifecycleTimestampWithoutAnOffsetRefusesTheRow() {
    assertRefusedWithOneDiagnostic(projection.project(lifecycle(Rows.id(1), "2026-09-01T10:00:00")));
  }

  @Test
  void aLifecycleEventIdThatCarriesASecretRefusesTheRow() {
    assertRefusedWithOneDiagnostic(projection.project(lifecycle(TOKEN, AT)));
  }

  @Test
  void aLifecycleEventIdBeyondTheBoundRefusesTheRow() {
    assertRefusedWithOneDiagnostic(projection.project(lifecycle("e".repeat(65), AT)));
  }

  // ---- truncation --------------------------------------------------------------------------------------------------------------

  @Test
  void aTruncationIsProjectedWithItsWireCauseAndTheResetCursor() {
    Optional<StreamEvent> event = projection.project(new FeedSignal.Truncated(MISSION, FeedSignal.Truncated.Reason.SIZE_SHRINK, 424));

    assertThat(event).contains(new StreamEvent.LogTruncated(Rows.ALPHA_ID, "size_shrink", 424, StreamCursor.start()));
    assertThat(event.orElseThrow().resumeCursor()).as("the reset cursor is data, never an id").isEmpty();
    assertThat(projection.project(new FeedSignal.Truncated(MISSION, FeedSignal.Truncated.Reason.CONTENT_MISMATCH, 1)).orElseThrow())
        .isInstanceOfSatisfying(StreamEvent.LogTruncated.class, truncated -> assertThat(truncated.truncationCause()).isEqualTo("content_mismatch"));
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aTruncationWhoseProjectionIsRefusedWritesOneDiagnosticAndYieldsNoEvent() {
    EventProjection flagging = new EventProjection(flagging(Rows.ALPHA_ID), diagnostics::add);

    Optional<StreamEvent> event = flagging.project(new FeedSignal.Truncated(MISSION, FeedSignal.Truncated.Reason.SIZE_SHRINK, 424));

    assertRefusedWithOneDiagnostic(event);
  }

  /** The real patterns plus a strict host-path class that matches the given text, so the Mission id itself cannot be represented. */
  private static LeakClasses flagging(String text) {
    LeakClasses real = LeakPatternsFile.load();
    List<java.util.regex.Pattern> strict = new ArrayList<>(real.strictHostPaths());
    strict.add(LeakClasses.compile(java.util.regex.Pattern.quote(text)));
    return new LeakClasses(strict, real.humanHostPaths(), real.email(), real.emailAnchored(), real.secrets());
  }
}
