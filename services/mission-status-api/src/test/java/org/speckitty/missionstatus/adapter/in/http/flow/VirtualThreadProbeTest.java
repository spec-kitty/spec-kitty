package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/** AC-9h, JVM run: the handler of {@code /api/v1/missions} and the handler and the pump of the event stream run on virtual threads. */
class VirtualThreadProbeTest {

  @Test
  void theMissionsHandlerTheStreamHandlerAndTheStreamPumpAllRunOnVirtualThreads() {
    FixtureSpec spec = FixtureSpec.of(PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")));
    try (StreamRig rig = StreamRig.over(FilesystemFixtureFactory.fromSpec(spec))) {
      assertThat(rig.http.get("/api/v1/missions").status()).isEqualTo(200);
      assertThat(rig.http.get("/api/v1/project").status()).isEqualTo(200);
      try (SseClient client = rig.scoped(Rows.ALPHA_ID)) {
        rig.append("alpha", Rows.status(Rows.id(2), "2026-09-01T10:01:00Z", "WP01", "claimed", "in_progress"));
        rig.tick();
        assertThat(client.nextEvent(StreamRig.BOUND)).isNotNull();
      }

      assertThat(rig.spy.missionsThreads()).as("the probe saw the missions handler").isNotEmpty().containsOnly(true);
      assertThat(rig.spy.projectThreads()).isNotEmpty().containsOnly(true);
      assertThat(rig.spy.subscribeThreads()).as("the probe saw the stream handler").isNotEmpty().containsOnly(true);
      assertThat(rig.spy.nextThreads()).as("the probe saw the connection's own thread").isNotEmpty().containsOnly(true);
    }
  }

  @Test
  void theProbeSeesAPlatformThread() throws Exception {
    org.speckitty.missionstatus.testsupport.http.SpyQuery spy =
        new org.speckitty.missionstatus.testsupport.http.SpyQuery(FilesystemFixtureFactory.fromSpec(FixtureSpec.of()).query());
    Thread platform = Thread.ofPlatform().start(() -> spy.missions(new org.speckitty.missionstatus.application.query.port.in.dto.PageRequest(null, null)));
    platform.join();

    assertThat(spy.missionsThreads()).as("positive control: a platform thread records false").containsExactly(false);
  }
}
