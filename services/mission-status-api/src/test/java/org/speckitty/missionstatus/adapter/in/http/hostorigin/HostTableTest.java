package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.function.IntFunction;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * AC-9b over real sockets: the Host tables. Every row carries its LITERAL expected status and its LITERAL {@code reachesFilter} flag
 * (written here, never taken from the reply just received) and runs on the five request targets. Set 1 (the filter sees the value) is
 * 403 {@code request_refused}; set 2 (the container decides, closed list) is the container's own 400 and never enters the filter.
 * Per row: status, filter entry, no Mission read, no stream, no secret in the reply, and no echo of the foreign value.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class HostTableTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  /** A request built for the bound port: the request line target and the header lines. */
  private record Row(String name, IntFunction<List<String>> headers, boolean absoluteForm, String http, int status, boolean reachesFilter, String foreignMarker) {
    @Override
    public String toString() {
      return name;
    }
  }

  private static Row row(String name, IntFunction<List<String>> headers, int status, boolean reachesFilter, String marker) {
    return new Row(name, headers, false, "HTTP/1.1", status, reachesFilter, marker);
  }

  private static final List<Row> ROWS =
      List.of(
          // set 1: the filter sees the value, 403
          row("1 evil.example", p -> List.of("Host: evil.example"), 403, true, "evil.example"),
          row("2 evil.example:port", p -> List.of("Host: evil.example:" + p), 403, true, "evil.example"),
          row("3 127.0.0.1 without port", p -> List.of("Host: 127.0.0.1"), 403, true, null),
          row("4 127.0.0.1:port+1", p -> List.of("Host: 127.0.0.1:" + (p + 1)), 403, true, null),
          new Row("5 no Host (HTTP/1.0)", p -> List.of(), false, "HTTP/1.0", 403, true, null),
          row("6 127.0.0.1.evil.example:port", p -> List.of("Host: 127.0.0.1.evil.example:" + p), 403, true, "evil.example"),
          row("7 localhost.evil.example:port", p -> List.of("Host: localhost.evil.example:" + p), 403, true, "evil.example"),
          row("9 [::1]:port over IPv4", p -> List.of("Host: [::1]:" + p), 403, true, "[::1]"),
          // set 2: the container answers itself, closed list of four, 400
          row("8 evil.example@127.0.0.1:port", p -> List.of("Host: evil.example@127.0.0.1:" + p), 400, false, "evil.example"),
          row("E1 duplicate Host", p -> List.of("Host: 127.0.0.1:" + p, "Host: 127.0.0.1:" + p), 400, false, null),
          new Row("E2 HTTP/1.1 without Host", p -> List.of(), false, "HTTP/1.1", 400, false, null),
          new Row("E3 HTTP/1.1 absolute-form foreign target, accepted Host", p -> List.of("Host: 127.0.0.1:" + p), true, "HTTP/1.1", 400, false, "evil.example"),
          // E-7 rows decided by the filter
          new Row("E4 HTTP/1.0 absolute-form foreign target", p -> List.of(), true, "HTTP/1.0", 403, true, "evil.example"),
          row("E5 empty Host", p -> List.of("Host:"), 403, true, null),
          row("E6 accepted Host + X-Forwarded-Host", p -> List.of("Host: 127.0.0.1:" + p, "X-Forwarded-Host: evil.example"), 403, true, "evil.example"),
          row("E7 accepted Host + Forwarded", p -> List.of("Host: 127.0.0.1:" + p, "Forwarded: host=evil.example"), 403, true, "evil.example"),
          row("E8 LOCALHOST:port", p -> List.of("Host: LOCALHOST:" + p), 403, true, "LOCALHOST"),
          row("E9 localhost.:port", p -> List.of("Host: localhost.:" + p), 403, true, "localhost."));

  static Stream<Arguments> cases() {
    return ROWS.stream().flatMap(row -> HostOriginRig.TARGETS.stream().map(target -> Arguments.of(row, target)));
  }

  private HostOriginRig server;

  @BeforeAll
  void start() {
    server = HostOriginRig.start();
  }

  @AfterAll
  void stop() {
    server.close();
  }

  @ParameterizedTest(name = "{0} on {1}")
  @MethodSource("cases")
  void everyRowAnswersItsLiteralStatusAndEntersTheFilterOrNot(Row row, String target) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    String requestTarget = row.absoluteForm() ? "http://evil.example" + target : target;
    RawClient.Reply reply = server.send("GET " + requestTarget + " " + row.http(), row.headers().apply(port).toArray(String[]::new));
    int entered = server.counter.entries() - entriesBefore;

    assertThat(reply.status()).as("status").isEqualTo(row.status());
    assertThat(entered).as("reachesFilter").isEqualTo(row.reachesFilter() ? 1 : 0);
    assertThat(server.reads() - readsBefore).as("Mission reads and port calls").isZero();
    assertThat(server.stream().spy.openSubscriptions()).as("no stream opened").isZero();
    assertThat(reply.text()).as("not an event stream").doesNotContainIgnoringCase("text/event-stream");
    for (String secret : server.secrets()) {
      assertThat(reply.text()).as("no secret in the reply").doesNotContain(secret);
    }
    if (row.foreignMarker() != null) {
      assertThat(reply.text()).as("no echo of the foreign value").doesNotContain(row.foreignMarker());
    }
    if (row.status() == 403) {
      assertRefusalProblem(reply);
    } else {
      assertThat(reply.text()).as("the container's own answer, not a service Problem").doesNotContain("request_refused").doesNotContain("application/problem+json");
    }
  }

  private static void assertRefusalProblem(RawClient.Reply reply) {
    assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json");
    String body = HostOriginRig.body(reply);
    assertThat(body).endsWith("\n");
    JsonNode problem = JSON.readTree(body);
    assertThat(problem.get("code").asString()).isEqualTo("request_refused");
    assertThat(problem.get("title").asString()).isEqualTo("Request refused");
    assertThat(problem.get("status").asInt()).isEqualTo(403);
    assertThat(problem.has("detail")).as("no detail naming the failed check").isFalse();
    assertThat(problem.size()).isEqualTo(3);
    assertThat(reply.text()).doesNotContainIgnoringCase("Access-Control-Allow");
  }

  @org.junit.jupiter.api.Test
  void aRefusedStreamRequestOpensNothingAndALedgerAppendProducesNoData() {
    int port = server.port();
    RawClient.Reply refused = server.send("GET /api/v1/events HTTP/1.1", "Host: evil.example:" + port, "Accept: text/event-stream");
    assertThat(refused.status()).isEqualTo(403);
    assertThat(refused.text()).doesNotContainIgnoringCase("text/event-stream");
    server.stream().append("canary-mission", "");
    assertThat(HostOriginRig.body(refused)).doesNotContain("event:").doesNotContain("data:");
    assertThat(server.stream().spy.totalSubscriptions()).isZero();
  }

  @org.junit.jupiter.api.Test
  void theSetsAreEightAndFourOnTheNineRowsPlusTheThreeContainerRows() {
    // the closed lists of the specification: eight 403 rows of AC-9b set 1, four 400 rows of set 2
    List<String> set1 = ROWS.stream().filter(r -> r.status() == 403).map(Row::name).filter(n -> n.matches("[1-79] .*")).toList();
    List<String> set2 = ROWS.stream().filter(r -> r.status() == 400).map(Row::name).toList();
    assertThat(set1).hasSize(8);
    assertThat(set2).hasSize(4);
  }

  // F1: the container's own sendError reaches the guard through an ERROR dispatch; F2: the springdoc paths do not exist and are guarded too

  static Stream<Arguments> methodRows() {
    return Stream.of("TRACE").flatMap(method -> HostOriginRig.TARGETS.stream().map(target -> Arguments.of(method, target)));
  }

  @ParameterizedTest(name = "{0} {1} with a foreign Host")
  @MethodSource("methodRows")
  void aContainerRefusedMethodWithAForeignHostIsRefusedByTheGuardOnTheErrorDispatch(String method, String target) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    RawClient.Reply reply = server.send(method + " " + target + " HTTP/1.1", "Host: evil.example:" + port);
    assertThat(reply.status()).isEqualTo(403);
    assertThat(server.counter.entries() - entriesBefore).as("reachesFilter").isEqualTo(1);
    assertThat(server.reads() - readsBefore).isZero();
    assertRefusalProblem(reply);
    assertThat(reply.text()).doesNotContain("evil.example").doesNotContain(target).doesNotContain("timestamp").doesNotContain("\"error\"");
  }

  static Stream<String> otherPaths() {
    return Stream.of("/v3/api-docs", "/v3/api-docs.yaml", "/swagger-ui.html", "/swagger-ui/index.html", "/nope", "/", "/api/v1/missions/01J01000000000000000000001");
  }

  @ParameterizedTest(name = "foreign Host on {0}")
  @MethodSource("otherPaths")
  void aForeignHostOnAnyOtherPathIsRefusedNotNotFound(String path) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    RawClient.Reply reply = server.send("GET " + path + " HTTP/1.1", "Host: evil.example:" + port);
    assertThat(reply.status()).isEqualTo(403);
    assertThat(server.counter.entries() - entriesBefore).isEqualTo(1);
    assertThat(server.reads() - readsBefore).isZero();
    assertRefusalProblem(reply);
    assertThat(reply.text()).doesNotContain("evil.example").doesNotContain(path.length() > 1 ? path : "\u0000");
  }

  static Stream<Arguments> errorControls() {
    return Stream.of(
        Arguments.of("GET", "/api/v1/nowhere-at-all", 404),
        Arguments.of("POST", "/api/v1/project", 405),
        Arguments.of("DELETE", "/api/v1/missions", 405));
  }

  @ParameterizedTest(name = "accepted Host, {0} {1}: {2}")
  @MethodSource("errorControls")
  void anAcceptedHostKeepsItsErrorProblem(String method, String target, int status) {
    int entriesBefore = server.counter.entries();
    RawClient.Reply reply = server.send(method + " " + target + " HTTP/1.1", "Host: 127.0.0.1:" + server.port());
    assertThat(reply.status()).isEqualTo(status);
    assertThat(server.counter.entries() - entriesBefore).as("entered once, not refused, not counted twice").isEqualTo(1);
    assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json").doesNotContain("request_refused");
    assertThat(JSON.readTree(HostOriginRig.body(reply)).get("status").asInt()).isEqualTo(status);
  }

  @org.junit.jupiter.api.Test
  void anAcceptedHostTraceIsTheContainersOwn405NotARefusal() {
    int entriesBefore = server.counter.entries();
    RawClient.Reply reply = server.send("TRACE /api/v1/project HTTP/1.1", "Host: 127.0.0.1:" + server.port());
    assertThat(reply.status()).isEqualTo(405);
    assertThat(server.counter.entries() - entriesBefore).isEqualTo(1);
    assertThat(reply.text()).doesNotContain("request_refused");
  }

  @org.junit.jupiter.api.Test
  void aWholeReadFailureKeepsItsProblemUnderAnAcceptedHost() {
    try (HostOriginRig failing = HostOriginRig.start()) {
      failing.stream().http.allowlistRecorder().failWhen(a -> true, () -> new java.nio.file.AccessDeniedException("injected"));
      int before = failing.counter.entries();
      RawClient.Reply reply = failing.send("GET /api/v1/project HTTP/1.1", "Host: 127.0.0.1:" + failing.port());
      assertThat(reply.status()).isEqualTo(500);
      assertThat(failing.counter.entries() - before).isEqualTo(1);
      assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json").doesNotContain("request_refused");
      assertThat(JSON.readTree(HostOriginRig.body(reply)).get("status").asInt()).isEqualTo(500);
    }
  }

  // F3: requests the container answers by itself before any filter, observed on Tomcat 11.0.24 and pinned as literal container-owned rows
  // (the same treatment as rows 8 and E1-E3): the guard is not reached, nothing is read, and the foreign Host is not echoed.

  private record ContainerRow(String name, String requestLine, int status) {
    @Override
    public String toString() {
      return name;
    }
  }

  static Stream<ContainerRow> containerOwned() {
    return Stream.of(
        new ContainerRow("OPTIONS * (asterisk-form)", "OPTIONS * HTTP/1.1", 200),
        new ContainerRow("CONNECT authority-form", "CONNECT 127.0.0.1:%d HTTP/1.1", 501));
  }

  @ParameterizedTest(name = "container-owned: {0}, foreign Host")
  @MethodSource("containerOwned")
  void requestsTheContainerAnswersItselfNeverReachTheGuardAndReadNothing(ContainerRow row) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    RawClient.Reply reply = server.send(row.requestLine().formatted(port), "Host: evil.example:" + port);
    assertThat(reply.status()).isEqualTo(row.status());
    assertThat(server.counter.entries() - entriesBefore).as("reachesFilter").isZero();
    assertThat(server.reads() - readsBefore).isZero();
    assertThat(reply.text()).doesNotContain("evil.example").doesNotContain("request_refused");
    for (String secret : server.secrets()) {
      assertThat(reply.text()).doesNotContain(secret);
    }
  }
}
