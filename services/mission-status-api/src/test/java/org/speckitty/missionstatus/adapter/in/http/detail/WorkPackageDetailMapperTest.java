package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.cycleFile;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.lanes;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.secret;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.model.WorkPackageDetail;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.ProjectionRow;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The nine {@code (row, route)} pairs of the projection table that {@code getWorkPackageDetail} carries (D-102, AC-8.4): T1, T5, T7, T8, T9, T15,
 * T16, T17 and T18. Each case plants the value that cannot be shown and drives the real projection (the application layer) and the mapper
 * together, then asserts the row's outcome: an M7 row is a refusal with one diagnostic (500 {@code source_unreadable} on this route), an M14 row
 * is the member {@code null} with a 200 and no diagnostic, and T18 is the 200 with the member withheld or replaced and one
 * {@code projection_refused}. A nullable member never refuses and a non-nullable one is never nulled. The discovered count of this class is nine.
 */
class WorkPackageDetailMapperTest {

  private static final String LEAK = "/home/someone/private";

  private static WorkPackageDetail served(DetailFixture fixture) {
    return WorkPackageDetailMapper.detail(DetailRoute.detail(fixture, "WP01"));
  }

  /** The Work Package is refused with {@code projection_refused} and exactly one diagnostic. */
  private static void assertRefused(DetailFixture fixture) {
    assertThatThrownBy(() -> served(fixture)).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
  }

  private static DetailFixture withFile(String... lines) {
    return fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", lines)));
  }

  @Test
  @ProjectionRow(row = "T1", route = "getWorkPackageDetail")
  void t1TheMissionIdIsATypedUlidAndNothingElseCanBeServed() {
    assertThatThrownBy(() -> new MissionId(LEAK)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionId("01j01000000000000000000001")).isInstanceOf(IllegalArgumentException.class);
    DetailFixture fixture = fixture(root -> {});

    assertThat(served(fixture).getMissionId()).isEqualTo(Rows.ALPHA_ID);
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  @ProjectionRow(row = "T5", route = "getWorkPackageDetail")
  void t5ADependencyIdThatIsNotAWorkPackageIdRefusesTheWorkPackageAndTheWorkPackageIdIsTyped() {
    assertRefused(withFile("dependencies: [\"" + LEAK + "\"]"));
    assertRefused(withFile("dependencies: [WP02x]"));
    assertThatThrownBy(() -> new WpId(LEAK)).isInstanceOf(IllegalArgumentException.class);
    // and a clean value is served as it is: a non-nullable member is never nulled
    DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02]")));
    WorkPackageDetail clean = served(fixture);
    assertThat(clean.getWpId()).isEqualTo("WP01");
    assertThat(clean.getDependencies()).extracting(dependency -> dependency.getWpId()).containsExactly("WP02");
  }

  @Test
  @ProjectionRow(row = "T7", route = "getWorkPackageDetail")
  void t7ASubtaskReferenceOrAnOwnedFilePatternThatCannotBeShownRefusesTheWorkPackage() {
    assertRefused(withFile("subtasks:", "  - " + LEAK));
    assertRefused(withFile("subtasks:", "  - \"~x\""));
    assertRefused(withFile("owned_files:", "  - " + LEAK + "/file.py"));
    assertRefused(withFile("owned_files:", "  - \"C:\\\\x\""));
    // a clean value is served as it is
    WorkPackageDetail clean = served(withFile("subtasks: [T001]", "owned_files: [src/**]"));
    assertThat(clean.getSubtasks()).extracting(subtask -> subtask.getId()).containsExactly("T001");
    assertThat(clean.getOwnedFiles()).extracting(owned -> owned.getPattern()).containsExactly("src/**");
  }

