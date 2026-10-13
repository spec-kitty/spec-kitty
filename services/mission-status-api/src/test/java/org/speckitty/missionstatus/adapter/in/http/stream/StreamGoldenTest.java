package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.http.StreamRig.BOUND;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The stream goldens of the oracle ({@code golden/stream.json}, recorded from live {@code poll_once}) against the real HTTP stream.
 * Each scenario Mission holds a {@code status.events.before.jsonl}: the log as it was when the cursor was taken. The test installs it as
 * the ledger, opens a Mission-scoped stream (which starts at the end of that log), replaces the ledger with {@code status.events.jsonl} and
 * lets the feed poll once. The golden records either the {@code log_truncated} event poll_once returned (reason, offset at detection, the
 * reset cursor) or the refusal it raised for a blank line; the stream must send the matching {@code log-truncated} event, or close with
 * one {@code ledger_unparseable} diagnostic and nothing more. The golden carries values, not the bytes of an event, so the comparison is on the
 * values; the framing (name, no id) is asserted beside them.
 */
class StreamGoldenTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  private record Scenario(String name, String missionId, String before, String current, JsonNode golden, SseClient client) {}

  private static String read(Path file) {
    try {
      return Files.readString(file, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Runs every scenario of one fixture against one server and returns the scenarios with their streams. */
  private static Map<String, Scenario> play(StreamRig[] holder, String tag, String fixture) {
    Path fixtureDir = ConformanceTree.root().resolve(tag).resolve(fixture);
    JsonNode golden = JSON.readTree(read(fixtureDir.resolve("golden").resolve("stream.json"))).get("scenarios");
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTree(fixtureDir);
    StreamRig rig = StreamRig.over(built);
    holder[0] = rig;
    Map<String, Scenario> scenarios = new TreeMap<>();
    for (String name : golden.propertyNames()) {
      String current = rig.read(name);
      String before = read(rig.missionDir(name).resolve("status.events.before.jsonl"));
      String missionId = JSON.readTree(read(rig.missionDir(name).resolve("meta.json"))).get("mission_id").asString();
      rig.replace(name, before);
      scenarios.put(name, new Scenario(name, missionId, before, current, golden.get(name), null));
    }
    Map<String, Scenario> open = new TreeMap<>();
    for (Scenario scenario : scenarios.values()) {
      SseClient client = rig.scoped(scenario.missionId());
      assertThat(client.status()).isEqualTo(200);
      open.put(scenario.name(), new Scenario(scenario.name(), scenario.missionId(), scenario.before(), scenario.current(), scenario.golden(), client));
    }
    for (Scenario scenario : open.values()) {
      rig.replace(scenario.name(), scenario.current());
    }
    rig.tick();
    return open;
  }

  private static void expectLogTruncated(Scenario scenario) {
    JsonNode events = scenario.golden().get("events");
    assertThat(events).as(scenario.name() + " records one poll_once event").hasSize(1);
    JsonNode golden = events.get(0);
    assertThat(golden.get("type").asString()).isEqualTo("log_truncated");
    SseClient.Event event = ValidatedEvents.valid(scenario.client().nextEvent(BOUND));
    assertThat(event.name()).isEqualTo("log-truncated");
    assertThat(event.id()).as("no id line").isNull();
    JsonNode data = JSON.readTree(event.data());
    assertThat(data.get("reason").asString()).isEqualTo(golden.get("reason").asString());
    assertThat(data.get("detectedAtOffset").asLong()).isEqualTo(golden.get("detected_at_offset").asLong());
    assertThat(data.get("streamCursor").get("offset").asLong()).isEqualTo(golden.get("tail_offset").asLong()).isEqualTo(scenario.golden().get("cursor").get("offset").asLong());
    assertThat(data.get("streamCursor").get("invariant").asString()).isEqualTo(golden.get("tail_invariant").asString()).isEqualTo(scenario.golden().get("cursor").get("invariant").asString());
    assertThat(data.get("missionId").asString()).isEqualTo(scenario.missionId());
  }

  /**
   * poll_once is all-or-nothing: it raised on the blank line and returned no events. The stream table (row S4) is the operator's ruling for
   * a stream: it delivers the rows BEFORE the bad line, then closes with one diagnostic. Both end in a refusal at the blank line and nothing
   * after it; the stream's events are the forwarded rows between the start offset and the blank line, in log order.
   */
  private static void expectClosedOnTheBlankLine(StreamRig rig, Scenario scenario) {
    assertThat(scenario.golden().get("refusal").get("exception").asString()).isEqualTo("JSONDecodeError");
    List<String> expected = new ArrayList<>();
    for (String line : scenario.current().substring(scenario.before().length()).split("(?<=\n)")) {
      if (line.strip().isEmpty()) {
        break;
      }
      expected.add(JSON.readTree(line).get("event_id").asString());
    }
    List<String> delivered = new ArrayList<>();
    for (SseClient.Event event : scenario.client().events(expected.size(), BOUND)) {
      delivered.add(JSON.readTree(ValidatedEvents.valid(event).data()).get("eventId").asString());
    }
    assertThat(delivered).as("the rows before the blank line").isEqualTo(expected);
    assertThat(scenario.client().awaitEnd(BOUND)).as("poll_once refused the blank line: the stream closes").isTrue();
    assertThat(scenario.client().items().stream().filter(item -> item instanceof SseClient.Event).count()).as("nothing after the blank line").isEqualTo(expected.size());
    List<Diagnostic> unparseable = new ArrayList<>(rig.built.handles().diagnostics().stream().filter(d -> d.code() == DiagnosticCode.LEDGER_UNPARSEABLE).toList());
    assertThat(unparseable).hasSize(1);
    assertThat(unparseable.get(0).mid8()).isEqualTo(scenario.missionId().substring(0, 8));
  }

  @Test
  void logTruncatedGoldenIsTheStreamsLogTruncatedEventForBothShrunkAndRewrittenLogs() {
    StreamRig[] holder = new StreamRig[1];
    try {
      Map<String, Scenario> scenarios = play(holder, "log-truncated", "shrunk-and-rewritten");
      assertThat(scenarios).containsKeys("log-shrunk", "log-rewritten");
      for (Scenario scenario : scenarios.values()) {
        expectLogTruncated(scenario);
      }
      assertThat(scenarios.get("log-shrunk").golden().get("events").get(0).get("reason").asString()).isEqualTo("size_shrink");
      assertThat(scenarios.get("log-rewritten").golden().get("events").get(0).get("reason").asString()).isEqualTo("content_mismatch");
    } finally {
      holder[0].close();
    }
  }

  @Test
  void blankLineGoldenIsAStreamThatClosesWithOneLedgerUnparseableDiagnostic() {
    StreamRig[] holder = new StreamRig[1];
    try {
      Map<String, Scenario> scenarios = play(holder, "malformed-rows", "blank-line");
      for (Scenario scenario : scenarios.values()) {
        expectClosedOnTheBlankLine(holder[0], scenario);
      }
    } finally {
      holder[0].close();
    }
  }

  @Test
  void blankLineFinalGoldenIsAStreamThatClosesWithOneLedgerUnparseableDiagnostic() {
    StreamRig[] holder = new StreamRig[1];
    try {
      Map<String, Scenario> scenarios = play(holder, "malformed-rows", "blank-line-final");
      for (Scenario scenario : scenarios.values()) {
        expectClosedOnTheBlankLine(holder[0], scenario);
      }
    } finally {
      holder[0].close();
    }
  }

  @Test
  void everyStreamGoldenOfTheCommittedTreeIsConsumedByAScenarioAbove() throws IOException {
    List<String> committed = new ArrayList<>();
    try (var walk = Files.walk(ConformanceTree.root())) {
      walk.filter(path -> path.getFileName().toString().equals("stream.json")).forEach(path -> committed.add(ConformanceTree.root().relativize(path.getParent().getParent()).toString().replace('\\', '/')));
    }
    assertThat(committed).containsExactlyInAnyOrder("log-truncated/shrunk-and-rewritten", "malformed-rows/blank-line", "malformed-rows/blank-line-final");
  }
}
