package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ID;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/**
 * The read scope of the route (WP10 review): the in-memory text source registers every entry under every read scope by default, so a route
 * test that only checked the result could not tell an {@code ARTIFACT} read from an {@code AUTHORED} one. This one asserts {@code readScopes()}
 * explicitly: every text read of the Work Package detail, the index's and the route's own, is made under {@code AUTHORED}, and the references
 * the route read are the ones it should.
 */
class WorkPackageDetailScopesTest {

  private static final MissionRef MISSION = new MissionRef("alpha");

  private static FileRef file(String path) {
    return new FileRef.MissionFile(MISSION, RelativePath.of(path));
  }

  private static byte[] text(String content) {
    return content.getBytes(StandardCharsets.UTF_8);
  }

  private static InMemoryTextSource populated() {
    return new InMemoryTextSource()
        .dir(file("tasks"), "WP01-one.md", "WP01-one")
        .file(file("tasks/WP01-one.md"), text(DetailRoute.wpFile("WP01", "One", "dependencies: [WP02]", "subtasks: [T001]", "owned_files: [src/**]")))
        .dir(file("tasks/WP01-one"), "review-cycle-1.md")
        .file(file("tasks/WP01-one/review-cycle-1.md"), text(DetailRoute.cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00")))
        .file(file("tasks.md"), text("## WP01\n- [ ] T001 Title\n"))
        .file(file("spec.md"), text("# Spec\n"))
        .file(file("lanes.json"), text(DetailRoute.lanes("alpha", "lane-a:WP01")))
        .dir(new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a")), ".git")
        .file(new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a/.git")), text("gitdir: elsewhere\n"));
  }

  @Test
  void everyReadOfTheRouteIsMadeUnderTheAuthoredScopeAndTheDetailIsBuiltFromWhatWasRead() {
    DetailFixture fixture = DetailRoute.fixture(root -> {});
    InMemoryTextSource source = populated();

    WorkPackageDetail served = DetailRoute.serviceOver(fixture, source, new AdmissionGate()).workPackageDetail(new MissionId(ID), new WpId("WP01"));

    assertThat(source.readScopes()).as("the scopes of every access, in order").isNotEmpty().containsOnly(ReadScope.AUTHORED);
    assertThat(source.readRefs())
        .contains(
            file("tasks"),
            file("tasks/WP01-one.md"),
            file("tasks.md"),
            file("lanes.json"),
            file("spec.md"),
            file("tasks/WP01-one/review-cycle-1.md"),
            new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a")),
            new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a/.git")));
    assertThat(served.subtasks()).extracting(entry -> entry.title()).containsExactly("Title");
    assertThat(served.reviewCycles()).hasSize(1);
    assertThat(served.workspace().worktreePresent()).isTrue();
    assertThat(served.artifactReferences().spec()).isNotNull();
    assertThat(served.ownedFiles()).hasSize(1);
  }

  @Test
  void aReadUnderTheArtifactScopeWouldBeSeenBecauseTheSourceRecordsTheScope() {
    InMemoryTextSource source = populated();

    source.stat(file("spec.md"), ReadScope.ARTIFACT);

    assertThat(source.readScopes()).containsExactly(ReadScope.ARTIFACT);
  }
}
