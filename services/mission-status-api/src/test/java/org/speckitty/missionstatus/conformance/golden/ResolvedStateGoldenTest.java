package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.reducer.UnreducibleLedgerException;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * AC-20.1 at the port-level path: the resolved state the Java reducer gives for the ledger of each {@code resolved-state} fixture, compared
 * with the committed oracle golden ({@code golden/get-work-package.json}, keyed by Work Package id). The golden is a whole Work Package
 * body; the members compared are exactly the ones the reduction owns (actor, assignment, history, review result and override, subtasks and
 * their progress, lane, force count, last event id and instant). The rest of the body is the route work packages'.
 *
 * <p>Eight fixtures carry the {@code knownDivergence} tag: the oracle serves there what Java deliberately does not (V21 to V25 and V28
 * of the manifest). They are not compared byte for byte; each is asserted against its manifest entry, so a divergence cannot drift unseen,
 * and the set of tagged fixtures must equal the set the entries name. Two facts are pinned here: in Java {@code history-mixed-offsets}
 * ends {@code approved}, not {@code done} (the fold orders by text, the history by instant: D-P4b-4), where the 10.5.1 oracle ends
 * {@code done} (V28, until spec-kitty#6268 ports the rule), and the V25 golden carries a non-text event id as its raw JSON value.
 */
class ResolvedStateGoldenTest {

  private static final String CLASS = "resolved-state";
  private static final String GOLDEN = "get-work-package.json";
  private static final Set<String> COMPARED_MEMBERS =
      Set.of("actor", "assignment", "history", "review", "subtasks", "subtaskProgress", "statusLane", "forceCount", "lastEventId", "lastTransitionAt");

  static List<TreeFixture> all() {
    return ConformanceTree.detailClasses().stream().filter(entry -> entry.tag().equals(CLASS)).flatMap(entry -> entry.fixtures().stream()).toList();
  }

  static Stream<TreeFixture> compared() {
    return all().stream().filter(fixture -> !fixture.knownDivergence());
  }

  static Stream<TreeFixture> diverging() {
    return all().stream().filter(TreeFixture::knownDivergence);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> golden(TreeFixture fixture) {
    return (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, GOLDEN));
  }

  /** The subject Mission's directory: the first directory of {@code kitty-specs}, in name order. */
  private static String missionDirectory(TreeFixture fixture) {
    try (Stream<Path> missions = Files.list(fixture.dir().resolve("kitty-specs"))) {
      return missions.filter(Files::isDirectory).map(path -> path.getFileName().toString()).sorted().findFirst().orElseThrow();
    } catch (IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    }
  }

  private static StatusSnapshot reduce(TreeFixture fixture) {
    return DetailFixture.of(fixture.dir()).reduce(missionDirectory(fixture));
  }

  // ---- the Java side as the members of the golden -----------------------------------------------------------------------------

  /** The compared members of one Work Package as the Java reduction gives them, in the shape of the golden. */
  static Map<String, Object> members(StatusSnapshot snapshot, String wpId) {
    WpResolved resolved = snapshot.resolved().getOrDefault(wpId, WpResolved.empty());
    WpState state = snapshot.workPackages().get(wpId);
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("actor", actor(resolved.actor()));
    Map<String, Object> assignment = new LinkedHashMap<>();
    assignment.put("agent", resolved.assignment().agent());
    assignment.put("agentProfile", resolved.assignment().agentProfile());
    assignment.put("agentProfileVersion", resolved.assignment().agentProfileVersion());
    assignment.put("assignee", resolved.assignment().assignee());
    assignment.put("model", resolved.assignment().model());
    assignment.put("provider", resolved.assignment().provider());
    assignment.put("role", resolved.assignment().role());
    out.put("assignment", assignment);
    List<Object> history = new ArrayList<>();
    for (HistoryRow row : resolved.history()) {
      Map<String, Object> entry = new LinkedHashMap<>();
      entry.put("actor", actor(row.actor()));
      entry.put("at", row.at());
      entry.put("eventId", row.eventId());
      entry.put("force", row.force());
      entry.put("fromStatusLane", shownLane(row.fromLane()));
      entry.put("kind", "transition");
      entry.put("reason", row.reason());
      entry.put("reviewVerdict", row.reviewVerdict());
      entry.put("toStatusLane", shownLane(row.toLane()));
      history.add(entry);
    }
    out.put("history", history);
    Map<String, Object> review = new LinkedHashMap<>();
    review.put("latestResult", result(resolved.reviewResult()));
    review.put("override", override(resolved.reviewOverride()));
    out.put("review", review);
    Map<String, Object> subtasks = new LinkedHashMap<>();
    int done = 0;
    for (Map.Entry<String, Lane> subtask : resolved.subtasks().entrySet()) {
      subtasks.put(subtask.getKey(), subtask.getValue().wire());
      done += subtask.getValue() == Lane.DONE ? 1 : 0;
    }
    out.put("subtasks", subtasks);
    Map<String, Object> progress = new LinkedHashMap<>();
    progress.put("done", done);
    progress.put("total", subtasks.size());
    out.put("subtaskProgress", progress);
    out.put("statusLane", state == null || !state.lane().isDisplay() ? null : state.lane().wire());
    out.put("forceCount", state == null ? 0 : state.forceCount());
    out.put("lastEventId", state == null ? null : state.lastEventId());
    out.put("lastTransitionAt", state == null ? null : state.lastTransitionAt());
    return out;
  }

  private static Map<String, Object> actor(Actor actor) {
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("profile", actor.profile());
    out.put("role", actor.role());
    out.put("tool", actor.tool());
    return out;
  }

  /** {@code Projector.lane}: null for no lane and for a lane that is not a display lane. */
  private static String shownLane(String stored) {
    return stored == null || !Lane.fromWire(stored).isDisplay() ? null : stored;
  }

  private static Map<String, Object> result(ReviewResultRecord record) {
    if (record == null) {
      return null;
    }
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("reference", record.reference() == null ? "" : record.reference());
    out.put("reviewer", record.reviewer());
    out.put("verdict", record.verdict());
    return out;
  }

  /** The oracle's {@code review_override}: the release marker is none; a time is shown only with an offset; an empty text is none. */
  private static Map<String, Object> override(ReviewOverrideRecord record) {
    if (record == null || record.releaseSentinel()) {
      return null;
    }
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("actor", record.actor().isEmpty() ? null : Actor.ofText(record.actor()).tool());
    out.put("at", !record.at().isEmpty() && Instants.hasOffset(record.at()) ? record.at() : null);
    out.put("complete", record.complete());
    out.put("reason", record.reason().isEmpty() ? null : record.reason());
    return out;
  }

  /** The golden members of one Work Package: the compared keys of its body. */
  @SuppressWarnings("unchecked")
  private static Map<String, Object> goldenMembers(Map<String, Object> body) {
    Map<String, Object> out = new LinkedHashMap<>();
    for (String key : COMPARED_MEMBERS) {
      out.put(key, body.get(key));
    }
    return out;
  }

  // ---- the comparison --------------------------------------------------------------------------------------------------------

  static void assertEqualsGolden(StatusSnapshot snapshot, Map<String, Object> golden) {
    assertThat(new TreeSet<>(snapshot.resolved().keySet()).containsAll(golden.keySet())).as("the reduction knows every Work Package of the golden").isTrue();
    for (Map.Entry<String, Object> wp : golden.entrySet()) {
      @SuppressWarnings("unchecked")
      Map<String, Object> body = (Map<String, Object>) wp.getValue();
      try {
        CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(members(snapshot, wp.getKey())), CanonicalJson.toBytes(goldenMembers(body)));
      } catch (AssertionError mismatch) {
        throw new AssertionError(wp.getKey() + ": " + mismatch.getMessage(), mismatch);
      }
    }
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("compared")
  void theJavaReductionEqualsTheOracleGoldenOnEveryComparedMember(TreeFixture fixture) {
    assertEqualsGolden(reduce(fixture), golden(fixture));
  }

  @Test
  void thereAreTwentyOneFixturesThirteenCompared() {
    assertThat(all()).hasSize(21);
    assertThat(compared().count()).isEqualTo(13);
    assertThat(diverging().map(TreeFixture::name)).containsExactlyInAnyOrder(
        "float-agent-and-actor", "annotation-at-float", "annotation-at-list", "override-member-float", "verdict-not-text", "subtask-status-genesis", "history-event-id-not-text",
        "history-mixed-offsets");
  }

  @Test
  void theComparisonIsNotVacuousAMemberChangedInTheJavaTreeIsRed() {
    TreeFixture fixture = all().stream().filter(candidate -> candidate.name().equals("set-each-member")).findFirst().orElseThrow();
    StatusSnapshot snapshot = reduce(fixture);
    Map<String, Object> golden = golden(fixture);
    assertEqualsGolden(snapshot, golden);

    // a golden whose assignee differs by one letter is red, and so is one whose history lost a row
    Map<String, Object> changed = deepCopy(golden);
    mapAt(changed, "WP01", "assignment").put("assignee", "owner-olgb");
    assertThatThrownBy(() -> assertEqualsGolden(snapshot, changed)).isInstanceOf(AssertionError.class).hasMessageContaining("WP01");

    Map<String, Object> shorter = deepCopy(golden);
    @SuppressWarnings("unchecked")
    List<Object> history = (List<Object>) ((Map<String, Object>) shorter.get("WP01")).get("history");
    history.removeFirst();
    assertThatThrownBy(() -> assertEqualsGolden(snapshot, shorter)).isInstanceOf(AssertionError.class);

    // the members that the golden holds are not all empty: a reducer that returned empty members would be red
    assertThat(((Map<?, ?>) mapAt(golden, "WP01", "assignment")).values()).anyMatch(value -> value != null);
    assertThat(members(snapshot, "WP01").get("history")).asList().isNotEmpty();
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> mapAt(Map<String, Object> golden, String wp, String member) {
    return (Map<String, Object>) ((Map<String, Object>) golden.get(wp)).get(member);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> deepCopy(Map<String, Object> source) {
    return (Map<String, Object>) CanonicalJson.parse(CanonicalJson.toBytes(source));
  }

  // ---- the oracle facts ------------------------------------------------------------------------------------------------------

  @Test
  void v28HistoryMixedOffsetsEndsApprovedInJavaAndDoneInThe1051Oracle() {
    TreeFixture fixture = fixture("history-mixed-offsets");
    StatusSnapshot snapshot = reduce(fixture);
    @SuppressWarnings("unchecked")
    Map<String, Object> goldenWp = (Map<String, Object>) golden(fixture).get("WP01");

    assertThat(mapAt(golden(fixture), "WP01", "assignment")).isNotNull();
    // the 10.5.1 oracle sorts the done departure after the clock-ahead approval it followed (spec-kitty#4941), so it ends done
    assertThat(goldenWp).containsEntry("statusLane", "done").containsEntry("lastEventId", "0000000000000000000000R104").containsEntry("lastTransitionAt", "2026-09-01T10:31:00Z");
    assertThat(mapAt(golden(fixture), "WP01", "actor")).containsEntry("tool", "claude");
    // Java keeps the 10.4.6 text order: the fold put the done transition before the approval
    assertThat(snapshot.workPackages().get("WP01").lane())
        .as("V28: Java ends approved until spec-kitty#6268 ports the 10.5.1 approved-departure rule; once Java ends done, retire V28 and untag the fixture")
        .isEqualTo(Lane.APPROVED);
    assertThat(snapshot.workPackages().get("WP01").lastEventId()).isEqualTo("0000000000000000000000R0A2");
    assertThat(snapshot.resolved().get("WP01").actor().tool()).isEqualTo("reviewer-renata");
    // the last row of the history by instant is the done transition, which the fold (by text) put before the approval
    List<HistoryRow> history = snapshot.resolved().get("WP01").history();
    assertThat(history.stream().map(HistoryRow::toLane)).contains("done");
    assertThat(history.getLast().toLane()).isNotEqualTo("approved");
    // every other member agrees, the history included
    assertEqualsExcept(snapshot, golden(fixture), Map.of("WP01", Set.of("actor", "statusLane", "lastEventId", "lastTransitionAt")));
  }

  // ---- the knownDivergence fixtures, by their manifest entries ---------------------------------------------------------------

  @Test
  void theTaggedFixturesAreExactlyTheOnesTheEntriesV21ToV25AndV28Name() {
    Set<String> named = new LinkedHashSet<>();
    Set<String> ids = new TreeSet<>();
    for (Map<String, Object> entry : ConformanceTree.knownDivergences()) {
      String id = (String) entry.get("id");
      if (List.of("V21", "V22", "V23", "V24", "V25", "V28").contains(id)) {
        ids.add(id);
        for (Object fixtureKey : (List<?>) entry.get("fixtures")) {
          named.add(fixtureKey.toString());
        }
      }
    }

    assertThat(ids).containsExactly("V21", "V22", "V23", "V24", "V25", "V28");
    assertThat(named).isEqualTo(new LinkedHashSet<>(diverging().map(TreeFixture::key).toList()));
  }

  @Test
  void v21AFloatAgentOrActorIsNullInJavaAndTheFloatsReprInTheGolden() {
    TreeFixture fixture = fixture("float-agent-and-actor");
    StatusSnapshot snapshot = reduce(fixture);

    assertThat(snapshot.resolved().get("WP01").assignment().agent()).isNull();
    assertThat(snapshot.resolved().get("WP02").actor().tool()).isNull();
    assertThat(mapAt(golden(fixture), "WP01", "assignment").get("agent")).isEqualTo("1.5");
    assertThat(mapAt(golden(fixture), "WP02", "actor")).containsEntry("tool", "2.5");
    // every other member agrees
    assertEqualsExcept(snapshot, golden(fixture), Map.of("WP01", Set.of("assignment"), "WP02", Set.of("actor")));
  }

  @Test
  void v22AnAnnotationAtOrAnOverrideMemberThatIsNotTextRaisesInJavaAndIsReadByTheOracle() {
    for (String name : List.of("annotation-at-float", "annotation-at-list", "override-member-float")) {
      TreeFixture fixture = fixture(name);

      assertThatThrownBy(() -> reduce(fixture)).as(name).isInstanceOf(RuntimeException.class);
      assertThat(golden(fixture)).as(name + " has a golden: the oracle read the row").containsKey("WP01");
    }
    assertThat(mapAt(golden(fixture("override-member-float")), "WP01", "review").get("override")).asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.MAP).containsEntry("reason", "2.5");
  }

  @Test
  void v23AVerdictThatIsNotTextIsNullInJavaAndTheRawValueInTheGolden() {
    TreeFixture fixture = fixture("verdict-not-text");
    StatusSnapshot snapshot = reduce(fixture);

    assertThat(snapshot.resolved().get("WP01").reviewResult().verdict()).isNull();
    assertThat(mapAt(golden(fixture), "WP01", "review").get("latestResult")).asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.MAP).containsEntry("verdict", new CanonicalJson.Num("7"));
  }

  @Test
  void v24ASubtaskStatusOfGenesisOrUninitializedIsKeptByTheReductionForTheMapperToRefuse() {
    TreeFixture fixture = fixture("subtask-status-genesis");
    StatusSnapshot snapshot = reduce(fixture);
    Map<String, Lane> subtasks = snapshot.resolved().get("WP01").subtasks();

    assertThat(subtasks).containsEntry("T001", Lane.GENESIS).containsEntry("T002", Lane.UNINITIALIZED).containsEntry("T003", Lane.DONE);
    assertThat(subtasks.values().stream().filter(lane -> !lane.isDisplay())).as("values outside StatusLane: the route mapper refuses them").hasSize(2);
    assertThat(golden(fixture)).extractingByKey("WP01").asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.MAP)
        .containsEntry("subtasks", Map.of("T001", "genesis", "T002", "uninitialized", "T003", "done"));
    CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(members(snapshot, "WP01").get("subtaskProgress")), CanonicalJson.toBytes(mapAt(golden(fixture), "WP01", "subtaskProgress")));
    assertEqualsExcept(snapshot, golden(fixture), Map.of("WP01", Set.of("subtasks")));
  }

  @Test
  void v25ANonTextEventIdMakesJavaRefuseTheLedgerWhereTheOracleCarriesTheRawJsonValue() {
    TreeFixture fixture = fixture("history-event-id-not-text");

    // D-P10-1 (decision of WP14, T12): the whole-ledger refusal stands. The codec classifies the row as unusable (a status row needs a text
    // event_id), so the reduction raises and no history is served. A narrower refusal at the Work Package route would need the codec to carry
    // the row with a non-text id into the fold, which the overview and the stream would then also serve where they refuse today; the manifest
    // entry allows "a null refused by the mapper", and a refused Mission is a refusal. The routes answer ledger_unparseable
    // (WorkPackageQueryServiceTest#v25..., WorkPackageQueryServiceDivergenceTest#v25...). The number is never served: whoever makes Java serve
    // "eventId": 424242 changes this test on purpose.
    assertThatThrownBy(() -> reduce(fixture)).isInstanceOfSatisfying(UnreducibleLedgerException.class, refusal -> assertThat(refusal.lineNumber()).isEqualTo(2));
    @SuppressWarnings("unchecked")
    List<Map<String, Object>> goldenHistory = (List<Map<String, Object>>) ((Map<String, Object>) golden(fixture).get("WP01")).get("history");
    assertThat(goldenHistory.getLast().get("eventId")).isEqualTo(new CanonicalJson.Num("424242"));
    assertThat(new String(CanonicalJson.toBytes(goldenHistory.getLast().get("eventId")), java.nio.charset.StandardCharsets.UTF_8)).isEqualTo("424242\n");
    assertThat(goldenHistory.getFirst().get("eventId")).as("the other rows keep text ids").isInstanceOf(String.class);
  }

  private static TreeFixture fixture(String name) {
    return all().stream().filter(candidate -> candidate.name().equals(name)).findFirst().orElseThrow();
  }

  /** The comparison with the named members of the named Work Packages left out (a knownDivergence says which). */
  @SuppressWarnings("unchecked")
  private static void assertEqualsExcept(StatusSnapshot snapshot, Map<String, Object> golden, Map<String, Set<String>> skip) {
    for (Map.Entry<String, Object> wp : golden.entrySet()) {
      Map<String, Object> expected = goldenMembers((Map<String, Object>) wp.getValue());
      Map<String, Object> actual = members(snapshot, wp.getKey());
      for (String member : skip.getOrDefault(wp.getKey(), Set.of())) {
        expected.remove(member);
        actual.remove(member);
      }
      CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(actual), CanonicalJson.toBytes(expected));
    }
  }
}
