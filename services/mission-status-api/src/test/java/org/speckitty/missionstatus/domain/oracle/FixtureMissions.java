package org.speckitty.missionstatus.domain.oracle;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.Topology;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Test-only reader of the committed conformance fixtures: it plays the part of the outbound adapter's codec so that the domain
 * can be compared with the goldens that live Python wrote. It is NOT domain code (JSON stays out of the domain).
 */
final class FixtureMissions {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final List<String> LIFECYCLE = List.of("MissionCreated", "SpecifyStarted", "SpecifyCompleted", "PlanStarted", "PlanCompleted", "TasksStarted", "TasksCompleted");

  record Mission(MissionMeta meta, List<LedgerLine> lines, StreamCursor cursor) {}

  private FixtureMissions() {}

  static List<Mission> load(Path fixtureRoot) throws IOException {
    List<Mission> missions = new ArrayList<>();
    try (Stream<Path> dirs = Files.list(fixtureRoot.resolve("kitty-specs"))) {
      for (Path dir : dirs.sorted().toList()) {
        if (Files.isRegularFile(dir.resolve("meta.json"))) {
          missions.add(loadMission(dir));
        }
      }
    }
    return missions;
  }

  private static String text(JsonNode node, String key) {
    JsonNode value = node.get(key);
    return value == null || value.isNull() ? null : value.asString();
  }

  private static Mission loadMission(Path dir) throws IOException {
    JsonNode meta = JSON.readTree(Files.readString(dir.resolve("meta.json"), StandardCharsets.UTF_8));
    MissionMeta missionMeta =
        new MissionMeta(
            new MissionId(text(meta, "mission_id")),
            text(meta, "slug"),
            text(meta, "friendly_name"),
            meta.get("mission_number") == null || meta.get("mission_number").isNull() ? null : meta.get("mission_number").asInt(),
            text(meta, "mission_type"),
            text(meta, "target_branch"),
            Topology.fromStored(text(meta, "topology")),
            text(meta, "created_at"),
            text(meta, "accepted_at"),
            text(meta, "merged_at"),
            text(meta, "discarded_at"),
            meta.get("baseline_merge_commit") != null && !meta.get("baseline_merge_commit").isNull() && !meta.get("baseline_merge_commit").asString().isEmpty());
    Path ledger = dir.resolve("status.events.jsonl");
    List<LedgerLine> lines = new ArrayList<>();
    // The cursor after the terminated lines: the end offset and the digest of the LAST TERMINATED LINE, whatever its kind. A blank
    // last line is that line (the tail reader hashes the physical line that ends at the offset); see BlankFinalLineCursorTest.
    StreamCursor cursor = StreamCursor.start();
    if (Files.isRegularFile(ledger)) {
      byte[] raw = Files.readAllBytes(ledger);
      int start = 0;
      int number = 0;
      byte[] lastLine = null;
      for (int i = 0; i < raw.length; i++) {
        if (raw[i] == '\n') {
          byte[] line = java.util.Arrays.copyOfRange(raw, start, i + 1);
          number++;
          lines.add(new LedgerLine(number, StreamCursor.digestOf(line), line.length, kindOf(new String(line, StandardCharsets.UTF_8).strip())));
          lastLine = line;
          start = i + 1;
        }
      }
      cursor = new StreamCursor(start, lastLine == null ? StreamCursor.start().invariant() : StreamCursor.digestOf(lastLine));
    }
    return new Mission(missionMeta, lines, cursor);
  }

  private static LineKind kindOf(String line) {
    if (line.isEmpty()) {
      return new LineKind.Blank();
    }
    JsonNode row;
    try {
      row = JSON.readTree(line);
    } catch (RuntimeException notJson) {
      return new LineKind.Malformed(MalformedReason.NOT_JSON);
    }
    if (!row.isObject()) {
      return new LineKind.Malformed(MalformedReason.NOT_OBJECT);
    }
    if (row.has("kind")) {
      return new LineKind.Annotation(text(row, "wp_id"));
    }
    if (row.has("event_type")) {
      String type = text(row, "event_type");
      return LIFECYCLE.contains(type) ? new LineKind.Lifecycle(new LifecycleEvent(text(row, "event_id"), type, text(row, "timestamp"))) : new LineKind.Ignored();
    }
    JsonNode policy = row.get("policy_metadata");
    String agent = policy != null && policy.isObject() ? text(policy, "agent") : null;
    return new LineKind.Status(
        new StatusEvent(
            text(row, "event_id"),
            text(row, "at"),
            text(row, "wp_id"),
            Lane.fromWire(text(row, "from_lane")),
            Lane.fromWire(text(row, "to_lane")),
            row.get("force").asBoolean(),
            text(row, "review_ref"),
            text(row, "reason"),
            text(row, "reason_source"),
            agent));
  }
}
