package org.speckitty.missionstatus.conformance.golden.served;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The provider of {@code getMission} is registered, owns exactly its row of the partition, serves every manifest fixture that holds the golden
 * (the {@code knownDivergence} fixtures excepted, which are named and pinned), and its bodies are what the comparator needs: AC-1.2 (one
 * head), AC-14.2 (the comparator bites). {@code ServedRoutes} loads providers by name and treats a missing class as an empty route, so a
 * typo would leave {@code DetailGoldenSuiteTest} green with zero comparisons: this test is what makes that impossible for this route.
 */
class MissionDetailServedRouteTest {

  /** The fixtures whose golden is the oracle's outcome and whose Java outcome differs on purpose (V1, V20). V19 is retired: head-dates-nulled is an ordinary conformance case, served and compared byte for byte. */
  private static final Set<String> DIVERGENT =
      Set.of(
          "phases-matrix/ps-link-file",
          "phases-matrix/ps-link-completed",
          "phases-matrix/ps-link-started",
          "phases-matrix/ps-link-neither",
          "wp-malformed-frontmatter/wpm-28");

  /** The classes the review checklist names, with the number of fixtures of each that holds a get-mission golden. */
  private static final Map<String, Integer> PER_CLASS_FLOORS =
      Map.of("detail-populated", 8, "detail-early", 1, "detail-planning-only", 1, "phases-matrix", 19, "wp-malformed-frontmatter", 28, "wp-duplicate-id", 3);

  private static ServedRoute provider() {
    return ServedRoutes.loaded().stream().filter(candidate -> candidate.getClass().getSimpleName().equals("MissionDetailServedRoute")).findFirst().orElseThrow(() -> new AssertionError("the registry did not load MissionDetailServedRoute"));
  }

  @Test
  void theRegistryLoadsTheProviderAndItsGoldenFilesAreItsRowOfThePartition() {
    ServedRoute provider = provider();

    assertThat(ServedRoutes.loadedProviderNames()).contains("MissionDetailServedRoute");
    Set<String> row = new java.util.TreeSet<>();
    ServedRoutes.OWNER.forEach((file, owner) -> {
      if (owner.equals("MissionDetailServedRoute")) {
        row.add(file);
      }
    });
    assertThat(provider.goldenFiles()).isEqualTo(row).containsExactly("get-mission.json");
    assertThat(ServedRoutes.ownershipProblems(List.of(provider))).isEmpty();
  }

  @Test
  void servedIsTheManifestDerivedSetMinusTheNamedDivergentFixtures() {
    ServedRoute provider = provider();
    Set<Entry> expected = ServedRoutes.expectedEntries(provider.goldenFiles());

    assertThat(MissionDetailServedRoute.divergentEntries()).extracting(Entry::fixtureKey).containsExactlyInAnyOrderElementsOf(DIVERGENT);
    assertThat(provider.served()).doesNotContainAnyElementsOf(MissionDetailServedRoute.divergentEntries());
    assertThat(provider.served().size() + MissionDetailServedRoute.divergentEntries().size()).isEqualTo(expected.size());
    assertThat(provider.served()).allSatisfy(entry -> assertThat(expected).contains(entry));
  }

  @Test
  void theServedSetMatchesTheClassEnumerationOfTheReviewChecklist() {
    Map<String, Integer> perClass = new TreeMap<>();
    for (Entry entry : provider().served()) {
      perClass.merge(entry.fixtureKey().substring(0, entry.fixtureKey().indexOf('/')), 1, Integer::sum);
    }

    PER_CLASS_FLOORS.forEach((tag, floor) -> {
      int divergent = (int) MissionDetailServedRoute.divergentEntries().stream().filter(entry -> entry.fixtureKey().startsWith(tag + "/")).count();
      assertThat(perClass.get(tag) + divergent).as(tag).isEqualTo(floor);
    });
    assertThat(perClass.get("wp-malformed-frontmatter")).as("28 getMission goldens, the SK-353 fixture left to its own test").isEqualTo(27);
    assertThat(perClass.get("detail-planning-only")).isEqualTo(1);
    assertThat(provider().served().stream().map(Entry::fixtureKey)).contains("detail-populated/bad-sibling-before", "detail-populated/bad-sibling-after", "wp-duplicate-id/duplicate-then-broken");
    assertThat(provider().served().stream().map(Entry::fixtureKey)).contains("phases-matrix/marker-row-without-event-id");
  }

  @Test
  void theProviderAnswersOnlyTheRequestKeyOfTheMissionLevelRequest() {
    ServedRoute provider = provider();
    Entry entry = provider.served().iterator().next();

    assertThat(provider.body(entry, "WP01")).isNull();
    assertThat(provider.body(entry, "-")).isNotNull();
  }

  // ---- AC-1.2: one head ------------------------------------------------------------------------------------------------------------

  /** The fixture with a sibling the list refuses on (#5529 L7): there is no item to compare with; AC-1.7 and the duplicate rows cover it. */
  private static final Set<String> LIST_REFUSES = Set.of("wp-duplicate-id/duplicate-then-broken");

