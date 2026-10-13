package org.speckitty.missionstatus.config.nativetags;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.speckitty.missionstatus.config.MissionStatusApplication;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;

/**
 * A Jackson-and-SSE round trip that has to survive the native image: a JSON body with explicit {@code null} members in sorted order, then
 * an event stream that sends a heartbeat comment and one event with its {@code id:} (and explicit nulls in its data). The poll is the
 * real one (500 ms), so the waits are ceilings, not measurements.
 */
@Tag("native")
@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NativeJsonSseRoundTripTest {

  private static final Path ROOT = NativeProject.create();

  @DynamicPropertySource
  static void project(DynamicPropertyRegistry registry) {
    registry.add("mission-status.project-root", ROOT::toString);
    registry.add("mission-status.stream.heartbeat-interval", () -> "PT0.3S");
  }

  @Value("${local.server.port}")
  int port;

  @Test
  void aJsonBodyCarriesExplicitNullsAndAStreamSendsAHeartbeatAndOneEventWithItsId() throws Exception {
    HttpResponse<byte[]> project =
        HttpClient.newHttpClient().send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/missions")).GET().build(), HttpResponse.BodyHandlers.ofByteArray());
    assertThat(project.statusCode()).isEqualTo(200);
    String body = new String(project.body(), StandardCharsets.UTF_8);
    assertThat(body).contains("\"acceptedAt\":null").contains("\"mergedAt\":null").endsWith("}\n");
    assertThat(body.indexOf("\"acceptedAt\"")).as("acceptedAt is present").isNotNegative();
    assertThat(body.indexOf("\"acceptedAt\"")).as("members in sorted order").isLessThan(body.indexOf("\"blockedCount\""));

    try (SseClient client = SseClient.open(port, "/api/v1/events?missionId=" + NativeProject.MISSION_ID)) {
      assertThat(client.status()).isEqualTo(200);
      assertThat(client.header("Content-Type")).startsWith("text/event-stream");
      assertThat(client.next(Duration.ofSeconds(10))).as("a heartbeat").isInstanceOfSatisfying(SseClient.Comment.class, comment -> assertThat(comment.raw()).isEqualTo(": heartbeat\n"));

      String row = Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress");
      NativeProject.append(ROOT, row);
      SseClient.Event event = client.nextEvent(Duration.ofSeconds(15));

      assertThat(event).as("the appended row, within the ceiling").isNotNull();
      assertThat(event.name()).isEqualTo("status-transition");
      assertThat(event.id()).matches("[0-9]+:[0-9a-f]{64}");
      assertThat(event.data()).startsWith("{\"actor\":{\"profile\":null,\"role\":null,\"tool\":\"claude\"},\"at\":\"2026-09-01T10:01:00Z\"");
    }
  }
}
