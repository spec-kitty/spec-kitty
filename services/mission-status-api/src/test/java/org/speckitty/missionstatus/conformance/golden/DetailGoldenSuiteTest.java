package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.BiFunction;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.CaseSensitiveHost;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;

/**
 * The Java comparison of served bytes with the committed detail goldens (FR-014 Java half, AC-14.1). A detail class is compared only for
 * the pairs a route phase registered in its {@link ServedRoute} provider (D-109); with no provider at this tip nothing is compared and
 * nothing is red. The non-vacuity of the comparison is a planted self-test provider that serves one real fixture: green on the
 * unperturbed golden bytes, red on one perturbed byte (the perturbation is made on an in-memory copy; the committed file is never
 * touched), red for a key it cannot answer, for an empty golden and for an absent golden.
 *
 * <p>The providers are named by string only ({@link ServedRoutes}); a test that names a later route type would break the tip it
 * stands on. The permanent assertions here are true at every tip: the default registry's loaded names are a subset of the four known
 * names, never "empty" and never "contains X".
 */
class DetailGoldenSuiteTest {

  /** Reads the golden bytes of an entry; the real one reads the committed tree. */
  private interface GoldenSource extends BiFunction<TreeFixture, String, byte[]> {}

  private static final GoldenSource COMMITTED = ConformanceTree::golden;

