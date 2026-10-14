package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.function.IntFunction;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * AC-9c: each foreign Origin, sent with an accepted Host on the five request targets, answers the refusal constant 403 and enters the
 * filter, with no CORS header and no Mission read. AC-9d: the accepted controls (both Host forms, with no Origin and with each accepted
 * Origin) answer 200 on {@code /api/v1/project}, so the guard is shown not to over-refuse.
 */
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class OriginTableTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  private record Row(String name, IntFunction<String> origin, String marker) {
    @Override
    public String toString() {
      return name;
    }
  }

  private static final List<Row> ORIGINS =
      List.of(
          new Row("https://evil.example", p -> "https://evil.example", "evil.example"),
          new Row("null", p -> "null", null),
          new Row("http://127.0.0.1:port+1", p -> "http://127.0.0.1:" + (p + 1), null),
          new Row("http://127.0.0.1.evil.example:port", p -> "http://127.0.0.1.evil.example:" + p, "evil.example"),
          new Row("https://127.0.0.1:port (wrong scheme)", p -> "https://127.0.0.1:" + p, "https://"),
          // beyond AC-9c, same constant: no port, a path, a trailing slash, upper-case scheme, the other loopback name with a wrong port
          new Row("http://127.0.0.1 (no port)", p -> "http://127.0.0.1", null),
          new Row("http://127.0.0.1:port/ (trailing slash)", p -> "http://127.0.0.1:" + p + "/", null),
          new Row("HTTP://127.0.0.1:port (upper-case scheme)", p -> "HTTP://127.0.0.1:" + p, "HTTP://"),
          new Row("http://localhost:port+1", p -> "http://localhost:" + (p + 1), null),
          new Row("http://[::1]:port", p -> "http://[::1]:" + p, "[::1]"),
          new Row("empty Origin", p -> "", null));

  static Stream<Arguments> cases() {
    return ORIGINS.stream().flatMap(row -> HostOriginRig.TARGETS.stream().map(target -> Arguments.of(row, target)));
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

  @ParameterizedTest(name = "Origin {0} on {1}")
  @MethodSource("cases")
  void aForeignOriginWithAnAcceptedHostIsRefused(Row row, String target) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    RawClient.Reply reply = server.send("GET " + target + " HTTP/1.1", "Host: 127.0.0.1:" + port, "Origin: " + row.origin().apply(port));

    assertThat(reply.status()).as("status").isEqualTo(403);
    assertThat(server.counter.entries() - entriesBefore).as("reachesFilter").isEqualTo(1);
    assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json");
    assertThat(reply.text()).doesNotContainIgnoringCase("Access-Control-");
    assertThat(reply.text()).doesNotContainIgnoringCase("text/event-stream");
    JsonNode problem = JSON.readTree(HostOriginRig.body(reply));
    assertThat(problem.get("code").asString()).isEqualTo("request_refused");
    assertThat(problem.get("status").asInt()).isEqualTo(403);
    assertThat(problem.has("detail")).isFalse();
    assertThat(server.reads() - readsBefore).as("Mission reads and port calls").isZero();
    for (String secret : server.secrets()) {
      assertThat(reply.text()).doesNotContain(secret);
    }
    if (row.marker() != null) {
      assertThat(reply.text()).as("no echo of the foreign Origin").doesNotContain(row.marker());
    }
  }

  static Stream<Arguments> fetchSites() {
    return Stream.concat(
        HostOriginRig.TARGETS.stream().map(target -> Arguments.of(target, "cross-site", 403)),
        Stream.of("same-origin", "same-site", "none").map(site -> Arguments.of("/api/v1/project", site, 200)));
  }

  /** A browser sends no Origin on a cross-site GET: Sec-Fetch-Site says where the request came from. Non-browser clients send none. */
  @ParameterizedTest(name = "Sec-Fetch-Site {1} on {0}")
  @MethodSource("fetchSites")
  void aCrossSiteFetchIsRefusedWhateverTheOriginAndTheOtherSitesPass(String target, String site, int status) {
    int port = server.port();
    int readsBefore = server.reads();
    RawClient.Reply reply = server.send("GET " + target + " HTTP/1.1", "Host: 127.0.0.1:" + port, "Sec-Fetch-Site: " + site);
    assertThat(reply.status()).isEqualTo(status);
    if (status == 403) {
      assertThat(server.reads() - readsBefore).as("Mission reads and port calls").isZero();
    }
  }

  @Test
  void aForeignOriginWithAForeignHostIsAlsoOneRefusal() {
    int port = server.port();
    RawClient.Reply reply = server.send("GET /api/v1/project HTTP/1.1", "Host: evil.example:" + port, "Origin: https://evil.example");
    assertThat(reply.status()).isEqualTo(403);
    assertThat(HostOriginRig.body(reply)).doesNotContain("evil.example");
  }

  // AC-9d: the accepted controls

  static Stream<Arguments> controls() {
    return Stream.of("127.0.0.1", "localhost")
        .flatMap(
            host ->
                Stream.of(
                    Arguments.of(host, "no Origin", (IntFunction<String>) null),
                    Arguments.of(host, "Origin http://127.0.0.1:port", (IntFunction<String>) p -> "http://127.0.0.1:" + p),
                    Arguments.of(host, "Origin http://localhost:port", (IntFunction<String>) p -> "http://localhost:" + p)));
  }

  @ParameterizedTest(name = "Host {0}:port, {1}")
  @MethodSource("controls")
  void theAcceptedFormsAreAnswered200(String host, String label, IntFunction<String> origin) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    String[] headers = origin == null ? new String[] {"Host: " + host + ":" + port} : new String[] {"Host: " + host + ":" + port, "Origin: " + origin.apply(port)};
    RawClient.Reply reply = server.send("GET /api/v1/project HTTP/1.1", headers);
    assertThat(reply.status()).as(label).isEqualTo(200);
    assertThat(server.counter.entries() - entriesBefore).as("the control enters the filter and passes").isEqualTo(1);
    assertThat(reply.text()).doesNotContainIgnoringCase("Access-Control-Allow");
  }

  static Stream<Arguments> streamControls() {
    return Stream.of("127.0.0.1", "localhost")
        .flatMap(host -> Stream.of("", "http://127.0.0.1:%d", "http://localhost:%d").map(origin -> Arguments.of(host, origin)));
  }

  @ParameterizedTest(name = "stream control, Host {0}:port, Origin {1}")
  @MethodSource("streamControls")
  void theStreamRouteOpensForTheAcceptedFormsOnly(String host, String originPattern) throws java.io.IOException {
    int port = server.port();
    try (java.net.Socket socket = new java.net.Socket("127.0.0.1", port)) {
      socket.setSoTimeout(5000);
      String origin = originPattern.isEmpty() ? "" : "Origin: " + originPattern.formatted(port) + "\r\n";
      socket.getOutputStream().write(("GET /api/v1/events HTTP/1.1\r\nHost: " + host + ":" + port + "\r\nAccept: text/event-stream\r\n" + origin + "\r\n").getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
      socket.getOutputStream().flush();
      StringBuilder head = new StringBuilder();
      java.io.InputStream in = socket.getInputStream();
      while (!head.toString().contains("\r\n\r\n")) {
        int next = in.read();
        if (next < 0) {
          break;
        }
        head.append((char) next);
      }
      assertThat(head.toString()).startsWith("HTTP/1.1 200");
      assertThat(head.toString().toLowerCase()).contains("content-type: text/event-stream");
    }
  }

  @Test
  void theOwnPortIsTheBoundPortOfAServerConfiguredWithPortZero() {
    assertThat(server.stream().http.context().getEnvironment().getProperty("server.port")).isEqualTo("0");
    assertThat(server.port()).isPositive();
    RawClient.Reply onLocalhost = server.send("GET /api/v1/project HTTP/1.1", "Host: localhost:" + server.port());
    assertThat(onLocalhost.status()).isEqualTo(200);
  }

  static Stream<Arguments> twoOrigins() {
    return HostOriginRig.TARGETS.stream().flatMap(t -> Stream.of(Arguments.of(t, true), Arguments.of(t, false)));
  }

  @ParameterizedTest(name = "two Origin headers on {0}, good first: {1}")
  @MethodSource("twoOrigins")
  void aSecondOriginHeaderIsChecked(String target, boolean goodFirst) {
    int port = server.port();
    int entriesBefore = server.counter.entries();
    int readsBefore = server.reads();
    String good = "Origin: http://127.0.0.1:" + port;
    String bad = "Origin: https://evil.example";
    RawClient.Reply reply = server.send("GET " + target + " HTTP/1.1", "Host: 127.0.0.1:" + port, goodFirst ? good : bad, goodFirst ? bad : good);
    assertThat(reply.status()).isEqualTo(403);
    assertThat(server.counter.entries() - entriesBefore).isEqualTo(1);
    assertThat(server.reads() - readsBefore).isZero();
    assertThat(reply.text()).doesNotContain("evil.example");
  }
}
