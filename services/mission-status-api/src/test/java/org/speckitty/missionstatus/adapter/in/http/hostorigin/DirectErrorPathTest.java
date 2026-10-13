package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.http.RawClient;

/**
 * Landing fold A6: a request that names the container's error page directly carries no error status, because nothing sent it there. It is an
 * unknown path like any other, a 404 Problem, never a 500 that a monitor probing unknown paths would read as a server fault. Nothing of the
 * request is echoed.
 */
class DirectErrorPathTest {

  @Test
  void aDirectRequestForTheErrorPageIsA404Problem() {
    try (HostOriginRig server = HostOriginRig.start()) {
      for (String route : new String[] {"/error", "/error?x=1"}) {
        RawClient.Reply reply = server.send("GET " + route + " HTTP/1.1", "Host: 127.0.0.1:" + server.port());
        assertThat(reply.status()).as(route).isEqualTo(404);
        assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json");
        assertThat(HostOriginRig.body(reply)).contains("\"status\":404").doesNotContain("internal_error").doesNotContain("x=1");
      }
    }
  }

  @Test
  void anErrorTheContainerRoutesThereKeepsItsStatus() {
    try (HostOriginRig server = HostOriginRig.start()) {
      RawClient.Reply reply = server.send("TRACE /api/v1/project HTTP/1.1", "Host: 127.0.0.1:" + server.port());
      assertThat(reply.status()).isEqualTo(405);
    }
  }
}
