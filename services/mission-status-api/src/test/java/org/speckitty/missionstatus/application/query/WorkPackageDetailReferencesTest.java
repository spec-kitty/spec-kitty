package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.detail.ArtifactReferenceBuilder;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactReference;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactReferences;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.Utf8Host;

/**
 * The artifact references of the detail (AC-3.6, row M9): pointers found by one listing of {@code tasks/} and an {@code lstat} per candidate,
 * with no file opened. The prompt file is name-keyed: the first regular, non-link {@code tasks/WP<digits>-*.md} in byte order whose name starts
 * with {@code <wpId>-}, which is not necessarily the file whose frontmatter holds the identifier.
 */
class WorkPackageDetailReferencesTest {

  private static ArtifactReferences references(DetailFixture fixture) {
    return detail(fixture, "WP01").artifactReferences();
  }

  @Test
  void thePromptAndTheSpecAreServedAsPointersWithTheirKinds() {
    DetailFixture fixture = fixture(root -> write(root, "spec.md", "# Spec\n"));

    ArtifactReferences served = references(fixture);

    assertThat(served.prompt().path()).isEqualTo("tasks/WP01-one.md");
    assertThat(served.prompt().kind()).isEqualTo(ArtifactKind.WORK_PACKAGE_PROMPT);
    assertThat(served.spec().path()).isEqualTo("spec.md");
    assertThat(served.spec().kind()).isEqualTo(ArtifactKind.SPEC);
  }

  @Test
  void aSpecThatIsAbsentALinkOrADirectoryIsNull() {
    DetailFixture absent = fixture(root -> {});
    DetailFixture link =
        fixture(
            root -> {
              write(root, "elsewhere.md", "# Spec\n");
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/spec.md"), root.resolve("kitty-specs/alpha/elsewhere.md"));
            });
    DetailFixture directory = fixture(root -> DetailRoute.directory(root, "kitty-specs/alpha/spec.md"));

    assertThat(references(absent).spec()).isNull();
    assertThat(references(link).spec()).isNull();
    assertThat(references(directory).spec()).isNull();
    assertThat(references(absent).prompt()).isNotNull();
  }

