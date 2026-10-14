package org.speckitty.missionstatus.application.query.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.StreamFx.ALPHA;
import static org.speckitty.missionstatus.application.query.StreamFx.BETA;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.Fx;
import org.speckitty.missionstatus.application.query.StreamFx;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;
import org.speckitty.missionstatus.testsupport.Rows;

/** The shared poller: forwarding, the unterminated tail, truncation, the fault rows S3 to S6, discovery, overflow and disconnect. */
class ChangeFeedTest {

  private static final String MID8_ALPHA = Rows.ALPHA_ID.substring(0, 8);
  private static final String MID8_BETA = Rows.BETA_ID.substring(0, 8);

  private static Subscription scoped(Fx fx) {
    return fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty());
  }

  private static Subscription unscoped(Fx fx) {
    return fx.service.subscribe(StreamScope.all(), Optional.empty());
  }

  private static void append(Fx fx, String mission, String text) {
    fx.source.appendLedger(mission, text);
    fx.executor.tick();
  }

  // ---- forwarding and dropping -----------------------------------------------------------------------------------------------

  @Test
  void ac3aAnAppendedStatusTransitionIsOneChangeWithTheCursorAfterIt() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      String row = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
      append(fx, "alpha", row);

      var changes = StreamFx.changes(StreamFx.drain(subscription));

      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(4));
      assertThat(changes.getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(StreamFx.alphaHistory() + row, 4));
      assertThat(changes.getFirst().missionId()).isEqualTo(ALPHA);
    }
  }

  @Test
  void ac3bAnnotationAndUnknownRowsAreDroppedAndTheStreamStaysOpen() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      String dropped = Rows.annotation(Rows.id(4), Fx.T2, "WP01");
      String unknownType = Rows.unknownType(Rows.id(5));
      String unknownKind = "{\"event_id\":\"x\",\"kind\":\"never-heard-of\"}\n";
      String unknownLane = Rows.status(Rows.id(6), Fx.T2, "WP01", "in_progress", "nope");
      append(fx, "alpha", dropped);
      append(fx, "alpha", unknownType);
      append(fx, "alpha", unknownKind);
      append(fx, "alpha", unknownLane);

      assertThat(StreamFx.drain(subscription)).as("no event, no close: the stream stays open").isEmpty();

      String row = Rows.status(Rows.id(7), Fx.T2, "WP01", "in_progress", "for_review");
      append(fx, "alpha", row);

      var changes = StreamFx.changes(StreamFx.drain(subscription));
      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(7));
      assertThat(changes.getFirst().cursor()).as("the offset advanced past every dropped row").isEqualTo(StreamFx.cursorAfter(StreamFx.alphaHistory() + dropped + unknownType + unknownKind + unknownLane + row, 8));
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void aLifecycleRowIsForwardedAndLaterRowsStillCarryTheRightCursorAfterADroppedRow() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      String dropped = Rows.annotation(Rows.id(4), Fx.T2, "WP01");
      String lifecycle = Rows.lifecycle(Rows.id(5), "PlanCompleted", Fx.T2);
      append(fx, "alpha", dropped + lifecycle);

      var changes = StreamFx.changes(StreamFx.drain(subscription));

      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(5));
      assertThat(changes.getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(StreamFx.alphaHistory() + dropped + lifecycle, 5));
    }
  }

  // ---- the unterminated tail -------------------------------------------------------------------------------------------------

  @Test
  void ac3lAnUnterminatedTailIsANonEventAndItsCompletionIsExactlyOneEvent() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      String row = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
      String half = row.substring(0, row.length() / 2);
      append(fx, "alpha", half);
      assertThat(StreamFx.drain(subscription)).isEmpty();

      append(fx, "alpha", row.substring(half.length()));

      var changes = StreamFx.changes(StreamFx.drain(subscription));
      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(4));
      assertThat(changes.getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(StreamFx.alphaHistory() + row, 4));
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void ac3lAFragmentThatIsAlreadyThereAtConnectIsNeverParsedAlone() {
    String row = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
    String half = row.substring(0, 30);
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, StreamFx.alphaHistory() + half)));
    try (Subscription scoped = scoped(fx);
        Subscription unscoped = unscoped(fx)) {
      fx.executor.tick();
      assertThat(StreamFx.drain(scoped)).isEmpty();
      assertThat(StreamFx.drain(unscoped)).isEmpty();

      append(fx, "alpha", row.substring(30));

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(scoped)))).containsExactly(Rows.id(4));
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(unscoped)))).containsExactly(Rows.id(4));
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  // ---- truncation (L5) -------------------------------------------------------------------------------------------------------

  @Test
  void ac3cAShrunkLogYieldsTruncatedAndTheStreamResumesFromTheNewBaseline() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      long before = StreamFx.alphaHistory().getBytes(StandardCharsets.UTF_8).length;
      String shorter = Rows.status(Rows.id(2), Fx.T0, "WP01", "planned", "claimed");
      fx.source.replaceLedger("alpha", shorter.getBytes(StandardCharsets.UTF_8));
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Truncated(ALPHA, StreamSignal.Truncated.Reason.SIZE_SHRINK, before));

      append(fx, "alpha", Rows.status(Rows.id(9), Fx.T2, "WP01", "claimed", "in_progress"));
      var changes = StreamFx.changes(StreamFx.drain(subscription));
      assertThat(StreamFx.eventIds(changes)).as("rows after the re-baseline are delivered, the rewritten history is not").containsExactly(Rows.id(9));
      assertThat(changes.getFirst().cursor().offset()).isGreaterThan(shorter.getBytes(StandardCharsets.UTF_8).length);
    }
  }

  @Test
  void ac3cASameLengthRewriteOfTheLastLineIsAContentMismatch() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      String original = StreamFx.alphaHistory();
      String rewritten = original.replace(Rows.id(3), Rows.id(9));
      fx.source.replaceLedger("alpha", rewritten.getBytes(StandardCharsets.UTF_8));
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription))
          .containsExactly(new StreamSignal.Truncated(ALPHA, StreamSignal.Truncated.Reason.CONTENT_MISMATCH, original.getBytes(StandardCharsets.UTF_8).length));
    }
  }

  @Test
  void aDeletedLedgerWhoseDirectoryRemainsIsTheSameShrink() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx);
        Subscription all = unscoped(fx)) {
      fx.source.deleteLedger("alpha");
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription)).singleElement().isInstanceOf(StreamSignal.Truncated.class);
      assertThat(StreamFx.drain(all)).singleElement().isInstanceOf(StreamSignal.Truncated.class);
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  // ---- S3 -------------------------------------------------------------------------------------------------------------------

  @Test
  void s3ScopedAnUnreadableLedgerClosesTheStreamWithOneDiagnostic() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);
      fx.executor.tick();
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Closed(Closure.LEDGER_UNREADABLE));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_ALPHA, null));
    assertThat(fx.service.feed().subscriberCount()).isZero();
  }

  @Test
  void s3UnscopedDropsOnlyThatMissionAndKeepsTheConnection() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);
      fx.executor.tick();
      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Dropped(MID8_ALPHA));

      append(fx, "beta", Rows.status(Rows.id(51), Fx.T2, "WP01", "claimed", "in_progress"));
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).containsExactly(Rows.id(51));
      StreamFx.assertIdle(subscription);

      fx.source.clear("alpha", Op.STAMP);
      append(fx, "alpha", Rows.status(Rows.id(8), Fx.T2, "WP01", "in_progress", "for_review"));
      assertThat(StreamFx.drain(subscription)).as("not re-watched on this connection").isEmpty();
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_ALPHA, null));
  }

  @Test
  void aMissionDroppedByOneConnectionIsWatchedAgainByAReconnectAndNotByTheOldConnection() {
    Fx fx = new Fx(StreamFx.twoMissions());
    Subscription old = unscoped(fx);
    fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);
    fx.executor.tick();
    assertThat(StreamFx.drain(old)).containsExactly(new StreamSignal.Dropped(MID8_ALPHA));
    fx.source.clear("alpha", Op.STAMP);

    try (Subscription fresh = unscoped(fx)) {
      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(fresh)))).containsExactly(Rows.id(4));
      assertThat(StreamFx.drain(old)).as("the old connection dropped it for good").isEmpty();
    }
    old.close();
  }

  @Test
  void anUnexpectedFailureWhileReadingIsTreatedAsAnUnreadableLedger() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      fx.source.injectUnexpected("alpha", Op.WINDOW);
      fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Closed(Closure.LEDGER_UNREADABLE));
    }
    assertThat(fx.handles.diagnostics()).hasSize(1);
  }

  // ---- S4 -------------------------------------------------------------------------------------------------------------------

  @Test
  void s4ScopedABadLineClosesAfterDeliveringTheRowsBeforeIt() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review") + "not json at all\n" + Rows.status(Rows.id(6), Fx.T2, "WP01", "for_review", "approved"));
      fx.executor.tick();

      List<StreamSignal> signals = StreamFx.drain(subscription);

      assertThat(StreamFx.eventIds(StreamFx.changes(signals))).containsExactly(Rows.id(4));
      assertThat(signals.getLast()).isEqualTo(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, null));
  }

  @Test
  void s4EachKindOfUnparseableLineIsTheSameRow() {
    for (String bad : List.of("[1,2,3]\n", "\n", "not json at all\n", "\"text\"\n")) {
      Fx fx = new Fx(StreamFx.twoMissions());
      try (Subscription subscription = scoped(fx)) {
        append(fx, "alpha", bad);
        assertThat(StreamFx.drain(subscription)).as(bad).containsExactly(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
      }
    }
  }

  @Test
  void s4AnObjectThatIsNoUsableRowIsSkippedOnEveryPathAndNeverClosesOrDrops() {
    for (String unusable : List.of("{\"actor\":\"c\"}\n", Rows.status(Rows.id(9), Fx.T2, "WP01", "in_progress", "nope"), "{\"event_id\":\"x\",\"kind\":\"never-heard-of\"}\n")) {
      String good = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
      String ledger = StreamFx.alphaHistory() + unusable + good;
      Fx fx = new Fx(StreamFx.twoMissions());
      try (Subscription scoped = scoped(fx);
          Subscription unscoped = unscoped(fx);
          Subscription resumed = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(StreamFx.alphaHistory(), 3)))) {
        append(fx, "alpha", unusable + good);

        for (Subscription subscription : List.of(scoped, unscoped, resumed)) {
          List<StreamSignal> signals = StreamFx.drain(subscription);
          assertThat(signals).as(unusable).allSatisfy(signal -> assertThat(signal).isInstanceOf(StreamSignal.Forwarded.class));
          assertThat(StreamFx.eventIds(StreamFx.changes(signals))).as(unusable).containsExactly(Rows.id(4));
          assertThat(StreamFx.changes(signals).getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(ledger, 5));
        }
      }
      assertThat(fx.handles.diagnostics()).as(unusable).isEmpty();

      Fx resuming = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));
      try (Subscription subscription = resuming.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(ledger, 3)))) {
        List<StreamSignal> signals = StreamFx.drain(subscription);
        assertThat(signals).as("resume over " + unusable).allSatisfy(signal -> assertThat(signal).isInstanceOf(StreamSignal.Forwarded.class));
        assertThat(StreamFx.eventIds(StreamFx.changes(signals))).containsExactly(Rows.id(4));
        assertThat(StreamFx.changes(signals).getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(ledger, 5));
      }
      assertThat(resuming.handles.diagnostics()).isEmpty();
    }
  }

  @Test
  void s4UnscopedDropsTheMissionOnceAndDeliversTheOthers() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      append(fx, "alpha", "[1]\n");
      append(fx, "alpha", Rows.status(Rows.id(7), Fx.T2, "WP01", "in_progress", "for_review"));
      append(fx, "beta", Rows.status(Rows.id(51), Fx.T2, "WP01", "claimed", "in_progress"));

      List<StreamSignal> signals = StreamFx.drain(subscription);

      assertThat(signals.getFirst()).isEqualTo(new StreamSignal.Dropped(MID8_ALPHA));
      assertThat(StreamFx.eventIds(StreamFx.changes(signals))).containsExactly(Rows.id(51));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, null));
  }

  // ---- S5 -------------------------------------------------------------------------------------------------------------------

  @Test
  void s5ScopedAVanishedMissionClosesTheStreamWithOneDiagnostic() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      fx.source.removeMission("alpha");
      fx.executor.tick();

      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Closed(Closure.MISSION_VANISHED));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_VANISHED, MID8_ALPHA, null));
  }

  @Test
  void s5AHundredUnscopedSubscribersSeeOneVanishAndOneDiagnosticLine() {
    Fx fx = new Fx(StreamFx.twoMissions());
    List<Subscription> subscriptions = new ArrayList<>();
    for (int i = 0; i < 100; i++) {
      subscriptions.add(unscoped(fx));
    }

    fx.source.removeMission("beta");
    fx.executor.tick();

    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_VANISHED, MID8_BETA, null));
    for (Subscription subscription : subscriptions) {
      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Dropped(MID8_BETA));
      subscription.close();
    }
  }

  // ---- S6 and discovery ------------------------------------------------------------------------------------------------------

  @Test
  void s6AnUnlistableSpecsDirectoryWritesOneDiagnosticPerTransitionIntoFailureAndDropsNothing() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.source.failListing(SourceFault.Kind.DIR_UNREADABLE);
      for (int i = 0; i < 3; i++) {
        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();
      }
      assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));

      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).as("nothing was dropped").containsExactly(Rows.id(4));

      fx.source.failListing(null);
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();
      fx.source.failListing(SourceFault.Kind.DIR_UNREADABLE);
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();

      assertThat(fx.handles.diagnostics()).as("a new line after a successful listing and a new failure").hasSize(2);
    }
  }

  @Test
  void ac3mAMissionThatAppearsAfterConnectDeliversAllItsRowsWhicheverFileCameFirst() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      String row = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
      fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, row));
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();

      var changes = StreamFx.changes(StreamFx.drain(subscription));
      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(60));
      assertThat(changes.getFirst().missionId().value()).isEqualTo(Rows.GAMMA_ID);

      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();
      assertThat(StreamFx.drain(subscription)).as("one event, not one per listing").isEmpty();
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void ac3mASecondUnscopedSubscriberConnectingBeforeTheRelistLosesNoRowOfTheFirst() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription first = unscoped(fx)) {
      String before = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
      fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, before));
      try (Subscription second = unscoped(fx)) {
        String after = Rows.status(Rows.id(61), Fx.T2, "WP01", "claimed", "in_progress");
        fx.source.appendLedger("gamma", after);
        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();

        var firstChanges = StreamFx.changes(StreamFx.drain(first));
        var secondChanges = StreamFx.changes(StreamFx.drain(second));
        assertThat(StreamFx.eventIds(firstChanges)).as("the first subscriber was there when both rows were written").containsExactly(Rows.id(60), Rows.id(61));
        assertThat(StreamFx.eventIds(secondChanges)).as("the second one gets only what was written after it connected").containsExactly(Rows.id(61));
        assertThat(secondChanges.getFirst().cursor()).isEqualTo(StreamFx.cursorAfter(before + after, 2));

        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();
        assertThat(StreamFx.drain(first)).isEmpty();
        assertThat(StreamFx.drain(second)).isEmpty();
      }
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void aSecondUnscopedSubscriberKeepsItsPerMissionFloorsApartAndAScopedStreamIsUnaffected() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription first = unscoped(fx);
        Subscription scopedAlpha = scoped(fx)) {
      String gamma = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
      fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, gamma));
      try (Subscription second = unscoped(fx)) {
        fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();

        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(first)))).containsExactlyInAnyOrder(Rows.id(60), Rows.id(4));
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(second)))).as("alpha's new row, not gamma's history").containsExactly(Rows.id(4));
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(scopedAlpha)))).containsExactly(Rows.id(4));
      }
    }
  }

  @Test
  void aSecondUnscopedSubscriberFindingAnUndiscoveredMissionUnreadableSkipsItWithOneDiagnosticAndKeepsTheFirstSubscribersView() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription first = unscoped(fx)) {
      fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed")));
      fx.source.inject("gamma", Op.WINDOW, SourceFault.Kind.LEDGER_UNREADABLE);

      try (Subscription second = unscoped(fx)) {
        assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, Rows.GAMMA_ID.substring(0, 8), null));
        append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(first)))).containsExactly(Rows.id(4));
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(second)))).containsExactly(Rows.id(4));
      }
    }
  }

  @Test
  void ac3mADirectoryNeverListedBecauseItHasNoMetaYieldsNothing() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();
      assertThat(StreamFx.drain(subscription)).isEmpty();
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void aNewMissionWhoseMetaCannotBeReadIsReportedOnceAndWatchedOnceItBecomesReadable() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      String row = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
      fx.source.addMission(FixtureSpec.Mission.of("gamma", "{broken", row));
      for (int i = 0; i < 3; i++) {
        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();
      }
      assertThat(StreamFx.drain(subscription)).isEmpty();
      assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE, null));

      fx.source.replaceMeta("gamma", Rows.meta(Rows.GAMMA_ID, "gamma", StreamFx.CREATED).getBytes(StandardCharsets.UTF_8));
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).containsExactly(Rows.id(60));
    }
  }

  @Test
  void aStrayExceptionWhileDiscoveringOrConnectingNeitherSilencesTheTickNorLeaksAWatch() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed")));
    fx.source.injectUnexpected("gamma", Op.META);

    assertThatThrownBy(() -> unscoped(fx)).isInstanceOf(IllegalStateException.class);
    assertThat(fx.service.feed().watchCount()).as("the watches of the refused connect are collected").isZero();

    Fx running = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(running)) {
      running.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, null));
      running.source.injectUnexpected("gamma", Op.META);
      // Listed after gamma: discovered in the same listing, so a stray failure is contained to the Mission that threw.
      running.source.addMission(Fx.mission("zeta", "01J04000000000000000000004", StreamFx.CREATED, Rows.status(Rows.id(61), Fx.T2, "WP01", "planned", "claimed")));
      for (int listing = 0; listing < 2; listing++) {
        running.clock.advance(Duration.ofSeconds(2));
        running.executor.tick();
      }

      append(running, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).as("the feed still ticks").containsExactly(Rows.id(61), Rows.id(4));
      assertThat(running.handles.diagnostics()).as("reported once over two listings").containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
    }
  }

  @Test
  void aStrayExceptionThatEscapesATickStepIsReportedAndTheNextTickStillDelivers() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.clock.advance(Duration.ofSeconds(2));
      fx.clock.failNextRead(new IllegalStateException("stray"));
      fx.executor.tick();

      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).as("the feed still ticks").containsExactly(Rows.id(4));
      assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
    }
  }

  @Test
  void aListingBeforeTheIntervalHasPassedIsNotRepeated() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.source.resetCalls();
      fx.executor.tick();
      fx.executor.tick();
      assertThat(fx.source.calls("listMissions")).isZero();
      fx.clock.advance(Duration.ofSeconds(1));
      fx.executor.tick();
      assertThat(fx.source.calls("listMissions")).isEqualTo(1);
      StreamFx.assertIdle(subscription);
    }
  }

  // ---- overflow (E-12) -------------------------------------------------------------------------------------------------------

  @Test
  void e12ASubscriberThatNeverReadsIsClosedAsSlowAfterItsQueueFillsAndOthersAreUnaffected() {
    Fx fx = new Fx(StreamFx.twoMissions(), StreamSettings.defaults().withQueueCapacity(2));
    try (Subscription slow = scoped(fx);
        Subscription healthy = scoped(fx)) {
      List<String> seen = new ArrayList<>();
      for (int i = 4; i <= 6; i++) {
        append(fx, "alpha", Rows.status(Rows.id(i), Fx.T2, "WP0" + i, "planned", "claimed"));
        seen.addAll(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(healthy))));
      }

      assertThat(seen).as("nothing is dropped for the healthy one").containsExactly(Rows.id(4), Rows.id(5), Rows.id(6));
      List<StreamSignal> signals = StreamFx.drain(slow);
      assertThat(StreamFx.eventIds(StreamFx.changes(signals))).as("nothing dropped or reordered before the close").containsExactly(Rows.id(4), Rows.id(5));
      assertThat(signals.getLast()).isEqualTo(new StreamSignal.Closed(Closure.SLOW_CONSUMER));
      assertThat(StreamFx.next(slow)).isEqualTo(new StreamSignal.Closed(Closure.SLOW_CONSUMER));
      assertThat(fx.service.feed().subscriberCount()).isEqualTo(1);
    }
    assertThat(fx.handles.diagnostics()).as("no Mission fault occurred").isEmpty();
  }

  @Test
  void e12AnUnscopedSubscriberWhoseQueueIsFullOfDropsIsAlsoClosed() {
    Fx fx = new Fx(StreamFx.twoMissions(), StreamSettings.defaults().withQueueCapacity(1));
    try (Subscription slow = unscoped(fx)) {
      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
      fx.source.removeMission("beta");
      fx.executor.tick();

      List<StreamSignal> signals = StreamFx.drain(slow);

      assertThat(signals.getLast()).isEqualTo(new StreamSignal.Closed(Closure.SLOW_CONSUMER));
    }
  }

  // ---- disconnect, idle and the shared poller --------------------------------------------------------------------------------

  @Test
  void closingASubscriptionUnsubscribesItAndTheLastOneStopsThePollTick() {
    Fx fx = new Fx(StreamFx.twoMissions());
    Subscription a = scoped(fx);
    Subscription b = unscoped(fx);
    assertThat(fx.service.feed().subscriberCount()).isEqualTo(2);
    assertThat(fx.executor.liveTasks()).isEqualTo(1);

    a.close();
    a.close();
    assertThat(fx.service.feed().subscriberCount()).isEqualTo(1);
    b.close();

    assertThat(fx.service.feed().subscriberCount()).isZero();
    assertThat(fx.service.feed().watchCount()).isZero();
    assertThat(fx.executor.liveTasks()).isZero();
  }

  @Test
  void aClosedSubscriptionCannotBeReadFrom() {
    Fx fx = new Fx(StreamFx.twoMissions());
    Subscription subscription = scoped(fx);
    subscription.close();

    org.assertj.core.api.Assertions.assertThatThrownBy(() -> subscription.next(Duration.ZERO)).isInstanceOf(IllegalStateException.class);
  }

  @Test
  void nextWaitsForTheDurationAndThenReportsIdle() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      assertThat(subscription.next(Duration.ofMillis(20))).isInstanceOf(StreamSignal.Idle.class);
    }
  }

  @Test
  void nextWakesWhenASignalArrivesFromAnotherThread() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = scoped(fx)) {
      Thread producer =
          Thread.ofVirtual()
              .unstarted(
                  () -> {
                    fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
                    fx.executor.tick();
                  });
      producer.start();

      StreamSignal signal = subscription.next(Duration.ofSeconds(10));

      assertThat(signal).isInstanceOf(StreamSignal.Forwarded.class);
      producer.join();
    }
  }

  @Test
  void nfr004cAHundredConnectionsCauseNoPerConnectionRescanAndNoExtraReduction() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.service.missions(new org.speckitty.missionstatus.application.query.port.in.dto.PageRequest(null, null));
    int reductionsAfterOne = fx.reductions();
    List<Subscription> subscriptions = new ArrayList<>();
    for (int i = 0; i < 100; i++) {
      subscriptions.add(unscoped(fx));
    }
    fx.source.resetCalls();

    fx.executor.tick();

    assertThat(fx.source.calls("stampLedger")).as("one stat per watched Mission per tick, not per connection").isEqualTo(2);
    assertThat(fx.source.calls("readLedgerFrom")).isZero();
    assertThat(fx.reductions()).isEqualTo(reductionsAfterOne);

    fx.source.resetCalls();
    append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
    assertThat(fx.source.calls("readLedgerFrom")).as("one read of the appended bytes however many listen").isEqualTo(1);
    subscriptions.forEach(Subscription::close);
  }

  @Test
  void aSecondScopedSubscriberOfTheSameMissionSharesTheWatch() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription one = scoped(fx);
        Subscription two = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(StreamFx.alphaHistory(), 2)))) {
      assertThat(fx.service.feed().watchCount()).isEqualTo(1);
      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(one)))).containsExactly(Rows.id(4));
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(two)))).as("catch-up row 3 first, then the live row once").containsExactly(Rows.id(3), Rows.id(4));
    }
  }

  @Test
  void aRowThatLandsBetweenThePollAndTheCatchUpReadIsDeliveredOnceNotTwice() {
    Fx fx = new Fx(StreamFx.twoMissions());
    String row = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
    try (Subscription one = scoped(fx)) {
      fx.source.beforeNextWindowRead(() -> fx.source.appendLedger("alpha", row));

      try (Subscription two = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(StreamFx.alphaHistory(), 3)))) {
        fx.executor.tick();

        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(two)))).as("by the catch-up, then not again by the feed").containsExactly(Rows.id(4));
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(one)))).containsExactly(Rows.id(4));
      }
    }
  }

  @Test
  void aScopedSubscriberDoesNotSeeAnotherMissionsRows() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(BETA), Optional.empty())) {
      append(fx, "alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      assertThat(StreamFx.drain(subscription)).isEmpty();
    }
  }

  @Test
  void aTruncationOfOneMissionDoesNotDisturbAnUnscopedSubscribersOthers() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription subscription = unscoped(fx)) {
      fx.source.replaceLedger("alpha", new byte[0]);
      fx.executor.tick();
      append(fx, "beta", Rows.status(Rows.id(51), Fx.T2, "WP01", "claimed", "in_progress"));

      List<StreamSignal> signals = StreamFx.drain(subscription);

      assertThat(signals.getFirst()).isInstanceOf(StreamSignal.Truncated.class);
      assertThat(StreamFx.eventIds(StreamFx.changes(signals))).containsExactly(Rows.id(51));
      assertThat(StreamCursor.start().offset()).isZero();
    }
  }

  // ---- landing folds R-3 and R-4: a scoped connect decides as an unscoped one would ------------------------------------------------

  @Test
  void r3AScopedConnectToAnUndiscoveredMissionLosesNoRowOfAnUnscopedSubscriber() {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription unscoped = unscoped(fx)) {
      String r01 = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
      fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, r01));
      try (Subscription gamma = fx.service.subscribe(StreamScope.mission(new MissionId(Rows.GAMMA_ID)), Optional.empty())) {
        String r02 = Rows.status(Rows.id(61), Fx.T2, "WP01", "claimed", "in_progress");
        fx.source.appendLedger("gamma", r02);
        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();

        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(unscoped)))).as("the unscoped stream was there when both rows were written").containsExactly(Rows.id(60), Rows.id(61));
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(gamma)))).as("the scoped one gets only what was written after it connected").containsExactly(Rows.id(61));

        fx.clock.advance(Duration.ofSeconds(2));
        fx.executor.tick();
        assertThat(StreamFx.drain(unscoped)).isEmpty();
        assertThat(StreamFx.drain(gamma)).isEmpty();
      }
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void r3AScopedConnectToAMissionNobodyElseListensToStillStartsAtTheEnd() {
    Fx fx = new Fx(StreamFx.twoMissions());
    String r01 = Rows.status(Rows.id(60), Fx.T2, "WP01", "planned", "claimed");
    fx.source.addMission(Fx.mission("gamma", Rows.GAMMA_ID, StreamFx.CREATED, r01));
    try (Subscription gamma = fx.service.subscribe(StreamScope.mission(new MissionId(Rows.GAMMA_ID)), Optional.empty())) {
      fx.source.appendLedger("gamma", Rows.status(Rows.id(61), Fx.T2, "WP01", "claimed", "in_progress"));
      fx.executor.tick();

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(gamma)))).containsExactly(Rows.id(61));
    }
  }

  @Test
  void r4AScopedConnectOntoAWatchWhoseConnectTimePollFaultsGetsTheSameStreamAsWithoutACoSubscriber() {
    String bad = "not json at all\n";
    for (boolean coSubscriber : new boolean[] {false, true}) {
      Fx fx = new Fx(StreamFx.twoMissions());
      Subscription first = coSubscriber ? scoped(fx) : null;
      try {
        fx.source.appendLedger("alpha", bad);
        try (Subscription second = scoped(fx)) {
          String row = Rows.status(Rows.id(7), Fx.T2, "WP01", "in_progress", "for_review");
          append(fx, "alpha", row);

          List<StreamSignal> signals = StreamFx.drain(second);
          assertThat(StreamFx.eventIds(StreamFx.changes(signals))).as("co-subscriber: " + coSubscriber).containsExactly(Rows.id(7));
          assertThat(signals).as("co-subscriber: " + coSubscriber).noneMatch(signal -> signal instanceof StreamSignal.Closed);
        }
        if (coSubscriber) {
          assertThat(StreamFx.drain(first).getLast()).as("the co-subscriber that was there when the bad line landed is told").isEqualTo(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
        }
      } finally {
        if (first != null) {
          first.close();
        }
      }
    }
  }
}
