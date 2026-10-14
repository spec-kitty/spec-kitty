package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.MID8;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.lanes;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.writeAtRoot;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.function.Consumer;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkspaceView;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * The workspace of the detail (FR-010, AC-3.5, AC-10.1 to AC-10.3, AC-3.9, rows W3, T8 and T9): the lane and branch from {@code lanes.json},
 * {@code worktreePresent} from two {@code lstat}s of {@code .worktrees/<slug>-<lane id>} and its {@code .git} entry, and the refusals of a
 * {@code lanes.json} that cannot be used, which are the Mission's for every one of its Work Packages. Nothing runs and nothing is opened.
 */
class WorkPackageDetailWorkspaceTest {

  private static WorkspaceView workspace(DetailFixture fixture) {
    return detail(fixture, "WP01").workspace();
  }

  private static DetailFixture withLane(Consumer<Path> extras) {
    return fixture(
        root -> {
          write(root, "lanes.json", lanes("alpha", "lane-a:WP01", "lane-planning:WP02"));
          extras.accept(root);
        });
  }

  private static void gitFile(Path root) {
    writeAtRoot(root, ".worktrees/alpha-lane-a/.git", "gitdir: elsewhere\n");
  }

  // ---- lane and branch -----------------------------------------------------------------------------------------------------------------

