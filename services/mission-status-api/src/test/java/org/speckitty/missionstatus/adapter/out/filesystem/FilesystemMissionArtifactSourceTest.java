package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.util.List;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactBytes;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactFile;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;

/** The artifact source over real trees: the Mission index, the link rules, the walk, the bounded read and the artifact allowlist. */
class FilesystemMissionArtifactSourceTest {

  private static final String ID_A = "01J01000000000000000000001";
  private static final String ID_B = "01J01000000000000000000002";
  private static final MissionRef ALPHA = new MissionRef("alpha-01J01000");

  @TempDir Path root;
  private RecordingAllowlistAccess recorder;
  private FilesystemMissionArtifactSource source;
  private Path alpha;

  @BeforeEach
  void setUp() {
    recorder = new RecordingAllowlistAccess(root);
    source = new FilesystemMissionArtifactSource(root, recorder);
    alpha = AdapterServiceHarness.mission(root, ALPHA.name(), ID_A, "2026-09-01T10:00:00+00:00", "");
  }

  private List<String> artifactViolations() {
    return ArtifactAllowlist.violations(recorder.accesses().stream().map(access -> new ArtifactAllowlist.Access(access.path(), access.mode())).toList());
  }

  @Test
  void aMissionIsFoundByItsIdAndTheFirstDirectoryInCodePointOrderWins() {
    AdapterServiceHarness.mission(root, "zeta", ID_B, "2026-09-01T10:00:00+00:00", null);
    AdapterServiceHarness.mission(root, "beta-copy", ID_A, "2026-09-01T10:00:00+00:00", null);
    assertThat(source.findMission(ID_A)).contains(ALPHA);
    assertThat(source.findMission(ID_B)).contains(new MissionRef("zeta"));
    assertThat(source.findMission("01J01000000000000000000009")).isEmpty();
    assertThat(artifactViolations()).isEmpty();
  }

  @Test
  void aMetaJsonThatCannotBeUsedIsSkippedNotFatal() {
    AdapterServiceHarness.write(root.resolve("kitty-specs/aa-broken/meta.json"), "{not json");
    AdapterServiceHarness.write(root.resolve("kitty-specs/ab-list/meta.json"), "[1]");
    AdapterServiceHarness.write(root.resolve("kitty-specs/ac-number/meta.json"), "{\"mission_id\": 7}");
    AdapterServiceHarness.write(root.resolve("kitty-specs/ad-file"), "a file, not a directory");
    assertThat(source.findMission(ID_A)).contains(ALPHA);
  }

  @Test
  void anUnlistableSpecsDirectoryMakesEveryMissionUnknown() {
    recorder.failWhen(access -> access.path().equals("kitty-specs") && access.mode() == Allowlist.OpenMode.LIST, () -> new IOException("injected"));
    assertThat(source.findMission(ID_A)).isEmpty();
  }

  @Test
  void theMissionDirectoryMustBeARealDirectoryInsideTheRoot() throws IOException {
    assertThat(source.missionDirPresent(ALPHA)).isTrue();
    assertThat(source.missionDirPresent(new MissionRef("gone"))).isFalse();
    Path outside = Files.createTempDirectory("outside-mission");
    SymlinkSupport.link(root.resolve("kitty-specs/linked"), outside);
    assertThat(source.missionDirPresent(new MissionRef("linked"))).isFalse();
  }

  @Test
  void aMissionDirectoryThatCannotBeStatedIsAFault() {
    recorder.failWhen(access -> access.path().equals("kitty-specs/" + ALPHA.name()) && access.mode() == Allowlist.OpenMode.STAT, () -> new IOException("injected"));
    assertThatThrownBy(() -> source.missionDirPresent(ALPHA)).isInstanceOf(SourceFault.class).extracting(fault -> ((SourceFault) fault).kind()).isEqualTo(SourceFault.Kind.DIR_UNREADABLE);
  }

  @Test
  void theWalkFindsRegularFilesAndNeverFollowsOrEntersALink() throws IOException {
    AdapterServiceHarness.write(alpha.resolve("spec.md"), "spec");
    AdapterServiceHarness.write(alpha.resolve("research/deep/notes.md"), "notes");
    AdapterServiceHarness.write(alpha.resolve("tasks/WP01-x.md"), "prompt");
    Path outside = Files.createTempDirectory("outside-tree");
    AdapterServiceHarness.write(outside.resolve("secret.md"), "outside");
    SymlinkSupport.link(alpha.resolve("linked-dir"), outside);
    SymlinkSupport.link(alpha.resolve("linked-file.md"), outside.resolve("secret.md"));
    assertThat(source.walk(ALPHA)).containsExactlyInAnyOrder("meta.json", "status.events.jsonl", "spec.md", "research/deep/notes.md", "tasks/WP01-x.md");
    assertThat(recorder.accesses()).noneMatch(access -> access.path().contains("secret"));
    assertThat(artifactViolations()).isEmpty();
  }

