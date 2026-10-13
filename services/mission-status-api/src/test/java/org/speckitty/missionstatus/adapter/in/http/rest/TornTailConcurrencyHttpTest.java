package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.CanonicalJson;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.GoldenDocuments;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;

/**
 * AC-4d, the HTTP leg: while a writer appends to a Mission's ledger, every 200 body carries ONE prefix of complete lines of the FINAL
 * log (eventCount, statusLaneCounts, lastEventId and streamCursor all from the same prefix), and every other answer is the L4 or L4b
 * Problem. A latch-controlled writer makes the L4 stage, the L4b stage and the completed row separate reads.
 */
class TornTailConcurrencyHttpTest {

  private static final int ROWS = 40;
  private static final List<String> TUPLE = List.of("eventCount", "statusLaneCounts", "lastEventId", "streamCursor");

  private static List<String> lines() {
    List<String> rows = new ArrayList<>();
    for (int i = 0; i < ROWS; i++) {
      rows.add(Rows.status(Rows.id(500 + i), String.format("2026-09-01T10:%02d:00Z", i), "WP" + String.format("%02d", i % 12 + 1), i < 12 ? "planned" : "claimed", i < 12 ? "claimed" : "in_progress"));
    }
    return rows;
  }

  private static FixtureSpec spec(String ledger) {
    return FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, ledger), PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", RouteSupport.moves(900, 1)));
  }

  /** The four-field tuple of the item for each prefix of complete lines, computed from the final log by the port. */
  private static List<JsonNode> expectedTuples(List<String> rows) {
    List<JsonNode> tuples = new ArrayList<>();
    for (int k = 0; k <= rows.size(); k++) {
      FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(spec(String.join("", rows.subList(0, k))));
      MissionOverview alpha = built.query().missions(new PageRequest(50, null)).items().stream().filter(i -> i.slug().equals("alpha")).findFirst().orElseThrow();
      tuples.add(tuple(RouteSupport.JSON.readTree(CanonicalJson.toBytes(GoldenDocuments.overview(alpha)))));
    }
    return tuples;
  }

  private static JsonNode tuple(JsonNode item) {
    tools.jackson.databind.node.ObjectNode out = RouteSupport.JSON.createObjectNode();
    for (String name : TUPLE) {
      out.set(name, item.get(name));
    }
    return out;
  }

  private static JsonNode alphaTuple(HttpHarness.Response response) {
    for (JsonNode item : RouteSupport.tree(response).get("items")) {
      if (item.get("slug").asString().equals("alpha")) {
        return tuple(item);
      }
    }
    throw new AssertionError("alpha is missing from the page");
  }

  private static void append(Path ledger, String text) throws IOException {
    Files.write(ledger, text.getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
  }

  @Test
  @Timeout(120)
  void freeRunningAppendsNeverServeAMixedOrHalfReadPrefix() throws Exception {
    List<String> rows = lines();
    List<JsonNode> expected = expectedTuples(rows);
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(spec(""));
    Path ledger = built.root().resolve("kitty-specs/alpha/status.events.jsonl");
    AtomicBoolean done = new AtomicBoolean();
    Thread writer =
        new Thread(
            () -> {
              try {
                for (String row : rows) {
                  append(ledger, row);
                  Thread.sleep(3);
                }
              } catch (IOException | InterruptedException failure) {
                throw new IllegalStateException(failure);
              } finally {
                done.set(true);
              }
            });
    int served = 0;
    int refused = 0;
    int calls = 0;
    try (HttpHarness server = HttpHarness.start(built)) {
      writer.start();
      while (calls < 200 || !done.get()) {
        HttpHarness.Response response = server.get("/api/v1/missions");
        calls++;
        if (response.status() == 200) {
          assertThat(expected).as("the served tuple is the tuple of one prefix of the final log").contains(alphaTuple(response));
          served++;
        } else {
          RouteSupport.assertProblem(response, 500, "ledger_torn_tail", built);
          refused++;
        }
      }
      writer.join();
      assertThat(alphaTuple(server.get("/api/v1/missions"))).isEqualTo(expected.get(ROWS));
    }
    assertThat(calls).isGreaterThanOrEqualTo(200);
    assertThat(served).as("some reads landed between appends").isPositive();
  }

  @Test
  @Timeout(60)
  void aLatchedWriterMakesTheTornStageTheUnterminatedStageAndTheCompletedRowThreeSeparateReads() throws Exception {
    List<String> rows = lines();
    List<JsonNode> expected = expectedTuples(rows);
    int base = 5;
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromSpec(spec(String.join("", rows.subList(0, base))));
    Path ledger = built.root().resolve("kitty-specs/alpha/status.events.jsonl");
    String next = rows.get(base);
    String body = next.substring(0, next.length() - 1);
    List<String> stages = new ArrayList<>();
    try (HttpHarness server = HttpHarness.start(built)) {
      assertThat(alphaTuple(server.get("/api/v1/missions"))).isEqualTo(expected.get(base));

      append(ledger, body.substring(0, body.length() / 2));
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "ledger_torn_tail", built);
      stages.add("L4 half row");

      append(ledger, body.substring(body.length() / 2));
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "ledger_torn_tail", built);
      stages.add("L4b whole row without newline");

      append(ledger, "\n");
      HttpHarness.Response complete = server.get("/api/v1/missions");
      assertThat(complete.status()).isEqualTo(200);
      assertThat(alphaTuple(complete)).isEqualTo(expected.get(base + 1));
      stages.add("complete row");
    }
    assertThat(stages).as("every stage was a read of its own").containsExactly("L4 half row", "L4b whole row without newline", "complete row");
  }
}
