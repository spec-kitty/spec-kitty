package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;

/**
 * {@code listArtifacts} and {@code getArtifactContent} over HTTP, with the production wiring over a real tree: every response the
 * contract lists, each body validated against the contract's schema for its status, and no refusal body that names a path.
 */
class ArtifactRoutesTest {

  private static final String ID = "01J01000000000000000000001";
  private static final String MISSIONS = "/api/v1/missions/";
  private static final String LISTING = MISSIONS + ID + "/artifacts";
  private static final String CONTENT = LISTING + "/content";
  private static final String CONTENT_PATH = "/missions/{missionId}/artifacts/content";
  private static final String LISTING_PATH = "/missions/{missionId}/artifacts";
  private static final String PROBLEM_JSON = "application/problem+json";

  @TempDir static Path root;
  private static Path outside;
  private static boolean linksMade;
  private static HttpHarness server;
  private static final ContractValidator VALIDATOR = ContractValidator.fromClasspath();

  @BeforeAll
  static void start() throws IOException {
    Path mission = root.resolve("kitty-specs/alpha-01J01000");
    write(mission.resolve("meta.json"), "{\"mission_id\": \"" + ID + "\", \"mission_slug\": \"alpha-01J01000\", \"created_at\": \"2026-09-01T10:00:00+00:00\", \"target_branch\": \"main\"}");
    write(mission.resolve("status.events.jsonl"), "");
    write(mission.resolve("status.json"), "{}");
    write(mission.resolve("spec.md"), "# Spec\n");
    write(mission.resolve("plan.md"), "# Plan\n");
    write(mission.resolve("research/notes.md"), "notes\n");
    write(mission.resolve("tasks/WP01-example.md"), "prompt\n");
    write(mission.resolve("tasks/WP01-example/review-cycle-1.md"), "cycle\n");
    write(mission.resolve("notes/handoff.md"), "Work happened in /" + "home/alice/x and the question went to alice" + "@" + "example.com.\n");
    write(mission.resolve("notes/empty.txt"), "");
    write(mission.resolve("notes/with space.md"), "space\n");
    write(mission.resolve("notes/hostile.md"), "-----" + "BEGIN " + "A ".repeat(20_000));
    write(mission.resolve("notes/secret.md"), "token " + "gh" + "p_" + "A".repeat(36) + "\n");
    writeBytes(mission.resolve("notes/nul.txt"), new byte[] {'a', 0, 'b'});
    write(mission.resolve(".env"), "OPENAI_API_KEY=" + "sk-" + "proj-" + "x".repeat(40) + "\n");
    write(mission.resolve("notes/credentials.json"), "{\"client_secret\": \"" + "x".repeat(24) + "\"}\n");
    writeBytes(mission.resolve("notes/latin1.txt"), new byte[] {'c', 'a', 'f', (byte) 0xe9});
    writeBytes(mission.resolve("notes/big.json"), new byte[262_145]);
    writeBytes(mission.resolve("notes/exact.txt"), "x".repeat(262_144).getBytes(StandardCharsets.UTF_8));
    outside = Files.createTempDirectory("artifact-routes-outside");
    write(outside.resolve("x.md"), "outside\n");
    try {
      Files.createSymbolicLink(mission.resolve("linked.md"), outside.resolve("x.md"));
      Files.createSymbolicLink(mission.resolve("linked-dir"), outside);
      linksMade = true;
    } catch (IOException | UnsupportedOperationException | SecurityException cannot) {
      System.out.println("NOT RUN ON THIS LEG: the link cases of ArtifactRoutesTest (" + cannot.getClass().getSimpleName() + ")");
    }
    server = HttpHarness.startWired(root);
  }

  @AfterAll
  static void stop() {
    if (server != null) {
      server.close();
    }
  }

  private static void write(Path file, String text) {
    writeBytes(file, text.getBytes(StandardCharsets.UTF_8));
  }

