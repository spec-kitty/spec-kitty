package org.speckitty.missionstatus.adapter.in.http.flow;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * The curated request set of the cross-route checks: the three routes, the contract document, a page with a cursor, the refusals of
 * every route and an event stream round trip (scoped and unscoped, a refusal, a resume). It is the same set for every check that needs
 * "the full flow", so what one check scans or fingerprints is what the others exercised.
 */
final class Flow {

  /** One answer as received: the request line, status, headers as text and body as text. */
  record Captured(String request, int status, String headers, String body) {
    String everything() {
      return request + "\n" + status + "\n" + headers + "\n" + body;
    }
  }

  private Flow() {}

  static Captured http(HttpHarness server, String path) {
    HttpHarness.Response response = server.get(path);
    StringBuilder headers = new StringBuilder();
    response.headers().map().forEach((name, values) -> values.forEach(value -> headers.append(name).append(": ").append(value).append('\n')));
    return new Captured("GET " + path, response.status(), headers.toString(), response.text());
  }

  /** The request/response part of the flow (no stream). */
  static List<Captured> requests(HttpHarness server) {
    List<Captured> all = new ArrayList<>();
    for (String path :
        List.of(
            "/api/v1/project",
            "/api/v1/missions",
            "/api/v1/missions?pageSize=1",
            "/api/v1/missions?pageSize=1&pageCursor=forged",
            "/api/v1/missions?pageSize=0",
            "/api/v1/openapi.yaml",
            "/api/v1/nowhere",
            "/api/v1/events?streamCursor=0:" + StreamCursor.start().invariant(),
            "/api/v1/events?missionId=01J09000000000000000000009",
            "/api/v1/events?missionId=01J01000000000000000000001&streamCursor=garbage")) {
      all.add(http(server, path));
    }
    return all;
  }

  /**
   * An event stream round trip: a scoped stream on {@code slug} and an unscoped one receive appended rows (a status transition whose
   * free text carries {@code reason}, and a lifecycle row on {@code otherSlug}); the scoped one is then truncated. Returns the transcripts
   * of both streams. This one WRITES to the fixture (the test is the writer, the service only reads).
   */
  static List<String> streams(StreamRig rig, String slug, String missionId, String otherSlug, String reason) {
    List<String> transcripts = new ArrayList<>();
    try (SseClient scoped = rig.scoped(missionId);
        SseClient unscoped = rig.unscoped()) {
      rig.append(
          slug,
          "{\"actor\":\"claude\",\"at\":\"2026-09-01T11:00:00Z\",\"event_id\":\"" + Rows.id(900) + "\",\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"claimed\","
              + "\"reason\":\"" + reason + "\",\"to_lane\":\"in_progress\",\"wp_id\":\"WP01\"}\n");
      rig.append(otherSlug, Rows.lifecycle(Rows.id(901), "PlanStarted", "2026-09-01T11:01:00Z"));
      rig.tick();
      scoped.events(1, Duration.ofSeconds(2));
      unscoped.events(2, Duration.ofSeconds(2));
      rig.replace(slug, Rows.status(Rows.id(902), "2026-09-01T11:02:00Z", "WP01", "planned", "claimed"));
      rig.tick();
      scoped.events(1, Duration.ofSeconds(2));
      unscoped.events(1, Duration.ofSeconds(2));
      transcripts.add(scoped.transcript());
      transcripts.add(unscoped.transcript());
    }
    return transcripts;
  }

  /**
   * The stream part of a flow that writes nothing: a resume from the start of a Mission's log (it replays what is there), an unscoped
   * stream, a poll tick and a refused resume. Returns the scoped transcript.
   */
  static String readOnlyStreams(StreamRig rig, String missionId, int rowsInLog) {
    try (SseClient scoped = SseClient.open(rig.http, "/api/v1/events?missionId=" + missionId + "&streamCursor=0:" + StreamCursor.start().invariant());
        SseClient unscoped = rig.unscoped()) {
      scoped.events(rowsInLog, Duration.ofSeconds(2));
      rig.tick();
      rig.tick();
      return scoped.transcript();
    }
  }
}
