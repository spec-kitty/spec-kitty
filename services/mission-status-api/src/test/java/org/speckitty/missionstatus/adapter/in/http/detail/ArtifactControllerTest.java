package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.ArtifactQueryService;
import org.speckitty.missionstatus.application.query.port.in.ArtifactQuery;
import org.speckitty.missionstatus.domain.redaction.TextScreen;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Utf8Host;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.testsupport.http.RawClient;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The HTTP edge of the two artifact routes over a real socket: raw-query decoding, one call on the port, the status mapping, row C1 and
 * row C2 (404, never 400), the path rule of AC-5.2, and the committed goldens served through the whole stack.
 */
class ArtifactControllerTest {

  private static final String ID = "00000000000000000000000001";
  private static final String BASE = "/api/v1/missions/" + ID + "/artifacts";
  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static DetailFixture fixture(String tag) {
    TreeFixture tree = ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(tag + "/" + tag)).findFirst().orElseThrow();
    return DetailFixture.of(tree.dir());
  }

  private static HttpHarness serve(DetailFixture fixture) {
    ArtifactQuery query = new ArtifactQueryService(fixture.readModel(), fixture.textSource(), new AdmissionGate(), fixture.built().handles().recorder(), new TextScreen(LeakPatternsFile.load()));
    return HttpHarness.startWith(fixture.built(), Map.of(ArtifactQuery.class, query));
  }

  private static JsonNode tree(HttpHarness.Response response) {
    return JSON.readTree(response.body());
  }

  private static void assertProblem(HttpHarness.Response response, int status, String code) {
    assertThat(response.status()).isEqualTo(status);
    assertThat(response.header("Content-Type")).startsWith("application/problem+json");
    JsonNode body = tree(response);
    assertThat(body.get("code").asString()).isEqualTo(code);
    assertThat(body.get("status").asInt()).isEqualTo(status);
    assertThat(body.get("type").asString()).isEqualTo("about:blank");
    assertThat(body.get("title").asString()).isNotBlank();
    assertThat(body.get("detail").asString()).isNotBlank();
  }

  // ---- the two routes ---------------------------------------------------------------------------------------------------------

  @Test
  void theListingAnswers200WithTheContractsBodyInTheCanonicalForm() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(BASE);

      assertThat(response.status()).isEqualTo(200);
      assertThat(response.header("Content-Type")).startsWith("application/json");
      JsonNode body = tree(response);
      assertThat(body.get("missionId").asString()).isEqualTo(ID);
      assertThat(body.get("truncated").asBoolean()).isFalse();
      assertThat(body.get("entries")).hasSize(14);
      assertThat(response.body()).isEqualTo(CanonicalJson.toBytes(CanonicalJson.parse(response.body())));
    }
  }

  @Test
  void theContentRouteAnswers200WithTheTextAndTheCanonicalBytes() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(BASE + "/content?path=spec.md");

      assertThat(response.status()).isEqualTo(200);
      JsonNode body = tree(response);
      assertThat(body.get("path").asString()).isEqualTo("spec.md");
      assertThat(body.get("kind").asString()).isEqualTo("spec");
      assertThat(body.get("encoding").asString()).isEqualTo("utf-8");
      assertThat(body.get("redacted").asBoolean()).isFalse();
      assertThat(response.body()).isEqualTo(CanonicalJson.toBytes(CanonicalJson.parse(response.body())));
    }
  }

  @Test
  void aSparseFileAboveTwoGibIsListedWithItsTrueSize() throws IOException {
    DetailFixture fixture = fixture("artifacts-populated");
    Path huge = fixture.root().resolve("kitty-specs").resolve("alpha-mission").resolve("huge.bin");
    try (var channel = java.nio.channels.FileChannel.open(huge, java.nio.file.StandardOpenOption.CREATE_NEW, java.nio.file.StandardOpenOption.WRITE)) {
      channel.write(java.nio.ByteBuffer.wrap(new byte[] {1}), 3_221_225_471L);
    }
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(BASE);

      assertThat(response.status()).isEqualTo(200);
      JsonNode entry = null;
      for (JsonNode candidate : tree(response).get("entries")) {
        if (candidate.get("path").asString().equals("huge.bin")) {
          entry = candidate;
        }
      }
      assertThat(entry).isNotNull();
      assertThat(entry.get("readable").asBoolean()).isFalse();
      assertThat(new String(response.body(), StandardCharsets.UTF_8)).contains("\"sizeBytes\":3221225472");
    }
  }

  // ---- row C2: 404, never 400 ---------------------------------------------------------------------------------------------------

  @Test
  void anIllFormedOrUnknownMissionIdIs404NotFoundNeverBadRequestForBothOperations() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      for (String id : List.of("nope", "00000000000000000000000009", "0000000000000000000000000a", "0000000000000000000000001", "000000000000000000000000011", "0000000000000000000000000U", "0000000000000000000000000I", "0000000000000000000000000L", "0000000000000000000000000O", "alpha-mission", "01")) {
        assertProblem(server.get("/api/v1/missions/" + id + "/artifacts"), 404, "not_found");
        assertProblem(server.get("/api/v1/missions/" + id + "/artifacts/content?path=spec.md"), 404, "not_found");
      }
      assertThat(server.get(BASE).status()).as("control: the real id is served").isEqualTo(200);
    }
  }

  /** Ruling OO-2: an ill-formed missionId with a malformed path is 404, never 400. */
  @Test
  void anIllFormedMissionIdTogetherWithAMalformedPathIs404NotFoundAndAWellFormedIdWithThePathIs400() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      for (String query : List.of("path=..%2fx", "path=%ff", "path=a&path=b", "", "path=")) {
        String suffix = query.isEmpty() ? "" : "?" + query;
        assertProblem(server.get("/api/v1/missions/not-a-ulid/artifacts/content" + suffix), 404, "not_found");
        assertProblem(server.get("/api/v1/missions/" + ID + "/artifacts/content" + suffix), 400, "invalid_artifact_path");
      }
    }
  }

  // ---- row C1 --------------------------------------------------------------------------------------------------------------------

  @Test
  void aForeignHostIs403RequestRefusedWithZeroReads() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      fixture.recorder().clear();
      RawClient.Reply listing = server.raw("GET " + BASE + " HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n");
      RawClient.Reply content = server.raw("GET " + BASE + "/content?path=spec.md HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n");

      assertThat(listing.status()).isEqualTo(403);
      assertThat(content.status()).isEqualTo(403);
      assertThat(listing.text()).contains("request_refused").doesNotContain("evil.example");
      assertThat(fixture.recorder().accesses()).isEmpty();
    }
  }

  // ---- the path rule of AC-5.2 ---------------------------------------------------------------------------------------------------

  private record Row(String query, int status, String code) {}

  @Test
  void thePathTableRunsAtTheHttpLegWithTheContractProblemBody() throws IOException {
    DetailFixture fixture = fixture("artifacts-populated");
    Path mission = fixture.root().resolve("kitty-specs").resolve("alpha-mission");
    Files.writeString(mission.resolve("a b"), "space\n");
    Files.writeString(mission.resolve("a+b"), "plus\n");
    Files.writeString(mission.resolve("a@b"), "at\n");
    Files.writeString(mission.resolve(".hidden"), "dot\n");
    Files.createDirectories(mission.resolve("home"));
    Files.writeString(mission.resolve("home/x.md"), "home\n");
    List<Row> rows =
        List.of(
            new Row("path=..%2fx", 400, "invalid_artifact_path"),
            new Row("path=%252e%252e", 404, "not_found"),
            new Row("path=a&path=b", 400, "invalid_artifact_path"),
            new Row("path=spec.md&path=plan.md", 400, "invalid_artifact_path"),
            new Row("", 400, "invalid_artifact_path"),
            new Row("path=", 400, "invalid_artifact_path"),
            new Row("other=spec.md", 400, "invalid_artifact_path"),
            new Row("path=%ff", 400, "invalid_artifact_path"),
            new Row("path=%c0%af", 400, "invalid_artifact_path"),
            new Row("path=%e2%82", 400, "invalid_artifact_path"),
            new Row("path=a%5cb", 400, "invalid_artifact_path"),
            new Row("path=a%00b", 400, "invalid_artifact_path"),
            new Row("path=a%0ab", 400, "invalid_artifact_path"),
            new Row("path=C%3Ax", 400, "invalid_artifact_path"),
            new Row("path=~%2Fx", 400, "invalid_artifact_path"),
            new Row("path=a%2F%2Fb", 400, "invalid_artifact_path"),
            new Row("path=a%2F", 400, "invalid_artifact_path"),
            new Row("path=" + "x".repeat(513), 400, "invalid_artifact_path"),
            new Row("path=" + "a/".repeat(255) + "ab", 404, "not_found"),
            new Row("path=spec.md", 200, null),
            new Row("path=a%20b", 200, null),
            new Row("path=a+b", 200, null),
            new Row("path=a%40b", 200, null),
            new Row("path=.hidden", 200, null),
            new Row("path=home%2Fx.md", 200, null),
            new Row("path=home/x.md", 200, null),
            new Row("path=a%2Bb", 200, null),
            new Row("path=nothing+here", 404, "not_found"));
    try (HttpHarness server = serve(fixture)) {
      for (Row row : rows) {
        HttpHarness.Response response = server.get(BASE + "/content" + (row.query().isEmpty() ? "" : "?" + row.query()));
        assertThat(response.status()).as(row.query()).isEqualTo(row.status());
        if (row.code() != null) {
          assertProblem(response, row.status(), row.code());
        }
      }
      assertThat(tree(server.get(BASE + "/content?path=a+b")).get("content").asString()).as("a plus sign is a plus sign, never a space").isEqualTo("plus\n");
      assertThat(tree(server.get(BASE + "/content?path=a%20b")).get("content").asString()).isEqualTo("space\n");
    }
  }

  @Test
  void aNonAsciiPathIsDecodedOnceAsUtf8() throws IOException {
    Utf8Host.assumeUtf8("ArtifactControllerTest#aNonAsciiPathIsDecodedOnceAsUtf8");
    DetailFixture fixture = fixture("artifacts-populated");
    Files.writeString(fixture.root().resolve("kitty-specs").resolve("alpha-mission").resolve("café.md"), "café\n", StandardCharsets.UTF_8);
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(BASE + "/content?path=caf%C3%A9.md");

      assertThat(response.status()).isEqualTo(200);
      assertThat(tree(response).get("content").asString()).isEqualTo("café\n");
      assertThat(server.get(BASE + "/content?path=caf%C3%A9.md%C3%A9").status()).isEqualTo(404);
    }
  }

  // ---- the faults of the routes -----------------------------------------------------------------------------------------------------

  @Test
  void anUnlistableMissionDirectoryIs500ArtifactListingUnreadableAndAnUnreadableFileIs500ArtifactUnreadable() {
    DetailFixture fixture = fixture("artifacts-populated");
    try (HttpHarness server = serve(fixture)) {
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.ARTIFACT_DIR && access.mode() == OpenMode.LIST, () -> new java.nio.file.AccessDeniedException("injected"));
      HttpHarness.Response listing = server.get(BASE);
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.ARTIFACT_FILE && access.mode() == OpenMode.READ, () -> new java.nio.file.AccessDeniedException("injected"));
      HttpHarness.Response content = server.get(BASE + "/content?path=spec.md");

      assertProblem(listing, 500, "artifact_listing_unreadable");
      assertProblem(content, 500, "artifact_unreadable");
      assertThat(listing.text()).doesNotContain(fixture.root().toString(), "injected");
      assertThat(content.text()).doesNotContain(fixture.root().toString(), "injected", "spec.md");
    }
  }
}
