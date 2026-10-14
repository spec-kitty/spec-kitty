package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.json.JsonMapper;

/**
 * Pre-merge fold J3: {@code mission-status.stream.max-connections} bounds the open event streams. Over the bound a request is refused with
 * a Problem (503, code {@code stream_capacity_reached}) before anything is subscribed, and a stream that ends frees its place.
 */
class StreamCapacityTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static StreamRig rig(int max) {
    return StreamRig.of(
        FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"))),
        "mission-status.stream.max-connections=" + max,
        // a vanished client is noticed at the next heartbeat write, which is when its place is freed
        "mission-status.stream.heartbeat-interval=PT0.2S");
  }

  @Test
  void aStreamOverTheBoundIsRefusedWithAProblemAndAFreedPlaceIsReused() throws Exception {
    try (StreamRig rig = rig(2)) {
      SseClient first = rig.unscoped();
      SseClient second = rig.scoped(Rows.ALPHA_ID);
      assertThat(first.status()).isEqualTo(200);
      assertThat(second.status()).isEqualTo(200);
      int subscriptionsBefore = rig.spy.totalSubscriptions();

      try (SseClient third = rig.unscoped()) {
        assertThat(third.status()).isEqualTo(503);
        assertThat(third.header("Content-Type")).startsWith("application/problem+json");
        String body = third.body();
        assertThat(JSON.readTree(body).get("code").asString()).isEqualTo("stream_capacity_reached");
        assertThat(JSON.readTree(body).get("status").asInt()).isEqualTo(503);
        assertThat(StreamRefusalContract.problem(body)).as("the body validates against the contract's Problem").isEmpty();
        assertThat(body).doesNotContain(rig.built.root().toString());
        assertThat(third.items()).as("no event was sent").isEmpty();
      }
      assertThat(rig.spy.totalSubscriptions()).as("a refused request subscribed nothing").isEqualTo(subscriptionsBefore);

      first.close();
      long deadline = System.nanoTime() + Duration.ofSeconds(10).toNanos();
      int status = 503;
      while (status == 503 && System.nanoTime() < deadline) {
        try (SseClient again = rig.unscoped()) {
          status = again.status();
        }
        if (status == 503) {
          Thread.sleep(100);
        }
      }
      assertThat(status).as("a closed stream frees its place").isEqualTo(200);
      second.close();
    }
  }

  @Test
  void aRefusedRequestDoesNotUseUpAPlace() {
    try (StreamRig rig = rig(1);
        SseClient only = rig.scoped(Rows.ALPHA_ID)) {
      for (int i = 0; i < 5; i++) {
        try (SseClient refused = rig.unscoped()) {
          assertThat(refused.status()).isEqualTo(503);
        }
      }
      assertThat(only.status()).isEqualTo(200);
    }
  }

  /** A HEAD request never writes a body, so it could never notice a disconnect: it takes no place and gets 405 with {@code Allow: GET}. */
  @Test
  void aHeadRequestTakesNoPlaceAndIsRefusedWithAllowGet() throws Exception {
    HttpClient client = HttpClient.newHttpClient();
    try (StreamRig rig = rig(1)) {
      HttpRequest head = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + rig.http.port() + "/api/v1/events")).method("HEAD", HttpRequest.BodyPublishers.noBody()).build();
      for (int i = 0; i < 3; i++) {
        HttpResponse<Void> reply = client.send(head, HttpResponse.BodyHandlers.discarding());
        assertThat(reply.statusCode()).as("HEAD " + i).isEqualTo(405);
        assertThat(reply.headers().firstValue("Allow")).hasValue("GET");
      }
      assertThat(rig.spy.totalSubscriptions()).as("a HEAD request subscribed nothing").isZero();
      try (SseClient stream = rig.unscoped()) {
        assertThat(stream.status()).as("the one place is still free").isEqualTo(200);
      }
    }
  }
}