  @Test
  @ProjectionRow(row = "T8", route = "getWorkPackageDetail")
  void t8APlanningBranchThatCannotBeShownIsNullWithA200AndNoDiagnostic() {
    for (String bad : new String[] {LEAK, "b".repeat(256), secret()}) {
      DetailFixture fixture = withFile("planning_base_branch: " + bad);

      assertThat(served(fixture).getWorkspace().getPlanningBranch()).as(bad).isNull();
      assertThat(fixture.diagnostics()).isEmpty();
    }
    assertThat(served(withFile("planning_base_branch: release/3.x")).getWorkspace().getPlanningBranch()).isEqualTo("release/3.x");
  }

  @Test
  @ProjectionRow(row = "T9", route = "getWorkPackageDetail")
  void t9ALaneIdOrABranchThatFailsTheContractIsNullWithA200AndNoDiagnostic() {
    DetailFixture badLane = fixture(root -> write(root, "lanes.json", lanes("alpha", "lane a:WP01")));
    DetailFixture longLane = fixture(root -> write(root, "lanes.json", lanes("alpha", "a".repeat(65) + ":WP01")));

    for (DetailFixture fixture : new DetailFixture[] {badLane, longLane}) {
      WorkPackageDetail served = served(fixture);
      assertThat(served.getWorkspace().getLaneId()).isNull();
      assertThat(served.getWorkspace().getLaneBranch()).isNull();
      assertThat(served.getWorkspace().getWorktreePresent()).isFalse();
      assertThat(fixture.diagnostics()).isEmpty();
    }
    WorkPackageDetail clean = served(fixture(root -> write(root, "lanes.json", lanes("alpha", "lane-a:WP01"))));
    assertThat(clean.getWorkspace().getLaneId()).isEqualTo("lane-a");
    assertThat(clean.getWorkspace().getLaneBranch()).isEqualTo("kitty/mission-alpha-lane-a");
  }

