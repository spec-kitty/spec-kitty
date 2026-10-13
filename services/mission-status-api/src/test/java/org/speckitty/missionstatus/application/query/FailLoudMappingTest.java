package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.overview.LifecycleStatus;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;
import org.speckitty.missionstatus.testsupport.Rows;

/** One test per row L1 to L11 at the port leg (AC-4a), plus the projection refusal. */
class FailLoudMappingTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";
  private static final String MID8_ALPHA = Rows.ALPHA_ID.substring(0, 8);
  private static final byte[] NEWLINE = "\n".getBytes(StandardCharsets.UTF_8);

  private static FixtureSpec twoMissions(String alphaLedger) {
    return FixtureSpec.of(
        Fx.mission("alpha", Rows.ALPHA_ID, CREATED, alphaLedger),
        Fx.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Fx.twoMoves("WP01", 20)));
  }

  private static byte[] join(byte[]... parts) {
    java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
    for (byte[] part : parts) {
      out.writeBytes(part);
    }
    return out.toByteArray();
  }

  private static void assertRefusedFromBothRoutes(Fx fx, DiagnosticCode code) {
    for (java.util.function.Supplier<Object> route : List.<java.util.function.Supplier<Object>>of(fx.service::project, () -> fx.service.missions(new PageRequest(null, null)))) {
      assertThatThrownBy(route::get).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
    }
  }

  // ---- L1 and L2 -------------------------------------------------------------------------------------------------------------

  @Test
  void l1AnAbsentLedgerIsAnEmptyDraftAtOffsetZeroWithNoDiagnostic() {
    Fx fx = new Fx(twoMissions(null));

    MissionOverview alpha = find(fx, "alpha");

    assertThat(alpha.wpTotal()).isZero();
    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(alpha.streamCursor()).isEqualTo(StreamCursor.start());
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void l1WithDiscardedAtIsDiscardedNotDraft() {
    String meta = Rows.metaWith(Rows.ALPHA_ID, "alpha", CREATED, "\"discarded_at\":\"2026-09-05T10:00:00+00:00\"");
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, null)));

    assertThat(find(fx, "alpha").lifecycleStatus()).isEqualTo(LifecycleStatus.DISCARDED);
  }

  @ParameterizedTest(name = "L2 via {0} {1}")
  @EnumSource(value = SourceFault.Kind.class, names = {"LEDGER_UNREADABLE", "PATH_REFUSED"})
  void l2AnUnreadableLedgerIsAnEmptyDraftItemPlusOneDiagnostic(SourceFault.Kind kind) {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.STAMP, kind);

    MissionOverview alpha = find(fx, "alpha");

    assertThat(alpha.wpTotal()).isZero();
    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(alpha.statusLaneCounts().values()).allMatch(count -> count == 0);
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_ALPHA, null));
  }

  @Test
  void l2AReadFailureAfterAGoodStampIsTheSameRow() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.LEDGER, SourceFault.Kind.LEDGER_UNREADABLE);

    assertThat(find(fx, "alpha").wpTotal()).isZero();
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNREADABLE, MID8_ALPHA, null));
  }

  @Test
  void l2WithDiscardedAtIsDiscarded() {
    String meta = Rows.metaWith(Rows.ALPHA_ID, "alpha", CREATED, "\"discarded_at\":\"2026-09-05T10:00:00+00:00\"");
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, Fx.twoMoves("WP01", 1))));
    fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);

    assertThat(find(fx, "alpha").lifecycleStatus()).isEqualTo(LifecycleStatus.DISCARDED);
  }

  @Test
  void anUnreadableLedgerIsNotCachedSoARepairIsSeenAtOnce() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.LEDGER_UNREADABLE);
    find(fx, "alpha");
    fx.source.clear("alpha", Op.STAMP);

    assertThat(find(fx, "alpha").wpTotal()).isEqualTo(1);
  }

  // ---- L3a and L3b -----------------------------------------------------------------------------------------------------------

  @Test
  void l3aAndL3bABadTerminatedLineRefusesBothRoutesWithItsLineNumber() {
    String bad = Rows.status(Rows.id(1), Fx.T0, "WP01", "planned", "claimed") + "this is not json\n" + Rows.status(Rows.id(3), Fx.T1, "WP01", "claimed", "in_progress");
    Fx fx = new Fx(twoMissions(bad));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.LEDGER_UNPARSEABLE);

    assertThat(fx.handles.diagnostics()).hasSize(2).allSatisfy(d -> assertThat(d).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, 2)));
  }

  @ParameterizedTest(name = "bad line {0}")
  @ValueSource(strings = {"[1,2,3]\n", "\"text\"\n", "{\"event_id\":\"x\"}\n", "{\"actor\":\"c\",\"at\":\"t\",\"event_id\":\"e\",\"force\":false,\"from_lane\":\"nope\",\"to_lane\":\"claimed\",\"wp_id\":\"WP01\",\"execution_mode\":\"worktree\"}\n"})
  void everyMalformedReasonMapsToTheOneCodeAndNeverServesTheEnumName(String line) {
    Fx fx = new Fx(twoMissions(line));

    assertThatThrownBy(() -> fx.service.missions(new PageRequest(null, null)))
        .isInstanceOfSatisfying(
            MissionStatusUnavailable.class,
            refusal -> {
              assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE);
              assertThat(refusal.getMessage()).doesNotContain("NOT_").doesNotContain("not_");
            });
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, 1));
  }

  @Test
  void aNonUtf8LineHasNoLineNumber() {
    byte[] ledger = join(Rows.status(Rows.id(1), Fx.T0, "WP01", "planned", "claimed").getBytes(StandardCharsets.UTF_8), new byte[] {(byte) 0xFF, (byte) 0xFE}, NEWLINE);
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.ofBytes("alpha", Rows.meta(Rows.ALPHA_ID, "alpha", CREATED).getBytes(StandardCharsets.UTF_8), ledger)));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.LEDGER_UNPARSEABLE);

    assertThat(fx.handles.diagnostics()).allSatisfy(d -> assertThat(d).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, null)));
  }

  @Test
  void aRowWhoseTimestampCannotBeParsedIsRefusedAsAnUnparseableLedger() {
    Fx fx = new Fx(twoMissions(Rows.status(Rows.id(1), "not a time", "WP01", "planned", "claimed")));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  // ---- L4 and L4b ------------------------------------------------------------------------------------------------------------

  @ParameterizedTest(name = "unterminated tail {0}")
  @ValueSource(strings = {"{\"half\":", "{\"actor\":\"claude\"}", "x"})
  void l4AndL4bAnyUnterminatedNonWhitespaceTailRefusesTheRead(String tail) {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1) + tail));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.LEDGER_TORN_TAIL);

    assertThat(fx.handles.diagnostics()).allSatisfy(d -> assertThat(d).isEqualTo(new Diagnostic(DiagnosticCode.LEDGER_TORN_TAIL, MID8_ALPHA, null)));
  }

  @Test
  void aBadTerminatedLineIsReportedBeforeALaterTornTail() {
    Fx fx = new Fx(twoMissions("garbage line\n{\"half\":"));

    assertThatThrownBy(() -> fx.service.missions(new PageRequest(null, null)))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE));
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_ALPHA, 1));
  }

  @Test
  void anUnparseableTornTailAloneIsTheTornTailRow() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1) + "{\"half\":"));

    assertThatThrownBy(() -> fx.service.missions(new PageRequest(null, null)))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
  }

  @Test
  void aWhitespaceOnlyTailIsNotATornTailAndTheCursorDescribesTheTerminatedPrefix() {
    String terminated = Fx.twoMoves("WP01", 1);
    Fx fx = new Fx(twoMissions(terminated + "   "));

    MissionOverview alpha = find(fx, "alpha");

    assertThat(alpha.wpTotal()).isEqualTo(1);
    assertThat(alpha.streamCursor().offset()).isEqualTo(terminated.getBytes(StandardCharsets.UTF_8).length);
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  // ---- L6 and L9 -------------------------------------------------------------------------------------------------------------

  @Test
  void l6AMissionThatVanishesBetweenEnumerationAndReadIsOmittedAndTheCountAgrees() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.META, SourceFault.Kind.VANISHED);

    var page = fx.service.missions(new PageRequest(null, null));

    assertThat(page.items()).extracting(MissionOverview::slug).containsExactly("beta");
    assertThat(page.missionCount()).isEqualTo(1);
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_VANISHED, Diagnostic.NONE, null));
    assertThat(fx.service.project().missionCount()).isEqualTo(1);
  }

  @Test
  void l6AVanishAfterTheMetaWasReadCarriesTheMid8() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.VANISHED);

    fx.service.missions(new PageRequest(null, null));

    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.MISSION_VANISHED, MID8_ALPHA, null));
  }

  @Test
  void l9ASymbolicLinkRefusalOmitsTheMissionWithPathRefusedAndNoMid8() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.META, SourceFault.Kind.PATH_REFUSED);

    var page = fx.service.missions(new PageRequest(null, null));

    assertThat(page.items()).extracting(MissionOverview::slug).containsExactly("beta");
    assertThat(page.missionCount()).isEqualTo(1);
    assertThat(fx.handles.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.PATH_REFUSED, Diagnostic.NONE, null));
  }

  // ---- L7 --------------------------------------------------------------------------------------------------------------------

  @ParameterizedTest(name = "unusable meta: {0}")
  @ValueSource(strings = {"{not json", "[1,2]", "", "{\"mission_id\":\"01J01000000000000000000001\"}", "{\"mission_id\":\"short\",\"slug\":\"a\",\"target_branch\":\"main\",\"created_at\":\"2026-09-02T10:00:00+00:00\"}"})
  void l7AnUnusableMetaJsonRefusesBothRoutesWithOneCodeAndNoMid8(String meta) {
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, null)));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.META_UNPARSEABLE);

    assertThat(fx.handles.diagnostics()).allSatisfy(d -> assertThat(d).isEqualTo(new Diagnostic(DiagnosticCode.META_UNPARSEABLE, Diagnostic.NONE, null)));
  }

  @Test
  void l7NonUtf8MetaAndAnOsLevelReadFailureHaveTheSameObservable() {
    FixtureSpec spec = FixtureSpec.of(FixtureSpec.Mission.ofBytes("alpha", new byte[] {'{', (byte) 0xC3, (byte) 0x28, '}'}, null));
    Fx fx = new Fx(spec);
    assertRefusedFromBothRoutes(fx, DiagnosticCode.META_UNPARSEABLE);

    Fx os = new Fx(twoMissions(null));
    os.source.inject("alpha", Op.META, SourceFault.Kind.META_UNPARSEABLE);
    assertRefusedFromBothRoutes(os, DiagnosticCode.META_UNPARSEABLE);
  }

  @Test
  void l7ACreatedAtThatIsNotAnInstantIsAnUnusableMeta() {
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, "yesterday", null)));

    assertRefusedFromBothRoutes(fx, DiagnosticCode.META_UNPARSEABLE);
  }

  // ---- L11 -------------------------------------------------------------------------------------------------------------------

  @Test
  void l11AnUnlistableSpecsDirectoryRefusesBothRoutes() {
    Fx fx = new Fx(twoMissions(null));
    fx.source.failListing(SourceFault.Kind.DIR_UNREADABLE);

    assertRefusedFromBothRoutes(fx, DiagnosticCode.MISSION_DIR_UNREADABLE);

    assertThat(fx.handles.diagnostics()).allSatisfy(d -> assertThat(d).isEqualTo(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null)));
  }

  @Test
  void l11AnUnreadableMissionDirectoryRefusesBothRoutes() {
    Fx fx = new Fx(twoMissions(null));
    fx.source.inject("alpha", Op.META, SourceFault.Kind.DIR_UNREADABLE);

    assertRefusedFromBothRoutes(fx, DiagnosticCode.MISSION_DIR_UNREADABLE);
  }

  @Test
  void l11AnUnreadableDirectoryFoundWhileStampingRefusesWithTheMid8() {
    Fx fx = new Fx(twoMissions(Fx.twoMoves("WP01", 1)));
    fx.source.inject("alpha", Op.STAMP, SourceFault.Kind.DIR_UNREADABLE);

    assertRefusedFromBothRoutes(fx, DiagnosticCode.MISSION_DIR_UNREADABLE);

    assertThat(fx.handles.diagnostics()).allSatisfy(d -> assertThat(d.mid8()).isEqualTo(MID8_ALPHA));
  }

  @Test
  void aProjectInputsFailureRefusesTheHeaderOnly() {
    Fx fx = new Fx(twoMissions(null));
    fx.source.failProject(SourceFault.Kind.DIR_UNREADABLE);

    assertThatThrownBy(fx.service::project)
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.MISSION_DIR_UNREADABLE));
    assertThat(fx.service.missions(new PageRequest(null, null)).items()).hasSize(2);
  }

  @Test
  void aKindThatCannotHappenAtMetaTimeStillRefusesInsteadOfLeaking() {
    Fx fx = new Fx(twoMissions(null));
    fx.source.inject("alpha", Op.META, SourceFault.Kind.LEDGER_UNREADABLE);

    assertRefusedFromBothRoutes(fx, DiagnosticCode.MISSION_DIR_UNREADABLE);
  }

  private static MissionOverview find(Fx fx, String slug) {
    MissionStatusQuery query = fx.service;
    return query.missions(new PageRequest(null, null)).items().stream().filter(item -> item.slug().equals(slug)).findFirst().orElseThrow();
  }
}
