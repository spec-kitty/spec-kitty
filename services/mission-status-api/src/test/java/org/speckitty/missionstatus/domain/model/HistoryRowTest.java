package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

/** One transition row of a Work Package's history (the oracle's {@code history_entries}); lane and stamp texts are stored, not projected. */
class HistoryRowTest {

  @Test
  void itCarriesTheNineMembersOfTheContractEntry() {
    HistoryRow row = new HistoryRow("WP01", "E1", "2026-09-01T10:00:00Z", "planned", "claimed", new Actor("claude", null, null), true, "why", "approved");
    assertThat(row.wpId()).isEqualTo("WP01");
    assertThat(row.eventId()).isEqualTo("E1");
    assertThat(row.at()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(row.fromLane()).isEqualTo("planned");
    assertThat(row.toLane()).isEqualTo("claimed");
    assertThat(row.actor().tool()).isEqualTo("claude");
    assertThat(row.force()).isTrue();
    assertThat(row.reason()).isEqualTo("why");
    assertThat(row.reviewVerdict()).isEqualTo("approved");
  }

  @Test
  void anyMemberButTheWorkPackageAndTheActorMayBeNull() {
    HistoryRow row = new HistoryRow("WP01", null, null, null, null, Actor.NONE, false, null, null);
    assertThat(row.eventId()).isNull();
    assertThat(row.at()).isNull();
    assertThat(row.fromLane()).isNull();
    assertThat(row.toLane()).isNull();
  }

  @Test
  void theWorkPackageAndTheActorAreRequired() {
    assertThatThrownBy(() -> new HistoryRow(null, "E", "t", "a", "b", Actor.NONE, false, null, null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new HistoryRow("WP01", "E", "t", "a", "b", null, false, null, null)).isInstanceOf(NullPointerException.class);
  }
}
