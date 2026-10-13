package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;

/** AC-1b, AC-1c, AC-2b and AC-2c over HTTP: the project header under a missing metadata file, the count across pages, paging and cursors. */
class ProjectAndPagingTest {

  private static FilesystemFixtureFactory.Built several(int n) {
    List<FixtureSpec.Mission> missions = new ArrayList<>();
    for (int i = 1; i <= n; i++) {
      missions.add(PortFixtures.mission("mission-" + i, PortFixtures.missionId(i), String.format("2026-09-%02dT10:00:00+00:00", i), RouteSupport.moves(100 * i, 2)));
    }
    return FilesystemFixtureFactory.fromSpec(FixtureSpec.of(missions.toArray(FixtureSpec.Mission[]::new)));
  }

  @Test
  void ac1bAMissingMetadataFileIsA200WithANullSchemaVersionAndNoHealthyBadge() throws IOException {
    var fixture = ConformanceTree.fixtures().stream().filter(f -> f.key().equals("project-header/healthy")).findFirst().orElseThrow();
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTreeRecording(fixture.dir());
    Files.delete(built.root().resolve(".kittify/metadata.yaml"));
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/project");
      assertThat(response.status()).isEqualTo(200);
      JsonNode body = RouteSupport.tree(response);
      assertThat(body.get("schemaVersion").isNull()).isTrue();
      assertThat(body.get("health").asString()).isNotEqualTo("healthy");
    }
  }

  @Test
  void ac1cMissionCountEqualsTheItemsAcrossAllPagesAtPageSizeOne() {
    FilesystemFixtureFactory.Built built = several(5);
    try (HttpHarness server = HttpHarness.start(built)) {
      int items = 0;
      String cursor = null;
      do {
        HttpHarness.Response response = server.get("/api/v1/missions?pageSize=1" + (cursor == null ? "" : "&pageCursor=" + cursor));
        assertThat(response.status()).isEqualTo(200);
        JsonNode page = RouteSupport.tree(response);
        items += page.get("items").size();
        JsonNode next = page.get("pageInfo").get("nextPageCursor");
        cursor = next.isNull() ? null : next.asString();
        assertThat(page.get("pageInfo").get("hasNextPage").asBoolean()).isEqualTo(cursor != null);
      } while (cursor != null);
      assertThat(items).isEqualTo(5);
      assertThat(RouteSupport.tree(server.get("/api/v1/project")).get("missionCount").asInt()).isEqualTo(items);
    }
  }

  @Test
  void aControlCursorFromARealPageReturnsTheNextPage() {
    FilesystemFixtureFactory.Built built = several(3);
    try (HttpHarness server = HttpHarness.start(built)) {
      JsonNode first = RouteSupport.tree(server.get("/api/v1/missions?pageSize=1"));
      String cursor = first.get("pageInfo").get("nextPageCursor").asString();
      HttpHarness.Response second = server.get("/api/v1/missions?pageSize=1&pageCursor=" + cursor);
      assertThat(second.status()).isEqualTo(200);
      assertThat(RouteSupport.tree(second).get("items").get(0).get("missionId").asString()).isNotEqualTo(first.get("items").get(0).get("missionId").asString());
    }
  }

  @ParameterizedTest
  @ValueSource(strings = {"x", "!!!", "v1.", "v1.AAAA", "v2.AAAA", "AAAAAAAA", "%20", "v1.%E2%82%AC"})
  void ac2cEightForgedCursorValuesAreA400InvalidPageCursor(String forged) {
    FilesystemFixtureFactory.Built built = several(2);
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions?pageCursor=" + forged);
      RouteSupport.assertProblem(response, 400, "invalid_page_cursor", built);
    }
  }

  @Test
  void anEmptyAndAnOverlongCursorAreRefusedToo() {
    FilesystemFixtureFactory.Built built = several(2);
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/missions?pageCursor="), 400, "invalid_page_cursor", built);
      RouteSupport.assertProblem(server.get("/api/v1/missions?pageCursor=" + "A".repeat(5000)), 400, "invalid_page_cursor", built);
    }
  }

  @ParameterizedTest
  @ValueSource(strings = {"0:1", "-5:1", "1:1", "200:200", "201:200", "100000:200", "99999999999:200", "-99999999999:1", "2147483648:200", "-2147483649:1", "007:7", "%2B5:5", "-0:1"})
  void thePageSizeIsClampedAtBothEndsAndNeverRefused(String pair) {
    String[] parts = pair.split(":");
    FilesystemFixtureFactory.Built built = several(3);
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions?pageSize=" + parts[0]);
      assertThat(response.status()).isEqualTo(200);
      assertThat(RouteSupport.tree(response).get("pageInfo").get("pageSize").asInt()).isEqualTo(Integer.parseInt(parts[1]));
    }
  }

  @Test
  void anAbsentPageSizeIsTheDefaultOfFifty() {
    FilesystemFixtureFactory.Built built = several(2);
    try (HttpHarness server = HttpHarness.start(built)) {
      assertThat(RouteSupport.tree(server.get("/api/v1/missions")).get("pageInfo").get("pageSize").asInt()).isEqualTo(50);
    }
  }

  /**
   * Operator ruling (analyze.ruling.md, 2026-10-12): a pageSize that is not an integer is treated as absent. An integer is an optional sign
   * and ASCII digits, nothing else: no spaces (a space encoded as %20 or + makes it text), no fraction, no exponent, no hex. A plus sign is
   * a sign (%2B5 is 5).
   */
  @ParameterizedTest
  @ValueSource(strings = {"abc", "1.5", "1e3", "%205", "5%20", "+5", "0x10", "%EF%BC%95", "", "--5", "5-", "1_000"})
  void aPageSizeThatIsNotAnIntegerIsTreatedAsAbsentAndServesTheDefault(String text) {
    FilesystemFixtureFactory.Built built = several(2);
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions?pageSize=" + text);
      assertThat(response.status()).isEqualTo(200);
      assertThat(RouteSupport.tree(response).get("pageInfo").get("pageSize").asInt()).isEqualTo(50);
      assertThat(org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator.fromClasspath().validateMissions(response.text())).isEmpty();
    }
  }

  @Test
  void everyPageSizeAnswerIsValidAgainstTheContract() {
    FilesystemFixtureFactory.Built built = several(2);
    var validator = org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator.fromClasspath();
    try (HttpHarness server = HttpHarness.start(built)) {
      for (String size : new String[] {"1", "99999999999", "-99999999999", "abc", "%2B5"}) {
        assertThat(validator.validateMissions(server.get("/api/v1/missions?pageSize=" + size).text())).as(size).isEmpty();
      }
    }
  }

  @Test
  void aNonGetMethodIsAProblem405() {
    FilesystemFixtureFactory.Built built = several(1);
    try (HttpHarness server = HttpHarness.start(built)) {
      var reply = server.raw("POST /api/v1/project HTTP/1.1\r\nHost: " + server.host() + "\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
      assertThat(reply.status()).isEqualTo(405);
      assertThat(reply.text()).contains("application/problem+json");
    }
  }

  @Test
  void theBodiesEndWithOneNewlineAndAreCompact() {
    FilesystemFixtureFactory.Built built = several(1);
    try (HttpHarness server = HttpHarness.start(built)) {
      for (String path : new String[] {"/api/v1/project", "/api/v1/missions"}) {
        String text = server.get(path).text();
        assertThat(text).endsWith("}\n").doesNotContain("\n  ").doesNotContain(": ");
      }
    }
  }
}
