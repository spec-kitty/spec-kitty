package org.speckitty.missionstatus.conformance.artifacts;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.node.StringNode;

/**
 * The artifact conformance gate: for every case of {@code artifact-conformance/cases.json}, the Java service, started with its
 * production wiring over the materialized tree, answers each request with exactly the status and body of the Python reference reader
 * ({@code golden.json}, written by {@code tests/contract/_mission_status_artifact_goldens.py}). {@code modifiedAt} is checked for its
 * format and then compared as the marker; a content longer than 4096 characters is compared by its SHA-256, as the golden stores it.
 * A case that needs symbolic links is reported as not run, with the reason, where the runner cannot create one.
 */
class ArtifactConformanceTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String MODIFIED_AT_MARKER = "<modifiedAt>";
  private static final int LONG_CONTENT = 4096;
  private static final String MODIFIED_AT_SHAPE = "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z";

  private static JsonNode resource(String name) {
    try (InputStream in = ArtifactConformanceTest.class.getResourceAsStream("/artifact-conformance/" + name)) {
      if (in == null) {
        throw new IllegalStateException(name + " is not on the classpath");
      }
      return JSON.readTree(in.readAllBytes());
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  @TestFactory
  Stream<DynamicTest> everyCaseAnswersAsTheReferenceDoes() {
    JsonNode cases = resource("cases.json");
    JsonNode golden = resource("golden.json").get("cases");
    String defaultMission = cases.get("missionId").asString();
    List<DynamicTest> tests = new ArrayList<>();
    for (JsonNode spec : cases.get("cases")) {
      String name = spec.get("name").asString();
      tests.add(DynamicTest.dynamicTest(name, () -> runCase(spec, golden.get(name), defaultMission)));
    }
    return tests.stream();
  }

  private static void runCase(JsonNode spec, JsonNode answers, String defaultMission) throws IOException {
    assertThat(answers).as("golden answers of " + spec.get("name").asString()).isNotNull();
    Path root = Files.createTempDirectory("artifact-conformance-");
    materialize(root, spec.get("tree"), spec.path("needsSymlinks").asBoolean(false));
    try (HttpHarness server = HttpHarness.startWired(root); Cleanup cleanup = new Cleanup(root)) {
      int index = 0;
      for (JsonNode expected : answers) {
        JsonNode request = expected.get("request");
        HttpHarness.Response response = server.get(url(request, defaultMission));
        String label = spec.get("name").asString() + " #" + index++ + " " + request;
        assertThat(response.status()).as(label).isEqualTo(expected.get("status").asInt());
        assertThat(masked(JSON.readTree(response.body()), label)).as(label).isEqualTo(expected.get("body"));
      }
    }
  }

  /** Deletes a materialized case tree when the case ends (links are deleted, never followed). */
  private record Cleanup(Path root) implements AutoCloseable {
    @Override
    public void close() throws IOException {
      try (Stream<Path> paths = Files.walk(root)) {
        for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toList()) {
          Files.deleteIfExists(path);
        }
      }
    }
  }

  /** The request URL: the listing, or the content read with every value of {@code paths} as one {@code path} parameter. */
  static String url(JsonNode request, String defaultMission) {
    String mission = request.has("missionId") ? request.get("missionId").asString() : defaultMission;
    StringBuilder url = new StringBuilder("/api/v1/missions/").append(mission).append("/artifacts");
    if (request.get("op").asString().equals("content")) {
      url.append("/content");
      String separator = "?";
      for (JsonNode path : request.get("paths")) {
        url.append(separator).append("path=").append(URLEncoder.encode(path.asString(), StandardCharsets.UTF_8).replace("+", "%20"));
        separator = "&";
      }
    }
    return url.toString();
  }

  /** The body masked as the golden generator masks it: a long content by its digest, each {@code modifiedAt} by the marker after its format is checked. */
  static JsonNode masked(JsonNode body, String label) {
    if (body.isObject() && body.has("content") && body.get("content").isString()) {
      String content = body.get("content").asString();
      if (content.codePointCount(0, content.length()) > LONG_CONTENT) {
        ((ObjectNode) body).set("content", StringNode.valueOf("<sha256:" + sha256(content) + ">"));
      }
    }
    if (body.isObject() && body.has("entries")) {
      for (JsonNode entry : body.get("entries")) {
        assertThat(entry.get("modifiedAt").asString()).as(label).matches(MODIFIED_AT_SHAPE);
        ((ObjectNode) entry).set("modifiedAt", StringNode.valueOf(MODIFIED_AT_MARKER));
      }
    }
    return body;
  }

  private static String sha256(String content) {
    try {
      return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content.getBytes(StandardCharsets.UTF_8)));
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  /** Writes a case tree the way the golden generator does. */
  static void materialize(Path root, JsonNode tree, boolean needsSymlinks) throws IOException {
    for (JsonNode entry : tree) {
      Path target = root.resolve(entry.get("path").asString());
      Files.createDirectories(target.getParent());
      if (entry.path("dir").asBoolean(false)) {
        Files.createDirectories(target);
      } else if (entry.has("symlink")) {
        link(target, Path.of(entry.get("symlink").asString()), needsSymlinks);
      } else if (entry.has("generate")) {
        JsonNode generate = entry.get("generate");
        Files.createDirectories(target);
        for (int i = 0; i < generate.get("count").asInt(); i++) {
          Files.write(target.resolve(String.format(generate.get("nameFormat").asString(), i)), generate.get("text").asString().getBytes(StandardCharsets.UTF_8));
        }
      } else {
        Files.write(target, bytes(entry));
      }
    }
  }

  private static void link(Path link, Path target, boolean needsSymlinks) {
    try {
      Files.createSymbolicLink(link, target);
    } catch (IOException | UnsupportedOperationException | SecurityException cannot) {
      String line = "NOT RUN ON THIS LEG: the runner cannot create a symbolic link (" + cannot.getClass().getSimpleName() + ")";
      System.out.println(line);
      Assumptions.assumeTrue(!needsSymlinks, line);
    }
  }

  static byte[] bytes(JsonNode entry) {
    if (entry.has("text")) {
      return entry.get("text").asString().getBytes(StandardCharsets.UTF_8);
    }
    if (entry.has("base64")) {
      return Base64.getDecoder().decode(entry.get("base64").asString());
    }
    if (entry.has("repeat")) {
      byte[] repeated = new byte[entry.get("repeat").get("count").asInt()];
      java.util.Arrays.fill(repeated, (byte) entry.get("repeat").get("byte").asInt());
      return repeated;
    }
    if (entry.has("parts")) {
      StringBuilder joined = new StringBuilder();
      entry.get("parts").forEach(part -> joined.append(part.asString()));
      return joined.toString().getBytes(StandardCharsets.UTF_8);
    }
    throw new IllegalArgumentException("a tree entry has no content");
  }

  @Test
  void aPlantedDifferenceIsSeen() {
    JsonNode expected = JSON.readTree("{\"content\":\"a\",\"entries\":[]}");
    JsonNode served = masked(JSON.readTree("{\"content\":\"b\",\"entries\":[]}"), "planted");
    assertThat(served).isNotEqualTo(expected);
    JsonNode listed = masked(JSON.readTree("{\"entries\":[{\"modifiedAt\":\"2026-09-22T10:30:00Z\",\"path\":\"a\"}]}"), "listed");
    assertThat(listed.get("entries").get(0).get("modifiedAt").asString()).isEqualTo(MODIFIED_AT_MARKER);
    String longText = "x".repeat(LONG_CONTENT + 1);
    assertThat(masked(JSON.readTree("{\"content\":\"" + longText + "\"}"), "long").get("content").asString()).startsWith("<sha256:");
  }
}
