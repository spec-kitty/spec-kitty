package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Pre-merge fold F4 and landing fold A2: a query string with a malformed percent-encoding is a client error, answered with the 400 each
 * route DECLARES, never the 500 {@code internal_error} and never a code-less body: {@code invalid_page_cursor} on {@code /missions}
 * ({@code PageCursorRefused}), {@code misaligned} with a fixed detail on {@code /events} ({@code StreamRefused}). Both are validated
 * against the contract, and nothing of the request is echoed.
 */
class MalformedQueryTest {

  private static final ContractValidator CONTRACT = ContractValidator.fromClasspath();
  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static String accepted(HostOriginRig server) {
    return "Host: 127.0.0.1:" + server.port();
  }

  private static void assertProblemJson(RawClient.Reply reply, String route) {
    assertThat(reply.status()).as(route).isEqualTo(400);
    assertThat(reply.text()).containsIgnoringCase("Content-Type: application/problem+json");
  }

  @Test
  void aMalformedPercentEncodingOnMissionsIsTheDeclaredInvalidPageCursor() throws Exception {
    try (HostOriginRig server = HostOriginRig.start()) {
      for (String route : new String[] {"/api/v1/missions?pageCursor=%zz", "/api/v1/missions?pageSize=%zz", "/api/v1/missions?cursor=x&limit=%zz"}) {
        RawClient.Reply reply = server.send("GET " + route + " HTTP/1.1", accepted(server));
        assertProblemJson(reply, route);
        String body = HostOriginRig.body(reply);
        JsonNode problem = JSON.readTree(body);
        assertThat(problem.get("code").asString()).as(route).isEqualTo("invalid_page_cursor");
        assertThat(CONTRACT.validatePageCursorRefusal(body)).as(route + " against PageCursorRefused").isEmpty();
        assertThat(body).doesNotContain("internal_error").doesNotContain("%zz").doesNotContain("limit").doesNotContain("pageSize");
      }
    }
  }

  @Test
  void aMalformedPercentEncodingOnEventsIsTheDeclaredMisalignedWithAFixedDetail() throws Exception {
    try (HostOriginRig server = HostOriginRig.start()) {
      for (String route : new String[] {"/api/v1/events?missionId=%zz", "/api/v1/events?cursor=x&limit=%zz"}) {
        RawClient.Reply reply = server.send("GET " + route + " HTTP/1.1", accepted(server));
        assertProblemJson(reply, route);
        String body = HostOriginRig.body(reply);
        JsonNode problem = JSON.readTree(body);
        assertThat(problem.get("code").asString()).as(route).isEqualTo("misaligned");
        assertThat(problem.get("detail").asString()).as(route).isNotBlank();
        assertThat(CONTRACT.validateStreamRefusal(400, body)).as(route + " against StreamRefused").isEmpty();
        assertThat(body).doesNotContain("internal_error").doesNotContain("%zz").doesNotContain("limit").doesNotContain("missionId");
      }
    }
  }
}
