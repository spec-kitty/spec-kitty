package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;
import jakarta.servlet.ServletException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.in.http.HostOriginFilter;
import org.speckitty.missionstatus.adapter.in.http.HostOriginRefusal;
import org.speckitty.missionstatus.adapter.in.http.OwnPortSource;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import tools.jackson.databind.json.JsonMapper;

/**
 * The decision of the filter in isolation (a fixed own port), for values a real client cannot send through the container, the constant of
 * the refusal, and the scope of that constant. The real-socket tables are {@link HostTableTest} and {@link OriginTableTest}.
 */
class HostOriginFilterTest {

  private static final int PORT = 43210;
  private static final OwnPortSource OWN = () -> PORT;

  private final HostOriginFilter filter = new HostOriginFilter(OWN, JsonMapper.builder().build());

  private record Outcome(int status, boolean passed, String body, String contentType) {}

  private Outcome run(String host, String origin, String... extraHeaders) throws ServletException, IOException {
    MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/project");
    if (host != null) {
      request.addHeader("Host", host);
    }
    if (origin != null) {
      request.addHeader("Origin", origin);
    }
    for (int i = 0; i + 1 < extraHeaders.length; i += 2) {
      request.addHeader(extraHeaders[i], extraHeaders[i + 1]);
    }
    MockHttpServletResponse response = new MockHttpServletResponse();
    AtomicInteger passed = new AtomicInteger();
    filter.doFilter(request, response, new MockFilterChain() {
      @Override
      public void doFilter(jakarta.servlet.ServletRequest req, jakarta.servlet.ServletResponse res) {
        passed.incrementAndGet();
      }
    });
    return new Outcome(response.getStatus(), passed.get() == 1, response.getContentAsString(StandardCharsets.UTF_8), response.getContentType());
  }

  @Test
  void theRefusalConstantIs403() {
    assertThat(HostOriginRefusal.STATUS).isEqualTo(403);
  }

  @ParameterizedTest
  @ValueSource(strings = {"127.0.0.1:43210", "localhost:43210"})
  void theTwoAcceptedHostFormsPassWithAndWithoutAnAcceptedOrigin(String host) throws Exception {
    assertThat(run(host, null).passed()).isTrue();
    assertThat(run(host, "http://127.0.0.1:43210").passed()).isTrue();
    assertThat(run(host, "http://localhost:43210").passed()).isTrue();
  }

  @ParameterizedTest
  @ValueSource(strings = {"127.0.0.1:43211", "127.0.0.1:4321", "127.0.0.1:043210", "127.0.0.1:43210 ", " 127.0.0.1:43210", "127.0.0.1:43210:1", "localhost:+43210", "[::1]:43210", "0.0.0.0:43210", "127.0.0.2:43210", "LOCALHOST:43210", "Localhost:43210", "localhost.:43210", "127.0.0.1.:43210", "", "evil.example"})
  void everyOtherHostIsRefusedWithoutReachingTheChain(String host) throws Exception {
    Outcome outcome = run(host, null);
    assertThat(outcome.status()).isEqualTo(403);
    assertThat(outcome.passed()).isFalse();
  }

  @Test
  void anAbsentHostIsRefused() throws Exception {
    Outcome outcome = run(null, null);
    assertThat(outcome.status()).isEqualTo(403);
    assertThat(outcome.passed()).isFalse();
  }

  @Test
  void theProxyHeadersAreRefusedEvenWithAnAcceptedHost() throws Exception {
    assertThat(run("127.0.0.1:43210", null, "Forwarded", "for=1.2.3.4").status()).isEqualTo(403);
    assertThat(run("127.0.0.1:43210", null, "X-Forwarded-Host", "127.0.0.1:43210").status()).isEqualTo(403);
    assertThat(run("127.0.0.1:43210", null, "X-Forwarded-Host", "").status()).isEqualTo(403);
  }

  @Test
  void aSecondOriginValueThatIsForeignIsRefused() throws Exception {
    Outcome outcome = run("127.0.0.1:43210", "http://127.0.0.1:43210", "Origin", "https://evil.example");
    assertThat(outcome.status()).isEqualTo(403);
    assertThat(outcome.passed()).isFalse();
  }

  @ParameterizedTest
  @ValueSource(strings = {"null", "", "https://127.0.0.1:43210", "http://127.0.0.1:43211", "http://127.0.0.1", "http://127.0.0.1:43210/", "http://127.0.0.1:43210/x", "http://127.0.0.1.evil.example:43210", "http://user@127.0.0.1:43210", "HTTP://127.0.0.1:43210", "http://LOCALHOST:43210", "http://[::1]:43210", "file://"})
  void everyOtherOriginIsRefused(String origin) throws Exception {
    Outcome outcome = run("127.0.0.1:43210", origin);
    assertThat(outcome.status()).isEqualTo(403);
    assertThat(outcome.passed()).isFalse();
  }

