package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The flow-level allowlist and read-only checks (AC-10a, AC-16a..16d): the full fixture flow through the real service over the real
 * source, under the recorder. Every access is on the allowlist and read-only, the coordination Mission is read from its coordination
 * directory only, and the project is the same after as before. The HTTP flow is re-run in WP20.
 */
class FilesystemMissionEventSourceAllowlistFlowTest {

  private static final String COORD_NAME = AdapterServiceHarness.BETA;
  private static final String COORD_DIR = ".worktrees/" + COORD_NAME + "-coord/kitty-specs/" + COORD_NAME;

  @TempDir Path sandbox;
  Path root;
  AdapterServiceHarness harness;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    buildProject(root, "");
    harness = new AdapterServiceHarness(root);
  }

  /** A single-branch Mission, a coordination Mission (with decoys on the primary side), and files the service must never open. */
  static void buildProject(Path root, String configExtra) {
    AdapterServiceHarness.healthyProject(root);
    AdapterServiceHarness.write(root.resolve(".kittify/config.yaml"), "project:\n  slug: fixture-project\n" + configExtra);

    Path alpha = AdapterServiceHarness.mission(root, AdapterServiceHarness.ALPHA, Rows.ALPHA_ID, "2026-09-01T09:00:00+00:00", AdapterServiceHarness.laneRow(1, "WP01", "planned", "claimed"));
    AdapterServiceHarness.write(alpha.resolve("tasks/WP01.md"), "---\nwork_package_id: WP01\n---\n");
    AdapterServiceHarness.write(alpha.resolve("spec.md"), "spec");
    AdapterServiceHarness.write(alpha.resolve("plan.md"), "plan");
    AdapterServiceHarness.write(alpha.resolve("status.json"), "{}");

    Path beta = root.resolve("kitty-specs").resolve(COORD_NAME);
    AdapterServiceHarness.write(
        beta.resolve("meta.json"),
        "{\"mission_id\":\"" + Rows.BETA_ID + "\",\"mission_slug\":\"" + COORD_NAME + "\",\"target_branch\":\"main\",\"created_at\":\"2026-09-02T09:00:00+00:00\","
            + "\"topology\":\"coord\",\"coordination_branch\":\"kitty/mission-" + COORD_NAME + "\"}");
    AdapterServiceHarness.write(beta.resolve("status.events.jsonl"), AdapterServiceHarness.laneRow(1, "WP09", "planned", "claimed"));
    Path coord = root.resolve(COORD_DIR);
    AdapterServiceHarness.write(coord.resolve("status.events.jsonl"), AdapterServiceHarness.laneRow(1, "WP01", "planned", "claimed") + AdapterServiceHarness.laneRow(2, "WP01", "claimed", "in_progress"));
    AdapterServiceHarness.write(coord.resolve("meta.json"), "{\"decoy\":\"coordination copy\"}");
    AdapterServiceHarness.write(coord.resolve("tasks/WP01.md"), "decoy");
  }

  /** The whole fixture flow: all three routes through {@code MissionStatusQuery}, plus a Mission-scoped and an unscoped stream. */
  static void runFlow(AdapterServiceHarness h) throws Exception {
    h.query.project();
    h.overviews();
    h.query.changesSince(new StreamScope.All(), Optional.empty());
    for (String id : List.of(Rows.ALPHA_ID, Rows.BETA_ID)) {
      h.query.changesSince(new StreamScope.OneMission(new MissionId(id)), Optional.of(StreamCursor.start()));
      try (Subscription scoped = h.query.subscribe(new StreamScope.OneMission(new MissionId(id)), Optional.of(StreamCursor.start()))) {
        h.executor.tick();
        h.clock.advance(java.time.Duration.ofSeconds(2));
        h.executor.tick();
      }
    }
    try (Subscription all = h.query.subscribe(new StreamScope.All(), Optional.empty())) {
      h.executor.tick();
    }
  }

  // ---- AC-10a -------------------------------------------------------------------------------------------------------------------

  @Test
  void everyReadOfTheFlowIsOnTheAllowlistAndReadsTheRightDirectory() throws Exception {
    runFlow(harness);

    List<Access> accesses = harness.recorder.accesses();
    assertThat(accesses).isNotEmpty();
    assertThat(harness.recorder.violations()).as("accesses outside the allowlist").isEmpty();
    assertThat(wrongDirectory(accesses)).as("reads from the wrong directory").isEmpty();

    List<String> paths = accesses.stream().filter(a -> a.mode() == OpenMode.READ).map(Access::path).distinct().toList();
    assertThat(paths)
        .contains(
            ".kittify/config.yaml",
            ".kittify/metadata.yaml",
            ".git/HEAD",
            "kitty-specs/" + AdapterServiceHarness.ALPHA + "/meta.json",
            "kitty-specs/" + AdapterServiceHarness.ALPHA + "/status.events.jsonl",
            "kitty-specs/" + COORD_NAME + "/meta.json",
            COORD_DIR + "/status.events.jsonl");
    assertThat(paths).noneMatch(path -> path.endsWith(".md") || path.endsWith("status.json") || path.endsWith("config.toml"));
  }

  /** A read (not a stat) of the coordination copy of {@code meta.json}, or of the primary ledger of the coordination Mission. */
  static List<String> wrongDirectory(List<Access> accesses) {
    List<String> wrong = new ArrayList<>();
    for (Access access : accesses) {
      String path = access.path();
      // DD-105: the coordination meta.json is stat-ed for its existence; only an open of it is a wrong read
      boolean coordinationMeta = access.mode() != OpenMode.STAT && path.startsWith(".worktrees/") && path.endsWith("/meta.json");
      boolean primaryLedgerOfCoordMission = path.equals("kitty-specs/" + COORD_NAME + "/status.events.jsonl");
      if (coordinationMeta || primaryLedgerOfCoordMission) {
        wrong.add(access.mode() + " " + path);
      }
    }
    return wrong;
  }

  @Test
  void aReadOfAFileOnNoClassIsFlaggedByTheRecorderPositiveControl() throws Exception {
    runFlow(harness);
    harness.recorder.record(root.resolve("kitty-specs").resolve(AdapterServiceHarness.ALPHA).resolve("research/notes.md"), OpenMode.READ);
    assertThat(harness.recorder.violations()).hasSize(1).first().satisfies(v -> assertThat(v.access().path()).endsWith("research/notes.md"));
  }

  @Test
  void aReadOfTheCoordinationMetaJsonIsFlaggedByTheRecorderPositiveControl() throws Exception {
    runFlow(harness);
    harness.recorder.record(root.resolve(COORD_DIR).resolve("meta.json"), OpenMode.READ);
    assertThat(harness.recorder.violations()).hasSize(1);
    assertThat(wrongDirectory(harness.recorder.accesses())).hasSize(1);
  }

  @Test
  void aReadOfThePrimaryLedgerOfTheCoordinationMissionIsFlaggedAsTheWrongDirectory() throws Exception {
    runFlow(harness);
    harness.recorder.record(root.resolve("kitty-specs").resolve(COORD_NAME).resolve("status.events.jsonl"), OpenMode.READ);
    assertThat(harness.recorder.violations()).as("on the allowlist as a class").isEmpty();
    assertThat(wrongDirectory(harness.recorder.accesses())).hasSize(1);
  }

  // ---- AC-16a -------------------------------------------------------------------------------------------------------------------

  @Test
  void noAccessOfTheFlowIsAnythingButReadOnly() throws Exception {
    runFlow(harness);
    assertThat(harness.recorder.accesses()).allMatch(access -> access.mode().readOnly(), "read-only mode");
    assertThat(harness.recorder.accesses()).extracting(Access::mode).doesNotContain(OpenMode.CREATE, OpenMode.WRITE, OpenMode.APPEND, OpenMode.TRUNCATE, OpenMode.DELETE_ON_CLOSE, OpenMode.RENAME, OpenMode.DELETE);
  }

  @Test
  void aWriteOpenIsFlaggedByTheRecorderPositiveControl() throws Exception {
    runFlow(harness);
    harness.recorder.record(root.resolve("kitty-specs").resolve(AdapterServiceHarness.ALPHA).resolve("status.events.jsonl"), OpenMode.APPEND);
    assertThat(harness.recorder.violations()).hasSize(1).first().satisfies(v -> assertThat(v.reason()).contains("not read-only"));
  }

  // ---- AC-16c -------------------------------------------------------------------------------------------------------------------

  @Test
  void theDrainSettingChangesNothingAndThePersonalConfigIsNeverRead() throws Exception {
    List<String> answers = new ArrayList<>();
    for (String drain : new String[] {"hosted:\n  drain: true\n", "hosted:\n  drain: false\n", ""}) {
      Path project = Files.createDirectory(sandbox.resolve("drain-" + answers.size()));
      Path personal = sandbox.resolve("home-" + answers.size() + "/spec-kitty/config.toml");
      AdapterServiceHarness.write(personal, "[hosted]\ndrain = true\n");
      AdapterServiceHarness.write(project.resolve("config.toml"), "[hosted]\ndrain = true\n");
      buildProject(project, drain);
      AdapterServiceHarness h = new AdapterServiceHarness(project);
      runFlow(h);
      assertThat(h.recorder.accesses()).as("drain=[" + drain.strip() + "]").noneMatch(access -> access.path().endsWith("config.toml"));
      assertThat(h.recorder.violations()).isEmpty();
      answers.add(h.query.project() + "|" + h.overviews());
    }
    assertThat(answers).hasSize(3);
    assertThat(answers.get(1)).isEqualTo(answers.get(0));
    assertThat(answers.get(2)).isEqualTo(answers.get(0));
  }

  // ---- AC-16b -------------------------------------------------------------------------------------------------------------------

  @Test
  void theProjectIsTheSameAfterTheFlowAsBefore() throws Exception {
    List<String> before = fingerprint(root);
    runFlow(harness);
    assertThat(fingerprint(root)).as("content hash, listing names and counts (lock and temp names included), modification times").isEqualTo(before);
  }

  /** Every entry under {@code root}: relative path, type, size, modification time, and for a file its SHA-256. */
  static List<String> fingerprint(Path root) {
    try (Stream<Path> walk = Files.walk(root)) {
      List<Path> all = walk.sorted().toList();
      List<String> lines = new ArrayList<>();
      for (Path path : all) {
        String relative = root.relativize(path).toString();
        if (Files.isDirectory(path)) {
          try (Stream<Path> children = Files.list(path)) {
            lines.add("D " + relative + " children=" + children.map(child -> child.getFileName().toString()).sorted().toList() + " mtime=" + Files.getLastModifiedTime(path));
          }
        } else {
          lines.add("F " + relative + " size=" + Files.size(path) + " mtime=" + Files.getLastModifiedTime(path) + " sha=" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))));
        }
      }
      return lines;
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    } catch (java.security.NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  // ---- AC-16d -------------------------------------------------------------------------------------------------------------------

  @Test
  void aProjectWhoseDirectoriesAreReadOnlyIsServedTheSame() throws Exception {
    assumeTrue(FileSystems.getDefault().supportedFileAttributeViews().contains("posix"), "POSIX permissions are unavailable on this file system (Windows)");
    String expected = harness.query.project() + "|" + harness.overviews();
    List<Path> directories;
    try (Stream<Path> walk = Files.walk(root)) {
      directories = walk.filter(Files::isDirectory).toList();
    }
    Set<PosixFilePermission> readOnly = java.nio.file.attribute.PosixFilePermissions.fromString("r-xr-xr-x");
    Set<PosixFilePermission> normal = java.nio.file.attribute.PosixFilePermissions.fromString("rwxr-xr-x");
    try {
      try {
        for (Path directory : directories) {
          Files.setPosixFilePermissions(directory, readOnly);
        }
      } catch (UnsupportedOperationException notPosix) {
        skip("the file system has no POSIX permissions");
      }
      // Enforcement test: a root user, or a file system that ignores the bits, can still create a file.
      Path probe = root.resolve("write-probe");
      boolean enforced;
      try {
        Files.createFile(probe);
        Files.delete(probe);
        enforced = false;
      } catch (IOException denied) {
        enforced = true;
      }
      if (!enforced) {
        skip("read-only directories are not enforced here (running as root, or a file system that ignores permissions)");
      }
      AdapterServiceHarness readOnlyRun = new AdapterServiceHarness(root);
      assertThat(readOnlyRun.query.project() + "|" + readOnlyRun.overviews()).isEqualTo(expected);
      assertThat(readOnlyRun.recorder.violations()).isEmpty();
    } finally {
      for (Path directory : directories) {
        Files.setPosixFilePermissions(directory, normal);
      }
    }
  }

  private static void skip(String reason) {
    String line = "NOT RUN ON THIS LEG: " + reason;
    System.out.println(line);
    assumeTrue(false, line);
  }
}