  private static void writeBytes(Path file, byte[] bytes) {
    try {
      Files.createDirectories(file.getParent());
      Files.write(file, bytes);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static String query(String path) {
    return CONTENT + "?path=" + java.net.URLEncoder.encode(path, StandardCharsets.UTF_8).replace("+", "%20");
  }

  private static void assertRefusal(HttpHarness.Response response, String contractPath, int status, String code) {
    assertThat(response.status()).as(code).isEqualTo(status);
    assertThat(response.header("Content-Type")).startsWith(PROBLEM_JSON);
    assertThat(VALIDATOR.validate(VALIDATOR.responseSchema(contractPath, Integer.toString(status), PROBLEM_JSON), response.text())).isEmpty();
    JsonNode body = RouteSupport.tree(response);
    assertThat(body.get("code").asString()).isEqualTo(code);
    assertThat(body.get("type").asString()).isEqualTo("about:blank");
    assertThat(response.text()).doesNotContain(root.toString()).doesNotContain("kitty-specs").doesNotContain("alpha-01J01000");
  }

  @Test
  void theListingHoldsEveryEligibleFileInByteOrderAndValidates() {
    HttpHarness.Response response = server.get(LISTING);
    assertThat(response.status()).isEqualTo(200);
    assertThat(VALIDATOR.validate(VALIDATOR.responseSchema(LISTING_PATH, "200", "application/json"), response.text())).isEmpty();
    JsonNode body = RouteSupport.tree(response);
    assertThat(body.get("missionId").asString()).isEqualTo(ID);
    assertThat(body.get("truncated").asBoolean()).isFalse();
    List<String> paths = new ArrayList<>();
    for (JsonNode entry : body.get("entries")) {
      paths.add(entry.get("path").asString());
    }
    assertThat(paths)
        .containsExactly(
            "meta.json", "notes/big.json", "notes/empty.txt", "notes/exact.txt", "notes/handoff.md", "notes/hostile.md", "notes/latin1.txt", "notes/nul.txt", "notes/secret.md",
            "notes/with space.md", "plan.md", "research/notes.md", "spec.md", "tasks/WP01-example.md", "tasks/WP01-example/review-cycle-1.md");
    assertThat(readable(body, "spec.md")).isTrue();
    assertThat(readable(body, "notes/exact.txt")).isTrue();
    assertThat(readable(body, "notes/big.json")).isFalse();
    assertThat(readable(body, "notes/secret.md")).isFalse();
    assertThat(readable(body, "notes/nul.txt")).isFalse();
    assertThat(readable(body, "notes/latin1.txt")).isFalse();
    assertThat(readable(body, "notes/hostile.md")).as("a scan that cannot finish is not readable, and the listing survives").isFalse();
    assertThat(entry(body, "tasks/WP01-example/review-cycle-1.md").get("kind").asString()).isEqualTo("review_cycle");
    assertThat(entry(body, "notes/big.json").get("sizeBytes").asLong()).isEqualTo(262_145);
    assertThat(entry(body, "spec.md").get("modifiedAt").asString()).matches("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z");
  }

  private static JsonNode entry(JsonNode body, String path) {
    for (JsonNode entry : body.get("entries")) {
      if (entry.get("path").asString().equals(path)) {
        return entry;
      }
    }
    throw new AssertionError("no entry " + path);
  }

  private static boolean readable(JsonNode body, String path) {
    return entry(body, path).get("readable").asBoolean();
  }

  @Test
  void anUnknownOrIllFormedMissionIsNotFound() {
    assertRefusal(server.get(MISSIONS + "01J01000000000000000000009/artifacts"), LISTING_PATH, 404, "not_found");
    assertRefusal(server.get(MISSIONS + "not-a-ulid/artifacts"), LISTING_PATH, 404, "not_found");
    assertRefusal(server.get(MISSIONS + "01J01000000000000000000009/artifacts/content?path=spec.md"), CONTENT_PATH, 404, "not_found");
  }

  @Test
  void aContentReadServesTheRedactedTextAndValidates() {
    HttpHarness.Response spec = server.get(query("spec.md"));
    assertThat(spec.status()).isEqualTo(200);
    assertThat(VALIDATOR.validate(VALIDATOR.responseSchema(CONTENT_PATH, "200", "application/json"), spec.text())).isEmpty();
    JsonNode body = RouteSupport.tree(spec);
    assertThat(body.get("kind").asString()).isEqualTo("spec");
    assertThat(body.get("mediaType").asString()).isEqualTo("text/markdown");
    assertThat(body.get("content").asString()).isEqualTo("# Spec\n");
    assertThat(body.get("sizeBytes").asLong()).isEqualTo(7);
    assertThat(body.get("redacted").asBoolean()).isFalse();

    JsonNode handoff = RouteSupport.tree(server.get(query("notes/handoff.md")));
    assertThat(handoff.get("content").asString()).isEqualTo("Work happened in [path] and the question went to [email].\n");
    assertThat(handoff.get("redacted").asBoolean()).isTrue();

    JsonNode empty = RouteSupport.tree(server.get(query("notes/empty.txt")));
    assertThat(empty.get("content").asString()).isEmpty();
    assertThat(empty.get("sizeBytes").asLong()).isZero();
    assertThat(empty.get("mediaType").asString()).isEqualTo("text/plain");

    assertThat(server.get(query("notes/with space.md")).status()).isEqualTo(200);
    assertThat(server.get(query("notes/exact.txt")).status()).isEqualTo(200);
  }

  @Test
  void aMissingRepeatedOrMalformedPathIsRefused400() {
    assertRefusal(server.get(CONTENT), CONTENT_PATH, 400, "invalid_artifact_path");
    assertRefusal(server.get(CONTENT + "?path=spec.md&path=plan.md"), CONTENT_PATH, 400, "invalid_artifact_path");
    assertRefusal(server.get(CONTENT + "?path="), CONTENT_PATH, 400, "invalid_artifact_path");
    for (String path : List.of("../meta.json", "/etc/passwd", "a\\b", "notes/", "notes//x", "./spec.md", "C:x", "~/x")) {
      assertRefusal(server.get(query(path)), CONTENT_PATH, 400, "invalid_artifact_path");
    }
    var malformed = server.raw("GET " + CONTENT + "?path=%zz HTTP/1.1\r\nHost: " + server.host() + "\r\nConnection: close\r\n\r\n");
    assertThat(malformed.status()).isEqualTo(400);
    String problem = malformed.text().substring(malformed.text().indexOf("\r\n\r\n") + 4);
    assertThat(problem).contains("\"code\":\"invalid_artifact_path\"");
  }

  @Test
  void aPathThatNamesNoEligibleArtifactIsNotFound() {
    for (String path : List.of("status.json", "STATUS.JSON", "status.events.jsonl", "notes", "missing.md", "spec.md/inner", ".env", "notes/credentials.json")) {
      assertRefusal(server.get(query(path)), CONTENT_PATH, 404, "not_found");
    }
    if (linksMade) {
      assertRefusal(server.get(query("linked.md")), CONTENT_PATH, 404, "not_found");
      assertRefusal(server.get(query("linked-dir/x.md")), CONTENT_PATH, 404, "not_found");
    }
  }

  @Test
  void anInvalidUtf8PercentEncodingIsRefusedAsAnInvalidPath() {
    // the container refuses a value that does not decode as UTF-8 and the advice maps it to the content route's 400, also when a
    // valid value comes with it (the reference's one-value rule would refuse the pair as well)
    assertRefusal(server.get(CONTENT + "?path=%FF"), CONTENT_PATH, 400, "invalid_artifact_path");
    assertRefusal(server.get(CONTENT + "?path=%FF&path=spec.md"), CONTENT_PATH, 400, "invalid_artifact_path");
  }

  @Test
  void theRefusalsOfTheContentFollowTheCodeOfEachCase() {
    assertRefusal(server.get(query("notes/big.json")), CONTENT_PATH, 413, "artifact_too_large");
    assertRefusal(server.get(query("notes/nul.txt")), CONTENT_PATH, 415, "artifact_not_text");
    assertRefusal(server.get(query("notes/latin1.txt")), CONTENT_PATH, 415, "artifact_not_text");
    HttpHarness.Response secret = server.get(query("notes/secret.md"));
    assertRefusal(secret, CONTENT_PATH, 422, "artifact_secret");
    assertThat(secret.text()).doesNotContain("p_AAAA");
    assertRefusal(server.get(query("notes/hostile.md")), CONTENT_PATH, 500, "artifact_unreadable");
  }
}