  @Test
  void theWalkNeverListsAFifo() throws Exception {
    Path fifo = alpha.resolve("pipe");
    Process made = new ProcessBuilder("mkfifo", fifo.toString()).redirectErrorStream(true).start();
    Assumptions.assumeTrue(made.waitFor() == 0 && Files.exists(fifo, LinkOption.NOFOLLOW_LINKS), "mkfifo is not available");
    assertThat(source.walk(ALPHA)).doesNotContain("pipe");
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "pipe")).isFalse();
  }

  @Test
  void aDirectoryThatCannotBeListedIsAFaultAndAVanishedOneIsEmpty() {
    AdapterServiceHarness.write(alpha.resolve("research/notes.md"), "notes");
    recorder.failWhen(access -> access.path().endsWith("/research") && access.mode() == Allowlist.OpenMode.LIST, () -> new IOException("injected"));
    assertThatThrownBy(() -> source.walk(ALPHA)).isInstanceOf(SourceFault.class);
    recorder.failWhen(access -> access.path().endsWith("/research") && access.mode() == Allowlist.OpenMode.LIST, () -> new java.nio.file.NoSuchFileException("gone"));
    assertThat(source.walk(ALPHA)).doesNotContain("research/notes.md");
  }

  @Test
  void eligibilityLooksAtEveryComponentWithoutFollowing() throws IOException {
    AdapterServiceHarness.write(alpha.resolve("contracts/api.yaml"), "a: 1");
    Path outside = Files.createTempDirectory("outside-contracts");
    AdapterServiceHarness.write(outside.resolve("api.yaml"), "b: 2");
    SymlinkSupport.link(alpha.resolve("linked"), outside);
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "contracts/api.yaml")).isTrue();
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "linked/api.yaml")).isFalse();
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "contracts")).isFalse();
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "missing.md")).isFalse();
    assertThat(source.isRegularFileWithoutLinks(ALPHA, "contracts/api.yaml/inner")).isFalse();
  }

  @Test
  void eligibilityRaisesAFaultTheOperatingSystemWillNotAnswer() {
    AdapterServiceHarness.write(alpha.resolve("spec.md"), "spec");
    recorder.failWhen(access -> access.path().endsWith("/spec.md"), () -> new IOException("injected"));
    assertThatThrownBy(() -> source.isRegularFileWithoutLinks(ALPHA, "spec.md")).isInstanceOf(SourceFault.class);
  }

  @Test
  void statGivesTheSizeAndTheFlooredModificationSecond() throws IOException {
    Path spec = alpha.resolve("spec.md");
    AdapterServiceHarness.write(spec, "12345");
    Files.setLastModifiedTime(spec, FileTime.fromMillis(1_758_537_000_900L));
    assertThat(source.stat(ALPHA, "spec.md")).contains(new ArtifactFile(5, 1_758_537_000L));
    assertThat(source.stat(ALPHA, "missing.md")).isEmpty();
  }

  @Test
  void theBoundedReadTakesTheSizeFromTheOpenHandleAndReadsAtMostCapPlusOne() {
    AdapterServiceHarness.write(alpha.resolve("small.md"), "hello");
    AdapterServiceHarness.writeBytes(alpha.resolve("big.md"), new byte[11]);
    assertThat(source.read(ALPHA, "small.md", 10)).isInstanceOfSatisfying(ArtifactBytes.Content.class, content -> {
      assertThat(content.sizeBytes()).isEqualTo(5);
      assertThat(content.data()).containsExactly('h', 'e', 'l', 'l', 'o');
    });
    assertThat(source.read(ALPHA, "big.md", 10)).isEqualTo(new ArtifactBytes.TooLarge(11));
    assertThat(source.read(ALPHA, "missing.md", 10)).isInstanceOf(ArtifactBytes.Unreadable.class);
    assertThat(source.read(ALPHA, "research", 10)).isInstanceOf(ArtifactBytes.Unreadable.class);
    assertThat(artifactViolations()).isEmpty();
  }

  @Test
  void theBoundedReadNeverFollowsAFinalLink() throws IOException {
    Path outside = Files.createTempDirectory("outside-read");
    AdapterServiceHarness.write(outside.resolve("x.md"), "outside");
    SymlinkSupport.link(alpha.resolve("link.md"), outside.resolve("x.md"));
    assertThat(source.read(ALPHA, "link.md", 100)).isInstanceOf(ArtifactBytes.Unreadable.class);
  }

  @Test
  void theStatusRecordsAreStatedNeverRead() {
    AdapterServiceHarness.write(alpha.resolve("status.json"), "{}");
    source.walk(ALPHA);
    assertThat(artifactViolations()).isEmpty();
    recorder.clear();
    recorder.record(alpha.resolve("status.json"), Allowlist.OpenMode.READ);
    assertThat(artifactViolations()).hasSize(1);
  }

  @Test
  void theEventSourceAllowlistIsUnchanged() {
    assertThat(Allowlist.classify(root, alpha.resolve("spec.md"))).isEmpty();
    assertThat(ArtifactAllowlist.classify("kitty-specs/m/spec.md")).contains(ArtifactAllowlist.PathClass.MISSION_ENTRY);
    assertThat(ArtifactAllowlist.classify("kitty-specs/m/STATUS.JSON")).contains(ArtifactAllowlist.PathClass.STATUS_RECORD);
    assertThat(ArtifactAllowlist.classify(".kittify/config.yaml")).isEmpty();
    assertThat(ArtifactAllowlist.classify("kitty-specs/m/../x")).isEmpty();
  }
}
