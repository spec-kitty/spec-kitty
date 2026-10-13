package org.speckitty.missionstatus.testsupport;

import java.util.LinkedHashMap;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.Progress;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.testsupport.CanonicalJson.Num;

/**
 * The test-side serialiser: the application's result as a tree of the contract's member names, to be written by
 * {@link CanonicalJson#toBytes}. It is independent of the production mapper (which is another work package's), so the golden suite
 * and the later HTTP run cannot agree by sharing a bug. A percentage is written the way Python's {@code json.dumps} writes a float
 * ({@link Progress#render}); every other number is an integer.
 */
public final class GoldenDocuments {

  private GoldenDocuments() {}

  /** The contract's {@code Project} document. */
  public static Map<String, Object> project(ProjectHeader header) {
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("name", header.name());
    out.put("missionCount", number(header.missionCount()));
    out.put("specKittyVersion", header.specKittyVersion());
    out.put("schemaVersion", header.schemaVersion() == null ? null : number(header.schemaVersion()));
    out.put("health", header.health().wire());
    out.put("currentBranch", header.currentBranch());
    out.put("lastActivityAt", header.lastActivityAt());
    return out;
  }

  /** The contract's {@code MissionOverviewPage} document. */
  public static Map<String, Object> page(MissionPage page) {
    Map<String, Object> pageInfo = new LinkedHashMap<>();
    pageInfo.put("hasNextPage", page.nextPageCursor() != null);
    pageInfo.put("nextPageCursor", page.nextPageCursor());
    pageInfo.put("pageSize", number(page.pageSize()));
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("items", page.items().stream().map(GoldenDocuments::overview).toList());
    out.put("pageInfo", pageInfo);
    return out;
  }

  /** The contract's {@code MissionOverview} document. */
  public static Map<String, Object> overview(MissionOverview item) {
    Map<String, Object> counts = new LinkedHashMap<>();
    for (Lane lane : Lane.values()) {
      if (lane.isDisplay()) {
        counts.put(lane.wire(), number(item.statusLaneCounts().getOrDefault(lane, 0)));
      }
    }
    Map<String, Object> progress = new LinkedHashMap<>();
    progress.put("weightedPercentage", new Num(Progress.render(item.progress().weightedPercentage())));
    progress.put("donePercentage", new Num(Progress.render(item.progress().donePercentage())));
    progress.put("doneCount", number(item.progress().doneCount()));
    progress.put("semantics", Progress.SEMANTICS);
    Map<String, Object> cursor = new LinkedHashMap<>();
    cursor.put("offset", new Num(Long.toString(item.streamCursor().offset())));
    cursor.put("invariant", item.streamCursor().invariant());
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("missionId", item.missionId().value());
    out.put("mid8", item.mid8());
    out.put("slug", item.slug());
    out.put("friendlyName", item.friendlyName());
    out.put("displayNumber", item.displayNumber() == null ? null : number(item.displayNumber()));
    out.put("missionType", item.missionType());
    out.put("targetBranch", item.targetBranch());
    out.put("topology", item.topology().wire());
    out.put("createdAt", item.createdAt());
    out.put("statusLaneCounts", counts);
    out.put("wpTotal", number(item.wpTotal()));
    out.put("blockedCount", number(item.blockedCount()));
    out.put("progress", progress);
    out.put("lifecycleStatus", item.lifecycleStatus().wire());
    out.put("acceptedAt", item.acceptedAt());
    out.put("mergedAt", item.mergedAt());
    out.put("discardedAt", item.discardedAt());
    out.put("lastEventId", item.lastEventId());
    out.put("lastActivityAt", item.lastActivityAt());
    out.put("eventCount", number(item.eventCount()));
    out.put("streamCursor", cursor);
    out.put("nextAction", item.nextAction());
    return out;
  }

  private static Num number(long value) {
    return new Num(Long.toString(value));
  }
}
