package org.speckitty.missionstatus.domain.model;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * What the reduction produces: the per-work-package map (in the order the fold first met each work package, like the oracle's dict), the count of distinct transitions, the id of the last
 * transition in sorted order (null when none) and its {@code at}.
 */
public record StatusSnapshot(Map<String, WpState> workPackages, int eventCount, String lastEventId, String materializedAt) {

  public StatusSnapshot {
    Objects.requireNonNull(workPackages, "workPackages");
    Objects.requireNonNull(materializedAt, "materializedAt");
    workPackages = Collections.unmodifiableMap(new LinkedHashMap<>(workPackages));
  }

  /** The nine display lanes in the contract's order, every lane present and zero-filled; non-display lanes are not counted. */
  public Map<Lane, Integer> laneCounts() {
    Map<Lane, Integer> counts = new LinkedHashMap<>();
    for (Lane lane : Lane.displayLanes()) {
      counts.put(lane, 0);
    }
    for (WpState state : workPackages.values()) {
      counts.computeIfPresent(state.lane(), (lane, count) -> count + 1);
    }
    return counts;
  }
}
