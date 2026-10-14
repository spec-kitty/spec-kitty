package org.speckitty.missionstatus.application.query.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.JsonLanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkspaceView;
import org.speckitty.missionstatus.testsupport.InMemoryTextSource;

/**
 * {@link WorkspaceReader} over the in-memory port, which makes the stat rule exact: every read is made under the authored scope (the in-memory
 * port registers an entry under every scope, so the scope the reader asks for is asserted by {@code readScopes()}, not assumed), the worktree is
 * two stats, a link anywhere on the way reads as absent and any other fault is thrown.
 */
class WorkspaceReaderTest {

  private static final MissionRef MISSION = new MissionRef("alpha");
  private static final FileRef LANES = new FileRef.MissionFile(MISSION, RelativePath.of("lanes.json"));
  private static final FileRef DIRECTORY = new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a"));
  private static final FileRef GIT = new FileRef.ProjectFile(RelativePath.of(".worktrees/alpha-lane-a/.git"));

  private static byte[] lanes(String laneId) {
    return DetailRoute.lanes("alpha", laneId + ":WP01").getBytes(StandardCharsets.UTF_8);
  }

  private static WorkspaceReader reader(InMemoryTextSource source) {
    return new WorkspaceReader(source, new JsonLanesDecoder());
  }

  @Test
  void aWorktreeThatIsADirectoryWithAGitFileIsPresentAndEveryReadIsUnderTheAuthoredScope() {
    InMemoryTextSource source = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(DIRECTORY, ".git").file(GIT, new byte[] {'g'});

    WorkspaceView served = reader(source).read(MISSION, "alpha", "WP01", "main");

    assertThat(served).isEqualTo(new WorkspaceView("lane-a", "kitty/mission-alpha-lane-a", "main", true));
    assertThat(source.readRefs()).containsExactly(LANES, DIRECTORY, GIT);
    assertThat(source.readScopes()).hasSize(3).containsOnly(ReadScope.AUTHORED);
  }

  @Test
  void aGitDirectoryIsPresentToo() {
    InMemoryTextSource source = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(DIRECTORY, ".git").dir(GIT, "refs");

    assertThat(reader(source).read(MISSION, "alpha", "WP01", null).worktreePresent()).isTrue();
  }

  @Test
  void aMissingLanesJsonAndAWorkPackageInNoLaneHaveNullLaneMembersAndTheGivenPlanningBranch() {
    assertThat(reader(new InMemoryTextSource()).read(MISSION, "alpha", "WP01", "main")).isEqualTo(new WorkspaceView(null, null, "main", false));
    InMemoryTextSource other = new InMemoryTextSource().file(LANES, DetailRoute.lanes("alpha", "lane-a:WP09").getBytes(StandardCharsets.UTF_8));
    assertThat(reader(other).read(MISSION, "alpha", "WP01", null)).isEqualTo(new WorkspaceView(null, null, null, false));
    assertThat(other.readRefs()).containsExactly(LANES);
  }

  @Test
  void aBranchOfMoreThan255CharactersIsNullAndTheWorktreeIsStillLookedFor() {
    String slug = "s".repeat(300);
    FileRef directory = new FileRef.ProjectFile(RelativePath.of(".worktrees/" + slug + "-lane-a"));
    FileRef git = new FileRef.ProjectFile(RelativePath.of(".worktrees/" + slug + "-lane-a/.git"));
    InMemoryTextSource source = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(directory, ".git").file(git, new byte[] {'g'});

    WorkspaceView served = reader(source).read(MISSION, slug, "WP01", null);

    assertThat(served.laneId()).isEqualTo("lane-a");
    assertThat(served.laneBranch()).isNull();
    assertThat(served.worktreePresent()).isTrue();
  }

  @Test
  void aSlugThatIsNoPathSegmentNamesNoWorktree() {
    InMemoryTextSource source = new InMemoryTextSource().file(LANES, lanes("lane-a"));

    WorkspaceView served = reader(source).read(MISSION, "a/b", "WP01", null);

    assertThat(served.worktreePresent()).isFalse();
    assertThat(served.laneId()).isEqualTo("lane-a");
    assertThat(source.readRefs()).containsExactly(LANES);
  }

  @Test
  void aLinkOnTheWayReadsAsAbsentButEveryOtherFaultIsThrown() {
    InMemoryTextSource linked = new InMemoryTextSource().file(LANES, lanes("lane-a")).fault(DIRECTORY, TextFault.Kind.PATH_REFUSED);
    InMemoryTextSource gitLinked = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(DIRECTORY, ".git").link(GIT);

    assertThat(reader(linked).read(MISSION, "alpha", "WP01", null).worktreePresent()).isFalse();
    assertThat(reader(gitLinked).read(MISSION, "alpha", "WP01", null).worktreePresent()).isFalse();
    for (TextFault.Kind kind : new TextFault.Kind[] {TextFault.Kind.DIR_UNREADABLE, TextFault.Kind.FILE_UNREADABLE, TextFault.Kind.VANISHED}) {
      InMemoryTextSource denied = new InMemoryTextSource().file(LANES, lanes("lane-a")).fault(DIRECTORY, kind);
      assertThatThrownBy(() -> reader(denied).read(MISSION, "alpha", "WP01", null)).isInstanceOfSatisfying(TextFault.class, fault -> assertThat(fault.kind()).isEqualTo(kind));
    }
    InMemoryTextSource gitDenied = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(DIRECTORY, ".git").fault(GIT, TextFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(() -> reader(gitDenied).read(MISSION, "alpha", "WP01", null)).isInstanceOf(TextFault.class);
  }

  @Test
  void aFileInPlaceOfTheDirectoryAndADirectoryWithoutGitAreAbsent() {
    InMemoryTextSource file = new InMemoryTextSource().file(LANES, lanes("lane-a")).file(DIRECTORY, new byte[] {'x'});
    InMemoryTextSource husk = new InMemoryTextSource().file(LANES, lanes("lane-a")).dir(DIRECTORY, "src");

    assertThat(reader(file).read(MISSION, "alpha", "WP01", null).worktreePresent()).isFalse();
    assertThat(reader(husk).read(MISSION, "alpha", "WP01", null).worktreePresent()).isFalse();
  }

  @Test
  void aLanesJsonThatCannotBeUsedIsRefusedAndAFaultOfThePortIsThrown() {
    assertThatThrownBy(() -> reader(new InMemoryTextSource().file(LANES, "nonsense".getBytes(StandardCharsets.UTF_8))).read(MISSION, "alpha", "WP01", null)).isInstanceOf(ReadRefused.class);
    assertThatThrownBy(() -> reader(new InMemoryTextSource().dir(LANES, "a")).read(MISSION, "alpha", "WP01", null)).isInstanceOf(ReadRefused.class);
    assertThatThrownBy(() -> reader(new InMemoryTextSource().file(LANES, new byte[WorkspaceReader.LANES_CAP_BYTES + 1])).read(MISSION, "alpha", "WP01", null)).isInstanceOf(ReadRefused.class);
    assertThatThrownBy(() -> reader(new InMemoryTextSource().fault(LANES, TextFault.Kind.FILE_UNREADABLE)).read(MISSION, "alpha", "WP01", null)).isInstanceOf(TextFault.class);
    assertThat(WorkspaceReader.LANES_CAP_BYTES).isEqualTo(1_048_576);
  }
}
