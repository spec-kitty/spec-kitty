package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-1.8 for the Work Package detail: the matched Mission's {@code meta.json} is read three times on a warm ledger cache and four times on a
 * cold one, every other Mission exactly once, whichever Mission of the listing is requested. The route takes the snapshot of the head the
 * way {@code getMission} does: no second probe and no second stamp (a control for the discovered rows: the count covers all three Missions).
 */
class WorkPackageDetailMetaReadCountTest {

  private static final String FIRST = "01J01000000000000000000001";
  private static final String MIDDLE = "01J02000000000000000000002";
  private static final String LAST = "01J03000000000000000000003";

  private static String moves(int fromId) {
    return Rows.status(Rows.id(fromId), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");
  }

  /** Three Missions whose directories sort alpha, beta, gamma, each with the Work Package file WP01. */
  private static DetailFixture three() {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(
            PortFixtures.mission("alpha", FIRST, "2026-09-01T10:00:00+00:00", moves(1)),
            PortFixtures.mission("beta", MIDDLE, "2026-09-02T10:00:00+00:00", moves(10)),
            PortFixtures.mission("gamma", LAST, "2026-09-03T10:00:00+00:00", moves(20))),
        root -> {
          for (String mission : new String[] {"alpha", "beta", "gamma"}) {
            MissionDetailServedRoute.write(root, mission, "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One"));
          }
        });
  }

  /** The reads of each Mission's {@code meta.json} the recorder has seen: directory name to count. */
  private static Map<String, Integer> readsPerMission(RecordingAllowlistAccess recorder) {
    Map<String, Integer> counts = new LinkedHashMap<>();
    for (Access access : recorder.accesses()) {
      if (access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ) {
        counts.merge(access.path().split("/")[1], 1, Integer::sum);
      }
    }
    return counts;
  }

  @Test
  void theMatchedMissionIsReadFourTimesColdAndThreeTimesWarmAndEveryOtherOnce() {
    for (String[] target : new String[][] {{FIRST, "alpha"}, {MIDDLE, "beta"}, {LAST, "gamma"}}) {
      DetailFixture fixture = three();
      WorkPackageDetailQueryService service = DetailRoute.serviceOver(fixture);
      RecordingAllowlistAccess recorder = fixture.recorder();
      recorder.clear();

      service.workPackageDetail(new MissionId(target[0]), new WpId("WP01"));
      Map<String, Integer> cold = readsPerMission(recorder);

      recorder.clear();
      service.workPackageDetail(new MissionId(target[0]), new WpId("WP01"));
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
  void theCountDoesNotDependOnTheNumberOfWorkPackagesOrOnTheSourcesOfTheDetail() {
    DetailFixture fixture = DetailRoute.fixture(root -> {
      DetailRoute.write(root, "tasks.md", "## WP01\n- [ ] T001 Title\n");
      DetailRoute.write(root, "lanes.json", DetailRoute.lanes("alpha", "lane-a:WP01"));
      DetailRoute.write(root, "tasks/WP01-one/review-cycle-1.md", DetailRoute.cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
    });
    WorkPackageDetailQueryService service = DetailRoute.serviceOver(fixture);
    service.workPackageDetail(new MissionId(DetailRoute.ID), new WpId("WP01"));
    fixture.recorder().clear();

    service.workPackageDetail(new MissionId(DetailRoute.ID), new WpId("WP01"));

    assertThat(readsPerMission(fixture.recorder())).containsOnlyKeys("alpha").containsEntry("alpha", 3);
  }
}
