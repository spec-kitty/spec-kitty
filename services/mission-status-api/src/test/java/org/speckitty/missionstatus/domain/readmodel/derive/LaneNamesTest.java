package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * {@link LaneNames} against the oracle's {@code lane_branch_name} and {@code worktree_dir_name}: each row below was run through the Python
 * functions. A mid8 tail (eight Crockford characters after the last hyphen) makes the stale {@code NNN-} prefix of the slug go; a slug
 * without one is used verbatim.
 */
class LaneNamesTest {

  @ParameterizedTest
  @CsvSource({
    "alpha-mission,kitty/mission-alpha-mission-lane-a",
    "083-foo,kitty/mission-083-foo-lane-a",
    "083-foo-01KNXQS9,kitty/mission-foo-01KNXQS9-lane-a",
    "foo-01KNXQS9,kitty/mission-foo-01KNXQS9-lane-a",
    "001-bar-baz,kitty/mission-001-bar-baz-lane-a",
    "08-foo,kitty/mission-08-foo-lane-a",
    "1234-foo,kitty/mission-1234-foo-lane-a",
    "083-,kitty/mission-083--lane-a",
    "foo-01KNXQSU,kitty/mission-foo-01KNXQSU-lane-a",
    "foo-01knxqs9,kitty/mission-foo-01knxqs9-lane-a",
    "mission-01KNXQS9-01KNXQS9,kitty/mission-mission-01KNXQS9-01KNXQS9-lane-a",
    "999-a-ABCDEFGH,kitty/mission-a-ABCDEFGH-lane-a",
    "x-ILOUILOU,kitty/mission-x-ILOUILOU-lane-a",
    "0831-y-01KNXQS9,kitty/mission-0831-y-01KNXQS9-lane-a",
    "-01KNXQS9,kitty/mission--01KNXQS9-lane-a",
    "083--01KNXQS9,kitty/mission--01KNXQS9-lane-a"
  })
  void theBranchOfACodeLaneIsTheOraclesBranch(String slug, String branch) {
    assertThat(LaneNames.codeLaneBranch(slug, "lane-a")).isEqualTo(branch);
  }

  @Test
  void aDigitOfAnyScriptIsADigitOfTheNumericPrefixAsInPython() {
    String arabic = "\u0663\u0663\u0663-x-01KNXQS9";

    assertThat(LaneNames.codeLaneBranch(arabic, "lane-a")).isEqualTo("kitty/mission-x-01KNXQS9-lane-a");
  }

  @Test
  void theWorktreeDirectoryIsTheRecordedSlugAndTheLaneIdVerbatim() {
    assertThat(LaneNames.worktreeDirName("083-foo-01KNXQS9", "lane-a")).isEqualTo("083-foo-01KNXQS9-lane-a");
    assertThat(LaneNames.worktreeDirName("alpha-mission", "lane-b")).isEqualTo("alpha-mission-lane-b");
  }

  @Test
  void aLaneIdFitsWhenItHasThePatternAndAtMost64Characters() {
    assertThat(LaneNames.fittingLaneId("lane-a")).isEqualTo("lane-a");
    assertThat(LaneNames.fittingLaneId("a".repeat(64))).hasSize(64);
    assertThat(LaneNames.fittingLaneId("a".repeat(65))).isNull();
    assertThat(LaneNames.fittingLaneId("-lane")).isNull();
    assertThat(LaneNames.fittingLaneId("lane a")).isNull();
    assertThat(LaneNames.fittingLaneId("lane/a")).isNull();
    assertThat(LaneNames.fittingLaneId("")).isNull();
    assertThat(LaneNames.fittingLaneId("lane-\u00e9")).isNull();
  }

  @Test
  void aBranchFitsWhenItHasThePatternAndAtMost255Characters() {
    assertThat(LaneNames.fittingBranch("kitty/mission-a-lane-a")).isEqualTo("kitty/mission-a-lane-a");
    assertThat(LaneNames.fittingBranch("a".repeat(255))).hasSize(255);
    assertThat(LaneNames.fittingBranch("a".repeat(256))).isNull();
    assertThat(LaneNames.fittingBranch("/kitty")).isNull();
    assertThat(LaneNames.fittingBranch("kitty mission")).isNull();
  }

  @Test
  void aPlanningBranchIsLimitedInLengthOnly() {
    assertThat(LaneNames.fittingPlanningBranch(null)).isNull();
    assertThat(LaneNames.fittingPlanningBranch("main")).isEqualTo("main");
    assertThat(LaneNames.fittingPlanningBranch("x".repeat(255))).hasSize(255);
    assertThat(LaneNames.fittingPlanningBranch("x".repeat(256))).isNull();
    assertThat(LaneNames.fittingPlanningBranch("release/3.x")).isEqualTo("release/3.x");
  }

  @Test
  void thePlanningLaneHasItsOwnId() {
    assertThat(LaneNames.PLANNING_LANE_ID).isEqualTo("lane-planning");
  }
}
