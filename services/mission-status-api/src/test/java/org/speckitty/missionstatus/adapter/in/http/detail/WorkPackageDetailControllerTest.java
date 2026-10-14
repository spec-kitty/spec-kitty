package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ID;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.fixture;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.path;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.serve;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The HTTP edge of {@code getWorkPackageDetail}: the body shape and content type, the foreign Host or Origin refused before any read (row C1), and
 * the controller's own contract: it parses the two identifiers into typed values, makes one call to the port and maps nothing itself (an empty
 * parse is {@link DetailRefusal#notFound()}, never a 400). The last test starts the production application with its own wiring, which is the
 * only place the {@code WorkPackageDetailWiring} bean is built and the one that shows it reuses the shared beans and declares none of its own.
 */
class WorkPackageDetailControllerTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  @Test
  void a200CarriesTheDetailAsJsonWithTheContractMembers() {
    try (HttpHarness server = serve(fixture(root -> {}))) {
      HttpHarness.Response response = server.get(path("WP01"));

      assertThat(response.status()).isEqualTo(200);
      assertThat(response.header("Content-Type")).startsWith("application/json");
      JsonNode body = JSON.readTree(response.body());
      assertThat(body.get("missionId").asString()).isEqualTo(ID);
      assertThat(body.get("wpId").asString()).isEqualTo("WP01");
      for (String member : new String[] {"subtasks", "dependencies", "reviewCycles", "ownedFiles"}) {
        assertThat(body.get(member).isArray()).as(member).isTrue();
      }
      assertThat(body.get("workspace").get("worktreePresent").asBoolean()).isFalse();
      assertThat(body.get("artifactReferences").get("prompt").get("path").asString()).isEqualTo("tasks/WP01-one.md");
      assertThat(body.size()).as("a closed body: eight members").isEqualTo(8);
    }
  }

  @Test
  void aForeignHostAndAForeignOriginAreRefusedBeforeAnyRead() {
    DetailFixture fixture = fixture(root -> {});
    try (HttpHarness server = serve(fixture)) {
      fixture.recorder().clear();
      String target = path("WP01");

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
  void theControllerParsesBothIdentifiersAndMakesOneCallToThePort() {
    List<String> asked = new ArrayList<>();
    WorkPackageDetailQuery spy =
        (missionId, wpId) -> {
          asked.add(missionId.value() + "/" + wpId.value());
          throw DetailRefusal.notFound();
        };
    DetailFixture fixture = fixture(root -> {});
    try (HttpHarness server = HttpHarness.startWith(fixture.built(), Map.of(WorkPackageDetailQuery.class, spy))) {
      assertThat(server.get(path("WP01")).status()).isEqualTo(404);
      assertThat(server.get("/api/v1/missions/not-a-ulid/work-packages/WP01/detail").status()).as("an empty parse is a refusal, the port is not called").isEqualTo(404);
      assertThat(server.get("/api/v1/missions/" + ID + "/work-packages/wp01/detail").status()).isEqualTo(404);
      assertThat(server.get("/api/v1/missions/" + ID + "/work-packages/WP1/detail").status()).isEqualTo(404);
    }

    assertThat(asked).containsExactly(ID + "/WP01");
  }

  @Test
  void everyKindOfUnavailabilityTheServiceCanThrowIsTheOneSourceUnreadableProblem() {
    for (DiagnosticCode code : DiagnosticCode.values()) {
      WorkPackageDetailQuery failing =
          (missionId, wpId) -> {
            throw new MissionStatusUnavailable(new Diagnostic(code, Diagnostic.NONE, null));
          };
      DetailFixture fixture = fixture(root -> {});
      try (HttpHarness server = HttpHarness.startWith(fixture.built(), Map.of(WorkPackageDetailQuery.class, failing))) {
        HttpHarness.Response response = server.get(path("WP01"));

        assertThat(response.status()).as(code.wire()).isEqualTo(500);
        assertThat(response.header("Content-Type")).startsWith("application/problem+json");
        assertThat(response.text()).isEqualTo("{\"code\":\"source_unreadable\",\"detail\":\"A file the detail is built from could not be read.\",\"status\":500,\"title\":\"A source of the work package could not be read\",\"type\":\"about:blank\"}\n");
      }
    }
  }

  @Test
  void aRefusalIsTheGoldensProblemByteForByte() {
    WorkPackageDetailQuery missing =
        (missionId, wpId) -> {
          throw DetailRefusal.notFound();
        };
    DetailFixture fixture = fixture(root -> {});
    try (HttpHarness server = HttpHarness.startWith(fixture.built(), Map.of(WorkPackageDetailQuery.class, missing))) {
      HttpHarness.Response response = server.get(path("WP01"));

      assertThat(response.status()).isEqualTo(404);
      assertThat(response.text()).isEqualTo("{\"code\":\"not_found\",\"detail\":\"No work package with this identifier exists in the Mission.\",\"status\":404,\"title\":\"The work package was not found\",\"type\":\"about:blank\"}\n");
    }
  }

  @Test
  void aKindTheRouteCannotThrowGetsTheSharedTextAndTheRoutesOwnTextIsOnlyForItsTwoKinds() {
    var artifact = ProblemMapper.workPackageDetail(new DetailRefusal(DetailRefusal.Kind.ARTIFACT_SECRET));
    var shared = ProblemMapper.detail(new DetailRefusal(DetailRefusal.Kind.ARTIFACT_SECRET));
    var missing = ProblemMapper.workPackageDetail(DetailRefusal.notFound());
    var unreadable = ProblemMapper.workPackageDetail(DetailRefusal.sourceUnreadable());

    assertThat(artifact.getBody()).isEqualTo(shared.getBody());
    assertThat(missing.getStatusCode().value()).isEqualTo(404);
    assertThat(missing.getBody().type()).isEqualTo("about:blank");
    assertThat(unreadable.getStatusCode().value()).isEqualTo(500);
    assertThat(unreadable.getBody().type()).isEqualTo("about:blank");
    assertThat(shared.getBody().type()).as("the shared mapper's texts are unchanged").isNull();
    assertThat(ProblemMapper.detail(DetailRefusal.notFound()).getBody().title()).isEqualTo("The resource was not found.");
  }

  @Test
  void theMapperShapesTheRecordThePortReturns() {
    DetailFixture fixture = fixture(root -> {});
    var detail = org.speckitty.missionstatus.application.query.detail.DetailRoute.serviceOver(fixture).workPackageDetail(new MissionId(ID), new WpId("WP01"));

    var model = WorkPackageDetailMapper.detail(detail);

    assertThat(model.getMissionId()).isEqualTo(detail.missionId().value());
    assertThat(model.getWpId()).isEqualTo(detail.wpId().value());
    assertThat(model.getReviewCycles()).hasSize(detail.reviewCycles().size());
  }

  @Test
  void theProductionApplicationBuildsTheRouteFromTheSharedBeansAndDeclaresNoneOfItsOwn() {
    DetailFixture fixture = fixture(root -> {});
    try (HttpHarness server = HttpHarness.startWired(fixture.root())) {
      HttpHarness.Response response = server.get(path("WP01"));

      assertThat(response.status()).isEqualTo(200);
      assertThat(JSON.readTree(response.body()).get("wpId").asString()).isEqualTo("WP01");
      assertThat(server.context().getBeansOfType(WorkPackageDetailQuery.class)).hasSize(1);
      assertThat(server.context().getBeansOfType(WorkPackageIndex.class)).hasSize(1);
      assertThat(server.context().getBeansOfType(TextSource.class)).hasSize(1);
      assertThat(server.context().getBeansOfType(AdmissionGate.class)).hasSize(1);
      assertThat(server.context().getBeansOfType(FrontmatterDecoder.class)).hasSize(1);
      assertThat(server.context().getBeansOfType(LanesDecoder.class)).hasSize(1);
    }
  }
}