  @Test
  void aWorkPackageInACodeLaneHasItsLaneAndItsBranchAndThePlanningBranchOfItsFile() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: release/3.x"));
              write(root, "lanes.json", lanes("alpha", "lane-a:WP01"));
            });

    WorkspaceView served = workspace(fixture);

    assertThat(served.laneId()).isEqualTo("lane-a");
    assertThat(served.laneBranch()).isEqualTo("kitty/mission-alpha-lane-a");
    assertThat(served.planningBranch()).isEqualTo("release/3.x");
    assertThat(served.worktreePresent()).isFalse();
  }

  @Test
  void thePlanningLaneHasNoBranchAndNoWorktreeEvenWhenADirectoryOfThatNameExists() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One"));
              write(root, "lanes.json", lanes("alpha", "lane-planning:WP01"));
              writeAtRoot(root, ".worktrees/alpha-lane-planning/.git", "gitdir: elsewhere\n");
            });

    WorkspaceView served = workspace(fixture);

    assertThat(served.laneId()).isEqualTo("lane-planning");
    assertThat(served.laneBranch()).isNull();
    assertThat(served.worktreePresent()).isFalse();
  }

  @Test
  void aWorkPackageInNoLaneAndAMissionWithoutLanesJsonHaveNullLaneMembersButKeepThePlanningBranch() {
    DetailFixture noLane = fixture(root -> {
      write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: main"));
      write(root, "lanes.json", lanes("alpha", "lane-a:WP09"));
    });
    DetailFixture noFile = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: main")));

    assertThat(workspace(noLane)).isEqualTo(new WorkspaceView(null, null, "main", false));
    assertThat(workspace(noFile)).isEqualTo(new WorkspaceView(null, null, "main", false));
  }

  @Test
  void aPlanningBranchOfMoreThan255CharactersIsNullAndOneOf255IsServed() {
    DetailFixture at = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: " + "b".repeat(255))));
    DetailFixture over = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: " + "b".repeat(256))));
    DetailFixture path = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "planning_base_branch: /home/someone/private")));

    assertThat(workspace(at).planningBranch()).hasSize(255);
    assertThat(workspace(over).planningBranch()).isNull();
    assertThat(workspace(path).planningBranch()).as("a strict nullable field that cannot be shown is null (M14), the Work Package is served").isNull();
    assertThat(path.diagnostics()).isEmpty();
  }

  @Test
  void aLaneIdThatFailsTheContractPatternIsNullWithItsBranchAndItsWorktree() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "lanes.json", lanes("alpha", "lane a:WP01"));
              writeAtRoot(root, ".worktrees/alpha-lane a/.git", "gitdir: elsewhere\n");
            });

    WorkspaceView served = workspace(fixture);

    assertThat(served.laneId()).isNull();
    assertThat(served.laneBranch()).isNull();
    assertThat(served.worktreePresent()).isFalse();
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void aBranchThatFailsThePatternIsNullAndTheLaneIsStillServed() {
    DetailFixture fixture = fixture(root -> write(root, "lanes.json", lanes("alpha", "lane_-a:WP01")));

    WorkspaceView served = workspace(fixture);

    assertThat(served.laneId()).isEqualTo("lane_-a");
    assertThat(served.laneBranch()).isEqualTo("kitty/mission-alpha-lane_-a");
  }

  // ---- worktreePresent (AC-10.3) ---------------------------------------------------------------------------------------------------------

  @Test
  void theDirectoryWithAGitFileOrAGitDirectoryIsPresent() {
    DetailFixture file = withLane(WorkPackageDetailWorkspaceTest::gitFile);
    DetailFixture directory = withLane(root -> DetailRoute.directory(root, ".worktrees/alpha-lane-a/.git"));

    assertThat(workspace(file).worktreePresent()).isTrue();
    assertThat(workspace(directory).worktreePresent()).isTrue();
    assertThat(workspace(file).laneId()).isEqualTo("lane-a");
  }

  static Stream<Consumer<Path>> absentRows() {
    return Stream.of(
        root -> {},
        root -> DetailRoute.directory(root, ".worktrees/alpha-lane-a"),
        root -> DetailRoute.directory(root, ".worktrees"),
        root -> writeAtRoot(root, ".worktrees/alpha-lane-a", "a file where the directory belongs\n"),
        root -> {
          DetailRoute.directory(root, "elsewhere/.git");
          DetailRoute.symlink(root.resolve(".worktrees/alpha-lane-a"), root.resolve("elsewhere"));
        },
        root -> {
          writeAtRoot(root, "elsewhere", "gitdir: elsewhere\n");
          DetailRoute.symlink(root.resolve(".worktrees/alpha-lane-a/.git"), root.resolve("elsewhere"));
        },
        root -> {
          DetailRoute.directory(root, "elsewhere");
          DetailRoute.symlink(root.resolve(".worktrees/alpha-lane-a/.git"), root.resolve("elsewhere"));
        });
  }

  /** The false rows: absent, a directory without {@code .git}, an empty {@code .worktrees}, a file, and a link on the directory or on its {@code .git} (V7). */
  @ParameterizedTest
  @MethodSource("absentRows")
  void everyOtherStateIsAbsent(Consumer<Path> extras) {
    DetailFixture fixture = withLane(extras);

    assertThat(workspace(fixture).worktreePresent()).isFalse();
    assertThat(workspace(fixture).laneId()).as("the lane is the manifest's whatever the host has").isEqualTo("lane-a");
  }

  @Test
  void aSymbolicLinkIsNotFollowedAndItsTargetIsNeverTouched() {
    DetailFixture fixture =
        withLane(
            root -> {
              DetailRoute.directory(root, "elsewhere/.git");
              DetailRoute.symlink(root.resolve(".worktrees/alpha-lane-a"), root.resolve("elsewhere"));
            });
    fixture.recorder().clear();

    detail(fixture, "WP01");

    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().contains("elsewhere"));
    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().startsWith(".worktrees/alpha-lane-a/"));
  }

  /** AC-10.3: only STAT, on the two paths; nothing is listed or read below {@code .worktrees/<..>/}. */
  @Test
  void onlyTheTwoPathsAreStattedAndNothingBelowTheWorktreeIsListedOrRead() {
    DetailFixture fixture = withLane(root -> {
      gitFile(root);
      writeAtRoot(root, ".worktrees/alpha-lane-a/src/secret.txt", "secret\n");
    });
    fixture.recorder().clear();

    detail(fixture, "WP01");

    assertThat(fixture.recorder().accesses())
        .filteredOn(access -> access.pathClass() == PathClass.WORKTREE_LANE || access.pathClass() == PathClass.WORKTREE_LANE_GIT)
        .extracting(access -> access.mode() + " " + access.path())
        .containsOnly("STAT .worktrees/alpha-lane-a", "STAT .worktrees/alpha-lane-a/.git")
        .contains("STAT .worktrees/alpha-lane-a/.git");
    assertThat(fixture.recorder().accesses())
        .filteredOn(access -> access.path().startsWith(".worktrees/alpha-lane-a"))
        .allSatisfy(access -> assertThat(access.mode()).isEqualTo(OpenMode.STAT));
    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().contains("secret"));
    assertThat(fixture.recorder().violations()).isEmpty();
  }

  @Test
  void aHostWithNoWorktreesAtAllAnswersFalseForEveryRow() {
    DetailFixture fixture = withLane(root -> {});

    assertThat(workspace(fixture)).isEqualTo(new WorkspaceView("lane-a", "kitty/mission-alpha-lane-a", null, false));
  }

  // ---- lanes.json that cannot be used (W3) -----------------------------------------------------------------------------------------------

  private static String lanesWith(String from, String to) {
    String text = lanes("alpha", "lane-a:WP01");
    assertThat(text).contains(from);
    return text.replace(from, to);
  }

  static Stream<String> refusedFiles() {
    return Stream.of(
        "not json at all",
        "[]",
        "{}",
        lanesWith("\"wp_ids\":[\"WP01\"]", "\"wp_ids\":\"WP01\""),
        lanesWith("\"lane_id\":\"lane-a\"", "\"lane_id\":7"),
        lanesWith("\"wp_ids\":[\"WP01\"]", "\"wp_ids\":[7]"),
        lanesWith("\"mission_slug\":\"alpha\"", "\"mission_slug\":7"),
        lanes("alpha", "lane-a:WP01").replace("\"mission_slug\":\"alpha\"", "\"feature_slug\":\"alpha\""),
        "\ufeff" + lanes("alpha", "lane-a:WP01"));
  }

  /** AC-3.5: a corrupt, legacy-shape or stricter-than-the-oracle file is the Mission's: 500 for every Work Package, and one diagnostic per request. */
  @ParameterizedTest
  @MethodSource("refusedFiles")
  void alanesJsonThatCannotBeUsedRefusesEveryWorkPackageOfTheMissionWithOneDiagnosticPerRequest(String content) {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP02-two.md", wpFile("WP02", "Two"));
              write(root, "lanes.json", content);
            });

    for (String wp : List.of("WP01", "WP02")) {
      fixture.recorder().clear();
      int before = fixture.diagnostics().size();
      assertThatThrownBy(() -> detail(fixture, wp)).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
      assertThat(fixture.diagnostics().subList(before, fixture.diagnostics().size())).containsExactly(new Diagnostic(DiagnosticCode.SOURCE_UNREADABLE, MID8, null));
    }
  }

  @Test
  void theCurrentShapeIsServedAsTheControlOfTheLegacyAndCorruptRows() {
    DetailFixture fixture = fixture(root -> write(root, "lanes.json", lanes("alpha", "lane-a:WP01")));

    assertThat(workspace(fixture).laneId()).isEqualTo("lane-a");
  }

  /** AC-3.9: 1048576 bytes are read and 1048577 are refused, both made here; the cap is applied by the bytes read. */
  @Test
  void aLanesJsonOfExactlyTheCapIsReadAndOneByteMoreIsRefused() {
    String base = lanes("alpha", "lane-a:WP01");
    String atCap = base + " ".repeat(1_048_576 - base.getBytes(StandardCharsets.UTF_8).length);
    DetailFixture at = fixture(root -> write(root, "lanes.json", atCap));
    DetailFixture over = fixture(root -> write(root, "lanes.json", atCap + " "));

    assertThat(atCap.getBytes(StandardCharsets.UTF_8)).hasSize(1_048_576);
    assertThat(workspace(at).laneId()).isEqualTo("lane-a");
    assertThatThrownBy(() -> detail(over, "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    assertThat(over.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.SOURCE_UNREADABLE, MID8, null));
  }

  @Test
  void aLanesJsonThatIsADirectoryIsRefusedLikeOneThatCannotBeRead() {
    DetailFixture fixture = fixture(root -> DetailRoute.directory(root, "kitty-specs/alpha/lanes.json"));

    assertThatThrownBy(() -> detail(fixture, "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
  }

  @Test
  void lanesJsonIsReadWheneverTheRouteRunsAndIsTheOnlyFileReadForTheWorkspace() throws Exception {
    DetailFixture fixture = withLane(WorkPackageDetailWorkspaceTest::gitFile);
    fixture.recorder().clear();

    detail(fixture, "WP01");

    assertThat(fixture.recorder().accesses())
        .filteredOn(access -> access.pathClass() == PathClass.LANES_JSON && access.mode() == OpenMode.READ)
        .extracting(access -> access.path())
        .isNotEmpty()
        .containsOnly("kitty-specs/alpha/lanes.json");
    assertThat(Files.exists(fixture.root().resolve("kitty-specs/alpha/lanes.json"))).isTrue();
  }
}
