package org.speckitty.missionstatus.domain.readmodel.overview;

import java.time.Instant;
import java.util.Collection;
import java.util.Map;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpState;

/** The derivations of FR-005, against {@code build_overview} and the contract text. */
public final class OverviewDeriver {

  private static final String REVIEW_THEN_ACCEPT = "Run /spec-kitty.review in your coding agent, then: spec-kitty accept --mission %s";
  private static final String CONSOLIDATE = "Run: spec-kitty consolidate --mission %s";
  private static final Lane[] ACTIVE = {Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW, Lane.APPROVED};
  private static final Lane[] OPEN = {Lane.PLANNED, Lane.BLOCKED};

  private OverviewDeriver() {}

  public static MissionOverview derive(MissionMeta meta, StatusSnapshot snapshot, StreamCursor streamCursor) {
    Map<Lane, Integer> counts = snapshot.laneCounts();
    int wpTotal = snapshot.workPackages().size();
    String friendlyName = PyText.isBlank(meta.friendlyName()) ? meta.slug() : PyText.strip(meta.friendlyName());
    return new MissionOverview(
        meta.missionId(),
        meta.missionId().mid8(),
        meta.slug(),
        friendlyName,
        meta.displayNumber(),
        meta.missionType(),
        meta.targetBranch(),
        meta.topology(),
        meta.createdAt(),
        counts,
        wpTotal,
        counts.get(Lane.BLOCKED),
        ProgressCalculator.compute(snapshot),
        lifecycleStatus(counts, wpTotal, meta.discardedAt(), meta.acceptedAt()),
        meta.acceptedAt(),
        meta.mergedAt(),
        meta.discardedAt(),
        snapshot.lastEventId(),
        lastActivityAt(snapshot.workPackages().values().stream().map(WpState::lastTransitionAt).toList()),
        snapshot.eventCount(),
        streamCursor,
        nextAction(meta.slug(), meta.acceptedAt(), meta.hasBaseline(), counts));
  }

  private static int count(Map<Lane, Integer> counts, Lane... lanes) {
    int total = 0;
    for (Lane lane : lanes) {
      total += counts.get(lane);
    }
    return total;
  }

  /** Contract rules in order: discarded, then no work packages, then active, planned, and finally active until accepted. */
  static LifecycleStatus lifecycleStatus(Map<Lane, Integer> counts, int wpTotal, String discardedAt, String acceptedAt) {
    if (discardedAt != null) {
      return LifecycleStatus.DISCARDED;
    }
    if (wpTotal == 0) {
      return LifecycleStatus.DRAFT;
    }
    if (count(counts, ACTIVE) > 0) {
      return LifecycleStatus.ACTIVE;
    }
    if (count(counts, OPEN) > 0) {
      return LifecycleStatus.PLANNED;
    }
    return acceptedAt != null ? LifecycleStatus.DONE : LifecycleStatus.ACTIVE;
  }

  /** The maximum by parsed instant, the first on ties, served as that value's own text; null when there is none. */
  public static String lastActivityAt(Collection<String> values) {
    String best = null;
    Instant bestInstant = null;
    for (String value : values) {
      if (value == null || value.isEmpty()) {
        continue;
      }
      Instant instant = Instants.parse(value);
      if (bestInstant == null || instant.isAfter(bestInstant)) {
        best = value;
        bestInstant = instant;
      }
    }
    return best;
  }

  static String nextAction(String slug, String acceptedAt, boolean hasBaseline, Map<Lane, Integer> counts) {
    if (acceptedAt != null) {
      return null;
    }
    if (hasBaseline) {
      return REVIEW_THEN_ACCEPT.formatted(slug);
    }
    int total = counts.values().stream().mapToInt(Integer::intValue).sum();
    boolean finished = total > 0 && count(counts, Lane.DONE, Lane.CANCELED) == total && counts.get(Lane.DONE) > 0;
    return finished ? CONSOLIDATE.formatted(slug) : null;
  }
}
