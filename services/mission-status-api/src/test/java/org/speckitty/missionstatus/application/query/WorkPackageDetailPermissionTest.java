package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.MID8;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.cycleFile;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.detail;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.lanes;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.writeAtRoot;

import java.nio.file.AccessDeniedException;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.PermissionCase;
import org.speckitty.missionstatus.testsupport.PermissionCase.Leg;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture;

/**
 * The permission cases of AC-10.3 and rows M4b (a review-cycle directory that cannot be listed) and the worktree stat of FR-010 (a stat that
 * fails other than "absent"), both legs under D-32 and D-101. Two case ids, each with exactly one injected-fault test and one real-permission
 * test: {@code AC-10.3/worktree-stat-denied} and {@code AC-10.3/cycle-directory-denied}. The real leg skips by assumption, and records
 * {@code not run: precondition unmet: <test id>}, when the operating system does not refuse the user (a root runner).
 */
class WorkPackageDetailPermissionTest {

  private static DetailFixture withWorktree() {
    return fixture(
        root -> {
          write(root, "lanes.json", lanes("alpha", "lane-a:WP01"));
          writeAtRoot(root, ".worktrees/alpha-lane-a/.git", "gitdir: elsewhere\n");
        });
  }

  private static DetailFixture withCycle() {
    return fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00")));
  }

  private static void assertSourceUnreadable(DetailFixture fixture) {
    assertThatThrownBy(() -> detail(fixture, "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    assertThat(fixture.diagnostics()).containsExactly(new Diagnostic(DiagnosticCode.SOURCE_UNREADABLE, MID8, null));
  }

  private static String id(TestInfo info) {
    return info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName();
  }

  // ---- the stat of the lane worktree -------------------------------------------------------------------------------------------------------

  @Test
  @PermissionCase(value = "AC-10.3/worktree-stat-denied", leg = Leg.INJECTED)
  void aStatOfTheLaneWorktreeThatFailsWithPermissionDeniedIsSourceUnreadable() {
    DetailFixture fixture = withWorktree();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WORKTREE_LANE && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));

    assertSourceUnreadable(fixture);
  }

  @Test
  @PermissionCase(value = "AC-10.3/worktree-stat-denied", leg = Leg.REAL)
  void aLaneWorktreeTheOperatingSystemWillNotLetTheUserStatIsSourceUnreadable(TestInfo info) {
    DetailFixture fixture = withWorktree();
    Path worktree = fixture.root().resolve(".worktrees/alpha-lane-a");

    try (RealPermissionFixture ignored = RealPermissionFixture.refusedForThisUser(worktree, id(info))) {
      assertSourceUnreadable(fixture);
    }
  }

  @Test
  void aStatOfTheGitEntryThatFailsIsSourceUnreadableToo() {
    DetailFixture fixture = withWorktree();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WORKTREE_LANE_GIT && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));

    assertSourceUnreadable(fixture);
  }

  // ---- the review-cycle directory ----------------------------------------------------------------------------------------------------------

  @Test
  @PermissionCase(value = "AC-10.3/cycle-directory-denied", leg = Leg.INJECTED)
  void aReviewCycleDirectoryThatCannotBeListedIsSourceUnreadable() {
    DetailFixture fixture = withCycle();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WP_CYCLE_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));

    assertSourceUnreadable(fixture);
  }

  @Test
  @PermissionCase(value = "AC-10.3/cycle-directory-denied", leg = Leg.REAL)
  void aReviewCycleDirectoryTheOperatingSystemWillNotLetTheUserListIsSourceUnreadable(TestInfo info) {
    DetailFixture fixture = withCycle();
    Path directory = fixture.root().resolve("kitty-specs/alpha/tasks/WP01-one");

    try (RealPermissionFixture ignored = RealPermissionFixture.refusedForThisUser(directory, id(info))) {
      assertSourceUnreadable(fixture);
    }
  }

  @Test
  void aCycleFileThatCannotBeReadIsStillAnEntryWithNullMembers() {
    DetailFixture fixture = withCycle();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WP_CYCLE_FILE && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));

    assertThat(detail(fixture, "WP01").reviewCycles()).singleElement().satisfies(entry -> {
      assertThat(entry.reviewer()).isNull();
      assertThat(entry.reviewedAt()).isNull();
      assertThat(entry.cycleNumber()).isEqualTo(1);
    });
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void aCycleFileWhoseStatFailsIsSourceUnreadable() {
    DetailFixture fixture = withCycle();
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WP_CYCLE_FILE && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));

    assertSourceUnreadable(fixture);
  }

  // ---- tasks.md and lanes.json -------------------------------------------------------------------------------------------------------------

  @Test
  void aTasksMdThatCannotBeReadIsSourceUnreadable() {
    DetailFixture fixture = fixture(root -> write(root, "tasks.md", "## WP01\n"));
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.TASKS_MD && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));

    assertSourceUnreadable(fixture);
  }

  @Test
  void aLanesJsonThatCannotBeReadIsSourceUnreadable() {
    DetailFixture fixture = fixture(root -> write(root, "lanes.json", lanes("alpha", "lane-a:WP01")));
    fixture.recorder().failWhen(access -> access.pathClass() == PathClass.LANES_JSON && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));

    assertThatThrownBy(() -> detail(fixture, "WP01")).isInstanceOf(MissionStatusUnavailable.class);
  }
}
