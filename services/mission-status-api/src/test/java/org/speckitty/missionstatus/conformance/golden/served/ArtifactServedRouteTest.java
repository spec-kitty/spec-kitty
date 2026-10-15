package org.speckitty.missionstatus.conformance.golden.served;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoute.Entry;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.CaseSensitiveHost;
import org.speckitty.missionstatus.testsupport.ConformanceTree;

/**
 * The provider-loaded guard and the provider-level completeness of the artifact routes (TASKS-GREEN-002, TASKS-FRESH3-003). The registry
 * loads providers by name and treats a missing class as an empty route, so a mistyped name would leave the golden suite green with zero
 * comparisons: this test fails when {@link ArtifactServedRoute} is not the class the registry found, when its golden files are not its row of the partition,
 * and when a manifest fixture holding one of its golden files is not served by it.
 */
class ArtifactServedRouteTest {

  @Test
  void theRegistryLoadedTheArtifactProviderByItsName() {
    assertThat(ServedRoutes.loadedProviderNames()).contains("ArtifactServedRoute");
    assertThat(ServedRoutes.loaded()).anyMatch(provider -> provider instanceof ArtifactServedRoute);
    assertThat(ServedRoutes.PROVIDER_NAMES).contains(ArtifactServedRoute.class.getSimpleName());
  }

  @Test
  void itsGoldenFilesAreExactlyItsRowOfThePartition() {
    Set<String> row = Set.of("list-artifacts.json", "get-artifact-content.json");

    assertThat(new ArtifactServedRoute().goldenFiles()).isEqualTo(row);
    assertThat(ServedRoutes.OWNER.entrySet().stream().filter(owner -> owner.getValue().equals("ArtifactServedRoute")).map(Map.Entry::getKey)).containsExactlyInAnyOrderElementsOf(row);
    assertThat(ServedRoutes.ownershipProblems(java.util.List.of(new ArtifactServedRoute()))).isEmpty();
  }

  @Test
  void everyManifestFixtureHoldingOneOfItsGoldenFilesIsServedByIt() {
    ArtifactServedRoute provider = new ArtifactServedRoute();

    Set<Entry> expected = ServedRoutes.expectedEntries(provider.goldenFiles());

    assertThat(provider.served()).isEqualTo(expected);
    assertThat(expected).as("the floor: the manifest holds these pairs").hasSizeGreaterThanOrEqualTo(5);
    assertThat(expected).extracting(Entry::fixtureKey).contains("artifacts-populated/artifacts-populated", "artifacts-sort/artifacts-sort", "artifacts-refusals/artifacts-refusals", "artifacts-redaction/artifacts-redaction");
    assertThat(expected).extracting(Entry::fixtureKey).as("artifacts-links has no golden: Java-only").noneMatch(key -> key.startsWith("artifacts-links/"));
  }

  /** The comparison of the golden suite, applied to this provider alone. */
  @SuppressWarnings("unchecked")
  private static int compare(ServedRoute provider, boolean perturb) {
    int compared = 0;
    for (Entry entry : provider.served()) {
      if (!CaseSensitiveHost.comparable(entry.fixtureKey())) {
        continue;
      }
      Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(ConformanceTree.detailFixtures().stream().filter(f -> f.key().equals(entry.fixtureKey())).findFirst().orElseThrow(), entry.goldenFile()));
      for (Map.Entry<String, Object> request : golden.entrySet()) {
        byte[] served = provider.body(entry, request.getKey());
        byte[] expected = CanonicalJson.toBytes(request.getValue());
        if (perturb) {
          expected = expected.clone();
          expected[expected.length / 2] ^= 0x01;
        }
        CanonicalJson.assertBodyEqualsGolden(served, expected);
        compared++;
      }
    }
    return compared;
  }

  @Test
  void theProviderServesEveryGoldenRequestByteForByteAndAPerturbedGoldenIsRed() {
    int compared = compare(new ArtifactServedRoute(), false);

    assertThat(compared).isGreaterThan(CaseSensitiveHost.isCaseSensitive() ? 25 : 24);
    assertThatThrownBy(() -> compare(new ArtifactServedRoute(), true)).isInstanceOf(AssertionError.class);
  }
}
