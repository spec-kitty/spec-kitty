package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat.EntryKind;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;

/** The text-read port over a real directory tree: all four operations, every result variant, and the link rules (AC-7.2). */
class FilesystemTextSourceTest {

  private static final String MISSION = "m-01ABCDEF";

  @TempDir Path sandbox;
  Path root;
  Path primary;
  RecordingAllowlistAccess recorder;
  TextSource source;
  FileRef.MissionFile mission;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    primary = Files.createDirectories(root.resolve("kitty-specs").resolve(MISSION));
    Files.writeString(primary.resolve("spec.md"), "# Spec\n");
    Files.createDirectories(primary.resolve("tasks"));
    Files.writeString(primary.resolve("tasks").resolve("WP01-x.md"), "wp one");
    recorder = new RecordingAllowlistAccess(root);
    source = new FilesystemTextSource(root, recorder, NameEncoding.fixed(true));
    mission = new FileRef.MissionFile(new MissionRef(MISSION), RelativePath.ROOT);
  }

  private FileRef.MissionFile at(String path) {
    return new FileRef.MissionFile(new MissionRef(MISSION), RelativePath.of(path));
  }

  private static Path outsideDir(Path sandbox) throws IOException {
    Path outside = Files.createDirectories(sandbox.resolve("outside"));
    Files.writeString(outside.resolve("secret.txt"), "TOP-SECRET");
    return outside;
  }

  // ---- construction --------------------------------------------------------------------------------------------------------

  @Test
  void itIsConstructibleFromAPlainPathWithNoSpring() throws Exception {
    TextSource plain = new FilesystemTextSource(root);
    assertThat(plain.readText(at("spec.md"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("# Spec\n", 7));
    assertThat(java.lang.reflect.Modifier.isPublic(FilesystemTextSource.class.getModifiers())).isTrue();
    assertThat(FilesystemTextSource.class.getConstructor(Path.class)).isNotNull();
    assertThat(FilesystemTextSource.class.getAnnotations()).as("no Spring stereotype: the class is wired by a config class").isEmpty();
  }

  // ---- readText / readBytes ------------------------------------------------------------------------------------------------

  @Test
  void readTextReturnsTheTextAndItsByteSize() throws IOException {
    assumeTrue("UTF-8".equals(System.getProperty("sun.jnu.encoding")));
    Files.writeString(primary.resolve("café.md"), "café", StandardCharsets.UTF_8);
    assertThat(source.readText(at("café.md"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("café", 5));
  }

  @Test
  void aByteOrderMarkIsKeptAndAnEmptyFileIsEmptyText() throws IOException {
    Files.write(primary.resolve("bom.md"), new byte[] {(byte) 0xEF, (byte) 0xBB, (byte) 0xBF, 'a'});
    Files.write(primary.resolve("empty.md"), new byte[0]);
    assertThat(source.readText(at("bom.md"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("﻿a", 4));
    assertThat(source.readText(at("empty.md"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("", 0));
  }

  @Test
  void invalidUtf8IsNotTextAndANulIsDecodedForTheApplicationToJudge() throws IOException {
    Files.write(primary.resolve("bad.md"), new byte[] {'o', 'k', (byte) 0xC3});
    Files.write(primary.resolve("nul.md"), new byte[] {'a', 0, 'b'});
    assertThat(source.readText(at("bad.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextRead.NotText.class);
    assertThat(source.readText(at("nul.md"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("a\u0000b", 3));
  }

  @Test
  void aFileOverTheCapIsOverCapAndTheCapIsTheCallers() throws IOException {
    Files.write(primary.resolve("big.md"), new byte[101]);
    assertThat(source.readText(at("big.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextRead.OverCap.class);
    assertThat(source.readBytes(at("big.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(BytesRead.OverCap.class);
    assertThat(source.readBytes(at("big.md"), 101, ReadScope.ARTIFACT)).isInstanceOf(BytesRead.Bytes.class);
  }

  @Test
  void aMissingFileIsAbsentAndADirectoryIsNotRegular() {
    assertThat(source.readText(at("nope.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextRead.Absent.class);
    assertThat(source.readBytes(at("nope.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(BytesRead.Absent.class);
    assertThat(source.readText(at("tasks"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextRead.NotRegular.class);
    assertThat(source.readBytes(at("tasks"), 100, ReadScope.ARTIFACT)).isInstanceOf(BytesRead.NotRegular.class);
  }

  @Test
  void aPathThroughAFileIsAbsent() {
    assertThat(source.readText(at("spec.md/deeper.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextRead.Absent.class);
    assertThat(source.stat(at("spec.md/deeper.md"), ReadScope.ARTIFACT)).isInstanceOf(EntryStat.Absent.class);
    assertThat(source.list(at("spec.md/deeper"), 10, ReadScope.ARTIFACT)).isInstanceOf(DirListing.Absent.class);
  }

  @Test
  void readBytesReturnsTheRawBytes() throws IOException {
    Files.write(primary.resolve("raw.bin"), new byte[] {1, 2, 3});
    BytesRead read = source.readBytes(at("raw.bin"), 10, ReadScope.AUTHORED);
    assertThat(((BytesRead.Bytes) read).content()).containsExactly(1, 2, 3);
  }

  // ---- links (AC-7.2) ------------------------------------------------------------------------------------------------------

  @Test
  void aLinkInAMiddleComponentIsRefusedAndTheTargetIsNeverRead() throws IOException {
    Path outside = outsideDir(sandbox);
    SymlinkSupport.link(primary.resolve("linkdir"), outside);
    assertThatThrownBy(() -> source.readText(at("linkdir/secret.txt"), 100, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
    assertThatThrownBy(() -> source.readBytes(at("linkdir/secret.txt"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextFault.class);
    assertThatThrownBy(() -> source.stat(at("linkdir/secret.txt"), ReadScope.ARTIFACT)).isInstanceOf(TextFault.class);
    assertThatThrownBy(() -> source.list(at("linkdir/x"), 10, ReadScope.ARTIFACT)).isInstanceOf(TextFault.class);
  }

  @Test
  void aLinkInTheFinalComponentIsRefusedForARead() throws IOException {
    Path outside = outsideDir(sandbox);
    SymlinkSupport.link(primary.resolve("ln.md"), outside.resolve("secret.txt"));
    assertThatThrownBy(() -> source.readText(at("ln.md"), 100, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
    assertThatThrownBy(() -> source.readBytes(at("ln.md"), 100, ReadScope.ARTIFACT)).isInstanceOf(TextFault.class);
  }

  @Test
  void theSamePathWithoutTheLinkIsRead() throws IOException {
    Path real = Files.createDirectory(primary.resolve("realdir"));
    Files.writeString(real.resolve("secret.txt"), "fine");
    assertThat(source.readText(at("realdir/secret.txt"), 100, ReadScope.ARTIFACT)).isEqualTo(new TextRead.Text("fine", 4));
  }

  @Test
  void aStatOfALinkReportsALinkAndNeverFollowsIt() throws IOException {
    Path outside = outsideDir(sandbox);
    SymlinkSupport.link(primary.resolve("ln.md"), outside.resolve("secret.txt"));
    SymlinkSupport.link(primary.resolve("lndir"), outside);
    assertThat(((EntryStat.Present) source.stat(at("ln.md"), ReadScope.ARTIFACT)).kind()).isEqualTo(EntryKind.SYMLINK);
    assertThat(((EntryStat.Present) source.stat(at("lndir"), ReadScope.ARTIFACT)).kind()).isEqualTo(EntryKind.SYMLINK);
  }

  @Test
  void aMissionDirectoryThatIsALinkIsRefusedAndOneThatVanishedIsVanished() throws IOException {
    Path outside = Files.createDirectories(sandbox.resolve("outside-mission"));
    SymlinkSupport.link(root.resolve("kitty-specs").resolve("m-linked"), outside);
    FileRef.MissionFile linked = new FileRef.MissionFile(new MissionRef("m-linked"), RelativePath.of("a.md"));
    assertThatThrownBy(() -> source.readText(linked, 10, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
    FileRef.MissionFile gone = new FileRef.MissionFile(new MissionRef("m-gone"), RelativePath.of("a.md"));
    assertThatThrownBy(() -> source.readText(gone, 10, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.VANISHED));
    FileRef.MissionFile unsafe = new FileRef.MissionFile(new MissionRef("../x"), RelativePath.of("a.md"));
    assertThatThrownBy(() -> source.readText(unsafe, 10, ReadScope.ARTIFACT)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(TextFault.Kind.PATH_REFUSED));
  }

  // ---- stat ----------------------------------------------------------------------------------------------------------------

  @Test
  void statDistinguishesFileDirectoryAndAbsent() {
    EntryStat.Present file = (EntryStat.Present) source.stat(at("spec.md"), ReadScope.AUTHORED);
    assertThat(file.kind()).isEqualTo(EntryKind.FILE);
    assertThat(file.sizeBytes()).isEqualTo(7);
    assertThat(file.modifiedEpochSecond()).isPositive();
    assertThat(((EntryStat.Present) source.stat(at("tasks"), ReadScope.AUTHORED)).kind()).isEqualTo(EntryKind.DIRECTORY);
    assertThat(((EntryStat.Present) source.stat(mission, ReadScope.AUTHORED)).kind()).isEqualTo(EntryKind.DIRECTORY);
    assertThat(source.stat(at("nope.md"), ReadScope.AUTHORED)).isInstanceOf(EntryStat.Absent.class);
  }

  // ---- list ----------------------------------------------------------------------------------------------------------------

  @Test
  void listReturnsNamesWithinTheLimitAndSaysWhetherMoreExisted() throws IOException {
    for (int i = 0; i < 5; i++) {
      Files.writeString(primary.resolve("f" + i + ".md"), "x");
    }
    DirListing.Names all = (DirListing.Names) source.list(mission, 100, ReadScope.ARTIFACT);
    assertThat(all.names()).containsExactlyInAnyOrder("f0.md", "f1.md", "f2.md", "f3.md", "f4.md", "spec.md", "tasks");
    assertThat(all.limitReached()).isFalse();
    assertThat(all.trustworthy()).isTrue();
    DirListing.Names exact = (DirListing.Names) source.list(mission, 7, ReadScope.ARTIFACT);
    assertThat(exact.names()).hasSize(7);
    assertThat(exact.limitReached()).as("exactly the limit: nothing more").isFalse();
    DirListing.Names limited = (DirListing.Names) source.list(mission, 3, ReadScope.ARTIFACT);
    assertThat(limited.names()).hasSize(3);
    assertThat(limited.limitReached()).isTrue();
  }

  @Test
  void listOfAFileIsNotADirectoryAndOfAMissingPathIsAbsent() {
    assertThat(source.list(at("spec.md"), 10, ReadScope.ARTIFACT)).isInstanceOf(DirListing.NotADirectory.class);
    assertThat(source.list(at("nope"), 10, ReadScope.ARTIFACT)).isInstanceOf(DirListing.Absent.class);
  }

  @Test
  void theTrustworthyFlagIsTheHostProbeAnswer() {
    TextSource untrusted = new FilesystemTextSource(root, recorder, NameEncoding.fixed(false));
    assertThat(((DirListing.Names) untrusted.list(mission, 10, ReadScope.ARTIFACT)).trustworthy()).isFalse();
  }

  @Test
  void aListingOfAProjectRootDirectoryUsesTheProjectFileReference() throws IOException {
    Files.createDirectories(root.resolve("docs"));
    Files.writeString(root.resolve("docs").resolve("a.md"), "x");
    DirListing.Names names = (DirListing.Names) source.list(new FileRef.ProjectFile(RelativePath.of("docs")), 10, ReadScope.AUTHORED);
    assertThat(names.names()).containsExactly("a.md");
    assertThat(source.readText(new FileRef.ProjectFile(RelativePath.of("docs/a.md")), 10, ReadScope.AUTHORED)).isEqualTo(new TextRead.Text("x", 1));
  }

  // ---- the fence -----------------------------------------------------------------------------------------------------------

  @Test
  void anArtifactWalkRecordsOnlyArtifactAccessesAndNoViolation() throws IOException {
    Files.createDirectories(primary.resolve("notes"));
    Files.writeString(primary.resolve("notes").resolve("a.md"), "x");
    source.list(mission, 100, ReadScope.ARTIFACT);
    source.list(at("notes"), 100, ReadScope.ARTIFACT);
    source.stat(at("notes/a.md"), ReadScope.ARTIFACT);
    source.readText(at("notes/a.md"), 100, ReadScope.ARTIFACT);
    source.readText(at("spec.md"), 100, ReadScope.ARTIFACT);
    assertThat(recorder.violations()).isEmpty();
    assertThat(recorder.scopedAccesses()).isNotEmpty().allSatisfy(access -> assertThat(access.scope()).isIn(ReadScope.ARTIFACT, ReadScope.AUTHORED));
    assertThat(recorder.scopedAccesses().stream().filter(access -> access.scope() == ReadScope.ARTIFACT).map(RecordingAllowlistAccess.ScopedAccess::pathClass).distinct().toList())
        .containsExactlyInAnyOrder(Allowlist.PathClass.ARTIFACT_DIR, Allowlist.PathClass.ARTIFACT_FILE);
  }

  @Test
  void anAuthoredReadOfAWorkPackageFileAndAListingOfTasksAreWithinTheFence() {
    source.list(at("tasks"), 100, ReadScope.AUTHORED);
    source.stat(at("tasks/WP01-x.md"), ReadScope.AUTHORED);
    source.readText(at("tasks/WP01-x.md"), 100, ReadScope.AUTHORED);
    assertThat(recorder.violations()).isEmpty();
    assertThat(recorder.scopedAccesses().stream().map(RecordingAllowlistAccess.ScopedAccess::pathClass).distinct().toList()).contains(Allowlist.PathClass.TASKS_DIR, Allowlist.PathClass.WP_FILE);
  }

  @Test
  void aReadOfPlanningFileUnderAuthoredIsTheDeliberateViolationTheFenceCatches() {
    source.readText(at("spec.md"), 100, ReadScope.AUTHORED);
    assertThat(recorder.violations()).isNotEmpty();
  }

  @Test
  void theNamesOfALongListingNeverExceedLimitPlusOneInMemory() throws IOException {
    for (int i = 0; i < 25; i++) {
      Files.writeString(primary.resolve("n" + i), "x");
    }
    DirListing.Names names = (DirListing.Names) source.list(mission, 10, ReadScope.ARTIFACT);
    assertThat(names.names()).hasSize(10);
    assertThat(names.limitReached()).isTrue();
    List<String> sorted = new ArrayList<>(names.names());
    assertThat(sorted).doesNotHaveDuplicates();
    assertThat(Arrays.asList(primary.toFile().list())).containsAll(sorted);
  }
}
