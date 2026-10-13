package org.speckitty.missionstatus.conformance.port;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.PortFixtures.Planted;
import org.speckitty.missionstatus.testsupport.PortLevelTest;

/** AC-2b: paging with page size 1 through N Missions yields each exactly once in the contract order, equal {@code createdAt} included. */
public class Ac2bPagingTest {

  /** The contract order, computed from what was planted: {@code createdAt} descending as an instant, then {@code missionId} ascending. */
  private static List<String> contractOrder(List<Planted> planted) {
    return planted.stream()
        .sorted(Comparator.comparing((Planted p) -> OffsetDateTime.parse(p.createdAt()).toInstant(), Comparator.reverseOrder()).thenComparing(Planted::missionId))
        .map(Planted::slug)
        .toList();
  }

  private static FixtureSpec specOf(List<Planted> planted) {
    // Written in a scrambled order so that file or listing order cannot stand in for the contract order.
    List<FixtureSpec.Mission> missions = new ArrayList<>();
    for (int i = planted.size() - 1; i >= 0; i -= 2) {
      missions.add(PortFixtures.mission(planted.get(i).slug(), planted.get(i).missionId(), planted.get(i).createdAt(), null));
    }
    for (int i = planted.size() - 2; i >= 0; i -= 2) {
      missions.add(PortFixtures.mission(planted.get(i).slug(), planted.get(i).missionId(), planted.get(i).createdAt(), null));
    }
    return FixtureSpec.of(missions.toArray(FixtureSpec.Mission[]::new));
  }

  /** Walks the pages of size 1, asserting each page holds one item and the same count, and returns the slugs in the order met. */
  private static List<String> walk(MissionStatusQuery query, int expectedCount) {
    List<String> seen = new ArrayList<>();
    String cursor = null;
    int pages = 0;
    do {
      MissionPage page = query.missions(new PageRequest(1, cursor));
      assertThat(page.items()).hasSize(1);
      assertThat(page.pageSize()).isEqualTo(1);
      assertThat(page.missionCount()).isEqualTo(expectedCount);
      seen.add(page.items().getFirst().slug());
      cursor = page.nextPageCursor();
      pages++;
      assertThat(pages).as("a walk that does not end").isLessThanOrEqualTo(expectedCount);
    } while (cursor != null);
    return seen;
  }

  @PortLevelTest("AC-2b/page-size-one")
  public void pageSizeOneYieldsEveryMissionOnceInContractOrder() {
    List<Planted> planted =
        List.of(
            new Planted("m-oldest", PortFixtures.missionId(5), "2026-08-01T10:00:00+00:00"),
            new Planted("m-newest", PortFixtures.missionId(1), "2026-09-09T10:00:00+00:00"),
            new Planted("m-offset", PortFixtures.missionId(4), "2026-09-05T14:00:00+02:00"),
            new Planted("m-middle", PortFixtures.missionId(3), "2026-09-05T11:00:00+00:00"),
            new Planted("m-second", PortFixtures.missionId(2), "2026-09-08T10:00:00+00:00"),
            // The offset reverses the text order: as text "10:00+02:00" sorts after "09:00+00:00", as instants (08:00Z against 09:00Z) it sorts before.
            new Planted("m-text-a", PortFixtures.missionId(6), "2026-09-05T10:00:00+02:00"),
            new Planted("m-text-b", PortFixtures.missionId(7), "2026-09-05T09:00:00+00:00"));
    MissionStatusQuery query = PortFixtures.open(specOf(planted));

    List<String> walked = walk(query, planted.size());

    assertThat(walked).as("each Mission exactly once, in contract order").containsExactlyElementsOf(contractOrder(planted));
    assertThat(walked).doesNotHaveDuplicates().hasSize(planted.size());
    assertThat(walked.indexOf("m-text-b")).as("by instant, 09:00Z is newer than 08:00Z").isLessThan(walked.indexOf("m-text-a"));
    assertThat(query.missions(new PageRequest(200, null)).items()).extracting(item -> item.slug()).containsExactlyElementsOf(walked);
  }

  @PortLevelTest("AC-2b/equal-created-at")
  public void twoMissionsWithEqualCreatedAtAreOrderedByMissionIdAcrossPages() {
    String same = "2026-09-05T10:00:00+00:00";
    List<Planted> planted =
        List.of(
            new Planted("tie-c", PortFixtures.missionId(30), same),
            new Planted("tie-a", PortFixtures.missionId(10), same),
            new Planted("tie-b", PortFixtures.missionId(20), same),
            new Planted("after", PortFixtures.missionId(5), "2026-09-06T10:00:00+00:00"),
            new Planted("before", PortFixtures.missionId(40), "2026-09-04T10:00:00+00:00"));
    MissionStatusQuery query = PortFixtures.open(specOf(planted));

    List<String> walked = walk(query, planted.size());

    assertThat(walked).containsExactly("after", "tie-a", "tie-b", "tie-c", "before");
    assertThat(walked).containsExactlyElementsOf(contractOrder(planted));
  }
}
