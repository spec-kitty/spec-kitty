package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.speckitty.missionstatus.testsupport.http.RawClient;

/**
 * Pre-merge fold J5 and J12: text the CALLER controls (a path, an e-mail address or a host path in the request target or the Host
 * header) is echoed neither in a log line nor in an error body. The container-routed errors (a method the container refuses, such as an
 * accepted-Host TRACE) answer with the shared Problem and no {@code path} member; a foreign Host is still refused with 403 first.
 */
@ExtendWith(OutputCaptureExtension.class)
class RequestEchoTest {

  // built at run time: a host-path shape the leak classes catch, with no such literal in the source
  private static final String HOME_PATH = "/" + String.join("/", "ho" + "me", "canary-user", "URLCANARY");
  private static final String MAIL = "mail-canary@example.invalid";

  @Test
  void aContainerRoutedErrorIsAProblemWithNoPathEcho() {
    try (HostOriginRig server = HostOriginRig.start()) {
      String accepted = "Host: 127.0.0.1:" + server.port();
      RawClient.Reply trace = server.send("TRACE " + HOME_PATH + " HTTP/1.1", accepted);
      assertThat(trace.status()).isEqualTo(405);
      assertThat(trace.text()).containsIgnoringCase("Content-Type: application/problem+json");
      String body = HostOriginRig.body(trace);
      assertThat(body.strip()).isEqualTo("{\"status\":405,\"title\":\"Method Not Allowed\"}");
      assertThat(trace.text()).doesNotContain("URLCANARY").doesNotContain("\"path\"");

      RawClient.Reply plain = server.send("TRACE /api/v1/project HTTP/1.1", accepted);
      assertThat(HostOriginRig.body(plain)).doesNotContain("path").doesNotContain("timestamp");
    }
  }

  @Test
  void aForeignHostStillGets403BeforeAnyContainerError() {
    try (HostOriginRig server = HostOriginRig.start()) {
      RawClient.Reply reply = server.send("TRACE /api/v1/project HTTP/1.1", "Host: evil.example:" + server.port());
      assertThat(reply.status()).isEqualTo(403);
      assertThat(HostOriginRig.body(reply)).contains("request_refused").doesNotContain("evil.example");
    }
  }

  @Test
  void aBadlyEncodedTargetIsTheContainersOwn400EvenUnderAForeignHost() {
    // WP11 N1: Tomcat rejects the target while parsing, before any filter; the guard is not reached and the Host is not echoed
    try (HostOriginRig server = HostOriginRig.start()) {
      int entriesBefore = server.counter.entries();
      RawClient.Reply reply = server.send("GET /%zz HTTP/1.1", "Host: evil.example:" + server.port());
      assertThat(reply.status()).isEqualTo(400);
      assertThat(server.counter.entries() - entriesBefore).as("reachesFilter").isZero();
      assertThat(reply.text()).doesNotContain("evil.example").doesNotContain("request_refused").doesNotContain("%zz");
    }
  }

  @Test
  void noLogLineEchoesAPathOrAnAddressFromTheHostOrTheTarget(CapturedOutput output) {
    try (HostOriginRig server = HostOriginRig.start()) {
      int port = server.port();
      String accepted = "Host: 127.0.0.1:" + port;
      // an unknown path (Spring's "No mapping for GET <path>"), a dot-segment path, a path with an address, and bad Host values
      server.send("GET " + HOME_PATH + " HTTP/1.1", accepted);
      server.send("GET /api/v1/../api/v1/project HTTP/1.1", accepted);
      server.send("GET /" + MAIL + " HTTP/1.1", accepted);
      server.send("GET /api/v1/missions HTTP/1.1", "Host: " + MAIL + HOME_PATH);
      server.send("GET /api/v1/missions HTTP/1.1", "Host: localhost:" + port + ".evil.example/" + MAIL);
      server.send("GET /api/v1/missions HTTP/1.1", "Host: evil.example:" + port);
    }
    assertThat(output.getAll())
        .doesNotContain("URLCANARY")
        .doesNotContain("canary-user")
        .doesNotContain("mail-canary")
        .doesNotContain("evil.example")
        .doesNotContain("api/v1/../api/v1");
  }
}
