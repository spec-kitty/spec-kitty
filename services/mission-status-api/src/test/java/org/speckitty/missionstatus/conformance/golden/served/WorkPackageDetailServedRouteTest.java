package org.speckitty.missionstatus.conformance.golden.served;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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

/**
 * The provider of {@code getWorkPackageDetail} is registered, owns exactly its row of the partition, serves every manifest fixture that holds
 * the golden (the {@code knownDivergence} fixtures excepted, which are named and pinned), and its answers are what the comparator needs (AC-3.1,
 * AC-14.2). {@code ServedRoutes} loads providers by name and treats a missing class as an empty route, so a typo would leave
 * {@code DetailGoldenSuiteTest} green with zero comparisons: this test is what makes that impossible for this route.
 */
class WorkPackageDetailServedRouteTest {

  /** The fixtures whose golden is the oracle's outcome and whose Java outcome differs on purpose (V7, V19, V20). */
  private static final Set<String> DIVERGENT =
      Set.of("worktree-states/directory-symlink", "worktree-states/git-entry-symlink", "projection-nulls/head-dates-nulled", "wp-malformed-frontmatter/wpm-28");

  /** The classes the review checklist names, with the number of fixtures of each that holds a detail golden. */
  private static final Map<String, Integer> PER_CLASS =
      Map.of(
          "worktree-states", 7,
          "cycles", 4,
          "tasks-md", 12,
          "legacy-lanes-json", 1,
          "detail-populated", 8,
          "wp-duplicate-id", 3,
          "wp-malformed-frontmatter", 28,
          "wp-two-selectors", 1,
          "projection-nulls", 6);

  private static ServedRoute provider() {
    return ServedRoutes.loaded().stream().filter(candidate -> candidate.getClass().getSimpleName().equals("WorkPackageDetailServedRoute")).findFirst().orElseThrow(() -> new AssertionError("the registry did not load WorkPackageDetailServedRoute"));
  }

  @Test
  void theRegistryLoadsTheProviderAndItsGoldenFilesAreItsRowOfThePartition() {
    ServedRoute provider = provider();

    assertThat(ServedRoutes.loadedProviderNames()).contains("WorkPackageDetailServedRoute");
    Set<String> row = new java.util.TreeSet<>();
    ServedRoutes.OWNER.forEach((file, owner) -> {
      if (owner.equals("WorkPackageDetailServedRoute")) {
        row.add(file);
      }
    });
    assertThat(provider.goldenFiles()).isEqualTo(row).containsExactly("get-work-package-detail.json");
    assertThat(ServedRoutes.ownershipProblems(java.util.List.of(provider))).isEmpty();
  }

  @Test
  void servedIsTheManifestDerivedSetMinusTheNamedDivergentFixtures() {
    ServedRoute provider = provider();
    Set<Entry> expected = ServedRoutes.expectedEntries(provider.goldenFiles());

    assertThat(WorkPackageDetailServedRoute.divergentEntries()).extracting(Entry::fixtureKey).containsExactlyInAnyOrderElementsOf(DIVERGENT);
    assertThat(provider.served()).doesNotContainAnyElementsOf(WorkPackageDetailServedRoute.divergentEntries());
    assertThat(provider.served().size() + WorkPackageDetailServedRoute.divergentEntries().size()).isEqualTo(expected.size());
    assertThat(provider.served()).allSatisfy(entry -> assertThat(expected).contains(entry));
    assertThat(expected).hasSize(70);
  }

  @Test
  void theServedSetMatchesTheClassEnumerationOfTheReviewChecklist() {
    Map<String, Integer> perClass = new TreeMap<>();
    for (Entry entry : ServedRoutes.expectedEntries(provider().goldenFiles())) {
      perClass.merge(entry.fixtureKey().substring(0, entry.fixtureKey().indexOf('/')), 1, Integer::sum);
    }

    assertThat(perClass).containsExactlyInAnyOrderEntriesOf(PER_CLASS);
    Map<String, Integer> served = new TreeMap<>();
    for (Entry entry : provider().served()) {
      served.merge(entry.fixtureKey().substring(0, entry.fixtureKey().indexOf('/')), 1, Integer::sum);
    }
    assertThat(served.get("worktree-states")).as("seven fixtures, the two symbolic-link rows left to their own test").isEqualTo(5);
    assertThat(served.get("wp-malformed-frontmatter")).as("28 fixtures, the SK-353 fixture left to its own test").isEqualTo(27);
    assertThat(served.get("projection-nulls")).isEqualTo(5);
  }

  @Test
  void theProviderAnswersOnlyTheRequestKeysOfTheGolden() {
    ServedRoute provider = provider();
    Entry entry = provider.served().stream().filter(candidate -> candidate.fixtureKey().equals("detail-populated/populated")).findFirst().orElseThrow();

    assertThat(provider.body(entry, "-")).isNull();
    assertThat(provider.body(entry, "WP01")).isNotNull();
    assertThat(provider.body(entry, "WP99")).isNotNull();
  }

  @Test
  void reorderingAMemberOrPerturbingOneGoldenByteTurnsTheComparisonRed() {
    ServedRoute provider = provider();
    Entry entry = provider.served().stream().filter(candidate -> candidate.fixtureKey().equals("detail-populated/populated")).findFirst().orElseThrow();
    TreeFixture fixture = WorkPackageDetailServedRoute.fixture(entry.fixtureKey());
    @SuppressWarnings("unchecked")
    Map<String, Object> goldenTree = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, entry.goldenFile()));
    byte[] goldenValue = CanonicalJson.toBytes(goldenTree.get("WP01"));
    byte[] served = provider.body(entry, "WP01");

    // green on the real bytes
    CanonicalJson.assertBodyEqualsGolden(served, goldenValue);

    // red when the golden differs by one byte (an in-memory copy)
    byte[] perturbed = goldenValue.clone();
    int at = new String(perturbed, java.nio.charset.StandardCharsets.UTF_8).indexOf("\"subtasks\"");
    perturbed[at + 2] = (byte) (perturbed[at + 2] ^ 0x01);
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(served, perturbed)).isInstanceOf(AssertionError.class);

    // red when the served worktree flag is the opposite of the golden's (the oracle's answer is a stat of the host)
    String flipped = new String(served, java.nio.charset.StandardCharsets.UTF_8).replace("\"worktreePresent\":false", "\"worktreePresent\":true");
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(flipped.getBytes(java.nio.charset.StandardCharsets.UTF_8), goldenValue)).isInstanceOf(AssertionError.class);
  }

  @Test
  void theMissionIdComesFromTheGoldenOrFromTheMetaOfAFixtureWhoseEveryGoldenIsARefusal() {
    assertThat(WorkPackageDetailServedRoute.missionIdOf(WorkPackageDetailServedRoute.fixture("detail-populated/populated"))).isEqualTo("00000000000000000000000001");
    assertThat(WorkPackageDetailServedRoute.missionIdOf(WorkPackageDetailServedRoute.fixture("legacy-lanes-json/legacy-lanes-json"))).isEqualTo("00000000000000000000000001");
  }
}
