package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.PosixHost;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * AC-16 over the HTTP flow: the file seam records the open mode of every access and none is a write (a); the fingerprint of the project
 * before and after the flow is identical (b); the answers do not depend on the drain keys and the personal {@code config.toml} is never
 * read (c); and a project directory made read-only is served unchanged (d). Every check has its positive control.
 */
class ReadOnlyFlowTest {

  private static final Path CANARY_TREE = ConformanceTree.root().resolve("secret-canaries").resolve("planted-canaries");

  private static final int ROWS_IN_CANARY_LOG = 1;
  private static final String ID = "01J6000000000000000000001W";

  private static List<String> flow(StreamRig rig) {
    List<String> all = new ArrayList<>();
    // the Date header is the clock of the moment, not an answer of the service
    Flow.requests(rig.http).forEach(captured -> all.add(captured.everything().replaceAll("(?m)^date: .*$", "date: <clock>")));
    all.add(Flow.readOnlyStreams(rig, ID, ROWS_IN_CANARY_LOG));
    return all;
  }

  private static FilesystemFixtureFactory.Built recorded() {
    return FilesystemFixtureFactory.fromTree(CANARY_TREE, RecordingAllowlistAccess::new);
  }

  @Test
  void ac16aNoOpenOfTheFullFlowIsAnythingButReadOnlyAndAWriteInjectedIntoTheRecorderTurnsItRed() {
    FilesystemFixtureFactory.Built built = recorded();
    try (StreamRig rig = StreamRig.over(built)) {
      flow(rig);
      RecordingAllowlistAccess recorder = rig.http.allowlistRecorder();

      assertThat(recorder.accesses()).as("the flow touched files (a recorder that saw nothing proves nothing)").isNotEmpty();
      assertThat(recorder.accesses()).allSatisfy(access -> assertThat(access.mode().readOnly()).as(access.toString()).isTrue());
      assertThat(recorder.violations()).isEmpty();

      recorder.record(built.root().resolve("kitty-specs/canary-mission/status.events.jsonl"), Allowlist.OpenMode.APPEND);
      assertThat(recorder.violations()).as("positive control: one write turns the check red").hasSize(1);
    }
  }

  @Test
  void ac16bTheFingerprintOfTheProjectIsIdenticalBeforeAndAfterTheFlowAndATouchedFileChangesIt() throws Exception {
    FilesystemFixtureFactory.Built built = recorded();
    try (StreamRig rig = StreamRig.over(built)) {
      List<String> before = Fingerprint.of(built.root());

      flow(rig);

      assertThat(Fingerprint.of(built.root())).as("content hash, listing and modification times").isEqualTo(before);

      Files.writeString(built.root().resolve("kitty-specs/canary-mission/stray.tmp"), "x");
      assertThat(Fingerprint.of(built.root())).as("positive control: one stray file changes the fingerprint").isNotEqualTo(before);
    }
  }

  private static List<String> flowWithDrain(boolean drain) throws Exception {
    FilesystemFixtureFactory.Built built = recorded();
    Path personal = Files.createDirectories(built.root().getParent().resolve("personal"));
    Files.writeString(personal.resolve("config.toml"), "[hosted]\ndrain = " + drain + "\n");
    Files.writeString(built.root().resolve("config.toml"), "[hosted]\ndrain = " + drain + "\n");
    Path config = built.root().resolve(".kittify/config.yaml");
    Files.writeString(config, Files.readString(config) + "hosted:\n  drain: " + drain + "\n");
    try (StreamRig rig = StreamRig.over(built)) {
      List<String> answers = flow(rig);
      assertThat(rig.http.allowlistRecorder().accesses()).as("the personal config.toml is never read").noneMatch(access -> access.path().endsWith("config.toml"));
      return answers;
    }
  }

  @Test
  void ac16cEveryAnswerIsByteIdenticalWithTheDrainKeysOnAndOff() throws Exception {
    List<String> on = flowWithDrain(true);
    List<String> off = flowWithDrain(false);

    assertThat(on).hasSameSizeAs(off);
    for (int i = 0; i < on.size(); i++) {
      assertThat(on.get(i)).as("answer " + i).isEqualTo(off.get(i));
    }
  }

  @Test
  void ac16dAReadOnlyProjectDirectoryIsServedUnchanged() throws Exception {
    PosixHost.assumePosix("ReadOnlyFlowTest.ac16dAReadOnlyProjectDirectoryIsServedUnchanged");
    List<String> writable;
    try (StreamRig rig = StreamRig.over(recorded())) {
      writable = flow(rig);
    }
    FilesystemFixtureFactory.Built built = recorded();
    List<Path> paths;
    try (var walk = Files.walk(built.root())) {
      paths = walk.sorted(java.util.Comparator.reverseOrder()).toList();
    }
    try {
      for (Path path : paths) {
        Files.setPosixFilePermissions(path, Files.isDirectory(path) ? PosixFilePermissions.fromString("r-xr-xr-x") : PosixFilePermissions.fromString("r--r--r--"));
      }
      Assumptions.assumeFalse(Files.isWritable(built.root()), "running as a user for whom a read-only directory is still writable (root): AC-16a carries the proof on this leg");
      try (StreamRig rig = StreamRig.over(built)) {
        assertThat(flow(rig)).isEqualTo(writable);
      }
    } finally {
      for (Path path : paths) {
        Set<PosixFilePermission> restore = Files.isDirectory(path) ? PosixFilePermissions.fromString("rwxr-xr-x") : PosixFilePermissions.fromString("rw-r--r--");
        Files.setPosixFilePermissions(path, restore);
      }
    }
  }