  private static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow(() -> new AssertionError("no detail fixture " + key));
  }

  /** The comparison: every pair of the provider, every request key of its golden, raw bytes against the canonical bytes of the golden's value. */
  @SuppressWarnings("unchecked")
  static int compare(ServedRoute provider, GoldenSource goldens) {
    int compared = 0;
    for (Entry entry : provider.served()) {
      if (!CaseSensitiveHost.comparable(entry.fixtureKey())) {
        continue;
      }
      TreeFixture fixture = fixture(entry.fixtureKey());
      byte[] golden = goldens.apply(fixture, entry.goldenFile());
      if (golden == null) {
        throw new AssertionError(entry + ": the manifest says the golden is absent");
      }
      Object parsed = CanonicalJson.parse(golden);
      if (!(parsed instanceof Map<?, ?> byKey) || byKey.isEmpty()) {
        throw new AssertionError(entry + ": the golden holds no request key");
      }
      for (Map.Entry<String, Object> request : ((Map<String, Object>) byKey).entrySet()) {
        byte[] served = provider.body(entry, request.getKey());
        if (served == null) {
          throw new AssertionError(entry + " " + request.getKey() + ": the provider cannot answer this request key");
        }
        CanonicalJson.assertBodyEqualsGolden(served, CanonicalJson.toBytes(request.getValue()));
        compared++;
      }
    }
    return compared;
  }

  /** The planted provider: it serves one real pair and answers every key from {@code answers}. */
  private static ServedRoute planted(Entry entry, Function<String, byte[]> answers) {
    return new ServedRoute() {
      @Override
      public Set<String> goldenFiles() {
        return Set.of(entry.goldenFile());
      }

      @Override
      public Set<Entry> served() {
        return Set.of(entry);
      }

      @Override
      public byte[] body(Entry asked, String requestKey) {
        return answers.apply(requestKey);
      }
    };
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> goldenOf(Entry entry) {
    return (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture(entry.fixtureKey()), entry.goldenFile()));
  }

  /** The first fixture of the manifest that holds a golden of this name. */
  private static Entry firstEntryWith(String goldenFile) {
    return ServedRoutes.expectedEntries(Set.of(goldenFile)).iterator().next();
  }

  // ---- the registered providers ----------------------------------------------------------------------------------------------

  @Test
  void everyProviderTheDefaultRegistryLoadsMatchesItsGoldensAndNothingIsComparedForAFixtureNoOneServes() {
    int compared = 0;
    for (ServedRoute provider : ServedRoutes.loaded()) {
      compared += compare(provider, COMMITTED);
    }

    // at a tip with no provider this is zero and green; each route phase's own tests pin that its provider was found
    assertThat(compared).isGreaterThanOrEqualTo(0);
    assertThat(ServedRoutes.loadedProviderNames()).isSubsetOf(ServedRoutes.PROVIDER_NAMES);
    assertThat(ServedRoutes.PROVIDER_NAMES).containsExactlyInAnyOrder("MissionDetailServedRoute", "WorkPackageServedRoute", "WorkPackageDetailServedRoute", "ArtifactServedRoute");
  }

  @Test
  void anInjectedRegistryReportsExactlyThePlantedProvider() {
    Entry entry = firstEntryWith("get-mission.json");
    ServedRoute provider = planted(entry, key -> CanonicalJson.toBytes(goldenOf(entry).get(key)));

    ServedRoutes injected = ServedRoutes.of(List.of(provider));

    assertThat(injected.providers()).containsExactly(provider);
    assertThat(injected.providerNames()).hasSize(1);
    // the default registry is another object: planting one provider moved nothing there
    assertThat(ServedRoutes.loadedProviderNames()).doesNotContainAnyElementsOf(injected.providerNames());
  }

  // ---- AC-14.1 (i) to (iii): the comparison is not vacuous ---------------------------------------------------------------------

  @Test
  void aPlantedProviderServingTheUnperturbedGoldenBytesIsGreen() {
    Entry entry = firstEntryWith("get-mission.json");
    ServedRoute provider = planted(entry, key -> CanonicalJson.toBytes(goldenOf(entry).get(key)));

    assertThat(compare(provider, COMMITTED)).isEqualTo(goldenOf(entry).size()).isPositive();
  }

  @Test
  void theSameProviderIsRedWhenOneByteOfTheGoldenIsPerturbedInACopy() {
    Entry entry = firstEntryWith("get-mission.json");
    byte[] committed = ConformanceTree.golden(fixture(entry.fixtureKey()), entry.goldenFile());
    ServedRoute provider = planted(entry, key -> CanonicalJson.toBytes(goldenOf(entry).get(key)));
    byte[] perturbed = committed.clone();
    int at = new String(committed, java.nio.charset.StandardCharsets.UTF_8).indexOf("\"mission");
    perturbed[at + 1] = (byte) (perturbed[at + 1] ^ 0x01);
    GoldenSource copy = (fixture, file) -> perturbed;

    assertThatThrownBy(() -> compare(provider, copy)).isInstanceOf(AssertionError.class);
    // the committed bytes were not touched
    assertThat(ConformanceTree.golden(fixture(entry.fixtureKey()), entry.goldenFile())).isEqualTo(committed);
  }

  @Test
  void aProviderThatServesOneByteOffIsRed() {
    Entry entry = firstEntryWith("get-mission.json");
    ServedRoute provider =
        planted(
            entry,
            key -> {
              byte[] body = CanonicalJson.toBytes(goldenOf(entry).get(key));
              body[body.length - 2] = (byte) (body[body.length - 2] ^ 0x01);
              return body;
            });

    assertThatThrownBy(() -> compare(provider, COMMITTED)).isInstanceOf(AssertionError.class);
  }

  @Test
  void aProviderThatCannotAnswerAKeyIsRed() {
    Entry entry = firstEntryWith("get-mission.json");

    assertThatThrownBy(() -> compare(planted(entry, key -> null), COMMITTED)).isInstanceOf(AssertionError.class).hasMessageContaining("cannot answer");
  }

  @Test
  void anEmptyGoldenAndAnAbsentGoldenAreRed() {
    Entry entry = firstEntryWith("get-mission.json");
    ServedRoute provider = planted(entry, key -> new byte[0]);

    assertThatThrownBy(() -> compare(provider, (fixture, file) -> "{}\n".getBytes(java.nio.charset.StandardCharsets.UTF_8))).hasMessageContaining("no request key");
    assertThatThrownBy(() -> compare(provider, (fixture, file) -> null)).hasMessageContaining("absent");
    assertThatThrownBy(() -> compare(planted(new Entry("no-such-class/no-such-fixture", "get-mission.json"), key -> new byte[0]), COMMITTED)).isInstanceOf(AssertionError.class);
  }

  @Test
  void aPlantedProviderServingOnePairLeavesEveryOtherFixtureUncompared() {
    Entry entry = firstEntryWith("get-mission.json");
    ServedRoute provider = planted(entry, key -> CanonicalJson.toBytes(goldenOf(entry).get(key)));

    // another pair with a different golden would be red if it were compared: only the served pair is
    assertThat(ServedRoutes.expectedEntries(Set.of("get-mission.json")).size()).isGreaterThan(1);
    assertThat(compare(provider, COMMITTED)).isEqualTo(goldenOf(entry).size());
  }

  @Test
  void theCanonicalWriterReproducesEveryCommittedDetailGoldenByteForByte() {
    int checked = 0;
    for (TreeFixture fixture : ConformanceTree.detailFixtures()) {
      for (String file : ServedRoutes.GOLDEN_FILES) {
        byte[] golden = ConformanceTree.golden(fixture, file);
        if (golden != null) {
          assertThat(CanonicalJson.toBytes(CanonicalJson.parse(golden))).as(fixture.key() + " " + file).isEqualTo(golden);
          checked++;
        }
      }
    }
    assertThat(checked).isGreaterThan(100);
  }

  // ---- the ownership rule ----------------------------------------------------------------------------------------------------

  /** A test-local provider; the rule reads the simple class name, so the four subclasses are named like the real providers. */
  private abstract static class Fake implements ServedRoute {
    private final Set<String> files;
    private final Set<Entry> entries;

    Fake(Set<String> files, Set<Entry> entries) {
      this.files = files;
      this.entries = entries;
    }

    @Override
    public Set<String> goldenFiles() {
      return files;
    }

    @Override
    public Set<Entry> served() {
      return entries;
    }

    @Override
    public byte[] body(Entry entry, String requestKey) {
      return new byte[0];
    }
  }

  private static final class MissionDetailServedRoute extends Fake {
    MissionDetailServedRoute(Set<String> files, Set<Entry> entries) {
      super(files, entries);
    }
  }

  private static final class WorkPackageServedRoute extends Fake {
    WorkPackageServedRoute(Set<Entry> entries) {
      super(Set.of("get-work-package.json", "get-work-package-prompt.json"), entries);
    }
  }

  private static final class WorkPackageDetailServedRoute extends Fake {
    WorkPackageDetailServedRoute(Set<Entry> entries) {
      super(Set.of("get-work-package-detail.json"), entries);
    }
  }

  private static final class ArtifactServedRoute extends Fake {
    ArtifactServedRoute(Set<Entry> entries) {
      super(Set.of("list-artifacts.json", "get-artifact-content.json"), entries);
    }
  }

  @Test
  void theOwnershipRuleHasTheSixGoldenFilesPartitionedOverFourProviders() {
    assertThat(ServedRoutes.OWNER).containsOnlyKeys("get-mission.json", "get-work-package.json", "get-work-package-prompt.json", "get-work-package-detail.json", "list-artifacts.json", "get-artifact-content.json");
    assertThat(ServedRoutes.OWNER.get("get-work-package.json")).isEqualTo(ServedRoutes.OWNER.get("get-work-package-prompt.json"));
    assertThat(ServedRoutes.OWNER.get("list-artifacts.json")).isEqualTo(ServedRoutes.OWNER.get("get-artifact-content.json"));
    assertThat(ServedRoutes.OWNER.values().stream().distinct().count()).isEqualTo(4);
  }

  @Test
  void expectedEntriesAreTheManifestsPairsAndNotAHardCodedList() {
    Set<Entry> all = ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES);
    Set<Entry> viaFixtures = new java.util.LinkedHashSet<>();
    for (TreeFixture fixture : ConformanceTree.detailFixtures()) {
      for (String file : ServedRoutes.GOLDEN_FILES) {
        if (ConformanceTree.golden(fixture, file) != null) {
          viaFixtures.add(new Entry(fixture.key(), file));
        }
      }
    }

    assertThat(all).isEqualTo(viaFixtures).hasSizeGreaterThan(100);
    assertThat(ServedRoutes.expectedEntries(Set.of())).isEmpty();
    assertThat(ServedRoutes.expectedEntries(Set.of("get-mission.json"))).allMatch(entry -> entry.goldenFile().equals("get-mission.json"));
  }

  @Test
  void aDoublyClaimedPairIsReported() {
    Entry pair = firstEntryWith("get-mission.json");
    ServedRoute first = new MissionDetailServedRoute(Set.of("get-mission.json"), Set.of(pair));
    ServedRoute second = new MissionDetailServedRoute(Set.of("get-mission.json"), Set.of(pair));

    assertThat(ServedRoutes.ownershipProblems(List.of(first, second))).anyMatch(problem -> problem.contains("is served by both"));
    assertThat(ServedRoutes.ownershipProblems(List.of(first))).isEmpty();
  }

  @Test
  void aPairOutsideTheProvidersRowAndAGoldenFileLeavingItsRowAreReported() {
    Entry foreign = firstEntryWith("get-work-package.json");
    ServedRoute stray = new MissionDetailServedRoute(Set.of("get-mission.json"), Set.of(foreign));
    ServedRoute widened = new MissionDetailServedRoute(Set.of("get-mission.json", "get-work-package.json"), Set.of());
    ServedRoute narrowed = new WorkPackageServedRoute(Set.of());
    ServedRoute narrowedFiles =
        new ServedRoute() {
          @Override
          public Set<String> goldenFiles() {
            return Set.of("get-work-package.json");
          }

          @Override
          public Set<Entry> served() {
            return Set.of();
          }

          @Override
          public byte[] body(Entry entry, String requestKey) {
            return new byte[0];
          }
        };

    assertThat(ServedRoutes.ownershipProblems(List.of(stray))).anyMatch(problem -> problem.contains("outside its row"));
    assertThat(ServedRoutes.ownershipProblems(List.of(widened))).anyMatch(problem -> problem.contains("but its row of the partition is"));
    assertThat(ServedRoutes.ownershipProblems(List.of(narrowed))).isEmpty();
    // a provider with a name that is no row owns nothing, so any golden file it claims is outside the partition
    assertThat(ServedRoutes.ownershipProblems(List.of(narrowedFiles))).anyMatch(problem -> problem.contains("but its row of the partition is"));
  }

  @Test
  void anOmittedPairIsReportedOnlyOnceAllSixGoldenFilesAreOwned() {
    List<ServedRoute> partial = List.of(new MissionDetailServedRoute(Set.of("get-mission.json"), Set.of()));
    List<ServedRoute> everyFile =
        List.of(
            new MissionDetailServedRoute(Set.of("get-mission.json"), Set.of()),
            new WorkPackageServedRoute(Set.of()),
            new WorkPackageDetailServedRoute(Set.of()),
            new ArtifactServedRoute(Set.of()));

    // without all six owned, completeness is not judged (a tip where later providers do not exist yet)
    assertThat(ServedRoutes.ownershipProblems(partial)).isEmpty();
    List<String> problems = ServedRoutes.ownershipProblems(everyFile);
    assertThat(problems).isNotEmpty().allMatch(problem -> problem.endsWith("is served by no provider"));
    assertThat(problems).hasSize(ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES).size());
  }

  @Test
  void aCompletePartitionServingEveryExpectedPairHasNoProblem() {
    Map<String, Set<Entry>> byOwner = new LinkedHashMap<>();
    for (Entry entry : ServedRoutes.expectedEntries(ServedRoutes.GOLDEN_FILES)) {
      byOwner.computeIfAbsent(ServedRoutes.OWNER.get(entry.goldenFile()), name -> new java.util.LinkedHashSet<>()).add(entry);
    }
    List<ServedRoute> providers =
        List.of(
            new MissionDetailServedRoute(Set.of("get-mission.json"), byOwner.get("MissionDetailServedRoute")),
            new WorkPackageServedRoute(byOwner.get("WorkPackageServedRoute")),
            new WorkPackageDetailServedRoute(byOwner.get("WorkPackageDetailServedRoute")),
            new ArtifactServedRoute(byOwner.get("ArtifactServedRoute")));

    assertThat(ServedRoutes.ownershipProblems(providers)).isEmpty();
  }
}
