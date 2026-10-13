package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** AC-3c: a log that shrinks, or whose last consumed line is rewritten, under an open stream is a log-truncated event without an id. */
class StreamTruncationTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String ROW1 = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
  private static final String ROW2 = Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress");
  private static final String ROW3 = Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP02", "planned", "claimed");
  private static final String HISTORY = ROW1 + ROW2 + ROW3;

  private StreamRig rig;

  @BeforeEach
  void start() {
    rig = StreamRig.of(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, HISTORY)));
  }

  @AfterEach
  void stop() {
    rig.close();
  }

  private static long size(String text) {
    return text.getBytes(StandardCharsets.UTF_8).length;
  }

  @Test
  void aShrunkLogYieldsLogTruncatedWithoutAnIdAndTheResetCursorInsideItsData() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.replace("alpha", ROW1);
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("log-truncated");
      assertThat(event.id()).as("a log-truncated event never carries an id line").isNull();
      assertThat(event.raw()).doesNotContain("id:");
      JsonNode data = JSON.readTree(event.data());
      assertThat(data.get("missionId").asString()).isEqualTo(Rows.ALPHA_ID);
      assertThat(data.get("reason").asString()).isEqualTo("size_shrink");
      assertThat(data.get("detectedAtOffset").asLong()).isEqualTo(size(HISTORY));
      assertThat(data.get("streamCursor").get("offset").asLong()).isZero();
      assertThat(data.get("streamCursor").get("invariant").asString()).isEqualTo(StreamCursor.start().invariant());
    }
  }

  @Test
  void aReconnectWithThePreTruncationIdIsRefusedOutOfRange() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.replace("alpha", ROW1);
      rig.tick();
      assertThat(client.nextEvent(BOUND)).isNotNull();
    }
    try (SseClient again = rig.scopedFrom(Rows.ALPHA_ID, Cursors.after(HISTORY, 3))) {
      assertThat(again.status()).isEqualTo(409);
      assertThat(again.body()).contains("\"code\":\"out_of_range\"");
    }
  }

  @Test
  void aSameLengthRewriteOfTheLastConsumedLineYieldsContentMismatchAndAReconnectIsRefusedContentMismatch() {
    String rewritten = ROW1 + ROW2 + ROW3.replace(Rows.id(3), Rows.id(4));
    assertThat(size(rewritten)).isEqualTo(size(HISTORY));
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.replace("alpha", rewritten);
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("log-truncated");
      assertThat(event.id()).isNull();
      JsonNode data = JSON.readTree(event.data());
      assertThat(data.get("reason").asString()).isEqualTo("content_mismatch");
      assertThat(data.get("detectedAtOffset").asLong()).isEqualTo(size(HISTORY));
    }
    try (SseClient again = rig.scopedFrom(Rows.ALPHA_ID, Cursors.after(HISTORY, 3))) {
      assertThat(again.status()).isEqualTo(409);
      assertThat(again.body()).contains("\"code\":\"content_mismatch\"");
    }
  }

  @Test
  void afterATruncationTheStreamIsRebaselinedAndDeliversTheNextRowWithAnIdInTheNewLog() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.replace("alpha", ROW1);
      rig.tick();
      assertThat(client.nextEvent(BOUND).name()).isEqualTo("log-truncated");

      rig.append("alpha", ROW2);
      rig.tick();
      SseClient.Event next = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(next.name()).isEqualTo("status-transition");
      assertThat(next.id()).isEqualTo(Cursors.text(ROW1 + ROW2, 2));
      assertThat(client.next(StreamRig.QUIET)).isNull();
    }
  }

  @Test
  void aDeletedLedgerFileWhileTheMissionDirectoryRemainsIsTheSameShrink() throws Exception {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      java.nio.file.Files.delete(rig.ledger("alpha"));
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("log-truncated");
      assertThat(JSON.readTree(event.data()).get("reason").asString()).isEqualTo("size_shrink");
    }
  }

  @Test
  void anUnscopedStreamSendsLogTruncatedToo() {
    try (SseClient client = rig.unscoped()) {
      rig.replace("alpha", ROW1);
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("log-truncated");
      assertThat(event.id()).isNull();
    }
  }
}
