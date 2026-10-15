package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageDetailServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * The four {@code knownDivergence} fixtures of the detail golden. {@code WorkPackageDetailServedRoute#served} leaves them out of the golden
 * comparison (their golden is the oracle's outcome), and each is asserted here against the Java outcome, with the proof that the two outcomes
 * differ where the manifest says they do (D-P9-3): V7 for the two symbolic-link worktrees, V20 for the subtasks written as mappings, and
 * V19 (retired) for the head dates, which both the oracle and {@code getMission} null and this route never serves.
 */
class WorkPackageDetailDivergenceTest {

  private static TreeFixture fixture(String key) {
    return WorkPackageDetailServedRoute.fixture(key);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> golden(TreeFixture fixture, String wp) {
    Map<String, Object> goldens = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, WorkPackageDetailServedRoute.GOLDEN));
    return (Map<String, Object>) goldens.get(wp);
  }

  @SuppressWarnings("unchecked")
  private static Object workspaceOf(Map<String, Object> envelope, String member) {
    return ((Map<String, Object>) ((Map<String, Object>) envelope.get("body")).get("workspace")).get(member);
  }

  /** V7: the oracle follows a symbolic link ({@code Path.exists}) and answers true; Java does not follow it and answers false. */
  @ParameterizedTest
  @ValueSource(strings = {"worktree-states/directory-symlink", "worktree-states/git-entry-symlink"})
  void aSymbolicLinkOnTheWorktreeOrItsGitEntryIsAbsentWhereTheOracleSaysPresent(String key) {
    TreeFixture tree = fixture(key);
    DetailFixture fixture = DetailFixture.of(tree.dir());

    WorkPackageDetail served = DetailRoute.detail(fixture, "00000000000000000000000001", "WP01");

    assertThat(workspaceOf(golden(tree, "WP01"), "worktreePresent")).as("the oracle's outcome").isEqualTo(true);
    assertThat(served.workspace().worktreePresent()).as("Java's outcome: the link is not followed").isFalse();
    assertThat(served.workspace().laneId()).isEqualTo(workspaceOf(golden(tree, "WP01"), "laneId"));
    assertThat(served.workspace().laneBranch()).isEqualTo(workspaceOf(golden(tree, "WP01"), "laneBranch"));
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void theTargetOfALinkedWorktreeIsNeverTouched() {
    DetailFixture fixture = DetailFixture.of(fixture("worktree-states/directory-symlink").dir());
    fixture.recorder().clear();

    DetailRoute.detail(fixture, "00000000000000000000000001", "WP01");

    assertThat(fixture.recorder().accesses()).noneMatch(access -> access.path().contains("real-worktree"));
  }

  /** V20: the oracle serves the Python {@code str()} of each mapping as a subtask id; Java refuses the Work Package (SK-353, D-97). */
  @Test
  void subtasksWrittenAsMappingsAreRefusedWhereTheOracleServesTheirPythonText() {
    TreeFixture tree = fixture("wp-malformed-frontmatter/wpm-28");
    DetailFixture fixture = DetailFixture.of(tree.dir());

    assertThat(((CanonicalJson.Num) golden(tree, "WP01").get("status")).text()).isEqualTo("200");
    assertThatThrownBy(() -> DetailRoute.detail(fixture, "00000000000000000000000001", "WP01")).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
  }

  /** V19 is retired: the oracle nulls the head dates too, and the detail serves no head, so the fixture is an ordinary case whose golden holds byte for byte. */
  @Test
  void theHeadDatesFixtureIsAnOrdinaryCaseHereAndItsGoldenHoldsByteForByte() {
    TreeFixture tree = fixture("projection-nulls/head-dates-nulled");
    Entry entry = new Entry(tree.key(), WorkPackageDetailServedRoute.GOLDEN);
    WorkPackageDetailServedRoute route = new WorkPackageDetailServedRoute();

    for (String wp : WorkPackageDetailServedRoute.requestKeys(tree)) {
      CanonicalJson.assertBodyEqualsGolden(route.body(entry, wp), CanonicalJson.toBytes(golden(tree, wp)));
    }
    assertThat(route.served()).contains(entry);
    assertThat(WorkPackageDetailServedRoute.divergentEntries()).doesNotContain(entry);
  }

  @Test
  void theSameRouteServesTheMissionWhoseHeadDatesAreNotInstants() {
    DetailFixture fixture = DetailFixture.of(fixture("projection-nulls/head-dates-nulled").dir());

    WorkPackageDetail served = DetailRoute.detail(fixture, "00000000000000000000000001", "WP01");

    assertThat(served.wpId().value()).isEqualTo("WP01");
    assertThat(served.missionId()).isEqualTo(new MissionId("00000000000000000000000001"));
  }
}
