package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.FileSystems;
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
    Assumptions.assumeTrue(FileSystems.getDefault().supportedFileAttributeViews().contains("posix"), "POSIX permissions are unavailable on this file system (Windows)");
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
}
