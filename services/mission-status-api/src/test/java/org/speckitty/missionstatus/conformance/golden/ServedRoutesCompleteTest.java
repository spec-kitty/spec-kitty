package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The whole-set floor of the detail golden harness (D-109, TASKS-FRESH3-002/003): every (fixture, golden file) pair of the manifest is served
 * by exactly one {@link ServedRoute} provider, except the pairs a provider leaves to its route's own tests. Two kinds are left out, and both are
 * derived here from the manifest, never listed (obligations 13 and 17):
 *
 * <ul>
 *   <li>the fixtures tagged {@code knownDivergence}: their golden is the oracle's outcome and the Java outcome differs on purpose, each with its
 *       own Java-outcome test (V1, V19, V20 and the {@code resolved-state} V21 to V25 on the routes that serve them);
 *   <li>the pairs whose golden holds no request key ({@code {}}), e.g. the 17 {@code wp-malformed-frontmatter} Work Package files the oracle's
 *       index skipped: {@code DetailGoldenSuiteTest} refuses an empty golden, so no provider can serve one.
 * </ul>
 *
 * A fixture of a Java-only class has no golden and is exempt by construction (it never enters {@link ServedRoutes#expectedEntries}); there is no
 * exemption list by class name.
 */
class ServedRoutesCompleteTest {

  /** The floor on the manifest-derived pairs (D-109): a manifest that shrinks, or a glob that matches nothing, is red. */
  static final int PAIR_FLOOR = 243;

  private static Map<String, TreeFixture> fixtures() {
    Map<String, TreeFixture> byKey = new java.util.LinkedHashMap<>();
    ConformanceTree.detailFixtures().forEach(fixture -> byKey.put(fixture.key(), fixture));
    return byKey;
  }

  /** The pairs of the manifest whose fixture is tagged {@code knownDivergence}. */
  static Set<Entry> taggedPairs() {
    Map<String, TreeFixture> fixtures = fixtures();
    Set<Entry> tagged = new LinkedHashSet<>();
    for (Entry entry : ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES)) {
      if (fixtures.get(entry.fixtureKey()).knownDivergence()) {
        tagged.add(entry);
      }
    }
    return tagged;
  }

  /** The pairs of the manifest whose golden is an empty object. */
  @SuppressWarnings("unchecked")
  static Set<Entry> emptyGoldenPairs() {
    Map<String, TreeFixture> fixtures = fixtures();
    Set<Entry> empty = new LinkedHashSet<>();
    for (Entry entry : ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES)) {
      Object golden = CanonicalJson.parse(ConformanceTree.golden(fixtures.get(entry.fixtureKey()), entry.goldenFile()));
      if (golden instanceof Map<?, ?> members && members.isEmpty()) {
        empty.add(entry);
      }
    }
    return empty;
  }

  /** What a provider may leave out: the tagged pairs and the empty-golden pairs. */
  static Set<Entry> exempt() {
    Set<Entry> exempt = new LinkedHashSet<>(taggedPairs());
    exempt.addAll(emptyGoldenPairs());
    return exempt;
  }

  /** The completeness problems of these providers: the four must be loaded, and the ownership partition must hold once the exempt pairs are subtracted. */
  static List<String> problems(List<ServedRoute> providers) {
    List<String> problems = new ArrayList<>();
    Set<String> names = new TreeSet<>();
    providers.forEach(provider -> names.add(provider.getClass().getSimpleName()));
    if (!names.equals(new TreeSet<>(ServedRoutes.PROVIDER_NAMES))) {
      problems.add("providers loaded " + names + " but the four are " + new TreeSet<>(ServedRoutes.PROVIDER_NAMES));
    }
    Set<String> allowedGaps = new LinkedHashSet<>();
    exempt().forEach(entry -> allowedGaps.add(entry + " is served by no provider"));
    ServedRoutes.ownershipProblems(providers).stream().filter(problem -> !allowedGaps.contains(problem)).forEach(problems::add);
    return problems;
  }

  @Test
  void allFourProvidersAreLoadedAndEveryPairOfTheManifestIsServedOnceOrExempt() {
    assertThat(ServedRoutes.loadedProviderNames()).containsExactlyInAnyOrderElementsOf(ServedRoutes.PROVIDER_NAMES);
    assertThat(problems(ServedRoutes.loaded())).isEmpty();
  }

  @Test
  void theManifestPairCountHoldsItsFloor() {
    assertThat(ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES)).hasSizeGreaterThanOrEqualTo(PAIR_FLOOR);
  }

  @Test
  void theUnservedPairsAreExactlyPairsTheManifestExemptsAndNoneOutsideThem() {
    Set<Entry> served = new LinkedHashSet<>();
    ServedRoutes.loaded().forEach(provider -> served.addAll(provider.served()));
    Set<Entry> unserved = new LinkedHashSet<>(ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES));
    unserved.removeAll(served);

    assertThat(exempt()).containsAll(unserved);
    assertThat(unserved).as("the exemptions are real: some pair is left to its route's own tests").isNotEmpty();
  }

  @Test
  void theSixKnownDivergenceFixturesOfGetMissionAreExemptedFromTheManifestTags() {
    Set<String> keys = new TreeSet<>();
    taggedPairs().stream().filter(entry -> entry.goldenFile().equals("get-mission.json")).forEach(entry -> keys.add(entry.fixtureKey()));

    assertThat(keys).hasSizeGreaterThanOrEqualTo(6);
    assertThat(keys).as("V1, V19 and V20 are tagged").anyMatch(key -> key.endsWith("head-dates-nulled")).anyMatch(key -> key.endsWith("wpm-28"));
    assertThat(keys.stream().filter(key -> key.contains("ps-link-")).count()).isEqualTo(4);
  }

  @Test
  void theSeventeenEmptyGoldensOfWpMalformedFrontmatterAreExemptedFromTheGoldenBytes() {
    Set<String> keys = new TreeSet<>();
    emptyGoldenPairs().stream().filter(entry -> entry.fixtureKey().startsWith("wp-malformed-frontmatter/")).filter(entry -> entry.goldenFile().equals("get-work-package.json")).forEach(entry -> keys.add(entry.fixtureKey()));

    assertThat(keys).hasSize(17);
  }

  @Test
  void everyProviderOwnsOnlyPairsOutsideTheExemptionsItDoesNotServeAndTheDivergentListsAreTagged() {
    Map<String, TreeFixture> fixtures = fixtures();
    for (String key : org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute.DIVERGENT) {
      assertThat(fixtures.get(key).knownDivergence()).as(key + " is tagged knownDivergence").isTrue();
    }
    assertThat(org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute.DIVERGENT).hasSize(9);
    assertThat(taggedPairs()).containsAll(org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute.divergentEntries());
    assertThat(taggedPairs()).containsAll(org.speckitty.missionstatus.conformance.golden.served.WorkPackageDetailServedRoute.divergentEntries());
    assertThat(taggedPairs()).containsAll(org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute.divergentEntries());
    assertThat(emptyGoldenPairs()).containsAll(org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute.emptyEntries());
  }

  @Test
  void aFixtureOfAJavaOnlyClassHasNoGoldenAndIsNotRequired() {
    Set<String> required = new TreeSet<>();
    ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES).forEach(entry -> required.add(entry.fixtureKey()));
    List<TreeFixture> goldenLess = new ArrayList<>();
    for (TreeFixture fixture : ConformanceTree.detailFixtures()) {
      boolean hasGolden = ServedRoutes.GOLDEN_FILES.stream().anyMatch(file -> ConformanceTree.golden(fixture, file) != null);
      if (!hasGolden) {
        goldenLess.add(fixture);
      }
    }

    assertThat(goldenLess).as("the Java-only classes artifacts-links, lookup-faults and projection-refusals").isNotEmpty();
    assertThat(goldenLess).allMatch(TreeFixture::javaOnly);
    goldenLess.forEach(fixture -> assertThat(required).doesNotContain(fixture.key()));
  }

  // ---- controls --------------------------------------------------------------------------------------------------------------

  /**
   * A stand-in that answers to the simple name of the provider it replaces (the ownership function reads {@code getClass().getSimpleName()})
   * and serves everything that provider does except one pair.
   */
  static final class MissionDetailServedRoute extends Dropping {
    MissionDetailServedRoute(ServedRoute original, Entry dropped) {
      super(original, dropped);
    }
  }

  /** The stand-in for {@code WorkPackageServedRoute}. */
  static final class WorkPackageServedRoute extends Dropping {
    WorkPackageServedRoute(ServedRoute original, Entry dropped) {
      super(original, dropped);
    }
  }

  abstract static class Dropping implements ServedRoute {
    private final ServedRoute original;
    private final Entry dropped;

    Dropping(ServedRoute original, Entry dropped) {
      this.original = original;
      this.dropped = dropped;
    }

    @Override
    public Set<String> goldenFiles() {
      return original.goldenFiles();
    }

    @Override
    public Set<Entry> served() {
      Set<Entry> served = new LinkedHashSet<>(original.served());
      served.remove(dropped);
      return served;
    }

    @Override
    public byte[] body(Entry entry, String requestKey) {
      return original.body(entry, requestKey);
    }
  }

  private static ServedRoute provider(List<ServedRoute> providers, String simpleName) {
    return providers.stream().filter(candidate -> candidate.getClass().getSimpleName().equals(simpleName)).findFirst().orElseThrow();
  }

  private static List<ServedRoute> replacing(List<ServedRoute> providers, ServedRoute original, ServedRoute stand) {
    List<ServedRoute> replaced = new ArrayList<>(providers);
    replaced.remove(original);
    replaced.add(stand);
    return replaced;
  }

  @Test
  void controlAPairNoProviderServesAndTheManifestDoesNotExemptIsRed() {
    List<ServedRoute> providers = ServedRoutes.loaded();
    ServedRoute original = provider(providers, "MissionDetailServedRoute");
    Entry dropped = original.served().iterator().next();
    assertThat(exempt()).doesNotContain(dropped);

    List<String> problems = problems(replacing(providers, original, new MissionDetailServedRoute(original, dropped)));

    assertThat(problems).containsExactly(dropped + " is served by no provider");
  }

  @Test
  void controlTheSecondGoldenFileOfAFixtureThatNoProviderClaimsIsRed() {
    List<ServedRoute> providers = ServedRoutes.loaded();
    ServedRoute original = provider(providers, "WorkPackageServedRoute");
    Entry dropped = original.served().stream().filter(entry -> entry.goldenFile().equals("get-work-package-prompt.json")).findFirst().orElseThrow();
    assertThat(exempt()).doesNotContain(dropped);

    List<String> problems = problems(replacing(providers, original, new WorkPackageServedRoute(original, dropped)));

    assertThat(problems).containsExactly(dropped + " is served by no provider");
  }

  @Test
  void controlAProviderThatIsNotLoadedIsRed() {
    List<ServedRoute> three = new ArrayList<>(ServedRoutes.loaded());
    three.removeIf(candidate -> candidate.getClass().getSimpleName().equals("ArtifactServedRoute"));

    assertThat(problems(three)).anyMatch(problem -> problem.startsWith("providers loaded"));
  }

  @Test
  void controlWithoutTheSubtractionTheRegistryIsRed() {
    assertThat(ServedRoutes.ownershipProblems(ServedRoutes.loaded())).as("the exemptions are what makes the complete registry green").isNotEmpty();
    assertThat(problems(ServedRoutes.loaded())).isEmpty();
  }
}
