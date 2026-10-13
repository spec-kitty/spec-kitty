package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver.ReadClass;
import org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver.Resolution;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.Topology;

/**
 * Which directory a Mission's ledger is read from (FR-006 rules 1-4), by stored topology and directory existence only. Test names cite
 * the Python function each case mirrors: {@code _resolve_existing_for_slug} (stored topology decides, the husk is not consulted),
 * {@code probe_coord_state} (MATERIALIZED and EMPTY), {@code classify_from_meta} and {@code topology_from_meta} (rule 3). The expected
 * classes were checked against the oracle on the same trees (see the WP08 tracer).
 */
class ReadDirResolverTest {

  private static final String NAME = "m-01ABCDEF";
  private static final String MISSION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00";
  private static final String VALID_LANES =
      "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"main\","
          + "\"lanes\":[{\"lane_id\":\"lane-a\",\"wp_ids\":[\"WP01\"]}],\"computed_at\":\"t\",\"computed_from\":\"f\"}";
  private static final String PLANNING_ONLY_LANES =
      "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"main\","
          + "\"lanes\":[{\"lane_id\":\"lane-planning\",\"wp_ids\":[\"WP01\"]}],\"computed_at\":\"t\",\"computed_from\":\"f\"}";

  /** The shape of conformance/resolver-cases.json (WP07), plus {@code coordinationBranch} for rule 3. */
  record Case(String id, String storedTopology, boolean coordRootPresent, boolean coordMissionDirPresent, String lanesJson, String expectedClass, boolean coordinationBranch) {
    Case(String id, String storedTopology, boolean coordRootPresent, boolean coordMissionDirPresent, String lanesJson, String expectedClass) {
      this(id, storedTopology, coordRootPresent, coordMissionDirPresent, lanesJson, expectedClass, false);
    }
  }

