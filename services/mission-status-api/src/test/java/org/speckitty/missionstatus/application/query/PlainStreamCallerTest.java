package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamRequest;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamCapacityReached;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * A plain Java caller of the stream, as a second inbound adapter would be: no Spring context, no HTTP type. Strings go in
 * ({@link StreamRequest#parse}), {@link MissionStatusQuery#subscribe} and {@link Subscription#next} run, and projected
 * {@link StreamEvent}s come out. It meets the same cap and the same shutdown hook as the HTTP adapter, and never a raw ledger row.
 */
class PlainStreamCallerTest {

  private static List<StreamEvent> events(Subscription subscription) throws InterruptedException {
    List<StreamEvent> events = new ArrayList<>();
    for (StreamSignal signal = subscription.next(Duration.ZERO); !(signal instanceof StreamSignal.Idle); signal = subscription.next(Duration.ZERO)) {
      if (signal instanceof StreamSignal.Events batch) {
        events.addAll(batch.events());
      }
    }
    return events;
  }

  @Test
  void stringsInProjectedEventsOutWithTheResumeCursorOfEachRow() throws Exception {
    Fx fx = new Fx(StreamFx.twoMissions());
    MissionStatusQuery query = fx.service;
    String cursorText = StreamFx.cursorAfter(StreamFx.alphaHistory(), 1).toText();

    StreamRequest request = StreamRequest.parse(Rows.ALPHA_ID, cursorText);
    try (Subscription subscription = query.subscribe(request.scope(), request.cursor())) {
      List<StreamEvent> replay = events(subscription);

      assertThat(replay).hasSize(2).allSatisfy(event -> assertThat(event).isInstanceOf(StreamEvent.StatusTransition.class));
      assertThat(replay.getFirst()).isInstanceOfSatisfying(StreamEvent.StatusTransition.class, transition -> {
        assertThat(transition.missionId()).isEqualTo(Rows.ALPHA_ID);
        assertThat(transition.eventId()).isEqualTo(Rows.id(2));
        assertThat(transition.wpId()).isEqualTo("WP01");
        assertThat(transition.fromStatusLane()).isEqualTo("planned");
        assertThat(transition.toStatusLane()).isEqualTo("claimed");
        assertThat(transition.actor().tool()).isEqualTo("claude");
      });
      assertThat(replay.getFirst().resumeCursor()).contains(StreamFx.cursorAfter(StreamFx.alphaHistory(), 2));

      fx.source.appendLedger("alpha", Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review"));
      fx.executor.tick();
      assertThat(StreamFx.eventIds(events(subscription))).containsExactly(Rows.id(4));
    }
  }

  @Test
  void aSecondCallerMeetsTheSameCapAndTheSameRefusalOrder() {
    Fx fx = new Fx(StreamFx.twoMissions(), StreamSettings.defaults().withMaxConnections(1));
    MissionStatusQuery query = fx.service;
    StreamRequest live = StreamRequest.parse(Rows.ALPHA_ID, null);

    try (Subscription first = query.subscribe(live.scope(), live.cursor())) {
      assertThat(first).isNotNull();
      assertThatThrownBy(() -> query.subscribe(live.scope(), live.cursor())).isInstanceOf(StreamCapacityReached.class);
    }
    assertThatThrownBy(() -> StreamRequest.parse(null, "5:abc")).isInstanceOfSatisfying(StreamRefused.class, refused -> assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.CURSOR_WITHOUT_MISSION));
  }

  @Test
  void theShutdownHookEndsTheCallersStream() {
    Fx fx = new Fx(StreamFx.twoMissions());
    MissionStatusQuery query = fx.service;
    StreamRequest request = StreamRequest.parse(null, null);
    Subscription subscription = query.subscribe(request.scope(), request.cursor());

    query.endStreams();

    assertThatThrownBy(() -> subscription.next(Duration.ZERO)).isInstanceOf(IllegalStateException.class);
  }
}
