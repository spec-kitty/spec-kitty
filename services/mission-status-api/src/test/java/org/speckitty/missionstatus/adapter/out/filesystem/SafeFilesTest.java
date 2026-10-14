package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledOnOs;
import org.junit.jupiter.api.condition.OS;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;

/**
 * NOFOLLOW reads and root containment (FR-010, AC-10d). The trees are built in temporary directories; the links at test time.
 * L2 is a symlinked ledger, L9 a symlinked {@code meta.json} or a Mission directory that is a link or leaves the root.
 */
class SafeFilesTest {

  private static final String MISSION = "kitty-specs/m-01ABCDEF";
  private static final String SECRET = "TOP-SECRET-CONTENT";

  @TempDir Path sandbox;
  Path root;
  Path outside;
  RecordingAllowlistAccess recorder;
  SafeFiles files;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    outside = Files.createDirectory(sandbox.resolve("outside"));
    Files.writeString(outside.resolve("secret.txt"), SECRET);
    Files.createDirectories(root.resolve(MISSION));
    recorder = new RecordingAllowlistAccess(root);
    files = new SafeFiles(root, recorder);
  }

  private Path ledger() {
    return root.resolve(MISSION).resolve("status.events.jsonl");
  }

  private Path meta() {
    return root.resolve(MISSION).resolve("meta.json");
  }

  private Kind faultOf(Runnable action) {
    try {
      action.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    throw new AssertionError("no SourceFault");
  }

  // ---- reads: the control and the refusals ---------------------------------------------------------------------------------

  @Test
  void anOrdinaryRegularFileIsReadNormally() throws IOException {
    Files.writeString(ledger(), "{}\n");
    Optional<byte[]> bytes = files.readRegular(ledger(), SafeFiles.SMALL_FILE_MAX, Kind.LEDGER_UNREADABLE, Kind.LEDGER_UNREADABLE);
    assertThat(bytes).hasValueSatisfying(value -> assertThat(new String(value, StandardCharsets.UTF_8)).isEqualTo("{}\n"));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void anAbsentFileIsEmptyNotAFault() {
    assertThat(files.readRegular(ledger(), SafeFiles.SMALL_FILE_MAX, Kind.LEDGER_UNREADABLE, Kind.LEDGER_UNREADABLE)).isEmpty();
    assertThat(files.readRegular(root.resolve("kitty-specs/absent/meta.json"), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).isEmpty();
  }

  @Test
  void aSymlinkedLedgerIsL2AndItsTargetIsNeverRead() {
    SymlinkSupport.link(ledger(), outside.resolve("secret.txt"));
    assertThat(faultOf(() -> files.readRegular(ledger(), SafeFiles.SMALL_FILE_MAX, Kind.LEDGER_UNREADABLE, Kind.LEDGER_UNREADABLE))).isEqualTo(Kind.LEDGER_UNREADABLE);
    assertThat(recorder.accesses()).noneMatch(access -> access.mode() == OpenMode.READ);
  }

  @Test
  void aSymlinkedMetaIsL9AndItsTargetIsNeverRead() {
    SymlinkSupport.link(meta(), outside.resolve("secret.txt"));
    assertThat(faultOf(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))).isEqualTo(Kind.PATH_REFUSED);
    assertThat(recorder.accesses()).noneMatch(access -> access.mode() == OpenMode.READ);
  }

  @Test
  void aLinkInsideTheRootIsRefusedToo() throws IOException {
    Files.writeString(root.resolve("real.json"), "{}");
    SymlinkSupport.link(meta(), root.resolve("real.json"));
    assertThat(faultOf(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aDanglingLinkIsRefusedNotTreatedAsAbsent() {
    SymlinkSupport.link(meta(), outside.resolve("no-such-file"));
    assertThat(faultOf(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aDirectoryWhereAFileShouldBeIsRefusedWithTheRefusalKind() throws IOException {
    Files.createDirectory(meta());
    assertThat(faultOf(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))).isEqualTo(Kind.PATH_REFUSED);
  }

  /** An open for reading blocks on a FIFO with no writer, so the stat must refuse it before any open. */
  @Test
  @EnabledOnOs(OS.LINUX)
  void aFifoWhereAFileShouldBeIsRefusedWithoutBlocking() throws IOException, InterruptedException {
    Process made = new ProcessBuilder("mkfifo", meta().toString()).redirectErrorStream(true).start();
    Assumptions.assumeTrue(made.waitFor() == 0 && !Files.isRegularFile(meta()) && Files.exists(meta(), LinkOption.NOFOLLOW_LINKS), "mkfifo is not available");

    Kind kind = assertTimeoutPreemptively(Duration.ofSeconds(10), () -> faultOf(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)));

    assertThat(kind).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void anOperatingSystemFailureMapsToTheUnreadableKindAndCarriesNoPath() throws IOException {
    Files.writeString(meta(), "{}");
    recorder.failWhen(access -> access.mode() == OpenMode.READ, () -> new AccessDeniedException(meta().toString()));
    assertThatThrownBy(() -> files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))
        .isInstanceOfSatisfying(
            SourceFault.class,
            fault -> {
              assertThat(fault.kind()).isEqualTo(Kind.META_UNPARSEABLE);
              assertThat(fault.getMessage()).doesNotContain(root.toString());
              assertThat(fault.getCause()).isNull();
            });
  }

  @Test
  void aFileLargerThanTheCapIsTheUnreadableKindAndOneAtTheCapIsRead() throws IOException {
    Files.write(meta(), new byte[100]);
    assertThat(files.readRegular(meta(), 100, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE)).hasValueSatisfying(value -> assertThat(value).hasSize(100));
    assertThat(faultOf(() -> files.readRegular(meta(), 99, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE))).isEqualTo(Kind.META_UNPARSEABLE);
  }

  @Test
  void aReadIsOnlyEverRecordedForAnAllowlistedPath() throws IOException {
    Files.writeString(meta(), "{}");
    files.readRegular(meta(), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE);
    assertThat(recorder.accesses()).extracting(Allowlist.Access::pathClass).contains(PathClass.MISSION_META);
    assertThat(recorder.violations()).isEmpty();
  }

  // ---- directories: containment -------------------------------------------------------------------------------------------

  @Test
  void anOrdinaryMissionDirectoryIsServed() {
    assertThat(files.requireContainedDir(root.resolve(MISSION))).isEqualTo(root.resolve(MISSION));
  }

  @Test
  void aMissionDirectoryThatIsGoneIsVanished() {
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve("kitty-specs/gone")))).isEqualTo(Kind.VANISHED);
  }

  @Test
  void aMissionDirectoryThatIsALinkOutsideTheRootIsL9() {
    SymlinkSupport.link(root.resolve("kitty-specs/escape"), outside);
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve("kitty-specs/escape")))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aMissionDirectoryThatIsALinkInsideTheRootIsL9Too() {
    SymlinkSupport.link(root.resolve("kitty-specs/alias"), root.resolve(MISSION));
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve("kitty-specs/alias")))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aMissionDirectoryReachedThroughALinkedKittySpecsThatLeavesTheRootIsL9() throws IOException {
    Files.createDirectories(outside.resolve("specs/m-other"));
    Files.delete(root.resolve(MISSION));
    Files.delete(root.resolve("kitty-specs"));
    SymlinkSupport.link(root.resolve("kitty-specs"), outside.resolve("specs"));
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve("kitty-specs/m-other")))).isEqualTo(Kind.PATH_REFUSED);
  }

  @Test
  void aRegularFileWhereAMissionDirectoryShouldBeIsVanished() throws IOException {
    Files.writeString(root.resolve("kitty-specs/stray"), "x");
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve("kitty-specs/stray")))).isEqualTo(Kind.VANISHED);
  }

  @Test
  void aDirectoryOutsideTheRealRootIsNotContainedAndOneInsideIs() throws IOException {
    Files.createDirectories(root.resolve(".worktrees/x-coord/kitty-specs/m"));
    assertThat(files.isContainedDirectory(root.resolve(".worktrees/x-coord/kitty-specs/m"))).isTrue();
    SymlinkSupport.link(root.resolve(".worktrees/y-coord"), outside);
    assertThat(files.isContainedDirectory(root.resolve(".worktrees/y-coord"))).isFalse();
    assertThat(files.isContainedDirectory(root.resolve(".worktrees/absent"))).isFalse();
  }

  @Test
  void aProjectRootThatCannotBeResolvedIsAnUnreadableDirectory() {
    recorder.failWhen(access -> access.mode() == OpenMode.REALPATH && access.pathClass() == PathClass.PROJECT_ROOT, () -> new IOException("injected"));
    assertThat(faultOf(() -> files.requireContainedDir(root.resolve(MISSION)))).isEqualTo(Kind.DIR_UNREADABLE);
  }
}
