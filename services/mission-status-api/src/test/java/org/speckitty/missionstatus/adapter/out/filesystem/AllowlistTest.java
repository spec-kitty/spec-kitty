package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;

/** The explicit read allowlist (FR-010 items 1-6, AC-10a at primitive level): what is classified, what is refused, which modes. */
class AllowlistTest {

  @TempDir Path root;

  private Optional<PathClass> classify(String relative) {
    return Allowlist.classify(root, root.resolve(relative));
  }

  @Test
  void theConstantListsEveryFr010ItemInOrder() {
    assertThat(Allowlist.PATTERNS)
        .containsExactly(
            "<read-dir>/status.events.jsonl",
            "<primary-dir>/meta.json",
            "<primary-dir>/lanes.json",
            ".kittify/config.yaml",
            ".kittify/metadata.yaml",
            ".git/HEAD",
            ".git (pointer file) and <gitdir>/HEAD",
            "kitty-specs/ (names only)",
            ".worktrees/ (names only)",
            ".worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/ (stat only)",
            ".worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/meta.json (stat only)",
            "<primary-dir>/tasks/ (names only; scope AUTHORED)",
            "<primary-dir>/tasks/WP*.md directly under tasks/ (frontmatter and body, 1 MiB; scope AUTHORED)",
            "<primary-dir>/tasks.md (4 MiB; stat for the tasks phase; scope AUTHORED)",
            "<primary-dir>/spec.md (stat only; scope AUTHORED)",
            "<primary-dir>/plan.md (stat only; scope AUTHORED)",
            "<primary-dir>/tasks/<wp-slug>/ (names only; scope AUTHORED)",
            "<primary-dir>/tasks/<wp-slug>/review-cycle-<N>.md (262144 bytes; scope AUTHORED)",
            ".worktrees/<slug>-<lane id>/ (stat only; scope AUTHORED)",
            ".worktrees/<slug>-<lane id>/.git (stat only, no follow; scope AUTHORED)",
            "<primary-dir> and every directory below it (names only; scope ARTIFACT)",
            "every regular file below <primary-dir> except the root status.events.jsonl and status.json (262144 bytes; scope ARTIFACT)");
    assertThat(Allowlist.ENTRIES).hasSameSizeAs(Allowlist.PATTERNS);
  }

  @Test
  void theOwnPrimaryDirectoryFilesAreClassified() {
    assertThat(classify("kitty-specs/m-01ABCDEF/status.events.jsonl")).contains(PathClass.LEDGER);
    assertThat(classify("kitty-specs/m-01ABCDEF/meta.json")).contains(PathClass.MISSION_META);
    assertThat(classify("kitty-specs/m-01ABCDEF/lanes.json")).contains(PathClass.LANES_JSON);
    assertThat(classify("kitty-specs/m-01ABCDEF")).contains(PathClass.MISSION_DIR);
    assertThat(classify("kitty-specs")).contains(PathClass.SPECS_DIR);
  }

  @Test
  void theCoordinationLedgerAndDirectoryAreClassified() {
    assertThat(classify(".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/status.events.jsonl")).contains(PathClass.LEDGER);
    assertThat(classify(".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF")).contains(PathClass.COORD_MISSION_DIR);
    assertThat(classify(".worktrees/m-01ABCDEF-coord")).contains(PathClass.COORD_ROOT);
    assertThat(classify(".worktrees")).contains(PathClass.WORKTREES_DIR);
    assertThat(classify(".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/meta.json")).contains(PathClass.COORD_META);
  }

  @Test
  void theProjectFilesAndTheGitHeadAreClassified() {
    assertThat(classify(".kittify/config.yaml")).contains(PathClass.CONFIG_YAML);
    assertThat(classify(".kittify/metadata.yaml")).contains(PathClass.METADATA_YAML);
    assertThat(classify(".git/HEAD")).contains(PathClass.GIT_HEAD);
    assertThat(classify(".git")).contains(PathClass.GIT_POINTER);
    assertThat(Allowlist.classify(root, root.getParent().resolve("elsewhere").resolve("HEAD"))).contains(PathClass.GITDIR_HEAD);
    assertThat(Allowlist.classify(root, root)).contains(PathClass.PROJECT_ROOT);
  }

