package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.in.http.detail.WorkPackageControllerRowsTest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The Java outcome of each {@code knownDivergence} fixture that {@code WorkPackageServedRoute} leaves out of the byte comparison (V20 to V25 and V28): the oracle's golden is the oracle's, and what Java does instead is pinned here, against the fixture, so the divergence cannot drift
 * unseen. Where the oracle serves a body and Java serves the same body with a member changed, the rest of the body is still compared with the
 * golden, byte for byte.
 */
class WorkPackageQueryServiceDivergenceTest {

  private static TreeFixture fixture(String key) {
    return WorkPackageServedRoute.fixture(key);
  }

  private static void assertUnavailable(String key, String wp, DiagnosticCode code) {
    TreeFixture tree = fixture(key);
    DetailFixture detail = DetailFixture.of(tree.dir());
    String mission = WorkPackageServedRoute.missionIdOf(tree);

    assertThatThrownBy(() -> WorkPackageControllerRowsTest.view(detail, mission, wp, false))
        .as(key)
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, refusal -> assertThat(refusal.code()).isEqualTo(code));
    assertThat(detail.diagnostics()).extracting(Diagnostic::code).as(key).containsExactly(code);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> golden(TreeFixture tree) {
    return (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(tree, WorkPackageServedRoute.GOLDEN));
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> served(TreeFixture tree, String wp) {
    DetailFixture detail = DetailFixture.of(tree.dir());
    try (HttpHarness server = HttpHarness.startWired(detail.root())) {
      HttpHarness.Response response = server.get(WorkPackageServedRoute.path(WorkPackageServedRoute.missionIdOf(tree), wp, false));
      assertThat(response.status()).isEqualTo(200);
      return (Map<String, Object>) CanonicalJson.parse(response.body());
    }
  }

  @Test
  void anEmptyGoldenIsAFileTheOracleSkippedAndJavaSkipsItToo() throws java.io.IOException {
    int checked = 0;
    for (ServedRoute.Entry entry : WorkPackageServedRoute.emptyEntries()) {
      TreeFixture tree = fixture(entry.fixtureKey());
      DetailFixture detail = DetailFixture.of(tree.dir());
      String mission = WorkPackageServedRoute.missionIdOf(tree);
      List<String> ids = new java.util.ArrayList<>();
      try (java.util.stream.Stream<java.nio.file.Path> missions = java.nio.file.Files.list(detail.root().resolve("kitty-specs"))) {
        for (java.nio.file.Path dir : missions.toList()) {
          java.nio.file.Path tasks = dir.resolve("tasks");
          if (java.nio.file.Files.isDirectory(tasks)) {
            try (java.util.stream.Stream<java.nio.file.Path> files = java.nio.file.Files.list(tasks)) {
              files.map(file -> file.getFileName().toString()).filter(name -> name.matches("WP[0-9]{2,}.*\\.md")).map(name -> name.substring(0, name.indexOf('-') < 0 ? name.length() - 3 : name.indexOf('-'))).forEach(ids::add);
            }
          }
        }
      }
      assertThat(ids).as(entry.fixtureKey() + " has a Work Package file").isNotEmpty();
      for (String id : ids) {
        assertThatThrownBy(() -> WorkPackageControllerRowsTest.view(detail, mission, id, false)).as(entry.fixtureKey() + " " + id).isInstanceOf(DetailRefusal.class);
      }
      checked++;
    }
    assertThat(checked).isEqualTo(17);
  }

  @Test
  void v20SubtasksWrittenAsMappingsAreProjectionRefusedWhereTheOracleStringifiesThem() {
    assertUnavailable("wp-malformed-frontmatter/wpm-28", WorkPackageServedRoute.requestKeys(fixture("wp-malformed-frontmatter/wpm-28"), WorkPackageServedRoute.GOLDEN).get(0), DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  @SuppressWarnings("unchecked")
  void v21AFloatAgentOrActorIsNullWhereTheOracleServesItsReprAndEveryOtherMemberIsTheGolden() {
    TreeFixture tree = fixture("resolved-state/float-agent-and-actor");
    Map<String, Object> expected = new LinkedHashMap<>(golden(tree));
    for (String wp : List.of("WP01", "WP02")) {
      Map<String, Object> body = new LinkedHashMap<>((Map<String, Object>) expected.get(wp));
      if (wp.equals("WP01")) {
        Map<String, Object> assignment = new LinkedHashMap<>((Map<String, Object>) body.get("assignment"));
        assertThat(assignment.get("agent")).isEqualTo("1.5");
        assignment.put("agent", null);
        body.put("assignment", assignment);
        // the same float is the claim's agent, which the implementer of record reads
        assertThat(body.get("implementerOfRecord")).isEqualTo("1.5");
        body.put("implementerOfRecord", null);
      } else {
        Map<String, Object> actor = new LinkedHashMap<>((Map<String, Object>) body.get("actor"));
        assertThat(actor.get("tool")).isEqualTo("2.5");
        actor.put("tool", null);
        body.put("actor", actor);
        // the history row carries the same float actor
        List<Object> history = new java.util.ArrayList<>((List<Object>) body.get("history"));
        Map<String, Object> last = new LinkedHashMap<>((Map<String, Object>) history.get(history.size() - 1));
        Map<String, Object> rowActor = new LinkedHashMap<>((Map<String, Object>) last.get("actor"));
        rowActor.put("tool", null);
        last.put("actor", rowActor);
        history.set(history.size() - 1, last);
        body.put("history", history);
      }
      CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(served(tree, wp)), CanonicalJson.toBytes(body));
    }
  }

  @ParameterizedTest(name = "{0}")
  @ValueSource(strings = {"annotation-at-float", "annotation-at-list", "override-member-float"})
  void v22AnAnnotationAtOrAnOverrideMemberThatIsNotTextMakesTheLedgerUnreadable(String name) {
    assertUnavailable("resolved-state/" + name, "WP01", DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  @Test
  void v23AVerdictThatIsNotTextIsAProjectionRefusalWhereTheOracleServesTheRawValue() {
    TreeFixture tree = fixture("resolved-state/verdict-not-text");

    assertUnavailable("resolved-state/verdict-not-text", "WP01", DiagnosticCode.PROJECTION_REFUSED);
    assertThat(golden(tree)).containsKey("WP01");
  }

  @Test
  void v24ASubtaskStatusOfGenesisOrUninitializedIsAProjectionRefusalWhereTheOracleServesIt() {
    assertUnavailable("resolved-state/subtask-status-genesis", "WP01", DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void v25ANonTextEventIdIsALedgerRefusalWhereTheOracleServesTheNumber() {
    assertUnavailable("resolved-state/history-event-id-not-text", "WP01", DiagnosticCode.LEDGER_UNPARSEABLE);
  }

  @Test
  @SuppressWarnings("unchecked")
  void v28AClockAheadApprovalsDepartureEndsApprovedWhereThe1051OracleEndsDoneAndEveryOtherMemberIsTheGolden() {
    TreeFixture tree = fixture("resolved-state/history-mixed-offsets");
    Map<String, Object> body = new LinkedHashMap<>((Map<String, Object>) golden(tree).get("WP01"));
    // the 10.5.1 oracle sorts the done departure after the clock-ahead approval it followed (spec-kitty#4941)
    assertThat(body).containsEntry("statusLane", "done").containsEntry("lastEventId", "0000000000000000000000R104").containsEntry("lastTransitionAt", "2026-09-01T10:31:00Z");
    // Java keeps the 10.4.6 text order until spec-kitty#6268 ports the rule; once it serves done, retire V28 and untag the fixture
    body.put("statusLane", "approved");
    body.put("lastEventId", "0000000000000000000000R0A2");
    body.put("lastTransitionAt", "2026-09-01T11:30:00+01:00");
    Map<String, Object> actor = new LinkedHashMap<>((Map<String, Object>) body.get("actor"));
    assertThat(actor.get("tool")).isEqualTo("claude");
    actor.put("tool", "reviewer-renata");
    body.put("actor", actor);
    CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(served(tree, "WP01")), CanonicalJson.toBytes(body));
    CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(served(tree, "WP02")), CanonicalJson.toBytes(golden(tree).get("WP02")));
  }

  @Test
  void theNamedTestsCoverEveryDivergentFixture() {
    Set<String> covered =
        Set.of(
            "wp-malformed-frontmatter/wpm-28",
            "resolved-state/float-agent-and-actor",
            "resolved-state/annotation-at-float",
            "resolved-state/annotation-at-list",
            "resolved-state/override-member-float",
            "resolved-state/verdict-not-text",
            "resolved-state/subtask-status-genesis",
            "resolved-state/history-event-id-not-text",
            "resolved-state/history-mixed-offsets");

    assertThat(WorkPackageServedRoute.DIVERGENT).isEqualTo(covered);
  }
}
