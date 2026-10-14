package org.speckitty.missionstatus.conformance.golden.served;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The provider of {@code getWorkPackage} is registered, owns exactly its row of the partition, serves every manifest fixture that holds one of
 * its two goldens (the named {@code knownDivergence} fixtures excepted, each pinned by a test of its own), and its bodies are what the
 * comparator needs: AC-2.1 (the with-prompt and without-prompt pair differs by exactly one member) and AC-14.2 (the comparator bites).
 * {@code ServedRoutes} loads providers by name and treats a missing class as an empty route, so a typo would leave
 * {@code DetailGoldenSuiteTest} green with zero comparisons: this test is what makes that impossible for this route (TASKS-GREEN-002).
 */
class WorkPackageServedRouteTest {

  /** The classes the review checklist names, with the number of fixtures of each that holds a {@code get-work-package.json} golden. */
  private static final Map<String, Integer> PER_CLASS = Map.of(
      "detail-populated", 8,
      "detail-planning-only", 1,
      "wp-malformed-frontmatter", 28,
      "wp-duplicate-id", 3,
      "wp-two-selectors", 1,
      "wp-prompt-bytes", 13,
      "resolved-state", 21,
      "projection-nulls", 6);

  private static ServedRoute provider() {
    return ServedRoutes.loaded().stream().filter(candidate -> candidate.getClass().getSimpleName().equals("WorkPackageServedRoute")).findFirst().orElseThrow(() -> new AssertionError("the registry did not load WorkPackageServedRoute"));
  }

  @Test
  void theRegistryLoadsTheProviderAndItsGoldenFilesAreItsRowOfThePartition() {
    ServedRoute provider = provider();

    assertThat(ServedRoutes.loadedProviderNames()).contains("WorkPackageServedRoute");
    Set<String> row = new TreeSet<>();
    ServedRoutes.OWNER.forEach((file, owner) -> {
      if (owner.equals("WorkPackageServedRoute")) {
        row.add(file);
      }
    });
    assertThat(new TreeSet<>(provider.goldenFiles())).isEqualTo(row).containsExactly("get-work-package-prompt.json", "get-work-package.json");
    assertThat(ServedRoutes.ownershipProblems(List.of(provider))).isEmpty();
  }

  @Test
  void servedIsTheManifestDerivedSetMinusTheNamedDivergentFixturesAndTheEmptyGoldens() {
    ServedRoute provider = provider();
    Set<Entry> expected = ServedRoutes.expectedEntries(provider.goldenFiles());

    assertThat(WorkPackageServedRoute.divergentEntries()).extracting(Entry::fixtureKey).containsExactlyInAnyOrderElementsOf(WorkPackageServedRoute.DIVERGENT);
    assertThat(provider.served()).doesNotContainAnyElementsOf(WorkPackageServedRoute.divergentEntries()).doesNotContainAnyElementsOf(WorkPackageServedRoute.emptyEntries());
    assertThat(WorkPackageServedRoute.emptyEntries()).as("an empty golden is a Work Package the oracle skipped").hasSize(17).allSatisfy(entry -> assertThat(entry.fixtureKey()).startsWith("wp-malformed-frontmatter/"));
    assertThat(provider.served().size() + WorkPackageServedRoute.divergentEntries().size() + WorkPackageServedRoute.emptyEntries().size()).isEqualTo(expected.size());
    assertThat(provider.served()).allSatisfy(entry -> assertThat(expected).contains(entry));
  }

  @Test
  void everyDivergentFixtureIsTaggedKnownDivergenceInTheManifest() {
    for (String key : WorkPackageServedRoute.DIVERGENT) {
      assertThat(WorkPackageServedRoute.fixture(key).knownDivergence()).as(key).isTrue();
    }
  }

  @Test
  void theServedSetMatchesTheClassEnumerationOfTheReviewChecklist() {
    Map<String, Integer> perClass = new TreeMap<>();
    for (Entry entry : provider().served()) {
      if (entry.goldenFile().equals(WorkPackageServedRoute.GOLDEN)) {
        perClass.merge(entry.fixtureKey().substring(0, entry.fixtureKey().indexOf('/')), 1, Integer::sum);
      }
    }

    PER_CLASS.forEach((tag, floor) -> {
      int divergent = (int) java.util.stream.Stream.concat(WorkPackageServedRoute.divergentEntries().stream(), WorkPackageServedRoute.emptyEntries().stream()).filter(entry -> entry.goldenFile().equals(WorkPackageServedRoute.GOLDEN) && entry.fixtureKey().startsWith(tag + "/")).count();
      assertThat(perClass.get(tag) + divergent).as(tag).isEqualTo(floor);
    });
    assertThat(perClass.get("wp-malformed-frontmatter")).as("28 goldens: 17 empty (the oracle skipped the file) and the SK-353 fixture (V20) left to their own tests").isEqualTo(10);
    assertThat(perClass.get("detail-planning-only")).isEqualTo(1);
    assertThat(perClass.get("resolved-state")).as("21 goldens, eight oracle-only outcomes (V21 to V25, V28) left to their own tests").isEqualTo(13);
    assertThat(provider().served().stream().map(Entry::fixtureKey)).contains("detail-populated/unicode-subtask-ids", "projection-nulls/merge-target-branch-path", "projection-nulls/override-partial-junk-at");
    assertThat(provider().served().stream().filter(entry -> entry.goldenFile().equals(WorkPackageServedRoute.PROMPT_GOLDEN)).map(entry -> entry.fixtureKey().substring(0, entry.fixtureKey().indexOf('/'))).distinct())
        .containsExactlyInAnyOrder("detail-populated", "wp-prompt-bytes");
  }

