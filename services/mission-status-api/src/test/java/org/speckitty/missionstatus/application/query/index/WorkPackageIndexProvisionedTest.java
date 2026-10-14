package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * AC-6.1 cases 22 and 23, read through the real file system: a directory named {@code WP05-d.md} and a symbolic link named
 * {@code WP06-l.md}, the link provisioned at test time by the fixture's {@code PROVISION_PLAN} (never committed, NFR-007). Both are
 * skipped candidates, and the target of the link is never read.
 */
class WorkPackageIndexProvisionedTest {

  private static TreeFixture fixture(String name) {
    return WorkPackageIndexTest.workPackageFixtures().stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
  }

  private static WorkPackageIndex.Result build(DetailFixture detail, List<Diagnostic> diagnostics) {
    return new WorkPackageIndex(detail.textSource(), new YamlFrontmatterDecoder())
        .build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.empty(), diagnostics::add);
  }

  @Test
  void case22ADirectoryNamedLikeAWorkPackageFileIsSkippedWithOneDiagnostic() {
    DetailFixture detail = DetailFixture.of(fixture("wpm-22").dir());
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(detail, diagnostics).workPackages()).isEmpty();
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.WP_FILE_SKIPPED, WorkPackageIndexTest.MID8, null));
  }

  @Test
  void case23ASymbolicLinkNamedLikeAWorkPackageFileIsSkippedAndItsTargetIsNeverRead() {
    DetailFixture detail = DetailFixture.of(fixture("wpm-23").dir());
    detail.recorder().clear();
    List<Diagnostic> diagnostics = new ArrayList<>();
    assertThat(build(detail, diagnostics).workPackages()).isEmpty();
    assertThat(diagnostics).containsExactly(new Diagnostic(DiagnosticCode.WP_FILE_SKIPPED, WorkPackageIndexTest.MID8, null));
    assertThat(detail.recorder().accesses().stream().filter(access -> access.mode() == OpenMode.READ)).as("no READ at all: the link was only stat-ed").isEmpty();
    assertThat(detail.recorder().accesses()).noneMatch(access -> access.path().contains("notes/"));
  }

  @Test
  void theCommittedCorpusReadThroughTheRealFileSystemEqualsTheOracleToo() {
    int compared = 0;
    for (TreeFixture fixture : WorkPackageIndexTest.workPackageFixtures()) {
      DetailFixture detail = DetailFixture.of(fixture.dir());
      WorkPackageIndex.Result result = build(detail, new ArrayList<>());
      java.util.Map<String, String> actual = new java.util.TreeMap<>();
      result.workPackages().forEach(entry -> actual.put(entry.id().value(), entry.metadata().title()));
      assertThat(actual).as(fixture.key()).isEqualTo(WorkPackageIndexTest.oracleTitles(fixture));
      assertThat(detail.recorder().violations()).as(fixture.key()).isEmpty();
      compared++;
    }
    assertThat(compared).isGreaterThanOrEqualTo(30);
  }
}
