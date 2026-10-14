package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Arrays;
import java.util.List;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.model.MissionDetail;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.ProjectionRow;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The seven {@code (row, route)} pairs of the projection table that {@code getMission} carries (D-102, AC-8.4): T1, T2, T3, T4 for the head
 * and T5, T6, T10 for the Work Package summary the route lists. Each case plants the value that cannot be shown and drives the real
 * projection (the application layer) and the mapper together, then asserts the row's outcome: an M7 row is 500 {@code projection_refused}
 * with one diagnostic, an M14 row is the member {@code null} with a 200, and T10 is the whole-head M3 {@code ledger_unparseable}. A nullable
 * member never refuses and a non-nullable one is never nulled. {@code ProjectionRowCoverageTest} closes the 26 pairs.
 */
class MissionDetailMapperTest {

  private static final String ID = Rows.ALPHA_ID;
  private static final String CREATED = "2026-09-01T10:00:00+00:00";
  private static final String LEAK = "/home/someone/private";

  private static String ledger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");
  }

  private static String meta(String extraReplacement, String from) {
    return Rows.meta(ID, "alpha", CREATED).replace(from, extraReplacement);
  }

  private static DetailFixture fixture(String metaText, String ledger, String wpFile) {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(FixtureSpec.Mission.of("alpha", metaText, ledger)),
        root -> {
          if (wpFile != null) {
            MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", wpFile);
          }
        });
  }

  private static DetailFixture fixture(String metaText) {
    return fixture(metaText, ledger(), MissionDetailServedRoute.workPackageFile("WP01", "One"));
  }

  private static MissionDetail served(DetailFixture fixture) {
    return MissionDetailMapper.detail(MissionDetailRowsTest.serviceOver(fixture).mission(new MissionId(ID)));
  }

  /** 500 {@code projection_refused} and exactly one diagnostic. */
  private static void assertRefused(DetailFixture fixture, DiagnosticCode code) {
    assertThatThrownBy(() -> served(fixture)).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(code);
  }

  private static String secret() {
    return "gh" + "p_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3";
  }

  // ---- head rows ---------------------------------------------------------------------------------------------------------------

  @Test
  @ProjectionRow(row = "T1", route = "getMission")
  void t1AStrictNonNullableHeadMemberThatCannotBeShownRefusesTheMission() {
    assertRefused(fixture(meta("\"target_branch\":\"" + LEAK + "\"", "\"target_branch\":\"main\"")), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(meta("\"mission_slug\":\"" + secret() + "\"", "\"mission_slug\":\"alpha\"")), DiagnosticCode.PROJECTION_REFUSED);
    // and a clean value is served as it is stored: a non-nullable member is never nulled
    MissionDetail served = served(fixture(Rows.meta(ID, "alpha", CREATED)));
    assertThat(served.getMissionId()).isEqualTo(ID);
    assertThat(served.getSlug()).isEqualTo("alpha");
    assertThat(served.getTargetBranch()).isEqualTo("main");
  }

  @Test
  @ProjectionRow(row = "T2", route = "getMission")
  void t2ANullableStrictHeadMemberThatCannotBeShownIsNullWith200AndNoDiagnostic() {
    DetailFixture fixture = fixture(meta("\"mission_type\":\"" + LEAK + "\"", "\"mission_type\":\"software-dev\""));

    MissionDetail served = served(fixture);

    assertThat(served.getMissionType()).isNull();
    assertThat(served.getMissionId()).isEqualTo(ID);
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  @ProjectionRow(row = "T3", route = "getMission")
  void t3AHumanHeadMemberWithAnUnremovableLeakRefusesAndAPathIsReplaced() {
    assertRefused(fixture(meta("\"friendly_name\":\"Rotate " + secret() + "\"", "\"friendly_name\":\"Fixture alpha\"")), DiagnosticCode.PROJECTION_REFUSED);

    MissionDetail replaced = served(fixture(meta("\"friendly_name\":\"See " + LEAK + " now\"", "\"friendly_name\":\"Fixture alpha\"")));
    assertThat(replaced.getFriendlyName()).isEqualTo("See [path] now");
  }

  @Test
  @ProjectionRow(row = "T4", route = "getMission")
  void t4ANullableHeadDateThatIsNotAnInstantIsNullWith200() {
    DetailFixture fixture =
        fixture(Rows.metaWith(ID, "alpha", CREATED, "\"accepted_at\":\"not-an-instant\",\"merged_at\":\"" + LEAK + "\",\"discarded_at\":\"2026-09-01T10:05:00\""));

    MissionDetail served = served(fixture);

    assertThat(served.getAcceptedAt()).isNull();
    assertThat(served.getMergedAt()).isNull();
    assertThat(served.getDiscardedAt()).as("no offset: not a date-time of the contract").isNull();
    assertThat(served.getLifecycleStatus()).as("derived without the dropped dates").isNotEqualTo(MissionDetail.LifecycleStatusEnum.DISCARDED);
    // the shared head writes one projection_refused for each value it dropped, and nothing else (#5529, landing fold R-7)
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- Work Package summary rows -------------------------------------------------------------------------------------------------

  @Test
  @ProjectionRow(row = "T5", route = "getMission")
  void t5ADependencyIdThatCannotBeShownRefusesTheMission() {
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "One", "dependencies:", "- '" + LEAK + "'")), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "One", "dependencies:", "- wp02")), DiagnosticCode.PROJECTION_REFUSED);

    MissionDetail served = served(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "One", "dependencies:", "- WP07")));
    assertThat(served.getWorkPackages().get(0).getDependencies()).containsExactly("WP07");
    assertThat(served.getWorkPackages().get(0).getReadiness().getUnsatisfied()).containsExactly("WP07");
    assertThat(served.getWorkPackages().get(0).getReadiness().getSatisfied()).isFalse();
  }

  @Test
  @ProjectionRow(row = "T6", route = "getMission")
  void t6AHumanSummaryMemberWithAnUnremovableLeakRefusesAndAPathIsReplaced() {
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "Rotate " + secret())), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "One", "phase: \"" + secret() + "\"")), DiagnosticCode.PROJECTION_REFUSED);

    MissionDetail replaced =
        served(fixture(Rows.meta(ID, "alpha", CREATED), ledger(), MissionDetailServedRoute.workPackageFile("WP01", "Fix " + LEAK, "phase: \"Phase in " + LEAK + "\"")));
    assertThat(replaced.getWorkPackages().get(0).getTitle()).isEqualTo("Fix [path]");
    assertThat(replaced.getWorkPackages().get(0).getPhaseLabel()).isEqualTo("Phase in [path]");
  }

  @Test
  @ProjectionRow(row = "T10", route = "getMission")
  void t10ALastTransitionThatIsNotAnInstantIsTheWholeHeadLedgerUnparseable() {
    DetailFixture fixture = fixture(Rows.meta(ID, "alpha", CREATED), Rows.status(Rows.id(1), "not-an-instant", "WP01", "planned", "claimed"), MissionDetailServedRoute.workPackageFile("WP01", "One"));

    assertRefused(fixture, DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  @Test
  void theClassDiscoversExactlyTheSevenPairsOfGetMission() {
    List<String> pairs =
        Arrays.stream(MissionDetailMapperTest.class.getDeclaredMethods())
            .map(method -> method.getAnnotation(ProjectionRow.class))
            .filter(java.util.Objects::nonNull)
            .map(row -> row.row() + "/" + row.route())
            .sorted()
            .toList();

    assertThat(pairs).containsExactly("T1/getMission", "T10/getMission", "T2/getMission", "T3/getMission", "T4/getMission", "T5/getMission", "T6/getMission");
  }

  // ---- the route mapper's refusal of a non-display lane (WP05 review N3, D-159 d) -------------------------------------------------

  private static String subtaskLedger(String first, String second) {
    return ledger()
        + "{\"actor\": \"claude\", \"at\": \"2026-09-01T10:02:00+00:00\", \"delta\": {\"subtasks\": {\"T001\": \"" + first + "\", \"T002\": \"" + second
        + "\", \"T003\": \"done\"}}, \"event_id\": \"0000000000000000000000R147\", \"kind\": \"annotation\", \"wp_id\": \"WP01\"}\n";
  }

  @Test
  void aSubtaskStatusOfGenesisIsAProjectionRefusalNeverNull() {
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), subtaskLedger("genesis", "done"), MissionDetailServedRoute.workPackageFile("WP01", "One")), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aSubtaskStatusOfUninitializedIsAProjectionRefusalNeverNull() {
    assertRefused(fixture(Rows.meta(ID, "alpha", CREATED), subtaskLedger("planned", "uninitialized"), MissionDetailServedRoute.workPackageFile("WP01", "One")), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void subtaskStatusesThatAreDisplayLanesAreCountedAndTheProgressIsDoneOverTotal() {
    MissionDetail served = served(fixture(Rows.meta(ID, "alpha", CREATED), subtaskLedger("planned", "done"), MissionDetailServedRoute.workPackageFile("WP01", "One")));

    assertThat(served.getWorkPackages().get(0).getSubtaskProgress().getDone()).isEqualTo(2);
    assertThat(served.getWorkPackages().get(0).getSubtaskProgress().getTotal()).isEqualTo(3);
  }

  @Test
  void aWorkPackageWithAFileAndNoEventsIsListedWithANullLaneAndNeverReady() {
    DetailFixture fixture = MissionDetailServedRoute.fixtureOf(FixtureSpec.of(PortFixtures.mission("alpha", ID, CREATED, "")), (Path root) -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One")));

    MissionDetail served = served(fixture);

    assertThat(served.getWpTotal()).isZero();
    assertThat(served.getWorkPackages()).hasSize(1);
    assertThat(served.getWorkPackages().get(0).getStatusLane()).isNull();
    assertThat(served.getWorkPackages().get(0).getLastTransitionAt()).isNull();
    assertThat(served.getWorkPackages().get(0).getReadyToStart()).isFalse();
  }
}
