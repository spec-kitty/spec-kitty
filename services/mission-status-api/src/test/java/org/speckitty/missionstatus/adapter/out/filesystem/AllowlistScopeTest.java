package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

/**
 * FR-011 and AC-11.2 to AC-11.4: the class of an access is a function of the pair (read scope, path). For every new class there is a
 * deliberate forbidden access (red) and its own permitted access (green); what stays forbidden stays refused in every mode under both
 * scopes.
 */
class AllowlistScopeTest {

  private static final String P = "kitty-specs/m-01ABCDEF";
  private static final List<PathClass> NEW_CLASSES =
      List.of(
          PathClass.TASKS_DIR,
          PathClass.WP_FILE,
          PathClass.TASKS_MD,
          PathClass.PLANNING_FILE,
          PathClass.WP_CYCLE_DIR,
          PathClass.WP_CYCLE_FILE,
          PathClass.WORKTREE_LANE,
          PathClass.WORKTREE_LANE_GIT,
          PathClass.ARTIFACT_DIR,
          PathClass.ARTIFACT_FILE);

  @TempDir Path root;

  private Optional<PathClass> classify(ReadScope scope, String relative) {
    return Allowlist.classify(scope, root, root.resolve(relative));
  }

  /** Whether the fence lets {@code mode} touch {@code relative} under {@code scope}: the class the recorder would assign, then the permission. */
  private boolean permitted(ReadScope scope, String relative, OpenMode mode) {
    return Allowlist.classify(scope, root, root.resolve(relative), mode).map(pathClass -> Allowlist.permits(pathClass, mode)).orElse(false);
  }

  // ---- the ten new classes: red and green ----------------------------------------------------------------------------------

