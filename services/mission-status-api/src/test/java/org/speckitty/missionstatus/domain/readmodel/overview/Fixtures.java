package org.speckitty.missionstatus.domain.readmodel.overview;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.Topology;
import org.speckitty.missionstatus.domain.model.WpState;

/** Test builders with synthetic ULIDs. */
public final class Fixtures {

  private Fixtures() {}

  public static String ulid(int number) {
    return "01J0" + String.format("%022d", number);
  }

  public static MissionMeta meta(int number, String createdAt) {
    return new MissionMeta(new MissionId(ulid(number)), "mission-" + number, "Mission " + number, null, "software-dev", "main", Topology.UNKNOWN, createdAt, null, null, null, false);
  }

  public static MissionMeta meta(String slug, String friendly, String accepted, String discarded, boolean baseline) {
    return new MissionMeta(new MissionId(ulid(1)), slug, friendly, 12, "software-dev", "main", Topology.LANES, "2026-09-01T10:00:00Z", accepted, null, discarded, baseline);
  }

  public static WpState wp(Lane lane, String lastTransitionAt) {
    return new WpState(lane, lastTransitionAt, lastTransitionAt == null ? null : "E-" + lane.wire(), 0, null, null, null);
  }

  /** A snapshot of work packages WP01.. in the given lanes, all transitioned at the same instant. */
  public static StatusSnapshot snapshot(Lane... lanes) {
    Map<String, WpState> states = new LinkedHashMap<>();
    for (int i = 0; i < lanes.length; i++) {
      states.put(String.format("WP%02d", i + 1), wp(lanes[i], "2026-09-01T10:00:00Z"));
    }
    return new StatusSnapshot(states, lanes.length, lanes.length == 0 ? null : "LAST", lanes.length == 0 ? "" : "2026-09-01T10:00:00Z");
  }

  public static MissionOverview overview(int number, String createdAt) {
    return OverviewDeriver.derive(meta(number, createdAt), snapshot(), StreamCursor.start());
  }

  public static List<MissionOverview> overviews(String... createdAtByNumber) {
    return java.util.stream.IntStream.range(0, createdAtByNumber.length).mapToObj(i -> overview(i + 1, createdAtByNumber[i])).toList();
  }
}
