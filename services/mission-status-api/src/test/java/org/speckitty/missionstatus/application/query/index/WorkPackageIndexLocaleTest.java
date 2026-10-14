package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.index.WorkPackageIndexTest.MID8;
import static org.speckitty.missionstatus.application.query.index.WorkPackageIndexTest.MISSION;
import static org.speckitty.missionstatus.application.query.index.WorkPackageIndexTest.file;
import static org.speckitty.missionstatus.application.query.index.WorkPackageIndexTest.ref;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;
import org.speckitty.missionstatus.testsupport.Utf8Host;

/**
 * AC-6.6, the index part (D-73): the file-name encoding rule. The stub leg injects the host probe through the port's {@code trustworthy}
 * flag, so it runs under any locale and calls no {@code assumeUtf8}; the live leg creates real non-ASCII names and needs a UTF-8 host.
 * The three-route child-JVM leg is WP18's.
 */
class WorkPackageIndexLocaleTest {

  private static final String E_ACUTE = "\u00e9";

  private static WorkPackageIndex.Result build(InMemoryTextSource source, List<Diagnostic> diagnostics) {
    return new WorkPackageIndex(source, new YamlFrontmatterDecoder()).build(MISSION, MID8, Optional.empty(), diagnostics::add);
  }

  private static InMemoryTextSource nonAsciiTree(boolean trustworthy) {
    return new InMemoryTextSource()
        .trustworthy(trustworthy)
        .file(ref("tasks/WP01-" + E_ACUTE + ".md"), file("WP01", "accented"))
        .file(ref("tasks/WP02-x.md"), file("WP02", "ascii"))
        .file(ref("tasks/notes-" + E_ACUTE + ".md"), file("WP09", "a note, not a candidate"));
  }

  @Test
  void stubLegAnUntrustworthyHostRefusesTheWholeIndexForANonAsciiCandidateAndOmitsNothingSilently() {
    InMemoryTextSource source = nonAsciiTree(false);
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThatThrownBy(() -> build(source, diagnostics))
        .isInstanceOfSatisfying(WorkPackageIndexFault.class, fault -> assertThat(fault.kind()).isEqualTo(WorkPackageIndexFault.Kind.NAMES_UNTRUSTWORTHY));
    assertThat(source.readRefs()).as("nothing but the listing was asked for: no partial index, no skipped file").containsExactly(ref("tasks"));
    assertThat(diagnostics).as("the route writes the one source_unreadable diagnostic, not the index").isEmpty();
  }

  @Test
  void stubLegAnUntrustworthyHostServesAnAsciiOnlyMissionAndIgnoresANonCandidate() {
    InMemoryTextSource ascii = new InMemoryTextSource().trustworthy(false).file(ref("tasks/WP01-a.md"), file("WP01", "a")).file(ref("tasks/WP02-b.md"), file("WP02", "b"));
    assertThat(build(ascii, new ArrayList<>()).workPackages()).hasSize(2);
    InMemoryTextSource withNote =
        new InMemoryTextSource().trustworthy(false).file(ref("tasks/WP01-a.md"), file("WP01", "a")).file(ref("tasks/notes-" + E_ACUTE + ".md"), file("WP09", "note"));
    assertThat(build(withNote, new ArrayList<>()).workPackages()).as("a non-candidate does not refuse").hasSize(1);
  }

  @Test
  void stubLegATrustworthyHostIndexesBothAccentedAndPlainWorkPackagesAndIgnoresTheNote() {
    List<Diagnostic> diagnostics = new ArrayList<>();
    WorkPackageIndex.Result result = build(nonAsciiTree(true), diagnostics);
    assertThat(result.workPackages()).extracting(entry -> entry.id().value()).containsExactly("WP01", "WP02");
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aCandidateHoldingAReplacementCharacterIsRefusedOnAnUntrustworthyHostAndSkippedOnATrustworthyOne() {
    String name = "tasks/WP03-\ufffd.md";
    InMemoryTextSource untrusted = new InMemoryTextSource().trustworthy(false).dir(ref("tasks"), "WP03-\ufffd.md");
    assertThatThrownBy(() -> build(untrusted, new ArrayList<>())).isInstanceOf(WorkPackageIndexFault.class);
    InMemoryTextSource trusted = new InMemoryTextSource().trustworthy(true).dir(ref("tasks"), "WP01-a.md", "WP03-\ufffd.md").file(ref("tasks/WP01-a.md"), file("WP01", "a"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(trusted, diagnostics).workPackages()).hasSize(1);
    assertThat(diagnostics).extracting(Diagnostic::code).as(name).containsExactly(DiagnosticCode.WP_FILE_SKIPPED);
  }

  @Test
  void liveLegUnderAUtf8LocaleBothWorkPackagesAreIndexedAndTheNoteIsIgnored(@TempDir Path project) throws IOException {
    Utf8Host.assumeUtf8("WorkPackageIndexLocaleTest#liveLegUnderAUtf8LocaleBothWorkPackagesAreIndexedAndTheNoteIsIgnored");
    Path tasks = Files.createDirectories(project.resolve("kitty-specs").resolve(MISSION.name()).resolve("tasks"));
    Files.write(tasks.resolve("WP01-" + E_ACUTE + ".md"), file("WP01", "accented"));
    Files.write(tasks.resolve("WP02-x.md"), file("WP02", "ascii"));
    Files.write(tasks.resolve("notes-" + E_ACUTE + ".md"), file("WP09", "note"));
    List<Diagnostic> diagnostics = new ArrayList<>();
    WorkPackageIndex.Result result =
        new WorkPackageIndex(new FilesystemTextSource(project), new YamlFrontmatterDecoder()).build(MISSION, MID8, Optional.empty(), diagnostics::add);
    assertThat(result.workPackages()).extracting(entry -> entry.fileName()).containsExactly("WP01-" + E_ACUTE + ".md", "WP02-x.md");
    assertThat(diagnostics).isEmpty();
  }
}
