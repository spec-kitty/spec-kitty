package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/** An idle stream, a disconnect, a slow consumer and a hundred connections: how a stream lives and how it ends. */
@ExtendWith(OutputCaptureExtension.class)
class StreamLifecycleTest {

  private static final String A1 = Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");

  private static FixtureSpec spec() {
    return FixtureSpec.of(
        PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, A1),
        PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", Rows.status(Rows.id(50), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
  }

  /**
   * An idle stream held past the first heartbeat (provisional, ADR 2026-10-05-2: 35 s of real time is the only way to show that the
   * 30 s default of the container does not end it). Revert: build the emitter with the container default timeout and this is red.
   */
  @Test
  void anIdleStreamIsHeldPastThirtyFiveSecondsReceivesItsHeartbeatAndStillDeliversARow() {
    try (StreamRig rig = StreamRig.of(spec(), "mission-status.stream.heartbeat-interval=PT30S");
        SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      SseClient.Item item = client.next(Duration.ofSeconds(35));

      assertThat(item).as("a heartbeat within 35 s").isInstanceOf(SseClient.Comment.class);
      assertThat(((SseClient.Comment) item).raw()).isEqualTo(": heartbeat\n");
      // Tomcat checks asynchronous timeouts about once a second, so a stream with a 30 s timeout is only seen to end a moment after it
      assertThat(client.awaitEnd(Duration.ofMillis(2500))).as("still open after the heartbeat, past the container's own 30 s").isFalse();

      rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress"));
      rig.tick();
      assertThat(ValidatedEvents.valid(client.nextEvent(BOUND)).name()).isEqualTo("status-transition");
    }
  }

  @Test
  void closingTheClientSocketUnsubscribesAfterTheNextHeartbeatWrite() {
    try (StreamRig rig = StreamRig.of(spec(), "mission-status.stream.heartbeat-interval=PT0.1S")) {
      SseClient client = rig.scoped(Rows.ALPHA_ID);
      assertThat(rig.spy.openSubscriptions()).isEqualTo(1);
      assertThat(client.next(BOUND)).isInstanceOf(SseClient.Comment.class);

      client.close();

      long deadline = System.nanoTime() + BOUND.toNanos() * 3;
      while (rig.spy.openSubscriptions() > 0 && System.nanoTime() < deadline) {
        Thread.onSpinWait();
      }
      assertThat(rig.spy.openSubscriptions()).as("the disconnect was noticed and the subscription closed").isZero();
    }
  }

  @Test
  void aSlowConsumerIsClosedWhenItsQueueOverflowsAndOtherConsumersAreUnaffected() throws Exception {
    CountDownLatch release = new CountDownLatch(1);
    try (StreamRig rig = StreamRig.withQueueCapacity(spec(), 2)) {
      rig.spy.holdNextSubscription(release);
      try (SseClient slow = rig.scoped(Rows.ALPHA_ID);
          SseClient fast = rig.scoped(Rows.ALPHA_ID)) {
        // the fast consumer is read after every tick, so its own queue (also two deep) never holds more than one signal
        List<SseClient.Event> received = new ArrayList<>();
        for (int i = 2; i <= 4; i++) {
          rig.append("alpha", Rows.status(Rows.id(i), "2026-09-01T10:0" + i + ":00Z", "WP0" + i, "planned", "claimed"));
          rig.tick();
          received.add(ValidatedEvents.valid(fast.nextEvent(BOUND)));
        }
        assertThat(received).as("the other consumer got every row").hasSize(3);
        assertThat(fast.awaitEnd(Duration.ofMillis(100))).isFalse();

        release.countDown();
        assertThat(slow.awaitEnd(BOUND)).as("the slow consumer is closed").isTrue();
        assertThat(slow.items().stream().filter(item -> item instanceof SseClient.Event).count()).as("it never got the row that did not fit").isLessThan(3);
      } finally {
        release.countDown();
      }
    }
  }

  @Test
  void aHundredUnscopedConnectionsSeeOneMissionVanishAsExactlyOneDiagnostic() {
    try (StreamRig rig = StreamRig.of(spec())) {
      List<SseClient> clients = new ArrayList<>();
      try {
        for (int i = 0; i < 100; i++) {
          clients.add(rig.unscoped());
        }
        assertThat(rig.spy.openSubscriptions()).isEqualTo(100);

        rig.removeTree(rig.missionDir("alpha"));
        rig.tick();

        assertThat(rig.diagnostics(DiagnosticCode.MISSION_VANISHED)).hasSize(1);
        assertThat(rig.diagnostics(DiagnosticCode.MISSION_VANISHED).get(0).mid8()).isEqualTo(Rows.ALPHA_ID.substring(0, 8));
        assertThat(rig.spy.openSubscriptions()).as("no connection was closed").isEqualTo(100);

        rig.append("beta", Rows.status(Rows.id(51), "2026-09-01T10:01:00Z", "WP02", "planned", "claimed"));
        rig.tick();
        for (SseClient client : clients) {
          assertThat(ValidatedEvents.valid(client.nextEvent(Duration.ofSeconds(5))).name()).isEqualTo("status-transition");
        }
      } finally {
        clients.forEach(SseClient::close);
      }
    }
  }

  @Test
  void shuttingDownEndsOpenStreamsInsteadOfWaitingOnThem() {
    long start = System.nanoTime();
    StreamRig rig = StreamRig.of(spec());
    SseClient client = rig.scoped(Rows.ALPHA_ID);
    rig.close();
    assertThat(client.awaitEnd(BOUND)).as("the server ended the stream").isTrue();
    assertThat(Duration.ofNanos(System.nanoTime() - start)).as("the graceful shutdown did not wait out its grace period").isLessThan(Duration.ofSeconds(20));
    client.close();
  }

  /** Landing fold R-5: a closed tab is not a fault. No ERROR line, no stack trace and no body written into a response that has gone. */
  @Test
  void aClientThatClosesItsStreamLeavesNoErrorLineAndNoStackTrace(CapturedOutput output) throws Exception {
    for (int round = 0; round < 5; round++) {
      try (StreamRig rig = StreamRig.of(spec(), "mission-status.stream.heartbeat-interval=PT0.05S")) {
        SseClient client = rig.scoped(Rows.ALPHA_ID);
        assertThat(client.next(BOUND)).isInstanceOf(SseClient.Comment.class);
        client.close();
        long deadline = System.nanoTime() + BOUND.toNanos() * 2;
        while (rig.spy.openSubscriptions() > 0 && System.nanoTime() < deadline) {
          Thread.sleep(20);
        }
        Thread.sleep(200);
      }
    }
    assertThat(output.getAll()).doesNotContain("unexpected failure").doesNotContain("AsyncRequestNotUsableException").doesNotContain("HttpMessageNotWritableException").doesNotContain("\tat ");
  }
}
