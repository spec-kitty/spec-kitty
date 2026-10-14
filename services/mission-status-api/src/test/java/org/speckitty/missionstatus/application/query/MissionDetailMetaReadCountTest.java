package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.adapter.in.http.detail.MissionDetailRowsTest;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.MetaReadCounter;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-1.8 on the real {@link MissionDetailQueryService} over {@link MissionReadModel}: the matched Mission's {@code meta.json} is read three
 * times on a warm ledger cache and four times on a cold one, every other Mission exactly once, whichever Mission of the listing is
 * requested; the stream route, which probes, reads the matched Mission twice before its feed starts (the control that makes the detail
 * route's count visible). The recorder counts only {@code (MISSION_META, READ)} accesses, per Mission directory.
 */
class MissionDetailMetaReadCountTest {

  private static final String FIRST = "01J01000000000000000000001";
  private static final String MIDDLE = "01J02000000000000000000002";
  private static final String LAST = "01J03000000000000000000003";

  /** Three Missions whose directories sort alpha, beta, gamma. */
  private static DetailFixture three() {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(
            PortFixtures.mission("alpha", FIRST, "2026-09-01T10:00:00+00:00", RouteLedger.moves(1, 1)),
            PortFixtures.mission("beta", MIDDLE, "2026-09-02T10:00:00+00:00", RouteLedger.moves(10, 2)),
            PortFixtures.mission("gamma", LAST, "2026-09-03T10:00:00+00:00", RouteLedger.moves(20, 1))),
        root -> {});
  }

  /** The reads of each Mission's {@code meta.json} the recorder has seen: directory name to count. */
  private static Map<String, Integer> readsPerMission(RecordingAllowlistAccess recorder) {
    Map<String, Integer> counts = new LinkedHashMap<>();
    for (Access access : recorder.accesses()) {
      if (access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ) {
        String name = access.path().split("/")[1];
        counts.merge(name, 1, Integer::sum);
      }
    }
    return counts;
  }

  @Test
  void theMatchedMissionIsReadFourTimesColdAndThreeTimesWarmAndEveryOtherOnce() {
    for (String[] target : new String[][] {{FIRST, "alpha"}, {MIDDLE, "beta"}, {LAST, "gamma"}}) {
      DetailFixture fixture = three();
      MissionDetailQueryService service = MissionDetailRowsTest.serviceOver(fixture);
      RecordingAllowlistAccess recorder = fixture.recorder();
      recorder.clear();

      service.mission(new MissionId(target[0]));
      Map<String, Integer> cold = readsPerMission(recorder);

      recorder.clear();
      service.mission(new MissionId(target[0]));
      Map<String, Integer> warm = readsPerMission(recorder);

      assertThat(cold.get(target[1])).as(target[1] + " cold").isEqualTo(4);
      assertThat(warm.get(target[1])).as(target[1] + " warm").isEqualTo(3);
      for (String other : new String[] {"alpha", "beta", "gamma"}) {
        if (!other.equals(target[1])) {
          assertThat(cold.get(other)).as(other + " cold, requesting " + target[1]).isEqualTo(1);
          assertThat(warm.get(other)).as(other + " warm, requesting " + target[1]).isEqualTo(1);
        }
      }
      assertThat(cold).as("a discovered-row floor: every Mission of the listing is counted").hasSize(3);
    }
  }

  @Test
  void theTotalsAlsoHoldThroughTheCounterOfTheHarness() {
    DetailFixture fixture = three();
    MissionDetailQueryService service = MissionDetailRowsTest.serviceOver(fixture);
    MetaReadCounter counter = new MetaReadCounter();
    service.mission(new MissionId(MIDDLE));
    counter.reset(fixture.recorder());

    service.mission(new MissionId(MIDDLE));

    assertThat(counter.count(fixture.recorder())).as("warm: 3 for the match and 1 for each of the other two").isEqualTo(5);
  }

  @Test
  void theStreamRouteReadsTheMatchedMissionOnceFewerThanTheDetailRouteColdBeforeItsFeedStarts() {
    DetailFixture fixture = three();
    fixture.recorder().clear();

    fixture.built().query().changesSince(StreamScope.mission(new MissionId(MIDDLE)), Optional.empty());

    Map<String, Integer> reads = readsPerMission(fixture.recorder());
    // the control: resolve looks the Mission up (one read) and then probes its ledger, which reads the Mission's meta.json again
    assertThat(reads.get("beta")).as("changesSince(one Mission) on a cold cache: " + reads).isEqualTo(3);
  }

  /** The ledger texts of the three Missions. */
  private static final class RouteLedger {
    static String moves(int fromId, int count) {
      StringBuilder text = new StringBuilder();
      for (int i = 0; i < count; i++) {
        text.append(Rows.status(Rows.id(fromId + i), String.format("2026-09-01T10:%02d:00Z", i), "WP" + String.format("%02d", i + 1), "planned", "claimed"));
      }
      return text.toString();
    }
  }
}
