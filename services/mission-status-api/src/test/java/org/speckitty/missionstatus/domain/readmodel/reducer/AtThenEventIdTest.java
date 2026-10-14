package org.speckitty.missionstatus.domain.readmodel.reducer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.domain.readmodel.reducer.Events.move;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Lane;

class AtThenEventIdTest {

  private final EventOrdering ordering = new AtThenEventId();

  @Test
  void ordersByAtAsTextThenByEventId() {
    var early = move("B", "2026-09-01T09:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED);
    var late = move("A", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED);
    assertThat(ordering.compare(early, late)).isNegative();
    assertThat(ordering.compare(late, early)).isPositive();
    var sameAtLowId = move("A", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED);
    var sameAtHighId = move("B", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED);
    assertThat(ordering.compare(sameAtLowId, sameAtHighId)).isNegative();
    assertThat(ordering.compare(sameAtLowId, sameAtLowId)).isZero();
  }

  @Test
  void textOrderIsNotInstantOrder() {
    var plusTwo = move("A", "2026-09-01T10:30:00+02:00", "WP01", Lane.PLANNED, Lane.CLAIMED);
    var zulu = move("B", "2026-09-01T09:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED);
    assertThat(ordering.compare(zulu, plusTwo)).isNegative();
  }
}
