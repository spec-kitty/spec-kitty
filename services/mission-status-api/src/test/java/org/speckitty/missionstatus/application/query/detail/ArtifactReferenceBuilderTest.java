package org.speckitty.missionstatus.application.query.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/**
 * {@link ArtifactReferenceBuilder} over the in-memory port: one listing of {@code tasks/} and one {@code lstat} per candidate, every call under
 * the authored scope (asserted through {@code readScopes()}), no file opened, and a fault of the port thrown, never swallowed (row M9).
 */
class ArtifactReferenceBuilderTest {

  private static final MissionRef MISSION = new MissionRef("alpha");
  private static final WpId WP01 = new WpId("WP01");

  private static FileRef file(String path) {
    return new FileRef.MissionFile(MISSION, RelativePath.of(path));
  }

  private static InMemoryTextSource tasks(String... names) {
    return new InMemoryTextSource().dir(file("tasks"), names);
  }

  private static byte[] x() {
    return new byte[] {'x'};
  }

  @Test
  void thePromptIsTheFirstEligibleNameInByteOrderAndTheSpecIsPointedAtWhenRegular() {
    InMemoryTextSource source = tasks("WP02-b.md", "WP01-b.md", "WP01-a.md", "WP011-x.md", "notes.md").file(file("tasks/WP01-a.md"), x()).file(file("tasks/WP01-b.md"), x()).file(file("spec.md"), x());

    ArtifactReferenceBuilder.Built built = new ArtifactReferenceBuilder(source).build(MISSION, WP01);

    assertThat(built.promptFileName()).isEqualTo("WP01-a.md");
    assertThat(built.references().prompt().path()).isEqualTo("tasks/WP01-a.md");
    assertThat(built.references().prompt().kind()).isEqualTo(ArtifactKind.WORK_PACKAGE_PROMPT);
    assertThat(built.references().spec().path()).isEqualTo("spec.md");
    assertThat(built.references().spec().kind()).isEqualTo(ArtifactKind.SPEC);
    assertThat(source.readRefs()).containsExactly(file("tasks"), file("tasks/WP01-a.md"), file("spec.md"));
    assertThat(source.readScopes()).hasSize(3).containsOnly(ReadScope.AUTHORED);
  }

  @Test
  void aLinkOrADirectoryIsSkippedAndTheNextNameIsTried() {
    InMemoryTextSource source = tasks("WP01-a.md", "WP01-b.md", "WP01-c.md").link(file("tasks/WP01-a.md")).dir(file("tasks/WP01-b.md"), "x").file(file("tasks/WP01-c.md"), x());

    assertThat(new ArtifactReferenceBuilder(source).build(MISSION, WP01).promptFileName()).isEqualTo("WP01-c.md");
    assertThat(source.readRefs()).containsExactly(file("tasks"), file("tasks/WP01-a.md"), file("tasks/WP01-b.md"), file("tasks/WP01-c.md"), file("spec.md"));
  }

  @Test
  void aNameThePathRuleRefusesIsNeverStatted() {
    InMemoryTextSource source = tasks("WP01-a\\b.md", "WP01-a\nb.md", "WP01-a\u0000b.md");

    assertThat(new ArtifactReferenceBuilder(source).build(MISSION, WP01).promptFileName()).isNull();
    assertThat(source.readRefs()).containsExactly(file("tasks"), file("spec.md"));
  }

  @Test
  void anAbsentTasksDirectoryAndANonDirectoryGiveNoPrompt() {
    InMemoryTextSource absent = new InMemoryTextSource();
    InMemoryTextSource regular = new InMemoryTextSource().file(file("tasks"), x());

    assertThat(new ArtifactReferenceBuilder(absent).build(MISSION, WP01).references().prompt()).isNull();
    assertThat(new ArtifactReferenceBuilder(regular).build(MISSION, WP01).references().prompt()).isNull();
    assertThat(new ArtifactReferenceBuilder(absent).build(MISSION, WP01).references().spec()).isNull();
  }

  @Test
  void aFaultOfTheListingOfAStatIsThrown() {
    for (TextFault.Kind kind : TextFault.Kind.values()) {
      InMemoryTextSource listing = new InMemoryTextSource().fault(file("tasks"), kind);
      InMemoryTextSource leaf = tasks("WP01-a.md").fault(file("tasks/WP01-a.md"), kind);
      InMemoryTextSource spec = tasks().fault(file("spec.md"), kind);

      assertThatThrownBy(() -> new ArtifactReferenceBuilder(listing).build(MISSION, WP01)).isInstanceOf(TextFault.class);
      assertThatThrownBy(() -> new ArtifactReferenceBuilder(leaf).build(MISSION, WP01)).isInstanceOf(TextFault.class);
      assertThatThrownBy(() -> new ArtifactReferenceBuilder(spec).build(MISSION, WP01)).isInstanceOf(TextFault.class);
    }
  }
}
