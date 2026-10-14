package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.StreamFx.ALPHA;
import static org.speckitty.missionstatus.application.query.StreamFx.BETA;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
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

/** Every connect-time outcome is decided in the service, before a subscription exists (rows S1, S2, the cursor refusals, AC-3g, AC-3i). */
class SubscribeConnectTest {

  private static final String MID8_ALPHA = Rows.ALPHA_ID.substring(0, 8);
  private static final String MID8_BETA = Rows.BETA_ID.substring(0, 8);
  private static final MissionId UNKNOWN = new MissionId("01JZZZZZZZZZZZZZZZZZZZZZZZ".replace('Z', '9'));

  private static StreamRefused refusal(Fx fx, StreamScope scope, Optional<StreamCursor> cursor) {
    Throwable thrown = org.assertj.core.api.Assertions.catchThrowable(() -> fx.service.subscribe(scope, cursor));
    assertThat(thrown).isInstanceOf(StreamRefused.class);
    return (StreamRefused) thrown;
  }

  // ---- S1 and S2, Mission-scoped ---------------------------------------------------------------------------------------------

  @Test
  void s1APlainlyUnknownMissionIs404WithNoDiagnostic() {
    Fx fx = new Fx(StreamFx.twoMissions());

    StreamRefused refused = refusal(fx, StreamScope.mission(UNKNOWN), Optional.empty());

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.UNKNOWN_MISSION);
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void s1ASymbolicLinkRefusalIs404AndWritesPathRefused() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.META, SourceFault.Kind.PATH_REFUSED);

    StreamRefused refused = refusal(fx, StreamScope.mission(UNKNOWN), Optional.empty());

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.UNKNOWN_MISSION);
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE, null));
  }

  @Test
  void s1AMissionThatVanishedDuringTheScanIsPlainlyUnknown() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.META, SourceFault.Kind.VANISHED);

    assertThat(refusal(fx, StreamScope.mission(BETA), Optional.empty()).kind()).isEqualTo(StreamRefused.Kind.UNKNOWN_MISSION);
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void aKnownMissionIsFoundEvenWhenAnotherMissionHasAnUnusableMeta() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.META, SourceFault.Kind.META_UNPARSEABLE);

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty())) {
      StreamFx.assertIdle(subscription);
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void s2AnUnusableMetaThatCouldBeTheRequestedMissionIs500MetaUnparseable() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.META, SourceFault.Kind.META_UNPARSEABLE);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(UNKNOWN), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.META_UNPARSEABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE, null));
  }

  @Test
  void s2AnUnreadableMissionDirectoryIs500MissionDirUnreadable() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.META, SourceFault.Kind.DIR_UNREADABLE);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(UNKNOWN), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.MISSION_DIR_UNREADABLE));
    assertThat(fx.handles.diagnostics()).hasSize(1);
  }

  @Test
  void s2AnUnlistableSpecsDirectoryIs500MissionDirUnreadable() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.failListing(SourceFault.Kind.DIR_UNREADABLE);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.MISSION_DIR_UNREADABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
  }

  @ParameterizedTest(name = "ledger probe fault {0}")
  @EnumSource(value = SourceFault.Kind.class, names = {"LEDGER_UNREADABLE", "PATH_REFUSED"})
  void s2AnUnreadableLedgerIs500LedgerUnreadableWithTheMid8(SourceFault.Kind kind) {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("alpha", Op.STAMP, kind);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNREADABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_ALPHA, null));
  }

  @Test
  void aLedgerProbeThatFindsTheDirectoryGoneIsPlainlyUnknownAndOneThatCannotStatItIsUnreadable() {
    Fx gone = new Fx(StreamFx.twoMissions());
    gone.source.inject("alpha", Op.STAMP, SourceFault.Kind.VANISHED);
    assertThat(refusal(gone, StreamScope.mission(ALPHA), Optional.empty()).kind()).isEqualTo(StreamRefused.Kind.UNKNOWN_MISSION);

    Fx dir = new Fx(StreamFx.twoMissions());
    dir.source.inject("alpha", Op.STAMP, SourceFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(() -> dir.service.subscribe(StreamScope.mission(ALPHA), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.MISSION_DIR_UNREADABLE));
  }

  @Test
  void aMissionWithNoLedgerOpensNormally() throws Exception {
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, null)));

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty())) {
      StreamFx.assertIdle(subscription);
      fx.source.appendLedger("alpha", Rows.status(Rows.id(1), Fx.T0, "WP01", "planned", "claimed"));
      fx.executor.tick();
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).containsExactly(Rows.id(1));
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  // ---- the cursor refusals ---------------------------------------------------------------------------------------------------

  @Test
  void aCursorWithoutAMissionIsRefused400() {
    Fx fx = new Fx(StreamFx.twoMissions());

    StreamRefused refused = refusal(fx, StreamScope.all(), Optional.of(StreamCursor.start()));

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.CURSOR_WITHOUT_MISSION);
    assertThatThrownBy(() -> fx.service.changesSince(StreamScope.all(), Optional.of(StreamCursor.start()))).isInstanceOf(StreamRefused.class);
  }

  @Test
  void outOfRangeIsRefused409() {
    Fx fx = new Fx(StreamFx.twoMissions());
    long size = StreamFx.alphaHistory().getBytes(StandardCharsets.UTF_8).length;

    StreamRefused refused = refusal(fx, StreamScope.mission(ALPHA), Optional.of(new StreamCursor(size + 1, StreamCursor.start().invariant())));

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.OUT_OF_RANGE);
    assertThat(refused.code()).isEqualTo("out_of_range");
  }

  @Test
  void anOffsetInTheMiddleOfALineIsMisaligned400() {
    Fx fx = new Fx(StreamFx.twoMissions());

    StreamRefused refused = refusal(fx, StreamScope.mission(ALPHA), Optional.of(new StreamCursor(7, StreamCursor.start().invariant())));

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.MISALIGNED);
  }

  @Test
  void aDigestThatDoesNotMatchTheLastLineIsAContentMismatch409() {
    Fx fx = new Fx(StreamFx.twoMissions());
    StreamCursor right = StreamFx.cursorAfter(StreamFx.alphaHistory(), 2);

    StreamRefused refused = refusal(fx, StreamScope.mission(ALPHA), Optional.of(new StreamCursor(right.offset(), StreamCursor.digestOf(new byte[] {1}))));

    assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.CONTENT_MISMATCH);
  }

  @Test
  void aCursorFromAnotherMissionsLogIsAContentMismatch() {
    Fx fx = new Fx(StreamFx.twoMissions());
    StreamCursor alphaPosition = StreamFx.cursorAfter(StreamFx.alphaHistory(), 2);
    StreamCursor betaDigest = StreamFx.cursorAfter(StreamFx.betaHistory(), 1);

    assertThat(refusal(fx, StreamScope.mission(ALPHA), Optional.of(new StreamCursor(alphaPosition.offset(), betaDigest.invariant()))).kind())
        .isEqualTo(StreamRefused.Kind.CONTENT_MISMATCH);
  }

  @Test
  void aNegativeAndAnUnparseableCursorTextAreRefusedBeforeAnyMissionIsLookedAt() {
    assertThat(org.assertj.core.api.Assertions.catchThrowableOfType(StreamRefused.class, () -> org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText.parse("-5:" + "a".repeat(64))).kind())
        .isEqualTo(StreamRefused.Kind.NEGATIVE);
    for (String text : List.of("-5:zz", "nonsense", "5:" + "g".repeat(64), "99999999999999999999:" + "a".repeat(64), "", "5")) {
      assertThat(org.assertj.core.api.Assertions.catchThrowableOfType(StreamRefused.class, () -> org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText.parse(text)).kind())
          .as(text)
          .isEqualTo(StreamRefused.Kind.MISALIGNED);
    }
    assertThat(org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText.parse("0:" + StreamCursor.start().invariant())).isEqualTo(StreamCursor.start());
  }

  // ---- AC-3g and AC-3i, the port leg ----------------------------------------------------------------------------------------

  @Test
  void ac3gAValidCursorDeliversTheForwardedRowsAfterItInOrderWithTheirCursors() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    String history = StreamFx.alphaHistory();

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(history, 1)))) {
      List<StreamSignal> signals = StreamFx.drain(subscription);

      var changes = StreamFx.changes(signals);
      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(2), Rows.id(3));
      assertThat(changes.get(0).resumeCursor().orElseThrow()).isEqualTo(StreamFx.cursorAfter(history, 2));
      assertThat(changes.get(1).resumeCursor().orElseThrow()).isEqualTo(StreamFx.cursorAfter(history, 3));

      fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
      fx.executor.tick();
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).containsExactly(Rows.id(4));
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void aCursorAtTheEndDeliversNothingAndAConnectionWithoutACursorReceivesNoHistory() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    String history = StreamFx.alphaHistory();

    try (Subscription atEnd = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(history, 3)));
        Subscription live = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty())) {
      StreamFx.assertIdle(atEnd);
      StreamFx.assertIdle(live);
    }
  }

  @Test
  void aCursorAtOffsetZeroReplaysTheWholeLogAndAnAnnotationInTheTailIsSkipped() throws Exception {
    String ledger = StreamFx.alphaHistory() + Rows.annotation(Rows.id(4), Fx.T2, "WP01") + Rows.unknownType(Rows.id(5));
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamCursor.start()))) {
      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).containsExactly(Rows.id(1), Rows.id(2), Rows.id(3));
    }
  }

  @Test
  void ac3iRowsAppendedInOneWriteArriveInLogOrderEachWithItsOwnCursor() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    String history = StreamFx.alphaHistory();
    String burst = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review") + Rows.status(Rows.id(5), Fx.T2, "WP02", "planned", "claimed") + Rows.lifecycle(Rows.id(6), "PlanStarted", Fx.T2);

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty())) {
      fx.source.appendLedger("alpha", burst);
      fx.executor.tick();

      var changes = StreamFx.changes(StreamFx.drain(subscription));
      assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(4), Rows.id(5), Rows.id(6));
      assertThat(changes).extracting(c -> c.resumeCursor().orElseThrow()).containsExactly(StreamFx.cursorAfter(history + burst, 4), StreamFx.cursorAfter(history + burst, 5), StreamFx.cursorAfter(history + burst, 6));
    }
  }

  @Test
  void changesSinceReturnsTheRowsAfterTheCursorAndTheCursorToResumeFrom() {
    Fx fx = new Fx(StreamFx.twoMissions());
    String history = StreamFx.alphaHistory();

    StreamBatch batch = fx.service.changesSince(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(history, 1)));

    assertThat(StreamFx.eventIds(batch.events())).containsExactly(Rows.id(2), Rows.id(3));
    assertThat(batch.cursor()).isEqualTo(StreamFx.cursorAfter(history, 3));
  }

  @Test
  void changesSinceWithoutACursorIsEmptyAtTheCurrentTip() {
    Fx fx = new Fx(StreamFx.twoMissions());

    StreamBatch scoped = fx.service.changesSince(StreamScope.mission(ALPHA), Optional.empty());
    StreamBatch unscoped = fx.service.changesSince(StreamScope.all(), Optional.empty());

    assertThat(scoped.events()).isEmpty();
    assertThat(scoped.cursor()).isEqualTo(StreamFx.cursorAfter(StreamFx.alphaHistory(), 3));
    assertThat(unscoped.events()).isEmpty();
    assertThat(unscoped.cursor()).isEqualTo(StreamCursor.start());
  }

  @Test
  void changesSinceRefusesABadLineAfterTheCursorAsAnUnparseableLedger() {
    String ledger = StreamFx.alphaHistory() + "not json\n";
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));

    assertThatThrownBy(() -> fx.service.changesSince(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(ledger, 2))))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, null));
  }

  @Test
  void changesSinceReportsAFaultOfTheLedgerWhileReading() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("alpha", Op.WINDOW, SourceFault.Kind.LEDGER_UNREADABLE);

    assertThatThrownBy(() -> fx.service.changesSince(StreamScope.mission(ALPHA), Optional.of(StreamCursor.start())))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNREADABLE));
    assertThatThrownBy(() -> fx.service.changesSince(StreamScope.mission(ALPHA), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNREADABLE));
  }

  // ---- S4 at connect with a resume, and diagnostics once ---------------------------------------------------------------------

  @Test
  void s4AResumeDeliversTheValidRowsThenClosesAndWritesOneDiagnostic() throws Exception {
    String ledger = StreamFx.alphaHistory() + Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review") + "garbage\n" + Rows.status(Rows.id(6), Fx.T2, "WP01", "for_review", "approved");
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(ledger, 2)))) {
      List<StreamSignal> signals = StreamFx.drain(subscription);

      assertThat(StreamFx.eventIds(StreamFx.changes(signals))).containsExactly(Rows.id(3), Rows.id(4));
      assertThat(signals.getLast()).isEqualTo(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
      assertThat(StreamFx.next(subscription)).as("a closed subscription stays closed").isEqualTo(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, null));
    assertThat(fx.service.feed().subscriberCount()).isZero();
  }

  @Test
  void aBlankLineAfterTheCursorIsAnUnparseableLineOnAStream() throws Exception {
    String ledger = StreamFx.alphaHistory() + "\n";
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));

    try (Subscription subscription = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(StreamFx.cursorAfter(ledger, 3)))) {
      assertThat(StreamFx.drain(subscription)).containsExactly(new StreamSignal.Closed(Closure.LEDGER_UNPARSEABLE));
    }
  }

  @Test
  void connectTimeDiagnosticsAreWrittenOnceByTheServiceAndNotAgainByTheFeed() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("beta", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);
    fx.source.inject("beta", Op.WINDOW, SourceFault.Kind.LEDGER_UNREADABLE);

    try (Subscription subscription = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      fx.executor.tick();
      fx.executor.tick();
      assertThat(StreamFx.drain(subscription)).isEmpty();
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_BETA, null));
  }

  // ---- unscoped connect ------------------------------------------------------------------------------------------------------

  @Test
  void anUnscopedConnectLeavesOutAMissionThatCannotBeReadWritesOneDiagnosticAndStillReturns() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("alpha", Op.META, SourceFault.Kind.META_UNPARSEABLE);

    try (Subscription subscription = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      fx.source.appendLedger("alpha", Rows.status(Rows.id(7), Fx.T2, "WP01", "in_progress", "for_review"));
      fx.source.appendLedger("beta", Rows.status(Rows.id(51), Fx.T2, "WP01", "claimed", "in_progress"));
      fx.executor.tick();

      assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(subscription)))).as("only the readable Mission is watched").containsExactly(Rows.id(51));
    }
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE, null));
  }

  @Test
  void anUnscopedConnectReportsTheRowOfEachKindOfFaultOnce() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("alpha", Op.META, SourceFault.Kind.PATH_REFUSED);
    fx.source.inject("beta", Op.META, SourceFault.Kind.VANISHED);

    fx.service.subscribe(StreamScope.all(), Optional.empty()).close();

    assertThat(fx.handles.diagnostics())
        .containsExactly(new Diagnostic(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE, null), new Diagnostic(DiagnosticCode.MISSION_VANISHED, Diagnostic.NONE, null));
  }

  @Test
  void anUnscopedConnectReportsADirectoryFaultAndALedgerThatVanished() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.inject("alpha", Op.META, SourceFault.Kind.DIR_UNREADABLE);
    fx.source.inject("beta", Op.STAMP, SourceFault.Kind.VANISHED);

    fx.service.subscribe(StreamScope.all(), Optional.empty()).close();

    assertThat(fx.handles.diagnostics())
        .containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null), new Diagnostic(DiagnosticCode.MISSION_VANISHED, MID8_BETA, null));
  }

  @Test
  void anUnscopedConnectWithAnUnlistableSpecsDirectoryIs500AndWritesOneDiagnostic() {
    Fx fx = new Fx(StreamFx.twoMissions());
    fx.source.failListing(SourceFault.Kind.DIR_UNREADABLE);

    assertThatThrownBy(() -> fx.service.subscribe(StreamScope.all(), Optional.empty()))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.MISSION_DIR_UNREADABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null));
    assertThat(fx.service.feed().subscriberCount()).isZero();
  }

  @Test
  void anUnscopedStreamDeliversNoHistoryOfAMissionPresentAtConnect() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());

    try (Subscription subscription = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      StreamFx.assertIdle(subscription);
      fx.executor.tick();
      StreamFx.assertIdle(subscription);
    }
  }

  @Test
  void aRowAppendedBeforeConnectButNotYetPolledIsStillHistory() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    try (Subscription first = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
      fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));

      try (Subscription second = fx.service.subscribe(StreamScope.all(), Optional.empty())) {
        fx.executor.tick();
        assertThat(StreamFx.eventIds(StreamFx.changes(StreamFx.drain(first)))).as("the older subscriber still gets it").containsExactly(Rows.id(4));
        assertThat(StreamFx.drain(second)).as("the new one saw it as history").isEmpty();
      }
    }
  }
}
