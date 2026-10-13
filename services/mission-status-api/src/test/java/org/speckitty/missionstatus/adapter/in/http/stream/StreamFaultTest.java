package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.QUIET;

import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.json.JsonMapper;

/** The stream table S1 to S6 (AC-3j, AC-3k, AC-3l, AC-3m, AC-3n, AC-3o) over the real socket, for both scopes. */
class StreamFaultTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String A1 = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
  private static final String B1 = Rows.status(Rows.id(50), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
  private static final String MID8_A = Rows.ALPHA_ID.substring(0, 8);
  private static final String MID8_B = Rows.BETA_ID.substring(0, 8);

  private StreamRig rig;

  @BeforeEach
  void start() {
    rig = twoMissions();
  }

  @AfterEach
  void stop() {
    rig.close();
  }

  private static StreamRig twoMissions(String... properties) {
    return StreamRig.of(
        FixtureSpec.of(
            PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, A1),
            PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", B1)),
        properties);
  }

  private static String betaRow(int n) {
    return Rows.status(Rows.id(50 + n), "2026-09-01T10:0" + n + ":00Z", "WP0" + n, "planned", "claimed");
  }

  private static String eventId(SseClient.Event event) {
    return JSON.readTree(event.data()).get("eventId").asString();
  }

  private void assertDiagnostics(DiagnosticCode code, String mid8, int count) {
    List<Diagnostic> found = rig.diagnostics(code);
    assertThat(found).as("diagnostics with code " + code.wire()).hasSize(count);
    found.forEach(diagnostic -> assertThat(diagnostic.mid8()).isEqualTo(mid8));
  }

  // ---- S3 / AC-3j ----------------------------------------------------------------------------------------------------------

  @Test
  void ac3jAScopedStreamClosesWhenItsLedgerBecomesUnreadableAndNothingFollows() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.swapLedgerForSymlink("alpha");
      rig.tick();

      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertThat(client.items()).as("no heartbeat or event follows").isEmpty();
      assertDiagnostics(DiagnosticCode.LEDGER_UNREADABLE, MID8_A, 1);
    }
  }

  @Test
  void ac3jAnUnscopedStreamDropsTheMissionKeepsTheConnectionAndStillHeartbeats() {
    rig.close();
    rig = twoMissions("mission-status.stream.heartbeat-interval=PT0.2S");
    try (SseClient client = rig.unscoped()) {
      rig.swapLedgerForSymlink("alpha");
      rig.tick();
      rig.append("beta", betaRow(1));
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(eventId(event)).isEqualTo(Rows.id(51));
      assertThat(client.awaitEnd(Duration.ofMillis(200))).as("the connection stays open").isFalse();
      assertDiagnostics(DiagnosticCode.LEDGER_UNREADABLE, MID8_A, 1);
      assertThat(client.next(BOUND)).as("a heartbeat still arrives").isInstanceOf(SseClient.Comment.class);
    }
  }

  // ---- S4 / AC-3k ----------------------------------------------------------------------------------------------------------

  @Test
  void ac3kANonJsonTerminatedLineClosesAScopedStreamWithOneLedgerUnparseableDiagnostic() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", "this is not json\n");
      rig.tick();

      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertThat(client.items()).isEmpty();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);
    }
  }

  @Test
  void ac3kAJsonArrayLineClosesAScopedStreamToo() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", "[1,2,3]\n");
      rig.tick();

      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);
    }
  }

  @Test
  void ac3kABlankLineIsUnparseableAndClosesAScopedStream() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", "\n");
      rig.tick();

      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);
    }
  }

  @Test
  void ac3kControlAValidRowOnAFreshStreamIsDelivered() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress"));
      rig.tick();
      assertThat(eventId(ValidatedEvents.valid(client.nextEvent(BOUND)))).isEqualTo(Rows.id(2));
      assertThat(rig.diagnostics(DiagnosticCode.LEDGER_UNPARSEABLE)).isEmpty();
    }
  }

  @Test
  void ac3kAResumeDeliversTheValidRowAndThenClosesAtTheBadOne() {
    String valid = Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress");
    rig.append("alpha", valid + "garbage\n");
    try (SseClient client = rig.scopedFrom(Rows.ALPHA_ID, Cursors.after(A1, 1))) {
      assertThat(client.status()).isEqualTo(200);
      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));
      assertThat(eventId(event)).isEqualTo(Rows.id(2));
      assertThat(event.id()).isEqualTo(Cursors.text(A1 + valid, 2));
      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);
    }
  }

  @Test
  void ac3kAnUnscopedStreamDropsOnlyTheFaultyMissionAndKeepsTheConnection() {
    try (SseClient client = rig.unscoped()) {
      rig.append("alpha", "garbage\n");
      rig.tick();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);

      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress"));
      rig.append("beta", betaRow(1));
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));
      assertThat(eventId(event)).isEqualTo(Rows.id(51));
      assertThat(client.next(QUIET)).as("no further event of the faulty Mission").isNull();
      assertThat(client.awaitEnd(Duration.ofMillis(100))).isFalse();
      assertDiagnostics(DiagnosticCode.LEDGER_UNPARSEABLE, MID8_A, 1);
    }
  }

  @Test
  void aRowThatIsAnObjectButNotAUsableRowIsSkippedAndTheStreamStaysOpen() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", "{\"event_id\":\"" + Rows.id(2) + "\",\"wp_id\":\"WP01\",\"from_lane\":\"planned\",\"to_lane\":\"not-a-lane\",\"at\":\"2026-09-01T10:01:00Z\"}\n");
      rig.append("alpha", "{\"to_lane\":\"claimed\"}\n");
      rig.tick();
      assertThat(client.next(QUIET)).isNull();
      assertThat(client.awaitEnd(Duration.ofMillis(100))).isFalse();

      rig.append("alpha", Rows.status(Rows.id(5), "2026-09-01T10:05:00Z", "WP01", "claimed", "in_progress"));
      rig.tick();
      assertThat(eventId(ValidatedEvents.valid(client.nextEvent(BOUND)))).isEqualTo(Rows.id(5));
      assertThat(rig.diagnostics(DiagnosticCode.LEDGER_UNPARSEABLE)).isEmpty();
    }
  }

  // ---- AC-3l: the unterminated tail ----------------------------------------------------------------------------------------

  private static final String ROW = Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress");

  @Test
  void ac3lAScopedStreamLeavesAnUnterminatedTailUntilItsNewlineArrives() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", ROW.substring(0, 40));
      rig.tick();
      assertThat(client.next(QUIET)).as("no event before the newline").isNull();
      assertThat(client.awaitEnd(Duration.ofMillis(100))).as("no close").isFalse();
      assertThat(rig.built.handles().diagnostics()).as("no diagnostic").isEmpty();

      rig.append("alpha", ROW.substring(40));
      rig.tick();
      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.id()).isEqualTo(Cursors.text(A1 + ROW, 2));
      assertThat(client.next(QUIET)).as("exactly one event").isNull();
    }
  }

  @Test
  void ac3lAnUnscopedStreamDoesTheSameAndSendsNoId() {
    try (SseClient client = rig.unscoped()) {
      rig.append("alpha", ROW.substring(0, 40));
      rig.tick();
      assertThat(client.next(QUIET)).isNull();

      rig.append("alpha", ROW.substring(40));
      rig.tick();
      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.id()).isNull();
      assertThat(client.next(QUIET)).isNull();
      assertThat(rig.built.handles().diagnostics()).isEmpty();
    }
  }

  @Test
  void ac3lAStreamOpenedAfterTheHalfWrittenRowNeverParsesTheFragmentAlone() {
    rig.append("alpha", ROW.substring(0, 40));
    try (SseClient scoped = rig.scoped(Rows.ALPHA_ID);
        SseClient unscoped = rig.unscoped()) {
      rig.tick();
      assertThat(scoped.next(QUIET)).isNull();
      assertThat(unscoped.next(QUIET)).isNull();

      rig.append("alpha", ROW.substring(40));
      rig.tick();

      assertThat(ValidatedEvents.valid(scoped.nextEvent(BOUND)).id()).isEqualTo(Cursors.text(A1 + ROW, 2));
      ValidatedEvents.valid(unscoped.nextEvent(BOUND));
      assertThat(scoped.next(QUIET)).isNull();
      assertThat(unscoped.next(QUIET)).isNull();
      assertThat(rig.built.handles().diagnostics()).isEmpty();
    }
  }

  // ---- AC-3m: an appearing Mission ----------------------------------------------------------------------------------------

  private void newMission(String slug, String id, boolean metaFirst, String ledger, boolean writeMeta) throws Exception {
    Path dir = rig.missionDir(slug);
    Files.createDirectories(dir);
    Path meta = dir.resolve("meta.json");
    if (metaFirst && writeMeta) {
      Files.writeString(meta, Rows.meta(id, slug, "2026-09-04T10:00:00+00:00"));
      rig.tick();
    }
    Files.writeString(rig.ledger(slug), ledger);
    if (!metaFirst && writeMeta) {
      rig.tick();
      Files.writeString(meta, Rows.meta(id, slug, "2026-09-04T10:00:00+00:00"));
    }
    rig.tick();
    rig.tick();
  }

  @Test
  void ac3mAMissionThatAppearsIsWatchedWhicheverFileCameFirstAndOneWithoutMetaIsNot() throws Exception {
    try (SseClient client = rig.unscoped()) {
      newMission("gamma", Rows.GAMMA_ID, true, Rows.status(Rows.id(70), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"), true);
      SseClient.Event first = ValidatedEvents.valid(client.nextEvent(BOUND));
      assertThat(eventId(first)).isEqualTo(Rows.id(70));
      assertThat(first.id()).isNull();
      assertThat(client.next(QUIET)).as("exactly one event for (i)").isNull();

      newMission("delta", "01J04000000000000000000004", false, Rows.status(Rows.id(80), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"), true);
      SseClient.Event second = ValidatedEvents.valid(client.nextEvent(BOUND));
      assertThat(eventId(second)).isEqualTo(Rows.id(80));
      assertThat(client.next(QUIET)).as("exactly one event for (ii)").isNull();

      newMission("epsilon", "01J05000000000000000000005", false, Rows.status(Rows.id(90), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"), false);
      assertThat(client.next(QUIET)).as("no event for a directory that never gets a meta.json (iii)").isNull();
      assertThat(rig.built.handles().diagnostics()).as("no diagnostic").isEmpty();
    }
  }

  @Test
  void aMissionThatExistedAtConnectWithHistoryDeliversNoneOfIt() {
    try (SseClient client = rig.unscoped()) {
      rig.tick();
      rig.tick();
      assertThat(client.next(QUIET)).isNull();
    }
  }

  // ---- S1 / S2 / AC-3n: connect time --------------------------------------------------------------------------------------

  @Test
  void ac3nAScopedConnectToAMissionWhoseMetaIsASymlinkIs404AndWritesPathRefused() throws Exception {
    Path meta = rig.missionDir("alpha").resolve("meta.json");
    Path moved = Files.move(meta, meta.resolveSibling("meta.real"));
    Files.createSymbolicLink(meta, moved);
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.status()).isEqualTo(404);
      assertThat(ValidatedEvents.contract().validateStreamRefusal(404, client.body())).isEmpty();
    }
    assertDiagnostics(DiagnosticCode.PATH_REFUSED, "none", 1);
  }

  @Test
  void ac3nAScopedConnectToAnUnreadableLedgerIs500LedgerUnreadableWithNoEvent() {
    rig.swapLedgerForSymlink("alpha");
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.status()).isEqualTo(500);
      assertThat(client.header("Content-Type")).startsWith("application/problem+json");
      String body = client.body();
      assertThat(JSON.readTree(body).get("code").asString()).isEqualTo("ledger_unreadable");
      assertThat(body).doesNotContain(rig.built.root().toString());
      assertThat(client.items()).isEmpty();
    }
    assertDiagnostics(DiagnosticCode.LEDGER_UNREADABLE, MID8_A, 1);
  }

  @Test
  void ac3nAScopedConnectToAMissionWithAMalformedMetaIs500MetaUnparseable() throws Exception {
    Files.writeString(rig.missionDir("alpha").resolve("meta.json"), "{ not json");
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.status()).isEqualTo(500);
      assertThat(JSON.readTree(client.body()).get("code").asString()).isEqualTo("meta_unparseable");
    }
    assertDiagnostics(DiagnosticCode.META_UNPARSEABLE, "none", 1);
  }

  @Test
  void ac3nControlAMissionWithNoLedgerOpensNormally() throws Exception {
    Files.delete(rig.ledger("alpha"));
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.status()).isEqualTo(200);
      assertThat(client.next(QUIET)).isNull();
      rig.append("alpha", A1);
      rig.tick();
      assertThat(ValidatedEvents.valid(client.nextEvent(BOUND)).id()).isEqualTo(Cursors.text(A1, 1));
    }
    assertThat(rig.built.handles().diagnostics()).isEmpty();
  }

  @Test
  void ac3nAnUnscopedConnectLeavesAFaultyMissionUnwatchedWithOneDiagnosticAndDeliversTheOther() throws Exception {
    rig.swapLedgerForSymlink("alpha");
    try (SseClient client = rig.unscoped()) {
      assertThat(client.status()).isEqualTo(200);
      assertThat(client.header("Content-Type")).startsWith("text/event-stream");
      assertDiagnostics(DiagnosticCode.LEDGER_UNREADABLE, MID8_A, 1);
      rig.append("beta", betaRow(1));
      rig.tick();
      assertThat(eventId(ValidatedEvents.valid(client.nextEvent(BOUND)))).isEqualTo(Rows.id(51));
    }
  }

  @Test
  void ac3nAnUnscopedConnectWithAMalformedMetaWritesMetaUnparseableWithMid8None() throws Exception {
    Files.writeString(rig.missionDir("alpha").resolve("meta.json"), "{ not json");
    try (SseClient client = rig.unscoped()) {
      assertThat(client.status()).isEqualTo(200);
      assertDiagnostics(DiagnosticCode.META_UNPARSEABLE, "none", 1);
      rig.append("beta", betaRow(1));
      rig.tick();
      ValidatedEvents.valid(client.nextEvent(BOUND));
    }
  }

  @Test
  void ac3nAnUnscopedConnectWithAnUnlistableKittySpecsIs500MissionDirUnreadable() throws Exception {
    Assumptions.assumeTrue(FileSystems.getDefault().supportedFileAttributeViews().contains("posix"), "POSIX permissions are unavailable on this file system (Windows)");
    Path specs = rig.built.root().resolve("kitty-specs");
    Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("--x------"));
    try {
      Assumptions.assumeFalse(Files.isReadable(specs), "running with privileges that list an unlistable directory (root)");
      try (SseClient client = rig.unscoped()) {
        assertThat(client.status()).isEqualTo(500);
        assertThat(JSON.readTree(client.body()).get("code").asString()).isEqualTo("mission_dir_unreadable");
      }
    } finally {
      Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("rwxr-xr-x"));
    }
  }

  // ---- S5 / S6 / AC-3o: while open ----------------------------------------------------------------------------------------

  @Test
  void ac3oAScopedStreamClosesWhenItsMissionDirectoryVanishesWithOneMissionVanishedDiagnostic() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.removeTree(rig.missionDir("alpha"));
      rig.tick();

      assertThat(client.awaitEnd(BOUND)).isTrue();
      assertThat(client.items()).isEmpty();
      assertDiagnostics(DiagnosticCode.MISSION_VANISHED, MID8_A, 1);
    }
  }

  @Test
  void ac3oAnUnscopedStreamKeepsTheConnectionWhenOneMissionVanishes() {
    try (SseClient client = rig.unscoped()) {
      rig.removeTree(rig.missionDir("alpha"));
      rig.tick();
      rig.append("beta", betaRow(1));
      rig.tick();

      assertThat(eventId(ValidatedEvents.valid(client.nextEvent(BOUND)))).isEqualTo(Rows.id(51));
      assertThat(client.awaitEnd(Duration.ofMillis(100))).isFalse();
      assertDiagnostics(DiagnosticCode.MISSION_VANISHED, MID8_A, 1);
    }
  }

  @Test
  void ac3oAnUnlistableKittySpecsKeepsTheConnectionAndWritesOneDiagnosticPerTransitionIntoFailure() throws Exception {
    Assumptions.assumeTrue(FileSystems.getDefault().supportedFileAttributeViews().contains("posix"), "POSIX permissions are unavailable on this file system (Windows)");
    Path specs = rig.built.root().resolve("kitty-specs");
    try (SseClient client = rig.unscoped()) {
      Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("--x------"));
      try {
        Assumptions.assumeFalse(Files.isReadable(specs), "running with privileges that list an unlistable directory (root)");
        rig.tick();
        rig.tick();
        assertDiagnostics(DiagnosticCode.MISSION_DIR_UNREADABLE, "none", 1);
        assertThat(client.awaitEnd(Duration.ofMillis(100))).isFalse();
      } finally {
        Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("rwxr-xr-x"));
      }
      rig.tick();
      rig.append("beta", betaRow(1));
      rig.tick();
      assertThat(eventId(ValidatedEvents.valid(client.nextEvent(BOUND)))).as("every watched Mission was kept").isEqualTo(Rows.id(51));
      Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("--x------"));
      try {
        rig.tick();
        assertDiagnostics(DiagnosticCode.MISSION_DIR_UNREADABLE, "none", 2);
      } finally {
        Files.setPosixFilePermissions(specs, PosixFilePermissions.fromString("rwxr-xr-x"));
      }
    }
  }

  @Test
  void aCursorForTheStartOfTheLogResumesTheWholeLog() {
    try (SseClient client = rig.scopedFrom(Rows.ALPHA_ID, StreamCursor.start())) {
      assertThat(ValidatedEvents.valid(client.nextEvent(BOUND)).id()).isEqualTo(Cursors.text(A1, 1));
    }
  }
}
