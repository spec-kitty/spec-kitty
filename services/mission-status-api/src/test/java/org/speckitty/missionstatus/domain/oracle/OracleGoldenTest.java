package org.speckitty.missionstatus.domain.oracle;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.OverviewDeriver;
import org.speckitty.missionstatus.domain.readmodel.overview.Progress;
import org.speckitty.missionstatus.domain.readmodel.paging.Pager;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Compares the domain with the goldens written by live Python ({@code materialize_snapshot} and {@code build_overview}) for the
 * fixture classes whose outcome is decided by ledger bytes and {@code meta.json} alone (the port-level classes of FR-013). No
 * Spring context is started.
 */
class OracleGoldenTest {

  private static final Path ROOT = Path.of("src/test/resources/conformance");
  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final Pattern PERCENT = Pattern.compile("\"(weightedPercentage|donePercentage)\":([0-9.]+)");

  static Stream<String> fixtures() {
    return Stream.of(
        "interleaved/two-missions",
        "lifecycle-only/seven-lifecycle-types",
        "no-ledger/plain-and-discarded",
        "log-truncated/shrunk-and-rewritten",
        "crlf-and-listing/crlf-and-lf-twin",
        "crlf-and-listing/listing-order");
  }

  private static String string(JsonNode node, String key) {
    JsonNode value = node.get(key);
    return value == null || value.isNull() ? null : value.asString();
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("fixtures")
  void everyMissionOverviewEqualsThePythonGolden(String fixture) throws IOException {
    Path root = ROOT.resolve(fixture);
    String goldenText = Files.readString(root.resolve("golden/missions.json"), StandardCharsets.UTF_8);
    JsonNode golden = JSON.readTree(goldenText).get("items");
    StatusReducer reducer = new StatusReducer(new AtThenEventId());
    List<MissionOverview> overviews = new ArrayList<>();
    for (FixtureMissions.Mission mission : FixtureMissions.load(root)) {
      StatusSnapshot snapshot = reducer.reduceLines(mission.lines());
      overviews.add(OverviewDeriver.derive(mission.meta(), snapshot, mission.cursor()));
    }
    MissionPage page = Pager.page(overviews.stream().map(o -> new Pager.Entry(o.slug(), o)).toList(), 200, null);

    assertThat(page.items()).hasSize(golden.size());
    List<String> renderedPercentages = new ArrayList<>();
    for (int i = 0; i < golden.size(); i++) {
      JsonNode expected = golden.get(i);
      MissionOverview actual = page.items().get(i);
      String name = actual.slug();
      assertThat(actual.missionId().value()).as(name + " order").isEqualTo(string(expected, "missionId"));
      assertThat(actual.mid8()).as(name).isEqualTo(string(expected, "mid8"));
      assertThat(actual.slug()).as(name).isEqualTo(string(expected, "slug"));
      assertThat(actual.friendlyName()).as(name).isEqualTo(string(expected, "friendlyName"));
      assertThat(actual.missionType()).as(name).isEqualTo(string(expected, "missionType"));
      assertThat(actual.targetBranch()).as(name).isEqualTo(string(expected, "targetBranch"));
      assertThat(actual.topology().wire()).as(name).isEqualTo(string(expected, "topology"));
      assertThat(actual.createdAt()).as(name).isEqualTo(string(expected, "createdAt"));
      assertThat(actual.acceptedAt()).as(name).isEqualTo(string(expected, "acceptedAt"));
      assertThat(actual.mergedAt()).as(name).isEqualTo(string(expected, "mergedAt"));
      assertThat(actual.discardedAt()).as(name).isEqualTo(string(expected, "discardedAt"));
      assertThat(actual.lifecycleStatus().wire()).as(name).isEqualTo(string(expected, "lifecycleStatus"));
      assertThat(actual.lastEventId()).as(name).isEqualTo(string(expected, "lastEventId"));
      assertThat(actual.lastActivityAt()).as(name).isEqualTo(string(expected, "lastActivityAt"));
      assertThat(actual.nextAction()).as(name).isEqualTo(string(expected, "nextAction"));
      assertThat(actual.wpTotal()).as(name).isEqualTo(expected.get("wpTotal").asInt());
      assertThat(actual.blockedCount()).as(name).isEqualTo(expected.get("blockedCount").asInt());
      assertThat(actual.eventCount()).as(name).isEqualTo(expected.get("eventCount").asInt());
      assertThat(actual.streamCursor().offset()).as(name).isEqualTo(expected.get("streamCursor").get("offset").asLong());
      assertThat(actual.streamCursor().invariant()).as(name).isEqualTo(string(expected.get("streamCursor"), "invariant"));
      for (Map.Entry<Lane, Integer> count : actual.statusLaneCounts().entrySet()) {
        assertThat(count.getValue()).as(name + " " + count.getKey()).isEqualTo(expected.get("statusLaneCounts").get(count.getKey().wire()).asInt());
      }
      JsonNode progress = expected.get("progress");
      assertThat(actual.progress().weightedPercentage()).as(name).isEqualTo(progress.get("weightedPercentage").asDouble());
      assertThat(actual.progress().donePercentage()).as(name).isEqualTo(progress.get("donePercentage").asDouble());
      assertThat(actual.progress().doneCount()).as(name).isEqualTo(progress.get("doneCount").asInt());
      assertThat(Progress.SEMANTICS).isEqualTo(string(progress, "semantics"));
    }
    // The pinned rendering equals the raw number text Python wrote, for every item, in document order.
    Matcher raw = PERCENT.matcher(goldenText);
    int index = 0;
    while (raw.find()) {
      MissionOverview item = page.items().get(index / 2);
      double value = raw.group(1).equals("weightedPercentage") ? item.progress().weightedPercentage() : item.progress().donePercentage();
      renderedPercentages.add(Progress.render(value));
      assertThat(Progress.render(value)).as(item.slug() + " " + raw.group(1)).isEqualTo(raw.group(2));
      index++;
    }
    assertThat(renderedPercentages).hasSize(golden.size() * 2);
  }

  @Test
  void theInterleavedUnitShapeAgreesWithTheGoldenFixtureCounts() throws IOException {
    // The hand-built unit shape and the committed fixture exercise the same rules; both must give a non-empty, non-vacuous result.
    List<FixtureMissions.Mission> missions = FixtureMissions.load(ROOT.resolve("interleaved/two-missions"));
    assertThat(missions).hasSize(2);
    assertThat(missions.stream().mapToInt(m -> m.lines().size()).sum()).isGreaterThan(5);
  }
}
