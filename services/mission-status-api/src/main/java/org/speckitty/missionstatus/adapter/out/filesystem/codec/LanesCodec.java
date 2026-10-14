package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.LanesManifest;
import org.speckitty.missionstatus.domain.model.LanesResult;

/**
 * The pure decoder of a {@code lanes.json} (FR-003, rows W3 and SK-351): bytes to a {@link LanesResult}, as the oracle's
 * {@code read_lanes_json} reads a file with {@code LanesManifest.from_dict}. The JSON is read the way Python's {@code json.loads}
 * reads it ({@link PythonJson}); the bytes must be strict UTF-8, and a byte order mark makes the document unreadable, as it does there.
 *
 * <p>The oracle accepts a few shapes it then misuses (a {@code wp_ids} that is a string is split into characters; a non-string slug is
 * formatted into a branch name). This decoder is stricter on those: a lane id, a Work Package id or a Mission slug that is not a
 * string, and a {@code wp_ids} that is not a list, are {@link LanesResult.Corrupt}. A refusal is the safe side: the route answers 500
 * {@code source_unreadable} rather than serving a workspace it cannot reproduce.
 */
public final class LanesCodec {

  private static final String MISSION_SLUG = "mission_slug";
  /** LEGACY (D-115): the one pre-identity slug key, recognised only to refuse the legacy shape of SK-351 and to know the oracle's old frontmatter key. */
  static final String LEGACY_SLUG_KEY = "feature_slug";

  private static final List<String> REQUIRED = List.of("version", "mission_branch", "target_branch", "lanes", "computed_at", "computed_from");

  private LanesCodec() {}

  /** Decodes the bytes of one {@code lanes.json}. */
  public static LanesResult decode(byte[] bytes) {
    if (!(StrictUtf8.decode(bytes) instanceof StrictUtf8.Decoded.Text decoded)) {
      return new LanesResult.Corrupt();
    }
    Object document;
    try {
      document = PythonJson.parse(decoded.text());
    } catch (PythonJson.Invalid invalid) {
      return new LanesResult.Corrupt();
    }
    if (!(document instanceof Map<?, ?> object)) {
      return new LanesResult.Corrupt();
    }
    if (!object.containsKey(MISSION_SLUG)) {
      return object.containsKey(LEGACY_SLUG_KEY) ? new LanesResult.Legacy() : new LanesResult.Corrupt();
    }
    return manifest(object);
  }

  private static LanesResult manifest(Map<?, ?> object) {
    if (!(object.get(MISSION_SLUG) instanceof String slug) || !object.keySet().containsAll(REQUIRED) || !collapseReportIsReadable(object)) {
      return new LanesResult.Corrupt();
    }
    if (object.get("lanes") instanceof Map<?, ?> emptyMapping && emptyMapping.isEmpty()) {
      return new LanesResult.Manifest(new LanesManifest(slug, object.get("mission_id") instanceof String id ? id : null, List.of()));
    }
    if (!(object.get("lanes") instanceof List<?> rawLanes)) {
      return new LanesResult.Corrupt();
    }
    List<LanesManifest.Lane> lanes = new ArrayList<>();
    for (Object rawLane : rawLanes) {
      LanesManifest.Lane lane = lane(rawLane);
      if (lane == null) {
        return new LanesResult.Corrupt();
      }
      lanes.add(lane);
    }
    String missionId = object.get("mission_id") instanceof String id ? id : null;
    return new LanesResult.Manifest(new LanesManifest(slug, missionId, lanes));
  }

  /** {@code ExecutionLane.from_dict}: a mapping with {@code lane_id} and {@code wp_ids}, and iterable optional members. */
  private static LanesManifest.Lane lane(Object rawLane) {
    if (!(rawLane instanceof Map<?, ?> lane) || !(lane.get("lane_id") instanceof String laneId) || !(lane.get("wp_ids") instanceof List<?> rawIds)) {
      return null;
    }
    List<String> wpIds = new ArrayList<>();
    for (Object id : rawIds) {
      if (!(id instanceof String text)) {
        return null;
      }
      wpIds.add(text);
    }
    for (String optional : List.of("write_scope", "predicted_surfaces", "depends_on_lanes")) {
      if (lane.containsKey(optional) && !iterable(lane.get(optional))) {
        return null;
      }
    }
    return new LanesManifest.Lane(laneId, wpIds);
  }

  /** What Python's {@code tuple(x)} accepts: a list, a string or a mapping (not null, a number or a boolean). */
  private static boolean iterable(Object value) {
    return value instanceof List<?> || value instanceof String || value instanceof Map<?, ?>;
  }

  /** The optional {@code collapse_report} is parsed by the oracle too: a mapping whose {@code events} are mappings with four keys. */
  private static boolean collapseReportIsReadable(Map<?, ?> object) {
    if (!object.containsKey("collapse_report")) {
      return true;
    }
    if (!(object.get("collapse_report") instanceof Map<?, ?> report)) {
      return false;
    }
    if (!report.containsKey("events")) {
      return true;
    }
    if (!(report.get("events") instanceof List<?> events)) {
      return false;
    }
    for (Object event : events) {
      if (!(event instanceof Map<?, ?> entry) || !entry.keySet().containsAll(List.of("wp_a", "wp_b", "rule", "evidence"))) {
        return false;
      }
    }
    return true;
  }
}
