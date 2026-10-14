package org.speckitty.missionstatus.domain.model;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * What the reduction produces: the per-work-package map (in the order the fold first met each work package, like the oracle's dict), the count of distinct transitions, the id of the last
 * transition in sorted order (null when none) and its {@code at}.
 *
 * <p>Two parallel members carry what the detail routes need and no overview derivation reads (FR-020, AC-20.2): {@code resolved} is the
 * resolved state of each work package (the fold's work packages and every work package that has a history row), and {@code lifecycleTypes}
 * is the set of text {@code event_type}s of the ledger rows, in the order first met (the oracle's {@code _lifecycle_types}; D-98). The
 * four-argument constructor leaves both empty, which is what the cache-growth floor and the older tests rely on.
 */
public record StatusSnapshot(
    Map<String, WpState> workPackages, int eventCount, String lastEventId, String materializedAt, Map<String, WpResolved> resolved, Set<String> lifecycleTypes) {

  public StatusSnapshot {
    Objects.requireNonNull(workPackages, "workPackages");
    Objects.requireNonNull(materializedAt, "materializedAt");
    Objects.requireNonNull(resolved, "resolved");
    Objects.requireNonNull(lifecycleTypes, "lifecycleTypes");
    workPackages = Collections.unmodifiableMap(new LinkedHashMap<>(workPackages));
    resolved = Collections.unmodifiableMap(new LinkedHashMap<>(resolved));
    lifecycleTypes = Collections.unmodifiableSet(new LinkedHashSet<>(lifecycleTypes));
  }

  /** A snapshot with no resolved state and no lifecycle types. */
  public StatusSnapshot(Map<String, WpState> workPackages, int eventCount, String lastEventId, String materializedAt) {
    this(workPackages, eventCount, lastEventId, materializedAt, Map.of(), Set.of());
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
