package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.AbstractMap.SimpleEntry;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.dto.WorkPackage;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Assignment;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.Readiness;
import org.speckitty.missionstatus.domain.readmodel.detail.ReviewView;
import org.speckitty.missionstatus.domain.readmodel.detail.SubtaskProgress;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.ProjectionRow;
import org.speckitty.missionstatus.testsupport.Rows;
import tools.jackson.databind.json.JsonMapper;

/**
 * The ten {@code (row, route)} pairs of the projection table that {@code getWorkPackage} carries (D-102, AC-8.4): T5, T6, T7, T8, T10, T11,
 * T12, T13, T14 and T17. Each case plants the value that cannot be shown and drives the real projection (the application layer) and the
 * mapper together, then asserts the row's outcome: an M7 row is 500 {@code projection_refused} with one diagnostic, an M14 row is the member
 * {@code null} with a 200, and T10 is the whole-head M3 {@code ledger_unparseable}. A nullable member never refuses and a non-nullable one is
 * never nulled. The class also pins the shape of the mapping (the order of {@code subtasks}, the absent prompt, the staleness).
 */
class WorkPackageMapperTest {

  private static final String ID = Rows.ALPHA_ID;
  private static final String CREATED = "2026-09-01T10:00:00+00:00";
  private static final String LEAK = "/home/someone/private";
  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static String transition(int n, String at, String from, String to, String extraMembers) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"event_id\":\"" + Rows.id(n) + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,"
        + "\"from_lane\":\"" + from + "\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"" + to + "\",\"wp_id\":\"WP01\"" + (extraMembers.isEmpty() ? "" : "," + extraMembers) + "}\n";
  }

  private static String annotation(int n, String delta) {
    return "{\"actor\":\"claude\",\"at\":\"2026-09-01T10:02:00Z\",\"delta\":" + delta + ",\"event_id\":\"" + Rows.id(n) + "\",\"kind\":\"annotation\",\"wp_id\":\"WP01\"}\n";
  }

  private static String ledger() {
    return transition(1, "2026-09-01T10:01:00Z", "planned", "claimed", "");
  }

  private static DetailFixture fixtureFile(String ledger, String wpFile) {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(PortFixtures.mission("alpha", ID, CREATED, ledger)), root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", wpFile));
  }

  private static DetailFixture fixture(String ledger, String... frontmatter) {
    return fixtureFile(ledger, MissionDetailServedRoute.workPackageFile("WP01", "One", frontmatter));
  }

  private static WorkPackage served(DetailFixture fixture) {
    return WorkPackageMapper.workPackage(WorkPackageControllerRowsTest.view(fixture, ID, "WP01", false));
  }

  /** 500 {@code projection_refused} and exactly one diagnostic. */
  private static void assertRefused(DetailFixture fixture, DiagnosticCode code) {
    assertThatThrownBy(() -> served(fixture)).isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(code);
  }

  private static String secret() {
    return "gh" + "p_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3";
  }

  // ---- the ten pairs -------------------------------------------------------------------------------------------------------------

  @Test
  @ProjectionRow(row = "T5", route = "getWorkPackage")
  void t5ADependencyIdThatCannotBeShownRefusesTheWorkPackage() {
    assertRefused(fixture(ledger(), "dependencies:", "- '" + LEAK + "'"), DiagnosticCode.PROJECTION_REFUSED);
    assertRefused(fixture(ledger(), "dependencies:", "- wp02"), DiagnosticCode.PROJECTION_REFUSED);

    WorkPackage shown = served(fixture(ledger(), "dependencies:", "- WP07"));
    assertThat(shown.wpId()).isEqualTo("WP01");
    assertThat(shown.dependencies()).containsExactly("WP07");
    assertThat(shown.readiness().getUnsatisfied()).containsExactly("WP07");
  }

  @Test
  @ProjectionRow(row = "T6", route = "getWorkPackage")
  void t6AHumanMemberWithAnUnremovableLeakRefusesAndAPathIsReplacedInEveryHumanMember() {
    for (String member : List.of("phase", "role", "agent_profile", "model", "task_type", "priority", "execution_mode")) {
      assertRefused(fixture(ledger(), member + ": \"" + secret() + "\""), DiagnosticCode.PROJECTION_REFUSED);
    }

    WorkPackage replaced =
        served(
            fixture(
                ledger() + annotation(2, "{\"review\":{\"actor\":\"operator-omar\",\"at\":\"2026-09-01T10:02:00+00:00\",\"reason\":\"see " + LEAK + "\",\"wp_id\":\"WP01\"}}"),
                "phase: \"Phase in " + LEAK + "\"",
                "role: \"Role " + LEAK + "\"",
                "agent_profile: \"Profile " + LEAK + "\"",
                "model: \"Model " + LEAK + "\"",
                "task_type: \"Task " + LEAK + "\"",
                "priority: \"Prio " + LEAK + "\"",
                "execution_mode: \"Mode " + LEAK + "\""));
    assertThat(replaced.phaseLabel()).isEqualTo("Phase in [path]");
    assertThat(replaced.authored().getRole()).isEqualTo("Role [path]");
    assertThat(replaced.authored().getAgentProfile()).isEqualTo("Profile [path]");
    assertThat(replaced.authored().getModel()).isEqualTo("Model [path]");
    assertThat(replaced.taskType()).isEqualTo("Task [path]");
    assertThat(replaced.priority()).isEqualTo("Prio [path]");
    assertThat(replaced.executionMode()).isEqualTo("Mode [path]");
    assertThat(replaced.review().getOverride().getReason()).isEqualTo("see [path]");
  }

  @Test
  @ProjectionRow(row = "T7", route = "getWorkPackage")
  void t7AStrictListMemberOrASubtaskKeyThatCannotBeShownRefusesTheWorkPackage() {
    for (String member : List.of("owned_files", "requirement_refs", "tracker_refs", "subtasks")) {
      assertRefused(fixture(ledger(), member + ":", "- '" + LEAK + "'"), DiagnosticCode.PROJECTION_REFUSED);
    }
    assertRefused(fixture(ledger() + annotation(2, "{\"subtasks\":{\"" + LEAK + "\":\"done\"}}")), DiagnosticCode.PROJECTION_REFUSED);

    WorkPackage shown = served(fixture(ledger(), "owned_files:", "- src/main/**", "requirement_refs:", "- FR-001", "tracker_refs:", "- GH-957", "subtasks:", "- T001"));
    assertThat(shown.ownedFiles()).containsExactly("src/main/**");
    assertThat(shown.requirementRefs()).containsExactly("FR-001");
    assertThat(shown.trackerRefs()).containsExactly("GH-957");
    assertThat(shown.authored().getSubtasks()).containsExactly("T001");
  }

  @Test
  @ProjectionRow(row = "T8", route = "getWorkPackage")
  void t8ANullableStrictMemberThatCannotBeShownIsNullWith200AndNoDiagnostic() {
    DetailFixture path = fixture(ledger(), "merge_target_branch: '" + LEAK + "'");
    DetailFixture address = fixture(ledger(), "merge_target_branch: 'someone@example.org'");
    DetailFixture token = fixture(ledger(), "merge_target_branch: '" + secret() + "'");

    assertThat(served(path).mergeTargetBranch()).isNull();
    assertThat(served(address).mergeTargetBranch()).isNull();
    assertThat(served(token).mergeTargetBranch()).isNull();
    assertThat(path.diagnostics()).isEmpty();
    assertThat(address.diagnostics()).isEmpty();
    assertThat(token.diagnostics()).isEmpty();
    assertThat(served(fixture(ledger(), "merge_target_branch: release/1.0")).mergeTargetBranch()).as("a clean value is served as stored").isEqualTo("release/1.0");
    // the contract gives mergeTargetBranch no length bound and the oracle serves a long clean name as stored; the plan's "over 255" is the planning branch of the detail route
    assertThat(served(fixture(ledger(), "merge_target_branch: '" + "b".repeat(300) + "'")).mergeTargetBranch()).hasSize(300);
  }

  @Test
  @ProjectionRow(row = "T10", route = "getWorkPackage")
  void t10ALastTransitionThatIsNotAnInstantIsTheWholeHeadLedgerUnparseable() {
    assertRefused(fixture(transition(1, "not-an-instant", "planned", "claimed", "")), DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  @Test
  @ProjectionRow(row = "T11", route = "getWorkPackage")
  void t11TheLastEventIdIsTheOneOfTheLastTransitionInSortedOrderAndPassesThroughTheMapper() {
    String ledger = transition(2, "2026-09-01T10:02:00Z", "claimed", "in_progress", "") + transition(1, "2026-09-01T10:01:00Z", "planned", "claimed", "");

    WorkPackage shown = served(fixture(ledger));

    assertThat(shown.lastEventId()).isEqualTo(Rows.id(2));
    assertThat(shown.lastTransitionAt()).isEqualTo("2026-09-01T10:02:00Z");
    assertThat(shown.forceCount()).isZero();
    // the mapper alone: it adds nothing and drops nothing
    assertThat(workPackage(handBuilt(List.of()).lastEventId("E-42")).lastEventId()).isEqualTo("E-42");
  }

  @Test
  @ProjectionRow(row = "T12", route = "getWorkPackage")
  void t12AHistoryEventIdThatCannotBeShownRefusesTheWorkPackage() {
    // a non-text id makes the codec refuse the whole ledger (V25, decision D-P10-1); a text id that is shaped like a path is the route's refusal
    assertRefused(fixture(transition(1, "2026-09-01T10:00:00Z", "planned", "claimed", "").replace(Rows.id(1), LEAK) + transition(2, "2026-09-01T10:02:00Z", "claimed", "in_progress", "")), DiagnosticCode.PROJECTION_REFUSED);

    WorkPackage shown = served(fixture(ledger()));
    assertThat(shown.history()).hasSize(1);
    assertThat(shown.history().get(0).getEventId()).isEqualTo(Rows.id(1));
  }

  @Test
  @ProjectionRow(row = "T13", route = "getWorkPackage")
  void t13AHistoryStampThatIsNotAnInstantRefusesTheWorkPackage() {
    assertRefused(fixture(transition(1, "0-not-an-instant", "planned", "claimed", "") + transition(2, "2026-09-01T10:02:00Z", "claimed", "in_progress", "")), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  @ProjectionRow(row = "T14", route = "getWorkPackage")
  void t14AnOverrideTimeThatIsNotAnInstantIsNullOnAPartialRecordAndARefusalOnACompleteOne() {
    WorkPackage partial = served(fixture(ledger() + annotation(2, "{\"review\":{\"actor\":\"operator-omar\",\"at\":\"2026-09-01T10:02:00\",\"reason\":\"\",\"wp_id\":\"WP01\"}}")));
    assertThat(partial.review().getOverride().getComplete()).isFalse();
    assertThat(partial.review().getOverride().getAt()).isNull();
    assertThat(partial.review().getOverride().getActor()).isEqualTo("operator-omar");

    assertRefused(fixture(ledger() + annotation(2, "{\"review\":{\"actor\":\"operator-omar\",\"at\":\"yesterday\",\"reason\":\"ship\",\"wp_id\":\"WP01\"}}")), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  @ProjectionRow(row = "T17", route = "getWorkPackage")
  void t17EveryActorHandleThatDoesNotFitIsNullAndNeverAnError() {
    String bad = "not a handle";
    String ledger =
        "{\"actor\":\"" + bad + "\",\"at\":\"2026-09-01T10:01:00Z\",\"event_id\":\"" + Rows.id(1) + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,"
            + "\"from_lane\":\"in_review\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"approved\",\"wp_id\":\"WP01\",\"policy_metadata\":{\"agent\":\"" + bad + "\"},"
            + "\"review_result\":{\"reference\":\"r\",\"reviewer\":\"" + bad + "\",\"verdict\":\"approved\"}}\n"
            + annotation(2, "{\"assignee\":\"" + bad + "\",\"role\":\"" + bad + "\",\"agent_profile\":\"" + bad + "\",\"model\":\"" + bad + "\",\"provider\":\"" + bad + "\",\"agent\":\"" + bad + "\"}")
            + annotation(3, "{\"review\":{\"actor\":\"" + bad + "\",\"at\":\"2026-09-01T10:02:00+00:00\",\"reason\":\"ship\",\"wp_id\":\"WP01\"}}");

    WorkPackage shown = served(fixture(ledger));

    assertThat(shown.assignment().getAgent()).isNull();
    assertThat(shown.assignment().getAssignee()).isNull();
    assertThat(shown.assignment().getRole()).isNull();
    assertThat(shown.assignment().getAgentProfile()).isNull();
    assertThat(shown.assignment().getModel()).isNull();
    assertThat(shown.assignment().getProvider()).isNull();
    assertThat(shown.implementerOfRecord()).isNull();
    assertThat(shown.actor().getTool()).isNull();
    assertThat(shown.review().getLatestResult().getReviewer()).isNull();
    assertThat(shown.review().getOverride().getActor()).isNull();
    assertThat(shown.history().get(0).getActor().getTool()).isNull();
    // and a handle that fits is shown as it is
    WorkPackage fits = served(fixture(transition(1, "2026-09-01T10:01:00Z", "planned", "claimed", "")));
    assertThat(fits.actor().getTool()).isEqualTo("claude");
    assertThat(fits.history().get(0).getActor().getTool()).isEqualTo("claude");
  }

  @Test
  void theClassDiscoversExactlyTheTenPairsOfGetWorkPackage() {
    List<String> pairs =
        Arrays.stream(WorkPackageMapperTest.class.getDeclaredMethods())
            .map(method -> method.getAnnotation(ProjectionRow.class))
            .filter(Objects::nonNull)
            .map(row -> row.row() + "/" + row.route())
            .sorted()
            .toList();

    assertThat(pairs)
        .containsExactly(
            "T10/getWorkPackage", "T11/getWorkPackage", "T12/getWorkPackage", "T13/getWorkPackage", "T14/getWorkPackage", "T17/getWorkPackage", "T5/getWorkPackage", "T6/getWorkPackage", "T7/getWorkPackage", "T8/getWorkPackage");
  }

  // ---- the shape of the mapping ----------------------------------------------------------------------------------------------------

  /** A view with the given ordered subtask entries and nothing else of note. */
  private static HandBuilt handBuilt(List<Map.Entry<String, Lane>> subtasks) {
    return new HandBuilt(subtasks);
  }

  private record HandBuilt(List<Map.Entry<String, Lane>> subtasks, String eventId) {
    HandBuilt(List<Map.Entry<String, Lane>> subtasks) {
      this(subtasks, null);
    }

    HandBuilt lastEventId(String id) {
      return new HandBuilt(subtasks, id);
    }
  }

  private static WorkPackage workPackage(HandBuilt built) {
    return WorkPackageMapper.workPackage(viewOf(built));
  }

  private static WorkPackageView viewOf(HandBuilt built) {
    return new WorkPackageView(
        new WpId("WP01"), "T", null, new WorkPackageView.Authored(null, null, null, List.of()), List.of(), List.of(), List.of(), null, null, null, null, List.of(), Lane.PLANNED, Assignment.EMPTY,
        built.subtasks(), new SubtaskProgress(0, built.subtasks().size()), null, null, 0, built.eventId(), Actor.NONE, null, new Readiness(true, List.of()), true, new ReviewView(null, null), List.of(), null, null);
  }

  @Test
  void theSubtasksKeepTheOrderTheViewGivesAndTheBodyWritesThemInCodePointOrder() {
    String early = "～a";
    String late = "😀b";
    HandBuilt built = handBuilt(List.of(new SimpleEntry<>(early, Lane.DONE), new SimpleEntry<>(late, Lane.PLANNED)));

    WorkPackage shown = workPackage(built);

    assertThat(shown.subtasks().keySet()).as("the mapper does no sorting").containsExactly(early, late);
    assertThat(shown.subtasks()).containsEntry(early, "done").containsEntry(late, "planned");
    String json = JSON.writeValueAsString(shown);
    assertThat(json.indexOf(early)).as("code-point order in the body, not UTF-16 order").isPositive().isLessThan(json.indexOf(late));
  }

  @Test
  void aViewThatArrivesInTheOtherOrderIsStillWrittenInCodePointOrder() {
    String early = "～a";
    String late = "😀b";
    WorkPackage shown = workPackage(handBuilt(List.of(new SimpleEntry<>(late, Lane.PLANNED), new SimpleEntry<>(early, Lane.DONE))));

    String json = JSON.writeValueAsString(shown);

    assertThat(json.indexOf(early)).isLessThan(json.indexOf(late));
  }

  @Test
  void theWithoutPromptBodyHasNoPromptKeyAtAllAndTheStalenessIsNull() {
    WorkPackage shown = workPackage(handBuilt(List.of()));

    String json = JSON.writeValueAsString(shown);

    assertThat(json).doesNotContain("promptMarkdown");
    assertThat(json).contains("\"staleness\":null");
    assertThat(shown.history()).isEmpty();
    assertThat(shown.cancellation()).isNull();
  }

  @Test
  void aViewWithEveryOptionalMemberIsShapedMemberForMember() {
    HistoryRow row = new HistoryRow("WP01", "E1", "2026-09-01T10:01:00Z", null, "planned", new Actor("claude", "implementer", "java-jenny"), true, "why", "approved");
    WorkPackageView view =
        new WorkPackageView(
            new WpId("WP01"), "T", "Phase", new WorkPackageView.Authored("r", "p", "m", List.of("T001")), List.of("a/**"), List.of(new WpId("WP00")), List.of("FR-1"), "code_change", "task", "high", "main", List.of("GH-1"),
            Lane.CANCELED, new Assignment("agent", "assignee", "role", "profile", "1", "model", "provider"), List.of(new SimpleEntry<>("T001", Lane.DONE)), new SubtaskProgress(1, 1), "impl", "2026-09-01T10:01:00Z", 2, "E1",
            new Actor("claude", null, null), new WorkPackageView.Cancellation(WorkPackageView.ReasonSource.OPERATOR, "stopped"), new Readiness(false, List.of(new WpId("WP00"))), false,
            new ReviewView(new ReviewView.Result("rev", ReviewView.Verdict.CHANGES_REQUESTED, "ref"), new ReviewView.ReviewOverride(true, "2026-09-01T10:02:00+00:00", "op", "ok")), List.of(row),
            new WorkPackageView.Staleness(WorkPackageView.Staleness.Status.NOT_APPLICABLE, WorkPackageView.Staleness.Reason.LIVE_CLAIM_PROCESS, 1.5), "prompt text");

    WorkPackage shown = WorkPackageMapper.workPackage(view);

    assertThat(shown.statusLane()).isEqualTo("canceled");
    assertThat(shown.cancellation().getReasonSource().getValue()).isEqualTo("operator");
    assertThat(shown.cancellation().getReason()).isEqualTo("stopped");
    assertThat(shown.assignment().getAgentProfileVersion()).isEqualTo("1");
    assertThat(shown.review().getLatestResult().getVerdict().getValue()).isEqualTo("changes_requested");
    assertThat(shown.review().getOverride().getComplete()).isTrue();
    assertThat(shown.history().get(0).getFromStatusLane()).isNull();
    assertThat(shown.history().get(0).getToStatusLane().getValue()).isEqualTo("planned");
    assertThat(shown.history().get(0).getForce()).isTrue();
    assertThat(shown.history().get(0).getReviewVerdict().getValue()).isEqualTo("approved");
    assertThat(shown.history().get(0).getActor().getProfile()).isEqualTo("java-jenny");
    assertThat(shown.staleness().getStatus().getValue()).isEqualTo("not_applicable");
    assertThat(shown.staleness().getReason().getValue()).isEqualTo("live_claim_process");
    assertThat(shown.staleness().getMinutesSinceCommit()).isEqualByComparingTo("1.5");
    assertThat(shown.promptMarkdown()).isEqualTo("prompt text");
    assertThat(shown.readyToStart()).isFalse();
    assertThat(shown.forceCount()).isEqualTo(2);
  }
}
