package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.domain.model.Topology;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The Mission-level operations of {@link FilesystemMissionEventSource}: listing, {@code readMeta}, and the ledger trio (stamp, read,
 * window), at the port, with the failure-table rows L1, L2, L4/L4b, L6, L7, L9 and L11 realised on real files and by fault injection.
 */
class FilesystemMissionEventSourceTest {

  private static final String NAME = AdapterServiceHarness.ALPHA;
  private static final String ID = Rows.ALPHA_ID;
  private static final String EMPTY_SHA = sha(new byte[0]);

  @TempDir Path sandbox;
  Path root;
  RecordingAllowlistAccess recorder;
  FilesystemMissionEventSource source;
  MissionRef ref = new MissionRef(NAME);

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    recorder = new RecordingAllowlistAccess(root);
    source = new FilesystemMissionEventSource(root, recorder);
    AdapterServiceHarness.healthyProject(root);
  }

  static String sha(byte[] bytes) {
    try {
      return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    } catch (java.security.NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  private Path dir() {
    return root.resolve("kitty-specs").resolve(NAME);
  }

  private Path ledger() {
    return dir().resolve("status.events.jsonl");
  }

  private void mission(String ledgerText) {
    AdapterServiceHarness.mission(root, NAME, ID, "2026-09-01T09:00:00+00:00", ledgerText);
  }

  private void ledgerBytes(byte[] bytes) {
    AdapterServiceHarness.writeBytes(ledger(), bytes);
  }

  private static Kind faultOf(Runnable call) {
    try {
      call.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    return null;
  }

  private static byte[] bytes(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  private static String row(int n, String from, String to) {
    return AdapterServiceHarness.laneRow(n, "WP01", from, to);
  }

  // ---- listing (L11) -----------------------------------------------------------------------------------------------------------

  @Test
  void missionsAreListedInCodePointOrderAndOnlyDirectoriesHoldingMetaJson() throws IOException {
    for (String name : List.of("b-01J02000", "a-01J01000", "A-01J03000", "é-01J04000")) {
      AdapterServiceHarness.mission(root, name, Rows.BETA_ID, "2026-09-01T09:00:00+00:00", null);
    }
    Files.createDirectories(root.resolve("kitty-specs/no-meta-here"));
    AdapterServiceHarness.write(root.resolve("kitty-specs/a-file.txt"), "x");
    assertThat(source.listMissions()).extracting(MissionRef::name).containsExactly("A-01J03000", "a-01J01000", "b-01J02000", "é-01J04000");
  }

  @Test
  void anAbsentSpecsDirectoryListsNothing() {
    assertThat(source.listMissions()).isEmpty();
  }

  @Test
  void anUnlistableSpecsDirectoryIsADirectoryFaultRowL11() {
    mission(null);
    recorder.failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(source::listMissions)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void aMissionWhoseMetaCannotBeStatedIsADirectoryFaultRowL11() {
    mission(null);
    recorder.failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(source::listMissions)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  // ---- meta (L7, L9, L6) ------------------------------------------------------------------------------------------------------

  @Test
  void metaJsonIsDecodedIntoTheMissionMeta() {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"mission_slug\":\"alpha-mission\",\"slug\":\"other\",\"friendly_name\":\" Alpha \",\"mission_number\":\"042\","
            + "\"mission_type\":\" software-dev \",\"target_branch\":\"main\",\"topology\":\"lanes\",\"created_at\":\"2026-09-01T09:00:00+00:00\","
            + "\"accepted_at\":\"2026-09-02T09:00:00+00:00\",\"merged_at\":\"\",\"discarded_at\":null,\"baseline_merge_commit\":\"abc\"}");
    MissionMeta meta = source.readMeta(ref);
    assertThat(meta.missionId().value()).isEqualTo(ID);
    assertThat(meta.slug()).isEqualTo("alpha-mission");
    assertThat(meta.friendlyName()).isEqualTo(" Alpha ");
    assertThat(meta.displayNumber()).isEqualTo(42);
    assertThat(meta.missionType()).isEqualTo("software-dev");
    assertThat(meta.targetBranch()).isEqualTo("main");
    assertThat(meta.topology()).isEqualTo(Topology.LANES);
    assertThat(meta.createdAt()).isEqualTo("2026-09-01T09:00:00+00:00");
    assertThat(meta.acceptedAt()).isEqualTo("2026-09-02T09:00:00+00:00");
    assertThat(meta.mergedAt()).isNull();
    assertThat(meta.discardedAt()).isNull();
    assertThat(meta.hasBaseline()).isTrue();
  }

  @Test
  void theOracleDefaultsApplyToAbsentOptionalMembers() {
    AdapterServiceHarness.write(dir().resolve("meta.json"), "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\"}");
    MissionMeta meta = source.readMeta(ref);
    assertThat(meta.slug()).as("resolve_mission_identity: the trusted directory name").isEqualTo(NAME);
    assertThat(meta.friendlyName()).isNull();
    assertThat(meta.displayNumber()).isNull();
    assertThat(meta.missionType()).as("typeless Missions read as empty").isNull();
    assertThat(meta.topology()).isEqualTo(Topology.UNKNOWN);
    assertThat(meta.hasBaseline()).isFalse();
  }

  @ParameterizedTest(name = "unsafe slug [{0}] falls back to the directory name")
  @ValueSource(strings = {"../../evil", "a/b", ".hidden", "a..b", " padded ", "café"})
  void anUnsafeSlugFallsBackToTheDirectoryName(String slug) {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"mission_slug\":" + jsonString(slug) + ",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\"}");
    assertThat(source.readMeta(ref).slug()).isEqualTo(NAME);
  }

  private static String jsonString(String text) {
    return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
  }

  @ParameterizedTest(name = "mission_number {0} reads as {1}")
  @org.junit.jupiter.params.provider.CsvSource(
      delimiter = '|',
      nullValues = "NULL",
      value = {"\"042\" | 42", "\"000\" | 0", "\"0\" | 0", "\"-3\" | -3", "\"+5\" | 5", "\"1_0\" | 10", "\" 12 \" | 12", "\"\u0663\" | 3", "\"  \" | NULL", "\"\" | NULL", "null | NULL", "7 | 7"})
  void aMissionNumberIsCoercedAsResolveMissionIdentityCoercesIt(String json, Integer expected) {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"mission_number\":" + json + "}");
    assertThat(source.readMeta(ref).displayNumber()).isEqualTo(expected);
  }

  @ParameterizedTest(name = "mission_number {0} is row L7")
  @ValueSource(strings = {"\"1__0\"", "\"0x1\"", "\"TBD\"", "\"unassigned\"", "[1]", "{}", "1099511627776", "2.0"})
  void aMissionNumberTheOracleRefusesIsRowL7(String json) {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"mission_number\":" + json + "}");
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @ParameterizedTest(name = "meta.json [{0}] is row L7")
  @ValueSource(
      strings = {
        "",
        "   ",
        "not json",
        "[]",
        "\"text\"",
        "42",
        "null",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\"}",
        "{\"created_at\":\"2026-09-01T09:00:00+00:00\",\"target_branch\":\"main\"}",
        "{\"mission_id\":\"not-a-ulid\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\"}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"created_at\":\"2026-09-01T09:00:00+00:00\"}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":7,\"created_at\":\"2026-09-01T09:00:00+00:00\"}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\",\"created_at\":null}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-01-01T00:00:00\"}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"mission_number\":true}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"mission_number\":\"pending\"}",
        "{\"mission_id\":\"" + Rows.ALPHA_ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"mission_number\":1.5}",
      })
  void anUnusableMetaJsonIsTheSingleL7Outcome(String text) {
    AdapterServiceHarness.write(dir().resolve("meta.json"), text);
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  // F7: meta.json is read with a size cap (1 MiB); a larger file is the single L7 outcome.
  @Test
  void aMetaJsonLargerThanTheCapIsRowL7ButOneBelowItIsRead() {
    String pad = "x".repeat(900 * 1024);
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"friendly_name\":\"" + pad + "\"}");
    assertThat(source.readMeta(ref).missionId().value()).isEqualTo(ID);
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"friendly_name\":\"" + pad + pad + "\"}");
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void aMetaJsonThatIsNotUtf8IsRowL7() {
    AdapterServiceHarness.writeBytes(dir().resolve("meta.json"), new byte[] {'{', '"', (byte) 0xff, '"', ':', '1', '}'});
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void anOsUnreadableMetaJsonIsRowL7ByFaultInjection() {
    mission(null);
    recorder.failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void aMetaJsonThatIsASymbolicLinkIsRowL9AndTheTargetIsNeverRead() throws IOException {
    Path target = sandbox.resolve("target-meta.json");
    AdapterServiceHarness.write(target, Rows.meta(ID, NAME, "2026-09-01T09:00:00+00:00"));
    Files.createDirectories(dir());
    SymlinkSupport.link(dir().resolve("meta.json"), target);
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ);
  }

  @Test
  void aMissionDirectoryThatIsASymbolicLinkIsRowL9() throws IOException {
    Path real = sandbox.resolve("real-mission");
    AdapterServiceHarness.write(real.resolve("meta.json"), Rows.meta(ID, NAME, "2026-09-01T09:00:00+00:00"));
    Files.createDirectories(root.resolve("kitty-specs"));
    SymlinkSupport.link(dir(), real);
    assertThat(source.listMissions()).extracting(MissionRef::name).containsExactly(NAME);
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(faultOf(() -> source.readLedger(ref, LedgerStamp.of()))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(faultOf(() -> source.readLedgerFrom(ref, 0))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aMissionDirectoryThatVanishedIsRowL6OnEveryOperation() throws IOException {
    mission(row(1, "planned", "claimed"));
    Files.delete(ledger());
    Files.delete(dir().resolve("meta.json"));
    Files.delete(dir());
    assertThat(faultOf(() -> source.readMeta(ref))).isEqualTo(Kind.VANISHED);
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.VANISHED);
    assertThat(faultOf(() -> source.readLedger(ref, LedgerStamp.of()))).isEqualTo(Kind.VANISHED);
    assertThat(faultOf(() -> source.readLedgerFrom(ref, 0))).isEqualTo(Kind.VANISHED);
  }

  @Test
  void aMissionNameThatIsNotOneSafeSegmentIsRefusedBeforeAnyAccess() {
    for (String hostile : List.of("..", "a/b", "../outside", "")) {
      recorder.clear();
      assertThat(faultOf(() -> source.readMeta(new MissionRef(hostile)))).as(hostile).isEqualTo(Kind.PATH_REFUSED);
      assertThat(faultOf(() -> source.stampLedger(new MissionRef(hostile)))).as(hostile).isEqualTo(Kind.PATH_REFUSED);
      assertThat(recorder.accesses()).as(hostile).isEmpty();
    }
  }

  @Test
  void aMetaJsonThatBecameUnusableMakesEveryLedgerOperationRowL7() {
    mission(row(1, "planned", "claimed"));
    AdapterServiceHarness.write(dir().resolve("meta.json"), "not json");
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.META_UNPARSEABLE);
    assertThat(faultOf(() -> source.readLedger(ref, LedgerStamp.of()))).isEqualTo(Kind.META_UNPARSEABLE);
    assertThat(faultOf(() -> source.readLedgerFrom(ref, 0))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  // ---- ledger: absent, unreadable (L1, L2) -------------------------------------------------------------------------------------

  @Test
  void anAbsentLedgerIsRowL1WithAStampOfItsOwn() {
    mission(null);
    LedgerStamp stamp = source.stampLedger(ref);
    assertThat(source.stampLedger(ref)).isEqualTo(stamp);
    assertThat(source.readLedger(ref, stamp)).isEqualTo(new LedgerRead(List.of(), TailClassification.NONE));
    LedgerWindow window = source.readLedgerFrom(ref, 0);
    assertThat(window).isEqualTo(new LedgerWindow(0, true, EMPTY_SHA, List.of(), TailClassification.NONE));
    ledgerBytes(bytes(row(1, "planned", "claimed")));
    assertThat(source.stampLedger(ref)).as("a ledger that appears changes the stamp").isNotEqualTo(stamp);
  }

  @Test
  void aLedgerThatIsASymbolicLinkIsRowL2AndTheTargetIsNeverRead() throws IOException {
    mission(null);
    Path target = sandbox.resolve("elsewhere.jsonl");
    AdapterServiceHarness.write(target, row(1, "planned", "claimed"));
    SymlinkSupport.link(ledger(), target);
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> source.readLedger(ref, LedgerStamp.of()))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> source.readLedgerFrom(ref, 0))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ && a.pathClass() == PathClass.LEDGER);
  }

  @Test
  void aLedgerThatIsADirectoryIsRowL2() throws IOException {
    mission(null);
    Files.createDirectories(ledger());
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.LEDGER_UNREADABLE);
  }

  @Test
  void anOsUnreadableLedgerIsRowL2ByFaultInjectionOnEveryOperation() {
    mission(row(1, "planned", "claimed"));
    recorder.failWhen(access -> access.pathClass() == PathClass.LEDGER && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> source.readLedger(ref, LedgerStamp.of()))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(faultOf(() -> source.readLedgerFrom(ref, 0))).isEqualTo(Kind.LEDGER_UNREADABLE);
  }

  @Test
  void aLedgerThatCannotBeStatedIsRowL2() {
    mission(row(1, "planned", "claimed"));
    recorder.failWhen(access -> access.pathClass() == PathClass.LEDGER && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> source.stampLedger(ref))).isEqualTo(Kind.LEDGER_UNREADABLE);
  }

  @Test
  void noFaultMessageEverCarriesAPath() {
    mission(null);
    AdapterServiceHarness.write(dir().resolve("meta.json"), "not json");
    SourceFault fault = org.junit.jupiter.api.Assertions.assertThrows(SourceFault.class, () -> source.readMeta(ref));
    assertThat(fault.getMessage()).isEqualTo("META_UNPARSEABLE");
    assertThat(fault.getCause()).isNull();
    assertThat(fault.toString()).doesNotContain(sandbox.toString()).doesNotContain(NAME);
  }

  // ---- ledger: read and tail classification -----------------------------------------------------------------------------------

  @Test
  void theWholeLedgerIsDecodedThroughTheCodec() {
    String ledger = row(1, "planned", "claimed") + "\n" + row(2, "claimed", "in_progress") + "not json\n";
    mission(ledger);
    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.tail()).isEqualTo(TailClassification.NONE);
    assertThat(read.lines()).hasSize(4);
    assertThat(read.lines().get(0).kind()).isInstanceOf(LineKind.Status.class);
    assertThat(read.lines().get(1).kind()).isInstanceOf(LineKind.Blank.class);
    assertThat(read.lines().get(3).kind()).isInstanceOf(LineKind.Malformed.class);
    assertThat(read.lines()).extracting(LedgerLine::lineNumber).containsExactly(1L, 2L, 3L, 4L);
    assertThat(read.lines().get(0).rawLineSha256()).isEqualTo(sha(bytes(row(1, "planned", "claimed"))));
  }

  @ParameterizedTest(name = "tail [{0}]")
  @ValueSource(strings = {"{\"event_id\":\"x\",\"at\":\"2026", "{\"a\":1}", "x", "   x"})
  void anUnterminatedNonWhitespaceTailIsClassifiedNonWhitespaceRowsL4AndL4b(String tail) {
    mission(row(1, "planned", "claimed") + tail);
    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.tail()).isEqualTo(TailClassification.NON_WHITESPACE);
    assertThat(read.lines()).as("the tail is never decoded as a line").hasSize(1);
  }

  @ParameterizedTest(name = "whitespace tail {index}")
  @ValueSource(strings = {" ", "\t", "  \t ", "\u000b\u000c", " ", " ", "\u0085", "\r"})
  void anUnterminatedWhitespaceTailIsClassifiedWhitespaceWithPythonStripSemantics(String tail) {
    mission(row(1, "planned", "claimed") + tail);
    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.tail()).isEqualTo(TailClassification.WHITESPACE);
    assertThat(read.lines()).hasSize(1);
  }

  @Test
  void aTailThatIsNotUtf8IsNonWhitespace() {
    ledgerBytesWithTail(new byte[] {(byte) 0xff, (byte) 0xfe});
    assertThat(source.readLedger(ref, source.stampLedger(ref)).tail()).isEqualTo(TailClassification.NON_WHITESPACE);
  }

  private void ledgerBytesWithTail(byte[] tail) {
    mission(row(1, "planned", "claimed"));
    byte[] head = bytes(row(1, "planned", "claimed"));
    byte[] all = new byte[head.length + tail.length];
    System.arraycopy(head, 0, all, 0, head.length);
    System.arraycopy(tail, 0, all, head.length, tail.length);
    ledgerBytes(all);
  }

  @Test
  void aCarriageReturnStaysInTheRawLineForPositionAndDigest() {
    String lf = row(1, "planned", "claimed");
    String crlf = lf.substring(0, lf.length() - 1) + "\r\n";
    mission(crlf);
    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.lines()).hasSize(1);
    assertThat(read.lines().get(0).byteLength()).isEqualTo(crlf.length());
    assertThat(read.lines().get(0).rawLineSha256()).isEqualTo(sha(bytes(crlf))).isNotEqualTo(sha(bytes(lf)));
    LedgerWindow window = source.readLedgerFrom(ref, crlf.length());
    assertThat(window.aligned()).isTrue();
    assertThat(window.precedingLineSha256()).isEqualTo(sha(bytes(crlf)));
  }

  // ---- stamp ----------------------------------------------------------------------------------------------------------------------

  @Test
  void aStampIsValueEqualWhileNothingChangesAndIsOpaque() {
    mission(row(1, "planned", "claimed"));
    LedgerStamp first = source.stampLedger(ref);
    assertThat(source.stampLedger(ref)).isEqualTo(first).hasSameHashCodeAs(first);
    assertThat(first.toString()).isEqualTo("LedgerStamp");
  }

  @Test
  void aStampChangesWhenTheLedgerGrowsOrItsTailChangesOrItsTimeMoves() throws IOException {
    mission(row(1, "planned", "claimed"));
    FileTime fixed = FileTime.from(Instant.parse("2026-09-01T10:00:00Z"));
    Files.setLastModifiedTime(ledger(), fixed);
    LedgerStamp base = source.stampLedger(ref);

    ledgerBytes(bytes(row(1, "planned", "claimed") + row(2, "claimed", "in_progress")));
    Files.setLastModifiedTime(ledger(), fixed);
    LedgerStamp grown = source.stampLedger(ref);
    assertThat(grown).as("size and last-line digest").isNotEqualTo(base);

    ledgerBytes(bytes(row(1, "planned", "claimed") + row(2, "claimed", "in_progress") + "{\"half"));
    Files.setLastModifiedTime(ledger(), fixed);
    assertThat(source.stampLedger(ref)).as("an unterminated tail: size differs").isNotEqualTo(grown);

    ledgerBytes(bytes(row(1, "planned", "claimed") + row(2, "claimed", "in_progress")));
    Files.setLastModifiedTime(ledger(), FileTime.from(Instant.parse("2026-09-01T10:00:01Z")));
    assertThat(source.stampLedger(ref)).as("only the modification time differs").isNotEqualTo(grown);
  }

  @Test
  void theStampReadsOnlyTheFinalLinesNotTheWholeLedger() {
    StringBuilder big = new StringBuilder();
    for (int n = 1; n <= 2000; n++) {
      big.append(row(n % 60 + 1, "planned", "claimed"));
    }
    mission(big.toString());
    recorder.clear();
    source.stampLedger(ref);
    assertThat(recorder.accesses().stream().filter(a -> a.pathClass() == PathClass.LEDGER).map(Access::mode)).containsExactly(OpenMode.STAT, OpenMode.READ);
  }

  // ---- window --------------------------------------------------------------------------------------------------------------------

  @Test
  void aWindowFromAnAlignedOffsetHoldsTheLaterLinesNumberedFromOne() {
    String one = row(1, "planned", "claimed");
    String two = row(2, "claimed", "in_progress");
    String three = row(3, "in_progress", "for_review");
    mission(one + two + three);

    LedgerWindow zero = source.readLedgerFrom(ref, 0);
    assertThat(zero.size()).isEqualTo(one.length() + two.length() + three.length());
    assertThat(zero.aligned()).isTrue();
    assertThat(zero.precedingLineSha256()).isEqualTo(EMPTY_SHA);
    assertThat(zero.lines()).extracting(LedgerLine::lineNumber).containsExactly(1L, 2L, 3L);

    LedgerWindow afterOne = source.readLedgerFrom(ref, one.length());
    assertThat(afterOne.aligned()).isTrue();
    assertThat(afterOne.precedingLineSha256()).isEqualTo(sha(bytes(one)));
    assertThat(afterOne.lines()).extracting(LedgerLine::lineNumber).containsExactly(1L, 2L);
    assertThat(afterOne.lines().get(0).rawLineSha256()).isEqualTo(sha(bytes(two)));

    LedgerWindow afterTwo = source.readLedgerFrom(ref, one.length() + two.length());
    assertThat(afterTwo.precedingLineSha256()).isEqualTo(sha(bytes(two)));
    assertThat(afterTwo.lines()).hasSize(1);

    long end = one.length() + two.length() + three.length();
    LedgerWindow atEnd = source.readLedgerFrom(ref, end);
    assertThat(atEnd.aligned()).isTrue();
    assertThat(atEnd.precedingLineSha256()).isEqualTo(sha(bytes(three)));
    assertThat(atEnd.lines()).isEmpty();
    assertThat(atEnd.tail()).isEqualTo(TailClassification.NONE);
    assertThat(atEnd.size()).isEqualTo(end);
  }

  @Test
  void aWindowCarriesTheTailClassificationOfWhatFollowsItsLastNewline() {
    String one = row(1, "planned", "claimed");
    mission(one + "{\"half");
    assertThat(source.readLedgerFrom(ref, one.length()).tail()).isEqualTo(TailClassification.NON_WHITESPACE);
    assertThat(source.readLedgerFrom(ref, one.length()).lines()).isEmpty();
    AdapterServiceHarness.write(ledger(), one + "  ");
    assertThat(source.readLedgerFrom(ref, one.length()).tail()).isEqualTo(TailClassification.WHITESPACE);
  }

  @Test
  void anOffsetInsideALineIsNotAligned() {
    String one = row(1, "planned", "claimed");
    mission(one + row(2, "claimed", "in_progress"));
    LedgerWindow middle = source.readLedgerFrom(ref, 10);
    assertThat(middle.aligned()).isFalse();
    assertThat(middle.lines()).isEmpty();
    assertThat(middle.precedingLineSha256()).isEqualTo(EMPTY_SHA);
    assertThat(middle.size()).isEqualTo((long) (one + row(2, "claimed", "in_progress")).length());
  }

  @Test
  void anOffsetPastTheEndIsNotAlignedAndHoldsNothing() {
    mission(row(1, "planned", "claimed"));
    long size = row(1, "planned", "claimed").length();
    LedgerWindow past = source.readLedgerFrom(ref, size + 5);
    assertThat(past.aligned()).isFalse();
    assertThat(past.lines()).isEmpty();
    assertThat(past.size()).isEqualTo(size);
    assertThat(past.precedingLineSha256()).isEqualTo(EMPTY_SHA);
  }

  @Test
  void aBlankLineIsTheLineThatEndsTheOffsetWhenItIsTheLastOne() {
    String one = row(1, "planned", "claimed");
    mission(one + "\n");
    LedgerWindow window = source.readLedgerFrom(ref, one.length() + 1);
    assertThat(window.aligned()).isTrue();
    assertThat(window.precedingLineSha256()).as("DD-92: the blank line, not the last non-blank one").isEqualTo(sha(bytes("\n"))).isNotEqualTo(sha(bytes(one)));
  }

  @Test
  void aNegativeOffsetIsNotAlignedAndHoldsNothing() {
    mission(row(1, "planned", "claimed"));
    LedgerWindow window = source.readLedgerFrom(ref, -1);
    assertThat(window.aligned()).isFalse();
    assertThat(window.lines()).isEmpty();
  }

  @Test
  void aLineLongerThanTheReadChunkIsDigestedWhole() {
    String longRow = "{\"pad\":\"" + "x".repeat(200_000) + "\"}\n";
    String one = row(1, "planned", "claimed");
    mission(one + longRow + one);
    long afterLong = one.length() + longRow.length();
    LedgerWindow window = source.readLedgerFrom(ref, afterLong);
    assertThat(window.precedingLineSha256()).isEqualTo(sha(bytes(longRow)));
    assertThat(window.lines()).hasSize(1);
    LedgerStamp stamp = source.stampLedger(ref);
    ledgerBytes(bytes(one + longRow));
    assertThat(source.stampLedger(ref)).isNotEqualTo(stamp);
    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.lines()).hasSize(2);
  }

  // ---- coordination routing ----------------------------------------------------------------------------------------------------

  @Test
  void aCoordinationMissionIsReadFromItsCoordinationLedgerAndNeverFromThePrimaryOne() {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"mission_slug\":\"" + NAME + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\","
            + "\"topology\":\"coord\",\"coordination_branch\":\"kitty/mission-x\"}");
    AdapterServiceHarness.write(ledger(), row(1, "planned", "claimed"));
    Path coord = root.resolve(".worktrees").resolve(NAME + "-coord").resolve("kitty-specs").resolve(NAME);
    String coordText = row(1, "planned", "claimed") + row(2, "claimed", "in_progress");
    AdapterServiceHarness.write(coord.resolve("status.events.jsonl"), coordText);
    AdapterServiceHarness.write(coord.resolve("meta.json"), "{\"decoy\":true}");

    LedgerRead read = source.readLedger(ref, source.stampLedger(ref));
    assertThat(read.lines()).hasSize(2);
    assertThat(source.readLedgerFrom(ref, 0).size()).isEqualTo(coordText.length());

    assertThat(recorder.accesses()).extracting(Access::path).doesNotContain("kitty-specs/" + NAME + "/status.events.jsonl");
    assertThat(recorder.accesses()).extracting(Access::path).noneMatch(path -> path.endsWith("/meta.json") && path.startsWith(".worktrees"));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aCoordinationTopologyWithoutACoordinationBranchReadsThePrimaryLedger() {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"topology\":\"coord\"}");
    AdapterServiceHarness.write(ledger(), row(1, "planned", "claimed"));
    Path coord = root.resolve(".worktrees").resolve(NAME + "-coord").resolve("kitty-specs").resolve(NAME);
    AdapterServiceHarness.write(coord.resolve("status.events.jsonl"), row(1, "planned", "claimed") + row(2, "claimed", "in_progress"));
    assertThat(source.readLedger(ref, source.stampLedger(ref)).lines()).hasSize(1);
  }

  @Test
  void aSingleBranchMissionNeverLooksAtItsCoordinationHusk() {
    AdapterServiceHarness.write(
        dir().resolve("meta.json"),
        "{\"mission_id\":\"" + ID + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-01T09:00:00+00:00\",\"topology\":\"single_branch\",\"coordination_branch\":\"b\"}");
    AdapterServiceHarness.write(ledger(), row(1, "planned", "claimed"));
    source.stampLedger(ref);
    assertThat(recorder.accesses()).extracting(Access::path).noneMatch(path -> path.startsWith(".worktrees"));
  }
}