  // ---- WP18 (T126, AC-16.1 to AC-16.3): the five detail routes -------------------------------------------------------------------

  /** The detail flow over a project: the answers with the clock neutralised, through the four fixture-built services. */
  private static List<String> detailFlow(DetailFlow.Project project, org.speckitty.missionstatus.testsupport.RouteMarker marker, org.speckitty.missionstatus.testsupport.http.HttpHarness server) {
    return DetailFlow.run(server, marker, project).stream().map(DetailFlow.Answer::everything).toList();
  }

  @Test
  void ac16aNoOpenOfTheDetailFlowIsAnythingButReadOnlyAndAWriteInjectedIntoTheRecorderTurnsItRed() {
    DetailFlow.Project project = DetailFlow.noTopology();
    org.speckitty.missionstatus.testsupport.RouteMarker marker = org.speckitty.missionstatus.testsupport.RouteMarker.create();
    try (var server = DetailFlow.start(project, marker)) {
      detailFlow(project, marker, server);
      RecordingAllowlistAccess recorder = server.allowlistRecorder();

      assertThat(recorder.accesses()).as("the detail flow touched files").isNotEmpty();
      assertThat(recorder.accesses()).allSatisfy(access -> assertThat(access.mode().readOnly()).as(access.toString()).isTrue());
      assertThat(recorder.violations()).isEmpty();

      recorder.record(project.fixture().root().resolve("kitty-specs/alpha/tasks/WP01-one.md"), Allowlist.OpenMode.WRITE);
      assertThat(recorder.violations()).as("positive control: one write turns the check red").hasSize(1);
    }
  }

  @Test
  void ac16bTheFingerprintOfTheDetailProjectIsIdenticalBeforeAndAfterTheFlowLinksAndRefusedFilesIncluded() throws Exception {
    DetailFlow.Project project = DetailFlow.noTopology();
    Path root = project.fixture().root();
    org.speckitty.missionstatus.testsupport.RouteMarker marker = org.speckitty.missionstatus.testsupport.RouteMarker.create();
    try (var server = DetailFlow.start(project, marker)) {
      List<String> before = Fingerprint.of(root);
      assertThat(before).as("the project holds a refused file (a credential)").anyMatch(entry -> entry.contains("leaky.md"));
      if (before.stream().noneMatch(entry -> entry.startsWith("L "))) {
        org.junit.jupiter.api.Assumptions.abort("symbolic links cannot be made here: the fingerprint of links is not exercised");
      }

      List<String> answers = detailFlow(project, marker, server);

      assertThat(answers).anySatisfy(answer -> assertThat(answer).contains("artifact_secret"));
      assertThat(Fingerprint.of(root)).as("content hash, listing including .lock and temporary names, modification times").isEqualTo(before);

      Files.writeString(root.resolve("kitty-specs/alpha/.lock"), "x");
      assertThat(Fingerprint.of(root)).as("positive control: a stray .lock changes the fingerprint").isNotEqualTo(before);
    }
  }

  private static List<String> detailFlowWithDrain(Boolean drain) throws Exception {
    DetailFlow.Project project = DetailFlow.noTopology();
    Path root = project.fixture().root();
    if (drain != null) {
      Path personal = Files.createDirectories(root.getParent().resolve("personal"));
      Files.writeString(personal.resolve("config.toml"), "[hosted]\ndrain = " + drain + "\n");
      Files.writeString(root.resolve("config.toml"), "[hosted]\ndrain = " + drain + "\n");
      Path config = root.resolve(".kittify/config.yaml");
      Files.writeString(config, Files.readString(config) + "hosted:\n  drain: " + drain + "\n");
    }
    org.speckitty.missionstatus.testsupport.RouteMarker marker = org.speckitty.missionstatus.testsupport.RouteMarker.create();
    try (var server = DetailFlow.start(project, marker)) {
      List<String> answers = detailFlow(project, marker, server);
      assertThat(server.allowlistRecorder().accesses()).as("no recorded read of config.toml").noneMatch(access -> access.path().endsWith("config.toml"));
      return answers;
    }
  }

  @Test
  void ac16cEveryDetailAnswerIsByteIdenticalWithTheDrainKeysBothTrueBothFalseAndBothAbsent() throws Exception {
    List<String> on = detailFlowWithDrain(true);
    List<String> off = detailFlowWithDrain(false);
    List<String> absent = detailFlowWithDrain(null);

    assertThat(on).hasSize(DetailFlow.requests(DetailFlow.noTopology()).size()).hasSameSizeAs(off).hasSameSizeAs(absent);
    for (int i = 0; i < on.size(); i++) {
      assertThat(on.get(i)).as("answer " + i + " drain on / off").isEqualTo(off.get(i));
      assertThat(on.get(i)).as("answer " + i + " drain on / absent").isEqualTo(absent.get(i));
    }
  }
}