  @Test
  void theProviderAnswersTheWorkPackageIdsOfTheGoldenAndOnlyThose() {
    ServedRoute provider = provider();
    Entry entry = provider.served().stream().filter(candidate -> candidate.fixtureKey().equals("detail-populated/populated") && candidate.goldenFile().equals("get-work-package.json")).findFirst().orElseThrow();
    TreeFixture fixture = WorkPackageServedRoute.fixture(entry.fixtureKey());

    for (String key : WorkPackageServedRoute.requestKeys(fixture, entry.goldenFile())) {
      assertThat(key).matches("WP[0-9]{2,}");
      assertThat(provider.body(entry, key)).isNotNull();
    }
  }

  /** The harness compares the same pairs ({@code DetailGoldenSuiteTest}); this is the floor under it: a provider that served nothing would pass there. */
  @Test
  void everyServedPairIsComparedByteForByteWithItsGoldenAndTheNumberIsAFloor() {
    ServedRoute provider = provider();
    int compared = 0;
    for (Entry entry : provider.served()) {
      TreeFixture fixture = WorkPackageServedRoute.fixture(entry.fixtureKey());
      Map<String, Object> golden = object(ConformanceTree.golden(fixture, entry.goldenFile()));
      for (Map.Entry<String, Object> request : golden.entrySet()) {
        CanonicalJson.assertBodyEqualsGolden(provider.body(entry, request.getKey()), CanonicalJson.toBytes(request.getValue()));
        compared++;
      }
    }
    assertThat(compared).isGreaterThanOrEqualTo(90);
  }

  // ---- AC-2.1: the pair differs by exactly one member ----------------------------------------------------------------------------

  @SuppressWarnings("unchecked")
  private static Map<String, Object> object(byte[] body) {
    return (Map<String, Object>) CanonicalJson.parse(body);
  }

  @Test
  void theWithPromptGoldenIsTheWithoutPromptGoldenPlusExactlyOneMember() {
    int compared = 0;
    for (Entry entry : ServedRoutes.expectedEntries(Set.of(WorkPackageServedRoute.PROMPT_GOLDEN))) {
      TreeFixture fixture = WorkPackageServedRoute.fixture(entry.fixtureKey());
      Map<String, Object> plain = object(ConformanceTree.golden(fixture, WorkPackageServedRoute.GOLDEN));
      Map<String, Object> prompt = object(ConformanceTree.golden(fixture, WorkPackageServedRoute.PROMPT_GOLDEN));
      for (Map.Entry<String, Object> wp : prompt.entrySet()) {
        Map<String, Object> withPrompt = new LinkedHashMap<>(object(CanonicalJson.toBytes(wp.getValue())));
        Map<String, Object> without = object(CanonicalJson.toBytes(plain.get(wp.getKey())));
        assertThat(withPrompt.keySet()).as(entry.fixtureKey()).contains("promptMarkdown");
        assertThat(without.keySet()).as(entry.fixtureKey() + " has no promptMarkdown key at all").doesNotContain("promptMarkdown");
        withPrompt.remove("promptMarkdown");
        assertThat(CanonicalJson.toBytes(withPrompt)).as(entry.fixtureKey() + " " + wp.getKey()).isEqualTo(CanonicalJson.toBytes(without));
        compared++;
      }
    }
    assertThat(compared).isGreaterThanOrEqualTo(21);
  }

  @Test
  void theComparatorBitesOnThisRoutesBytes() {
    ServedRoute provider = provider();
    Entry entry = provider.served().stream().filter(candidate -> candidate.fixtureKey().equals("wp-prompt-bytes/crlf") && candidate.goldenFile().equals(WorkPackageServedRoute.PROMPT_GOLDEN)).findFirst().orElseThrow();
    TreeFixture fixture = WorkPackageServedRoute.fixture(entry.fixtureKey());
    String key = WorkPackageServedRoute.requestKeys(fixture, entry.goldenFile()).get(0);
    byte[] goldenValue = CanonicalJson.toBytes(object(ConformanceTree.golden(fixture, entry.goldenFile())).get(key));
    byte[] served = provider.body(entry, key);

    // green on the real bytes
    CanonicalJson.assertBodyEqualsGolden(served, goldenValue);

    // red when the prompt member is dropped from the Java answer
    Map<String, Object> dropped = object(served);
    dropped.remove("promptMarkdown");
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(CanonicalJson.toBytes(dropped), goldenValue)).isInstanceOf(AssertionError.class);

    // red when one byte of the golden is perturbed (an in-memory copy)
    byte[] perturbed = goldenValue.clone();
    int at = new String(perturbed, StandardCharsets.UTF_8).indexOf("\"promptMarkdown\"");
    perturbed[at + 2] = (byte) (perturbed[at + 2] ^ 0x01);
    assertThatThrownBy(() -> CanonicalJson.assertBodyEqualsGolden(served, perturbed)).isInstanceOf(AssertionError.class);
  }
}