  @TempDir Path sandbox;
  Path root;
  RecordingAllowlistAccess recorder;
  ReadDirResolver resolver;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    recorder = new RecordingAllowlistAccess(root);
    resolver = new ReadDirResolver(new SafeFiles(root, recorder));
  }

  // ---- fixtures ---------------------------------------------------------------------------------------------------------

  private Path primary() {
    return root.resolve("kitty-specs").resolve(NAME);
  }

  private Path coordMission() {
    return root.resolve(".worktrees").resolve(NAME + "-coord").resolve("kitty-specs").resolve(NAME);
  }

  private void meta(String json) throws IOException {
    Files.createDirectories(primary());
    Files.writeString(primary().resolve("meta.json"), json);
  }

  private static String metaJson(String topology, boolean coordinationBranch) {
    StringBuilder json = new StringBuilder("{\"mission_id\":\"" + MISSION_ID + "\",\"mission_slug\":\"" + NAME + "\"");
    if (topology != null) {
      json.append(",\"topology\":").append(topology);
    }
    if (coordinationBranch) {
      json.append(",\"coordination_branch\":\"kitty/mission-").append(NAME).append("\"");
    }
    return json.append("}").toString();
  }

  private void lanes(String kind) throws IOException {
    switch (kind) {
      case "valid" -> Files.writeString(primary().resolve("lanes.json"), VALID_LANES);
      case "corrupt" -> Files.writeString(primary().resolve("lanes.json"), "{not json");
      case "absent" -> { }
      default -> throw new IllegalArgumentException(kind);
    }
  }

  private void coord(boolean rootPresent, boolean missionDirPresent) throws IOException {
    if (missionDirPresent) {
      Files.createDirectories(coordMission());
      Files.writeString(coordMission().resolve("status.events.jsonl"), "{}\n");
    } else if (rootPresent) {
      Files.createDirectories(root.resolve(".worktrees").resolve(NAME + "-coord"));
    }
  }

  private static Kind faultOf(Runnable action) {
    try {
      action.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    throw new AssertionError("no SourceFault");
  }

  // ---- the case table (the shape WP09 swaps for resolver-cases.json) -----------------------------------------------------

  static Stream<Arguments> cases() {
    return Stream.of(
            // rule 1: stored single_branch / lanes => PRIMARY, a husk beside it is never consulted (_resolve_existing_for_slug)
            new Case("single-branch-no-coordination", "single_branch", false, false, "absent", "own"),
            new Case("single-branch-husk-with-mission-dir", "single_branch", true, true, "absent", "own"),
            new Case("single-branch-husk-root-only", "single_branch", true, false, "absent", "own"),
            new Case("lanes-no-coordination", "lanes", false, false, "valid", "own"),
            new Case("lanes-husk-with-mission-dir", "lanes", true, true, "valid", "own"),
            // rule 2: stored coord / lanes_with_coord => coordination Mission directory when it exists (probe_coord_state MATERIALIZED)
            new Case("coord-materialized", "coord", true, true, "absent", "coord"),
            new Case("lanes-with-coord-materialized", "lanes_with_coord", true, true, "valid", "coord"),
            // rule 2: else primary (probe_coord_state EMPTY and UNMATERIALIZED)
            new Case("coord-root-without-mission-dir", "coord", true, false, "absent", "own"),
            new Case("coord-worktree-absent", "coord", false, false, "absent", "own"),
            new Case("lanes-with-coord-root-without-mission-dir", "lanes_with_coord", true, false, "valid", "own"),
            new Case("lanes-with-coord-worktree-absent", "lanes_with_coord", false, false, "valid", "own"),
            // rule 3: absent topology, classified from coordination_branch and lanes.json (classify_from_meta / topology_from_meta)
            new Case("absent-topology-no-lanes", "absent", false, false, "absent", "own"),
            new Case("absent-topology-valid-lanes", "absent", false, false, "valid", "own"),
            new Case("absent-topology-corrupt-lanes", "absent", false, false, "corrupt", "own"),
            new Case("absent-topology-husk-without-declared-coordination", "absent", true, true, "absent", "own"),
            new Case("absent-topology-declared-coordination-materialized", "absent", true, true, "absent", "coord", true),
            new Case("absent-topology-declared-coordination-lanes-materialized", "absent", true, true, "valid", "coord", true),
            new Case("absent-topology-declared-coordination-corrupt-lanes-materialized", "absent", true, true, "corrupt", "coord", true),
            new Case("absent-topology-declared-coordination-root-only", "absent", true, false, "absent", "own", true),
            new Case("absent-topology-declared-coordination-worktree-absent", "absent", false, false, "absent", "own", true),
            // an unrecognised stored value is absent (MissionTopology.from_stored)
            new Case("unrecognised-topology-declared-coordination-materialized", "\"weird\"", true, true, "absent", "coord", true),
            new Case("non-string-topology-declared-coordination-materialized", "5", true, true, "absent", "coord", true),
            new Case("unrecognised-topology-husk-only", "\"weird\"", true, true, "absent", "own"))
        .map(c -> Arguments.of(c.id(), c));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("cases")
  void theReadDirectoryClassFollowsTheStoredTopologyAndTheDirectoriesPresent(String id, Case c) throws IOException {
    String topology = c.storedTopology().equals("absent") ? null : (c.storedTopology().startsWith("\"") || Character.isDigit(c.storedTopology().charAt(0)) ? c.storedTopology() : "\"" + c.storedTopology() + "\"");
    meta(metaJson(topology, c.coordinationBranch() || c.storedTopology().contains("coord")));
    lanes(c.lanesJson());
    coord(c.coordRootPresent(), c.coordMissionDirPresent());

    Resolution resolution = resolver.resolve(NAME);

    assertThat(resolution.readClass().name().toLowerCase()).as(id).isEqualTo(c.expectedClass());
    assertThat(resolution.dir()).isEqualTo(c.expectedClass().equals("coord") ? coordMission() : primary());
    assertThat(resolution.classified()).isTrue();
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aStoredCoordLessTopologyNeverTouchesTheWorktreesAtAll() throws IOException {
    meta(metaJson("\"single_branch\"", true));
    coord(true, true);
    resolver.resolve(NAME);
    assertThat(recorder.accesses()).noneMatch(access -> access.path().startsWith(".worktrees"));
  }

  @Test
  void theTopologyIsReportedAsStoredOrClassified() throws IOException {
    meta(metaJson("\"lanes_with_coord\"", true));
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.LANES_WITH_COORD);

    meta(metaJson(null, true));
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.COORD);

    Files.writeString(primary().resolve("lanes.json"), VALID_LANES);
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.LANES_WITH_COORD);

    meta(metaJson(null, false));
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.LANES);

    Files.delete(primary().resolve("lanes.json"));
    // topology_from_meta never derives single_branch at runtime (unstamped_runtime_topology): a coord-less, lane-less Mission reads as LANES
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.LANES);
  }

  @Test
  void aPlanningOnlyLanesJsonIsNotACodeLane() throws IOException {
    meta(metaJson(null, true));
    Files.writeString(primary().resolve("lanes.json"), PLANNING_ONLY_LANES);
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.COORD);
  }

  // ---- rule 3: an empty or malformed meta.json leaves the topology unclassified (the application maps it to L7) ----------

  static Stream<Arguments> unusableMetas() {
    return Stream.of(
        Arguments.of("empty", ""),
        Arguments.of("whitespace", "  \n"),
        Arguments.of("not-json", "{not json"),
        Arguments.of("array", "[]"),
        Arguments.of("scalar", "5"),
        Arguments.of("null", "null"),
        Arguments.of("bom", "﻿{}"),
        Arguments.of("truncated", "{\"topology\":\"coord\""),
        Arguments.of("trailing-garbage", "{} x"),
        Arguments.of("two-documents", "{}{}"),
        Arguments.of("single-quotes", "{'a':1}"),
        Arguments.of("trailing-comma", "{\"a\":1,}"),
        Arguments.of("comment", "{/*x*/}"),
        Arguments.of("leading-zero", "{\"a\":01}"),
        Arguments.of("raw-control-character", "{\"a\":\"x\ty\"}"),
        Arguments.of("plus-infinity", "{\"a\":+Infinity,\"topology\":\"single_branch\"}"),
        Arguments.of("inf", "{\"a\":INF,\"topology\":\"single_branch\"}"));
  }

  /** What {@code json.loads} reads that a stricter parser would refuse; each was run through the oracle's {@code load_meta}. */
  static Stream<Arguments> usableMetas() {
    return Stream.of(
        Arguments.of("nan", "{\"a\":NaN,\"topology\":\"coord\"}"),
        Arguments.of("infinity", "{\"a\":Infinity,\"b\":-Infinity,\"topology\":\"coord\"}"),
        Arguments.of("huge-exponent", "{\"a\":1e999,\"topology\":\"coord\"}"),
        Arguments.of("lone-surrogate-escape", "{\"a\":\"\\ud800\",\"topology\":\"coord\"}"),
        Arguments.of("nul-escape", "{\"a\":\"\\u0000\",\"topology\":\"coord\"}"),
        Arguments.of("trailing-newline", "{\"topology\":\"coord\"}\n"));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("usableMetas")
  void aMetaThatJsonLoadsReadsIsUsable(String id, String content) throws IOException {
    meta(content);
    assertThat(resolver.resolve(NAME).classified()).as(id).isTrue();
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("unusableMetas")
  void anEmptyOrMalformedMetaLeavesTheTopologyUnclassifiedAndReadsThePrimaryDirectory(String id, String content) throws IOException {
    meta(content);
    coord(true, true);
    Resolution resolution = resolver.resolve(NAME);
    assertThat(resolution.classified()).as(id).isFalse();
    assertThat(resolution.topology()).isEqualTo(Topology.UNKNOWN);
    assertThat(resolution.readClass()).isEqualTo(ReadClass.OWN);
    assertThat(resolution.dir()).isEqualTo(primary());
  }

  @Test
  void aMetaThatIsNotUtf8IsUnusable() throws IOException {
    Files.createDirectories(primary());
    Files.write(primary().resolve("meta.json"), new byte[] {'{', '"', 'a', '"', ':', '"', (byte) 0xC3, (byte) 0x28, '"', '}'});
    assertThat(resolver.resolve(NAME).classified()).isFalse();
  }

  @Test
  void aMetaWithDuplicateKeysTakesTheLastLikeJsonLoads() throws IOException {
    meta("{\"topology\":\"coord\",\"topology\":\"single_branch\",\"mission_id\":\"" + MISSION_ID + "\"}");
    coord(true, true);
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.OWN);
  }

  // ---- rule 3 and the lanes signal: read only when needed, degrades when corrupt or unreadable ------------------------------

  @Test
  void lanesJsonIsReadOnlyWhenTheTopologyIsAbsent() throws IOException {
    meta(metaJson("\"coord\"", true));
    lanes("valid");
    coord(true, true);
    resolver.resolve(NAME);
    assertThat(recorder.accesses()).noneMatch(access -> access.pathClass() == PathClass.LANES_JSON);

    meta(metaJson(null, true));
    recorder.clear();
    resolver.resolve(NAME);
    assertThat(recorder.accesses()).anyMatch(access -> access.pathClass() == PathClass.LANES_JSON && access.mode() == OpenMode.READ);
  }

  @Test
  void aSymlinkedOrUnreadableLanesJsonDegradesToNoLanesAndNeverFailsTheRead() throws IOException {
    meta(metaJson(null, true));
    coord(true, true);
    Path elsewhere = Files.writeString(sandbox.resolve("lanes-target.json"), VALID_LANES);
    SymlinkSupport.link(primary().resolve("lanes.json"), elsewhere);
    Resolution linked = resolver.resolve(NAME);
    assertThat(linked.topology()).isEqualTo(Topology.COORD);
    assertThat(linked.readClass()).isEqualTo(ReadClass.COORD);

    Files.delete(primary().resolve("lanes.json"));
    Files.writeString(primary().resolve("lanes.json"), VALID_LANES);
    recorder.failWhen(access -> access.pathClass() == PathClass.LANES_JSON && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(resolver.resolve(NAME).topology()).isEqualTo(Topology.COORD);
  }

  static Stream<Arguments> corruptLanes() {
    return Stream.of(
        Arguments.of("not-json", "{nope"),
        Arguments.of("array", "[]"),
        Arguments.of("no-lanes-key", "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"t\",\"computed_at\":\"t\",\"computed_from\":\"f\"}"),
        Arguments.of("missing-required-key", "{\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"t\",\"lanes\":[{\"lane_id\":\"lane-a\",\"wp_ids\":[]}],\"computed_at\":\"t\",\"computed_from\":\"f\"}"),
        Arguments.of("lane-without-id", "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"t\",\"lanes\":[{\"wp_ids\":[]}],\"computed_at\":\"t\",\"computed_from\":\"f\"}"),
        Arguments.of("lanes-not-a-list-of-objects", "{\"version\":1,\"mission_slug\":\"m\",\"mission_branch\":\"b\",\"target_branch\":\"t\",\"lanes\":[\"lane-a\"],\"computed_at\":\"t\",\"computed_from\":\"f\"}"));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("corruptLanes")
  void aCorruptLanesJsonCountsAsNoLanes(String id, String content) throws IOException {
    meta(metaJson(null, false));
    Files.writeString(primary().resolve("lanes.json"), content);
    assertThat(resolver.resolve(NAME).topology()).as(id).isEqualTo(Topology.LANES);
    // "no lanes" and no coordination_branch is single_branch, which the runtime reads as lanes; with a coordination branch it is coord:
    meta(metaJson(null, true));
    assertThat(resolver.resolve(NAME).topology()).as(id).isEqualTo(Topology.COORD);
  }

  // ---- rule 4: meta.json from the Mission's OWN primary directory only -----------------------------------------------------

  @Test
  void theCoordinationCopyOfMetaJsonIsNeverReadAndNeverOverridesThePrimaryOne() throws IOException {
    meta(metaJson("\"coord\"", true));
    coord(true, true);
    Files.writeString(coordMission().resolve("meta.json"), metaJson("\"single_branch\"", false));
    Resolution resolution = resolver.resolve(NAME);
    assertThat(resolution.readClass()).isEqualTo(ReadClass.COORD);
    assertThat(recorder.accesses()).noneMatch(access -> access.path().startsWith(".worktrees") && access.mode() == OpenMode.READ);
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aMissionWhoseOnlyMetaIsInTheCoordinationCopyIsUnclassified() throws IOException {
    meta("");
    coord(true, true);
    Files.writeString(coordMission().resolve("meta.json"), metaJson("\"coord\"", true));
    assertThat(resolver.resolve(NAME).classified()).isFalse();
  }

  // ---- the identity that names the coordination directory ----------------------------------------------------------------------

  @Test
  void theCoordinationDirectoryNameUsesTheDeclaredMid8() throws IOException {
    // resolve_declared_mid8: meta.mid8, then mission_id[:8], then the slug's tail. The name is not double-suffixed (coord_mission_dir_name).
    String other = "01ZZZZZZ";
    Path divergent = root.resolve(".worktrees").resolve(NAME + "-" + other + "-coord").resolve("kitty-specs").resolve(NAME + "-" + other);

    meta("{\"mission_id\":\"" + other + "000000000000000000\",\"topology\":\"coord\",\"coordination_branch\":\"b\"}");
    Files.createDirectories(divergent);
    assertThat(resolver.resolve(NAME).dir()).isEqualTo(divergent);

    meta("{\"mid8\":\"" + other + "\",\"mission_id\":\"" + MISSION_ID + "\",\"topology\":\"coord\",\"coordination_branch\":\"b\"}");
    assertThat(resolver.resolve(NAME).dir()).isEqualTo(divergent);

    coord(true, true);
    meta("{\"topology\":\"coord\",\"coordination_branch\":\"b\"}");
    assertThat(resolver.resolve(NAME).dir()).as("the slug tail is the last fallback").isEqualTo(coordMission());
  }

  @Test
  void withNoIdentityAtAllACoordinationTopologyCannotBeAddressedAndReadsThePrimary() throws IOException {
    Files.createDirectories(root.resolve("kitty-specs/plain"));
    Files.writeString(root.resolve("kitty-specs/plain/meta.json"), "{\"topology\":\"coord\",\"coordination_branch\":\"b\"}");
    Files.createDirectories(root.resolve(".worktrees/plain-coord/kitty-specs/plain"));
    Resolution resolution = resolver.resolve("plain");
    assertThat(resolution.readClass()).isEqualTo(ReadClass.OWN);
    assertThat(resolution.dir()).isEqualTo(root.resolve("kitty-specs/plain"));
  }

  @Test
  void aDeclaredMid8ThatIsNotASafePathSegmentNeverReachesTheFileSystem() throws IOException {
    for (String hostile : List.of("../../outside", "a/b", "..", ".", "a\\\\b")) {
      meta("{\"mid8\":\"" + hostile + "\",\"topology\":\"coord\",\"coordination_branch\":\"b\"}");
      recorder.clear();
      Resolution resolution = resolver.resolve(NAME);
      assertThat(resolution.readClass()).as(hostile).isEqualTo(ReadClass.OWN);
      assertThat(recorder.accesses()).as(hostile).noneMatch(access -> access.path().startsWith(".worktrees") || access.path().contains(".."));
    }
  }

  // ---- containment ----------------------------------------------------------------------------------------------------------

  @Test
  void aCoordinationDirectoryWhoseRealPathLeavesTheRootIsReadFromThePrimaryDirectory() throws IOException {
    meta(metaJson("\"coord\"", true));
    Path outside = Files.createDirectories(sandbox.resolve("outside/kitty-specs/" + NAME));
    Files.writeString(outside.resolve("status.events.jsonl"), "{}\n");
    SymlinkSupport.link(root.resolve(".worktrees").resolve(NAME + "-coord"), sandbox.resolve("outside"));
    Resolution resolution = resolver.resolve(NAME);
    assertThat(resolution.readClass()).isEqualTo(ReadClass.OWN);
    assertThat(resolution.dir()).isEqualTo(primary());
  }

  @Test
  void aMissionDirectoryThatIsALinkIsL9AndANeverReadMeta() throws IOException {
    Path elsewhere = Files.createDirectories(sandbox.resolve("elsewhere"));
    Files.writeString(elsewhere.resolve("meta.json"), metaJson("\"coord\"", true));
    Files.createDirectories(root.resolve("kitty-specs"));
    SymlinkSupport.link(primary(), elsewhere);
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(recorder.accesses()).noneMatch(access -> access.mode() == OpenMode.READ);
  }

  @Test
  void aSymlinkedMetaJsonIsL9() throws IOException {
    Files.createDirectories(primary());
    Path target = Files.writeString(sandbox.resolve("target.json"), metaJson("\"coord\"", true));
    SymlinkSupport.link(primary().resolve("meta.json"), target);
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(recorder.accesses()).noneMatch(access -> access.mode() == OpenMode.READ);
  }

  @Test
  void aMissionDirectoryThatIsGoneIsVanishedAndAMetaThatIsGoneIsVanishedToo() throws IOException {
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.VANISHED);
    Files.createDirectories(primary());
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.VANISHED);
  }

  @Test
  void aMetaThatCannotBeReadIsUnparseableNotRefused() throws IOException {
    meta(metaJson("\"coord\"", true));
    recorder.failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void aCoordinationDirectoryThatCannotBeStatedIsAnUnreadableDirectory() throws IOException {
    meta(metaJson("\"coord\"", true));
    coord(true, true);
    recorder.failWhen(access -> access.pathClass() == PathClass.COORD_MISSION_DIR && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void metaIsReadAsBytesAndDecodedAsUtf8() throws IOException {
    Files.createDirectories(primary());
    Files.write(primary().resolve("meta.json"), "{\"friendly_name\":\"café\",\"topology\":\"single_branch\"}".getBytes(StandardCharsets.UTF_8));
    assertThat(resolver.resolve(NAME).classified()).isTrue();
  }

  // ---- coordination routing needs a non-blank STRING coordination_branch (operator ruling 2026-10-12, WP08 review F1/F3) -----------
  // Expected classes are the oracle's: resolve_read_dir run on the same trees, registered worktree and husk alike (probe/resolver_probe2.py).

  static Stream<Arguments> branchCases() {
    String id = "\"mission_id\":\"" + MISSION_ID + "\",\"mission_slug\":\"" + NAME + "\"";
    String branch = ",\"coordination_branch\":\"kitty/mission-" + NAME + "\"";
    return Stream.of(
        Arguments.of("L33 coord, no coordination_branch", "{" + id + ",\"topology\":\"coord\"}", "own"),
        Arguments.of("L34 lanes_with_coord, no coordination_branch", "{" + id + ",\"topology\":\"lanes_with_coord\"}", "own"),
        Arguments.of("L36 coord, empty coordination_branch", "{" + id + ",\"topology\":\"coord\",\"coordination_branch\":\"\"}", "own"),
        Arguments.of("coord, null coordination_branch", "{" + id + ",\"topology\":\"coord\",\"coordination_branch\":null}", "own"),
        Arguments.of("coord, blank coordination_branch (ruling: non-blank; oracle husk reads coord, registered raises)", "{" + id + ",\"topology\":\"coord\",\"coordination_branch\":\"   \"}", "own"),
        Arguments.of("coord, coordination_branch true (F3)", "{" + id + ",\"topology\":\"coord\",\"coordination_branch\":true}", "own"),
        Arguments.of("coord, coordination_branch 5 (F3)", "{" + id + ",\"topology\":\"coord\",\"coordination_branch\":5}", "own"),
        Arguments.of("absent topology, coordination_branch true (F3)", "{" + id + ",\"coordination_branch\":true}", "own"),
        Arguments.of("coord with a string coordination_branch (control)", "{" + id + ",\"topology\":\"coord\"" + branch + "}", "coord"));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("branchCases")
  void coordinationRoutingNeedsANonBlankStringCoordinationBranchEvenWhenTheCoordinationDirectoryExists(String id, String metaJson, String expected) throws IOException {
    meta(metaJson);
    lanes("valid");
    coord(true, true);
    Resolution resolution = resolver.resolve(NAME);
    assertThat(resolution.readClass().name().toLowerCase()).as(id).isEqualTo(expected);
    assertThat(resolution.dir()).isEqualTo(expected.equals("coord") ? coordMission() : primary());
  }

  @Test
  void aNonStringMid8IsStringifiedLikeTheOracleDoesNotDroppedFromTheCascade() throws IOException {
    // resolve_read_dir with "mid8": 12345678 reads the coordination directory named with "12345678" (oracle: coord), and does NOT fall
    // through to mission_id[:8] (oracle: own when the directory sits at mission_id[:8]). The review's F3 mid8 remedy contradicts it.
    String id = "\"mission_id\":\"" + MISSION_ID + "\"";
    String tail = ",\"topology\":\"coord\",\"coordination_branch\":\"kitty/mission-" + NAME + "\"}";
    meta("{" + id + ",\"mid8\":12345678" + tail);
    coord(true, true);
    assertThat(resolver.resolve(NAME).readClass()).as("directory at mission_id[:8] only").isEqualTo(ReadClass.OWN);
    Path numeric = root.resolve(".worktrees").resolve(NAME + "-12345678-coord").resolve("kitty-specs").resolve(NAME + "-12345678");
    Files.createDirectories(numeric);
    assertThat(resolver.resolve(NAME).dir()).isEqualTo(numeric);
  }

  @Test
  void aBooleanTrueMid8IsStringifiedAsTrueAndNamesTheCoordinationDirectory() throws IOException {
    // WP08 G1. resolve_read_dir with "mid8": true reads the coordination directory named "<name>-True" (oracle: COORD), because
    // resolve_declared_mid8 stringifies the value with str(); it is not dropped from the cascade and not mission_id[:8].
    String id = "\"mission_id\":\"" + MISSION_ID + "\"";
    String tail = ",\"topology\":\"coord\",\"coordination_branch\":\"kitty/mission-" + NAME + "\"}";
    meta("{" + id + ",\"mid8\":true" + tail);
    coord(true, true);
    assertThat(resolver.resolve(NAME).readClass()).as("directory at mission_id[:8] only").isEqualTo(ReadClass.OWN);
    Path stringified = root.resolve(".worktrees").resolve(NAME + "-True-coord").resolve("kitty-specs").resolve(NAME + "-True");
    Files.createDirectories(stringified);
    Resolution resolution = resolver.resolve(NAME);
    assertThat(resolution.readClass()).isEqualTo(ReadClass.COORD);
    assertThat(resolution.dir()).isEqualTo(stringified);
  }

  // ---- F4: a Mission name is one safe path segment ---------------------------------------------------------------------------------

  @Test
  void aMissionNameThatIsNotOneSafePathSegmentIsRefusedBeforeAnyFileSystemAccess() throws IOException {
    meta(metaJson("\"coord\"", true));
    Files.writeString(root.resolve("meta.json"), metaJson("\"coord\"", true));
    for (String hostile : List.of("..", ".", "", "a/../b", "../outside", "a/b", "a\\b", "x\0y")) {
      recorder.clear();
      assertThat(faultOf(() -> resolver.resolve(hostile))).as("[" + hostile + "]").isEqualTo(Kind.PATH_REFUSED);
      assertThat(recorder.accesses()).as("[" + hostile + "]").isEmpty();
    }
  }

  // ---- DD-105: the full oracle routing rule, every row of conformance/resolver-cases.json -------------------------------------------
  // For a stored coord or lanes_with_coord topology with the coordination Mission folder present the result is COORD when that folder
  // holds a meta.json (whatever coordination_branch holds), else COORD only for a non-blank string coordination_branch, else OWN.

  private static final String ROW_NAME = "resolver-case-01J77000";
  private static final String ROW_MISSION_ID = "01J77000000000000000000001";

  /** Every row of the committed table: the WP07 shape, with its defaults (coordMeta present; branch present for a coord-routing topology). */
  static List<JsonNode> tableRows() throws IOException {
    try (var in = ReadDirResolverTest.class.getResourceAsStream("/conformance/resolver-cases.json")) {
      JsonNode rows = JsonMapper.builder().build().readTree(in);
      List<JsonNode> list = new ArrayList<>();
      rows.forEach(list::add);
      return list;
    }
  }

  static Stream<Arguments> tableRowArguments() throws IOException {
    return tableRows().stream().map(row -> Arguments.of(row.get("id").stringValue(), row));
  }

  private static String field(JsonNode row, String key, String fallback) {
    return row.has(key) ? row.get(key).stringValue() : fallback;
  }

  /** Builds one table row the way tests/contract/_mission_status_conformance.py materialise_resolver_case does, minus git. */
  private void materialise(JsonNode row) throws IOException {
    String stored = row.get("storedTopology").stringValue();
    boolean routing = stored.equals("coord") || stored.equals("lanes_with_coord");
    String branch = field(row, "coordinationBranch", routing ? "present" : "absent");
    StringBuilder meta = new StringBuilder("{\"mission_id\":\"" + ROW_MISSION_ID + "\",\"mission_slug\":\"" + ROW_NAME + "\"");
    if (!stored.equals("absent")) {
      meta.append(",\"topology\":\"").append(stored).append("\"");
    }
    if (branch.equals("present")) {
      meta.append(",\"coordination_branch\":\"kitty/mission-").append(ROW_NAME).append("\"");
    } else if (branch.equals("empty")) {
      meta.append(",\"coordination_branch\":\"\"");
    }
    Path own = root.resolve("kitty-specs").resolve(ROW_NAME);
    Files.createDirectories(own);
    Files.writeString(own.resolve("meta.json"), meta.append("}").toString());
    String lanes = row.get("lanesJson").stringValue();
    if (lanes.equals("valid")) {
      Files.writeString(own.resolve("lanes.json"), VALID_LANES);
    } else if (lanes.equals("corrupt")) {
      Files.writeString(own.resolve("lanes.json"), "{not json");
    }
    Path coordRoot = root.resolve(".worktrees").resolve(ROW_NAME + "-coord");
    if (row.get("coordRootPresent").booleanValue()) {
      Files.createDirectories(coordRoot);
      if (row.get("coordMissionDirPresent").booleanValue()) {
        Path dir = Files.createDirectories(coordRoot.resolve("kitty-specs").resolve(ROW_NAME));
        Files.writeString(dir.resolve("status.events.jsonl"), "{}\n");
        if (field(row, "coordMeta", "present").equals("present")) {
          Files.writeString(dir.resolve("meta.json"), "{\"copy\":\"coordination\"}");
        }
      }
    }
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("tableRowArguments")
  void everyRowOfTheCommittedResolverTableReadsTheClassTheOracleGave(String id, JsonNode row) throws IOException {
    materialise(row);
    Resolution resolution = resolver.resolve(ROW_NAME);
    assertThat(resolution.readClass().name().toLowerCase()).as(id).isEqualTo(row.get("expectedClass").stringValue());
    assertThat(recorder.violations()).as(id).isEmpty();
    assertThat(recorder.accesses()).as(id + ": the coordination meta.json is never read").noneMatch(a -> a.mode() == OpenMode.READ && a.path().startsWith(".worktrees"));
  }

  @Test
  void theCommittedTableHoldsTheTwentyDd105RowsAndAllOfThemRun() throws IOException {
    assertThat(tableRows()).hasSizeGreaterThanOrEqualTo(34);
    assertThat(tableRows()).extracting(row -> row.get("id").stringValue()).contains("coord-husk-coord-meta-present-branch-absent", "lanes-with-coord-registered-coord-meta-absent-branch-empty");
  }

  // The coordination meta.json is stat-ed through the seam and never read. What the oracle does with an odd one (resolve_read_dir,
  // coord topology, no coordination_branch; probe/resolver_probe4.py): a regular file or a symlink to a file (inside or outside the
  // project) reads COORD; a dangling symlink reads OWN; a directory, an empty file or a corrupt one makes the oracle raise
  // MissionMetaReadError, where the service (which reads no content) treats a regular file as present and a directory as absent.

  private void coordNoBranchWithCoordMeta() throws IOException {
    meta("{\"mission_id\":\"" + MISSION_ID + "\",\"mission_slug\":\"" + NAME + "\",\"topology\":\"coord\"}");
    Files.createDirectories(coordMission());
    Files.writeString(coordMission().resolve("status.events.jsonl"), "{}\n");
  }

  @Test
  void theCoordinationMetaIsStatedNotRead() throws IOException {
    coordNoBranchWithCoordMeta();
    Files.writeString(coordMission().resolve("meta.json"), "{\"copy\":1}");
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.COORD);
    assertThat(recorder.accesses()).anyMatch(a -> a.pathClass() == PathClass.COORD_META && a.mode() == OpenMode.STAT);
    assertThat(recorder.accesses()).noneMatch(a -> a.pathClass() == PathClass.COORD_META && a.mode() == OpenMode.READ);
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aCoordinationMetaThatIsASymlinkToAFileReadsCoordLikeTheOracle() throws IOException {
    coordNoBranchWithCoordMeta();
    Path target = Files.writeString(sandbox.resolve("coord-meta-target.json"), "{}");
    SymlinkSupport.link(coordMission().resolve("meta.json"), target);
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.COORD);
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ && a.path().startsWith(".worktrees"));
  }

  @Test
  void aCoordinationMetaThatIsADanglingSymlinkIsAbsentLikeTheOracle() throws IOException {
    coordNoBranchWithCoordMeta();
    SymlinkSupport.link(coordMission().resolve("meta.json"), sandbox.resolve("nowhere.json"));
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.OWN);
  }

  @Test
  void aCoordinationMetaThatIsADirectoryIsAbsent() throws IOException {
    coordNoBranchWithCoordMeta();
    Files.createDirectory(coordMission().resolve("meta.json"));
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.OWN);
  }

  @Test
  void aCorruptCoordinationMetaIsPresentBecauseItsContentIsNeverLookedAt() throws IOException {
    coordNoBranchWithCoordMeta();
    Files.writeString(coordMission().resolve("meta.json"), "{not json");
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.COORD);
  }

  @Test
  void aCoordinationMetaThatCannotBeStatedIsAnUnreadableDirectory() throws IOException {
    coordNoBranchWithCoordMeta();
    Files.writeString(coordMission().resolve("meta.json"), "{}");
    recorder.failWhen(a -> a.pathClass() == PathClass.COORD_META, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(() -> resolver.resolve(NAME))).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void withANonBlankBranchTheCoordinationMetaIsNotEvenStated() throws IOException {
    meta(metaJson("\"coord\"", true));
    coord(true, true);
    assertThat(resolver.resolve(NAME).readClass()).isEqualTo(ReadClass.COORD);
    assertThat(recorder.accesses()).noneMatch(a -> a.pathClass() == PathClass.COORD_META);
  }
}
