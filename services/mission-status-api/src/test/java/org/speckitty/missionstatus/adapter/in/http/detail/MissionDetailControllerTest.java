package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The HTTP edge of {@code getMission} (T093 step 6): the body shape and content type, the foreign Host or Origin refused before any read
 * (row C1), and the controller's own contract: it parses the identifier into a typed value, makes one call to the port and maps nothing
 * itself (an empty parse is {@link DetailRefusal#notFound()}, never a 400).
 */
class MissionDetailControllerTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static DetailFixture fixture() {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, "2026-09-01T10:00:00+00:00", Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed"))),
        root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One")));
  }

  @Test
  void a200CarriesTheDetailAsJsonWithTheContractMembers() {
    try (HttpHarness server = MissionDetailRowsTest.serve(fixture())) {
      HttpHarness.Response response = server.get(MissionDetailServedRoute.path(Rows.ALPHA_ID));

      assertThat(response.status()).isEqualTo(200);
      assertThat(response.header("Content-Type")).startsWith("application/json");
      JsonNode body = JSON.readTree(response.body());
      assertThat(body.get("missionId").asString()).isEqualTo(Rows.ALPHA_ID);
      assertThat(body.get("phases")).hasSize(5);
      assertThat(body.get("workPackages")).hasSize(1);
      assertThat(body.get("workPackages").get(0).get("wpId").asString()).isEqualTo("WP01");
      assertThat(body.get("workPackages").get(0).get("statusLane").asString()).isEqualTo("claimed");
      assertThat(body.get("wpTotal").asInt()).isEqualTo(1);
    }
  }

  @Test
  void aForeignHostAndAForeignOriginAreRefusedBeforeAnyRead() {
    DetailFixture fixture = fixture();
    try (HttpHarness server = MissionDetailRowsTest.serve(fixture)) {
      fixture.recorder().clear();
      String target = MissionDetailServedRoute.path(Rows.ALPHA_ID);

      RawClient.Reply host = server.raw("GET " + target + " HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n");
      RawClient.Reply origin = server.raw("GET " + target + " HTTP/1.1\r\nHost: " + server.host() + "\r\nOrigin: http://evil.example\r\nConnection: close\r\n\r\n");

      for (RawClient.Reply reply : List.of(host, origin)) {
        assertThat(reply.status()).isEqualTo(403);
        assertThat(reply.text()).contains("request_refused");
      }
      assertThat(fixture.recorder().accesses()).as("row C1: zero reads recorded").isEmpty();
      assertThat(fixture.diagnostics()).isEmpty();
    }
  }

  @Test
  void theControllerParsesTheIdentifierAndMakesOneCallToThePort() {
    List<MissionId> asked = new java.util.ArrayList<>();
    MissionDetailQuery spy =
        missionId -> {
          asked.add(missionId);
          throw DetailRefusal.notFound();
        };
    DetailFixture fixture = fixture();
    try (HttpHarness server = HttpHarness.startWith(fixture.built(), Map.of(MissionDetailQuery.class, spy))) {
      assertThat(server.get(MissionDetailServedRoute.path(Rows.ALPHA_ID)).status()).isEqualTo(404);
      assertThat(server.get(MissionDetailServedRoute.path("not-a-ulid")).status()).as("an empty parse is a refusal, the port is not called").isEqualTo(404);
    }

    assertThat(asked).containsExactly(new MissionId(Rows.ALPHA_ID));
  }

  @Test
  void theDetailRecordThePortReturnsIsTheOneTheBodyIsShapedFrom() {
    DetailFixture fixture = fixture();
    MissionDetail detail = MissionDetailRowsTest.serviceOver(fixture).mission(new MissionId(Rows.ALPHA_ID));

    var model = MissionDetailMapper.detail(detail);

    assertThat(model.getMissionId()).isEqualTo(detail.overview().missionId().value());
    assertThat(model.getPhases()).hasSize(detail.phases().size());
    assertThat(model.getWorkPackages()).hasSize(detail.workPackages().size());
  }
}