  @Test
  @ProjectionRow(row = "T15", route = "getWorkPackageDetail")
  void t15AReviewTimeThatIsNoDateTimeIsNullWithA200AndNoDiagnostic() {
    for (String bad : new String[] {"2026-09-21", "yesterday", "2026-13-45T25:61:61Z", "2026-09-21T09:15:00"}) {
      DetailFixture fixture = fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "reviewer-renata", bad)));

      assertThat(served(fixture).getReviewCycles()).singleElement().satisfies(cycle -> assertThat(cycle.getReviewedAt()).as(bad).isNull());
      assertThat(fixture.diagnostics()).isEmpty();
    }
    DetailFixture clean = fixture(root -> write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00")));
    assertThat(served(clean).getReviewCycles().get(0).getReviewedAt()).isEqualTo("2026-09-21T09:15:00+00:00");
  }

  @Test
  @ProjectionRow(row = "T16", route = "getWorkPackageDetail")
  void t16APointerOrAPathThePolicyRefusesIsNullWithA200AndNoDiagnostic() {
    // a work package directory with a space in its name: the product refuses the pointer segment, the artifact path is valid
    DetailFixture spaced =
        fixture(
            root -> {
              DetailRoute.delete(root, "tasks/WP01-one.md");
              write(root, "tasks/WP01-a b.md", wpFile("WP01", "One"));
              write(root, "tasks/WP01-a b/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
            });
    // a cycle file that is a link: no path, while the pointer is fine
    DetailFixture linked =
        fixture(
            root -> {
              write(root, "elsewhere.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
              DetailRoute.symlink(root.resolve("kitty-specs/alpha/tasks/WP01-one/review-cycle-1.md"), root.resolve("kitty-specs/alpha/elsewhere.md"));
            });

    assertThat(served(spaced).getReviewCycles()).singleElement().satisfies(cycle -> {
      assertThat(cycle.getFeedbackReference()).isNull();
      assertThat(cycle.getArtifactPath()).isEqualTo("tasks/WP01-a b/review-cycle-1.md");
    });
    assertThat(served(linked).getReviewCycles()).singleElement().satisfies(cycle -> {
      assertThat(cycle.getFeedbackReference()).isEqualTo("review-cycle://alpha/WP01-one/review-cycle-1.md");
      assertThat(cycle.getArtifactPath()).isNull();
    });
    assertThat(spaced.diagnostics()).isEmpty();
    assertThat(linked.diagnostics()).isEmpty();
  }

  @Test
  @ProjectionRow(row = "T17", route = "getWorkPackageDetail")
  void t17AReviewerThatIsNoHandleIsNullAndNeverAnError() {
    DetailFixture fixture =
        fixture(
            root -> {
              write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "\"Reviewer Renata\"", "2026-09-21T09:15:00+00:00"));
              write(root, "tasks/WP01-one/review-cycle-2.md", cycleFile(2, "\"" + LEAK + "\"", "2026-09-21T09:15:00+00:00"));
              write(root, "tasks/WP01-one/review-cycle-3.md", cycleFile(3, secret(), "2026-09-21T09:15:00+00:00"));
              write(root, "tasks/WP01-one/review-cycle-4.md", cycleFile(4, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
            });

    assertThat(served(fixture).getReviewCycles()).extracting(cycle -> cycle.getReviewer()).containsExactly(null, null, null, "reviewer-renata");
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  @ProjectionRow(row = "T18", route = "getWorkPackageDetail")
  void t18ASubtaskTitleIsWithheldADependencyTitleIsTheIdAndEachWritesOneDiagnostic() {
    DetailFixture subtask =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
              write(root, "tasks.md", "## WP01\n- [ ] T001 Rotate " + secret() + "\n");
            });
    DetailFixture dependency =
        fixture(
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "Rotate " + secret()));
            });

    assertThat(served(subtask).getSubtasks()).singleElement().satisfies(entry -> {
      assertThat(entry.getId()).isEqualTo("T001");
      assertThat(entry.getTitle()).isNull();
    });
    assertThat(served(dependency).getDependencies()).singleElement().satisfies(entry -> {
      assertThat(entry.getWpId()).isEqualTo("WP02");
      assertThat(entry.getTitle()).isEqualTo("WP02");
    });
    assertThat(subtask.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
    assertThat(dependency.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- the shape of the body ----------------------------------------------------------------------------------------------------------

  @Test
  void everyArrayIsPresentAndTheMembersAreTheRecordsMembers() {
    DetailFixture fixture =
        fixture(
            DetailRoute.ledger() + DetailRoute.subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"done\"}"),
            root -> {
              write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]", "dependencies: [WP02]", "owned_files: [src/**]"));
              write(root, "tasks/WP02-two.md", wpFile("WP02", "Two"));
              write(root, "spec.md", "# Spec\n");
              write(root, "lanes.json", lanes("alpha", "lane-a:WP01"));
              write(root, "tasks/WP01-one/review-cycle-1.md", cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
            });

    WorkPackageDetail model = served(fixture);

    assertThat(model.getSubtasks()).hasSize(1);
    assertThat(model.getSubtasks().get(0).getStatusLane().getValue()).isEqualTo(Lane.DONE.wire());
    assertThat(model.getDependencies()).hasSize(1);
    assertThat(model.getReviewCycles()).hasSize(1);
    assertThat(model.getOwnedFiles().get(0).getIsGlob()).isTrue();
    assertThat(model.getOwnedFiles().get(0).getChangeState().getValue()).isEqualTo("unknown");
    assertThat(model.getArtifactReferences().getPrompt().getKind().getValue()).isEqualTo("work_package_prompt");
    assertThat(model.getArtifactReferences().getSpec().getKind().getValue()).isEqualTo("spec");
    assertThat(model.getWorkspace().getLaneId()).isEqualTo("lane-a");
    WorkPackageDetail empty = served(fixture(root -> {}));
    assertThat(empty.getSubtasks()).isEmpty();
    assertThat(empty.getDependencies()).isEmpty();
    assertThat(empty.getReviewCycles()).isEmpty();
    assertThat(empty.getOwnedFiles()).isEmpty();
    assertThat(empty.getArtifactReferences().getSpec()).isNull();
  }
}
