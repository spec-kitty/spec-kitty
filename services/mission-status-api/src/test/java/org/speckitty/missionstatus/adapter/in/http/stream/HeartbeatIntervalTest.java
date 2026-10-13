package org.speckitty.missionstatus.adapter.in.http.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * Landing fold R-6: {@code mission-status.stream.heartbeat-interval} is validated at start, as {@code max-connections} is. A zero or negative
 * interval would make every idle wait return at once and the writer loop spin, writing a heartbeat as fast as it can on every open stream.
 */
class HeartbeatIntervalTest {

  private static FixtureSpec spec() {
    return FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
  }

  private static Throwable rootOf(Throwable failure) {
    Throwable root = failure;
    while (root.getCause() != null && root.getCause() != root) {
      root = root.getCause();
    }
    return root;
  }

  @Test
  void aZeroOrNegativeIntervalRefusesToStart() {
    for (String interval : new String[] {"PT0S", "-PT1S", "PT-0.5S"}) {
      assertThatThrownBy(() -> StreamRig.of(spec(), "mission-status.stream.heartbeat-interval=" + interval).close())
          .as(interval)
          .satisfies(failure -> assertThat(rootOf(failure)).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("heartbeat-interval"));
    }
  }

  @Test
  void aPositiveIntervalStarts() {
    try (StreamRig rig = StreamRig.of(spec(), "mission-status.stream.heartbeat-interval=PT0.05S")) {
      assertThat(rig.http.port()).isPositive();
    }
  }
}
