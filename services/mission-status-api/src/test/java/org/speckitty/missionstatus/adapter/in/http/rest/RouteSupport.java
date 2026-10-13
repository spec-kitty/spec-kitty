package org.speckitty.missionstatus.adapter.in.http.rest;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/** Shared helpers of the REST suites: fixtures built as trees, a JSON reader and the checks every Problem body must pass. */
final class RouteSupport {

  static final JsonMapper JSON = JsonMapper.builder().build();
  static final String ALPHA_ID = Rows.ALPHA_ID;
  static final String BETA_ID = Rows.BETA_ID;

  private RouteSupport() {}

  static String moves(int fromId, int count) {
    StringBuilder text = new StringBuilder();
    for (int i = 0; i < count; i++) {
      text.append(Rows.status(Rows.id(fromId + i), String.format("2026-09-01T10:%02d:00Z", i), "WP" + String.format("%02d", i + 1), "planned", "claimed"));
    }
    return text.toString();
  }

  /** Alpha (older) with the given ledger text, beta (newer) healthy. */
  static FilesystemFixtureFactory.Built pair(String alphaLedger) {
    return FilesystemFixtureFactory.fromSpec(
        FixtureSpec.of(
            PortFixtures.mission("alpha", ALPHA_ID, PortFixtures.CREATED, alphaLedger),
            PortFixtures.mission("beta", BETA_ID, "2026-09-03T10:00:00+00:00", moves(20, 1))));
  }

  static JsonNode tree(HttpHarness.Response response) {
    return JSON.readTree(response.body());
  }

  /** The members of a Problem body that every non-2xx answer must hold, and nothing that names a path. */
  static void assertProblem(HttpHarness.Response response, int status, String code, FilesystemFixtureFactory.Built built) {
    org.assertj.core.api.Assertions.assertThat(response.status()).isEqualTo(status);
    org.assertj.core.api.Assertions.assertThat(response.header("Content-Type")).startsWith("application/problem+json");
    JsonNode body = tree(response);
    org.assertj.core.api.Assertions.assertThat(body.get("status").asInt()).isEqualTo(status);
    org.assertj.core.api.Assertions.assertThat(body.get("title").asString()).isNotBlank();
    if (code != null) {
      org.assertj.core.api.Assertions.assertThat(body.get("code").asString()).isEqualTo(code);
    }
    List<String> forbidden = new ArrayList<>();
    forbidden.add(System.getProperty("user.home"));
    if (System.getenv("HOME") != null) {
      forbidden.add(System.getenv("HOME"));
    }
    if (built != null) {
      forbidden.add(built.root().toString());
    }
    forbidden.add("kitty-specs");
    forbidden.add("status.events.jsonl");
    String text = new String(response.body(), StandardCharsets.UTF_8);
    for (String needle : forbidden) {
      org.assertj.core.api.Assertions.assertThat(text).as("body must not carry " + (needle.length() > 12 ? "a path" : needle)).doesNotContain(needle);
    }
  }
}
