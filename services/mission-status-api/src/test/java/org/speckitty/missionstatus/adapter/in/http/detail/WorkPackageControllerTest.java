package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The HTTP edge of {@code getWorkPackage} (T100, T101): the body and its content type, the parameter rules of {@code includePrompt} (AC-2.2,
 * AC-2.5), the typed identifiers (rows C2 and W1 are 404, never 400; AC-2.3), the foreign Host or Origin refused before any read (row C1,
 * AC-9.3) and the controller's own contract: it parses, makes one call to the port and maps nothing itself.
 */
class WorkPackageControllerTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String HOST_PATH = "/home/someone/private/notes";
  private static final String PROMPT_MARKER = "PROMPT-BYTES-MARKER";

  private static DetailFixture fixture() {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, "2026-09-01T10:00:00+00:00", Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed"))),
        root ->
            MissionDetailServedRoute.write(
                root, "alpha", "tasks/WP01-one.md", "---\nwork_package_id: WP01\ntitle: See " + HOST_PATH + "\n---\n\n" + PROMPT_MARKER + " " + HOST_PATH + "\r\nsecond line\n"));
  }

  private static String path(String mission, String wp, String query) {
    return "/api/v1/missions/" + mission + "/work-packages/" + wp + (query == null ? "" : "?" + query);
  }

  @Test
  void a200CarriesTheWorkPackageAsJsonWithoutThePromptMemberByDefault() {
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture())) {
      HttpHarness.Response response = server.get(path(Rows.ALPHA_ID, "WP01", null));

      assertThat(response.status()).isEqualTo(200);
      assertThat(response.header("Content-Type")).startsWith("application/json");
      JsonNode body = JSON.readTree(response.body());
      assertThat(body.get("wpId").asString()).isEqualTo("WP01");
      assertThat(body.get("statusLane").asString()).isEqualTo("claimed");
      assertThat(body.get("title").asString()).as("AC-9.2: the human member is substituted").isEqualTo("See [path]");
      assertThat(body.has("promptMarkdown")).as("AC-2.1: the key is absent, not null").isFalse();
      assertThat(response.text()).doesNotContain(PROMPT_MARKER).doesNotContain(HOST_PATH).doesNotContain("promptMarkdown");
    }
  }

  @Test
  void includePromptTrueAddsExactlyThePromptMemberWithTheBodyAsAuthoredAndLineEndingsAsLf() {
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture())) {
      JsonNode plain = JSON.readTree(server.get(path(Rows.ALPHA_ID, "WP01", null)).body());
      HttpHarness.Response response = server.get(path(Rows.ALPHA_ID, "WP01", "includePrompt=true"));

      assertThat(response.status()).isEqualTo(200);
      JsonNode body = JSON.readTree(response.body());
      assertThat(body.get("promptMarkdown").asString()).contains(PROMPT_MARKER + " " + HOST_PATH).contains("second line").doesNotContain("\r");
      assertThat(body.get("title").asString()).as("AC-9.2: the title is substituted in the same response").isEqualTo("See [path]");
      var names = new ArrayList<String>();
      body.propertyNames().forEach(names::add);
      var plainNames = new ArrayList<String>();
      plain.propertyNames().forEach(plainNames::add);
      names.remove("promptMarkdown");
      assertThat(names).as("AC-2.1: the pair differs by exactly one member").containsExactlyInAnyOrderElementsOf(plainNames);
    }
  }

  @Test
  void includePromptFalseIsTheSameAsAbsent() {
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture())) {
      HttpHarness.Response response = server.get(path(Rows.ALPHA_ID, "WP01", "includePrompt=false"));

      assertThat(response.status()).isEqualTo(200);
      assertThat(JSON.readTree(response.body()).has("promptMarkdown")).isFalse();
    }
  }

  @ParameterizedTest(name = "[{index}] {0}")
  @ValueSource(strings = {"includePrompt=1", "includePrompt=yes", "includePrompt=TRUE", "includePrompt=True", "includePrompt=", "includePrompt", "includePrompt=true&includePrompt=true", "includePrompt=true&includePrompt=false", "includePrompt=true,false", "includePrompt=%20true"})
  void aValueThatIsNotExactlyTrueOrFalseIs400InvalidParameterAndNoFileIsRead(String query) {
    DetailFixture fixture = fixture();
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture)) {
      fixture.recorder().clear();

      HttpHarness.Response response = server.get(path(Rows.ALPHA_ID, "WP01", query));

      assertThat(response.status()).isEqualTo(400);
      assertThat(response.header("Content-Type")).startsWith("application/problem+json");
      assertThat(JSON.readTree(response.body()).get("code").asString()).isEqualTo("invalid_parameter");
      assertThat(response.text()).doesNotContain(PROMPT_MARKER).doesNotContain("yes").doesNotContain("TRUE");
      assertThat(fixture.recorder().accesses()).as("no file is read").isEmpty();
      assertThat(server.get(path(Rows.ALPHA_ID, "WP01", "includePrompt=true")).status()).as("true on the same request is 200").isEqualTo(200);
    }
  }

  @Test
  void aMalformedPercentEncodingAnywhereInTheQueryIsTheStatusOnly400() {
    DetailFixture fixture = fixture();
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture)) {
      fixture.recorder().clear();

      RawClient.Reply response = server.raw("GET " + path(Rows.ALPHA_ID, "WP01", "other=%zz&includePrompt=true") + " HTTP/1.1\r\nHost: " + server.host() + "\r\nConnection: close\r\n\r\n");

      assertThat(response.status()).isEqualTo(400);
      assertThat(response.text()).doesNotContain(PROMPT_MARKER).doesNotContain("%zz");
      assertThat(fixture.recorder().accesses()).isEmpty();
    }
  }

  @ParameterizedTest(name = "[{index}] {0}")
  @ValueSource(strings = {"wp01", "WP1", "WP", "WPab", "WP01x", "WP0%D9%A1", "WP0000000000000000000000000000000000000000000000000000000000000001"})
  void anIllFormedWorkPackageIdIsNotFoundNeverABadRequestAndNoWorkPackageFileIsRead(String wp) {
    DetailFixture fixture = fixture();
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture)) {
      fixture.recorder().clear();

      HttpHarness.Response plain = server.get(path(Rows.ALPHA_ID, wp, null));
      HttpHarness.Response withBadParameter = server.get(path(Rows.ALPHA_ID, wp, "includePrompt=1"));

      assertThat(plain.status()).isEqualTo(404);
      assertThat(JSON.readTree(plain.body()).get("code").asString()).isEqualTo("not_found");
      assertThat(withBadParameter.status()).as("S-27: the identifier is judged before the parameter").isEqualTo(404);
      assertThat(fixture.recorder().accesses().stream().filter(access -> access.pathClass() == PathClass.WP_FILE)).as("AC-2.3").isEmpty();
      assertThat(fixture.recorder().accesses()).isEmpty();
    }
  }

  @ParameterizedTest(name = "[{index}] {0}")
  @ValueSource(strings = {"01J01000", "alpha", "7", "01j01000000000000000000001", "01J0100000000000000000000", "01J010000000000000000000011"})
  void anIllFormedMissionIdIsNotFoundNeverABadRequest(String mission) {
    DetailFixture fixture = fixture();
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture)) {
      HttpHarness.Response response = server.get(path(mission, "WP01", "includePrompt=true"));

      assertThat(response.status()).isEqualTo(404);
      assertThat(JSON.readTree(response.body()).get("code").asString()).isEqualTo("not_found");
      assertThat(fixture.recorder().accesses()).isEmpty();
    }
  }

  @Test
  void aForeignHostAndAForeignOriginAreRefusedBeforeAnyReadAndCarryNoByteOfThePrompt() {
    DetailFixture fixture = fixture();
    try (HttpHarness server = WorkPackageControllerRowsTest.serve(fixture)) {
      fixture.recorder().clear();
      String target = path(Rows.ALPHA_ID, "WP01", "includePrompt=true");

      RawClient.Reply host = server.raw("GET " + target + " HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n");
      RawClient.Reply origin = server.raw("GET " + target + " HTTP/1.1\r\nHost: " + server.host() + "\r\nOrigin: http://evil.example\r\nConnection: close\r\n\r\n");

      for (RawClient.Reply reply : List.of(host, origin)) {
        assertThat(reply.status()).isEqualTo(403);
        assertThat(reply.text()).contains("request_refused").doesNotContain(PROMPT_MARKER).doesNotContain(HOST_PATH).doesNotContain("promptMarkdown");
      }
      assertThat(fixture.recorder().accesses()).as("row C1, AC-9.3: zero reads recorded").isEmpty();
      assertThat(fixture.diagnostics()).isEmpty();
      RawClient.Reply accepted = server.raw("GET " + target + " HTTP/1.1\r\nHost: " + server.host() + "\r\nConnection: close\r\n\r\n");
      assertThat(accepted.status()).as("an accepted Host is 200 with the bytes").isEqualTo(200);
      assertThat(accepted.text()).contains(PROMPT_MARKER);
    }
  }

  @Test
  void theControllerParsesTheIdentifiersAndTheParameterAndMakesOneCallToThePort() {
    List<String> asked = new ArrayList<>();
    WorkPackageQuery spy =
        (missionId, wpId, includePrompt) -> {
          asked.add(missionId.value() + "/" + wpId.value() + "/" + includePrompt);
          throw DetailRefusal.notFound();
        };
    DetailFixture fixture = fixture();
    try (HttpHarness server = HttpHarness.startWith(fixture.built(), Map.of(WorkPackageQuery.class, spy))) {
      assertThat(server.get(path(Rows.ALPHA_ID, "WP01", null)).status()).isEqualTo(404);
      assertThat(server.get(path(Rows.ALPHA_ID, "WP02", "includePrompt=true")).status()).isEqualTo(404);
      assertThat(server.get(path(Rows.ALPHA_ID, "WP03", "includePrompt=false")).status()).isEqualTo(404);
      assertThat(server.get(path("not-a-ulid", "WP01", null)).status()).as("an empty parse is a refusal, the port is not called").isEqualTo(404);
      assertThat(server.get(path(Rows.ALPHA_ID, "bad", null)).status()).isEqualTo(404);
      assertThat(server.get(path(Rows.ALPHA_ID, "WP01", "includePrompt=yes")).status()).as("a refused parameter does not reach the port").isEqualTo(400);
    }

    assertThat(asked).containsExactly(Rows.ALPHA_ID + "/WP01/false", Rows.ALPHA_ID + "/WP02/true", Rows.ALPHA_ID + "/WP03/false");
  }

  @Test
  void theViewThePortReturnsIsTheOneTheBodyIsShapedFrom() {
    DetailFixture fixture = fixture();
    var view = WorkPackageControllerRowsTest.serviceOver(fixture).workPackage(new MissionId(Rows.ALPHA_ID), new WpId("WP01"), true);

    var shaped = WorkPackageMapper.workPackage(view);

    assertThat(shaped.wpId()).isEqualTo("WP01");
    assertThat(shaped.promptMarkdown()).isEqualTo(view.promptMarkdown());
    assertThat(WorkPackageServedRoute.path(Rows.ALPHA_ID, "WP01", true)).endsWith("?includePrompt=true");
  }
}