  @Test
  void aPortNotYetKnownRefusesEverything() throws Exception {
    HostOriginFilter beforeBind = new HostOriginFilter(() -> -1, JsonMapper.builder().build());
    MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/project");
    request.addHeader("Host", "127.0.0.1:-1");
    MockHttpServletResponse response = new MockHttpServletResponse();
    beforeBind.doFilter(request, response, new MockFilterChain());
    assertThat(response.getStatus()).isEqualTo(403);
  }

  @ParameterizedTest
  @ValueSource(strings = {"evil.example\" onload=\"x", "<script>alert(1)</script>.example:43210", "café-marker.example", "evil\u0001marker.example", "marker.example\\u0000"})
  void aRefusalCarriesNeitherTheHostNorTheOriginBackInAnyForm(String foreign) throws Exception {
    for (Outcome outcome : List.of(run(foreign, null), run("127.0.0.1:43210", foreign), run("127.0.0.1:43210", null, "X-Forwarded-Host", foreign))) {
      assertThat(outcome.status()).isEqualTo(403);
      assertThat(outcome.body()).doesNotContain("marker").doesNotContain("evil").doesNotContain("script").doesNotContain("onload").doesNotContain("caf");
      assertThat(outcome.contentType()).startsWith("application/problem+json");
    }
  }

  @Test
  void theBodyIsTheSharedProblemWithOneTrailingNewline() throws Exception {
    Outcome outcome = run("evil.example", null);
    assertThat(outcome.body()).isEqualTo("{\"code\":\"request_refused\",\"status\":403,\"title\":\"Request refused\"}\n");
  }

  @Test
  void anErrorDispatchIsGuardedAndARequestThatAlreadyPassedPassesItsErrorRedispatchOnce() throws Exception {
    // a foreign Host on an ERROR dispatch (the container's own sendError) is refused
    MockHttpServletRequest foreign = new MockHttpServletRequest("TRACE", "/api/v1/project");
    foreign.setDispatcherType(jakarta.servlet.DispatcherType.ERROR);
    foreign.setAttribute("jakarta.servlet.error.request_uri", "/api/v1/project");
    foreign.addHeader("Host", "evil.example");
    MockHttpServletResponse refused = new MockHttpServletResponse();
    AtomicInteger passed = new AtomicInteger();
    filter.doFilter(foreign, refused, new MockFilterChain() {
      @Override
      public void doFilter(jakarta.servlet.ServletRequest req, jakarta.servlet.ServletResponse res) {
        passed.incrementAndGet();
      }
    });
    assertThat(refused.getStatus()).isEqualTo(403);
    assertThat(passed.get()).isZero();

    // an accepted request: the REQUEST pass, then its ERROR redispatch on the same request: both pass, neither is refused
    MockHttpServletRequest accepted = new MockHttpServletRequest("GET", "/api/v1/x");
    accepted.addHeader("Host", "127.0.0.1:43210");
    MockHttpServletResponse first = new MockHttpServletResponse();
    filter.doFilter(accepted, first, new MockFilterChain() {
      @Override
      public void doFilter(jakarta.servlet.ServletRequest req, jakarta.servlet.ServletResponse res) {
        passed.incrementAndGet();
      }
    });
    accepted.setDispatcherType(jakarta.servlet.DispatcherType.ERROR);
    accepted.setAttribute("jakarta.servlet.error.request_uri", "/api/v1/x");
    MockHttpServletResponse second = new MockHttpServletResponse();
    filter.doFilter(accepted, second, new MockFilterChain() {
      @Override
      public void doFilter(jakarta.servlet.ServletRequest req, jakarta.servlet.ServletResponse res) {
        passed.incrementAndGet();
      }
    });
    assertThat(passed.get()).isEqualTo(2);
    assertThat(first.getStatus()).isEqualTo(200);
    assertThat(second.getStatus()).isEqualTo(200);
  }

  /** The constant governs the filter's refusals only: no other class of the service names it (AC-9b status-constant scope). */
  @Test
  void theRefusalConstantIsNamedByTheFilterAlone() throws IOException {
    Path main = Path.of("src", "main", "java");
    try (Stream<Path> walk = Files.walk(main)) {
      List<String> users =
          walk.filter(path -> path.toString().endsWith(".java"))
              .filter(
                  path -> {
                    try {
                      return Files.readString(path).contains("HostOriginRefusal");
                    } catch (IOException failure) {
                      throw new java.io.UncheckedIOException(failure);
                    }
                  })
              .map(path -> path.getFileName().toString())
              .sorted()
              .toList();
      assertThat(users).containsExactly("HostOriginFilter.java", "HostOriginRefusal.java");
    }
  }
}
