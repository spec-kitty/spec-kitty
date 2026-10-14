package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.detail.MissionDetailRowsTest;
import org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The semantics of {@code getWorkPackage} at the application layer (T099): which source each member comes from, the code-point order of
 * {@code subtasks} (this service is its ordering owner, TASKS-FRESH3-001), the order of {@code history} by instant, the N3 history half
 * (WP05 review: {@code genesis} and {@code uninitialized} become null, any other non-display lane is a refusal), the V25 pin, the review
 * partial-record rule, the cancellation rule and the one-read prompt capture. The route rows of the failure table are
 * {@code WorkPackageControllerRowsTest}.
 */
class WorkPackageQueryServiceTest {

  private static final String ID = Rows.ALPHA_ID;
  private static final String CREATED = "2026-09-01T10:00:00+00:00";

  // ---- ledger rows ---------------------------------------------------------------------------------------------------------------

  private static String transition(int n, String at, String wp, String from, String to, String extraMembers) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"event_id\":\"" + Rows.id(n) + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,"
        + "\"from_lane\":\"" + from + "\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"" + to + "\",\"wp_id\":\"" + wp + "\""
        + (extraMembers.isEmpty() ? "" : "," + extraMembers) + "}\n";
  }

  private static String annotation(int n, String at, String wp, String delta) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"delta\":" + delta + ",\"event_id\":\"" + Rows.id(n) + "\",\"kind\":\"annotation\",\"wp_id\":\"" + wp + "\"}\n";
  }

  private static DetailFixture fixture(String ledger, String wpFile) {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(PortFixtures.mission("alpha", ID, CREATED, ledger)), root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", wpFile));
  }

  private static DetailFixture fixture(String ledger) {
    return fixture(ledger, MissionDetailServedRoute.workPackageFile("WP01", "One"));
  }

  private static WorkPackageView view(DetailFixture fixture, boolean includePrompt) {
    return WorkPackageControllerRowsTest.view(fixture, ID, "WP01", includePrompt);
  }

  private static void assertRefused(DetailFixture fixture, DiagnosticCode code) {
    assertThatThrownBy(() -> view(fixture, false)).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(code);
  }

  private static String secret() {
    return "gh" + "p_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3";
  }

  // ---- sources of the members -------------------------------------------------------------------------------------------------------

  @Test
  void resolvedStateIsNeverReadFromTheKeysAnOldPlanningFileStillCarries() {
    DetailFixture fixture =
        fixture(
            transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", ""),
            MissionDetailServedRoute.workPackageFile("WP01", "One", "agent: file-agent", "assignee: file-assignee", "shell_pid: 42", "lane: done", "review_status: approved", "role: authored-role"));

    WorkPackageView served = view(fixture, false);

    assertThat(served.assignment().agent()).isNull();
    assertThat(served.assignment().assignee()).isNull();
    assertThat(served.statusLane()).as("the lane is the ledger's, not the file's").isEqualTo(Lane.CLAIMED);
    assertThat(served.review().latestResult()).isNull();
    assertThat(served.authored().role()).as("the authored role is the file's").isEqualTo("authored-role");
  }

  @Test
  void executionModeHasOnePairOfLiteralQuotesStripped() {
    DetailFixture quoted = fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", ""), MissionDetailServedRoute.workPackageFile("WP01", "One", "execution_mode: \"'code_change'\""));
    DetailFixture twice = fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", ""), MissionDetailServedRoute.workPackageFile("WP01", "One", "execution_mode: \"''code_change''\""));

    assertThat(view(quoted, false).executionMode()).isEqualTo("code_change");
    assertThat(view(twice, false).executionMode()).as("one pair only").isEqualTo("'code_change'");
  }

  @Test
  void aWorkPackageWithAFileAndNoEventsHasANullLaneAndIsNeverReady() {
    DetailFixture fixture = fixture("");

    WorkPackageView served = view(fixture, false);

    assertThat(served.statusLane()).isNull();
    assertThat(served.readyToStart()).isFalse();
    assertThat(served.lastTransitionAt()).isNull();
    assertThat(served.lastEventId()).isNull();
    assertThat(served.forceCount()).isZero();
    assertThat(served.history()).isEmpty();
    assertThat(served.staleness()).as("always null").isNull();
  }

  @Test
  void aDependencyThatIsNotDoneKeepsTheWorkPackageNotReady() {
    DetailFixture fixture = fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "genesis", "planned", ""), MissionDetailServedRoute.workPackageFile("WP01", "One", "dependencies:", "- WP07"));

    WorkPackageView served = view(fixture, false);

    assertThat(served.dependencies()).extracting(id -> id.value()).containsExactly("WP07");
    assertThat(served.readiness().satisfied()).isFalse();
    assertThat(served.readiness().unsatisfied()).extracting(id -> id.value()).containsExactly("WP07");
    assertThat(served.readyToStart()).isFalse();
  }

  // ---- subtasks ----------------------------------------------------------------------------------------------------------------------

  private static String subtaskLedger(String subtasks) {
    return transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", "") + annotation(2, "2026-09-01T10:02:00Z", "WP01", "{\"subtasks\":" + subtasks + "}");
  }

  @Test
  void subtasksAreInCodePointOrderNotUtf16OrderAndTheProgressIsDoneOverTotal() {
    // U+FF5E sorts before U+1F600 by code point; by UTF-16 unit the surrogate pair (D83D) sorts before U+FF5E
    String early = "～a";
    String late = "😀b";
    DetailFixture fixture = fixture(subtaskLedger("{\"" + late + "\":\"planned\",\"" + early + "\":\"done\",\"T005\":\"done\"}"));

    WorkPackageView served = view(fixture, false);

    assertThat(served.subtasks()).extracting(Map.Entry::getKey).containsExactly("T005", early, late);
    assertThat(late.compareTo(early)).as("the UTF-16 order is the other one").isNegative();
    assertThat(served.subtaskProgress().done()).isEqualTo(2);
    assertThat(served.subtaskProgress().total()).isEqualTo(3);
  }

  @Test
  void aSubtaskIdThatCannotBeShownRefusesTheWorkPackage() {
    assertRefused(fixture(subtaskLedger("{\"/home/someone/private\":\"done\"}")), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aSubtaskStatusOfGenesisOrUninitializedIsAProjectionRefusalNeverNull() {
    assertRefused(fixture(subtaskLedger("{\"T001\":\"genesis\"}")), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(subtaskLedger("{\"T001\":\"uninitialized\"}")), DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- history -----------------------------------------------------------------------------------------------------------------------

  @Test
  void historyIsOrderedByTheParsedInstantNotByTheText() {
    // by text: 10:30:00Z < 12:00:00+02:00; by instant: 12:00:00+02:00 (= 10:00Z) comes first
    String ledger =
        transition(1, "2026-09-01T10:30:00Z", "WP01", "claimed", "in_progress", "")
            + transition(2, "2026-09-01T12:00:00+02:00", "WP01", "planned", "claimed", "")
            + transition(3, "2026-09-01T10:45:00.5Z", "WP01", "in_progress", "for_review", "");
    DetailFixture fixture = fixture(ledger);

    WorkPackageView served = view(fixture, false);

    assertThat(served.history()).extracting(HistoryRow::eventId).containsExactly(Rows.id(2), Rows.id(1), Rows.id(3));
  }

  @Test
  void aHistoryStampThatIsNotAnInstantIsAProjectionRefusal() {
    // the stamp sorts before every real one, so the head (which follows the last row) is intact and the refusal is the route's (T13, M7)
    String ledger = transition(1, "0-not-an-instant", "WP01", "planned", "claimed", "") + transition(2, "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress", "");

    assertRefused(fixture(ledger), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aHistoryStampWithoutAnOffsetIsAProjectionRefusalBecauseTheContractNeedsOne() {
    String ledger = transition(1, "0000-01-01T00:00:00", "WP01", "planned", "claimed", "") + transition(2, "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress", "");

    assertRefused(fixture(ledger), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aHistoryLaneOfGenesisIsNullNeverARefusal() {
    WorkPackageView served = view(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "genesis", "planned", "")), false);

    assertThat(served.history()).hasSize(1);
    assertThat(served.history().get(0).fromLane()).isNull();
    assertThat(served.history().get(0).toLane()).isEqualTo("planned");
  }

  @Test
  void aHistoryLaneOfUninitializedIsNullNeverARefusal() {
    WorkPackageView served = view(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "uninitialized", "planned", "")), false);

    assertThat(served.history().get(0).fromLane()).isNull();
    assertThat(served.history().get(0).toLane()).isEqualTo("planned");
  }

  @Test
  void anyOtherNonDisplayHistoryLaneIsAProjectionRefusal() {
    assertThatThrownBy(() -> WorkPackageQueryService.displayLane("banana")).isInstanceOf(ProjectionError.class);
    assertThatThrownBy(() -> WorkPackageQueryService.displayLane("Planned")).as("the case matters").isInstanceOf(ProjectionError.class);
    assertThatThrownBy(() -> WorkPackageQueryService.displayLane("")).isInstanceOf(ProjectionError.class);
    assertThat(WorkPackageQueryService.displayLane(null)).isNull();
    assertThat(WorkPackageQueryService.displayLane("genesis")).isNull();
    assertThat(WorkPackageQueryService.displayLane("uninitialized")).isNull();
    for (Lane lane : Lane.displayLanes()) {
      assertThat(WorkPackageQueryService.displayLane(lane.wire())).isEqualTo(lane.wire());
    }
  }

  @Test
  void aCarriedHistoryRowWithAnUnknownLaneRefusesTheWholeHistory() {
    HistoryRow row = new HistoryRow("WP01", "E1", "2026-09-01T10:01:00Z", "banana", "planned", Actor.NONE, false, null, null);

    assertThatThrownBy(() -> WorkPackageQueryService.history(List.of(row), new Projector(LeakPatternsFile.load()))).isInstanceOf(ProjectionError.class);
  }

  @Test
  void aHistoryEventIdThatIsAPathIsAProjectionRefusal() {
    HistoryRow row = new HistoryRow("WP01", "/home/someone/private", "2026-09-01T10:01:00Z", "planned", "claimed", Actor.NONE, false, null, null);

    assertThatThrownBy(() -> WorkPackageQueryService.history(List.of(row), new Projector(LeakPatternsFile.load()))).isInstanceOf(ProjectionError.class);
  }

  @Test
  void aHistoryReasonIsRedactedAndAHistoryVerdictOutsideTheContractIsRefused() {
    HistoryRow reason = new HistoryRow("WP01", "E1", "2026-09-01T10:01:00Z", "planned", "claimed", Actor.NONE, true, "see /home/someone/private now", "approved");
    HistoryRow verdict = new HistoryRow("WP01", "E2", "2026-09-01T10:02:00Z", "planned", "claimed", Actor.NONE, false, null, "shrug");

    List<HistoryRow> shown = WorkPackageQueryService.history(List.of(reason), new Projector(LeakPatternsFile.load()));

    assertThat(shown.get(0).reason()).isEqualTo("see [path] now");
    assertThat(shown.get(0).force()).isTrue();
    assertThat(shown.get(0).reviewVerdict()).isEqualTo("approved");
    assertThatThrownBy(() -> WorkPackageQueryService.history(List.of(verdict), new Projector(LeakPatternsFile.load()))).isInstanceOf(ProjectionError.class);
  }

  // ---- V25: a history event id that is not text ---------------------------------------------------------------------------------------

  @Test
  void v25ANonTextEventIdMakesTheWholeLedgerUnreadableForTheRouteAsForTheMissionDetail() {
    TreeFixture tree = WorkPackageServedRoute.fixture("resolved-state/history-event-id-not-text");
    DetailFixture route = DetailFixture.of(tree.dir());
    DetailFixture mission = DetailFixture.of(tree.dir());
    String missionId = WorkPackageServedRoute.missionIdOf(tree);

    assertThatThrownBy(() -> WorkPackageControllerRowsTest.view(route, missionId, "WP01", false))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE));
    assertThatThrownBy(() -> MissionDetailRowsTest.serviceOver(mission).mission(new MissionId(missionId)))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).as("the Mission detail refuses the same ledger the same way").isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE));
    assertThat(route.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  // ---- review ------------------------------------------------------------------------------------------------------------------------

  private static String reviewedLedger(String resultMember) {
    return transition(1, "2026-09-01T10:01:00Z", "WP01", "for_review", "in_review", "") + transition(2, "2026-09-01T10:02:00Z", "WP01", "in_review", "approved", resultMember);
  }

  @Test
  void aReviewResultIsServedWithAnEmptyReferenceWhenTheRowHasNone() {
    WorkPackageView served = view(fixture(reviewedLedger("\"review_result\":{\"reference\":null,\"reviewer\":\"reviewer-ruben\",\"verdict\":\"approved\"}")), false);

    assertThat(served.review().latestResult().reviewer()).isEqualTo("reviewer-ruben");
    assertThat(served.review().latestResult().verdict().wire()).isEqualTo("approved");
    assertThat(served.review().latestResult().reference()).isEmpty();
    assertThat(served.history().get(1).reviewVerdict()).isEqualTo("approved");
  }

  @Test
  void aReviewReferenceIsHumanTextSoAPathInItIsReplaced() {
    WorkPackageView served = view(fixture(reviewedLedger("\"review_result\":{\"reference\":\"see /home/someone/private/notes\",\"reviewer\":\"r\",\"verdict\":\"changes_requested\"}")), false);

    assertThat(served.review().latestResult().reference()).isEqualTo("see [path]");
    assertThat(served.review().latestResult().verdict().wire()).isEqualTo("changes_requested");
  }

  @Test
  void aReviewVerdictOutsideTheContractIsAProjectionRefusal() {
    assertRefused(fixture(reviewedLedger("\"review_result\":{\"reference\":\"r\",\"reviewer\":\"r\",\"verdict\":\"shrug\"}")), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(reviewedLedger("\"review_result\":{\"reference\":\"r\",\"reviewer\":\"r\",\"verdict\":7}")), DiagnosticCode.PROJECTION_REFUSED);
  }

  private static String overrideLedger(String review) {
    return transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", "") + annotation(2, "2026-09-01T10:02:00Z", "WP01", "{\"review\":" + review + "}");
  }

  @Test
  void aCompleteOverrideIsServedWithItsTimeAndAPartialOneWithNullForTheBlankMembers() {
    WorkPackageView complete = view(fixture(overrideLedger("{\"actor\":\"operator-omar\",\"at\":\"2026-09-01T10:02:00+00:00\",\"reason\":\"ship it\",\"wp_id\":\"WP01\"}")), false);
    WorkPackageView partial = view(fixture(overrideLedger("{\"actor\":\"\",\"at\":\"\",\"reason\":\"needs rework\",\"wp_id\":\"\"}")), false);

    assertThat(complete.review().override().complete()).isTrue();
    assertThat(complete.review().override().at()).isEqualTo("2026-09-01T10:02:00+00:00");
    assertThat(complete.review().override().actor()).isEqualTo("operator-omar");
    assertThat(complete.review().override().reason()).isEqualTo("ship it");
    assertThat(partial.review().override().complete()).isFalse();
    assertThat(partial.review().override().at()).isNull();
    assertThat(partial.review().override().actor()).isNull();
    assertThat(partial.review().override().reason()).isEqualTo("needs rework");
  }

  @Test
  void aReleaseMarkerIsNoOverrideAndACompleteOverrideWithAJunkTimeIsAProjectionRefusal() {
    assertThat(view(fixture(overrideLedger("{\"actor\":\"\",\"at\":\"\",\"reason\":\"\",\"wp_id\":\"\"}")), false).review().override()).isNull();
    assertRefused(fixture(overrideLedger("{\"actor\":\"operator-omar\",\"at\":\"2026-09-01T10:02:00\",\"reason\":\"ship it\",\"wp_id\":\"WP01\"}")), DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- cancellation ------------------------------------------------------------------------------------------------------------------

  @Test
  void aCancellationIsServedOnlyWhileTheLaneIsCanceled() {
    WorkPackageView operator = view(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "canceled", "\"reason\":\"no longer needed\",\"reason_source\":\"operator\"")), false);
    WorkPackageView bogus = view(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "canceled", "\"reason\":\"dropped\",\"reason_source\":\"bogus\"")), false);
    WorkPackageView running = view(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", "")), false);

    assertThat(operator.cancellation().reasonSource().wire()).isEqualTo("operator");
    assertThat(operator.cancellation().reason()).isEqualTo("no longer needed");
    assertThat(bogus.cancellation().reasonSource().wire()).as("anything but operator is synthetic").isEqualTo("synthetic");
    assertThat(running.cancellation()).isNull();
  }

  @Test
  void aCancellationReasonWithAnUnremovableLeakIsAProjectionRefusal() {
    assertRefused(fixture(transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "canceled", "\"reason\":\"" + secret() + "\",\"reason_source\":\"operator\"")), DiagnosticCode.PROJECTION_REFUSED);
  }

  // ---- the prompt --------------------------------------------------------------------------------------------------------------------

  @Test
  void thePromptIsTheBodyOfTheWinningFileUnprojectedAndOnlyWhenAsked() {
    String hostPath = "/home/someone/private/notes";
    DetailFixture fixture =
        MissionDetailServedRoute.fixtureOf(
            FixtureSpec.of(PortFixtures.mission("alpha", ID, CREATED, transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", ""))),
            root -> {
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", "---\nwork_package_id: WP01\ntitle: See " + hostPath + "\n---\n\nFirst body " + hostPath + "\r\nline two\n");
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-two.md", MissionDetailServedRoute.workPackageFile("WP01", "Second"));
            });

    WorkPackageView without = view(fixture, false);
    WorkPackageView with = view(fixture, true);

    assertThat(without.promptMarkdown()).isNull();
    assertThat(with.title()).as("AC-9.2: the title shows [path]").isEqualTo("See [path]");
    assertThat(with.promptMarkdown()).as("the prompt keeps the path and reads CRLF as LF").contains(hostPath).contains("First body").doesNotContain("\r").doesNotContain("Body of WP01");
  }

  @Test
  void thePromptOfTheWinningFileIsServedWhenAnotherFileSortsFirstWithAnotherId() {
    DetailFixture fixture =
        MissionDetailServedRoute.fixtureOf(
            FixtureSpec.of(PortFixtures.mission("alpha", ID, CREATED, transition(1, "2026-09-01T10:01:00Z", "WP01", "planned", "claimed", ""))),
            root -> {
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP00-first.md", MissionDetailServedRoute.workPackageFile("WP00", "Zero"));
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One"));
            });

    assertThat(view(fixture, true).promptMarkdown()).isEqualTo("\nBody of WP01\n");
  }
}
