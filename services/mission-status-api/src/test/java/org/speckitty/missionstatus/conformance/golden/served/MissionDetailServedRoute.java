package org.speckitty.missionstatus.conformance.golden.served;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import org.speckitty.missionstatus.conformance.golden.ServedRoute;
import org.speckitty.missionstatus.conformance.golden.ServedRoutes;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The provider of {@code getMission} for the golden harness (T094), and the fixture helpers the route's tests share. {@link #served()} is every manifest fixture whose {@code golden/} holds {@code get-mission.json}, derived by
 * {@link ServedRoutes#expectedEntries} and not from a list, except the fixtures tagged {@code knownDivergence}: their golden is the
 * oracle's outcome and the Java outcome differs on purpose, so a byte comparison with it could only be red. Those five are served and
 * asserted by the route's own tests against the Java outcome (V1, V20; V19 is retired), and {@link #divergentEntries()} names them so a test pins
 * the exclusion.
 *
 * <p>The request key is {@code "-"}: {@code GET /api/v1/missions/{missionId}} over the real HTTP server with the production wiring, with the id
 * the golden carries. This class imports no adapter class (rule 11b); the tests that need the service over a fixture build it in
 * {@code MissionDetailRowsTest}.
 */
public final class MissionDetailServedRoute implements ServedRoute {

  public static final String GOLDEN = "get-mission.json";
  public static final String REQUEST_KEY = "-";

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
    if (!REQUEST_KEY.equals(requestKey)) {
      return null;
    }
    TreeFixture fixture = fixture(entry.fixtureKey());
    // the production application with its own wiring over the provisioned copy of the fixture: the bytes a client would receive
    DetailFixture detail = DetailFixture.of(fixture.dir());
    try (HttpHarness server = HttpHarness.startWired(detail.root())) {
      return server.get(path(missionIdOf(fixture))).body();
    }
  }

  // ---- the route's tests build on these -----------------------------------------------------------------------------------------

  /** The path of the route for a Mission id. */
  public static String path(String missionId) {
    return "/api/v1/missions/" + missionId;
  }

  /** The id the fixture's golden is about. */
  @SuppressWarnings("unchecked")
  public static String missionIdOf(TreeFixture fixture) {
    Map<String, Object> golden = (Map<String, Object>) CanonicalJson.parse(ConformanceTree.golden(fixture, GOLDEN));
    return (String) ((Map<String, Object>) golden.get(REQUEST_KEY)).get("missionId");
  }

  public static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow(() -> new AssertionError("no detail fixture " + key));
  }

  /**
   * A fixture built from a source-neutral spec, with the file seam recording, after {@code extras} added files to the tree (planning
   * files, Work Package files, a {@code .worktrees} entry). The Mission directories are {@code <root>/kitty-specs/<name>}.
   */
  public static DetailFixture fixtureOf(FixtureSpec spec, Consumer<Path> extras) {
    Path source = FilesystemFixtureFactory.fromSpec(spec).root();
    extras.accept(source);
    // copied into a scratch root with the recording file seam, like a committed fixture
    return DetailFixture.of(source);
  }

  /** Writes a text file below a Mission directory of the tree, creating the directories. */
  public static void write(Path root, String mission, String relative, String text) {
    Path file = root.resolve("kitty-specs").resolve(mission).resolve(relative);
    try {
      Files.createDirectories(file.getParent());
      Files.writeString(file, text, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** A minimal valid Work Package file. */
  public static String workPackageFile(String id, String title, String... frontmatterLines) {
    StringBuilder text = new StringBuilder("---\nwork_package_id: ").append(id).append("\ntitle: ").append(title).append('\n');
    for (String line : frontmatterLines) {
      text.append(line).append('\n');
    }
    return text.append("---\n\nBody of ").append(id).append('\n').toString();
  }
}
