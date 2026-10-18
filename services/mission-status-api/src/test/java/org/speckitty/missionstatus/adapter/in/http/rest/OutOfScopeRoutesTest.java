package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * WP02 T005 criterion 8, the real proof (WP10 T053 step 8): the operations of the contract that this service does not implement
 * answer 404 exactly like any unknown path, not 501 and not a stub's Problem. The two artifact operations left this list when they
 * were implemented (#957); the five below remain.
 */
class OutOfScopeRoutesTest {

  static final List<String> OUT_OF_SCOPE =
      List.of(
          "/api/v1/missions/01J01000000000000000000001",
          "/api/v1/missions/01J01000000000000000000001/work-packages/WP01",
          "/api/v1/missions/01J01000000000000000000001/work-packages/WP01/detail",
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
