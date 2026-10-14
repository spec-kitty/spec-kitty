package org.speckitty.missionstatus.application.query.index;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/**
 * The access set of the index (FR-006, FR-011, plan D-76): exactly one {@code WP_FILE} READ for each candidate and none twice, with or
 * without the requested body, under the read scope AUTHORED, and nothing outside the fence. Read through the real file system and the
 * recording seam; the in-memory twin asserts the scope.
 */
class WorkPackageIndexAccessSetTest {

  private static TreeFixture fixture(String name) {
    return WorkPackageIndexTest.workPackageFixtures().stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
  }

  private static List<String> wpFileReads(DetailFixture detail) {
    return detail.recorder().accesses().stream()
        .filter(access -> access.pathClass() == PathClass.WP_FILE && access.mode() == OpenMode.READ)
        .map(Access::path)
        .toList();
  }

  private static WorkPackageIndex index(DetailFixture detail) {
    return new WorkPackageIndex(detail.textSource(), new YamlFrontmatterDecoder());
  }

  @Test
  void eachCandidateIsReadExactlyOnceWhetherOrNotABodyIsRequested() {
    DetailFixture detail = DetailFixture.of(fixture("duplicate-wp-id").dir());
    detail.recorder().clear();
    index(detail).build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.empty(), diagnostic -> {});
    List<String> without = wpFileReads(detail);
    assertThat(without).hasSize(2).doesNotHaveDuplicates();

    detail.recorder().clear();
    WorkPackageIndex.Result result = index(detail).build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.of(new WpId("WP01")), diagnostic -> {});
    List<String> with = wpFileReads(detail);
    assertThat(with).as("the prompt comes from the same read: no second read").hasSize(2).doesNotHaveDuplicates().containsExactlyInAnyOrderElementsOf(without);
    assertThat(result.capturedBody()).isPresent();
  }

  @Test
  void aSkippedLinkOrDirectoryIsNeverRead() {
    DetailFixture directory = DetailFixture.of(fixture("wpm-22").dir());
    directory.recorder().clear();
    index(directory).build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.empty(), diagnostic -> {});
    assertThat(wpFileReads(directory)).isEmpty();
  }

  @Test
  void everyAccessIsInsideTheFenceAndTheListingIsOfTasksOnly() {
    DetailFixture detail = DetailFixture.of(fixture("wpm-27").dir());
    detail.recorder().clear();
    index(detail).build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.empty(), diagnostic -> {});
    assertThat(detail.recorder().violations()).isEmpty();
    assertThat(detail.recorder().accesses()).extracting(Access::pathClass).containsOnly(PathClass.TASKS_DIR, PathClass.WP_FILE, PathClass.MISSION_DIR, PathClass.PROJECT_ROOT);
    assertThat(detail.recorder().accesses().stream().filter(access -> access.mode() == OpenMode.LIST).map(Access::path)).containsOnly("kitty-specs/alpha-mission/tasks");
    assertThat(Allowlist.permits(PathClass.WP_FILE, OpenMode.READ)).isTrue();
  }

  @Test
  void everyCallOfTheIndexIsMadeUnderTheAuthoredScopeAndNoOtherPath() throws IOException {
    InMemoryTextSource source = WorkPackageIndexTest.sourceOf(fixture("duplicate-wp-id").dir());
    new WorkPackageIndex(source, new YamlFrontmatterDecoder()).build(WorkPackageIndexTest.MISSION, WorkPackageIndexTest.MID8, Optional.empty(), (Diagnostic diagnostic) -> {});
    assertThat(source.readScopes()).as("the scopes are asserted explicitly: the double registers every scope").isNotEmpty().containsOnly(ReadScope.AUTHORED);
    List<String> paths = new ArrayList<>(source.readRefs().stream().map(ref -> ref.path().toString()).toList());
    assertThat(paths).allMatch(path -> path.equals("tasks") || path.startsWith("tasks/WP"));
  }
}