  @Test
  void tasksDirAllowsStatAndListAndNeverReadUnderAuthored() {
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks")).contains(PathClass.TASKS_DIR);
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks", OpenMode.LIST)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks", OpenMode.READ)).isFalse();
  }

  @Test
  void wpFileAllowsStatAndReadAndNeverListAndOnlyDirectlyUnderTasks() {
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x.md")).contains(PathClass.WP_FILE);
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x.md", OpenMode.READ)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x.md", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x.md", OpenMode.LIST)).isFalse();
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/wp01.md")).as("case-sensitive WP prefix").isNotEqualTo(Optional.of(PathClass.WP_FILE));
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x.txt")).isNotEqualTo(Optional.of(PathClass.WP_FILE));
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/notes.md", OpenMode.READ)).as("a non-WP file under tasks is not readable").isFalse();
  }

  @Test
  void tasksMdAllowsStatAndReadButNotList() {
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks.md")).contains(PathClass.TASKS_MD);
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks.md", OpenMode.READ)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks.md", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks.md", OpenMode.LIST)).isFalse();
  }

  @Test
  void aReadOfSpecOrPlanUnderAuthoredIsRedAndItsGreenTwinIsTheReadUnderArtifact() {
    for (String planning : List.of("spec.md", "plan.md")) {
      String path = P + "/" + planning;
      assertThat(classify(ReadScope.AUTHORED, path)).contains(PathClass.PLANNING_FILE);
      assertThat(permitted(ReadScope.AUTHORED, path, OpenMode.READ)).as("READ " + planning + " AUTHORED").isFalse();
      assertThat(permitted(ReadScope.AUTHORED, path, OpenMode.STAT)).as("STAT " + planning + " AUTHORED").isTrue();
      assertThat(classify(ReadScope.ARTIFACT, path)).contains(PathClass.ARTIFACT_FILE);
      assertThat(permitted(ReadScope.ARTIFACT, path, OpenMode.READ)).as("READ " + planning + " ARTIFACT").isTrue();
    }
  }

  @Test
  void theArtifactScopeReachesTheAuthoredSourcesWithoutWideningTheAuthoredClasses() {
    for (String authored : List.of("tasks.md", "meta.json", "lanes.json", "tasks/WP01-x.md", "tasks/WP01-x/review-cycle-1.md")) {
      assertThat(classify(ReadScope.ARTIFACT, P + "/" + authored)).as("ARTIFACT " + authored).contains(PathClass.ARTIFACT_FILE);
      assertThat(permitted(ReadScope.ARTIFACT, P + "/" + authored, OpenMode.READ)).as("READ " + authored).isTrue();
    }
    assertThat(classify(ReadScope.AUTHORED, P + "/meta.json")).contains(PathClass.MISSION_META);
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks.md")).contains(PathClass.TASKS_MD);
    assertThat(classify(ReadScope.AUTHORED, P + "/lanes.json")).contains(PathClass.LANES_JSON);
  }

  @Test
  void wpCycleDirAndFileHaveTheirModesAndTheNumberRule() {
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x")).contains(PathClass.WP_CYCLE_DIR);
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x", OpenMode.LIST)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x", OpenMode.READ)).isFalse();
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x/review-cycle-1.md")).contains(PathClass.WP_CYCLE_FILE);
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x/review-cycle-12.md")).contains(PathClass.WP_CYCLE_FILE);
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x/review-cycle-1.md", OpenMode.READ)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, P + "/tasks/WP01-x/review-cycle-1.md", OpenMode.LIST)).isFalse();
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x/review-cycle-01.md")).as("a leading zero is not a cycle file").isEmpty();
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x/notes.md")).isEmpty();
    assertThat(classify(ReadScope.AUTHORED, P + "/tasks/WP01-x/deeper/review-cycle-1.md")).isEmpty();
  }

  @Test
  void worktreeLaneAndItsGitPointerAreStatOnlyAndNeverListedOrRead() {
    assertThat(classify(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a")).contains(PathClass.WORKTREE_LANE);
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a", OpenMode.LIST)).as("LIST .worktrees/<..>/").isFalse();
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a", OpenMode.READ)).isFalse();
    assertThat(classify(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a/.git")).contains(PathClass.WORKTREE_LANE_GIT);
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a/.git", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a/.git", OpenMode.READ)).as("READ .worktrees/<..>/.git").isFalse();
    assertThat(permitted(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a/.git", OpenMode.LIST)).isFalse();
    assertThat(classify(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-lane-a/kitty-specs")).as("nothing below a lane worktree but its .git").isEmpty();
    assertThat(classify(ReadScope.AUTHORED, ".worktrees/m-01ABCDEF-coord")).as("the coordination root keeps its own class").contains(PathClass.COORD_ROOT);
  }

  @Test
  void theFirstListingOfThePrimaryDirectoryIsRedUnderAuthoredAndGreenUnderArtifact() {
    assertThat(classify(ReadScope.AUTHORED, P)).contains(PathClass.MISSION_DIR);
    assertThat(permitted(ReadScope.AUTHORED, P, OpenMode.LIST)).as("LIST <primary-dir> AUTHORED").isFalse();
    assertThat(permitted(ReadScope.AUTHORED, P, OpenMode.REALPATH)).isTrue();
    assertThat(classify(ReadScope.ARTIFACT, P)).contains(PathClass.ARTIFACT_DIR);
    assertThat(permitted(ReadScope.ARTIFACT, P, OpenMode.LIST)).as("LIST <primary-dir> ARTIFACT").isTrue();
    assertThat(permitted(ReadScope.ARTIFACT, P, OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.ARTIFACT, P, OpenMode.REALPATH)).as("containment is an AUTHORED operation").isFalse();
  }

  @Test
  void artifactDirectoriesAndFilesBelowThePrimaryDirectoryHaveTheirModes() {
    assertThat(classify(ReadScope.ARTIFACT, P + "/notes/a.md")).contains(PathClass.ARTIFACT_FILE);
    assertThat(permitted(ReadScope.ARTIFACT, P + "/notes/a.md", OpenMode.READ)).isTrue();
    assertThat(permitted(ReadScope.ARTIFACT, P + "/notes/a.md", OpenMode.STAT)).isTrue();
    assertThat(permitted(ReadScope.ARTIFACT, P + "/notes", OpenMode.LIST)).as("a directory below the primary directory").isTrue();
    assertThat(Allowlist.classify(ReadScope.ARTIFACT, root, root.resolve(P + "/notes"), OpenMode.LIST)).contains(PathClass.ARTIFACT_DIR);
    assertThat(permitted(ReadScope.ARTIFACT, P + "/sub/status.events.jsonl", OpenMode.READ)).as("a nested ledger is an ordinary artifact").isTrue();
    assertThat(permitted(ReadScope.ARTIFACT, P + "/sub/status.json", OpenMode.READ)).as("only the root status record is excluded").isTrue();
  }

  @Test
  void nothingOfTheArtifactClassesExistsUnderAuthored() {
    for (String path : List.of(P + "/notes/a.md", P + "/notes", P + "/other.txt")) {
      assertThat(classify(ReadScope.AUTHORED, path)).as(path).isNotEqualTo(Optional.of(PathClass.ARTIFACT_DIR)).isNotEqualTo(Optional.of(PathClass.ARTIFACT_FILE));
    }
  }

  // ---- AC-11.2: write, and the root status record --------------------------------------------------------------------------

  @Test
  void aWriteToAnyClassIsRefused() {
    for (PathClass pathClass : PathClass.values()) {
      for (OpenMode mode : OpenMode.values()) {
        if (!mode.readOnly()) {
          assertThat(Allowlist.violations(List.of(new Access(pathClass, "x", mode)))).as(pathClass + " " + mode).hasSize(1);
        }
      }
    }
  }

  @Test
  void theRootStatusRecordIsOnNoClassUnderEitherScopeInAnyCase() {
    for (String record : List.of("status.json", "Status.JSON", "STATUS.JSON", "Status.Json")) {
      for (ReadScope scope : EnumSet.of(ReadScope.AUTHORED, ReadScope.ARTIFACT)) {
        for (OpenMode mode : OpenMode.values()) {
          assertThat(permitted(scope, P + "/" + record, mode)).as(scope + " " + mode + " " + record).isFalse();
        }
        assertThat(classify(scope, P + "/" + record)).isEmpty();
      }
    }
  }

  // ---- AC-11.4: what stays forbidden --------------------------------------------------------------------------------------

  @Test
  void whatStaysOutsideEveryClassIsRefusedInEveryModeUnderBothScopes() {
    List<String> forbidden =
        List.of(
            P + "/status.json",
            P + "/Status.JSON",
            ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/status.json",
            ".git/refs/heads/main",
            ".git/packed-refs",
            "config.toml",
            ".kittify/config.toml",
            P + "/../secret",
            "kitty-specs/./m-01ABCDEF/meta.json",
            ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/lanes.json");
    for (ReadScope scope : EnumSet.of(ReadScope.AUTHORED, ReadScope.ARTIFACT)) {
      for (String path : forbidden) {
        for (OpenMode mode : OpenMode.values()) {
          assertThat(permitted(scope, path, mode)).as(scope + " " + mode + " " + path).isFalse();
        }
      }
      Path elsewhere = root.getParent().resolve("elsewhere").resolve("config.toml");
      for (OpenMode mode : OpenMode.values()) {
        assertThat(Allowlist.classify(scope, root, elsewhere, mode)).as("outside the root " + scope + " " + mode).isEmpty();
      }
    }
  }

  @Test
  void theCoordinationMetaIsNeverReadUnderEitherScope() {
    String coordMeta = ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/meta.json";
    assertThat(permitted(ReadScope.AUTHORED, coordMeta, OpenMode.READ)).isFalse();
    assertThat(permitted(ReadScope.ARTIFACT, coordMeta, OpenMode.READ)).isFalse();
    assertThat(classify(ReadScope.ARTIFACT, coordMeta)).isEmpty();
    assertThat(classify(ReadScope.AUTHORED, coordMeta)).contains(PathClass.COORD_META);
  }

  @Test
  void everythingOutsideThePrimaryDirectoryIsUnclassifiedUnderArtifact() {
    for (String path : List.of("kitty-specs", ".kittify/config.yaml", ".git/HEAD", ".worktrees", ".worktrees/m-01ABCDEF-coord", ".worktrees/m-01ABCDEF-lane-a/.git", "tasks/WP01.md", "")) {
      assertThat(classify(ReadScope.ARTIFACT, path)).as(path).isEmpty();
    }
    assertThat(Allowlist.classify(ReadScope.ARTIFACT, root, root.getParent().resolve("elsewhere").resolve("HEAD"))).isEmpty();
  }

  @Test
  void theControlEveryNewClassHasAPathPermittedForItsModes() {
    List<String> samples =
        List.of(
            P + "/tasks",
            P + "/tasks/WP01-x.md",
            P + "/tasks.md",
            P + "/spec.md",
            P + "/tasks/WP01-x",
            P + "/tasks/WP01-x/review-cycle-3.md",
            ".worktrees/m-01ABCDEF-lane-a",
            ".worktrees/m-01ABCDEF-lane-a/.git");
    Set<PathClass> seen = EnumSet.noneOf(PathClass.class);
    for (String sample : samples) {
      PathClass pathClass = classify(ReadScope.AUTHORED, sample).orElseThrow();
      seen.add(pathClass);
      assertThat(Allowlist.permits(pathClass, OpenMode.STAT)).as(sample).isTrue();
    }
    seen.add(classify(ReadScope.ARTIFACT, P).orElseThrow());
    seen.add(classify(ReadScope.ARTIFACT, P + "/a.md").orElseThrow());
    assertThat(seen).containsAll(NEW_CLASSES);
  }

  @Test
  void theGreenTwinOfTheLedgerIsReadableUnderAuthoredAndUnclassifiedUnderArtifact() {
    String ledger = P + "/status.events.jsonl";
    assertThat(classify(ReadScope.AUTHORED, ledger)).contains(PathClass.LEDGER);
    assertThat(permitted(ReadScope.AUTHORED, ledger, OpenMode.READ)).isTrue();
    assertThat(classify(ReadScope.ARTIFACT, ledger)).isEmpty();
    assertThat(permitted(ReadScope.ARTIFACT, ledger, OpenMode.READ)).isFalse();
    assertThat(classify(ReadScope.ARTIFACT, P + "/Status.Events.JSONL")).as("the root ledger in another case").isEmpty();
  }

  @Test
  void theUnscopedClassifyIsTheAuthoredScope() {
    assertThat(Allowlist.classify(root, root.resolve(P + "/tasks/WP01-x.md"))).contains(PathClass.WP_FILE);
    assertThat(Allowlist.classify(root, root.resolve(P + "/spec.md"))).contains(PathClass.PLANNING_FILE);
  }

  @Test
  void theConstantHasTwentyTwoEntriesTheLastElevenBeingTheNewOnes() {
    assertThat(Allowlist.ENTRIES).hasSize(22);
    assertThat(Allowlist.ENTRIES.subList(11, 22).stream().map(Allowlist.Entry::pathClass).toList())
        .containsExactly(
            PathClass.TASKS_DIR,
            PathClass.WP_FILE,
            PathClass.TASKS_MD,
            PathClass.PLANNING_FILE,
            PathClass.PLANNING_FILE,
            PathClass.WP_CYCLE_DIR,
            PathClass.WP_CYCLE_FILE,
            PathClass.WORKTREE_LANE,
            PathClass.WORKTREE_LANE_GIT,
            PathClass.ARTIFACT_DIR,
            PathClass.ARTIFACT_FILE);
    assertThat(Allowlist.PATTERNS.subList(11, 22)).allSatisfy(pattern -> assertThat(pattern).containsAnyOf("scope AUTHORED", "scope ARTIFACT"));
  }
}
