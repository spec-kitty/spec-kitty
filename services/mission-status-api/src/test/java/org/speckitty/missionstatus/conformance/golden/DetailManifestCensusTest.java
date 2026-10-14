package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.ClassEntry;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The paired Java census of the detail and artifact classes (D-109). The Python conformance test and this class pin the same Count column of
 * FR-014 as amended by plan section 14 ({@code DETAIL_CLASS_FLOORS} here, {@code CLASS_FLOORS} there; a Python test parses this map and
 * demands that the union with {@code GoldenSuiteTest.CLASS_FLOORS} equals the Python map). The census enumerates the manifest: the detail
 * classes it lists are the keys of the floors, each class meets its floor, and each fixture holds the goldens its parity demands. It compares
 * no golden with a route; no route exists at this tip, and the overview consumers keep seeing the overview surface only.
 */
class DetailManifestCensusTest {

  /** The per-class floors of the detail and artifact classes; a shrinking class fails here before it is missed. */
  private static final Map<String, Integer> DETAIL_CLASS_FLOORS =
      Map.ofEntries(
          Map.entry("detail-populated", 8), Map.entry("detail-early", 1), Map.entry("detail-planning-only", 1), Map.entry("phases-matrix", 19),
          Map.entry("wp-malformed-frontmatter", 28), Map.entry("wp-duplicate-id", 3), Map.entry("wp-two-selectors", 1), Map.entry("wp-prompt-bytes", 13),
          Map.entry("cycles", 4), Map.entry("legacy-lanes-json", 1), Map.entry("tasks-md", 12), Map.entry("worktree-states", 7),
          Map.entry("artifacts-populated", 1), Map.entry("artifacts-sort", 1), Map.entry("artifacts-refusals", 1), Map.entry("artifacts-links", 3),
          Map.entry("artifacts-redaction", 1), Map.entry("lookup-faults", 3), Map.entry("projection-nulls", 6), Map.entry("projection-refusals", 4),
          Map.entry("resolved-state", 21));

  /** The names a golden file of a detail class may have: one file per route, named after the operation. */
  private static final Set<String> ROUTE_GOLDENS =
      Set.of("get-mission.json", "get-work-package.json", "get-work-package-prompt.json", "get-work-package-detail.json", "list-artifacts.json", "get-artifact-content.json");

  /**
   * Retired divergence ids: reserved, never reused and never renumbered. V19 (a nullable head date that is not an instant) retired when main's oracle fix
   * (29d49cd77) began nulling an off-shape head date before it derives the lifecycle; {@code projection-nulls/head-dates-nulled} is now an ordinary conformance
   * case. V20 to V27 keep their numbers. V28 is the 10.5.1 approved-departure lift that Java does not port until spec-kitty#6268.
   */
  private static final Set<String> RETIRED_ENTRY_IDS = Set.of("V19");

  private static final Set<String> ENTRY_IDS = new TreeSet<>(Set.of("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V20", "V21", "V22", "V23", "V24", "V25", "V26", "V27", "V28"));

  /** The census over fixture names per tag: the tags equal the floors' keys and each class holds its floor. Empty when it holds. */
  static List<String> censusProblems(Map<String, List<String>> fixturesByTag, Map<String, Integer> floors) {
    List<String> problems = new ArrayList<>();
    if (!fixturesByTag.keySet().equals(floors.keySet())) {
      problems.add("the detail tags " + new TreeSet<>(fixturesByTag.keySet()) + " are not the floors' keys " + new TreeSet<>(floors.keySet()));
    }
    floors.forEach(
        (tag, floor) -> {
          int held = fixturesByTag.getOrDefault(tag, List.of()).size();
          if (held < floor) {
            problems.add("class " + tag + " holds " + held + " fixtures, the floor is " + floor);
          }
        });
    return problems;
  }

  private static Map<String, List<String>> fixturesByTag() {
    Map<String, List<String>> byTag = new LinkedHashMap<>();
    ConformanceTree.detailClasses().forEach(entry -> byTag.put(entry.tag(), entry.fixtures().stream().map(TreeFixture::name).toList()));
    return byTag;
  }

  @Test
  void theDetailTagsOfTheManifestAreTheKeysOfTheFloorsAndEveryClassMeetsItsFloor() {
    assertThat(censusProblems(fixturesByTag(), DETAIL_CLASS_FLOORS)).isEmpty();
    assertThat(ConformanceTree.detailClasses()).extracting(ClassEntry::tag).containsExactlyInAnyOrderElementsOf(DETAIL_CLASS_FLOORS.keySet());
    for (ClassEntry entry : ConformanceTree.detailClasses()) {
      assertThat(entry.fixtures()).as(entry.tag() + " is not empty").isNotEmpty();
      assertThat(entry.surface()).isEqualTo(ConformanceTree.SURFACE_DETAIL);
    }
  }

  @Test
  void aCopyWithOneFixtureOneClassOrOneFloorMissingIsRed() {
    Map<String, List<String>> held = fixturesByTag();
    assertThat(censusProblems(held, DETAIL_CLASS_FLOORS)).as("control: the real manifest holds").isEmpty();

    Map<String, List<String>> oneFixtureShort = new LinkedHashMap<>(held);
    oneFixtureShort.put("phases-matrix", held.get("phases-matrix").subList(1, held.get("phases-matrix").size()));
    assertThat(censusProblems(oneFixtureShort, DETAIL_CLASS_FLOORS)).anyMatch(problem -> problem.contains("phases-matrix holds 18"));

    Map<String, List<String>> oneClassShort = new LinkedHashMap<>(held);
    oneClassShort.remove("cycles");
    assertThat(censusProblems(oneClassShort, DETAIL_CLASS_FLOORS)).isNotEmpty();

    Map<String, Integer> oneFloorMissing = new LinkedHashMap<>(DETAIL_CLASS_FLOORS);
    oneFloorMissing.remove("tasks-md");
    assertThat(censusProblems(held, oneFloorMissing)).isNotEmpty();

    Map<String, Integer> oneFloorRaised = new LinkedHashMap<>(DETAIL_CLASS_FLOORS);
    oneFloorRaised.put("wp-malformed-frontmatter", 29);
    assertThat(censusProblems(held, oneFloorRaised)).anyMatch(problem -> problem.contains("wp-malformed-frontmatter holds 28"));
  }

