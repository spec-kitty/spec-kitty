package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;

/**
 * {@code projectInputs()}: {@code .kittify/config.yaml} ({@code project.slug}), {@code .kittify/metadata.yaml}
 * ({@code spec_kitty.version}, {@code spec_kitty.schema_version}) and the {@code HEAD} read, as the oracle's
 * {@code tests/contract/_mission_status_project.py} reads them (read_project_name, project_version, schema_version_of, read_head,
 * head_file); the expected values of the metadata and HEAD tables are the reference builder's own output on the same text (oracle
 * probe, WP19 tracer). The branch-name pattern and length rules are the application's; the adapter hands over the raw name.
 */
class FilesystemMissionEventSourceProjectTest {

  @TempDir Path sandbox;
  Path root;
  RecordingAllowlistAccess recorder;
  FilesystemMissionEventSource source;

  @BeforeEach
  void setUp() throws IOException {
    root = Files.createDirectory(sandbox.resolve("project"));
    recorder = new RecordingAllowlistAccess(root);
    source = new FilesystemMissionEventSource(root, recorder);
    AdapterServiceHarness.healthyProject(root);
  }

  private void metadata(String text) {
    AdapterServiceHarness.write(root.resolve(".kittify/metadata.yaml"), text);
  }

  private void head(String text) {
    AdapterServiceHarness.write(root.resolve(".git/HEAD"), text);
  }

  private static Kind faultOf(Runnable call) {
    try {
      call.run();
    } catch (SourceFault fault) {
      return fault.kind();
    }
    return null;
  }

  @Test
  void aHealthyProjectGivesTheSlugTheVersionTheSchemaAndTheBranch() {
    assertThat(source.projectInputs()).isEqualTo(new ProjectInputs("fixture-project", "3.2.7", 3, "main"));
  }

  @Test
  void aMissingMetadataFileGivesNullVersionAndSchema() throws IOException {
    Files.delete(root.resolve(".kittify/metadata.yaml"));
    assertThat(source.projectInputs()).isEqualTo(new ProjectInputs("fixture-project", null, null, "main"));
  }

