package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * WP02 T005 criterion 8, the real proof (WP10 T053 step 8): the operations of the contract that this service does not implement
 * answer 404 exactly like any unknown path, not 501 and not a stub's Problem.
 */
class OutOfScopeRoutesTest {

  static final List<String> OUT_OF_SCOPE =
      List.of(
          "/api/v1/drift",
          "/api/v1/ops/invocations");

  @Test
  void everyOutOfScopeOperationAnswersLikeAnUnknownPath() {
    FilesystemFixtureFactory.Built built = RouteSupport.pair(RouteSupport.moves(1, 1));
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response unknown = server.get("/api/v1/nope");
      assertThat(unknown.status()).isEqualTo(404);
      for (String path : OUT_OF_SCOPE) {
        HttpHarness.Response response = server.get(path);
        assertThat(response.status()).as(path).isEqualTo(404);
        assertThat(response.header("Content-Type")).as(path).isEqualTo(unknown.header("Content-Type"));
        assertThat(RouteSupport.tree(response).get("status").asInt()).as(path).isEqualTo(404);
        assertThat(RouteSupport.tree(response).has("code")).as(path + " is not a stub's Problem").isFalse();
      }
    }
  }

  /** AC-18.2, the final form: the five detail routes are served by the production application over a fixture Mission, and drift and Ops (above) are not. */
  static final List<String> DETAIL_ROUTES =
      List.of(
          "/api/v1/missions/" + Rows.ALPHA_ID,
          "/api/v1/missions/" + Rows.ALPHA_ID + "/work-packages/WP01",
          "/api/v1/missions/" + Rows.ALPHA_ID + "/work-packages/WP01/detail",
          "/api/v1/missions/" + Rows.ALPHA_ID + "/artifacts",
          "/api/v1/missions/" + Rows.ALPHA_ID + "/artifacts/content?path=spec.md");

  @Test
  void theFiveDetailRoutesAreServedForAFixtureMissionAndAnUnknownMissionIsStillAProblemNotAnUnknownPath() {
    DetailFixture fixture = DetailRoute.fixture(root -> DetailRoute.write(root, "spec.md", "# Spec\n"));
    try (HttpHarness server = HttpHarness.startWired(fixture.root())) {
      HttpHarness.Response unknown = server.get("/api/v1/nope");
      for (String path : DETAIL_ROUTES) {
        HttpHarness.Response response = server.get(path);
        assertThat(response.status()).as(path).isEqualTo(200);
        assertThat(response.header("Content-Type")).as(path).isNotEqualTo(unknown.header("Content-Type"));
      }
      HttpHarness.Response missing = server.get("/api/v1/missions/00000000000000000000000000/artifacts");
      assertThat(missing.status()).isEqualTo(404);
      assertThat(RouteSupport.tree(missing).get("code").asText()).as("a coded not_found of the route, unlike an unknown path").isEqualTo("not_found");
    }
  }

  @Test
  void aPathOutsideThePrefixIsNotServed() {
    FilesystemFixtureFactory.Built built = RouteSupport.pair(RouteSupport.moves(1, 1));
    try (HttpHarness server = HttpHarness.start(built)) {
      assertThat(server.get("/project").status()).isEqualTo(404);
      assertThat(server.get("/missions").status()).isEqualTo(404);
      assertThat(server.get("/").status()).isEqualTo(404);
    }
  }
}
