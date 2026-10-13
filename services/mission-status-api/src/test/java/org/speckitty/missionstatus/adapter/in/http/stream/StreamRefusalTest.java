package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** AC-3d: one request per refusal code returns the status the contract fixes, with no event sent. */
class StreamRefusalTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String HISTORY = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed") + Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress");

  private StreamRig rig;

  @BeforeEach
  void start() {
    rig = StreamRig.of(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, HISTORY)));
  }

  @AfterEach
  void stop() {
    rig.close();
  }

  private JsonNode refused(String query, int status, String code, String... headers) {
    try (SseClient client = SseClient.open(rig.http, "/api/v1/events" + query, headers)) {
      assertThat(client.status()).as(query).isEqualTo(status);
      assertThat(client.header("Content-Type")).startsWith("application/problem+json");
      String body = client.body();
      assertThat(client.items()).as("no event was sent").isEmpty();
      assertThat(ValidatedEvents.contract().validateStreamRefusal(status, body)).as("the refusal validates against the contract").isEmpty();
      JsonNode problem = JSON.readTree(body);
      assertThat(problem.get("code").asString()).isEqualTo(code);
      assertThat(problem.get("status").asInt()).isEqualTo(status);
      assertThat(body).doesNotContain(rig.built.root().toString()).doesNotContain("kitty-specs");
      return problem;
    }
  }

  @Test
  void negativeIs400() {
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=-1:" + StreamCursor.start().invariant(), 400, "negative");
  }

  @Test
  void misalignedIs400() {
    // inside the first line, not at a line start
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=5:" + StreamCursor.start().invariant(), 400, "misaligned");
  }

  @Test
  void aCursorTextThatDoesNotParseIsMisalignedWithTheFixedUnparseableDetail() {
    JsonNode problem = refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=not-a-cursor", 400, "misaligned");
    assertThat(problem.get("detail").asString()).isEqualTo(StreamCursorText.UNPARSEABLE_DETAIL);
  }

  @Test
  void cursorWithoutMissionIs400() {
    refused("?streamCursor=" + Cursors.text(HISTORY, 1), 400, "cursor_without_mission");
    refused("", 400, "cursor_without_mission", "Last-Event-ID", Cursors.text(HISTORY, 1));
  }

  @Test
  void outOfRangeIs409() {
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=" + (Cursors.after(HISTORY, 2).offset() + 1000) + ":" + StreamCursor.start().invariant(), 409, "out_of_range");
  }

  @Test
  void contentMismatchIs409() {
    String other = Cursors.after(Rows.status(Rows.id(9), "2026-09-01T10:00:00Z", "WP09", "planned", "claimed") + HISTORY, 1).invariant();
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=" + Cursors.after(HISTORY, 1).offset() + ":" + other, 409, "content_mismatch");
  }

  @Test
  void anUnknownMissionIs404BeforeAnyEvent() {
    String unknown = "01J09000000000000000000009";
    try (SseClient client = rig.scoped(unknown)) {
      assertThat(client.status()).isEqualTo(404);
      assertThat(client.header("Content-Type")).startsWith("application/problem+json");
      assertThat(ValidatedEvents.contract().validateStreamRefusal(404, client.body())).isEmpty();
      assertThat(client.items()).isEmpty();
    }
    assertThat(rig.built.handles().diagnostics()).as("a plainly unknown id writes no diagnostic").isEmpty();
  }

  @Test
  void aMissionIdThatIsNotAUlidIsTheSame404() {
    try (SseClient client = SseClient.open(rig.http, "/api/v1/events?missionId=not-an-id")) {
      assertThat(client.status()).isEqualTo(404);
    }
  }

  @Test
  void eachRefusalIsOneRequestAndNoSubscriptionIsLeftOpen() {
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=zz", 400, "misaligned");
    refused("?missionId=" + Rows.ALPHA_ID + "&streamCursor=" + (Cursors.after(HISTORY, 2).offset() + 1000) + ":" + StreamCursor.start().invariant(), 409, "out_of_range");
    assertThat(rig.spy.openSubscriptions()).isZero();
    assertThat(List.of(400, 409)).hasSize(2);
  }
}
