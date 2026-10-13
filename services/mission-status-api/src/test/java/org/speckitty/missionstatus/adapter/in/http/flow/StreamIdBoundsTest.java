package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.speckitty.missionstatus.adapter.in.http.contract.ContractValidator;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;

/**
 * Landing fold A5: the contract bounds {@code eventId} and {@code wpId} of a stream event to 64 characters. A row whose id is longer is
 * dropped with one {@code projection_refused} diagnostic, as a row whose {@code at} is no instant is (J6), and the next row is delivered.
 * The oracle forwards such an id; the divergence is recorded in the service README.
 */
@ExtendWith(OutputCaptureExtension.class)
class StreamIdBoundsTest {

  private static final String MID8 = Rows.ALPHA_ID.substring(0, 8);
  private static final ContractValidator CONTRACT = ContractValidator.fromClasspath();

  private static FixtureSpec spec() {
    return FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
  }

  @Test
  void aRowWithAnEventIdOrAWpIdOverSixtyFourCharactersIsDroppedWithOneDiagnosticEach(CapturedOutput output) throws Exception {
    String longEventId = "E".repeat(65);
    String longWpId = "WP" + "1".repeat(63);
    try (StreamRig rig = StreamRig.of(spec());
        SseClient client = rig.scoped(Rows.ALPHA_ID)) {
      rig.append("alpha", Rows.status(longEventId, "2026-09-01T11:00:00Z", "WP01", "claimed", "in_progress"));
      rig.append("alpha", Rows.status(Rows.id(3), "2026-09-01T11:30:00Z", longWpId, "planned", "claimed"));
      rig.append("alpha", Rows.lifecycle("L".repeat(65), "PlanStarted", "2026-09-01T11:45:00Z"));
      rig.append("alpha", Rows.status("F".repeat(64), "2026-09-01T11:50:00Z", "WP01", "claimed", "in_progress"));
      rig.append("alpha", Rows.status(Rows.id(5), "2026-09-01T12:00:00Z", "WP01", "in_progress", "for_review"));
      rig.tick();

      SseClient.Event atTheBound = client.nextEvent(StreamRig.BOUND);
      assertThat(atTheBound.data()).as("an id of exactly 64 characters is served").contains("F".repeat(64));
      assertThat(CONTRACT.validateEventData("status-transition", atTheBound.data())).isEmpty();
      SseClient.Event next = client.nextEvent(StreamRig.BOUND);
      assertThat(next.data()).contains(Rows.id(5));
      assertThat(client.next(StreamRig.QUIET)).isNull();
      assertThat(client.transcript()).doesNotContain(longEventId).doesNotContain(longWpId).doesNotContain("L".repeat(65));
      assertThat(output.getAll().split("code=projection_refused mid8=" + MID8, -1)).as("one diagnostic per dropped row").hasSize(4);
    }
  }
}
