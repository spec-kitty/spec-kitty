package org.speckitty.missionstatus.readme;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

/**
 * The README states what the service answers (FR-018, SC-009, SC-008): the nine routes, that drift and Ops have no Java owner yet, the
 * divergence list and the note about the two read instants, and the one locale sentence. {@link #problems(String)} is pure so that a
 * control can feed it a mutated copy and expect the violation.
 */
class MissionStatusReadmeTest {

  private static final Path README = Path.of("README.md");
  private static final String ROUTES_HEADING = "## Routes and scope";

  /** The nine routes, as they are written in the routes list. */
  private static final List<String> ROUTES =
      List.of(
          "`GET /api/v1/project`",
          "`GET /api/v1/missions`",
          "`GET /api/v1/events`",
          "`GET /api/v1/openapi.yaml`",
          "`GET /api/v1/missions/{missionId}`",
          "`GET /api/v1/missions/{missionId}/work-packages/{wpId}`",
          "`GET /api/v1/missions/{missionId}/work-packages/{wpId}/detail`",
          "`GET /api/v1/missions/{missionId}/artifacts`",
          "`GET /api/v1/missions/{missionId}/artifacts/content?path=");

  /** Paths the out-of-scope test still asserts as 404: they must not be listed as routes. */
  private static final List<String> STILL_NOT_FOUND = List.of("/api/v1/drift", "/api/v1/ops");

  /** The needles the README must hold, each with the reason it is there. */
  private static final List<String[]> REQUIRED =
      List.of(
          new String[] {"no Java owner yet", "drift and Ops have no Java owner (FR-018)"},
          new String[] {"UTF-8 locale", "the locale sentence (WP16)"},
          new String[] {"sun.jnu.encoding", "the locale sentence (WP16)"},
          new String[] {"LC_ALL", "the locale sentence (WP16)"},
          new String[] {"read one after the other", "the ledger and the Work Package files are read at slightly different instants (SC-008)"},
          new String[] {"mission-status.stream.max-connections", "the stream cap key is unchanged"},
          new String[] {"belong to the inbound port", "the stream projection sentence"},
          new String[] {"### Divergences of the detail routes", "the divergence list"});

  @Test
  void theReadmeStatesTheNineRoutesAndThatDriftAndOpsHaveNoJavaOwner() {
    assertThat(README).as("README.md of the module working directory").exists();

    assertThat(problems(read())).isEmpty();
  }

  @Test
  void everyDivergenceFromV1ToV19IsNamedInTheDivergenceListAndTheResolvedStateOnesAreCoveredByRange() {
    String section = between(read(), "### Divergences of the detail routes", "## Release and binaries");

    for (int number = 1; number <= 19; number++) {
      assertThat(section).as("V" + number).containsPattern("\\bV" + number + "\\b");
    }
    assertThat(section).contains("V20 to V25").contains("V26");
  }

  @Test
  void aRevertedRoutesSectionIsReported() {
    String good = read();
    String reverted =
        good.replace("drift and Ops have no Java owner yet", "artifacts, drift, Ops")
            .replace("Drift and Ops have no Java owner yet", "Detail routes (a single Mission or Work Package, artifacts, drift, Ops) are issue #957 and out of scope here");

    assertThat(reverted).isNotEqualTo(good);
    assertThat(problems(reverted)).anyMatch(problem -> problem.contains("artifacts, drift, Ops")).anyMatch(problem -> problem.contains("are issue #957"));
  }

  @Test
  void eachRequiredNeedleIsReportedWhenItIsRemoved() {
    String good = read();
    for (String[] required : REQUIRED) {
      String mutated = good.replace(required[0], "REMOVED");
      assertThat(mutated).as("the README holds " + required[0]).isNotEqualTo(good);
      assertThat(problems(mutated)).as("without " + required[0]).anyMatch(problem -> problem.contains(required[0]));
    }
  }

  @Test
  void aRouteThatIsMissingOrThatIsStillOutOfScopeIsReported() {
    String good = read();
    for (String route : ROUTES) {
      String mutated = good.replace(route, "`GET /api/v1/removed`");
      assertThat(mutated).as(route).isNotEqualTo(good);
      assertThat(problems(mutated)).as("without " + route).anyMatch(problem -> problem.contains(route));
    }
    String listed = good.replace("- `GET /api/v1/events`", "- `GET /api/v1/drift`\n- `GET /api/v1/events`");
    assertThat(problems(listed)).anyMatch(problem -> problem.contains("/api/v1/drift"));
  }

  @Test
  void noUnnamedGitHubUsernameOrHomePathIsInTheReadme() {
    String text = read();

    assertThat(text).doesNotContain("/" + "home/").doesNotContain("/" + "Users/");
  }

  /** Every violation of the README contract, empty when the text holds it. */
  static List<String> problems(String readme) {
    List<String> found = new ArrayList<>();
    if (readme.contains("are issue #957")) {
      found.add("the README still says \"are issue #957\" (drift and Ops are no longer #957's)");
    }
    if (readme.contains("artifacts, drift, Ops")) {
      found.add("the README still lists \"artifacts, drift, Ops\" as out of scope");
    }
    int start = readme.indexOf(ROUTES_HEADING);
    if (start < 0) {
      return List.of("the README has no \"" + ROUTES_HEADING + "\" section");
    }
    String routes = between(readme, ROUTES_HEADING, "\n## ");
    for (String route : ROUTES) {
      if (!routes.contains(route)) {
        found.add("the routes section does not list " + route);
      }
    }
    for (String path : STILL_NOT_FOUND) {
      if (routes.contains("`GET " + path)) {
        found.add("the routes section lists " + path + ", which still answers 404");
      }
    }
    if (!routes.contains("no Java owner yet")) {
      found.add("the routes section does not say that drift and Ops have \"no Java owner yet\"");
    }
    for (String[] required : REQUIRED) {
      if (!readme.contains(required[0])) {
        found.add("the README lacks \"" + required[0] + "\": " + required[1]);
      }
    }
    Matcher listed = Pattern.compile("^- `GET (/api/v1/\\S*?)`?[ :(]", Pattern.MULTILINE).matcher(routes);
    int count = 0;
    while (listed.find()) {
      count++;
    }
    if (count != ROUTES.size()) {
      found.add("the routes section lists " + count + " routes, not " + ROUTES.size());
    }
    return found;
  }

  private static String between(String text, String from, String to) {
    int start = text.indexOf(from);
    if (start < 0) {
      return "";
    }
    int end = text.indexOf(to, start + from.length());
    return end < 0 ? text.substring(start) : text.substring(start, end);
  }

  private static String read() {
    try {
      return Files.readString(README, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