  @Test
  void everyDetailFixtureHoldsTheGoldensItsParityDemands() throws IOException {
    for (ClassEntry entry : ConformanceTree.detailClasses()) {
      boolean goldenParity = entry.parity().equals(ConformanceTree.PARITY_GOLDEN);
      assertThat(entry.goldenFiles().isEmpty()).as(entry.tag() + " lists golden files exactly when it is a python-golden class").isEqualTo(!goldenParity);
      assertThat(ROUTE_GOLDENS).as(entry.tag() + " names route goldens only").containsAll(entry.goldenFiles());
      for (TreeFixture fixture : entry.fixtures()) {
        Path goldens = fixture.dir().resolve(ConformanceTree.GOLDEN_DIR);
        if (goldenParity) {
          Set<String> held;
          try (Stream<Path> files = Files.list(goldens)) {
            held = files.map(path -> path.getFileName().toString()).collect(Collectors.toCollection(TreeSet::new));
          }
          assertThat(held).as(fixture.key() + " holds the per-class golden files").isEqualTo(new TreeSet<>(entry.goldenFiles()));
          int keyed = 0;
          for (String file : entry.goldenFiles()) {
            Object document = CanonicalJson.parse(ConformanceTree.golden(fixture, file));
            assertThat(document).as(fixture.key() + " " + file + " is a keyed object").isInstanceOf(Map.class);
            keyed += ((Map<?, ?>) document).size();
          }
          assertThat(keyed).as(fixture.key() + " keys at least one request").isPositive();
          assertThat(fixture.javaOnly()).as(fixture.key() + " is compared").isFalse();
        } else {
          assertThat(goldens).as(fixture.key() + " is java-only and holds no golden").doesNotExist();
          assertThat(fixture.javaOnly()).as(fixture.key() + " is tagged javaOnly").isTrue();
        }
      }
    }
  }

  @Test
  void theOverviewSurfaceStaysWhatEveryExistingConsumerSaw() {
    Set<String> detailTags = DETAIL_CLASS_FLOORS.keySet();
    assertThat(ConformanceTree.classes()).extracting(ClassEntry::tag).doesNotContainAnyElementsOf(detailTags);
    assertThat(ConformanceTree.fixtures()).extracting(TreeFixture::tag).doesNotContainAnyElementsOf(detailTags);
    assertThat(ConformanceTree.classes()).allSatisfy(entry -> assertThat(entry.surface()).isEqualTo(ConformanceTree.SURFACE_OVERVIEW));
    assertThat(ConformanceTree.allClasses()).hasSize(ConformanceTree.classes().size() + ConformanceTree.detailClasses().size());
    assertThat(ConformanceTree.detailFixtures()).hasSize(ConformanceTree.detailClasses().stream().mapToInt(entry -> entry.fixtures().size()).sum());
    assertThat(ConformanceTree.fixturesOf("phases-matrix")).as("a detail tag has no overview fixtures").isEmpty();
  }

  @Test
  void theKnownDivergencesAreReadableAndEveryNamedFixtureIsInTheManifest() {
    List<Map<String, Object>> entries = ConformanceTree.knownDivergences();
    assertThat(entries.stream().map(entry -> entry.get("id").toString()).toList()).containsExactlyElementsOf(ENTRY_IDS.stream().sorted(DetailManifestCensusTest::byNumber).toList());
    assertThat(entries.stream().map(entry -> entry.get("id").toString()).toList()).as("a retired id stays absent").doesNotContainAnyElementsOf(RETIRED_ENTRY_IDS);
    assertThat(ENTRY_IDS).as("a retired id is not silently dropped from a range: it is named").doesNotContainAnyElementsOf(RETIRED_ENTRY_IDS);
    assertThat(ConformanceTree.allClasses().stream().flatMap(entry -> entry.fixtures().stream()).filter(fixture -> fixture.key().equals("projection-nulls/head-dates-nulled")).toList())
        .as("head-dates-nulled is an ordinary conformance case")
        .singleElement()
        .satisfies(fixture -> assertThat(fixture.knownDivergence()).isFalse());
    Set<String> keys = ConformanceTree.allClasses().stream().flatMap(entry -> entry.fixtures().stream()).map(TreeFixture::key).collect(Collectors.toSet());
    for (Map<String, Object> entry : entries) {
      assertThat(entry.get("oracleOutcome")).as(entry.get("id") + " has two different outcomes").isNotEqualTo(entry.get("javaAssertion"));
      @SuppressWarnings("unchecked")
      List<Object> fixtures = (List<Object>) entry.get("fixtures");
      fixtures.forEach(key -> assertThat(keys).as(entry.get("id") + " names " + key).contains(key.toString()));
    }
  }

  private static int byNumber(String left, String right) {
    return Integer.compare(Integer.parseInt(left.substring(1)), Integer.parseInt(right.substring(1)));
  }
}
