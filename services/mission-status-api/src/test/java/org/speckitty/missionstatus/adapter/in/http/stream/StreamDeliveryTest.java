package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.QUIET;

import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** AC-3a, AC-3b, AC-3e, AC-3f, AC-3g, AC-3h and AC-3i over the real socket: what a stream delivers and how it frames it. */
class StreamDeliveryTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String HISTORY = Rows.lifecycle(Rows.id(1), "MissionCreated", "2026-09-01T10:00:00Z") + Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");

  private StreamRig rig;

  @BeforeEach
  void start() {
    rig =
        StreamRig.of(
            FixtureSpec.of(
                PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, HISTORY),
                PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Rows.status(Rows.id(50), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"))));
  }

  @AfterEach
  void stop() {
    rig.close();
  }

  @Test
  void ac3aOneAppendedTransitionIsExactlyOneEventWithTheCursorAfterItAsItsId() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.status()).isEqualTo(200);
      assertThat(client.header("Content-Type")).startsWith("text/event-stream");
      String row = Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress");
      rig.append("alpha", row);
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("status-transition");
      assertThat(event.id()).isEqualTo(Cursors.text(HISTORY + row, 3));
      assertThat(event.raw()).startsWith("event: status-transition\nid: " + event.id() + "\ndata: {");
      JsonNode data = JSON.readTree(event.data());
      assertThat(data.get("missionId").asString()).isEqualTo(Rows.ALPHA_ID);
      assertThat(data.get("eventId").asString()).isEqualTo(Rows.id(3));
      assertThat(data.get("wpId").asString()).isEqualTo("WP01");
      assertThat(data.get("fromStatusLane").asString()).isEqualTo("claimed");
      assertThat(data.get("toStatusLane").asString()).isEqualTo("in_progress");
      assertThat(data.get("at").asString()).isEqualTo("2026-09-01T10:02:00Z");
      assertThat(data.get("force").asBoolean()).isFalse();
      assertThat(JSON.writeValueAsString(data.get("streamCursor"))).isEqualTo(JSON.writeValueAsString(JSON.readTree("{\"invariant\":\"" + Cursors.after(HISTORY + row, 3).invariant() + "\",\"offset\":" + Cursors.after(HISTORY + row, 3).offset() + "}")));
      assertThat(client.next(QUIET)).as("not a second event").isNull();
    }
  }

  @Test
  void theActorOfTheRowIsAThreeHandleObjectAndNeverOmitted() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress"));
      rig.tick();

      JsonNode data = JSON.readTree(ValidatedEvents.valid(client.nextEvent(BOUND)).data());

      assertThat(data.has("actor")).isTrue();
      assertThat(data.get("actor").get("tool").asString()).isEqualTo("claude");
      assertThat(data.get("actor").get("role").isNull()).isTrue();
      assertThat(data.get("actor").get("profile").isNull()).isTrue();
    }
  }

  @Test
  void aStructuredActorKeepsItsThreeHandlesAndDropsTheModelAndTheResolverSentinels() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append(
          "alpha",
          "{\"actor\":{\"model\":\"m\",\"profile\":\"__resolved_profile_absent__\",\"role\":\"implementer\",\"tool\":\"claude\"},\"at\":\"2026-09-01T10:02:00Z\",\"event_id\":\"" + Rows.id(3)
              + "\",\"execution_mode\":\"worktree\",\"force\":true,\"from_lane\":\"genesis\",\"to_lane\":\"planned\",\"wp_id\":\"WP07\"}\n");
      rig.tick();

      JsonNode data = JSON.readTree(ValidatedEvents.valid(client.nextEvent(BOUND)).data());

      assertThat(data.get("actor").get("tool").asString()).isEqualTo("claude");
      assertThat(data.get("actor").get("role").asString()).isEqualTo("implementer");
      assertThat(data.get("actor").get("profile").isNull()).as("a resolver sentinel is not a handle").isTrue();
      assertThat(data.get("actor").has("model")).isFalse();
      assertThat(data.get("fromStatusLane").isNull()).as("the genesis lane is not a display value").isTrue();
      assertThat(data.get("force").asBoolean()).isTrue();
    }
  }

  @Test
  void aLifecycleRowIsAMissionLifecycleEventWithItsIdAndTheSevenTypesOnly() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      String row = Rows.lifecycle(Rows.id(3), "SpecifyStarted", "2026-09-01T10:03:00Z");
      rig.append("alpha", row);
      rig.tick();

      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));

      assertThat(event.name()).isEqualTo("mission-lifecycle");
      assertThat(event.id()).isEqualTo(Cursors.text(HISTORY + row, 3));
      JsonNode data = JSON.readTree(event.data());
      assertThat(data.get("eventType").asString()).isEqualTo("SpecifyStarted");
      assertThat(data.get("at").asString()).isEqualTo("2026-09-01T10:03:00Z");
    }
  }

  @Test
  void ac3bAnnotationUnknownTypeAndUnknownKindRowsAreForwardedAsNothingAndTheConnectionStaysOpen() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.annotation(Rows.id(3), "2026-09-01T10:02:00Z", "WP01"));
      rig.append("alpha", Rows.unknownType(Rows.id(4)));
      rig.append("alpha", "{\"event_id\":\"" + Rows.id(5) + "\",\"kind\":\"something-new\",\"wp_id\":\"WP01\"}\n");
      rig.tick();

      assertThat(client.next(QUIET)).as("no event for any of the three").isNull();
      assertThat(client.awaitEnd(java.time.Duration.ofMillis(100))).as("the connection stays open").isFalse();

      String control = Rows.status(Rows.id(6), "2026-09-01T10:05:00Z", "WP01", "claimed", "in_progress");
      rig.append("alpha", control);
      rig.tick();
      SseClient.Event event = ValidatedEvents.valid(client.nextEvent(BOUND));
      assertThat(JSON.readTree(event.data()).get("eventId").asString()).isEqualTo(Rows.id(6));
    }
  }

  @Test
  void ac3bTheOtherNonForwardedRowsAreDroppedToo() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", "{\"event_id\":\"" + Rows.id(3) + "\",\"event_type\":\"WPCreated\",\"timestamp\":\"2026-09-01T10:02:00Z\"}\n");
      rig.append("alpha", "{\"event_id\":\"" + Rows.id(4) + "\",\"event_type\":\"RetrospectiveCaptured\",\"timestamp\":\"2026-09-01T10:02:00Z\"}\n");
      rig.tick();
      assertThat(client.next(QUIET)).isNull();
    }
  }

  @Test
  void aTransitionWhoseWorkPackageIdIsNotAWpIdIsDroppedNotRepaired() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "T001", "claimed", "in_progress"));
      rig.tick();
      assertThat(client.next(QUIET)).isNull();
    }
  }

  @Test
  void ac3eAnUnscopedStreamSendsNoIdLinesAndReplaysNothing() {
    try (SseClient client = rig.unscoped()) {
      assertThat(client.next(QUIET)).as("no replay of the history of either Mission").isNull();
      rig.append("alpha", Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress"));
      rig.append("beta", Rows.lifecycle(Rows.id(51), "PlanStarted", "2026-09-01T10:03:00Z"));
      rig.tick();

      List<SseClient.Event> events = client.events(2, BOUND);

      assertThat(events).hasSize(2);
      for (SseClient.Event event : events) {
        ValidatedEvents.valid(event);
        assertThat(event.id()).as("no id on an unscoped stream").isNull();
        assertThat(event.raw()).doesNotContain("id:");
      }
      assertThat(events).extracting(SseClient.Event::name).containsExactlyInAnyOrder("status-transition", "mission-lifecycle");
    }
  }

  @Test
  void ac3gAResumeDeliversTheRowsAfterTheCursorInOrderEachWithItsOwnCursorAndThenTheLiveOnes() {
    String rows = Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress") + Rows.status(Rows.id(4), "2026-09-01T10:03:00Z", "WP02", "planned", "claimed");
    rig.append("alpha", rows);
    String ledger = HISTORY + rows;
    try (SseClient client = rig.scopedFrom(Rows.ALPHA_ID, Cursors.after(ledger, 2))) {
      assertThat(client.status()).isEqualTo(200);
      List<SseClient.Event> replay = client.events(2, BOUND);
      assertThat(replay).extracting(SseClient.Event::id).containsExactly(Cursors.text(ledger, 3), Cursors.text(ledger, 4));
      replay.forEach(ValidatedEvents::valid);
      assertThat(client.next(QUIET)).as("nothing at or before the cursor is replayed").isNull();

      String live = Rows.status(Rows.id(5), "2026-09-01T10:04:00Z", "WP02", "claimed", "in_progress");
      rig.append("alpha", live);
      rig.tick();
      assertThat(ValidatedEvents.valid(client.nextEvent(BOUND)).id()).isEqualTo(Cursors.text(ledger + live, 5));
    }
  }

  @Test
  void ac3gAConnectionWithoutACursorReceivesNoneOfTheHistory() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      assertThat(client.next(QUIET)).isNull();
    }
  }

  @Test
  void ac3hStreamCursorWinsOverLastEventId() {
    String rows = Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress") + Rows.status(Rows.id(4), "2026-09-01T10:03:00Z", "WP02", "planned", "claimed");
    rig.append("alpha", rows);
    String ledger = HISTORY + rows;
    try (SseClient client =
        org.speckitty.missionstatus.testsupport.http.SseClient.open(
            rig.http, "/api/v1/events?missionId=" + Rows.ALPHA_ID + "&streamCursor=" + Cursors.text(ledger, 2), "Last-Event-ID", Cursors.text(ledger, 3))) {
      List<SseClient.Event> replay = client.events(2, BOUND);
      assertThat(replay).extracting(SseClient.Event::id).as("resumes after the query cursor (line 2), not after Last-Event-ID (line 3)").containsExactly(Cursors.text(ledger, 3), Cursors.text(ledger, 4));
    }
  }

  @Test
  void aLastEventIdAloneResumesLikeTheQueryCursor() {
    String rows = Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress");
    rig.append("alpha", rows);
    String ledger = HISTORY + rows;
    try (SseClient client = rig.scoped(Rows.ALPHA_ID, "Last-Event-ID", Cursors.text(ledger, 2))) {
      assertThat(client.events(1, BOUND)).extracting(SseClient.Event::id).containsExactly(Cursors.text(ledger, 3));
    }
  }

  @Test
  void ac3iKRowsAppendedInOneWriteArriveAsKEventsInLogOrderEachWithTheCursorAfterItsOwnRow() {
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      String rows =
          Rows.status(Rows.id(3), "2026-09-01T10:02:00Z", "WP01", "claimed", "in_progress")
              + Rows.lifecycle(Rows.id(4), "SpecifyCompleted", "2026-09-01T10:03:00Z")
              + Rows.status(Rows.id(5), "2026-09-01T10:04:00Z", "WP02", "planned", "claimed")
              + Rows.status(Rows.id(6), "2026-09-01T10:05:00Z", "WP02", "claimed", "in_progress");
      rig.append("alpha", rows);
      rig.tick();

      List<SseClient.Event> events = client.events(4, BOUND);

      assertThat(events).hasSize(4);
      events.forEach(ValidatedEvents::valid);
      String ledger = HISTORY + rows;
      assertThat(events).extracting(SseClient.Event::id).containsExactly(Cursors.text(ledger, 3), Cursors.text(ledger, 4), Cursors.text(ledger, 5), Cursors.text(ledger, 6));
      assertThat(events).extracting(event -> JSON.readTree(event.data()).get("eventId").asString()).containsExactly(Rows.id(3), Rows.id(4), Rows.id(5), Rows.id(6));
      assertThat(client.next(QUIET)).isNull();
    }
  }

  @Test
  void ac3fAHeartbeatIsAColonCommentLineThatCarriesNoDataAndNoEventName() {
    rig.close();
    rig = StreamRig.of(FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, HISTORY)), "mission-status.stream.heartbeat-interval=PT0.1S");
    try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      SseClient.Item item = client.next(BOUND);

      assertThat(item).isInstanceOf(SseClient.Comment.class);
      SseClient.Comment comment = (SseClient.Comment) item;
      assertThat(comment.text()).isEqualTo("heartbeat");
      assertThat(comment.raw()).isEqualTo(": heartbeat\n");
      assertThat(client.items()).allSatisfy(each -> assertThat(each).isInstanceOf(SseClient.Comment.class));
    }
  }
}
