package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory.Built;

/**
 * The shared plumbing of the golden suite (T048): the static fixture tree is copied into a scratch directory and materialised by the
 * same project-header step the Python side runs, with no git binary, then served by the real service over the real adapter.
 */
class FilesystemFixtureFactoryTest {

  private static TreeFixture fixture(String tag, String name) {
    return ConformanceTree.fixturesOf(tag).stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
  }

  private static Path materialise(TreeFixture fixture) throws IOException {
    Path root = Files.createDirectories(ScratchDirs.create().resolve("project"));
    ProjectHeaderMaterialisation.materialise(fixture.dir(), root);
    return root;
  }

  static Stream<TreeFixture> projectHeaderFixtures() {
    return ConformanceTree.fixturesOf("project-header").stream();
  }

  /** {@code ref: refs/heads/<name>\n} gives the name; anything else (a detached HEAD) gives none. */
  private static String branchOf(String headText) {
    String line = headText.strip();
    return line.startsWith("ref: refs/heads/") ? line.substring("ref: refs/heads/".length()) : null;
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("projectHeaderFixtures")
  void theMaterialisedHeadHoldsExactlyTheManifestHeadText(TreeFixture fixture) throws IOException {
    Path root = materialise(fixture);

    if (fixture.headText() == null) {
      assertThat(root.resolve(".git")).as("a fixture without a HEAD text installs no .git").doesNotExist();
      return;
    }
    Path git = root.resolve(".git");
    Path head = Files.isDirectory(git) ? git.resolve("HEAD") : root.resolve("gitdir-target").resolve("HEAD");
    String installed = Files.readString(head, StandardCharsets.UTF_8);

    assertThat(installed).isEqualTo(fixture.headText());
    assertThat(branchOf(installed)).isEqualTo(branchOf(fixture.headText()));
    if (fixture.name().equals("git-pointer-file")) {
      assertThat(git).as("a pointer fixture installs .git as a regular file").isRegularFile();
      assertThat(Files.readString(git)).startsWith("gitdir:");
    }
  }

  @Test
  void aFixtureThatPythonProvisionsAsAGitRepositoryGetsTheHeadOfGitInitMain() throws IOException {
    // `git init -b main` is how the oracle run provisions a coordination worktree, a husk or a declared coordination branch; the
    // golden therefore records currentBranch "main". The service reads no git, so the materialisation installs only that HEAD.
    for (TreeFixture fixture : List.of(fixture("coordination", "coordinated-mission"), fixture("coordination", "coord-worktree-absent"), fixture("coord-husk", "husk-beside-single-branch-and-lanes"))) {
      Path root = materialise(fixture);
      assertThat(Files.readString(root.resolve(".git/HEAD"), StandardCharsets.UTF_8)).as(fixture.key()).isEqualTo("ref: refs/heads/main\n");
    }
    for (TreeFixture fixture : List.of(fixture("interleaved", "two-missions"), fixture("absent-topology", "valid-and-corrupt-lanes"), fixture("no-ledger", "plain-and-discarded"))) {
      assertThat(materialise(fixture).resolve(".git")).as(fixture.key() + " is not a git fixture").doesNotExist();
    }
  }

  @Test
  void aFixtureWithItsOwnHeadKeepsIt() throws IOException {
    Path root = materialise(fixture("project-header", "unborn-branch"));

    assertThat(Files.readString(root.resolve(".git/HEAD"), StandardCharsets.UTF_8)).isEqualTo("ref: refs/heads/unborn/topic\n");
  }

  @Test
  void theProvisioningInputsAreNotCopiedIntoTheProjectRoot() throws IOException {
    Path root = materialise(fixture("coordination", "coordinated-mission"));

    for (String name : List.of("golden", "HEAD", "GITDIR_POINTER", "gitdir-target", "coord-worktree", "husk-worktree", "SYMLINK_PLAN", "outside")) {
      assertThat(root.resolve(name)).as(name).doesNotExist();
    }
    assertThat(root.resolve("kitty-specs/coordinated-01J03000/meta.json")).isRegularFile();
  }

  @Test
  void aCoordinationWorktreeIsInstalledAtTheComposedName() throws IOException {
    Path root = materialise(fixture("coordination", "coordinated-mission"));

    // <slug>-<mid8>-coord, and the slug already ends with the mid8 so the name is not doubled
    assertThat(root.resolve(".worktrees/coordinated-01J03000-coord/kitty-specs/coordinated-01J03000/status.events.jsonl")).isRegularFile();
    assertThat(ProjectHeaderMaterialisation.coordinationDirName("coordinated-01J03000", "01J03000")).isEqualTo("coordinated-01J03000-coord");
    assertThat(ProjectHeaderMaterialisation.coordinationDirName("plain", "01J03000")).isEqualTo("plain-01J03000-coord");
  }

  @Test
  void aHuskIsInstalledAtTheSamePathAsAnUnregisteredDirectory() throws IOException {
    Path root = materialise(fixture("coord-husk", "husk-beside-single-branch-and-lanes"));

    assertThat(root.resolve(".worktrees/husk-single-01J05000-coord/kitty-specs/husk-single-01J05000/status.events.jsonl")).isRegularFile();
    assertThat(root.resolve(".worktrees/husk-lanes-01J06000-coord/kitty-specs/husk-lanes-01J06000/status.events.jsonl")).isRegularFile();
    assertThat(root.resolve(".worktrees/husk-single-01J05000-coord/.git")).as("no git is run, so nothing registers it").doesNotExist();
  }

  @Test
  void aSymlinkPlanCreatesLinksAtTestTime() throws IOException {
    Path root = materialise(fixture("symlink", "symlinked-ledger"));
    Path link = root.resolve("kitty-specs/symlink-symlinked-ledger/status.events.jsonl");

    assertThat(Files.isSymbolicLink(link)).isTrue();
    assertThat(Files.readSymbolicLink(link).toString()).isEqualTo("status.events.real.jsonl");
    assertThat(root.resolve("SYMLINK_PLAN")).doesNotExist();
  }

  @Test
  void anOutsideTargetPointsIntoASiblingDirectoryOfTheProjectRoot() throws IOException {
    Path root = materialise(fixture("symlink", "mission-directory-escapes-root"));
    Path link = root.resolve("kitty-specs/symlink-mission-directory-escapes-root");

    assertThat(Files.isSymbolicLink(link)).isTrue();
    Path real = link.toRealPath();
    assertThat(real.startsWith(root.toRealPath())).as("the link leaves the project root").isFalse();
    assertThat(real.resolve("meta.json")).isRegularFile();
    assertThat(real.getParent()).isEqualTo(root.toRealPath().resolveSibling("outside"));
  }

  @Test
  void aTreeFixtureIsServedByTheRealServiceOverTheRealAdapter() {
    Built built = FilesystemFixtureFactory.fromTree(fixture("interleaved", "two-missions").dir());

    assertThat(built.query().project().missionCount()).isEqualTo(2);
    assertThat(built.query().missions(new PageRequest(50, null)).items()).extracting(item -> item.slug()).containsExactlyInAnyOrder("interleaved-alpha", "interleaved-beta");
    assertThat(built.source()).isNotNull();
    assertThat(built.handles().allowlistRecorder()).as("no recorder was given").isNull();
  }

  @Test
  void aRecordingTreeFixtureReportsItsAccessesAndNoViolations() {
    Built built = FilesystemFixtureFactory.fromTreeRecording(fixture("interleaved", "two-missions").dir());

    built.query().project();
    built.query().missions(new PageRequest(50, null));

    assertThat(built.handles().allowlistAccessCount()).isPositive();
    assertThat(built.handles().allowlistViolations()).isEmpty();
  }

  @Test
  void aRecorderThatWasGivenIsExposedAndSeesOnlyAllowedReads() {
    Built built = FilesystemFixtureFactory.fromTree(fixture("interleaved", "two-missions").dir(), RecordingAllowlistAccess::new);

    built.query().project();
    built.query().missions(new PageRequest(50, null));

    RecordingAllowlistAccess recorder = built.handles().allowlistRecorder();
    assertThat(recorder).isNotNull();
    assertThat(recorder.accesses()).isNotEmpty();
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aSpecIsWrittenAsATreeAndServedByTheSameService() {
    FixtureSpec spec = PortFixtures.interleavedPair();

    Built built = FilesystemFixtureFactory.fromSpec(spec);

    assertThat(built.query().project().name()).isEqualTo("fixture-project");
    assertThat(built.query().project().currentBranch()).isEqualTo("main");
    assertThat(built.query().project().specKittyVersion()).isEqualTo("3.2.7");
    assertThat(built.query().missions(new PageRequest(null, null)).items()).hasSize(2);
  }

  @Test
  void aSpecWithoutABranchWritesNoHeadAndAnAbsentLedgerWritesNoFile() throws IOException {
    FixtureSpec spec =
        new FixtureSpec(
            new FixtureSpec.Project("p", null, null, null),
            List.of(FixtureSpec.Mission.of("alpha", Rows.meta(Rows.ALPHA_ID, "alpha", PortFixtures.CREATED), null)));

    Built built = FilesystemFixtureFactory.fromSpec(spec);

    assertThat(built.root().resolve(".git")).doesNotExist();
    assertThat(built.root().resolve("kitty-specs/alpha/status.events.jsonl")).doesNotExist();
    assertThat(built.query().project().currentBranch()).isNull();
    assertThat(built.query().project().specKittyVersion()).isNull();
  }

  @Test
  void aTornTailIsRefusedThroughTheFilesystemSourceAndTheDiagnosticIsRecorded() {
    String torn = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed") + "{\"actor\":\"claude\",\"at\":\"2026-09-01T10:10:";
    Built built = FilesystemFixtureFactory.fromSpec(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, torn)));

    assertThatThrownBy(() -> built.query().project()).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL));
    assertThat(built.diagnostics()).isNotEmpty();
  }

  @Test
  void theReadDirectoryClassIsTheOneTheResolverChooses() throws IOException {
    Path coord = materialise(fixture("coordination", "coordinated-mission"));
    Path own = materialise(fixture("coordination", "coord-worktree-absent"));

    assertThat(FilesystemFixtureFactory.readDirectoryClass(coord, "coordinated-01J03000")).isEqualTo("coord");
    assertThat(FilesystemFixtureFactory.readDirectoryClass(own, "absent-coord-01J04000")).isEqualTo("own");
  }

  @Test
  void theLeakClassesLoadedFromTheCommittedFileEqualTheInlinePatternsSourceForSource() {
    var fromFile = LeakPatternsFile.load();
    var inline = LeakFixtures.python();

    assertThat(fromFile.strictHostPaths()).extracting(java.util.regex.Pattern::pattern).containsExactlyElementsOf(inline.strictHostPaths().stream().map(java.util.regex.Pattern::pattern).toList());
    assertThat(fromFile.humanHostPaths()).extracting(java.util.regex.Pattern::pattern).containsExactlyElementsOf(inline.humanHostPaths().stream().map(java.util.regex.Pattern::pattern).toList());
    assertThat(fromFile.email().pattern()).isEqualTo(inline.email().pattern());
    assertThat(fromFile.emailAnchored().pattern()).isEqualTo(inline.emailAnchored().pattern());
    assertThat(fromFile.secrets()).extracting(java.util.regex.Pattern::pattern).containsExactlyElementsOf(inline.secrets().stream().map(java.util.regex.Pattern::pattern).toList());
  }

  @Test
  void theManifestFixturesAreAllDiscovered() {
    Map<String, Integer> counts = new java.util.TreeMap<>();
    ConformanceTree.classes().forEach(entry -> counts.put(entry.tag(), entry.fixtures().size()));

    assertThat(counts).containsEntry("malformed-rows", 12).containsEntry("project-header", 9).containsEntry("interleaved", 4);
    assertThat(ConformanceTree.resolverCases()).hasSize(34);
  }
}
