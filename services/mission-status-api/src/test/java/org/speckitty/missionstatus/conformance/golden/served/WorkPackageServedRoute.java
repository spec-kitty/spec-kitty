package org.speckitty.missionstatus.conformance.golden.served;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The provider of {@code getWorkPackage} for the golden harness (T102). {@link #served()} is every manifest fixture whose {@code golden/}
 * holds {@code get-work-package.json} or {@code get-work-package-prompt.json}, derived by {@link ServedRoutes#expectedEntries} and not from
 * a list, except the {@link #DIVERGENT} fixtures and the {@link #emptyEntries()}: the golden of the first is the oracle's outcome and the Java
 * outcome differs on purpose, so a byte comparison with it could only be red, and the second holds nothing to compare. Each of those is asserted against the Java outcome by a named test of this route
 * ({@code WorkPackageQueryServiceDivergenceTest}), and {@link #divergentEntries()} names them so a test pins the exclusion.
 *
 * <p>The request key is the Work Package id the golden holds: {@code GET /api/v1/missions/{missionId}/work-packages/{wpId}}, with
 * {@code includePrompt=true} for {@code get-work-package-prompt.json}, over the real HTTP server with the production wiring. This class
 * imports no adapter class (rule 11b).
 */
public final class WorkPackageServedRoute implements ServedRoute {

  public static final String GOLDEN = "get-work-package.json";
  public static final String PROMPT_GOLDEN = "get-work-package-prompt.json";

  /**
   * The {@code knownDivergence} fixtures whose Java outcome is not the oracle's golden for this route: V20
   * (subtasks written as mappings), V21 (a float agent or actor), V22 (an annotation or override member that is not text), V23 (a verdict
   * that is not text), V24 (a subtask status outside the nine lanes), V25 (an event id that is not text) and V28 (a departure from approved stamped
   * before a clock-ahead approval, which the 10.5.1 oracle lifts and Java keeps in text order until spec-kitty#6268).
   */
  public static final Set<String> DIVERGENT =
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

  @Override
  public Set<String> goldenFiles() {
    return Set.of(GOLDEN, PROMPT_GOLDEN);
  }

  @Override
  public Set<Entry> served() {
    Set<Entry> entries = new LinkedHashSet<>(ServedRoutes.expectedEntries(goldenFiles()));
    entries.removeAll(divergentEntries());
    entries.removeAll(emptyEntries());
    return entries;
  }

  /**
   * The pairs whose golden holds no request key ({@code {}}): the oracle's index skipped the Work Package file, so there was no Work Package
   * to ask for. {@code DetailGoldenSuiteTest} refuses an empty golden (it can compare no body), so this provider cannot serve them; the Java
   * outcome (the same file is skipped and its Work Package is not found) is asserted by {@code WorkPackageQueryServiceDivergenceTest}.
   */
  public static Set<Entry> emptyEntries() {
    Set<Entry> empty = new LinkedHashSet<>();
    for (Entry entry : ServedRoutes.expectedEntries(Set.of(GOLDEN, PROMPT_GOLDEN))) {
      if (requestKeys(fixture(entry.fixtureKey()), entry.goldenFile()).isEmpty()) {
        empty.add(entry);
      }
    }
    return empty;
  }

  /** The pairs of {@link ServedRoutes#expectedEntries} that this provider leaves to the route's own tests. */
  public static Set<Entry> divergentEntries() {
    Set<Entry> divergent = new LinkedHashSet<>();
    for (Entry entry : ServedRoutes.expectedEntries(Set.of(GOLDEN, PROMPT_GOLDEN))) {
      if (DIVERGENT.contains(entry.fixtureKey())) {
        divergent.add(entry);
      }
    }
    return divergent;
  }

  @Override
  public byte[] body(Entry entry, String requestKey) {
    TreeFixture fixture = fixture(entry.fixtureKey());
    DetailFixture detail = DetailFixture.of(fixture.dir());
    try (HttpHarness server = HttpHarness.startWired(detail.root())) {
      return server.get(path(missionIdOf(fixture), requestKey, PROMPT_GOLDEN.equals(entry.goldenFile()))).body();
    }
  }

  // ---- the route's tests build on these -----------------------------------------------------------------------------------------

  /** The path of the route, with {@code includePrompt=true} when asked. */
  public static String path(String missionId, String wpId, boolean includePrompt) {
    return "/api/v1/missions/" + missionId + "/work-packages/" + wpId + (includePrompt ? "?includePrompt=true" : "");
  }

  /** The id of the Mission of the fixture: the {@code mission_id} of the first {@code meta.json} in directory order (the duplicate-id fixtures repeat it). */
  @SuppressWarnings("unchecked")
  public static String missionIdOf(TreeFixture fixture) {
    try (java.util.stream.Stream<java.nio.file.Path> missions = java.nio.file.Files.list(fixture.dir().resolve("kitty-specs"))) {
      java.nio.file.Path first = missions.sorted().findFirst().orElseThrow();
      Map<String, Object> meta = (Map<String, Object>) CanonicalJson.parse(java.nio.file.Files.readAllBytes(first.resolve("meta.json")));
      return (String) meta.get("mission_id");
    } catch (java.io.IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    }
  }

  /** The Work Package ids a golden holds, in its order. */
  @SuppressWarnings("unchecked")
  public static List<String> requestKeys(TreeFixture fixture, String goldenFile) {
    Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, goldenFile));
    return List.copyOf(golden.keySet());
  }

  public static TreeFixture fixture(String key) {
    return MissionDetailServedRoute.fixture(key);
  }
}