  @Test
  void everythingElseInTheTreeIsNotOnTheAllowlist() {
    List<String> refused =
        List.of(
            "tasks/WP01.md",
            "kitty-specs/m-01ABCDEF/notes.md",
            "kitty-specs/m-01ABCDEF/status.json",
            "kitty-specs/m-01ABCDEF/research/notes.md",
            ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/lanes.json",
            ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/status.json",
            ".worktrees/m-01ABCDEF-lane-a/kitty-specs/m-01ABCDEF/status.events.jsonl",
            "config.toml",
            ".kittify/config.toml",
            ".kittify/charter/charter.md",
            ".git/packed-refs",
            ".git/refs/remotes/origin/HEAD",
            ".git/worktrees/lane/HEAD",
            ".git/modules/x/HEAD",
            ".git/refs/heads/main",
            ".git/config",
            "kitty-specs/../secret",
            "kitty-specs/./m/meta.json");
    for (String path : refused) {
      assertThat(classify(path)).as(path).isEmpty();
    }
    assertThat(Allowlist.classify(root, root.getParent().resolve("elsewhere").resolve("config.toml"))).isEmpty();
  }

  @Test
  void classesPermitReadsAndStatsAndNeverAWrite() {
    for (PathClass pathClass : PathClass.values()) {
      for (OpenMode mode : OpenMode.values()) {
        if (!mode.readOnly()) {
          assertThat(Allowlist.permits(pathClass, mode)).as(pathClass + " " + mode).isFalse();
        }
      }
    }
    assertThat(Allowlist.permits(PathClass.LEDGER, OpenMode.READ)).isTrue();
    assertThat(Allowlist.permits(PathClass.SPECS_DIR, OpenMode.LIST)).isTrue();
    assertThat(Allowlist.permits(PathClass.WORKTREES_DIR, OpenMode.LIST)).isTrue();
    assertThat(Allowlist.permits(PathClass.COORD_MISSION_DIR, OpenMode.STAT)).isTrue();
    assertThat(Allowlist.permits(PathClass.COORD_MISSION_DIR, OpenMode.READ)).isFalse();
    assertThat(Allowlist.permits(PathClass.LEDGER, OpenMode.LIST)).isFalse();
    // The coordination copy of meta.json is stat-ed for its existence (DD-105) and never read.
    assertThat(Allowlist.permits(PathClass.COORD_META, OpenMode.STAT)).isTrue();
    assertThat(Allowlist.permits(PathClass.COORD_META, OpenMode.READ)).isFalse();
  }

  @Test
  void aSequenceOfAllowedAccessesHasNoViolation() {
    List<Access> sequence =
        List.of(
            new Access(PathClass.SPECS_DIR, "kitty-specs", OpenMode.LIST),
            new Access(PathClass.MISSION_META, "kitty-specs/m/meta.json", OpenMode.READ),
            new Access(PathClass.LEDGER, "kitty-specs/m/status.events.jsonl", OpenMode.READ));
    assertThat(Allowlist.violations(sequence)).isEmpty();
  }

  @Test
  void anUnclassifiedAccessAndAnyWriteModeAreViolations() {
    Access unclassified = new Access(null, "kitty-specs/m/tasks/WP01.md", OpenMode.READ);
    Access write = new Access(PathClass.LEDGER, "kitty-specs/m/status.events.jsonl", OpenMode.WRITE);
    List<Allowlist.Violation> violations = Allowlist.violations(List.of(unclassified, write));
    assertThat(violations).extracting(Allowlist.Violation::access).containsExactly(unclassified, write);
    for (OpenMode mode : OpenMode.values()) {
      if (!mode.readOnly()) {
        assertThat(Allowlist.violations(List.of(new Access(PathClass.LEDGER, "kitty-specs/m/status.events.jsonl", mode))))
            .as(mode.name())
            .hasSize(1);
      }
    }
  }

  @Test
  void aReadOfTheCoordinationMetaIsAViolationAndAStatOfItIsNot() {
    String path = ".worktrees/m-01ABCDEF-coord/kitty-specs/m-01ABCDEF/meta.json";
    assertThat(Allowlist.violations(List.of(new Access(PathClass.COORD_META, path, OpenMode.READ)))).hasSize(1);
    assertThat(Allowlist.violations(List.of(new Access(PathClass.COORD_META, path, OpenMode.STAT)))).isEmpty();
  }
}