  /** AC-1.2, for every fixture and over HTTP with the production wiring: the body without its phases and Work Packages is the list item. */
  @Test
  void theBodyWithoutPhasesAndWorkPackagesIsTheMissionsItemOnTheListForEveryFixture() {
    int compared = 0;
    List<String> skipped = new ArrayList<>();
    for (Entry entry : provider().served()) {
      TreeFixture fixture = MissionDetailServedRoute.fixture(entry.fixtureKey());
      String id = MissionDetailServedRoute.missionIdOf(fixture);
      DetailFixture detail = DetailFixture.of(fixture.dir());
      try (HttpHarness server = HttpHarness.startWired(detail.root())) {
        Map<String, Object> body = object(server.get(MissionDetailServedRoute.path(id)).body());
        HttpHarness.Response listed = server.get("/api/v1/missions?pageSize=200");
        if (listed.status() != 200) {
          skipped.add(entry.fixtureKey());
          continue;
        }
        Map<String, Object> item = items(object(listed.body())).stream().filter(candidate -> id.equals(candidate.get("missionId"))).findFirst().orElseThrow();
        assertThat(sharedMembersDiffer(body, item)).as(entry.fixtureKey()).isFalse();
        compared++;
      }
    }
    assertThat(skipped).containsExactlyInAnyOrderElementsOf(LIST_REFUSES);
    assertThat(compared).isGreaterThan(55);
  }

  /** The control: alter nextAction in the detail path only and the comparison goes red. */
  @Test
  void theComparisonOfTheSharedMembersGoesRedWhenNextActionIsAlteredInTheDetailBodyOnly() {
    TreeFixture fixture = MissionDetailServedRoute.fixture("detail-populated/populated");
    DetailFixture detail = DetailFixture.of(fixture.dir());
    String id = MissionDetailServedRoute.missionIdOf(fixture);
    Map<String, Object> detailBody;
    Map<String, Object> item;
    try (HttpHarness server = HttpHarness.startWired(detail.root())) {
      detailBody = object(server.get(MissionDetailServedRoute.path(id)).body());
      item = items(object(server.get("/api/v1/missions?pageSize=200").body())).stream().filter(candidate -> id.equals(candidate.get("missionId"))).findFirst().orElseThrow();
    }

    assertThat(sharedMembersDiffer(detailBody, item)).isFalse();
    Map<String, Object> altered = new LinkedHashMap<>(detailBody);
    altered.put("nextAction", "Something else entirely");
    assertThat(sharedMembersDiffer(altered, item)).isTrue();
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> object(byte[] body) {
    return (Map<String, Object>) CanonicalJson.parse(body);
  }

  @SuppressWarnings("unchecked")
  private static List<Map<String, Object>> items(Map<String, Object> page) {
    List<Map<String, Object>> items = new ArrayList<>();
    for (Object item : (List<Object>) page.get("items")) {
      items.add((Map<String, Object>) item);
    }
    return items;
  }

  /** True when the detail body without {@code phases} and {@code workPackages} is not, canonically, the list item. */
  private static boolean sharedMembersDiffer(Map<String, Object> detailBody, Map<String, Object> item) {
    Map<String, Object> shared = new LinkedHashMap<>(detailBody);
    shared.remove("phases");
    shared.remove("workPackages");
    return !java.util.Arrays.equals(CanonicalJson.toBytes(shared), CanonicalJson.toBytes(item));
  }

  // ---- AC-14.2: the comparator bites on this route's bytes ------------------------------------------------------------------------

  @Test
  void reorderingThePhasesOrPerturbingOneGoldenByteTurnsTheComparisonRed() {
    ServedRoute provider = provider();
    Entry entry = provider.served().stream().filter(candidate -> candidate.fixtureKey().equals("detail-populated/populated")).findFirst().orElseThrow();
    TreeFixture fixture = MissionDetailServedRoute.fixture(entry.fixtureKey());
    byte[] golden = ConformanceTree.golden(fixture, entry.goldenFile());
    byte[] served = provider.body(entry, "-");
    Map<String, Object> goldenTree = object(golden);
    byte[] goldenValue = CanonicalJson.toBytes(goldenTree.get("-"));

    // green on the real bytes
    CanonicalJson.assertBodyEqualsGolden(served, goldenValue);

    // red when the phases are reordered in the Java output
    Map<String, Object> reordered = object(served);
    @SuppressWarnings("unchecked")
    List<Object> phases = new ArrayList<>((List<Object>) reordered.get("phases"));
    java.util.Collections.swap(phases, 0, 1);
    reordered.put("phases", phases);
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(reordered), goldenValue)).isInstanceOf(AssertionError.class);

    // red when one byte of the golden is perturbed (an in-memory copy)
    byte[] perturbed = goldenValue.clone();
    int at = new String(perturbed, StandardCharsets.UTF_8).indexOf("\"phases\"");
    perturbed[at + 2] = (byte) (perturbed[at + 2] ^ 0x01);
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(served, perturbed)).isInstanceOf(AssertionError.class);
  }
}
