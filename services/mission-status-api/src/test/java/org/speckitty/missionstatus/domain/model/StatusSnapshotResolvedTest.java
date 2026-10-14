package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** The parallel members of the snapshot (FR-020): the older constructor keeps the overview's reading, the new members are copies. */
class StatusSnapshotResolvedTest {

  private static Map<String, WpState> states() {
    return Map.of("WP01", new WpState(Lane.CLAIMED, "t", "E1", 0, null, null, null));
  }

  @Test
  void theFourArgumentConstructorLeavesTheParallelMembersEmptyAndTheLaneCountsAsTheyWere() {
    StatusSnapshot snapshot = new StatusSnapshot(states(), 1, "E1", "t");
    assertThat(snapshot.resolved()).isEmpty();
    assertThat(snapshot.lifecycleTypes()).isEmpty();
    assertThat(snapshot.laneCounts().get(Lane.CLAIMED)).isEqualTo(1);
  }

  @Test
  void theResolvedMapAndTheTypesAreCopiedUnmodifiableAndKeepTheirOrder() {
    Map<String, WpResolved> resolved = new LinkedHashMap<>();
    resolved.put("WP02", WpResolved.empty());
    resolved.put("WP01", WpResolved.empty());
    Set<String> types = new LinkedHashSet<>(java.util.List.of("PlanStarted", "Custom"));
    StatusSnapshot snapshot = new StatusSnapshot(states(), 1, "E1", "t", resolved, types);

    resolved.clear();
    types.clear();

    assertThat(snapshot.resolved().keySet()).containsExactly("WP02", "WP01");
    assertThat(snapshot.lifecycleTypes()).containsExactly("PlanStarted", "Custom");
    assertThatThrownBy(() -> snapshot.resolved().put("x", WpResolved.empty())).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> snapshot.lifecycleTypes().add("x")).isInstanceOf(UnsupportedOperationException.class);
  }

  @Test
  void theParallelMembersAreRequired() {
    assertThatThrownBy(() -> new StatusSnapshot(states(), 1, "E1", "t", null, Set.of())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new StatusSnapshot(states(), 1, "E1", "t", Map.of(), null)).isInstanceOf(NullPointerException.class);
  }
}
