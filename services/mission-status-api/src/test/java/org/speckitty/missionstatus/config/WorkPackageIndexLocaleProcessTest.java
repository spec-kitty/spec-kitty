package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.Utf8Host;

/**
 * AC-6.6, the process leg (FRESH3-004): in a child JVM started with {@code LC_ALL=C} the file-name decoding is not trustworthy, so a Work
 * Package index that finds a non-ASCII candidate refuses, and each of {@code getMission}, {@code getWorkPackage} and
 * {@code getWorkPackageDetail} answers 500 {@code source_unreadable} with exactly one path-free {@code source_unreadable} diagnostic line. It
 * never omits {@code WP01} silently and never serves a partial index. An ASCII-only fixture is served under the same locale, the non-candidate
 * {@code notes-é.md} does not refuse, and the same non-ASCII fixture under a UTF-8 child is served in full (the control: the refusal comes from
 * the locale, and a child that inherited a UTF-8 locale would fail the first test loudly). The stub leg ({@code NameEncoding}) runs under any
 * locale and is not repeated here; the parent only has to create the fixture, so a host that cannot skips with the recorded line.
 */
class WorkPackageIndexLocaleProcessTest {

  private static final long UP_SECONDS = 90;
  private static final String ID = Rows.ALPHA_ID;

  private static Path project(boolean nonAscii) {
    Path root = FilesystemFixtureFactory.fromSpec(FixtureSpec.of(PortFixtures.mission("alpha", ID, DetailRoute.CREATED, DetailRoute.ledger()))).root();
    MissionDetailServedRoute.write(root, "alpha", nonAscii ? "tasks/WP01-é.md" : "tasks/WP01-a.md", DetailRoute.wpFile("WP01", "One"));
    MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-x.md", DetailRoute.wpFile("WP02", "Two"));
    MissionDetailServedRoute.write(root, "alpha", nonAscii ? "tasks/notes-é.md" : "tasks/notes-a.md", "notes\n");
    return root;
  }

  /** The child answers; each route returns its status, Problem code (or null) and the number of new source_unreadable diagnostic lines. */
  private record Answer(String route, int status, String body, int newDiagnostics) {}

  private static List<Answer> ask(Path dir, Path root, Map<String, String> environment) throws Exception {
    Path log = dir.resolve("out.log");
    int port = AppProcess.freePort();
    Process process = AppProcess.launch(log, dir, environment, List.of(), List.of("--server.port=" + port, "--mission-status.project-root=" + root));
    try {
      awaitUp(process, port, log);
      String base = "http://127.0.0.1:" + port + "/api/v1/missions/" + ID;
      List<Answer> answers = new java.util.ArrayList<>();
      int seen = 0;
      for (String route : List.of("", "/work-packages/WP01", "/work-packages/WP01/detail")) {
        HttpResponse<String> response = HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create(base + route)).GET().build(), HttpResponse.BodyHandlers.ofString());
        Thread.sleep(400);
        int total = diagnostics(log);
        answers.add(new Answer(route.isEmpty() ? "getMission" : route.endsWith("detail") ? "getWorkPackageDetail" : "getWorkPackage", response.statusCode(), response.body(), total - seen));
        seen = total;
      }
      return answers;
    } finally {
      process.destroyForcibly();
      process.waitFor();
    }
  }

  private static int diagnostics(Path log) throws IOException {
    return (int) Files.readAllLines(log).stream().filter(line -> line.contains("diagnostic code=source_unreadable")).count();
  }

  @Test
  @Timeout(300)
  void underLcAllCTheThreeRoutesRefuseWithOneDiagnosticEachAndOmitNothingSilently(@TempDir Path dir) throws Exception {
    Utf8Host.assumeUtf8("WorkPackageIndexLocaleProcessTest#underLcAllC");
    Utf8Host.assumeChildNamesUntrustworthy("WorkPackageIndexLocaleProcessTest#underLcAllC.childLocale", Map.of("LC_ALL", "C"));

    List<Answer> answers = ask(dir, project(true), Map.of("LC_ALL", "C"));

    assertThat(answers).hasSize(3);
    for (Answer answer : answers) {
      assertThat(answer.status()).as(answer.route() + " under LC_ALL=C").isEqualTo(500);
      assertThat(answer.body()).contains("\"code\":\"source_unreadable\"").doesNotContain("WP01").doesNotContain("WP02").doesNotContain("é");
      assertThat(answer.newDiagnostics()).as(answer.route() + " writes exactly one source_unreadable diagnostic").isEqualTo(1);
    }
  }

  @Test
  @Timeout(300)
  void anAsciiOnlyFixtureIsServedUnderLcAllCAndTheNonCandidateDoesNotRefuse(@TempDir Path dir) throws Exception {
    Utf8Host.assumeUtf8("WorkPackageIndexLocaleProcessTest#asciiUnderLcAllC");

    List<Answer> answers = ask(dir, project(false), Map.of("LC_ALL", "C"));

    assertThat(answers).extracting(Answer::status).containsExactly(200, 200, 200);
    assertThat(answers).extracting(Answer::newDiagnostics).containsExactly(0, 0, 0);
  }

  @Test
  @Timeout(300)
  void controlTheSameNonAsciiFixtureIsServedInFullByAUtf8Child(@TempDir Path dir) throws Exception {
    Utf8Host.assumeUtf8("WorkPackageIndexLocaleProcessTest#controlUtf8Child");

    List<Answer> answers = ask(dir, project(true), Map.of("LC_ALL", "C.UTF-8"));

    assertThat(answers).extracting(Answer::status).as("a child that inherited a UTF-8 locale would not refuse: the first test is red then").containsExactly(200, 200, 200);
    assertThat(answers.get(0).body()).contains("WP01").contains("WP02");
    assertThat(answers).extracting(Answer::newDiagnostics).containsExactly(0, 0, 0);
  }

  private static void awaitUp(Process process, int port, Path log) throws IOException, InterruptedException {
    long deadline = System.nanoTime() + UP_SECONDS * 1_000_000_000L;
    while (System.nanoTime() < deadline && process.isAlive()) {
      try (Socket socket = new Socket()) {
        socket.connect(new InetSocketAddress("127.0.0.1", port), 500);
        return;
      } catch (IOException notYet) {
        Thread.sleep(200);
      }
    }
    throw new AssertionError("the service did not come up: " + Files.readString(log));
  }
}