  @Test
  void thePromptFileIsNameKeyedNotFrontmatterKeyed() {
    // WP01-one.md holds the id WP02 in its frontmatter, and WP01-two.md holds WP01: the references of WP01 point at the file called WP01-*
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP02", "Two"));
              write(root, "tasks/WP09-nine.md", wpFile("WP01", "One"));
            });

    assertThat(references(fixture).prompt().path()).isEqualTo("tasks/WP01-one.md");
    assertThat(detail(fixture, "WP01").wpId().value()).isEqualTo("WP01");
  }

  @Test
  void theFirstRegularNonLinkFileInByteOrderWinsAndALinkOrADirectoryIsSkipped() {
    DetailFixture fixture =
        fixture(
            root -> {
              DetailRoute.directory(root, "kitty-specs/alpha/tasks/WP01-a.md");
              write(root, "elsewhere.md", "x\n");
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/tasks/WP01-b.md"), root.resolve("kitty-specs/alpha/elsewhere.md"));
              write(root, "tasks/WP01-c.md", wpFile("WP03", "Three"));
              write(root, "tasks/WP01-d.md", wpFile("WP04", "Four"));
            });

    assertThat(references(fixture).prompt().path()).isEqualTo("tasks/WP01-c.md");
  }

  @Test
  void aNameThatOnlyStartsLikeTheIdIsNotThePrompt() {
    DetailFixture fixture =
        fixture(
            root -> {
              DetailRoute.delete(root, "tasks/WP01-one.md");
              write(root, "tasks/WP01.md", wpFile("WP01", "One"));
              write(root, "tasks/WP011-x.md", wpFile("WP02", "Two"));
              write(root, "tasks/WP01-notes.txt", "x\n");
            });

    assertThat(references(fixture).prompt()).isNull();
    assertThat(references(fixture).spec()).isNull();
  }

  @Test
  void aPromptNameWithNothingAfterTheDashIsStillThePromptAndItsKindIsFixed() {
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-.md", wpFile("WP03", "Three")));

    // the oracle's name rule is ^WP[0-9]{2,}-[^/]*\\.md$ and its kind is a constant: the artifact classifier would call this name "other"
    assertThat(references(fixture).prompt()).isEqualTo(new ArtifactReference("tasks/WP01-.md", ArtifactKind.WORK_PACKAGE_PROMPT));
  }

  @Test
  void aPromptFileCodePointOrderIsByteOrderOfTheUtf8NotUtf16Order() {
    DetailFixture fixture =
        fixture(
            root -> {
              DetailRoute.delete(root, "tasks/WP01-one.md");
              write(root, "tasks/WP01-\uff21.md", wpFile("WP01", "Fullwidth"));
              write(root, "tasks/WP01-\ud83d\ude00.md", wpFile("WP02", "Emoji"));
            });

    // U+FF21 (3 bytes) sorts before U+1F600 (4 bytes) in UTF-8 and in code points, and after it in UTF-16 units
    assertThat(references(fixture).prompt().path()).isEqualTo("tasks/WP01-\uff21.md");
  }

  // ---- AC-6.6: non-ASCII names ---------------------------------------------------------------------------------------------------------

  private static DetailFixture accent() {
    return fixture(
        root -> {
          DetailRoute.delete(root, "tasks/WP01-one.md");
          write(root, "tasks/WP01-\u00e9.md", wpFile("WP01", "Accent"));
        });
  }

  /** The stub leg: with a host that decodes names, the non-ASCII prompt file is found whatever the locale of the machine that runs the test. */
  @Test
  void withTheNameEncodingStubANonAsciiPromptFileIsFoundRegardlessOfTheHostLocale() {
    DetailFixture base = accent();
    DetailFixture fixture = new DetailFixture(base.built(), new FilesystemTextSource(base.root(), base.recorder(), NameEncoding.fixed(true)), base.readModel());

    WorkPackageDetail served = DetailRoute.serviceOver(fixture).workPackageDetail(new MissionId(DetailRoute.ID), new WpId("WP01"));

    assertThat(served.artifactReferences().prompt().path()).isEqualTo("tasks/WP01-\u00e9.md");
  }

  @Test
  void aRealNonAsciiPromptFileNameOnAUtf8HostIsFound(TestInfo info) {
    Utf8Host.assumeUtf8(info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName());

    assertThat(references(accent()).prompt().path()).isEqualTo("tasks/WP01-\u00e9.md");
  }

  /** AC-3.6: the recorded access shows a directory read and the {@code lstat}s, and no READ of the prompt file or of {@code spec.md}. */
  @Test
  void buildingTheReferencesListsTasksAndStatsAndOpensNothing() {
    DetailFixture fixture = fixture(root -> write(root, "spec.md", "# Spec\n"));
    ArtifactReferenceBuilder builder = new ArtifactReferenceBuilder(fixture.textSource());
    fixture.recorder().clear();

    ArtifactReferenceBuilder.Built built = builder.build(new MissionRef("alpha"), new WpId("WP01"));

    assertThat(built.promptFileName()).isEqualTo("WP01-one.md");
    assertThat(built.references().prompt()).isEqualTo(new ArtifactReference("tasks/WP01-one.md", ArtifactKind.WORK_PACKAGE_PROMPT));
    assertThat(fixture.recorder().accesses()).isNotEmpty().noneMatch(access -> access.mode() == OpenMode.READ);
    assertThat(fixture.recorder().accesses()).filteredOn(access -> access.mode() == OpenMode.LIST).extracting(access -> access.path()).containsExactly("kitty-specs/alpha/tasks");
    assertThat(fixture.recorder().violations()).isEmpty();
  }
}
