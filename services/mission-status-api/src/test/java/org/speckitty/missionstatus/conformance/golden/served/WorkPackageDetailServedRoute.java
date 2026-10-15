package org.speckitty.missionstatus.conformance.golden.served;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Stream;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The provider of {@code getWorkPackageDetail} for the golden harness (T109). {@link #served()} is every manifest fixture whose {@code golden/}
 * holds {@code get-work-package-detail.json}, derived by {@link ServedRoutes#expectedEntries} and not from a list, except the fixtures tagged
 * {@code knownDivergence}: their golden is the oracle's outcome and the Java outcome differs on purpose (V7 for the two symbolic-link worktrees,
 * V20 for the subtasks written as mappings; V19 is retired). Those three are served and asserted by the route's own tests against the
 * Java outcome, and {@link #divergentEntries()} names them so a test pins the exclusion.
 *
 * <p>The golden of this route is an object keyed by Work Package id whose values are {@code {"body", "status"}}: one request per key, over the
 * real HTTP server with the production wiring, answered as the same envelope. The body is compared as the server sent it: before it is wrapped
 * it must be, byte for byte, the canonical form of its own document. A fixture is served by one server for all its keys.
 */
public final class WorkPackageDetailServedRoute implements ServedRoute {

  public static final String GOLDEN = "get-work-package-detail.json";

  private static final Map<Entry, Map<String, byte[]>> ANSWERS = new ConcurrentHashMap<>();

  @Override
  public Set<String> goldenFiles() {
    return Set.of(GOLDEN);
  }

  @Override
  public Set<Entry> served() {
    Set<Entry> entries = new LinkedHashSet<>(ServedRoutes.expectedEntries(goldenFiles()));
    entries.removeAll(divergentEntries());
    return entries;
  }

  /** The pairs of {@link ServedRoutes#expectedEntries} that this provider leaves to the route's own tests: the {@code knownDivergence} fixtures. */
  public static Set<Entry> divergentEntries() {
    Set<Entry> divergent = new LinkedHashSet<>();
    for (Entry entry : ServedRoutes.expectedEntries(Set.of(GOLDEN))) {
      if (fixture(entry.fixtureKey()).knownDivergence()) {
        divergent.add(entry);
      }
    }
    return divergent;
  }

  @Override
  public byte[] body(Entry entry, String requestKey) {
    return ANSWERS.computeIfAbsent(entry, WorkPackageDetailServedRoute::answerAll).get(requestKey);
  }

  /** One server over the provisioned fixture, one request for each key of the golden. */
  @SuppressWarnings("unchecked")
  private static Map<String, byte[]> answerAll(Entry entry) {
    TreeFixture fixture = fixture(entry.fixtureKey());
    Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, entry.goldenFile()));
    DetailFixture detail = DetailFixture.of(fixture.dir());
    String missionId = missionIdOf(fixture);
    Map<String, byte[]> answers = new LinkedHashMap<>();
    try (HttpHarness server = HttpHarness.startWired(detail.root())) {
      for (String wpId : golden.keySet()) {
        answers.put(wpId, envelope(server.get(path(missionId, wpId))));
      }
    }
    return answers;
  }

  /** The envelope of the golden: {@code {"body": <the served document>, "status": <the status>}}, after the body is shown to be canonical. */
  private static byte[] envelope(HttpHarness.Response response) {
    Object document = CanonicalJson.parse(response.body());
    CanonicalJson.assertBodyEqualsGolden(response.body(), CanonicalJson.toBytes(document));
    Map<String, Object> envelope = new LinkedHashMap<>();
    envelope.put("body", document);
    envelope.put("status", response.status());
    return CanonicalJson.toBytes(envelope);
  }

  // ---- the route's tests build on these -----------------------------------------------------------------------------------------

  /** The path of the route for a Mission id and a Work Package id. */
  public static String path(String missionId, String wpId) {
    return "/api/v1/missions/" + missionId + "/work-packages/" + wpId + "/detail";
  }

  public static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow(() -> new AssertionError("no detail fixture " + key));
  }

  /**
   * The Mission id the fixture's goldens are about: the {@code missionId} member of any 200 body of its detail golden, else the first Mission id
   * its {@code meta.json} files carry (a fixture whose every golden is a refusal carries it only there).
   */
  @SuppressWarnings("unchecked")
  public static String missionIdOf(TreeFixture fixture) {
    byte[] golden = ConformanceTree.golden(fixture, GOLDEN);
    if (golden != null) {
      for (Object value : ((Map<String, Object>) CanonicalJson.parse(golden)).values()) {
        Object body = ((Map<String, Object>) value).get("body");
        if (body instanceof Map<?, ?> document && document.get("missionId") instanceof String id) {
          return id;
        }
      }
    }
    Path specs = fixture.dir().resolve("kitty-specs");
    try (Stream<Path> missions = Files.list(specs)) {
      return missions
          .sorted()
          .map(mission -> mission.resolve("meta.json"))
          .filter(Files::isRegularFile)
          .map(WorkPackageDetailServedRoute::idOf)
          .filter(java.util.Objects::nonNull)
          .findFirst()
          .orElseThrow(() -> new AssertionError("no Mission id in " + fixture.key()));
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  @SuppressWarnings("unchecked")
  private static String idOf(Path meta) {
    try {
      Object document = CanonicalJson.parse(Files.readAllBytes(meta));
      return document instanceof Map<?, ?> map && ((Map<String, Object>) map).get("mission_id") instanceof String id ? id : null;
    } catch (IOException | IllegalArgumentException unreadable) {
      return null;
    }
  }

  /** The request keys of a golden, in the order the golden holds them. */
  @SuppressWarnings("unchecked")
  public static String[] requestKeys(TreeFixture fixture) {
    return ((Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, GOLDEN))).keySet().toArray(String[]::new);
  }
}