  @Test
  void anOsUnreadableMetadataFileGivesNullVersionAndSchema() {
    recorder.failWhen(access -> access.pathClass() == PathClass.METADATA_YAML && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(source.projectInputs()).isEqualTo(new ProjectInputs("fixture-project", null, null, "main"));
  }

  @ParameterizedTest(name = "metadata [{0}] -> version {1}, schema {2}")
  @CsvSource(
      delimiter = '|',
      nullValues = "NULL",
      value = {
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3 | 3.2.7 | 3",
        "spec_kitty:\\n  version: '3.2.7'\\n  schema_version: '3' | 3.2.7 | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: ' 4 ' | 3.2.7 | 4",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3.9 | 3.2.7 | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: true | 3.2.7 | 1",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: not-a-number | 3.2.7 | NULL",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: [1] | 3.2.7 | NULL",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: ~ | 3.2.7 | NULL",
        "spec_kitty:\\n  version: unknown\\n  schema_version: 3 | NULL | 3",
        "spec_kitty:\\n  version: 3.2\\n  schema_version: 3 | NULL | 3",
        "spec_kitty:\\n  version: [1]\\n  schema_version: 3 | NULL | 3",
        "spec_kitty:\\n  schema_version: 3 | NULL | 3",
        "spec_kitty: [1] | NULL | NULL",
        "spec_kitty: ~ | NULL | NULL",
        "- a\\n- b | NULL | NULL",
        "'' | NULL | NULL",
        "key: [unclosed | NULL | NULL",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3\\nmigrations: x | NULL | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3\\nenvironment: ~ | NULL | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3\\nmigrations:\\n  applied: [5] | NULL | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 3\\nmigrations:\\n  applied: [{id: a}] | 3.2.7 | 3",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: 1_0 | 3.2.7 | 10",
        "spec_kitty:\\n  version: 3.2.7\\n  schema_version: '1__0' | 3.2.7 | NULL",
      })
  void metadataValuesAreCoercedAsTheOracleCoercesThem(String text, String version, Integer schema) {
    metadata(text.replace("\\n", "\n"));
    ProjectInputs inputs = source.projectInputs();
    assertThat(inputs.specKittyVersion()).isEqualTo(version);
    assertThat(inputs.schemaVersion()).isEqualTo(schema);
  }

  // F4: ProjectMetadata.load calls parse_iso on initialized_at, last_upgraded_at and every migration's applied_at; a truthy (or, for
  // applied_at, any present) non-string value raises TypeError, which project_version reads as null. Expected values are the oracle's.
  @ParameterizedTest(name = "metadata tail [{0}] -> version {1}")
  @CsvSource(
      delimiter = '|',
      nullValues = "NULL",
      value = {
        "  initialized_at: 5 | NULL",
        "  initialized_at: true | NULL",
        "  initialized_at: [1] | NULL",
        "  initialized_at: 0 | 3.2.7",
        "  initialized_at: ~ | 3.2.7",
        "  initialized_at: notadate | 3.2.7",
        "  initialized_at: '2026-01-01T00:00:00+00:00' | 3.2.7",
        "  last_upgraded_at: 7 | NULL",
        "  last_upgraded_at: [1] | NULL",
        "  last_upgraded_at: nope | 3.2.7",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: 5, result: ok} | NULL",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: true, result: ok} | NULL",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: ~, result: ok} | NULL",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: 0, result: ok} | NULL",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: x, result: ok} | 3.2.7",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: 5} | NULL",
        "migrations:\\n  applied:\\n    - {applied_at: 5} | 3.2.7",
        "migrations:\\n  applied:\\n    - {id: a, applied_at: '2026-01-01T00:00:00+00:00', result: ok} | 3.2.7",
      })
  void aNonStringTimestampMakesTheMetadataLoadFailLikeParseIso(String tail, String version) {
    // CsvSource trims the value, so the two keys of the spec_kitty section are re-indented here
    String section = tail.startsWith("initialized_at") || tail.startsWith("last_upgraded_at") ? "  " : "";
    metadata("spec_kitty:\n  version: 3.2.7\n  schema_version: 3\n" + section + tail.replace("\\n", "\n") + "\n");
    ProjectInputs inputs = source.projectInputs();
    assertThat(inputs.specKittyVersion()).isEqualTo(version);
    assertThat(inputs.schemaVersion()).as("schema_version_of is a separate read").isEqualTo(3);
  }

  // F5: the oracle reads HEAD and the .git pointer with plain utf-8, so a byte order mark is not skipped there (utf-8-sig is for metadata).
  @Test
  void aByteOrderMarkInFrontOfHeadOrOfThePointerIsNotSkipped() throws IOException {
    AdapterServiceHarness.writeBytes(root.resolve(".git/HEAD"), ("\uFEFFref: refs/heads/main\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    assertThat(source.projectInputs().branchName()).as("oracle: None").isNull();

    Path store = Files.createDirectories(sandbox.resolve("bom-store"));
    AdapterServiceHarness.write(store.resolve("HEAD"), "ref: refs/heads/linked\n");
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.writeBytes(root.resolve(".git"), ("\uFEFFgitdir: ../bom-store\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    assertThat(source.projectInputs().branchName()).as("oracle: None").isNull();

    AdapterServiceHarness.write(root.resolve(".git"), "gitdir: ../bom-store\n");
    assertThat(source.projectInputs().branchName()).as("control: the plain pointer is followed").isEqualTo("linked");
    AdapterServiceHarness.writeBytes(store.resolve("HEAD"), ("\uFEFFref: refs/heads/linked\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    assertThat(source.projectInputs().branchName()).as("oracle: None").isNull();
  }

  // F9: the named git directory is contained by real path, not lexically.
  @Test
  void aPointerThroughASymbolicLinkToADirectoryInsideTheRootIsRefusedAndItsHeadIsNeverRead() throws IOException {
    Files.createDirectories(root.resolve("inner-git"));
    AdapterServiceHarness.write(root.resolve("inner-git/HEAD"), "ref: refs/heads/inside\n");
    SymlinkSupport.link(sandbox.resolve("alias"), root.resolve("inner-git"));
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.write(root.resolve(".git"), "gitdir: ../alias\n");

    assertThat(source.projectInputs().branchName()).isNull();
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ && a.path().endsWith("HEAD"));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aPointerThroughASymbolicLinkToADirectoryOutsideTheRootIsStillFollowed() throws IOException {
    Path store = Files.createDirectories(sandbox.resolve("outer-git"));
    AdapterServiceHarness.write(store.resolve("HEAD"), "ref: refs/heads/outside\n");
    SymlinkSupport.link(sandbox.resolve("alias2"), store);
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.write(root.resolve(".git"), "gitdir: ../alias2\n");
    assertThat(source.projectInputs().branchName()).isEqualTo("outside");
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aMetadataFileThatIsNotUtf8GivesNullVersionAndSchema() {
    AdapterServiceHarness.writeBytes(root.resolve(".kittify/metadata.yaml"), new byte[] {'a', ':', ' ', (byte) 0xff, '\n'});
    assertThat(source.projectInputs()).isEqualTo(new ProjectInputs("fixture-project", null, null, "main"));
  }

  @Test
  void aByteOrderMarkInFrontOfTheMetadataIsSkippedLikeUtf8Sig() {
    AdapterServiceHarness.writeBytes(root.resolve(".kittify/metadata.yaml"), ("﻿spec_kitty:\n  version: 3.2.7\n  schema_version: 3\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    assertThat(source.projectInputs().schemaVersion()).isEqualTo(3);
  }

  @ParameterizedTest(name = "config [{0}] is a fault")
  @CsvSource(
      delimiter = '|',
      value = {
        "project: {}",
        "project:\\n  slug: ''",
        "project:\\n  slug: 5",
        "project: [a]",
        "- a",
        "key: [unclosed",
      })
  void aConfigurationWithoutAUsableSlugIsADirectoryFault(String text) {
    AdapterServiceHarness.write(root.resolve(".kittify/config.yaml"), text.replace("\\n", "\n"));
    assertThat(faultOf(source::projectInputs)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void aMissingOrUnreadableConfigurationIsADirectoryFault() throws IOException {
    recorder.failWhen(access -> access.pathClass() == PathClass.CONFIG_YAML && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(faultOf(source::projectInputs)).isEqualTo(Kind.DIR_UNREADABLE);
    recorder.failWhen(access -> false, () -> new IOException());
    Files.delete(root.resolve(".kittify/config.yaml"));
    assertThat(faultOf(source::projectInputs)).isEqualTo(Kind.DIR_UNREADABLE);
  }

  @Test
  void theConfigurationIsReadForTheSlugOnlyAndTheDrainKeyChangesNothing() {
    AdapterServiceHarness.write(root.resolve(".kittify/config.yaml"), "project:\n  slug: fixture-project\nhosted:\n  drain: true\n");
    assertThat(source.projectInputs().name()).isEqualTo("fixture-project");
  }

  // ---- HEAD ------------------------------------------------------------------------------------------------------------------

  @ParameterizedTest(name = "HEAD [{0}] -> {1}")
  @CsvSource(
      delimiter = '|',
      nullValues = "NULL",
      value = {
        "ref: refs/heads/main\\n | main",
        "ref: refs/heads/feature/x-1\\n | feature/x-1",
        "ref:refs/heads/main | main",
        "  ref: refs/heads/main  \\n\\n | main",
        "0123456789abcdef0123456789abcdef01234567\\n | NULL",
        "ref: refs/remotes/origin/main\\n | NULL",
        "ref: refs/tags/v1\\n | NULL",
        "'' | NULL",
        "ref: refs/heads/\\n | ''",
      })
  void theBranchIsTheNameHeadPointsAtAndNothingElse(String text, String expected) {
    head(text.replace("\\n", "\n"));
    assertThat(source.projectInputs().branchName()).isEqualTo(expected);
  }

  @Test
  void aHeadThatIsNotUtf8GivesNullBranch() {
    AdapterServiceHarness.writeBytes(root.resolve(".git/HEAD"), new byte[] {'r', 'e', 'f', ':', ' ', (byte) 0xff});
    assertThat(source.projectInputs().branchName()).isNull();
  }

  @Test
  void aMissingGitEntryGivesNullBranch() throws IOException {
    Files.delete(root.resolve(".git/HEAD"));
    assertThat(source.projectInputs().branchName()).isNull();
    Files.delete(root.resolve(".git"));
    assertThat(source.projectInputs().branchName()).isNull();
  }

  @Test
  void anUnreadableHeadGivesNullBranch() {
    recorder.failWhen(access -> access.pathClass() == PathClass.GIT_HEAD && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    assertThat(source.projectInputs().branchName()).isNull();
  }

  @Test
  void aGitPointerFileNamesTheGitDirectoryWhoseSingleHeadIsRead() throws IOException {
    Path store = Files.createDirectories(sandbox.resolve("store/worktrees/linked"));
    AdapterServiceHarness.write(store.resolve("HEAD"), "ref: refs/heads/linked-branch\n");
    AdapterServiceHarness.write(store.resolve("packed-refs"), "decoy\n");
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.write(root.resolve(".git"), "gitdir: ../store/worktrees/linked\n");

    assertThat(source.projectInputs().branchName()).isEqualTo("linked-branch");

    List<Access> gitReads = recorder.accesses().stream().filter(a -> a.mode() == OpenMode.READ && (a.pathClass() == PathClass.GIT_POINTER || a.pathClass() == PathClass.GITDIR_HEAD)).toList();
    assertThat(gitReads).extracting(Access::path).containsExactly(".git", "<outside>/HEAD");
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void anAbsoluteGitdirIsFollowedToo() throws IOException {
    Path store = Files.createDirectories(sandbox.resolve("abs-store"));
    AdapterServiceHarness.write(store.resolve("HEAD"), "ref: refs/heads/absolute\n");
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.write(root.resolve(".git"), "gitdir: " + store + "\n");
    assertThat(source.projectInputs().branchName()).isEqualTo("absolute");
  }

  @ParameterizedTest(name = "pointer [{0}] gives a null branch")
  @CsvSource(
      delimiter = '|',
      value = {
        "gitdir: ../no-such-directory",
        "not a pointer",
        "gitdir:",
        "''",
        "gitdir: .git2",
        "gitdir: .",
        "gitdir: .git/worktrees/x",
        "gitdir: sub/../.git/worktrees/x",
      })
  void aPointerThatNamesNothingReadableOrSomethingInsideTheRootGivesNullBranchAndReadsNoHead(String pointer) throws IOException {
    Files.createDirectories(root.resolve(".git2"));
    AdapterServiceHarness.write(root.resolve(".git2/HEAD"), "ref: refs/heads/inside\n");
    Files.createDirectories(root.resolve(".git.real/worktrees/x"));
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    AdapterServiceHarness.write(root.resolve(".git"), pointer + "\n");

    assertThat(source.projectInputs().branchName()).isNull();
    // F5: an in-root HEAD other than .git/HEAD is never read
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ && a.path().endsWith("HEAD"));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void aGitEntryThatIsASymbolicLinkIsNotFollowed() throws IOException {
    Path store = Files.createDirectories(sandbox.resolve("elsewhere"));
    AdapterServiceHarness.write(store.resolve("HEAD"), "ref: refs/heads/elsewhere\n");
    Files.delete(root.resolve(".git/HEAD"));
    Files.delete(root.resolve(".git"));
    SymlinkSupport.link(root.resolve(".git"), store);
    assertThat(source.projectInputs().branchName()).isNull();
    assertThat(recorder.accesses()).noneMatch(a -> a.mode() == OpenMode.READ && a.path().startsWith(".git"));
  }

  @Test
  void aHeadThatIsASymbolicLinkIsNotFollowed() throws IOException {
    Path other = sandbox.resolve("other-head");
    AdapterServiceHarness.write(other, "ref: refs/heads/linked\n");
    Files.delete(root.resolve(".git/HEAD"));
    SymlinkSupport.link(root.resolve(".git/HEAD"), other);
    assertThat(source.projectInputs().branchName()).isNull();
  }

  @Test
  void aHugeConfigurationOrHeadIsRefusedNotBuffered() {
    AdapterServiceHarness.writeBytes(root.resolve(".git/HEAD"), new byte[2 * 1024 * 1024]);
    assertThat(source.projectInputs().branchName()).isNull();
    AdapterServiceHarness.writeBytes(root.resolve(".kittify/metadata.yaml"), new byte[2 * 1024 * 1024]);
    assertThat(source.projectInputs().schemaVersion()).isNull();
  }

  @Test
  void theWholeProjectReadStaysInsideTheAllowlist() {
    source.projectInputs();
    assertThat(recorder.violations()).isEmpty();
    assertThat(recorder.accesses()).extracting(Access::path).contains(".kittify/config.yaml", ".kittify/metadata.yaml", ".git", ".git/HEAD");
  }

  @Test
  void aFaultMessageNeverCarriesAPath() throws IOException {
    Files.delete(root.resolve(".kittify/config.yaml"));
    assertThatThrownBy(source::projectInputs).isInstanceOf(SourceFault.class).hasMessage("DIR_UNREADABLE").satisfies(fault -> assertThat(fault.toString()).doesNotContain(sandbox.toString()));
  }

  // ---- .kittify containment (pre-merge fold J4, ruling 3 of 2026-10-13) ------------------------------------------------------------

  @Test
  void aKittifyThatLinksOutsideTheRootIsUnusableProjectConfigurationAndNothingOutsideIsRead() throws IOException {
    Path outside = Files.createDirectories(sandbox.resolve("outside/.kittify"));
    AdapterServiceHarness.write(outside.resolve("config.yaml"), "project:\n  slug: outside-slug-READ\n");
    AdapterServiceHarness.write(outside.resolve("metadata.yaml"), "spec_kitty:\n  version: 9.9.9-OUTSIDE\n");
    org.assertj.core.api.Assertions.assertThat(root.resolve(".kittify").toFile().isDirectory()).isTrue();
    deleteRecursively(root.resolve(".kittify"));
    SymlinkSupport.link(root.resolve(".kittify"), outside);

    assertThat(faultOf(() -> source.projectInputs())).isEqualTo(Kind.DIR_UNREADABLE);

    AdapterServiceHarness harness = new AdapterServiceHarness(root);
    assertThatThrownBy(() -> harness.query.project())
        .isInstanceOfSatisfying(
            org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable.class,
            refusal -> assertThat(refusal.code()).isEqualTo(org.speckitty.missionstatus.domain.model.DiagnosticCode.MISSION_DIR_UNREADABLE));
  }

  @Test
  void aKittifyThatLinksToAnotherDirectoryInsideTheRootIsStillRead() throws IOException {
    Path inner = Files.createDirectories(root.resolve("tooling/kittify-store"));
    AdapterServiceHarness.write(inner.resolve("config.yaml"), "project:\n  slug: inner-slug\n");
    deleteRecursively(root.resolve(".kittify"));
    SymlinkSupport.link(root.resolve(".kittify"), inner);

    assertThat(source.projectInputs().name()).isEqualTo("inner-slug");
  }

  private static void deleteRecursively(Path directory) throws IOException {
    try (var walk = Files.walk(directory)) {
      for (Path path : walk.sorted(java.util.Comparator.reverseOrder()).toList()) {
        Files.delete(path);
      }
    }
  }
}
